## 2024-05-02 - React State for Hover/Focus Effects
**Learning:** Direct DOM manipulation for hover effects (e.g., `e.target.style`) bypasses React state management and creates accessibility gaps. It fails to provide visual feedback for keyboard users since `onMouseEnter`/`onMouseLeave` are mouse-only events.
**Action:** Always use React state (e.g., `useState`) bound to both mouse (`onMouseEnter`/`onMouseLeave`) and keyboard (`onFocus`/`onBlur`) events, or use CSS classes like `:hover` and `:focus-visible` to ensure consistent visual feedback for all users.
