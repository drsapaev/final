# PLAN CHECKLIST — PROD READINESS

## P0 Security (Phase 0, Blocker)
- [x] Remove `.secret_key` from repo/history; secrets only via env/secret store.
- [x] Prod CORS: `CORS_ALLOW_ALL` forbidden; `BACKEND_CORS_ORIGINS` strict whitelist; prod fails to start if allow_all.
- [x] DEV auth fallback disabled for `ENV=prod`; fails closed if enabled.
- [x] EMR audit trail: immutable read/write log with `user_id`, timestamp, action.

## P1 Release Gating (Phase 0)
- [x] CI stages: build → lint/tests → security scan → deploy; prod deploy requires manual approval (GitHub environment `production` with required reviewers).
- [x] GO only if any failed stage blocks deployment.

## STOP/GO Phase 0 → 1
- [x] STOP if any P0 item open.
- [x] STOP if prod deploy lacks manual approval gate (enforced via environment `production`).

## P1 Architecture/Data (Phase 1)
- [x] Postgres default for prod/docker-compose.
- [x] Alembic baseline passes on Postgres (`0001_baseline`).
- [x] Service/Repository layer: controllers only validate/auth/call service; domain rules live in `services/*`.
- [x] Redis pub/sub backs WebSocket queues; supports multi-instance scale-out.

## P1 Product Core (Phase 1)
- [x] Online queue with QR: models, API, UI; 07:00 rule covered by tests.
- [x] Payments (Click/Payme/Kaspi): init, webhook, attach visit; E2E happy path green.
- [x] WebSocket display board: events `queue.created|called|updated` drive live UI.

## STOP/GO Phase 1 → 2
- [x] GO only if: Postgres + migrations green; ≥80% E6 tests green; WebSocket works on 2 instances with Redis.

## P2 Reliability/Observability (Phase 2)
- [x] DB backups + proven restore; DR runbook.
- [x] Structured logs, metrics, traces; alerts on SLA (latency, error rate, queue lag).

## P2 QA Depth (Phase 2)
- [x] E2E: 07:00 queue, payment, print, RBAC/EMR flows in CI.
- [x] Load tests (k6/Locust) with target RPS; regressions tracked.
- [x] Security testing: DAST (ZAP nightly) + SAST/deps policy in CI.

## STOP/GO Phase 2 → 3
- [x] GO only if: DR test passes; alerts wired; E2E critical flows green; load metrics within targets.

## P2 Architecture Finish
- [ ] Controllers free of business logic; services unit-tested; repositories encapsulate ORM.

## P3 UX & Docs (Phase 3)
- [ ] A11y: WCAG contrast, focus, ARIA validated on key flows.
- [ ] UX polish: save states, clear errors/recovery, meaningful empty states.
- [ ] OpenAPI complete; contract tests; onboarding/runbooks current.
