import { useEffect, useRef } from 'react';
import { Copy, Reply, Trash } from 'lucide-react';
import './MessageContextMenu.css';
import { useTranslation } from '../../i18n/useTranslation';
import type { MouseEvent } from 'react';

interface MessageData {
  id: number;
  content?: string;
  sender_id?: number;
  [key: string]: unknown;
}

interface MessageContextMenuProps {
  x: number;
  y: number;
  message: MessageData;
  onBlur: () => void;
  onAction: (action: string, message: MessageData) => void;
  isOwn: boolean;
}

const MessageContextMenu = ({ x, y, message, onBlur, onAction, isOwn }: MessageContextMenuProps) => {
  const { t: rawT } = useTranslation(); const t = rawT;
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: globalThis.MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        onBlur();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [onBlur]);

  const handleAction = (action: string) => {
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
      {isOwn && (
        <button role="menuitem" className="delete" onClick={() => handleAction('delete')}>
          <Trash size={14} /> <span>{t('common.delete')}</span>
        </button>
      )}
    </div>
  );
};

// audit/strict: removed self-referencing propTypes spread

export default MessageContextMenu;
