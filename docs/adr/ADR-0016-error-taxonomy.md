# ADR-0016 — Error Taxonomy

**Status:** Accepted
**Created:** 2026-07-31
**Depends on:** ADR-0013, ADR-0014
**Source audit:** `scripts/audit-3-error-types.csv` (162 rows), `scripts/audit-3-error-handling.csv` (2472 rows)

## Summary

The codebase has **three distinct error-type families**. This ADR
documents WHY they are kept separate and prescribes the canonical shape
for each layer. It explicitly does NOT unify them into a single
`AppError` — the families serve genuinely different roles.

## The three error-type families

### Family A — Structured error (ChatError)

```typescript
type ChatErrorCode =
  | 'network_error' | 'auth_error' | 'model_error' | 'rate_limit'
  | 'cancelled' | 'contract_mismatch' | 'unknown';

interface ChatError {
  code: ChatErrorCode;
  message: string;
  retryable: boolean;
}
```

**Used by:** `ChatSessionState` (the WebSocket transport layer of
`useAIChat`).

**Why structured:** the UI needs to branch on `code`. On `auth_error`,
hide the Retry button and force re-login. On `rate_limit`, show an
upgrade prompt. On `cancelled`, do nothing. A bare `string` cannot
express this.

### Family B — Bare string error (AsyncState error variant)

```typescript
type AsyncState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: string };  // ← bare string
```

**Used by:** 14 hooks (the AsyncState adopters per audit-1).

**Why bare string:** the UI only displays the message. No code-branching
needed. Forcing a `ChatError` shape here would force every consumer to
handle `code` and `retryable` that they never use.

### Family C — Unknown (reducer escape hatch)

```typescript
interface EmrState {
  // ...
  error: unknown;  // ← escape hatch
}
```

**Used by:** `useEMR` (the only useReducer hook).

**Why unknown:** the EMR reducer catches errors from heterogeneous
sources (load, save, sign, amend, autosave). Each source has a different
shape. The reducer does not need to interpret the error — it just stores
it. The UI calls `getErrorMessage(state.error)` to extract a string.

## Current inventory (audit-3, 2026-07-31)

| Metric | Count |
|--------|------:|
| Error-type declarations across the codebase | 161 |
| Distinct error type names | ~67 |
| Error-handling sites (catch + throw + setError) | 2,472 |
| Unique files with error handling | ~440 |
| Try/catch blocks in components/pages (anti-pattern) | 608 |
| Silent-swallow catch blocks (log only, no rethrow/setError) | ~502 |
| Component files importing error-type symbols directly | 63 |

### Per-layer error-handling distribution

| Layer | throw | rethrow | catch | getErrMsg | setErr | tryCmp | impErr | subtotal |
|-------|------:|--------:|------:|----------:|-------:|-------:|-------:|---------:|
| api | 9 | 13 | 25 | 3 | 0 | 0 | 0 | 50 |
| api/mappers | 21 | 2 | 6 | 0 | 0 | 0 | 0 | 29 |
| **components** | 52 | 16 | **466** | 76 | **278** | **464** | 44 | **1396** |
| contexts | 5 | 8 | 25 | 0 | 0 | 0 | 0 | 38 |
| hooks | 26 | 54 | 138 | 32 | 97 | 0 | 0 | 347 |
| **pages** | 17 | 7 | 144 | 61 | 51 | **144** | 19 | **443** |
| services | 4 | 1 | 25 | 7 | 0 | 0 | 0 | 37 |
| stores | 0 | 0 | 13 | 0 | 0 | 0 | 0 | 13 |
| theme | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 4 |
| types | 10 | 2 | 2 | 0 | 1 | 0 | 0 | 15 |
| utils | 17 | 6 | 61 | 6 | 2 | 0 | 0 | 92 |
| other | 0 | 2 | 6 | 0 | 0 | 0 | 0 | 8 |

**Hotspot:** `components/` layer carries 56% of all error-handling
sites. This is a strong signal that error handling is leaking into
components instead of staying in hooks.

## Duplication analysis

### Bucket A — `{ code, message, retryable }` (ChatError-shape)
- 1 type: `ChatError` (types/chat-session-state.ts)
- **No duplication.** This is the only structured-error type.

### Bucket B — `{ response?: { status?, data? }, message? }` (AxiosLikeError-shape)
**18 type declarations across 4 layers** — massive structural duplication:

| Type | Files | Layer |
|------|-------|-------|
| `WrappedApiError` (×2) | `api/patients.ts`, `api/payments.ts` | api |
| `ApiErrorResponse` (×2) | `components/admin/WebhookManager.tsx`, `components/security/TwoFactorManager.tsx` | components |
| `AxiosLikeError` (×3) | `api/interceptors.ts`, `utils/type-guards.ts`, `utils/networkErrorMessages.ts` | api / utils |
| `ErrorWithExtras` (×2) | `components/TelegramManager.tsx`, `pages/RegistrarPanel.tsx` | components / pages |
| `ErrorWithResponse` (×1) | `utils/errorHandler.ts` | utils |
| `EMRApiError` (×1) | `types/domain/emr.ts` | domain |
| `LocalRateLimitError` (×1) | `api/client.ts` | api |
| `CatchError` (×3) | `hooks/useApi.ts`, `hooks/useDoctorQueue.ts`, `hooks/usePatients.ts` | hooks |
| `WebAuthnErrorResponse` (×1) | `hooks/useWebAuthn.tsx` | hooks |

**All define the same Axios-shape.** This is the single biggest cleanup
opportunity in the error taxonomy.

