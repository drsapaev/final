# 2026-09-06 — Cloudflare Tunnel cutover: external 530 window (~10 min) during Windows-Service migration

## Summary

During the planned cutover of the `api.finalclinic.fyi` Cloudflare Tunnel from a
login-session user-process to a Windows Service, production API availability was
lost externally for approximately 10 minutes (HTTP 530, Cloudflare error 1033 —
edge could not reach any tunnel connector). Patient-facing impact window:
2026-09-06 ~06:25–06:35 +0500. No data was lost; backend (uvicorn :18000) was
healthy locally throughout — this was purely an ingress (tunnel connector)
outage.

## Timeline

| Time (+0500) | Event |
|---|---|
| Sep 5 ~21:17 | Pre-cutover state: tunnel carried by a login-session user-process (PID 16848); a first UAC pass had installed the cloudflared service, but the stock `cloudflared service install` registers a **remote-managed agent** (binPath without arguments) that never registers the named config tunnel — external probes still 200 via the user-process. |
| Sep 6 ~06:2x | Fix attempt: ImagePath corrected to `tunnel run` (registry), boot tasks created, then `Restart-Service` issued. |
| 06:2x | **Primary failure**: the service hung in `STOP_PENDING` — the agent does not reliably answer `SERVICE_CONTROL_STOP`; `Restart-Service` (no timeout) waited indefinitely. Concurrently the serving user-process tunnel disappeared. With zero live connectors, Cloudflare edge answered **530/1033**. |
| ~06:3x | Restore: user-process tunnel relaunched from the known-good command line → external 200×3. |
| ~06:4x | Rescue (elevated): force-killed the STOP_PENDING service process (PID 13540) → the stop completed and the service started under the corrected ImagePath (new PID), registered the tunnel. |
| ~06:5x | Cutover completed: user-process retired, service-only external **200×5**; crash-drill (kill service PID → SCM recovery restart/5000 → Running with new PID in ≤6 s) passed; WS path verified (101 on `/ws/chat` through the tunnel; `/ws/queue/auth` 403-parity local==external documented separately). |

## Root causes

1. **Wrong service mode**: `cloudflared service install` (2026.8.2) creates a
   remote-managed agent; a locally-managed named tunnel needs an explicit
   `tunnel run <name>` in binPath. `Status=Running` alone proved nothing — the
   service was "running" without serving the tunnel (the exact anti-pattern the
   acceptance criteria warned against).
2. **Unbounded stop**: `Restart-Service` has no timeout; the agent can ignore
   stop requests, hanging the cutover script in an infinite
   `Ожидание остановки службы` loop.
3. **Cutover order defect**: the fallback connector (user-process) was removed
   before the service connector proved tunnel registration — during the overlap
   there was no serving connector at all.

## Corrective actions

- Service binPath fixed via registry (`ImagePath = "…cloudflared.exe" tunnel run`);
  config (logfile, tunnel id, credentials) duplicated into
  `C:\Windows\System32\config\systemprofile\.cloudflared`.
- SCM recovery policy: `sc failure cloudflared reset= 0 actions= restart/5000/restart/50000/restart/300000`
  (verified live: process kill → Running with new PID in ≤6 s).
- Boot tasks (SYSTEM, AtStartup): `ClinicBackendBootAutostart` (uvicorn headless)
  and `CloudflaredBootTunnelCheck` (writes `tools/boot_tunnel_check.log` samples
  with svc/proc/local/external/registrations **before any user login**).
- Startup-folder `.cmd`: tunnel line retired (service owns the tunnel now);
  backend netstat guard kept.
- `tools/cloudflared_service_fix.ps1` hardened (v3): bounded stop (30 s) →
  force-kill rescue → bounded start wait (45 s). `Restart-Service` without a
  timeout must never be used on this service again.
- Runbook rule for any future cutover: **keep the fallback connector up until
  the new connector proves tunnel registration** (fresh `Registered tunnel
  connection` log lines attributable to the new process), then retire the
  fallback, then verify external health.

## Follow-ups

- Watchdog as a second recovery layer (detects a live-but-stuck connector) —
  proposed, not implemented.
- `docs/ROLES_AND_ROUTING.md`-style ops runbook entry for tunnel operations.

## Impact

External API unavailable ~10 min (530). Frontend (Vercel) stayed up; backend
locally healthy; no writes lost (writes cannot arrive without ingress).
Uptime Monitor CI caught the earlier (unrelated) window of the same day — the
monitoring layer worked as designed.
