# Email SMS Enhanced API Service Cleanup Plan

Scope:
- delete dead router-style residue
  `backend/app/services/email_sms_enhanced_api_service.py`

Evidence:
- `backend/app/api/v1/api.py` mounts the endpoint owner
  `email_sms_enhanced.py`
- `backend/openapi.json` contains the live `/api/v1/email-sms/*` routes served
  by that owner
- no confirmed backend, test, docs, or frontend import of
  `email_sms_enhanced_api_service.py` remains
- the file was not the mounted owner and represented an older detached router
  implementation for the same enhanced email/SMS surface

Why this is safe:
- the file was not a mounted owner
- the live enhanced email/SMS endpoints remain in `email_sms_enhanced.py`
- removing the residue does not change the active enhanced email/SMS runtime

Out of scope:
- changing email or SMS delivery behavior
- changing SMS provider behavior
- removing the mounted `email_sms_enhanced.py` owner
