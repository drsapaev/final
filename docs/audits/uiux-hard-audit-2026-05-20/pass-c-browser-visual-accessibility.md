# UI/UX Hard Audit 2026-05-20 - Pass C: Browser Visual/Accessibility QA

## Scope

Independent browser/runtime audit pass focused on visual QA, accessibility smoke checks, and route reachability. This pass did not use findings from Pass A or Pass B before completion.

Audit mode: report-only. No runtime, backend, frontend, API, RBAC, route, database, notification, or Telegram behavior was changed.

Primary skill: `clinic-ui-ux-master`.

References loaded:

- `.agents/skills/clinic-ui-ux-master/references/visual-qa-playbook.md`
- `.agents/skills/clinic-ui-ux-master/references/accessibility-hardening.md`
- `.agents/skills/clinic-ui-ux-master/references/runtime-performance-qa.md`
- `.agents/skills/clinic-ui-ux-master/references/react-performance-ux.md`
- `.agents/skills/clinic-ui-ux-master/references/report-templates.md`

Local runtime assumptions checked:

- frontend: `http://127.0.0.1:5173`
- backend port: `127.0.0.1:18000`
- backend `/health` endpoint returned `404`, so the port was live but `/health` is not a valid health endpoint in this checkout.

Screenshots and browser summaries were written to a temporary local evidence directory:

- `C:\Users\DrSapaev\AppData\Local\Temp\uiux-hard-audit-2026-05-20`
- `C:\Users\DrSapaev\AppData\Local\Temp\uiux-hard-audit-2026-05-20\browser-summary.json`
- `C:\Users\DrSapaev\AppData\Local\Temp\uiux-hard-audit-2026-05-20\browser-summary.tsv`

The screenshot directory is not committed because this request asked for report artifacts only.

## Browser Matrix

Routes attempted:

- `/admin`
- `/admin/appointments`
- `/admin/audit`
- `/admin/user-select`
- `/registrar`
- `/doctor`
- `/cashier`
- `/lab`
- `/patient`
- `/queue/join`
- `/payment/success`
- `/payment/cancel`
- `/doctor/cardiology`
- `/doctor/dermatology`
- `/doctor/dentistry`

Viewports:

- `375x812`
- `768x1024`
- `1280x800`
- `1920x1080`

Checks recorded:

- final route after navigation
- horizontal overflow
- focusable element count
- unnamed button count
- unnamed icon-only button count
- `role="alert"` count
- live region count
- visible focus candidate count
- console error count
- failed network response count
- screenshot path

## Route/Viewport Results

### Protected route behavior

The following protected routes redirected to `/login` at every tested viewport:

- `/admin`
- `/admin/appointments`
- `/admin/audit`
- `/admin/user-select`
- `/registrar`
- `/doctor`
- `/cashier`
- `/lab`
- `/patient`
- `/doctor/cardiology`
- `/doctor/dermatology`
- `/doctor/dentistry`

Observed login redirect state across protected routes:

- horizontal overflow: none detected
- console errors: none detected
- failed network responses: none detected
- unnamed icon buttons: 0
- focusable controls: 9
- live regions: 1
- alerts: 0

Interpretation:

The unauthenticated redirect path is visually stable in the tested viewport set. This does not certify the protected role panels themselves because authenticated session data was not available.

### `/queue/join`

Observed state:

- final route: `/queue/join`
- horizontal overflow: none detected in all tested viewports
- console errors: 0
- failed network responses: 0
- focusable controls: 2
- unnamed buttons: 0
- unnamed icon-only buttons: 0
- alerts: 1
- live regions: 2

Visible state summary:

- QR-code context was missing.
- The page rendered an error/recovery state telling the user that a QR code was not found and offering retry/home actions.

Interpretation:

The public missing-QR state did not break layout in the tested viewports and exposes alert/live semantics. A full happy-path queue join flow still requires valid clinic QR context or seeded data.

### `/payment/success`

Observed state:

