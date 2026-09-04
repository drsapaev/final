# CLINIC_HOST_AVAILABILITY_RUNBOOK

**Single-origin reality:** `api.finalclinic.fyi` terminates on ONE Windows host
(`C:\final`). Cloudflare/Vercel/Supabase are external, but the API itself is
only as available as this machine. Everything below is an **availability
dependency**, not a preference. This host = controlled-pilot origin;
"not high-availability production" is an explicit, accepted limitation (#2772).

## 1. Power settings — availability dependency (owner decision 2026-08-27)

The machine must never sleep on mains. Sleep = tunnel down = API down for
every clinic user, and missed nightly backups (RPO breach).

Mandatory values (re-apply after any Windows power-plan change):

```bat
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /setacvalueindex SCHEME_CURRENT SUB_SLEEP UNATTENDSLEEP 0
powercfg /setactive SCHEME_CURRENT
```

`UNATTENDSLEEP` is the hidden timeout (default 2 min) that overrides the
visible one after an unattended wake — it silently slept the host at
02:33 on 2026-08-28 even with `standby-timeout-ac 0` set.

Verification:

```bat
powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE   → AC index 0x00000000
powercfg /query SCHEME_CURRENT SUB_SLEEP UNATTENDSLEEP → AC index 0x00000000
```

## 2. Autostart chain (survives reboot, proven 2026-08-27)

- Startup folder: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\clinic-api-autostart.cmd`
  (source: `tools/start_backend_tunnel_boot.cmd`) — starts uvicorn :18000 if
  not listening, then cloudflared.
- Tunnel config: `%USERPROFILE%\.cloudflared\config.yml` — **`protocol: http2`**
  is mandatory (QUIC streams died under UDP loss, 2026-08-27; keep http2).
- `--logfile` is a TOP-LEVEL cloudflared flag and must precede `tunnel run`.

## 3. Nightly backup chain (armed 2026-08-28)

`AUTO_BACKUP_ENABLED=true` in `backend/.env` (was the silent blocker —
scheduler never armed without it), `BACKUP_HOUR=2 BACKUP_MINUTE=0`
(**local time**, UTC+5 → 21:00Z). Chain per night, all five steps must hold
for the #2773 mutation-window counter:

`scheduler fires` → `pg_dump` → `non-zero artifact` → `SHA256` →
`R2 upload` → `R2 verify (HEAD digest)`.

Evidence strings in `tools/uvicorn_restart.log`:
`⏰ Next backup scheduled for:` (arming) · `🔄 Starting scheduled backup...`
(wake) · `✅ Scheduled backup completed:` (chain done; artifact auto-uploads
to R2 `daily/`). A missing ⏰ line after any restart means the scheduler did
NOT arm — check `AUTO_BACKUP_ENABLED` first.

## 4. Morning-after checklist

1. `curl https://api.finalclinic.fyi/api/v1/health` → `{"ok":true,"db":"ok"}`.
2. `backend/backups/` has today's `backup_scheduled_*.db.gz` (>0 bytes).
3. R2 bucket `finalclinic-db-backups` lists the same key under `daily/`.
4. `tools/cloudflared.log` tail shows 4× `Registered tunnel connection`
   without repeated `Serve tunnel error` bursts.
5. If any step fails: machine awake? backend process alive (`netstat :18000`)?
   cloudflared alive (`tasklist`)? Then apply §1/§2 and re-check.

## 5. Known operational boundaries

- Host sleep/hibernate on AC = **forbidden** (§1).
- No process supervisor yet: a killed uvicorn stays dead until reboot or
  manual start — chaos-scenario #1 in #2774 measures this deliberately
  before any watchdog decision.
- Offsite copies live in R2 (`daily/` ×30d, `weekly/` ×84d lifecycle,
  owner-managed). Local copies are convenience, not the backup of record.
