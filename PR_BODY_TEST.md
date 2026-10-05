## Summary
**💡 What:** Added visual tooltips and localized `aria-label`s to the icon-only pagination buttons in `AppointmentPagination.tsx`.
**🎯 Why:** The chevron icons might not be immediately intuitive to all users. Adding explicit tooltips and screen-reader labels ensures the controls are clear and accessible, and prevents users from guessing what the buttons do.
**📸 Before/After:** N/A (Visual change is the addition of a tooltip on hover)
**♿ Accessibility:** Added internationalized `aria-label`s replacing hardcoded Russian text, and wrapped disabled buttons in `<span>` elements so that tooltips still trigger via pointer events even when the pagination reaches the first or last page.

## Cyclic Execution Evidence
Not applicable because this is a UI-only tooltip text change.

## Contract Impact
Not applicable because there is no API contract impact.

## RBAC / Permissions
Not applicable because there are no permission changes.

## Notification / Realtime
Not applicable because there are no realtime components modified.

## Frontend Resilience
Not applicable because there is no state loading mechanism changed.

## Scope Gate
Not applicable because this is a localized UI change for tooltips.

## Validation
Not applicable because there is no validation logic affected.
