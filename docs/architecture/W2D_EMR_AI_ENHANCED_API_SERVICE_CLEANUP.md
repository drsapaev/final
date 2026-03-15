# EMR AI Enhanced API Service Cleanup

`backend/app/services/emr_ai_enhanced_api_service.py` and
`backend/app/repositories/emr_ai_enhanced_api_repository.py` were handled as a
protected EMR-adjacent duplicate pair, not as a blind-delete candidate.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/emr_ai_enhanced.py` under
  `/api/v1/emr/ai-enhanced`
- `backend/openapi.json` publishes the live `/api/v1/emr/ai-enhanced/*`
  surface, including smart-template generation, smart suggestions, auto-fill,
  validation, ICD-10 suggestions, patient analysis, specialty templates,
  per-EMR enhancement, and quality analytics
- no live imports of the detached service or repository remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- diff vs the mounted owner was limited to typing/import drift only
- the detached repository was only a trivial unused DB-session adapter

Cleanup performed:
- added `backend/tests/integration/test_emr_ai_enhanced_endpoint_contract.py`
  to protect:
  - embedded multi-body contract on
    `POST /api/v1/emr/ai-enhanced/generate-smart-template`
  - raw dict body plus query contract on
    `POST /api/v1/emr/ai-enhanced/smart-suggestions`
  - path/query plus CRUD wiring on
    `POST /api/v1/emr/ai-enhanced/emr/{emr_id}/ai-enhance`
- fixed a narrow mounted-owner drift in
  `backend/app/api/v1/endpoints/emr_ai_enhanced.py`: the live `ai-enhance`
  route now reads EMR records through `emr_crud.get(...)` instead of calling a
  missing module-level `get(...)`
- deleted detached `backend/app/services/emr_ai_enhanced_api_service.py`
- deleted detached
  `backend/app/repositories/emr_ai_enhanced_api_repository.py`

Effect:
- no mounted `/api/v1/emr/ai-enhanced/*` route was removed
- the live `ai-enhance` path no longer depends on a broken CRUD import shape
- the detached EMR AI enhanced duplicate pair is gone
- the cleanup-capable protected duplicate queue is effectively exhausted
