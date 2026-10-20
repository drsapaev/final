#!/bin/bash
export PR_BODY="## Summary
🎨 Palette: Add \`aria-busy\` to AppLoading component

**💡 What:** Added \`aria-busy=\"true\"\` to the root \`<section>\` element of the \`AppLoading\` component.
**🎯 Why:** While \`AppLoading\` already had \`role=\"status\"\` and \`aria-live=\"polite\"\`, omitting \`aria-busy=\"true\"\` meant screen readers might not reliably understand that the region is actively busy and waiting for content to resolve.
**📸 Before/After:** N/A (Non-visual change).
**♿ Accessibility:** Explicitly informs assistive technologies that the section is actively processing/loading, improving the experience for screen reader users when async data is being fetched.

## Cyclic Execution Evidence

- Fresh main sync: Yes
- Clean workspace: Yes
- Branch: palette-apploading-aria-busy
- Scope gate: Passed
- Red-check handling: None encountered

## Contract Impact
not applicable: No API or domain interface changes.

## RBAC / Permissions
not applicable: No authorization changes.

## Notification / Realtime
not applicable: No WebSocket or notification event changes.

## Frontend Resilience
not applicable: Purely a semantic HTML/ARIA attribute addition, no async logic changed.

## Scope Gate
not applicable: Verified no unintended zero-delta impacts as this is an isolated component fix.

## Validation

- Targeted tests or smoke run: ran pnpm run test:run src/components/ui/macos/__tests__/AppState.test.tsx
- Result: Passed
- Not checked: Visual regression"

python scripts/run_pr_review_gate_checks.py --body-env PR_BODY
