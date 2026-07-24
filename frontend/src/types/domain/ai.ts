/**
 * Domain types for AI assistants (chat, suggestions, translation, image analysis).
 *
 * Used by useAI.tsx (useAIAssistant, useAISuggestions, useAITranslation,
 * useAIImageAnalysis) and by the MCP mapper that translates transport
 * payloads (types/domain/mcp.ts) into these domain shapes.
 *
 * NOTE on SpeechRecognition*: those are W3C Web Speech API polyfills and
 * live in src/types/declarations.d.ts, NOT here. They are DOM surface
 * types, not domain concepts.
 *
 * NOTE on hook option/return types (UseAIAssistantOptions etc.): those
 * are React-hook-specific and stay local to useAI.tsx. Only the *value
 * objects* that flow across module boundaries live here.
 */

export type AIProvider = 'mcp' | 'openai' | 'anthropic' | string;
export type AIContext = 'medical' | 'translation' | 'image_analysis' | string;
export type AIChatRole = 'user' | 'assistant' | 'system';
export type AIChatMessageType = 'text' | 'error';

export interface AIChatMessage {
  id: number;
  role: AIChatRole;
  content: string;
  timestamp: Date;
  type: AIChatMessageType;
  metadata?: unknown;
  [key: string]: unknown;
}

export interface AISuggestion {
  id: number;
  text: string;
  confidence: number;
  category: string;
  timestamp: Date;
  [key: string]: unknown;
}

export interface AISuggestionHistoryEntry {
  context: string;
  suggestions: AISuggestion[];
  timestamp: Date;
  [key: string]: unknown;
}

export interface AITranslationEntry {
  id: number;
  original: string;
  translated: string;
  from: string;
  to: string;
  timestamp: Date;
  [key: string]: unknown;
}

export interface AIBatchTranslationResult {
  original: string;
  translated: string;
  error?: string;
  [key: string]: unknown;
}

export interface AIImageAnalysisFinding {
  label?: string;
  confidence?: number;
  description?: string;
  [key: string]: unknown;
}

export interface AIImageAnalysisResult {
  summary: string;
  findings: AIImageAnalysisFinding[];
  imageType?: string;
  metadata?: { provider?: string; stub?: boolean; [k: string]: unknown };
  [key: string]: unknown;
}
