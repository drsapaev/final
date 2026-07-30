/**
 * Domain types for the in-app clinic chat (1:1 messaging between staff).
 *
 * Used by ChatContext.tsx, api/messages.ts, pushNotifications, and the
 * chat UI components.
 *
 * These describe the canonical shapes the chat subsystem works with.
 * The raw backend JSON is mapped into these via src/api/messages.ts
 * (still implicit-any today; will be typed in a later batch — see ADR-0013).
 *
 * NOT included here:
 *   - WsIncomingMessage protocol envelope (transport concern; stays local
 *     to ChatContext.tsx until the WS layer gets its own domain file)
 *   - ChatContextValue / ChatProviderProps (React-specific; feature-local)
 *   - AuthState (belongs to domain/auth.ts; the local copy in ChatContext
 *     is a known duplicate — flagged for removal in Wave 3)
 */

export type ChatMessageType = 'text' | 'system' | 'file';

export interface ChatReaction {
  reaction: string;
  id?: number;
  user_id: number;
  user_name?: string | null;
}

export interface ChatMessage {
  id: number;
  sender_id: number;
  recipient_id: number;
  sender_name?: string;
  content?: string;
  is_read?: boolean;
  reactions?: ChatReaction[];
  created_at?: string;
  type?: ChatMessageType;
  attachment_url?: string;
  attachment_name?: string;
}

export interface ChatConversation {
  user_id: number;
  user_name?: string;
  user_role?: string;
  role?: string;
  last_message_time?: string;
  last_message?: string;
  last_message_at?: string;
  unread_count?: number;
}

export interface ChatAvailableUser {
  id: number;
  name?: string;
  full_name?: string;
  role?: string;
  is_online?: boolean;
  last_seen?: string;
}

// Response envelopes — these are DTOs from the REST API. They live in the
// domain layer for now because ChatContext consumes them directly; once
// the API → mapper → domain boundary is enforced (Wave 4), these move
// to src/api/messages.ts as internal transport types.
export interface ChatConversationsResponse {
  conversations?: ChatConversation[];
  total_unread?: number;
}

export interface ChatConversationResponse {
  messages?: ChatMessage[];
  has_more?: boolean;
}

export interface ChatUnreadCountResponse {
  count?: number;
}

export interface ChatAvailableUsersResponse {
  users?: ChatAvailableUser[];
}

export type ChatOnlineStatus = boolean | 'online' | 'offline' | 'away';

export interface ChatOnlineStatusMap {
  [userId: string]: ChatOnlineStatus | unknown;
}

export interface ChatTypingMap {
  [userId: string]: boolean | unknown;
}
