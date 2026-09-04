## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2024-05-23 - Component Testing with useTranslation hook
**Learning:** I learned that it is critical to confirm the `useTranslation` hook is properly initialized inside the functional component when using `t()`, rather than just relying on the top-level import. Doing so prevents runtime ReferenceErrors when the component mounts.
**Action:** When I replace hardcoded strings with `t()`, I must explicitly check the component's body for `const { t } = useTranslation();`, and add it if missing.

## 2026-08-14 - Table wrapper accessibility
**Learning:** The EnhancedAppointmentsTable component was showing a loading spinner visually, but the table wrapper itself did not have `aria-busy` or `aria-live` attributes, making it invisible to screen readers that the table is currently updating.
**Action:** Add `aria-busy={loading}` and `aria-live="polite"` to the `eat-table-scroll` wrapper when the table is fetching data.

## 2026-08-26 - Missing aria-hidden on Purely Visual Placeholders
**Learning:** Adding `aria-busy="true"` to a container component to indicate a loading state is good, but if that container renders custom placeholder DOM elements (like skeleton loaders), those placeholders themselves can create "noise" for screen readers. Screen readers may attempt to read the empty inner `<div>`s intended only for visual effect.
**Action:** When creating skeleton loaders or other purely visual placeholder elements, always add `aria-hidden="true"` to their root nodes so screen readers ignore them entirely, especially when their parent container already accurately conveys the state via `aria-busy` and `role="status"`.

## 2026-08-31 - [Added Native Tooltip to IconButton]
 **Learning:** [Accessibility] While native `title` attributes provide basic tooltips, screen readers might announce them redundantly with `aria-label`, and they don't follow custom design system styles.
 **Action:** For icon-only buttons using existing components, wrap them in a custom `<Tooltip content={label}>` and use `aria-label` on the button itself. Remove the `title` attribute from the button. This prevents double tooltips while preserving a11y and UX consistency.

## 2026-09-02 - Communicating error states via aria-invalid
**Learning:** Visual error states (like red borders) on form inputs, textareas, custom checkboxes, and custom selects are completely invisible to screen readers unless the `aria-invalid` attribute is used. Relying only on color to convey state is an accessibility violation.
**Action:** Always ensure `aria-invalid={!!error}` is passed down to the underlying interactive element (e.g. `<input>`, `<textarea>`, `<button>`, `<div role="checkbox">`) within custom form controls to properly communicate error states to assistive technologies.

## 2026-09-03 - Component Testing with useTranslation hook
**Learning:** I learned that it is critical to confirm the  hook is properly initialized inside the functional component when using , rather than just relying on the top-level import. Doing so prevents runtime ReferenceErrors when the component mounts.
**Action:** When I replace hardcoded strings with , I must explicitly check the component's body for , and add it if missing.
