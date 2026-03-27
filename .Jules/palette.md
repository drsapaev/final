## 2024-03-27 - Keyboard Navigation for MacOSTable Headers
**Learning:** React components imitating native semantic elements like tables must explicitly ensure interactive cells like `<th>` preserve their role while gaining keyboard focusability (`tabIndex=0`). Using `role="button"` overrides the `columnheader` role making the table non-compliant for screen readers reading grids.
**Action:** For interactive table headers, retain native `columnheader` role, use `tabIndex={0}`, and map `onKeyDown` to replicate click events for Space/Enter keys while adding `aria-sort` to communicate state.
