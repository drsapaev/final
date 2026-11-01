import os
body = """🎨 Palette: [Add Tooltip to close/dismiss buttons in Modal & Alert]

## Summary

* 💡 **What**: Replaced native title with custom Tooltip for Modal's fullscreen close button, and added Tooltip to Alert's dismiss button.
* 🎯 **Why**: Improves visual consistency across the system, provides a visual hint for icon-only buttons, and prevents redundant screen reader announcements from native `title` attributes.
* 📸 **Before/After**: Screenshots if visual change (not applicable).
* ♿ **Accessibility**: Removed redundant `title` attributes and ensured `aria-label` is present and not duplicated by tooltip for screen readers.

## Cyclic Execution Evidence

- Fresh main sync: branch created from current origin/main
- Clean workspace: inspected before edits; only frontend macos components changed
- Branch: palette-tooltip-close-buttons
- Scope gate: allowed frontend ui components; denied backend runtime, migrations, and generated output
- Red-check handling: fix any failed docs/gate check in this same PR before merge

## Contract Impact

not applicable - frontend ui only, no API, websocket, event, or frontend consumer contract changed.

## RBAC / Permissions

not applicable - no route, endpoint, guard, role helper, or auth-sensitive behavior changed.

## Notification / Realtime

not applicable - no notification, websocket, chat, or realtime behavior changed.

## Frontend Resilience

not applicable - purely visual UI component change, no frontend resilience behavior changed.

## Scope Gate

- Allowed paths: frontend/src/components/ui/macos/**
- Denied paths: backend runtime, migrations, generated output
- Migration/docs/test impact: frontend ui only; no migration expected
- Rollback note: revert the frontend ui changes

## Validation

- Targeted tests or smoke run: local vitest for macos components
- Result: passed
- Not checked: backend integration tests, because no backend runtime files changed
"""
os.environ["PR_BODY"] = body
os.system("python scripts/check_pr_review_template.py --body-env PR_BODY")
