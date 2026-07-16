// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useEffect, useRef } from 'react';
import PropTypes from 'prop-types';
import { X } from 'lucide-react';
// UX Audit Registrar #5: useTheme удалён — все стили в CSS с macos tokens.
import './ModernDialog.css';
import { useTranslation } from '../../i18n/useTranslation';

const ModernDialog = ({
  isOpen,
  onClose,
  title,
  children,
  customHeader,
  actions,
  maxWidth = '28rem',
  maxHeight = 'calc(100dvh - 2rem)',
  showCloseButton = true,
  closeOnBackdrop = true,
  closeOnEscape = true,
  className = '',
  dialogClassName = '',
  dialogStyle = {},
  ...props
}) => {
  // UX Audit Registrar #5: useTheme() удалён — getColor/theme больше не нужны
  // (все стили перенесены в CSS с macos tokens + [data-theme="dark"] selectors).
  const dialogRef = useRef(null);

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

  // UX Audit Registrar #5: backdropButtonStyle и dialogStyles вынесены в CSS,
  // но dialogStyles всё ещё нужен для maxWidth/maxHeight/dialogStyle props.
  const dialogStyles = {
    maxWidth,
    maxHeight,
    ...dialogStyle
  };

  const dialogLabelProps = customHeader && title ? {
    'aria-label': typeof title === 'string' ? title : undefined
  } : {
    'aria-labelledby': title ? 'dialog-title' : undefined
  };

  return (
    <div
      className={`modern-dialog-backdrop modern-dialog-backdrop--overlay ${className}`}
      role="presentation"
      {...props}>
      {closeOnBackdrop &&
      <button
        type="button"
        className="modern-dialog-backdrop-button"
        onClick={onClose}
        tabIndex={-1}
        aria-label="Закрыть диалог" />

      }
      
      <div
        ref={dialogRef}
        className={`modern-dialog-container modern-dialog-container--styled ${dialogClassName}`}
        role="dialog"
        aria-modal="true"
        {...dialogLabelProps}
        style={dialogStyles}>
        
        {/* Заголовок */}
        {(customHeader || title || showCloseButton) &&
        <div className="modern-dialog-header">
            {customHeader ?
          customHeader :

          <>
                {title &&
            <h3
              id="dialog-title"
              className="modern-dialog-title modern-dialog-title--styled">
              
                    {title}
                  </h3>
            }
                {showCloseButton &&
            <button
              type="button"
              className="modern-dialog-close modern-dialog-close--styled"
              onClick={onClose}
              aria-label="Закрыть диалог">
              
                    <X size={20} />
                  </button>
            }
              </>
          }
          </div>
        }

        {/* Контент */}
        <div className="modern-dialog-content">
          {children}
        </div>

        {/* Действия */}
        {actions && actions.length > 0 &&
        <div
          className="modern-dialog-actions modern-dialog-actions--styled">
          
            {actions.map((action, index) =>
          <button
            key={index}
            type="button"
            className={`modern-dialog-action ${action.variant || 'secondary'} ${action.className || ''}`}
            onClick={action.onClick}
            disabled={action.disabled}
            style={action.style}
            {...action.props}>
            
                {action.icon && <span className="action-icon">{action.icon}</span>}
                {action.label}
              </button>
          )}
          </div>
        }
      </div>
    </div>);

};

ModernDialog.propTypes = {
  isOpen: PropTypes.bool,
  onClose: PropTypes.func,
  title: PropTypes.node,
  children: PropTypes.node,
  customHeader: PropTypes.node,
  actions: PropTypes.arrayOf(
    PropTypes.shape({
      label: PropTypes.node,
      variant: PropTypes.string,
      className: PropTypes.string,
      onClick: PropTypes.func,
      disabled: PropTypes.bool,
      icon: PropTypes.node,
      style: PropTypes.object,
      props: PropTypes.object
    })
  ),
  maxWidth: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  maxHeight: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  showCloseButton: PropTypes.bool,
  closeOnBackdrop: PropTypes.bool,
  closeOnEscape: PropTypes.bool,
  className: PropTypes.string,
  dialogClassName: PropTypes.string,
  dialogStyle: PropTypes.object
};

export default ModernDialog;
