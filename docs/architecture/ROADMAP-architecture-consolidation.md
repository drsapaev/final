# Architecture Consolidation — Sprint Roadmap

**Status:** Planning (awaiting PR #2619 merge)
**Author:** operator (Z)
**Created:** 2026-07-31
**Depends on:** PR #2619 (sprint-b-plus/architecture-decisions) merged to main

---

## Why this sprint exists

After PR #2619 the codebase has four coexisting state patterns
(`AsyncState`, `ChatSessionState`, `useReducer`, plain `useState`) plus a
DTO→Domain→Hook→Component layering. Each pattern was introduced for a real
reason — but no document yet checks that **together they form a coherent
system**, not a pile of local decisions.

The goal of this sprint is **not to find new problems**. It is to verify
that the patterns already in place actually compose into something a new
contributor can reason about.

## Definition of done (qualitative, not numeric)

The sprint is finished when the answer to all five questions below is
**"yes, and here is the document that says so"**:

1. Can a new hook pick the correct state pattern without asking anyone?
2. Is there a single DTO → Domain boundary enforced across the codebase?
3. Is there a single error strategy, or an explicit taxonomy that explains
   why there are several?
4. Is there a single state-transition strategy, or an explicit list of
   which state machines use which transition rules?
5. Is there a single runtime-validation strategy, or an explicit list of
   which layers validate what?

If any answer is "no", the sprint produces a small ADR that either
unifies the layer or documents why the split is intentional. **The
deliverable is never a new generic type.** The system got better
precisely because different problems got different models; consolidating
should not collapse that.

## What this sprint explicitly does NOT do

- ❌ Create another generic `State<T>` / `Result<T, E>` abstraction
- ❌ Unify `AsyncState` and `ChatSessionState` into a single type
- ❌ Rewrite `useEMR` (it correctly uses `useReducer`)
- ❌ Introduce a global reducer / store
- ❌ Refactor for refactoring's sake — every change must trace back to an
  incoherence found in one of the four ADRs below

---

## Step 1 — Close PR #2619 first

This sprint must evaluate **merged state**, not a local branch. Before any
ADR-0014 work begins:

- [ ] PR #2619 passes code review
- [ ] PR #2619 merged to main
- [ ] CI green on main (Frontend lint ✅, Frontend build ✅, PR Review ✅,
      Regression Audit ✅)
- [ ] `useAIChat` public API surface verified unchanged
  - 18 fields preserved (sessions, currentSession, messages, loading,
    streaming, error, connected, 6 REST methods, 3 WS methods, 3
    utilities)
  - 1 new additive field: `sessionState: ChatSessionState`
  - `AIChatWidget` (only consumer) runs without code changes
  - vitest `useAIChat.test.tsx` race-condition test still green
- [ ] Worklog entry confirms merged hash + verified API

Only after every checkbox above is ticked does Step 2 begin.

---

## Step 2 — Four ADRs (delivered as a single coherent set)

The four ADRs below are written together. They reference each other.
Splitting them across sprints would defeat the purpose — they exist to
show that the four dimensions (state, boundary, error, transition) form
one system.

### ADR-0014 — State Pattern Matrix

**Question:** *Can a developer pick the right state pattern without
discussion?*

Document, for each of the four patterns, where it is permitted and where
it is forbidden.

| Pattern | Permitted for | Forbidden for |
|---------|---------------|---------------|
| `AsyncState<T>` | HTTP resources with loading lifecycle | Streaming, workflow state machines, UI state |
| `ChatSessionState` | WebSocket / chat streaming transport | CRUD API, simple fetch, UI state |
| `useReducer` | Workflow / state machines (e.g. EMR draft→dirty→saving→conflict) | Simple async fetches, UI state, transport |
| `useState<T>` | Local UI state (selectedId, search, modal, tab, filter) | Async lifecycle, streaming, workflow |

**Inputs to ADR-0014:**
- ADR-0013 (already merged) — the per-pattern rules
- A codebase audit listing every hook and which pattern it uses
- Concrete "you are here" examples for each pattern (≥2 real hooks each)

**Done when:** A new contributor reading only ADR-0014 can correctly
classify a hypothetical new hook ("a hook that loads a paginated patient
list with search and filter") into `AsyncState<Patient[]>` +
`useState<string>` for search + `useState<Filter>` for filter — without
asking anyone.

### ADR-0015 — Domain Boundary Matrix

**Question:** *Is there a single DTO → Domain boundary?*

The expected layering (already partially in place):

```
REST DTO  (types/api/*.ts, generated-shaped)
   ↓  (mapper function — pure, no React)
Mapper    (api/mappers/*.ts)
   ↓
Domain    (types/domain/*.ts, branded IDs, business unions)
   ↓  (hook consumes domain only)
Hook      (hooks/*.ts)
   ↓
Component (components/*.tsx, never imports types/api/* directly)
```

For each layer, ADR-0015 must answer:
- What can it import?
- What must it NOT import?
- Where are the current violations (if any)?

**Inputs to ADR-0015:**
- Existing `ADR-001-backend-ssot.md`, `ADR-002-generated-dto-immutable.md`,
  `ADR-003-dto-mapper-domain.md`, `ADR-004-no-ts-nocheck-policy.md`
- `eslint` import-boundary rule config (if it exists; if not, this ADR
  proposes one)
- A `grep` audit: count of `import ... from '../../types/api'` inside
  `components/` — should be 0

**Done when:** Either (a) there are zero boundary violations, or (b)
every violation is documented with a TECH-DEBT marker and a remediation
owner.

### ADR-0016 — Error Taxonomy

**Question:** *Is there a single error strategy, or an explicit taxonomy
that explains the split?*

Current error types in the codebase (preliminary list — to be audited):

- `ChatError` (`types/chat-session-state.ts`) — structured
  `{ code, message, retryable }`
- `AsyncState<T>` error branch — bare `string`
- `useEMR` reducer error — likely `string` inside reducer state (TBC)
- `api/client.ts` — likely an `AxiosError`-shaped error (TBC)
- `getErrorMessage()` util — coerces unknown → string

**Risk:** these may silently duplicate each other. `ChatError` already
exists because `string` was insufficient for chat; if the same is true
for other layers and we missed it, that's a hidden inconsistency.

**Inputs to ADR-0016:**
- Inventory of every error type/shape used in `src/`
- Per-layer audit: which layer produces which error, which layer
  consumes which error
- A small contract proposal: `interface AppError { code: string;
  message: string; retryable: boolean; source: 'network' | 'auth' |
  'model' | 'business' | 'unknown' }` — proposed only if it doesn't
  collapse useful distinctions

**Done when:** ADR-0016 either defines one shared `AppError` contract
or explicitly lists which layers need a specialized error and why. It
does NOT force `ChatError`'s 7 codes onto `AsyncState` if `AsyncState`'s
callers don't actually need them.

### ADR-0017 — Transition Verification

**Question:** *Is there a single state-transition strategy?*

`ChatSessionState` already ships `isValidConnectionTransition` /
`isValidStreamTransition` with explicit allowed-edge tables. ADR-0017
treats these as **finite state machines** and verifies them with
property-based / table-driven tests:

- Every vertex is reachable from `idle`
- No forbidden transition can be forced via the public API
- No "dangling" state (every state has at least one outgoing edge)
- The `applyConnectionTransition` / `applyStreamTransition` enforcers
  return the previous state unchanged on a forbidden edge (no silent
  corruption)

**Inputs to ADR-0017:**
- `frontend/src/types/chat-session-state.ts` — the type + transition
  validators
- `fast-check` (already a dev dep? TBC) for property-based tests, or
  plain table-driven tests if not
- `vitest` test file at `frontend/src/types/__tests__/chat-session-state.test.ts`

**Done when:** The test suite fails if anyone adds a forbidden edge to
the allowed-transition table, or removes an edge that breaks
reachability.

---

## Step 3 — Maturity check (qualitative, not numeric)

After Step 2 ships, the next sprint evaluates maturity by the five
questions in the "Definition of done" section above — not by counting
`any` / `string | number` / `useState<string | null>`. If all five
answers are "yes", that is a more significant architectural milestone
than any further reduction in those counts.

## Out of scope (explicitly)

- New generic state types
- Merging `AsyncState` and `ChatSessionState`
- Rewriting `useEMR`
- Global reducer / store
- Any change that does not trace to a concrete incoherence found in
  ADR-0014 / 0015 / 0016 / 0017

## Reference

- ADR-0013 (merged with PR #2619) — State Management Boundaries
- `docs/adr/ADR-0013-state-management-boundaries.md` — the per-pattern rules
- `frontend/src/types/chat-session-state.ts` — ChatSessionState +
  transition validators
- `frontend/src/types/async-state.ts` — AsyncState<T>
- This roadmap: `docs/architecture/ROADMAP-architecture-consolidation.md`
