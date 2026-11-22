// Local MCP fallback used by legacy hooks. It has no server or clinical
// capability, so it must never manufacture a successful medical AI response.
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

const failure = (error: unknown): { status: 'error'; error: string } => ({
  status: 'error',
  error: String(error || 'Unavailable')
});

export const mcpAPI = {
  async chat(payload: McpChatPayload = {}): Promise<McpResult<McpChatData>> {
    void payload;
    return failure('AI service unavailable');
  },

  async generateSuggestions(payload: McpSuggestionPayload = {}): Promise<McpResult<McpSuggestionData>> {
    void payload;
    return failure('AI service unavailable');
  },

  async translate(payload: McpTranslatePayload = {}): Promise<McpResult<McpTranslateData>> {
    void payload;
    return failure('AI service unavailable');
  },

  async analyzeImage(
    _file: File | Blob | unknown,
    imageType = 'general',
    options: McpAnalyzeImageOptions = {}
  ): Promise<McpResult<McpAnalyzeImageData>> {
    void _file;
    void imageType;
    void options;
    return failure('AI service unavailable');
  }
};

export default mcpAPI;
