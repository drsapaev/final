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
        backgroundColor: '#ffffff',
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        overflow: 'hidden'
      }}
      {...props}>
      
      {/* Заголовок */}
      <div
        className="ai-assistant-header"
        style={{
          padding: '16px 20px',
          backgroundColor: '#f8fafc',
          borderBottom: '1px solid #e5e7eb',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ fontSize: '20px' }}>🤖</div>
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: '600', color: '#374151' }}>
            ИИ Помощник
          </h3>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={onStartListening}
            disabled={loading || isListening}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              backgroundColor: isListening ? '#dbeafe' : '#ffffff',
              color: '#374151',
              cursor: loading || isListening ? 'not-allowed' : 'pointer',
              opacity: loading || isListening ? 0.6 : 1,
              transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
            }}
            onMouseEnter={(e) => {
              if (!loading && !isListening && !prefersReducedMotion) {
                e.target.style.backgroundColor = '#f9fafb';
              }
            }}
            onMouseLeave={(e) => {
              if (!loading && !isListening && !prefersReducedMotion) {
                e.target.style.backgroundColor = '#ffffff';
              }
            }}>
            
            {isListening ? '🎤 Слушаю...' : '🎤 Голос'}
          </button>

          <button
            onClick={onClearMessages}
            disabled={loading || messages.length === 0}
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              backgroundColor: '#ffffff',
              color: '#374151',
              cursor: loading || messages.length === 0 ? 'not-allowed' : 'pointer',
              opacity: loading || messages.length === 0 ? 0.6 : 1,
              transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
            }}
            onMouseEnter={(e) => {
              if (!loading && messages.length > 0 && !prefersReducedMotion) {
                e.target.style.backgroundColor = '#fef2f2';
                e.target.style.borderColor = '#fecaca';
              }
            }}
            onMouseLeave={(e) => {
              if (!loading && messages.length > 0 && !prefersReducedMotion) {
                e.target.style.backgroundColor = '#ffffff';
                e.target.style.borderColor = '#d1d5db';
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
          padding: '16px'
        }}>
        
        {messages.length === 0 ?
        <div
          style={{
            textAlign: 'center',
            color: '#6b7280',
            fontSize: '14px',
            marginTop: '40px'
          }}>
          
            Начните разговор с ИИ помощником
          </div> :

        messages.map((message) =>
        <div
          key={message.id}
          className={`message ${message.role}`}
          style={{
            marginBottom: '16px',
            padding: '12px 16px',
            borderRadius: '8px',
            maxWidth: '80%',
            ...(message.role === 'user' ?
            {
              backgroundColor: '#3b82f6',
              color: '#ffffff',
              marginLeft: 'auto',
              borderBottomRightRadius: '4px'
            } :
            {
              backgroundColor: '#f3f4f6',
              color: '#374151',
              borderBottomLeftRadius: '4px'
            })

          }}>
          
              <div style={{ fontSize: '14px', lineHeight: '1.4' }}>
                {message.content}
              </div>
              <div
            style={{
              fontSize: '11px',
              opacity: 0.7,
              marginTop: '4px'
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
          borderTop: '1px solid #e5e7eb',
          backgroundColor: '#f8fafc'
        }}>
        
        {error &&
        <div
          style={{
            color: '#ef4444',
            fontSize: '12px',
            marginBottom: '8px',
            padding: '4px 8px',
            backgroundColor: '#fef2f2',
            borderRadius: '4px',
            border: '1px solid #fecaca'
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
          style={{ display: 'flex', gap: '8px' }}>
          
          <input
            type="text"
            name="message"
            placeholder="Задайте вопрос ИИ помощнику..."
            disabled={loading}
            style={{
              flex: 1,
              padding: '10px 12px',
              fontSize: '14px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              backgroundColor: '#ffffff',
              color: '#374151',
              outline: 'none',
              transition: prefersReducedMotion ? 'none' : 'border-color 0.2s ease'
            }}
            onFocus={(e) => {
              if (!prefersReducedMotion) {
                e.target.style.borderColor = '#3b82f6';
              }
            }}
            onBlur={(e) => {
              if (!prefersReducedMotion) {
                e.target.style.borderColor = '#d1d5db';
              }
            }} />
          

          <button
            type="submit"
            disabled={loading}
            style={{
              padding: '10px 16px',
              fontSize: '14px',
              fontWeight: '500',
              border: '1px solid #3b82f6',
              borderRadius: '6px',
              backgroundColor: '#3b82f6',
              color: '#ffffff',
              cursor: loading ? 'not-allowed' : 'pointer',
              opacity: loading ? 0.6 : 1,
              transition: prefersReducedMotion ? 'none' : 'all 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
            onMouseEnter={(e) => {
              if (!loading && !prefersReducedMotion) {
                e.target.style.backgroundColor = '#2563eb';
              }
            }}
            onMouseLeave={(e) => {
              if (!loading && !prefersReducedMotion) {
                e.target.style.backgroundColor = '#3b82f6';
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
        backgroundColor: '#ffffff',
        border: '1px solid #e5e7eb',
        borderRadius: '8px',
        overflow: 'hidden'
      }}
      {...props}>
      
      {/* Заголовок */}
      <div
        style={{
          padding: '16px 20px',
          backgroundColor: '#f8fafc',
          borderBottom: '1px solid #e5e7eb',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ fontSize: '18px' }}>💡</div>
          <h4 style={{ margin: 0, fontSize: '14px', fontWeight: '600', color: '#374151' }}>
            ИИ Предложения
          </h4>
        </div>

        <button
          onClick={onGenerateMore}
          disabled={loading}
          style={{
            padding: '6px 12px',
            fontSize: '12px',
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            backgroundColor: '#ffffff',
            color: '#374151',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1,
            transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
          }}
          onMouseEnter={(e) => {
            if (!loading && !prefersReducedMotion) {
              e.target.style.backgroundColor = '#f9fafb';
            }
          }}
          onMouseLeave={(e) => {
            if (!loading && !prefersReducedMotion) {
              e.target.style.backgroundColor = '#ffffff';
            }
          }}>
          
          {loading ? 'Генерация...' : '🔄 Ещё'}
        </button>
      </div>

      {/* Предложения */}
      <div style={{ padding: '16px' }}>
        {error &&
        <div
          style={{
            color: '#ef4444',
            fontSize: '12px',
            marginBottom: '12px',
            padding: '8px',
            backgroundColor: '#fef2f2',
            borderRadius: '4px',
            border: '1px solid #fecaca'
          }}>
          
            {error}
          </div>
        }

        {suggestions.length === 0 && !loading && !error ?
        <div
          style={{
            textAlign: 'center',
            color: '#6b7280',
            fontSize: '14px',
            padding: '20px'
          }}>
          
            Предложений пока нет
          </div> :

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {suggestions.map((suggestion) =>
          <button
            key={suggestion.id}
            onClick={() => onSelectSuggestion && onSelectSuggestion(suggestion)}
            style={{
              padding: '12px 16px',
              textAlign: 'left',
              border: '1px solid #e5e7eb',
              borderRadius: '6px',
              backgroundColor: '#ffffff',
              color: '#374151',
              cursor: 'pointer',
              transition: prefersReducedMotion ? 'none' : 'all 0.2s ease',
              fontSize: '14px',
              lineHeight: '1.4'
            }}
            onMouseEnter={(e) => {
              if (!prefersReducedMotion) {
                e.target.style.backgroundColor = '#f8fafc';
                e.target.style.borderColor = '#d1d5db';
              }
            }}
            onMouseLeave={(e) => {
              if (!prefersReducedMotion) {
                e.target.style.backgroundColor = '#ffffff';
                e.target.style.borderColor = '#e5e7eb';
              }
            }}>
            
                <div style={{ fontWeight: '500', marginBottom: '4px' }}>
                  {suggestion.text}
                </div>
                {suggestion.confidence &&
            <div
              style={{
                fontSize: '11px',
                color: '#6b7280',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
              
                    <span>Уверенность: {Math.round(suggestion.confidence * 100)}%</span>
                    {suggestion.category &&
              <span style={{ backgroundColor: '#e5e7eb', padding: '2px 6px', borderRadius: '10px' }}>
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
