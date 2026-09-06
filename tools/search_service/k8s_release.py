#!/usr/bin/env python3
"""Create immutable release identities and promote a preflighted Kubernetes release.

Every cluster operation requires an explicit kubeconfig/context/namespace. Promotion
is a plan unless --apply is supplied. Existing traffic changes use resourceVersion
and selector tests, so a stale operator cannot overwrite another promotion.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

import yaml


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def image_ref(value, development):
    if not value or (
        not development and not re.search(r"@sha256:[0-9a-f]{64}$", value)
    ):
        raise ValueError("release images must be pinned by digest")
    return value


def build_manifest(
    bundle,
    tenant,
    image,
    artifact_image,
    encoder_id=None,
    model_image=None,
    development=False,
):
    snapshot = bundle["snapshot"]
    if (
        digest(snapshot) != bundle["sha256"]
        or digest(bundle["router_index"]) != bundle["router_index_sha256"]
    ):
        raise ValueError("bundle integrity mismatch")
    if (
        snapshot.get("format") != "guidefold-service-snapshot-v1"
        or bundle["router_index"].get("format") != "guidefold-bm25f-build-v1"
    ):
        raise ValueError("unsupported snapshot/index format")
    if (
        bundle["router_index"].get("snapshot_sha256") != bundle["sha256"]
        or bundle["router_index"].get("policy_sha256") != snapshot["cli_sha256"]
    ):
        raise ValueError("index belongs to a different snapshot/policy")
    if not tenant:
        raise ValueError("tenant is required")
    if encoder_id is not None and not re.fullmatch(r"[0-9a-f]{64}", encoder_id):
        raise ValueError("invalid encoder identity")
    if bool(encoder_id) != bool(model_image):
        raise ValueError("encoder ID and model image must be supplied together")
    result = {
        "format": "guidefold-release-v1",
        "tenant": tenant,
        "repository": snapshot["repo_id"],
        "snapshot": "repository:" + bundle["sha256"],
        "policy_revision": snapshot["cli_sha256"],
        "router_index_revision": bundle["router_index_sha256"],
        "image": image_ref(image, development),
        "artifact_image": image_ref(artifact_image, development),
        "encoder_id": encoder_id,
        "model_image": image_ref(model_image, development) if model_image else None,
        "development": development,
    }
    result["release"] = "gf-" + digest(result)[:16]
    return result


def validate_manifest(manifest):
    required = {
        "format",
        "tenant",
        "repository",
        "snapshot",
        "policy_revision",
        "router_index_revision",
        "image",
        "artifact_image",
        "encoder_id",
        "model_image",
        "development",
        "release",
    }
    if set(manifest) != required or type(manifest["development"]) is not bool:
        raise ValueError("invalid release manifest fields")
    for key in (
        "tenant",
        "repository",
        "snapshot",
        "image",
        "artifact_image",
        "release",
    ):
        if not isinstance(manifest[key], str) or not manifest[key].strip():
            raise ValueError("invalid release identity")
    for key in ("policy_revision", "router_index_revision"):
        if not isinstance(manifest[key], str) or not re.fullmatch(
            r"[0-9a-f]{64}", manifest[key]
        ):
            raise ValueError("invalid release digest")
    if bool(manifest["encoder_id"]) != bool(manifest["model_image"]):
        raise ValueError("incomplete model identity")
    identity = {k: v for k, v in manifest.items() if k != "release"}
    if (
        manifest.get("format") != "guidefold-release-v1"
        or manifest.get("release") != "gf-" + digest(identity)[:16]
    ):
        raise ValueError("release manifest integrity mismatch")
    for key in ("image", "artifact_image"):
        image_ref(manifest[key], manifest["development"])
    if manifest["model_image"]:
        image_ref(manifest["model_image"], manifest["development"])


def selector(release):
    return {
        "app.kubernetes.io/name": "guidefold",
        "app.kubernetes.io/instance": release,
        "app.kubernetes.io/component": "api",
    }


def promotion_change(current, manifest, namespace, service, expected):
    """Pure compare-and-swap planning; Kubernetes enforces the returned tests."""
    target = selector(manifest["release"])
    annotations = {
        "guidefold.io/tenant": manifest["tenant"],
        "guidefold.io/repository": manifest["repository"],
    }
    if current is None:
        if expected != "none":
            raise ValueError(
                "traffic service absent; expected current release does not match"
            )
        return {
            "operation": "create",
            "object": {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "name": service,
                    "namespace": namespace,
                    "labels": {"guidefold.io/traffic": "managed"},
                    "annotations": annotations,
                },
                "spec": {
                    "type": "ClusterIP",
                    "selector": target,
                    "ports": [{"name": "http", "port": 8080, "targetPort": "http"}],
                },
            },
        }
    if current["metadata"].get("labels", {}).get("guidefold.io/traffic") != "managed":
        raise ValueError("refusing to take ownership of an unrelated Service")
    if any(
        current["metadata"].get("annotations", {}).get(k) != v
        for k, v in annotations.items()
    ):
        raise ValueError("traffic tenant/repository mismatch")
    old = current["spec"].get("selector", {})
    if old != selector(expected):
        raise ValueError("current release differs from --expect-current")
    return {
        "operation": "patch",
        "patch": [
            {
                "op": "test",
                "path": "/metadata/resourceVersion",
                "value": current["metadata"]["resourceVersion"],
            },
            {"op": "test", "path": "/spec/selector", "value": old},
            {"op": "replace", "path": "/spec/selector", "value": target},
        ],
    }


class Cluster:
    def __init__(self, args):
        self.base = [
            "kubectl",
            "--kubeconfig",
            str(args.kubeconfig),
            "--context",
            args.context,
            "--namespace",
            args.namespace,
            "--request-timeout=30s",
        ]

    def command(self, *args, data=None):
        result = subprocess.run(
            self.base + list(args),
            input=json.dumps(data) if data is not None else None,
            capture_output=True,
            text=True,
            timeout=150,
        )
        if result.returncode:
            # kubectl diagnostics may include object contents. Keep secrets off stdout.
            raise RuntimeError(
                "kubectl failed: "
                + " ".join(args[:2])
                + " (inspect the named resource)"
            )
        return result.stdout

    def get(self, kind, name):
        raw = self.command("get", kind, name, "--ignore-not-found", "-o", "json")
        return json.loads(raw) if raw.strip() else None


def preflight(cluster, manifest):
    release = manifest["release"]
    deployment = cluster.get("deployment", release)
    if deployment is None:
        raise ValueError("candidate deployment is absent")
    status, spec = deployment.get("status", {}), deployment["spec"]
    desired = spec.get("replicas", 1)
    if (
        desired < 1
        or status.get("observedGeneration", 0) < deployment["metadata"]["generation"]
    ):
        raise ValueError("candidate rollout is not observed")
    if (
        status.get("updatedReplicas", 0) != desired
        or status.get("availableReplicas", 0) < desired
    ):
        raise ValueError("all candidate replicas must be updated and available")
    expected_selector = selector(release)
    if spec["selector"]["matchLabels"] != expected_selector:
        raise ValueError("unexpected candidate pod selector")
    containers = spec["template"]["spec"]["containers"]
    if (
        len(containers) != 1
        or containers[0]["name"] != "api"
        or containers[0]["image"] != manifest["image"]
    ):
        raise ValueError("candidate image mismatch")
    config = cluster.get("configmap", release)
    expected_config = {
        "GUIDEFOLD_TENANT": manifest["tenant"],
        "GUIDEFOLD_REPO": manifest["repository"],
        "GUIDEFOLD_SNAPSHOT_ID": manifest["snapshot"],
        "GUIDEFOLD_RETRIEVAL_MODE": "sparse",
        "GUIDEFOLD_ENCODER_ID": manifest["encoder_id"] or "",
        "GUIDEFOLD_SHADOW": str(bool(manifest["encoder_id"])).lower(),
    }
    if (
        not config
        or not config.get("immutable")
        or any(config["data"].get(k) != v for k, v in expected_config.items())
    ):
        raise ValueError("candidate immutable configuration mismatch")
    if manifest["model_image"]:
        gpu = cluster.get("deployment", release + "-tei")
        if (
            not gpu
            or gpu["spec"]["template"]["spec"]["containers"][0]["image"]
            != manifest["model_image"]
        ):
            raise ValueError("candidate model image mismatch")
    labels = ",".join(k + "=" + v for k, v in expected_selector.items())
    pods = json.loads(cluster.command("get", "pods", "-l", labels, "-o", "json"))[
        "items"
    ]
    pods = [p for p in pods if not p["metadata"].get("deletionTimestamp")]
    if len(pods) != desired:
        raise ValueError("candidate pod set is changing; retry preflight")
    for pod in pods:
        if not any(
            c["type"] == "Ready" and c["status"] == "True"
            for c in pod.get("status", {}).get("conditions", [])
        ):
            raise ValueError("candidate pod is not Ready")
        raw = cluster.command(
            "exec",
            pod["metadata"]["name"],
            "-c",
            "api",
            "--",
            "/app/guidefold-search",
            "verify-release",
        )
        evidence = json.loads(raw)
        expected = {
            k: manifest[k]
            for k in (
                "tenant",
                "repository",
                "snapshot",
                "policy_revision",
                "router_index_revision",
                "encoder_id",
            )
        }
        if evidence.get("pinned") is not True or any(
            evidence.get(k) != v for k, v in expected.items()
        ):
            raise ValueError("live release preflight differs from manifest")
    return {
        "replicas_verified": len(pods),
        "snapshot": manifest["snapshot"],
        "encoder_id": manifest["encoder_id"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("manifest")
    build.add_argument("--snapshot", type=Path, required=True)
    build.add_argument("--tenant", required=True)
    build.add_argument("--image", required=True)
    build.add_argument("--artifact-image", required=True)
    build.add_argument("--encoder-id")
    build.add_argument("--model-image")
    build.add_argument("--development", action="store_true")
    build.add_argument("--output", type=Path, required=True)
    values = commands.add_parser("values")
    values.add_argument("--manifest", type=Path, required=True)
    values.add_argument("--base", type=Path, required=True)
    values.add_argument(
        "--workload", choices=("serve", "migrate", "publish"), default="serve"
    )
    values.add_argument("--output", type=Path, required=True)
    promote = commands.add_parser("promote")
    promote.add_argument("--manifest", type=Path, required=True)
    promote.add_argument("--kubeconfig", type=Path, required=True)
    promote.add_argument("--context", required=True)
    promote.add_argument("--namespace", required=True)
    promote.add_argument("--service", default="guidefold")
    promote.add_argument(
        "--expect-current",
        required=True,
        help="previous release name, or none for initial creation",
    )
    promote.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.command == "manifest":
        result = build_manifest(
            json.loads(args.snapshot.read_text()),
            args.tenant,
            args.image,
            args.artifact_image,
            args.encoder_id,
            args.model_image,
            args.development,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"release": result["release"], "manifest": str(args.output)}))
        return
    manifest = json.loads(args.manifest.read_text())
    validate_manifest(manifest)
    if args.command == "values":
        base = yaml.safe_load(args.base.read_text())
        base.update(
            workload=args.workload,
            image=manifest["image"],
            artifactImage=manifest["artifact_image"],
            tenant=manifest["tenant"],
            repository=manifest["repository"],
            snapshotID=manifest["snapshot"],
            developmentMode=manifest["development"],
        )
        base.setdefault("gpu", {}).update(
            enabled=bool(manifest["encoder_id"]),
            encoderID=manifest["encoder_id"] or "",
            image=manifest["model_image"] or "",
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(yaml.safe_dump(base, sort_keys=False))
        print(json.dumps({"release": manifest["release"], "values": str(args.output)}))
        return
    cluster = Cluster(args)
    evidence = preflight(cluster, manifest)
    current = cluster.get("service", args.service)
    change = promotion_change(
        current, manifest, args.namespace, args.service, args.expect_current
    )
    if args.apply:
        if change["operation"] == "create":
            cluster.command("create", "-f", "-", data=change["object"])
        else:
            cluster.command(
                "patch",
                "service",
                args.service,
                "--type=json",
                "-p",
                json.dumps(change["patch"]),
            )
    print(
        json.dumps(
            {
                "applied": args.apply,
                "release": manifest["release"],
                "preflight": evidence,
                "change": change,
            }
        )
    )


if __name__ == "__main__":
    main()
