/**
 * Главное окно чата
 */

import React, { useState, useEffect, useRef } from 'react';
import ReactDOM from 'react-dom';
import { X, Send, MessageCircle, ChevronLeft, Plus, Search, Check, CheckCheck, Mic, Filter } from 'lucide-react';
import { useChat } from '../../hooks/useChat';
import auth from '../../stores/auth';
import VoiceRecorder from './VoiceRecorder';
import VoiceMessage from './VoiceMessage';
import './Chat.css';

const ChatWindow = ({ isOpen, onClose }) => {
    const [authState, setAuthState] = useState(auth.getState());
    const user = authState.profile;
    const {
        conversations,
        messages,
        activeConversation,
        unreadCount,
        isConnected,
        isLoading,
        typingUsers,
        loadConversations,
        loadMessages,
        sendMessage,
        sendTyping,
        searchUsers,
        closeConversation,
        setActiveConversation
    } = useChat();

    const [inputValue, setInputValue] = useState('');
    const [isSending, setIsSending] = useState(false);
    const [showNewChat, setShowNewChat] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [isSearching, setIsSearching] = useState(false);
    const [showVoiceRecorder, setShowVoiceRecorder] = useState(false);

    // Search & Filter State
    const [convSearchQuery, setConvSearchQuery] = useState('');
    const [convFilter, setConvFilter] = useState('all'); // 'all' | 'unread'
    const [showMsgSearch, setShowMsgSearch] = useState(false);
    const [msgSearchQuery, setMsgSearchQuery] = useState('');

    // Список всех пользователей для отображения по дефолту
    const [allUsers, setAllUsers] = useState([]);

    const messagesEndRef = useRef(null);
    const inputRef = useRef(null);
    const typingTimeoutRef = useRef(null);

    // Позиция окна - правый верхний угол (macOS стиль)
    const [position] = useState({ x: window.innerWidth - 400, y: 70 });

    // Подписка на изменения auth
    useEffect(() => {
        const unsubscribe = auth.subscribe(setAuthState);
        return unsubscribe;
    }, []);

    // Прокрутка к последнему сообщению
    useEffect(() => {
        if (messages.length > 0) {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages]);

    // Фокус на input при открытии беседы
    useEffect(() => {
        if (activeConversation) {
            inputRef.current?.focus();
        }
    }, [activeConversation]);

    // Загрузка пользователей если нет бесед
    useEffect(() => {
        if (isOpen && conversations.length === 0) {
            // Загружаем пользователей каждый раз при открытии окна (если нет бесед)
            searchUsers('').then(users => {
                if (users && Array.isArray(users)) {
                    setAllUsers(users);
                }
            }).catch(e => console.error('Failed to load users:', e));
        }
    }, [isOpen, conversations.length]);

    // Поиск пользователей
    useEffect(() => {
        if (!showNewChat) return;

        const search = async () => {
            if (searchQuery.length < 1) {
                setSearchResults([]);
                return;
            }

            setIsSearching(true);
            try {
                const results = await searchUsers(searchQuery);
                setSearchResults(results);
            } catch (e) {
                console.error('Search error:', e);
            } finally {
                setIsSearching(false);
            }
        };

        const timeout = setTimeout(search, 300);
        return () => clearTimeout(timeout);
    }, [searchQuery, showNewChat, searchUsers]);

    // Отправка сообщения
    const handleSend = async () => {
        if (!inputValue.trim() || !activeConversation || isSending) return;

        const content = inputValue.trim();
        setInputValue('');
        setIsSending(true);

        try {
            await sendMessage(activeConversation, content);
            sendTyping(activeConversation, false);
        } catch (error) {
            setInputValue(content);
            alert('Ошибка отправки сообщения');
        } finally {
            setIsSending(false);
        }
    };

    // Отправка голосового сообщения
    const handleSendVoice = async (audioBlob, duration) => {
        console.log('📤 handleSendVoice called. activeConversation:', activeConversation);

        if (!activeConversation || isSending) {
            console.warn('⚠️ Cannot send voice: activeConversation=', activeConversation, 'isSending=', isSending);
            return;
        }

        setIsSending(true);
        setShowVoiceRecorder(false);

        try {
            const formData = new FormData();
            formData.append('audio_file', audioBlob, 'voice.webm');
            formData.append('recipient_id', activeConversation);

            const token = auth.getState().token;
            const response = await fetch('/api/v1/messages/send-voice', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Ошибка отправки');
            }

            const messageData = await response.json();
            console.log('✅ Voice message sent successfully, response:', messageData);

            // Обновляем только список бесед - сообщение придет через WebSocket
            loadConversations();
        } catch (error) {
            console.error('Voice send error:', error);
            alert('Ошибка отправки голосового сообщения: ' + error.message);
        } finally {
            setIsSending(false);
        }
    };

    // Обработка ввода
    const handleInputChange = (e) => {
        setInputValue(e.target.value);

        if (activeConversation) {
            sendTyping(activeConversation, true);
            clearTimeout(typingTimeoutRef.current);
            typingTimeoutRef.current = setTimeout(() => {
                sendTyping(activeConversation, false);
            }, 2000);
        }
    };

    // Enter для отправки
    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    // Начать новую беседу
    const startConversation = (userId) => {
        setShowNewChat(false);
        setSearchQuery('');
        setSearchResults([]);
        loadMessages(userId);
    };

    // Назад к списку
    const handleBack = () => {
        if (showNewChat) {
            setShowNewChat(false);
            setSearchQuery('');
            setSearchResults([]);
        } else {
            closeConversation();
        }
    };

    // Форматирование времени
    const formatTime = (dateStr) => {
        const date = new Date(dateStr);
        const now = new Date();
        const diff = now - date;

        if (diff < 86400000 && date.getDate() === now.getDate()) {
            return date.toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' });
        }
        if (diff < 172800000) {
            return 'Вчера';
        }
        return date.toLocaleDateString('ru', { day: 'numeric', month: 'short' });
    };

    const getActiveUser = () => {
        return conversations.find(c => c.user_id === activeConversation);
    };

    // Filtered Conversations
    const filteredConversations = conversations.filter(c => {
        const matchesSearch = !convSearchQuery ||
            (c.user_name && c.user_name.toLowerCase().includes(convSearchQuery.toLowerCase())) ||
            (c.last_message && c.last_message.toLowerCase().includes(convSearchQuery.toLowerCase()));

        const matchesFilter = convFilter === 'all' ||
            (convFilter === 'unread' && c.unread_count > 0);

        return matchesSearch && matchesFilter;
    });

    // Filtered Messages
    const filteredMessages = showMsgSearch && msgSearchQuery
        ? messages.filter(m => m.content && m.content.toLowerCase().includes(msgSearchQuery.toLowerCase()))
        : messages;

    if (!isOpen) return null;

    const activeUser = getActiveUser();

    // Используем Portal для рендеринга вне иерархии (z-index проблема)
    return ReactDOM.createPortal(
        <div className="chat-window-overlay" style={{ pointerEvents: 'none', background: 'transparent' }}>
            <div
                className="chat-window"
                style={{
                    position: 'absolute',
                    left: position.x,
                    top: position.y,
                    transform: 'none',
                    margin: 0,
                    pointerEvents: 'auto',
                    height: 550 // Высота окна фиксирована
                }}

                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="chat-header">
                    <div className="chat-title-group">
                        <div className={`chat-status-indicator ${isConnected ? 'online' : 'connecting'}`}
                            title={isConnected ? 'Онлайн' : 'Подключение...'} />

                        {(activeConversation || showNewChat) && (
                            <button onClick={handleBack} className="chat-btn-icon" title="Назад">
                                <ChevronLeft size={20} />
                            </button>
                        )}

                        <h3>
                            {showNewChat
                                ? 'Новое сообщение'
                                : activeUser
                                    ? activeUser.user_name
                                    : 'Чаты'
                            }
                        </h3>
                    </div>

                    <div className="chat-actions" style={{ display: 'flex', gap: '4px' }}>
                        {activeConversation && !showNewChat && (
                            <button
                                onClick={() => {
                                    setShowMsgSearch(!showMsgSearch);
                                    if (showMsgSearch) setMsgSearchQuery('');
                                }}
                                className={`chat-btn-icon ${showMsgSearch ? 'active' : ''}`}
                                title="Поиск в переписке"
                            >
                                <Search size={18} />
                            </button>
                        )}
                        <button
                            onClick={() => setShowNewChat(true)}
                            className="chat-btn-icon"
                            title="Новый чат"
                            style={{ opacity: (activeConversation || showNewChat) ? 0.5 : 1 }}
                            disabled={activeConversation || showNewChat}
                        >
                            <Plus size={18} />
                        </button>
                        <button onClick={onClose} className="chat-btn-icon" title="Закрыть">
                            <X size={18} />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="chat-content">
                    {/* User Search */}
                    {showNewChat && (
                        <>
                            <div className="user-search-container">
                                <input
                                    type="text"
                                    className="user-search-input"
                                    placeholder="Поиск..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    autoFocus
                                    onMouseDown={e => e.stopPropagation()}
                                />
                            </div>

                            <div className="user-search-results">
                                {isSearching ? (
                                    <div className="chat-loading" />
                                ) : searchResults.length > 0 ? (
                                    [...searchResults]
                                        .sort((a, b) => (b.is_online ? 1 : 0) - (a.is_online ? 1 : 0))
                                        .map(u => (
                                            <div
                                                key={u.id}
                                                className="conversation-item"
                                                onClick={() => startConversation(u.id)}
                                            >
                                                <div className="conv-avatar" style={{ position: 'relative' }}>
                                                    {(u.name?.[0] || '?').toUpperCase()}
                                                    {u.is_online && (
                                                        <span style={{
                                                            position: 'absolute',
                                                            bottom: 0,
                                                            right: 0,
                                                            width: '10px',
                                                            height: '10px',
                                                            backgroundColor: '#34C759',
                                                            borderRadius: '50%',
                                                            border: '2px solid var(--mac-bg-primary)'
                                                        }} />
                                                    )}
                                                </div>
                                                <div className="conv-info">
                                                    <div className="conv-name" style={{ color: u.is_online ? '#34C759' : 'inherit' }}>
                                                        {u.name}
                                                    </div>
                                                    <div className="conv-role">{u.role}</div>
                                                </div>
                                            </div>
                                        ))
                                ) : searchQuery.length > 0 ? (
                                    <div className="empty-state">
                                        <p>Пользователи не найдены</p>
                                    </div>
                                ) : (
                                    <div className="empty-state">
                                        <Search size={48} className="empty-state-icon" />
                                        <h4>Поиск</h4>
                                        <p>Введите имя сотрудника</p>
                                    </div>
                                )}
                            </div>
                        </>
                    )}

                    {/* Conversation List or Default Users */}
                    {!activeConversation && !showNewChat && (
                        <div className="conversations-list">
                            <div className="chat-search-bar" style={{ padding: '8px 12px', display: 'flex', gap: 8 }}>
                                <div style={{ position: 'relative', flex: 1 }}>
                                    <Search size={14} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: '#8e8e93' }} />
                                    <input
                                        value={convSearchQuery}
                                        onChange={e => setConvSearchQuery(e.target.value)}
                                        placeholder="Поиск..."
                                        style={{
                                            width: '100%',
                                            padding: '6px 8px 6px 30px',
                                            borderRadius: 6,
                                            border: '1px solid var(--mac-border)',
                                            fontSize: 13,
                                            background: 'var(--mac-background-secondary)'
                                        }}
                                    />
                                </div>
                                <button
                                    onClick={() => setConvFilter(f => f === 'unread' ? 'all' : 'unread')}
                                    style={{
                                        padding: '4px 8px',
                                        borderRadius: 6,
                                        border: '1px solid var(--mac-border)',
                                        background: convFilter === 'unread' ? 'var(--mac-accent-blue)' : 'transparent',
                                        color: convFilter === 'unread' ? 'white' : 'var(--mac-text-secondary)',
                                        cursor: 'pointer'
                                    }}
                                    title="Только непрочитанные"
                                >
                                    <Filter size={16} />
                                </button>
                            </div>

                            {isLoading ? (
                                <div className="chat-loading" />
                            ) : filteredConversations.length > 0 ? (
                                filteredConversations.map(conv => (
                                    <div
                                        key={conv.user_id}
                                        className="conversation-item"
                                        onClick={() => loadMessages(conv.user_id)}
                                    >
                                        <div className="conv-avatar">
                                            {(conv.user_name?.[0] || '?').toUpperCase()}
                                        </div>
                                        <div className="conv-info">
                                            <div className="conv-top-row">
                                                <span className="conv-name">{conv.user_name}</span>
                                                <span className="conv-time">
                                                    {formatTime(conv.last_message_time)}
                                                </span>
                                            </div>
                                            <div className="conv-top-row">
                                                <div className="conv-preview">{conv.last_message}</div>
                                                {conv.unread_count > 0 && (
                                                    <span className="unread-badge">
                                                        {conv.unread_count > 99 ? '99+' : conv.unread_count}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))
                            ) : (
                                /* Если нет бесед, показываем список всех доступных пользователей */
                                <>
                                    <div className="section-header" style={{ padding: '12px 14px', fontSize: '12px', fontWeight: '600', color: '#8e8e93', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Сотрудники
                                    </div>
                                    {allUsers.length === 0 ? (
                                        <div className="empty-state">
                                            <MessageCircle size={64} className="empty-state-icon" />
                                            <h4>Загрузка...</h4>
                                        </div>
                                    ) : (
                                        allUsers.map(u => (
                                            <div
                                                key={u.id}
                                                className="conversation-item"
                                                onClick={() => startConversation(u.id)}
                                            >
                                                <div className="conv-avatar" style={{ background: 'linear-gradient(135deg, #a8c0ff, #3f2b96)', color: 'white' }}>
                                                    {(u.name?.[0] || '?').toUpperCase()}
                                                </div>
                                                <div className="conv-info">
                                                    <div className="conv-name">{u.name}</div>
                                                    <div className="conv-role" style={{ fontSize: '12px', color: '#8e8e93' }}>
                                                        {u.role || 'Сотрудник'}
                                                    </div>
                                                </div>
                                                <div className="conv-action">
                                                    <Plus size={16} color="#007AFF" />
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </>
                            )}
                        </div>
                    )}

                    {/* Messages */}
                    {activeConversation && !showNewChat && (
                        <>
                            <div className="messages-container">
                                {showMsgSearch && (
                                    <div className="message-search-bar" style={{
                                        padding: '8px 12px',
                                        position: 'sticky',
                                        top: 0,
                                        zIndex: 10,
                                        background: 'var(--mac-background)',
                                        borderBottom: '1px solid var(--mac-border)'
                                    }}>
                                        <input
                                            value={msgSearchQuery}
                                            onChange={e => setMsgSearchQuery(e.target.value)}
                                            placeholder="Поиск по сообщениям..."
                                            autoFocus
                                            style={{
                                                width: '100%',
                                                padding: '6px 12px',
                                                borderRadius: 6,
                                                border: '1px solid var(--mac-border)',
                                                fontSize: 13
                                            }}
                                        />
                                    </div>
                                )}

                                {isLoading ? (
                                    <div className="chat-loading" />
                                ) : messages.length === 0 ? (
                                    <div className="empty-state">
                                        <div className="conv-avatar" style={{ width: 64, height: 64, fontSize: 24, marginBottom: 16 }}>
                                            {(activeUser?.user_name?.[0] || '?').toUpperCase()}
                                        </div>
                                        <h4>{activeUser?.user_name}</h4>
                                        <p>{activeUser?.role || 'Сотрудник'}</p>
                                        <p style={{ marginTop: 8, fontSize: 13, opacity: 0.6 }}>Напишите первое сообщение</p>
                                    </div>
                                ) : (
                                    <>
                                        {[...filteredMessages].reverse().map(msg => (
                                            <div
                                                key={msg.id}
                                                className={`message ${msg.sender_id === user?.id ? 'sent' : 'received'}`}
                                            >
                                                {msg.message_type === 'voice' ? (
                                                    <>
                                                        <VoiceMessage
                                                            message={msg}
                                                            fileUrl={msg.file_url}
                                                        />
                                                        <div className="message-meta">
                                                            <span className="message-time">
                                                                {(() => {
                                                                    let dateStr = msg.created_at;
                                                                    // Если нет Z и нет смещения, считаем UTC
                                                                    if (dateStr && dateStr.indexOf('Z') === -1 && dateStr.indexOf('+') === -1) {
                                                                        dateStr += 'Z';
                                                                    }
                                                                    return new Date(dateStr).toLocaleTimeString('ru', {
                                                                        hour: '2-digit',
                                                                        minute: '2-digit'
                                                                    });
                                                                })()}
                                                            </span>
                                                            {msg.sender_id === user?.id && (
                                                                <span className="message-status">
                                                                    {msg.is_read ? <CheckCheck size={14} /> : <Check size={14} />}
                                                                </span>
                                                            )}
                                                        </div>
                                                    </>
                                                ) : (
                                                    <>
                                                        <div className="message-content">{msg.content}</div>
                                                        <div className="message-meta">
                                                            <span className="message-time">
                                                                {(() => {
                                                                    let dateStr = msg.created_at;
                                                                    // Если нет Z и нет смещения, считаем UTC
                                                                    if (dateStr && dateStr.indexOf('Z') === -1 && dateStr.indexOf('+') === -1) {
                                                                        dateStr += 'Z';
                                                                    }
                                                                    return new Date(dateStr).toLocaleTimeString('ru', {
                                                                        hour: '2-digit',
                                                                        minute: '2-digit'
                                                                    });
                                                                })()}
                                                            </span>
                                                            {msg.sender_id === user?.id && (
                                                                <span className="message-status">
                                                                    {msg.is_read ? <CheckCheck size={14} /> : <Check size={14} />}
                                                                </span>
                                                            )}
                                                        </div>
                                                    </>
                                                )}
                                            </div>
                                        ))}

                                        {typingUsers[activeConversation] && (
                                            <div className="typing-container">
                                                <div className="typing-dot"></div>
                                                <div className="typing-dot"></div>
                                                <div className="typing-dot"></div>
                                            </div>
                                        )}
                                        <div ref={messagesEndRef} />
                                    </>
                                )}
                            </div>

                            <div className="message-input-container">
                                {showVoiceRecorder ? (
                                    <VoiceRecorder
                                        onSend={handleSendVoice}
                                        onCancel={() => setShowVoiceRecorder(false)}
                                    />
                                ) : (
                                    <>
                                        <textarea
                                            ref={inputRef}
                                            value={inputValue}
                                            onChange={handleInputChange}
                                            onKeyPress={handleKeyPress}
                                            placeholder="Сообщение..."
                                            rows={1}
                                            disabled={isSending}
                                            onMouseDown={e => e.stopPropagation()}
                                        />
                                        <button
                                            onClick={() => setShowVoiceRecorder(true)}
                                            className="voice-btn"
                                            title="Голосовое сообщение"
                                            disabled={isSending}
                                        >
                                            <Mic size={18} />
                                        </button>
                                        <button
                                            onClick={handleSend}
                                            disabled={!inputValue.trim() || isSending}
                                            className="send-btn"
                                            title="Отправить"
                                        >
                                            <Send size={16} />
                                        </button>
                                    </>
                                )}
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>,
        document.body
    );
};

export default ChatWindow;
