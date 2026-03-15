# Section Templates API Service Cleanup

`backend/app/services/section_templates_api_service.py` and
`backend/app/repositories/section_templates_api_repository.py` were handled as
a protected EMR-adjacent duplicate pair, not as a blind-delete candidate.

Verified facts:
- `backend/app/api/v1/api.py` mounts
  `backend/app/api/v1/endpoints/section_templates.py`
- `backend/openapi.json` publishes the live `/api/v1/section-templates/*`
  surface:
  - `/api/v1/section-templates/{section_type}`
  - `/api/v1/section-templates/{section_type}/{template_id}/pin`
  - `/api/v1/section-templates/{section_type}/{template_id}`
- no live imports of the detached service or repository remained in
  `backend/app`, `backend/tests`, `docs`, or `frontend`
- diff vs the mounted owner was limited to typing/import drift only
- the detached repository was only a trivial unused DB-session adapter

Cleanup performed:
- added `backend/tests/integration/test_section_templates_endpoint_contract.py`
  to protect:
  - mounted invalid `section_type` validation
  - the doctor-scoped query contract for
    `GET /api/v1/section-templates/{section_type}`
  - the live write contract for
    `PUT /api/v1/section-templates/{section_type}/{template_id}`
- deleted detached `backend/app/services/section_templates_api_service.py`
- deleted detached
  `backend/app/repositories/section_templates_api_repository.py`

Effect:
- no mounted `/api/v1/section-templates/*` route was removed
- the detached EMR duplicate pair is gone
- the protected EMR cleanup lane moved forward with proof-first coverage
  instead of silent deletion
