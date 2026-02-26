## 2025-05-24 - Exposing Visual Status to Screen Readers
**Learning:** Purely visual indicators like status dots (online/offline) are invisible to screen readers unless explicitly described.
**Action:** When adding visual status indicators, always update the parent component's `aria-label` or description to include this state textually (e.g., "User Name (Role) - Online").
