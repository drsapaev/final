[<- Previous Page](ARCHITECTURE.md) | [Back to README](../README.md) | [Next Page ->](SECURITY_CHECKLIST.md)

# API Notes

This is a recovery-oriented API map, not a complete endpoint reference.

## Source Of Truth

- Router composition: `backend/app/api/v1/api.py`
- OpenAPI runtime: start backend and inspect `/docs` or `/openapi.json`
- Auth dependency anchor: `backend/app/api/deps.py`

## Important Mounted Areas

| Area | Notes |
|---|---|
| Auth | Canonical login should use the 2FA-aware authentication flow. Fallback auth routers are disabled by default. |
| Patients/visits | Critical registrar and doctor workflow surface. Visit read RBAC was tightened in recovery. |
| Queue/QR | Multiple queue surfaces exist; queue SSOT tests should stay green before consolidation. |
| EMR | EMR v2 and EMR AI routes exist; AI-assisted outputs must remain draft-only. |
| Payments | There are singular and plural webhook surfaces. Provider-canonical callback ownership still needs follow-up. |
| Telegram | Multiple Telegram routers exist. Patched webhook surfaces now fail closed without a configured secret. |
| AI | `/ai/v2` gateway is safer than legacy `/ai`; legacy `/ai` now has a coarse RBAC gate but still needs migration. |

## API Safety Rules

- Validate input at endpoints or schemas.
- Check permissions in every protected endpoint.
- Avoid returning internal exception text to clients.
- Do not log tokens, secrets, raw webhook payloads, or patient-sensitive details.
- Use retryable HTTP status codes for retryable webhook processing failures.
- Keep payment callbacks idempotent.

## See Also

- [Architecture](ARCHITECTURE.md)
- [Security Checklist](SECURITY_CHECKLIST.md)
- [Testing](TESTING.md)
