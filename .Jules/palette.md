## 2024-05-01 - Icon-only buttons lack ARIA labels
**Learning:** Found multiple instances of icon-only `Button` components missing `aria-label` and `title` attributes (e.g., Settings and Search Clear in Header). This is a critical pattern to watch for across the custom macOS UI library.
**Action:** Always ensure `aria-label` (and `title` for hover) is explicitly provided when using the `Button` or `MacOSButton` components without text children.
