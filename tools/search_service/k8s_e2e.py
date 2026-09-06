#!/usr/bin/env python3
"""Real kind/Postgres release E2E. Touches only guidefold-release-e2e resources."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.k8s_release import build_manifest, canonical, digest, selector

NAME = "guidefold-release-e2e"
CONTEXT = "kind-" + NAME
LOCAL = ROOT / ".guidefold/k8s-e2e"
CHART = ROOT / "deploy/k8s/chart"
IMAGE = "guidefold-search:k8s-e2e"
DB_IMAGE = "paradedb/paradedb:0.25.6-pg17"
CLIENT_IMAGE = "python:3.12-alpine"


def command(args, data=None, timeout=300):
    result = subprocess.run(
        [str(x) for x in args],
        input=data,
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError(
            "command failed: "
            + " ".join(str(x) for x in args[:4])
            + "\n"
            + result.stderr[-4000:]
        )
    return result.stdout


def run(args):
    LOCAL.mkdir(parents=True, exist_ok=True)
    kubeconfig = ROOT / ".guidefold/kubeconfig"
    kubectl = ["kubectl", "--kubeconfig", kubeconfig, "--context", CONTEXT, "-n", NAME]
    helm = ["helm", "--kubeconfig", kubeconfig, "--kube-context", CONTEXT, "-n", NAME]

    def k(*parts, data=None):
        return command(kubectl + list(parts), data)

    def apply(obj):
        return k("apply", "-f", "-", data=json.dumps(obj))

    checks = []

    def record(name, condition, **details):
        checks.append({"name": name, "passed": bool(condition), **details})
        if not condition:
            raise AssertionError((name, details))
        print(json.dumps({"check": name, "passed": True}), flush=True)

    completed = False
    try:
        clusters = command(["kind", "get", "clusters"]).splitlines()
        if NAME not in clusters:
            command(
                [
                    "kind",
                    "create",
                    "cluster",
                    "--name",
                    NAME,
                    "--image",
                    "kindest/node:v1.36.1",
                    "--kubeconfig",
                    kubeconfig,
                    "--wait",
                    "60s",
                ]
            )
        elif not args.reuse:
            raise RuntimeError(
                "dedicated cluster already exists; pass --reuse to use it"
            )
        existing = k("get", "namespace", NAME, "--ignore-not-found", "-o", "json")
        if existing.strip():
            ns = json.loads(existing)
            if (
                not args.reset
                or ns["metadata"].get("labels", {}).get("guidefold.e2e") != "owned"
            ):
                raise RuntimeError(
                    "existing test namespace requires --reset and ownership label"
                )
            k("delete", "namespace", NAME, "--wait=true", "--timeout=120s")
        apply(
            {
                "apiVersion": "v1",
                "kind": "Namespace",
                "metadata": {"name": NAME, "labels": {"guidefold.e2e": "owned"}},
            }
        )
        if not args.skip_build:
            command(
                [
                    "docker",
                    "build",
                    "-f",
                    "services/search/Dockerfile",
                    "-t",
                    IMAGE,
                    ".",
                ]
            )
        command([sys.executable, "tools/search_service/dev.py", "prepare"])
        from tools.search_service.index import with_router_index
        from tools.serve_spike.server import load_cli_snapshot

        cli, _ = load_cli_snapshot(ROOT / "skills/guidefold/scripts/guidefold")
        original = json.loads((ROOT / ".guidefold/compose/snapshot.json").read_text())
        bundles, manifests = [], []
        for i in range(3):
            bundle = deepcopy(original)
            # Synthetic release fixtures, not quality corpora or a new ranking variant.
            bundle["snapshot"]["revision"] = "k8s-release-fixture-" + str(i)
            bundle["sha256"] = digest(bundle["snapshot"])
            bundle = with_router_index(cli, bundle)
            artifact = "guidefold-artifact:k8s-e2e-" + str(i)
            bundles.append(bundle)
            manifests.append(
                build_manifest(bundle, "test", IMAGE, artifact, development=True)
            )
            folder = LOCAL / ("artifact-" + str(i))
            folder.mkdir(exist_ok=True)
            (folder / "snapshot.json").write_bytes(canonical(bundle))
            (folder / "Dockerfile").write_text(
                "FROM " + IMAGE + "\nCOPY snapshot.json /input/snapshot.json\n"
            )
            if i < 2:
                command(
                    [
                        "docker",
                        "build",
                        "--provenance=false",
                        "--platform=linux/amd64",
                        "-t",
                        artifact,
                        folder,
                    ]
                )
        command(["docker", "pull", CLIENT_IMAGE])
        command(["docker", "pull", DB_IMAGE])
        archive = LOCAL / "images.tar"
        command(
            [
                "docker",
                "image",
                "save",
                "--platform=linux/amd64",
                "-o",
                archive,
                IMAGE,
                DB_IMAGE,
                CLIENT_IMAGE,
                manifests[0]["artifact_image"],
                manifests[1]["artifact_image"],
            ]
        )
        command(["kind", "load", "image-archive", "--name", NAME, archive])
        token = secrets.token_urlsafe(32)
        admin_password = secrets.token_urlsafe(32)
        app_password = secrets.token_urlsafe(32)
        apply(
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": "guidefold-credentials"},
                "stringData": {
                    "app-password": app_password,
                    "api-token": token,
                },
            }
        )
        apply(
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": "guidefold-operator-credentials"},
                "stringData": {
                    "admin-password": admin_password,
                    "app-password": app_password,
                },
            }
        )
        apply(
            {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {"name": "db-data"},
                "spec": {
                    "accessModes": ["ReadWriteOnce"],
                    "resources": {"requests": {"storage": "5Gi"}},
                },
            }
        )
        apply(
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "db"},
                "spec": {
                    "replicas": 1,
                    "strategy": {"type": "Recreate"},
                    "selector": {"matchLabels": {"app": "guidefold-test-db"}},
                    "template": {
                        "metadata": {"labels": {"app": "guidefold-test-db"}},
                        "spec": {
                            "containers": [
                                {
                                    "name": "db",
                                    "image": DB_IMAGE,
                                    "imagePullPolicy": "IfNotPresent",
                                    "env": [
                                        {"name": "POSTGRES_DB", "value": "guidefold"},
                                        {
                                            "name": "POSTGRES_PASSWORD_FILE",
                                            "value": "/run/credentials/admin-password",
                                        },
                                        {
                                            "name": "PGDATA",
                                            "value": "/var/lib/postgresql/data/pgdata",
                                        },
                                    ],
                                    "ports": [{"containerPort": 5432}],
                                    "resources": {
                                        "requests": {"cpu": "250m", "memory": "512Mi"},
                                        "limits": {"memory": "2Gi"},
                                    },
                                    "readinessProbe": {
                                        "exec": {
                                            "command": [
                                                "pg_isready",
                                                "-h",
                                                "127.0.0.1",
                                                "-U",
                                                "postgres",
                                                "-d",
                                                "guidefold",
                                            ]
                                        },
                                        "periodSeconds": 2,
                                    },
                                    "volumeMounts": [
                                        {
                                            "name": "data",
                                            "mountPath": "/var/lib/postgresql/data",
                                        },
                                        {
                                            "name": "credentials",
                                            "mountPath": "/run/credentials",
                                            "readOnly": True,
                                        },
                                    ],
                                }
                            ],
                            "volumes": [
                                {
                                    "name": "data",
                                    "persistentVolumeClaim": {"claimName": "db-data"},
                                },
                                {
                                    "name": "credentials",
                                    "secret": {
                                        "secretName": "guidefold-operator-credentials",
                                        "items": [
                                            {
                                                "key": "admin-password",
                                                "path": "admin-password",
                                            }
                                        ],
                                    },
                                },
                            ],
                        },
                    },
                },
            }
        )
        apply(
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": "db"},
                "spec": {
                    "selector": {"app": "guidefold-test-db"},
                    "ports": [{"port": 5432}],
                },
            }
        )
        k("rollout", "status", "deployment/db", "--timeout=120s")
        base = {
            "developmentMode": True,
            "image": IMAGE,
            "tenant": "test",
            "repository": "meridian",
            "database": {
                "host": "db",
                "sslMode": "disable",
                "networkPeers": [
                    {"podSelector": {"matchLabels": {"app": "guidefold-test-db"}}}
                ],
            },
            "autoscaling": {"enabled": False},
            "replicas": 2,
            "resources": {
                "requests": {"cpu": "100m", "memory": "128Mi"},
                "limits": {"cpu": "1", "memory": "1Gi"},
            },
        }

        def install(name, values, wait=True):
            path = LOCAL / (name + ".yaml")
            path.write_text(yaml.safe_dump(values))
            command(helm + ["install", name, CHART, "-f", path])
            if wait:
                if values.get("workload", "serve") == "serve":
                    k("rollout", "status", "deployment/" + name, "--timeout=150s")
                else:
                    k(
                        "wait",
                        "--for=condition=complete",
                        "job/" + name,
                        "--timeout=150s",
                    )

        install("gf-migrate", {**base, "workload": "migrate"})
        for i in range(2):
            m = manifests[i]
            install(
                "gf-publish-" + str(i),
                {
                    **base,
                    "workload": "publish",
                    "snapshotID": m["snapshot"],
                    "artifactImage": m["artifact_image"],
                },
            )
            install(m["release"], {**base, "snapshotID": m["snapshot"]})
            (LOCAL / (m["release"] + ".json")).write_text(json.dumps(m))
        head = k(
            "exec",
            "deployment/db",
            "--",
            "psql",
            "-U",
            "postgres",
            "-d",
            "guidefold",
            "-Atc",
            "SELECT count(*) FROM gf.heads",
        )
        record("staged_jobs_do_not_activate_mutable_head", head.strip() == "0")
        apply(
            {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": "client", "labels": {"guidefold.client": "true"}},
                "spec": {
                    "automountServiceAccountToken": False,
                    "securityContext": {
                        "runAsUser": 65532,
                        "runAsGroup": 65532,
                        "runAsNonRoot": True,
                    },
                    "containers": [
                        {
                            "name": "client",
                            "image": CLIENT_IMAGE,
                            "imagePullPolicy": "IfNotPresent",
                            "command": [
                                "python",
                                "-c",
                                "import time; time.sleep(3600)",
                            ],
                            "resources": {
                                "requests": {"cpu": "25m", "memory": "32Mi"},
                                "limits": {"memory": "128Mi"},
                            },
                            "volumeMounts": [
                                {
                                    "name": "credentials",
                                    "mountPath": "/run/credentials",
                                    "readOnly": True,
                                }
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": "credentials",
                            "secret": {
                                "secretName": "guidefold-credentials",
                                "items": [{"key": "api-token", "path": "api-token"}],
                            },
                        }
                    ],
                },
            }
        )
        k("wait", "--for=condition=Ready", "pod/client", "--timeout=90s")

        def client(service, loops=1):
            script = """import json,time,urllib.request,urllib.error,hashlib
