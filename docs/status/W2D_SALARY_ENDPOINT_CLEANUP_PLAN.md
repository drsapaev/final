# Salary Endpoint Cleanup Plan

Scope:
- delete dead endpoint artifact `backend/app/api/v1/endpoints/salary.py`
- correct stale API reference content that still advertised salary endpoints

Evidence:
- `backend/app/api/v1/api.py` does not mount `salary.router`
- `backend/openapi.json` contains no salary endpoint paths
- no confirmed frontend or backend runtime import of the endpoint module remains
- `docs/API_REFERENCE.md` still described a salary API surface that is not
  actually mounted

Why this is safe:
- the endpoint was not mounted, so deleting it cannot change runtime routing
- OpenAPI already excludes the salary routes, so docs should not advertise them

Out of scope:
- salary service/repository/domain refactors
- HR product decisions
- reintroducing or redesigning salary APIs
