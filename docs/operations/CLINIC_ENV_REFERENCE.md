# CLINIC_ENV_REFERENCE

> **Every environment variable** the application reads, with source, criticality, and failure impact.
> Installer must verify ALL "Required" variables before starting the backend.

## Backend (backend/.env)

| Variable | Required | Secret | Source | Impact if missing/wrong |
|---|---|---|---|---|
| `DATABASE_URL` | ✅ | 🔴 | Supabase dashboard → Settings → Database | App won't start; all queries fail |
| `SECRET_KEY` | ✅ | 🔴 | Generated (`secrets.token_hex(32)`) | JWT invalid → nobody can login |
| `ENCRYPTION_KEY` | ✅ | 🔴 | Generated (`Fernet.generate_key()`) | Backups undecryptable |
| `AUTO_BACKUP_ENABLED` | ✅ | — | Set `true` | **Nightly backups never fire** (silent) |
| `BACKUP_HOUR` | ✅ | — | Set `2` | Backup time (local) |
| `BACKUP_MINUTE` | ✅ | — | Set `0` | Backup minute |
| `SMTP_SERVER` | ✅ | — | Brevo: `smtp-relay.brevo.com` | No email delivery |
| `SMTP_PORT` | ✅ | — | Brevo: `587` | — |
| `SMTP_USERNAME` | ✅ | 🟡 | Brevo SMTP key name | Auth failure |
| `SMTP_PASSWORD` | ✅ | 🔴 | Brevo SMTP key value | Auth failure |
| `SMTP_FROM` | ✅ | — | Verified sender domain | Emails rejected/spam |
| `SMTP_USE_TLS` | ✅ | — | `true` | — |
| `R2_ACCOUNT_ID` | ✅* | 🟡 | Cloudflare R2 → API tokens | Offsite backups skipped silently |
| `R2_ACCESS_KEY_ID` | ✅* | 🟡 | Cloudflare R2 → API tokens | Same |
| `R2_SECRET_ACCESS_KEY` | ✅* | 🔴 | Cloudflare R2 → API tokens | Same |
| `R2_BUCKET` | ✅* | — | Chosen bucket name | Same |
| `SENTRY_DSN` | ✅ | 🟡 | Sentry project settings | No error tracking |
| `ENV` | ✅ | — | `production` | Controls fail-fast on bad SECRET_KEY |
| `CORS_ORIGINS` | ✅ | — | Frontend URL(s) | CORS errors from frontend |
| `FRONTEND_URL` | ✅ | — | Frontend URL | Password-reset links wrong |
| `TELEGRAM_BOT_TOKEN` | — | 🔴 | BotFather | Telegram notifications disabled |
| `GOOGLE_APPLICATION_CREDENTIALS` | — | 🔴 | Firebase console | Push notifications disabled |
| `SMS_API_KEY` | — | 🔴 | SMS provider | SMS recovery not available |

*`R2_*` variables: if absent, backup still works locally but offsite is skipped (`offsite: skipped`).*

## Frontend (Vercel env vars)

| Variable | Required | Secret | Source | Impact if missing |
|---|---|---|---|---|
| `VITE_API_BASE_URL` | ✅ | — | `https://api.<clinic-domain>` | Frontend can't reach API |
| `VITE_SENTRY_DSN` | ✅ | 🟡 | Sentry frontend project | No frontend error tracking |

## Task Scheduler (external)

| Variable | Required | Source | Impact if wrong |
|---|---|---|---|
| `ENCRYPTION_KEY` | ✅ | Same as backend .env | Encrypted backups undecryptable |

## Deployment Policy

- **One clinic = one isolated deployment = one set of all values above.**
- **No sharing of secrets between clinics.**
- **ENCRYPTION_KEY must be backed up outside the production host.**
- `log_statement='mod'` on Supabase is a separate hardening task (not set by default).

## Known Traps (from live incidents)

| Trap | Impact | Reference |
|---|---|---|
| `pg_dump` not on PATH | Nightly backups silently fail | #2853 |
| `AUTO_BACKUP_ENABLED` missing/false | Scheduler never armed | #2772 |
| `SMTP_FROM` not verified in Brevo | Emails rejected | — |
| Brevo IP blocking enabled | 525 errors on dynamic ISP IP | — |
| Windows sleep on AC | API down + missed backups | runbook §1 |
| `log_statement` not `'mod'` | DML invisible in Supabase logs | #2877 |
