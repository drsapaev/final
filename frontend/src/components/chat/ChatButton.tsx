
/**
 * Кнопка чата для хедера (macOS стиль)
 */

import { lazy, Suspense, useState, useEffect, useRef } from 'react';
import { MessageCircle } from 'lucide-react';
import { useChat } from '../../hooks/useChat';
import { useTranslation } from '../../i18n/useTranslation';

const ChatWindow = lazy(() => import('./ChatWindow'));

/**
 * Кнопка открытия чата с бейджем непрочитанных сообщений
 */
const ChatButton = () => {
  const { t: rawT } = useTranslation(); const t = rawT;
    const [isOpen, setIsOpen] = useState(false);
    const [hasOpened, setHasOpened] = useState(false);
    const { unreadCount, isConnected, loadMessages } = useChat();
    // PR-68 / P0-1: listen for 'openChat' CustomEvent from desktop notifications
    const pendingUserIdRef = useRef<number | null>(null);

    useEffect(() => {
        const handleOpenChat = (event: Event) => {
            const customEvent = event as CustomEvent<{ userId?: number }>;
            setHasOpened(true);
            setIsOpen(true);
            if (customEvent?.detail?.userId) {
                pendingUserIdRef.current = customEvent.detail.userId;
            }
        };
        window.addEventListener('openChat', handleOpenChat);
        return () => window.removeEventListener('openChat', handleOpenChat);
    }, [loadMessages]);

    // When chat opens with a pending userId, load that conversation
    useEffect(() => {
        if (isOpen && pendingUserIdRef.current && loadMessages) {
            loadMessages(pendingUserIdRef.current);
            pendingUserIdRef.current = null;
        }
    }, [isOpen, loadMessages]);

    return (
        <>
            <button
                onClick={() => {
                    setHasOpened(true);
                    setIsOpen(true);
                }}
                title={isConnected ? t('chatMessages') : t('chatMessagesOffline')}
                aria-label={isConnected ? t('chatOpen') : t('chatOpenOffline')}
                style={{
                    position: 'relative',
                    width: '36px',
                    height: '36px',
                    borderRadius: 'var(--mac-radius-sm)',
                    border: '1px solid var(--mac-border)',
                    background: 'transparent',
                    color: 'var(--mac-text-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    transition: 'all var(--mac-duration-fast)',
                    padding: 0
                }}
                onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                    e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
                }}
                onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                }}
            >
                <MessageCircle size={18} />
                {unreadCount > 0 && (
                    <span style={{
                        position: 'absolute',
                        top: '-4px',
                        right: '-4px',
                        backgroundColor: 'var(--mac-error)',
                        color: 'white',
                        fontSize: 'var(--mac-font-size-xs)',
                        fontWeight: 'var(--mac-font-weight-bold)',
                        height: '18px',
                        minWidth: '18px',
                        padding: '0 4px',
                        borderRadius: '9px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        border: '2px solid var(--mac-bg-primary)',
                        boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                    }}>
                        {unreadCount > 99 ? '99+' : unreadCount}
                    </span>
                )}
            </button>

            {hasOpened && (
                <Suspense fallback={
                    <div
                        role="status"
                        aria-live="polite"
                        style={{
                            position: 'fixed',
                            right: 'var(--mac-spacing-4)',
                            bottom: 'var(--mac-spacing-4)',
                            zIndex: 10000,
                            padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                            border: '1px solid var(--mac-border)',
                            borderRadius: 'var(--mac-radius-sm)',
                            background: 'var(--mac-bg-primary)',
                            color: 'var(--mac-text-primary)'
                        }}
                    >
                        {t('common.loading')}
                    </div>
                }>
                    <ChatWindow isOpen={isOpen} onClose={() => setIsOpen(false)} />
                </Suspense>
            )}
        </>
    );
};

export default ChatButton;
