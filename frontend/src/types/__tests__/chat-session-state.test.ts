/**
 * State machine tests for ChatSessionState transition validators.
 *
 * Per ADR-0017 (Architecture Consolidation), we treat the transition tables
 * as finite state machines and verify four properties:
 *
 * 1. **Reachability** — every vertex is reachable from `idle`.
 * 2. **Forbidden edges rejected** — every transition NOT in the allowed-edge
 *    table is rejected by the validator AND a no-op for the applicator.
 * 3. **No dangling states** — every state has at least one outgoing edge.
 * 4. **Idempotency** — `from → from` is always allowed (and is a no-op for
 *    the applicator).
 *
 * Test style: table-driven (not property-based) because the state space is
 * small (5×5 + 3×3 = 34 transitions total) and explicit enumeration reads
 * better than generated cases for this kind of invariant.
 */

import { describe, expect, it } from 'vitest';
import {
  idleChatSessionState,
  applyConnectionTransition,
  applyStreamTransition,
  setChatError,
  incrementReconnectAttempt,
  isValidConnectionTransition,
  isValidStreamTransition,
  chatError,
  type ConnectionStatus,
  type StreamStatus,
  type ChatSessionState,
} from '../chat-session-state';

// ===========================================================================
// Test data: full transition matrices
// ===========================================================================

const ALL_CONNECTION_STATUSES: ConnectionStatus[] = [
  'idle',
  'connecting',
  'connected',
  'reconnecting',
  'disconnected',
];

const ALL_STREAM_STATUSES: StreamStatus[] = ['idle', 'streaming', 'completed'];

/**
 * Authoritative allowed-edge tables (must match chat-session-state.ts).
 * Duplicated here intentionally — the tests assert that the source matches
 * this expected table. If the table in chat-session-state.ts changes, this
 * test must be updated AND the change must be reflected in ADR-0013 §2.
 */
const EXPECTED_CONNECTION_EDGES: Record<ConnectionStatus, ConnectionStatus[]> = {
  idle: ['connecting', 'disconnected'],
  connecting: ['connected', 'disconnected', 'reconnecting'],
  connected: ['reconnecting', 'disconnected', 'connecting'],
  reconnecting: ['connected', 'disconnected', 'connecting'],
  disconnected: ['connecting'],
};

const EXPECTED_STREAM_EDGES: Record<StreamStatus, StreamStatus[]> = {
  idle: ['streaming'],
  streaming: ['completed', 'idle'],
  completed: ['idle', 'streaming'],
};

// ===========================================================================
// Property 1: Reachability — every vertex reachable from idle
// ===========================================================================

describe('ChatSessionState — Property 1: reachability from idle', () => {
  it('connection: every status is reachable from idle via allowed edges', () => {
    const visited = new Set<ConnectionStatus>(['idle']);
    const queue: ConnectionStatus[] = ['idle'];
    while (queue.length > 0) {
      const current = queue.shift() as ConnectionStatus;
      for (const next of ALL_CONNECTION_STATUSES) {
        if (
          isValidConnectionTransition(current, next) &&
          !visited.has(next)
        ) {
          visited.add(next);
          queue.push(next);
        }
      }
    }
    expect(visited).toEqual(new Set(ALL_CONNECTION_STATUSES));
  });

  it('stream: every status is reachable from idle via allowed edges', () => {
    const visited = new Set<StreamStatus>(['idle']);
    const queue: StreamStatus[] = ['idle'];
    while (queue.length > 0) {
      const current = queue.shift() as StreamStatus;
      for (const next of ALL_STREAM_STATUSES) {
        if (
          isValidStreamTransition(current, next) &&
          !visited.has(next)
        ) {
          visited.add(next);
          queue.push(next);
        }
      }
    }
    expect(visited).toEqual(new Set(ALL_STREAM_STATUSES));
  });
});

