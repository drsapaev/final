# EMR Versioning Enhanced API Service Cleanup Plan

Scope:
- review detached `backend/app/services/emr_versioning_enhanced_api_service.py`
- review detached
  `backend/app/repositories/emr_versioning_enhanced_api_repository.py`
- prove the live `/api/v1/emr/versions/*` contract before any deletion
- avoid broader EMR version-history workflow changes in this slice

Evidence:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/emr_versioning_enhanced.py`
- `backend/openapi.json` publishes the live `/api/v1/emr/versions/*` routes
- no confirmed backend, test, docs, or frontend imports of the detached pair
  remain
- diff vs the mounted owner is non-behavioral only
- the detached repository is a trivial session adapter with no live callers

Why this is safe:
- dedicated endpoint proof lands before deleting the detached pair
- no live route is removed or remapped
- the cleanup only touches the detached service/repository pair
- verification includes OpenAPI, boundary checks, and the full backend suite

Out of scope:
- rewriting `EMRVersioningEnhancedService`
- changing version-history or restore semantics
- redesigning frontend EMR history UX
