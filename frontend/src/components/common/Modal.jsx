// Система модальных окон
import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useTheme } from '../../contexts/ThemeContext';

// Контекст для модальных окон
const ModalContext = createContext();

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

    setModals(prev => [...prev, newModal]);
    return id;
  }, []);

  const closeModal = useCallback((id) => {
    setModals(prev => prev.filter(modal => modal.id !== id));
  }, []);

  const closeAllModals = useCallback(() => {
    setModals([]);
  }, []);

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
    </ModalContext.Provider>
  );
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
  const { getColor, getSpacing } = theme;

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
    padding: getSpacing('md')
  };

  return (
    <>
      {modals.map(modal => (
        <div key={modal.id} style={overlayStyle}>
          <ModalItem
            modal={modal}
            onClose={onClose}
            theme={theme}
          />
        </div>
      ))}
    </>
  );
}

/**
 * Отдельное модальное окно
 */
function ModalItem({ modal, onClose, theme }) {
  const { getColor, getSpacing, getFontSize } = theme;
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
    backgroundColor: getColor('background', 'primary'),
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
    flexDirection: 'column'
  };

  const headerStyle = {
    padding: getSpacing('lg'),
    borderBottom: `1px solid ${getColor('border', 'light')}`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between'
  };

  const titleStyle = {
    fontSize: getFontSize('xl'),
    fontWeight: '600',
    color: getColor('text', 'primary'),
    margin: 0
  };

  const closeButtonStyle = {
    background: 'none',
    border: 'none',
    fontSize: getFontSize('xl'),
    cursor: 'pointer',
    color: getColor('text', 'secondary'),
    padding: getSpacing('xs'),
    borderRadius: '4px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '32px',
    height: '32px'
  };

  const contentStyle = {
    padding: getSpacing('lg'),
    flex: 1,
    overflow: 'auto'
  };

  const footerStyle = {
    padding: getSpacing('lg'),
    borderTop: `1px solid ${getColor('border', 'light')}`,
    display: 'flex',
    justifyContent: 'flex-end',
    gap: getSpacing('sm')
  };

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget && modal.closable) {
      onClose(modal.id);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape' && modal.closable) {
      onClose(modal.id);
    }
  };

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [modal.id, modal.closable]);

  return (
    <div
      style={modalStyle}
      onClick={handleOverlayClick}
      onKeyDown={handleKeyDown}
    >
      {modal.title && (
        <div style={headerStyle}>
          <h2 style={titleStyle}>{modal.title}</h2>
          {modal.closable && (
            <button
              style={closeButtonStyle}
              onClick={() => onClose(modal.id)}
              onMouseOver={(e) => {
                e.target.style.backgroundColor = getColor('background', 'tertiary');
              }}
              onMouseOut={(e) => {
                e.target.style.backgroundColor = 'transparent';
              }}
            >
              ×
            </button>
          )}
        </div>
      )}
      
      <div style={contentStyle}>
        {modal.content}
      </div>
      
      {modal.footer && (
        <div style={footerStyle}>
          {modal.footer}
        </div>
      )}
    </div>
  );
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
}) {
  const theme = useTheme();
  const { getColor, getSpacing, getFontSize } = theme;

  if (!isOpen) return null;

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
    padding: getSpacing('md')
  };

  const modalStyle = {
    backgroundColor: getColor('background', 'primary'),
    borderRadius: '12px',
    boxShadow: '0 20px 40px rgba(0, 0, 0, 0.3)',
    maxWidth: getSize(size),
    width: '100%',
    maxHeight: '90vh',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    ...props.style
  };

  const headerStyle = {
    padding: getSpacing('lg'),
    borderBottom: `1px solid ${getColor('border', 'light')}`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between'
  };

  const titleStyle = {
    fontSize: getFontSize('xl'),
    fontWeight: '600',
    color: getColor('text', 'primary'),
    margin: 0
  };

  const closeButtonStyle = {
    background: 'none',
    border: 'none',
    fontSize: getFontSize('xl'),
    cursor: 'pointer',
    color: getColor('text', 'secondary'),
    padding: getSpacing('xs'),
    borderRadius: '4px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '32px',
    height: '32px'
  };

  const contentStyle = {
    padding: getSpacing('lg'),
    flex: 1,
    overflow: 'auto'
  };

  const footerStyle = {
    padding: getSpacing('lg'),
    borderTop: `1px solid ${getColor('border', 'light')}`,
    display: 'flex',
    justifyContent: 'flex-end',
    gap: getSpacing('sm')
  };

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget && closable) {
      onClose();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape' && closable) {
      onClose();
    }
  };

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [closable]);

  return (
    <div
      style={overlayStyle}
      onClick={handleOverlayClick}
      onKeyDown={handleKeyDown}
    >
      <div style={modalStyle}>
        {title && (
          <div style={headerStyle}>
            <h2 style={titleStyle}>{title}</h2>
            {closable && (
              <button
                style={closeButtonStyle}
                onClick={onClose}
                onMouseOver={(e) => {
                  e.target.style.backgroundColor = getColor('background', 'tertiary');
                }}
                onMouseOut={(e) => {
                  e.target.style.backgroundColor = 'transparent';
                }}
              >
                ×
              </button>
            )}
          </div>
        )}
        
        <div style={contentStyle}>
          {children}
        </div>
        
        {footer && (
          <div style={footerStyle}>
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Утилиты для быстрого создания модальных окон
 */
export const modal = {
  confirm: (message, onConfirm, onCancel) => {
    const { openModal } = useModal();
    return openModal({
      title: 'Подтверждение',
      content: <p>{message}</p>,
      footer: (
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={onCancel}>Отмена</button>
          <button onClick={onConfirm}>Подтвердить</button>
        </div>
      )
    });
  },
  
  alert: (message, onClose) => {
    const { openModal } = useModal();
    return openModal({
      title: 'Уведомление',
      content: <p>{message}</p>,
      footer: (
        <button onClick={onClose}>OK</button>
      )
    });
  }
};
