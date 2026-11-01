import os
body = """🎨 Palette: [Add Tooltip to close/dismiss buttons in Modal & Alert]

## Summary

* 💡 **What**: Replaced native title with custom Tooltip for Modal's fullscreen close button, and added Tooltip to Alert's dismiss button.
* 🎯 **Why**: Improves visual consistency across the system, provides a visual hint for icon-only buttons, and prevents redundant screen reader announcements from native `title` attributes.
* 📸 **Before/After**: Screenshots if visual change (not applicable).
* ♿ **Accessibility**: Removed redundant `title` attributes and ensured `aria-label` is present and not duplicated by tooltip for screen readers.

## Cyclic Execution Evidence
Not applicable.

## Contract Impact
Not applicable.

## RBAC / Permissions
Not applicable.

## Notification / Realtime
Not applicable.

## Frontend Resilience
Not applicable.

## Scope Gate
Not applicable.

## Validation
Verified visually via Playwright integration run and standard lint and test runs.

---
*PR created automatically by Jules for task [3011052966258764017](https://jules.google.com/task/3011052966258764017) started by @drsapaev*
"""
os.environ["PR_BODY"] = body
os.system("python scripts/check_pr_review_template.py --body-env PR_BODY")
