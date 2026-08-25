## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2026-08-25 - Custom Form Components Error State Accessibility
**Learning:** Custom UI components (like Checkbox, Select wrappers) and native inputs must pass `aria-invalid={!!error}` down to the underlying interactive element (`role="checkbox"`, `<input>`, `<textarea>`, `<button>`) to ensure assistive technologies correctly announce field error states during validation.
**Action:** When creating or modifying custom form controls that accept an `error` prop, always bind `aria-invalid` to the core focusable element rather than just relying on visual indicators (like red borders).
