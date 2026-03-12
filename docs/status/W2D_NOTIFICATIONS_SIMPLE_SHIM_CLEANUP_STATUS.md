# Notifications Simple Shim Cleanup Status

Status: completed

What changed:
- deleted `backend/app/api/v1/endpoints/notifications_simple.py`
- deleted `backend/app/services/notifications_simple_api_service.py`

Validation:
- OpenAPI contract tests remain green
- full backend test suite remains green

Result:
- one more detached endpoint/service shim pair is gone
- mounted notifications runtime ownership remains unchanged