// ===========================================================================
// Property 2: Forbidden edges rejected + applicator is a no-op
// ===========================================================================

describe('ChatSessionState — Property 2: forbidden edges rejected', () => {
  const connectionCases: Array<{
    from: ConnectionStatus;
    to: ConnectionStatus;
    expected: boolean;
  }> = [];
  for (const from of ALL_CONNECTION_STATUSES) {
    for (const to of ALL_CONNECTION_STATUSES) {
      const expected =
        from === to || EXPECTED_CONNECTION_EDGES[from].includes(to);
      connectionCases.push({ from, to, expected });
    }
  }

  it.each(connectionCases)(
    'connection: isValidConnectionTransition($from → $to) === $expected',
    ({ from, to, expected }) => {
      expect(isValidConnectionTransition(from, to)).toBe(expected);
    }
  );

  it.each(connectionCases.filter((c) => !c.expected))(
    'connection applicator: forbidden $from → $to is a no-op (returns prev unchanged)',
    ({ from, to }) => {
      const prev: ChatSessionState = {
        ...idleChatSessionState(),
        connectionStatus: from,
        reconnectAttempt: 3,
        error: chatError('network_error', 'pre-existing error', true),
      };
      const next = applyConnectionTransition(prev, to);
      expect(next).toBe(prev);
      expect(next.connectionStatus).toBe(from);
      expect(next.reconnectAttempt).toBe(3);
      expect(next.error).not.toBeNull();
    }
  );

  const streamCases: Array<{
    from: StreamStatus;
    to: StreamStatus;
    expected: boolean;
  }> = [];
  for (const from of ALL_STREAM_STATUSES) {
    for (const to of ALL_STREAM_STATUSES) {
      const expected = from === to || EXPECTED_STREAM_EDGES[from].includes(to);
      streamCases.push({ from, to, expected });
    }
  }

  it.each(streamCases)(
    'stream: isValidStreamTransition($from → $to) === $expected',
    ({ from, to, expected }) => {
      expect(isValidStreamTransition(from, to)).toBe(expected);
    }
  );

  it.each(streamCases.filter((c) => !c.expected))(
    'stream applicator: forbidden $from → $to is a no-op (returns prev unchanged)',
    ({ from, to }) => {
      const prev: ChatSessionState = {
        ...idleChatSessionState(),
        streamStatus: from,
        error: chatError('model_error', 'pre-existing error', true),
      };
      const next = applyStreamTransition(prev, to);
      expect(next).toBe(prev);
      expect(next.streamStatus).toBe(from);
      expect(next.error).not.toBeNull();
    }
  );
});

// ===========================================================================
// Property 3: No dangling states
// ===========================================================================

describe('ChatSessionState — Property 3: no dangling states', () => {
  it('connection: every status has at least one outgoing edge', () => {
    for (const from of ALL_CONNECTION_STATUSES) {
      const outgoing = EXPECTED_CONNECTION_EDGES[from].filter((to) => to !== from);
      expect(
        outgoing.length,
        `connection status ${from} has no outgoing edges`
      ).toBeGreaterThan(0);
    }
  });

  it('stream: every status has at least one outgoing edge', () => {
    for (const from of ALL_STREAM_STATUSES) {
      const outgoing = EXPECTED_STREAM_EDGES[from].filter((to) => to !== from);
      expect(
        outgoing.length,
        `stream status ${from} has no outgoing edges`
      ).toBeGreaterThan(0);
    }
  });
});

// ===========================================================================
// Property 4: Idempotency
// ===========================================================================

