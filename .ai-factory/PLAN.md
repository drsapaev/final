# Implementation Plan: Panel QA Checklist v2 Rollout

Created: 2026-03-21

### Scope

Operationalize the new SSOT panel QA runbook so execution progress is preserved across sessions and the first Smoke/P0 run can start from a real local environment.

### Tasks

- [x] Create SSOT checklist document:
  - `docs/PANEL_QA_CHECKLIST.md`
- [x] Add docs index entry:
  - `docs/README.md`
- [x] Add execution discipline with step markers and resume rules:
  - `docs/PANEL_QA_CHECKLIST.md`
- [x] Add project rules for AI Factory skill-first execution and OpenHands-compatible progress tracking:
  - `.ai-factory/RULES.md`
- [x] Check local environment readiness for first Smoke/P0 run:
  - frontend `http://localhost:5173` -> `200`
  - backend `http://localhost:18000/api/v1/health` -> `200`
- [x] Execute first Smoke/P0 chain from:
  - `docs/PANEL_QA_CHECKLIST.md`
- [x] Record smoke evidence, failures, blockers, and resume point in:
  - `.ai-factory/logs/PANEL_QA_IMPLEMENTATION_STATUS.md`

### Bootstrap execution completed

- [x] Registrar bootstrap path:
  - `REG-01`, `REG-02`, `REG-03`
- [x] Laboratory bootstrap path:
  - `LAB-01`, `LAB-02`, `LAB-03`
- [x] Cashier bootstrap path:
  - `CASH-01`, `CASH-02`, `CASH-03`
- [x] Cashier regression follow-up:
  - `CASH-04`, `CASH-05`
- [x] Cashier destructive regression attempted:
  - `CASH-06` refund API path passed, but same-session cashier history stayed stale until full reload
- [x] Specialist routing bootstrap attempted:
  - registrar created `K01` cardiology visit
  - `/doctor-panel` did not receive it
  - `/cardiologist` did receive it and allowed queue transition to `Вызван`
- [x] Specialist profile save check attempted:
  - cardiology blood-test create returned backend `200`
  - UI persistence mismatch recorded in status log
- [x] Cardiology history and supporting-tab regression follow-up:
  - `CARD-02` blocked by missing persisted cardio artifacts after `CARD-01`, while patient-context/history routing itself opened correctly
  - `CARD-03` passed: `Services -> AI Assistant -> History -> Visit` kept the same patient context intact
- [x] Admin smoke bootstrap path:
  - `ADM-01`, `ADM-02`
- [x] Admin regression bootstrap path:
  - `ADM-03`, `ADM-04`, `ADM-05`, `ADM-06`
- [x] Laboratory reprint regression attempted:
  - backend `pdf + mark-printed` path passed for `instance #22`
  - fresh `/lab-panel` session exposed `Бланки 0`, so UI reprint remained blocked and was recorded in status log
- [x] Resume point documented:
  - next targeted regression case starts from `DERM-01`
- [x] Investigate targeted fix root causes:
  - `CARD-01` confirmed as backend stubbed `/cardio/blood-tests` plus frontend payload missing canonical patient context
  - `CASH-06` confirmed as same-session history refresh gap caused by reload logic that did not bump refresh state on page `1`
- [x] Implement `CARD-01` persistence fix:
  - add `cardio_blood_tests` model and schema
  - replace stubbed `/cardio/blood-tests` create/list with persisted API flow
  - accept cardiology-specialty roles alongside doctor/admin roles
- [x] Add migration and focused backend verification for `CARD-01`:
  - Alembic revision `0014_cardio_blood_tests`
  - integration test `backend/tests/integration/test_cardio_api.py`
  - local `pytest` green
- [x] Implement `CASH-06` same-session refresh fix:
  - cashier actions now use shared `triggerDataReload()` for refund, cancel, manual refresh, and payment success
