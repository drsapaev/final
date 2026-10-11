## Summary
🎨 Palette: Add tooltips to icon-only close buttons

💡 What: Wrapped icon-only close/dismiss buttons in `Alert` and `Modal` components with a custom `Tooltip` component and removed the native `title` attribute from the Modal close button.
🎯 Why: Relying solely on `aria-label` hides the action's purpose from sighted users who don't use screen readers. Using the native `title` attribute provides an inconsistent UX across different browsers/OS. The `Tooltip` component provides a consistent and accessible visual cue.
📸 Before/After: Before, no custom tooltip on hover (either native title or nothing). After, custom macOS-style tooltip on hover.
♿ Accessibility: Maintains `aria-label` for screen reader support while providing visual tooltip for sighted users.

## Cyclic Execution Evidence
Not applicable because no cyclic execution loops were modified.

## Contract Impact
Not applicable because no contracts or APIs were modified.

## RBAC / Permissions
Not applicable because no permission changes.

## Notification / Realtime
Not applicable because no realtime or notification changes.

## Frontend Resilience
Not applicable because these are cosmetic visual changes.

## Scope Gate
Not applicable because this is a small UX enhancement that doesn't change scope.

## Validation
Not applicable because ran lint checks and test suite. Tested locally that components render.
