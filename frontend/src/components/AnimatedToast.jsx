import React, { useState, useEffect } from 'react';
import { designTokens, getColor } from '../design-system';

const AnimatedToast = ({
  message,
  type = 'info',
  duration = 3000,
  onClose,
  position = 'top-right',
  className = '',
  style = {}
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const [isLeaving, setIsLeaving] = useState(false);

  useEffect(() => {
    // Показываем toast с задержкой
    const showTimer = setTimeout(() => {
      setIsVisible(true);
    }, 100);

    // Автоматически скрываем через duration
    const hideTimer = setTimeout(() => {
      handleClose();
    }, duration);

    return () => {
      clearTimeout(showTimer);
      clearTimeout(hideTimer);
    };
  }, [duration]);

  const handleClose = () => {
    setIsLeaving(true);
    setTimeout(() => {
      setIsVisible(false);
      if (onClose) onClose();
    }, 300);
  };

  const getTypeStyles = () => {
    const typeStyles = {
      success: {
        backgroundColor: getColor('success', 500),
        color: 'white',
        borderLeft: `4px solid ${getColor('success', 600)}`
      },
      error: {
        backgroundColor: getColor('danger', 500),
        color: 'white',
        borderLeft: `4px solid ${getColor('danger', 600)}`
      },
      warning: {
        backgroundColor: getColor('warning', 500),
        color: 'white',
        borderLeft: `4px solid ${getColor('warning', 600)}`
      },
      info: {
        backgroundColor: getColor('info', 500),
        color: 'white',
        borderLeft: `4px solid ${getColor('info', 600)}`
      }
    };
    return typeStyles[type] || typeStyles.info;
  };

  const getPositionStyles = () => {
    const positionStyles = {
      'top-left': { top: '20px', left: '20px' },
      'top-right': { top: '20px', right: '20px' },
      'top-center': { top: '20px', left: '50%', transform: 'translateX(-50%)' },
      'bottom-left': { bottom: '20px', left: '20px' },
      'bottom-right': { bottom: '20px', right: '20px' },
      'bottom-center': { bottom: '20px', left: '50%', transform: 'translateX(-50%)' }
    };
    return positionStyles[position] || positionStyles['top-right'];
  };

  const toastStyles = {
    position: 'fixed',
    zIndex: 9999,
    minWidth: '300px',
    maxWidth: '400px',
    padding: '16px 20px',
    borderRadius: '12px',
    boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '12px',
    opacity: isVisible && !isLeaving ? 1 : 0,
    transform: isVisible && !isLeaving 
      ? 'translateY(0) scale(1)' 
      : 'translateY(-20px) scale(0.95)',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    ...getTypeStyles(),
    ...getPositionStyles(),
    ...style
  };

  const closeButtonStyles = {
    background: 'none',
    border: 'none',
    color: 'inherit',
    cursor: 'pointer',
    padding: '4px',
    borderRadius: '4px',
    fontSize: '18px',
    lineHeight: 1,
    opacity: 0.7,
    transition: 'opacity 0.2s ease',
    '&:hover': {
      opacity: 1
    }
  };

  if (!isVisible && !isLeaving) return null;

  return (
    <div
      className={`animated-toast ${className}`}
      style={toastStyles}
      role="alert"
      aria-live="polite"
    >
      <span style={{ flex: 1 }}>{message}</span>
      <button
        style={closeButtonStyles}
        onClick={handleClose}
        aria-label="Закрыть уведомление"
      >
        ×
      </button>
    </div>
  );
};

export default AnimatedToast;