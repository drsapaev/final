# DEPLOYMENT_NEW_CLINIC

> **Orchestrator**: this document coordinates the deployment procedure.
> Detailed procedures live in the referenced sub-documents.
> **Installer must complete ALL steps before declaring deployment VERIFIED.**

## Policy

**One clinic = one isolated deployment.** See [CLINIC_DEPLOYMENT_ARCHITECTURE.md](../architecture/CLINIC_DEPLOYMENT_ARCHITECTURE.md).

## Prerequisites (accounts to create)

- [ ] Supabase project (free tier sufficient for pilot)
- [ ] Cloudflare account (tunnel + R2)
- [ ] Brevo account (SMTP — see policy below)
- [ ] Sentry account (backend + frontend projects)
- [ ] Vercel account (frontend hosting)
- [ ] Windows host with Python 3.11+. PostgreSQL 17 client tools must be installed; application resolves pg_dump/pg_restore through the repository resolver (`_resolve_pg_tool`). PATH presence is not required

## Brevo Policy

Two valid options — **record which one is chosen**:

| Option | Isolation | Billing | When to use |
|---|---|---|---|
| A: Shared Brevo account | Sender domain per clinic | Single bill | Same operator manages multiple clinics |
| B: Brevo per clinic | Full isolation | Separate bills | Different operators, max isolation |

## ENCRYPTION_KEY — Critical

```text
ENCRYPTION_KEY → encrypts .dump.enc artifacts (external Task Scheduler backup)
```

- Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- **Unique per clinic**
- **NOT in Git** — only in `.env`
- **Backup outside production host** (printed on paper / password manager)
- Restoration procedure: key + `.enc` file → decrypt → pg_restore
- **Verify restore with this key** before declaring deployment complete

> **Important**: R2 `.db.gz` artifacts created by `BackupService.create_backup()` are gzip-compressed but NOT encrypted with `ENCRYPTION_KEY`. They are protected by R2 bucket access controls. The `.dump.enc` artifacts from the external Task Scheduler script ARE encrypted. These are two separate artifact types with different protection models.

## Step-by-Step Procedure

### Phase 1: Supabase

| Step | Action | Verification |
|---|---|---|
| 1.1 | Create Supabase project | Dashboard shows project active |
| 1.2 | Copy `DATABASE_URL` — use the canonical Supabase session-pooler URI (`:5432`, db `postgres`). Verify with `SELECT current_database(), current_user` before proceeding | `.env` DATABASE_URL set |
| 1.3 | Run `alembic upgrade head` | 171 tables created, no errors |
| 1.4 | Enable RLS (deny-all baseline) on all application tables via Alembic migration | Verify: anon/authenticated roles cannot read PHI through Data API. Application authorization enforced by FastAPI/RBAC (not Supabase policies) |
| 1.5 | Verify: `SELECT count(*) FROM users` → 0 | Clean schema |

**Failure handling**: if alembic fails, check DATABASE_URL. Do NOT proceed without clean migration.

### Phase 2: Backend Host (Windows)

| Step | Action | Verification |
|---|---|---|
| 2.1 | Clone repo, `pip install -r requirements.txt` | `pip check` passes |
| 2.2 | Create `.env` from `.env.example` | All required vars filled |
| 2.3 | Generate `SECRET_KEY` (32+ chars) | Set in `.env` |
| 2.4 | Generate `ENCRYPTION_KEY` | Set in `.env` + backup outside host |
| 2.5 | Set `AUTO_BACKUP_ENABLED=true` | In `.env`. **Deployment acceptance requires actual scheduled backup artifact (non-zero, in R2), not just config presence** |
| 2.6 | Set `BACKUP_HOUR=2` `BACKUP_MINUTE=0` | In `.env` |
| 2.7 | Start uvicorn :18000 | `curl localhost:18000/api/v1/health` → 200 |
| 2.8 | Create autostart script | Startup folder: `clinic-api-autostart.cmd` |
| 2.9 | Disable sleep: `powercfg /change standby-timeout-ac 0` | `powercfg /query` shows 0x0 |
| 2.10 | Disable hibernate: `powercfg /change hibernate-timeout-ac 0` | Same |
| 2.11 | Disable unattended sleep: `powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP UNATTENDSLEEP 0` | Same |

