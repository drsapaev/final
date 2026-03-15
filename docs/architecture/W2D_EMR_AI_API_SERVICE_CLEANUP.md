# EMR AI API Service Cleanup

`backend/app/services/emr_ai_api_service.py` and
`backend/app/repositories/emr_ai_api_repository.py` were handled as a
protected EMR-adjacent duplicate pair, not as a blind-delete candidate.

Verified facts:
- `backend/app/api/v1/api.py` mounts `backend/app/api/v1/endpoints/emr_ai.py`
  under `/api/v1/emr/ai`
- `backend/openapi.json` publishes the live `/api/v1/emr/ai/*` surface,
  including diagnosis, treatment, ICD-10, auto-fill, validate, generic AI
  suggestions, health, and EMR v2 suggest routes
- no live imports of the detached service or repository remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- diff vs the mounted owner was limited to typing/import drift only
- the detached repository was only a trivial unused DB-session adapter

Cleanup performed:
- added `backend/tests/integration/test_emr_ai_endpoint_contract.py` to
  protect:
  - list-body plus specialty query parsing on
    `POST /api/v1/emr/ai/suggestions/diagnosis`
  - embedded multi-body contract on `POST /api/v1/emr/ai/auto-fill`
  - EMR v2 doctor-context contract on `POST /api/v1/emr/ai/suggest`
- deleted detached `backend/app/services/emr_ai_api_service.py`
- deleted detached `backend/app/repositories/emr_ai_api_repository.py`

Effect:
- no mounted `/api/v1/emr/ai/*` route was removed
- the detached EMR AI duplicate pair is gone
- the protected EMR cleanup lane moved forward with proof-first coverage
  instead of silent deletion
