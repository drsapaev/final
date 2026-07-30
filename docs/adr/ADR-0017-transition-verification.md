# ADR-0017 — Transition Verification

**Status:** Accepted
**Created:** 2026-07-31
**Depends on:** ADR-0013 (ChatSessionState invariants)
**Source tests:** `frontend/src/types/__tests__/chat-session-state.test.ts` (107 tests)

## Summary

The `ChatSessionState` type from ADR-0013 ships two finite state machines
(connection status + stream status) with explicit allowed-edge tables.
This ADR prescribes treating those tables as **finite state machines**
and verifying them with table-driven tests covering four properties:
reachability, forbidden-edge rejection, no-dangling-states, and
idempotency.

## The two state machines

### Connection status (5 states, 11 allowed edges)

States: `idle`, `connecting`, `connected`, `reconnecting`, `disconnected`

Allowed edges (from ADR-0013 §2):

| From \ To      | idle | connecting | connected | reconnecting | disconnected |
|----------------|------|------------|-----------|--------------|--------------|
| idle           |  ✓   |     ✓      |           |              |      ✓       |
| connecting     |      |     ✓      |     ✓     |       ✓      |      ✓       |
| connected      |      |     ✓      |     ✓     |       ✓      |      ✓       |
| reconnecting   |      |     ✓      |     ✓     |       ✓      |      ✓       |
| disconnected   |      |     ✓      |           |              |      ✓       |

Self-loops (diagonal) are always allowed (idempotency).

Forbidden edges (will be rejected by `isValidConnectionTransition` and
silently no-op'd by `applyConnectionTransition`):
- `idle → connected` — must go through `connecting`
- `idle → reconnecting` — nothing to reconnect to
- `disconnected → connected` — must re-init via `connecting`
- `disconnected → reconnecting` — `disconnected` is terminal

### Stream status (3 states, 4 allowed edges)

States: `idle`, `streaming`, `completed`

Allowed edges:

| From \ To    | idle | streaming | completed |
|--------------|------|-----------|-----------|
| idle         |  ✓   |     ✓     |           |
| streaming    |  ✓   |     ✓     |     ✓     |
| completed    |  ✓   |     ✓     |     ✓     |

Forbidden edges:
- `idle → completed` — must stream first

## Four verified properties

### Property 1: Reachability

Every vertex is reachable from `idle` via allowed edges. Verified by BFS
from `idle` using `isValidConnectionTransition` / `isValidStreamTransition`
as the edge predicate.

**Test:** "connection: every status is reachable from idle via allowed
edges" / "stream: every status is reachable from idle via allowed edges"

**Why it matters:** if a state were unreachable, the type would allow
declaring it but no code path could ever produce it. That's dead code at
best and a latent bug at worst.

### Property 2: Forbidden edges rejected + applicator is a no-op

Every transition NOT in the allowed-edge table is rejected by the
validator AND a no-op for the applicator. Verified by table-driven test
covering all 5×5 = 25 (connection) + 3×3 = 9 (stream) = 34 transitions.

For forbidden edges, the applicator returns the previous state
**unchanged** (same reference, `next === prev`). This is critical: a
forbidden transition indicates a logic bug in the caller; we surface it
loudly in dev (`console.warn`) but never crash production and never
silently corrupt state.

**Tests:** 25 connection cases + 9 stream cases + 9 forbidden-connection
no-op cases + 4 forbidden-stream no-op cases = 47 tests.

### Property 3: No dangling states

Every state has at least one outgoing edge (excluding self-loops). A
state with no outgoing edges would be a trap — the state machine could
enter it but never leave.

**Test:** "connection: every status has at least one outgoing edge" /
"stream: every status has at least one outgoing edge"

### Property 4: Idempotency

`from → from` is always allowed (self-loop) and is a no-op for the
applicator. Verified by table-driven test covering all 5 connection
statuses + all 3 stream statuses.

**Why it matters:** WebSocket `onopen` can fire multiple times in some
edge cases. The applicator must tolerate `connected → connected`
without resetting state or clearing error.

## Test inventory

**File:** `frontend/src/types/__tests__/chat-session-state.test.ts`
**Total:** 107 tests, 0 failures, ~13ms runtime.

| Suite | Tests | What it verifies |
|-------|------:|------------------|
| Property 1: reachability from idle | 2 | BFS from idle visits all states |
| Property 2: forbidden edges rejected | 47 | Full transition matrix + forbidden no-op |
| Property 3: no dangling states | 2 | Every state has ≥1 outgoing edge |
| Property 4: idempotency | 12 | Self-loops allowed + no-op |
| Transition table matches ADR-0013 §2 | 34 | Drift detection between source and ADR |
| Applicator side-effects | 8 | clearError / resetReconnectAttempt / setChatError / incrementReconnectAttempt |
| Reconnect lifecycle scenario | 2 | Full connected → reconnecting → connected + give-up-after-5-attempts |
| **Total** | **107** | |

## Why table-driven, not property-based

The state space is small (5×5 + 3×3 = 34 transitions total). Explicit
enumeration reads better than generated cases for this kind of
invariant. Property-based testing (`fast-check`) is overkill: it would
generate the same 34 cases with extra setup complexity.

If the state space ever grows past ~10 states per dimension, switch to
property-based. Until then, table-driven is the right tool.

## Drift detection

The test suite duplicates the allowed-edge tables
(`EXPECTED_CONNECTION_EDGES` and `EXPECTED_STREAM_EDGES`) and asserts
that `isValidConnectionTransition` / `isValidStreamTransition` agree
with the expected table for every (from, to) pair.

**Why duplicate:** if someone edits the source table in
`chat-session-state.ts` without updating ADR-0013 §2, this test will
fail. The fix is to update BOTH the source AND the ADR — never just
one. The test enforces this contract.

## Verification commands

```bash
cd frontend
npx vitest run src/types/__tests__/chat-session-state.test.ts
```

Expected output: 107 tests passed, 0 failed.

The dev-only `console.warn` messages in stderr are EXPECTED — they
confirm the applicator detects forbidden transitions and surfaces them
loudly in dev. Production builds (`process.env.NODE_ENV === 'production'`)
suppress these warnings.

## Future work (out of scope for this ADR)

1. **Apply the same pattern to `useEMR`'s reducer.** The EMR state
   machine (`draft` → `dirty` → `saving` → `saved` → `conflict` →
   `readonly` → `autosaving`) does not currently have explicit
   transition validators. A follow-up sprint could extract
   `isValidEmrTransition` and add equivalent property tests.

2. **Apply the same pattern to `useAppointments` and other hooks** that
   have implicit state machines (e.g. `pending` → `confirmed` →
   `completed` / `cancelled`).

3. **Add an ESLint rule** banning direct assignment to
   `ChatSessionState` fields outside the transition helpers. Currently
   the helpers are conventional; an ESLint rule would make them
   mandatory.

## Rule of thumb

> "If a state machine has more than 3 states, encode the allowed edges
> in a table and test all four properties. If it has fewer than 3
> states, a plain discriminated union is enough."

This ADR is the single source of truth for transition verification.
ADR-0013 explains the state shape; ADR-0017 verifies the state machine
is correct.
