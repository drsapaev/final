// Система уведомлений (Toast)
import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import AnimatedToast from '../AnimatedToast.jsx';

// Контекст для уведомлений
const ToastContext = createContext();

/**
 * Провайдер контекста уведомлений
 */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const theme = useTheme();

  const addToast = useCallback((toast) => {
    const id = Date.now() + Math.random();
    const newToast = {
      id,
      type: 'info',
      duration: 5000,
      ...toast
    };

    setToasts(prev => [...prev, newToast]);

    // Автоматическое удаление
    if (newToast.duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, newToast.duration);
    }

    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  }, []);

  const clearAllToasts = useCallback(() => {
    setToasts([]);
  }, []);

  const value = {
    toasts,
    addToast,
    removeToast,
    clearAllToasts
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastContainer toasts={toasts} onRemove={removeToast} theme={theme} />
    </ToastContext.Provider>
  );
}

/**
 * Хук для использования уведомлений
 */
export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

/**
 * Контейнер для отображения уведомлений
 */
function ToastContainer({ toasts, onRemove, theme }) {

  const containerStyle = {
    position: 'fixed',
    top: '1rem',
    right: '1rem',
    zIndex: 9999,
    display: 'flex',
    flexDirection: 'column',
    gap: '0.5rem',
    maxWidth: '400px',
    width: '100%'
  };

  return (
    <div style={containerStyle}>
      {toasts.map(toast => (
        <ToastItem
          key={toast.id}
          toast={toast}
          onRemove={onRemove}
          theme={theme}
        />
      ))}
    </div>
  );
}

/**
 * Отдельное уведомление
 */
function ToastItem({ toast, onRemove, theme }) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Анимация появления
    const timer = setTimeout(() => setIsVisible(true), 10);
    return () => clearTimeout(timer);
  }, []);

  const getToastStyles = (type) => {
    const baseStyle = {
      padding: '1rem',
      borderRadius: '8px',
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
      display: 'flex',
      alignItems: 'flex-start',
      gap: '0.5rem',
      transform: isVisible ? 'translateX(0)' : 'translateX(100%)',
      opacity: isVisible ? 1 : 0,
      transition: 'all 0.3s ease',
      position: 'relative',
      overflow: 'hidden'
    };

    const typeStyles = {
      success: {
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        borderLeft: '4px solid var(--color-success)',
        color: 'var(--color-success)'
      },
      error: {
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        borderLeft: '4px solid var(--color-danger)',
        color: 'var(--color-danger)'
      },
      warning: {
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
        borderLeft: '4px solid var(--color-warning)',
        color: 'var(--color-warning)'
      },
      info: {
        backgroundColor: 'rgba(6, 182, 212, 0.1)',
        borderLeft: '4px solid var(--color-info)',
        color: 'var(--color-info)'
      }
    };

    return { ...baseStyle, ...typeStyles[type] };
  };

  const getIcon = (type) => {
    const iconStyle = {
      fontSize: '16px',
      flexShrink: 0,
      marginTop: '2px'
    };

    const icons = {
      success: '✅',
      error: '❌',
      warning: '⚠️',
      info: 'ℹ️'
    };

    return <span style={iconStyle}>{icons[type] || icons.info}</span>;
  };

  const contentStyle = {
    flex: 1,
    fontSize: '14px',
    lineHeight: 1.4
  };

  const titleStyle = {
    fontWeight: '600',
    marginBottom: toast.message ? '0.25rem' : 0
  };

  const messageStyle = {
    color: 'var(--color-text-secondary)'
  };

  const closeButtonStyle = {
    background: 'none',
    border: 'none',
    fontSize: '16px',
    cursor: 'pointer',
    color: 'inherit',
    opacity: 0.7,
    padding: 0,
    marginLeft: '0.5rem',
    flexShrink: 0
  };

  const progressBarStyle = {
    position: 'absolute',
    bottom: 0,
    left: 0,
    height: '3px',
    backgroundColor: toast.type === 'success' ? 'var(--color-success)' :
      toast.type === 'error' ? 'var(--color-danger)' :
        toast.type === 'warning' ? 'var(--color-warning)' :
          'var(--color-info)',
    width: '100%',
    transform: 'scaleX(1)',
    transformOrigin: 'left',
    animation: `toast-progress ${toast.duration}ms linear forwards`
  };

  return (
    <div style={getToastStyles(toast.type)}>
      {getIcon(toast.type)}
      <div style={contentStyle}>
        {toast.title && <div style={titleStyle}>{toast.title}</div>}
        {toast.message && <div style={messageStyle}>{toast.message}</div>}
      </div>
      <button
        style={closeButtonStyle}
        onClick={() => onRemove(toast.id)}
        onMouseOver={(e) => e.target.style.opacity = '1'}
        onMouseOut={(e) => e.target.style.opacity = '0.7'}
      >
        ×
      </button>
      {toast.duration > 0 && (
        <div style={progressBarStyle} />
      )}
    </div>
  );
}

/**
 * Утилиты для быстрого создания уведомлений
 */
export const toast = {
  success: (message, options = {}) => {
    const { addToast } = useToast();
    return addToast({ type: 'success', message, ...options });
  },

  error: (message, options = {}) => {
    const { addToast } = useToast();
    return addToast({ type: 'error', message, ...options });
  },

  warning: (message, options = {}) => {
    const { addToast } = useToast();
    return addToast({ type: 'warning', message, ...options });
  },

  info: (message, options = {}) => {
    const { addToast } = useToast();
    return addToast({ type: 'info', message, ...options });
  }
};

// CSS анимация для прогресс-бара
const style = document.createElement('style');
style.textContent = `
  @keyframes toast-progress {
    from { transform: scaleX(1); }
    to { transform: scaleX(0); }
  }
`;
document.head.appendChild(style);

