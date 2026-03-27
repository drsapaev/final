# Panel QA Checklist v2 Implementation Status

Updated: 2026-03-27

## Run Metadata

- Run mode: `Implementation -> Smoke/P0 bootstrap (cycle 3)`
- Environment: local
- Operator: Codex
- Branch: `main`
- Active runbook: `docs/PANEL_QA_CHECKLIST.md`

## Progress

- `[x]` Runbook created and linked in docs index
- `[x]` Execution discipline and progress markers added to runbook
- `[x]` AI Factory rules added for skill-first and OpenHands-compatible tracking
- `[x]` Local frontend started on `http://localhost:5173`
- `[x]` Local backend started on `http://localhost:18000`
- `[x]` REG-01 - registrar login successful, `/registrar-panel` opened, base navigation rendered
- `[x]` REG-02 - new registrar appointment created for lab service; live row rendered without manual refresh
- `[x]` REG-03 - registrar handoff confirmed in lab queue for visit `728`
- `[x]` REG-01-CYCLE-2 - fresh registrar login `registrar@example.com / registrar123` opened canonical `/registrar-panel`; queue empty state rendered with `Создать первую запись` CTA and dynamic registrar data loaded
- `[x]` REG-02-CYCLE-2 - fresh registrar wizard flow created a new lab appointment for `QA Smoke BCDEFG`; backend returned `invoice_id=319`, the live registrar row for visit `748` rendered without manual refresh, and the queue count advanced to `1`
- `[x]` REG-03-CYCLE-2 - fresh lab login `lab@example.com / lab123` opened canonical `/lab-panel`; queue entry `visit 748` rendered with canonical patient/visit context, services `Общий анализ крови`, and `Ожидает` status
- `[x]` LAB-02-CYCLE-2 - fresh lab workbench opened report `#23` for visit `748`, then `Сохранить черновик` transitioned the instance from `Черновик` to `Заполняется` without a page refresh
- `[x]` LAB-03-CYCLE-2 - report `#23` for visit `748` moved through `READY -> FINALIZED -> PRINTED`; backend PDF endpoint responded `200` and the browser captured the PDF download
- `[x]` LAB-04-CYCLE-2 - forms browser on `/lab-panel` loaded the recent reports list with `Бланки23`, then opened existing finalized report `#23` from the list without going back through patient history
- `[x]` LAB-01 - lab queue shows canonical patient and visit context for created registrar visit
- `[x]` LAB-02 - auto-created `ОАК` report saved from `Черновик` to `Заполняется`
- `[x]` LAB-03 - report moved through `READY -> FINALIZED -> PRINTED`; backend PDF endpoint responded `200`
- `[x]` CASH-01 - cashier pending list shows the same patient and pending amount `15 000`
- `[x]` CASH-01-CYCLE-3 - fresh cashier auth state loaded `/cashier-panel`; stats, pending payments, and payment history returned `200`, and the pending list rendered `QA Smoke BCDEFG` with `15 000 сум`
- `[x]` CASH-02-CYCLE-3 - fresh cashier online smoke on `💳 Онлайн` auto-confirmed payment `196` through the correct cashier confirm endpoint; pending list dropped to `0`, and downstream badge refresh was verified
- `[x]` CASH-02 - cash payment processed successfully; pending list dropped to `0`
- `[x]` CASH-03 - downstream registrar row updated to paid state (`✅`, cash badge) after cashier action
- `[x]` CASH-04 - receipt download now returns PDF on paid history rows; `/cashier/payments/188/receipt` responded `200`, browser smoke on `Шамсиддинова Лола` saved `cash-04-ui-receipt-188.pdf`
- `[x]` CASH-05 - payment history row for `Тестовый Пациент Регистратура` stayed consistent for date, amount, method, and paid status
- `[x]` CASH-06 - live reverify passed on the current cashier stack: a fresh paid history row for `Пациент Тест` changed from `Оплачено` to `Возвращено` in the same session immediately after refund, without a full reload
- `[x]` Specialist bootstrap visit created from registrar for `Консультация кардиолога` (`K01`)
- `[x]` DOC-01 - legacy `/doctor-panel` queue flow moved to canonical specialty-based `general` source; temp live API proof for `doctor@example.com` now returns controlled `200` empty payload instead of the previous broken doctor-id path
- `[x]` DOC-02 - current-code temp stack (`:18005` -> `:8080`) loaded a seeded `general` waiting entry in `/doctor-panel`; `Вызвать следующего` moved the same row from `waiting` to `called` in UI and follow-up API state
- `[x]` DOC-03 - current-code temp stack (`:18005` -> `:8080`) now completes the diagnostics return-notify path without frontend/backend errors; `На обследование` keeps the row in `diagnostics`, and `Вернуть с диагностики (Push)` sends canonical `POST /queue/position/notify/diagnostics-return/6 -> 200` with environment-specific `sent=false/no_user_found`
- `[x]` DOC-04 - queue completion path now prefers canonical `queue_entries.id`; after temp-backend restart on `:18005`, live browser proof on `:8080` showed `POST /doctor/queue/6/complete -> 200`, `Обслужены: 1`, and the same row moved to `Обслужен`
- `[x]` DOC-05 - schedule-next modal now loads patients/services from backend `:18005` and submits through canonical `/doctor/visits/schedule-next`; live browser proof returned `200` and success feedback with confirmation token `f6584973-2ee1-4695-b329-9da69a81e0ee`
- `[x]` DOC-06 - destructive doctor queue path passed on the current temp stack (`:18005` -> `:8080`): isolated diagnostics row `entry #7` moved from `На обследовании` to `Не завершён` after canonical `POST /queue/entry/7/incomplete -> 200`
- `[x]` Cardiology routing sanity - same visit appears in `/cardiologist` and moves to `Вызван`
- `[!]` CARD-01 - blood-test save returned backend `POST 200`, but `Blood Tests` UI still showed `Нет данных анализов` after reopen
- `[-]` CARD-02 - history route opened with the correct selected patient context, but there was no ECG/blood artifact to reopen because `/cardio/ecg` and `/cardio/blood-tests` for patient `444` remained empty after `CARD-01`
- `[x]` CARD-03 - `Services -> AI Assistant -> History -> Visit` tab sequence preserved patient context and returned cleanly to the same cardiology visit
- `[x]` ADM-01 - `/admin` dashboard and core navigation rendered without access errors
- `[x]` ADM-02 - `Users` section search and role filter returned the expected `lab@example.com` result
- `[x]` ADM-03 - test lab user created in admin UI and successfully routed to `/lab-panel`
- `[x]` ADM-04 - doctor record created in admin UI and appeared in downstream `registrar/doctors` payload
- `[x]` ADM-05 - patient created in admin UI; downstream patient visible in admin and registrar patients API as `id=448`
- `[x]` ADM-06 - service created in admin UI; downstream service visible in admin `/services` and registrar `/registrar/services` payload as `id=129`
  - `[x]` ADM-05-FIX - fresh admin patient-create proof passed on `:4194 -> :18008`; created patient `id=453` persisted `doc_type=passport` together with `doc_number=AA2553099`, and the same row stayed visible in admin patients search
  - `[x]` ADM-05-EMAIL - patient email now persists through Patient model, CRUDBase, and both patient-create service paths; migration `0016_patient_email` applied and live service smoke confirmed `email` roundtrip
  - `[x]` ADM-06-FIX - registrar service grouping now prefers explicit routing fields (`queue_tag`, `department_key`, category specialty) over code fallback; targeted regression `test_registrar_services_grouping.py` passed and no longer routes a lab-tagged service into `procedures`
