import type { CSSProperties, ReactNode } from 'react';

import { useTranslation } from '../../i18n/useTranslation';
import i18n from '../../i18n';
// Система модальных окон
import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
const t18 = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;

// Контекст для модальных окон
const ModalContext = createContext<any>(null);
let openModalExternal: ((modal: Partial<ModalEntry>) => number) | null = null;

const getFontSize = (size: string): string => {
  // t accessed via closure or t18()
  const sizes: Record<string, string> = {
    sm: '0.875rem',
    md: '1rem',
    lg: '1.125rem',
    xl: '1.25rem'
  };
  return sizes[size] || sizes.md;
};

/**
 * Провайдер контекста модальных окон
 */
export interface ModalProviderProps {
  children?: ReactNode;
}

export function ModalProvider({ children }: ModalProviderProps) {
  const [modals, setModals] = useState<ModalEntry[]>([]);
  const theme = useTheme();

  const openModal = useCallback((modal: Partial<ModalEntry>): number => {
    const id = Date.now() + Math.random();
    const newModal: ModalEntry = {
      id,
      type: 'default',
      size: 'medium',
      closable: true,
      ...modal
    };

    setModals((prev) => [...prev, newModal]);
    return id;
  }, []);

  const closeModal = useCallback((id: string | number) => {
    setModals((prev) => prev.filter((modal) => modal.id !== id));
  }, []);

  const closeAllModals = useCallback(() => {
    setModals([]);
  }, []);

  useEffect(() => {
    openModalExternal = openModal;
    return () => {
      if (openModalExternal === openModal) {
        openModalExternal = null;
      }
    };
  }, [openModal]);

  const value = {
    modals,
    openModal,
    closeModal,
    closeAllModals
  };

  return (
    <ModalContext.Provider value={value}>
      {children}
      <ModalContainerAny modals={modals} onClose={closeModal} />
    </ModalContext.Provider>);

}

/**
 * Хук для использования модальных окон
 */
export function useModal() {
  const context = useContext(ModalContext);
  if (!context) {
    throw new Error('useModal must be used within a ModalProvider');
  }
  return context;
}

/**
 * Контейнер для отображения модальных окон
 */
interface ModalEntry {
  id: string | number;
  closable?: boolean;
  title?: ReactNode;
  content?: ReactNode;
  footer?: ReactNode;
  size?: string;
  type?: string;
  [key: string]: unknown;
}

interface ModalContainerProps {
  modals: ModalEntry[];
  onClose: (id: string | number) => void;
  theme?: string;
}
function ModalContainer({ modals, onClose, theme }: ModalContainerProps) {

  const overlayStyle = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'color-mix(in srgb, black, transparent 50%)',
    zIndex: 1000,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '1rem'
  };
  const backdropButtonStyle = {
    position: 'absolute',
    inset: 0,
    border: 'none',
    margin: 0,
    padding: 0,
    background: 'transparent'
  };

  return (
    <>
      {modals.map((modal) =>
      <div key={modal.id} style={overlayStyle as CSSProperties}>
          {modal.closable &&
        <button
          type="button"
          style={backdropButtonStyle as CSSProperties}
          onClick={() => onClose(modal.id)}
          tabIndex={-1}
          aria-label="Close modal" />

        }
          <ModalItem
          modal={modal}
          onClose={onClose} />

        </div>
      )}
    </>);

}

/**
 * Отдельное модальное окно
 */
interface ModalItemProps {
  modal: ModalEntry;
  onClose: (id: string | number) => void;
}

function ModalItem({ modal, onClose }: ModalItemProps) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Анимация появления
    const timer = setTimeout(() => setIsVisible(true), 10);
    return () => clearTimeout(timer);
  }, []);

  const getSize = (size: string): string => {
    const sizes: Record<string, string> = {
      small: '400px',
      medium: '600px',
      large: '800px',
      xlarge: '1000px',
      fullscreen: '95vw'
    };
    return sizes[size] || sizes.medium;
  };

  const modalStyle = {
    backgroundColor: 'var(--color-background-primary)',
    borderRadius: 'var(--mac-radius-lg)',
    boxShadow: '0 20px 40px rgba(0, 0, 0, 0.3)',
    maxWidth: getSize(modal.size ?? 'medium'),
    width: '100%',
    maxHeight: '90vh',
    overflow: 'hidden',
    transform: isVisible ? 'scale(1)' : 'scale(0.9)',
    opacity: isVisible ? 1 : 0,
    transition: 'all 0.3s ease',
    display: 'flex',
    flexDirection: 'column',
    position: 'relative',
    zIndex: 1
  };

  const headerStyle = {
    padding: '1.5rem',
    borderBottom: '1px solid var(--color-border-medium)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between'
  };

  const titleStyle = {
    fontSize: getFontSize('xl'),
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--color-text-primary)',
    margin: 0
  };

  const closeButtonStyle = {
    background: 'none',
    border: 'none',
    fontSize: getFontSize('xl'),
    cursor: 'pointer',
    color: 'var(--color-text-secondary)',
    padding: '0.5rem',
    borderRadius: 'var(--mac-radius-sm)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '32px',
    height: '32px'
  };

  const contentStyle = {
    padding: '1.5rem',
    flex: 1,
    overflow: 'auto'
  };

  const footerStyle = {
    padding: '1.5rem',
    borderTop: '1px solid var(--color-border-medium)',
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '0.5rem'
  };

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' && modal.closable) {
      onClose(modal.id);
    }
  }, [modal.closable, modal.id, onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <div
      style={modalStyle as CSSProperties}>

      {modal.title &&
      <div style={headerStyle as CSSProperties}>
          <h2 style={titleStyle as CSSProperties}>{modal.title}</h2>
          {modal.closable &&
        <button
          style={closeButtonStyle as CSSProperties}
          onClick={() => onClose(modal.id)}
          onMouseOver={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.backgroundColor = 'var(--color-background-tertiary)';
          }}
          onMouseOut={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.backgroundColor = 'transparent';
          }}>

              ×
            </button>
        }
        </div>
      }
      
      <div style={contentStyle as CSSProperties}>
        {modal.content}
      </div>
      
      {modal.footer &&
      <div style={footerStyle as CSSProperties}>
          {modal.footer}
        </div>
      }
    </div>);

}

