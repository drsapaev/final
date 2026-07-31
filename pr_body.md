## Summary

- Added `aria-invalid` attribute to custom form wrappers (`Input.tsx`, `Textarea.tsx`, `Select.tsx`) in the MacOS UI kit.
- The `aria-invalid` attribute is dynamically tied to the presence of the `error` prop.
- Improves accessibility by informing assistive technologies (like screen readers) of the invalid state when a form field fails validation.

## Cyclic Execution Evidence

- Fresh main sync: yes
- Clean workspace: yes
- Branch: palette-aria-invalid-fix
- Scope gate: passed
- Red-check handling: resolved

## Contract Impact

not applicable - UI component accessibility change only. No API contracts modified.

## RBAC / Permissions

not applicable - No permission or RBAC logic changed.

## Notification / Realtime

not applicable - No notification or realtime logic changed.

## Frontend Resilience

- Empty data proof: not applicable
- Partial data proof: not applicable
- Forbidden secondary path behavior: not applicable
- Missing draft/resource behavior: not applicable
- Stale route/deep-link behavior: not applicable

## Scope Gate

- Allowed paths: frontend/src/components/ui/macos/
- Denied paths: none
- Migration/docs/test impact: local tests passed
- Rollback note: trivial to revert

## DevBrain Memory Impact

- [x] no durable memory update needed
- [ ] PROJECT_MEMORY updated
- [ ] DEVBRAIN_STATUS updated
- [ ] AI Factory dossier/log/patch updated
- [ ] agent_gate routing rule updated
- [ ] indexes/artifacts refreshed locally
- [ ] regression matrix run

## Validation

- Targeted tests or smoke run: `cd frontend && pnpm run test:run src/components/ui/macos/__tests__/`
- Result: 13 passed
- Not checked: none
