#!/usr/bin/env python3
"""Validate the GPU and custom-metric manifests with the dedicated kind API server."""
import json
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.search_service.k8s_e2e import command, CONTEXT


def main():
    pin = "example.invalid/fixture@sha256:" + "a" * 64
    values = {
        "image": pin,
        "tenant": "schema",
        "repository": "fixture",
        "snapshotID": "repository:" + "b" * 64,
        "database": {
            "host": "postgres.internal",
            "networkPeers": [{"ipBlock": {"cidr": "10.20.0.0/24"}}],
        },
        "gpu": {
            "enabled": True,
            "image": pin,
            "encoderID": "c" * 64,
            "autoscaling": {
                "enabled": True,
                "queueMetric": "guidefold_tei_queue_depth",
            },
        },
        "autoscaling": {"inflightMetric": "guidefold_admitted_requests"},
    }
    path = ROOT / ".guidefold/k8s-schema-values.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(values))
    rendered = command(
        ["helm", "template", "gf-schema", ROOT / "deploy/k8s/chart", "-f", path]
    )
    command(
        [
            "kubectl",
            "--kubeconfig",
            ROOT / ".guidefold/kubeconfig",
            "--context",
            CONTEXT,
            "-n",
            "default",
            "apply",
            "--dry-run=server",
            "-f",
            "-",
        ],
        rendered,
    )
    result = {
        "passed": True,
        "server_dry_run": True,
        "resources": len(list(yaml.safe_load_all(rendered))),
        "gpu_scheduled": False,
        "gpu_inference_exercised": False,
        "custom_metrics_controller_exercised": False,
    }
    out = ROOT / ".guidefold/checks/kubernetes-gpu-schema.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