/**
 * Базовый компонент модального окна
 */
export interface ModalProps {
  isOpen?: boolean;
  onClose?: () => void;
  title?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  size?: string;
  closable?: boolean;
  style?: CSSProperties;
  [key: string]: unknown;
}

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'medium',
  closable = true,
  ...props
}: ModalProps) {void
  useTheme();

  const getSize = (size: string): string => {
    const sizes: Record<string, string> = {
      small: '400px',
      medium: '600px',
      large: '800px',
      xlarge: '1000px',
      fullscreen: '95vw'
    };
    return sizes[size] || sizes.medium;
  };

  const overlayStyle = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'color-mix(in srgb, black, transparent 50%)',
    zIndex: 1000,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '1rem'
  };
  const backdropButtonStyle = {
    position: 'absolute',
    inset: 0,
    border: 'none',
    margin: 0,
    padding: 0,
    background: 'transparent'
  };

  const modalStyle = {
    backgroundColor: 'var(--color-background-primary)',
    borderRadius: 'var(--mac-radius-lg)',
    boxShadow: '0 20px 40px rgba(0, 0, 0, 0.3)',
    maxWidth: getSize(size),
    width: '100%',
    maxHeight: '90vh',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    position: 'relative',
    zIndex: 1,
    ...props.style
  };

  const headerStyle = {
    padding: '1.5rem',
    borderBottom: '1px solid var(--color-border-medium)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between'
  };

  const titleStyle = {
    fontSize: getFontSize('xl'),
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--color-text-primary)',
    margin: 0
  };

  const closeButtonStyle = {
    background: 'none',
    border: 'none',
    fontSize: getFontSize('xl'),
    cursor: 'pointer',
    color: 'var(--color-text-secondary)',
    padding: '0.5rem',
    borderRadius: 'var(--mac-radius-sm)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '32px',
    height: '32px'
  };

  const contentStyle = {
    padding: '1.5rem',
    flex: 1,
    overflow: 'auto'
  };

  const footerStyle = {
    padding: '1.5rem',
    borderTop: '1px solid var(--color-border-medium)',
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '0.5rem'
  };

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' && closable) {
      onClose?.();
    }
  }, [closable, onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  if (!isOpen) return null;

  return (
    <div style={overlayStyle as CSSProperties}>
      {closable &&
      <button
        type="button"
        style={backdropButtonStyle as CSSProperties}
        onClick={onClose}
        tabIndex={-1}
        aria-label="Close modal" />

      }

      <div style={modalStyle as CSSProperties}>
        {title &&
        <div style={headerStyle as CSSProperties}>
            <h2 style={titleStyle as CSSProperties}>{title}</h2>
            {closable &&
          <button
            style={closeButtonStyle as CSSProperties}
            onClick={onClose}
            onMouseOver={(e: React.MouseEvent<HTMLElement>) => {
              e.currentTarget.style.backgroundColor = 'var(--color-background-tertiary)';
            }}
            onMouseOut={(e: React.MouseEvent<HTMLElement>) => {
              e.currentTarget.style.backgroundColor = 'transparent';
            }}>

                ×
              </button>
          }
          </div>
        }
        
        <div style={contentStyle as CSSProperties}>
          {children}
        </div>
        
        {footer &&
        <div style={footerStyle as CSSProperties}>
            {footer}
          </div>
        }
      </div>
    </div>);

}

/**
 * Утилиты для быстрого создания модальных окон
 */
export const modal = {
  confirm: (message: ReactNode, onConfirm: () => void, onCancel: () => void): number | null => {
    if (!openModalExternal) {
      return null;
    }
    return openModalExternal({
      title: t18('final.modal_confirm_title'),
      content: <p>{message}</p>,
      footer:
      <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)' } as CSSProperties}>
          <button onClick={onCancel}>Отмена</button>
          <button onClick={onConfirm}>Подтвердить</button>
        </div>

    });
  },

  alert: (message: ReactNode, onClose: () => void): number | null => {
    if (!openModalExternal) {
      return null;
    }
    return openModalExternal({
      title: t18('final.modal_notification_title'),
      content: <p>{message}</p>,
      footer:
      <button onClick={onClose}>OK</button>

    });
  }
};



const ModalContainerAny = ModalContainer;