- [x] Implement `VERIFY-CARD-02-UI` hydration fix:
  - cardiology panel now retries URL-based patient hydration after auth/storage refresh events
  - URL-selected patient is upgraded with canonical appointment and visit context once appointments load
  - blood-test state resets cleanly when patient context changes
- [x] Targeted verification after fixes:
  - backend `pytest` green
  - frontend `build` green
  - temp backend `:18001` live API verified for create/list blood tests
  - temp frontend `:4173` live browser proof passed against `http://localhost:18001`
  - deep link `/cardiologist?patientId=444&tab=appointments` restored patient context and surfaced the saved appointment row
  - `Blood Tests` and `History` displayed the persisted cardiology artifact for patient `444`
  - previous `:5175` failures were traced to temp CORS/origin mismatch rather than a remaining cardiology UI logic defect
- [x] Implement dermatologist persistence and specialist data fixes:
  - add persisted dermatology examination/procedure API flow plus Alembic revision `0015_derma_records`
  - add focused integration tests `backend/tests/integration/test_derma_api.py`
  - fix `/registrar/all-appointments` date filters so ISO `date_from/date_to` no longer trigger Postgres operator mismatch
  - add regression test `backend/tests/integration/test_registrar_all_appointments.py`
- [x] Restore global success/error feedback for specialist panels:
  - mount shared `react-toastify` container in `frontend/src/App.jsx`
  - remove registrar-local `ToastContainer` to avoid duplicate toasts after app-shell fix
- [x] Verify `DERM-01` on clean preview stack:
  - fresh backend `http://localhost:18003` confirmed CORS-safe for `http://localhost:8080`
  - preview frontend rebuilt against `http://localhost:18003`
  - live browser proof passed for `Appointments -> Skin Examination save -> History -> Skin reopen`
  - success toast, persisted diagnosis, history entry, and reopened skin block all confirmed
- [x] Verify `DERM-02` regression on saved dermatology artifact:
  - open `History` on the same clean preview stack
  - confirm saved `exam_id` remains visible in history
  - return to `Skin Examination` and confirm the same `exam_id` plus diagnosis reopen consistently
- [x] Verify `DERM-03` supporting-tab regression:
  - traverse `Photos -> Services -> AI Assistant -> Patients -> Visit`
  - confirm the same dermatology patient context is restored after the tab sequence
- [x] Implement `DOC-01` legacy general doctor queue fix:
  - move `DoctorPanel` queue source from `doctor_id` filtering over `/registrar/queues/today` to specialty-based `/doctor/general/queue/today`
  - make backend `/doctor/{specialty}/queue/today` resilient for `general` when the user has no linked `Doctor` row
  - keep queue actions on canonical queue-entry endpoints instead of legacy doctor-id queue actions
- [x] Verify `DOC-01` after fix:
  - `pytest backend/tests/integration/test_doctor_general_queue.py ...` green together with existing cardio/derma/registrar regression tests
  - frontend `npm run build` green
  - temp backend `:18004` live API proof for `doctor@example.com` returns `200` with explicit empty general queue payload instead of the previous broken/misleading path
- [x] Implement and verify `LAB-04` fresh-session forms recovery:
  - `LabPanel` now loads recent report instances for a fresh `/lab-panel?tab=reports` session instead of showing `Бланки 0`
  - `LabReportWorkbench` keeps patient-specific history when context is selected and falls back to a recent-reports browser otherwise
  - focused regression test `frontend/src/components/laboratory/__tests__/LabReportWorkbench.test.jsx` passed
  - frontend `npm run build` passed after the forms-browser change
  - temp frontend `:18080` live browser proof against backend `:18001` showed non-zero forms count and successful open of an existing report from the forms tab
- [x] Verify `DOC-02` on current-code temp stack:
  - current backend `http://127.0.0.1:18005` returned canonical `general` queue payload for `doctor@example.com`
  - seeded one `waiting` general queue entry on Postgres to unblock the smoke path
  - temp frontend `http://127.0.0.1:8080` showed the same queue row in `/doctor-panel`
  - `Вызвать следующего` moved the row from `waiting` to `called` in both UI and follow-up API payload
