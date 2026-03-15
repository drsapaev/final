# AI Tracking Endpoint Cleanup

`backend/app/api/v1/endpoints/ai_tracking.py` was a detached legacy endpoint
artifact.

Verified facts:
- `backend/app/api/v1/api.py` did not include `ai_tracking.router`
- `backend/openapi.json` did not expose the file's `/api/v1/ai/models/*`,
  `/api/v1/ai/providers/stats`, or `/api/v1/ai/requests/recent` routes
- no live source imports of `backend/app/api/v1/endpoints/ai_tracking.py`
  were found in `backend/app` or `backend/tests`
- the supporting `backend/app/services/ai_tracking_api_service.py`,
  `backend/app/repositories/ai_tracking_api_repository.py`, and
  `backend/tests/unit/test_ai_tracking_api_service.py` remain in place and were
  not changed by this cleanup

Cleanup performed:
- removed `backend/app/api/v1/endpoints/ai_tracking.py`

Effect:
- no mounted runtime route was removed
- live AI service and repository code remain available for any future mounted
  owner
- one more dead AI endpoint artifact is gone
