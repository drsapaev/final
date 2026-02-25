# Implementation Plan: Domain Modules (Phase 4)

Branch: wip/precommit-commit  
Created: 2026-02-22

## Settings
- Testing: yes
- Logging: verbose
- Docs: yes

## Scope

Formalize bounded contexts for `Patient`, `Scheduling`, `Queue`, `Billing`, `EMR`, `IAM` with explicit contracts and CI enforcement of allowed dependencies.

## Commit Plan

- **Commit 1** (after tasks 1-3): `docs(architecture): add bounded-context map and contract skeleton`
- **Commit 2** (after tasks 4-6): `test(architecture): enforce context boundaries in CI`
- **Commit 3** (after tasks 7-9): `refactor(domain): migrate pilot flows to context contracts`

## Tasks

### Phase 1: Context Definition
- [x] **Task 1: Create domain context map**
  - Add `docs/architecture/DOMAIN_CONTEXT_MAP.md` with:
  - Context responsibilities, owned models/services/repositories, allowed inbound/outbound calls.
  - Explicit "forbidden direct dependency" table.
  - Logging requirement: add one `INFO` startup log in each touched service showing context tag (e.g., `context=queue`).

- [x] **Task 2: Add backend context registry**
  - Create `backend/app/domain/context_registry.py` with canonical context names and module ownership map.
  - Add helper validators for boundary test usage.
  - Logging requirement: `DEBUG` logs in validators for detected module/context mapping.

- [x] **Task 3: Add contract package skeleton**
  - Create `backend/app/domain/contracts/` with contract interfaces (Protocol/dataclass/Pydantic DTO) for:
  - `patient_contracts.py`, `scheduling_contracts.py`, `queue_contracts.py`, `billing_contracts.py`, `emr_contracts.py`, `iam_contracts.py`.
  - Logging requirement: each orchestrator-level method using contracts emits entry/exit `DEBUG` logs with request ids.

### Phase 2: Boundary Enforcement
- [x] **Task 4: Add architecture boundary tests**
  - Add `backend/tests/architecture/test_context_boundaries.py`.
  - Implement import graph checks for `backend/app/services` and `backend/app/repositories`.
  - Fail test if module imports a disallowed context directly instead of contract/facade.
  - Logging requirement: test output must list violating module -> forbidden import.
  - Depends on: Task 1, Task 2, Task 3.

- [x] **Task 5: Wire boundary checks into CI**
  - Update `.github/workflows/ci-cd-unified.yml` to ensure boundary tests always run on `workflow_dispatch` and `push` to `main`.
  - Keep checks blocking (no `continue-on-error`).
  - Logging requirement: CI step prints concise summary (`contexts checked`, `violations`, `duration`).
  - Depends on: Task 4.

- [x] **Task 6: Add service facades per context**
  - Create facade entry points in `backend/app/services/context_facades/`:
  - `patient_facade.py`, `scheduling_facade.py`, `queue_facade.py`, `billing_facade.py`, `emr_facade.py`, `iam_facade.py`.
  - Facades expose stable methods used by other contexts.
  - Logging requirement: facade methods log `INFO` business event and `ERROR` failures with correlation id.
  - Depends on: Task 3.

### Phase 3: Pilot Migration + Validation
- [x] **Task 7: Migrate high-impact cross-context call sites**
  - Refactor pilot flows to use facades/contracts:
  - `queue <-> billing`, `registrar/scheduling <-> patient`, `emr <-> iam`.
  - Target files in `backend/app/services/*_api_service.py` that currently use direct imports/calls across domains.
  - Logging requirement: keep old/new path parity logs during migration window.
  - Depends on: Task 6.

- [x] **Task 8: Add regression and contract tests**
  - Add/extend tests:
  - `backend/tests/unit/test_context_contracts.py`
  - `backend/tests/unit/test_service_repository_boundary.py` (extend for context rules)
  - Integration tests for migrated pilot flows.
  - Logging requirement: assertion messages must clearly identify broken contract and caller context.
  - Depends on: Task 7.

