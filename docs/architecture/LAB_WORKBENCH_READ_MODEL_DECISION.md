# Lab Workbench Read-Model Decision

**Status:** Evidence checkpoint  
**Date:** 2026-05-25  
**Scope:** Lab workbench read flow only  
**Base evidence:** `c656d701` (`test: document explicit registrar queue doctor selection (#1241)`)

## Executive Decision

Do not add BFF-lite for LabPanel yet.

The Lab workbench is the strongest remaining read-model candidate, but the next implementation step should extend existing endpoints first. A separate BFF service is not justified, and `/api/v1/ui/*` is premature.

Recommended next implementation PR:

- Use the existing `department` query on `GET /api/v1/registrar/queues/today` for lab queue rows.
- Add an additive read option to `GET /api/v1/lab/report-instances`, such as `latest_per_visit=true`, if the current frontend latest-instance merge remains fragile.
- Keep lab report commands on the existing `/api/v1/lab/report-instances/*` command routes.

Only re-open `/api/v1/ui/lab/workbench` after that extension is measured and still leaves fragile screen assembly.

## Evidence

Frontend orchestration:

- `frontend/src/pages/LabPanel.jsx:254` fetches `/registrar/queues/today`.
- `frontend/src/pages/LabPanel.jsx:264` filters queues to `lab` / `laboratory` in React.
- `frontend/src/pages/LabPanel.jsx:273` fetches `/lab/report-instances` by `visit_ids`.
- `frontend/src/pages/LabPanel.jsx:103` merges queue rows with the latest lab report instance by `visit_id`.
- `frontend/src/pages/LabPanel.jsx:308` fetches `/lab/templates`.
- `frontend/src/pages/LabPanel.jsx:313` fetches `/lab/templates/{template_id}`.
- `frontend/src/pages/LabPanel.jsx:337` fetches patient report history through `/lab/report-instances?patient_id=...`.
- `frontend/src/pages/LabPanel.jsx:350` fetches recent reports through `/lab/report-instances?limit=50`.
- `frontend/src/pages/LabPanel.jsx:377` asks the backend to resolve allowed/default templates through `/lab/template-resolutions/resolve`.

Backend contract owners:

- `backend/app/api/v1/endpoints/lab_reporting.py:223` publishes `GET /lab/templates`.
- `backend/app/api/v1/endpoints/lab_reporting.py:232` publishes `POST /lab/template-resolutions/resolve`.
- `backend/app/api/v1/endpoints/lab_reporting.py:375` publishes `GET /lab/report-instances`.
- `backend/app/api/v1/endpoints/lab_reporting.py:398` publishes `POST /lab/report-instances`.
- `backend/app/api/v1/endpoints/lab_reporting.py:463` publishes `mark-ready`.
- `backend/app/api/v1/endpoints/lab_reporting.py:476` publishes `finalize`.
- `backend/app/api/v1/endpoints/lab_reporting.py:489` publishes `revise`.
- `backend/app/api/v1/endpoints/lab_reporting.py:502` publishes `mark-printed`.
- `backend/app/services/lab_reporting_service.py:118` owns template resolution.
- `backend/app/services/lab_reporting_service.py:402` owns instance listing.
- `backend/app/services/lab_reporting_service.py:434` owns instance creation and visit/order resolution.
- `backend/app/services/lab_reporting_service.py:567` owns mark-ready.
- `backend/app/services/lab_reporting_service.py:575` owns finalization.
- `backend/app/services/lab_reporting_service.py:627` owns revision.
- `backend/app/services/lab_reporting_service.py:665` owns printed status.
- `backend/app/services/lab_reporting_service.py:675` and `:683` own `available_actions` and `can_*` flags.

Existing tests:

- `frontend/src/pages/__tests__/LabPanel.contract.test.jsx` already proves queue status and lab report status stay separate.
- `backend/tests/test_lab_reporting_api.py` covers template resolution, report instance state transitions, available actions, and legacy lab route suppression.

## API Call Inventory

Initial `/lab` load:

- `GET /api/v1/registrar/queues/today`
- Conditional `GET /api/v1/lab/report-instances?visit_ids=...&limit=...`
- `GET /api/v1/lab/templates`
- Conditional `GET /api/v1/lab/templates/{template_id}`
- `GET /api/v1/lab/report-instances?limit=50`

Selecting a queue row:

- `GET /api/v1/lab/report-instances?patient_id=...&limit=50`
- `POST /api/v1/lab/template-resolutions/resolve`

Opening an existing report:

- `GET /api/v1/lab/report-instances/{instance_id}`
- Then patient history refresh if the instance carries `patient_snapshot.patient_id`.

Report commands:

