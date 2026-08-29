# CLINIC_SECRETS_POLICY

## Principles

1. **Secrets never in Git, chat, CI logs, or issues.**
2. **One clinic = one set of secrets.** No sharing between clinics.
3. **ENCRYPTION_KEY has an offsite backup** (paper / password manager) — loss = all backups unusable.
4. **Brevo SMTP key ≠ Brevo account password.** S3 API key ≠ Cloudflare dashboard password.
5. **Rotate after any suspected exposure.** Rotation procedure: create new → verify new works → deactivate old.

## Secret Inventory

| Secret | Where stored | Who creates it | Rotation trigger | Offsite backup |
|---|---|---|---|---|
| `SECRET_KEY` | backend/.env | Installer (generated) | Suspected compromise | Encrypted note |
| `ENCRYPTION_KEY` | backend/.env | Installer (Fernet.generate_key) | Never (unless compromised) | **Paper + password manager** |
| `DATABASE_URL` (with password) | backend/.env | Supabase creates | Suspected compromise | Password manager |
| `SMTP_PASSWORD` | backend/.env | Brevo (SMTP key) | Suspected compromise | Password manager |
| `R2_SECRET_ACCESS_KEY` | backend/.env | Cloudflare (API token) | Suspected compromise | Password manager |
| `SENTRY_DSN` | backend/.env + Vercel | Sentry project (public DSN) | N/A (send-only) | N/A |
| `TELEGRAM_BOT_TOKEN` | backend/.env | BotFather | Suspected compromise | Password manager |
| `SENTRY_AUTH_TOKEN` | Sentry dashboard only | Sentry (for API management) | Suspected compromise | Password manager |

## Brevo SMTP — Key Confusion Prevention

| Confusion | Fact |
|---|---|
| SMTP key value | This IS the password for SMTP auth |
| SMTP key name | NOT used for auth — only label in dashboard |
| Brevo account password | NOT used for SMTP — do not put in .env |
| Brevo API token (`cfat_…`) | NOT for SMTP — for Brevo REST API only |

## Cloudflare R2 — Key Model

| Key | Permissions | Scope |
|---|---|---|
| backup-writer | Object Read & Write | One bucket only |
| restore-reader | Object Read Only | Same bucket |
| dashboard | Full control | Managed by owner |

R2 does NOT support write-only tokens. Closest minimal model: bucket-scoped Read & Write + lifecycle rules managed by owner.

## Incident Response for Secret Exposure

1. Create replacement secret.
2. Update `.env`.
3. Restart backend.
4. Verify new secret works.
5. Deactivate old secret.
6. Document in incident log.

## ENCRYPTION_KEY Loss Recovery

```text
ENCRYPTION_KEY lost
       ↓
All encrypted backups (.dump.enc) undecryptable
       ↓
Recovery options:
  a) Offsite R2 backups if not encrypted
  b) Supabase built-in backup (if paid plan)
  c) Unrecoverable if neither exists
       ↓
Prevention: ENCRYPTION_KEY backup outside production host
           (paper + password manager + encrypted note to owner)
```
