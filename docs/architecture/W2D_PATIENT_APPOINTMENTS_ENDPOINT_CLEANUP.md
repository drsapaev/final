# Patient Appointments Endpoint Cleanup

`backend/app/api/v1/endpoints/patient_appointments.py` was a dead endpoint
artifact.

Verified facts:
- it defined `router = APIRouter(prefix="/patient", tags=["patient"])`
- `backend/app/api/v1/api.py` did not include `patient_appointments.router`
- `backend/openapi.json` already exposed patient appointment reads via the
  mounted `/api/v1/patients/{patient_id}/appointments` route from
  `patients.py`, not via `/api/v1/patient/*`
- no live source imports of `backend/app/api/v1/endpoints/patient_appointments.py`
  were found in `backend/app` or `backend/tests`
- `docs/TODO_REVIEW.md` still referenced TODOs in the removed endpoint file

Cleanup performed:
- removed `backend/app/api/v1/endpoints/patient_appointments.py`
- removed the stale Patient Appointments section from `docs/TODO_REVIEW.md`

Effect:
- no runtime route was removed, because the endpoint was never mounted
- patient appointment service/repository code remains untouched
- docs no longer describe TODOs in a dead endpoint artifact
