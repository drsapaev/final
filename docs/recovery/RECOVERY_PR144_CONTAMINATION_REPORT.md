# PR 144 Contamination Report

## Summary
PR `#144` / branch `codex/recovery-main-execution` is contaminated by unrelated runtime expansion and must not be merged as-is.

## Approved Scope
- `docs/recovery/*` execution packet artifacts
- docs reconciliation changes tied to recovery packet execution
- workflow/dependency files directly related to the 7 validated recovery changes
- final recovery closeout docs and validation evidence

## Outside Approved Scope
- `frontend/src/components/emr-v2/*`
- `frontend/src/pages/PatientPanel.jsx`
- `backend/app/services/*`
- `backend/app/api/v1/endpoints/*` beyond the explicitly approved recovery changes
- `docs/status/*`
- unrelated historical feature files under `frontend/src/components/*` and `backend/app/*`
- bulk UI refactors and EMR runtime work

## Examples Of Unrelated Runtime Expansion
- `frontend/src/components/emr-v2/EMRContainerV2.jsx`
- `frontend/src/components/emr-v2/EMRHelpDialog.jsx`
- `frontend/src/pages/PatientPanel.jsx`
- `backend/app/services/emr_v2_service.py`
- `backend/app/services/notification_platform_service.py`
- `backend/app/services/lab_reporting_service.py`
- `docs/status/WAVE2_GATE_DECISION.md`
- `docs/status/wave196/W196_UNIFIED_CI_RESULT.md`

## Likely Contamination Sources
- Branch-state drift relative to the approved recovery packet
- Inherited historical content already present on the execution branch when the recovery packet was assembled
- Possible accidental carry-forward of earlier wave content during prior recovery work

## What Is Not Evidenced
- I do not see evidence that the approved recovery docs or dependency/CI recovery edits themselves required the unrelated runtime expansion.
- The contamination footprint is much broader than the recovery packet and therefore cannot be justified as part of the approved scope.

## Exact Recommendation
- Rebuild a narrow PR from clean current `main`.
- Port only the approved recovery docs, validated dependency/CI recovery slices, and closeout docs.
- Do not attempt to salvage PR `#144` by merging, rebasing, or rewriting it in place.
