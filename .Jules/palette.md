## 2024-05-12 - Missing aria-busy on Complex Loading States
**Learning:** While buttons effectively communicated their loading states via `aria-busy`, larger container components in the design system (Tables, Lists, Stat Cards) with custom loading skeletons or empty states completely lacked this attribute. This creates a confusing experience for screen reader users who aren't notified when these regions are processing or waiting for data.
**Action:** Always add `aria-busy="true"` (or `aria-busy={loading}`) to the root container of complex UI components that handle asynchronous data loading, especially when rendering custom loading skeletons or empty states instead of standard UI elements.

## 2026-05-29 - Hover and Focus in Custom Context Menus
**Learning:** Direct DOM manipulation for hover styles (e.g. `e.target.style.backgroundColor`) in custom components completely bypasses React's render cycle and fails to handle keyboard focus events. This creates inaccessible dropdowns/menus for keyboard users, as the focused state is invisible.
**Action:** Always use React state (`useState`) or CSS classes for hover effects, and bind focus visibility to BOTH mouse events (`onMouseEnter`/`onMouseLeave`) and keyboard events (`onFocus`/`onBlur`) along with an `outline` property to ensure focus is always visible.
