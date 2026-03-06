## 2025-03-01 - Add aria-busy to loading buttons
**Learning:** Found that custom buttons in the macOS component library did not set `aria-busy` when in a loading state, despite adding an active spinner or other loading indicator. Disabled state alone isn't enough context for screen readers when an action is actively processing.
**Action:** Always add `aria-busy={loading}` when handling asynchronous states in custom buttons.