- `[x]` ADM-06-LIVE-VERIFY - fresh stack `:4195 -> :18009` created admin service `ADM-06 Live Lab 409003` (`id=130`, code `L99`); secondary SoT `GET /registrar/services` returned the same row under `laboratory` with `procedures_count=0`
- `[x]` PANEL-RUNBOOK-VERIFY - runbook structure, appendices, and case budget confirmed; consolidated backend regressions passed (`14 passed`), frontend build passed, focused vitest suite passed (`13 passed`)
- `[x]` FOLLOWUP-BACKLOG-TRIAGE - residual findings classified into `P1` and `P2`; environment-only noise kept out of backlog unless reproduced on a clean stack
- `[x]` LAB-04 - fresh `/lab-panel?tab=reports` session now loads recent report instances; forms counter is non-zero again and existing reports can be opened from the forms browser
- `[x]` Smoke evidence bundle recorded in `output/playwright`
- `[x]` Smoke findings summarized for resume and bug capture
- `[x]` REG-01-CYCLE-2 - fresh registrar login `registrar@example.com / registrar123` opened canonical `/registrar-panel`; queue empty state rendered with `Создать первую запись` CTA and dynamic registrar data loaded
- `[x]` CARD-01 fix implemented in code: persisted `cardio_blood_tests` API path replaces stubbed blood-test create/list flow
- `[x]` CARD-01 backend verification passed: `pytest tests/integration/test_cardio_api.py -q` -> `2 passed`
- `[x]` CARD-01 migration applied locally: Alembic upgraded Postgres from `0013_lab_bind_actual_codes` to `0014_cardio_blood_tests`
- `[x]` CARD-01 live API verification passed on temp backend `http://localhost:18001`: create returned `201`, list returned the new blood-test row for patient `444`
- `[x]` CASH-06 fix implemented in code: cashier refund/cancel/payment success now force same-session reload through shared refresh trigger
- `[x]` Frontend verification baseline passed after fixes: `npm run build` completed successfully
- `[x]` VERIFY-CARD-02-UI fix implemented in code: cardiology panel now retries URL hydration after auth/storage refresh and upgrades URL-selected patient context from loaded appointments
- `[x]` VERIFY-CARD-02-UI live browser verification passed on allowed temp origin `http://localhost:4173` against backend `http://localhost:18001`: `Appointments`, `Blood Tests`, and `History` all surfaced the saved cardiology artifact for patient `444`
- `[~]` Temp verify note: earlier `http://localhost:5175` browser failures were traced to CORS/origin mismatch in the temporary stack, not to a remaining cardiology panel logic defect
- `[x]` Specialist shared backend fix implemented: `/registrar/all-appointments` now parses ISO `date_from/date_to` correctly and returns `200` instead of the previous Postgres type-mismatch `500`
- `[x]` App-shell feedback fix implemented: global `react-toastify` container mounted in `App.jsx`; registrar-local container removed to prevent duplicate toasts
- `[x]` DERM-01 - fresh dermatology proof passed on `http://localhost:8080` -> `http://localhost:18003`: appointments row opened the same patient visit, `Skin Examination` saved with success toast, `History` displayed the saved diagnosis, and `Skin Examination` reopened the same persisted artifact
- `[x]` DERM-02 - existing dermatology artifact reopened consistently: `History` showed `exam #4`, and returning to `Skin Examination` reopened the same `exam #4` with the same diagnosis
- `[x]` DERM-03 - supporting tabs `Photos -> Services -> AI Assistant -> Patients -> Visit` preserved the same dermatology patient context and restored the same visit cleanly
- `[x]` DOC-01 - backend `/doctor/{specialty}/queue/today` now supports `general` without a linked `Doctor` row by falling back to current-user identity plus queue-tag filtering
- `[x]` DOC-01 - `DoctorPanel` queue hook now reads the canonical specialty queue endpoint and uses queue-entry actions instead of legacy doctor-id queue actions
- `[x]` DOC-01 - focused integration coverage added for `general` doctor queue with and without configured queue rows
- `[x]` DENT-01 - dentist appointments now accept canonical backend specialty `stomatology`, so the seeded dental visit became visible in `/dentist` `Appointments`
- `[x]` DENT-01 - `Examinations` no longer blocks on role-scoped `GET /patients?department=Dental`; the panel derives patient cards from the dentist queue and opened a live examination form for `DENT 01 Пациент 1774146335`
- `[x]` DENT-01 - backend dental clinician endpoints now allow role `dentist`; focused integration coverage added in `backend/tests/integration/test_dental_api.py`, and live browser proof completed with `POST /api/v1/dental/examinations -> 200`
- `[~]` DENT-01 - dedicated `GET /patients?department=Dental` still returns `403` for dentist on the current stack, but it is no longer a blocker for the mandatory save flow because the panel now uses queue-derived patients as fallback
- `[x]` DENT-02 - backend EMR v2 save now uses a proper `{ data: ... }` request body, so visit `746` persists through `/api/v1/v2/emr/746 -> 200` and `GET /api/v1/v2/emr/746 -> 200`
- `[x]` DENT-02 - live browser proof on `http://127.0.0.1:4174` reopened the backend-saved protocol from `Reports`; the modal showed `Визит #746`, `Лечение кариеса`, and `Просмотр данных` with `Редактировать` available and `Сохранить` hidden
- `[x]` DENT-LIST-500 - dentistry discovery endpoints `/api/v1/specialized/dentistry/patients` and `/api/v1/specialized/dentistry/visits` now return `200` after RBAC role-normalization fix; the shared `require_roles` helper now accepts legacy list-form inputs and the specialized panel routes use canonical varargs
- `[x]` DENT-03 - DOM-driven sidebar sequence passed for `Dental Chart -> Treatment Plans -> Photo Archive -> AI Assistant -> Visit Protocols`; no broken navigation observed
- `[x]` DENT-03 - supporting tabs returned cleanly to `/dentist?tab=visits` with the same patient context still open for `DENT 01 Пациент 1774146335`
- `[x]` DENT-EMR-404 - dentist `Visit Protocols` now opens a clean empty EMR draft for visit `746` without a visible `EMR not found` alert/toast in the DOM; the backend still returns a single bootstrap `404`, but the frontend treats it as expected empty-state behavior
- `[x]` DENT-EMR-404 - `useEMR` now resolves missing `/v2/emr/{visitId}` through `validateStatus`, while the API interceptor suppresses canceled axios requests before centralized error handling
- `[~]` DENT-EMR-404 - Playwright console export in the long-lived browser context still contains stale historical API error lines from earlier runs, so the final live proof for this case used screenshot/DOM plus current network capture as the primary sources of truth

