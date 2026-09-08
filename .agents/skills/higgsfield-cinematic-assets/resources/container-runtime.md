# Higgsfield Media Gateway runtime

Use this resource only for an operator-approved media phase in `chmiel17`.

## Boundary

- The design agent writes `/workspace/design/asset-plan.json`; it never calls Higgsfield.
- The controller validates the plan, request digest, approval expiry, provider, and maximum
  cost before creating a media Job.
- `unslopify-media-gateway` in `unslopify-providers` owns `higgsfield-auth`, provider-job
  idempotency and delivery state. It has a ClusterIP Service and no Ingress.
- The media Job mounts only the workspace. It receives one short-lived capability and gateway
  URL, but no provider, Codex, Claude, PRIME, Supabase, runner or Kubernetes credentials.
- Write provider output to `media-staging/`. Run deterministic `media-integrate` only after the
  writer and media checkpoints, then copy verified bytes to exact plan outputs.

## Authentication bootstrap

The gateway's pinned official `@higgsfield/cli` adapter uses browser OAuth. Store its
refreshable session on the retained `higgsfield-auth` RWO PVC with `HOME=/auth/higgsfield`.
Run login only through a
one-off sleeping bootstrap Job and `kubectl exec -it`. If the OAuth callback requires a
loopback port, use a temporary `kubectl port-forward` to the bootstrap Pod; do not create an
Ingress or Service and remove the bootstrap Job after readiness passes.

Never run `higgsfield auth token` in automation because it prints the credential. Readiness
uses a non-secret command such as `higgsfield model list --json` with output discarded and
emits only `Higgsfield auth ready` or a typed failure.

## Approved execution

1. Parse the asset plan against `/harness/schemas/asset-plan.schema.json` and calculate its
   canonical SHA-256 digest.
   The private-alpha schema permits exactly one Higgsfield slot and therefore one paid
   operation per capability JTI.
2. Poll the runner approval endpoint while heartbeats retain the active lease. Accept only a
   capability bound to job, revision, fence, `media` phase, digest, tool allowlist, budget,
   expiry and unique ID.
3. Call `media.estimate`; reject an estimate above the capability budget before spending.
4. Call `media.generate_approved`. The gateway discovers a compatible current model; model
   IDs never come from customer input or an unvalidated agent string.
5. Poll `media.status` under the phase deadline. Retry the same plan digest/generation ID and
   never create a second paid job.
6. Request `media.delivery_manifest` and download only through its capability-protected,
   same-gateway-origin path. Never persist upstream signed delivery URLs.
7. Validate dimensions, duration, codec, fps, audio policy, size and SHA-256 in staging.
8. Run `media-integrate` after writer completion; recheck plan paths, hashes and bytes before
   atomic promotion to `site/public/generated/`.
9. Emit schema-bound delivery/integration manifests and phase metrics. On auth expiry return
   `needs_reauth`; on unavailable capacity return `paused_capacity`; never fall back to a
   paid provider automatically.

## Idempotency and cancellation

Before provider submission, the gateway durably stores capability ID, request digest and
provider job ID. Repeated `generate_approved` calls return that generation instead of spending
again. On cancellation, the runner calls `media.cancel`; preserve only sanitized job metadata.
