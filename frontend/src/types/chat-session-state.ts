/**
 * ChatSessionState — transport-layer state model for real-time chat with
 * WebSocket streaming.
 *
 * Design constraints (see ADR-0013 §2 for full rationale):
 *
 * 1. **Transport only.** This state describes the WebSocket connection and the
 *    active streaming operation. It MUST NOT carry chat messages — those live
 *    in a separate `ChatData<TMessage>` (or just `useState<TMessage[]>` in the
 *    hook) so that reconnecting or clearing history does not invalidate the
 *    other dimension.
 *
 * 2. **Two independent dimensions.** `connectionStatus` and `streamStatus`
 *    evolve independently. We deliberately avoid a single enum with twenty
 *    variants like `authenticated_streaming_receiving_typing_retrying` —
 *    that becomes unreadable and prevents independent state transitions.
 *
 * 3. **Explicit transitions.** `isValidConnectionTransition` and
 *    `isValidStreamTransition` encode the allowed state machine edges.
 *    `applyConnectionTransition` / `applyStreamTransition` enforce them at
 *    runtime (dev-only `console.warn` on forbidden edges).
 *
 * 4. **Structured error.** Errors are NOT encoded as `streamStatus === 'error'`.
 *    Instead, `error: ChatError | null` carries the full picture: code,
 *    human-readable message, and whether the user can retry. The UI can then
 *    distinguish network failure / model failure / rate limit / user-cancel.
 *
 * 5. **No reducer coupling.** This type is a value object. The hook may use
 *    `useState<ChatSessionState>` or `useReducer`; either way, WebSocket
 *    callbacks and REST API calls remain separate functions. The state type
 *    does not prescribe how transitions are dispatched.
 *
 * See ADR-0013 for the allowed transition tables and invariants.
 */

// ===========================================================================
// Error — structured, separate from status (constraint #5)
// ===========================================================================

export type ChatErrorCode =
  | 'network_error'        // WebSocket close, transport failure
  | 'auth_error'           // JWT invalid / expired / rejected
  | 'model_error'          // backend model failed to produce a response
  | 'rate_limit'           // 429 / quota exceeded
  | 'cancelled'            // user-initiated cancel
  | 'contract_mismatch'    // protocol version mismatch with backend
  | 'unknown';

export interface ChatError {
  code: ChatErrorCode;
  message: string;
  /** When false, the UI should not show a "Retry" button. */
  retryable: boolean;
}

export function chatError(
  code: ChatErrorCode,
  message: string,
  retryable: boolean = true
): ChatError {
  return { code, message, retryable };
}

// ===========================================================================
// Two independent status dimensions (constraints #1, #4)
// ===========================================================================

/**
 * WebSocket transport dimension.
 *
 * Allowed transitions (see `isValidConnectionTransition`):
 *
 *   idle ──▶ connecting ──▶ connected ──▶ reconnecting ──▶ connected
 *                │              │              │
 *                ▼              ▼              ▼
 *           disconnected   disconnected    disconnected
 *
 * Forbidden:
 *   - idle → connected (must go through connecting)
 *   - idle → reconnecting (nothing to reconnect to)
 *   - disconnected → connected (must explicitly re-connect via connecting)
 *   - disconnected → reconnecting (disconnected is terminal)
 */
export type ConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'disconnected';

/**
 * Streaming operation dimension. Independent of connection status.
 *
 * Allowed transitions:
 *
 *   idle ──▶ streaming ──▶ completed ──▶ idle      (normal cycle)
 *                       └──▶ idle                  (cancelled / session_closed)
 *
 * Forbidden:
 *   - idle → completed (must stream first)
 *
 * Note: there is NO `error` value here. Errors are carried in `ChatError`
 * (constraint #5). When an error occurs, streamStatus typically returns to
 * `idle` and `error` is populated.
 */
export type StreamStatus =
  | 'idle'
  | 'streaming'
  | 'completed';

// ===========================================================================
// ChatSessionState — transport + stream + error (NO messages — constraints #1, #2)
// ===========================================================================

export interface ChatSessionState {
  connectionStatus: ConnectionStatus;
  streamStatus: StreamStatus;
  error: ChatError | null;
  /** Number of reconnect attempts since the last successful connection. */
  reconnectAttempt: number;
}

// ===========================================================================
// ChatData — messages and active session, SEPARATE from session state
// (constraints #1, #2)
// ===========================================================================

export interface ChatData<TMessage = unknown> {
  messages: TMessage[];
  activeSessionId: string | number | null;
}

// ===========================================================================
// Initial state + helper constructors
// ===========================================================================

