# Activation API Service Cleanup Status

Status: completed

What changed:
- deleted `backend/app/services/activation_api_service.py`
- deleted `backend/app/repositories/activation_api_repository.py`
- added activation endpoint contract tests
- repointed the boundary test to the live `activation_admin_service.py`

Validation:
- activation targeted tests pass
- OpenAPI contract tests pass
- full backend suite passes

Result:
- dead activation service/repository residue is reduced
- mounted activation route ownership and runtime behavior remain unchanged
