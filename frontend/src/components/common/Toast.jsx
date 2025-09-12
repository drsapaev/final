// Система уведомлений (Toast)
import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useTheme } from '../../contexts/ThemeContext';

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
  const { getColor, getSpacing, getFontSize } = theme;

  const containerStyle = {
    position: 'fixed',
    top: getSpacing('md'),
    right: getSpacing('md'),
    zIndex: 9999,
    display: 'flex',
    flexDirection: 'column',
    gap: getSpacing('sm'),
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
  const { getColor, getSpacing, getFontSize } = theme;
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Анимация появления
    const timer = setTimeout(() => setIsVisible(true), 10);
    return () => clearTimeout(timer);
  }, []);

  const getToastStyles = (type) => {
    const baseStyle = {
      padding: getSpacing('md'),
      borderRadius: '8px',
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
      display: 'flex',
      alignItems: 'flex-start',
      gap: getSpacing('sm'),
      transform: isVisible ? 'translateX(0)' : 'translateX(100%)',
      opacity: isVisible ? 1 : 0,
      transition: 'all 0.3s ease',
      position: 'relative',
      overflow: 'hidden'
    };

    const typeStyles = {
      success: {
        backgroundColor: getColor('success', 'light'),
        borderLeft: `4px solid ${getColor('success', 'main')}`,
        color: getColor('success', 'dark')
      },
      error: {
        backgroundColor: getColor('error', 'light'),
        borderLeft: `4px solid ${getColor('error', 'main')}`,
        color: getColor('error', 'dark')
      },
      warning: {
        backgroundColor: getColor('warning', 'light'),
        borderLeft: `4px solid ${getColor('warning', 'main')}`,
        color: getColor('warning', 'dark')
      },
      info: {
        backgroundColor: getColor('info', 'light'),
        borderLeft: `4px solid ${getColor('info', 'main')}`,
        color: getColor('info', 'dark')
      }
    };

    return { ...baseStyle, ...typeStyles[type] };
  };

  const getIcon = (type) => {
    const iconStyle = {
      fontSize: getFontSize('lg'),
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
    fontSize: getFontSize('md'),
    lineHeight: 1.4
  };

  const titleStyle = {
    fontWeight: '600',
    marginBottom: toast.message ? getSpacing('xs') : 0
  };

  const messageStyle = {
    color: getColor('text', 'secondary')
  };

  const closeButtonStyle = {
    background: 'none',
    border: 'none',
    fontSize: getFontSize('lg'),
    cursor: 'pointer',
    color: 'inherit',
    opacity: 0.7,
    padding: 0,
    marginLeft: getSpacing('sm'),
    flexShrink: 0
  };

  const progressBarStyle = {
    position: 'absolute',
    bottom: 0,
    left: 0,
    height: '3px',
    backgroundColor: getColor(toast.type, 'main'),
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
