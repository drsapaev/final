## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2024-05-14 - Missing aria-invalid on Form Components
**Learning:** Native form components support the 'error' state for styling purposes, but failed to pass the aria-invalid attribute to the underlying input elements. This causes screen readers to remain unaware of the invalid state, leading to a poor experience for visually impaired users.
**Action:** Always add aria-invalid={!!error} to the native form elements in custom wrappers like Input, Textarea, Select, and Checkbox when implementing a custom error state.
