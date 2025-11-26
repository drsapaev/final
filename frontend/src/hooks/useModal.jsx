/**
 * Улучшенная система модальных окон для медицинских интерфейсов
 * Основана на принципах доступности и медицинских стандартах UX
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useReducedMotion } from './useEnhancedMediaQuery';

// Hook for managing animations
const useAnimation = (isActive, type = 'fade', duration = 300) => {
  const [shouldRender, setShouldRender] = useState(isActive);
  const [animationClasses, setAnimationClasses] = useState('');

  useEffect(() => {
    if (isActive) {
      setShouldRender(true);
      setTimeout(() => {
        setAnimationClasses('active');
      }, 10);
    } else {
      setAnimationClasses('');
      const timer = setTimeout(() => {
        setShouldRender(false);
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [isActive, duration]);

  return { shouldRender, animationClasses };
};

// Хук для управления модальными окнами
export const useModal = (initialOpen = false) => {
  const [isOpen, setIsOpen] = useState(initialOpen);
  const [isAnimating, setIsAnimating] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [loading, setLoading] = useState(false);

  const openModal = useCallback((item = null) => {
    setSelectedItem(item);
    setIsOpen(true);
    setIsAnimating(true);
  }, []);

  const closeModal = useCallback(() => {
    setIsAnimating(false);
    setLoading(false);
    setTimeout(() => {
      setIsOpen(false);
      setSelectedItem(null);
    }, 300);
  }, []);

  const toggleModal = useCallback((item = null) => {
    if (isOpen) {
      closeModal();
    } else {
      openModal(item);
    }
  }, [isOpen, openModal, closeModal]);

  const setModalLoading = useCallback((isLoading) => {
    setLoading(isLoading);
  }, []);

  return {
    isOpen,
    isAnimating,
    selectedItem,
    loading,
    openModal,
    closeModal,
    toggleModal,
    setModalLoading
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

// Placeholder components for backwards compatibility
export const ModalWithActions = Modal;
export const ConfirmModal = Modal;
export const FormModal = Modal;
export const InfoModal = Modal;

export default useModal;