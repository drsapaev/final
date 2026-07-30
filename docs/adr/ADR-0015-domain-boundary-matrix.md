# ADR-0015 — Domain Boundary Matrix

**Status:** Accepted
**Created:** 2026-07-31
**Depends on:** ADR-001 (backend SSOT), ADR-002 (generated DTO immutable), ADR-003 (DTO→mapper→domain), ADR-0013
**Source audit:** `scripts/audit-2-violations.csv` (23 violations), `scripts/audit-2-layer-imports.csv` (25 layer-imports)

## Summary

The codebase has a four-layer type/data flow:

```
REST DTO    (types/api.ts, types/generated/api.ts — backend-shaped)
   ↓  (pure mapper function, no React)
Mapper      (api/mappers/*.ts)
   ↓
Domain      (types/domain/*.ts — branded IDs, business unions)
   ↓
Hook        (hooks/*.ts — consumes domain only)
   ↓
Component   (components/*.tsx — consumes domain only)
```

This ADR documents the import rules between layers and the current
violation inventory.

## Layer responsibilities

| Layer | Path | Imports allowed | Imports forbidden |
|-------|------|-----------------|-------------------|
| **api-type** | `types/api.ts`, `types/generated/api.ts` | (stdlib only) | `types/domain/*`, anything React |
| **api-mapper** | `api/mappers/*.ts` | `types/api`, `types/domain`, `utils/type-guards` | React, hooks, components |
| **domain-type** | `types/domain/*.ts` | `types/domain/*` (intra-domain), `types/branded` | `types/api`, `types/generated`, React |
| **api-client** | `api/client.ts`, `api/runtime.ts`, `api/index.ts` (barrel) | `types/api`, `utils/logger`, `utils/tokenManager` | `types/domain`, React, hooks |
| **api-other** | `api/patients.ts`, `api/payments.ts`, etc. (resource modules) | `api/client`, `types/api`, `types/domain` | React, hooks, components |
| **hook** | `hooks/*.ts` | `api/*` (client + resource modules + mappers), `types/domain`, `types/async-state`, `types/chat-session-state` | `types/api`, `types/generated`, `axios` directly, components |
| **component** | `components/*.tsx` | hooks, `types/domain`, `utils/*`, UI libraries | `types/api`, `types/generated`, `api/*` (except the `api/index.ts` barrel re-export of `api`), `api/mappers`, `axios` |
| **page** | `pages/*.tsx` | (same as component) | (same as component) |

## Current violations (audit-2, 2026-07-31)

**23 violations across 21 files.** All at the **runtime** boundary
(components/pages calling `api/` modules directly). The **type-level**
boundary is fully clean: 0 violations of "component/hook imports
`types/api` or `types/generated` directly".

### Violation breakdown

| Category | Count | Files |
|----------|------:|-------|
| `component imports api/ module directly` | 22 | 20 |
| `hook imports axios directly` | 1 | 1 (`hooks/useAdminData.ts:3`) |
| **Total** | **23** | **21** |

### Worst offending files

| File | Violations |
|------|-----------:|
| `components/admin/ClinicSettings.tsx` | 2 (lines 5, 6) |
| `components/wizard/AppointmentWizardV2.tsx` | 2 (lines 40, 47) |
| `components/QueueIntegration.tsx` | 1 |
| `components/admin/BenefitSettings.tsx` | 1 |
| `components/admin/PaymentProviderSettings.tsx` | 1 |

(19 other files tie at 1 violation each — see `scripts/audit-2-violations.csv`.)

### Worst layer-to-layer flow

**`component → api-other`: 22 violations.** Components call `api/`
runtime modules (e.g. `adminSettings`, `registrar`, `mcpClient`,
`labReporting`, `queue`, `services`, `payments`, `patients`,
`ticketPrintSettings`, `api/index.ts` barrel) instead of going through
a hook.

The violations cluster around 6 `api/` modules. The biggest cleanup
opportunity is `adminSettings` (5 components importing it directly) —
introducing a `useAdminSettings` hook would resolve all 5 violations.

## What is clean (ZERO violations)

