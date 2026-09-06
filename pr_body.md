## Summary

- Adds `docs/incidents/2026-09-06-cloudflared-tunnel-cutover-530-window.md` — the operational incident record requested after the cloudflared Windows-Service cutover: a ~10-minute external 530 window (Cloudflare 1033, zero live connectors) during the tunnel cutover.
- Documents the three root causes (remote-managed service mode vs named-tunnel `tunnel run`; unbounded `Restart-Service` hanging in STOP_PENDING; fallback connector retired before service registration proof), all corrective actions already applied (binPath fix, SCM recovery policy, boot SYSTEM tasks, Startup .cmd retirement, hardened fix script v3), and the runbook rule for any future cutover.
- Docs-only change: no code, no schema, no runtime surface touched.

## Cyclic Execution Evidence

- Fresh main sync: worktree cut from `origin/main` `649150b13` (post-#3067).
- Clean workspace: worktree contains exactly one new file; `git diff --check` clean.
- Branch: `docs/incident-tunnel-cutover-530`.
- Scope gate: single-purpose incident record; no unrelated changes.
- Red-check handling: not applicable - docs-only change introduces no executable surface; all CI checks expected green from the pristine base.

## Contract Impact

- Canonical surface: none - adds a markdown document under `docs/incidents/` (established incident-record location, precedent 2026-09-02).
- Request shape: not applicable - no API surface touched.
- Response shape: not applicable - no API surface touched.
- Status codes: not applicable - no API surface touched.
- Frontend consumer: none - document is not imported anywhere.
- Compatibility path or alias: not applicable - documentation only, no vocabulary change.
- Contract proof: `git diff` touches exactly one new `.md` file; openapi/api-types unchanged.

## RBAC / Permissions

- Roles allowed: unchanged - no authorization surface touched.
- Roles denied: unchanged - no authorization surface touched.
- Positive auth proof: not applicable - no auth path changed.
- Negative auth proof: not applicable - no auth path changed.

## Notification / Realtime

- Event type or websocket channel: not applicable - no realtime channel touched.
- Payload version / ack behavior: not applicable - no payload contract exists in this change.
- Read/unread or delivery semantics: not applicable - no delivery path touched.
- Reconnect/resync proof: not applicable - no realtime surface exists to resync.

## Frontend Resilience

- Empty data proof: not applicable - no UI surface touched.
- Partial data proof: not applicable - no data-fetch surface touched.
- Forbidden secondary path behavior: not applicable - no route or guard touched.
- Missing draft/resource behavior: not applicable - no draft/resource surface touched.
- Stale route/deep-link behavior: not applicable - no route registry entry changed.

## Scope Gate

- Allowed paths: `docs/incidents/2026-09-06-cloudflared-tunnel-cutover-530-window.md` (new file only).
- Denied paths: no code, no scripts, no migrations, no CI changes in this PR (ops tooling lives in gitignored `tools/` by design).
- Migration/docs/test impact: docs-only; no test impact; no migration.
- Rollback note: plain revert deletes the document; nothing else depends on it.

## Validation

- Targeted tests or smoke run: not applicable - docs-only; production verification evidence for the underlying tunnel migration is recorded in the document itself (external 200 service-only, crash-drill ≤6 s recovery, WS 101 through tunnel, boot-checker headless samples).
- Result: markdown-only diff (+1 file); CI expected green on the untouched base.
- Not checked: none - no executable surface exists in this change.
