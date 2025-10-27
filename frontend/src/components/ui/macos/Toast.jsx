import React, { useState, useEffect } from 'react';

const Toast = React.forwardRef(({ 
  message,
  type = 'info',
  duration = 4000,
  position = 'top-right',
  onClose,
  className = '',
  style = {},
  autoClose,
  ...props
}, ref) => {
  const [isVisible, setIsVisible] = useState(true);
  const [isExiting, setIsExiting] = useState(false);

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => {
        handleClose();
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [duration]);

  const handleClose = () => {
    setIsExiting(true);
    setTimeout(() => {
      setIsVisible(false);
      onClose && onClose();
    }, 200);
  };

  const typeStyles = {
    success: {
      backgroundColor: 'var(--mac-success)',
      color: 'white',
      icon: '✓'
    },
    error: {
      backgroundColor: 'var(--mac-danger)',
      color: 'white',
      icon: '✕'
    },
    warning: {
      backgroundColor: 'var(--mac-warning)',
      color: 'white',
      icon: '⚠'
    },
    info: {
      backgroundColor: 'var(--mac-accent-blue)',
      color: 'white',
      icon: 'ℹ'
    }
  };

  const positionStyles = {
    'top-right': { top: '20px', right: '20px' },
    'top-left': { top: '20px', left: '20px' },
    'bottom-right': { bottom: '20px', right: '20px' },
    'bottom-left': { bottom: '20px', left: '20px' },
    'top-center': { top: '20px', left: '50%', transform: 'translateX(-50%)' },
    'bottom-center': { bottom: '20px', left: '50%', transform: 'translateX(-50%)' }
  };

  const toastStyles = {
    position: 'fixed',
    zIndex: 'var(--mac-z-toast)',
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px 16px',
    borderRadius: '8px',
    boxShadow: 'var(--mac-shadow-lg)',
    backdropFilter: 'var(--mac-blur-medium)',
    WebkitBackdropFilter: 'var(--mac-blur-medium)',
    border: '1px solid rgba(255, 255, 255, 0.2)',
    minWidth: '300px',
    maxWidth: '400px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    fontSize: '13px',
    fontWeight: '500',
    opacity: isExiting ? 0 : 1,
    transform: isExiting ? 'translateY(-20px) scale(0.95)' : 'translateY(0) scale(1)',
    transition: 'all var(--mac-duration-slow) var(--mac-ease)',
    ...typeStyles[type],
    ...positionStyles[position],
    ...style
  };

  if (!isVisible) return null;

  return (
    <div
      ref={ref}
      className={`mac-toast mac-toast--${type} ${className}`}
      style={toastStyles}
      role="alert"
      aria-live="polite"
      {...props}
    >
      <span className="mac-toast-icon" style={{ fontSize: '16px', fontWeight: 'bold' }}>
        {typeStyles[type].icon}
      </span>
      <span className="mac-toast-message" style={{ flex: 1 }}>
        {message}
      </span>
      <button
        className="mac-toast-close"
        onClick={handleClose}
        style={{
          background: 'none',
          border: 'none',
          color: 'inherit',
          cursor: 'pointer',
          padding: '4px',
          borderRadius: '4px',
          fontSize: '14px',
          opacity: 0.7,
          transition: 'opacity var(--mac-duration-fast) var(--mac-ease)'
        }}
        aria-label="Close notification"
      >
        ✕
      </button>
      <style>{`
        .mac-toast:hover {
          transform: ${isExiting ? 'translateY(-20px) scale(0.95)' : 'translateY(-2px) scale(1.02)'};
          box-shadow: var(--mac-shadow-xl);
        }
        .mac-toast-close:hover {
          opacity: 1;
          background: rgba(255, 255, 255, 0.2);
        }
        @media (prefers-reduced-motion: reduce) {
          .mac-toast {
            transition: none;
          }
        }
        @media (prefers-color-scheme: dark) {
          .mac-toast {
            border-color: rgba(255, 255, 255, 0.1);
          }
        }
      `}</style>
    </div>
  );
});

// Toast Container Component
export const ToastContainer = ({ children, position = 'top-right', maxToasts = 5 }) => {
  const [toasts, setToasts] = useState([]);

  const addToast = (toastProps) => {
    const id = Math.random().toString(36).slice(2);
    const newToast = { ...toastProps, id };
    
    setToasts(prev => {
      const updated = [...prev, newToast];
      return updated.slice(-maxToasts);
    });
  };

  const removeToast = (id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  };

  return (
    <div className="mac-toast-container" style={{ position: 'relative' }}>
      {children}
      {toasts.map(toast => (
        <Toast
          key={toast.id}
          {...toast}
          position={position}
          onClose={() => removeToast(toast.id)}
        />
      ))}
    </div>
  );
};

export default Toast;
