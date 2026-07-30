# ADR-0013 — State Management Boundaries

**Status:** Accepted (revised)
**Last updated:** 2026-07-31

## Summary

This ADR defines the architectural boundary between four state management
patterns in the frontend codebase. It serves as a project rule to prevent
reverse migration and ensure consistent state management decisions.

| Pattern | Use case | Examples |
|---------|----------|----------|
| `AsyncState<T>` | Async resources with loading lifecycle | useUsers, useReports, useFinance |
| `useReducer` | Complex workflows / state machines | useEMR (draft → dirty → saving → conflict) |
| `useState<T>` | Local UI state | selectedId, search, modalOpen, activeTab, filter |
| Specialized state | Streaming / real-time transport | useAIChat (`ChatSessionState`) |

---

## 1. AsyncState<T> — for async resources with loading lifecycle

### When to use
AsyncState applies **only to data obtained asynchronously**. Use it when at
least **two** of the following conditions are met:

- There is an HTTP/WebSocket request
- There is a `loading` state
- There is an `error` state
- There is a `success` state with data
- There is retry/refresh functionality
- The state is used by multiple callbacks

### When NOT to use
AsyncState must NOT be used for:

- `selectedId` / `selectedItem` — local UI selection state
- `search` / `searchTerm` — search input state
- `modalId` / `dialogOpen` — modal visibility state
- `activeTab` — tab selection state
- `filter` / `filterType` / `filterStatus` — filter state
- Any state that does not involve an async lifecycle

These are **not technical debt**. They are normal UI state and should remain
as `useState<T>`.

### Current adoption (40 references in hooks/)
- `useUsers` — full migration ✅
- `useReports` — full migration ✅
- `useFinance` — full migration with cache-fallback ✅
- `useDoctors`, `useRoles`, `useSecurity`, `useDoctorPhrases`, `usePaymentMethods`,
  `usePayments`, `useAppointments`, `useSettings`, `useAdminData`, `useUserPreferences`
  — partial (loading+error merged into AsyncState, data separate) ✅
- `useAIChat` — NOT migrated (see §2 below)
- `useEMR` — NOT migrated (see §3 below)

---

## 2. useAIChat — specialized streaming state (NOT AsyncState)

### Why not AsyncState
`useAIChat` has a WebSocket-based streaming lifecycle that goes beyond the simple
`idle → loading → success → error` model:

- `connecting` — WebSocket connecting
- `streaming` — receiving partial messages
- `reconnecting` — connection lost, attempting reconnect
- `connected` — connection established, idle

This is a **streaming model**, not a request/response model. Forcing it into
`AsyncState<T>` would constantly work around its limitations.

### ChatSessionState — architectural invariants

The `ChatSessionState` type models the **transport layer** of the chat. It
follows six invariants. Violating any of them is a bug.

#### Invariant 1: Transport ≠ content
`ChatSessionState` MUST NOT carry chat messages. Messages live in a separate
`ChatData<TMessage>` (or just `useState<TMessage[]>` in the hook).

```typescript
interface ChatSessionState {
  connectionStatus: ConnectionStatus;
  streamStatus: StreamStatus;
  error: ChatError | null;
  reconnectAttempt: number;
}
interface ChatData<TMessage = unknown> {
  messages: TMessage[];
  activeSessionId: string | number | null;
}
```

**Why:** reconnecting the WebSocket must not invalidate the message history.
Clearing the message history must not tear down the connection. Receiving a
streaming token must not rewrite the entire state object.

#### Invariant 2: Two independent dimensions
`connectionStatus` and `streamStatus` evolve independently. We deliberately
avoid a single enum with twenty variants like
`authenticated_streaming_receiving_typing_retrying`. Such a flat enum would:
- explode combinatorially,
- force every transition to specify the full cross-product,
- make "I only changed connection" indistinguishable from "I changed everything".

#### Invariant 3: Explicit transition tables
The allowed edges are encoded in `isValidConnectionTransition` /
`isValidStreamTransition` and enforced at runtime by `applyConnectionTransition`
/ `applyStreamTransition` (dev-only `console.warn` on forbidden edges).

