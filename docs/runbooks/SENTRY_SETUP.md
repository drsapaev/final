# Sentry Setup Runbook

> **Last updated**: 2026-07-04
> **Status**: Active — DSNs created, env vars configured, code integrated.

This runbook documents how Sentry is wired into the clinic system and how to
manage the configuration.

---

## 1. Architecture

```
┌────────────────────┐    ┌────────────────────┐
│   Frontend (React) │    │  Backend (FastAPI) │
│                    │    │                    │
│  @sentry/react     │    │  sentry-sdk        │
│  + PII scrubbing   │    │  + FastAPI/SQLA/   │
│    in beforeSend   │    │    Redis/asyncPG   │
│                    │    │    integrations    │
└─────────┬──────────┘    └─────────┬──────────┘
          │                         │
          │   Sentry ingest URL    │
          └────────────┬───────────┘
                       ▼
              ┌────────────────────┐
              │  sentry.io         │
              │  org: clinic       │
              │  - clinic-frontend │
              │  - clinic-backend  │
              └────────────────────┘
```

**Two separate Sentry projects**:
- `clinic-frontend` — captures React errors + browser performance traces
- `clinic-backend` — captures FastAPI errors + SQLAlchemy queries + Redis ops

PII is scrubbed in **three layers** before any event leaves your infra:
1. **Code**: backend `pii_masker.py` scrubs dicts before logging
2. **Logs**: `PIIMaskingFilter` scrubs log records before they hit stdout
3. **Sentry**: `beforeSend` callback (in `sanitize_event`) scrubs request bodies + breadcrumbs + extras
   before the event is sent to sentry.io

Backend layers (Code + Logs + Sentry) all delegate to `mask_pii()` from
`pii_masker.py` — the single source of truth for backend PII patterns
(`PII_FIELD_PATTERNS`). Frontend has its own `MEDICAL_PII_KEYS` list in
`frontend/src/services/sentry.ts` (separate concern, more aggressive —
includes auth tokens and payment fields per BS-57).

Medical field names redacted at all 3 backend layers: `iin`, `passport_number`,
`phone`, `email`, `diagnosis`, `complaints`, `prescription`, `medications`,
`allergies`, `first_name`, `last_name`, `birth_date`, `address`, etc.

---

## 2. DSNs (Data Source Names)

DSNs are **safe to commit** to code/config — they are public send-only keys.
The secret part (`sntrys_...`) is only the `SENTRY_AUTH_TOKEN` used for
source map upload (CI-only, never in client code).

### Frontend (React PWA)

```
VITE_SENTRY_DSN=https://57fde20209e223ec5a4a96e3a5a59fa2@o4511673323749376.ingest.us.sentry.io/4511673366282240
```

- **Org ID**: `o4511673323749376`
- **Project ID**: `4511673366282240`
- **Region**: US (`us.sentry.io`)

### Backend (FastAPI)

```
SENTRY_DSN=https://65b5195082de2f0522c27dd6695536b7@o4511673323749376.ingest.us.sentry.io/4511673347670016
```

- **Org ID**: `o4511673323749376`
- **Project ID**: `4511673347670016`
- **Region**: US (`us.sentry.io`)

---

## 3. Where to set the env vars

### Frontend (Vercel)

```
Vercel → drsapaev/final project → Settings → Environment Variables
```

Add the following (all required for full functionality):

| Name | Value | Environments |
|---|---|---|
| `VITE_SENTRY_DSN` | `https://57fde20209e223ec5a4a96e3a5a59fa2@o4511673323749376.ingest.us.sentry.io/4511673366282240` | Production, Preview |
| `VITE_SENTRY_ENV` | `production` (for prod) / `preview` (for previews) | Production, Preview |
| `VITE_SENTRY_TRACES_SAMPLE_RATE` | `0.05` (5% perf traces) | Production, Preview |
| `VITE_APP_VERSION` | `0.9.0` (matches `package.json` version) | Production, Preview |

