## 2026-03-02 - MacOSInput Clear Button Layout Constraints
**Learning:** When adding functional interactive elements inside existing input components (like a clear button), it's crucial to account for existing absolute-positioned elements (like right-aligned icons) to prevent visual overlap.
**Action:** Always dynamically calculate padding (e.g., `paddingRight`) and positioning (e.g., `right`) based on the active combination of internal elements.
