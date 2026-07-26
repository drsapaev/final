## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2024-07-26 - Missing aria-invalid on Custom Inputs
**Learning:** Custom form wrappers like `Input`, `Textarea`, and `Select` often manage visual error states well (e.g., via red borders or text) but frequently fail to pass `aria-invalid={!!error}` to the underlying native element. This leaves screen reader users completely unaware that a field is in an invalid state.
**Action:** Always ensure that custom form wrappers correctly map their `error` prop (even if it's a boolean or a string) to the `aria-invalid` attribute of the underlying native element (`<input>`, `<textarea>`, or the trigger `<button>` for selects).
