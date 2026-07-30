import type { CSSProperties } from 'react';

// Система уведомлений (Toast)
import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { useTranslation } from '../../i18n/useTranslation';


// Контекст для уведомлений
const ToastContext = createContext<unknown>(null);
let addToastExternal: ((toast: Record<string, unknown>) => string | number | null) | null = null;

/**
 * Провайдер контекста уведомлений
 */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [toasts, setToasts] = useState<Record<string, unknown>[]>([]);
  const theme = useTheme();

  const addToast = useCallback((toast: Record<string, unknown>) => {
    const id = Date.now() + Math.random();
    const newToast = {
      id,
      type: 'info',
      duration: 5000,
      ...toast
    };

    setToasts((prev) => [...prev, newToast]);

    // Автоматическое удаление
    if (newToast.duration > 0) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((item) => item.id !== id));
      }, newToast.duration);
    }

    return id;
  }, []);

  const removeToast = useCallback((id: string | number) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const clearAllToasts = useCallback(() => {
    setToasts([]);
  }, []);

  useEffect(() => {
    addToastExternal = addToast;
    return () => {
      if (addToastExternal === addToast) {
        addToastExternal = null;
      }
    };
  }, [addToast]);

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
    </ToastContext.Provider>);

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
function ToastContainer({ toasts, onRemove, theme }: { toasts: Record<string, unknown>[]; onRemove: (id: string | number) => void; theme?: unknown }) {

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
    <div style={containerStyle as CSSProperties}>
      {toasts.map((toast: Record<string, unknown>) =>
      <ToastItem
        key={toast.id as string | number}
        toast={toast}
        onRemove={onRemove}
        theme={theme as string} />

      )}
    </div>);

}

/**
 * Отдельное уведомление
 */

function ToastItem({ toast, onRemove, theme }: { toast: Record<string, unknown>; onRemove: (id: string | number) => void; theme?: string }) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Анимация появления
    const timer = setTimeout(() => setIsVisible(true), 10);
    return () => clearTimeout(timer);
  }, []);

  const getToastStyles = (type: string) => {
    const baseStyle = {
      padding: '1rem',
      borderRadius: 'var(--mac-radius-md)',
      boxShadow: 'var(--mac-shadow-md)',
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
        backgroundColor: 'var(--mac-error-bg)',
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

    return { ...baseStyle, ...typeStyles[type as keyof typeof typeStyles] };
  };

  const getIcon = (type: string) => {
    const iconStyle = {
      fontSize: 'var(--mac-font-size-lg)',
      flexShrink: 0,
      marginTop: '2px'
    };

    const icons = {
      success: '✅',
      error: '❌',
      warning: '⚠️',
      info: 'ℹ️'
    };

    return <span style={iconStyle}>{icons[type as keyof typeof icons] || icons.info}</span>;
  };

  const contentStyle = {
    flex: 1,
    fontSize: 'var(--mac-font-size-base)',
    lineHeight: 1.4
  };

  const titleStyle = {
    fontWeight: 'var(--mac-font-weight-semibold)',
    marginBottom: toast.message ? '0.25rem' : 0
  };

  const messageStyle = {
    color: 'var(--color-text-secondary)'
  };

  const closeButtonStyle = {
    background: 'none',
    border: 'none',
    fontSize: 'var(--mac-font-size-lg)',
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
    <div style={getToastStyles(toast.type as string) as unknown as CSSProperties}>
      {getIcon(toast.type as string)}
      <div style={contentStyle as unknown as CSSProperties}>
        {Boolean(toast.title) && <div style={titleStyle as unknown as CSSProperties}>{toast.title as string}</div>}
        {Boolean(toast.message) && <div style={messageStyle}>{toast.message as string}</div>}
      </div>
      <button
        style={closeButtonStyle}
        onClick={() => onRemove(toast.id as string | number)}
        onMouseOver={(e: React.MouseEvent<HTMLElement>) => e.currentTarget.style.opacity = '1'}
        onMouseOut={(e: React.MouseEvent<HTMLElement>) => e.currentTarget.style.opacity = '0.7'}>

        ×
      </button>
      {(toast.duration as number) > 0 &&
      <div style={progressBarStyle as unknown as CSSProperties} />
      }
    </div>);

}





/**
 * Утилиты для быстрого создания уведомлений
 */
export const toast = {
  success: (message: string, options: Record<string, unknown> = {}) => {
    if (!addToastExternal) return null;
    return addToastExternal({ type: 'success', message, ...options });
  },

  error: (message: string, options: Record<string, unknown> = {}) => {
    if (!addToastExternal) return null;
    return addToastExternal({ type: 'error', message, ...options });
  },

  warning: (message: string, options: Record<string, unknown> = {}) => {
    if (!addToastExternal) return null;
    return addToastExternal({ type: 'warning', message, ...options });
  },

  info: (message: string, options: Record<string, unknown> = {}) => {
    if (!addToastExternal) return null;
    return addToastExternal({ type: 'info', message, ...options });
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
