# Real Chaos Injection — Contract (issue #2774)

Status: contract approved structure, implementation pending owner GO ·
Owner: CI/reliability · Created: 2026-09-05 · Source issue: #2774

Rule of order (issue #2774, from the reliability review): **contract
first, implementation second.** This document answers every required
field for each approved scenario BEFORE any injection code is written.
The mock-based chaos workflow (`chaos.yml`, frontend `page.route`
injection) stays exactly as it is — real injection is a separate,
clearly-named workflow.

## 0. Scope and environment

**Where it runs.** Scenarios S1–S3 run inside a dedicated GitHub Actions
workflow (`nightly-chaos-real.yml`, nightly cron + workflow_dispatch) that
reuses the `load.yml` bring-up pattern verbatim: postgres:16 container →
`SELECT 1` retry gate → `alembic upgrade head` → uvicorn background with
readiness gate → `dev_seed` → minted JWT. No production host, no
production database, no production tunnel is ever touched by S1–S3.

**Where it does NOT run.** S4 (production-host drills: cloudflared kill,
host reboot) executes on the production host ONLY as a manual quarterly
ops drill with explicit owner GO at the moment of execution, evidence
appended to this runbook (§5). It is never automated against production.

** Preconditions (met).** Issue #2772 checkpoint passed (Load and DR
scheduled contracts green); nightly-health has the R1 alert pattern
(`if: failure() && github.event_name == 'schedule'`).

**Terminology.** "load" = the k6 stage profile from `load.yml`
(`k6-queue-load.js`) running against the CI stack for the duration of the
injection. "Committed write" = an HTTP 2xx response to a write request.

---

## S1 — uvicorn process kill (CI, automated)

| Field | Value |
|---|---|
| Failure injection | `kill -9 <uvicorn.pid>` (SIGKILL — no graceful shutdown) while k6 load is in its middle stage. Uptime of the outage: exactly until the workflow's restart step runs (≈5s later). |
| Expected invariant | During the outage: k6 sees connection refused/reset — fast failures, NO hangs (no request may wait >10s before erroring). Committed writes (2xx) issued BEFORE the kill are all durable. |
| Observed behavior | k6 per-iteration results (error class + latency histogram); Postgres `SELECT COUNT(*) FROM visits` before-kill vs after-recovery snapshot comparison. |
| Recovery requirement | Workflow restarts uvicorn (same bring-up command); `GET /health` → 200 within 30s; every pre-kill 2xx write still present (COUNT equality); k6 error rate after recovery returns to baseline. |
| PASS / FAIL | PASS = (a) zero k6 iterations with latency >10s during outage (failures must be fast), (b) pre-kill committed COUNT == post-recovery COUNT, (c) /health 200 ≤30s after restart, (d) post-recovery k6 error rate == baseline. Any of (a)–(d) violated → FAIL. |
| R1 alert + evidence | Scheduled-run failure opens the standard R1 ci-failure issue; workflow uploads k6 results + DB snapshots as artifacts; nightly-health gains a `chaos-real (S1 uvicorn)` row labeled real-injection with PASS/FAIL. |

## S2 — database sever for 60s (CI, automated)

| Field | Value |
|---|---|
| Failure injection | `docker stop <postgres-container>` for exactly 60s (data volume preserved — this is a sever, not data loss) while k6 load runs. |
| Expected invariant | During the outage: every request fails FAST (bounded by `DB_CONNECT_TIMEOUT_S=10` and `DB_STATEMENT_TIMEOUT_MS`), never hangs; the app process stays alive (no crash-loop); k6 errors are connection-class only, no 5xx data-corruption signatures. After reconnect: the app serves reads and accepts writes with zero restarts. |
| Observed behavior | k6 error classes + latency histogram; uvicorn stays-alive assertion (PID unchanged at t+60s); app log grep for reconnect (no fatal). |
| Recovery requirement | After `docker start`: first successful `SELECT 1` through the app's pool within 30s; k6 error rate returns to baseline within one stage; committed writes from before the sever all durable. |
| PASS / FAIL | PASS = (a) no request latency >15s during outage (bounded failures), (b) uvicorn PID unchanged, (c) pool self-recovers ≤30s after container start, (d) pre-sever committed writes durable, (e) zero duplicate/ghost rows in `visits` after recovery. Any violated → FAIL. |
| R1 alert + evidence | Same R1 pattern as S1; artifacts: k6 results, app log tail, DB snapshot; nightly-health row `chaos-real (S2 postgres-sever)`. |

