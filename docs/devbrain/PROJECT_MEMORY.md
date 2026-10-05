# Project Memory

Compact router for durable ownership decisions and confirmed failure patterns. Keep task checkpoints in local automatic memory; keep implementation truth in current source, tests, migrations, and runbooks. See [bootstrap rule preservation](BOOTSTRAP_RULE_PRESERVATION.md).

## Stable ownership

- Backend services own payment, queue, authorization, clinical, lab, notification, Telegram-security, and persistence behavior. Frontend code presents API-owned decisions unless an explicit read-model contract says otherwise.
- Database truth is SQLAlchemy model + schema contract + Alembic revision + validation/tests. Route truth starts at `frontend/src/routing/routeRegistry.ts`; role truth starts at `backend/app/models/role_permission.py`.
- Queue identity/fairness follows profile → specialist/doctor mapping → backend queue ordering → API contract → presentation. Keep payment and visit/queue statuses separate.
- Telegram token storage/security is model → migration → expiry/single-use service behavior → Bot API/UI. Bot UX does not own storage.
- Notification types and delivery semantics start at the catalog/producer and user preference policy; consumers do not invent event types.

## Recurrent failure patterns

- Keyword routing can misclassify migration/storage work as Telegram, queue, status, endpoint, or UI work. Find the canonical writer and its direct tests before editing.
- An all-ascending index cannot serve a mixed-direction `ORDER BY`; mirror the query directions or inspect the query plan. See `backend/app/api/v1/endpoints/derma.py` and migration `0076_derma_history_read_order.py`.
- Session SQLAlchemy listeners must be registered from a module loaded by every relevant entry point, not only an endpoint import. Verify startup/import paths and focused tests.
- A closed `/ws/queue` socket must leave the receive loop, cancel heartbeat, and leave its room. See `backend/tests/unit/test_queue_ws_disconnect.py`.

## Local runtime contour

- Manual local development uses PostgreSQL `clinic_dev`, an explicit PostgreSQL `DATABASE_URL`, and confirmed reset/seed flags; do not rely on SQLite fallbacks. Local 2FA bypass flags are manual smoke aids only, never production-like configuration. See [PostgreSQL dev database](../dev/POSTGRES_DEV_DATABASE.md) and [local onboarding](../runbooks/LOCAL_DEV_ONBOARDING.md).
- WSL staging is a separate Compose project/database with synthetic fixtures only. Run `Preflight` before build and use `Session` for the full long-running validation; skipped PG cases are not success, image/mount identity is not served-revision proof, and uptime reset alone does not prove OOM. See [session worktrees](../runbooks/AGENT_SESSION_WORKTREES.md) and [WSL staging session](../runbooks/WSL_STAGING_SESSION.md).

## DevBrain routing

- New agent sessions follow [automatic memory](AUTOMATIC_MEMORY.md); shared portable facts live in [`memory/curated.json`](memory/curated.json), local task state lives outside the checkout, and local evidence never overrides current source.
- Check [status](DEVBRAIN_STATUS.md), [memory routing](MEMORY_ROUTING.md), and [role map](DEV_BRAIN_ROLE_MAP.md) with filesystem evidence before graph-heavy or ownership-sensitive work.
- LlamaIndex and LightRAG are legacy dormant retrieval unless current artifacts and acceptance evidence say otherwise. Do not claim a unified brain without the recorded acceptance gate.
- July 2026 Z.ai sprint notes are historical snapshots in [`archive/2026-07-zai-cleanup-sprint.md`](archive/2026-07-zai-cleanup-sprint.md); verify any operational fact before relying on it.