**Failure handling**: if `alembic` not found, install: `pip install alembic`.

### Phase 3: Cloudflare Tunnel

| Step | Action | Verification |
|---|---|---|
| 3.1 | `cloudflared tunnel create <clinic-name>` | Credentials file created |
| 3.2 | DNS CNAME: `<subdomain>` → `<tunnel-id>.cfargotunnel.com` | DNS resolves |
| 3.3 | `config.yml`: ingress → `http://localhost:18000` | Config valid |
| 3.4 | Set `protocol: http2` in config.yml. Prefer HTTP/2 for this deployment unless QUIC has been explicitly validated on target ISP | Tunnel connects via HTTP/2 |
| 3.5 | `cloudflared tunnel run <clinic-name>` | `curl https://api.<domain>/api/v1/health` → 200 |
| 3.6 | Autostart script in Startup folder | Survives reboot |

**Failure handling**: if tunnel won't connect, check cloudflared logfile. Common: DNS not propagated (wait 5 min), wrong tunnel ID.

### Phase 4: Cloudflare R2

| Step | Action | Verification |
|---|---|---|
| 4.1 | Create bucket `<clinic-name>-db-backups` | Dashboard shows bucket |
| 4.2 | Create **backup-writer** token (Object Read & Write, scoped to this bucket) and **restore-reader** token (Object Read Only, same bucket). Production restore uses restore-reader; writer used for restore only as documented exception | 3 values obtained |
| 4.3 | Set `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` in `.env` | Present |
| 4.4 | Set lifecycle: `daily/` ×30d, `weekly/` ×84d | Dashboard shows rules |
| 4.5 | Test upload: run manual backup, verify in R2 | Object in `daily/` |
| 4.6 | Download + SHA256 verify | Checksum matches |

### Phase 5: Brevo SMTP

| Step | Action | Verification |
|---|---|---|
| 5.1 | Create sender `no-reply@<clinic-domain>` | Sender verified |
| 5.2 | Add DNS: SPF, DKIM (2 CNAMEs), DMARC | DNS records live |
| 5.3 | Verify domain in Brevo | All checks green |
| 5.4 | Create SMTP key → `SMTP_PASSWORD` in `.env` | Key works |
| 5.5 | Set `SMTP_FROM=no-reply@<clinic-domain>` | In `.env` |
| 5.6 | SMTP IP restriction must match the actual egress model. Disable only when the origin has no stable allowlisted IP (e.g. dynamic ISP). On VPS/static IP, keep IP allowlisting enabled | Security → IP blocking → Deactivated |
| 5.7 | Send test email via password-reset flow | Email delivered, link works |

### Phase 6: Sentry

| Step | Action | Verification |
|---|---|---|
| 6.1 | Create 2 projects: `<clinic>-backend` + `<clinic>-frontend` | Dashboard shows both |
| 6.2 | Copy DSNs → `.env` (SENTRY_DSN) + Vercel (VITE_SENTRY_DSN) | Set |
| 6.3 | Create alert rule: new issue, level error, env production, email to admin | Rule active |
| 6.4 | Send test event → verify email received | Email in inbox |

### Phase 7: Vercel (Frontend)

| Step | Action | Verification |
|---|---|---|
| 7.1 | Import repo → Vercel project | Build succeeds |
| 7.2 | Set env: `VITE_API_BASE_URL=https://api.<domain>` | Set |
| 7.3 | Set env: `VITE_SENTRY_DSN` | Set |
| 7.4 | Assign domain `<clinic-domain>` | HTTPS working |

