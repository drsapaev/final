## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.
## $(date +%Y-%m-%d) - Adding accessibility labels to custom UI chat components
**Learning:** Found that custom macOS-styled chat components and voice recording components had multiple icon-only interactive elements without corresponding aria-labels, relying only on tooltips (title).
**Action:** When creating or modifying chat overlays, floating buttons, and inline media controls, always provide an `aria-label` attribute matching the visual tooltip intent for screen reader accessibility.