For **source map upload** (recommended — makes stack traces readable):

| Name | Value | Environments |
|---|---|---|
| `SENTRY_AUTH_TOKEN` | `sntrys_...` (create in Sentry → Settings → Auth Tokens) | All (CI/preview/prod) |
| `SENTRY_ORG` | your Sentry org slug (visible in URL: `sentry.io/organizations/SLUG/`) | All |
| `SENTRY_PROJECT` | `clinic-frontend` | All |

To create auth token:
1. https://sentry.io/settings/account/api/auth-tokens/
2. Create new token
3. Scopes: `org:read`, `project:releases`, `team:read`
4. **Store in GitHub secrets** (not in repo): `Settings → Secrets and variables → Actions → New repository secret → SENTRY_AUTH_TOKEN`

### Backend (Docker Compose / staging env)

Update `ops/compose.staging.yml` `worker` + `backend` services, or set in
your deployment env file:

```bash
# /etc/clinic/backend.env or docker-compose env_file
SENTRY_DSN=https://65b5195082de2f0522c27dd6695536b7@o4511673323749376.ingest.us.sentry.io/4511673347670016
SENTRY_ENV=staging               # or 'production'
SENTRY_TRACES_SAMPLE_RATE=0.05
APP_VERSION=0.9.0
```

---

## 4. Verify it works

### Frontend smoke test

After deploying to Vercel with `VITE_SENTRY_DSN` set:

1. Open your deployed frontend URL in browser
2. Open DevTools Console
3. Run:
   ```js
   setTimeout(() => { throw new Error("smoke test sentry frontend") }, 1000)
   ```
4. Wait 10 seconds
5. Check Sentry dashboard → Issues → should see `Error: smoke test sentry frontend`

### Backend smoke test

SSH into the server or run locally with `SENTRY_DSN` set:

```bash
# Trigger a test exception via Python shell
cd backend
python -c "
import os
os.environ['SENTRY_DSN'] = 'https://65b5195082de2f0522c27dd6695536b7@o4511673323749376.ingest.us.sentry.io/4511673347670016'
from app.core.sentry import init_sentry, capture_exception
init_sentry()
try:
    raise RuntimeError('smoke test sentry backend')
except RuntimeError as e:
    capture_exception(e)
print('Sent. Check Sentry dashboard in 10 seconds.')
"
```

### PII scrubbing verification

Verify PII is redacted before sending. Run with a fake patient dict using
`sanitize_event` (the same function `before_send` calls):

```python
from app.core.sentry import sanitize_event
fake_event = {
    "request": {
        "method": "POST",
        "url": "/api/v1/patients",
        "body": {
            "first_name": "Akmal",
            "phone": "+998901234567",
            "iin": "12345678901234",
            "diagnosis": "I10 Essential hypertension",
        }
    }
}
sanitize_event(fake_event)
print(fake_event)
# Expected:
# {
#   "request": {
#     "method": "POST",                       ← preserved
#     "url": "/api/v1/patients",              ← preserved
#     "body": {
#       "first_name": "A.",                   ← partial-mask (initials)
#       "phone": "+998901•••567",             ← partial-mask (debug-friendly)
#       "iin": "[REDACTED]",                  ← full redact (identifier)
#       "diagnosis": "[REDACTED]"             ← full redact (medical)
#     }
#   }
# }
```

Note: `mask_pii()` (the function backing `sanitize_event`) applies
**partial masking** for some fields (`phone`, `email`, `name`, `birth_date`)
to preserve debug structure, and **full redaction** for identifiers and
medical content. Free-text strings also get regex scrubbing for
phone/email/passport/IIN patterns embedded anywhere in the value.

If any PII leaks through, the test above will reveal it.

---

## 5. What gets captured (and what doesn't)

### Captured automatically

