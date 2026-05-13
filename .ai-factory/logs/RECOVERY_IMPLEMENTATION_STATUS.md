# Recovery Implementation Status

Started: 2026-05-09
Active plan: `.ai-factory/PLAN.md`
Workflow: `/aif-plan` -> `/aif-improve @.ai-factory/PLAN.md` -> `/aif-implement @.ai-factory/PLAN.md` -> `/aif-verify --strict`

## Current Status

- Current task: Task 26 - remaining backend raw print/public error leakage
- Last completed slice: Task 26 queue cabinet management endpoint leakage cleanup
- Next task: continue Task 26 with the next one-file mounted runtime leakage slice
- Blocker state: none for the current slice; Task 26 remains open as a multi-slice audit
- Runtime code changed: yes
- Secrets inspected or printed: no

## Task 26 Slice Queue Limits Evidence

Post-merge recovery note:

- Runtime hardening for `backend/app/api/v1/endpoints/queue_limits.py` is already present in `main` via PR #676 commit `a5ad8e390bf8472956be5985bf338530f705a4bd`.
- PR #678 carried the same queue-limits hardening plus this recovery evidence, but it was closed unmerged after `main` advanced and made the code portion redundant.
- This section records the verified Task 26 queue-limits evidence without reopening the runtime code slice.

Execution mode:

- selected mode: `gate_known_root_cause`, continued as narrow override
- reason: mounted queue limits endpoint leaked raw exception text through public HTTP 500 details
- risky domain: yes, queue limits and staff workflow
- root cause known: yes
- command: `python scripts\agent_gate.py "Task 26 sanitize mounted queue limits endpoint raw public exception leakage without changing queue limit route contracts roles domain behavior or success payloads" --known-root-cause "backend/app/api/v1/endpoints/queue_limits.py"`

Gate result:

- The gate returned frontend routing files alongside the confirmed backend root-cause file.
- Per `AGENTS.md`, execution stayed narrowed to `backend/app/api/v1/endpoints/queue_limits.py` plus recovery evidence only.

Changed behavior:

- Replaced raw public HTTP 500 details that included exception text with generic `Internal server error`.
- Added structured endpoint logging with action name plus exception class only.
- Preserved route paths, role dependencies, domain 404 behavior, success payload shapes, and service/repository behavior.
- Added explicit `HTTPException` passthrough so endpoint-local HTTP errors are not masked as generic 500.

Validation run:

- `python -m py_compile backend\app\api\v1\endpoints\queue_limits.py`
  - result: passed
- `python -m ruff check backend\app\api\v1\endpoints\queue_limits.py`
  - result: passed
- `python -m black --check backend\app\api\v1\endpoints\queue_limits.py`
  - result: passed
- static leakage scan for raw exception details/logging in the file
  - result: no matches
- direct endpoint smoke with marker exception
  - result: passed; HTTP 500 returned `Internal server error`, marker text did not leak to response or logs, and `DOCTOR_NOT_FOUND` stayed HTTP 404
- `python -m pytest backend\tests\architecture\test_w2c_queue_boundaries.py backend\tests\unit\test_queue_limits_api_service.py backend\tests\unit\test_queue_domain_service.py backend\tests\unit\test_service_repository_boundary.py -q --tb=short --disable-warnings`
  - result: 69 passed, 1 warning
- `npm.cmd --prefix frontend run build`
  - result: passed from `C:\final`; warnings were existing Vite dynamic/static import and large chunk warnings
- GitHub PR #676 CI
  - result: passed; runtime code is merged to `main`

Scope note:

- Task 26 remains open. This slice only records the already-merged queue limits endpoint hardening and does not claim all backend runtime leakage is gone.

## Task 26 Slice Wait-Time Analytics Evidence

Post-merge recovery note:

- PR #672 merged commit `a5efc515670478947eb17167137d3214f8c77908`.
- Runtime file changed: `backend/app/api/v1/endpoints/wait_time_analytics.py`.
- The intended recovery-log note was not included in PR #672, so this section records the already-merged evidence without reopening that code slice.

Execution mode:

- selected mode: `gate_known_root_cause`, continued as narrow override
- reason: mounted analytics endpoint leaked raw exception text through public HTTP 500 details and f-string exception logs
- risky domain: yes
- root cause known: yes
- command: `python scripts\agent_gate.py "Task 26 sanitize mounted wait_time_analytics endpoint raw public exception leakage and f-string exception logging without changing analytics route contracts auth guards or success payloads" --known-root-cause "backend/app/api/v1/endpoints/wait_time_analytics.py"`

Validation run:

- `python -m py_compile backend\app\api\v1\endpoints\wait_time_analytics.py`
  - result: passed
- `python -m ruff check backend\app\api\v1\endpoints\wait_time_analytics.py`
  - result: passed
- `python -m black --check backend\app\api\v1\endpoints\wait_time_analytics.py`
  - result: passed
- static leakage scan for raw exception details/logging in the file
  - result: no matches
- direct async endpoint smoke with marker exception
  - result: passed; HTTP 500 returned `Internal server error`, marker text did not leak to response or logs, and invalid date remained HTTP 400
- `python -m pytest backend\tests\test_security_middleware.py -q --tb=short --disable-warnings`
  - result: 24 passed, 1 warning
- `npm.cmd --prefix frontend run build`
  - result: passed with existing Vite chunk/import warnings
- GitHub PR #672 CI
  - result: passed; PR merged and remote branch pruned

Scope note:

- Task 26 remains open. This slice only hardened the mounted wait-time analytics endpoint and did not claim repo-wide leak cleanup.

## Task 26 Slice Queue Cabinet Management Evidence

Execution mode:

- selected mode: `gate_known_root_cause`, continued as narrow override
- reason: mounted queue cabinet endpoint leaked raw exception text through public HTTP 500 details and f-string exception logs
- risky domain: yes, queue/cabinet routing and staff workflow
- root cause known: yes
- command: `python scripts\agent_gate.py "Task 26 sanitize mounted queue cabinet management endpoint raw public exception leakage and f-string exception logging without changing queue cabinet route contracts roles domain errors or success payloads" --known-root-cause "backend/app/api/v1/endpoints/queue_cabinet_management.py"`

Gate result:

- The gate included frontend routing files due routing ownership, even with the confirmed backend root-cause file.
- Per `AGENTS.md`, execution continued as a narrow override limited to `backend/app/api/v1/endpoints/queue_cabinet_management.py` plus this recovery log.

Changed behavior:

- Replaced raw public HTTP 500 details that included exception text with generic `Internal server error`.
- Replaced f-string exception logging with structured action name plus exception class only.
- Preserved route paths, role dependencies, domain-error passthrough, success payload shapes, and service/repository behavior.
- Added explicit `HTTPException` passthrough so endpoint-local validation such as bad date keeps its intended 400 response instead of being masked as generic 500.

Validation run:

- `python -m py_compile backend\app\api\v1\endpoints\queue_cabinet_management.py`
  - result: passed
- `python -m ruff check backend\app\api\v1\endpoints\queue_cabinet_management.py`
  - result: passed
- `python -m black --check backend\app\api\v1\endpoints\queue_cabinet_management.py`
  - result: passed
- static leakage scan for raw exception details/logging in the file
  - result: no matches
- direct endpoint smoke with marker exception
  - result: passed; HTTP 500 returned `Internal server error`, marker text did not leak to response or logs, and bad-date remained HTTP 400
- `python -m pytest backend\tests\architecture\test_w2c_queue_boundaries.py backend\tests\unit\test_queue_cabinet_management_api_service.py backend\tests\integration\test_admin_linkage_cleanup.py -q --tb=short --disable-warnings`
  - result: 15 passed, 1 warning
- `npm.cmd --prefix frontend run build`
  - result: passed with existing Vite chunk/import warnings

Scope note:

- Task 26 remains open. This slice only hardens the mounted queue cabinet management endpoint and does not claim all backend runtime leakage is gone.

## Task 1 Evidence

Commands and inspections used:

- `git status --short`
- `.ai-factory/PLAN.md` existence/content check
- `.ai-factory/skill-context/aif-improve/SKILL.md`
- `.ai-factory/skill-context/aif-implement/SKILL.md`
- `.ai-factory/RULES.md`
- backend/frontend/test/workflow file counts
- backend endpoint inventory
- frontend route count from `frontend/src/routing/routeRegistry.js`
- docs/runbooks inventory

Canonical anchors confirmed:

- Repo operating rules: `AGENTS.md`
- Project SSOT: `.ai-factory/DESCRIPTION.md`
- Architecture SSOT: `.ai-factory/ARCHITECTURE.md`
- Active AIF plan: `.ai-factory/PLAN.md`
- Backend app entrypoint: `backend/app/main.py`
- Backend API router: `backend/app/api/v1/api.py`
- Backend endpoints: `backend/app/api/v1/endpoints`
- Backend migrations: `backend/alembic/versions`
- Backend tests: `backend/tests`
- Frontend app entrypoint: `frontend/src/App.jsx`
- Frontend route SSOT: `frontend/src/routing/routeRegistry.js`
- Frontend route selectors/guards: `frontend/src/routing/routeSelectors.js`, `frontend/src/routing/routeGuards.jsx`
- Frontend API clients: `frontend/src/api`
- Frontend tests: `frontend/src/**/__tests__`
- CI workflows: `.github/workflows`
- Operator/runbook docs: `docs/runbooks`

Measured surface:

- Backend app files: 2276
- Frontend source files: 775
- Backend endpoint files: 144
- Alembic revision files: 22
- Backend test files: 207
- Frontend test/spec files: 61
- GitHub workflow files: 9
- Frontend route registry entries: 128

Initial observations:

- The previous `.ai-factory/PLAN.md` was a historical completed fast-plan bundle, so it was replaced with the new active recovery plan.
- The repo contains many historical reports and completion claims; they remain context only, not proof.
- The route registry and route selector files show visible mojibake in labels/sections, which is a likely early user-visible P1/P2 cleanup target.
- The backend API router includes several duplicate/legacy/auth/payment/AI/Telegram surfaces that need canonical-vs-legacy classification before fixes.
- Existing tests already cover useful slices for routing, queue, payments, RBAC, patient documents, registrar services, and frontend API runtime behavior.

## Task 2 Evidence

Commands and inspections used:

- `git ls-files` filtered for env/secret/token/auth-like tracked files
- `frontend/src/routing/routeRegistry.js` scan for internal-demo, legacy redirects, and visible encoding artifacts
- `backend/app/api/v1/api.py` scan for auth/payment/queue/file/AI/Telegram mounted surfaces
- `backend/alembic/versions` revision inventory
- `frontend/src/api/*.js` scan for hardcoded origins and fetch surfaces
- `backend/app/**/*.py` scan for auth/security/config keywords

Backlog recorded in `.ai-factory/PLAN.md`:

- P0 until proven safe: tracked `temp_token.json` and `test_auth.json`
- P1: duplicate `/auth` surfaces and OAuth token URL drift risk
- P1: published file upload/test/simple routes need canonical/security classification
- P1: duplicate payment webhook surfaces need idempotency/signature classification
- P1/P2: mixed-language and possible encoding-artifact UX in route/UI metadata
- P1: AI/Telegram surfaces need human-approval and external-service safety audit
- P2: internal demo/test routes need production visibility confirmation
- P2: historical reports/completed plans can mislead agents/operators
- P2: development `.secret_key` behavior needs secret-source policy verification
- P3: landing polish after operational recovery

## Task 3 Evidence

Commands and inspections used:

