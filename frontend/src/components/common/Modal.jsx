// Система модальных окон
import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useTheme } from '../../contexts/ThemeContext';

// Контекст для модальных окон
const ModalContext = createContext();
let openModalExternal = null;

const getFontSize = (size) => {
  const sizes = {
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
export function ModalProvider({ children }) {
  const [modals, setModals] = useState([]);
  const theme = useTheme();

  const openModal = useCallback((modal) => {
    const id = Date.now() + Math.random();
    const newModal = {
      id,
      type: 'default',
      size: 'medium',
      closable: true,
      ...modal
    };

    setModals((prev) => [...prev, newModal]);
    return id;
  }, []);

  const closeModal = useCallback((id) => {
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
      <ModalContainer modals={modals} onClose={closeModal} theme={theme} />
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
function ModalContainer({ modals, onClose, theme }) {

  const overlayStyle = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
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
      <div key={modal.id} style={overlayStyle}>
          {modal.closable &&
        <button
          type="button"
          style={backdropButtonStyle}
          onClick={() => onClose(modal.id)}
          tabIndex={-1}
          aria-label="Close modal" />

        }
          <ModalItem
          modal={modal}
          onClose={onClose}
          theme={theme} />

        </div>
      )}
    </>);

}

/**
 * Отдельное модальное окно
 */
function ModalItem({ modal, onClose }) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Анимация появления
    const timer = setTimeout(() => setIsVisible(true), 10);
    return () => clearTimeout(timer);
  }, []);

  const getSize = (size) => {
    const sizes = {
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
    borderRadius: '12px',
    boxShadow: '0 20px 40px rgba(0, 0, 0, 0.3)',
    maxWidth: getSize(modal.size),
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
    fontWeight: '600',
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
    borderRadius: '4px',
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

  const handleKeyDown = useCallback((e) => {
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
      style={modalStyle}>

      {modal.title &&
      <div style={headerStyle}>
          <h2 style={titleStyle}>{modal.title}</h2>
          {modal.closable &&
        <button
          style={closeButtonStyle}
          onClick={() => onClose(modal.id)}
          onMouseOver={(e) => {
            e.target.style.backgroundColor = 'var(--color-background-tertiary)';
          }}
          onMouseOut={(e) => {
            e.target.style.backgroundColor = 'transparent';
          }}>

              ×
            </button>
        }
        </div>
      }
      
      <div style={contentStyle}>
        {modal.content}
      </div>
      
      {modal.footer &&
      <div style={footerStyle}>
          {modal.footer}
        </div>
      }
    </div>);

}

/**
 * Базовый компонент модального окна
 */
export function Modal({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'medium',
  closable = true,
  ...props
}) {void
  useTheme();

  const getSize = (size) => {
    const sizes = {
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
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
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
    borderRadius: '12px',
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
    fontWeight: '600',
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
    borderRadius: '4px',
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

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape' && closable) {
      onClose();
    }
  }, [closable, onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  if (!isOpen) return null;

  return (
    <div style={overlayStyle}>
      {closable &&
      <button
        type="button"
        style={backdropButtonStyle}
        onClick={onClose}
        tabIndex={-1}
        aria-label="Close modal" />

      }

      <div style={modalStyle}>
        {title &&
        <div style={headerStyle}>
            <h2 style={titleStyle}>{title}</h2>
            {closable &&
          <button
            style={closeButtonStyle}
            onClick={onClose}
            onMouseOver={(e) => {
              e.target.style.backgroundColor = 'var(--color-background-tertiary)';
            }}
            onMouseOut={(e) => {
              e.target.style.backgroundColor = 'transparent';
            }}>

                ×
              </button>
          }
          </div>
        }
        
        <div style={contentStyle}>
          {children}
        </div>
        
        {footer &&
        <div style={footerStyle}>
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
  confirm: (message, onConfirm, onCancel) => {
    if (!openModalExternal) {
      return null;
    }
    return openModalExternal({
      title: 'Подтверждение',
      content: <p>{message}</p>,
      footer:
      <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={onCancel}>Отмена</button>
          <button onClick={onConfirm}>Подтвердить</button>
        </div>

    });
  },

  alert: (message, onClose) => {
    if (!openModalExternal) {
      return null;
    }
    return openModalExternal({
      title: 'Уведомление',
      content: <p>{message}</p>,
      footer:
      <button onClick={onClose}>OK</button>

    });
  }
};

ModalProvider.propTypes = {
  children: PropTypes.node
};

ModalContainer.propTypes = {
  modals: PropTypes.array,
  onClose: PropTypes.func,
  theme: PropTypes.any
};

ModalItem.propTypes = {
  modal: PropTypes.object,
  onClose: PropTypes.func
};

Modal.propTypes = {
  isOpen: PropTypes.bool,
  onClose: PropTypes.func,
  title: PropTypes.node,
  children: PropTypes.node,
  footer: PropTypes.node,
  size: PropTypes.string,
  closable: PropTypes.bool,
  style: PropTypes.object
};
