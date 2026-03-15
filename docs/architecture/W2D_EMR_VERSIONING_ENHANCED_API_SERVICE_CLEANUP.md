# EMR Versioning Enhanced API Service Cleanup

`backend/app/services/emr_versioning_enhanced_api_service.py` and
`backend/app/repositories/emr_versioning_enhanced_api_repository.py` were
handled as a protected EMR-adjacent duplicate pair, not as a blind-delete
candidate.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/emr_versioning_enhanced.py` under
  `/api/v1/emr/versions`
- `backend/openapi.json` publishes the live `/api/v1/emr/versions/*` surface,
  including timeline, compare, restore, statistics, create, details, delete,
  and export routes
- no live imports of the detached service or repository remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- diff vs the mounted owner was limited to typing/import drift only
- the detached repository was only a trivial unused DB-session adapter

Cleanup performed:
- added
  `backend/tests/integration/test_emr_versioning_enhanced_endpoint_contract.py`
  to protect:
  - doctor-scoped timeline access and query contract
  - create-version body/query contract with previous-version handoff
  - admin-only delete behavior on `/api/v1/emr/versions/{emr_id}/versions/{version_id}`
- deleted detached
  `backend/app/services/emr_versioning_enhanced_api_service.py`
- deleted detached
  `backend/app/repositories/emr_versioning_enhanced_api_repository.py`

Effect:
- no mounted `/api/v1/emr/versions/*` route was removed
- the detached EMR versioning duplicate pair is gone
- the protected EMR cleanup lane moved forward with proof-first coverage
  instead of silent deletion
