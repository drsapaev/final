/**
 * Улучшенная система ИИ для медицинских интерфейсов
 * Основана на принципах доступности и медицинских стандартах UX
 */

import PropTypes from 'prop-types';
import { useState, useCallback } from 'react';
import { useReducedMotion } from './useEnhancedMediaQuery';
import { mcpAPI } from '../utils/mcp';
import { validateAIChatMessage, detectPromptInjection } from '../utils/aiValidator';

import logger from '../utils/logger';
import { Input } from '../../ui/macos';
// Основные настройки ИИ
const AI_CONFIG = {
  defaultProvider: 'mcp',
  timeout: 30000,
  retryAttempts: 3,
  retryDelay: 1000
};

// Хук для ИИ помощника
export const useAIAssistant = (options = {}) => {
  const {
    provider = AI_CONFIG.defaultProvider,
    model = 'gpt-4',
    temperature = 0.7,
    maxTokens = 1000,
    systemPrompt = 'Вы - медицинский ИИ помощник. Отвечайте профессионально и точно.',
    context = 'medical'
  } = options;

  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isListening, setIsListening] = useState(false);void
  useReducedMotion();

  // Отправка сообщения
  const sendMessage = useCallback(async (message, options = {}) => {
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

    const userMessage = {
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
        });

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
      setError(err.message);

      const errorMessage = {
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
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      setError('Голосовой ввод не поддерживается в вашем браузере');
      return;
    }

    setIsListening(true);

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();

    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'ru-RU';

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      sendMessage(transcript);
    };

    recognition.onerror = (event) => {
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
export const useAISuggestions = (options = {}) => {
  const {
    provider = AI_CONFIG.defaultProvider,
    model = 'gpt-3.5-turbo',
    type = 'medical',
    maxSuggestions = 5
  } = options;

  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  // Генерация предложений
  const generateSuggestions = useCallback(async (context, options = {}) => {
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
        const newSuggestions = response.data.suggestions.map((suggestion, index) => ({
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
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [type, provider, model, maxSuggestions]);

  // Фильтрация по уверенности
  const filterByConfidence = useCallback((minConfidence = 0.5) => {
    return suggestions.filter((suggestion) => suggestion.confidence >= minConfidence);
  }, [suggestions]);

  // Группировка по категориям
  const groupByCategory = useCallback(() => {
    return suggestions.reduce((groups, suggestion) => {
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
export const useAITranslation = (options = {}) => {
  const {
    provider = AI_CONFIG.defaultProvider,
    sourceLanguage = 'ru',
    targetLanguage = 'en'
  } = options;

  const [translations, setTranslations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Перевод текста
  const translate = useCallback(async (text, fromLang = sourceLanguage, toLang = targetLanguage) => {
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
        const translation = {
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
      setError(err.message);
      return text; // Возвращаем оригинальный текст при ошибке
    } finally {
      setLoading(false);
    }
  }, [sourceLanguage, targetLanguage, provider]);

  // Пакетный перевод
  const translateBatch = useCallback(async (texts, fromLang = sourceLanguage, toLang = targetLanguage) => {
    const results = [];

    for (const text of texts) {
      try {
        const translated = await translate(text, fromLang, toLang);
        results.push({ original: text, translated });
      } catch (err) {
        results.push({ original: text, translated: text, error: err.message });
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
export const useAIImageAnalysis = (options = {}) => {
  const {
    provider = AI_CONFIG.defaultProvider,

    useMCP = true
  } = options;

  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  // Анализ изображения
  const analyzeImage = useCallback(async (imageFile, imageType = 'general', options = {}) => {
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
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [provider, useMCP]);

  // Анализ медицинских изображений
  const analyzeMedicalImage = useCallback(async (imageFile, options = {}) => {
    return analyzeImage(imageFile, 'medical', options);
  }, [analyzeImage]);

  // Анализ документов
  const analyzeDocument = useCallback(async (imageFile, options = {}) => {
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
