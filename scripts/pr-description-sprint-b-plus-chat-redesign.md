## feat: redesign ChatSessionState per 6 architectural invariants

Revises the P1 ChatSessionState work (commit 476e639b) to enforce strict
separation between transport and content, with explicit state transition
rules. The original design violated 4 of the 6 constraints the user laid
out and would have become "another big state object" over time.

### Architecture changes (ADR-0013 §2)

Six invariants now govern `ChatSessionState`. Violating any of them is a bug.

| # | Invariant | What changed |
|---|-----------|--------------|
| 1 | **Transport ≠ content** | Removed `messages` field from `ChatSessionState`. Messages live in a separate `useState<AIAssistantMsg[]>` in `useAIChat`. Reconnecting the WebSocket no longer invalidates message history; clearing history no longer tears down the connection. |
| 2 | **No messages inside ChatSessionState** | `ChatData<TMessage>` interface defined for documentation but not bundled into transport state. |
| 3 | **Explicit transition tables** | Added `isValidConnectionTransition` / `isValidStreamTransition` with allowed-edge tables. `applyConnectionTransition` / `applyStreamTransition` enforce at runtime (dev-only `console.warn` on forbidden edges). Full matrices documented in ADR. |
| 4 | **Two independent dimensions** | `connectionStatus` × `streamStatus` evolve independently. Deliberately avoids a single enum with 20+ combined variants like `authenticated_streaming_receiving_typing_retrying`. |
| 5 | **Structured error** | Removed `'error'` value from `StreamStatus`. Errors now live in `error: ChatError \| null` with shape `{ code, message, retryable }`. UI can differentiate network blip / model overload / rate limit / user cancel / auth failure. |
| 6 | **No reducer coupling** | `useAIChat` keeps `useState<ChatSessionState>` + separate `useCallback`s for WS callbacks and REST API. The state type does not prescribe how transitions are dispatched. |

### ChatError codes

```typescript
type ChatErrorCode =
  | 'network_error'        // WebSocket close, transport failure
  | 'auth_error'           // JWT invalid / expired / rejected
  | 'model_error'          // backend model failed to produce a response
  | 'rate_limit'           // 429 / quota exceeded
  | 'cancelled'            // user-initiated cancel
  | 'contract_mismatch'    // protocol version mismatch with backend
  | 'unknown';
```

### Connection status transition matrix

| From \ To      | idle | connecting | connected | reconnecting | disconnected |
|----------------|------|------------|-----------|--------------|--------------|
| idle           |  ✓   |     ✓      |           |              |      ✓       |
| connecting     |      |     ✓      |     ✓     |       ✓      |      ✓       |
| connected      |      |     ✓      |     ✓     |       ✓      |      ✓       |
| reconnecting   |      |     ✓      |     ✓     |       ✓      |      ✓       |
| disconnected   |      |     ✓      |           |              |      ✓       |

### Stream status transition matrix

| From \ To    | idle | streaming | completed |
|--------------|------|-----------|-----------|
| idle         |  ✓   |     ✓     |           |
| streaming    |  ✓   |     ✓     |     ✓     |
| completed    |  ✓   |     ✓     |     ✓     |

### useAIChat integration

- Replaced 4 `useState` (`loading`, `streaming`, `error`, `connected`) with single `useState<ChatSessionState>` initialized to `idleChatSessionState()`.
- WS callbacks (`onopen`/`onclose`/`onerror`/`onmessage`) now call `applyConnectionTransition` / `applyStreamTransition` / `setChatError` — never assign to `sessionState` directly.
- REST API loading + errors remain separate `useState` (`restLoading`, `restError`) — REST is request/response, not streaming.
- Public return shape preserved: `loading`, `streaming`, `error`, `connected` are derived accessors for backward compatibility with `AIChatWidget`.
- `sessionState` also exposed for advanced consumers that need to distinguish `'reconnecting'` from `'connecting'`.

### Files changed (3 files, +662 / −183)

- `docs/adr/ADR-0013-state-management-boundaries.md` — added 6 invariants, transition matrices, migration plan, §5 next sprint preview
- `frontend/src/types/chat-session-state.ts` — full rewrite: structured `ChatError`, transition validators, transition applicators
- `frontend/src/hooks/useAIChat.ts` — migrated to new type; preserved public API

### Verification

| Gate | Result |
|------|--------|
| `tsc --noEmit` (strict:true) | ✅ 0 errors |
| `eslint src/**/*.{ts,tsx} --quiet` | ✅ 0 errors |
| `type-debt-check` | ✅ PASS (20/20, delta 0) |
| `regression-audit-check` | ✅ 31/31 PASS |
| `vitest useAIChat.test.tsx` | ✅ 1/1 PASS (race condition test) |
| `vitest hooks/__tests__/` | ✅ 17/17 PASS (6 files) |
| `vite build` | ✅ success |

### Next sprint preview (NOT this PR)

Per ADR-0013 §5, the next sprint is an **architectural review**, not further
state migration. Three questions to answer:

1. Is there duplication between `AsyncState`, `ChatSessionState`, and
   `useEMR`'s workflow state? (Suspected: no — different lifecycles.)
2. Can the common principles be described without unifying the types?
   (Suspected: yes — see ADR-0013 §4.)
3. Have any hooks started mixing transport / workflow / UI state inside
   a single state object? (Suspected: needs audit.)

The deliverable is a short architectural invariants document — not a new
state type. This locks in the boundary and reduces the likelihood that,
six months from now, new hooks start using different patterns for the
same problem.

### Related

- Supersedes commit 476e639b (P1 ChatSessionState type) on this branch.
- Builds on ADR-0013 (commit 48391019) — revised in this PR.
- Continues Sprint B+ (PR #2618 — useReports/useFinance AsyncState migration).
