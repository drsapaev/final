/**
 * Унифицированный компонент Modal
 * Согласно MASTER_TODO_LIST строка 219
 */
import React, { useEffect } from 'react';
import { colors, typography, spacing } from '../theme';

const Modal = ({
  isOpen = false,
  onClose,
  title,
  children,
  size = 'medium',
  variant = 'default',
  showCloseButton = true,
  closeOnOverlayClick = true,
  closeOnEscape = true,
  className = '',
  style = {},
  ...props
}) => {
  // Размеры модального окна
  const sizes = {
    small: {
      maxWidth: '400px',
      width: '90%',
    },
    medium: {
      maxWidth: '600px',
      width: '90%',
    },
    large: {
      maxWidth: '800px',
      width: '95%',
    },
    xlarge: {
      maxWidth: '1200px',
      width: '95%',
    },
    fullscreen: {
      maxWidth: '100%',
      width: '100%',
      height: '100%',
      margin: 0,
    },
  };

  // Варианты стилей
  const variants = {
    default: {
      backgroundColor: colors.neutral.white,
      borderRadius: '12px',
      boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
    },
    medical: {
      backgroundColor: colors.neutral.white,
      borderRadius: '8px',
      border: `2px solid ${colors.brand.primary[100]}`,
      boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
    },
    minimal: {
      backgroundColor: colors.neutral.white,
      borderRadius: '6px',
      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
    },
  };

  const sizeStyles = sizes[size];
  const variantStyles = variants[variant];

  // Обработка нажатия Escape
  useEffect(() => {
    if (!isOpen || !closeOnEscape) return;

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, closeOnEscape, onClose]);

  // Блокировка скролла при открытом модальном окне
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const overlayStyles = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1400,
    padding: spacing.spacing[4],
  };

  const modalStyles = {
    position: 'relative',
    ...sizeStyles,
    ...variantStyles,
    maxHeight: '90vh',
    overflow: 'auto',
    ...style,
  };

  const headerStyles = {
    padding: spacing.spacing[6],
    borderBottom: `1px solid ${colors.neutral.gray[200]}`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  };

  const titleStyles = {
    fontSize: typography.fontSizes.xl,
    fontWeight: typography.fontWeights.semibold,
    color: colors.neutral.gray[900],
    margin: 0,
  };

  const closeButtonStyles = {
    background: 'none',
    border: 'none',
    fontSize: typography.fontSizes.xl,
    color: colors.neutral.gray[500],
    cursor: 'pointer',
    padding: spacing.spacing[2],
    borderRadius: '4px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'color 200ms ease',
    
    '&:hover': {
      color: colors.neutral.gray[700],
      backgroundColor: colors.neutral.gray[100],
    },
  };

  const contentStyles = {
    padding: spacing.spacing[6],
  };

  return (
    <div
      style={overlayStyles}
      onClick={closeOnOverlayClick ? onClose : undefined}
    >
      <div
        style={modalStyles}
        className={className}
        onClick={(e) => e.stopPropagation()}
        {...props}
      >
        {/* Заголовок */}
        {(title || showCloseButton) && (
          <div style={headerStyles}>
            {title && <h2 style={titleStyles}>{title}</h2>}
            {showCloseButton && (
              <button
                style={closeButtonStyles}
                onClick={onClose}
                aria-label="Закрыть"
              >
                ✕
              </button>
            )}
          </div>
        )}
        
        {/* Содержимое */}
        <div style={contentStyles}>
          {children}
        </div>
      </div>
    </div>
  );
};

export default Modal;
