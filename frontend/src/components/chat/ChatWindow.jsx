/**
 * Главное окно чата
 */

import { api } from '../../api/client';
import { useState, useEffect, useRef, useLayoutEffect } from 'react';
import ReactDOM from 'react-dom';
import PropTypes from 'prop-types';
import { X, Send, MessageCircle, ChevronLeft, ChevronDown, Plus, Search, Check, CheckCheck, Mic, Filter, Smile, Paperclip, Zap, AlertCircle, VolumeX, Volume2 } from 'lucide-react';
import { useChat } from '../../hooks/useChat';
import auth from '../../stores/auth';
import VoiceRecorder from './VoiceRecorder';
import VoiceMessage from './VoiceMessage';
import EmojiPicker from './EmojiPicker';
import Avatar from '../common/Avatar';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() call.
import { useConfirm } from '../common/ConfirmDialog';
import MessageContextMenu from './MessageContextMenu';
import ReactMarkdown from 'react-markdown';
import LinkPreview from './LinkPreview';
import FileUploader from './FileUploader';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useToast } from '../../components/common/Toast';
import logger from '../../utils/logger';
import './Chat.css';
import { Input } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

const groupReactions = (reactions) => {
  if (!reactions) return {};
  const groups = {};
  reactions.forEach((r) => {
    if (!groups[r.reaction]) groups[r.reaction] = [];
    groups[r.reaction].push(r.user_id);
  });
  return groups;
};

const COMPACT_CHAT_BREAKPOINT = 768;

// === HELPER FUNCTIONS ===

// Форматирование времени сообщения
const formatMessageTime = (dateStr) => {
  if (!dateStr) return '';
  let d = dateStr;
  if (d.indexOf('Z') === -1 && d.indexOf('+') === -1) d += 'Z';
  return new Date(d).toLocaleTimeString('ru', { hour: '2-digit', minute: '2-digit' });
};

// Форматирование разделителя даты
const formatDateSeparator = (dateStr, t) => {
  const date = new Date(dateStr);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date.toDateString() === today.toDateString()) return t('misc.cw_today');
  if (date.toDateString() === yesterday.toDateString()) return t('misc.cw_yesterday');
  return date.toLocaleDateString('ru', { day: 'numeric', month: 'long' });
};

