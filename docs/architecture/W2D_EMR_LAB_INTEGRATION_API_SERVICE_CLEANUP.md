# EMR Lab Integration API Service Cleanup

`backend/app/services/emr_lab_integration_api_service.py` and
`backend/app/repositories/emr_lab_integration_api_repository.py` were handled
as a protected EMR-adjacent duplicate pair, not as a blind-delete candidate.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/emr_lab_integration.py` under
  `/api/v1/emr/lab`
- `backend/openapi.json` publishes the live `/api/v1/emr/lab/*` surface,
  including patient results, integrate, abnormal results, summary, doctor
  notify, statistics, and trends routes
- no live imports of the detached service or repository remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- diff vs the mounted owner was limited to typing/import drift only
- the detached repository was only a trivial unused DB-session adapter

Cleanup performed:
- added `backend/tests/integration/test_emr_lab_integration_endpoint_contract.py`
  to protect:
  - query parsing on `GET /api/v1/emr/lab/patients/{patient_id}/lab-results`
  - list-body contract on `POST /api/v1/emr/lab/emr/{emr_id}/integrate-lab-results`
  - notify parameter contract on
    `POST /api/v1/emr/lab/lab-results/{result_id}/notify-doctor`
- deleted detached `backend/app/services/emr_lab_integration_api_service.py`
- deleted detached
  `backend/app/repositories/emr_lab_integration_api_repository.py`

Effect:
- no mounted `/api/v1/emr/lab/*` route was removed
- the detached EMR lab-integration duplicate pair is gone
- the protected EMR cleanup lane moved forward with proof-first coverage
  instead of silent deletion
