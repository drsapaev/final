# Authenticated UI QA Harness

This Playwright harness is for local UI/UX audit evidence only. It does not change production auth, RBAC, backend data, or route contracts.

## What It Does

- Seeds `localStorage` with a short-lived QA JWT-shaped token and role profile before the app loads.
- Mocks local `/api/v1/*` requests inside Playwright so protected role panels can render without production secrets or a live database.
- Keeps route access checks active: protected routes must still pass the existing frontend route guard for the seeded role.
- Captures screenshots for Admin, Registrar, Doctor, Cashier, Lab, and Patient payment entry surfaces.

## Command

```powershell
cd frontend
npx playwright test e2e/authenticated-role-smoke.spec.js --project=chromium --reporter=line
```

## Role Coverage

| Role | Route | Route ID |
| --- | --- | --- |
| Admin | `/admin` | `admin-dashboard` |
| Registrar | `/registrar` | `registrar-home` |
| Doctor | `/doctor` | `doctor-home` |
| Cashier | `/cashier` | `cashier-home` |
| Lab | `/lab` | `lab-home` |
| Patient | `/patient/payments` | `patient-payment-entry` |

`/patient` is currently staff-scoped in the route registry, so the patient QA surface uses the authenticated patient payment entry route.

## Boundaries

- Do not use this harness to bypass backend contract tests.
- Do not copy the seeded token/profile into production code.
- Do not weaken `RouteAccessBoundary`, `RoleGate`, or backend RBAC because this harness exists.
- For business-flow verification, use live QA credentials or dedicated backend fixtures in a separate plan.