### Bucket C — `class XError extends Error`
- 1 type: `AuthInvariantViolationError` (types/auth-mapper.ts)
- The only genuine JS Error subclass in the codebase. Keep as-is.

### Other duplications

1. **`AsyncState` declared in 2 incompatible ways.** `types/async-state.ts`
   has the canonical discriminated union (per ADR-0013).
   `types/ui.ts:62` has a stale interface with
   `{ data: T | null; loading: boolean; error: unknown; lastFetchedAt: number | null }`.
   Audit confirmed `types/ui.ts` has **zero importers** — the interface
   is dead code. **Action: delete the dead interface.**

2. **`getErrorMessage()` exported twice.**
   - `utils/type-guards.ts:42` — 1-arg signature: `getErrorMessage(err: unknown): string`
   - `utils/errorHandler.ts:80` — 2-arg signature: `getErrorMessage(err: unknown, fallbackMessage?: string): string`
   The 2-arg version is a strict superset. **Action: consolidate to one
   export in `utils/errorMessage.ts` (or keep in `utils/type-guards.ts`);
   deprecate the other.**

3. **`useErrorHandler` exported twice** with different shapes:
   - `components/common/ErrorBoundary.tsx:204` — returns `{ error, handleError, resetError }`
   - `utils/errorHandler.ts:227` — returns a function
   **Action: rename one of them.** Suggest renaming the utils version
   to `withErrorBoundaryHandler` or similar.

## Decision: do NOT unify into a single AppError

The three families serve genuinely different roles:

| Family | Type | Used by | Purpose |
|--------|------|---------|---------|
| A | `ChatError { code, message, retryable }` | `useAIChat` WS layer | UI branches on `code` |
| B | `AsyncState<T>` error variant (bare `string`) | 14 hooks (one-shot REST) | UI only displays the message |
| C | `EmrState.error: unknown` | `useEMR` (reducer-based) | Escape hatch for heterogeneous catch sites |

Forcing them into a single `AppError { code, message, retryable }` would
either:
- **over-specify Family B** (14 hooks would have to handle `code` /
  `retryable` they don't use), or
- **under-specify Family A** (lose the structured codes that drive UI
  branching), or
- **break Family C** (the EMR reducer legitimately cannot predict error
  shapes from 5 different operations).

## Concrete actions for this sprint

These are documented as decisions; the actual code changes are
scheduled for follow-up sprints:

1. **Extract a shared `AxiosLikeError` interface** to a new
   `types/errors.ts`. Replace the 14 duplicate declarations in Bucket B.
   This is the single biggest cleanup.

2. **Delete the dead `AsyncState` interface in `types/ui.ts:62`.**
   Verified zero importers.

3. **Consolidate the two `getErrorMessage()` exports** into one. Suggest
   `utils/errorMessage.ts` as the canonical location.

4. **Rename one of the two `useErrorHandler` exports.** Suggested:
   rename the utils version to `withErrorBoundaryHandler`.

5. **Tighten `EmrState.error: unknown` → `string | null`** by having the
   EMR reducer call `getErrorMessage(err)` before dispatching
   `saveError(...)`. Low-risk change.

6. **Add `chatError: ChatError | null` field to `useAIChat`'s public
   return** so consumers that need `code`-branching can access the
   structured ChatError (currently flattened to `string | null` via
   `getChatErrorMessage`).

7. **Add ESLint rule** banning `try { ... } catch` in `components/` and
   `pages/`. 608 violations exist today; the rule can be added with
   auto-fix suggestions ("move this catch into the hook that owns the
   state"). Existing violations get `// eslint-disable-next-line` +
   TECH-DEBT marker.

8. **Document policy on silent-swallow catch blocks.** ~502 catch
   blocks only `logger.error` / `logger.warn` and swallow. ADR-0016
   prescribes: **silent-logging-without-propagation is acceptable only
   in non-critical paths** (e.g. analytics, telemetry). In critical
   paths (data fetch, save, sign), catch blocks MUST either rethrow or
   surface to UI via `setError(...)`.

## Error flow diagram

```
   Backend returns HTTP error
            │
            ▼
   api/client.ts (axios interceptor)
            │
            ▼
   AxiosError (raw, with response.data)
            │
            ▼
   ┌──────────────────────────────────────────────┐
   │ Hook catch block (try { fetch() } catch e)   │
   │                                              │
   │  REST hook:                                  │
   │    setState(errorState(getErrorMessage(e)))  │
   │    → stored as AsyncState.error (string)     │
   │    → UI displays message                     │
   │                                              │
   │  useAIChat WS callback:                      │
   │    setSessionState(setChatError(prev,        │
   │      chatError(inferErrorCode(e), msg,       │
   │      isRetryable(e))))                       │
   │    → stored as ChatSessionState.error        │
   │    → UI branches on code                     │
   │                                              │
   │  useEMR reducer:                             │
   │    dispatch({ type: 'saveError',             │
   │               error: e })                    │
   │    → stored as EmrState.error (unknown)      │
   │    → UI calls getErrorMessage(state.error)   │
   └──────────────────────────────────────────────┘
```

## Rule of thumb

> "If the UI needs to branch on the error, use ChatError. If the UI only
> displays the message, use AsyncState's bare string. If the reducer
> cannot predict the shape, use `unknown` and let the consumer call
> `getErrorMessage()`."

This ADR is the single source of truth for error shapes. ADR-0013
explains state patterns; ADR-0014 explains pattern selection; ADR-0015
explains import boundaries; ADR-0016 explains error shapes.
