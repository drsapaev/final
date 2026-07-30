
/**
 * AIChatWidget - Виджет AI чата
 * 
 * Встраиваемый компонент для чата с AI.
 * Может использоваться на любой странице.
 */

import React, { useState, useRef, useEffect } from 'react';
import { useAIChat } from '../../hooks/useAIChat';
import './AIChatWidget.css';
import { useTranslation } from '../../i18n/useTranslation';

/**
 * AI Chat Widget Component
 * 
 * @param {Object} props
 * @param {string} props.contextType - Тип контекста (emr, lab, general)
 * @param {string} props.specialty - Специализация врача
 * @param {boolean} props.useWebSocket - Использовать WebSocket для streaming
 * @param {boolean} props.minimized - Начать в свернутом состоянии
 * @param {string} props.position - Позиция виджета (bottom-right, bottom-left)
 */
const AIChatWidget = ({
  contextType = 'general',
  specialty = null,
  useWebSocket = false,
  minimized: initialMinimized = true,
  position = 'bottom-right'
}: {
  contextType?: string;
  specialty?: string | null;
  useWebSocket?: boolean;
  minimized?: boolean;
  position?: string;
}) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [minimized, setMinimized] = useState(initialMinimized);
  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const {
    messages,
    loading,
    streaming,
    error,
    connected,
    sendMessage,
    sendMessageWS,
    clearError,
    createSession

  } = useAIChat({
    useWebSocket,
    contextType,
    specialty
  });

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    if (!minimized) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, minimized]);

  // Focus input when expanded
  useEffect(() => {
    if (!minimized) {
      inputRef.current?.focus();
    }
  }, [minimized]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!inputValue.trim() || loading || streaming) return;

    const message = inputValue.trim();
    setInputValue('');

    if (useWebSocket) {
      sendMessageWS(message);
    } else {
      await sendMessage(message);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as unknown as React.FormEvent);
    }
  };

  const formatTime = (isoString: string) => {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  };

  const renderMessage = (msg: {
    id?: string | number;
    role: string;
    content: unknown;
    _streaming?: boolean;
    _pending?: boolean;
    created_at?: string;
    [key: string]: unknown;
  }, index: number) => {
    const isUser = msg.role === 'user';
    const isStreaming = msg._streaming;
    const content = String(msg.content ?? '');

    return (
      <div
        key={msg.id || index}
        className={`chat-message ${isUser ? 'user' : 'assistant'} ${isStreaming ? 'streaming' : ''}`}>
        
                <div className="message-avatar">
                    {isUser ? '👤' : '🤖'}
                </div>
                <div className="message-content">
                    <div className="message-text">
                        {content}
                        {isStreaming && <span className="cursor">▌</span>}
                    </div>
                    <div className="message-meta">
                        {!isUser && msg.provider ? (
            <span className="provider-badge">{String(msg.provider)}</span>
            ) : null}
                        {!isUser && msg.was_cached ? (
            <span className="cached-badge">⚡ cached</span>
            ) : null}
                        <span className="time">{formatTime(msg.created_at || '')}</span>
                    </div>
                </div>
            </div>);

  };

  if (minimized) {
    return (
      <button
        className={`chat-widget-fab ${position}`}
        onClick={() => setMinimized(false)}
        title={t('misc.acw_otkryt_ai_chat')}>
        
                <span className="fab-icon">💬</span>
                <span className="fab-label">AI</span>
                {useWebSocket && connected && <span className="connected-dot" />}
            </button>);

  }

  return (
    <div className={`chat-widget ${position}`}>
            {/* Header */}
            <div className="chat-widget-header">
                <div className="header-left">
                    <span className="header-icon">🤖</span>
                    <span className="header-title">AI Ассистент</span>
                    {useWebSocket &&
          <span className={`connection-status ${connected ? 'online' : 'offline'}`}>
                            {connected ? t('misc.acw_onlayn') : t('misc.acw_offlayn')}
                        </span>
          }
                </div>
                <div className="header-actions">
                    <button
            className="header-btn"
            onClick={() => createSession()}
            title={t('misc.acw_novyy_chat')}>
            
                        ➕
                    </button>
                    <button
            className="header-btn"
            onClick={() => setMinimized(true)}
            title={t('misc.acw_svernut')}>
            
                        ➖
                    </button>
                </div>
            </div>

            {/* Messages */}
            <div className="chat-widget-messages">
                {messages.length === 0 ?
        <div className="empty-state">
                        <div className="empty-icon">💡</div>
                        <div className="empty-title">{t('misc.acw_zadayte_vopros_ai')}</div>
                        <div className="empty-hint">
                            AI поможет с анализом симптомов, подбором кодов МКБ-10,
                            интерпретацией анализов и другими медицинскими вопросами.
                        </div>
                        <div className="empty-disclaimer">
                            ⚠️ AI дает рекомендации, окончательное решение принимает врач
                        </div>
                    </div> :

        <>
                        {messages.map(renderMessage)}
                        <div ref={messagesEndRef} />
                    </>
        }
            </div>

            {/* Error */}
            {error &&
      <div className="chat-widget-error">
                    <span>⚠️ {error}</span>
                    <button onClick={clearError}>✕</button>
                </div>
      }

            {/* Input */}
            <form className="chat-widget-input" onSubmit={handleSubmit}>
                <textarea
          ref={inputRef}
          aria-label={t('misc.acw_soobschenie_dlya_ai_chata')}
          value={inputValue}
          onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('misc.acw_vvedite_soobschenie')}
          disabled={loading || streaming}
          rows={1} />
        
                <button
          type="submit"
          disabled={!inputValue.trim() || loading || streaming}
          title={t('misc.acw_otpravit')}>
          
                    {loading || streaming ?
          <span className="spinner">⏳</span> :

          '📤'
          }
                </button>
            </form>
        </div>);

};


// audit/strict: removed self-referencing propTypes spread

export default AIChatWidget;
