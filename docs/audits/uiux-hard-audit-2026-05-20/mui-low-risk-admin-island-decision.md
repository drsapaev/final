# PR-MUI-2 Low-Risk Admin MUI Island Decision

Date: 2026-05-20

## Scope

Decision-only review for the third-cycle MUI backlog item:

> Migrate exactly one low-risk admin MUI island only if a dedicated first-touch
> file and browser proof are available.

No runtime code was changed in this decision slice.

## References Inspected

- `AGENTS.md`
- `.cursorrules`
- `frontend/DESIGN_SYSTEM.md`
- `frontend/THEME_SYSTEM_GUIDE.md`
- `frontend/MUI_RUNTIME_INVENTORY.md`
- `frontend/src/components/ui/macos/index.js`
- `frontend/src/components/admin/UserManagement.jsx`
- `frontend/src/components/dashboard/Dashboard.jsx`

## Fresh Inventory

Command:

```powershell
rg -l "@mui|Mui" frontend\src\pages frontend\src\components
```

The remaining candidate files from the shared/admin-sensitive bucket are:

- `frontend/src/components/admin/UserManagement.jsx`
- `frontend/src/components/dashboard/Dashboard.jsx`

## Candidate Review

### `UserManagement.jsx`

Decision: do not migrate in PR-MUI-2.

Reason:

- The remaining MUI island is the admin actions menu.
- The file owns user creation, update, activation/deactivation, deletion, and
  self-delete guardrail presentation.
- Even a visual-only menu migration can accidentally alter keyboard behavior,
  destructive-action affordance, focus handling, or account action ordering.
- This needs a dedicated admin/RBAC proof slice, not the generic low-risk MUI
  cleanup slot.

### `Dashboard.jsx`

Decision: do not migrate in PR-MUI-2.

Reason:

- The file is a self-contained dashboard component with MUI summary/list UI.
- Static search did not find an active route or caller for this component in
  `frontend/src`.
- Because there is no confirmed route surface, the required browser proof is
  not available for this PR.
- Migrating an apparently unmounted component would reduce a static MUI count
  but would not prove runtime UI quality.

## Result

No low-risk admin MUI island satisfies both requirements for PR-MUI-2:

1. dedicated first-touch file;
2. route/browser proof for the affected UI.

Therefore PR-MUI-2 is intentionally decision-only. Runtime MUI migration should
resume only through one of these narrower future slices:

- Admin user actions menu migration with authenticated admin browser proof and
  RBAC/destructive-action validation.
- Dashboard consolidation or removal decision if `Dashboard.jsx` is confirmed
  unused.
- A dedicated route-owner discovery PR if the dashboard component has an
  indirect caller that static search did not expose.

## Stop Conditions Triggered

- Browser/auth proof is required but not available for `Dashboard.jsx`.
- `UserManagement.jsx` touches admin account action semantics and destructive
  action affordance.

## Next Smallest Step

Proceed to PR-MUI-3: decide the example-only MUI policy for
`frontend/src/components/examples/UnifiedButton.tsx` and
`frontend/src/components/examples/UnifiedCard.tsx` without changing runtime UI.
