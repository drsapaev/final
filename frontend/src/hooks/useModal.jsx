/**
 * Улучшенная система модальных окон для медицинских интерфейсов
 * Основана на принципах доступности и медицинских стандартах UX
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useReducedMotion } from './useEnhancedMediaQuery';

// Хук для управления модальными окнами
export const useModal = (initialOpen = false) => {
  const [isOpen, setIsOpen] = useState(initialOpen);
  const [isAnimating, setIsAnimating] = useState(false);

  const openModal = useCallback(() => {
    setIsOpen(true);
    setIsAnimating(true);
  }, []);

  const closeModal = useCallback(() => {
    setIsAnimating(false);
    setTimeout(() => {
      setIsOpen(false);
    }, 300); // Время анимации
  }, []);

  const toggleModal = useCallback(() => {
    if (isOpen) {
      closeModal();
    } else {
      openModal();
    }
  }, [isOpen, openModal, closeModal]);

  return {
    isOpen,
    isAnimating,
    openModal,
    closeModal,
    toggleModal
  };
};

// Хук для управления несколькими модальными окнами
export const useModals = () => {
  const [modals, setModals] = useState({});

  const openModal = useCallback((id) => {
    setModals(prev => ({
      ...prev,
      [id]: { isOpen: true, isAnimating: true }
    }));
  }, []);

  const closeModal = useCallback((id) => {
    setModals(prev => ({
      ...prev,
      [id]: { isOpen: prev[id]?.isOpen || false, isAnimating: false }
    }));
    
    setTimeout(() => {
      setModals(prev => ({
        ...prev,
        [id]: { isOpen: false, isAnimating: false }
      }));
    }, 300);
  }, []);

  const toggleModal = useCallback((id) => {
    const modal = modals[id];
    if (modal?.isOpen) {
      closeModal(id);
    } else {
      openModal(id);
    }
  }, [modals, openModal, closeModal]);

  const isModalOpen = useCallback((id) => {
    return modals[id]?.isOpen || false;
  }, [modals]);

  const isModalAnimating = useCallback((id) => {
    return modals[id]?.isAnimating || false;
  }, [modals]);

  return {
    modals,
    openModal,
    closeModal,
    toggleModal,
    isModalOpen,
    isModalAnimating
  };
};

// Компонент модального окна
export const Modal = ({ 
  isOpen, 
  onClose, 
  title,
  children,
  size = 'md',
  closable = true,
  maskClosable = true,
  className = '',
  ...props 
}) => {
  const { prefersReducedMotion } = useReducedMotion();
  const { shouldRender, animationClasses } = useAnimation(isOpen, 'modal', 300);
  const modalRef = useRef(null);

  const sizes = {
    sm: 'max-w-md',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
    full: 'max-w-full'
  };

  // Обработка клавиши Escape
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen && closable) {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
      document.body.style.overflow = 'hidden';
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, closable, onClose]);

  // Обработка клика по маске
  const handleMaskClick = (e) => {
    if (e.target === e.currentTarget && maskClosable && closable) {
      onClose();
    }
  };

  if (!shouldRender) return null;

  return (
    <div
      className={`modal-mask ${animationClasses}`}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px'
      }}
      onClick={handleMaskClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? 'modal-title' : undefined}
    >
      <div
        ref={modalRef}
        className={`modal-content ${sizes[size]} ${className}`}
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '12px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          maxHeight: '90vh',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          width: '100%'
        }}
        onClick={(e) => e.stopPropagation()}
        {...props}
      >
        {/* Заголовок */}
        {title && (
          <div
            className="modal-header"
            style={{
              padding: '20px 24px',
              borderBottom: '1px solid #e5e7eb',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}
          >
            <h2
              id="modal-title"
              style={{
                margin: 0,
                fontSize: '18px',
                fontWeight: '600',
                color: '#374151'
              }}
            >
              {title}
            </h2>
            
            {closable && (
              <button
                onClick={onClose}
                style={{
                  background: 'none',
                  border: 'none',
                  fontSize: '24px',
                  cursor: 'pointer',
                  color: '#6b7280',
                  padding: '4px',
                  borderRadius: '4px',
                  transition: prefersReducedMotion ? 'none' : 'background-color 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  if (!prefersReducedMotion) {
                    e.target.style.backgroundColor = '#f3f4f6';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!prefersReducedMotion) {
                    e.target.style.backgroundColor = 'transparent';
                  }
                }}
                aria-label="Закрыть модальное окно"
              >
                ×
              </button>
            )}
          </div>
        )}

        {/* Содержимое */}
        <div
          className="modal-body"
          style={{
            padding: '24px',
            overflow: 'auto',
            flex: 1
          }}
        >
          {children}
        </div>
      </div>
    </div>
  );
};

