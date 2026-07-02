[<- Previous Page](API.md) | [Back to README](../README.md) | [Next Page ->](AI_MODULE.md)

# Security Checklist

This checklist describes privacy/security readiness gaps. It does not claim HIPAA, GDPR, or local-law compliance.

## Current Recovery Status

| Area | Status | Notes |
|---|---|---|
| Authentication | Improved | Canonical frontend login no longer targets minimal-login; fallback auth disabled by default. |
| 2FA | Improved | Existing 2FA tests were expanded in recovery, but full auth CI still needs a clean run. |
| RBAC | Improved but incomplete | Visit read RBAC tightened; patient-own-data linkage still has known gaps. |
| Secrets | Improved | Tracked auth fixture files removed from the worktree; recurrence-prevention ignore rules added; rotation status must be handled outside repo if reused anywhere. |
| Payments | Improved but incomplete | Singular webhook errors now return retryable status; duplicate callback ownership still unresolved. |
| Uploads | Improved | Simple upload disabled unless explicitly enabled and has basic metadata gates. |
| Telegram | Improved but incomplete | Patched webhook routes fail closed without secret; retry/outbox and PHI minimization need follow-up. |
| AI | Improved but incomplete | Draft-only boundary added to EMR AI and visible assistant; mock-provider policy still unresolved. |
| Database | Partially verified | Alembic chain linear with head `0022_service_audit_log`; clean online upgrade blocked locally because no disposable PostgreSQL target with create/drop permission was available. |
| Logging | Mixed | Some sensitive logging was reduced; additional screens/services need review. |

## Required Before Production

- Run secret scanning on repository and deployment artifacts.
- Confirm historical credential-like artifacts are either rotated externally or formally accepted as non-reused development artifacts.
- Prove no enabled auth route issues an access token before required 2FA.
- Run RBAC tests for all staff roles and cross-patient denial paths.
- Verify payment signatures, idempotency keys, duplicate prevention, and reconciliation.
- Confirm uploads are stored outside the code tree and protected by size, MIME, extension, filename, and scan policy.
- Confirm Telegram webhook `secret_token` is required and persisted without being returned to clients.
- Ensure logs do not include tokens, raw webhook bodies, patient names/phones, or payment secrets.
- Decide whether mock AI is allowed outside explicit dev/demo mode.
- Verify backup/restore and rollback on the target deployment contour.

## Credential Artifact Policy

- Do not recover credentials from repository history, docs, local auth payloads, profile token files, or removed auth fixtures.
- Do not print token, password, database URL, secret, or credential values while auditing cleanup status; record filenames and classifications only.
- Treat any historically tracked credential-like value as untrusted and non-production. If it was ever reused outside local development, rotate it in the owning external system.
- Do not rewrite git history or delete historical commits without explicit human approval, a backup plan, and a coordinated force-push window.
- Keep recurrence-prevention patterns in `.gitignore` for local auth payloads, auth diff artifacts, temporary auth fixtures, environment files, and private keys.

## See Also

- [AI Module](AI_MODULE.md)
- [Deployment](DEPLOYMENT.md)
- [Project Audit](PROJECT_AUDIT.md)
