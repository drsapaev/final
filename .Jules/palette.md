## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2026-08-31 - [Added Native Tooltip to IconButton]
 **Learning:** [Accessibility] While native `title` attributes provide basic tooltips, screen readers might announce them redundantly with `aria-label`, and they don't follow custom design system styles.
 **Action:** For icon-only buttons using existing components, wrap them in a custom `<Tooltip content={label}>` and use `aria-label` on the button itself. Remove the `title` attribute from the button. This prevents double tooltips while preserving a11y and UX consistency.
