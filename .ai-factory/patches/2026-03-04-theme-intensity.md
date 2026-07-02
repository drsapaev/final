# Theme Intensity Pass

- added scheme-specific scene tokens for header, cards, nav items and main shell
- made custom themes visually diverge from plain dark mode through stronger canvas overlays
- updated sidebar active/hover states to use theme-specific nav tokens instead of the generic accent-only styling
- added `app-shell` and `app-main` hooks so custom themes can style the page canvas consistently
- verified in browser automation that `dark`, `vibrant`, `glass`, and `gradient` now produce different header/main/card treatments
