# Architecture: Modular Monolith (Layered + Domain Modules)

## Overview

This project is best served by a modular monolith: one deployable system with strict module boundaries. It matches the current stack and team workflow while keeping operations simpler than microservices.

Inside the monolith, each domain follows layered flow: API endpoint -> service -> repository -> database. This keeps business rules in services, keeps controllers thin, and makes data access predictable and testable.

## Decision Rationale

- **Project type:** EMR/clinic platform with payments, queueing, chat, and role-based workflows.
- **Tech stack:** FastAPI + SQLAlchemy + Alembic + PostgreSQL, React 18 + Vite, GitHub Actions CI/CD.
- **Key factor:** High domain complexity with strong consistency and audit requirements, but better served by single deployment and strict internal boundaries.

## Folder Structure

```text
backend/
  alembic/
    versions/
  app/
    api/
      v1/
        endpoints/          # HTTP controllers (validation, auth, service calls)
    services/               # Business use-cases and domain rules
    repositories/           # ORM access and query composition
    models/                 # SQLAlchemy entities
    schemas/                # Pydantic request/response contracts
    ws/                     # WebSocket managers and realtime channels
    core/                   # Config, security, logging, infra wiring
    db/                     # Session/engine setup
  tests/
    unit/
    integration/
    e2e/

frontend/
  src/
    pages/                  # Route-level composition
    components/             # UI modules by role/domain
    api/                    # HTTP clients and endpoint mappings
    hooks/                  # Reusable UI/application hooks
    contexts/               # Shared app state providers
    locales/                # i18n dictionaries
    test/                   # frontend test assets

.github/
  workflows/                # CI/CD, security, role integrity, load testing
```

## Dependency Rules

- ✅ `api/v1/endpoints` may depend on `schemas`, `services`, and auth dependencies.
- ✅ `services` may depend on `repositories`, `models` (domain objects), and shared `core` utilities.
- ✅ `repositories` may depend on `db` session and `models` only.
- ✅ `ws` may call `services` and pub/sub adapters, but not embed domain decisions.
- ✅ `frontend/pages` may compose `components`, `hooks`, and `api` clients.

- ❌ Controllers must not execute raw ORM/business workflows directly.
- ❌ Services must not bypass repository boundaries with ad-hoc session logic.
- ❌ Repositories must not import HTTP layer objects (`Request`, router, response classes).
- ❌ Frontend components must not hardcode backend URLs or role rules.

## Layer/Module Communication

- HTTP flow: request validation in endpoint -> use-case in service -> persistence via repository.
- Realtime flow: service emits queue/display events -> WebSocket manager broadcasts -> Redis pub/sub syncs instances.
- Cross-domain flow: services call explicit service APIs from neighboring modules, not internal repository internals.
- Migration flow: schema changes through Alembic revisions only; no manual drift scripts as default path.

## Deployment Topology

- Proposed target model: **single-tenant per clinic deployment**
- This is treated as the target architecture and is aligned to current repo behavior where possible, not assumed blindly as a universal runtime fact.
- Each clinic deployment should run in isolation with:
  - its own runtime
  - its own PostgreSQL database
  - its own branding/config context
  - its own first admin account
- Isolation may be delivered through VPS hosting or an on-prem clinic host.
- First-run setup belongs inside the deployed application at `/setup`.
- `/setup` must orchestrate existing SSOT entities and services rather than introducing a second source of truth.

## Packaging And Configuration Boundaries

- The application must ship as one universal package for all clinics.
- The package contains shared code and assets only:
  - backend code
  - frontend code
  - migrations
  - lifecycle helpers and runbooks
  - sample env files
  - `/setup`
- Per-clinic differences must not be baked into the package at build time.

Install-time per-clinic technical configuration belongs outside the package:
- `DATABASE_URL`
- `RESTORE_DATABASE_URL`
- `APP_HOST`
- `PUBLIC_URL`
- `BACKEND_URL`
- `SECRET_KEY`
- `AUTH_SECRET`
- database credentials
- clinic-specific paths for backups, logs, uploads, and similar runtime state

First-run `/setup` owns clinic business identity only:
- clinic name
- first branch name
- first admin full name
- first admin email
- first admin username
- first admin password
- activation or license key when required

Shared operational defaults may remain package-level when they are intentionally global:
- timezone defaults
- queue start hour
- backup schedule defaults
- branch code fallback such as `main`

The frontend should prefer runtime or current-origin API resolution over hardcoded per-clinic build-time URLs. Rebuilding the frontend per clinic is a fallback transport, not the preferred steady-state model.

## Access And Installation Roles

- **Host machine** is the clinic server or main machine where backend, PostgreSQL, storage, backup, and update tooling run.
- **Admin user** is the person who manages the system through RBAC inside the application.
- **Workstation user** is the person who signs in from another machine with their own account.

These roles must stay separate:
- machine role is selected by deployment/install mode
- user authority is selected by RBAC
- the system must not infer admin authority from the machine being used