from pathlib import Path
token=Path('/run/credentials/api-token').read_text().strip()
def call(path,payload=None):
    req=urllib.request.Request('http://SERVICE:8080'+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    try: r=urllib.request.urlopen(req,timeout=3)
    except urllib.error.HTTPError as e: r=e
    except urllib.error.URLError: return 0,{}
    with r: return r.status,json.loads(r.read())
rows=[]
for i in range(LOOPS):
    status,result=call('/v1/search',{'schema_version':'1.1','query':'postgres production','node':'_root','deadline_ms':1000})
    row={'status':status,'snapshot':result.get('snapshot')}
    if status==200 and result['cards']:
        card=result['cards'][0]
        us,body=call('/v1/use',{'skill_id':card['skill_id'],'revision':card['revision']})
        row.update(use_status=us,checksum_ok=us==200 and body['checksum']==hashlib.sha256(body['body'].encode()).hexdigest())
    rows.append(row)
    if LOOPS>1: time.sleep(.02)
print(json.dumps(rows))
""".replace(
                "SERVICE", service
            ).replace(
                "LOOPS", str(loops)
            )
            return json.loads(
                k("exec", "-i", "client", "--", "python", "-", data=script)
            )

        def await_snapshot(service, snapshot):
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                row = client(service)[0]
                if row["status"] == 200 and row["snapshot"] == snapshot:
                    return True
                time.sleep(0.1)
            return False

        a, b = manifests[:2]
        for m in (a, b):
            rows = client(m["release"])
            record(
                "preview_" + m["release"],
                all(
                    r["status"] == 200
                    and r["snapshot"] == m["snapshot"]
                    and r.get("checksum_ok")
                    for r in rows
                ),
            )

        def promote(m, expected, apply_change=True):
            parts = [
                sys.executable,
                "tools/search_service/k8s_release.py",
                "promote",
                "--manifest",
                LOCAL / (m["release"] + ".json"),
                "--kubeconfig",
                kubeconfig,
                "--context",
                CONTEXT,
                "--namespace",
                NAME,
                "--expect-current",
                expected,
            ]
            if apply_change:
                parts.append("--apply")
            return json.loads(command(parts))

        plan = promote(a, "none", False)
        record(
            "promotion_plan_does_not_change_traffic",
            not plan["applied"]
            and not k(
                "get", "service", "guidefold", "--ignore-not-found", "-o", "name"
            ).strip(),
        )
        promote(a, "none")
        record("initial_promotion", await_snapshot("guidefold", a["snapshot"]))
        statement = (
            "INSERT INTO gf.heads VALUES ('test','meridian','" + b["snapshot"] + "')"
        )
        k(
            "exec",
            "deployment/db",
            "--",
            "psql",
            "-U",
            "postgres",
            "-d",
            "guidefold",
            "-c",
            statement,
        )
        record(
            "pinned_release_ignores_head_change",
            client(a["release"])[0]["snapshot"] == a["snapshot"],
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            sampling = executor.submit(client, "guidefold", 150)
            promote(b, a["release"])
            rows = sampling.result()
        record(
            "traffic_during_promotion",
            all(
                r["status"] == 200
                and r["snapshot"] in (a["snapshot"], b["snapshot"])
                and r.get("checksum_ok")
                for r in rows
            ),
            requests=len(rows),
        )
        record(
            "new_release_receives_traffic",
            await_snapshot("guidefold", b["snapshot"]),
        )
        try:
            promote(a, a["release"])
        except RuntimeError:
            stale_rejected = True
        else:
            stale_rejected = False
        record(
            "stale_promotion_rejected",
            stale_rejected and await_snapshot("guidefold", b["snapshot"]),
        )
        promote(a, b["release"])
        record("rollback", await_snapshot("guidefold", a["snapshot"]))
        k("scale", "deployment/" + a["release"], "--replicas=3")
        k("rollout", "status", "deployment/" + a["release"], "--timeout=120s")
        record(
            "scale_three_replicas",
            promote(a, a["release"], False)["preflight"]["replicas_verified"] == 3,
        )
        k("rollout", "restart", "deployment/" + a["release"])
        k("rollout", "status", "deployment/" + a["release"], "--timeout=150s")
        record(
            "rolling_restart_keeps_pin",
            client(a["release"])[0]["snapshot"] == a["snapshot"],
        )
        bad = manifests[2]
        (LOCAL / (bad["release"] + ".json")).write_text(json.dumps(bad))
        install(bad["release"], {**base, "snapshotID": bad["snapshot"]}, wait=False)
        # Wait for a running container so the negative test proves database pin
        # rejection, rather than just observing an unfinished Kubernetes rollout.
        deadline = time.monotonic() + 90
        bad_pod = None
        while time.monotonic() < deadline:
            pods = json.loads(
                k(
                    "get",
                    "pods",
                    "-l",
                    "app.kubernetes.io/instance=" + bad["release"],
                    "-o",
                    "json",
                )
            )["items"]
            if pods and all(
                p.get("status", {}).get("phase") == "Running" for p in pods
            ):
                bad_pod = pods[0]["metadata"]["name"]
                break
            time.sleep(1)
        record("unpublished_candidate_container_started", bad_pod is not None)
        rejected_pin = subprocess.run(
            [str(x) for x in kubectl]
            + [
                "exec",
                bad_pod,
                "-c",
                "api",
                "--",
                "/app/guidefold-search",
                "verify-release",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        record(
            "missing_pin_rejected_by_go",
            rejected_pin.returncode != 0
            and "snapshot_not_published" in rejected_pin.stdout,
        )
        # Its snapshot was never published; it must not replace the healthy Service.
        try:
            promote(bad, a["release"])
        except RuntimeError:
            rejected = True
        else:
            rejected = False
        record(
            "unpublished_candidate_cannot_promote",
            rejected and await_snapshot("guidefold", a["snapshot"]),
        )
        completed = True
    finally:
        result = {
            "schema_version": 1,
            "kind": "kubernetes_release_e2e",
            "passed": completed and all(c["passed"] for c in checks),
            "checks": checks,
            "gpu_executed": False,
            "quality_evaluated": False,
            "autoscaling_controller_exercised": False,
            "network_policy_enforcement_verified": False,
            "production_ready": False,
        }
        out = ROOT / ".guidefold/checks/kubernetes-release.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n")
        print(
            json.dumps({k: v for k, v in result.items() if k != "checks"}), flush=True
        )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reuse", action="store_true")
    p.add_argument("--reset", action="store_true")
    p.add_argument("--skip-build", action="store_true")
    run(p.parse_args())


if __name__ == "__main__":
    main()
