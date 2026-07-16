// src/types/features/chat.ts
// Phase 0.5 — Chat domain UI types (placeholder).
// Will be filled in during Phase 5.7 (chat components migration) and
// Phase 3 (ChatContext migration).
//
// SSOT:
//   - frontend/src/contexts/ChatContext.jsx
//   - frontend/src/components/chat/
//   - backend OpenAPI schemas: ChatMessageResponse, ChatSessionResponse, MessageOut

// TODO Phase 3/5.7: ChatMessage, ChatState, WebSocketConfig
export type ChatState = Record<string, unknown>;
export type WebSocketConfig = {
  url: string;
  protocols?: string | string[];
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
};
