// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useEffect } from 'react';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import { Button } from './ui';
import { X } from 'lucide-react';
import PropTypes from 'prop-types';

const ResponsiveModal = ({
  isOpen,
  onClose,
  title,
  children,
  size = 'md',
  className = '',
  style = {}
}) => {
  const { isMobile } = useBreakpoint();

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

  const handleOverlayClick = () => {
    onClose();
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'color-mix(in srgb, black, transparent 50%)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: isMobile ? 'flex-end' : 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: isMobile ? '0' : '16px'
      }}>
      <button
        type="button"
        aria-label="Закрыть модальное окно"
        onClick={handleOverlayClick}
        style={{
          position: 'absolute',
          inset: 0,
          border: 'none',
          margin: 0,
          padding: 0,
          background: 'transparent',
          cursor: 'pointer'
        }}
      />
      
      <div
        style={{
          backgroundColor: 'var(--mac-bg-primary)',  // PR-42 / Medium-F: was 'white' (broke dark mode)
          borderRadius: isMobile ? '16px 16px 0 0' : '20px',
          boxShadow: 'var(--mac-shadow-xl)',
          maxHeight: isMobile ? '90vh' : '90vh',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          ...modalSize,
          ...mobileStyles,
          ...style
        }}
        className={`responsive-modal ${className}`}>
        
        {/* Заголовок */}
        {title &&
        <div
          style={{
            padding: isMobile ? '16px' : '24px',
            borderBottom: '1px solid var(--mac-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'linear-gradient(135deg, var(--mac-accent-blue) 0%, var(--mac-accent-blue-hover) 100%)',
            color: 'white'
          }}>
          
            <h2
            style={{
              margin: 0,
              fontSize: isMobile ? '18px' : '20px',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
            
              {title}
            </h2>
            <Button
            variant="ghost"
            size="sm"
            onClick={onClose}
            type="button"
            title="Закрыть модальное окно"
            aria-label={typeof title === 'string' ? `Закрыть: ${title}` : 'Закрыть модальное окно'}
            style={{
              minWidth: 'auto',
              padding: 'var(--mac-spacing-2)',
              color: 'white',
              border: '1px solid rgba(255, 255, 255, 0.2)'
            }}>

              <X aria-hidden="true" size={isMobile ? 18 : 20} />
            </Button>
          </div>
        }

        {/* Содержимое */}
        <div
          style={{
            flex: 1,
            overflow: 'auto',
            padding: isMobile ? '16px' : '24px'
          }}>
          
          {children}
        </div>

        {/* Футер (если нужен) */}
        {isMobile &&
        <div
          style={{
            padding: 'var(--mac-spacing-4)',
            borderTop: '1px solid var(--mac-border)',
            background: 'var(--mac-bg-secondary)'
          }}>
          
            <Button
            variant="primary"
            size="lg"
            onClick={onClose}
            style={{ width: '100%' }}>
            
              Закрыть
            </Button>
          </div>
        }
      </div>
    </div>);

};


ResponsiveModal.propTypes = {
  ...(ResponsiveModal.propTypes || {}),
  children: PropTypes.any,
  className: PropTypes.any,
  isOpen: PropTypes.any,
  onClose: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
  title: PropTypes.any,
};

export default ResponsiveModal;
