# Project: Clinic Management System

## Overview

Full-stack EMR and clinic operations platform for multi-role medical teams (admin, registrar, doctor, cashier, lab).  
System covers patient lifecycle from registration and queue to visit documentation, billing, and analytics.

## Core Features

- Patient registration, search, and visit history
- Appointment scheduling and online QR queue
- Real-time display board and queue updates (WebSocket)
- EMR workflows with role-aware access and audit logging
- Payments (Click, Payme, Kaspi) with webhook processing
- Admin modules for departments, pricing, settings, and reporting
- i18n interface (RU/UZ/EN) with accessibility-focused UI improvements

## Tech Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy, Pydantic v2
- **Database:** PostgreSQL (primary), Alembic migrations
- **Realtime/Infra:** Redis pub/sub for multi-instance WebSocket broadcast
- **Frontend:** React 18, Vite, React Router, Axios
- **Testing:** Pytest, Vitest, Playwright, k6 (CI load tests)
- **CI/CD:** GitHub Actions workflows for lint/test/security/deploy gates

## Architecture Notes

- Chosen pattern: **Modular Monolith (Layered + Domain Modules)**
- Request flow: `endpoint -> service -> repository -> DB`
- Controllers stay thin (validation/auth/orchestration only)
- Business rules and use-cases live in `backend/app/services`
- ORM access is encapsulated in `backend/app/repositories`
- Detailed rules: see `.ai-factory/ARCHITECTURE.md`

## Data & Migration Policy

- **Single source of truth:** PostgreSQL + Alembic
- Schema changes are applied only through Alembic revisions
- SQLite (`clinic.db`) is not a target for production truth
- Baseline and head migration state must be CI-verifiable

## Non-Functional Requirements

- **Security:** strict RBAC, immutable EMR audit trail, fail-closed prod auth, secrets only via env/secret store
- **Quality gates:** deploy blocked unless lint/tests/security stages pass
- **Reliability:** backup/restore runbook and disaster-recovery checks
- **Observability:** structured logs, metrics/traces, SLA alerts
- **Performance targets:** p95 latency < 500ms, error rate < 1%
- **UX/A11y:** no silent disabling of a11y checks on critical flows

## Current Program Context

- Strategic milestones and phase gates tracked in `docs/PLAN_CHECKLIST.md`
- High-level delivery roadmap tracked in `.ai-factory/ROADMAP.md`
