## Summary

- Add `aria-live="polite"` attribute to `MacOSTable` and `MacOSList` containers.
- Re-bind `aria-busy` to dynamic boolean state `loading`.

## Cyclic Execution Evidence

- Fresh main sync: yes
- Clean workspace: yes
- Branch: `palette-loading-state-aria`
- Scope gate: Modified only UI components
- Red-check handling: fixed

## Contract Impact
not applicable - purely frontend accessibility attribute changes, no API or backend contracts affected.

## RBAC / Permissions
not applicable - no authentication or authorization logic modified.

## Notification / Realtime
not applicable - no notification or realtime features modified.

## Frontend Resilience
not applicable - no frontend data flow logic or pathing changed.

## Scope Gate

- Allowed paths: components/ui/macos
- Denied paths: none
- Migration/docs/test impact: none
- Rollback note: safe

## DevBrain Memory Impact

- [x] no durable memory update needed
- [ ] PROJECT_MEMORY updated
- [ ] DEVBRAIN_STATUS updated
- [ ] AI Factory dossier/log/patch updated
- [ ] agent_gate routing rule updated
- [ ] indexes/artifacts refreshed locally
- [ ] regression matrix run

## Validation

- Targeted tests or smoke run: test
- Result: pass
- Not checked: none
