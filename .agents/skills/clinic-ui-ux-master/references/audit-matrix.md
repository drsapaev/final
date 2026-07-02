# Audit Matrix

Use this reference for detailed UI/UX audits. Keep findings evidence-based and tied to a route, role, file, or screenshot.

## Severity

- `P0`: blocks task completion, hides critical state, creates clinical/payment/queue misunderstanding, or breaks layout so badly that work cannot continue.
- `P1`: severe workflow friction, inaccessible control, responsive failure, missing critical state, risky visual hierarchy, or major design-system drift on a critical role screen.
- `P2`: inconsistent spacing, typography, color, icon, component, table, or form pattern that slows staff or lowers trust.
- `P3`: polish, microcopy, motion restraint, subtle spacing, minor alignment, low-risk consistency.

Fix or plan P0/P1 before P2/P3.

## Visual Hierarchy

Check:

- primary action is visually obvious
- destructive actions are visually and spatially separated
- secondary actions do not compete with the main action
- status and error states appear near the affected data
- section headings describe the staff task, not the component type
- dense screens still have clear scan order

Evidence to collect:

- route and role
- visible primary action
- competing actions
- source file and component
- screenshot when possible

## Layout And Spacing

Check:

- no overlapping text or controls
- no horizontal overflow at 375, 768, 1280, and 1920px
- cards are not nested unnecessarily
- repeated rows and controls keep stable height
- toolbars wrap predictably
- modals fit mobile and desktop
- tables keep action columns usable

Clinical risks:

- clipped patient name, amount, queue number, date, diagnosis, or lab result is at least P1
- clipped destructive or confirmation action is P0/P1 depending on workflow

## Typography

Check:

- body text is readable under time pressure
- headings are smaller inside panels than page-level headings
- no negative letter spacing
- no viewport-scaled font sizing
- numeric values align and use consistent units
- clinical labels do not rely only on color or icon meaning

Avoid:

- ornamental or unusual fonts
- all-caps long labels
- tiny secondary labels for critical medical/payment state

## Color And Contrast

Check:

- status colors map consistently: success, warning, error, info, neutral
- hardcoded colors are replaced with tokens when practical
- contrast is sufficient in light and dark themes
- disabled controls remain readable
- focus outline is visible
- charts and badges do not rely on color alone

Escalate:

- error/warning/success state ambiguity in queue, payment, lab, or EMR is P1
- hidden disabled state on forms is P1 if staff may assume the action is available

## Components

Check:

- canonical macOS/clinic UI primitives are used for role dashboards, tables, forms, payment states, and app shell
- no new parallel component API is introduced
- controls use stable dimensions
- icon buttons have accessible names
- buttons use existing variants and sizes
- cards are used for repeated entities, modals, or framed tools, not every page section

Drift signals:

- `style={{` in many repeated elements
- `legacy-` classes on active routes
- `@mui/` imports in screens that otherwise use canonical clinic components
- duplicate colors, shadows, border radii, or spacing constants

## Forms

Check:

- labels are explicit and close to inputs
- required fields are visually and programmatically clear
- errors are field-specific where possible
- invalid state is not only red color
- submit button communicates loading and disabled state
- keyboard order matches visual order
- phone, amount, date, and code formatting are forgiving and clear

Clinical risks:

- ambiguous patient identity, phone, payment amount, queue date, or procedure selection is P1/P0
- errors shown only at top of a long form are P1 on critical flows

## Tables And Lists

Check:

- columns match staff scan behavior
- primary identifiers remain visible
- action column is stable
- empty state explains what happened and what to do next
- loading state preserves layout enough to avoid jump
- sorting/filtering labels are clear
- pagination or virtual scrolling does not hide current context

Clinical risks:

- row action ambiguity is P1
- stale or misleading status is P1/P0
- missing empty state on operational work queues is P2/P1 depending on workflow

## States

Every touched workflow should account for:

- loading
- empty
- partial data
- error
- forbidden or role-denied
- disabled action
- optimistic update or pending state
- success confirmation

Payment, queue, lab, and EMR screens must not collapse multiple states into the same visual treatment.

## Accessibility

Check:

- keyboard access reaches every interactive element
- focus is visible and not clipped
- interactive icons have names
- live status messages use appropriate semantics when needed
- form errors are announced or associated
- modals trap focus and restore it
- tables have meaningful headers
- color is not the only channel for status

Minimum static search:

- `aria-label`
- `aria-describedby`
- `aria-invalid`
- `role=`
- `tabIndex`
- `onKeyDown`
- icon-only buttons

## Responsive And Touch

Check:

- 375px mobile has no clipped actions
- 768px tablet keeps sidebars/toolbars usable
- desktop and wide desktop do not stretch text lines excessively
- touch targets are large enough for thumbs
- bottom and sticky actions do not cover content
- scroll containers are obvious and not nested confusingly

High-risk mobile surfaces:

- queue join
- payment result/cancel
- patient portal
- registration/check-in
- public callback pages

## Performance

Check:

- no heavy animation in operational screens
- no avoidable layout shift
- no decorative asset that delays core workflow
- no unnecessary dependency for a one-screen improvement
- browser console is clean after route load

Treat performance as UX when staff repeat the workflow many times per day.
