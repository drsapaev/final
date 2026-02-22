import React, { useEffect } from 'react';
import PropTypes from 'prop-types';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '../../../utils/cn';

const Modal = React.forwardRef(({ 
  children, 
  isOpen = false,
  onClose,
  title,
  size = 'md',
  showCloseButton = true,
  closeOnOverlayClick = true,
  closeOnEscape = true,
  className = '',
  overlayClassName = '',
  ...props 
}, ref) => {
  const sizes = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
    full: 'max-w-full mx-4'
  };

  // Закрытие по Escape
  useEffect(() => {
    if (!isOpen || !closeOnEscape) return;

    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose?.();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, closeOnEscape, onClose]);

  // Блокировка скролла страницы
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = 'unset';
      };
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleOverlayClick = () => {
    if (closeOnOverlayClick) {
      onClose?.();
    }
  };

  const modalContent = (
    <div 
      className={cn(
        'fixed inset-0 z-50 flex items-center justify-center p-4',
        overlayClassName
      )}
    >
      {/* Overlay */}
      {closeOnOverlayClick ? (
        <button
          type="button"
          className="absolute inset-0 bg-black bg-opacity-50 transition-opacity"
          onClick={handleOverlayClick}
          aria-label="Закрыть модальное окно"
          style={{ border: 0, margin: 0, padding: 0 }}
        />
      ) : (
        <div className="absolute inset-0 bg-black bg-opacity-50 transition-opacity" />
      )}
      
      {/* Modal */}
      <div
        ref={ref}
        className={cn(
          'relative bg-white rounded-lg shadow-xl w-full',
          sizes[size],
          'transform transition-all',
          'animate-in fade-in-0 zoom-in-95 duration-200',
          className
        )}
        {...props}
      >
        {/* Header */}
        {(title || showCloseButton) && (
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            {title && (
              <h3 className="text-lg font-semibold text-gray-900">
                {title}
              </h3>
            )}
            {showCloseButton && (
              <button
                onClick={onClose}
                className="p-1 text-gray-400 hover:text-gray-600 transition-colors rounded-md hover:bg-gray-100"
              >
                <X className="w-5 h-5" />
              </button>
            )}
          </div>
        )}
        
        {/* Content */}
        <div className="p-6">
          {children}
        </div>
      </div>
    </div>
  );

  // Рендерим в портал
  return createPortal(modalContent, document.body);
});

Modal.displayName = 'Modal';

Modal.propTypes = {
  children: PropTypes.node,
  isOpen: PropTypes.bool,
  onClose: PropTypes.func,
  title: PropTypes.node,
  size: PropTypes.oneOf(['sm', 'md', 'lg', 'xl', 'full']),
  showCloseButton: PropTypes.bool,
  closeOnOverlayClick: PropTypes.bool,
  closeOnEscape: PropTypes.bool,
  className: PropTypes.string,
  overlayClassName: PropTypes.string
};

const ModalHeader = React.forwardRef(({ 
  children, 
  className = '', 
  ...props 
}, ref) => (
  <div
    ref={ref}
    className={cn('px-6 py-4 border-b border-gray-200', className)}
    {...props}
  >
    {children}
  </div>
));

ModalHeader.displayName = 'ModalHeader';

ModalHeader.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string
};

const ModalTitle = React.forwardRef(({ 
  children, 
  className = '', 
  ...props 
}, ref) => (
  <h3
    ref={ref}
    className={cn('text-lg font-semibold text-gray-900', className)}
    {...props}
  >
    {children}
  </h3>
));

ModalTitle.displayName = 'ModalTitle';

ModalTitle.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string
};

const ModalContent = React.forwardRef(({ 
  children, 
  className = '', 
  ...props 
}, ref) => (
  <div
    ref={ref}
    className={cn('px-6 py-4', className)}
    {...props}
  >
    {children}
  </div>
));

ModalContent.displayName = 'ModalContent';

ModalContent.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string
};

const ModalFooter = React.forwardRef(({ 
  children, 
  className = '', 
  ...props 
}, ref) => (
  <div
    ref={ref}
    className={cn('px-6 py-4 border-t border-gray-200 flex justify-end space-x-2', className)}
    {...props}
  >
    {children}
  </div>
));

ModalFooter.displayName = 'ModalFooter';

ModalFooter.propTypes = {
  children: PropTypes.node,
  className: PropTypes.string
};

export default Modal;
export { ModalHeader, ModalTitle, ModalContent, ModalFooter };



