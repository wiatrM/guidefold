#!/usr/bin/env python3
"""Exercise a real CPU HPA on the dedicated kind fixture, not a capacity benchmark."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.k8s_e2e import NAME, CONTEXT, LOCAL, CHART, command

URL = "https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.8.1/components.yaml"
SHA = "4a672c4891902573a3ff753cece5de1bf1f55dd053403dfec39df9d1636b7ff1"


def main():
    kubeconfig = ROOT / ".guidefold/kubeconfig"
    kubectl = ["kubectl", "--kubeconfig", kubeconfig, "--context", CONTEXT]

    def k(*parts, data=None):
        return command(kubectl + list(parts), data)

    namespace = json.loads(k("get", "namespace", NAME, "-o", "json"))
    if namespace["metadata"].get("labels", {}).get("guidefold.e2e") != "owned":
        raise RuntimeError(
            "refusing to modify a cluster without the owned E2E namespace"
        )
    raw = urllib.request.urlopen(URL, timeout=30).read()
    if hashlib.sha256(raw).hexdigest() != SHA:
        raise RuntimeError("metrics-server manifest integrity mismatch")
    docs = list(yaml.safe_load_all(raw))
    for obj in docs:
        if obj["kind"] == "Deployment":
            # Only the local kind kubelet uses a self-signed serving certificate.
            obj["spec"]["template"]["spec"]["containers"][0]["args"].append(
                "--kubelet-insecure-tls"
            )
    k(
        "apply",
        "-f",
        "-",
        data=json.dumps({"apiVersion": "v1", "kind": "List", "items": docs}),
    )
    k(
        "-n",
        "kube-system",
        "rollout",
        "status",
        "deployment/metrics-server",
        "--timeout=150s",
    )
    svc = json.loads(k("-n", NAME, "get", "service", "guidefold", "-o", "json"))
    release = svc["spec"]["selector"]["app.kubernetes.io/instance"]
    values = yaml.safe_load((LOCAL / (release + ".yaml")).read_text())
    values["autoscaling"] = {
        "enabled": True,
        "minReplicas": 2,
        "maxReplicas": 4,
        "cpuUtilization": 2,
    }
    path = LOCAL / "hpa-test-values.yaml"
    path.write_text(yaml.safe_dump(values))
    helm = ["helm", "--kubeconfig", kubeconfig, "--kube-context", CONTEXT, "-n", NAME]
    command(helm + ["upgrade", release, CHART, "-f", path])
    script = """import json,time,urllib.request,urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
token=Path('/run/credentials/api-token').read_text().strip()
end=time.monotonic()+75
def worker(_):
    counts={}
    while time.monotonic()<end:
        req=urllib.request.Request('http://guidefold:8080/v1/search',data=b'{"query":"postgres production","deadline_ms":1000}',headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=3) as r: r.read(); status=r.status
        except urllib.error.HTTPError as e: e.read(); status=e.code
        except urllib.error.URLError: status=0
        counts[status]=counts.get(status,0)+1
    return counts
with ThreadPoolExecutor(max_workers=6) as e: print(json.dumps(list(e.map(worker,range(6)))))
"""
    observations = []
    passed = False
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            traffic = executor.submit(
                k, "-n", NAME, "exec", "-i", "client", "--", "python", "-", data=script
            )
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                hpa = json.loads(k("-n", NAME, "get", "hpa", release, "-o", "json"))
                deployment = json.loads(
                    k("-n", NAME, "get", "deployment", release, "-o", "json")
                )
                row = {
                    "desired": hpa.get("status", {}).get("desiredReplicas"),
                    "available": deployment.get("status", {}).get(
                        "availableReplicas", 0
                    ),
                    "active": any(
                        c["type"] == "ScalingActive" and c["status"] == "True"
                        for c in hpa.get("status", {}).get("conditions", [])
                    ),
                }
                observations.append(row)
                if row["active"] and row["desired"] == 4 and row["available"] >= 4:
                    passed = True
                    break
                time.sleep(5)
            counts = json.loads(traffic.result(timeout=120))
    finally:
        # Restore the test installation's original scaling config, not a shared release.
        command(helm + ["upgrade", release, CHART, "-f", LOCAL / (release + ".yaml")])
    result = {
        "schema_version": 1,
        "kind": "kind_cpu_hpa_e2e",
        "passed": passed,
        "metrics_server_manifest_sha256": SHA,
        "target_cpu_percent": 2,
        "max_replicas": 4,
        "observations": observations,
        "traffic_status_counts": counts,
        "capacity_benchmark": False,
        "production_target_calibrated": False,
        "gpu_scaling_exercised": False,
    }
    out = ROOT / ".guidefold/checks/kubernetes-hpa.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k not in ("observations", "traffic_status_counts")
            }
        ),
        flush=True,
    )
    if not passed:
        raise AssertionError(
            "HPA did not bring four API replicas online under test load"
        )


if __name__ == "__main__":
    main()
