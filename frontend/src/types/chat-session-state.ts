/**
 * ChatSessionState — specialized state model for real-time chat with WebSocket streaming.
 *
 * Unlike AsyncState<T> (which models request/response: idle → loading → success → error),
 * ChatSessionState models a streaming lifecycle:
 *
 *   idle → connecting → connected → streaming → completed
 *                                   ↘ reconnecting ↗
 *                                   ↘ disconnected
 *
 * This separation keeps AsyncState simple for request/response patterns while
 * giving the chat hook a purpose-built state that accurately represents its
 * WebSocket-based lifecycle.
 *
 * See ADR-0013 for the full rationale.
 */

export type ConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'disconnected';

export type StreamStatus =
  | 'idle'
  | 'streaming'
  | 'completed'
  | 'error';

export interface ChatSessionState<TMessage = unknown> {
  /** WebSocket connection state */
  connectionStatus: ConnectionStatus;
  /** Current streaming operation state */
  streamStatus: StreamStatus;
  /** Chat messages (accumulated during session) */
  messages: TMessage[];
  /** Error message (from connection or streaming) */
  error: string | null;
}

// === Helper constructors ===

export function idleChatState<T>(): ChatSessionState<T> {
  return { connectionStatus: 'idle', streamStatus: 'idle', messages: [], error: null };
}

export function connectingChatState<T>(messages: T[] = []): ChatSessionState<T> {
  return { connectionStatus: 'connecting', streamStatus: 'idle', messages, error: null };
}

export function connectedChatState<T>(messages: T[] = []): ChatSessionState<T> {
  return { connectionStatus: 'connected', streamStatus: 'idle', messages, error: null };
}

export function streamingChatState<T>(messages: T[]): ChatSessionState<T> {
  return { connectionStatus: 'connected', streamStatus: 'streaming', messages, error: null };
}

export function completedChatState<T>(messages: T[]): ChatSessionState<T> {
  return { connectionStatus: 'connected', streamStatus: 'completed', messages, error: null };
}

export function reconnectingChatState<T>(messages: T[]): ChatSessionState<T> {
  return { connectionStatus: 'reconnecting', streamStatus: 'idle', messages, error: null };
}

export function disconnectedChatState<T>(messages: T[] = []): ChatSessionState<T> {
  return { connectionStatus: 'disconnected', streamStatus: 'idle', messages, error: null };
}

export function errorChatState<T>(error: string, messages: T[] = []): ChatSessionState<T> {
  return { connectionStatus: 'disconnected', streamStatus: 'error', messages, error };
}

// === Convenience accessors ===

export function isChatLoading<T>(state: ChatSessionState<T>): boolean {
  return state.connectionStatus === 'connecting' || state.connectionStatus === 'reconnecting';
}

export function isChatStreaming<T>(state: ChatSessionState<T>): boolean {
  return state.streamStatus === 'streaming';
}

export function isChatConnected<T>(state: ChatSessionState<T>): boolean {
  return state.connectionStatus === 'connected';
}

export function getChatError<T>(state: ChatSessionState<T>): string | null {
  return state.error;
}

export function getChatMessages<T>(state: ChatSessionState<T>): T[] {
  return state.messages;
}