- [x] Implement and verify `DOC-03` diagnostics-return path on the current temp stack:
  - backend `/queue/position/notify/diagnostics-return/{entry_id}` no longer crashes on the current `Doctor` schema and now resolves specialist name from linked user data
  - `DoctorPanel` return action now uses canonical `getApiOrigin()` instead of a same-origin relative fetch
  - frontend `npm run build` stayed green after the doctor-panel patch
  - live browser proof on `http://127.0.0.1:8080` confirmed `На обследование -> Вернуть с диагностики (Push)` sends `POST http://127.0.0.1:18005/api/v1/queue/position/notify/diagnostics-return/6 -> 200`
  - current environment returns `sent=false, reason=no_user_found`, but the patient stays attached to the diagnostics row and the return path no longer breaks
- [x] Implement and verify `DOC-04` completion path on the current temp stack:
  - `/doctor/queue/{entry_id}/complete` now resolves canonical `queue_entries.id` before any legacy fallback to `Visit` or `Appointment`
  - regression test `backend/tests/integration/test_doctor_general_queue.py` now covers queue-entry ID collision against an unrelated `Visit.id`
  - targeted backend verification passed: `pytest test_doctor_general_queue.py test_queue_position_notify.py -q` -> `4 passed`
  - after restarting temp backend `:18005`, live browser proof on `http://127.0.0.1:8080` showed `POST /doctor/queue/6/complete -> 200`
  - doctor queue UI changed the same row from `diagnostics` to `served` (`Обслужены: 1`, status badge `Обслужен`)
- [x] Implement and verify `DOC-05` schedule-next flow on the current temp stack:
  - `ScheduleNextModal` now uses canonical `getApiOrigin()` for patients, services, and `/doctor/visits/schedule-next`
  - frontend `npm run build` stayed green after the modal-origin patch
  - live browser proof on `http://127.0.0.1:8080` showed `GET /patients -> 200`, `GET /services -> 200`, and `POST /doctor/visits/schedule-next -> 200`
  - doctor UI returned success feedback with confirmation token `f6584973-2ee1-4695-b329-9da69a81e0ee`
  - fresh live browser proof on `http://localhost:18080/doctor-panel` now shows the new follow-up row rendered at the top of `Записи` in the same session, so the appointments table no longer needs the network-family fallback as secondary SoT
  - evidence: `output/playwright/doc-05-refresh-final.png`, `output/playwright/doc-05-network.txt`, `output/playwright/doc-05-console.log`
- [x] Implement and verify `DOC-06` destructive doctor queue path on the current temp stack:
  - seeded isolated destructive row `entry #7` for `DOC 06 Пациент 1774163475` so the destructive proof would not mutate the already-completed `entry #6`
  - long-lived browser session expired mid-run and surfaced as a misleading `User not found`; relogin under `doctor@example.com` restored the canonical queue state on `http://127.0.0.1:8080`
  - live browser proof on `http://127.0.0.1:8080` showed the seeded diagnostics row in `На обследовании`
  - canonical destructive action completed through `POST /queue/entry/7/incomplete -> 200`
  - doctor queue UI reloaded the same row to `Не завершён`, closing the `diagnostics -> incomplete` half of the runbook destructive path
- [x] Resume point updated:
  - next targeted blocker/fix case starts from `DENT-01`
- [x] Implement and verify `DENT-01` dentist mandatory-tabs save flow on the current temp stack:
  - frontend `DentistPanelUnified` now treats backend `stomatology` rows as canonical dentistry appointments instead of filtering them out
  - `Examinations` now falls back to patient cards derived from the current dentist queue when role-scoped `GET /patients?department=Dental` stays forbidden
  - dental backend clinician endpoints now accept role `dentist`, and focused integration coverage was added in `backend/tests/integration/test_dental_api.py`
  - live browser proof on `http://127.0.0.1:8080` showed seeded patient `DENT 01 Пациент 1774146335` in `Appointments`, then in `Examinations`, and the save flow completed through `POST /api/v1/dental/examinations -> 200`
