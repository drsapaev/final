# Clinic Deployment Architecture

## Policy: One Clinic = One Isolated Deployment

This is a **mandatory architectural decision**, not a recommendation.

```text
Clinic A → Supabase A → Host A → Tunnel A → Brevo A → Sentry A
Clinic B → Supabase B → Host B → Tunnel B → Brevo B → Sentry B
Clinic C → Supabase C → Host C → Tunnel C → Brevo C → Sentry C
```

NOT multi-tenant:

```text
Supabase (single)
 ├── clinic_a schema    ← FORBIDDEN
 ├── clinic_b schema
 └── clinic_c schema
```

### Rationale

| Concern | Why isolated |
|---|---|
| PHI isolation | Clinic data isolated at the deployment/database boundary, reducing cross-clinic blast radius |
| Backup/restore | Restore Clinic A never touches Clinic B |
| Clinic decommission | Delete entire Supabase project + R2 bucket — done |
| Compliance | Each clinic's data residency can differ |
| Operational blame | One Sentry project per clinic = no alert mixing |
| Billing | Per-clinic cost is transparent |

## Component Topology

```text
Browser (clinic staff)
       ↓ HTTPS
Vercel (frontend, React SPA)
       ↓ API calls
api.<clinic-domain>
       ↓
Cloudflare Tunnel (per-clinic; prefer HTTP/2 unless QUIC explicitly validated on target ISP)
       ↓ localhost:18000
Windows Host (uvicorn, FastAPI)
       ↓
       ├── Supabase (PostgreSQL, per-clinic project)
       ├── Brevo SMTP (per-clinic or shared sender domain)
       ├── Sentry (per-clinic project: backend + frontend)
       └── Cloudflare R2 (backups, per-clinic bucket)
```

## What Lives Where

| Layer | Artifact | Portable via git? | Per-clinic? |
|---|---|---|---|
| Application code | Git repository | ✅ `git clone` | No — same code |
| Database schema | Alembic migrations | ✅ in repo | Schema same, data unique |
| Configuration | `backend/.env` | ❌ secrets | **Yes — all values unique** |
| Secrets | `.env` + ENCRYPTION_KEY | ❌ | **Yes** |
| Frontend build | Vercel | ❌ | Yes — env vars, domain |
| Database data | Supabase | ❌ | **Yes** |
| Offsite backups | Cloudflare R2 | ❌ | **Yes** |
| Email sender | Brevo | ❌ | Yes (see policy) |
| Error tracking | Sentry | ❌ | Yes |

## Deployment Flow (correct order)

```text
1. Release artifact (git revision pinned)
2. Runtime dependencies (pip install -r requirements.txt)
3. Clinic-specific .env + secrets
4. Database (create Supabase project)
5. Migrations (alembic upgrade head)
6. External services (Brevo, Sentry, R2, Vercel)
7. Host services (autostart, power, tunnel)
8. Verification (acceptance checklist)
```

**NOT** `git clone + pip install + alembic upgrade head` — that skips steps 3, 6, 7, 8.
