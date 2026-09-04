---
name: classification-labels
description: "[security] Data-classification labels in Meridian: the Label enum in libs/classification (UNCLASSIFIED, OFFICIAL, RESTRICTED, CONFIDENTIAL), how labels attach to datasets, records and API responses, and how they propagate through joins, pipelines and exports. Use when you add a field or dataset that carries a label, write code that merges or derives data, or expose data over an API. Do not use for audit event formats or for RBAC policy authoring."
license: Apache-2.0
compatibility: "Needs the libs/classification Go module (or its Python mirror) and the classification lint in CI."
metadata:
  scope: security
  owner: security-org
  references: "libs/classification/labels.go#Label"
  status: active
  since: "2026-09-04"
  kind: governance
  layer: platform
  triggers: "classification Label enum, UNCLASSIFIED OFFICIAL RESTRICTED CONFIDENTIAL, Propagate helper, X-Meridian-Classification header, label downgrade, libs/classification"
  digest: >-
    Every dataset, record and API response in Meridian carries a classification Label from libs/classification,
    ordered UNCLASSIFIED to CONFIDENTIAL. Derived data always takes the highest label of its inputs, and code
    must use the shared Propagate helper rather than string comparisons.
---

# Classification labels

## When to use / when NOT to use
Use when you:
- add a table, dataset, Kafka topic or object type that stores labelled data;
- write pipeline, join, aggregation or export code that combines inputs with different labels;
- return data from an API and must set the response label header;
- add a new label value or handling caveat (this needs security-org review and an ADR).

Do not use for how audit events are recorded (`security.audit:audit-logging`) or for writing access
policies that consume labels (`atlas.identity:rbac-policies`).

## Steps
1. Import `meridian.example/libs/classification` and use the `Label` type; never a bare string or int.
   Valid values, lowest to highest: `UNCLASSIFIED`, `OFFICIAL`, `RESTRICTED`, `CONFIDENTIAL`.
2. Store the label in a dedicated column or field named `classification` with a NOT NULL constraint and a
   check against the enum. In ontology schemas the property is `classification: label`.
3. When deriving data compute the output label with `classification.Propagate(inputs...)`, which returns the
   highest input label. Do not hand-roll `max` over strings; the order is defined once in `labels.go`.
4. On HTTP responses set `X-Meridian-Classification: <label>` from the payload's computed label. gRPC uses
   the `meridian-classification` metadata key. The auth SDK reads it for policy checks.
5. Exports (CSV, Parquet, bundle) write the label into file metadata and the file name suffix
   (`dataset_2026-09.RESTRICTED.parquet`).
6. Downgrading a label is a manual, audited action through the security service; code paths must never
   assign a lower label than `Propagate` returns.
7. Run the classification lint before pushing; CI blocks any labelled type without a `classification` field.

## Conventions specific to this scope
- The enum is closed. Adding a value changes `labels.go`, the Python mirror, the Postgres domain type and
  the ontology schema in one PR with security-org approval.
- Label comparisons use `a.AtMost(b)` and `a.Dominates(b)`; `==` is only for equality of the same level.
- Unknown or missing labels are an error (`ErrUnlabelled`), never a default to `UNCLASSIFIED`.
- Caveats (for example `REL-PARTNER`) are a separate `Caveats []string` field; they are additive and also
  propagate.
- Test fixtures use labelled sample data from `libs/classification/testdata`; do not invent label strings.
- Logs and metrics never include record content, only the label level as a dimension.
- UI components render labels with the shared banner component; colour and wording come from the library,
  not from per-app CSS.

## Verify
```bash
go test ./libs/classification/...                                        # enum order and Propagate
go run ./libs/classification/cmd/classlint ./platforms/...              # every labelled type carries a Label
grep -rn '"RESTRICTED"\|"CONFIDENTIAL"' --include=*.go platforms/ libs/  # literals outside labels.go are a smell
psql "$DATABASE_URL" -c "\dT+ classification_label"                      # Postgres domain matches the enum
```

## See also
- urn:skill:meridian:security.audit:audit-logging
- urn:skill:meridian:atlas.identity:rbac-policies