- [x] Resume point updated:
  - next targeted blocker/fix case starts from `DENT-02`
- [x] Implement and verify `DENT-02` dentist reports reopen flow on the current temp stack:
  - `DentistPanelUnified` now persists saved visit protocols into local history under `dentist_panel_documents_v1`
  - live browser proof on `http://127.0.0.1:8080` saved a dentist visit protocol for visit `746`, then surfaced it in `/dentist?tab=reports` as `Сохранённые протоколы визитов`
  - reopening the saved protocol from `Reports` preserved the procedure payload for patient `DENT 01 Пациент 1774146335` (`Лечение кариеса`, tooth `11`, `12:55-13:10`, saved description) without silent overwrite
- [x] Resume point updated:
  - next targeted blocker/fix case starts from `DENT-03`
- [x] Implement and verify `DENT-03` dentist supporting-tabs stability flow on the current temp stack:
  - live DOM-driven sidebar proof on `http://127.0.0.1:8080` traversed `Dental Chart -> Treatment Plans -> Photo Archive -> AI Assistant -> Visit Protocols`
  - `Dental Chart`, `Treatment Plans`, and `Photo Archive` each retained the same patient card for `DENT 01 Пациент 1774146335`
  - after the supporting-tabs sequence the panel returned to `/dentist?tab=visits` with the same patient context still open (`Прием пациента: DENT 01 Пациент 1774146335`)
- [x] Resume point updated:
  - dentist regression tranche is complete through `DENT-03`; next explicit step is targeted panel-runbook verification
- [x] Implement and verify `DENT-EMR-404` empty-state bootstrap cleanup on the current temp stack:
  - `frontend/src/hooks/useEMR.js` now treats missing `/v2/emr/{visitId}` as a resolved empty-state bootstrap via `validateStatus`, then initializes a clean draft instead of routing `404` through the EMR error path
  - `frontend/src/api/interceptors.js` now suppresses canceled axios requests before centralized error handling, which protects the double-mount / aborted-request path from noisy false-positive network errors
  - focused frontend verification stayed green: `npm run test:run -- src/api/__tests__/interceptors.test.js` -> `6 passed`
  - frontend `npm run build` stayed green after the EMR/bootstrap patch
  - fresh live dentist proof on `http://127.0.0.1:8080` reopened `Appointments -> Visit Protocols` for visit `746` and showed a clean empty EMR draft without a visible `EMR not found` alert/toast in the DOM
  - secondary SoT for the live proof is the network capture with a single canonical bootstrap miss `GET /api/v1/v2/emr/746 -> 404`, which is now treated as expected empty-state behavior
- [x] Resume point updated:
  - targeted dentist EMR bootstrap cleanup is verified at UI/network layer; next explicit step is `CASH-06-REVERIFY`
- [x] Re-verify `CASH-06` same-session cashier refund refresh on the current temp stack:
  - recovered live cashier credentials from the current Postgres user store (`cashier@example.com` / `<set QA_CASHIER_PASSWORD>`)
  - live browser proof on `http://127.0.0.1:8080` created a fresh cash payment for `Пациент Тест`, then opened `История платежей` in the same session
  - canonical refund flow completed through the history row and updated the same row from `Оплачено` to `Возвращено` without a full page reload
  - secondary SoT captured the same-session refresh network family in `cash-06-reverify-network.txt`
- [x] Resume point updated:
  - `CASH-06-REVERIFY` is closed; next explicit step is `ADM-05-FIX`
- [x] Implement and verify `ADM-05-FIX` on a fresh current-code stack:
  - backend patient-create paths now persist `doc_type` together with `doc_number`
  - targeted backend verification passed: `pytest backend/tests/integration/test_patient_documents_api.py -q` -> `1 passed`
  - fresh live proof on `http://127.0.0.1:4194` against backend `http://127.0.0.1:18008` created patient `id=453`
  - create response returned `doc_type='passport'` together with `doc_number='AA2553099'`
  - the same patient row stayed visible in admin patients search after creation
