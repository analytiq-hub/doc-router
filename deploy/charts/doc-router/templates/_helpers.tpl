{{/*
Expand the name of the chart.
*/}}
{{- define "doc-router.name" -}}
{{- .Chart.Name }}
{{- end }}

{{/*
Common labels applied to all resources.
*/}}
{{- define "doc-router.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/name: {{ include "doc-router.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
