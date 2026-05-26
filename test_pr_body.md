## Summary
- Added an `aria-label` attribute to the `MacOSMetricCard` component when it acts as an interactive button (`onClick` is provided).
- Enhances screen reader accessibility for this interactive element.

## Cyclic Execution Evidence
not applicable - UI micro-enhancement only.

## Contract Impact
not applicable - No backend API or data contracts were changed.

## RBAC / Permissions
not applicable - No auth or routing changes.

## Notification / Realtime
not applicable - No realtime features were changed.

## Frontend Resilience
not applicable - Data flow and resilience remain unchanged.

## Scope Gate
not applicable - Strictly limited to a single frontend UI component.

## DevBrain Memory Impact
- [x] no durable memory update needed
- [ ] PROJECT_MEMORY updated
- [ ] DEVBRAIN_STATUS updated
- [ ] AI Factory dossier/log/patch updated
- [ ] agent_gate routing rule updated
- [ ] indexes/artifacts refreshed locally
- [ ] regression matrix run

## Validation
- Targeted tests or smoke run: `pnpm test --run` executed locally.
- Result: Passed without regressions.
- Not checked: End-to-end visual tests since this is an aria-label change.