- [x] Resume point updated:
  - `ADM-05-FIX` is closed; next explicit step is `ADM-06-FIX`
- [x] Implement and verify `ADM-06-FIX`:
  - registrar service grouping now resolves from explicit routing fields (`queue_tag`, `department_key`, category specialty) before code-derived fallback
  - backend emits `[FIX:ADM-06]` info logs when explicit routing overrides the code/category fallback path
  - targeted regression added in `backend/tests/integration/test_registrar_services_grouping.py`
  - verification passed: `python -m pytest backend/tests/integration/test_registrar_services_grouping.py -q` -> `1 passed`
  - regression safety check also passed: `python -m pytest backend/tests/integration/test_patient_documents_api.py -q` -> `1 passed`
- [x] Resume point updated:
  - `ADM-06-FIX` code path is closed; next explicit step is `ADM-06-LIVE-VERIFY`
- [x] Execute `ADM-06-LIVE-VERIFY` on a fresh current-code stack:
  - temp backend `http://127.0.0.1:18009` and temp frontend `http://127.0.0.1:4195` started from current code
  - live admin proof created service `ADM-06 Live Lab 409003` with code `L99` through `/admin?section=services`
  - secondary SoT `GET /api/v1/registrar/services` returned the same service under `laboratory` with `procedures_count=0`
  - evidence saved in `output/playwright/adm-06-live-verify-4195.json` and `output/playwright/adm-06-live-admin-service-4195.png`
- [x] Resume point updated:
  - `ADM-06-LIVE-VERIFY` is closed; next explicit step is `PANEL-RUNBOOK-VERIFY`
- [x] Verify rollout against the plan and runbook:
  - runbook structure confirmed: core sections, appendices, and case budget `15/24/8/47` are present in `docs/PANEL_QA_CHECKLIST.md`
  - consolidated backend verification passed: `python -m pytest ...test_cardio_api.py ...test_registrar_services_grouping.py -q` -> `14 passed`
  - frontend production build passed: `npm run build`
  - focused frontend verification passed: `npm run test:run -- src/api/__tests__/interceptors.test.js src/components/laboratory/__tests__/LabReportWorkbench.test.jsx src/utils/__tests__/patientDocument.test.js src/utils/__tests__/dentistrySpecialty.test.js src/utils/__tests__/dentistryDocuments.test.js` -> `13 passed`
  - targeted eslint returned `18` warnings and `0` errors on the touched verification surface; this remains follow-up quality debt, not a rollout blocker
- [x] Resume point updated:
  - `PANEL-RUNBOOK-VERIFY` is closed; rollout plan is complete
  - next optional step is `FOLLOWUP-BACKLOG-TRIAGE`

### Execution Notes

- Do not rely on memory between steps.
- After each completed case, update the status log with:
  - current case,
  - last completed case,
  - next case,
  - blocker state,
  - evidence state.
- Existing dirty worktree includes user/playwright artifacts; do not reset or discard them.

---

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

---

## Implementation Plan: Local-First Stabilization + VPS Preparation (Phase 10)

Created: 2026-03-19
Branch: main (fast plan)

### Scope

Пока проект работает локально, использовать уже поднятый host-based staging contour как основной рабочий контур:
- backend `:18000`
- frontend `:18080`
- dedicated staging Postgres `:55432`

Цель этого этапа:
- закрыть ручную приемку ключевых ролей на локальном staging,
- закрыть оставшийся вопрос по queue-domain migration/archival,
- зафиксировать VPS rollout как обязательный следующий этап, но не выполнять его до завершения локальной приемки.

### Deliverables

- Краткий smoke-check evidence по ролям и specialist flows
- Документированное решение по legacy queue cluster
- Актуальные env/runbook/roadmap записи для будущего VPS promotion
- Практический local-first checklist: `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md`
- Четкий local → VPS gate без двусмысленностей