- [x] **Task 9: Update architecture docs and close milestone**
  - Update:
  - `.ai-factory/ARCHITECTURE.md` (context table + dependency matrix),
  - `.ai-factory/ROADMAP.md` (mark milestone complete when tests/CI are green),
  - `docs/PLAN_CHECKLIST.md` only if checklist criteria are explicitly satisfied.
  - Logging requirement: record completion evidence links (test command outputs / CI run ID) in doc notes.
  - Depends on: Task 5, Task 8.
  - Evidence:
  - CI run: `https://github.com/drsapaev/final/actions/runs/22278770795` (all required jobs green).
  - Artifacts confirmed: `load-test-report` includes `k6-summary.json` and `load-regression-report.md`.

## Execution Notes

- Migration strategy: pilot-first, then fan-out to remaining modules in subsequent plan.
- Risk control: keep boundary test strict, but rollout can use explicit temporary allowlist with expiry date.
- Done criteria:
  - Boundary tests pass locally and in CI.
  - Pilot flows pass unit + integration tests.
  - Contracts become mandatory path for cross-context calls.

---

## Implementation Plan: Clinical Security Maturity (Phase 5)

Created: 2026-02-22

### Scope

Add baseline PHI lifecycle controls required by roadmap milestone:
- retention visibility for PHI-bearing tables,
- encryption posture validation with runtime smoke-check,
- access reporting from EMR/user audit logs,
- break-glass policy validation.

### Tasks

- [x] Add `ClinicalSecurityMaturityService` with:
  - retention inventory (`build_retention_inventory`),
  - encryption posture checks (`evaluate_encryption_posture`),
  - PHI access report (`build_phi_access_report`),
  - break-glass policy validation (`validate_break_glass_policy`).
- [x] Extend settings (`app/core/config.py`) with:
  - `PHI_RETENTION_DAYS`,
  - `BREAK_GLASS_*` controls.
- [x] Add unit tests:
  - `backend/tests/unit/test_clinical_security_maturity_service.py`.
- [x] Validate locally:
  - `ruff check backend/app/services/clinical_security_maturity_service.py backend/tests/unit/test_clinical_security_maturity_service.py`
  - `pytest backend/tests/unit/test_clinical_security_maturity_service.py -q`

### Evidence

- Service: `backend/app/services/clinical_security_maturity_service.py`
- Tests: `backend/tests/unit/test_clinical_security_maturity_service.py` (`5 passed`)

---

## Implementation Plan: SLO & Capacity Engineering (Phase 6)

Created: 2026-02-22

### Scope

Scale load regression control from one baseline run to profile-based capacity budgets across critical endpoint groups.

### Tasks

- [x] Extend k6 scenario (`ops/load/clinic_core.js`) to accept:
  - profile tag (`K6_PROFILE`),
  - dynamic endpoint set (`K6_ENDPOINTS_JSON`).
- [x] Add profile budget config:
  - `ops/load/endpoint_profiles.json` with per-profile `targets`, `baseline`, `regression`.
- [x] Extend regression checker:
  - `ops/scripts/check_load_regression.py` now supports `--profile` and profile-aware configs.
- [x] Add load profile orchestrator:
  - `ops/scripts/run_load_profiles.py` runs all profiles, writes aggregated and per-profile artifacts.
- [x] Update CI load job (`.github/workflows/ci-cd-unified.yml`) to run full profile matrix and enforce aggregated gate.
- [x] Add unit tests:
  - `backend/tests/unit/test_load_regression_profiles.py` (`4 passed`).
- [x] Update runbook:
  - `docs/runbooks/LOAD_TESTING_RUNBOOK.md`.

### Local Validation

- `ruff check ops/scripts/check_load_regression.py ops/scripts/run_load_profiles.py backend/tests/unit/test_load_regression_profiles.py`
- `pytest backend/tests/unit/test_load_regression_profiles.py -q`

---

## Implementation Plan: Interoperability + Multi-Clinic Scale (Phase 7)

Created: 2026-02-23

### Scope

Start the final roadmap milestone with contract-first interoperability and branch-scope isolation primitives.

### Tasks

- [x] Add interoperability contracts:
  - `backend/app/domain/contracts/interoperability_contracts.py`
  - export from `backend/app/domain/contracts/__init__.py`.
- [x] Add gateway service over external integration registry:
  - `backend/app/services/interoperability_gateway_service.py`.
