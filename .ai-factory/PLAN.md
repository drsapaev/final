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