- frontend health check: `http://localhost:5173` returned `200`
- backend health check: `http://localhost:18000/api/v1/health` returned `200`
- route registry inventory via Node import
- static scan of `frontend/src/routing/routeRegistry.js`, `routeSelectors.js`, `routeGuards.jsx`, and `App.jsx`
- component scan for demo/test/showcase candidates
- route contract verification through `npm.cmd`

Route inventory:

- canonical routes: 72
- route groups: public 14, onboarding 1, admin 35, clinical 16, internal-demo 6
- nav routes: 37
- compatibility redirects: 33
- internal-demo routes: 6

User-visible backlog recorded in `.ai-factory/PLAN.md`:

- UVD-1: internal demo/test routes have legacy direct aliases
- UVD-2: mixed-language role navigation
- UVD-3: AI Assistant appears in clinical navigation before safety posture is proven
- UVD-4: large compatibility redirect surface
- UVD-5: public callback/queue/display routes need user-state smoke
- UVD-6: browser smoke is available but role credentials must be resolved safely
- UVD-7: demo/test/showcase components exist in source

Validation run:

- `npm --prefix frontend ...` was blocked by PowerShell execution policy for `npm.ps1`
- rerun with `npm.cmd --prefix frontend run test:run -- src/routing/__tests__/routeContract.test.js src/routing/__tests__/routeOwnershipEnforcement.test.js`
- result: 2 test files passed, 14 tests passed

Correction:

- Earlier terminal output made route text look like mojibake, but current source reads valid Cyrillic in `routeRegistry.js`, `routeSelectors.js`, and `App.jsx`.
- The confirmed visible text issue is mixed-language/inconsistent UX, not proven source-file encoding corruption.

## Next Action

Proceed through `/aif-implement @.ai-factory/PLAN.md` to Task 6:

- run `cd C:\final\ai\langgraph && python scripts\agent_gate.py "audit auth router precedence and bypass surfaces" --known-root-cause "backend/app/api/v1/api.py"`
- build a no-secret auth endpoint map before editing
- do not proceed to UX friction, VPS promotion, or commit until P0-A through P0-E are audited and fixed or downgraded by evidence
- current blocker: restore/locate the required gate script or provide an approved replacement command; do not edit auth/payment/upload code before this is resolved

## Task 4 Evidence

Changed files:

- `frontend/src/routing/routeRegistry.js`
- `frontend/src/routing/routeGuards.jsx`

Changed behavior:

- Registrar, doctor, patient, cashier, cardiology, dermatology, dentistry, and lab role sidebar labels now use a consistent Russian clinic UI style.
- Route guard loading text is now `Загрузка...` instead of mojibake.
- System 401/403/404 route pages are now localized:
  - `Требуется вход`
  - `Доступ запрещён`
  - `Страница не найдена`

Scope notes:

- Route paths were not changed.
- Route roles were not changed.
- Route auth modes were not changed.
- Compatibility redirects were not changed.
- API calls were not changed.

Validation run:

- `npm.cmd --prefix frontend run test:run -- src/routing/__tests__/routeContract.test.js src/routing/__tests__/routeOwnershipEnforcement.test.js`
  - result: 2 test files passed, 14 tests passed
- `npm.cmd --prefix frontend run build`
  - result: passed
  - warnings: existing Vite warnings about dynamic/static `errorHandler.js` import and large chunks
- Node Playwright smoke against running frontend `http://localhost:5173`
  - `/forbidden`: PASS, rendered `Доступ запрещён`
  - `/not-found`: PASS, rendered `Страница не найдена`

Implementation note:

- A point patch could not match one mojibake line in `routeGuards.jsx` because of actual encoded codepoints in the file, so the small route-guard file was replaced as a whole while preserving behavior and exports.

## Task 5 Evidence

Execution mode:

- selected mode: `direct_execute`
- reason: confirmed route ownership, narrow frontend-only selector/test slice, no route path or role contract change
- risky domain: no for this slice; internal/demo route visibility only
- root cause known: yes, `frontend/src/routing/routeSelectors.js`
- scope expectation: narrow
- command: not needed for direct execute

Initial boundaries:

- canonical anchor: `frontend/src/routing/routeRegistry.js`
- first-touch files: `frontend/src/routing/routeSelectors.js`, `frontend/src/routing/__tests__/routeContract.test.js`
- validation target: route contract tests, frontend build, browser smoke for a legacy demo alias
- stop condition watched first: any route path, role, auth mode, or compatibility redirect behavior change outside internal-demo gating

Changed files:

- `frontend/src/routing/routeSelectors.js`
- `frontend/src/routing/__tests__/routeContract.test.js`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Changed behavior:

- Internal demo access is no longer enabled automatically by Vite dev mode.
- Internal demo routes now require explicit `VITE_ENABLE_INTERNAL_DEMO=1`.
- Added a route contract test proving demo routes are disabled by default and only accessible when explicitly enabled.

Route disposition:

- `/internal-demo/payment-test`: internal only, hidden unless `VITE_ENABLE_INTERNAL_DEMO=1`
- `/internal-demo/css-test`: internal only, hidden unless `VITE_ENABLE_INTERNAL_DEMO=1`
- `/internal-demo/buttons`: internal only, hidden unless `VITE_ENABLE_INTERNAL_DEMO=1`
- `/internal-demo/macos-demo`: internal only, hidden unless `VITE_ENABLE_INTERNAL_DEMO=1`
- `/internal-demo/medilab-demo`: internal only, hidden unless `VITE_ENABLE_INTERNAL_DEMO=1`
- `/internal-demo/integration-demo`: internal only, hidden unless `VITE_ENABLE_INTERNAL_DEMO=1`
- `/payment/test`, `/css-test`, `/buttons`, `/macos-demo`, `/medilab-demo`, `/integration-demo`: compatibility aliases still resolve to canonical internal-demo routes, but those canonical targets are denied by default and render `/not-found`

Scope notes:

- Route paths were not changed.
- Route roles were not changed.
- Route auth modes were not changed.
- Compatibility redirects were not changed.
- Demo components were not deleted.
- API calls were not changed.

Validation run:

- `npm.cmd --prefix frontend run test:run -- src/routing/__tests__/routeContract.test.js src/routing/__tests__/routeOwnershipEnforcement.test.js`
  - result: 2 test files passed, 15 tests passed
- `npm.cmd --prefix frontend run build`
  - result: passed
  - warnings: existing Vite warnings about dynamic/static `errorHandler.js` import and large chunks
- Node Playwright smoke against running frontend `http://localhost:5173/payment/test`
  - result: PASS
  - final URL: `http://localhost:5173/not-found`
  - rendered expected not-found page

## Principal Review Reconciliation Evidence

Trigger:

- User provided an independent principal review and required all implementation to proceed through `/aif-implement @.ai-factory/PLAN.md`, not ad hoc coding.

Skills/context loaded:

- `aif-improve`
- `aif-implement`
- `.ai-factory/skill-context/common/SKILL.md`
- `.ai-factory/skill-context/aif-improve/SKILL.md`
- `.ai-factory/skill-context/aif-implement/SKILL.md`
- `.ai-factory/DESCRIPTION.md`
- `.ai-factory/ARCHITECTURE.md`
- `.ai-factory/RULES.md`

Verified review findings without printing secrets:

- `frontend/src/components/auth/LoginFormStyled.jsx` calls `buildApiUrl('/auth/minimal-login')`.
- `backend/app/api/v1/endpoints/minimal_auth.py` exposes `/minimal-login` and returns an `access_token` response model.
- `backend/app/api/deps.py` sets `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/minimal-login")`.
- `backend/tests/test_2fa_enforcement.py` targets `/api/v1/authentication/login`, not the frontend minimal-login path.
- `backend/app/api/v1/endpoints/payment_webhook.py` catches webhook exceptions and returns a normal JSON body with `ok: false` instead of an HTTP error.
- `backend/app/api/v1/endpoints/file_upload_simple.py` uses user-provided filenames, writes to relative `uploads/`, and logs upload/user details via `print`.
- `backend/app/api/v1/api.py` mounts duplicate/overlapping auth, payment webhook, queue, Telegram, AI, file upload, and EMR v2 route surfaces.
- `git ls-files` confirms `temp_token.json` and `test_auth.json` are tracked; their contents were not printed in this log.
- `frontend/.env.example` and `README.md` do not currently mention `VITE_ENABLE_INTERNAL_DEMO`.

Plan changes applied:

- Added `Principal Review Override (2026-05-09)` to `.ai-factory/PLAN.md`.
- Elevated auth 2FA bypass, tracked credential artifact, payment webhook silent loss, simple file upload, and OAuth tokenUrl issues to P0.
- Blocked UX friction, landing polish, VPS promotion, and commit until P0-A through P0-E are audited and closed or downgraded with evidence.
- Replaced the old pending UX Task 6 with a gated auth router precedence and 2FA-bypass audit.
- Added STOP & SECURE tasks for auth canonicalization, fallback auth gating, 2FA regression coverage, credential artifact triage, payment webhook behavior, and simple upload hardening/disablement.
- Deferred UX friction to Task 19 and added Task 20 for the `VITE_ENABLE_INTERNAL_DEMO` DX documentation gap.

Next required AIF command:

- `/aif-implement @.ai-factory/PLAN.md`

## Task 6 Gate Attempt

Execution mode:

- selected mode: `gate_known_root_cause`
- reason: auth/2FA is production-sensitive and canonical-vs-fallback ownership is ambiguous
- risky domain: yes
- root cause known: yes, `backend/app/api/v1/api.py`
- scope expectation: multi-file audit, no edits before gate handoff
- command attempted: `python scripts\agent_gate.py "audit auth router precedence and bypass surfaces" --known-root-cause "backend/app/api/v1/api.py"` from `C:\final\ai\langgraph`

Result:

- blocked before implementation
- Python reported `scripts\agent_gate.py` does not exist
- `C:\final\ai\langgraph\scripts` currently contains only `__pycache__`
- recursive search under `C:\final` found no `agent_gate.py`

Stop condition hit:

- Required gate cannot run, so Task 6 cannot proceed safely.

## Task 6 Completion Evidence

Prerequisite tooling repair:

- Restored `ai/langgraph/scripts/agent_gate.py` from git history commit `75745254` because the required gate script was absent from the working tree and only `__pycache__` remained.
- Verified restored gate with `python -m py_compile ai\langgraph\scripts\agent_gate.py`.

Gate rerun:

- command: `python scripts\agent_gate.py "audit auth router precedence and bypass surfaces" --known-root-cause "backend/app/api/v1/api.py"` from `C:\final\ai\langgraph`
- result: `narrow override`
- `gate_misroute`: yes
- `override_used`: yes
- known root cause: `backend/app/api/v1/api.py`
- issue recorded in `ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md` as Task 84

Auth route map:

- `POST /api/v1/auth/login`
  - owner: `backend/app/api/v1/endpoints/auth.py`
  - service: `backend/app/services/auth_api_service.py`
  - token behavior: returns `access_token`
  - 2FA behavior: no 2FA gate found in this path
  - status: legacy/unsafe until proven otherwise
- `POST /api/v1/auth/json-login`
  - owner: `backend/app/api/v1/endpoints/auth.py`
  - service: `backend/app/services/auth_api_service.py`
  - token behavior: returns `access_token`
  - 2FA behavior: no 2FA gate found in this path
  - status: legacy/unsafe until proven otherwise
- `POST /api/v1/auth/simple-login`
  - owner: `backend/app/api/v1/endpoints/simple_auth.py`
  - service: `backend/app/services/auth_fallback_service.py`
  - token behavior: returns `access_token`
  - 2FA behavior: no 2FA gate found in this path
  - status: fallback/unsafe until gated
