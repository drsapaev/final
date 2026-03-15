# EMR AI Enhanced API Service Cleanup Plan

Scope:
- review detached `backend/app/services/emr_ai_enhanced_api_service.py`
- review detached `backend/app/repositories/emr_ai_enhanced_api_repository.py`
- prove the live `/api/v1/emr/ai-enhanced/*` contract before any deletion
- avoid broader EMR/AI provider redesign or MCP/frontend rewrites

Evidence:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/emr_ai_enhanced.py`
- `backend/openapi.json` publishes the live `/api/v1/emr/ai-enhanced/*`
  routes
- no confirmed backend, test, docs, or frontend imports of the detached pair
  remain
- diff vs the mounted owner is non-behavioral only
- the detached repository is a trivial session adapter with no live callers

Why this is safe:
- dedicated endpoint proof lands before deleting the detached pair
- no live route is removed or remapped
- any mounted-owner fix must stay narrow, evidence-based, and contract-safe
- verification includes OpenAPI, boundary checks, and the full backend suite

Out of scope:
- rewriting `EMREnhancedAIService`
- changing EMR AI enhancement semantics or analytics behavior
- redesigning frontend AI consumers
