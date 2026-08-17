## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2024-05-13 - Conditional AI Assist Icons Need ARIA Context
**Learning:** Found that conditional icon-only buttons (like `SmartAssistButton` which swaps between ✨, 🧠, or a spinner based on state) had `title` attributes for visual tooltips but lacked `aria-label`s. Screen reader users would hear the emoji descriptions ("sparkles" or "brain") out of context instead of the actual intent.
**Action:** When creating icon-only buttons that use conditional logic to display different icons (especially emojis), ensure an `aria-label` is applied using the exact same conditional logic as the `title` attribute to provide consistent, intent-based context rather than literal icon descriptions.
