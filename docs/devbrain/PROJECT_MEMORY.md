# Project Memory

Canonical compact memory for DevBrain routing and guardrails. Keep this file short and operational. Do not turn `AGENTS.md` into a full history dump; update this file when project-wide ownership decisions change.

## Core SSOT Decisions

- Backend business rules are the source of truth for payment, queue, RBAC, EMR, lab, Telegram security, and persistence behavior.
- Frontend is presentation and interaction orchestration unless a route-specific adapter is explicitly documented as a read model.
- Route registry ownership starts from `frontend/src/routing/routeRegistry.js`.
- Database shape ownership starts from SQLAlchemy models plus Alembic revisions, not endpoint text or UI assumptions.
- CI and PR gates are repository safety infrastructure and must not be bypassed to save time.
- AI Factory, dossiers, evidence logs, and skills are advisory memory layers; executable source and tests still win when they conflict.

## Known Ownership Chains

- DB persistence: `SQLAlchemy model -> schema/table contract -> Alembic revision -> DB validation -> tests`.
- Registrar payment/status: `backend service/persistence -> API DTO/read model -> frontend adapter/table -> print/payment UI`.
- Queue identity/fairness: `profile/specialist/doctor mapping -> queue service ordering -> API contract -> frontend presentation`.
- Notifications: `event catalog -> producer service -> user preference/anti-noise policy -> delivery adapter -> frontend consumer`.
- Telegram token/security: `token model/storage -> Alembic revision -> service expiry/single-use checks -> webhook/command UX`.
- Routing: `routeRegistry.js -> route guards/layouts -> role panels -> links/navigation`.

## Known Failure Patterns

- Keyword routing can misclassify storage or migration tasks as Telegram, queue, status, endpoint, or UI tasks.
- Multi-hop ownership is often missed when a change spans UI, endpoint, service, persistence, and tests.
- Manual reconstruction repeats when dossiers/evidence are not consulted before graph-heavy work.
- Existing migrations can be tempting to edit, but already-applied revisions must remain immutable.
- Frontend presentation code must not invent backend-owned values such as payment status, queue ordering, role policy, or appointment time.
- Broad audit findings should be converted into small PR slices before implementation.

## Strict Operating Rules

- Use direct execution only for narrow known-root-cause tasks with no risky domain or ownership ambiguity.
- Use dossier or handoff for graph-heavy, mixed-contract, or ownership-sensitive work.
- Use gate or gate-known-root-cause for DB, RBAC, payment, queue, Telegram security/storage, EMR/lab, CI/CD, deploy, and frontend/backend contract work.
- If the gate misroutes, retry once with `--known-root-cause`; if it still misses the confirmed file, use narrow override and report it.
- Do not silently expand scope. Stop when the required file set exceeds the declared first-touch boundary.
- Every PR needs evidence: local validation, `git diff --check`, PR scope/impact notes, and green GitHub checks when opened.

## Migration / Alembic Ownership Rules

- SQLAlchemy model without a matching table/migration is migration ownership, not endpoint, webhook, queue, status, or UI ownership.
- If a model exists and the table is missing, first-touch must include a new Alembic revision under `backend/alembic/versions/`.
- Never edit an already-applied migration as a substitute for creating a new revision.
- Treat the existing model and previous revision as read-only references unless the user explicitly changes the model contract.
- Validate Alembic chain state with heads/history review and disposable/test database upgrade when available.
- Stop on multi-head ambiguity, existing target table, destructive migration requirements, or model/table mismatch.

## Queue Identity Rules

- Queue ordering and fairness belong to backend queue services and persistence.
- Do not infer queue identity from labels, display names, frontend filters, or QR text alone.
- Preserve the distinction between specialist, profile, doctor, and ticket identity.
- Frontend queue changes should remain presentation-only unless an API contract change is explicitly planned.

## Payment / Status Separation

- Payment state and visit/queue status are separate domains.
- Frontend must not normalize or invent backend payment status values.
- Registrar/cashier UI should display backend-owned payment state and route actions through canonical payment endpoints/services.
- Print/receipt behavior must not become the source of truth for payment completion.

## Notification Catalog Ownership

- Notification event types belong to the catalog/producer contract first.
- Producer services must emit catalog-backed events rather than ad hoc strings.
- User preferences and anti-noise behavior must be checked before adding notifications.
- Frontend notification UI consumes catalog-backed events and must not invent delivery semantics.

## Telegram Token / Security Ownership

- Bot UX/webhook design is separate from token storage/security ownership.
- Staff link tokens, webhook secrets, bot tokens, and one-time tokens are security-sensitive.
- Do not hardcode secrets, expose tokens in logs, weaken expiry, or weaken single-use guarantees.
- Telegram tasks mentioning Alembic, SQLAlchemy, table missing, Postgres SSOT, storage migration, create table, link token storage, or revision use DB ownership first.
- Use `telegram-bot-builder` only after confirming the task is Bot API/UX/webhook work rather than storage/migration/security root cause.

## Route Registry SSOT

- Start route work from `frontend/src/routing/routeRegistry.js`.
- Preserve canonical routes, aliases, guards, and role ownership.
- Do not create duplicate navigation truth in page components, tests, or docs.
- Stop when a route change implies RBAC, backend contract, or legacy redirect behavior not covered by the current scope.
