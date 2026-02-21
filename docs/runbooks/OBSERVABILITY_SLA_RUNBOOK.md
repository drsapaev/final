# Observability SLA Runbook

## Scope
- Structured JSON request logs with `request_id` and `trace_id`
- SLA metrics for latency, error rate, and queue lag
- Runtime alerts via `alert_manager`

## Endpoints
- `GET /api/v1/observability/metrics`
  - Prometheus-style metrics payload
  - No auth (for internal scraper compatibility)
- `GET /api/v1/observability/sla`
  - Admin-only SLA snapshot and alert stats
- `GET /api/v1/observability/alerts?hours=24`
  - Admin-only recent observability alerts

## SLA Thresholds (env)
- `OBS_SLA_WINDOW_SECONDS=300`
- `OBS_SLA_LATENCY_P95_MS=1200`
- `OBS_SLA_ERROR_RATE_PCT=5`
- `OBS_SLA_QUEUE_LAG_MAX=50`

## Logging (env)
- `LOG_STRUCTURED=1`
- `LOG_LEVEL=INFO`

## Alert Policy
- `error_rate > OBS_SLA_ERROR_RATE_PCT` -> `AlertType.HIGH_ERROR_RATE`
- `p95 latency > OBS_SLA_LATENCY_P95_MS` -> `AlertType.SYSTEM_RESOURCE`
- `queue lag > OBS_SLA_QUEUE_LAG_MAX` -> `AlertType.QUEUE_ERROR`

`alert_manager` cooldown prevents alert storms.

## Quick Checks
1. `curl http://localhost:8000/api/v1/observability/metrics | head`
2. `curl -H "Authorization: Bearer <admin_token>" http://localhost:8000/api/v1/observability/sla`
3. `curl -H "Authorization: Bearer <admin_token>" http://localhost:8000/api/v1/observability/alerts?hours=1`
