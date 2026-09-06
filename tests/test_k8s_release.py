"""Release identity, stale-promotion rejection and deployment safety contracts."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "k8s_release", ROOT / "tools/search_service/k8s_release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
build_manifest = release.build_manifest
digest = release.digest
preflight = release.preflight
promotion_change = release.promotion_change
selector = release.selector
validate_manifest = release.validate_manifest

PIN = "example.invalid/guidefold@sha256:" + "a" * 64


def manifest():
    snapshot = {
        "format": "guidefold-service-snapshot-v1",
        "repo_id": "repo",
        "cli_sha256": "b" * 64,
    }
    index = {
        "format": "guidefold-bm25f-build-v1",
        "snapshot_sha256": digest(snapshot),
        "policy_sha256": snapshot["cli_sha256"],
    }
    bundle = {
        "snapshot": snapshot,
        "sha256": digest(snapshot),
        "router_index": index,
        "router_index_sha256": digest(index),
    }
    return build_manifest(bundle, "tenant", PIN, PIN)


def test_manifest_binds_all_runtime_artifacts():
    m = manifest()
    validate_manifest(m)
    for key in (
        "image",
        "artifact_image",
        "snapshot",
        "policy_revision",
        "router_index_revision",
        "tenant",
    ):
        changed = deepcopy(m)
        changed[key] += "changed"
        with pytest.raises(ValueError):
            validate_manifest(changed)


def test_promotion_requires_owned_matching_tenant_and_previous_release():
    m = manifest()
    create = promotion_change(None, m, "tenant-ns", "guidefold", "none")["object"]
    create["metadata"]["resourceVersion"] = "123"
    patch = promotion_change(create, m, "tenant-ns", "guidefold", m["release"])["patch"]
    assert patch[:2] == [
        {"op": "test", "path": "/metadata/resourceVersion", "value": "123"},
        {"op": "test", "path": "/spec/selector", "value": selector(m["release"])},
    ]
    for changed in (None, deepcopy(create), deepcopy(create)):
        if changed is None:
            with pytest.raises(ValueError):
                promotion_change(None, m, "tenant-ns", "guidefold", "old")
        else:
            changed["metadata"]["annotations"]["guidefold.io/tenant"] = "other"
            with pytest.raises(ValueError):
                promotion_change(changed, m, "tenant-ns", "guidefold", m["release"])
    with pytest.raises(ValueError):
        promotion_change(create, m, "tenant-ns", "guidefold", "stale")
    del create["metadata"]["labels"]["guidefold.io/traffic"]
    with pytest.raises(ValueError):
        promotion_change(create, m, "tenant-ns", "guidefold", m["release"])


class Candidate:
    def __init__(self, m, bad_second=False):
        self.m, self.bad_second, self.visited = m, bad_second, []

    def get(self, kind, name):
        m = self.m
        if kind == "deployment":
            return {
                "metadata": {"generation": 3},
                "status": {
                    "observedGeneration": 3,
                    "updatedReplicas": 2,
                    "availableReplicas": 2,
                },
                "spec": {
                    "replicas": 2,
                    "selector": {"matchLabels": selector(m["release"])},
                    "template": {
                        "spec": {"containers": [{"name": "api", "image": m["image"]}]}
                    },
                },
            }
        return {
            "immutable": True,
            "data": {
                "GUIDEFOLD_TENANT": m["tenant"],
                "GUIDEFOLD_REPO": m["repository"],
                "GUIDEFOLD_SNAPSHOT_ID": m["snapshot"],
                "GUIDEFOLD_RETRIEVAL_MODE": "sparse",
                "GUIDEFOLD_ENCODER_ID": "",
                "GUIDEFOLD_SHADOW": "false",
            },
        }

    def command(self, *args):
        if args[0] == "get":
            return json.dumps(
                {
                    "items": [
                        {
                            "metadata": {"name": name},
                            "status": {
                                "conditions": [{"type": "Ready", "status": "True"}]
                            },
                        }
                        for name in ("pod-1", "pod-2")
                    ]
                }
            )
        self.visited.append(args[1])
        evidence = {
            k: self.m[k]
            for k in (
                "tenant",
                "repository",
                "snapshot",
                "policy_revision",
                "router_index_revision",
                "encoder_id",
            )
        }
        evidence["pinned"] = True
        if self.bad_second and args[1] == "pod-2":
            evidence["router_index_revision"] = "wrong"
        return json.dumps(evidence)


def test_preflight_checks_every_replica_and_rejects_live_index_mismatch():
    m = manifest()
    good = Candidate(m)
    assert preflight(good, m)["replicas_verified"] == 2
    assert good.visited == ["pod-1", "pod-2"]
    bad = Candidate(m, bad_second=True)
    with pytest.raises(ValueError, match="differs from manifest"):
        preflight(bad, m)
    assert bad.visited == ["pod-1", "pod-2"]


@pytest.fixture
def helm_values():
    return {
        "image": PIN,
        "artifactImage": PIN,
        "tenant": "tenant",
        "repository": "repo",
        "snapshotID": "repository:" + "c" * 64,
        "database": {
            "host": "db.internal",
            "networkPeers": [{"ipBlock": {"cidr": "10.20.0.0/24"}}],
        },
    }


def render(tmp_path, values):
    if not shutil.which("helm"):
        pytest.skip("Helm is exercised by the kubernetes-service CI job")
    file = tmp_path / "values.yaml"
    file.write_text(yaml.safe_dump(values))
    return subprocess.run(
        [
            "helm",
            "template",
            "gf-release",
            str(ROOT / "deploy/k8s/chart"),
            "-f",
            str(file),
        ],
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    "change",
    [
        {"image": "guidefold:latest"},
        {"snapshotID": ""},
        {"database": {"host": "db", "sslMode": "disable", "networkPeers": []}},
        {
            "database": {
                "host": "db",
                "connectionBudget": 16,
                "networkPeers": [{"ipBlock": {"cidr": "10.0.0.0/8"}}],
            }
        },
        {"networkPolicy": {"enabled": False}},
        {"gpu": {"enabled": True, "image": PIN, "encoderID": "bad"}},
        {
            "gpu": {
                "enabled": True,
                "image": PIN,
                "encoderID": "d" * 64,
                "autoscaling": {"enabled": True},
            }
        },
        {"autoscalling": {"enabled": True}},
    ],
)
def test_chart_rejects_unsafe_or_unknown_configuration(tmp_path, helm_values, change):
    helm_values.update(change)
    assert render(tmp_path, helm_values).returncode != 0


@pytest.mark.parametrize(
    "workload,gpu",
    [
        ("serve", False),
        ("serve", True),
        ("migrate", False),
        ("publish", False),
        ("publish", True),
    ],
)
def test_chart_workload_contracts(tmp_path, helm_values, workload, gpu):
    helm_values.update(
        workload=workload, gpu={"enabled": gpu, "image": PIN, "encoderID": "d" * 64}
    )
    result = render(tmp_path, helm_values)
    assert result.returncode == 0, result.stderr
    docs = list(yaml.safe_load_all(result.stdout))
    config = next(d for d in docs if d["kind"] == "ConfigMap")
    assert config["immutable"]
    assert config["data"]["GUIDEFOLD_SNAPSHOT_ID"] == helm_values["snapshotID"]
    assert config["data"]["GUIDEFOLD_RETRIEVAL_MODE"] == "sparse"
    assert config["data"]["GUIDEFOLD_EXPERIMENTAL_OUTPUT"] == "false"
    assert not any(d["kind"] in ("Secret", "Ingress", "StatefulSet") for d in docs)
    for d in docs:
        if d["kind"] not in ("Deployment", "Job"):
            continue
        pod = d["spec"]["template"]["spec"]
        assert pod["automountServiceAccountToken"] is False
        assert pod["securityContext"]["runAsNonRoot"]
        for container in pod.get("initContainers", []) + pod["containers"]:
            assert container["securityContext"]["readOnlyRootFilesystem"]
            assert container["securityContext"]["capabilities"]["drop"] == ["ALL"]
        if d["kind"] == "Job":
            for container in pod.get("initContainers", []) + pod["containers"]:
                assert {v["name"]: v["value"] for v in container["env"]}[
                    "GUIDEFOLD_PUBLISH_ACTIVATE"
                ] == "false"
        elif d["metadata"]["name"] == "gf-release":
            secret = next(
                v["secret"] for v in pod["volumes"] if v["name"] == "credentials"
            )
            assert {i["key"] for i in secret["items"]} == {"app-password", "api-token"}
            assert (
                pod["containers"][0]["readinessProbe"]["httpGet"]["path"]
                == "/health/ready"
            )
    if gpu and workload == "serve":
        network = next(
            d
            for d in docs
            if d["kind"] == "NetworkPolicy" and d["metadata"]["name"] == "gf-release"
        )
        expression = network["spec"]["podSelector"]["matchExpressions"][0]
        assert (
            "tei" not in expression["values"]
        )  # a second policy must not widen GPU ingress
