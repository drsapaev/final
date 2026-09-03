## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.
## 2026-09-03 - Component Testing with useTranslation hook
**Learning:** I learned that it is critical to confirm the  hook is properly initialized inside the functional component when using , rather than just relying on the top-level import. Doing so prevents runtime ReferenceErrors when the component mounts.
**Action:** When I replace hardcoded strings with , I must explicitly check the component's body for , and add it if missing.
## 2024-05-23 - Component Testing with useTranslation hook
**Learning:** I learned that it is critical to confirm the `useTranslation` hook is properly initialized inside the functional component when using `t()`, rather than just relying on the top-level import. Doing so prevents runtime ReferenceErrors when the component mounts.
**Action:** When I replace hardcoded strings with `t()`, I must explicitly check the component's body for `const { t } = useTranslation();`, and add it if missing.