- `POST /api/v1/lab/report-instances`
- `PUT /api/v1/lab/report-instances/{instance_id}`
- `POST /api/v1/lab/report-instances/{instance_id}/bulk-values`
- `POST /api/v1/lab/report-instances/{instance_id}/mark-ready`
- `POST /api/v1/lab/report-instances/{instance_id}/finalize`
- `POST /api/v1/lab/report-instances/{instance_id}/revise`
- `POST /api/v1/lab/report-instances/{instance_id}/mark-printed`
- `GET /api/v1/lab/report-instances/{instance_id}/pdf`

Template administration:

- `GET /api/v1/lab/catalog/units`
- `GET /api/v1/lab/catalog/analytes`
- Existing template mutation routes under `/api/v1/lab/templates/*` and `/api/v1/lab/template-versions/*`.

## Assembly Classification

Presentation-only:

- Lab tabs, counters, selected row state, local form state, labels, badges, and alert text.
- Local rendering of queue row cards and report history cards.
- Local draft input state before saving report values.
- Local print fallback UI after backend permits printing.

Existing endpoint extension candidates:

- Lab queue filtering currently happens in React after `/registrar/queues/today`. Prefer using the existing `department=lab` query before adding a new endpoint.
- Latest report status per queue row is selected in React by merging `/registrar/queues/today` with `/lab/report-instances?visit_ids=...`. Prefer an additive `latest_per_visit=true` option on `GET /lab/report-instances` before adding `/api/v1/ui/lab/workbench`.
- The initial template summary plus first template detail fetch may be acceptable now. If it becomes a performance issue, prefer an additive template summary/detail option under existing `/lab/templates`.

True BFF-lite candidate:

- A read-only `GET /api/v1/ui/lab/workbench` may be justified later only if the existing endpoint extensions above still leave fragile cross-domain assembly.
- Such an endpoint would be a screen DTO only: queue rows, latest report summary, template choices, and read-only action facts already computed by core services.

Contract concerns to keep out of BFF:

- Lab finalization, revision, printed state, immutability, template publishing, reference range evaluation, critical finding calculation, and `available_actions` must remain in `LabReportingService`.
- Queue fairness, queue time, and lab queue membership must remain backend-owned through existing queue/registrar services.
- React must not infer lab command availability from `status`; it should continue consuming backend `available_actions` / `can_*`.

Command-related follow-up:

- `frontend/src/components/laboratory/LabReportWorkbench.jsx` already gates report action buttons with backend `available_actions` / `can_*`.
- The auto-create behavior for a single allowed template is command-related frontend behavior. Do not move it into a read-model endpoint. If product wants to keep it, add a focused contract test proving backend template resolution drives the choice and `createInstance` still performs final validation.

## Endpoint Strategy

Next PR should be existing endpoint extension, not BFF-lite:

1. Backend:
   - Keep `GET /api/v1/registrar/queues/today` as the queue source.
   - Use or test its existing `department` query for lab-only rows.
   - Consider `GET /api/v1/lab/report-instances?visit_ids=...&latest_per_visit=true` as an additive contract.
   - Keep all lab commands on existing `/lab/report-instances/*` routes.

2. Frontend:
   - Replace client-side lab queue filtering with the backend `department=lab` query if the existing endpoint behavior is correct.
   - Reduce latest-instance selection to consuming the backend's latest-per-visit result if added.
   - Preserve presentation-only state and labels.

3. Tests:
   - Backend test for lab-only queue filtering, if not already covered.
   - Backend test for latest-per-visit report instance query if added.
   - Frontend contract test proving LabPanel no longer owns latest-instance selection when the backend provides it.
   - OpenAPI contract test only if the response/query shape changes.

Rollback:

- Revert the frontend to existing `/registrar/queues/today` plus `/lab/report-instances?visit_ids=...` assembly.
- No data migration or command semantic rollback should be required.

## No-Go Rules

Do not add in the next PR:

- `/api/v1/ui/*`
- a separate BFF service
- command wrappers
- frontend-owned lab status transitions
- frontend-owned finalization, revision, print, or template publish policy
- queue fairness/order logic in LabPanel
- duplicated lab reference range or critical finding logic

## Decision Gate After Endpoint Extension

Re-measure after the existing endpoint extension PR:

- Initial `/lab` call count.
- Whether LabPanel still merges queue rows with latest report instances.
- Whether report action availability remains backend-owned.
- Whether template resolution remains backend-owned.
- Whether template detail/history/recent report calls are still fragile or just normal tab-level data.

If the extension removes the queue/report merge fragility, BFF-lite is not needed for LabPanel. If the screen still requires brittle cross-domain assembly, consider a read-only `/api/v1/ui/lab/workbench` with backend services remaining the source of truth.
