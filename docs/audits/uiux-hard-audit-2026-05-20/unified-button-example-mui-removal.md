# UnifiedButton Example MUI Removal

Date: 2026-05-20

## Scope

Mode: `direct_execute`, example-only.

Runtime file:

- `frontend/src/components/examples/UnifiedButton.tsx`

Documentation evidence:

- `frontend/MUI_RUNTIME_INVENTORY.md`
- `docs/audits/uiux-hard-audit-2026-05-20/mui-example-only-policy.md`

## Shape Brief

- Surface: design-system example file, not an active clinic route.
- Primary action: keep `UnifiedButton` and `UnifiedButtonShowcase` available as reference examples.
- Risk level: low, because static source search found no active app callers.
- Drift source: the example still taught future agents to use `@mui/material`.
- Intended direction: macOS/native example that points toward the canonical clinic UI layer.
- Out of scope: runtime role panels, routes, backend, RBAC, queue, payment, clinical flows, Telegram, AI/MCP, and dependency removal.

## Changed

- Removed `@mui/material/Button`, `@mui/material/styles`, and MUI `useTheme` usage.
- Reimplemented the example with a native `button` and CSS variable based macOS styling.
- Preserved the exported names:
  - `UnifiedButton`
  - `UnifiedButtonShowcase`
- Preserved example props for common docs usage:
  - `variant`
  - `medical`
  - `loading`
  - `disabled`
  - `size`

## Validation

Commands and results:

- `cd frontend; npm.cmd run test:run -- src/routing/__tests__/routeOwnershipEnforcement.test.js`: passed, 2 tests.
- `cd frontend; npm.cmd run lint:check`: passed with 54 existing warnings, 0 errors.
- `cd frontend; npm.cmd run build`: passed.
- Static MUI search: `UnifiedButton.tsx` no longer matches `@mui|Mui`.
- Current MUI search count: 11 files.

## Contract And Safety

- No runtime route imports this file.
- No app page, role panel, API client, RBAC, backend, notification, payment, queue, clinical, Telegram, or AI/MCP code changed.
- No package dependency was removed; MUI dependency removal remains blocked while runtime imports remain.

## Remaining Risk

Historical design-system docs still mention `UnifiedButton` as an example component. The export name remains available, but the docs may still describe older MUI-specific internals. Broad docs cleanup should be handled separately.

## Next Smallest Step

Convert `frontend/src/components/examples/UnifiedCard.tsx` to a macOS/native example in a separate PR, then reassess the remaining runtime MUI count.