// Компонент модального окна с действиями
export const ModalWithActions = ({ 
  isOpen, 
  onClose, 
  onConfirm,
  title,
  children,
  confirmText = 'Подтвердить',
  cancelText = 'Отмена',
  confirmVariant = 'primary',
  loading = false,
  size = 'md',
  className = '',
  ...props 
}) => {
  const { prefersReducedMotion } = useReducedMotion();

  const handleConfirm = async () => {
    if (onConfirm) {
      await onConfirm();
    }
  };

  const variants = {
    primary: {
      backgroundColor: '#3b82f6',
      color: '#ffffff',
      borderColor: '#3b82f6'
    },
    danger: {
      backgroundColor: '#ef4444',
      color: '#ffffff',
      borderColor: '#ef4444'
    },
    success: {
      backgroundColor: '#10b981',
      color: '#ffffff',
      borderColor: '#10b981'
    },
    warning: {
      backgroundColor: '#f59e0b',
      color: '#ffffff',
      borderColor: '#f59e0b'
    }
  };

  const confirmStyle = variants[confirmVariant] || variants.primary;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      size={size}
      className={className}
      {...props}
    >
      {children}
      
      {/* Действия */}
      <div
        className="modal-actions"
        style={{
          padding: '20px 24px',
          borderTop: '1px solid #e5e7eb',
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '12px'
        }}
      >
        <button
          onClick={onClose}
          disabled={loading}
          style={{
            padding: '10px 20px',
            fontSize: '14px',
            fontWeight: '500',
            border: '1px solid #d1d5db',
            borderRadius: '8px',
            backgroundColor: '#ffffff',
            color: '#374151',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1,
            transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
          }}
          onMouseEnter={(e) => {
            if (!loading && !prefersReducedMotion) {
              e.target.style.backgroundColor = '#f9fafb';
            }
          }}
          onMouseLeave={(e) => {
            if (!loading && !prefersReducedMotion) {
              e.target.style.backgroundColor = '#ffffff';
            }
          }}
        >
          {cancelText}
        </button>
        
        <button
          onClick={handleConfirm}
          disabled={loading}
          style={{
            padding: '10px 20px',
            fontSize: '14px',
            fontWeight: '500',
            border: `1px solid ${confirmStyle.borderColor}`,
            borderRadius: '8px',
            backgroundColor: confirmStyle.backgroundColor,
            color: confirmStyle.color,
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1,
            transition: prefersReducedMotion ? 'none' : 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
          onMouseEnter={(e) => {
            if (!loading && !prefersReducedMotion) {
              e.target.style.opacity = '0.9';
            }
          }}
          onMouseLeave={(e) => {
            if (!loading && !prefersReducedMotion) {
              e.target.style.opacity = '1';
            }
          }}
        >
          {loading && (
            <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
          )}
          {confirmText}
        </button>
      </div>
    </Modal>
  );
};

// Компонент модального окна подтверждения
export const ConfirmModal = ({ 
  isOpen, 
  onClose, 
  onConfirm,
  title = 'Подтверждение',
  message,
  confirmText = 'Подтвердить',
  cancelText = 'Отмена',
  variant = 'primary',
  loading = false,
  className = '',
  ...props 
}) => {
  return (
    <ModalWithActions
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={onConfirm}
      title={title}
      confirmText={confirmText}
      cancelText={cancelText}
      confirmVariant={variant}
      loading={loading}
      size="sm"
      className={className}
      {...props}
    >
      <div style={{ fontSize: '14px', color: '#374151', lineHeight: '1.5' }}>
        {message}
      </div>
    </ModalWithActions>
  );
};

// Компонент модального окна с формой
export const FormModal = ({ 
  isOpen, 
  onClose, 
  onSubmit,
  title,
  children,
  submitText = 'Сохранить',
  cancelText = 'Отмена',
  loading = false,
  size = 'md',
  className = '',
  ...props 
}) => {
  const handleSubmit = (e) => {
    e.preventDefault();
    if (onSubmit) {
      onSubmit(e);
    }
  };

  return (
    <ModalWithActions
      isOpen={isOpen}
      onClose={onClose}
      onConfirm={handleSubmit}
      title={title}
      confirmText={submitText}
      cancelText={cancelText}
      confirmVariant="primary"
      loading={loading}
      size={size}
      className={className}
      {...props}
    >
      <form onSubmit={handleSubmit}>
        {children}
      </form>
    </ModalWithActions>
  );
};

// Компонент модального окна с информацией
export const InfoModal = ({ 
  isOpen, 
  onClose, 
  title,
  message,
  type = 'info',
  className = '',
  ...props 
}) => {
  const types = {
    info: { icon: 'ℹ️', color: '#06b6d4' },
    success: { icon: '✅', color: '#10b981' },
    warning: { icon: '⚠️', color: '#f59e0b' },
    error: { icon: '❌', color: '#ef4444' }
  };

  const typeConfig = types[type] || types.info;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      size="sm"
      className={className}
      {...props}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
        <div style={{ fontSize: '24px', flexShrink: 0 }}>
          {typeConfig.icon}
        </div>
        <div style={{ fontSize: '14px', color: '#374151', lineHeight: '1.5' }}>
          {message}
        </div>
      </div>
    </Modal>
  );
};

export default useModal;