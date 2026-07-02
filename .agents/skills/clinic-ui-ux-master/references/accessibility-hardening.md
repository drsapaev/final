# Accessibility Hardening

Use this reference for accessibility audits or fixes. It borrows the strongest parts of WCAG-focused skills and adapts them to this clinic app.

## Baseline

Target WCAG AA behavior for active clinic workflows. Treat accessibility as workflow reliability: staff may use keyboard navigation, zoom, high contrast, screen readers, or mobile assistive tech under time pressure.

## Audit Order

1. Identify route, role, workflow, and critical action.
2. Check semantic structure and heading order.
3. Check keyboard-only navigation.
4. Check focus visibility and focus return.
5. Check form labels and error association.
6. Check dynamic status announcements.
7. Check color contrast and non-color status cues.
8. Check touch targets and responsive zoom.
9. Check reduced-motion and animation restraint.
10. Map findings to severity and workflow impact.

## Keyboard

Check:

- all interactive elements are reachable by Tab or documented arrow-key pattern
- focus order matches visual order
- focus is visible and not clipped
- Escape closes dialogs, popovers, and menus when expected
- modal focus is trapped and restored to the opener
- disabled controls are not focus traps
- keyboard users can submit and recover from validation errors

High-risk components:

- appointment wizard
- payment actions
- queue join form
- role sidebars and tabs
- EMR sections
- lab report builder
- dialogs and menus

## Screen Reader And Semantics

Prefer semantic HTML before ARIA:

- use `button` for actions
- use `a` for navigation
- use `label` for inputs
- use table headers for data tables
- use headings in a logical order
- use landmarks for page, nav, main, and complementary regions

Use ARIA when semantics are not enough:

- `aria-label` for icon-only controls
- `aria-describedby` for hints and errors
- `aria-invalid` for invalid fields
- `aria-expanded` and `aria-controls` for disclosure controls
- `aria-live` for async status updates that matter
- `aria-current` for active navigation where appropriate

Avoid:

- adding `role="button"` to non-buttons when a real button works
- hiding visible labels from assistive tech
- putting interactive controls inside other interactive controls
- generic labels like "click", "open", "more"

## Forms

Every important form should have:

- visible labels
- programmatic label association
- input purpose and format hints when needed
- field-level errors near the field
- a summary only as a supplement for long forms
- loading and disabled submit states
- clear recovery path after validation failure

Clinical priority fields:

- patient name
- phone
- date and time
- department and specialist
- payment amount
- queue date/number
- lab sample/result identifiers
- diagnosis/procedure identifiers

## Dynamic Content

Use live-region patterns for:

- queue state changes
- payment status changes
- save success/failure
- async form validation result
- report generation completion

Do not announce noisy polling updates unless the message changes user action.

## Contrast And Status

Check:

- normal text meets contrast expectations
- UI boundaries and focus rings are visible
- disabled state is readable
- status is conveyed by text and icon/shape, not color alone
- charts and badges have labels or legends
- dark theme preserves contrast

Treat ambiguous success/warning/error states in queue, payment, lab, and EMR as high severity.

## Touch And Zoom

Check:

- touch targets are comfortable around 44px where practical
- controls are not packed too tightly on mobile
- page works at browser zoom
- mobile keyboard does not cover required actions or errors
- sticky controls do not hide content

## Reduced Motion

Respect user preference:

- avoid mandatory animation in operational screens
- reduce or disable non-essential motion under `prefers-reduced-motion`
- do not use motion as the only way to communicate status
- keep loading indicators calm and non-blocking

## Static Searches

Use searches like:

```powershell
rg -n "aria-label|aria-describedby|aria-invalid|aria-live|role=|tabIndex|onKeyDown|onKeyUp" frontend/src
rg -n "<div[^>]+onClick|<span[^>]+onClick" frontend/src
rg -n "outline:\\s*none|outline: ?0" frontend/src
```

Static searches are leads, not proof. Confirm with source and, when possible, browser behavior.

## Report Fields

For each accessibility finding include:

- route and role
- component/file
- user impact
- WCAG-like category: perceivable, operable, understandable, robust
- smallest remediation
- validation method
