/**
 * Кнопка чата для хедера (macOS стиль)
 */

import React, { useState } from 'react';
import { MessageCircle } from 'lucide-react';
import { useChat } from '../../hooks/useChat';
import ChatWindow from './ChatWindow';

/**
 * Кнопка открытия чата с бейджем непрочитанных сообщений
 */
const ChatButton = () => {
    const [isOpen, setIsOpen] = useState(false);
    const { unreadCount, isConnected } = useChat();

    return (
        <>
            <button
                onClick={() => setIsOpen(true)}
                title={isConnected ? 'Сообщения' : 'Сообщения (офлайн)'}
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
                onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
                }}
                onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                }}
            >
                <MessageCircle size={18} />
                {unreadCount > 0 && (
                    <span style={{
                        position: 'absolute',
                        top: '-4px',
                        right: '-4px',
                        backgroundColor: '#FF3B30',
                        color: 'white',
                        fontSize: '10px',
                        fontWeight: '700',
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

            <ChatWindow isOpen={isOpen} onClose={() => setIsOpen(false)} />
        </>
    );
};

export default ChatButton;
