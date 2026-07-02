# Benefit Settings stat card color cleanup

## Root Cause
- `BenefitSettings.jsx` passed CSS variable strings such as `var(--mac-success)` into `MacOSStatCard.color`.
- `MacOSStatCard` only accepts canonical tokens (`blue`, `green`, `orange`, `red`, `purple`, `gray`), so React emitted prop warnings during the panel smoke.

## Fix
- Replaced the invalid `color` prop values with canonical tokens:
  - repeat visit window -> `blue`
  - repeat discount -> `green` / `orange`
  - benefit consultation -> `green` / `orange`
  - All Free auto-approve -> `orange` / `blue`

## Verification
- Live browser smoke on `/admin/benefit-settings?section=benefit-settings`
- Save flow passed:
  - `21 -> 22`
  - `POST /api/v1/admin/benefit-settings -> 200`
  - reload reflected `22 days`
  - restore flow returned the panel to `21 days`
- Fresh browser session console was clean after the fix: `0 errors, 0 warnings`
- Browser evidence captured in:
  - `output/playwright/benefit-settings-smoke-final.png`
  - `output/playwright/benefit-settings-smoke-network.log`

## Prevention
- Prefer design-system tokens over raw CSS variables when a component defines an explicit prop enum.
- Treat React prop-type warnings as a real UX regression during panel smokes, not as harmless noise.
