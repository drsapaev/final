# Clinic Routing Proof Phase

Date: 2026-04-07
Host: Windows pilot host
Runtime: `http://192.168.1.18:18080`
Scope: live browser proof for canonical router, legacy redirects, role-home routing, visible navigation parity, and post-fix rerun of route-content issues

## Purpose

Prove that the new routing contract works on the live frontend runtime, not only in `vitest` and `vite build`.

## Runtime Preconditions

- Live frontend reachable at `http://192.168.1.18:18080`
- Live backend reachable through same-origin runtime API
- App is already initialized

## Public and System Routes

Validated in a clean unauthenticated browser session.

| Input | Expected | Result | Status |
|---|---|---|---|
| `/` | landing page | stayed on `/` | PASS |
| `/login` | login page | stayed on `/login` | PASS |
| `/health` | public health surface | stayed on `/health`, health payload rendered, no access-denied block | PASS |
| `/setup` | initialized host should not reopen setup | redirected to `/login` | PASS |
| `/unauthorized` | system route | stayed on `/unauthorized` | PASS |
| `/forbidden` | system route | stayed on `/forbidden` | PASS |
| `/not-found` | system route | stayed on `/not-found` | PASS |

## Canonical Admin and Legacy Redirect Paths

Validated in a clean admin session.

### Canonical admin routes

| Input | Result | Status |
|---|---|---|
| `/admin` | `/admin` | PASS |
| `/admin/settings` | `/admin/settings` | PASS |
| `/admin/analytics` | `/admin/analytics` | PASS |
| `/admin/activation` | `/admin/activation` | PASS |

### Legacy redirects

| Input | Expected canonical path | Result | Status |
|---|---|---|---|
| `/registrar-panel` | `/registrar` | `/registrar` | PASS |
| `/doctor-panel` | `/doctor` | `/doctor` | PASS |
| `/cardiologist` | `/doctor/cardiology` | `/doctor/cardiology` | PASS |
| `/settings` | `/admin/settings` | `/admin/settings` | PASS |
| `/analytics` | `/admin/analytics` | `/admin/analytics` | PASS |
| `/payment/test` | `/internal-demo/payment-test` | `/internal-demo/payment-test` | PASS |

## Canonical Role-Home Behavior

Validated via direct login on the live router during the proof window on 2026-04-07.

| Role / account | Expected home | Result | Status |
|---|---|---|---|
| `admin` | `/admin` | `/admin` | PASS |
| `registrar@example.com` | `/registrar` | `/registrar` | PASS |
| `doctor@example.com` | `/doctor` | `/doctor` | PASS |
| `lab@example.com` | `/lab` | `/lab` | PASS |
| `cashier@example.com` | `/cashier` | `/cashier` | PASS |
| `cardio@example.com` | `/doctor/cardiology` | `/doctor/cardiology` | PASS |
| `derma@example.com` | `/doctor/dermatology` | `/doctor/dermatology` | PASS |
| `dentist@example.com` | `/doctor/dentistry` | `/doctor/dentistry` | PASS |

Notes:
- Specialist homes required proof against live login because backend specialist accounts currently authenticate as generic `Doctor` role.
- The canonical router now resolves those specialist accounts to canonical specialty homes on the frontend.
- A full serial rerun of every login in one browser session was limited by backend auth throttling (`5` logins per `300` seconds). The post-fix rerun reconfirmed admin/registrar/doctor behavior, and the previously recorded same-day live proofs for lab/cashier/specialists remain valid because the residual fixes in this pass did not modify role-home selectors or role-home guard logic.

## Visible Navigation Parity

Validated by direct inspection in admin and registrar shells.

Confirmed:
- no dead route was found in the inspected visible navigation
- no flat legacy admin links were exposed in production-visible navigation
- no `internal-demo` links were exposed in production-visible navigation
- no duplicate user-facing admin entries were found for the same canonical destination
- admin section buttons navigated to canonical admin paths:
  - `Настройки` -> `/admin/settings`
  - `Аналитика` -> `/admin/analytics`
  - `Активация` -> `/admin/activation`
  - `Аудит` -> `/admin/audit`
  - `Уведомления` -> `/admin/notifications`
  - `Telegram` -> `/admin/integrations/telegram`

## Setup Gating

Validated on the initialized live host:
- `/setup` redirected away to `/login`
- public and system routes remained reachable on the initialized host

Not executed on the live host:
- non-initialized `/setup` proof was not rerun against this pilot machine because the host is already initialized and resetting it would not be safe evidence collection

Coverage note:
- non-initialized setup precedence remains covered by automated routing tests and should be revalidated separately on a disposable contour when needed

## Route-Content Rerun

The three route-content issues found in the first proof pass were rerun after targeted fixes.

### `/health`

Result:
- public health output renders cleanly
- no `Доступ ограничен` block is rendered for unauthenticated users

Status:
- RESOLVED

### `/admin/audit`

Result:
- canonical route opens successfully
- audit table loads live records
- no `GET /api/v1/audit` `404` remains

Status:
- RESOLVED

### `/admin/integrations/telegram`

Result:
- canonical route opens successfully
- Telegram bot status loads from live backend contract
- Telegram templates load from live backend contract
- no template-load `404` remains
- the specific DOM prop warnings discovered in the first pass were removed from this screen

Status:
- RESOLVED

## Conclusion

Routing contract proof on the live host is green:
- canonical public, system, admin, and clinical routes are mounted correctly
- legacy redirects resolve to canonical destinations
- role-home routing is canonical for admin, registrar, doctor, lab, cashier, and specialist users
- visible navigation no longer exposes flat admin links or internal-demo links
- the three route-content issues found in the first proof pass are resolved

No routing-contract blocker remains in this proof packet.

## Recommended Next Step

Cut the routing-only commit and PR slice, and attach this packet as evidence for the live-router proof.
