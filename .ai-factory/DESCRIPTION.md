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

## Deployment Model

- Target architecture: **isolated deployment per clinic**
- Each clinic deployment owns:
  - its own backend/frontend runtime
  - its own PostgreSQL database
  - its own host/domain or clinic-host endpoint
  - its own clinic branding and admin context
- Deployment may run as:
  - VPS-hosted rollout
  - on-prem / clinic-host install
- Branches remain inside a single clinic deployment and are not treated as independent deployments.
- First-run business initialization happens inside the deployed app via `/setup`.
- `/setup` is an orchestration layer over existing SSOT entities:
  - `clinic_settings`
  - `branches`
  - `users` + related profile/preferences/notification rows
  - activation records

## Package And Setup Model

- The system should be distributed as one universal application package, not as a custom build per clinic.
- The universal package includes:
  - backend code
  - frontend code
  - Alembic migrations
  - backup/update/restore helpers
  - sample env files
  - `/setup`

Per-clinic technical configuration is install-time state and must stay outside the package:
- database connection strings
- host or domain values
- public and backend URLs
- secrets
- PostgreSQL credentials
- backup, log, and upload paths

Per-clinic business identity belongs to `/setup`:
- clinic name
- first branch
- first admin identity and credentials
- optional activation or license key

Global defaults may stay shared until there is a clear product requirement to make them clinic-specific:
- default timezone
- queue window defaults
- backup schedule defaults
- fallback branch code

## Access Model

- **Host machine**
  - the clinic server or main machine where backend, PostgreSQL, storage, backup, and update tooling run
- **Admin user**
  - the person who manages the system through application roles
- **Workstation user**
  - the person who signs in from another machine with their own account

Default workstation access is:
- browser/LAN access
- no separate backend install
- no separate PostgreSQL instance

Any thin launcher is optional convenience only and not a required second install mode.

## Release Artifact Model

- Clinic updates are delivered as an **approved release artifact**.
- The same artifact format must support:
  - online delivery from GitHub Releases or another approved release source
  - offline delivery as a copied package
- Release approval source of truth is the approved release ref plus the manifest embedded in the artifact.

## Local-Only Policy

- Local-only clinics must be able to complete install, setup, login, and core workflows without mandatory internet services.
- External integrations remain optional and are configured later when needed.
- The following remain unavailable until configured explicitly:
  - Telegram flows
  - SMS delivery
  - push via FCM
  - cloud AI features
  - internet-facing payment callbacks or webhooks

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
- Current primary runtime is the local host-based staging contour:
  - backend on `:18000`
  - frontend on `:5173`
  - dedicated staging Postgres cluster on `:55432`
- EMR v2 hard-cutover has already been rehearsed successfully on the local staging contour.
- Current local-first execution checklist is maintained in `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md`.
- VPS rollout is one supported isolated-deployment path after local acceptance and is documented in `ops/vps/README.md` and `docs/runbooks/VPS_HOST_ROLLOUT_RUNBOOK.md`.
- The same deployment contract is intended to support clinic-host / on-prem installs with the same post-deploy `/setup` flow.
