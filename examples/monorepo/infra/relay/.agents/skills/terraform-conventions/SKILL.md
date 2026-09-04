---
name: terraform-conventions
description: "[relay] Terraform layout, module usage, remote state, and review rules for Meridian infrastructure under infra/relay. Use when adding or changing a Terraform module, root stack, provider version, or backend configuration. Do not use for Kubernetes manifests and Helm charts (relay.k8s) or for offline bundle assembly (relay.edge)."
license: Apache-2.0
compatibility: "Needs terraform >= 1.9, tflint, terraform-docs, and read access to the relay state backend; `terraform plan` runs in CI with a read-only role."
metadata:
  scope: relay
  owner: relay-infra
  references: "infra/relay/terraform/main.tf"
  status: active
  since: "2026-09-04"
  digest: >-
    Relay infrastructure is one root stack per environment under infra/relay/terraform, composed only
    from modules in infra/relay/terraform/modules, with locked remote state per environment. Provider
    versions are pinned and plans are reviewed as PR artifacts before CI applies on merge.
---
# Terraform conventions for Relay

## When to use / when NOT to use
Use when you:
- add or change a module under `infra/relay/terraform/modules/<name>/`,
- change the root stack in `infra/relay/terraform/main.tf` or an `envs/<env>.tfvars` file,
- bump a provider or module version,
- change backend or remote state configuration.

Do NOT use when:
- the change is a Helm values file or chart (`relay.k8s:helm-conventions`),
- you are assembling the offline bundle for an air-gapped site (`relay.edge:air-gapped-deploy`),
- the resource belongs to another platform's own Terraform; they follow the same rules but own their state.

## Steps
1. Branch from `main`; run `make tf-init ENV=dev` (wraps `terraform init -backend-config=envs/dev.backend.hcl`).
2. Put reusable resources in `modules/<name>/{main.tf,variables.tf,outputs.tf,README.md}`.
   The root `main.tf` only declares providers, locals, and module calls.
3. Pin versions: `required_version` in `main.tf`, every provider with `~>` to a minor, every remote
   module `source` with `?ref=v<x.y.z>`; local modules use a relative `./modules/<name>` path.
4. Run `terraform fmt -recursive` and `tflint --recursive`.
5. Produce a plan: `make tf-plan ENV=dev` writes `plan.out` and a `plan.txt` summary to attach to the PR.
6. Open the PR with the `terraform` label; CI re-runs the plan with the read-only role and comments the diff.
7. After approval, apply happens from CI on merge (`make tf-apply ENV=<env>`), never from a laptop.

## Conventions specific to this scope
- One root stack per environment (`dev`, `staging`, `prod`, `edge-template`), selected by
  `-var-file=envs/<env>.tfvars`. No `terraform workspace` switching.
- Remote state: one backend per environment, state locking enabled, `prevent_destroy` on the state store.
- Resource names come from `local.name_prefix` (`<project>-<env>-<component>`); never hardcode the environment.
- Every resource gets `local.tags` (`owner`, `env`, `component`, `managed-by=terraform`) through provider `default_tags`.
- Variables have `description` and `type`; no untyped `any`. Sensitive inputs are `sensitive = true` and have no default.
- Outputs are consumed by other stacks only through `terraform_remote_state` data sources, never by copy-paste.
- No `provisioner` blocks and no `local-exec`; bootstrap logic belongs in a container image or a Helm hook.
- `count` for on/off toggles, `for_each` for collections; never index lists that can reorder.
- Secrets never appear in `.tfvars`; reference secret-manager paths and resolve them at runtime.
- Module `README.md` is generated with `terraform-docs markdown table` and diffed in CI.

## Verify
```bash
terraform fmt -check -recursive infra/relay/terraform
tflint --recursive --config infra/relay/terraform/.tflint.hcl
make tf-plan ENV=dev && grep -E "Plan: [0-9]+ to add" plan.txt
terraform-docs markdown table infra/relay/terraform/modules/<name> | diff - infra/relay/terraform/modules/<name>/README.md
```

## See also
- urn:skill:meridian:relay.k8s:helm-conventions
- urn:skill:meridian:relay.edge:air-gapped-deploy
