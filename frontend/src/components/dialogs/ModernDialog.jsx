import React, { useEffect, useRef } from 'react';
import { X } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import './ModernDialog.css';

const ModernDialog = ({
  isOpen,
  onClose,
  title,
  children,
  customHeader,
  actions,
  maxWidth = '28rem',
  showCloseButton = true,
  closeOnBackdrop = true,
  closeOnEscape = true,
  className = '',
  ...props
}) => {
  const { theme, getColor } = useTheme();
  const dialogRef = useRef(null);
  const firstFocusableRef = useRef(null);

  // Фокус-ловушка и управление клавишами
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && closeOnEscape) {
        e.preventDefault();
        onClose();
      }

      if (e.key === 'Tab') {
        const focusableElements = dialogRef.current?.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );

        if (focusableElements && focusableElements.length > 0) {
          const firstElement = focusableElements[0];
          const lastElement = focusableElements[focusableElements.length - 1];

          if (e.shiftKey && document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          } else if (!e.shiftKey && document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    // Фокус на первый элемент
    setTimeout(() => {
      const firstFocusable = dialogRef.current?.querySelector(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (firstFocusable) {
        firstFocusable.focus();
      }
    }, 100);

    // Блокируем скролл body
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, closeOnEscape, onClose]);

  if (!isOpen) return null;

  const handleBackdropClick = (e) => {
    if (closeOnBackdrop && e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className={`modern-dialog-backdrop ${className}`}
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? 'dialog-title' : undefined}
      style={{
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        backdropFilter: 'blur(4px)'
      }}
      {...props}
    >
      <div
        ref={dialogRef}
        className="modern-dialog-container"
        style={{
          backgroundColor: getColor('cardBg'),
          maxWidth,
          boxShadow: theme === 'dark'
            ? '0 25px 50px -12px rgba(0, 0, 0, 0.8)'
            : '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
        }}
      >
        {/* Заголовок */}
        {(customHeader || title || showCloseButton) && (
          <div className="modern-dialog-header">
            {customHeader ? (
              customHeader
            ) : (
              <>
                {title && (
                  <h3
                    id="dialog-title"
                    className="modern-dialog-title"
                    style={{ color: getColor('textPrimary') }}
                  >
                    {title}
                  </h3>
                )}
                {showCloseButton && (
                  <button
                    type="button"
                    className="modern-dialog-close"
                    onClick={onClose}
                    aria-label="Закрыть диалог"
                    style={{
                      color: getColor('textSecondary'),
                      backgroundColor: 'transparent'
                    }}
                  >
                    <X size={20} />
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {/* Контент */}
        <div className="modern-dialog-content">
          {children}
        </div>

        {/* Действия */}
        {actions && actions.length > 0 && (
          <div
            className="modern-dialog-actions"
            style={{
              backgroundColor: theme === 'dark' ? '#1f2937' : '#f9fafb',
              borderTop: `1px solid ${theme === 'dark' ? '#374151' : '#e5e7eb'}`
            }}
          >
            {actions.map((action, index) => (
              <button
                key={index}
                type="button"
                className={`modern-dialog-action ${action.variant || 'secondary'} ${action.className || ''}`}
                onClick={action.onClick}
                disabled={action.disabled}
                style={action.style}
                {...action.props}
              >
                {action.icon && <span className="action-icon">{action.icon}</span>}
                {action.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ModernDialog;


