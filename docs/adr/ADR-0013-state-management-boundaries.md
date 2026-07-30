# Sprint B+ Architecture Decision Record

## State Management Boundaries

This document defines the architectural boundary between three state management
patterns in the codebase. It serves as a project rule to prevent reverse migration
and ensure consistent state management decisions.

---

## 1. AsyncState<T> — for async resources with loading lifecycle

### When to use
AsyncState applies **only to data obtained asynchronously**. Use it when at least
**two** of the following conditions are met:

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

These are **not technical debt**. They are normal UI state and should remain as
`useState<T>`.

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

### Recommended approach
Create a specialized type:

```typescript
type ChatSessionState = {
  connectionStatus: 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'disconnected';
  streamStatus: 'idle' | 'streaming' | 'completed' | 'error';
  messages: AIAssistantMsg[];
  error: string | null;
};
```

This keeps `AsyncState` simple while giving the chat hook a purpose-built state
model that accurately represents its lifecycle.

### Current state
- `useState<ChatSession[]>` — sessions list (could use AsyncState for the list)
- `useState<ChatSession | null>` — current session (UI state, keep as useState)
- `useState<AIAssistantMsg[]>` — messages (streaming, needs specialized state)
- `useState(false)` — loading (part of async lifecycle)
- `useState(false)` — streaming (NOT part of AsyncState)
- `useState<string | null>` — error (part of async lifecycle)
- `useState(false)` — connected (NOT part of AsyncState)

### Migration plan
1. Create `ChatSessionState` type in `src/types/async-state.ts` (or separate file)
2. Replace `loading` + `streaming` + `error` + `connected` with `ChatSessionState`
3. Keep `sessions` as `AsyncState<ChatSession[]>` (it's a simple fetch)
4. Keep `currentSession` and `messages` as separate state (they have different update patterns)

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
2. Optionally add `AsyncState<void>` for save/sign/amend operations (if there's value in tracking their individual loading/error states separately from the reducer)
3. This is low priority — the current `useReducer` approach is architecturally correct

---

## 4. Summary

| Pattern | Use case | Examples |
|---------|----------|----------|
| `AsyncState<T>` | Async resources with loading lifecycle | useUsers, useReports, useFinance |
| `useReducer` | Complex workflows / state machines | useEMR (draft → dirty → saving → conflict) |
| `useState<T>` | Local UI state | selectedId, search, modalOpen, activeTab, filter |
| Specialized state | Streaming / real-time | useAIChat (ChatSessionState) |

### Migration rules
1. **Do** migrate to `AsyncState` when: HTTP request + loading + error + success + retry
2. **Do not** migrate to `AsyncState` when: no async lifecycle (UI state)
3. **Do not** migrate `useReducer` to `AsyncState` (different pattern)
4. **Do** create specialized types for streaming/real-time state
5. **Do not** create abstractions "for the future" — only when there's actual repetition

### Next steps
- P1: Create `ChatSessionState` for useAIChat
- P2: Leave useEMR as-is (useReducer is correct)
- P3: Do not touch simple `useState<string | null>` (UI state)
- P4: After 40+ AsyncState usages, evaluate if `useAsyncResource` / `createAsyncState` helpers would reduce boilerplate
