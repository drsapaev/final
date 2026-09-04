## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2026-08-14 - Table wrapper accessibility
**Learning:** The EnhancedAppointmentsTable component was showing a loading spinner visually, but the table wrapper itself did not have `aria-busy` or `aria-live` attributes, making it invisible to screen readers that the table is currently updating.
**Action:** Add `aria-busy={loading}` and `aria-live="polite"` to the `eat-table-scroll` wrapper when the table is fetching data.

## 2026-08-26 - Missing aria-hidden on Purely Visual Placeholders
**Learning:** Adding `aria-busy="true"` to a container component to indicate a loading state is good, but if that container renders custom placeholder DOM elements (like skeleton loaders), those placeholders themselves can create "noise" for screen readers. Screen readers may attempt to read the empty inner `<div>`s intended only for visual effect.
**Action:** When creating skeleton loaders or other purely visual placeholder elements, always add `aria-hidden="true"` to their root nodes so screen readers ignore them entirely, especially when their parent container already accurately conveys the state via `aria-busy` and `role="status"`.

## 2026-08-31 - [Added Native Tooltip to IconButton]
 **Learning:** [Accessibility] While native `title` attributes provide basic tooltips, screen readers might announce them redundantly with `aria-label`, and they don't follow custom design system styles.
 **Action:** For icon-only buttons using existing components, wrap them in a custom `<Tooltip content={label}>` and use `aria-label` on the button itself. Remove the `title` attribute from the button. This prevents double tooltips while preserving a11y and UX consistency.
