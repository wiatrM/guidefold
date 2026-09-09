"""Read-only preflight: this Helm change may replace only the UI image."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import yaml

helm = ["helm", "--kubeconfig=/home/mike/projects/hsk-monorepo/deployment/helm/webkd-prod/kubeconfig.yaml"]
chart = str(Path(__file__).resolve().parents[2] / "deploy/k8s/chart")
image = sys.argv[1]
if len(sys.argv) > 2:
    chart = sys.argv[2]

def run(args, payload=None):
    return subprocess.run(helm + args, input=payload, text=True, capture_output=True, check=True).stdout

def resources(raw):
    return {(item["kind"], item["metadata"]["name"]): item for item in yaml.safe_load_all(raw) if item}

values = run(["get", "values", "guidefold", "-n", "guidefold", "-o", "json"])
live = resources(run(["get", "manifest", "guidefold", "-n", "guidefold"]))
rendered = resources(run(["template", "guidefold", chart, "-n", "guidefold", "-f", "-", "--set-string", "ui.image=" + image], values))
expected = copy.deepcopy(live)
target = ("Deployment", "guidefold-ui")
containers = expected[target]["spec"]["template"]["spec"]["containers"]
assert len(containers) == 1, "UI container count changed; review required"
previous = containers[0]["image"]
containers[0]["image"] = image
if expected != rendered:
    changed = ["/".join(key) for key in set(expected) | set(rendered) if expected.get(key) != rendered.get(key)]
    print(json.dumps({"result": "blocked", "changedResources": sorted(changed)}))
    raise SystemExit("Changes exceed the UI image; review required")
print(json.dumps({"result": "passed", "onlyChange": "Deployment/guidefold-ui container image", "previous": previous, "next": image}))