- final route: `/payment/success`
- horizontal overflow: none detected in all tested viewports
- console errors: 0
- failed network responses: 0
- focusable controls: 1
- unnamed buttons: 0
- unnamed icon-only buttons: 0
- alerts: 1
- live regions: 1

Visible state summary:

- No payment ID was provided.
- The page rendered a "payment not found / missing payment ID" recovery state and a home action.

Interpretation:

The missing-payment success route is semantically stronger than most public recovery states because it exposes alert/live behavior and did not overflow.

### `/payment/cancel`

Observed state:

- final route: `/payment/cancel`
- horizontal overflow: none detected in all tested viewports
- console errors: 0
- failed network responses: 0
- focusable controls: 3
- unnamed buttons: 0
- unnamed icon-only buttons: 0
- alerts: 0
- live regions: 1

Visible state summary:

- The page explained that payment was not completed and offered recovery guidance/actions.

Interpretation:

The page is visually stable in the tested viewport set, but the canceled-payment state did not expose an alert region in the browser smoke check. This should be treated as an accessibility and payment-confidence improvement candidate.

## Findings

### P1 - Protected role panels could not be visually certified

Evidence:

- All protected role routes redirected to `/login` without safe test credentials or seeded session data.
- The unauthenticated redirect was stable, but the actual Admin, Registrar, Doctor, Cashier, Lab, Patient, and specialty role panels were not visible in browser QA.

Impact:

The audit cannot honestly claim that protected role workflows are free of overlap, clipping, focus loss, keyboard traps, or mobile usability issues.

Safe direction:

Create or document a safe authenticated QA harness for local role sessions before doing visual sign-off on role panels.

### P2 - `/payment/cancel` needs stronger semantic status treatment

Evidence:

- Browser smoke result: `alerts=0`, `live=1` for `/payment/cancel`.
- Route is payment-related and exposes recovery actions.

Impact:

A canceled payment is a high-trust state. It should be announced consistently and should make recovery actions unmistakable.

Safe direction:

Add semantic status/alert treatment and verify keyboard order. Keep payment logic untouched.

### P2 - Public queue happy path was blocked by missing QR context

Evidence:

- `/queue/join` rendered a missing-QR recovery state in all tested viewports.

Impact:

The missing-QR state is stable, but this pass did not validate specialist selection, patient form completion, successful join, or waiting states in the browser.

Safe direction:

Add a local QA fixture or documented QR test link for queue happy-path visual QA.

### P3 - Login redirect path is stable but should not be overinterpreted

Evidence:

- No overflow, no console errors, no failed network responses, and no unnamed icon buttons were found on login redirects across protected routes.

Impact:

This is useful evidence for the unauthenticated shell only. It should not be used as a substitute for role panel QA.

Safe direction:

Keep login redirect evidence in the QA matrix but separate it from authenticated role evidence.

## Route/Viewport Matrix Summary

| Route family | Viewports tested | Result |
| --- | ---: | --- |
| Protected role routes | 4 each | redirected to `/login`; role content blocked by auth |
| `/queue/join` | 4 | stable missing-QR recovery state; no overflow/errors |
| `/payment/success` | 4 | stable missing-payment recovery state; no overflow/errors |
| `/payment/cancel` | 4 | stable visual layout; semantic alert gap |

## Validation Plan

For follow-up browser QA:

- provide safe local auth/session setup for Admin, Registrar, Doctor, Cashier, Lab, Patient, and specialty roles
- rerun the route matrix at the same four viewports
- capture screenshots for actual role content, not only login redirects
- record keyboard tab order and visible focus around primary workflows
- include empty/loading/error/forbidden states where role data can be seeded
- keep screenshots as artifacts for PRs that change UI

## Stop Conditions

Stop and mark a route `blocked` instead of guessing if:

- authentication/session data is missing
- seeded clinical/payment/queue data is not available
- browser route redirects away from the target surface
- a route requires live external services, production secrets, or live database state
- a visual issue cannot be reproduced with a screenshot or concrete viewport
