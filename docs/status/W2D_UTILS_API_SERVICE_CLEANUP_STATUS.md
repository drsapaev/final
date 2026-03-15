# Utils API Service Cleanup Status

Status: completed

What changed:
- deleted `backend/app/services/utils_api_service.py`

Validation:
- OpenAPI contract tests remain green
- full backend test suite remains green

Result:
- dead utils router-style service residue is reduced
- mounted utils route ownership remains unchanged
