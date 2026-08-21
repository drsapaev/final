## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2026-08-21 - Added aria-invalid to form controls
**Learning:** When creating custom form controls (Input, Textarea, Checkbox, Select), applying visual error styles (like red borders) is not enough for accessibility. Assistive technologies need explicit programmatic notification of error states.
**Action:** Always ensure `aria-invalid={!!error}` is passed to the underlying native element or the element with the relevant `role` to communicate the error state properly.
