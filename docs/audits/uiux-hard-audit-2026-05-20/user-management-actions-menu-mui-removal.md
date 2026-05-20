# UserManagement Actions Menu MUI Removal

Date: 2026-05-20

## Scope

Mode: `safe-patch` with `gate_known_root_cause` / narrow override.

First-touch runtime file:

- `frontend/src/components/admin/UserManagement.jsx`

Documentation evidence:

- `frontend/MUI_RUNTIME_INVENTORY.md`

## Shape Brief

- Role/workflow: Admin user lifecycle management on `/admin/advanced-users`.
- Primary action: open the per-user actions menu, then edit, activate/deactivate, or open delete confirmation.
- Risk level: admin-sensitive because the surface exposes user update/delete/deactivate actions and self-delete guardrails.
- Current drift source: the actions menu was the only remaining MUI island in `UserManagement.jsx`.
- Intended tone: quiet, clinical, keyboard-reachable, consistent with existing macOS UI primitives.
- Out of scope: no API, RBAC, route, user lifecycle, self-delete guardrail, role list, filter, modal, or table behavior changes.

## Changed

- Removed the `@mui/material` actions-menu import from `UserManagement.jsx`.
- Replaced the MUI `Menu`, `MenuItem`, `ListItemIcon`, `ListItemText`, `Divider`, and `IconButton` usage with:
  - existing `MacOSButton` for the trigger;
  - native `button` menu items;
  - `role="menu"` and `role="menuitem"` semantics;
  - Escape, outside-click, scroll, and resize close behavior.
- Preserved the existing action callbacks:
  - edit opens `UserModal`;
  - activate/deactivate calls `handleToggleUserStatus`;
  - delete opens the existing delete confirmation dialog.

## Validation

Commands and results:

- `cd C:\final\ai\langgraph; py -3 scripts\agent_gate.py ... --known-root-cause "frontend/src/components/admin/UserManagement.jsx"`: passed with narrow override; first-touch file approved.
- `cd frontend; npm.cmd run test:run -- src/routing/__tests__/routeOwnershipEnforcement.test.js`: passed, 2 tests.
- `cd frontend; npm.cmd run lint:check`: passed with 54 existing warnings, 0 errors; `UserManagement.jsx` a11y warnings removed.
- `cd frontend; npm.cmd run build`: passed.
- Static MUI search: `UserManagement.jsx` no longer matches `@mui|Mui`.
- Current MUI search count: 12 files.
- One-off authenticated browser smoke for `/admin/advanced-users`: passed with seeded Admin session, mocked user list, actions menu open, three menu items visible, Escape close, no horizontal overflow, no page errors.

Browser artifact:

- `output/playwright/user-management-actions-menu.png` (ignored generated artifact, not committed).

## Contract And Safety

- API request paths and payloads unchanged.
- User create/update/delete/deactivate code paths unchanged.
- Self-delete and deactivate fallback guardrails unchanged.
- Route owner remains `admin-advanced-users` / `admin.users`.
- No backend, schema, RBAC, notification, payment, queue, EMR, lab, Telegram, or AI behavior changed.

## Remaining Risk

The browser smoke uses a local QA harness and mocked API responses, so it proves route rendering and menu interaction, not backend authorization. Backend authorization remains covered by the existing backend/API guardrails outside this UI-only slice.

## Next Smallest Step

Continue one risky MUI island per PR. The remaining runtime MUI targets are payment, queue, clinical, Telegram/AI, and example-only files; each still needs its own gate/handoff and route-specific proof.
