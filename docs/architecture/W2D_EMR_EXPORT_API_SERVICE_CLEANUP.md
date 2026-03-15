# EMR Export API Service Cleanup

`backend/app/services/emr_export_api_service.py` and
`backend/app/repositories/emr_export_api_repository.py` were handled as a
protected EMR-adjacent duplicate pair, not as a blind-delete candidate.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/emr_export.py` under `/api/v1/emr/export`
- `backend/openapi.json` publishes the live `/api/v1/emr/export/*` surface,
  including format discovery, export, import, validation, estimate-size,
  templates, and statistics routes
- no live imports of the detached service or repository remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- diff vs the mounted owner was limited to typing/import drift only
- the detached repository was only a trivial unused DB-session adapter

Cleanup performed:
- added `backend/tests/integration/test_emr_export_endpoint_contract.py` to
  protect:
  - authenticated access to `GET /api/v1/emr/export/formats`
  - the CSV download contract for `POST /api/v1/emr/export/export/csv`
  - the query/body contract for `POST /api/v1/emr/export/validate`
- deleted detached `backend/app/services/emr_export_api_service.py`
- deleted detached `backend/app/repositories/emr_export_api_repository.py`

Effect:
- no mounted `/api/v1/emr/export/*` route was removed
- the detached EMR export duplicate pair is gone
- the protected EMR cleanup lane moved forward with proof-first coverage
  instead of silent deletion
