
## 2024-03-26 - Missing ARIA labels on macOS System Components
**Learning:** Icon-only buttons in custom system components (like macOS `Header`) frequently miss `aria-label` attributes. Screen readers rely on these labels to announce the purpose of the button since there is no textual content.
**Action:** Always verify that `Button` components rendering only an `<Icon />` have an explicitly defined `aria-label` to ensure accessibility standards are met.
