/**
 * Domain types for the MCP (Model Context Protocol) integration layer.
 *
 * MCP is the *transport* between the frontend and the AI backend stub.
 * These types describe the canonical request/response shapes that
 * utils/mcp.ts exposes as `mcpAPI`. The AI hooks in useAI.tsx consume
 * these, and the upcoming mapper (Wave 4) will translate them into
 * pure domain AI shapes from types/domain/ai.ts.
 *
 * Architecture boundary:
 *
 *     AI hook  ──▶  domain/ai.ts (pure value objects)
 *                    ▲
 *                    │  (mapper, Wave 4)
 *                    │
 *     mcpAPI   ──▶  domain/mcp.ts (transport shapes)
 *
 * Components MUST NOT import from domain/mcp.ts once the mapper exists.
 * For now (Wave 1), useAI.tsx imports from here directly — this will be
 * cleaned up in Wave 4.
 */

import type { AIChatMessage } from './ai';

// === Result envelope ========================================================

export interface McpSuccess<T> {
  status: 'success';
  data: T;
  [key: string]: unknown;
}

export interface McpFailure {
  status: 'error';
  error: string;
  [key: string]: unknown;
}

export type McpResult<T> = McpSuccess<T> | McpFailure;

// === Chat transport =========================================================

export interface McpChatMessage {
  id?: number;
  role?: 'user' | 'assistant' | 'system';
  content?: string;
  timestamp?: Date;
  type?: string;
  metadata?: unknown;
  [key: string]: unknown;
}

export interface McpChatPayload {
  messages?: McpChatMessage[];
  provider?: string;
  model?: string;
  temperature?: number;
  maxTokens?: number;
  systemPrompt?: string;
  context?: string;
  [key: string]: unknown;
}

export interface McpChatData {
  message: string;
  metadata: { provider: string; model: string; stub: boolean };
  [key: string]: unknown;
}

// === Suggestions transport =================================================

export interface McpSuggestionPayload {
  context?: string;
  type?: string;
  maxSuggestions?: number;
  provider?: string;
  model?: string;
  [key: string]: unknown;
}

export interface McpSuggestionItem {
  text: string;
  confidence: number;
  category: string;
  [key: string]: unknown;
}

export interface McpSuggestionData {
  suggestions: McpSuggestionItem[];
  metadata: { type: string; stub: boolean };
  [key: string]: unknown;
}

// === Translation transport =================================================

export interface McpTranslatePayload {
  text?: string;
  from?: string;
  to?: string;
  provider?: string;
  context?: string;
  [key: string]: unknown;
}

export interface McpTranslateData {
  translation: string;
  metadata: { stub: boolean };
  [key: string]: unknown;
}

// === Image analysis transport ==============================================

export interface McpAnalyzeImageOptions {
  provider?: string;
  [key: string]: unknown;
}

export interface McpAnalyzeImageData {
  summary: string;
  findings: unknown[];
  metadata: { stub: boolean };
  [key: string]: unknown;
}

// === Mapper helpers (Wave 4 will move these to src/types/api-mapper/) ======

export function mcpChatMessageToDomain(m: McpChatMessage): AIChatMessage {
  return {
    id: m.id ?? Date.now(),
    role: m.role ?? 'user',
    content: m.content ?? '',
    timestamp: m.timestamp ?? new Date(),
    type: (m.type === 'error' ? 'error' : 'text') as AIChatMessage['type'],
    metadata: m.metadata,
  };
}