Default workstation model:
- browser/LAN access first
- no separate backend on workstations
- no separate PostgreSQL on workstations
- any thin launcher is optional convenience only

## Release Artifact Policy

- Clinic updates must be delivered as an **approved release artifact**.
- The same approved artifact may be delivered:
  - from GitHub Releases or another approved online release source
  - as an offline package copied to the clinic host
- The clinic host is the only machine that imports or deploys approved release artifacts.
- The approved artifact must stay compatible with the existing backup, migration, smoke, and rollback path.

## Local-Only External Services Policy

- Local-only clinics must be able to install, initialize, and run core workflows without mandatory internet services.
- External integrations are disabled by default for local-only clinics:
  - AI/cloud providers
  - Telegram
  - SMS gateways
  - FCM/push providers
  - external payment webhooks
- `/setup` must support a configure-later path for these integrations.
- Unsupported-until-configured external features must not block core clinical workflows.

## Verified Current Semantics

- `clinic_settings` stores deployment-level clinic identity/config.
- `branches` model branch/facility data inside one deployment.
- `tenant_scope` is currently a feature-flagged write guard on scoped routes and must not be treated as proven multi-clinic tenancy.
- Activation is server-bound via machine fingerprint and is not tied to a receptionist/admin workstation.
- `ensure_admin.py` is now restricted from mutating an already initialized deployment unless an explicit ops override flag is provided.

## DRIFT And Migration Notes

- Current repo still contains public landing/login routes in the same frontend bundle as the clinic app.
- Current setup detection is inferred from SSOT entities (`clinic_settings`, `branches`, active admin users) rather than a dedicated setup-state table by design.
- This avoids a second source of truth, but future refactors must preserve that constraint when expanding provisioning or installer workflows.

## Domain Context Matrix

| Context | Primary ownership |
|---|---|
| `patient` | patient identity/profile and linkage data |
| `scheduling` | appointments, slot orchestration, registrar pre-queue flow |
| `queue` | live queue/tokens/display updates |
| `billing` | invoices/payments/webhooks/reconciliation |
| `emr` | visit clinical records/templates/history |
| `iam` | authentication, roles/permissions, policy checks |

## Dependency Matrix

Cross-context access is allowed only via `app.services.context_facades.*` + `app.domain.contracts.*`.

| Caller | Allowed target contexts |
|---|---|
| `patient` | `iam` |
| `scheduling` | `patient`, `queue`, `billing`, `iam` |
| `queue` | `patient`, `scheduling`, `billing`, `iam` |
| `billing` | `patient`, `scheduling`, `queue`, `iam` |
| `emr` | `patient`, `scheduling`, `billing`, `iam` |
| `iam` | none |

Direct imports between context internals are blocked by:
- `backend/tests/architecture/test_context_boundaries.py`
- CI job `architecture-boundary` in `.github/workflows/ci-cd-unified.yml`

## Phase 4 Evidence (2026-02-22)

- Boundary/contract enforcement is active in CI run: `https://github.com/drsapaev/final/actions/runs/22278770795`.
- Required gates green in the same run: `architecture-boundary`, `backend-tests`, `integration`, `security`, `load-tests-nightly`, `dast-zap-nightly`.
- Load gate artifacts confirmed: `k6-summary.json`, `load-regression-report.md`.

## Key Principles

1. Postgres + Alembic are the data contract source of truth.
2. Business rules live in services, not in controllers or repository query snippets.
3. Repositories encapsulate ORM and keep query logic centralized.
4. Every critical clinical/billing action is auditable and role-checked.
5. CI gates (lint/tests/security/load) are release controls, not optional checks.

## Code Examples

### Endpoint Delegates to Service

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.schemas.queue import QueueCreate, QueueRead
from app.services.queue_api_service import QueueApiService

router = APIRouter()


@router.post("/queue", response_model=QueueRead)
def create_queue_item(
    payload: QueueCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> QueueRead:
    service = QueueApiService(db=db)
    return service.create_item(payload=payload, actor=user)
```

### Service Uses Repository Boundary

```python
from app.repositories.queue_api_repository import QueueApiRepository


class QueueApiService:
    def __init__(self, db):
        self.repo = QueueApiRepository(db)

    def create_item(self, payload, actor):
        # Domain rule in service layer
        if not actor.can_manage_queue:
            raise PermissionError("queue access denied")

        # Persistence details hidden in repository layer
        item = self.repo.create(payload, created_by=actor.id)
        self.repo.commit()
        return item
```

## Anti-Patterns

- ❌ Endpoint reads/writes ORM models directly and mixes auth, validation, and business logic in one function.
- ❌ Service imports router objects or returns raw framework responses.
- ❌ Schema drift from direct SQL/manual table edits outside Alembic.
- ❌ Cross-module shortcuts where one domain reads another domain tables directly instead of service contracts.
