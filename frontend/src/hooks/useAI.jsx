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

// Компонент ИИ помощника
export const AIAssistant = ({
  messages = [],
  loading = false,
  error = null,
  onSendMessage,
  onClearMessages,
  onStartListening,
  isListening = false,
  className = '',
  ...props
}) => {
  const { prefersReducedMotion } = useReducedMotion();

  return (
    <div
      className={`ai-assistant ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: 'var(--mac-bg-primary)',
        border: '1px solid var(--mac-border)',
        borderRadius: 'var(--mac-radius-md)',
        overflow: 'hidden'
      }}
      {...props}>
      
      {/* Заголовок */}
      <div
        className="ai-assistant-header"
        style={{
          padding: '16px 20px',
          backgroundColor: 'var(--mac-bg-secondary)',
          borderBottom: '1px solid var(--mac-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
          <div style={{ fontSize: 'var(--mac-font-size-2xl)' }}>🤖</div>
          <h3 style={{ margin: 0, fontSize: 'var(--mac-font-size-lg)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
            ИИ Помощник
          </h3>
        </div>

        <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)' }}>
          <button
            onClick={onStartListening}
            disabled={loading || isListening}
            style={{
              padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
              fontSize: 'var(--mac-font-size-xs)',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-sm)',
              backgroundColor: isListening ? 'var(--mac-accent-bg)' : 'var(--mac-bg-primary)',
              color: 'var(--mac-text-primary)',
              cursor: loading || isListening ? 'not-allowed' : 'pointer',
              opacity: loading || isListening ? 0.6 : 1,
              transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
            }}
            onMouseEnter={(e) => {
              if (!loading && !isListening && !prefersReducedMotion) {
                e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
              }
            }}
            onMouseLeave={(e) => {
              if (!loading && !isListening && !prefersReducedMotion) {
                e.target.style.backgroundColor = 'var(--mac-bg-primary)';
              }
            }}>
            
            {isListening ? '🎤 Слушаю...' : '🎤 Голос'}
          </button>

          <button
            onClick={onClearMessages}
            disabled={loading || messages.length === 0}
            style={{
              padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
              fontSize: 'var(--mac-font-size-xs)',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-sm)',
              backgroundColor: 'var(--mac-bg-primary)',
              color: 'var(--mac-text-primary)',
              cursor: loading || messages.length === 0 ? 'not-allowed' : 'pointer',
              opacity: loading || messages.length === 0 ? 0.6 : 1,
              transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
            }}
            onMouseEnter={(e) => {
              if (!loading && messages.length > 0 && !prefersReducedMotion) {
                e.target.style.backgroundColor = 'var(--mac-error-bg)';
                e.target.style.borderColor = 'var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))';
              }
            }}
            onMouseLeave={(e) => {
              if (!loading && messages.length > 0 && !prefersReducedMotion) {
                e.target.style.backgroundColor = 'var(--mac-bg-primary)';
                e.target.style.borderColor = 'var(--mac-border)';
              }
            }}>
            
            🗑️ Очистить
          </button>
        </div>
      </div>

      {/* Сообщения */}
      <div
        className="ai-assistant-messages"
        style={{
          flex: 1,
          overflow: 'auto',
          padding: 'var(--mac-spacing-4)'
        }}>
        
        {messages.length === 0 ?
        <div
          style={{
            textAlign: 'center',
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-base)',
            marginTop: '40px'
          }}>
          
            Начните разговор с ИИ помощником
          </div> :

        messages.map((message) =>
        <div
          key={message.id}
          className={`message ${message.role}`}
          style={{
            marginBottom: 'var(--mac-spacing-4)',
            padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
            borderRadius: 'var(--mac-radius-md)',
            maxWidth: '80%',
            ...(message.role === 'user' ?
            {
              backgroundColor: 'var(--mac-accent-blue)',
              color: 'var(--mac-bg-primary)',
              marginLeft: 'auto',
              borderBottomRightRadius: '4px'
            } :
            {
              backgroundColor: 'var(--mac-bg-secondary)',
              color: 'var(--mac-text-primary)',
              borderBottomLeftRadius: '4px'
            })

          }}>
          
              <div style={{ fontSize: 'var(--mac-font-size-base)', lineHeight: '1.4' }}>
                {message.content}
              </div>
              <div
            style={{
              fontSize: 'var(--mac-font-size-xs)',
              opacity: 0.7,
              marginTop: 'var(--mac-spacing-1)'
            }}>
            
                {message.timestamp.toLocaleTimeString()}
              </div>
            </div>
        )
        }
      </div>

      {/* Поле ввода */}
      <div
        className="ai-assistant-input"
        style={{
          padding: '16px 20px',
          borderTop: '1px solid var(--mac-border)',
          backgroundColor: 'var(--mac-bg-secondary)'
        }}>
        
        {error &&
        <div
          style={{
            color: 'var(--mac-error)',
            fontSize: 'var(--mac-font-size-xs)',
            marginBottom: 'var(--mac-spacing-2)',
            padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
            backgroundColor: 'var(--mac-error-bg)',
            borderRadius: 'var(--mac-radius-sm)',
            border: '1px solid var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))'
          }}>
          
            {error}
          </div>
        }

        <form
          onSubmit={(e) => {
            e.preventDefault();
            const input = e.target.elements.message;
            if (input.value.trim()) {
              onSendMessage(input.value);
              input.value = '';
            }
          }}
          style={{ display: 'flex', gap: 'var(--mac-spacing-2)' }}>
          
          <input
            type="text"
            name="message"
            placeholder="Задайте вопрос ИИ помощнику..."
            aria-label="Сообщение ИИ помощнику"
            disabled={loading}
            style={{
              flex: 1,
              padding: '10px 12px',
              fontSize: 'var(--mac-font-size-base)',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-sm)',
              backgroundColor: 'var(--mac-bg-primary)',
              color: 'var(--mac-text-primary)',
              outline: 'none',
              transition: prefersReducedMotion ? 'none' : 'border-color 0.2s ease'
            }}
            onFocus={(e) => {
              if (!prefersReducedMotion) {
                e.target.style.borderColor = 'var(--mac-accent-blue)';
              }
            }}
            onBlur={(e) => {
              if (!prefersReducedMotion) {
                e.target.style.borderColor = 'var(--mac-border)';
              }
            }} />
          

          <button
            type="submit"
            disabled={loading}
            aria-label={loading ? 'Отправка сообщения ИИ помощнику' : 'Отправить сообщение ИИ помощнику'}
            style={{
              padding: '10px 16px',
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-medium)',
              border: '1px solid var(--mac-accent-blue)',
              borderRadius: 'var(--mac-radius-sm)',
              backgroundColor: 'var(--mac-accent-blue)',
              color: 'var(--mac-bg-primary)',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1,
              transition: prefersReducedMotion ? 'none' : 'all 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-2)'
            }}
            onMouseEnter={(e) => {
              if (!loading && !prefersReducedMotion) {
                e.target.style.backgroundColor = 'var(--mac-accent-blue-hover)';
              }
            }}
            onMouseLeave={(e) => {
              if (!loading && !prefersReducedMotion) {
                e.target.style.backgroundColor = 'var(--mac-accent-blue)';
              }
            }}>
            
            {loading ?
            <>
                <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Отправка...
              </> :

            <>
                <span>Отправить</span>
                <span>📤</span>
              </>
            }
          </button>
        </form>
      </div>
    </div>);

};

// Компонент ИИ предложений
export const AISuggestions = ({
  suggestions = [],
  loading = false,
  error = null,
  onSelectSuggestion,
  onGenerateMore,
  className = '',
  ...props
}) => {
  const { prefersReducedMotion } = useReducedMotion();

  return (
    <div
      className={`ai-suggestions ${className}`}
      style={{
        backgroundColor: 'var(--mac-bg-primary)',
        border: '1px solid var(--mac-border)',
        borderRadius: 'var(--mac-radius-md)',
        overflow: 'hidden'
      }}
      {...props}>
      
      {/* Заголовок */}
      <div
        style={{
          padding: '16px 20px',
          backgroundColor: 'var(--mac-bg-secondary)',
          borderBottom: '1px solid var(--mac-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
          <div style={{ fontSize: 'var(--mac-font-size-xl)' }}>💡</div>
          <h4 style={{ margin: 0, fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
            ИИ Предложения
          </h4>
        </div>

        <button
          onClick={onGenerateMore}
          disabled={loading}
          style={{
            padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
            fontSize: 'var(--mac-font-size-xs)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-sm)',
            backgroundColor: 'var(--mac-bg-primary)',
            color: 'var(--mac-text-primary)',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1,
            transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
          }}
          onMouseEnter={(e) => {
            if (!loading && !prefersReducedMotion) {
              e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
            }
          }}
          onMouseLeave={(e) => {
            if (!loading && !prefersReducedMotion) {
              e.target.style.backgroundColor = 'var(--mac-bg-primary)';
            }
          }}>
          
          {loading ? 'Генерация...' : '🔄 Ещё'}
        </button>
      </div>

      {/* Предложения */}
      <div style={{ padding: 'var(--mac-spacing-4)' }}>
        {error &&
        <div
          style={{
            color: 'var(--mac-error)',
            fontSize: 'var(--mac-font-size-xs)',
            marginBottom: 'var(--mac-spacing-3)',
            padding: 'var(--mac-spacing-2)',
            backgroundColor: 'var(--mac-error-bg)',
            borderRadius: 'var(--mac-radius-sm)',
            border: '1px solid var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))'
          }}>
          
            {error}
          </div>
        }

        {suggestions.length === 0 && !loading && !error ?
        <div
          style={{
            textAlign: 'center',
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-base)',
            padding: 'var(--mac-spacing-5)'
          }}>
          
            Предложений пока нет
          </div> :

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-2)' }}>
            {suggestions.map((suggestion) =>
          <button
            key={suggestion.id}
            onClick={() => onSelectSuggestion && onSelectSuggestion(suggestion)}
            style={{
              padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
              textAlign: 'left',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-sm)',
              backgroundColor: 'var(--mac-bg-primary)',
              color: 'var(--mac-text-primary)',
              cursor: 'pointer',
              transition: prefersReducedMotion ? 'none' : 'all 0.2s ease',
              fontSize: 'var(--mac-font-size-base)',
              lineHeight: '1.4'
            }}
            onMouseEnter={(e) => {
              if (!prefersReducedMotion) {
                e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
                e.target.style.borderColor = 'var(--mac-border)';
              }
            }}
            onMouseLeave={(e) => {
              if (!prefersReducedMotion) {
                e.target.style.backgroundColor = 'var(--mac-bg-primary)';
                e.target.style.borderColor = 'var(--mac-border)';
              }
            }}>
            
                <div style={{ fontWeight: 'var(--mac-font-weight-medium)', marginBottom: 'var(--mac-spacing-1)' }}>
                  {suggestion.text}
                </div>
                {suggestion.confidence &&
            <div
              style={{
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--mac-text-secondary)',
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--mac-spacing-2)'
              }}>
              
                    <span>Уверенность: {Math.round(suggestion.confidence * 100)}%</span>
                    {suggestion.category &&
              <span style={{ backgroundColor: 'var(--mac-border)', padding: '2px 6px', borderRadius: 'var(--mac-radius-lg)' }}>
                        {suggestion.category}
                      </span>
              }
                  </div>
            }
              </button>
          )}
          </div>
        }
      </div>
    </div>);

};

const aiMessageShape = PropTypes.shape({
  id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  role: PropTypes.string,
  content: PropTypes.string,
  timestamp: PropTypes.oneOfType([PropTypes.instanceOf(Date), PropTypes.string]),
  type: PropTypes.string
});

const aiSuggestionShape = PropTypes.shape({
  id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  text: PropTypes.string,
  confidence: PropTypes.number,
  category: PropTypes.string
});

AIAssistant.propTypes = {
  messages: PropTypes.arrayOf(aiMessageShape),
  loading: PropTypes.bool,
  error: PropTypes.oneOfType([PropTypes.string, PropTypes.node]),
  onSendMessage: PropTypes.func,
  onClearMessages: PropTypes.func,
  onStartListening: PropTypes.func,
  isListening: PropTypes.bool,
  className: PropTypes.string
};

AISuggestions.propTypes = {
  suggestions: PropTypes.arrayOf(aiSuggestionShape),
  loading: PropTypes.bool,
  error: PropTypes.oneOfType([PropTypes.string, PropTypes.node]),
  onSelectSuggestion: PropTypes.func,
  onGenerateMore: PropTypes.func,
  className: PropTypes.string
};

export default useAIAssistant;
