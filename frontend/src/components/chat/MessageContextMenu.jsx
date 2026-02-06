
import React, { useEffect, useRef } from 'react';
import { Copy, Reply, Trash, Forward } from 'lucide-react';
import './MessageContextMenu.css';

const MessageContextMenu = ({ x, y, message, onBlur, onAction, isOwn }) => {
    const menuRef = useRef(null);

    useEffect(() => {
        const handleClickOutside = (event) => {
            if (menuRef.current && !menuRef.current.contains(event.target)) {
                onBlur();
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [onBlur]);

    const handleAction = (action) => {
        onAction(action, message);
        onBlur();
    };

    return (
        <div
            className="message-context-menu"
            ref={menuRef}
            style={{
                left: x,
                top: y
            }}
        >
            <button onClick={() => handleAction('copy')}>
                <Copy size={14} /> <span>Копировать</span>
            </button>
            <button onClick={() => handleAction('reply')}>
                <Reply size={14} /> <span>Ответить</span>
            </button>
            <button onClick={() => handleAction('forward')}>
                <Forward size={14} /> <span>Переслать</span>
            </button>
            {isOwn && (
                <button className="delete" onClick={() => handleAction('delete')}>
                    <Trash size={14} /> <span>Удалить</span>
                </button>
            )}
        </div>
    );
};

export default MessageContextMenu;
