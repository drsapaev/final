# Dashboard Stale Component Removal

Date: 2026-05-20

## Scope

Removed the stale dashboard MUI island after the route-owner discovery in:

- `docs/audits/uiux-hard-audit-2026-05-20/dashboard-route-owner-discovery.md`

Deleted files:

- `frontend/src/components/dashboard/Dashboard.jsx`
- `frontend/src/components/dashboard/index.js`

## Why

The discovery PR found no active route registry entry, `ROUTE_COMPONENTS` entry,
or caller for `frontend/src/components/dashboard/Dashboard.jsx`.

Keeping the stale component preserved a dead MUI island and made the MUI debt
inventory noisier without improving any reachable dashboard route.

## Behavior

No active route, RBAC, API, payment, queue, clinical, Telegram, notification, or
backend behavior is intended to change.

Dashboard-like active surfaces still use their existing owners:

- `frontend/src/pages/AdminPanel.jsx`
- `frontend/src/pages/AnalyticsPage.jsx`
- role-specific panel dashboard sections
- internal demo pages

## Validation

Required validation for this PR:

```powershell
rg -n "components/dashboard|dashboard/Dashboard|dashboard/index|<Dashboard\b|import\s+Dashboard|\bDashboard\s+from" frontend\src
rg -n "component: 'Dashboard'" frontend\src\routing frontend\src\App.jsx
rg -n 'component: "Dashboard"' frontend\src\routing frontend\src\App.jsx
cd frontend
npm.cmd run test:run -- src/routing/__tests__/routeOwnershipEnforcement.test.js
npm.cmd run lint:check
npm.cmd run build
cd ..
rg -l "@mui|Mui" frontend\src\pages frontend\src\components
git diff --check
```

Expected MUI inventory after deletion: 13 files.

## Next Smallest Step

The next runtime MUI candidate is no longer generic dashboard cleanup. Future
work should use the existing gated handoffs:

- admin user actions menu;
- payment;
- queue;
- clinical-heavy panels;
- Telegram/AI.