### Phase 8: External Encrypted Backup (Task Scheduler)

> This phase creates a SEPARATE, ENCRYPTED backup pipeline that is independent
> from the internal `BackupService.create_backup()` R2 backups. The two systems
> produce different artifact types:
> - **R2 `.db.gz`** (internal scheduler): gzip-compressed, NOT encrypted with ENCRYPTION_KEY, protected by R2 access controls
> - **`.dump.enc`** (external Task Scheduler): Fernet-encrypted with ENCRYPTION_KEY, stored locally

The external backup script (`backups/backup_supabase.py`) is **gitignored** and must be manually deployed to the host. It is not part of the git repository.

| Step | Action | Verification |
|---|---|---|
| 8.1 | Copy `backups/backup_supabase.py` to host (path: `C:\final\backups\`) | File exists, `ENCRYPTION_KEY` present in `backend/.env` |
| 8.2 | Create Task Scheduler job: daily 03:00, runs `python backup_supabase.py` (cwd = `C:\final\backups`) | Task exists, last result = 0 |
| 8.3 | Run manually → verify `.dump.enc` file created (non-zero) | File present, SHA256 recorded |
| 8.4 | Verify ENCRYPTION_KEY: decrypt test file → pg_restore succeeds | Round-trip OK |

**Failure handling**: if pg_dump not found, ensure PostgreSQL 17 client tools installed (application resolver handles path; Task Scheduler context may differ from uvicorn). If `EMAXCONNSESSION`, wait for backend connection to release and retry.

### Phase 9: First Admin + Smoke Test

| Step | Action | Verification |
|---|---|---|
| 9.1 | Bootstrap admin user (script or registration) | User in DB |
| 9.2 | Login → `/auth/me` → 200 | Auth chain works |
| 9.3 | Change password → login with new password | Password change works |
| 9.4 | 2FA enrollment → verify TOTP code | 2FA works |
| 9.5 | Password recovery: initiate → email → click link → new password → login | E2E works |
| 9.6 | Create test patient → verify in list | CRUD works |
| 9.7 | WebSocket chat → connect + message | WS works |
| 9.8 | Sentry: trigger test error → verify in dashboard + email | Alerting works |
| 9.9 | Backup: run manual → verify R2 object | Backup works |
| 9.10 | Reboot → verify: uvicorn process = 1, cloudflared process = 1, tunnel registered (shared log), public API = 200, WS handshake OK | Full autostart + API chain works |

### Final Acceptance

```text
ALL boxes in Phases 1–9 checked
         ↓
STAGING_VALIDATION.md checklist passed
         ↓
scripts/smoke_test_staging.sh passed
         ↓
DEPLOYMENT VERIFIED ✅
```

**Any unchecked box = deployment NOT complete.**

> **STAGING_VALIDATION.md** covers: AI safety contract, arq worker, PII scrubbing, DR drill, unit/build tests, Sentry smoke, pre-commit hooks, Telegram bot. The automated smoke test (`scripts/smoke_test_staging.sh`) covers the critical path. Neither may be skipped.

---

## Related Documents

| Document | Purpose |
|---|---|
| [CLINIC_DEPLOYMENT_ARCHITECTURE.md](../architecture/CLINIC_DEPLOYMENT_ARCHITECTURE.md) | Architecture policy and topology |
| `CLINIC_ENV_REFERENCE.md` | All environment variables with source and criticality |
| `CLINIC_SECRETS_POLICY.md` | Secrets handling, ENCRYPTION_KEY management |
| `CLINIC_BACKUP_RESTORE_RUNBOOK.md` | Backup and restore procedures (to be created) |
| `CLINIC_DISASTER_RECOVERY_RUNBOOK.md` | DR procedures (to be created) |
| `CLINIC_UPDATE_RUNBOOK.md` | Production update procedure (to be created) |