## Current Tracking

- Current case: `CASH-03`
- Last completed case: `CASH-02-CYCLE-3`
- Next case: `CASH-04`
  - Open blockers:
      - none; dynamic pricing and discount benefits smokes completed and smoke records were cleaned up from Postgres after live proof
  - Evidence status: new runbook cycle advanced through `CASH-02` on a fresh auth state; previous cycle artifacts remain in `output/playwright`, and the next smoke should continue with the payment path at `CASH-03`
- CI workflows/docs sweep verified: `.github/workflows/ci-cd-unified.yml`, `load-testing.yml`, and `monitoring.yml` now use backend `18000` plus Postgres service containers, while `README-CI-CD.md` and `CI-CD-README.md` now show Postgres-first examples instead of legacy database setup
- Additional CI artifacts sweep verified: `backend/CICD_TEST_REPORT.md` now points at backend `18000`, and `SETUP-CI-CD.md` now uses Postgres-first environment and launch examples

## Environment Checks

- Frontend: `200` on `/`
- Backend: `200` on `/api/v1/health`
- Note: working tree already contains unrelated `.playwright-cli` artifacts; left untouched

## Observed Findings

- `[!]` REG-02 - patient full name rejects digits with inline validation; this is expected validation behavior, but it means generated test data must stay letter-only
- `[x]` REG-02 - phone input now canonicalizes local 9-digit values to `+998XXXXXXXXX` in AppointmentWizardV2 before uniqueness checks and submit-time patient create/update; frontend unit tests and build passed
- `[x]` CASH-02 - smoke passed through `💵 Касса` and `💳 Онлайн`; pending list dropped to `0`, backend payment tests passed, and downstream badge refresh was verified
- `[x]` CASH-02-CYCLE-3 - local smoke auto-confirm now uses the cashier confirm endpoint, normalizes backend `paid` to UI `completed`, and settles payment `196` so the pending list drops to `0`
- `[x]` CASH-01-CYCLE-3 - fresh cashier auth state loaded `/cashier-panel`; stats, pending payments, and payment history returned `200`, and the pending list rendered `QA Smoke BCDEFG` with `15 000 сум`
- `[x]` CASH-04 - receipt path now downloads `receipt_<id>.pdf` for paid cashier history rows; browser proof on payment `188` saved `cash-04-ui-history-188.png` and `cash-04-ui-receipt-188.pdf`
- `[x]` CASH-06 - code path updated so refund/cancel/payment-success now increment shared refresh state instead of relying on `setCurrentPage(1)` when already on page `1`
- `[x]` CASH-06 - live reverify now passes on the current cashier stack: after creating a fresh paid row for `Пациент Тест`, refund updated the same history row to `Возвращено` immediately in-session, and the refund button became disabled without a reload
- `[x]` DOC-01 - the original failing expectation was a mixed concern: `K01` is a cardiology queue item, while legacy `/doctor-panel` was still wired to doctor-id filtering; the panel now uses the canonical `general` specialty queue path and returns a stable empty-state payload for unconfigured general doctors
- `[x]` DOC-02 - live browser proof now passes on the current-code temp stack: a seeded general queue row appears in `/doctor-panel`, `Вызвать следующего` changes it to `called`, and `/doctor/general/queue/today` reports `waiting=0`, `called=1`
- `[x]` DOC-03 - fixed in code and live-proof: `DoctorPanel` now uses canonical API origin for `Вернуть с диагностики (Push)`, backend no longer crashes on specialist name resolution, and the browser hits `http://127.0.0.1:18005/api/v1/queue/position/notify/diagnostics-return/6 -> 200`
- `[~]` DOC-03 - current environment has no downstream recipient user/device for the return notification, so the endpoint responds `sent=false` with `reason=no_user_found`; the diagnostics row stays intact and the patient is not lost from the queue
- `[x]` DOC-04 - fixed in code and live-proof: `/doctor/queue/{entry_id}/complete` now prioritizes `queue_entries.id` over colliding `Visit/Appointment` ids, so the canonical queue row completes successfully instead of falling into an unrelated visit and failing on zero-payment billing
- `[~]` DOC-04 - during temp backend PID swap the frontend logged transient `ERR_CONNECTION_REFUSED` on queue refresh and notification WebSocket reconnect; once the new backend `5608` was live, the same completion flow passed without code changes on the frontend
- `[x]` DOC-05 - fixed in code and live-proof: `ScheduleNextModal` now uses canonical API origin for patients/services/schedule-next, and the live browser run returned `POST /doctor/visits/schedule-next -> 200` with a real confirmation token
- `[~]` DOC-05 - the `Записи` table in this doctor panel does not visibly refresh from the just-created follow-up record in the same session, so this case used the network-family fallback for secondary SoT as allowed by the runbook appendix
- `[x]` DOC-06 - destructive `diagnostics -> incomplete` path passed in live browser proof: isolated row `entry #7` returned `POST /queue/entry/7/incomplete -> 200`, then the doctor queue reloaded the same patient to status `Не завершён`
- `[~]` DOC-06 - the long-lived doctor session expired mid-run and surfaced in UI as `User not found`; after relogin the same queue endpoint returned `200`, so this was treated as environment/session noise rather than a queue-domain regression
- `[!]` CARD-01 - `POST /api/v1/cardio/blood-tests` returns `200`, but the specialized UI still renders `Нет данных анализов` after reopen
- `[x]` CARD-01 - fixed in code and temp backend verification: `POST /cardio/blood-tests` now returns `201` with persisted payload, and follow-up `GET /cardio/blood-tests?patient_id=444` returns the saved record on `:18001`
- `[!]` CARD-01 - `/api/v1/registrar/all-appointments?...` returned `500` repeatedly while using the cardiologist panel
- `[x]` CARD-02 - temp browser proof now passes on allowed origin `http://localhost:4173`: URL-selected patient context hydrates into `Appointments`, and persisted `Blood Tests` plus `History` reopen correctly against backend `:18001`
- `[~]` CARD-02 - earlier `:5175` failure was a verification-environment issue: temp frontend origin was not in backend CORS allowlist, so browser errors there are not treated as an open cardiology logic blocker
- `[x]` CARD-03 - supporting cardiology tabs (`Services`, `AI Assistant`, `History`) did not drop patient context; returning to `Visit` kept the same patient and visit open
- `[x]` CARD-01 - shared dependency behind cardiology/dermatology panels fixed: `/registrar/all-appointments` date-filter endpoint now parses ISO dates and regression test coverage was added
- `[x]` DERM-01 - dermatologist success/error feedback now renders through the shared app-shell `ToastContainer` instead of failing silently outside the registrar page
- `[x]` DERM-01 - clean-stack browser proof passed on `:8080` -> `:18003`; saved skin examination appears in both `History` and reopened `Skin Examination`
- `[x]` DERM-02 - `History` and reopened `Skin Examination` stayed consistent for saved dermatology `exam_id=4`; no duplicate reopen mismatch observed in the dedicated regression pass
- `[x]` DERM-03 - `Photos`, `Services`, `AI Assistant`, and `Patients` did not drop patient context; returning to `Visit` restored the same dermatologist patient card
- `[x]` DENT-02 - backend EMR v2 save/reopen now works on the live stack; `POST /api/v1/v2/emr/746` returns `200`, `GET /api/v1/v2/emr/746` returns the persisted protocol, and `Reports` reopens the same protocol in read-only view
- `[x]` DENT-EMR-404 - fixed at the UI/network layer: a new dentist visit still produces backend `GET /api/v1/v2/emr/{visit_id} -> 404`, but the frontend now treats it as expected empty-state bootstrap and no longer shows a visible `EMR not found` alert in the verified dentist flow
- `[~]` DENT-EMR-404 - Playwright console export remains noisy in this long-lived browser context, so current verification for this case is anchored on the fresh network capture and the no-alert DOM/screenshot proof rather than on aggregated console history
- `[x]` ADM-03 - admin user create/update now accepts reserved test domains like `.test.local` in non-production and still rejects malformed emails; create flow verified by schema/integration coverage
- `[x]` ADM-05 - fixed in code and live-proof: admin patient create now persists `doc_type='passport'` together with `doc_number`; fresh stack proof on `:4194 -> :18008` returned patient `id=453` and kept the created row visible in admin patients UI
- `[x]` ADM-05-EMAIL - patient email entered in admin UI now round-trips as persisted `email` after the Patient model, CRUDBase, and service create-path fixes
- `[x]` ADM-06 - fixed in code, targeted regression, and fresh live proof: `registrar/services` now resolves group from explicit routing fields (`queue_tag`, `department_key`, category specialty) before code/category fallback, and live service `id=130` landed in `laboratory` with `procedures_count=0`
- `[x]` ADM-06 - admin service catalog now rejects mismatched SSOT code prefixes at create/update time, uppercases `category_code`, and shows canonical code in the catalog so service metadata stays aligned with selected routing
- `[x]` GROUP-PERMISSIONS-FIX - group permissions API now uses DB joins instead of missing relationship collections; live browser smoke on `/admin/users?section=group-permissions` passed after backend restart, with users list, `Группы`, and `Кэш` tabs all rendering
- `[x]` LAB-04 - fixed in code and live-proof: the forms tab now falls back to recent report instances on a fresh session, shows `Бланки 22`, surfaces printed `instance #22`, and opens existing reports from the forms browser without requiring patient history context
- `[x]` PANEL-RUNBOOK-VERIFY - targeted eslint on the touched frontend verification surface now returns `0` warnings and `0` errors after the focused prop-types/hooks cleanup; quality sweep is complete
- `[x]` STARTUP-18000 - backend launch scripts now default to port `18000` across `run_server.py`, `start_server.py`, `run_server_auto.py`, the verbose launcher, and the Windows wrappers so the frontend proxy can start without manual port overrides
- `[x]` DOCS-PORT-PG-CLEANUP - README and onboarding/runbooks now reference `python run_server.py` / backend `18000` and remove old legacy startup instructions from the Postgres-first docs

