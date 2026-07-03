# ADR-0003: Migrate Cardiologist Panel to EMRContainerV2

**Status:** Proposed
**Date:** 2026-07-04
**Owner:** Frontend Platform
**Related:** `docs/WORKFLOW_REFACTOR_FOLLOWUP.md` P0-3

## Context

The three doctor specialty panels use **two different patterns** for EMR v2 access:

| Panel | EMR access pattern | Has autosave? | Has conflict resolution? | Has undo/redo? |
|---|---|---|---|---|
| Dermatologist | `<EMRContainerV2>` + `useEMR` reducer | ✅ 3s debounce + 30s maxWait | ✅ optimistic locking + `client_session_id` | ✅ 50-step history |
| Dentist | `<EMRContainerV2>` + `useEMR` reducer (via visit protocol bridge) | ✅ (in `persistVisitProtocol`) | ✅ (via `row_version` in EMR v2 API) | ❌ (protocol uses local cache fallback) |
| **Cardiologist** | **Raw `fetch('/v2/emr/{visitId}')`** | ❌ | ❌ | ❌ |

### The Problem

`CardiologistPanelUnified.loadEMR` (line ~1216) bypasses the entire EMR v2 infrastructure:

```javascript
const response = await fetch(`${API_V1_BASE}/v2/emr/${visitId}`, {
  method: 'GET',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  }
});
```

And the local `visitData` state:
```javascript
const [visitData, setVisitData] = useState({
  complaint: '',
  diagnosis: '',
  icd10: '',
  notes: ''
});
```

This causes **five concrete problems**:

1. **No autosave** — the doctor's typing is lost on page refresh or accidental navigation. Derma and Dentist autosave every 3s; Cardio doesn't autosave at all.

2. **No conflict resolution** — if two Cardio tabs open the same visit, both can save and the second overwrite silently wins. Derma/Dentist get 409 Conflict + `reloadFromServer()` / `forceOverwrite()` UI.

3. **No undo/redo** — Cardio doctors cannot undo a typo in the diagnosis field. Derma has 50-step history via `emrReducer.js`.

4. **State duplication** — Cardio maintains its own `visitData` shape `{ complaint, diagnosis, icd10, notes }` that duplicates the EMR v2 backend shape. When the backend adds a field (e.g. `blood_pressure`), Cardio must manually add it to `visitData`, the loadEMR mapping, and the save handler. Derma/Dentist get new fields for free via `useEMR`'s generic `SET_FIELD` action.

5. **Inconsistent error handling** — PR #1779 (commit eae3a00) improved Cardio's `loadEMR` error handling (401/403/5xx/AbortError), but it's still bespoke. Derma/Dentist get the unified `useEMR` error handling including `writeAccessDeniedRef` (instant pause on 401/403, no further API calls until reset).

## Decision

**Migrate CardiologistPanelUnified to use `<EMRContainerV2>` like DermatologistPanelUnified.**

### Principles

1. **One EMR component** — all three specialty panels render `<EMRContainerV2 visitId={...} patientId={...} specialty="cardiology" />`.
2. **One EMR hook** — `useEMR` reducer is the single source of truth for EMR state (load, save, conflict, undo/redo).
3. **One autosave hook** — `useEMRAutosave` handles debounce, max-wait, backoff, and access-denied pause.
4. **Specialty-specific sections** — Cardio keeps its ICD-10 critical-diagnosis warning (`getCriticalDiagnosisWarning`) by passing it as an `ICD10Component` prop to `EMRContainerV2`, matching the Derma pattern.
5. **Visit completion stays in the panel** — `handleSaveVisit` (which calls `queueService.completeVisit`) is workflow logic, not EMR logic. It stays in the panel and reads the final EMR state from `useEMR`'s `data` field.

### Migration Plan (4 phases, each a separate PR)

#### Phase 1: Audit Cardio EMR fields vs. EMR v2 schema (No code change)
- Document every field Cardio currently reads/writes: `complaint`, `diagnosis`, `icd10`, `notes`, plus any cardiology-specific fields (ECG, blood tests — these are separate tabs, not EMR).
- Compare with `backend/app/schemas/emr_v2.py` — confirm all Cardio fields exist in EMR v2.
- If any field is missing from EMR v2, add it to the backend schema first.
- **Output**: `docs/architecture/ADR-0003-cardio-emr-field-mapping.md` (appendix to this ADR).

#### Phase 2: Extract Cardio ICD-10 warning into a reusable component (Low risk)
- Move `getCriticalDiagnosisWarning` + the critical-ICD-10 confirm dialog from `CardiologistPanelUnified.jsx` into `frontend/src/components/cardiology/CriticalICD10Warning.jsx`.
- Accept props: `icd10`, `onConfirm`, `onCancel`.
- Cardio imports it and passes it as `ICD10Component` to `EMRContainerV2`.
- **Estimated diff**: ~150 lines moved, 0 behaviour change.
- **Testing**: Existing Cardio manual test — I21 critical diagnosis → red confirm dialog.

#### Phase 3: Replace Cardio `loadEMR` + `visitData` with `useEMR` hook (Medium risk)
- Add `import { useEMR } from '../hooks/useEMR'` to Cardio.
- Replace local `visitData` state with `useEMR(visitId, { specialty: 'cardiology' })` return value.
- Replace `loadEMR` function with the `useEMR` load effect.
- Replace `handleSaveVisit`'s payload construction to read from `useEMR.data` instead of local `visitData`.
- Keep the existing `queueService.completeVisit` call — that part doesn't change.
- Remove the raw `fetch` calls in `loadEMR`.
- **Estimated diff**: ~200 lines removed, ~50 lines added.
- **Testing**: Manual Cardio flow — load EMR → edit fields → see autosave indicator → complete visit.

