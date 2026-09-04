#!/usr/bin/env bash
# build-bundle.sh: build (or verify) the offline Meridian release bundle for a release tag.
#   tools/release/build-bundle.sh vYYYY.MM.N             -> dist/meridian-<tag>.tar.gz
#   tools/release/build-bundle.sh --dry-run vYYYY.MM.N   -> list what would be packed
#   tools/release/build-bundle.sh --verify <bundle>      -> check SHA256SUMS + manifest signature offline
# Bundle layout is fixed: images/ charts/ migrations/<service>/ sbom/ manifest.yaml SHA256SUMS
set -euo pipefail

MODE=build
case "${1:-}" in --dry-run) MODE=dry-run; shift ;; --verify) MODE=verify; shift ;; esac
ARG="${1:?usage: build-bundle.sh [--dry-run|--verify] <tag|bundle>}"
DIST="${DIST:-dist}"

if [[ "$MODE" == "verify" ]]; then
  tmp="$(mktemp -d)"; tar -xzf "$ARG" -C "$tmp"
  (cd "$tmp" && sha256sum -c SHA256SUMS)
  cosign verify-blob --key security/policy/cosign.pub --signature "$tmp/manifest.yaml.sig" "$tmp/manifest.yaml"
  echo "bundle ok: $ARG"; exit 0
fi

TAG="$ARG"
[[ "$TAG" =~ ^v[0-9]{4}\.[0-9]{2}\.[0-9]+$ ]] || { echo "tag must look like vYYYY.MM.N" >&2; exit 2; }
IMAGES=$(bazel query 'kind(oci_image, //platforms/... + //security/...)')
CHARTS=$(find infra/relay/k8s/charts -mindepth 1 -maxdepth 1 -type d)
MIGRATIONS=$(find platforms libs -type d -name migrations)
if [[ "$MODE" == "dry-run" ]]; then
  printf 'images:\n%s\ncharts:\n%s\nmigrations:\n%s\n' "$IMAGES" "$CHARTS" "$MIGRATIONS"; exit 0
fi

STAGE="$DIST/stage-$TAG"; rm -rf "$STAGE"; mkdir -p "$STAGE"/{images,charts,migrations,sbom}
for t in $IMAGES; do bazel run "$t.push" -- --format=oci --to "$STAGE/images"; done   # digests only
for c in $CHARTS; do helm package "$c" -d "$STAGE/charts" >/dev/null; done
for d in $MIGRATIONS; do svc="$(basename "$(dirname "$d")")"; mkdir -p "$STAGE/migrations/$svc"; cp "$d"/*.sql "$STAGE/migrations/$svc/"; done
for img in "$STAGE"/images/*; do syft "oci-dir:$img" -o spdx-json > "$STAGE/sbom/$(basename "$img").spdx.json"; done
{ echo "tag: $TAG"; echo "builtFrom: $(git rev-parse "$TAG")"; echo "images:"
  for img in "$STAGE"/images/*; do echo "  - $(basename "$img")"; done; } > "$STAGE/manifest.yaml"
cosign sign-blob --key env://COSIGN_KEY --output-signature "$STAGE/manifest.yaml.sig" "$STAGE/manifest.yaml"
(cd "$STAGE" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
tar --sort=name --mtime="@0" --owner=0 --group=0 --numeric-owner -czf "$DIST/meridian-$TAG.tar.gz" -C "$STAGE" .
echo "wrote $DIST/meridian-$TAG.tar.gz"