- [x] Refactor integration endpoints to consume gateway contract instead of concrete provider classes:
  - `backend/app/services/integrations_api_service.py`.
- [x] Add tenant-scope isolation utilities:
  - `backend/app/core/tenant_scope.py`.
- [x] Add unit tests:
  - `backend/tests/unit/test_interoperability_gateway_service.py`
  - `backend/tests/unit/test_tenant_scope.py`.
- [x] Add architecture baseline doc:
  - `docs/architecture/INTEROPERABILITY_MULTI_CLINIC.md`.
- [x] Enforce tenant scope on selected write flows (`billing`, `queue`, `emr`) under feature flag.
  - `backend/app/middleware/tenant_scope_middleware.py`
  - `backend/app/core/config.py` (`TENANT_SCOPE_ENFORCE_WRITES`, `TENANT_SCOPE_WRITE_PREFIXES`)
  - protected write prefixes include branch-owned `/api/v1/clinic/equipment`.
  - `backend/app/main.py` middleware registration.
- [x] Add CI architecture guard against direct API imports of concrete integration provider classes:
  - `backend/tests/architecture/test_interoperability_import_boundaries.py`
  - `.github/workflows/ci-cd-unified.yml` (`architecture-boundary` runs both architecture tests).
- [x] Add repository-level branch scope helpers for branch-owned models:
  - `backend/app/repositories/branch_scope_repository.py`
  - scoped CRUD methods in `backend/app/crud/clinic_management.py` for `Equipment`.
  - equipment service/api wiring:
  - `backend/app/services/clinic_management_service.py`
  - `backend/app/services/clinic_management_api_service.py`.
  - tests:
  - `backend/tests/unit/test_branch_scope_repository.py`
  - `backend/tests/unit/test_clinic_management_equipment_scoped_crud.py`.
- [x] Expand integration contract tests with provider stubs and failure-mode matrix:
  - extended gateway matrix in:
  - `backend/tests/unit/test_interoperability_gateway_service.py`
  - added API error-mapping matrix:
  - `backend/tests/unit/test_integrations_api_error_mapping.py`.

### Local Validation

- `ruff check backend/app/domain/contracts/interoperability_contracts.py backend/app/domain/contracts/__init__.py backend/app/services/interoperability_gateway_service.py backend/app/services/integrations_api_service.py backend/app/core/tenant_scope.py backend/tests/unit/test_interoperability_gateway_service.py backend/tests/unit/test_tenant_scope.py`
- `pytest backend/tests/unit/test_interoperability_gateway_service.py backend/tests/unit/test_tenant_scope.py backend/tests/unit/test_endpoint_shims.py backend/tests/architecture/test_interoperability_import_boundaries.py -q`
- `pytest backend/tests/architecture/test_context_boundaries.py backend/tests/architecture/test_interoperability_import_boundaries.py -q`
- `pytest backend/tests/test_tenant_scope_middleware.py backend/tests/unit/test_tenant_scope.py backend/tests/test_settings.py -q`
- `pytest backend/tests/unit/test_branch_scope_repository.py backend/tests/unit/test_clinic_management_equipment_scoped_crud.py backend/tests/test_tenant_scope_middleware.py backend/tests/test_settings.py -q`
- `pytest backend/tests/unit/test_interoperability_gateway_service.py backend/tests/unit/test_integrations_api_error_mapping.py backend/tests/unit/test_endpoint_shims.py -q`

### CI Evidence

- Unified workflow (green): `https://github.com/drsapaev/final/actions/runs/22298766412`

---

## Implementation Plan: Post-Merge Stabilization (Phase 8)

Created: 2026-02-23

### Scope

Close post-merge reliability gaps discovered on `main` and lock the fixes with deterministic CI coverage.

### Tasks

- [x] Add targeted regression test for `get_settings()`:
  - cover missing `SECRET_KEY` + production validation path,
  - assert no `UnboundLocalError` for `env`,
  - file: `backend/tests/test_settings.py`.
- [x] Add deterministic fallback checker script for role integrity workflow:
  - file: `backend/scripts/ci/validate_role_integrity.py`,
  - checks required RBAC routes + `validate_critical_user_roles()` with clear exit codes.
