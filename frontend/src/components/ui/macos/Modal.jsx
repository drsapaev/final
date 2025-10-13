import React, { useEffect, useRef } from 'react';
import { useTheme } from '../../../contexts/ThemeContext';
import { Button } from './Button';

/**
 * macOS-style Modal Component
 * Implements Apple's Human Interface Guidelines for modal dialogs
 */
const Modal = ({
  isOpen,
  onClose,
  title,
  children,
  actions,
  size = 'default',
  variant = 'default',
  closeOnBackdrop = true,
  closeOnEscape = true,
  className = '',
  style = {},
  ...props
}) => {
  const { theme } = useTheme();
  const modalRef = useRef(null);
  const backdropRef = useRef(null);

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (isOpen && closeOnEscape && e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      // Focus trap for accessibility
      if (modalRef.current) {
        modalRef.current.focus();
      }
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, closeOnEscape, onClose]);

  // Handle backdrop click
  const handleBackdropClick = (e) => {
    if (closeOnBackdrop && e.target === backdropRef.current) {
      onClose();
    }
  };

  // Size styles
  const sizeStyles = {
    small: { width: '400px', maxWidth: '90vw' },
    default: { width: '500px', maxWidth: '90vw' },
    large: { width: '700px', maxWidth: '90vw' },
    fullscreen: { width: '90vw', height: '90vh', maxWidth: 'none', maxHeight: 'none' }
  };

  // Modal styles
  const modalStyles = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    display: isOpen ? 'flex' : 'none',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1100,
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    ...style
  };

  const backdropStyles = {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    animation: isOpen ? 'mac-modal-fade-in 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)' : 'mac-modal-fade-out 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)'
  };

  const contentStyles = {
    backgroundColor: 'rgba(255, 255, 255, 0.95)',
    borderRadius: '12px',
    boxShadow: '0 20px 40px rgba(0, 0, 0, 0.15)',
    border: '1px solid rgba(0, 0, 0, 0.1)',
    position: 'relative',
    maxHeight: '80vh',
    overflow: 'hidden',
    animation: isOpen ? 'mac-modal-slide-up 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)' : 'mac-modal-slide-down 0.2s cubic-bezier(0.2, 0.8, 0.2, 1)',
    ...sizeStyles[size]
  };

  if (!isOpen) return null;

  return (
    <div
      ref={modalRef}
      className={`mac-modal ${className}`}
      style={modalStyles}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      {...props}
    >
      {/* Backdrop */}
      <div
        ref={backdropRef}
        className="mac-modal-backdrop"
        style={backdropStyles}
        onClick={handleBackdropClick}
      />

      {/* Modal Content */}
      <div className="mac-modal-content" style={contentStyles}>
        {/* Header */}
        {title && (
          <div className="mac-modal-header" style={{
            padding: '20px 20px 0 20px',
            borderBottom: title ? '1px solid rgba(0, 0, 0, 0.1)' : 'none',
            marginBottom: title ? '16px' : '0'
          }}>
            <h2
              id="modal-title"
              style={{
                fontSize: '17px',
                fontWeight: '600',
                color: 'var(--mac-text-primary)',
                margin: '0 0 8px 0',
                fontFamily: 'inherit'
              }}
            >
              {title}
            </h2>
          </div>
        )}

        {/* Body */}
        <div className="mac-modal-body" style={{
          padding: title ? '0 20px' : '20px',
          paddingBottom: actions ? '0' : '20px',
          overflowY: 'auto',
          maxHeight: size === 'fullscreen' ? 'calc(90vh - 140px)' : '60vh'
        }}>
          {children}
        </div>

        {/* Footer */}
        {actions && (
          <div className="mac-modal-footer" style={{
            padding: '16px 20px',
            borderTop: '1px solid rgba(0, 0, 0, 0.1)',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '8px',
            backgroundColor: 'rgba(248, 249, 250, 0.8)'
          }}>
            {actions}
          </div>
        )}

        {/* Close button for fullscreen modals */}
        {size === 'fullscreen' && (
          <Button
            variant="ghost"
            size="small"
            onClick={onClose}
            style={{
              position: 'absolute',
              top: '12px',
              right: '12px',
              width: '28px',
              height: '28px',
              borderRadius: '6px',
              padding: '0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            ✕
          </Button>
        )}
      </div>

      <style jsx>{`
        @keyframes mac-modal-fade-in {
          from {
            opacity: 0;
          }
          to {
            opacity: 1;
          }
        }

        @keyframes mac-modal-fade-out {
          from {
            opacity: 1;
          }
          to {
            opacity: 0;
          }
        }

        @keyframes mac-modal-slide-up {
          from {
            opacity: 0;
            transform: translateY(20px) scale(0.95);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }

        @keyframes mac-modal-slide-down {
          from {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
          to {
            opacity: 0;
            transform: translateY(20px) scale(0.95);
          }
        }

        /* Dark mode adjustments */
        @media (prefers-color-scheme: dark) {
          .mac-modal-content {
            background-color: rgba(255, 255, 255, 0.05) !important;
            border-color: rgba(255, 255, 255, 0.1) !important;
            color: #f5f5f7 !important;
          }

          .mac-modal-footer {
            background-color: rgba(248, 249, 250, 0.05) !important;
            border-color: rgba(255, 255, 255, 0.1) !important;
          }
        }

        /* High contrast mode */
        @media (prefers-contrast: high) {
          .mac-modal-content {
            border-width: 2px !important;
          }
        }

        /* Reduced motion */
        @media (prefers-reduced-motion: reduce) {
          .mac-modal-backdrop,
          .mac-modal-content {
            animation: none !important;
          }
        }

        /* Focus trap for accessibility */
        .mac-modal:focus {
          outline: 2px solid #007aff;
          outline-offset: 2px;
        }
      `}</style>
    </div>
  );
};

/**
 * macOS-style Modal Header Component
 */
export const ModalHeader = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  return (
    <div
      ref={ref}
      className={`mac-modal-header ${className}`}
      style={{
        padding: '20px 20px 0 20px',
        ...style
      }}
      {...props}
    >
      {children}
    </div>
  );
});

