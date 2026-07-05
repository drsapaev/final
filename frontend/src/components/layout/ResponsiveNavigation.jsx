import { useState } from 'react';
import { useBreakpoint } from '../../hooks/useEnhancedMediaQuery';
import { Button } from '../ui';
import { Menu, X } from 'lucide-react';
import PropTypes from 'prop-types';

const ResponsiveNavigation = ({
  items = [],
  activeItem,
  onItemClick,
  className = '',
  style = {}
}) => {
  const { isMobile, isTablet } = useBreakpoint();
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  // Мобильная навигация - гамбургер меню
  if (isMobile) {
    return (
      <div className={`responsive-nav ${className}`} style={style}>
        {/* Заголовок с кнопкой меню */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: 'var(--mac-spacing-4)',
          background: 'color-mix(in srgb, white, transparent 10%)',
          backdropFilter: 'blur(20px)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.2)'
        }}>
          <div style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)' }}>
            Меню
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            type="button"
            title={isMenuOpen ? 'Закрыть меню' : 'Открыть меню'}
            aria-label={isMenuOpen ? 'Закрыть меню' : 'Открыть меню'}
            aria-expanded={isMenuOpen}
            style={{ minWidth: 'auto', padding: 'var(--mac-spacing-2)' }}>
            
            {isMenuOpen ? <X aria-hidden="true" size={20} /> : <Menu aria-hidden="true" size={20} />}
          </Button>
        </div>

        {/* Выпадающее меню */}
        {isMenuOpen &&
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          background: 'rgba(255, 255, 255, 0.95)',
          backdropFilter: 'blur(20px)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
          zIndex: 1000,
          boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
        }}>
            {items.map((item, index) =>
          <div
            key={index}
            role="button"
            tabIndex={0}
            style={{
              padding: 'var(--mac-spacing-4)',
              borderBottom: index < items.length - 1 ? '1px solid rgba(255, 255, 255, 0.1)' : 'none',
              cursor: 'pointer',
              background: activeItem === item.key ? 'var(--mac-accent-bg)' : 'transparent',
              transition: 'background-color 0.2s ease'
            }}
            onClick={() => {
              onItemClick?.(item.key);
              setIsMenuOpen(false);
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onItemClick?.(item.key);
                setIsMenuOpen(false);
              }
            }}>
            
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-3)' }}>
                  {item.icon}
                  <span style={{ fontSize: 'var(--mac-font-size-lg)', fontWeight: 'var(--mac-font-weight-medium)' }}>
                    {item.label}
                  </span>
                </div>
              </div>
          )}
          </div>
        }
      </div>);

  }

  // Планшетная навигация - компактные кнопки
  if (isTablet) {
    return (
      <div className={`responsive-nav ${className}`} style={{
        display: 'flex',
        gap: 'var(--mac-spacing-2)',
        padding: 'var(--mac-spacing-4)',
        background: 'color-mix(in srgb, white, transparent 10%)',
        backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
        ...style
      }}>
        {items.map((item, index) =>
        <Button
          key={index}
          variant={activeItem === item.key ? 'primary' : 'ghost'}
          size="sm"
          onClick={() => onItemClick?.(item.key)}
          style={{ flex: 1, minWidth: 0 }}>
          
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
              {item.icon}
              <span style={{ fontSize: 'var(--mac-font-size-xs)' }}>{item.label}</span>
            </div>
          </Button>
        )}
      </div>);

  }

  // Десктопная навигация - полные кнопки
  return (
    <div className={`responsive-nav ${className}`} style={{
      display: 'flex',
      gap: 'var(--mac-spacing-3)',
      padding: '20px 24px',
      background: 'color-mix(in srgb, white, transparent 10%)',
      backdropFilter: 'blur(20px)',
      borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
      ...style
    }}>
      {items.map((item, index) =>
      <Button
        key={index}
        variant={activeItem === item.key ? 'primary' : 'ghost'}
        size="md"
        onClick={() => onItemClick?.(item.key)}>
        
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
            {item.icon}
            <span>{item.label}</span>
          </div>
        </Button>
      )}
    </div>);

};


ResponsiveNavigation.propTypes = {
  ...(ResponsiveNavigation.propTypes || {}),
  activeItem: PropTypes.any,
  className: PropTypes.any,
  items: PropTypes.any,
  onItemClick: PropTypes.any,
  style: PropTypes.any,
};

export default ResponsiveNavigation;
