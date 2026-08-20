## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2026-08-20 - Missing aria-invalid on Form Controls
**Learning:** While custom form controls in the design system (Input, Textarea, Select, Checkbox) visually indicated their error states, they lacked the `aria-invalid` attribute. This results in screen reader users not being explicitly notified when a form field contains invalid data, making error recovery difficult.
**Action:** Always pass `aria-invalid={!!error}` to the underlying native element (like `<input>` or `<textarea>`) or the custom element with a semantic role (like `<div role="checkbox">`) when building custom form controls that support error states.
