{{- define "gf.name" -}}{{ .Release.Name | trunc 53 | trimSuffix "-" }}{{- end -}}
{{- define "gf.labels" -}}
app.kubernetes.io/name: guidefold
app.kubernetes.io/instance: {{ include "gf.name" . }}
{{- end -}}
{{- define "gf.validate" -}}
{{- if not (has .Values.workload (list "serve" "migrate" "publish")) }}{{ fail "workload must be serve, migrate or publish" }}{{ end -}}
{{- $tenant := required "tenant is required" .Values.tenant -}}
{{- $repo := required "repository is required" .Values.repository -}}
{{- $db := required "database.host is required" .Values.database.host -}}
{{- $image := required "image is required" .Values.image -}}
{{- if and (ne .Values.workload "migrate") (empty .Values.snapshotID) }}{{ fail "snapshotID is required; serving must never follow a mutable head" }}{{ end -}}
{{- if and (eq .Values.workload "publish") (empty .Values.artifactImage) }}{{ fail "publish requires artifactImage" }}{{ end -}}
{{- if not .Values.developmentMode -}}
  {{- if not (regexMatch "@sha256:[0-9a-f]{64}$" .Values.image) }}{{ fail "production image must be pinned by digest" }}{{ end -}}
  {{- if and (eq .Values.workload "publish") (not (regexMatch "@sha256:[0-9a-f]{64}$" .Values.artifactImage)) }}{{ fail "artifactImage must be pinned by digest" }}{{ end -}}
  {{- if ne .Values.database.sslMode "verify-full" }}{{ fail "production Postgres requires verify-full TLS" }}{{ end -}}
  {{- if not .Values.networkPolicy.enabled }}{{ fail "production NetworkPolicy cannot be disabled" }}{{ end -}}
  {{- if empty .Values.database.networkPeers }}{{ fail "explicit Postgres network peers are required" }}{{ end -}}
  {{- if lt (int .Values.replicas) 2 }}{{ fail "production serving requires at least two replicas" }}{{ end -}}
  {{- if and .Values.autoscaling.enabled (lt (int .Values.autoscaling.minReplicas) 2) }}{{ fail "production HPA minReplicas must be at least two" }}{{ end -}}
{{- end -}}
{{- $max := int .Values.replicas -}}
{{- if .Values.autoscaling.enabled }}{{ $max = int .Values.autoscaling.maxReplicas }}{{ end -}}
{{- if lt $max (int .Values.autoscaling.minReplicas) }}{{ fail "max replicas cannot be below min replicas" }}{{ end -}}
{{- if gt (add (mul 16 (add $max 1)) (int .Values.database.reservedConnections)) (int .Values.database.connectionBudget) }}{{ fail "Postgres budget must cover two releases, each with maxReplicas+1 surge pods at 8 connections, plus reserve" }}{{ end -}}
{{- if .Values.gpu.enabled -}}
  {{- if not (regexMatch "^[0-9a-f]{64}$" .Values.gpu.encoderID) }}{{ fail "GPU requires a content-addressed encoderID" }}{{ end -}}
  {{- $gpuImage := required "GPU image is required" .Values.gpu.image -}}
  {{- if and (not .Values.developmentMode) (not (regexMatch "@sha256:[0-9a-f]{64}$" .Values.gpu.image)) }}{{ fail "GPU image must be pinned by digest" }}{{ end -}}
  {{- if and .Values.gpu.autoscaling.enabled (empty .Values.gpu.autoscaling.queueMetric) }}{{ fail "GPU autoscaling requires a measured queue metric; CPU is not a GPU load signal" }}{{ end -}}
{{- end -}}
{{- end -}}
{{- define "gf.podSecurity" -}}
runAsNonRoot: true
runAsUser: 65532
runAsGroup: 65532
fsGroup: 65532
seccompProfile: {type: RuntimeDefault}
{{- end -}}
{{- define "gf.containerSecurity" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities: {drop: [ALL]}
{{- end -}}
{{- define "gf.dbEnv" -}}
- {name: PGHOST, value: {{ .Values.database.host | quote }}}
- {name: PGPORT, value: {{ .Values.database.port | quote }}}
- {name: PGDATABASE, value: {{ .Values.database.name | quote }}}
- {name: PGSSLMODE, value: {{ .Values.database.sslMode | quote }}}
{{- if ne .Values.database.sslMode "disable" }}
- {name: PGSSLROOTCERT, value: /run/postgres-ca/ca.crt}
{{- end }}
{{- end -}}
{{- define "gf.tlsMount" -}}
{{- if ne .Values.database.sslMode "disable" }}
- {name: postgres-ca, mountPath: /run/postgres-ca, readOnly: true}
{{- end }}
{{- end -}}
{{- define "gf.tlsVolume" -}}
{{- if ne .Values.database.sslMode "disable" }}
- name: postgres-ca
  secret: {secretName: {{ .Values.database.tlsSecret | quote }}, defaultMode: 0440}
{{- end }}
{{- end -}}
