// Safe MCP fallback API used by useAI.tsx.
// Provides stubbed methods to avoid runtime failures when MCP backend is absent.
//
// All transport types live in src/types/domain/mcp.ts (SSOT). This file
// re-exports them for backwards compatibility with any callers that still
// import from '@/utils/mcp'. New code should import from the domain layer
// directly.

import type {
  McpResult,
  McpChatPayload,
  McpChatData,
  McpSuggestionPayload,
  McpSuggestionData,
  McpTranslatePayload,
  McpTranslateData,
  McpAnalyzeImageOptions,
  McpAnalyzeImageData,
} from '../types/domain/mcp';

// Re-export for backwards compatibility (do NOT add new re-exports — callers
// should migrate to importing from '@/types/domain/mcp').
export type {
  McpSuccess,
  McpFailure,
  McpResult,
  McpChatMessage,
  McpChatPayload,
  McpChatData,
  McpSuggestionPayload,
  McpSuggestionItem,
  McpSuggestionData,
  McpTranslatePayload,
  McpTranslateData,
  McpAnalyzeImageOptions,
  McpAnalyzeImageData,
} from '../types/domain/mcp';

const delay = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

const success = <T,>(data: T): { status: 'success'; data: T } => ({ status: 'success', data });
const failure = (error: unknown): { status: 'error'; error: string } => ({
  status: 'error',
  error: String(error || 'Unavailable')
});

export const mcpAPI = {
  async chat(payload: McpChatPayload = {}): Promise<McpResult<McpChatData>> {
    try {
      await delay(50);
      const messages = payload.messages ?? [];
      const provider = payload.provider ?? 'mcp';
      const model = payload.model ?? 'gpt-4';
      const last = messages[messages.length - 1];
      return success({
        message: last?.content ? `Echo (${provider}/${model}): ${last.content}` : 'Здравствуйте! Чем могу помочь?',
        metadata: { provider, model, stub: true }
      });
    } catch (e) {
      return failure(e);
    }
  },

  async generateSuggestions(payload: McpSuggestionPayload = {}): Promise<McpResult<McpSuggestionData>> {
    try {
      await delay(50);
      const context = payload.context ?? '';
      const type = payload.type ?? 'medical';
      const maxSuggestions = payload.maxSuggestions ?? 5;
      const suggestions = Array.from({ length: Math.max(1, Math.min(maxSuggestions, 5)) }).map((_, i) => ({
        text: `Предложение ${i + 1} для контекста: ${context}`,
        confidence: 0.6 + i * 0.05,
        category: type
      }));
      return success({ suggestions, metadata: { type, stub: true } });
    } catch (e) {
      return failure(e);
    }
  },

  async translate(payload: McpTranslatePayload = {}): Promise<McpResult<McpTranslateData>> {
    try {
      await delay(50);
      const text = payload.text ?? '';
      const from = payload.from ?? 'ru';
      const to = payload.to ?? 'en';
      // Simple mock translation by marking text
      return success({ translation: `[${from}->${to}] ${text}`, metadata: { stub: true } });
    } catch (e) {
      return failure(e);
    }
  },

  async analyzeImage(
    _file: File | Blob | unknown,
    imageType = 'general',
    options: McpAnalyzeImageOptions = {}
  ): Promise<McpResult<McpAnalyzeImageData>> {
    try {
      void _file;
      void options;
      await delay(50);
      return success({
        summary: `Анализ изображения (${imageType}) выполнен (stub)`,
        findings: [],
        metadata: { stub: true }
      });
    } catch (e) {
      return failure(e);
    }
  }
};

export default mcpAPI;