- [x] Refactor `.github/workflows/role-system-check.yml`:
  - call new fallback script instead of inline heredoc Python,
  - keep blocking behavior and clearer failure logs.
- [x] Add CI evidence note updates:
  - append latest green run IDs to `docs/PLAN_CHECKLIST.md`,
  - ensure references stay current after each hotfix merge.

### Validation Plan

- `python -m pytest backend/tests/test_settings.py backend/tests/integration/test_rbac_matrix.py -q`
- `python backend/scripts/ci/validate_role_integrity.py` (local dry-run)
- Trigger `Role System Integrity Check` and verify green on `main`.

### CI Evidence

- `https://github.com/drsapaev/final/actions/runs/22321183829` (Unified CI on `main`, green)
- `https://github.com/drsapaev/final/actions/runs/22321183830` (Role System Integrity Check on `main`, green)
- `https://github.com/drsapaev/final/actions/runs/22321183816` (Security scan on `main`, green)
- `load-test-report` artifact verified in run `22321183829` with `k6-summary.json` and `load-regression-report.md`.

---

## Implementation Plan: Frontend ↔ Backend Feature Parity + UX Fit (Phase 9)

Created: 2026-02-24
Branch: main (fast plan)

### Settings

- Testing: yes
- Logging: verbose
- Docs: yes

### Scope

Проверить, все ли реализованные backend-функции покрыты во frontend, и оценить:
- функциональную корректность соответствия контрактам API,
- удобство и предсказуемость UX (loading/error/empty/access states) на ключевых ролях.

### Deliverables

- Машиночитаемая матрица соответствия: `docs/reports/frontend_backend_parity.json`
- Человекочитаемый отчёт: `docs/reports/FRONTEND_BACKEND_PARITY_REPORT.md`
- Scorecard корректности/удобства: `docs/reports/FRONTEND_UX_CORRECTNESS_SCORECARD.md`
- CI-проверка, блокирующая drift между backend API и frontend клиентом.

### Commit Plan

- **Commit 1** (после задач 1-3): `feat(parity): add backend-frontend API inventory and baseline matrix`
- **Commit 2** (после задач 4-6): `test(parity): validate critical role flows and UX correctness scorecard`
- **Commit 3** (после задач 7-9): `ci(parity): enforce contract drift checks and publish parity report`

### Tasks

#### Phase 1: Контрактная инвентаризация

- [x] **Task 1: Зафиксировать backend API контракт (SSOT)**
  - Обновить snapshot OpenAPI из текущего backend:
  - `backend/generate_openapi.py`
  - `backend/openapi.json`
  - Логирование: `INFO` начало/конец генерации, `DEBUG` количество путей/операций.

- [x] **Task 2: Построить инвентаризацию frontend API-вызовов**
  - Создать анализатор frontend вызовов API:
  - `ops/scripts/extract_frontend_api_usage.py`
  - Источники: `frontend/src/api/*.js`, `frontend/src/services/*.js`, ключевые `frontend/src/hooks/**/*.js`
  - Артефакт: `docs/reports/frontend_api_usage_inventory.json`
  - Логирование: `INFO` по модулям, `DEBUG` по endpoint/method/source-file.

- [x] **Task 3: Сформировать baseline parity matrix**
  - Сопоставить `backend/openapi.json` и frontend inventory:
  - `ops/scripts/build_frontend_backend_parity.py`
  - Выгрузить:
  - `docs/reports/frontend_backend_parity.json`
  - `docs/reports/FRONTEND_BACKEND_PARITY_REPORT.md`
  - Категории: `implemented`, `partial`, `missing_in_frontend`, `frontend_orphan`.
  - Логирование: `INFO` coverage %, `WARNING` по критичным пропускам (`auth/queue/billing/emr`).
  - Depends on: Task 1, Task 2.

#### Phase 2: Проверка корректности и удобства

- [x] **Task 4: Проверить критические role-flows на контрактную корректность**
  - Проверить сценарии: registrar queue, doctor EMR read/write, cashier payment status/receipt, admin settings.
  - Точки интеграции:
  - `frontend/src/pages/**/*`
  - `frontend/src/components/**/*`
  - `backend/tests/integration/*` (переиспользование проверок контрактов)
  - Артефакт: секция `critical_flows` в `docs/reports/frontend_backend_parity.json`.
  - Логирование: `INFO` по каждому сценарию (pass/fail), `ERROR` с endpoint+payload mismatch.
  - Depends on: Task 3.