**Connection status transitions:**

| From \ To      | idle | connecting | connected | reconnecting | disconnected |
|----------------|------|------------|-----------|--------------|--------------|
| idle           |  ✓   |     ✓      |           |              |      ✓       |
| connecting     |      |     ✓      |     ✓     |       ✓      |      ✓       |
| connected      |      |     ✓      |     ✓     |       ✓      |      ✓       |
| reconnecting   |      |     ✓      |     ✓     |       ✓      |      ✓       |
| disconnected   |      |     ✓      |           |              |      ✓       |

Forbidden (will be logged in dev):
- `idle → connected` (must go through `connecting`)
- `idle → reconnecting` (nothing to reconnect to)
- `disconnected → connected` (must explicitly re-connect via `connecting`)
- `disconnected → reconnecting` (`disconnected` is terminal)

**Stream status transitions:**

| From \ To    | idle | streaming | completed |
|--------------|------|-----------|-----------|
| idle         |  ✓   |     ✓     |           |
| streaming    |  ✓   |     ✓     |     ✓     |
| completed    |  ✓   |     ✓     |     ✓     |

Forbidden:
- `idle → completed` (must stream first)

#### Invariant 4: Error is a structured object, not a status value
`streamStatus` does NOT have an `'error'` value. Errors live in a separate
`error: ChatError | null` field with shape `{ code, message, retryable }`.

```typescript
type ChatErrorCode =
  | 'network_error'      // WebSocket close, transport failure
  | 'auth_error'         // JWT invalid / expired / rejected
  | 'model_error'        // backend model failed to produce a response
  | 'rate_limit'         // 429 / quota exceeded
  | 'cancelled'          // user-initiated cancel
  | 'contract_mismatch'  // protocol version mismatch with backend
  | 'unknown';

interface ChatError {
  code: ChatErrorCode;
  message: string;
  retryable: boolean;
}
```

**Why:** the UI needs to differentiate between "network blip — retry in 2s",
"model overload — switch model", "rate limit — show upgrade prompt", and
"user cancelled — do nothing". A bare `streamStatus: 'error'` cannot express
this; the UI would have to re-derive the cause from string matching on the
error message.

#### Invariant 5: No reducer coupling
`ChatSessionState` is a value object. The hook may use `useState<ChatSessionState>`
or `useReducer`; either way:
- WebSocket callbacks (`onopen`, `onclose`, `onmessage`) remain separate functions,
- REST API calls (`loadSessions`, `sendMessage`) remain separate functions,
- the state type does not prescribe how transitions are dispatched.

The reducer (if any) MUST NOT know how to open a socket, parse a token, or
construct an HTTP request. Its only job is to apply the next state.

#### Invariant 6: No premature unification with AsyncState
`AsyncState` and `ChatSessionState` intentionally share no inheritance or
generic parameter. They model different lifecycles. Attempts to unify them
(e.g. `AsyncState<T>` with extra `streaming` status, or `ChatSessionState`
extending `AsyncState<TMessage[]>`) are explicitly forbidden — they collapse
the conceptual boundary and force callers to handle states that cannot occur.

### Migration plan for useAIChat
1. ✅ Create `ChatSessionState` type with the six invariants above
2. Replace four `useState` calls (`loading`, `streaming`, `error`, `connected`)
   with a single `useState<ChatSessionState>` initialized to `idleChatSessionState()`
3. Keep `messages` as a separate `useState<AIAssistantMsg[]>` (Invariant 1)
4. Keep `currentSession` as a separate `useState<ChatSession | null>` (UI state)
5. Keep `sessions` as a separate `useState<ChatSession[]>` (it could later become
   `AsyncState<ChatSession[]>`, but that is out of scope for this PR)
6. WebSocket callbacks call `applyConnectionTransition` / `applyStreamTransition`
   / `setChatError` — they never mutate `state` directly
7. REST API methods (`loadSessions`, `sendMessage`, etc.) are unchanged in shape;
   they update `messages` and `currentSession` directly, not the session state