describe('ChatSessionState — Property 4: idempotency', () => {
  it.each(ALL_CONNECTION_STATUSES)(
    'connection: %s → %s is allowed (self-loop)',
    (status) => {
      expect(isValidConnectionTransition(status, status)).toBe(true);
    }
  );

  it.each(ALL_CONNECTION_STATUSES)(
    'connection applicator: %s → %s is a no-op',
    (status) => {
      const prev: ChatSessionState = {
        ...idleChatSessionState(),
        connectionStatus: status,
        reconnectAttempt: 2,
      };
      const next = applyConnectionTransition(prev, status);
      expect(next.connectionStatus).toBe(status);
      expect(next.reconnectAttempt).toBe(2);
    }
  );

  it.each(ALL_STREAM_STATUSES)(
    'stream: %s → %s is allowed (self-loop)',
    (status) => {
      expect(isValidStreamTransition(status, status)).toBe(true);
    }
  );

  it.each(ALL_STREAM_STATUSES)(
    'stream applicator: %s → %s is a no-op',
    (status) => {
      const prev: ChatSessionState = {
        ...idleChatSessionState(),
        streamStatus: status,
      };
      const next = applyStreamTransition(prev, status);
      expect(next.streamStatus).toBe(status);
    }
  );
});

// ===========================================================================
// Allowed-edge table matches the source (regression test)
// ===========================================================================

describe('ChatSessionState — transition table matches ADR-0013 §2', () => {
  it.each(ALL_CONNECTION_STATUSES.flatMap((from) =>
    ALL_CONNECTION_STATUSES.map((to) => ({ from, to }))
  ))(
    'connection edge $from → $to matches ADR-0013 expected table',
    ({ from, to }) => {
      const expected = from === to || EXPECTED_CONNECTION_EDGES[from].includes(to);
      expect(isValidConnectionTransition(from, to)).toBe(expected);
    }
  );

  it.each(ALL_STREAM_STATUSES.flatMap((from) =>
    ALL_STREAM_STATUSES.map((to) => ({ from, to }))
  ))(
    'stream edge $from → $to matches ADR-0013 expected table',
    ({ from, to }) => {
      const expected = from === to || EXPECTED_STREAM_EDGES[from].includes(to);
      expect(isValidStreamTransition(from, to)).toBe(expected);
    }
  );
});

// ===========================================================================
// Applicator behavior — clearError + resetReconnectAttempt flags
// ===========================================================================

describe('ChatSessionState — applicator side-effects', () => {
  it('applyConnectionTransition clears error when clearError:true', () => {
    const prev: ChatSessionState = {
      ...idleChatSessionState(),
      connectionStatus: 'connecting',
      error: chatError('network_error', 'old error', true),
    };
    const next = applyConnectionTransition(prev, 'connected', { clearError: true });
    expect(next.connectionStatus).toBe('connected');
    expect(next.error).toBeNull();
  });

  it('applyConnectionTransition preserves error when clearOption not set', () => {
    const prev: ChatSessionState = {
      ...idleChatSessionState(),
      connectionStatus: 'connecting',
      error: chatError('network_error', 'old error', true),
    };
    const next = applyConnectionTransition(prev, 'connected');
    expect(next.connectionStatus).toBe('connected');
    expect(next.error).not.toBeNull();
    expect(next.error?.message).toBe('old error');
  });

  it('applyConnectionTransition resets reconnectAttempt when resetReconnectAttempt:true', () => {
    const prev: ChatSessionState = {
      ...idleChatSessionState(),
      connectionStatus: 'reconnecting',
      reconnectAttempt: 4,
    };
    const next = applyConnectionTransition(prev, 'connected', {
      resetReconnectAttempt: true,
    });
    expect(next.connectionStatus).toBe('connected');
    expect(next.reconnectAttempt).toBe(0);
  });

  it('applyConnectionTransition preserves reconnectAttempt when reset not requested', () => {
    const prev: ChatSessionState = {
      ...idleChatSessionState(),
      connectionStatus: 'reconnecting',
      reconnectAttempt: 4,
    };
    const next = applyConnectionTransition(prev, 'connected');
    expect(next.reconnectAttempt).toBe(4);
  });

  it('applyStreamTransition clears error when clearError:true', () => {
    const prev: ChatSessionState = {
      ...idleChatSessionState(),
      streamStatus: 'idle',
      error: chatError('model_error', 'old error', true),
    };
    const next = applyStreamTransition(prev, 'streaming', { clearError: true });
    expect(next.streamStatus).toBe('streaming');
    expect(next.error).toBeNull();
  });

  it('incrementReconnectAttempt increments by 1', () => {
    const prev: ChatSessionState = {
      ...idleChatSessionState(),
      reconnectAttempt: 2,
    };
    const next = incrementReconnectAttempt(prev);
    expect(next.reconnectAttempt).toBe(3);
    expect(next.connectionStatus).toBe(prev.connectionStatus);
    expect(next.streamStatus).toBe(prev.streamStatus);
    expect(next.error).toBe(prev.error);
  });

  it('setChatError replaces the error field', () => {
    const prev: ChatSessionState = {
      ...idleChatSessionState(),
      error: chatError('network_error', 'old', true),
    };
    const next = setChatError(prev, chatError('auth_error', 'new', false));
    expect(next.error?.code).toBe('auth_error');
    expect(next.error?.retryable).toBe(false);
  });

  it('setChatError(null) clears the error', () => {
    const prev: ChatSessionState = {
      ...idleChatSessionState(),
      error: chatError('network_error', 'old', true),
    };
    const next = setChatError(prev, null);
    expect(next.error).toBeNull();
  });
});

