# AdminPanel Deep Audit Summary

Date: 2026-06-01
Mode: audit-only

## Verdict

AdminPanel is functional in many core routes, but the admin architecture is not yet clean. The biggest risk is not visual polish; it is route ownership drift. Several routes render successfully while showing the wrong functional content because direct pathname routes and aggregator `?section=` state are not aligned.

## Top Findings

1. P0: `/admin/reports` is broken by `GET /api/v1/reports/daily-summary` returning 500.
2. P1: Direct contextual settings routes render generic settings instead of route-specific screens.
3. P1: `/admin/telegram-settings` opens Bot Manager by default, not settings.
4. P1: `/admin/file-management` shows an empty file manager while critical file API calls return 422/401.
5. P1: User management, Telegram, notifications, settings, and analytics have duplicate or parallel route/component families.
6. P2: Overview navigation group contains operational/integration tooling and is overloaded.
7. P2: `AdminPanel.jsx` remains a broad route switch plus implementation container.
8. P2: Shared component warnings exist in Services and GraphQL routes.
9. P3: Some routes lack clear top-level heading evidence.

## P0/P1/P2/P3 Backlog

### P0

- Fix `/admin/reports` daily summary failure so Admin Reports does not default to an error screen.

### P1

- Align direct contextual routes with their intended aggregator sections:
  - `/admin/ai-settings`
  - `/admin/security`
  - `/admin/benefit-settings`
  - `/admin/wizard-settings`
  - `/admin/payment-providers`
  - `/admin/clinic-settings`
  - `/admin/queue-settings`
  - `/admin/display-settings`
- Make `/admin/telegram-settings` open Telegram settings, or rename/redirect it if Bot Manager is canonical.
- Fix `/admin/file-management` 422/401 ambiguity.
- Decide canonical user-management route/component.
- Decide canonical Telegram and notification route map.

### P2

- Move integration/tooling routes out of "Overview" or rename the section to match reality.
- Add route contract tests for every AdminPanel-owned contextual route.
- Resolve `MacOSTable` prop warning in `/admin/services`.
- Resolve React unknown prop warning in `/admin/graphql-explorer`.

### P3

- Add clear `h1/h2` heading semantics where route heading extraction is weak.
- Improve density/scanability after functional routing is fixed.

## Recommended Fix Slices

### PR-ADMIN-1: Route state adapter

Scope:

- `frontend/src/pages/AdminPanel.jsx`
- aggregator props only if needed
- tests for route -> section mapping

Goal:

Direct admin contextual routes must render their intended subcomponent without requiring `?section=...`.

Validation:

- Vitest route/section tests.
- Browser smoke for `/admin/security`, `/admin/payment-providers`, `/admin/queue-settings`, `/admin/display-settings`, `/admin/ai-settings`.

### PR-ADMIN-2: Reports empty/low-data hardening

Scope:

- Backend reports endpoint and/or frontend report fallback, depending on root cause.

Goal:

`/admin/reports` must render an understandable no-data report state instead of a 500-backed error.

### PR-ADMIN-3: File manager auth/params contract

Scope:

- File manager frontend API calls and backend file endpoint expectations.

Goal:

Admin file management must distinguish no files from unauthorized/malformed request.

### PR-ADMIN-4: Canonical admin route map cleanup

Scope:

- Docs/tests first, then one family per PR:
  - users
  - Telegram
  - notifications
  - settings/security

Goal:

Duplicate families become explicit aliases, tabs, or separate route owners with tests.

### PR-ADMIN-5: Navigation grouping pass

Scope:

- `routeRegistry.js`
- route selector tests

Goal:

Admin sidebar groups reflect business ownership: Overview vs Management vs System/Integrations/Operations.

## Audit Quality Gate

Completed:

- Static route registry review.
- AdminPanel render switch review.
- Admin components inventory.
- Browser route pass under Admin auth.
- Mobile sample on representative routes.

Not completed in this docs-only PR:

- No runtime fixes.
- No destructive action QA.
- No full four-viewport sweep for every route.
- No backend trace of report/file failures beyond browser-observed HTTP status.

## Next Smallest Patch

Implement `PR-ADMIN-1: Route state adapter`. It has the highest safety-to-value ratio because it fixes false-success routes without changing admin data contracts, RBAC, or backend behavior.
