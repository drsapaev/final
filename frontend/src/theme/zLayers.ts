/**
 * HDR-FX-1 (header audit P2-3): a single z-strategy for header floating layers.
 *
 * The sticky header itself is z-1000 (header-new.css). Body-portaled dropdowns
 * that belong to header controls (theme menu, search results, language menu)
 * sit one step above that layer and below the app-level overlays
 * (Tooltip/Toast/CommandPalette 9999, session-expiry modal 10000), so system
 * overlays always win the stacking race.
 *
 * Previously these dropdowns used z-index 2147483647 (INT32_MAX), which placed
 * them above every overlay in the app — including the session-expiry modal —
 * and mixed three different layering strategies inside one component tree.
 */
export const HEADER_PORTAL_Z = 1100;