// ===========================================================================
// Specific scenario: full reconnect lifecycle
// ===========================================================================

describe('ChatSessionState — reconnect lifecycle scenario', () => {
  it('models a full reconnect sequence: connected → reconnecting → connected', () => {
    let state = idleChatSessionState();
    state = applyConnectionTransition(state, 'connecting', { resetReconnectAttempt: true });
    state = applyConnectionTransition(state, 'connected', {
      clearError: true,
      resetReconnectAttempt: true,
    });
    expect(state.connectionStatus).toBe('connected');
    expect(state.reconnectAttempt).toBe(0);

    state = incrementReconnectAttempt(state);
    state = applyConnectionTransition(state, 'reconnecting');
    expect(state.connectionStatus).toBe('reconnecting');
    expect(state.reconnectAttempt).toBe(1);

    state = applyConnectionTransition(state, 'connected', {
      clearError: true,
      resetReconnectAttempt: true,
    });
    expect(state.connectionStatus).toBe('connected');
    expect(state.reconnectAttempt).toBe(0);

    state = applyStreamTransition(state, 'streaming', { clearError: true });
    expect(state.streamStatus).toBe('streaming');

    state = applyStreamTransition(state, 'completed');
    expect(state.streamStatus).toBe('completed');

    state = applyStreamTransition(state, 'idle');
    expect(state.streamStatus).toBe('idle');
  });

  it('models giving up after MAX_RECONNECT_ATTEMPTS: disconnected is terminal', () => {
    let state = idleChatSessionState();
    state = applyConnectionTransition(state, 'connecting');
    state = applyConnectionTransition(state, 'reconnecting');
    state = incrementReconnectAttempt(state);
    state = incrementReconnectAttempt(state);
    state = incrementReconnectAttempt(state);
    state = incrementReconnectAttempt(state);
    state = incrementReconnectAttempt(state);
    expect(state.reconnectAttempt).toBe(5);

    state = applyConnectionTransition(state, 'disconnected');
    expect(state.connectionStatus).toBe('disconnected');

    // Disconnected is terminal — cannot go to connected directly
    const invalid = applyConnectionTransition(state, 'connected');
    expect(invalid).toBe(state);
    expect(invalid.connectionStatus).toBe('disconnected');

    // Can only re-init via connecting
    state = applyConnectionTransition(state, 'connecting', {
      resetReconnectAttempt: true,
    });
    expect(state.connectionStatus).toBe('connecting');
    expect(state.reconnectAttempt).toBe(0);
  });
});
