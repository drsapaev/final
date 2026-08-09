## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2024-08-09 - Missing aria-invalid on Custom Form Controls
**Learning:** The custom form components (Input, Textarea, Select, Checkbox) visually indicated their error states (e.g., using red borders via a custom `error` prop), but failed to programmatically communicate this invalid state to assistive technologies. Users relying on screen readers wouldn't know a field was invalid.
**Action:** When creating custom form controls that accept an `error` prop for visual feedback, always ensure `aria-invalid={!!error}` is passed down to the underlying interactive element (`<input>`, `<textarea>`, `<button>`, or the element with `role="checkbox"`).
