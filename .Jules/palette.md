
## 2024-05-18 - Accessibility on Custom Popovers/Modals
**Learning:** Custom UI components like popovers and modals throughout the application often use a simple "×" character or an icon component (like `X`, `Eye`, or `Edit` from lucide-react) inside a `<button>` without providing an accessible name (`aria-label`). This makes these buttons completely unintelligible to screen reader users, who will just hear "button" without context on what the button does.
**Action:** Always proactively check for and add appropriate `aria-label`s (like `aria-label="Закрыть"`, `aria-label="Просмотр"`, `aria-label="Редактировать"`) to any icon-only button, especially close buttons in modals/popovers that don't use standard component library tools but render their own `<button>` elements.