#### Phase 4: Replace Cardio visit tab with `<EMRContainerV2>` (Medium risk)
- Replace the inline visit-tab JSX (the form with complaint/diagnosis/icd10/notes inputs) with `<EMRContainerV2 visitId={...} patientId={...} specialty="cardiology" ICD10Component={CriticalICD10Warning} />`.
- The container renders the form fields, autosave indicator, conflict dialog, undo/redo buttons.
- Cardio's `handleSaveVisit` reads the final EMR state via a `ref` or `onComplete` callback from `EMRContainerV2`.
- **Estimated diff**: ~300 lines removed, ~20 lines added.
- **Testing**: Full Cardio clinic flow per `docs/WORKFLOW_REFACTOR_FOLLOWUP.md` §1.1.

### Acceptance Criteria

- [ ] `CardiologistPanelUnified.jsx` no longer contains any `fetch('/v2/emr/')` call
- [ ] `CardiologistPanelUnified.jsx` no longer maintains local `visitData` state
- [ ] Cardio renders `<EMRContainerV2 specialty="cardiology" />` in the visit tab
- [ ] Cardio ICD-10 critical warning still triggers for I21/I46/I50/I71/R57 codes
- [ ] Cardio `handleSaveVisit` still calls `queueService.completeVisit` with the same payload shape
- [ ] Autosave indicator visible in Cardio (was: absent)
- [ ] Conflict dialog appears when two Cardio tabs edit the same visit (was: silent overwrite)
- [ ] Undo/redo buttons work in Cardio (was: absent)
- [ ] `npx vitest run` — all 500+ tests pass
- [ ] `DoctorPanels.contract.test.jsx` — all 9 SSOT assertions pass
- [ ] Manual clinic test per `docs/WORKFLOW_REFACTOR_FOLLOWUP.md` §1.1 — Cardio flow

## Consequences

**Плюсы:**
- All three specialty panels use the same EMR pattern — easier to maintain
- Cardio gets autosave, conflict resolution, undo/redo "for free"
- New EMR v2 backend fields automatically available in Cardio
- ~500 lines of bespoke Cardio EMR code deleted
- Better PHI protection (useVisitLifecycle already wired in PR #1779; EMRContainerV2 adds another layer)

**Минусы:**
- 4-phase migration requires coordination — each phase is a separate PR
- Phase 3 and 4 are medium risk — manual Cardio clinic testing required
- Cardio's `getCriticalDiagnosisWarning` logic must be preserved exactly (it triggers `intent='danger'` for I21/I46/I50/I71/R57 ICD-10 codes — a regression here could cause missed critical diagnoses)
- The `EMRContainerV2` component must support a `specialty="cardiology"` canonical speciality — verify this is already handled in `useEMR.js`'s `buildInitialEMRData(specialty)` function
- Backend EMR v2 schema must be checked to ensure all Cardio fields are supported (Phase 1 output)

## Alternatives Considered

### A. Keep Cardio on raw fetch, but add autosave/conflict/undo manually
- Implement autosave, conflict resolution, and undo/redo in Cardio's bespoke EMR code.
- **Rejected**: This duplicates ~500 lines of `useEMR` + `useEMRAutosave` + `emrReducer.js` logic. The whole point of those modules is to be shared.

### B. Migrate Derma and Dentist OFF EMRContainerV2 to raw fetch (for consistency with Cardio)
- Move all three panels to the simpler raw-fetch pattern.
- **Rejected**: Loses autosave, conflict resolution, undo/redo for all three panels. Regression.

### C. Wait for EMR v3 before consolidating
- Defer this migration until a hypothetical EMR v3 rewrite.
- **Rejected**: The PHI leak risk (no conflict resolution → silent overwrite) is present today. We should not wait.

## Follow-up

- After Phase 4 is merged, add a CI lint rule that forbids any new `fetch('/v2/emr/')` call outside `hooks/useEMR.js`.
- Add Cardio to the EMR v2 conflict-resolution audit (`docs/WORKFLOW_REFACTOR_FOLLOWUP.md` §A3).
- Consider extracting the `handleSaveVisit` pattern (read EMR → build payload → call `queueService.completeVisit` → reset state → `callNextWaiting`) into a shared `useVisitCompletion` hook, so all three panels share that logic too.

## References

- `frontend/src/pages/CardiologistPanelUnified.jsx:1216` — current `loadEMR` with raw fetch
- `frontend/src/pages/DermatologistPanelUnified.jsx:1612` — reference `<EMRContainerV2>` usage
- `frontend/src/components/emr-v2/EMRContainerV2.jsx` — the container component
- `frontend/src/hooks/useEMR.js` — the EMR reducer hook
- `frontend/src/hooks/useEMRAutosave.js` — the autosave hook
- `frontend/src/hooks/useVisitLifecycle.js` — already wired in Cardio (PR #1779 commit 5ee3de3)
- `docs/EMR_V2_DOCTOR_GUIDE.md` — doctor-facing EMR v2 guide
- `docs/WORKFLOW_REFACTOR_FOLLOWUP.md` P0-3 — original problem statement
- `backend/app/api/v1/endpoints/emr_v2.py` — EMR v2 backend endpoints
- `backend/app/schemas/emr_v2.py` — EMR v2 Pydantic schemas
