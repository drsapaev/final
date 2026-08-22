## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2024-05-30 - Form Component Error States
**Learning:** React elements naturally cast boolean variables passed to ARIA attributes (e.g., `aria-invalid={!!error}`) into proper `"true"` or `"false"` string DOM attributes. Passing `!!error` directly safely ensures accessibility APIs register the correct state without manual string interpolation.
**Action:** When implementing custom wrapper components over native elements (`input`, `textarea`, custom `role="checkbox"` divs), always explicitly proxy `aria-invalid` based on the internal error state to maintain parity with native HTML5 form validation.
