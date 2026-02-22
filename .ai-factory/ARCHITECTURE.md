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
