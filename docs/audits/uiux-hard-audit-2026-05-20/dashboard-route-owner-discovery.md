# Dashboard Route Owner Discovery

Date: 2026-05-20

## Scope

Audit-only route ownership check for:

- `frontend/src/components/dashboard/Dashboard.jsx`
- `frontend/src/components/dashboard/index.js`

No runtime code was changed in this PR.

## Why This Exists

The third UI/UX performance and MUI debt cycle left
`frontend/src/components/dashboard/Dashboard.jsx` in the shared/admin-sensitive
MUI bucket because it imports MUI components and icons, but it did not have a
confirmed route surface.

Before deleting, archiving, or migrating that component, route ownership must be
proven from source.

## Commands

```powershell
rg -n "components/dashboard" frontend\src docs frontend\MUI_RUNTIME_INVENTORY.md
rg -n "dashboard/Dashboard|dashboard/index" frontend\src docs frontend\MUI_RUNTIME_INVENTORY.md
rg -n "<Dashboard\b|import\s+Dashboard|Dashboard\s+from" frontend\src
rg -n "component: 'Dashboard'" frontend\src\routing frontend\src
rg -n 'component: "Dashboard"' frontend\src\routing frontend\src
rg -n "Dashboard" frontend\src\routing frontend\src\App.jsx frontend\src\components\layout frontend\src\pages
```

## Evidence

### Route Registry

`frontend/src/routing/routeRegistry.js` does not register a route with:

```text
component: 'Dashboard'
```

or:

```text
component: "Dashboard"
```

Dashboard-like route IDs currently resolve to other components, especially
`AdminPanel`, `AnalyticsPage`, role panels, or demo pages.

### App Route Component Map

`frontend/src/App.jsx` defines `ROUTE_COMPONENTS`, but it does not lazy-load or
map `frontend/src/components/dashboard/Dashboard.jsx`.

Relevant active mappings include:

- `AdminPanel`
- `AnalyticsPage`
- `UserManagement`
- `MacOSDemoPage`
- `PaymentTest`

No `Dashboard` entry is present in `ROUTE_COMPONENTS`.

### Caller Search

Static caller search found no active app import of:

- `frontend/src/components/dashboard/Dashboard.jsx`
- `frontend/src/components/dashboard/index.js`
- `<Dashboard />`

The search did find unrelated local dashboard render functions in files such as
`AdminPanel.jsx`, `DentistPanelUnified.jsx`, and `MediLabDemo.jsx`; these are
not imports or callers of `components/dashboard/Dashboard.jsx`.

### Barrel Export

`frontend/src/components/dashboard/index.js` only re-exports:

```javascript
export { default as Dashboard } from './Dashboard.jsx';
```

No active caller of that barrel was found.

## Decision

`frontend/src/components/dashboard/Dashboard.jsx` is currently an unowned stale
dashboard component from the route graph perspective.

It should not be migrated as a runtime UI surface because there is no active
route/browser proof to validate. It is a better candidate for a dedicated
archive/delete PR after one more clean search from fresh `origin/main`.

## Next Smallest PR

Create a separate removal PR:

- delete `frontend/src/components/dashboard/Dashboard.jsx`;
- delete `frontend/src/components/dashboard/index.js` if it remains caller-free;
- update `frontend/MUI_RUNTIME_INVENTORY.md`;
- run frontend build and MUI inventory proof.

## Stop Conditions For Removal

Stop before deletion if any of these become true:

- `Dashboard.jsx` gains an active route registry component entry;
- `App.jsx` starts importing/mapping `Dashboard`;
- another component imports `components/dashboard` or `Dashboard.jsx`;
- a test fixture or docs build requires the barrel export;
- deletion breaks frontend build.