- `[x]` `SETTINGS-THEME-SMOKE` - user preferences theme toggle now bootstraps missing profile/preferences/notification rows and persists across reload; live PUT on user `#45` returned `200` and the panel was restored back to `Авто`

## Follow-up Backlog Triage

- `[x]` `P1` `CASH-02` - `💳 Онлайн` cashier path (`CashierPanel` -> `PaymentWidget` -> `/payments/init` or `/payments/test-init` -> redirect/status refresh -> downstream badge refresh`) closed by live smoke and backend payment tests
- `[x]` `CASH-02-CYCLE-3` - local smoke auto-confirm now uses the cashier confirm endpoint, normalizes backend `paid` to UI `completed`, and settles payment `196` so the pending list drops to `0`
- `[x]` `P2` `REG-02` - phone placeholder/validation mismatch fixed by canonicalizing wizard input through `phoneUtils` and submit-time normalization
- `[x]` `P2` `CASH-04` - receipt formatting now downloads `receipt_<id>.pdf`; browser proof on payment `188` confirmed the PDF path and saved `cash-04-ui-receipt-188.pdf`
- `[x]` `P2` `DENT-02` - reopen persistence now uses backend EMR v2 as the primary source of truth; localStorage remains only a bootstrap cache
- `[x]` `P2` `DENT-LIST-500` - dentistry discovery endpoints now return `200`; fixed by hardening the shared RBAC helper to flatten legacy list-form role inputs and by canonicalizing specialized-panel route dependencies to varargs
- `[x]` `P2` `ADM-03` - special-use domain rejection for `.test.local` resolved by a custom admin-user email validator that preserves syntax checks but allows reserved test domains outside production
  - `[x]` `P2` `ADM-05-EMAIL` - patient email now persists by the current patient model, CRUDBase, and both patient-create service paths
- `[x]` `P2` `ADM-06` - service catalog code-prefix inconsistency resolved by prefix guardrails in the service create/update path and canonical category code normalization
- `[x]` `P2` `ADM-06-BROWSER-SMOKE` - live browser smoke on `:4194 -> :18008` confirmed the service catalog guardrail: `Код P77 не подходит для группы "Лаборатория"` blocked submit without a `POST`, while valid `Прочие услуги` + `O77` created `QA Mismatch Smoke` and updated the table immediately
- `[x]` `P2` `PANEL-RUNBOOK-VERIFY` - eslint warnings on the touched frontend surface closed by focused prop-types/hooks cleanup and a zero-warning eslint run
- `[x]` `P2` `FINANCE-CRUD-SMOKE` - browser CRUD is green in a single admin session on the current stack; backend `/admin/finance/transactions` roundtrips returned `200` for create/update/delete and the row persisted across reload until explicit delete
- `[x]` `P2` `QUEUE-SETTINGS-NAN` - Queue Settings now defaults missing specialty start/max values to `1`, preventing `NaN` ranges while preserving save and QR test paths
- `[x]` `CI-WORKFLOWS-PG-18000-CLEANUP` - GitHub Actions workflows and CI docs now use Postgres service containers, backend `18000`, and no standalone legacy port or database instructions remain in the CI surface
- `Env-only / excluded until reproduced on a clean stack` - `DOC-03`, `DOC-04`, `DOC-06`, `CARD-02`, `DENT-EMR-404`

## Queue Profiles Smoke

- `[x]` `QUEUE-PROFILES-CRUD-SMOKE` - admin `Services -> Вкладки регистратуры` loaded the canonical queue-profile list on `:4194 -> :18008`; created temp profile `qa_queue_smoke`, updated its title to `QA Queue Smoke v2`, then deleted it and confirmed the table returned to `10` rows with no leftover temp key
- `[x]` `QUEUE-PROFILES-SMOKE-SHOT` - post-cleanup screenshot captured at `output/playwright/queue-profiles-smoke-clean.png`

## Queue Settings Smoke

- `[x]` `QUEUE-SETTINGS-SMOKE` - admin `section=queue-settings` loaded on `:4194`; `Кардиология` QR test generated successfully, `Сохранить` returned `Настройки очередей обновлены`, and the rendered ranges no longer showed `NaN`
- `[x]` `QUEUE-SETTINGS-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/queue-settings-smoke.png`

## Queue Limits Smoke

- `[x]` `QUEUE-LIMITS-SMOKE` - admin `section=queue-limits` now loads via canonical `/api/v1/admin/queue-limits` and `/api/v1/admin/queue-status`; the backend fallback `doctor.user.full_name -> doctor.user.username -> Врач #id` prevents `doctor_name` validation crashes, and the status table renders with live rows
- `[x]` `QUEUE-LIMITS-FIX` - backend regression added for the queue-status doctor-name fallback so the `QueueStatusResponse` schema cannot fail on `None`
- `[x]` `QUEUE-LIMITS-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/queue-limits-smoke-fixed.png`

## Queue Cabinet Management Smoke

- `[x]` `QUEUE-CABINET-MANAGEMENT-SMOKE` - admin `Queue Cabinet Management` loaded on `:5173 -> :18022` with a штатный `admin/admin` login token; date filter `2026-03-22` returned `2` live rows, `Синхронизировать из врачей` kept the row count stable, temp edit saved cabinet values `QA-CAB-18022 / 9 / QA-CAB-18022`, and clearing the fields restored the row back to `Не указан / — / —`
- `[x]` `QUEUE-CABINET-MANAGEMENT-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/queue-cabinet-management-smoke-18022.png`
- `[x]` `QUEUE-CABINET-MANAGEMENT-SMOKE-JSON` - evidence JSON captured at `output/playwright/queue-cabinet-management-smoke-18022.json`

## Clinic Management Smoke

- `[x]` `CLINIC-MANAGEMENT-AUTH` - clinic management now uses token-based Admin guard via `require_roles("Admin")`; backend regression `test_clinic_management_admin_access.py` passed
- `[x]` `CLINIC-MANAGEMENT-SMOKE` - browser smoke on `:5173 -> :18008` loaded `Управление клиникой`, the overview cards rendered, and `GET /clinic/stats` plus `GET /clinic/health` returned `200`
- `[x]` `CLINIC-MANAGEMENT-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/clinic-management-smoke-18008.png`
- `[x]` `CLINIC-MANAGEMENT-SMOKE-JSON` - evidence JSON captured at `output/playwright/clinic-management-smoke-18008.json`
- `[x]` `CLINIC-BRANCHES-FIX` - BranchManagement now uses the canonical `/clinic/branches` CRUD path and derives summary stats from the branch list instead of a nonexistent `/branches/stats` endpoint
- `[x]` `CLINIC-BRANCHES-SMOKE` - browser smoke on the `Филиалы` tab loaded `5` live branches, `5` active branches, and rendered the real branch cards after the route-shape fix
- `[x]` `CLINIC-BRANCHES-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/clinic-branches-smoke-fixed.png`
- `[x]` `CLINIC-EQUIPMENT-FIX` - EquipmentManagement now uses canonical `/clinic/equipment` and `/clinic/branches` routes, derives live stats from the response payload, and no longer falls back to fake equipment/branch data on load errors
- `[x]` `CLINIC-EQUIPMENT-SMOKE` - browser smoke on the `Оборудование` tab loaded `3` live equipment rows and `3` active units, with `GET /clinic/equipment` and `GET /clinic/branches` returning `200`
- `[x]` `CLINIC-EQUIPMENT-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/clinic-equipment-smoke-fixed.png`
- `[x]` `CLINIC-BACKUPS-FIX` - BackupManagement now uses canonical `/clinic/backups` routes, derives live stats from the backup list, and no longer calls the missing `/backups` or `/backups/stats` endpoints
- `[x]` `CLINIC-BACKUPS-SMOKE` - browser smoke on the `Резервные копии` tab loaded `1` live backup and `0` completed backups; `GET /clinic/backups` returned `200` and the panel rendered the real card plus cleanup action
- `[x]` `CLINIC-BACKUPS-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/clinic-backups-smoke-fixed.png`

## Group Permissions Smoke

- `[x]` `GROUP-PERMISSIONS-SMOKE` - admin `Users -> Group Permissions` loaded on `:5173 -> :18008`; users list populated from `/users/users`, `GET /admin/permissions/groups|roles|permissions|cache/stats` returned `200`, `Группы` rendered the group cards, and `Кэш` rendered the live cache stats card with `Очистить кэш`
- `[x]` `GROUP-PERMISSIONS-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/group-permissions-smoke-final.png`

## Finance CRUD Smoke

- `[x]` `FINANCE-CRUD-SMOKE` - admin `Finance` overview loaded on the current stack; one-session browser CRUD passed: created `ADM-07 Finance Smoke 2026-03-27T02-25-50-510Z`, edited amount `12 000 -> 13 000` and status `Ожидает -> Завершена`, then deleted the row and returned the table back to the baseline count
- `[x]` `FINANCE-CRUD-SMOKE-SHOT` - evidence screenshots captured at `output/playwright/finance-smoke-after-create.png`, `output/playwright/finance-smoke-after-edit.png`, and `output/playwright/finance-smoke-after-delete.png`
- `[x]` `FINANCE-AMOUNT-STEP-UX` - finance amount input now uses integer-friendly browser validation (`min=1`, `step=1`, `inputMode=numeric`) with a helper hint for UZS amounts; focused vitest, eslint, and frontend build passed after the UX tweak

## Security Settings Smoke

- `[x]` `SECURITY-SMOKE` - admin security subpanel rendered on `:5173 -> :18008`; tabs `Пароль / 2FA / Сессии / Безопасность / Аудит` switched correctly, invalid password validation fired, and the local `onSave` path executed without runtime errors
- `[~]` `SECURITY-SETTINGS-LOCAL-ONLY` - current `SecuritySettings` implementation persists to component state and logs success only; the panel does not yet wire a backend persistence endpoint
- `[x]` `SECURITY-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/security-settings-smoke-final.png`

## Wizard Settings Smoke

- `[x]` `WIZARD-SETTINGS-SMOKE` - admin wizard settings toggled `true -> false -> true` on `:5173 -> :18008`; `POST /api/v1/admin/wizard-settings` returned `200`, the reload reflected the saved value, and cleanup restored the original state
- `[x]` `WIZARD-SETTINGS-SMOKE-SHOT` - evidence screenshots captured at `output/playwright/wizard-settings-initial.png` and `output/playwright/wizard-settings-final.png`
- `[x]` `WIZARD-SETTINGS-WARNINGS` - `WizardSettings` no longer feeds invalid `MacOSStatCard` color props; supported tokens `green / orange / blue` removed the React warning noise and `npm run build` stayed green

## AI Settings Smoke

- `[x]` `AI-SETTINGS-SMOKE` - admin AI settings loaded on `:5173 -> :18008`; `GET /api/v1/admin/ai/providers`, `/settings`, and `/stats?days_back=7` all returned `200`, the provider cards rendered, and the refresh button reloaded the same data without runtime errors
- `[x]` `AI-SETTINGS-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/ai-settings-smoke.png`
- `[x]` `DISPLAY-SETTINGS-SMOKE` - admin display settings loaded on `:5174 -> :18000` after adding the frontend origin to backend CORS allowlist in `backend/.env`; `GET /api/v1/admin/display/boards`, `/themes`, `/stats`, and `/users/me/preferences` all returned `200`, and the browser save/reload flow persisted `QA display room smoke` with queue count `8`
- `[x]` `DISPLAY-SETTINGS-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/display-settings-smoke-final.png`

## Activation Smoke

- `[x]` `ACTIVATION-SMOKE` - admin `Activation` panel loaded on `:5174 -> :18000`; create-key UI issued a trial key successfully, the list refetched without crashing, and backend revoke returned the stack to `NO_ACTIVATION`
- `[x]` `ACTIVATION-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/activation-smoke-final.png`
- `[x]` `ACTIVATION-SMOKE-API` - live API proof on `:18000` confirmed two smoke keys were issued and then revoked; `/activation/status` remained `NO_ACTIVATION`

## Payment Providers Smoke

- `[x]` `PAYMENT-PROVIDERS-SMOKE` - admin `Payment Providers` loaded on `:5174 -> :18000`; saving required provider fields succeeded after filling test-only credentials, and the refreshed page preserved the saved `CLICK`/`PAYME` values
- `[x]` `PAYMENT-PROVIDERS-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/payment-providers-smoke-final-clean.png`
- `[x]` `BILLING-SMOKE` - invoice create path now normalizes timezone-aware timestamps to local-naive `DateTime` values; live browser smoke on `/admin/settings?section=billing` created `INV-2026-000002` and returned to the invoice list without timezone errors
- `[x]` `BILLING-SMOKE-EVIDENCE` - browser evidence captured in `.playwright-cli/page-2026-03-27T08-00-52-463Z.yml` and `.playwright-cli/network-2026-03-27T08-01-29-244Z.log`; targeted unit regression passed in `backend/tests/unit/test_billing_service_timezone.py`
- `[x]` `BILLING-SMOKE-CLEANUP` - stale console/WebSocket noise from the long-lived browser session was treated as environmental; final billing proof now uses the clean reload path plus the fresh network capture and unit regression as the source of truth

## Benefit Settings Smoke

- `[x]` `BENEFIT-SETTINGS-SMOKE` - admin `Benefit Settings` loaded on `:5173 -> :18008`; repeated visits and льготные flags rendered, `POST /api/v1/admin/benefit-settings` returned `200`, reload reflected `22 days`, and cleanup restored the original `21 days`
- `[x]` `BENEFIT-SETTINGS-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/benefit-settings-smoke-final.png`
- `[x]` `BENEFIT-SETTINGS-SMOKE-NETWORK` - network trace captured at `output/playwright/benefit-settings-smoke-network.log`

## Clinic Settings Smoke

- `[x]` `CLINIC-SETTINGS-SMOKE` - admin `Clinic Settings` loaded on `:5173 -> :18008`; clinic profile fields rendered, timezone save `Asia/Tashkent -> Asia/Almaty` returned `Настройки успешно сохранены`, reload reflected `Asia/Almaty`, and cleanup restored `Asia/Tashkent`
- `[x]` `CLINIC-SETTINGS-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/clinic-settings-smoke-final.png`
- `[x]` `CLINIC-SETTINGS-SMOKE-NETWORK` - network trace captured at `output/playwright/clinic-settings-smoke-network.log`

## Settings Theme Smoke

- `[x]` `SETTINGS-THEME-SMOKE` - admin settings theme preference now bootstraps the missing profile/preferences/notification rows for user `#45`; `PUT /api/v1/users/me/preferences` returned `200`, the theme toggled to `Темная`, reload preserved it, and cleanup restored `Авто`
- `[x]` `SETTINGS-THEME-SMOKE-SHOT` - evidence screenshot captured at `output/playwright/settings-theme-smoke-final.png`
- `[x]` `SETTINGS-THEME-SMOKE-NETWORK` - network trace captured at `output/playwright/settings-theme-smoke-network.log`

## Dynamic Pricing Smoke

- `[x]` `DYNAMIC-PRICING-SMOKE` - admin `Dynamic Pricing` loaded on `:5173 -> :18008`; rule create/save passed once payload normalization mapped enum values to backend lowercase and stripped empty optional fields, then the smoke rule was removed from Postgres during cleanup
- `[x]` `DYNAMIC-PRICING-DELETE-500` - UI delete action now passes after dynamic pricing cleanup removed linked `pricing_rule_services` rows and detached `service_packages`; live API delete on rule `3` returned `200`, the temporary package remained with `pricing_rule_id=None`, and the smoke log was captured in `output/playwright/dynamic-pricing-delete-smoke.log`
- `[x]` `DYNAMIC-PRICING-SMOKE-SHOT` - clean-state screenshot captured at `output/playwright/dynamic-pricing-smoke-clean.png`

## Evidence Index

- `output/playwright/reg-01-after-login-refresh.png`
- `output/playwright/reg-01-cycle-2.json`
- `output/playwright/reg-01-cycle-2.png`
- `output/playwright/reg-02-cycle2-final-success3.png`
- `output/playwright/reg-03-cycle2-lab-panel-final.png`
- `output/playwright/lab-02-workbench-open-instance.png`
- `output/playwright/lab-02-after-save-cycle2.png`
- `output/playwright/lab-03-after-finalize-cycle2.png`
- `output/playwright/lab-03-after-print-cycle2.png`
- `output/playwright/lab-04-reports-tab-cycle2.png`
- `output/playwright/lab-04-open-existing-report-cycle2.png`
- `output/playwright/reg-02-before-finish-valid-phone.png`
- `output/playwright/reg-02-after-finish-valid-phone.png`
- `output/playwright/lab-01-queue.png`
- `output/playwright/lab-02-after-save.png`
- `output/playwright/lab-03-after-print.png`
- `output/playwright/cashier-after-login.png`
- `output/playwright/cashier-after-payment.png`
- `output/playwright/cash-04-receipt.txt`
- `output/playwright/cash-05-history-row.png`
- `output/playwright/cash-05-history-row.txt`
- `output/playwright/cash-04-ui-history-188.png`
- `output/playwright/cash-04-ui-receipt-188.pdf`
- `output/playwright/cash-04-backend-18020.log`
- `output/playwright/cash-04-frontend-4174.log`
- `output/playwright/cash-06-refund-modal.png`
- `output/playwright/cash-06-after-refund.png`
- `output/playwright/cash-06-after-reload.png`
- `output/playwright/cash-06-refund-state.json`
- `output/playwright/cash-01-cycle3.png`
- `output/playwright/cash-01-cycle3.txt`
- `output/playwright/cash-02-local-smoke-final.png`
- `cash-06-reverify-history-empty.png`
- `cash-06-reverify-cash-modal.png`
- `cash-06-reverify-history-before-refund.png`
- `cash-06-reverify-refund-modal-filled.png`
- `cash-06-reverify-history-after-refund-same-session.png`
- `cash-06-reverify-network.txt`
- `output/playwright/doctor-after-login.png`
- `output/playwright/doctor-queue-clicked.png`
- `output/playwright/cardio-after-login.png`
- `output/playwright/cardio-after-call.png`
- `output/playwright/cardio-blood-tests-filled.png`
- `output/playwright/cardio-blood-tests-saved.png`
- `output/playwright/cardio-blood-tests-reopen.png`
- `output/playwright/cardio-after-row-click.png`
- `output/playwright/cardio-history-after-select.png`
- `output/playwright/cardio-history-body.txt`
- `output/playwright/cardio-supporting-tabs-sequence.json`
- `output/playwright/cardio-supporting-tabs-sequence.png`
- `output/playwright/admin-dashboard.png`
- `output/playwright/admin-users-search.png`
- `output/playwright/admin-users-role-filter.png`
- `output/playwright/admin-user-after-create.png`
- `output/playwright/qa-lab-login.png`
- `output/playwright/admin-doctor-after-create.png`
- `output/playwright/admin-patient-after-create.png`
- `output/playwright/admin-service-after-create.png`
- `output/playwright/admin-live-ids.json`
- `output/playwright/adm-05-passport-after-fix-4194.json`
- `output/playwright/adm-05-passport-after-fix-4194.png`
- `output/playwright/adm-06-live-verify-4195.json`
- `output/playwright/adm-06-live-admin-service-4195.png`
- `output/playwright/queue-profiles-smoke-clean.png`
- `output/playwright/queue-settings-smoke.png`
- `output/playwright/queue-limits-smoke-fixed.png`
- `output/playwright/queue-cabinet-management-smoke-18022.png`
- `output/playwright/queue-cabinet-management-smoke-18022.json`
- `output/playwright/clinic-management-smoke-18008.png`
- `output/playwright/clinic-management-smoke-18008.json`
- `output/playwright/clinic-branches-smoke-fixed.png`
- `output/playwright/clinic-equipment-smoke-fixed.png`
- `output/playwright/clinic-licenses-smoke-fixed.png`
- `output/playwright/clinic-backups-smoke-fixed.png`
- `output/playwright/group-permissions-smoke-final.png`
- `output/playwright/lab-04-forms-empty.png`
- `output/playwright/lab-04-reprint.pdf`
- `output/playwright/lab-04-recent-reports.png`
- `output/playwright/lab-04-opened-existing-report.png`
- `output/playwright/lab-04-recent-reports.json`
- `output/playwright/cardio-fix-create-18001.json`
- `output/playwright/cardio-fix-list-18001.json`
- `output/playwright/backend-18001-live.log`
- `output/playwright/frontend-4173-live.log`
- `output/playwright/derma-live-appointments.png`
- `output/playwright/derma-live-visit.png`
- `output/playwright/derma-live-skin-after-save.png`
- `output/playwright/derma-live-history-after-save.png`
- `output/playwright/derma-live-skin-reopen.png`
- `output/playwright/derma-live-created-visit.json`
- `output/playwright/derma-live-verification.json`
- `output/playwright/derma-02-history.png`
- `output/playwright/derma-02-skin-reopen.png`
- `output/playwright/derma-02-check.json`
- `output/playwright/derma-03-supporting-tabs.png`
- `output/playwright/derma-03-supporting-tabs.json`
- `output/playwright/doctor-general-live-18004.json`
- `output/playwright/backend-18005-live.log`
- `output/playwright/frontend-8080-live.log`
- `output/playwright/doc-02-before-call.png`
- `output/playwright/doc-02-after-call.png`
- `output/playwright/doc-02-live-verification.json`
- `output/playwright/doc-03-diagnostics.png`
- `output/playwright/doc-03-return-after-fix.png`
- `output/playwright/doc-03-network.txt`
- `output/playwright/doc-03-console.txt`
- `output/playwright/doc-04-after-complete.png`
- `output/playwright/doc-04-network.txt`
- `output/playwright/doc-04-console.txt`
- `output/playwright/doc-05-appointments-after-submit.png`
- `output/playwright/doc-05-network.txt`
- `output/playwright/doc-05-console.txt`
- `output/playwright/doc-06-network-pre-fix.txt`
- `output/playwright/doc-06-after-no-return.png`
- `output/playwright/doc-06-after-incomplete.png`
- `output/playwright/doc-06-network.txt`
- `output/playwright/doc-06-console.txt`
- `output/playwright/dent-01-network.txt`
- `output/playwright/dent-01-network-postsave.txt`
- `output/playwright/dent-01-network-after-dom-save.txt`
- `output/playwright/dent-01-network-after-backend-restart.txt`
- `output/playwright/dent-01-console-errors.txt`
- `output/playwright/dent-01-after-save.png`
- `output/playwright/dent-02-visit-protocol-before-save.png`
- `output/playwright/dent-02-reports-reopen.png`
- `output/playwright/dent-02-visit-protocol-reopened.png`
- `output/playwright/dent-02-reopen-state.json`
- `output/playwright/dent-02-ui-final.png`
- `output/playwright/dent-02-ui-final.json`
- `output/playwright/dent-02-tab-scan.json`
- `output/playwright/dent-patients-search-451.json`
- `output/playwright/dent-02-debug-dom.png`
- `output/playwright/dent-02-debug-dom.json`
- `output/playwright/dent-03-supporting-tabs.png`
- `output/playwright/dent-03-supporting-tabs.json`
- `output/playwright/dent-emr-404-after-validate-status.png`
- `output/playwright/dent-emr-404-network-after-validate-status.txt`
- `output/playwright/dent-emr-404-console-after-validate-status.txt`
- `output/playwright/registrar-storage.json`
- `output/playwright/lab-storage.json`
- `output/playwright/cashier-storage.json`
- `output/playwright/doctor-storage.json`
- `output/playwright/cardio-storage.json`
- `output/playwright/admin-storage.json`
- `output/playwright/qa-lab-storage.json`
- `output/playwright/finance-smoke-after-create.png`
- `output/playwright/finance-smoke-after-edit.png`
- `output/playwright/finance-smoke-after-delete.png`
- `output/playwright/benefit-settings-smoke-final.png`
- `output/playwright/benefit-settings-smoke-network.log`
- `output/playwright/clinic-settings-smoke-final.png`
- `output/playwright/clinic-settings-smoke-network.log`
- `output/playwright/settings-theme-smoke-final.png`
- `output/playwright/settings-theme-smoke-network.log`
- `output/playwright/dynamic-pricing-delete-smoke.log`
- `output/playwright/dynamic-pricing-smoke-clean.png`
- `output/playwright/discount-benefits-smoke-clean.png`
- `output/playwright/activation-smoke-final.png`
- `output/playwright/payment-providers-smoke-final-clean.png`
- `frontend/test-results/cardio-fix-live-CARD-01-CA-c2127-ix-on-temp-5175-18001-stack-chromium/test-failed-1.png`
- `frontend/test-results/cardio-fix-live-CARD-01-CA-c2127-ix-on-temp-5175-18001-stack-chromium/error-context.md`
