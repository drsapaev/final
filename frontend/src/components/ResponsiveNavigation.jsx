import React, { useState } from 'react';
import { useBreakpoint } from '../hooks/useMediaQuery';
import { Button } from './ui';
import { Menu, X, ChevronDown } from 'lucide-react';

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
          padding: '16px',
          background: 'rgba(255, 255, 255, 0.9)',
          backdropFilter: 'blur(20px)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.2)'
        }}>
          <div style={{ fontSize: '18px', fontWeight: '600' }}>
            Меню
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsMenuOpen(!isMenuOpen)}
            style={{ minWidth: 'auto', padding: '8px' }}
          >
            {isMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </Button>
        </div>

        {/* Выпадающее меню */}
        {isMenuOpen && (
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
            {items.map((item, index) => (
              <div
                key={index}
                style={{
                  padding: '16px',
                  borderBottom: index < items.length - 1 ? '1px solid rgba(255, 255, 255, 0.1)' : 'none',
                  cursor: 'pointer',
                  background: activeItem === item.key ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                  transition: 'background-color 0.2s ease'
                }}
                onClick={() => {
                  onItemClick?.(item.key);
                  setIsMenuOpen(false);
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  {item.icon}
                  <span style={{ fontSize: '16px', fontWeight: '500' }}>
                    {item.label}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Планшетная навигация - компактные кнопки
  if (isTablet) {
    return (
      <div className={`responsive-nav ${className}`} style={{
        display: 'flex',
        gap: '8px',
        padding: '16px',
        background: 'rgba(255, 255, 255, 0.9)',
        backdropFilter: 'blur(20px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
        ...style
      }}>
        {items.map((item, index) => (
          <Button
            key={index}
            variant={activeItem === item.key ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => onItemClick?.(item.key)}
            style={{ flex: 1, minWidth: 0 }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {item.icon}
              <span style={{ fontSize: '12px' }}>{item.label}</span>
            </div>
          </Button>
        ))}
      </div>
    );
  }

  // Десктопная навигация - полные кнопки
  return (
    <div className={`responsive-nav ${className}`} style={{
      display: 'flex',
      gap: '12px',
      padding: '20px 24px',
      background: 'rgba(255, 255, 255, 0.9)',
      backdropFilter: 'blur(20px)',
      borderBottom: '1px solid rgba(255, 255, 255, 0.2)',
      ...style
    }}>
      {items.map((item, index) => (
        <Button
          key={index}
          variant={activeItem === item.key ? 'primary' : 'ghost'}
          size="md"
          onClick={() => onItemClick?.(item.key)}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {item.icon}
            <span>{item.label}</span>
          </div>
        </Button>
      ))}
    </div>
  );
};

export default ResponsiveNavigation;