### Backward compatibility
The hook's public return shape is preserved. The legacy boolean fields
(`loading`, `streaming`, `connected`, `error: string | null`) are derived from
`ChatSessionState` via accessors (`isChatConnecting`, `isChatStreaming`,
`isChatConnected`, `getChatErrorMessage`). Consumers do not need to change.

---

## 3. useEMR — useReducer + AsyncState for operations (NOT full migration)

### Why not migrate
`useEMR` already uses `useReducer` — this is correct because EMR has a complex
state machine:

- `draft` — unsaved changes
- `dirty` — modified since last save
- `saving` — save in progress
- `saved` — save completed
- `conflict` — concurrent edit detected
- `readonly` — signed/amended, no edits allowed
- `autosaving` — background autosave

This is a **workflow state machine**, not a simple async resource. `useReducer`
is the right tool.

### Recommended approach
Keep `useReducer` for the document state machine. Use `AsyncState` **only inside
specific operations**:

```typescript
// Inside useEMR:
const [state, dispatch] = useReducer(emrReducer, initialState);

// AsyncState for individual operations:
const [saveState, setSaveState] = useState<AsyncState<void>>(idleState());
const [loadState, setLoadState] = useState<AsyncState<EMRData>>(idleState());
```

This separates concerns:
- `useReducer` manages the document workflow (draft → dirty → saving → saved → conflict)
- `AsyncState` manages individual async operations (load, save, sign, amend)

### Current state
- `useReducer(emrReducer, initialState)` — document state machine ✅ (keep)
- `useState(false)` — writeAccessDenied (UI gate, keep as useState)
- No `useState<string | null>` — error is part of the reducer state

### Migration plan
1. Do NOT replace `useReducer` with `AsyncState`
2. Optionally add `AsyncState<void>` for save/sign/amend operations (if there's
   value in tracking their individual loading/error states separately from the
   reducer)
3. This is low priority — the current `useReducer` approach is architecturally
   correct

---

## 4. Summary table

| Pattern | Use case | Examples | What it is NOT |
|---------|----------|----------|----------------|
| `AsyncState<T>` | Async resources with loading lifecycle | useUsers, useReports, useFinance | Not for UI state, not for streaming |
| `useReducer` | Complex workflows / state machines | useEMR (draft → dirty → saving → conflict) | Not for simple async fetches, not for transport |
| `useState<T>` | Local UI state | selectedId, search, modalOpen, activeTab, filter | Not technical debt — do NOT migrate to AsyncState |
| `ChatSessionState` | Streaming / real-time transport | useAIChat | Not a generic AsyncState variant, NOT for messages |

### Migration rules
1. **Do** migrate to `AsyncState` when: HTTP request + loading + error + success + retry
2. **Do not** migrate to `AsyncState` when: no async lifecycle (UI state)
3. **Do not** migrate `useReducer` to `AsyncState` (different pattern)
4. **Do** create specialized types for streaming/real-time state — but only when
   the lifecycle genuinely diverges from `AsyncState`
5. **Do not** create abstractions "for the future" — only when there's actual
   repetition
6. **Do not** mix transport / workflow / UI state inside a single state object.
   Each layer gets its own state slot.

---

## 5. Next sprint — architectural review

After `ChatSessionState` is integrated into `useAIChat`, the next sprint is
**NOT** further state migration. Instead, it is an architectural review that
answers three questions:

1. **Is there duplication** between `AsyncState`, `ChatSessionState`, and
   `useEMR`'s workflow state? (Suspected answer: no — they model genuinely
   different lifecycles.)
2. **Can the common principles be described** without unifying the types?
   (Suspected answer: yes — see §4 above.)
3. **Have any hooks started mixing transport / workflow / UI state** inside a
   single state object? (Suspected answer: needs audit.)

The deliverable is **not** a new state type. It is a short architectural
invariants document that consolidates the rules in this ADR with concrete
examples from the codebase. This locks in the boundary and reduces the
likelihood that, six months from now, new hooks start using different patterns
for the same problem.
