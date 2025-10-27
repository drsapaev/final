import React, { useEffect } from 'react';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import { Button } from './ui';
import { X } from 'lucide-react';

const ResponsiveModal = ({
  isOpen,
  onClose,
  title,
  children,
  size = 'md',
  className = '',
  style = {}
}) => {
  const { isMobile, isTablet } = useBreakpoint();

  // Блокируем скролл страницы когда модал открыт
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

  // Закрытие по Escape
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Размеры модала
  const sizes = {
    xs: { width: '320px', maxWidth: '90vw' },
    sm: { width: '480px', maxWidth: '90vw' },
    md: { width: '640px', maxWidth: '90vw' },
    lg: { width: '800px', maxWidth: '90vw' },
    xl: { width: '1024px', maxWidth: '90vw' },
    full: { width: '100vw', height: '100vh', maxWidth: '100vw' }
  };

  const modalSize = sizes[size] || sizes.md;

  // Стили для мобильных
  const mobileStyles = isMobile ? {
    width: '100vw',
    height: '100vh',
    maxWidth: '100vw',
    maxHeight: '100vh',
    borderRadius: '0',
    margin: '0'
  } : {};

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: isMobile ? 'flex-end' : 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: isMobile ? '0' : '16px'
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        style={{
          backgroundColor: 'white',
          borderRadius: isMobile ? '16px 16px 0 0' : '20px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          maxHeight: isMobile ? '90vh' : '90vh',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          ...modalSize,
          ...mobileStyles,
          ...style
        }}
        className={`responsive-modal ${className}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Заголовок */}
        {title && (
          <div
            style={{
              padding: isMobile ? '16px' : '24px',
              borderBottom: '1px solid #e5e7eb',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
              color: 'white'
            }}
          >
            <h2
              style={{
                margin: 0,
                fontSize: isMobile ? '18px' : '20px',
                fontWeight: '600'
              }}
            >
              {title}
            </h2>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              style={{
                minWidth: 'auto',
                padding: '8px',
                color: 'white',
                border: '1px solid rgba(255, 255, 255, 0.2)'
              }}
            >
              <X size={isMobile ? 18 : 20} />
            </Button>
          </div>
        )}

        {/* Содержимое */}
        <div
          style={{
            flex: 1,
            overflow: 'auto',
            padding: isMobile ? '16px' : '24px'
          }}
        >
          {children}
        </div>

        {/* Футер (если нужен) */}
        {isMobile && (
          <div
            style={{
              padding: '16px',
              borderTop: '1px solid #e5e7eb',
              background: '#f9fafb'
            }}
          >
            <Button
              variant="primary"
              size="lg"
              onClick={onClose}
              style={{ width: '100%' }}
            >
              Закрыть
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ResponsiveModal;