- [x] **Task 5: Проверить RBAC-соответствие UI vs backend**
  - Найти frontend role-guards и сравнить с backend permission surface:
  - `frontend/src/App.jsx`, `frontend/src/components/**/*Guard*`, `frontend/src/contexts/*`
  - `backend/app/core/permissions.py`, `backend/app/core/role_validation.py`
  - Артефакт: секция `rbac_alignment` в `docs/reports/FRONTEND_BACKEND_PARITY_REPORT.md`.
  - Логирование: `INFO` по ролям, `WARNING` при “UI allows / backend denies” и наоборот.
  - Depends on: Task 3.

- [x] **Task 6: Оценить UX корректность и удобство по matched-фичам**
  - Оценить для ключевых страниц наличие и качество:
  - loading, empty, error recovery, form validation feedback, keyboard/a11y.
  - Источники:
  - `frontend/src/pages/**/*`
  - `frontend/src/components/**/*`
  - Итог: `docs/reports/FRONTEND_UX_CORRECTNESS_SCORECARD.md` (оценка 0-5: Correctness, Usability).
  - Логирование: `INFO` итоговый score по модулю, `DEBUG` конкретные UX gaps и приоритет.
  - Depends on: Task 4, Task 5.

#### Phase 3: Закрытие разрывов и CI gate

- [x] **Task 7: Исправить high-impact parity gaps во frontend**
  - Поправить endpoint/method/path/query-body расхождения в:
  - `frontend/src/api/*.js`
  - `frontend/src/services/*.js`
  - `frontend/src/pages/**/*` (если есть неправильные вызовы/обработка)
  - Логирование: `INFO` migrated endpoint map, `WARNING` временные backward shims (с TODO-датой удаления).
  - Depends on: Task 3, Task 4.

- [x] **Task 8: Добавить regression-тесты parity и UX-критериев**
  - Добавить/обновить тесты:
  - `frontend/src/test/**/*` (unit/integration по API клиентам и состояниям UI)
  - `backend/tests/test_openapi_contract.py` (если нужен экспорт метаданных для parity)
  - Логирование: тестовые сообщения должны явно показывать `missing/partial/orphan`.
  - Depends on: Task 7.

- [x] **Task 9: Включить CI gate и обновить checklist evidence**
  - Включить генерацию parity-отчётов и fail condition в:
  - `.github/workflows/ci-cd-unified.yml`
  - Артефакты CI: parity JSON/MD + UX scorecard MD.
  - Обновить:
  - `docs/PLAN_CHECKLIST.md`
  - `.ai-factory/ROADMAP.md` (если критерии milestone закрыты)
  - Логирование: `INFO` summary в CI (`coverage`, `missing_critical`, `ux_score`).
  - Depends on: Task 8.

### Exit Criteria

- Critical role-flows (`registrar_queue`, `doctor_emr_rw`, `cashier_payment`, `admin_settings`) pass in parity matrix.
- UI RBAC не конфликтует с backend RBAC (`rbac_alignment=pass`).
- Scorecard показывает приемлемый уровень:
  - Correctness >= 4/5
  - Usability >= 4/5
- CI включает blocking parity gate и публикует артефакты parity/UX.

### Validation Evidence

- `python ops/scripts/extract_frontend_api_usage.py --log-level INFO`
- `python ops/scripts/build_frontend_backend_parity.py --log-level INFO`
- `python ops/scripts/evaluate_frontend_ux_scorecard.py --log-level INFO`
- `python ops/scripts/check_frontend_backend_parity.py --log-level INFO` (pass)
- `python -m pytest backend/tests/unit/test_frontend_backend_parity.py backend/tests/unit/test_frontend_backend_parity_gate.py backend/tests/test_openapi_contract.py -q` (15 passed)
- `npm --prefix frontend run test:run -- src/api/__tests__/adminSettings.test.js src/api/__tests__/queue.test.js src/test/parity/rbacRouteParity.test.js src/pages/__tests__/QueueJoin.accessibility.test.jsx` (16 passed)