| Event type | Frontend | Backend |
|---|---|---|
| Unhandled exceptions | ✅ | ✅ |
| Promise rejections | ✅ | ✅ (async) |
| HTTP 5xx responses | ✅ (via fetch interceptor) | ✅ (FastAPI middleware) |
| Slow DB queries | — | ✅ (>1s threshold via SQLAlchemy integration) |
| WebSocket disconnects | ✅ | ✅ (Redis pubsub) |
| Failed AI API calls | ✅ | ✅ |
| Visit reminder send failures | — | ✅ (arq worker raises → retry → capture) |

### NOT captured (by design)

- 4xx client errors (e.g. 404, 403) — not bugs, don't pollute Sentry
- Health check endpoints (`/api/v1/health`)
- Successful operations
- Patient PII (redacted in `beforeSend`)
- Auth tokens / passwords (never logged anywhere)
- Static asset 404s (CDN issue, not app bug)

### Performance traces

5% of requests get a performance trace (configured via
`SENTRY_TRACES_SAMPLE_RATE=0.05`). This shows:
- Endpoint → DB query → Redis call → external API call timing breakdown
- Slowest 5% of requests (p95/p99)
- Database query analysis (which SQL is slow)

Errors are **always** captured regardless of sample rate.

---

## 6. Alerting (recommended setup)

In Sentry UI, create the following alert rules:

### P0 — immediate page

1. **New issue in production** (any project)
   - Notify: Slack `#clinic-alerts` + email
   - Throttle: 1 notification per issue per hour

2. **Issue affecting 5+ users in 5 minutes**
   - Notify: Slack `#clinic-alerts` + SMS
   - This is a "regression wave" — usually means deploy broke something

3. **Backend 500 error rate > 1% over 5 min**
   - Notify: Slack `#clinic-alerts` + Telegram bot
   - Production down scenario

### P1 — daily digest

4. **Daily issue digest** at 09:00 local time
   - Notify: email
   - Summary of new issues + most frequent

### P2 — weekly

5. **Weekly performance regression report**
   - Compare p95 latency this week vs last week
   - Notify: email

To create: Sentry UI → Alerts → Create Alert → choose rule type.

---

## 7. Source map upload (frontend only)

Without source maps, Sentry shows minified stack traces like:
```
at t.render (chunk-abc123.js:1:45678)
```

With source maps uploaded, Sentry shows:
```
at PatientPanel.render (src/pages/PatientPanel.jsx:42:15)
```

### Setup

1. **Install the plugin** (one-time):
   ```bash
   cd frontend && npm install --save-dev @sentry/vite-plugin
   ```

2. **Set CI env vars** (Vercel or GitHub Actions):
   - `SENTRY_AUTH_TOKEN` — created at https://sentry.io/settings/account/api/auth-tokens/
   - `SENTRY_ORG` — your org slug (visible in URL bar)
   - `SENTRY_PROJECT=clinic-frontend`

3. **Verify**: trigger a frontend error, check Sentry → issue → should show
   `src/pages/...jsx:42` instead of `chunk-...js:1:45678`.

If you see `chunk-...js` in Sentry, source maps aren't uploading. Check:
- `@sentry/vite-plugin` installed? (`npm ls @sentry/vite-plugin`)
- `SENTRY_AUTH_TOKEN` set in CI?
- Build log should show `[sentry] uploading source maps...`

---

## 8. Cost management

### Free tier limits (Sentry Developer plan)

- **5 000 errors/month** — both projects combined
- **10 000 performance transactions/month**
- **50 replay sessions/month** (disabled by default)

### If you exceed limits

1. **Reduce noise**: filter out expected errors (network blips, aborts) in `beforeSend`:
   ```js
   if (event.exception.values[0].value.includes('NetworkError')) return null
   ```

2. **Lower sample rate**: change `VITE_SENTRY_TRACES_SAMPLE_RATE` from `0.05` to `0.01`

