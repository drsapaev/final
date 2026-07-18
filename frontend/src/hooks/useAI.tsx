/**
 * Улучшенная система ИИ для медицинских интерфейсов
 * Основана на принципах доступности и медицинских стандартах UX
 */

import { useState, useCallback } from 'react';
import type { CSSProperties } from 'react';
import { useReducedMotion } from './useEnhancedMediaQuery';
import { mcpAPI } from '../utils/mcp';
import { validateAIChatMessage, detectPromptInjection } from '../utils/aiValidator';

import logger from '../utils/logger';

// TypeScript doesn't ship SpeechRecognition types in lib.dom. Declare a
// minimal structural type so consumers of useAIAssistant can compile
// without `@ts-nocheck`. This mirrors the W3C SpeechRecognition surface
// used by Chromium-based browsers (`webkitSpeechRecognition`).
interface SpeechRecognitionResult {
  transcript: string;
  confidence: number;
}

interface SpeechRecognitionResultList {
  readonly length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}

interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string;
  readonly message: string;
}

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

interface WindowWithSpeechRecognition extends Window {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
}

// Основные настройки ИИ
const AI_CONFIG = {
  defaultProvider: 'mcp',
  timeout: 30000,
  retryAttempts: 3,
  retryDelay: 1000
} as const;

type AIProvider = string;
type AIContext = string;

interface ChatMessage {
  id: number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  type: 'text' | 'error';
  metadata?: unknown;
}

interface AISuggestion {
  id: number;
  text: string;
  confidence: number;
  category: string;
  timestamp: Date;
}

interface SuggestionHistoryEntry {
  context: string;
  suggestions: AISuggestion[];
  timestamp: Date;
}

interface TranslationEntry {
  id: number;
  original: string;
  translated: string;
  from: string;
  to: string;
  timestamp: Date;
}

interface BatchTranslationResult {
  original: string;
  translated: string;
  error?: string;
}

interface UseAIAssistantOptions {
  provider?: AIProvider;
  model?: string;
  temperature?: number;
  maxTokens?: number;
  systemPrompt?: string;
  context?: AIContext;
}

interface UseAIAssistantReturn {
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
  isListening: boolean;
  sendMessage: (message: string, options?: Record<string, unknown>) => Promise<ChatMessage | undefined>;
  clearMessages: () => void;
  startListening: () => void;
}

interface UseAISuggestionsOptions {
  provider?: AIProvider;
  model?: string;
  type?: string;
  maxSuggestions?: number;
}

interface UseAISuggestionsReturn {
  suggestions: AISuggestion[];
  loading: boolean;
  error: string | null;
  history: SuggestionHistoryEntry[];
  generateSuggestions: (context: string, options?: Record<string, unknown>) => Promise<AISuggestion[] | undefined>;
  filterByConfidence: (minConfidence?: number) => AISuggestion[];
  groupByCategory: () => Record<string, AISuggestion[]>;
  clearSuggestions: () => void;
  clearHistory: () => void;
}

interface UseAITranslationOptions {
  provider?: AIProvider;
  sourceLanguage?: string;
  targetLanguage?: string;
}

interface UseAITranslationReturn {
  translations: TranslationEntry[];
  loading: boolean;
  error: string | null;
  translate: (text: string, fromLang?: string, toLang?: string) => Promise<string>;
  translateBatch: (texts: string[], fromLang?: string, toLang?: string) => Promise<BatchTranslationResult[]>;
  clearTranslations: () => void;
}

interface UseAIImageAnalysisOptions {
  provider?: AIProvider;
  useMCP?: boolean;
}

interface UseAIImageAnalysisReturn {
  analysis: unknown;
  loading: boolean;
  error: string | null;
  history: unknown[];
  analyzeImage: (imageFile: File | Blob, imageType?: string, options?: Record<string, unknown>) => Promise<unknown>;
  analyzeMedicalImage: (imageFile: File | Blob, options?: Record<string, unknown>) => Promise<unknown>;
  analyzeDocument: (imageFile: File | Blob, options?: Record<string, unknown>) => Promise<unknown>;
  clearResults: () => void;
  clearHistory: () => void;
  setAnalysis: (value: unknown) => void;
  setError: (value: string | null) => void;
}

