# FCM Notifications API Service Cleanup Status

Status: completed

What changed:
- deleted `backend/app/services/fcm_notifications_api_service.py`

Validation:
- OpenAPI contract tests remain green
- full backend test suite remains green

Result:
- dead FCM router-style service residue is reduced
- mounted FCM route ownership remains unchanged
