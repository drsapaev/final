# W2D print_templates_api_service cleanup plan

Date: 2026-03-11
Mode: bounded cleanup

## Scope

Remove only:

- `backend/app/services/print_templates_api_service.py`

## Why this candidate is in scope

Current review confirms:

- mounted print-templates runtime already lives in
  `backend/app/api/v1/endpoints/print_templates.py`
- `backend/app/api/v1/api.py` includes the endpoint router, not this
  service-side mirror
- no live source imports of `print_templates_api_service.py` remain under
  `backend/app` or `backend/tests`

## What remains out of scope

- `backend/app/api/v1/endpoints/print_templates.py`
- print template CRUD behavior
- print config CRUD logic
