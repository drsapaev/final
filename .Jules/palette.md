## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2024-05-18 - Dynamically Map Error States to aria-invalid
**Learning:** Many custom form input components (like wrappers for `input`, `textarea`, or `select`) accept an `error` prop for visual styling, but fail to programmatically link this error state to screen readers via the `aria-invalid` attribute on the underlying native element.
**Action:** When creating or auditing custom form controls that take an `error` prop, always ensure that `aria-invalid={!!error}` is passed down to the inner `<input>`, `<textarea>`, or trigger `<button>` to communicate the invalid state to assistive technologies.
