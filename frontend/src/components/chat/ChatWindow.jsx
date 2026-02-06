/**
 * Главное окно чата
 */

import React, { useState, useEffect, useRef, useLayoutEffect } from 'react';
import ReactDOM from 'react-dom';
import { X, Send, MessageCircle, ChevronLeft, ChevronDown, Plus, Search, Check, CheckCheck, Mic, Filter, Smile, Paperclip } from 'lucide-react';
import { useChat } from '../../hooks/useChat';
import auth from '../../stores/auth';
import VoiceRecorder from './VoiceRecorder';
import VoiceMessage from './VoiceMessage';
import EmojiPicker from './EmojiPicker';
import Avatar from '../common/Avatar';
import MessageContextMenu from './MessageContextMenu';
import ReactMarkdown from 'react-markdown';
import LinkPreview from './LinkPreview';
import FileUploader from './FileUploader';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useToast } from '../../components/common/Toast';
import './Chat.css';

const groupReactions = (reactions) => {
    if (!reactions) return {};
    const groups = {};
    reactions.forEach(r => {
        if (!groups[r.reaction]) groups[r.reaction] = [];
        groups[r.reaction].push(r.user_id);
    });
    return groups;
};

// === HELPER FUNCTIONS ===

// Форматирование времени сообщения
const formatMessageTime = (dateStr) => {
    if (!dateStr) return '';
    let d = dateStr;
    if (d.indexOf('Z') === -1 && d.indexOf('+') === -1) d += 'Z';
    return new Date(d).toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' });
};

// Форматирование разделителя даты
const formatDateSeparator = (dateStr) => {
    const date = new Date(dateStr);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) return 'Сегодня';
    if (date.toDateString() === yesterday.toDateString()) return 'Вчера';
    return date.toLocaleDateString('ru', { day: 'numeric', month: 'long' });
};

// Группировка сообщений по датам
const groupMessagesByDate = (msgs) => {
    if (!msgs || msgs.length === 0) return [];

    const groups = [];
    let currentDate = null;

    // Сортируем от старых к новым для правильной группировки
    const sorted = [...msgs].reverse();

    sorted.forEach(msg => {
        const msgDate = new Date(msg.created_at).toDateString();
        if (msgDate !== currentDate) {
            groups.push({ type: 'date-separator', date: msg.created_at, id: `sep-${msg.id}` });
            currentDate = msgDate;
        }
        groups.push({ type: 'message', ...msg });
    });

    return groups;
};

