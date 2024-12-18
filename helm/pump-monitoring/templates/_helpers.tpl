{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "pump-monitoring.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "pump-monitoring.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "pump-monitoring.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Producer environment variables
*/}}
{{- define "pump-monitoring.producerEnv" -}}
- name: DATABASE_HOST
  value: {{ .Values.global.env.DATABASE_HOST | quote }}
- name: DATABASE_PORT
  value: {{ .Values.global.env.DATABASE_PORT | quote }}
- name: DATABASE_NAME
  value: {{ .Values.global.env.DATABASE_NAME | quote }}
- name: DATABASE_USER
  value: {{ .Values.global.env.DATABASE_USER | quote }}
- name: DATABASE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.global.env.KUBERNETES_CREDENTIALS_SECRET_NAME }}
      key: PATRONI_SUPERUSER_PASSWORD
- name: PUMP_ID
  value: {{ printf "%s-%s" .Values.global.env.PUMP_ID "${HOSTNAME}" | quote }}
- name: MONITORING_PROMETHEUS_PORT
  value: {{ .Values.global.env.MONITORING_PROMETHEUS_PORT | quote }}
- name: MONITORING_FLASK_PORT
  value: {{ .Values.global.env.MONITORING_FLASK_PORT | quote }}
- name: LOGGING_LEVEL
  value: {{ .Values.global.env.LOGGING_LEVEL | quote }}
- name: LOGGING_FORMAT
  value: {{ .Values.global.env.LOGGING_FORMAT | quote }}
- name: DATA_RETENTION_DAYS
  value: {{ .Values.global.env.DATA_RETENTION_DAYS | quote }}
- name: ENVIRONMENT_TYPE
  value: {{ .Values.global.env.ENVIRONMENT_TYPE | quote }}
{{- end }}