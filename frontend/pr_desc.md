## Summary
**What:** Added `aria-hidden="true"` to the button loading spinner SVG.
**Why:** Even though buttons communicate their loading state effectively via `aria-busy`, the internal visual spinner (`<svg>`) used within the button can still be picked up by screen readers as an empty image or graphic, adding noise.
**Before/After:** The visual is unchanged. The SVG now contains `aria-hidden="true"`.
**Accessibility:** Prevents screen readers from announcing the loading SVG redundantly when the button itself has `aria-busy`.

## Cyclic Execution Evidence
not applicable - UI accessibility change only

## Contract Impact
not applicable - UI accessibility change only

## RBAC / Permissions
not applicable - UI accessibility change only

## Notification / Realtime
not applicable - UI accessibility change only

## Frontend Resilience
not applicable - UI accessibility change only

## Scope Gate
not applicable - UI accessibility change only

## Validation
not applicable - UI accessibility change only