ModalHeader.displayName = 'macOS Modal Header';

/**
 * macOS-style Modal Title Component
 */
export const ModalTitle = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  return (
    <h2
      ref={ref}
      className={`mac-modal-title ${className}`}
      style={{
        fontSize: '17px',
        fontWeight: '600',
        color: 'var(--mac-text-primary)',
        margin: '0 0 8px 0',
        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
        ...style
      }}
      {...props}
    >
      {children}
    </h2>
  );
});

ModalTitle.displayName = 'macOS Modal Title';

/**
 * macOS-style Modal Content Component
 */
export const ModalContent = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  return (
    <div
      ref={ref}
      className={`mac-modal-content ${className}`}
      style={{
        padding: '0 20px',
        paddingBottom: '20px',
        color: 'var(--mac-text-primary)',
        fontSize: '13px',
        lineHeight: '1.5',
        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
        ...style
      }}
      {...props}
    >
      {children}
    </div>
  );
});

ModalContent.displayName = 'macOS Modal Content';

/**
 * macOS-style Modal Footer Component
 */
export const ModalFooter = React.forwardRef(({
  children,
  className = '',
  style = {},
  ...props
}, ref) => {
  return (
    <div
      ref={ref}
      className={`mac-modal-footer ${className}`}
      style={{
        padding: '16px 20px',
        borderTop: '1px solid rgba(0, 0, 0, 0.1)',
        display: 'flex',
        justifyContent: 'flex-end',
        gap: '8px',
        backgroundColor: 'rgba(248, 249, 250, 0.8)',
        ...style
      }}
      {...props}
    >
      {children}
    </div>
  );
});

ModalFooter.displayName = 'macOS Modal Footer';

export default Modal;