export function idleChatSessionState(): ChatSessionState {
  return {
    connectionStatus: 'idle',
    streamStatus: 'idle',
    error: null,
    reconnectAttempt: 0,
  };
}

// ===========================================================================
// Transition validation (constraint #3)
// ===========================================================================

const ALLOWED_CONNECTION_TRANSITIONS: Record<ConnectionStatus, readonly ConnectionStatus[]> = {
  idle: ['connecting', 'disconnected'],
  connecting: ['connected', 'disconnected', 'reconnecting'],
  connected: ['reconnecting', 'disconnected', 'connecting'],
  reconnecting: ['connected', 'disconnected', 'connecting'],
  disconnected: ['connecting'],
};

const ALLOWED_STREAM_TRANSITIONS: Record<StreamStatus, readonly StreamStatus[]> = {
  idle: ['streaming'],
  streaming: ['completed', 'idle'],
  completed: ['idle', 'streaming'],
};

export function isValidConnectionTransition(
  from: ConnectionStatus,
  to: ConnectionStatus
): boolean {
  if (from === to) return true; // idempotent
  return ALLOWED_CONNECTION_TRANSITIONS[from].includes(to);
}

export function isValidStreamTransition(
  from: StreamStatus,
  to: StreamStatus
): boolean {
  if (from === to) return true; // idempotent
  return ALLOWED_STREAM_TRANSITIONS[from].includes(to);
}

// ===========================================================================
// Transition applicators — enforce invariants at runtime (dev-only warn)
// ===========================================================================

/**
 * Apply a connection-status transition. Returns the (possibly updated) state.
 *
 * On a forbidden transition, logs a warning and returns the state unchanged
 * (or with `error` populated if requested). This is intentional: a forbidden
 * transition indicates a logic bug in the caller; we surface it loudly in dev
 * but never crash production.
 */
export function applyConnectionTransition(
  state: ChatSessionState,
  next: ConnectionStatus,
  options: { resetReconnectAttempt?: boolean; clearError?: boolean } = {}
): ChatSessionState {
  if (!isValidConnectionTransition(state.connectionStatus, next)) {
    if (process.env.NODE_ENV !== 'production') {
      // eslint-disable-next-line no-console
      console.warn(
        `[ChatSessionState] forbidden connection transition: ${state.connectionStatus} → ${next}`
      );
    }
    return state;
  }
  return {
    ...state,
    connectionStatus: next,
    reconnectAttempt: options.resetReconnectAttempt ? 0 : state.reconnectAttempt,
    error: options.clearError ? null : state.error,
  };
}

/**
 * Apply a stream-status transition. Returns the (possibly updated) state.
 *
 * On a forbidden transition, logs a warning and returns the state unchanged.
 */
export function applyStreamTransition(
  state: ChatSessionState,
  next: StreamStatus,
  options: { clearError?: boolean } = {}
): ChatSessionState {
  if (!isValidStreamTransition(state.streamStatus, next)) {
    if (process.env.NODE_ENV !== 'production') {
      // eslint-disable-next-line no-console
      console.warn(
        `[ChatSessionState] forbidden stream transition: ${state.streamStatus} → ${next}`
      );
    }
    return state;
  }
  return {
    ...state,
    streamStatus: next,
    error: options.clearError ? null : state.error,
  };
}

/**
 * Set the structured error on the state. Does NOT change connection/stream
 * status — the caller decides whether to also transition (e.g. to `idle`).
 */
export function setChatError(
  state: ChatSessionState,
  error: ChatError | null
): ChatSessionState {
  return { ...state, error };
}

/**
 * Increment the reconnect attempt counter. Used by the WebSocket onclose
 * handler when scheduling the next reconnect.
 */
export function incrementReconnectAttempt(
  state: ChatSessionState
): ChatSessionState {
  return { ...state, reconnectAttempt: state.reconnectAttempt + 1 };
}

// ===========================================================================
// Convenience accessors — derive the legacy boolean fields from the new state
// ===========================================================================

export function isChatConnecting(state: ChatSessionState): boolean {
  return (
    state.connectionStatus === 'connecting' ||
    state.connectionStatus === 'reconnecting'
  );
}

export function isChatConnected(state: ChatSessionState): boolean {
  return state.connectionStatus === 'connected';
}

export function isChatStreaming(state: ChatSessionState): boolean {
  return state.streamStatus === 'streaming';
}

export function getChatError(state: ChatSessionState): ChatError | null {
  return state.error;
}

/**
 * Returns a human-readable error message suitable for the UI, or null if
 * there is no error. Kept for backward-compat with the legacy `error: string`
 * API of useAIChat.
 */
export function getChatErrorMessage(state: ChatSessionState): string | null {
  return state.error?.message ?? null;
}