// Хук для ИИ помощника
export const useAIAssistant = (options: UseAIAssistantOptions = {}): UseAIAssistantReturn => {
  const {
    provider = AI_CONFIG.defaultProvider,
    model = 'gpt-4',
    temperature = 0.7,
    maxTokens = 1000,
    systemPrompt = 'Вы - медицинский ИИ помощник. Отвечайте профессионально и точно.',
    context = 'medical'
  } = options;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isListening, setIsListening] = useState(false);
  useReducedMotion();

  // Отправка сообщения
  const sendMessage = useCallback(async (message: string, options: Record<string, unknown> = {}): Promise<ChatMessage | undefined> => {
    void options;
    if (!message || message.trim() === '') return;

    // Detect prompt injection attempts
    if (detectPromptInjection(message)) {
      logger.warn('[AI Security] Potential prompt injection detected in user message');
      setError('Обнаружена подозрительная активность. Сообщение заблокировано.');
      return;
    }

    setLoading(true);
    setError(null);

    const userMessage: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: message,
      timestamp: new Date(),
      type: 'text'
    };

    setMessages((prev) => [...prev, userMessage]);

    try {
      const response = await mcpAPI.chat({
        messages: [...messages, userMessage],
        provider,
        model,
        temperature,
        maxTokens,
        systemPrompt,
        context
      });

      if (response.status === 'success') {
        // Validate and sanitize AI response
        const validatedMessage = validateAIChatMessage({
          id: Date.now() + 1,
          role: 'assistant',
          content: response.data.message,
          timestamp: new Date(),
          type: 'text',
          metadata: response.data.metadata
        }) as ChatMessage | null;

        if (!validatedMessage) {
          throw new Error('AI response validation failed');
        }

        setMessages((prev) => [...prev, validatedMessage]);
        return validatedMessage;
      } else {
        throw new Error(response.error || 'AI request failed');
      }
    } catch (err) {
      logger.error('AI assistant error:', err);
      const message = err instanceof Error ? err.message : String(err);
      setError(message);

      const errorMessage: ChatMessage = {
        id: Date.now() + 2,
        role: 'assistant',
        content: 'Извините, произошла ошибка. Попробуйте еще раз.',
        timestamp: new Date(),
        type: 'error'
      };

      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  }, [messages, provider, model, temperature, maxTokens, systemPrompt, context]);

  // Очистка сообщений
  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  // Голосовой ввод
  const startListening = useCallback(() => {
    const win = window as WindowWithSpeechRecognition;
    if (!win.SpeechRecognition && !win.webkitSpeechRecognition) {
      setError('Голосовой ввод не поддерживается в вашем браузере');
      return;
    }

    setIsListening(true);

    const SpeechRecognitionCtor = (win.SpeechRecognition || win.webkitSpeechRecognition) as SpeechRecognitionConstructor;
    const recognition = new SpeechRecognitionCtor();

    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'ru-RU';

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const transcript = event.results[0]?.transcript ?? '';
      void sendMessage(transcript);
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      setError(`Ошибка распознавания речи: ${event.error}`);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.start();
  }, [sendMessage]);

  return {
    messages,
    loading,
    error,
    isListening,
    sendMessage,
    clearMessages,
    startListening
  };
};

