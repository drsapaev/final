// Safe MCP fallback API used by useAI.tsx
// Provides stubbed methods to avoid runtime failures when MCP backend is absent.

// Result types — discriminated unions so consumers can narrow without `any`.
export interface McpSuccess<T> {
  status: 'success';
  data: T;
}

export interface McpFailure {
  status: 'error';
  error: string;
}

export type McpResult<T> = McpSuccess<T> | McpFailure;

// Payloads accepted by mcpAPI.* methods. Extra keys are allowed (callers
// forward `...options` from the calling hooks) — but the named fields here
// are the only ones the stub actually reads.
export interface ChatMessageLike {
  id?: number;
  role?: 'user' | 'assistant' | 'system';
  content?: string;
  timestamp?: Date;
  type?: string;
  metadata?: unknown;
}

export interface ChatPayload {
  messages?: ChatMessageLike[];
  provider?: string;
  model?: string;
  temperature?: number;
  maxTokens?: number;
  systemPrompt?: string;
  context?: string;
  [key: string]: unknown;
}

export interface ChatData {
  message: string;
  metadata: { provider: string; model: string; stub: boolean };
}

export interface SuggestionPayload {
  context?: string;
  type?: string;
  maxSuggestions?: number;
  provider?: string;
  model?: string;
  [key: string]: unknown;
}

export interface SuggestionItem {
  text: string;
  confidence: number;
  category: string;
}

export interface SuggestionData {
  suggestions: SuggestionItem[];
  metadata: { type: string; stub: boolean };
}

export interface TranslatePayload {
  text?: string;
  from?: string;
  to?: string;
  provider?: string;
  context?: string;
  [key: string]: unknown;
}

export interface TranslateData {
  translation: string;
  metadata: { stub: boolean };
}

export interface AnalyzeImageOptions {
  provider?: string;
  [key: string]: unknown;
}

export interface AnalyzeImageData {
  summary: string;
  findings: unknown[];
  metadata: { stub: boolean };
}

const delay = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));

const success = <T>(data: T): McpSuccess<T> => ({ status: 'success', data });
const failure = (error: unknown): McpFailure => ({
  status: 'error',
  error: String(error || 'Unavailable')
});

export const mcpAPI = {
  async chat(payload: ChatPayload = {}): Promise<McpResult<ChatData>> {
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

  async generateSuggestions(payload: SuggestionPayload = {}): Promise<McpResult<SuggestionData>> {
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

  async translate(payload: TranslatePayload = {}): Promise<McpResult<TranslateData>> {
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
    options: AnalyzeImageOptions = {}
  ): Promise<McpResult<AnalyzeImageData>> {
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