- `POST /api/v1/auth/minimal-login`
  - owner: `backend/app/api/v1/endpoints/minimal_auth.py`
  - service: `backend/app/services/auth_fallback_service.py`
  - token behavior: returns `access_token`
  - 2FA behavior: no 2FA gate found in this path
  - status: fallback/unsafe until gated
- `POST /api/v1/authentication/login`
  - owner: `backend/app/api/v1/endpoints/authentication.py`
  - service: `backend/app/services/authentication_service.py`
  - token behavior: returns no `access_token` when 2FA is required; returns `pending_2fa_token` instead
  - 2FA behavior: enforces critical-role 2FA setup and pending 2FA verification path
  - status: canonical 2FA-aware candidate
- `POST /api/v1/2fa/verify`
  - owner: `backend/app/api/v1/endpoints/two_factor_auth.py`
  - token behavior: returns access/refresh tokens after pending-token and OTP verification
  - status: canonical second step

Frontend/API documentation findings:

- `frontend/src/components/auth/LoginFormStyled.jsx` calls `buildApiUrl('/auth/minimal-login')`; this is the current user-facing login path and is unsafe because it uses fallback auth.
- `backend/app/api/deps.py` sets `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/minimal-login")`; API docs normalize the unsafe fallback path.
- `backend/tests/test_2fa_enforcement.py` covers `/api/v1/authentication/login`, not the current frontend `/auth/minimal-login` path.
- `frontend/src/components/auth/LoginFormStyled.jsx` logs login credentials/form data to the frontend logger; this should be removed during Task 7.

Validation run:

- `python -m py_compile backend\app\api\v1\api.py`
  - result: passed

Scope notes:

- No runtime auth code was edited in Task 6.
- The only tooling code restored was the missing required gate script.
- No passwords, tokens, or patient data were printed in this log.

## Task 7 Evidence

Execution mode:

- selected mode: `gate_known_root_cause`
- reason: frontend login path change affects staff access and 2FA behavior
- risky domain: yes
- root cause known: yes, `frontend/src/components/auth/LoginFormStyled.jsx`
- scope expectation: single-file frontend slice
- gate command: `python scripts\agent_gate.py "change frontend login form to canonical 2FA-aware endpoint frontend/src/components/auth/LoginFormStyled.jsx" --known-root-cause "frontend/src/components/auth/LoginFormStyled.jsx"`
- gate result: `narrow override`
- `gate_misroute`: no
- `override_used`: yes

Changed files:

- `frontend/src/components/auth/LoginFormStyled.jsx`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Changed behavior:

- User-facing login now posts to `buildApiUrl('/authentication/login')` instead of the fallback `/auth/minimal-login`.
- 2FA pending responses now preserve the backend-provided `two_factor_method`, falling back to `totp`.
- Login submit/error logs no longer include the raw username, password, credentials object, or full form data.

Scope notes:

- No backend auth code changed in this task.
- The existing current-origin API resolution through `buildApiUrl` was preserved.
- Password is still sent in the request body as required for login, but is no longer logged.

Validation run:

- Static check on `frontend/src/components/auth/LoginFormStyled.jsx`
  - `/auth/minimal-login`: not present in the file
  - `/authentication/login`: present in the login request
  - no logger entry for `username: formData.username`
- `npm.cmd --prefix frontend run test:run -- src/pages/__tests__/Login.accessibility.test.jsx src/components/auth/__tests__/loginErrorUtils.test.js`
  - result: 2 test files passed, 5 tests passed
  - warning: existing React Router future-flag warning
- `npm.cmd --prefix frontend run build`
  - result: passed
  - warnings: existing Vite dynamic/static `errorHandler.js` warning and large chunks

## Task 8 Evidence

Execution mode:

- selected mode: `gate_known_root_cause`
- reason: backend auth mount and OpenAPI tokenUrl changes are production-sensitive
- risky domain: yes
- root cause known: yes
- first gate root: `backend/app/api/v1/api.py`
- second gate root: `backend/app/api/v1/endpoints/auth.py`, after Task 8 inspection showed legacy `/auth/login` and `/auth/json-login` also bypass 2FA
- gate result: `gate ok`
- `gate_misroute`: no
- `override_used`: no

Changed files:

- `backend/app/core/config.py`
- `backend/app/api/deps.py`
- `backend/app/api/v1/api.py`
- `backend/app/api/v1/endpoints/auth.py`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Changed behavior:

- Added `ENABLE_FALLBACK_AUTH` setting, default `False`.
- `simple_auth.router` and `minimal_auth.router` mount only when `ENABLE_FALLBACK_AUTH` is explicitly enabled.
- `/api/v1/auth/login` and `/api/v1/auth/json-login` now return 404 by default unless fallback auth is explicitly enabled.
- `/api/v1/auth/me` and `/api/v1/auth/csrf-token` remain mounted through `auth.router` for existing frontend profile/CSRF helpers.
- `OAuth2PasswordBearer.tokenUrl` now points to `/api/v1/authentication/login`.

Scope notes:

- No DB schema changed.
- No auth token creation logic was modified.
- The fallback auth implementation files remain present for explicit break-glass/dev use, but are not mounted/enabled by default.
- Existing backend tests still contain many `/api/v1/auth/minimal-login` references; Task 9 must replace false-green coverage with canonical/fallback regression coverage.

Validation run:

- `python -m py_compile backend\app\api\v1\api.py backend\app\api\v1\endpoints\auth.py backend\app\api\v1\endpoints\minimal_auth.py backend\app\api\v1\endpoints\simple_auth.py backend\app\api\deps.py backend\app\core\config.py`
  - result: passed
- `pytest backend\tests\test_2fa_enforcement.py -q`
  - result: 5 passed
- Inline TestClient fallback-auth smoke
  - `/api/v1/auth/minimal-login`: 404
  - `/api/v1/auth/simple-login`: 404
  - `/api/v1/auth/json-login`: 404
  - `/api/v1/auth/login`: 404

## Task 9 Evidence

Execution mode:

- selected mode: `gate_known_root_cause`
- reason: auth regression coverage protects production-sensitive 2FA behavior
- risky domain: yes
- root cause known: yes, `backend/tests/test_2fa_enforcement.py`
- gate command: `python scripts\agent_gate.py "add 2FA regression coverage for canonical and fallback login paths backend/tests/test_2fa_enforcement.py" --known-root-cause "backend/tests/test_2fa_enforcement.py"`
- gate result: `gate ok`
- `gate_misroute`: no
- `override_used`: no

Changed files:

- `backend/tests/test_2fa_enforcement.py`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Changed behavior:

- Added regression coverage proving fallback login paths are disabled by default and do not return `access_token`.
- Added regression coverage proving canonical `/api/v1/authentication/login` returns `pending_2fa_token` but no access/refresh token before OTP.

Validation run:

- `python -m py_compile backend\tests\test_2fa_enforcement.py`
  - result: passed
- `pytest backend\tests\test_2fa_enforcement.py -q`
  - result: 7 passed
  - warning: existing pytest warning

## Task 10 Evidence

Execution mode:

- selected mode: `direct_execute`
- reason: narrow tracked-file artifact cleanup with no runtime auth or database mutation
- risky domain: yes
- root cause known: yes, `temp_token.json` and `test_auth.json`
- scope expectation: narrow
- command: not needed for direct execute

Initial boundaries:

- canonical anchor: `git ls-files temp_token.json test_auth.json`
- first-touch files: `temp_token.json`, `test_auth.json`, `.ai-factory/PLAN.md`, `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`
- validation target: files absent from working tree and git diff shows deletion only
- stop condition watched first: local DB shows the referenced account exists or rotation cannot be documented

Classification:

- `temp_token.json`
  - tracked by git before deletion: yes
  - JSON parsed: yes
  - sensitive-shaped keys: no
  - disposition: tracked trash, deleted
- `test_auth.json`
  - tracked by git before deletion: yes
  - JSON parsed: yes
  - sensitive-shaped keys: yes
  - disposition: credential-shaped artifact, deleted from working tree

Rotation/local account check:

- Local database check completed without printing credential values.
- Referenced account exists in accessible local DB: no.
- Non-local/staging/production environments were not accessible in this session; if that account exists elsewhere, rotate or delete it before release.
- Git history may still contain the deleted artifact until history rewrite is deliberately performed; this task only removes it from the current tree.

Validation run:

- `Test-Path temp_token.json; Test-Path test_auth.json`
  - result: both `False`
- `git status --short -- temp_token.json test_auth.json`
  - result: both deleted
- `git diff --name-status -- temp_token.json test_auth.json`
  - result: both `D`

Scope notes:

- No runtime code changed in this task.
- No database user was created, modified, or deleted.
- No credential values were printed in this log.

## Task 11 Evidence

Execution mode:

- selected mode: `gate_known_root_cause`
- reason: payment webhooks are financial/data-loss sensitive and duplicate callback surfaces exist
- risky domain: yes
- root cause known: yes, `backend/app/api/v1/endpoints/payment_webhook.py`
- gate command: `python scripts\agent_gate.py "fix payment webhook silent loss behavior backend/app/api/v1/endpoints/payment_webhook.py backend/app/api/v1/endpoints/payment_webhooks.py" --known-root-cause "backend/app/api/v1/endpoints/payment_webhook.py"`
- gate result: `gate ok`
- `gate_misroute`: no
- `override_used`: no

Initial boundaries:

- canonical anchor: legacy public callbacks in `backend/app/api/v1/endpoints/payment_webhook.py`, compared against `backend/app/api/v1/endpoints/payment_webhooks.py`
- first-touch files: `backend/app/api/v1/endpoints/payment_webhook.py`, `backend/app/api/v1/endpoints/payment_webhooks.py`
- validation target: py_compile for both endpoint files and focused HTTP/helper smoke for non-2xx retryable failures
- stop condition watched first: service/repository/idempotency schema changes required outside the endpoint slice

Changed files:

- `backend/app/api/v1/endpoints/payment_webhook.py`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Changed behavior:

- Legacy public Payme/Click callbacks no longer return HTTP 200 JSON for technical processing failures.
- Service result `Error processing webhook...` now maps to HTTP 500.
- Missing payment provider configuration maps to HTTP 503.
- Invalid signature maps to HTTP 400.
- Unknown rejected provider payload maps to HTTP 422.
- Duplicate webhook results with an existing webhook record are accepted idempotently with `ok: true`.
- Endpoint-level unexpected failures are logged through structured `logger.exception` and returned as HTTP 500 without raw payloads, signatures, secrets, or patient data.

Validation run:

- `python -m py_compile backend\app\api\v1\endpoints\payment_webhook.py backend\app\api\v1\endpoints\payment_webhooks.py`
  - result: passed
- Direct helper smoke for accepted, duplicate, 400, 503, 500, and 422 classifications
  - result: passed
- FastAPI TestClient smoke for `/webhooks/payment/payme`
  - missing signature: 400
  - simulated service technical failure: 500
  - result: passed

Scope notes:

- No DB schema changed.
- No payment service/repository/idempotency persistence behavior was changed in this slice.
- Duplicate callback ownership across `/api/v1/webhooks/payment/*` and `/api/v1/payments/webhook/*` is still a follow-up risk for payment consolidation/reconciliation.

## Task 12 Evidence

Execution mode:

- selected mode: `gate_known_root_cause`
- reason: file upload is PHI/security-sensitive and the simple endpoint is mounted in the API
- risky domain: yes
- root cause known: yes, `backend/app/api/v1/endpoints/file_upload_simple.py`
- gate command: `python scripts\agent_gate.py "disable or harden simple file upload before production use backend/app/api/v1/endpoints/file_upload_simple.py" --known-root-cause "backend/app/api/v1/endpoints/file_upload_simple.py"`
- gate result: `gate ok`
- `gate_misroute`: no
- `override_used`: no

Initial boundaries:

