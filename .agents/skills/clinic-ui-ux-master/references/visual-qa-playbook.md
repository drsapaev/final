# Visual QA Playbook

Use this reference when the task needs browser evidence, screenshot review, responsive checks, or before/after verification.

## Preconditions

Confirm:

- relevant backend/frontend dev servers are running, or start the minimal needed server when the task requires it
- route and role are known
- test user/session requirements are known or discoverable
- browser tooling is available

If credentials or data are required, do not guess. Use seeded users, live auth response, or ask for the missing credential path.

## Viewports

Default viewport set:

- mobile: 375 x 812
- tablet: 768 x 1024
- desktop: 1280 x 800
- wide desktop: 1920 x 1080

Use fewer only when the route is clearly desktop-only or mobile-only, and state that choice.

## Route Inspection

For each route:

1. Load the route.
2. Wait for network and loading state to settle.
3. Inspect console errors.
4. Inspect visible network failures if available.
5. Capture or inspect screenshot.
6. Check keyboard focus path for touched controls.
7. Check empty/error/loading states if reachable.

Evidence to record:

- route
- role
- viewport
- screenshot path or summary
- console/network errors
- observed issue
- source file candidate

## Visual Checks

Look for:

- overlap
- clipped text
- horizontal scroll
- fixed header/sidebar covering content
- sticky footer covering actions
- modal overflow
- focus outline hidden behind containers
- inconsistent card widths
- status badges wrapping badly
- table action columns collapsing
- long localized strings breaking controls
- loading skeleton shifting layout

## Mobile Checks

On mobile:

- primary action is reachable without excessive scroll
- inputs are readable and tap targets are comfortable
- keyboard does not hide submit/recovery action
- fixed actions do not cover validation messages
- long Russian/Uzbek labels wrap cleanly
- phone/date/payment fields remain usable

## Desktop Checks

On desktop and wide desktop:

- content does not stretch into unreadable long lines
- dashboard cards align consistently
- table density remains useful
- sidebars and topbars do not compete
- empty states do not look like landing page heroes

## Re-Verification

After editing:

1. Re-open the same route.
2. Use the same viewport.
3. Verify the original issue is gone.
4. Check no new overlap, clipping, console error, or lost focus state appeared.
5. Run the narrowest relevant automated check.

Do not claim visual fix success without either browser evidence or a clear statement that browser tooling was unavailable.

## Screenshot Report Format

Use:

```text
Route:
Role:
Viewport:
Before:
After:
Issue:
Result:
Residual risk:
```

## When Browser QA Is Not Worth It

Skip browser QA only for:

- docs-only changes
- skill/reference changes
- static routing metadata text changes with no rendered UI impact
- pure test updates

For visible UI changes, browser QA is strongly preferred.
