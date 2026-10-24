## Summary

🎨 Palette: Remove redundant title attribute from Modal close button

*   **💡 What:** Removed the native `title` attribute from the fullscreen `Modal` close button in `frontend/src/components/ui/macos/Modal.tsx`.
*   **🎯 Why:** The close button already contained a proper `aria-label`. Having both `aria-label` and a native `title` attribute with the same text often causes screen readers to redundantly announce the label twice. The visual tooltip was unnecessary as the "✕" icon is universally understood for closing modals.
*   **📸 Before/After:** N/A (Only affects native hover tooltip and screen reader output).
*   **♿ Accessibility:** Streamlined screen reader output by removing redundant announcements.

## Cyclic Execution Evidence
Not applicable because this is a simple UI change without backend logic.

## Contract Impact
Not applicable because no API contracts were changed or affected.

## RBAC / Permissions
Not applicable because there are no permission changes in this PR.

## Notification / Realtime
Not applicable because there are no realtime or notification changes here.

## Frontend Resilience
Not applicable because this is purely a presentation layer accessibility change.

## Scope Gate
Not applicable because it is strictly within the scope of the Palette persona constraints.

## Validation
Not applicable because I have verified this using local vitest test runs.