- canonical anchor: `backend/app/api/v1/endpoints/file_upload_simple.py`
- first-touch files: `backend/app/api/v1/endpoints/file_upload_simple.py`
- validation target: `python -m py_compile backend/app/api/v1/endpoints/file_upload_simple.py`
- stop condition watched first: required changes outside this endpoint file

Changed files:

- `backend/app/api/v1/endpoints/file_upload_simple.py`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Changed behavior:

- The legacy `/files/upload-simple` endpoint is disabled by default unless `ENABLE_SIMPLE_FILE_UPLOAD=1` is explicitly set.
- Added a 10 MB upload limit.
- Added MIME and extension allowlists for PDF, JPEG, PNG, and plain text.
- Added path traversal resistant filename normalization.
- Changed storage to an absolute backend-local `uploads/simple` root.
- Removed raw filename, username, and server `file_path` exposure from logs/response.
- Generic upload failures now log structured metadata and return a generic HTTP 500 response.

Validation run:

- `python -m py_compile backend\app\api\v1\endpoints\file_upload_simple.py`
  - result: passed
- FastAPI TestClient smoke
  - disabled by default: 404
  - unsupported content type/extension: 415
  - empty upload: 400
  - traversal-shaped filename with allowed PDF content: saved with sanitized filename, no `..`, no slash, no `file_path`
  - result: passed

Scope notes:

- No API router/config/docs files were touched because the gate first-touch slice allowed only `file_upload_simple.py`.
- No antivirus scanning, object storage, patient-document ownership model, or canonical document upload consolidation was added in this slice.
- The endpoint remains legacy/dev-only; production document upload still needs the canonical file/document service review.

## Task 13 Evidence

Execution mode:

- selected mode: `gate_known_root_cause`
- reason: EMR route contract is production-sensitive and affects frontend/backend ownership
- risky domain: yes
- root cause known: yes, `backend/app/api/v1/api.py`
- gate command: `python scripts\agent_gate.py "verify EMR v2 route contract and audit coverage backend/app/api/v1/api.py backend/app/api/v1/endpoints/emr_v2.py" --known-root-cause "backend/app/api/v1/api.py"`
- gate result: `gate ok`
- `gate_misroute`: no
- `override_used`: no

Initial boundaries:

- canonical anchor: `backend/app/api/v1/api.py` plus `backend/app/api/v1/endpoints/emr_v2.py`
- first-touch files: `backend/app/api/v1/api.py`, `backend/app/api/v1/endpoints/emr_v2.py`, `frontend/src/routing/routeRegistry.js`, `frontend/src/routing/routeSelectors.js`
- validation target: py_compile for API/EMR endpoint files, registered route proof, frontend build
- stop condition watched first: frontend/backend contract ownership ambiguity

Route contract conclusion:

- `emr_v2.router` has router prefix `/emr`.
- `api_router.include_router(emr_v2.router, prefix="/v2", tags=["emr-v2"])` therefore intentionally exposes `/api/v1/v2/emr/...`.
- This is supported by frontend calls to `/v2/emr/...`, tenant scope config `/api/v1/v2/emr`, and appointment-flow text naming canonical `/api/v1/v2/emr` endpoints.
- No runtime route mount change was needed.

Validation run:

- `python -m py_compile backend\app\api\v1\api.py backend\app\api\v1\endpoints\emr_v2.py`
  - result: passed
- Registered route proof from `app.main`
  - found `/api/v1/v2/emr/doctor-history`
  - found `/api/v1/v2/emr/{visit_id}`
  - found `/api/v1/v2/emr/{visit_id}/history`
  - did not find `/api/v1/emr/v2`
  - result: passed
- `npm.cmd run build` in `frontend`
  - result: passed
  - warnings: existing dynamic/static `errorHandler.js` import and large chunks
- `pytest tests\unit\test_emr_v2_api.py tests\unit\test_emr_contract.py -q`
  - first run: failed because `test_emr_v2_api.py` still used disabled `/api/v1/auth/minimal-login`
  - test sub-slice gate: `python scripts\agent_gate.py "fix stale EMR v2 route test auth setup backend/tests/unit/test_emr_v2_api.py after fallback auth disabled" --known-root-cause "backend/tests/unit/test_emr_v2_api.py"`
  - after replacing local login setup with canonical `auth_headers` fixture: 5 passed, 1 warning

Changed files:

- `backend/tests/unit/test_emr_v2_api.py`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Scope notes:

- No runtime EMR route changed.
- No frontend route changed.
- Stale test dependence on fallback auth was removed.

## Task 14 Evidence

Execution mode:

- selected mode: `gate_known_root_cause`
- reason: queue routing and SSOT affect patient order, QR join, and call-next fairness
- risky domain: yes
- root cause known: yes, `backend/app/api/v1/api.py`
- gate command: `python scripts\agent_gate.py "queue SSOT and route surface audit backend/app/api/v1/api.py backend/app/core/service_mapping.py backend/app/api/v1/endpoints/qr_queue.py backend/app/api/v1/endpoints/online_queue_new.py backend/app/api/v1/endpoints/queues.py backend/app/api/v1/endpoints/queue.py" --known-root-cause "backend/app/api/v1/api.py"`
- gate result: `gate ok`
- `gate_misroute`: no
- `override_used`: no

Initial boundaries:

- canonical anchor: `backend/app/api/v1/api.py`
- reference-only SSOT: `backend/app/services/service_mapping.py`
- first-touch files: queue endpoint mount files from gate plus gated test sub-slice
- validation target: queue endpoint py_compile, architecture contract test, frontend build
- stop condition watched first: needed changes outside first-touch or unclear queue owner

Route surface classification:

- `/api/v1/queue/*`: canonical QR/join/status/call-next/entry/admin surface from `qr_queue.router`.
- `/api/v1/queue/legacy/*`: deprecated compatibility surface from `queue_router`.
- `/api/v1/online-queue/*`: separate online queue surface from `online_queue_new.router`.
- `/api/v1/queues/*`: older stats/next-ticket surface from `queues.router`.
- `/api/v1/queue/reorder/*`: specialized reorder surface.
- `/api/v1/queue/position/*`: queue position/notification surface.

SSOT correction:

- The active service mapping file is `backend/app/services/service_mapping.py`, not `backend/app/core/service_mapping.py`.
- `QUEUE_GROUPS` contains the expected registrar/queue groups: cardiology, ecg, dermatology, dental, laboratory, procedures.
- Contract check now proves each group's `queue_tag` and `tab_key` resolve back to the same canonical group key.

Changed files:

- `backend/tests/architecture/test_w2c_queue_boundaries.py`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Validation run:

- `python -m py_compile backend\tests\architecture\test_w2c_queue_boundaries.py backend\app\services\service_mapping.py`
  - result: passed
- `pytest tests\architecture\test_w2c_queue_boundaries.py -q`
  - result: 7 passed, 1 warning
- `python -m py_compile backend\app\api\v1\api.py backend\app\api\v1\endpoints\qr_queue.py backend\app\api\v1\endpoints\online_queue_new.py backend\app\api\v1\endpoints\queues.py backend\app\api\v1\endpoints\queue.py`
  - result: passed
- `npm.cmd run build` in `frontend`
  - result: passed
  - warnings: existing dynamic/static `errorHandler.js` import and large chunks

Scope notes:

- No queue runtime logic changed.
- No `queue_time`, call-next ordering, QR token handling, or display-board behavior changed.
- Task 14 is a verified ownership/contract guard; deeper queue fairness and QR expiry/security behavior remain covered by later flow-specific tasks.

## Task 15 Evidence

Execution mode:

- selected mode: `gate`
- reason: registrar patient/visit creation touches frontend/backend contracts, RBAC, audit logs, and clinic workflow data
- risky domain: yes
- root cause known: initially no; later yes for unauthenticated visits read endpoints
- initial gate command: `python scripts\agent_gate.py "verify registrar patient and visit creation flow patient registration visit creation appointment linkage validation duplicate patient nullable unique email role access transactions audit logs"`
- initial gate result: `stop` because no first-touch files resolved
- follow-up gate command: `python scripts\agent_gate.py "verify registrar patient and visit creation flow backend/app/api/v1/endpoints/patients.py backend/app/api/v1/endpoints/visits.py backend/app/api/v1/endpoints/appointments.py backend/app/api/v1/endpoints/registrar_integration.py backend/app/api/v1/endpoints/appointment_flow.py"`
- follow-up gate result: `gate ok`
- runtime sub-slice gate command: `python scripts\agent_gate.py "fix unauthenticated visits list and visit detail endpoints role access in backend/app/api/v1/endpoints/visits.py" --known-root-cause "backend/app/api/v1/endpoints/visits.py"`
- runtime sub-slice gate result: `gate ok`
- test sub-slice gate command: `python scripts\agent_gate.py "update visits router service wiring tests after visits read endpoints require role auth" --known-root-cause "backend/tests/unit/test_visits_router_service_wiring.py"`
- test sub-slice gate result: `narrow override`
- `gate_misroute`: yes on test sub-slice
- `override_used`: yes on test sub-slice, limited to the confirmed backend test file

Initial boundaries:

- canonical anchors: `backend/app/api/v1/endpoints/patients.py`, `backend/app/api/v1/endpoints/visits.py`, `backend/app/api/v1/endpoints/registrar_wizard.py`, `backend/app/crud/visit.py`
- reference-only files inspected: `frontend/src/components/wizard/AppointmentWizardV2.jsx`, `backend/app/services/patient_service.py`, `backend/app/services/visits_api_service.py`, `backend/app/repositories/visits_api_repository.py`, `backend/app/api/v1/endpoints/registrar_integration.py`
- first-touch runtime file: `backend/app/api/v1/endpoints/visits.py`
- first-touch test file after override: `backend/tests/unit/test_visits_router_service_wiring.py`
- validation target: visits endpoint py_compile, visits router tests, patient service tests, registrar all-appointments tests, registrar cart queue characterization, e2e clinic flow
- stop condition watched first: needed changes outside first-touch or canonical-vs-legacy uncertainty

Route and workflow conclusions:

- The visible registrar wizard creates/fetches patients through `/api/v1/patients/`.
- The visible registrar wizard creates the operational cart through `/api/v1/registrar/cart`, which creates `Visit` rows through `app.crud.visit.create_visit`, creates an invoice, links visits to invoice rows, assigns same-day queue numbers, and commits the cart transaction.
- `POST /api/v1/registrar/appointments` in `registrar_integration.py` is a mounted legacy/stale endpoint that returns a temporary appointment id and does not create a real `Appointment` or `Visit`; frontend search found no visible caller for that exact route.
- `POST /api/v1/visits/visits` already required Admin/Registrar/Doctor and logs create audit entries through `VisitsApiService`.
- `GET /api/v1/visits/visits` and `GET /api/v1/visits/visits/{visit_id}` were unauthenticated before this task; they now require one of Admin, Registrar, Doctor, Cashier, Lab, or Nurse.

Changed files:

- `backend/app/api/v1/endpoints/visits.py`
- `backend/tests/unit/test_visits_router_service_wiring.py`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Changed behavior:

- Visit list/detail read endpoints now fail closed without authentication.
- Authorized staff roles can still read visit list/detail endpoints.
- Router wiring tests now pass auth headers for allowed read cases and assert unauthenticated read requests return 401 before the service layer is called.

Validation run:

- `python -m py_compile backend\app\api\v1\endpoints\patients.py backend\app\api\v1\endpoints\visits.py backend\app\api\v1\endpoints\appointments.py backend\app\api\v1\endpoints\registrar_integration.py backend\app\api\v1\endpoints\appointment_flow.py`
  - result: passed