3. **Self-host**: run Sentry in Docker (https://github.com/getsentry/self-hosted)
   - ~2GB RAM, 50GB disk
   - Free unlimited errors
   - But you maintain it

### Monitoring your usage

Sentry UI → Settings → Subscription → see current usage stats.

---

## 9. Incident response: "Sentry is silent"

If you suspect Sentry isn't capturing errors:

### Quick checks

1. **DSN set?**
   ```bash
   # Frontend (in browser DevTools):
   console.log(import.meta.env.VITE_SENTRY_DSN)

   # Backend (in shell):
   echo $SENTRY_DSN
   ```

2. **SDK initialized?**
   ```js
   // Frontend
   import * as Sentry from '@sentry/react'
   console.log('Sentry client:', Sentry.getClient())
   ```

   ```python
   # Backend
   import sentry_sdk
   print('Sentry hub:', sentry_sdk.Hub.current.client)
   ```

3. **Network reachable?**
   ```bash
   curl -I https://o4511673323749376.ingest.us.sentry.io
   # Should return 200 or 404 (both mean: reachable)
   ```

4. **Rate limited?**
   - Sentry free tier rate limits at 50 events/min per project
   - Check Sentry UI → Settings → Quotas

5. **Ad blocker?**
   - Browser ad blockers sometimes block sentry.io
   - Test in incognito mode

### If still silent

- Check backend logs for `[sentry] initialized` message
- Check Sentry UI → Settings → Projects → check "Last received event" timestamp
- Try the smoke tests in section 4 above

---

## 10. Maintenance

### Rotating DSN

If DSN is compromised (rare, but possible):

1. Sentry UI → Settings → Projects → clinic-frontend → Client Keys
2. Disable old DSN, generate new one
3. Update Vercel env var `VITE_SENTRY_DSN`
4. Update backend env var `SENTRY_DSN`
5. Redeploy both

### Adding new PII fields

If a new medical field is added to the schema that should be scrubbed:

1. **Backend** (single source of truth for backend layers):
   - Add field name to `PII_FIELD_PATTERNS` in `backend/app/core/pii_masker.py`
     (line ~30). This list is used by `mask_pii()`, which is in turn used by
     `PIIMaskingFilter` (log layer) and `sanitize_event` (Sentry layer).
2. **Frontend** (separate concern, only if relevant to browser surface):
   - Add field name to `MEDICAL_PII_KEYS` in `frontend/src/services/sentry.ts`
     (line ~24). Frontend has a more aggressive list that also includes auth
     tokens and payment fields (per BS-57).
3. Add a test case to `backend/tests/unit/test_pii_masker.py` (backend) and/or
   `frontend/src/services/__tests__/sentry.test.ts` (frontend).

The two lists are **intentionally separate** — backend focuses on medical
PHI, frontend covers a wider browser surface (auth tokens, payment fields).
They do not need to mirror each other.

### Removing Sentry

If you decide to stop using Sentry:

1. Remove env vars (`SENTRY_DSN`, `VITE_SENTRY_DSN`) from Vercel + backend env
2. Code automatically becomes no-op (init_sentry returns early if DSN is empty)
3. Optionally remove the `@sentry/react` + `sentry-sdk` deps from package.json
4. Optionally delete `frontend/src/services/sentry.ts` + `backend/app/core/sentry.py`

---

## 11. Related files

| File | Purpose |
|---|---|
| `frontend/src/services/sentry.ts` | Sentry init for React + PII scrubbing in `beforeSend` |
| `frontend/src/main.jsx` | Calls `initSentry()` on app startup |
| `frontend/vite.config.js` | Optional `@sentry/vite-plugin` for source map upload (CI only) |
| `backend/app/core/sentry.py` | Sentry init for FastAPI + PII scrubbing + integrations |
| `backend/app/main.py` | Calls `init_backend_sentry()` after logging setup |
| `backend/app/core/pii_masker.py` | PII scrubbing for Python logging (3rd layer) |
| `backend/requirements-monitoring.txt` | `sentry-sdk[fastapi]>=2.61.1` |
| `frontend/package.json` | `@sentry/react@^8.47.0` |
| `frontend/.env.example` | Documents all Sentry env vars |
| `backend/.env.example` | Documents all Sentry env vars |