### Tasks

#### Phase 1: Local Acceptance

- [x] **Task 1: Пройти ручной smoke-check основных ролей**
  - Проверить: admin, registrar, cashier, lab, doctor specialist flows.
  - Зафиксировать pass/fail и блокеры.
  - Result: local staging contour booted on canonical `18000/18080`; admin, registrar, cashier, lab, and doctor panels loaded successfully after auth bootstrap from current DB users.

- [x] **Task 2: Пройти specialist EMR flows на локальном staging**
  - Проверить cardiology, dermatology, dentistry, lab.
  - Подтвердить canonical `visit_id`, specialist-specific sections, history, sign/amend flow.
  - Result: live proofs for CARD/DERM/DENT/LAB are already recorded in the status log and cover the full specialist contour.

- [x] **Task 3: Проверить соседние бизнес-флоу после cutover**
  - Prescription eligibility
  - complete-visit/status flows
  - doctor-history filtering
  - files and attachments
  - Result: prescription eligibility now uses canonical `canCreatePrescription`, cardiology history filtering now includes blood tests/ECG/attachments, and file upload/listing now accepts `visit_id` on the canonical backend surface.
  - Verification: focused backend/frontend checks passed (`python -m py_compile`, targeted ESLint, and `npm run build`); no fresh live browser smoke was completed in this pass.

#### Phase 2: Data Closure

- [x] **Task 4: Закрыть решение по queue-domain migration**
  - Либо мигрировать legacy queue cluster в текущую Postgres модель.
  - Либо заархивировать и явно зафиксировать, что это неканоничный legacy domain.
  - Result: legacy queue is already archived and documented as non-canonical in `docs/PLAN_CHECKLIST.md` and `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md`; no hidden dual source remains.

- [x] **Task 5: Проверить оставшиеся skipped/legacy-only data paths**
  - appointments with missing patient refs
  - orphan message refs
  - source-only legacy tables
  - Result: migration dry-run against `backend/clinic.db` produced the expected legacy skips (`appointments` missing patient refs: 2; `messages` missing recipient refs: 14; `queue_entries` incompatible with the current daily-queues domain; `telegram_messages` source shape mismatch). Live Postgres audit also surfaced 7 orphan `visits.doctor_id` rows and 11 orphan `visit_services.service_id` rows, which are now documented as legacy residue/follow-up cleanup candidates.

#### Phase 3: VPS Preparation Only

- [x] **Task 6: Держать VPS rollout kit актуальным**
  - Проверять `ops/vps/*` и `docs/runbooks/VPS_HOST_ROLLOUT_RUNBOOK.md` при изменениях deployment path.
  - Result: current `ops/vps/*` already matches the active deployment path (`PostgreSQL`, `systemd`, Nginx, backend `18000`), and a targeted sweep found no stale `8000` or SQLite instructions in the VPS kit / runbook surface.

- [x] **Task 7: Зафиксировать VPS как mandatory next milestone**
  - `.ai-factory/ROADMAP.md`
  - `docs/PLAN_CHECKLIST.md`
  - `.ai-factory/DESCRIPTION.md`
  - Result: VPS is now called out explicitly as the mandatory next milestone in the roadmap, plan checklist, and project description.

- [x] **Task 8: Не начинать production rollout до VPS staging**
  - Production допускается только после отдельного VPS staging contour и повторного green cutover.
  - Result: production rollout sections in `ops/vps/README.md` and `docs/runbooks/VPS_HOST_ROLLOUT_RUNBOOK.md` now explicitly warn that staging smoke, EMR cutover, and a short soak window must pass first.

### Exit Criteria

- Локальный staging полностью проходит роль-based smoke-check.
- Решение по queue-domain migration/archival задокументировано.
- VPS promotion path зафиксирован в каноничных плановых документах.
- Следующий этап после локальной приемки однозначно определен: VPS staging rollout.
