
import { useEffect, useRef } from 'react';
import { Copy, Reply, Trash } from 'lucide-react';
import './MessageContextMenu.css';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';

const MessageContextMenu = ({ x, y, message, onBlur, onAction, isOwn }) => {
  const { t } = useTranslation();
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
            role="menu"
            aria-label="Меню сообщения"
            style={{
                left: x,
                top: y
            }}
        >
            <button role="menuitem" onClick={() => handleAction('copy')}>
                <Copy size={14} /> <span>Копировать</span>
            </button>
            <button role="menuitem" onClick={() => handleAction('reply')}>
                <Reply size={14} /> <span>Ответить</span>
            </button>
            {/* PR-69 / H-4: removed forward stub */}
            {isOwn && (
                <button role="menuitem" className="delete" onClick={() => handleAction('delete')}>
                    <Trash size={14} /> <span>{t('common.delete')}</span>
                </button>
            )}
        </div>
    );
};


MessageContextMenu.propTypes = {
  ...(MessageContextMenu.propTypes || {}),
  isOwn: PropTypes.any,
  message: PropTypes.any,
  onAction: PropTypes.any,
  onBlur: PropTypes.any,
  x: PropTypes.any,
  y: PropTypes.any,
};

export default MessageContextMenu;
