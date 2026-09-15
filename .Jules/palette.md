## 2024-05-14 - Add aria-label to icon-only close buttons
**Learning:** Found several components using `✕` and `×` for close buttons that lacked an `aria-label`, making them inaccessible to screen readers.
**Action:** Always ensure icon-only buttons have descriptive `aria-label` attributes using the translation keys (e.g. `t('close')`) if available, to provide context for screen reader users.
