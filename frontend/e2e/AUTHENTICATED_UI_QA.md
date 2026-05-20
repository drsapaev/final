# Authenticated UI QA Harness

This Playwright harness is for local UI/UX audit evidence only. It does not change production auth, RBAC, backend data, or route contracts.

## What It Does

- Seeds `localStorage` with a short-lived QA JWT-shaped token and role profile before the app loads.
- Mocks local `/api/v1/*` requests inside Playwright so protected role panels can render without production secrets or a live database.
- Keeps route access checks active: protected routes must still pass the existing frontend route guard for the seeded role.
- Captures screenshots for Admin, Registrar, Doctor, Cashier, Lab, and Patient payment entry surfaces.
- Captures specialty doctor panel screenshots for Cardiology, Dermatology, and Dentistry without production credentials.

## Command

```powershell
cd frontend
npx playwright test e2e/authenticated-role-smoke.spec.js --project=chromium --reporter=line
npx playwright test e2e/authenticated-rbac-deny.spec.js --project=chromium --reporter=line
```

## Role Coverage

| Role | Route | Route ID |
| --- | --- | --- |
| Admin | `/admin` | `admin-dashboard` |
| Registrar | `/registrar` | `registrar-home` |
| Doctor | `/doctor` | `doctor-home` |
| Doctor | `/doctor/cardiology` | `doctor-cardiology` |
| Doctor | `/doctor/dermatology` | `doctor-dermatology` |
| Doctor | `/doctor/dentistry` | `doctor-dentistry` |
| Cashier | `/cashier` | `cashier-home` |
| Lab | `/lab` | `lab-home` |
| Patient | `/patient/payments` | `patient-payment-entry` |

`/patient` is currently staff-scoped in the route registry, so the patient QA surface uses the authenticated patient payment entry route.

## Negative RBAC Coverage

These checks seed an authenticated session with a real but wrong role and verify that the route guard sends the user to `/forbidden` instead of rendering the protected app shell or falling back to `/login`.

| Seeded Role | Denied Route | Denied Route ID |
| --- | --- | --- |
| Cashier | `/admin` | `admin-dashboard` |
| Doctor | `/cashier` | `cashier-home` |
| Cashier | `/lab` | `lab-home` |
| Registrar | `/doctor/cardiology` | `doctor-cardiology` |

## Boundaries

- Do not use this harness to bypass backend contract tests.
- Do not copy the seeded token/profile into production code.
- Do not weaken `RouteAccessBoundary`, `RoleGate`, or backend RBAC because this harness exists.
- For business-flow verification, use live QA credentials or dedicated backend fixtures in a separate plan.
- Keep negative RBAC browser checks in their own focused PR so this smoke harness remains a positive render check.
- Negative RBAC smoke must not be used as backend authorization proof; it only verifies frontend route-denial UX.