// Группировка сообщений по датам
const groupMessagesByDate = (msgs) => {
  if (!msgs || msgs.length === 0) return [];

  const groups = [];
  let currentDate = null;

  // Сортируем от старых к новым для правильной группировки
  const sorted = [...msgs].reverse();

  sorted.forEach((msg) => {
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
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirm, confirmDialog] = useConfirm();
  const [authState, setAuthState] = useState(auth.getState());
  const user = authState.profile;
  const { addToast } = useToast();
  const { t } = useTranslation();  // PR-72
  const {
    conversations,
    messages,
    activeConversation,

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
    // PR-71: muted conversations from context
    mutedConversations,
    setMutedConversations,

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
  const [viewport, setViewport] = useState(() => ({
    width: window.innerWidth,
    height: window.innerHeight,
  }));

  const [showVoiceRecorder, setShowVoiceRecorder] = useState(false);
  const [reactionMenuMessageId, setReactionMenuMessageId] = useState(null);
  const [contextMenu, setContextMenu] = useState(null); // { x, y, message }
  // PR-69 / H-3: reply state for quote block
  const [replyTo, setReplyTo] = useState(null); // { id, content, sender_name }

  // Search & Filter State
  const [convSearchQuery, setConvSearchQuery] = useState('');
  const [convFilter, setConvFilter] = useState('all'); // 'all' | 'unread'
  const [showMsgSearch, setShowMsgSearch] = useState(false);
  const [msgSearchQuery, setMsgSearchQuery] = useState('');
  // PR-71: new features — draft persistence, urgent flag
  const [drafts, setDrafts] = useState({}); // { [conversationId]: text }
  // mutedConversations comes from ChatContext now (for sound suppression)
  const [isUrgent, setIsUrgent] = useState(false);
  const [showQuickReplies, setShowQuickReplies] = useState(false);

  // PR-71: quick-reply templates for clinic workflow
  const quickReplies = [
    t('misc.cw_qr_patient_ready'),
    t('misc.cw_qr_come_to_reception'),
    t('misc.cw_qr_come_to_office_3'),
    t('misc.cw_qr_call_next_patient'),
    t('misc.cw_qr_lunch_break'),
    t('misc.cw_qr_phone_call_mz'),
  ];

  // Список всех пользователей для отображения по дефолту
  const [allUsers, setAllUsers] = useState([]);

  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const prevScrollHeightRef = useRef(null);
  const inputRef = useRef(null);
  const typingTimeoutRef = useRef(null);
  const typingThrottleRef = useRef(null); // PR-70 / M-8: throttle typing events

  // Scroll to bottom button state
  const [showScrollToBottom, setShowScrollToBottom] = useState(false);

  // Максимальная длина сообщения
  const MAX_MESSAGE_LENGTH = 4000;

  // Filtered Messages
  const filteredMessages = showMsgSearch && msgSearchQuery ?
  messages.filter((m) => m.content && m.content.toLowerCase().includes(msgSearchQuery.toLowerCase())) :
  messages;

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
  }, [groupedMessages.length, rowVirtualizer]);



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
      const userIds = conversations.map((c) => c.user_id);
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
      // PR-68 / P0-5: preserve scroll position after loading older messages
      // (was: prevScrollHeightRef set but never read — view jumped to top)
      if (prevScrollHeightRef.current) {
        requestAnimationFrame(() => {
          const newScrollHeight = container.scrollHeight;
          container.scrollTop = newScrollHeight - prevScrollHeightRef.current;
          prevScrollHeightRef.current = null;
        });
      }
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
      searchUsers('').then((users) => {
        if (users && Array.isArray(users)) {
          setAllUsers(users);
        }
      }).catch((e) => logger.error('Failed to load users:', e));
    }
  }, [isOpen, conversations.length, searchUsers]);

  // Поиск пользователей
  useEffect(() => {
    if (!showNewChat) return;

    const search = async () => {
      const normalizedQuery = searchQuery.trim().toLowerCase();
      if (normalizedQuery.length < 1) {
        setSearchResults([]);
        return;
      }

      setIsSearching(true);
      try {
        const results = await searchUsers(searchQuery);
        const serverResults = Array.isArray(results) ? results : [];

        // Keep backend search behavior and augment with local full_name fallback.
        const existingIds = new Set(serverResults.map((userItem) => userItem.id));
        const fullNameFallback = allUsers.filter((userItem) => {
          if (existingIds.has(userItem.id)) return false;
          const displayName = String(userItem.name || '').toLowerCase();
          return displayName.includes(normalizedQuery);
        });

        setSearchResults([...serverResults, ...fullNameFallback]);
      } catch (e) {
        logger.error('Search error:', e);
      } finally {
        setIsSearching(false);
      }
    };

    const timeout = setTimeout(search, 300);
    return () => clearTimeout(timeout);
  }, [searchQuery, showNewChat, searchUsers, allUsers]);

  // Отправка сообщения
  const handleSend = async () => {
    if (!inputValue.trim() || !activeConversation || isSending) return;

    const content = inputValue.trim();
    setInputValue('');
    // PR-71: clear draft on send
    setDrafts((prev) => { const next = { ...prev }; delete next[activeConversation]; return next; });
    setIsSending(true);
    const wasUrgent = isUrgent;
    setIsUrgent(false);

    try {
      // PR-71: prepend urgent marker if flagged
      const messageContent = wasUrgent ? `${t('chatUrgentPrefix')}${content}` : content;
      await sendMessage(activeConversation, messageContent);
      sendTyping(activeConversation, false);
    } catch {
      setInputValue(content);
      if (wasUrgent) setIsUrgent(true);
      addToast({ type: 'error', message: t('chatSendError') });
    } finally {
      setIsSending(false);
    }
  };

  // Отправка голосового сообщения
  // PR-70 / L-10: accept duration argument (was dropped by parent)
  const handleSendVoice = async (audioBlob, duration) => {


    if (!activeConversation || isSending) {
      logger.warn('Cannot send voice', { activeConversation, isSending });
      return;
    }

    setIsSending(true);
    setShowVoiceRecorder(false);

    try {
      const formData = new FormData();
      formData.append('audio_file', audioBlob, 'voice.webm');
      formData.append('recipient_id', activeConversation);
      // PR-70 / L-10: send voice_duration (was silently dropped)
      if (duration) {
        formData.append('voice_duration', String(duration));
      }

      // PR-68 / P0-3: replaced raw fetch with axios client
      // (was: fetch('/messages/send-voice') — no /api/v1 prefix, no CSRF, no token refresh)
      const response = await api.post('/messages/send-voice', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      // PR-68: axios response already has .data, no need for .json()
      // Обновляем только список бесед - сообщение придет через WebSocket
      loadConversations();
    } catch (error) {
      logger.error('Voice send error:', error);
      addToast({ type: 'error', message: t('misc.cw_voice_send_error', { error: error.message }) });
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
      // PR-70 / M-8: throttle sendTyping to max once per 500ms (was every keystroke)
      if (!typingThrottleRef.current) {
        sendTyping(activeConversation, true);
        typingThrottleRef.current = setTimeout(() => {
          typingThrottleRef.current = null;
        }, 500);
      }
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
        addToast({ type: 'success', message: t('chatCopied') });
      } catch (err) {
        logger.error('Failed to copy text:', err);
      }
    } else if (action === 'delete') {
      // P-013 fix: replaced window.confirm() with shared useConfirm hook.
      const ok = await confirm({
        title: t('chatDeleteTitle'),
        message: t('chatDeleteConfirm'),
        description: t('misc.cw_delete_desc'),
        confirmLabel: t('chatDelete'),
        cancelLabel: t('chatCancel'),
        intent: 'danger',
      });
      if (ok) {
        try {
          await deleteMessage(msg.id);
          addToast({ type: 'success', message: t('chatDeleted') });
        } catch {
          addToast({ type: 'error', message: t('chatDeleteError') });
        }
      }
    } else if (action === 'reply') {
      // PR-69 / H-3: real reply — set replyTo state for quote block display
      setReplyTo({ id: msg.id, content: msg.content, sender_name: msg.sender_name });
      setInputValue('');
      inputRef.current?.focus();
    }
    // PR-69 / H-4: removed 'forward' stub (was showing 'в разработке' toast)
  };

  const handleFileUpload = async (file) => {
    if (!activeConversation) return;
    setIsSending(true);
    try {
      await uploadFile(activeConversation, file);
      addToast({ type: 'success', message: t('chatFileSent') });
    } catch {
      addToast({ type: 'error', message: t('chatFileError') });
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
    if (isCompactViewport) return;
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
    if (isCompactViewport) return;
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
  const handleActivationKeyDown = (event, onActivate) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      event.stopPropagation();
      onActivate();
    }
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
      // PR-71: save draft before closing conversation
      if (activeConversation && inputValue) {
        setDrafts((prev) => ({ ...prev, [activeConversation]: inputValue }));
      }
      closeConversation();
      setInputValue('');
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
      return t('chatYesterday');
    }
    return date.toLocaleDateString('ru', { day: 'numeric', month: 'short' });
  };

  const getActiveUser = () => {
    return conversations.find((c) => c.user_id === activeConversation);
  };

  // Filtered Conversations
  const filteredConversations = conversations.filter((c) => {
    const matchesSearch = !convSearchQuery ||
    c.user_name && c.user_name.toLowerCase().includes(convSearchQuery.toLowerCase()) ||
    c.last_message && c.last_message.toLowerCase().includes(convSearchQuery.toLowerCase());

    const matchesFilter = convFilter === 'all' ||
    convFilter === 'unread' && c.unread_count > 0;

    return matchesSearch && matchesFilter;
  });

  const isCompactViewport = viewport.width <= COMPACT_CHAT_BREAKPOINT;

  // PR-71: restore draft when switching to a conversation
  useEffect(() => {
    if (activeConversation && drafts[activeConversation]) {
      setInputValue(drafts[activeConversation]);
    } else if (activeConversation) {
      setInputValue('');
    }
    setIsUrgent(false); // reset urgent flag on conversation switch
  }, [activeConversation]);

  useEffect(() => {
    const updateViewport = () => {
      setViewport((prev) => {
        const next = {
          width: window.innerWidth,
          height: window.innerHeight,
        };

        if (prev.width === next.width && prev.height === next.height) {
          return prev;
        }

        return next;
      });
    };

    updateViewport();
    window.addEventListener('resize', updateViewport);

    return () => {
      window.removeEventListener('resize', updateViewport);
    };
  }, []);

  useEffect(() => {
    if (!isCompactViewport) return;
    setIsDragging(false);
    setIsResizing(false);
    setReactionMenuMessageId(null);
    setContextMenu(null);
  }, [isCompactViewport]);

  const chatWindowStyle = isCompactViewport ? {
    position: 'fixed',
    inset: 0,
    width: '100vw',
    height: '100dvh',
    maxWidth: '100vw',
    maxHeight: '100dvh',
    transform: 'none',
    margin: 0,
    pointerEvents: 'auto',
    cursor: 'default',
    userSelect: 'auto',
    borderRadius: 0,
    boxShadow: 'none'
  } : {
    position: 'absolute',
    left: Math.max(0, Math.min(window.innerWidth - size.width, position.x)),
    top: Math.max(0, Math.min(window.innerHeight - size.height, position.y)),
    width: size.width,
    height: size.height,
    transform: 'none',
    margin: 0,
    pointerEvents: 'auto',
    cursor: isDragging ? 'grabbing' : 'default',
    userSelect: isDragging || isResizing ? 'none' : 'auto'
  };



  if (!isOpen) return null;

  const activeUser = getActiveUser();

  // Используем Portal для рендеринга вне иерархии (z-index проблема)
  // P-013 fix: wrapped in a fragment so we can also render the confirmDialog
  // portal alongside the chat portal (both mount to document.body via their
  // own createPortal calls).
  const chatWindowElement = ReactDOM.createPortal(
    <div className="chat-window-overlay" style={{ pointerEvents: 'none', background: 'transparent' }}>
            <div
        // PR-69 / H-8: added role="dialog" + aria-modal + Esc-to-close
        role="dialog"
        aria-modal="true"
        aria-label={t('chatTitle')}
        className={`chat-window ${isDragging ? 'dragging' : ''} ${isResizing ? 'resizing' : ''} ${isCompactViewport ? 'compact' : ''}`}
        onPointerDown={isCompactViewport ? undefined : handleMouseDown}
        onKeyDown={(e) => { if (e.key === 'Escape' && isOpen) { onClose(); } }}
        style={chatWindowStyle}>
        
                {/* Header */}
                <div className="chat-header">
                    <div className="chat-title-group">
                        <div className={`chat-status-indicator ${isConnected ? 'online' : 'connecting'}`}
            title={isConnected ? t('chatOnline') : t('chatConnecting')} />

                        {(activeConversation || showNewChat) &&
            <button onClick={handleBack} className="chat-btn-icon" title={t('chatBack')} aria-label={t('chatBack')}>
                                <ChevronLeft size={20} />
                            </button>
            }

                        <h3>
                            {showNewChat ?
              t('misc.cw_new_message') :
              activeUser ?

              <span className="chat-header-name">
                                            {activeUser.user_name}
                                            {onlineUsers[activeConversation] &&
                <span className="user-online-dot" title={t('misc.cw_online_title')} />
                }
                                        </span> :

              t('misc.cw_chats')
              }
                        </h3>
                    </div>

                    <div className="chat-actions" style={{ display: 'flex', gap: 'var(--mac-spacing-1)' }}>
                        {activeConversation && !showNewChat &&
            <button
              onClick={() => {
                setShowMsgSearch(!showMsgSearch);
                if (showMsgSearch) setMsgSearchQuery('');
              }}
              className={`chat-btn-icon ${showMsgSearch ? 'active' : ''}`}
              title={t('chatSearch')}
              aria-label={showMsgSearch ? t('chatSearch') : t('chatSearch')}>

                                <Search size={18} />
                            </button>
            }
            {/* PR-71: Mute conversation toggle */}
            {activeConversation && (
              <button
                onClick={() => {
                  setMutedConversations((prev) => {
                    const next = new Set(prev);
                    if (next.has(activeConversation)) next.delete(activeConversation);
                    else next.add(activeConversation);
                    return next;
                  });
                }}
                className="chat-btn-icon"
                title={mutedConversations.has(activeConversation) ? t('chatUnmute') : t('chatMute')}
                aria-label={mutedConversations.has(activeConversation) ? t('chatUnmute') : t('chatMute')}
                style={{ color: mutedConversations.has(activeConversation) ? 'var(--mac-text-tertiary)' : 'var(--mac-text-secondary)' }}>
                {mutedConversations.has(activeConversation) ? <VolumeX size={16} /> : <Volume2 size={16} />}
              </button>
            )}
                        <button
              onClick={() => setShowNewChat(true)}
              className="chat-btn-icon"
              title={t('chatNewChat')}
              aria-label={t('chatNewChat')}
              style={{ opacity: activeConversation || showNewChat ? 0.5 : 1 }}
              disabled={activeConversation || showNewChat}>
              
                            <Plus size={18} />
                        </button>
                        <button onClick={onClose} className="chat-btn-icon" title={t('chatClose')} aria-label={t('chatClose')}>
                            <X size={18} />
                        </button>
                    </div>
                </div>

                {/* Content */}
                <div className="chat-content">
                    {/* User Search */}
                    {showNewChat &&
          <>
                            <div className="user-search-container">
                                <Input
                type="text"
                className="user-search-input"
                placeholder={t('common.search')}
                aria-label={t('misc.cw_search_user_aria')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                autoFocus
                onMouseDown={(e) => e.stopPropagation()} />
              
                            </div>

                            <div className="user-search-results">
                                {isSearching ?
              <div className="chat-loading" /> :
              searchResults.length > 0 ?
              [...searchResults].
              sort((a, b) => (b.is_online ? 1 : 0) - (a.is_online ? 1 : 0)).
              map((u) =>
              <div
                key={u.id}
                className="conversation-item"
                role="button"
                tabIndex={0}
                onKeyDown={(event) => handleActivationKeyDown(event, () => startConversation(u.id))}
                onClick={() => startConversation(u.id)}>
                
                                                <div className="conv-avatar" style={{ position: 'relative' }}>
                                                    {(u.name?.[0] || '?').toUpperCase()}
                                                    {u.is_online &&
                  <span style={{
                    position: 'absolute',
                    bottom: 0,
                    right: 0,
                    width: '10px',
                    height: '10px',
                    backgroundColor: 'var(--mac-success)',
                    borderRadius: '50%',
                    border: '2px solid var(--mac-bg-primary)'
                  }} />
                  }
                                                </div>
                                                <div className="conv-info">
                                                    <div className="conv-name" style={{ color: u.is_online ? 'var(--mac-success)' : 'inherit' }}>
                                                        {u.name}
                                                    </div>
                                                    <div className="conv-role">{u.role}</div>
                                                </div>
                                            </div>
              ) :
              searchQuery.length > 0 ?
              <div className="empty-state">
                                        <p>{t('misc.cw_no_users_found')}</p>
                                    </div> :

              <div className="empty-state">
                                        <Search size={48} className="empty-state-icon" />
                                        <h4>{t('common.search')}</h4>
                                        <p>{t('misc.cw_enter_employee_name')}</p>
                                    </div>
              }
                            </div>
                        </>
          }

                    {/* Conversation List or Default Users */}
                    {!activeConversation && !showNewChat &&
          <div className="conversations-list">
                            <div className="chat-search-bar" style={{ padding: 'var(--mac-spacing-2) var(--mac-spacing-3)', display: 'flex', gap: 8 }}>
                                <div style={{ position: 'relative', flex: 1 }}>
                                    <Search size={14} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--mac-text-tertiary)' }} />
                                    <Input
                  value={convSearchQuery}
                  onChange={(e) => setConvSearchQuery(e.target.value)}
                  placeholder={t('common.search')}
                  aria-label={t('misc.cw_search_chats_aria')}
                  style={{
                    width: '100%',
                    padding: '6px 8px 6px 30px',
                    borderRadius: 6,
                    border: '1px solid var(--mac-border)',
                    fontSize: 13,
                    background: 'var(--mac-bg-secondary)'
                  }} />
                
                                </div>
                                <button
                onClick={() => setConvFilter((f) => f === 'unread' ? 'all' : 'unread')}
                style={{
                  padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
                  borderRadius: 6,
                  border: '1px solid var(--mac-border)',
                  background: convFilter === 'unread' ? 'var(--mac-accent-blue)' : 'transparent',
                  color: convFilter === 'unread' ? 'white' : 'var(--mac-text-secondary)',
                  cursor: 'pointer'
                }}
                title={t('misc.cw_unread_only_title')}
                aria-label={convFilter === 'unread' ? t('misc.cw_show_all_chats_aria') : t('misc.cw_show_unread_chats_aria')}>
                
                                    <Filter size={16} />
                                </button>
                            </div>

                            {isLoading ?
            <div className="chat-loading" /> :
            filteredConversations.length > 0 ?
            filteredConversations.map((conv) =>
              <div
                key={conv.user_id}
                className="conversation-item"
                data-user-id={conv.user_id}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => handleActivationKeyDown(event, () => loadMessages(conv.user_id))}
                onClick={() => loadMessages(conv.user_id)}>
              
                                        <div className="conv-avatar-wrapper">
                                            <div className="conv-avatar">
                                                {(conv.user_name?.[0] || '?').toUpperCase()}
                                            </div>
                                            {onlineUsers[conv.user_id] &&
                <span className="avatar-online-indicator" />
                }
                                        </div>
                                        <div className="conv-info">
                                            <div className="conv-top-row">
                                                <span className="conv-name">{conv.user_name}</span>
                                                <span className="conv-time">
                                                    {formatTime(conv.last_message_time)}
                                                </span>
                                            </div>
                                            <div className="conv-top-row">
                                                {/* PR-69 / H-2: conversation preview with message-type indicators */}
                                                <div className="conv-preview">
                                                  {conv.last_message?.startsWith('data:image/') || conv.last_message?.match(/\.(jpg|jpeg|png|gif|webp)/i) ? t('chatPhoto')
                                                  : conv.last_message?.startsWith('data:audio/') || conv.last_message?.includes('voice') ? t('chatVoice')
                                                  : conv.last_message?.startsWith('/api/') || conv.last_message?.includes('file') ? t('chatFile')
                                                  : conv.last_message || ''}
                                                </div>
                                                {conv.unread_count > 0 &&
                  <span className="unread-badge">
                                                        {conv.unread_count > 99 ? '99+' : conv.unread_count}
                                                    </span>
                  }
                                            </div>
                                        </div>
                                    </div>
            ) : (

            /* Если нет бесед, показываем список всех доступных пользователей */
            <>
                                    <div className="section-header" style={{ padding: '12px 14px', fontSize: 'var(--mac-font-size-xs)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        {t('misc.cw_employees')}
                                    </div>
                                    {allUsers.length === 0 ?
              <div className="empty-state">
                                            <MessageCircle size={64} className="empty-state-icon" />
                                            <h4>{t('misc.cw_loading')}</h4>
                                        </div> :

              allUsers.map((u) =>
              <div
                key={u.id}
                className="conversation-item"
                data-user-id={u.id}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => handleActivationKeyDown(event, () => startConversation(u.id))}
                onClick={() => startConversation(u.id)}>
                
                                                <div className="conv-avatar" style={{ background: 'linear-gradient(135deg, #a8c0ff, #3f2b96)', color: 'white' }}>
                                                    {(u.name?.[0] || '?').toUpperCase()}
                                                </div>
                                                <div className="conv-info">
                                                    <div className="conv-name">{u.name}</div>
                                                    <div className="conv-role" style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)' }}>
                                                        {u.role || t('misc.cw_employee_default')}
                                                    </div>
                                                </div>
                                                <div className="conv-action">
                                                    <Plus size={16} color="var(--mac-accent-blue)" />
                                                </div>
                                            </div>
              )
              }
                                </>)
            }
                        </div>
          }

                    {/* Messages */}
                    {activeConversation && !showNewChat &&
          <>
                            <div
              className="messages-container"
              ref={messagesContainerRef}
              onScroll={handleScroll}>
              
                                {showMsgSearch &&
              <div className="message-search-bar" style={{
                padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                position: 'sticky',
                top: 0,
                zIndex: 10,
                background: 'var(--mac-bg-primary)',
                borderBottom: '1px solid var(--mac-border)'
              }}>
                                        <Input
                  value={msgSearchQuery}
                  onChange={(e) => setMsgSearchQuery(e.target.value)}
                  placeholder={t('misc.cw_search_messages_placeholder')}
                  aria-label={t('misc.cw_search_messages_aria')}
                  autoFocus
                  style={{
                    width: '100%',
                    padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                    borderRadius: 6,
                    border: '1px solid var(--mac-border)',
                    fontSize: 13
                  }} />
                
                                    </div>
              }

                                {isLoading ? (
              /* Skeleton Loading */
              <div className="chat-skeleton">
                                        {[1, 2, 3, 4, 5].map((i) =>
                <div key={i} className={`skeleton-message ${i % 2 ? 'sent' : 'received'}`}>
                                                <div className="skeleton-bubble" />
                                            </div>
                )}
                                    </div>) :
              messages.length === 0 ?
              <div className="empty-state">
                                        <div className="conv-avatar" style={{ width: 64, height: 64, fontSize: 24, marginBottom: 16 }}>
                                            {(activeUser?.user_name?.[0] || '?').toUpperCase()}
                                        </div>
                                        <h4>{activeUser?.user_name}</h4>
                                        <p>{activeUser?.role || t('misc.cw_employee_default')}</p>
                                        <p style={{ marginTop: 8, fontSize: 13, opacity: 0.6 }}>{t('misc.cw_write_first_message')}</p>
                                    </div> :

              <div
                style={{
                  height: `${rowVirtualizer.getTotalSize()}px`,
                  width: '100%',
                  position: 'relative'
                }}>
                
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
                      }}>
                      
                                                    {item.type === 'date-separator' ?
                      <div className="date-separator">
                                                            <span>{formatDateSeparator(item.date, t)}</span>
                                                        </div> :

                      <div className={`message-row ${item.sender_id === user?.id ? 'sent' : 'received'}`}>
                                                            {item.sender_id !== user?.id && activeUser &&
                        <Avatar
                          user={{
                            name: activeUser.user_name,
                            role: activeUser.user_role
                          }}
                          size={28}
                          className="message-avatar" />

                        }
                                                            <div
                          className={`message ${item.sender_id === user?.id ? 'sent' : 'received'}`}
                          onContextMenuCapture={(e) => handleMessageContextMenu(e, item)}>
                          
                                                                {item.message_type === 'voice' ?
                          <>
                                                                        <VoiceMessage
                              message={item}
                              fileUrl={item.file_url} />
                            
                                                                        <div className="message-meta">
                                                                            <span className="message-time">{formatMessageTime(item.created_at)}</span>
                                                                            {item.sender_id === user?.id &&
                              <span className="message-status">
                                                                                    {item.is_read ? <CheckCheck size={14} /> : <Check size={14} />}
                                                                                </span>
                              }
                                                                        </div>
                                                                    </> :

                          <>
                                                                        <div className="message-content">
                                                                            {item.message_type === 'image' ?
                              <div className="message-image">
                                                                                    <img
                                  src={item.content}
                                  alt="Attached"
                                  role="button"
                                  tabIndex={0}
                                  aria-label={t('misc.cw_open_image_aria')}
                                  onClick={() => window.open(item.content, '_blank')}
                                  onKeyDown={(event) => handleActivationKeyDown(event, () => window.open(item.content, '_blank'))}
                                  style={{ cursor: 'pointer', maxWidth: '100%', borderRadius: 8 }} />
                                
                                                                                </div> :
                              (item.message_type === 'file' || (item.file_id && item.file_url && item.message_type !== 'voice')) ?
                              <div className="message-file">
                                                                                    <a href={item.content} target="_blank" rel="noopener noreferrer" className="file-link">
                                                                                        <Paperclip size={16} />
                                                                                        <span>{item.content.split('name=')[1] || t('misc.cw_file_default')}</span>
                                                                                    </a>
                                                                                </div> :

                              <ReactMarkdown
                                urlTransform={(url) => {
                                  // F-010: filter dangerous protocols
                                  const allowed = /^(https?:|mailto:|tel:|\/|#)/i;
                                  if (!allowed.test(url)) return '#';
                                  return url;
                                }}
                                components={{
                                  a: ({ href, children, ...props }) => {
                                    if (href && /^(javascript|data|vbscript):/i.test(href)) {
                                      return <span>{children}</span>;
                                    }
                                    return <a {...props} href={href} target="_blank" rel="noopener noreferrer" />;
                                  }

                                }}>
                                
                                                                                    {item.content}
                                                                                </ReactMarkdown>
                              }

                                                                            {item.message_type === 'text' && item.content && item.content.match(/https?:\/\/[^\s]+/) &&
                              <LinkPreview url={item.content.match(/https?:\/\/[^\s]+/)[0]} />
                              }
                                                                        </div>
                                                                        <div className="message-meta">
                                                                            <span className="message-time">{formatMessageTime(item.created_at)}</span>
                                                                            {item.sender_id === user?.id &&
                              <span className="message-status">
                                                                                    {item.is_read ? <CheckCheck size={14} /> : <Check size={14} />}
                                                                                </span>
                              }
                                                                        </div>
                                                                    </>
                          }

                                                                {item.reactions && item.reactions.length > 0 &&
                          <div className="message-reactions">
                                                                        {Object.entries(groupReactions(item.reactions)).map(([emoji, userIds]) =>
                            <span
                              key={emoji}
                              className={`reaction-bubble ${userIds.includes(user?.id) ? 'active' : ''}`}
                              role="button"
                              tabIndex={0}
                              onKeyDown={(event) => handleActivationKeyDown(event, () => toggleReaction(item.id, emoji))}
                              onClick={(e) => {e.stopPropagation();toggleReaction(item.id, emoji);}}>
                              
                                                                                {emoji} {userIds.length > 1 && userIds.length}
                                                                            </span>
                            )}
                                                                    </div>
                          }

                                                                <button
                            className="add-reaction-btn"
                            aria-label={t('misc.cw_add_reaction_aria')}
                            onClick={(e) => {
                              e.stopPropagation();
                              setReactionMenuMessageId(reactionMenuMessageId === item.id ? null : item.id);
                            }}>
                            
                                                                    <Smile size={14} />
                                                                </button>

                                                                {reactionMenuMessageId === item.id &&
                          <div className="reaction-menu">
                                                                        {['👍', '❤️', '😂', '😮', '😢', '🔥'].map((emoji) =>
                            <button
                              key={emoji}
                              aria-label={`React with ${emoji}`}
                              onClick={(e) => {
                                e.stopPropagation();
                                toggleReaction(item.id, emoji);
                                setReactionMenuMessageId(null);
                              }}>
                              
                                                                                {emoji}
                                                                            </button>
                            )}
                                                                    </div>
                          }
                                                            </div>
                                                        </div>
                      }
                                                </div>);

                })}

                                        {/* Typing Indicator inside scroll area */}
                                        {typingUsers[activeConversation] &&
                <div
                  className="typing-indicator-modern"
                  style={{
                    position: 'absolute',
                    // PR-68 / P0-4: fixed position — was bottom: -40 (clipped by overflow: hidden)
                    bottom: 8,
                    left: 12,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8
                  }}>
                  
                                                <Avatar
                    user={{
                      name: activeUser?.user_name,
                      role: activeUser?.user_role
                    }}
                    size={24} />
                  
                                                <div className="typing-bubble">
                                                    <div className="typing-dots">
                                                        <span></span><span></span><span></span>
                                                    </div>
                                                </div>
                                            </div>
                }
                                        <div ref={messagesEndRef} style={{ height: 1 }} />
                                    </div>
              }

                                {/* Scroll to Bottom Button */}
                                {showScrollToBottom &&
              <button
                className="scroll-to-bottom-btn"
                onClick={scrollToBottom}
                title={t('misc.cw_scroll_to_bottom_title')}
                aria-label={t('misc.cw_scroll_to_bottom_aria')}>
                
                                        <ChevronDown size={20} />
                                    </button>
              }
                            </div>

                            <div className="message-input-container">
                                {/* PR-71: Quick-reply templates popover */}
                                {showQuickReplies && (
                                  <div style={{
                                    position: 'absolute',
                                    bottom: '100%',
                                    left: 0,
                                    right: 0,
                                    background: 'var(--mac-bg-primary)',
                                    border: '1px solid var(--mac-border)',
                                    borderRadius: 'var(--mac-radius-md)',
                                    padding: '8px',
                                    display: 'grid',
                                    gridTemplateColumns: '1fr 1fr',
                                    gap: '4px',
                                    zIndex: 10,
                                    boxShadow: 'var(--mac-shadow-md)',
                                  }}>
                                    {quickReplies.map((reply) => (
                                      <button
                                        key={reply}
                                        onClick={() => {
                                          setInputValue(reply);
                                          setShowQuickReplies(false);
                                          inputRef.current?.focus();
                                        }}
                                        style={{
                                          padding: '6px 10px',
                                          textAlign: 'left',
                                          background: 'var(--mac-bg-secondary)',
                                          border: 'none',
                                          borderRadius: 'var(--mac-radius-sm)',
                                          cursor: 'pointer',
                                          fontSize: 'var(--mac-font-size-sm)',
                                          color: 'var(--mac-text-primary)',
                                        }}
                                      >
                                        {reply}
                                      </button>
                                    ))}
                                  </div>
                                )}
                                {showVoiceRecorder ?
              <VoiceRecorder
                onSend={handleSendVoice}
                onCancel={() => setShowVoiceRecorder(false)} /> :


              <>
                                        <div className="input-wrapper">
                                            <textarea
                    ref={inputRef}
                    value={inputValue}
                    onChange={handleInputChange}
                    onKeyPress={handleKeyPress}
                    placeholder={t('misc.cw_message_input_placeholder')}
                    rows={1}
                    disabled={isSending}
                    onMouseDown={(e) => e.stopPropagation()}
                    aria-label={t('misc.cw_enter_message_aria')} />
                  
                                            {inputValue.length > 100 &&
                  <span className={`char-counter ${inputValue.length > MAX_MESSAGE_LENGTH * 0.9 ? 'warning' : ''}`}>
                                                    {inputValue.length}/{MAX_MESSAGE_LENGTH}
                                                </span>
                  }
                                        </div>
                                        <FileUploader
                  onUpload={handleFileUpload}
                  disabled={isSending} />

                                        {/* PR-71: Quick-reply templates */}
                                        <button
                  onClick={() => setShowQuickReplies((v) => !v)}
                  className="voice-btn"
                  title={t('chatQuickReplies')}
                  aria-label={t('chatQuickReplies')}
                  disabled={isSending}>
                  <Zap size={16} />
                </button>

                                        <EmojiPicker
                  onEmojiSelect={(emoji) => {
                    setInputValue((prev) => prev + emoji);
                    inputRef.current?.focus();
                  }}
                  disabled={isSending} />

                                        {/* PR-71: Urgent flag toggle */}
                                        <button
                  onClick={() => setIsUrgent((v) => !v)}
                  className="voice-btn"
                  title={isUrgent ? t('chatUrgentRemove') : t('chatUrgent')}
                  aria-label={isUrgent ? t('chatUrgentRemove') : t('chatUrgent')}
                  style={{ color: isUrgent ? 'var(--mac-error, #dc2626)' : 'var(--mac-text-secondary)' }}
                  disabled={isSending}>
                  <AlertCircle size={16} />
                </button>

                                        <button
                  onClick={() => setShowVoiceRecorder(true)}
                  className="voice-btn"
                  title={t('chatVoiceMessage')}
                  aria-label={t('chatVoiceMessage')}
                  disabled={isSending}>

                                            <Mic size={18} />
                                        </button>
                                        <button
                  onClick={handleSend}
                  disabled={!inputValue.trim() || isSending}
                  className="send-btn"
                  title={t('chatSend')}
                  aria-label={t('chatSend')}>
                  
                                            <Send size={16} />
                                        </button>
                                    </>
              }
                            </div>
                        </>
          }
                </div>
                {contextMenu &&
        <MessageContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          message={contextMenu.message}
          isOwn={contextMenu.message.sender_id === user?.id}
          onBlur={() => setContextMenu(null)}
          onAction={handleMenuAction} />

                }

                {/* Resize handle */}
                {!isCompactViewport &&
        <div className="chat-resize-handle" onPointerDown={handleResizeStart} />
                }
            </div>
        </div>,
    document.body
  );
  // P-013 fix: portal-mounted ConfirmDialog rendered outside the chat portal
  // (useConfirm's createPortal already mounts to document.body, so we just
  // need to invoke it from this component's render tree).
  return (
    <>
      {chatWindowElement}
      {confirmDialog}
    </>
  );
};

ChatWindow.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
};

export default ChatWindow;
