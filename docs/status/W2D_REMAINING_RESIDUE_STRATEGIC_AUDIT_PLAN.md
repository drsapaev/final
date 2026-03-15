# W2D Remaining Residue Strategic Audit Plan

Scope:
- confirm whether the post-W2D cleanup lane still has safe delete candidates
- classify the remaining residue into actionable buckets
- update status docs so the next work item is plan-gated instead of assumed

Evidence targets:
- mount status in `backend/app/api/v1/api.py`
- published route status in `backend/openapi.json`
- live imports across `backend/app`, `backend/tests`, `docs`, and `frontend`
- diff shape between endpoint owners and detached residues

Expected outcome:
- no additional blind cleanup if candidates fail the proof gates
- clear split between mixed-risk, protected audit-only, and non-candidate files
- next execution unit changed from cleanup continuation to planning/prep