| Boundary | Status |
|----------|--------|
| `component → types/api` | ✅ 0 violations |
| `component → types/generated` | ✅ 0 violations |
| `component → api/mappers` | ✅ 0 violations |
| `component → axios` | ✅ 0 violations |
| `hook → types/api` | ✅ 0 violations |
| `hook → types/generated` | ✅ 0 violations |
| `hook → api/mappers` | ✅ 0 violations (and not a violation — mappers SHOULD be called by hooks) |
| `domain-type → types/api` | ✅ 0 violations |
| `domain-type → types/generated` | ✅ 0 violations |
| `api-type → types/domain` | ✅ 0 violations |

**Headline finding:** The TYPE-level boundary is enforced by convention
+ the `*Dto` suffix convention + the `api/mappers/index.ts` docstring
rules. All 23 remaining violations are at the RUNTIME boundary.

## Special cases (documented exceptions)

1. **Test files** may import anything. 2 of the 22 component→api-other
   violations are in `__tests__/` files exercising the component + API
   contract together. This is a common test pattern and is acceptable.
   ADR-0015 carves out a separate policy: tests may import from any
   layer, but production code MUST NOT.

2. **Soft mappers** (`api/mappers/chat.ts`, `api/mappers/queue.ts`)
   declare local `type ChatDtoLike = Record<string, unknown>` instead
   of importing actual `*Dto` types. They accept any shape and just
   normalize field names. The `queue.ts` header explicitly justifies
   this: "Some queue endpoints return free-form dicts that don't have a
   stable domain type yet." This is acceptable for unstable shapes; the
   mapper should be upgraded to a typed mapper when the backend contract
   stabilizes.

3. **`api/index.ts` barrel** is treated as `api-other` (forbidden for
   components). `components/search/GlobalSearchBar.tsx:9` does
   `import { api } from '../../api';` (the barrel). This is semantically
   equivalent to importing from `api/client`, but ADR-0015 keeps the
   rule sharp: components should not import from `api/*` at all — they
   should call a hook.

4. **DTO layer is two single files**, not a directory:
   `types/api.ts` (hand-written) + `types/generated/api.ts` (generated).
   Both are off-limits to components/hooks.

5. **`types/ui.ts:62` declares an incompatible `AsyncState<T>` interface**
   (`{ data: T | null; loading: boolean; error: unknown; lastFetchedAt: number | null }`)
   which conflicts with the canonical `AsyncState<T>` discriminated
   union in `types/async-state.ts`. Audit confirmed `types/ui.ts` has
   **zero importers** — the interface is dead code. ADR-0016 will
   prescribe removal (or rename to `LegacyAsyncState` if any hidden
   consumer resurfaces).

## Recommended actions

This ADR documents the current state. Concrete remediation is owned by
future sprints:

1. **Introduce `useAdminSettings` hook** → resolves 5 component→api-other
   violations in `adminSettings` cluster.
2. **Introduce hooks for the remaining 5 worst-offender api modules**
   (`registrar`, `mcpClient`, `labReporting`, `queue`, `services`) →
   resolves the remaining 17 component→api-other violations.
3. **Replace `import axios from 'axios'` in `hooks/useAdminData.ts:3`**
   with `import { api } from '../api/client'` → resolves the only
   hook→axios violation.
4. **Add an ESLint `no-restricted-paths` rule** to enforce the boundary
   automatically. Suggested config:
   ```js
   'no-restricted-paths': ['error', {
     zones: [
       { target: './src/components', from: './src/api' },
       { target: './src/components', from: './src/types/api.ts' },
       { target: './src/components', from: './src/types/generated' },
       { target: './src/hooks', from: './src/types/api.ts' },
       { target: './src/hooks', from: './src/types/generated' },
     ]
   }]
   ```
   This rule would fail CI on any new violation. Existing 23 violations
   can be marked with `// eslint-disable-next-line no-restricted-paths`
   + a TECH-DEBT marker until they are remediated.

## Rule of thumb

> "If a component imports from `api/` or `types/api`, the boundary is
> broken. Add a hook."

This ADR is the single source of truth for layer boundaries. ADR-0013
explains state patterns; ADR-0015 explains import boundaries.