## S3 — full stack restart baseline (CI, automated)

| Field | Value |
|---|---|
| Failure injection | Stop k6, kill uvicorn, `docker stop` + `docker rm` the postgres container, then bring the full stack back with the exact `load.yml` bring-up (same container name, fresh-but-volume-preserved start is NOT used — this is a cold-start baseline: fresh container, `alembic upgrade head` must be a no-op on an up-to-date DB). |
| Expected invariant | Cold start converges: migrations idempotent (head unchanged, no new revision applied), seed idempotent (no duplicate users/rows), health green, one full k6 smoke stage at baseline error rate. |
| Observed behavior | `alembic current` before/after; dev_seed output; `/health` readiness timing; k6 smoke stage results. |
| Recovery requirement | `/health` 200 ≤60s after uvicorn start; `alembic current` == head; login flow works with seeded credentials; k6 smoke error rate == baseline. |
| PASS / FAIL | PASS = (a) alembic applies zero pending revisions on the second run, (b) seed reports idempotent (no duplicates — COUNT checks on users/patients), (c) /health ≤60s, (d) k6 smoke at baseline. Any violated → FAIL (this is the drift-detector scenario: it exists to catch "works only on the first run" classes). |
| R1 alert + evidence | Same R1 pattern; artifacts: alembic output, seed output, k6 results; nightly-health row `chaos-real (S3 cold-start)`. |

## S4 — production-host drills (manual, quarterly, owner-gated)

| Field | Value |
|---|---|
| Failure injection | (a) `net stop cloudflared` (or service equivalent) for 15 minutes; (b) planned host reboot via the documented reboot procedure (CLINIC_HOST_AVAILABILITY_RUNBOOK). Both ONLY with the owner's explicit GO immediately before execution. |
| Expected invariant | (a) direct-IP/LAN access to the API keeps working (tunnel is the edge, not the origin); finalclinic.fyi shows fast 5xx/connection errors (no hang). (b) After reboot: the autostart chain brings up cloudflared + uvicorn + nightly tasks with no manual steps. |
| Observed behavior | (a) LAN `GET /health` during outage; public URL error class from an external probe. (b) Boot-to-health timing; autostart chain log; first nightly backup after reboot lands in R2. |
| Recovery requirement | (a) `net start cloudflared` → public URL 200 within 60s. (b) Boot → health 200 within the documented availability budget (autostart chain); scheduled backup fires at the next 02:00 window. |
| PASS / FAIL | (a) PASS = LAN health 200 throughout, public 200 ≤60s after start. (b) PASS = health 200 within budget, zero manual interventions, next scheduled backup verified in R2. Any violated → FAIL + incident doc. |
| R1 alert + evidence | Evidence appended to this runbook §5 (date, timings, artifacts) + incident doc if FAIL; nightly-health row `chaos-real (S4 prod-drill)` on the next scheduled run via manual annotation. |

---

## §2. Implementation notes for the follow-up PR (NOT in this PR)

- New workflow `nightly-chaos-real.yml`: nightly cron (offset from
  nightly-health to avoid overlap), `workflow_dispatch` for manual runs;
  reuses the load.yml job skeleton; uploads all artifacts.
- k6 `handleSummary` writes per-iteration error classes so the PASS
  assertions (fast-fail check) are machine-evaluated, not eyeballed.
- DB snapshot steps use a dedicated read-only connection and COUNT checks
  only — no content dumps into artifacts (PHI policy applies to the seed
  database too).
- nightly-health consumes a workflow-run query and emits the
  `chaos-real (S# …)` rows with real-injection labels.
- R1: job failure → ci-failure issue (identical to nightly-health's
  `if: failure() && github.event_name == 'schedule'` block).

## §3. Non-goals

- The mock-based `chaos.yml` is untouched and stays labeled mock-based.
- No injection against the production host from CI. Ever.
- No data-loss scenarios: S2 preserves the volume; nothing in this
  contract deletes committed rows.

## §4. Rollback

The workflow file is self-contained; revert deletes the schedule and
returns nightly-health to its current row set. No runtime component of
the product is affected.

## §5. Execution evidence log

| Date | Scenario | Result | Evidence / notes |
|---|---|---|---|
| — | — | — | no executions yet (contract PR) |
