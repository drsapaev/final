## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2026-09-04 - Missing aria-invalid on Form Components
**Learning:** Custom form components (like Checkbox, Input, Textarea, Select) correctly propagated error styling visually using the `error` prop, but failed to communicate this invalid state programmatically via `aria-invalid`. This is a common pattern when building wrapper components around native HTML inputs, where accessibility attributes are often overlooked in favor of visual styling.
**Action:** Always ensure that custom form wrapper components pass down the `aria-invalid={!!error}` attribute to their underlying native elements or custom role elements to properly communicate error states to assistive technologies.
