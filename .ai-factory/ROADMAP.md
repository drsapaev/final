# Project Roadmap

> Build a production-grade clinic platform where Postgres + Alembic are the single source of truth, clinical workflows are role-safe, and quality gates block unsafe releases.

## Milestones

- [x] **Security Baseline (P0)** — secrets from env only, strict CORS, fail-closed auth in prod, immutable EMR audit trail.
- [x] **Release Gating Foundation** — CI stages ordered as build -> lint/tests -> security -> deploy, with mandatory manual approval for production.
- [x] **Data Platform Reset to Postgres SSOT** — local/dev workflow aligned to PostgreSQL, Alembic baseline and upgrade flow validated.
- [x] **Service/Repository Boundary** — thin controllers and service-first business logic with repositories encapsulating ORM access.
- [x] **Real-Time Queue Core** — QR queue and live display board events delivered through WebSocket + Redis pub/sub.
- [x] **Payments Core** — Click/Payme/Kaspi flow with webhook handling and visit-payment linkage covered by tests.
- [x] **Reliability and Observability** — backup/restore runbook, structured logs, metrics/traces, and SLA-oriented alerting.
- [x] **QA Depth in CI** — critical E2E flows, load tests, and security checks wired into CI pipelines.
- [x] **UX and A11y Baseline** — key flows cleaned for accessibility, OpenAPI contract checks, and onboarding/runbook docs updated.
- [x] **Domain Modules (Phase 4)** — formalize bounded contexts (Patient, Scheduling, Queue, Billing, EMR, IAM) with explicit cross-module contracts. (Completed; CI evidence: run `22278770795`)
- [x] **Clinical Security Maturity** — add PHI data lifecycle controls (retention, encryption posture, access reporting, break-glass policy validation). (Baseline service + tests implemented on 2026-02-22)
- [x] **SLO and Capacity Engineering** — automate regression budgets for latency/error rate and scale test profiles per critical endpoint group. (k6 profile matrix + aggregated regression gate implemented on 2026-02-22)
- [ ] **Interoperability and Multi-Clinic Scale** — standardize adapter contracts for external systems and prepare tenant/branch isolation strategy.

## Completed

| Milestone | Date |
|-----------|------|
| Security Baseline (P0) | 2026-02-22 |
| Release Gating Foundation | 2026-02-22 |
| Data Platform Reset to Postgres SSOT | 2026-02-22 |
| Service/Repository Boundary | 2026-02-22 |
| Real-Time Queue Core | 2026-02-22 |
| Payments Core | 2026-02-22 |
| Reliability and Observability | 2026-02-22 |
| QA Depth in CI | 2026-02-22 |
| UX and A11y Baseline | 2026-02-22 |
| Domain Modules (Phase 4) | 2026-02-22 |
| Clinical Security Maturity | 2026-02-22 |
| SLO and Capacity Engineering | 2026-02-22 |
