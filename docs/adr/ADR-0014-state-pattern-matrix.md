# ADR-0014 — State Pattern Matrix

**Status:** Accepted
**Created:** 2026-07-31
**Depends on:** ADR-0013 (state management boundaries)
**Source audit:** `scripts/audit-1-hook-state-inventory.csv` (294 rows, 54 hooks)

## Summary

A new contributor reading only this ADR must be able to pick the correct
state pattern for a new hook without asking anyone. This ADR consolidates
the four permitted patterns into a single decision matrix with concrete
examples from the current codebase.

## Decision matrix

| Pattern | Permitted for | Forbidden for | Canonical example |
|---------|---------------|---------------|--------------------|
| `AsyncState<T>` | HTTP resources with loading lifecycle (idle → loading → success → error + retry) | Streaming, workflow state machines, local UI state | `useUsers.ts` — `useState<AsyncState<User[]>>` + 4 plain useStates for UI state |
| `ChatSessionState` | WebSocket / streaming transport with reconnect logic | CRUD API, simple fetch, UI state, workflow state machines | `useAIChat.ts` — `useState<ChatSessionState>` for WS transport + plain useStates for messages + REST state |
| `useReducer` | Workflow / state machines with multiple states and transitions (e.g. EMR draft→dirty→saving→conflict) | Simple async fetches, UI state, transport layer | `useEMR.ts` — `useReducer(emrReducer, initialState)` for document workflow |
| `useState<T>` | Local UI state (selectedId, search, modal, tab, filter, pagination) | Async lifecycle, streaming, workflow state machines | Every hook — UI state never migrates to AsyncState |

## Decision flowchart

```
Does the hook own an HTTP request that produces data?
├── Yes → Does it also have a WebSocket or streaming lifecycle?
│         ├── Yes → BOTH AsyncState (for REST) + ChatSessionState (for WS)
│         └── No  → AsyncState<T> for the data; useState for UI state
└── No
    ├── Does it model a workflow with discrete states (draft/dirty/saving/conflict)?
    │   └── Yes → useReducer with explicit transition table
    ├── Does it own a WebSocket connection with reconnect logic?
    │   └── Yes → ChatSessionState (transport) + useState (messages)
    └── Otherwise → useState<T> for local UI state
```

## Concrete examples from the codebase

### Pattern: AsyncState<T> + plain useStates for UI

Canonical: `useUsers.ts` (and 13 other hooks follow this exact shape)

```typescript
const [usersState, setUsersState] = useState<AsyncState<User[]>>(idleState());
// UI state stays as plain useState (NOT technical debt)
const [searchTerm, setSearchTerm] = useState('');
const [filterRole, setFilterRole] = useState('');
const [filterStatus, setFilterStatus] = useState('');
```

**Why UI state stays as useState:** `searchTerm` has no async lifecycle.
Migrating it to `AsyncState<string>` would force callers to handle
`loading` / `error` states that can never occur. This is explicitly NOT
technical debt — see ADR-0013 §1.

### Pattern: ChatSessionState + plain useStates for messages + REST

Canonical: `useAIChat.ts` (the only ChatSessionState user)

```typescript
const [sessionState, setSessionState] = useState<ChatSessionState>(idleChatSessionState);
const [messages, setMessages] = useState<AIAssistantMsg[]>([]);   // NOT in sessionState
const [sessions, setSessions] = useState<ChatSession[]>([]);      // separate
const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
const [restLoading, setRestLoading] = useState(false);            // REST lifecycle
const [restError, setRestError] = useState<string | null>(null);  // REST error
```

**Why messages are NOT in ChatSessionState:** reconnecting the WebSocket
must not invalidate the message history; clearing history must not tear
down the connection. See ADR-0013 §2 Invariant 1.

**Why REST loading/error are separate from sessionState:** REST is
request/response, not streaming. Forcing it into ChatSessionState would
collapse the conceptual boundary. See ADR-0013 §2 Invariant 6.

### Pattern: useReducer for workflow state machine

Canonical: `useEMR.ts` (the only useReducer user)

```typescript
const [state, dispatch] = useReducer(emrReducer, initialState);
// state.status: 'draft' | 'dirty' | 'saving' | 'saved' | 'conflict' | 'readonly' | 'autosaving'
```

**Why not AsyncState:** EMR has 7 states, not 4. `AsyncState` cannot
express `conflict` or `readonly`. See ADR-0013 §3.

### Pattern: plain useState for UI state

Every hook uses this for UI controls. Examples from `useUsers.ts`:
`searchTerm`, `filterRole`, `filterStatus`, `pagination`.

## Current adoption (audit-1, 2026-07-31)

| Pattern | Hooks | Notes |
|---------|------:|-------|
| `AsyncState<T>` | 14 | 20 files import `AsyncState`, but 6 are dead imports (see §"Migration candidates" below) |
| `ChatSessionState` | 1 | `useAIChat.ts` |
| `useReducer` | 1 | `useEMR.ts` |
| Plain `useState` | 42 | All AsyncState/ChatSessionState hooks also use useState for UI state |
| Stateless utility hooks | 12 | Hotkey registrars, media queries, navigation guards, theme |

**Total:** 54 hook files scanned (top-level `.ts`/`.tsx` in `src/hooks/`).

## Migration candidates (low-priority follow-up)

The audit identified 6 hooks that import `AsyncState` but never use it
(no `useState<AsyncState<>>`, no helpers, no type annotations). They
still use the legacy `useState<T[]>([])` + `useState<boolean>(false)` +
`useState<string | null>(null)` trio:

- `useAI.tsx`
- `useApi.ts`
- `useAsyncAction.ts`
- `useDoctorHistory.ts`
- `useDoctorQueue.ts`
- `useDoctorTreatmentTemplates.ts`

**Action:** either migrate them to `AsyncState<T>` properly, or remove
the dead import. `useAsyncAction` is a generic async wrapper — migrating
it would transitively propagate `AsyncState` to all consumers, which may
or may not be desired. Decide case-by-case in a separate sprint.

**This is NOT blocking for ADR-0014.** The matrix is the same whether
these 6 hooks are migrated or not.

## Anti-patterns to avoid

1. **AsyncState<UIState>** — never wrap UI state in AsyncState. UI state
   has no async lifecycle.
2. **ChatSessionState for CRUD** — never use ChatSessionState for a
   simple HTTP fetch. It is purpose-built for streaming transport.
3. **useReducer for simple async** — never use useReducer for a single
   fetch. `AsyncState<T>` is the right tool.
4. **Mixing transport + content in one state** — never bundle WebSocket
   connection state and chat messages in the same useState. See ADR-0013
   §2 Invariant 1.
5. **Stateless hook masquerading as stateful** — if a hook only computes
   derived values from props, do not add `useState` just to "look
   consistent". State is for things that change.

## Rule of thumb

> "If a new contributor reading only this ADR cannot decide which pattern
> to use, the ADR has failed. Add a concrete example, not a new rule."

This ADR is the single source of truth. ADR-0013 explains WHY each
pattern exists; ADR-0014 explains WHICH pattern to pick.
