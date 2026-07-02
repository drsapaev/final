# Initial Bundle Target Decision

Date: 2026-05-22

Scope: PR-PERF-1 report-only decision for the next runtime bundle slice. No
frontend runtime code, tests, route registry, backend, API, RBAC, payment,
queue, EMR, lab, Telegram backend, Vite config, CI, dependencies, or deployment
behavior changed in this PR.

## Cycle Status

- [x] Fresh `origin/main` branch used for target selection.
- [x] Fresh frontend production build completed.
- [x] Existing bundle analyzer run completed.
- [x] `App.jsx` and route registry inspected.
- [x] Current largest JS assets reviewed.
- [x] One safe target selected for the next runtime PR.
- [ ] Next PR: implement only the selected target and compare bundle output.

## Evidence

Fresh build command:

```powershell
cd frontend
npm.cmd run build
npm.cmd run analyze
```

Result:

- Build passed.
- Bundle analyzer completed.
- `dist` size: `6.15 MB`.
- Largest JS assets remain:
  - `index-BlAk62rR.js`: `1423.9 KB`
  - `heic2any-BadZ30Qs.js`: `1320.5 KB`
  - `AdminPanel-CsIG3n58.js`: `971.8 KB`

Source inspection:

- `frontend/src/App.jsx` imports lazy route pages, renders the route registry,
  and also owns the Telegram Mini App patient shell.
- Telegram Mini App code starts near `const MINI_APP_I18N` and includes:
  language dictionaries, section parsing, auth payload helpers, API calls,
  patient-facing panels, form handlers, report download handling, and inline
  style constants.
- The route registry maps `/telegram/mini-app/patient` to
  `TelegramMiniAppPatientShell`.
- Existing guardrail tests read Mini App snippets directly from `App.jsx`, so
  the runtime PR must update those tests to read the new module.

## Selected Target For PR-PERF-2

Extract the Telegram Mini App patient shell from `frontend/src/App.jsx` into a
lazy-loaded route module, for example:

```text
frontend/src/pages/TelegramMiniAppPatientShell.jsx
```

Expected implementation shape:

- Move Mini App dictionaries, helpers, component, and style constants into the
  new route module.
- Keep `App.jsx` route rendering, `RouteRenderer`, `AppShell`, providers, and
  route registry behavior unchanged.
- Replace the inline component in `App.jsx` with:
  `const TelegramMiniAppPatientShell = lazy(() => import('./pages/TelegramMiniAppPatientShell.jsx'));`
- Preserve the route registry component key `TelegramMiniAppPatientShell`.
- Update Mini App guardrail tests to inspect the new module instead of
  `App.jsx`.

## Why This Target Is Safer Than Alternatives

- It targets one direct route surface: `/telegram/mini-app/patient`.
- It removes route-specific code from the initial app module without changing
  backend endpoints, request payloads, route path, RBAC, or clinic staff flows.
- It avoids casual `AdminPanel` splitting now that `AdminPanel-*` is below the
  previous local review target.
- It avoids touching `heic2any-*`, which is already isolated as a lazy HEIC
  conversion chunk and needs a dedicated upload-flow plan.
- It avoids changing `chunkSizeWarningLimit`.

## Required PR-PERF-2 Validation

- [ ] `cd frontend; npm.cmd run test:run -- src/__tests__/telegramMiniApp*.test.js`
- [ ] `cd frontend; npm.cmd run test:run -- src/routing/__tests__/routeOwnershipEnforcement.test.js`
- [ ] `cd frontend; npm.cmd run audit:no-mui-runtime`
- [ ] `cd frontend; npm.cmd run lint:check`
- [ ] `cd frontend; npm.cmd run build`
- [ ] Compare top JS assets before/after and record whether `index-*` moved
  down.
- [ ] Browser smoke `/telegram/mini-app/patient` at a public/error state if the
  local backend is unavailable; do not fabricate authenticated Telegram data.
- [ ] `git diff --check`

## Stop Conditions For PR-PERF-2

- Stop if extraction changes any `/telegram/mini-app/*` endpoint string,
  payload key, handled error status, report download response type, or route
  path.
- Stop if the slice requires backend changes, Telegram bot changes, database
  migrations, production secrets, auth weakening, or route registry contract
  changes.
- Stop if tests need to be weakened instead of retargeted to the new source
  module.
- Stop if bundle output shows no measurable `index-*` reduction and the change
  becomes only code motion without performance value.
