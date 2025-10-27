import React, { useEffect } from 'react';
import { X } from 'lucide-react';

const MacOSModal = ({
  isOpen = false,
  onClose,
  title,
  children,
  size = 'md',
  variant = 'default',
  closable = true,
  closeOnOverlayClick = true,
  closeOnEscape = true,
  className,
  style
}) => {
  const sizeStyles = {
    sm: {
      width: '400px',
      maxWidth: '90vw',
      padding: '20px'
    },
    md: {
      width: '600px',
      maxWidth: '90vw',
      padding: '24px'
    },
    lg: {
      width: '800px',
      maxWidth: '95vw',
      padding: '32px'
    },
    xl: {
      width: '1000px',
      maxWidth: '95vw',
      padding: '40px'
    },
    fullscreen: {
      width: '100vw',
      height: '100vh',
      maxWidth: '100vw',
      padding: '0'
    }
  };

  const variantStyles = {
    default: {
      background: 'var(--mac-bg-primary)',
      border: '1px solid var(--mac-border)',
      borderRadius: 'var(--mac-radius-lg)',
      boxShadow: '0 10px 40px rgba(0, 0, 0, 0.2)'
    },
    filled: {
      background: 'var(--mac-bg-secondary)',
      border: 'none',
      borderRadius: 'var(--mac-radius-lg)',
      boxShadow: '0 10px 40px rgba(0, 0, 0, 0.2)'
    },
    minimal: {
      background: 'var(--mac-bg-primary)',
      border: 'none',
      borderRadius: 'var(--mac-radius-md)',
      boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)'
    }
  };

  const currentSize = sizeStyles[size] || sizeStyles.md;
  const currentVariant = variantStyles[variant] || variantStyles.default;

  const overlayStyle = {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'rgba(0, 0, 0, 0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: '20px',
    opacity: isOpen ? 1 : 0,
    visibility: isOpen ? 'visible' : 'hidden',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)'
  };

  const modalStyle = {
    background: currentVariant.background,
    border: currentVariant.border,
    borderRadius: currentVariant.borderRadius,
    boxShadow: currentVariant.boxShadow,
    width: currentSize.width,
    maxWidth: currentSize.maxWidth,
    maxHeight: size === 'fullscreen' ? '100vh' : '90vh',
    overflow: 'hidden',
    transform: isOpen ? 'scale(1)' : 'scale(0.95)',
    transition: 'transform var(--mac-duration-normal) var(--mac-ease)',
    ...style
  };

  const headerStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '20px 24px',
    borderBottom: '1px solid var(--mac-separator)',
    background: 'var(--mac-bg-primary)'
  };

  const titleStyle = {
    fontSize: 'var(--mac-font-size-lg)',
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-text-primary)',
    margin: 0
  };

  const closeButtonStyle = {
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    padding: '8px',
    borderRadius: 'var(--mac-radius-sm)',
    color: 'var(--mac-text-tertiary)',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  };

  const contentStyle = {
    padding: currentSize.padding,
    overflow: 'auto',
    maxHeight: size === 'fullscreen' ? 'calc(100vh - 80px)' : 'calc(90vh - 80px)'
  };

  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget && closeOnOverlayClick) {
      onClose();
    }
  };

  const handleClose = () => {
    if (onClose) {
      onClose();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape' && closeOnEscape) {
      handleClose();
    }
  };

  const handleCloseMouseEnter = (e) => {
    e.target.style.background = 'var(--mac-bg-tertiary)';
    e.target.style.color = 'var(--mac-text-primary)';
  };

  const handleCloseMouseLeave = (e) => {
    e.target.style.background = 'none';
    e.target.style.color = 'var(--mac-text-tertiary)';
  };

  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'hidden';
    } else {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className={className}
      style={overlayStyle}
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? "modal-title" : undefined}
    >
      <div style={modalStyle}>
        {title && (
          <div style={headerStyle}>
            <h2 id="modal-title" style={titleStyle}>
              {title}
            </h2>
            {closable && (
              <button
                style={closeButtonStyle}
                onClick={handleClose}
                onMouseEnter={handleCloseMouseEnter}
                onMouseLeave={handleCloseMouseLeave}
                aria-label="Закрыть модальное окно"
              >
                <X size={20} />
              </button>
            )}
          </div>
        )}
        
        <div style={contentStyle}>
          {children}
        </div>
      </div>
    </div>
  );
};

export default MacOSModal;
