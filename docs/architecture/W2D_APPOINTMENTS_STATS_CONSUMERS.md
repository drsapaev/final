# W2D appointments.stats consumers

## In-repo consumer audit

### Confirmed direct runtime consumers

None confirmed.

## Findings

| Finding | File | Type | Live/runtime | Confidence |
| --- | --- | --- | --- | --- |
| Endpoint constant exists | [endpoints.js](C:/final/frontend/src/api/endpoints.js) | Indirect frontend API definition | No confirmed call site | High |
| Generic service wrapper exists | [services.js](C:/final/frontend/src/api/services.js) | Indirect frontend API wrapper | No confirmed call site | High |
| Mounted route exists in backend | [appointments.py](C:/final/backend/app/api/v1/endpoints/appointments.py) | Route owner | Yes | High |
| OpenAPI exposure exists | [openapi.json](C:/final/backend/openapi.json) | Public contract exposure | Yes | High |

## What was not found

No confirmed call sites were found in:

- `frontend/src/pages/*`
- `frontend/src/hooks/*`
- backend internal callers
- repo-local scripts
- characterization or integration tests

## Meaning of the result

Current evidence supports this position:

- the route is still mounted and externally callable
- the repo still exposes a frontend wrapper for it
- but there is no confirmed in-repo live runtime consumer

That makes `appointments.stats()` weaker than `queues.stats()` and much weaker
than the board-display path in terms of current product/runtime dependence.