const ChatWindow = ({ isOpen, onClose }) => {
    const [authState, setAuthState] = useState(auth.getState());
    const user = authState.profile;
    const { addToast } = useToast();
    const {
        conversations,
        messages,
        activeConversation,
        unreadCount,
        isConnected,
        isLoading,
        typingUsers,
        setIsChatOpen,
        onlineUsers,
        requestOnlineStatus,
        loadConversations,
        loadMessages,
        loadMoreMessages,
        hasMore,
        sendMessage,
        sendTyping,
        searchUsers,
        closeConversation,
        setActiveConversation,
        toggleReaction,
        deleteMessage,
        uploadFile
    } = useChat();

    const [inputValue, setInputValue] = useState('');
    const [isSending, setIsSending] = useState(false);
    const [showNewChat, setShowNewChat] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [isSearching, setIsSearching] = useState(false);

    // Drag and Resize State
    const [position, setPosition] = useState({ x: window.innerWidth - 420, y: window.innerHeight - 640 });
    const [size, setSize] = useState({ width: 380, height: 600 });
    const [isDragging, setIsDragging] = useState(false);
    const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
    const [isResizing, setIsResizing] = useState(false);
    const [resizeStart, setResizeStart] = useState({ x: 0, y: 0, w: 0, h: 0 });

    const [showVoiceRecorder, setShowVoiceRecorder] = useState(false);
    const [reactionMenuMessageId, setReactionMenuMessageId] = useState(null);
    const [contextMenu, setContextMenu] = useState(null); // { x, y, message }

    // Search & Filter State
    const [convSearchQuery, setConvSearchQuery] = useState('');
    const [convFilter, setConvFilter] = useState('all'); // 'all' | 'unread'
    const [showMsgSearch, setShowMsgSearch] = useState(false);
    const [msgSearchQuery, setMsgSearchQuery] = useState('');

    // Список всех пользователей для отображения по дефолту
    const [allUsers, setAllUsers] = useState([]);

    const messagesEndRef = useRef(null);
    const messagesContainerRef = useRef(null);
    const prevScrollHeightRef = useRef(null);
    const inputRef = useRef(null);
    const typingTimeoutRef = useRef(null);

    // Scroll to bottom button state
    const [showScrollToBottom, setShowScrollToBottom] = useState(false);

    // Максимальная длина сообщения
    const MAX_MESSAGE_LENGTH = 4000;

    // Filtered Messages
    const filteredMessages = showMsgSearch && msgSearchQuery
        ? messages.filter(m => m.content && m.content.toLowerCase().includes(msgSearchQuery.toLowerCase()))
        : messages;

    const groupedMessages = groupMessagesByDate(filteredMessages);

    const rowVirtualizer = useVirtualizer({
        count: groupedMessages.length,
        getScrollElement: () => messagesContainerRef.current,
        estimateSize: (index) => {
            const item = groupedMessages[index];
            if (item.type === 'date-separator') return 40;
            if (item.message_type === 'image') return 220;
            if (item.message_type === 'voice') return 90;
            return 70;
        },
        overscan: 15,
        scrollToAlignment: 'end'
    });

    // Scroll to bottom effect
    useLayoutEffect(() => {
        if (groupedMessages.length > 0 && !prevScrollHeightRef.current) {
            rowVirtualizer.scrollToIndex(groupedMessages.length - 1);
        }
    }, [groupedMessages.length]);



    // Подписка на изменения auth
    useEffect(() => {
        const unsubscribe = auth.subscribe(setAuthState);
        return unsubscribe;
    }, []);

    // Sync chat open state with context for notification sound logic
    useEffect(() => {
        setIsChatOpen(isOpen);
    }, [isOpen, setIsChatOpen]);

    // Request online status for all conversation partners when chat opens
    useEffect(() => {
        if (isOpen && isConnected && conversations.length > 0) {
            const userIds = conversations.map(c => c.user_id);
            requestOnlineStatus(userIds);

            // Refresh online status every 30 seconds while chat is open
            const interval = setInterval(() => {
                requestOnlineStatus(userIds);
            }, 30000);

            return () => clearInterval(interval);
        }
    }, [isOpen, isConnected, conversations, requestOnlineStatus]);

    // Скролл-позиция теперь обрабатывается через rowVirtualizer и эффект в начале компонента


    const handleScroll = async (e) => {
        const container = e.target;

        // Показать/скрыть кнопку "scroll to bottom"
        const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
        setShowScrollToBottom(!isNearBottom);

        // Load more при скролле вверх
        if (container.scrollTop === 0 && hasMore && !isLoading) {
            prevScrollHeightRef.current = container.scrollHeight;
            await loadMoreMessages();
        }
    };

    // Прокрутка вниз
    const scrollToBottom = () => {
        rowVirtualizer.scrollToIndex(groupedMessages.length - 1, { behavior: 'smooth' });
    };

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
            addToast({ type: 'error', message: 'Ошибка отправки сообщения' });
        } finally {
            setIsSending(false);
        }
    };

    // Отправка голосового сообщения
    const handleSendVoice = async (audioBlob, duration) => {
        // console.log('📤 handleSendVoice called. activeConversation:', activeConversation);


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
            // console.log('✅ Voice message sent successfully, response:', messageData);


            // Обновляем только список бесед - сообщение придет через WebSocket
            loadConversations();
        } catch (error) {
            console.error('Voice send error:', error);
            addToast({ type: 'error', message: 'Ошибка отправки голосового сообщения: ' + error.message });
        } finally {
            setIsSending(false);
        }
    };

    // Обработка ввода
    const handleInputChange = (e) => {
        const value = e.target.value;

        // Ограничение длины
        if (value.length > MAX_MESSAGE_LENGTH) return;

        setInputValue(value);

        // Auto-resize textarea
        const textarea = e.target;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
        if (activeConversation) {
            sendTyping(activeConversation, true);
            clearTimeout(typingTimeoutRef.current);
            typingTimeoutRef.current = setTimeout(() => {
                sendTyping(activeConversation, false);
            }, 2000);
        }
    };

    const handleMessageContextMenu = (e, message) => {
        e.preventDefault();
        setContextMenu({
            x: e.clientX,
            y: e.clientY,
            message: message
        });
    };

    const handleMenuAction = async (action, msg) => {
        if (action === 'copy') {
            try {
                await navigator.clipboard.writeText(msg.content);
                addToast({ type: 'success', message: 'Текст скопирован' });
            } catch (err) {
                console.error('Failed to copy text:', err);
            }
        } else if (action === 'delete') {
            if (window.confirm('Удалить это сообщение у себя?')) {
                try {
                    await deleteMessage(msg.id);
                    addToast({ type: 'success', message: 'Сообщение удалено' });
                } catch (e) {
                    addToast({ type: 'error', message: 'Не удалось удалить сообщение' });
                }
            }
        } else if (action === 'reply') {
            setInputValue(`@${msg.sender_name || 'Сотрудник'}, `);
            inputRef.current?.focus();
        } else if (action === 'forward') {
            addToast({ type: 'info', message: 'Функция пересылки в разработке' });
        }
    };

    const handleFileUpload = async (file) => {
        if (!activeConversation) return;
        setIsSending(true);
        try {
            await uploadFile(activeConversation, file);
            addToast({ type: 'success', message: 'Файл отправлен' });
        } catch (e) {
            addToast({ type: 'error', message: 'Ошибка при загрузке файла' });
        } finally {
            setIsSending(false);
        }
    };

    useEffect(() => {
        const handleCloseMenu = () => setContextMenu(null);
        window.addEventListener('click', handleCloseMenu);
        return () => window.removeEventListener('click', handleCloseMenu);
    }, []);

    // Drag Logic
    const handleMouseDown = (e) => {
        if (e.target.closest('.chat-header') && !e.target.closest('button')) {
            setIsDragging(true);
            setDragOffset({
                x: e.clientX - position.x,
                y: e.clientY - position.y
            });
        }
    };

    // Resize Logic
    const handleResizeStart = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsResizing(true);
        setResizeStart({
            x: e.clientX,
            y: e.clientY,
            w: size.width,
            h: size.height
        });
    };

    useEffect(() => {
        const handleMouseMove = (e) => {
            if (isDragging) {
                setPosition({
                    x: e.clientX - dragOffset.x,
                    y: e.clientY - dragOffset.y
                });
            }
            if (isResizing) {
                const dw = e.clientX - resizeStart.x;
                const dh = e.clientY - resizeStart.y;
                setSize({
                    width: Math.max(300, resizeStart.w + dw),
                    height: Math.max(400, resizeStart.h + dh)
                });
            }
        };

        const handleMouseUp = () => {
            setIsDragging(false);
            setIsResizing(false);
        };

        if (isDragging || isResizing) {
            window.addEventListener('mousemove', handleMouseMove);
            window.addEventListener('mouseup', handleMouseUp);
        }

        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [isDragging, isResizing, dragOffset, resizeStart]);

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



    if (!isOpen) return null;

    const activeUser = getActiveUser();

    // Используем Portal для рендеринга вне иерархии (z-index проблема)
    return ReactDOM.createPortal(
        <div className="chat-window-overlay" style={{ pointerEvents: 'none', background: 'transparent' }}>
            <div
                className={`chat-window ${isDragging ? 'dragging' : ''} ${isResizing ? 'resizing' : ''}`}
                onMouseDown={handleMouseDown}
                style={{
                    position: 'absolute',
                    left: Math.max(0, Math.min(window.innerWidth - size.width, position.x)),
                    top: Math.max(0, Math.min(window.innerHeight - size.height, position.y)),
                    width: size.width,
                    height: size.height,
                    transform: 'none',
                    margin: 0,
                    pointerEvents: 'auto',
                    cursor: isDragging ? 'grabbing' : 'default',
                    userSelect: (isDragging || isResizing) ? 'none' : 'auto'
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
                                    ? (
                                        <span className="chat-header-name">
                                            {activeUser.user_name}
                                            {onlineUsers[activeConversation] && (
                                                <span className="user-online-dot" title="В сети" />
                                            )}
                                        </span>
                                    )
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
                                        <div className="conv-avatar-wrapper">
                                            <div className="conv-avatar">
                                                {(conv.user_name?.[0] || '?').toUpperCase()}
                                            </div>
                                            {onlineUsers[conv.user_id] && (
                                                <span className="avatar-online-indicator" />
                                            )}
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
                            <div
                                className="messages-container"
                                ref={messagesContainerRef}
                                onScroll={handleScroll}
                            >
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
                                    /* Skeleton Loading */
                                    <div className="chat-skeleton">
                                        {[1, 2, 3, 4, 5].map(i => (
                                            <div key={i} className={`skeleton-message ${i % 2 ? 'sent' : 'received'}`}>
                                                <div className="skeleton-bubble" />
                                            </div>
                                        ))}
                                    </div>
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
                                    <div
                                        style={{
                                            height: `${rowVirtualizer.getTotalSize()}px`,
                                            width: '100%',
                                            position: 'relative',
                                        }}
                                    >
                                        {rowVirtualizer.getVirtualItems().map((virtualItem) => {
                                            const item = groupedMessages[virtualItem.index];
                                            return (
                                                <div
                                                    key={virtualItem.key}
                                                    data-index={virtualItem.index}
                                                    ref={rowVirtualizer.measureElement}
                                                    style={{
                                                        position: 'absolute',
                                                        top: 0,
                                                        left: 0,
                                                        width: '100%',
                                                        transform: `translateY(${virtualItem.start}px)`,
                                                        padding: '0 12px'
                                                    }}
                                                >
                                                    {item.type === 'date-separator' ? (
                                                        <div className="date-separator">
                                                            <span>{formatDateSeparator(item.date)}</span>
                                                        </div>
                                                    ) : (
                                                        <div className={`message-row ${item.sender_id === user?.id ? 'sent' : 'received'}`}>
                                                            {item.sender_id !== user?.id && activeUser && (
                                                                <Avatar
                                                                    user={{
                                                                        name: activeUser.user_name,
                                                                        role: activeUser.user_role
                                                                    }}
                                                                    size={28}
                                                                    className="message-avatar"
                                                                />
                                                            )}
                                                            <div
                                                                className={`message ${item.sender_id === user?.id ? 'sent' : 'received'}`}
                                                                onContextMenu={(e) => handleMessageContextMenu(e, item)}
                                                            >
                                                                {item.message_type === 'voice' ? (
                                                                    <>
                                                                        <VoiceMessage
                                                                            message={item}
                                                                            fileUrl={item.file_url}
                                                                        />
                                                                        <div className="message-meta">
                                                                            <span className="message-time">{formatMessageTime(item.created_at)}</span>
                                                                            {item.sender_id === user?.id && (
                                                                                <span className="message-status">
                                                                                    {item.is_read ? <CheckCheck size={14} /> : <Check size={14} />}
                                                                                </span>
                                                                            )}
                                                                        </div>
                                                                    </>
                                                                ) : (
                                                                    <>
                                                                        <div className="message-content">
                                                                            {item.message_type === 'image' ? (
                                                                                <div className="message-image">
                                                                                    <img
                                                                                        src={item.content}
                                                                                        alt="Attached"
                                                                                        onClick={() => window.open(item.content, '_blank')}
                                                                                        style={{ cursor: 'pointer', maxWidth: '100%', borderRadius: 8 }}
                                                                                    />
                                                                                </div>
                                                                            ) : item.message_type === 'file' ? (
                                                                                <div className="message-file">
                                                                                    <a href={item.content} target="_blank" rel="noopener noreferrer" className="file-link">
                                                                                        <Paperclip size={16} />
                                                                                        <span>{item.content.split('name=')[1] || 'Файл'}</span>
                                                                                    </a>
                                                                                </div>
                                                                            ) : (
                                                                                <ReactMarkdown
                                                                                    components={{
                                                                                        a: ({ node, ...props }) => (
                                                                                            <a {...props} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} />
                                                                                        )
                                                                                    }}
                                                                                >
                                                                                    {item.content}
                                                                                </ReactMarkdown>
                                                                            )}

                                                                            {item.message_type === 'text' && item.content && item.content.match(/https?:\/\/[^\s]+/) && (
                                                                                <LinkPreview url={item.content.match(/https?:\/\/[^\s]+/)[0]} />
                                                                            )}
                                                                        </div>
                                                                        <div className="message-meta">
                                                                            <span className="message-time">{formatMessageTime(item.created_at)}</span>
                                                                            {item.sender_id === user?.id && (
                                                                                <span className="message-status">
                                                                                    {item.is_read ? <CheckCheck size={14} /> : <Check size={14} />}
                                                                                </span>
                                                                            )}
                                                                        </div>
                                                                    </>
                                                                )}

                                                                {item.reactions && item.reactions.length > 0 && (
                                                                    <div className="message-reactions">
                                                                        {Object.entries(groupReactions(item.reactions)).map(([emoji, userIds]) => (
                                                                            <span
                                                                                key={emoji}
                                                                                className={`reaction-bubble ${userIds.includes(user?.id) ? 'active' : ''}`}
                                                                                onClick={(e) => { e.stopPropagation(); toggleReaction(item.id, emoji); }}
                                                                            >
                                                                                {emoji} {userIds.length > 1 && userIds.length}
                                                                            </span>
                                                                        ))}
                                                                    </div>
                                                                )}

                                                                <button
                                                                    className="add-reaction-btn"
                                                                    onClick={(e) => {
                                                                        e.stopPropagation();
                                                                        setReactionMenuMessageId(reactionMenuMessageId === item.id ? null : item.id);
                                                                    }}
                                                                >
                                                                    <Smile size={14} />
                                                                </button>

                                                                {reactionMenuMessageId === item.id && (
                                                                    <div className="reaction-menu">
                                                                        {['👍', '❤️', '😂', '😮', '😢', '🔥'].map(emoji => (
                                                                            <button
                                                                                key={emoji}
                                                                                onClick={(e) => {
                                                                                    e.stopPropagation();
                                                                                    toggleReaction(item.id, emoji);
                                                                                    setReactionMenuMessageId(null);
                                                                                }}
                                                                            >
                                                                                {emoji}
                                                                            </button>
                                                                        ))}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}

                                        {/* Typing Indicator inside scroll area */}
                                        {typingUsers[activeConversation] && (
                                            <div
                                                className="typing-indicator-modern"
                                                style={{
                                                    position: 'absolute',
                                                    bottom: -40,
                                                    left: 12,
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: 8
                                                }}
                                            >
                                                <Avatar
                                                    user={{
                                                        name: activeUser?.user_name,
                                                        role: activeUser?.user_role
                                                    }}
                                                    size={24}
                                                />
                                                <div className="typing-bubble">
                                                    <div className="typing-dots">
                                                        <span></span><span></span><span></span>
                                                    </div>
                                                </div>
                                            </div>
                                        )}
                                        <div ref={messagesEndRef} style={{ height: 1 }} />
                                    </div>
                                )}

                                {/* Scroll to Bottom Button */}
                                {showScrollToBottom && (
                                    <button
                                        className="scroll-to-bottom-btn"
                                        onClick={scrollToBottom}
                                        title="К последним сообщениям"
                                    >
                                        <ChevronDown size={20} />
                                    </button>
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
                                        <div className="input-wrapper">
                                            <textarea
                                                ref={inputRef}
                                                value={inputValue}
                                                onChange={handleInputChange}
                                                onKeyPress={handleKeyPress}
                                                placeholder="Сообщение... (Shift+Enter для новой строки)"
                                                rows={1}
                                                disabled={isSending}
                                                onMouseDown={e => e.stopPropagation()}
                                                aria-label="Введите сообщение"
                                            />
                                            {inputValue.length > 100 && (
                                                <span className={`char-counter ${inputValue.length > MAX_MESSAGE_LENGTH * 0.9 ? 'warning' : ''}`}>
                                                    {inputValue.length}/{MAX_MESSAGE_LENGTH}
                                                </span>
                                            )}
                                        </div>
                                        <FileUploader
                                            onUpload={handleFileUpload}
                                            disabled={isSending}
                                        />
                                        <EmojiPicker
                                            onEmojiSelect={(emoji) => {
                                                setInputValue(prev => prev + emoji);
                                                inputRef.current?.focus();
                                            }}
                                            disabled={isSending}
                                        />
                                        <button
                                            onClick={() => setShowVoiceRecorder(true)}
                                            className="voice-btn"
                                            title="Голосовое сообщение"
                                            aria-label="Записать голосовое сообщение"
                                            disabled={isSending}
                                        >
                                            <Mic size={18} />
                                        </button>
                                        <button
                                            onClick={handleSend}
                                            disabled={!inputValue.trim() || isSending}
                                            className="send-btn"
                                            title="Отправить"
                                            aria-label="Отправить сообщение"
                                        >
                                            <Send size={16} />
                                        </button>
                                    </>
                                )}
                            </div>
                        </>
                    )}
                </div>
                {contextMenu && (
                    <MessageContextMenu
                        x={contextMenu.x}
                        y={contextMenu.y}
                        message={contextMenu.message}
                        isOwn={contextMenu.message.sender_id === user?.id}
                        onBlur={() => setContextMenu(null)}
                        onAction={handleMenuAction}
                    />
                )}

                {/* Resize handle */}
                <div className="chat-resize-handle" onMouseDown={handleResizeStart} />
            </div>
        </div>,
        document.body
    );
};

export default ChatWindow;
