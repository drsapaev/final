## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2024-05-14 - Missing aria-invalid on Form Controls with Errors
**Learning:** While form controls accurately represented error states visually (via red borders), they lacked the `aria-invalid` attribute. Screen reader users would hear the label and value, but not the critical context that the current value is invalid or in an error state.
**Action:** For form inputs, textareas, custom checkboxes, and select triggers, always ensure `aria-invalid={!!error}` is passed to the underlying native element or custom element (e.g., `role="checkbox"`) to properly communicate error states to assistive technologies.