// Хук для ИИ предложений
export const useAISuggestions = (options: UseAISuggestionsOptions = {}): UseAISuggestionsReturn => {
  const {
    provider = AI_CONFIG.defaultProvider,
    model = 'gpt-3.5-turbo',
    type = 'medical',
    maxSuggestions = 5
  } = options;

  const [suggestions, setSuggestions] = useState<AISuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<SuggestionHistoryEntry[]>([]);

  // Генерация предложений
  const generateSuggestions = useCallback(async (context: string, options: Record<string, unknown> = {}): Promise<AISuggestion[] | undefined> => {
    setLoading(true);
    setError(null);

    try {
      const response = await mcpAPI.generateSuggestions({
        context,
        type,
        provider,
        model,
        maxSuggestions,
        ...options
      });

      if (response.status === 'success') {
        const newSuggestions: AISuggestion[] = (response.data.suggestions as Array<{ text: string; confidence: number; category: string }>).map((suggestion, index) => ({
          id: Date.now() + index,
          text: suggestion.text,
          confidence: suggestion.confidence,
          category: suggestion.category,
          timestamp: new Date()
        }));

        setSuggestions(newSuggestions);
        setHistory((prev) => [...prev, { context, suggestions: newSuggestions, timestamp: new Date() }]);
        return newSuggestions;
      } else {
        throw new Error(response.error || 'Failed to generate suggestions');
      }
    } catch (err) {
      logger.error('AI suggestions error:', err);
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [type, provider, model, maxSuggestions]);

  // Фильтрация по уверенности
  const filterByConfidence = useCallback((minConfidence = 0.5): AISuggestion[] => {
    return suggestions.filter((suggestion) => suggestion.confidence >= minConfidence);
  }, [suggestions]);

  // Группировка по категориям
  const groupByCategory = useCallback((): Record<string, AISuggestion[]> => {
    return suggestions.reduce<Record<string, AISuggestion[]>>((groups, suggestion) => {
      const category = suggestion.category || 'other';
      if (!groups[category]) {
        groups[category] = [];
      }
      groups[category].push(suggestion);
      return groups;
    }, {});
  }, [suggestions]);

  // Очистка предложений
  const clearSuggestions = useCallback(() => {
    setSuggestions([]);
    setError(null);
  }, []);

  // Очистка истории
  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  return {
    suggestions,
    loading,
    error,
    history,
    generateSuggestions,
    filterByConfidence,
    groupByCategory,
    clearSuggestions,
    clearHistory
  };
};

// Хук для ИИ перевода
export const useAITranslation = (options: UseAITranslationOptions = {}): UseAITranslationReturn => {
  const {
    provider = AI_CONFIG.defaultProvider,
    sourceLanguage = 'ru',
    targetLanguage = 'en'
  } = options;

  const [translations, setTranslations] = useState<TranslationEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Перевод текста
  const translate = useCallback(async (text: string, fromLang = sourceLanguage, toLang = targetLanguage): Promise<string> => {
    if (!text || text.trim() === '') return '';

    setLoading(true);
    setError(null);

    try {
      const response = await mcpAPI.translate({
        text,
        from: fromLang,
        to: toLang,
        provider,
        context: 'medical'
      });

      if (response.status === 'success') {
        const translation: TranslationEntry = {
          id: Date.now(),
          original: text,
          translated: response.data.translation,
          from: fromLang,
          to: toLang,
          timestamp: new Date()
        };

        setTranslations((prev) => [...prev, translation]);
        return response.data.translation;
      } else {
        throw new Error(response.error || 'Translation failed');
      }
    } catch (err) {
      logger.error('AI translation error:', err);
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      return text; // Возвращаем оригинальный текст при ошибке
    } finally {
      setLoading(false);
    }
  }, [sourceLanguage, targetLanguage, provider]);

  // Пакетный перевод
  const translateBatch = useCallback(async (texts: string[], fromLang = sourceLanguage, toLang = targetLanguage): Promise<BatchTranslationResult[]> => {
    const results: BatchTranslationResult[] = [];

    for (const text of texts) {
      try {
        const translated = await translate(text, fromLang, toLang);
        results.push({ original: text, translated });
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        results.push({ original: text, translated: text, error: message });
      }
    }

    return results;
  }, [translate, sourceLanguage, targetLanguage]);

  // Очистка переводов
  const clearTranslations = useCallback(() => {
    setTranslations([]);
    setError(null);
  }, []);

  return {
    translations,
    loading,
    error,
    translate,
    translateBatch,
    clearTranslations
  };
};

// Хук для анализа изображений ИИ
export const useAIImageAnalysis = (options: UseAIImageAnalysisOptions = {}): UseAIImageAnalysisReturn => {
  const {
    provider = AI_CONFIG.defaultProvider,
    useMCP = true
  } = options;

  const [analysis, setAnalysis] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<unknown[]>([]);

  // Анализ изображения
  const analyzeImage = useCallback(async (imageFile: File | Blob, imageType = 'general', options: Record<string, unknown> = {}): Promise<unknown> => {
    setLoading(true);
    setError('');

    try {
      if (useMCP) {
        const mcpResult = await mcpAPI.analyzeImage(imageFile, imageType, {
          ...options,
          provider: provider
        });

        if (mcpResult.status === 'success') {
          return mcpResult.data;
        } else {
          throw new Error(mcpResult.error || 'MCP image analysis failed');
        }
      } else {
        throw new Error('Image analysis requires MCP mode');
      }
    } catch (err) {
      logger.error('AI image analysis error:', err);
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [provider, useMCP]);

  // Анализ медицинских изображений
  const analyzeMedicalImage = useCallback((imageFile: File | Blob, options: Record<string, unknown> = {}): Promise<unknown> => {
    return analyzeImage(imageFile, 'medical', options);
  }, [analyzeImage]);

  // Анализ документов
  const analyzeDocument = useCallback((imageFile: File | Blob, options: Record<string, unknown> = {}): Promise<unknown> => {
    return analyzeImage(imageFile, 'document', options);
  }, [analyzeImage]);

  // Очистка результатов
  const clearResults = useCallback(() => {
    setAnalysis(null);
    setError(null);
  }, []);

  // Очистка истории
  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  return {
    analysis,
    loading,
    error,
    history,
    analyzeImage,
    analyzeMedicalImage,
    analyzeDocument,
    clearResults,
    clearHistory,

    // Сеттеры
    setAnalysis,
    setError
  };
};

export default useAIAssistant;
