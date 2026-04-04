## 2026-04-04 - Added keyboard support and ARIA to sortable table headers
**Learning:** Interactive table headers used for sorting need `tabIndex={0}`, an `onKeyDown` listener for Enter/Space, and the `aria-sort` attribute to properly communicate sorting state to screen readers.
**Action:** Always add keyboard handlers and ARIA attributes when adding interactive behavior (like sorting) to structural elements.
