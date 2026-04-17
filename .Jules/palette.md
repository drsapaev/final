## 2024-05-24 - Do not hardcode localized strings into component primitives
**Learning:** Hardcoding localized strings (e.g., Russian "Очистить ввод") into fallback attributes like `aria-label` or `title` inside reusable components (like `MacOSInput`) causes regressions for English users.
**Action:** Use default English strings (e.g., 'Clear input') for `aria-label` and `title` attributes inside base UI components unless the component specifically supports localization through props or a context provider.
