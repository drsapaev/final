# Salary Endpoint Cleanup

`backend/app/api/v1/endpoints/salary.py` was a dead endpoint artifact.

Verified facts:
- it defined `router = APIRouter(prefix="/salary", tags=["salary"])`
- `backend/app/api/v1/api.py` did not include `salary.router`
- `backend/openapi.json` contained no `/api/v1/salary/*` or
  `/api/v1/admin/salary/*` paths
- no live source imports of `backend/app/api/v1/endpoints/salary.py` were found
  in `backend/app` or `backend/tests`
- `docs/API_REFERENCE.md` still advertised a non-mounted salary API surface

Cleanup performed:
- removed `backend/app/api/v1/endpoints/salary.py`
- deleted the stale Salary Management section from `docs/API_REFERENCE.md`

Effect:
- no runtime route was removed, because the endpoint was never mounted
- salary domain/service/repository code remains untouched
- docs now stop claiming the non-existent salary API surface is available
