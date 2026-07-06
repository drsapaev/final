
/**
 * Окно чата с AI Доктором
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import ReactDOM from 'react-dom';
import { X, Send, Bot, RefreshCw, Copy, Sparkles } from 'lucide-react';
import { apiClient } from '../../api/client';
import { notify } from '../../services/notify.js';
import logger from '../../utils/logger';
import './AIChatWindow.css';
import PropTypes from 'prop-types';

const AIChatWindow = ({ isOpen, onClose, contextData = {} }) => {
  const [messages, setMessages] = useState([
  {
    id: 'welcome',
    role: 'assistant',
    content: 'Здравствуйте! Я ваш AI-ассистент. Я могу помочь с дифференциальной диагностикой, планом лечения или интерпретацией анализов. Чем могу быть полезен?'
  }]
  );
  const [inputValue, setInputValue] = useState('');
  const [isThinking, setIsThinking] = useState(false);

  // Initial position centered or to the right
  // Initial position from localStorage or default
  const [position, setPosition] = useState(() => {
    const savedPos = localStorage.getItem('ai_chat_position');
    if (savedPos) {
      try {
        return JSON.parse(savedPos);
      } catch (e) {
        logger.error('Failed to parse saved chat position', e);
      }
    }
    return {
      x: Math.max(0, window.innerWidth - 420),
      y: 100
    };
  });

  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  // focus input
  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    }
  }, [isOpen]);

  const handleSend = async () => {
    if (!inputValue.trim() || isThinking) return;

    const userMsg = {
      id: Date.now(),
      role: 'user',
      content: inputValue.trim()
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');
    setIsThinking(true);

    try {
      // Prepare context for AI
      const requestData = {
        message: userMsg.content,
        context: contextData,
        history: messages.map((m) => ({ role: m.role, content: m.content }))
      };

      // Call backend 
      const response = await apiClient.post('/ai/doctor-chat', requestData);

      const aiMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.data.reply
      };

      setMessages((prev) => [...prev, aiMsg]);
    } catch (error) {
      logger.error('AI Chat Error:', error);
      notify.error('Ошибка связи с AI сервисом');

      // Add error message to chat
      setMessages((prev) => [...prev, {
        id: Date.now() + 1,
        role: 'system',
        content: 'Произошла ошибка при получении ответа. Пожалуйста, попробуйте еще раз.'
      }]);
    } finally {
      setIsThinking(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Drag handlers
  const handleMouseDown = (e) => {
    setIsDragging(true);
    setDragOffset({
      x: e.clientX - position.x,
      y: e.clientY - position.y
    });
  };

  const handleMouseMove = useCallback((e) => {
    if (isDragging) {
      setPosition({
        x: e.clientX - dragOffset.x,
        y: e.clientY - dragOffset.y
      });
    }
  }, [isDragging, dragOffset]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    // Save final position
    localStorage.setItem('ai_chat_position', JSON.stringify(position));
  }, [position]);

  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    notify.success('Скопировано');
  };

  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <div className="ai-chat-overlay" style={{ pointerEvents: 'none' }}>
            <div
        className="ai-chat-window"
        style={{
          position: 'absolute',
          left: position.x,
          top: position.y,
          pointerEvents: 'auto'
        }}>
        
                {/* Header with Drag Handle */}
                <div
          className="ai-chat-header"
          onPointerDown={handleMouseDown}
          style={{ cursor: isDragging ? 'grabbing' : 'grab', userSelect: 'none' }}>
          
                    <div className="ai-chat-title">
                        <div className="ai-avatar">
                            <Bot size={20} color="white" />
                        </div>
                        <div>
                            <h3>AI Doctor</h3>
                            <span className="ai-status">
                                {isThinking ? 'Анализирую...' : 'Online'}
                            </span>
                        </div>
                    </div>
                    <div className="ai-actions">
                        <button onClick={() => setMessages([{
              id: 'welcome',
              role: 'assistant',
              content: 'Здравствуйте! Я ваш AI-ассистент. Чем могу помочь?'
            }])} className="ai-btn-icon" title="Очистить чат" aria-label="Очистить чат">
                            <RefreshCw size={16} />
                        </button>
                        <button onClick={onClose} className="ai-btn-icon" title="Закрыть" aria-label="Закрыть">
                            <X size={18} />
                        </button>
                    </div>
                </div>

                {/* Messages */}
                <div className="ai-chat-content">
                    {messages.map((msg) =>
          <div key={msg.id} className={`ai-message ${msg.role}`}>
                            <div className="message-bubble">
                                {msg.role === 'assistant' &&
              <div className="message-icon bot">
                                        <Sparkles size={14} />
                                    </div>
              }
                                <div className="message-text">
                                    {msg.content}
                                </div>
                                {msg.role === 'assistant' &&
              <button
                className="copy-btn"
                onClick={() => copyToClipboard(msg.content)}
                title="Копировать"
                aria-label="Копировать ответ AI Doctor">
                
                                        <Copy size={12} />
                                    </button>
              }
                            </div>
                        </div>
          )}
                    {isThinking &&
          <div className="ai-message assistant">
                            <div className="message-bubble thinking">
                                <div className="dot"></div>
                                <div className="dot"></div>
                                <div className="dot"></div>
                            </div>
                        </div>
          }
                    <div ref={messagesEndRef} />
                </div>

                {/* Input */}
                <div className="ai-chat-input">
                    <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Спросите о диагнозе, лечении или анализах..."
            aria-label="Сообщение AI Doctor"
            rows={1}
            disabled={isThinking} />
          
                    <button
            onClick={handleSend}
            disabled={!inputValue.trim() || isThinking}
            aria-label="Отправить сообщение AI Doctor"
            className="ai-send-btn">
            
                        <Send size={16} />
                    </button>
                </div>
            </div>
        </div>,
    document.body
  );
};


AIChatWindow.propTypes = {
  ...(AIChatWindow.propTypes || {}),
  contextData: PropTypes.any,
  isOpen: PropTypes.any,
  onClose: PropTypes.any,
};

export default AIChatWindow;