- `python -m py_compile backend\tests\unit\test_visits_router_service_wiring.py backend\app\api\v1\endpoints\visits.py`
  - result: passed
- `pytest backend\tests\unit\test_visits_router_service_wiring.py -q`
  - result: 6 passed, 1 warning
- `pytest backend\tests\unit\test_patient_service.py backend\tests\unit\test_visits_router_service_wiring.py backend\tests\integration\test_registrar_all_appointments.py backend\tests\characterization\test_registrar_wizard_queue_characterization.py -q`
  - result: 16 passed, 1 warning
- `pytest backend\tests\integration\test_e2e_clinic.py -q`
  - result: 1 passed, 1 warning

Scope notes:

- No patient schema, patient service, visit service, registrar cart, queue assignment, payment invoice, migration, or frontend runtime file changed in this task.
- The stale `/api/v1/registrar/appointments` mounted endpoint remains a follow-up risk because changing or disabling it would require a separate ownership decision.
- Patient-role own-data restrictions remain a known RBAC gap: existing RBAC tests still document that patient-to-own-patient linkage is incomplete.
- Frontend wizard logging still contains sensitive operational details in console output; that belongs in a later frontend/security cleanup slice, not this backend Task 15 patch.

## Task 16 Evidence

Execution mode:

- selected mode: `gate`
- reason: Telegram webhooks and notifications are security-sensitive and span backend/frontend ownership
- risky domain: yes
- root cause known: initially no; later yes for webhook fail-open helpers
- initial gate command: `python scripts\agent_gate.py "verify Telegram webhook and notification safety secret-token validation retry handling PHI exposure opt-in opt-out failed notification handling backend Telegram endpoints services tests docs"`
- initial gate result: `gate ok`
- first webhook sub-slice files: `backend/app/api/v1/endpoints/admin_telegram.py`, `backend/app/api/v1/endpoints/telegram_webhook.py`
- test sub-slice gate command: `python scripts\agent_gate.py "add Telegram webhook tests for missing secret fail-closed and no full payload logging" --known-root-cause "backend/tests/unit/test_telegram_webhook_security.py"`
- test sub-slice gate result: `narrow override`
- `gate_misroute`: yes on test sub-slice
- `override_used`: yes on test sub-slice, limited to the confirmed backend test file
- additional webhook gate command: `python scripts\agent_gate.py "fix Telegram bot and enhanced webhook secret validation fail-open behavior backend/app/api/v1/endpoints/telegram_bot.py backend/app/api/v1/endpoints/telegram_webhook_enhanced.py" --known-root-cause "backend/app/api/v1/endpoints/telegram_bot.py"`
- additional webhook gate result: `gate ok`

Initial boundaries:

- canonical anchor: Telegram mount list in `backend/app/api/v1/api.py`
- webhook first-touch files: `backend/app/api/v1/endpoints/telegram_webhook.py`, `backend/app/api/v1/endpoints/admin_telegram.py`, `backend/app/api/v1/endpoints/telegram_bot.py`, `backend/app/api/v1/endpoints/telegram_webhook_enhanced.py`
- test first-touch file after override: `backend/tests/unit/test_telegram_webhook_security.py`
- reference-only files inspected: `backend/app/api/v1/endpoints/telegram_integration.py`, `backend/app/api/v1/endpoints/telegram_notifications.py`, `backend/app/crud/telegram_config.py`, `backend/app/models/telegram_config.py`, `frontend/src/components/telegram/TelegramManager.jsx`, `frontend/src/components/TelegramManager.jsx`
- validation target: Telegram endpoint py_compile, targeted webhook/security tests, visit confirmation tests, frontend build
- stop condition watched first: required changes outside first-touch or unclear canonical-vs-legacy webhook ownership

Route and workflow conclusions:

- Mounted webhook surfaces include `/api/v1/telegram/webhook`, `/api/v1/telegram/webhook/enhanced`, and `/api/v1/telegram/bot/webhook`.
- Before this task, all three webhook secret helpers accepted updates when `webhook_secret` was absent.
- The visible Telegram manager posts JSON to `/api/v1/admin/telegram/set-webhook`, while `admin_telegram.py` previously accepted a plain function parameter and set Telegram webhook without a `secret_token`.
- `telegram_webhook.py` previously logged the full incoming Telegram update payload; this could include patient names, message text, phone-like content, or callback data.

Changed files:

- `backend/app/api/v1/endpoints/admin_telegram.py`
- `backend/app/api/v1/endpoints/telegram_webhook.py`
- `backend/app/api/v1/endpoints/telegram_bot.py`
- `backend/app/api/v1/endpoints/telegram_webhook_enhanced.py`
- `backend/tests/unit/test_telegram_webhook_security.py`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Changed behavior:

- `/api/v1/telegram/webhook`, `/api/v1/telegram/webhook/enhanced`, and `/api/v1/telegram/bot/webhook` now reject webhook updates with HTTP 503 if no webhook secret is configured.
- Invalid Telegram webhook secret tokens still return HTTP 403.
- The normal webhook now logs only safe update metadata (`update_id`, `message_id`, callback presence), not the full update payload.
- `/api/v1/admin/telegram/set-webhook` now accepts the JSON shape sent by the frontend (`{"webhook_url": "..."}`), generates a Telegram webhook `secret_token`, sends it to Telegram's `setWebhook`, and persists the matching `webhook_secret` in `telegram_configs` without returning the secret in the API response.

Validation run:

- `python -m py_compile backend\app\api\v1\endpoints\admin_telegram.py backend\app\api\v1\endpoints\telegram_webhook.py`
  - result: passed
- `python -m py_compile backend\tests\unit\test_telegram_webhook_security.py backend\app\api\v1\endpoints\admin_telegram.py backend\app\api\v1\endpoints\telegram_webhook.py`
  - result: passed
- `python -m py_compile backend\app\api\v1\endpoints\telegram_bot.py backend\app\api\v1\endpoints\telegram_webhook_enhanced.py backend\app\api\v1\endpoints\admin_telegram.py backend\app\api\v1\endpoints\telegram_webhook.py`
  - result: passed
- `pytest backend\tests\unit\test_telegram_webhook_security.py -q`
  - result: 5 passed, 1 warning
- `pytest backend\tests\unit\test_telegram_webhook_security.py backend\tests\unit\test_telegram_bot_management_api_service.py -q`
  - result: 8 passed, 1 warning
- `pytest backend\tests\integration\test_visit_confirmation_api.py -q`
  - result: 16 passed, 1 warning
- `npm.cmd run build` in `frontend`
  - result: passed
  - warnings: existing dynamic/static `errorHandler.js` import and large chunks

Scope notes:

- No Telegram token values, webhook secrets, chat IDs from real data, or patient data were printed.
- Notification endpoints in `telegram_integration.py` and `telegram_notifications.py` still return patient phone/name/chat metadata in some authorized responses; this remains a privacy-readiness cleanup item.
- Telegram notification retry/outbox semantics remain thin; failed background task delivery is not yet reconciled with a durable notification log.
- The frontend has two Telegram manager components; canonical UI ownership should be consolidated later, but no frontend runtime file was changed in this task.

## Task 17 Evidence

Execution mode:

- selected mode: `gate`
- reason: Alembic/PostgreSQL migration safety is database-source-of-truth and deployment-sensitive
- risky domain: yes
- root cause known: no for the audit; yes for the later staging-port drift sub-slices
- initial gate command: `python scripts\agent_gate.py "verify Alembic revision chain and clean PostgreSQL upgrade safety backend/alembic/versions alembic config CI runbooks"`
- initial gate result: `gate ok`
- staging compose drift gate command: `python scripts\agent_gate.py "fix staging Postgres host port drift from 15432 to canonical 55432 in compose and operator docs" --known-root-cause "ops/compose.staging.yml"`
- staging compose drift gate result: `gate ok`
- ops README drift gate command: `python scripts\agent_gate.py "update ops README staging Postgres port from stale 15432 to canonical 55432" --known-root-cause "ops/README.md"`
- ops README drift gate result: `narrow override`
- `gate_misroute`: yes on the README docs sub-slice
- `override_used`: yes on the README docs sub-slice, limited to the single stale staging Postgres port line

Initial boundaries:

- canonical anchors: `backend/alembic/versions/*`, `backend/alembic.ini`, `backend/alembic/env.py`
- deployment references: `ops/docker-compose.yml`, `ops/compose.staging.yml`, `ops/backend.entrypoint.sh`, `ops/README.md`
- validation target: Alembic revision chain proof, Alembic heads/branches/history, offline SQL generation attempt, disposable PostgreSQL availability check, staging port-drift search
- stop condition watched first: migration edits or unknown live database target ambiguity

Migration chain conclusions:

- Alembic revision files found: 22.
- Base revision: `0001_baseline`.
- Head revision: `0022_service_audit_log`.
- Duplicate revisions: none.
- Missing `down_revision` references: none.
- Branch points: none.
- Linear chain length: 22.
- `python -m alembic heads --verbose` reports `0022_service_audit_log (head)`.
- `python -m alembic branches --verbose` reports no branches.
- `python -m alembic history -r base:head` lists the expected single linear history from `<base> -> 0001_baseline` through `0021_printing_tables -> 0022_service_audit_log`.

Clean upgrade status:

- Docker and Docker Compose are not available in this local environment, so compose-backed disposable PostgreSQL could not be started here.
- Local staging PostgreSQL port `127.0.0.1:55432` was closed before the compose default fix.
- Local `127.0.0.1:5432` was open, but it was not used for `alembic upgrade head` because it may be the current live/dev clinic database and was not a disposable target.
- `psql` was not available in PATH, so a local disposable database could not be created with CLI tools.
- `python -m alembic upgrade head --sql` was attempted against a dummy PostgreSQL URL and generated 2369 lines of SQL before failing at `0003_schema_parity_tables`; the failure is offline-mode incompatibility because that revision calls `inspect(bind).get_table_names()` against Alembic's mock connection.
- Therefore a clean PostgreSQL upgrade to head is documented as blocked locally until Docker/Compose or another explicitly disposable PostgreSQL target is available.

Changed files:

- `ops/compose.staging.yml`
- `ops/README.md`
- `ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Changed behavior:

- Staging compose now publishes PostgreSQL on the canonical host port `55432` by default.
- Ops staging README now matches the canonical `127.0.0.1:55432` staging Postgres port.

Validation run:

- `rg --files backend\alembic\versions`
  - result: 22 revision files listed
- structured AST revision check
  - result: one base, one head, no duplicate revisions, no missing `down_revision`, no branch points, linear count 22
- structured AST upgrade/downgrade check
  - result: all files define upgrade and downgrade; `0012_lab_bind_real_codes.py` and `0013_lab_bind_actual_catalog_codes.py` intentionally have pass-only downgrades preserving live operator mapping data
- `python -m alembic heads --verbose`
  - result: passed, head `0022_service_audit_log`
- `python -m alembic branches --verbose`
  - result: passed, no branch output
- `python -m alembic history -r base:head`
  - result: passed, linear history output
- offline SQL generation with dummy PostgreSQL URL
  - result: failed at `0003_schema_parity_tables.py` because offline mock connections cannot support SQLAlchemy inspection
- TCP availability check
  - result: `127.0.0.1:55432` closed before local compose startup; `127.0.0.1:5432` open but intentionally not used
- Docker/Docker Compose availability check
  - result: not available
- staging port-drift search
  - result: `ops/compose.staging.yml`, `ops/README.md`, `docs/runbooks/LOCAL_STAGING_ACCEPTANCE_RUNBOOK.md`, `AGENTS.md`, and `.ai-factory` context all now point at `55432`

Scope notes:

- No Alembic migration file was edited.
- No database DDL was run against a live or unknown database.
- No database URL, password, token, or patient data was printed.
- CI workflows already contain PostgreSQL-backed `alembic upgrade head` steps, but those workflows were not run locally in this session.
- A future verification pass still needs an actual disposable PostgreSQL target to prove online `alembic upgrade head` end-to-end.

## Task 18 Evidence

Execution mode:

- selected mode: `gate`
- reason: AI clinical assistance is medical/privacy-sensitive and spans backend endpoints plus visible doctor/specialist UI
- risky domain: yes
- root cause known: no for the initial audit; yes for follow-up backend and frontend slices
- initial gate command: `python scripts\agent_gate.py "verify AI module safety and visible fallback using backend/app/api/v1/api.py backend/app/api/v1/endpoints/ai.py backend/app/api/v1/endpoints/ai_gateway.py backend/app/api/v1/endpoints/ai_chat.py backend/app/api/v1/endpoints/emr_ai.py backend/app/api/v1/endpoints/emr_ai_enhanced.py backend/app/services/ai frontend/src/routing/routeRegistry.js frontend/src/components/ai frontend/src/components/emr-v2/ai frontend/src/components/emr-v2/EMRContainerV2.jsx" --known-root-cause "backend/app/api/v1/api.py"`
- backend gate result: `gate ok`
- frontend visible-fallback gate command: `python scripts\agent_gate.py "add visible AI draft-only and provider-fallback warnings in frontend AI assistant widgets for Task 18" --known-root-cause "frontend/src/components/ai/AIAssistant.jsx"`
- frontend gate result: `narrow override`
- `gate_misroute`: no on the frontend sub-slice
- `override_used`: yes on the frontend sub-slice, limited to `frontend/src/components/ai/AIAssistant.jsx`

Initial boundaries:

- canonical anchors: AI mount list in `backend/app/api/v1/api.py`, AI RBAC matrix in `backend/app/core/rbac.py`, canonical AI gateway contract in `backend/app/services/ai/ai_interfaces.py`
- backend first-touch files: `backend/app/api/v1/endpoints/ai.py`, `backend/app/api/v1/endpoints/ai_gateway.py`, `backend/app/api/v1/endpoints/ai_chat.py`, `backend/app/api/v1/endpoints/emr_ai.py`, `backend/app/api/v1/endpoints/emr_ai_enhanced.py`
- frontend first-touch file after override: `frontend/src/components/ai/AIAssistant.jsx`
- reference-only files inspected: `backend/app/services/ai/ai_manager.py`, `backend/app/services/ai/ai_gateway.py`, `frontend/src/routing/routeRegistry.js`, doctor/specialist panel imports, `frontend/src/components/emr-v2/ai/*`
- validation target: AI endpoint py_compile, frontend build, targeted AI component tests, available AI backend unit tests
- stop condition watched first: required edits outside first-touch files or canonical-vs-legacy ambiguity across `/ai`, `/ai/v2`, `/ai/chat`, `/emr/ai`, and EMR v2 AI hooks

AI surface conclusions:

- `backend/app/api/v1/api.py` mounts multiple AI surfaces: legacy `/ai`, canonical-ish gateway `/ai/v2`, `/ai/chat`, `/emr/ai`, `/emr/ai-enhanced`, admin AI, analytics, and EMR AI integrations.
- `backend/app/api/v1/endpoints/ai_gateway.py` already uses `require_ai_permission(...)`, PII anonymization, audit logging, fallback metadata, and an AI response contract with disclaimer.
- `backend/app/api/v1/endpoints/ai_chat.py` already uses `require_ai_permission(AIPermission.CHAT)` for REST and checks chat permission on WebSocket token auth.
- Legacy `backend/app/api/v1/endpoints/ai.py` had broad `get_current_user` authentication but no router-level AI permission gate.
- `backend/app/api/v1/endpoints/emr_ai.py` used generic auth and exposed `/suggestions/health` without an authenticated AI permission dependency.
- `backend/app/services/ai/ai_manager.py` initializes a mock provider by default when no external provider is configured, so the visible UI must not imply autonomous clinical readiness.

Changed files:

- `backend/app/api/v1/endpoints/ai.py`
- `backend/app/api/v1/endpoints/emr_ai.py`
- `backend/app/api/v1/endpoints/emr_ai_enhanced.py`
- `frontend/src/components/ai/AIAssistant.jsx`
- `ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Changed behavior:

- Legacy `/api/v1/ai/*` endpoints now require at least one clinical/admin AI RBAC permission at router level instead of allowing any authenticated user role through the legacy surface.
- `/api/v1/emr/ai/*` now uses an AI RBAC dependency for diagnosis, ICD-10, document-analysis, or admin AI permissions.
- `/api/v1/emr/ai/suggestions/health` is no longer public; it requires the same EMR AI access boundary as the other EMR AI endpoints.
- EMR AI responses now include `decision_boundary: "suggestion_only"`, `requires_doctor_confirmation: true`, and a draft-only notice where the endpoint returns clinical AI suggestions.
- EMR v2 AI suggestion response models now default to `requiresDoctorConfirmation`/`requires_doctor_confirmation` and `decision_boundary: "suggestion_only"`.
- The visible `AIAssistant` component now always displays a draft-only/human-confirmation warning when open.
- `AIAssistant` now treats backend `error`/`detail` payloads such as "No AI provider available" as user-visible errors instead of rendering them as successful clinical results.
- `AIAssistant` now shows a friendly provider-unavailable message for missing/unconfigured provider errors and a visible warning when a mock fallback provider is detected in the result payload.

Validation run:

- `python -m py_compile backend\app\api\v1\api.py backend\app\api\v1\endpoints\ai.py backend\app\api\v1\endpoints\ai_gateway.py backend\app\api\v1\endpoints\ai_chat.py backend\app\api\v1\endpoints\emr_ai.py backend\app\api\v1\endpoints\emr_ai_enhanced.py`
  - result: passed
- `npm.cmd run build` in `frontend`
  - result: passed
  - warnings: existing dynamic/static `errorHandler.js` import and large chunks
- `npm.cmd run test:run -- src/components/ai/__tests__/AIAssistant.test.jsx`
  - result: 1 test file passed, 9 tests passed
- `python -m pytest backend\tests\unit\test_ai_tracking_api_service.py backend\tests\unit\test_admin_ai_service.py -q`
  - result: 3 passed, 1 warning
- `python -m pytest backend\tests\unit\test_ai_chat_api_service.py backend\tests\unit\test_ai_tracking_api_service.py backend\tests\unit\test_admin_ai_service.py -q`
  - result: blocked during collection because `backend/tests/unit/test_ai_chat_api_service.py` uses `@pytest.mark.asyncio` while `backend/pytest.ini` has `--strict-markers` and no `asyncio` marker entry

Scope notes:

- No AI prompt content, patient data, provider keys, tokens, or production URLs were printed.
- The legacy `/api/v1/ai/*` surface is still not migrated to the canonical `/ai/v2` gateway contract; this task only added a coarse AI permission gate.
- Other visible AI surfaces such as `AIChatWidget`, EMR v2 popovers, quality-control widgets, and admin AI screens were inspected but not edited because the frontend gate allowed only `AIAssistant.jsx`.
- `AIManager` still initializes the mock provider by default; the UI now warns on detected mock/default/unavailable states, but a later backend slice should decide whether mock AI is allowed outside explicit demo/test mode.
- The pytest `asyncio` marker configuration issue is a test-infrastructure follow-up and was not changed inside this AI safety slice.

## Task 19 Evidence

Execution mode:

- selected mode: `narrow_override`
- reason: top confirmed visible role-screen defect had a known root cause in `frontend/src/pages/DoctorPanel.jsx`, and `agent_gate.py` allowed only that file for the first patch slice
- risky domain: yes
- root cause known: yes
- gate command: `python scripts\agent_gate.py "Task 19 fix DoctorPanel fake/mock patient and appointment data in visible doctor role screen with safe empty/error state" --known-root-cause "frontend/src/pages/DoctorPanel.jsx"`
- gate result: `narrow override`
- `gate_misroute`: no
- `override_used`: yes, limited to `frontend/src/pages/DoctorPanel.jsx`

Initial boundaries:

- canonical anchor: visible general doctor role screen in `frontend/src/pages/DoctorPanel.jsx`
- first-touch file: `frontend/src/pages/DoctorPanel.jsx`
- reference-only files inspected: doctor/specialist panels for fake-data/fallback patterns
- validation target: `npm.cmd run build` in `frontend`, static search proving fake patient fixture removal
- stop condition watched first: need to introduce or guess a new patient/appointment API contract, or edit shared API/services outside the allowed file

User-visible conclusion:

- `DoctorPanel.jsx` previously created three fake patients with names, phone-like values, diagnoses, and appointments after an artificial delay.
- This could make a doctor-facing production screen look populated with real clinic data when no real backend data had loaded.
- The task intentionally fixed this strongest confirmed visible defect first instead of broad UX cleanup across unrelated panels.

Changed files:

- `frontend/src/pages/DoctorPanel.jsx`
- `ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Changed behavior:

- The general doctor screen no longer generates fake patients, phone numbers, diagnoses, or appointments.
- The patients and appointments tabs now show honest empty states when there is no real data.
- Loading failure state is explicit and offers a retry action without showing fake data.
- Patient and appointment rows now render safe fallbacks for missing optional fields instead of printing `undefined` or crashing on missing names/phones.
- Existing queue integration remains the real doctor workflow surface; no new API contract was invented.

Validation run:

- `npm.cmd run build` in `frontend`
  - result: passed
  - warnings: existing dynamic/static `errorHandler.js` import and large chunks
- `rg -n "mockPatients|mockAppointments|Симуляция загрузки|Тестовые данные|Ахмедов|Каримова|Тошматов|\+998 90 123" frontend\src\pages\DoctorPanel.jsx`
  - result: no matches, proving the local fake-data fixture was removed from the visible doctor screen

Scope notes:

- No specialist panels were changed in this task.
- No backend patient/appointment endpoint contract was guessed or added.
- Some quick-action/report buttons in the general doctor screen still need a separate UX slice because they are outside the fake-data patch and may require product decisions.

## Task 20 Evidence

Execution mode:

- selected mode: `direct_execute`
- reason: narrow env-example and developer note update, no runtime route behavior change
- risky domain: no
- root cause known: yes
- command: not needed for direct execute

Initial boundaries:

- canonical anchor: `frontend/src/routing/routeSelectors.js` requiring `VITE_ENABLE_INTERNAL_DEMO=1`
- first-touch files: `frontend/.env.example`, `README.md`
- validation target: route contract test and static search for the documented env var
- stop condition watched first: any change that re-enabled internal demo routes by default

Changed files:

- `frontend/.env.example`
- `README.md`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Changed behavior:

- No runtime behavior changed.
- `frontend/.env.example` now documents `VITE_ENABLE_INTERNAL_DEMO=1` as an explicit local-only switch for hidden internal demo/test pages.
- `README.md` now tells developers that `/payment/test`, `/css-test`, `/buttons`, and other internal demo/test aliases remain hidden by default and must not be enabled in production-like environments.

Validation run:

- `npm.cmd run test:run -- src/routing/__tests__/routeContract.test.js`
  - result: 1 test file passed, 13 tests passed
- `rg -n "VITE_ENABLE_INTERNAL_DEMO|payment/test|css-test|buttons" frontend\.env.example README.md frontend\src\routing\routeSelectors.js frontend\src\routing\__tests__\routeContract.test.js`
  - result: documented env var and existing route gate/test references found

Scope notes:

- No frontend route registry, selectors, guards, or runtime code was changed in this task.
- Internal demo routes remain disabled unless `VITE_ENABLE_INTERNAL_DEMO=1` is explicitly set.

## Task 21 Evidence

Execution mode:

- selected mode: `direct_execute`
- reason: docs/AIF-context alignment using verified evidence only; no runtime behavior change
- risky domain: no
- root cause known: yes
- command: not needed for direct execute

Initial boundaries:

- canonical anchor: `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`
- first-touch files: `docs/PROJECT_AUDIT.md`, `docs/RECOVERY_PLAN.md`, `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/SECURITY_CHECKLIST.md`, `docs/AI_MODULE.md`, `docs/TESTING.md`, `docs/DEPLOYMENT.md`, `docs/README.md`, `.ai-factory/DESCRIPTION.md`
- validation target: docs file presence, docs index references, simple link presence check, and search for false compliance/production-ready claims
- stop condition watched first: any claim not supported by completed Tasks 1-20 or source files

Changed files:

- `docs/PROJECT_AUDIT.md`
- `docs/RECOVERY_PLAN.md`
- `docs/ARCHITECTURE.md`
- `docs/API.md`
- `docs/SECURITY_CHECKLIST.md`
- `docs/AI_MODULE.md`
- `docs/TESTING.md`
- `docs/DEPLOYMENT.md`
- `docs/README.md`
- `.ai-factory/DESCRIPTION.md`
- `.ai-factory/PLAN.md`
- `.ai-factory/logs/RECOVERY_IMPLEMENTATION_STATUS.md`

Changed behavior:

- No runtime behavior changed.
- Recovery docs now summarize verified audit facts, remaining risks, recovery phases, architecture boundaries, API surfaces, security checklist, AI safety posture, testing gaps, and deployment gates.
- `docs/README.md` now links the new recovery docs.
- `.ai-factory/DESCRIPTION.md` now points future agents to the active recovery plan, resume log, and new recovery docs.

Validation run:

- file presence check for the eight new recovery docs
  - result: all expected files exist
- `rg -n "production-ready|Production-ready|compliant|compliance|HIPAA|GDPR|ready for production|production ready" docs\PROJECT_AUDIT.md docs\RECOVERY_PLAN.md docs\ARCHITECTURE.md docs\API.md docs\SECURITY_CHECKLIST.md docs\AI_MODULE.md docs\TESTING.md docs\DEPLOYMENT.md`
  - result: only the intended non-compliance warning in `docs/SECURITY_CHECKLIST.md` was found
- docs index search for new recovery docs
  - result: `docs/README.md` references all new recovery docs
- simple Python link-presence check across new docs and `docs/README.md`
  - result: passed

Scope notes:

- These docs intentionally do not claim production readiness.
- Historical docs were not moved, deleted, or rewritten.
- `/aif-verify --strict` remains the next workflow step before security/review/commit overlays.

## Strict Verify Evidence

Workflow:

- `/aif-verify --strict` was run after all `/aif-implement @.ai-factory/PLAN.md` tasks were checked complete.
- A stale-auth test failure was found: several backend tests still requested `/api/v1/auth/minimal-login` after fallback auth was disabled.
- The failure was fixed through `/aif-fix` using gate-known-root-cause slices for test files only.

Fix files:

- `backend/tests/conftest.py`
- `backend/tests/test_file_security.py`
- `backend/tests/integration/test_rbac_matrix.py`
- `backend/tests/integration/test_analytics_contracts.py`
- `backend/tests/integration/test_doctor_general_queue.py`
- `backend/tests/integration/test_admin_finance_transactions.py`
- `backend/tests/integration/test_activation_api.py`
- `backend/tests/unit/test_ticket_print_settings.py`
- `ai/langgraph/EVIDENCE_LIGHTRAG_READINESS.md`

Strict verification run:

- `git diff --check`
  - result: passed; Git printed line-ending normalization warnings only
- `python -m py_compile ...` for changed backend runtime and test files
  - result: passed
- backend strict bundle:
  - `python -m pytest backend\tests\test_2fa_enforcement.py backend\tests\test_security_middleware.py backend\tests\test_file_security.py backend\tests\unit\test_file_system_api_service.py backend\tests\unit\test_payment_webhook_service.py backend\tests\unit\test_payment_webhook_api_service.py backend\tests\unit\test_provider_webhook_service.py backend\tests\unit\test_payment_reconciliation_service.py backend\tests\integration\test_payment_init_e2e.py backend\tests\integration\test_e2e_payment_flow.py backend\tests\unit\test_telegram_webhook_security.py backend\tests\unit\test_visits_router_service_wiring.py backend\tests\unit\test_emr_v2_api.py backend\tests\architecture\test_w2c_queue_boundaries.py backend\tests\integration\test_rbac_matrix.py backend\tests\integration\test_doctor_general_queue.py backend\tests\integration\test_analytics_contracts.py backend\tests\integration\test_admin_finance_transactions.py backend\tests\integration\test_activation_api.py backend\tests\unit\test_ticket_print_settings.py -q --tb=short --disable-warnings`
  - result: 126 passed, 1 warning
- frontend targeted tests:
  - `npm.cmd run test:run -- src/routing/__tests__/routeContract.test.js src/components/ai/__tests__/AIAssistant.test.jsx`
  - result: 2 files passed, 22 tests passed
- frontend build:
  - `npm.cmd run build`
  - result: passed
  - warnings: existing dynamic/static `errorHandler.js` import warning and large chunk warnings
- stale minimal-login search:
  - result: remaining references are fallback implementation, middleware classifier tests, and 2FA fallback-disabled assertions only

Known verification gap:

- Alembic clean upgrade on a disposable PostgreSQL target was not run locally because no disposable PG target was available in this session.

## Pre-Commit Security Checklist Evidence

Workflow:

- `/aif-security-checklist` was applied to the current recovery diff before staging/commit.
- `.ai-factory/SECURITY.md` ignore file was not present.
- Review scope focused on fail-closed auth, RBAC-sensitive tests, payment webhook retry semantics, upload safety, Telegram webhook secrets, AI human-in-loop metadata, and secret leakage.

Security checks run:

- tracked env check:
  - `git ls-files .env .env.* backend/.env backend/.env.* frontend/.env frontend/.env.*`
  - result: only env example files are tracked
- changed-file secret pattern scan:
  - result: no new hardcoded secret values found in the recovery diff; matches were placeholders/config field names or existing non-secret text
- auth surface scan:
  - result: canonical login uses `/api/v1/authentication/login`, fallback auth is disabled by default, OAuth2 token URL points to the canonical login path, and fallback-disabled tests pass
- payment webhook scan:
  - result: public Payme/Click webhook failures now raise non-200 HTTP errors instead of returning `{"ok": false}` with HTTP 200
- simple upload scan:
  - result: simple upload is feature-gated and validates content type, extension, size, and safe storage path before writing
- Telegram scan:
  - result: Telegram webhook handlers require `X-Telegram-Bot-Api-Secret-Token` when a webhook secret is configured
- AI safety scan:
  - result: AI endpoints are permission-gated and EMR AI responses expose draft-only/human-confirmation metadata
- frontend dependency scan:
  - `npm.cmd audit --omit=dev --audit-level=high`
  - result: found 0 vulnerabilities

Residual risks:

- Some legacy backend paths still contain `print(...)` error logging outside the first recovery slice; no new sensitive prints were introduced in this diff.
- Repo-wide historical files still contain test/API-key-like words; they were not introduced by this recovery diff and need a separate secrets-history cleanup policy.
- Alembic clean upgrade on disposable PostgreSQL remains unverified locally.

## PR #377 CI Follow-Up Evidence

Issue:

- GitHub backend CI failed on `tests/integration/test_notification_catalog_slice3_legacy_webhooks.py::test_legacy_payme_webhook_emits_failed_payment_notification`.
- The recovery payment hardening returned HTTP 422 for `ok: false` results even when a webhook record existed and the failed-payment notification was emitted.

Fix:

- `backend/app/api/v1/endpoints/payment_webhook.py` now treats `ok: false` plus a saved `webhook_id` as an accepted domain result.
- Retryable processing failures without a webhook record still return non-200 errors.

Validation run:

- `python -m py_compile backend\app\api\v1\endpoints\payment_webhook.py`
  - result: passed
- `python -m pytest backend\tests\integration\test_notification_catalog_slice3_legacy_webhooks.py::test_legacy_payme_webhook_emits_failed_payment_notification backend\tests\integration\test_notification_catalog_slice3_legacy_webhooks.py::test_legacy_payme_webhook_duplicate_callback_does_not_create_duplicate_delivery backend\tests\unit\test_payment_webhook_service.py backend\tests\unit\test_payment_webhook_api_service.py backend\tests\unit\test_provider_webhook_service.py backend\tests\unit\test_payment_reconciliation_service.py backend\tests\integration\test_payment_init_e2e.py backend\tests\integration\test_e2e_payment_flow.py -q --tb=short --disable-warnings`
  - result: 30 passed, 1 warning

PR metadata:

- PR body was updated to satisfy the local PR review quality gate template.
- `python scripts\run_pr_review_gate_checks.py --body-env PR_BODY`
  - result: passed locally before updating PR #377.

## Task 22 Evidence

Execution mode:

- selected mode: `gate_known_root_cause`
- reason: payment/billing endpoint logging and public error detail hardening
- risky domain: yes
- root cause known: yes
- command: `python scripts\agent_gate.py "Task 22 remove legacy payment webhook endpoint print and raw error leakage from admin/registrar list_transactions and webhook_summary endpoints while preserving role guards and webhook semantics" --known-root-cause "backend/app/api/v1/endpoints/payment_webhook.py"`

Initial boundaries:

- canonical anchor: `backend/app/api/v1/endpoints/payment_webhook.py`
- first-touch files: `backend/app/api/v1/endpoints/payment_webhook.py`
- validation target: compile plus targeted payment webhook API/repository/service and legacy notification tests
- stop condition watched first: any required edit outside endpoint logging/error detail

Changed behavior:

- Removed legacy `print(...)` diagnostics from `list_transactions` and `get_webhook_summary`.
- Replaced raw exception text in public HTTP 500 details with generic messages.
- Added structured `logger.exception(...)` metadata using endpoint name and filter-presence booleans only.
- Preserved role guards and payment webhook processing semantics.

Validation run:

- `python -m py_compile backend\app\api\v1\endpoints\payment_webhook.py`
  - result: passed
- `python -m pytest backend\tests\unit\test_payment_webhook_api_service.py backend\tests\unit\test_payment_webhook_api_repository.py backend\tests\unit\test_payment_webhook_service.py backend\tests\integration\test_notification_catalog_slice3_legacy_webhooks.py -q --tb=short --disable-warnings`
  - result: 16 passed, 1 warning
- `rg -n "print\(|Error getting transactions:|Error getting summary:" backend\app\api\v1\endpoints\payment_webhook.py`
  - result: no matches

## Task 23 Evidence

Execution mode:

- selected mode: `gate_known_root_cause`
- reason: payment/billing service logging and public error detail hardening
- risky domain: yes
- root cause known: yes
- command: `python scripts\agent_gate.py "Task 23 audit remaining payment service logging and public error leakage in backend payment webhook service while preserving reconciliation and notification semantics" --known-root-cause "backend/app/services/payment_webhook.py"`

Initial boundaries:

- canonical anchor: `backend/app/services/payment_webhook.py`
- first-touch files: `backend/app/services/payment_webhook.py`
- validation target: compile plus targeted payment webhook/payment service tests
- stop condition watched first: any required behavior/schema/repository edit outside service logging/error detail cleanup

Changed behavior:

- Removed raw `print(...)` diagnostics from the Payme/Click payment webhook service integration path.
- Replaced public result messages that included raw exception text with generic `Error processing webhook` messages.
- Replaced summary error payload `str(exc)` with a generic summary error string.
- Added structured logger metadata with provider, webhook record id, target type, and exception class only.
- Preserved webhook persistence, status mapping, duplicate handling, and visit/payment integration flow.

Validation run:

- `python -m py_compile backend\app\services\payment_webhook.py`
  - result: passed
- `python -m pytest backend\tests\unit\test_payment_webhook_service.py backend\tests\unit\test_payment_webhook_api_service.py backend\tests\unit\test_payment_webhook_api_repository.py backend\tests\unit\test_provider_webhook_service.py backend\tests\unit\test_payment_reconciliation_service.py backend\tests\integration\test_notification_catalog_slice3_legacy_webhooks.py backend\tests\integration\test_payment_init_e2e.py backend\tests\integration\test_e2e_payment_flow.py -q --tb=short --disable-warnings`
  - result: 35 passed, 1 warning
- `rg -n 'print\(' backend\app\services\payment_webhook.py`
  - result: no matches
- `rg -n 'Error processing webhook:|return \{"error": str\(|str\(e\)|str\(exc\)' backend\app\services\payment_webhook.py`
  - result: no matches

LightRAG evidence note:

- No new LightRAG readiness entry was appended for this routine narrow gate slice; no gate misroute or retrieval regression was observed.

## Task 26 Slice MCP Endpoint Evidence

Execution mode:

- selected mode: `gate`, then `gate_known_root_cause` with `backend/app/api/v1/endpoints/mcp.py`
- reason: mounted MCP/AI clinical endpoint leaked raw exception text in public HTTP 500 details and f-string exception logs
- risky domain: yes, AI/clinical support endpoint
- root cause known: selected after the broad Task 26 gate stopped without a first-touch file and repository search identified `mcp.py`
- command: `python scripts\agent_gate.py "Task 26 sanitize mounted MCP endpoint raw public exception leakage and f-string exception logging without changing AI clinical suggestion behavior auth guards routes or success payloads" --known-root-cause "backend/app/api/v1/endpoints/mcp.py"`

Initial boundaries:

- canonical anchor: `backend/app/api/v1/endpoints/mcp.py`
- first-touch files: `backend/app/api/v1/endpoints/mcp.py`
- validation target: compile, ruff, black, static leakage scan, direct endpoint smoke
- stop condition watched first: any required edit outside `mcp.py` or any change to routes, auth guards, success payload shapes, or AI clinical decision boundaries

Changed behavior:

- Replaced raw public `detail=str(e)` HTTP 500 responses with a generic `Internal server error`.
- Replaced f-string exception logs with structured action name plus exception class only.
- Removed raw exception text from ICD-10 fallback response messages while preserving the existing non-500 fallback shape.
- Preserved explicit `HTTPException` guard behavior for role/file/JSON validation paths so intended 403/400 responses are not converted to generic 500 responses.
- Applied same-file ruff mechanical typing fixes so changed-file lint stays clean.

Validation run:

- `python -m py_compile backend\app\api\v1\endpoints\mcp.py`
  - result: passed
- `python -m ruff check backend\app\api\v1\endpoints\mcp.py`
  - result: passed
- `python -m black --check backend\app\api\v1\endpoints\mcp.py`
  - result: passed
- `rg -n "str\(e\)|str\(exc\)|str\(mcp_error\)|detail=str\(|logger\.error\(f|logger\.warning\(f|print\(" backend\app\api\v1\endpoints\mcp.py`
  - result: no matches
- direct async endpoint smoke with monkeypatched MCP managers raising a marker exception
  - result: passed; HTTP 500 returned `Internal server error`, marker text did not leak to response or logs, ICD-10 fallback message did not include the marker, and a role guard still returned HTTP 403
- `python -m pytest backend\tests\test_security_middleware.py -q --tb=short --disable-warnings`
  - result: 24 passed, 1 warning
- `git diff --check`
  - result: passed; Git printed line-ending normalization warnings only

Scope note:

- Task 26 remains open. This slice hardens only the mounted MCP endpoint and does not claim all backend runtime leakage is gone.

## Task 26 Current Slice Evidence (2026-05-12 - EMR AI endpoint)

Execution mode:

- selected mode: `gate_known_root_cause`
- reason: narrow Task 26 runtime leak fix in the canonical EMR AI endpoint without changing draft-only clinical behavior
- risky domain: yes
- root cause known: yes
- command: `python scripts\agent_gate.py "Task 26 sanitize emr_ai endpoint public raw exception leakage without changing AI draft-only behavior route prefixes auth guards or success response shapes" --known-root-cause "backend/app/api/v1/endpoints/emr_ai.py"`

Initial boundaries:

- canonical anchor: `backend/app/api/v1/endpoints/emr_ai.py`
- first-touch files: `backend/app/api/v1/endpoints/emr_ai.py`
- validation target: compile, static no-match for public `str(e)` leakage, and direct endpoint smoke proving generic 500 redaction
- stop condition watched first: any needed change outside `emr_ai.py` or any change to AI approval semantics, route/auth behavior, or success response shapes

Gate result:

- The gate response misrouted the first-touch set toward unrelated frontend routing files even with the confirmed root-cause file supplied.
- Per `AGENTS.md`, execution continued as a narrow override limited to `backend/app/api/v1/endpoints/emr_ai.py`.

Changed behavior:

- Added a structured EMR AI endpoint helper that logs only the operation name and exception class for internal failures.
- Replaced raw public HTTP 500 details that included exception text across the EMR AI suggestion/validation handlers with a generic `Internal server error` response.
- Preserved AI draft/suggestion posture, existing `requires_doctor_confirmation` behavior, route prefixes, auth guards, and success payload shapes.

Validation run:

- `python -m py_compile backend\app\api\v1\endpoints\emr_ai.py`
  - result: passed
- `rg -n "detail=f.*str\(e\)|detail=str\(|logger\.error\(f|logger\.exception\(f|\{str\(e\)\}" backend\app\api\v1\endpoints\emr_ai.py`
  - result: no matches
- direct async endpoint smoke with a monkeypatched EMR AI service raising a marker exception
  - result: passed; HTTP 500 returned `Internal server error` and the marker text did not leak
- `git diff --check`
  - result: passed

Scope note:

- Task 26 remains open. This slice only hardens one confirmed EMR AI runtime surface and does not claim the broader backend leak audit is finished.

LightRAG evidence note:

- A new LightRAG readiness entry was not appended for this slice; the gate misroute was handled locally under the existing narrow-override rule and did not require a separate retrieval-quality evidence update.

## Task 26 Slice A Evidence

Execution mode:

- selected mode: `gate`, then `gate_known_root_cause`
- reason: backend runtime logging/public error leakage audit outside payment webhook
- risky domain: yes, auth/login endpoint
- root cause known: selected after repository search found raw debug prints in the canonical authentication login endpoint
- command: `python scripts\agent_gate.py "Task 26 remove raw print and public-sensitive debug logging from canonical authentication login endpoint while preserving 2FA behavior" --known-root-cause "backend/app/api/v1/endpoints/authentication.py"`

Initial boundaries:

- canonical anchor: `backend/app/api/v1/endpoints/authentication.py`
- first-touch files: `backend/app/api/v1/endpoints/authentication.py`
- validation target: compile, 2FA enforcement tests, static search for removed login debug prints
- stop condition watched first: any required change outside the canonical login endpoint

Changed behavior:

- Removed raw `print(...)` diagnostics from the canonical `/api/v1/authentication/login` endpoint.
- Stopped logging username, raw IP/User-Agent values, auth service object, full login result payload, and traceback text through print statements.
- Replaced the login endpoint public HTTP 500 detail that included raw exception text with a generic login failure message.
- Preserved the 2FA response contract and token behavior.

Validation run:

- `python -m py_compile backend\app\api\v1\endpoints\authentication.py`
  - result: passed
- `python -m pytest backend\tests\test_2fa_enforcement.py -q --tb=short --disable-warnings`
  - result: 7 passed, 1 warning
- static search for removed login debug strings and `print(...)` in `authentication.py`
  - result: no matches

Scope note:

- Task 26 remains pending because this was the first selected high-risk slice, not a repo-wide cleanup of every remaining raw public error detail.

## Task 25 Evidence

Execution mode:

- selected mode: `gate`, then `gate_known_root_cause` retry with `backend/alembic/env.py`
- reason: PostgreSQL/Alembic deployment readiness and database source-of-truth proof
- risky domain: yes
- root cause known: initially no; Alembic env became the confirmed anchor after the first gate missed it

Gate result:

- Initial gate failed before Task 25 because `ai/langgraph/scripts/agent_gate.py` was missing from `main`.
- Restored `agent_gate.py` from existing git history in a separate dev-brain commit.
- First Task 25 gate selected only ops packaging files.
- Retry with `--known-root-cause backend/alembic/env.py` returned `gate_misroute: yes` and `override_used: yes`.
- Narrow override was used only for plan/status/testing/deployment docs because the plan explicitly allowed deployment/testing docs when the disposable PostgreSQL proof was blocked.

Validation run:

- `python -m py_compile backend\alembic\env.py`
  - result: passed
- `python -m alembic heads --verbose`
  - result: passed; single head `0022_service_audit_log`
- `python -m alembic branches --verbose`
  - result: passed; no branch split reported
- `python -m alembic history -r base:head`
  - result: passed; linear chain from `0001_baseline` to `0022_service_audit_log`
- `Test-NetConnection localhost -Port 55432`
  - result: failed; staging PostgreSQL port closed
- Docker/Compose availability check
  - result: failed; Docker command unavailable
- `psql` availability check
  - result: failed; `psql` command unavailable
- Disposable database proof on reachable local PostgreSQL `5432`
  - result: blocked before migrations; configured role lacks `CREATEDB`, no throwaway database was created

Task result:

- Alembic revision graph is verified as linear with a single current head.
- Clean online `alembic upgrade head` is still not proven in this local environment.
- The blocker is now documented in testing/deployment/security docs without claiming production readiness.

## Task 24 Evidence

Execution mode:

- selected mode: `gate_known_root_cause`
- reason: patient-facing role screen displayed mock appointment and lab-result data as real patient data
- risky domain: yes
- root cause known: yes
- command: `python scripts\agent_gate.py "Task 24 fix one verified user-visible role-screen friction: PatientPanel shows mock appointments and lab results as real patient data; replace with honest empty state without inventing backend API" --known-root-cause "frontend/src/pages/PatientPanel.jsx"`

Initial boundaries:

- canonical anchor: `frontend/src/pages/PatientPanel.jsx`
- first-touch files: `frontend/src/pages/PatientPanel.jsx`
- validation target: frontend production build plus static proof that mock patient data was removed
- stop condition watched first: any required backend/API contract or route ownership change

Changed behavior:

- Removed fake `/patient` appointment and lab-result arrays from `PatientPanel`.
- Removed the fake loading delay used only to make mock data look like an API response.
- Replaced false patient data with honest empty states for appointments and results.
- Disabled the patient-panel appointment action until real patient data/workflow is connected, so it no longer presents as a working primary action.
- Did not invent a new backend API contract.

Validation run:

- `npm.cmd run build` from `frontend/`
  - result: passed
  - warnings: existing dynamic/static `errorHandler.js` import warning and large chunk warnings
- `rg -n "Кардиолог|Дерматолог|Анализ крови|ЭКГ|2025-09|2025-08|setTimeout|setAppointments|setResults|Skeleton" frontend\src\pages\PatientPanel.jsx`
  - result: no matches

LightRAG evidence note:

- No new LightRAG readiness entry was appended for this routine narrow gate slice; no gate misroute or retrieval regression was observed.
