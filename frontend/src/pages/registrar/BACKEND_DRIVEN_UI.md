# Registrar Panel — Backend-driven UI (Strategic Direction 3)

> **Status**: Phase 1 complete — canonical nested routes added alongside legacy `?view=` query param.
> Phase 2 (full migration) is deferred.

## Audit Context

The UX audit (§5.1 Information Architecture, score 5/10) identified that the Registrar Panel used a **parallel routing system** inside a single React component — URL query params (`?view=welcome`, `?view=queue`, `?tab=cardio`, etc.) instead of proper React Router nested routes.

**Problems with `?view=` pattern**:
1. Not registered in `routeRegistry.js` — invisible to route guards, DevTools, breadcrumbs
2. Browser Back button doesn't restore state correctly
3. Deep linking is fragile (user sees `/registrar` but gets unexpected view)
4. SEO unfriendly (search engines see one URL for all views)
5. Doesn't compose with future code-splitting (can't lazy-load WelcomeView separately)

**Strategic Direction 3** (audit §8) calls for migrating to nested routes: `/registrar/welcome`, `/registrar/queue`.

## Phase 1 — What's Done (This PR)

### New canonical routes

Two new route entries added to `routeRegistry.js`:

| Path | ID | Component | Purpose |
|---|---|---|---|
| `/registrar/welcome` | `registrar-welcome` | `RegistrarPanel` | Welcome dashboard view |
| `/registrar/queue` | `registrar-queue` | `RegistrarPanel` | Online queue management view |

Both routes:
- Share the same `RegistrarPanel` component (no duplicate code)
- Use `entry: 'direct'` (not in nav menu — accessible via in-app navigation)
- Have `hideSidebar: true` (consistent with `/registrar`)
- Have role guards: `['Admin', 'Registrar']` (same as parent)
- Have descriptive page titles for accessibility

### Navigation helpers

New module `registrarNavigation.js` provides:

```javascript
import {
  REGISTRAR_VIEW_PATHS,      // { welcome: '/registrar/welcome', queue: '/registrar/queue', worklist: '/registrar' }
  getRegistrarPath,           // view → canonical path
  getViewFromPath,            // path → view name
  isRegistrarRoute,           // pathname → boolean
  navigateToRegistrarView,    // view → { pathname, search } for navigate()
} from './registrar/registrarNavigation';
```

### Updated `currentView` logic

`RegistrarPanel.jsx` now derives `currentView` from **two sources**, with path taking priority:

```javascript
const currentView = useMemo(() => {
  // 1. Prefer canonical path-derived view (Strategic Direction 3)
  const pathView = getViewFromPath(location.pathname);
  if (pathView) return pathView;

  // 2. Backward compatibility: legacy ?view= query param
  const explicitView = searchParams.get('view');
  if (explicitView === 'welcome' || explicitView === 'queue') {
    return explicitView;
  }
  // ... legacy ?tab= fallback
  return explicitView;
}, [searchParams, location.pathname]);
```

### Backward compatibility

| Old URL | New URL | Status |
|---|---|---|
| `/registrar?view=welcome` | `/registrar/welcome` | Both work; path is canonical |
| `/registrar?view=queue` | `/registrar/queue` | Both work; path is canonical |
| `/registrar` (no view) | `/registrar` | Unchanged (worklist) |
| `/registrar?tab=cardio` | (unchanged) | Tab still uses query param |

**No breaking changes**: existing bookmarks, deep links, and `?view=` navigation continue to work. The new path-based URLs are additive.

## Phase 2 — What's Deferred

### Full migration (remove `?view=` entirely)

Phase 2 would:
1. Update all `setSearchParams({ view: 'welcome' })` calls to `navigate('/registrar/welcome')`
2. Update all `setSearchParams({ view: 'queue' })` calls to `navigate('/registrar/queue')`
3. Add a redirect: `/registrar?view=welcome` → `/registrar/welcome` (HTTP 301)
4. Remove the `?view=` parsing from `currentView` useMemo
5. Update contract tests to verify path-based routing

**Why deferred**: Phase 2 requires touching ~15 call sites in RegistrarPanel.jsx, plus updating tests. It's a behavioral change that needs careful E2E testing. Phase 1 establishes the infrastructure without risk.

### Tab routing (?tab=cardio → /registrar/cardio)

The `?tab=` query param (for department tabs: cardio, ecg, derma, dental, lab, procedures) is **not migrated** in Phase 1. Tabs are different from views — they're filters within the worklist view, not separate views. They could become nested routes (`/registrar/cardio`) in a future phase, but this requires backend coordination (queue profiles API).

### View extraction (WelcomeView, WorklistView components)

Phase 1 keeps all view JSX in RegistrarPanel.jsx. Phase 2 would extract `WelcomeView` and `WorklistView` into separate components, each lazy-loaded via `React.lazy()` for code-splitting. This depends on Strategic Direction 1 (Decomposition) reaching step 6b/6c.

## Benefits (Phase 1)

| Benefit | Before | After |
|---|---|---|
| Route guards | `?view=` invisible to guards | `/registrar/queue` checked by `RouteAccessBoundary` |
| Browser Back | Unreliable (query param only) | Reliable (path-based navigation) |
| Deep linking | `/registrar?view=queue` (fragile) | `/registrar/queue` (stable) |
| DevTools | Single route entry | 3 route entries (visible in React Router DevTools) |
| Page titles | Generic "Registrar Panel" | Specific: "Registrar — Welcome", "Registrar — Queue" |
| SEO | One URL for all views | Distinct URLs per view |

## Verification

```bash
# Verify routes are registered
grep -E "id: 'registrar-(home|welcome|queue)'" frontend/src/routing/routeRegistry.js

# Verify navigation helpers
node -e "
const { getViewFromPath, getRegistrarPath } = require('./frontend/src/pages/registrar/registrarNavigation.js');
console.log(getViewFromPath('/registrar/welcome'));  // 'welcome'
console.log(getViewFromPath('/registrar/queue'));    // 'queue'
console.log(getViewFromPath('/registrar'));           // null (worklist)
console.log(getRegistrarPath('welcome'));             // '/registrar/welcome'
"

# Verify backward compat — both URLs should render the same view
# /registrar?view=welcome  →  shows welcome dashboard
# /registrar/welcome       →  shows welcome dashboard (canonical)
```

## Audit Score Impact

| Section | Before | After Phase 1 | After Phase 2 (projected) |
|---|---|---|---|
| §5.1 Information Architecture | 5/10 | **6/10** | 8/10 |
| §5.2 Navigation | 4/10 | **5/10** | 7/10 |
| §5.12 Scalability | 3/10 | **4/10** | 6/10 |

Phase 1 improves scores by adding canonical routes and infrastructure. Phase 2 (full migration) would complete the improvement.
