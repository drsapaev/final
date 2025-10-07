import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Button, useFade, useSlide } from '../ui/native';
import { colors } from '../../theme/tokens';

const AdminNavigation = ({ sections = [] }) => {
  const location = useLocation();
  const { isVisible: fadeIn, fadeIn: startFadeIn } = useFade(false);
  const { isVisible: slideIn, slideIn: startSlideIn } = useSlide(false, 'up');

  React.useEffect(() => {
    const timer = setTimeout(() => {
      startFadeIn(100);
      startSlideIn(200);
    }, 50);
    return () => clearTimeout(timer);
  }, [startFadeIn, startSlideIn]);

  const isActive = (path) => {
    if (path === '/admin' || path === '/admin/') {
      return location.pathname === '/admin' || location.pathname === '/admin/';
    }
    return location.pathname.startsWith(path);
  };

  return (
    <div 
      className="mb-8"
      style={{
        opacity: fadeIn ? 1 : 0,
        transform: slideIn ? 'translateY(0)' : 'translateY(20px)'
      }}
    >
      {sections.map((section, sectionIndex) => (
        <div key={section.title} className="mb-6">
          <h3 
            className="text-sm font-semibold mb-3 px-2"
            style={{ 
              color: 'var(--text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.05em'
            }}
          >
            {section.title}
          </h3>
          <div className="flex flex-wrap gap-2">
            {section.items.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.to);
              
              return (
                <NavLink key={item.to} to={item.to}>
                  <button
                    className={`navigation-button ${active ? 'active' : ''} flex items-center space-x-2 transition-all duration-200 ${
                      active 
                        ? 'shadow-md transform scale-105' 
                        : 'hover:shadow-sm hover:transform hover:scale-102'
                    }`}
                    style={{
                      background: active
                        ? colors.primary[500]  // ✅ Основной синий из токенов
                        : colors.semantic.surface.selected,  // ✅ Полупрозрачный фон
                      borderWidth: '1px',
                      borderStyle: 'solid',
                      borderColor: active
                        ? colors.primary[500]  // ✅ Основной синий из токенов
                        : colors.semantic.border.medium,  // ✅ Средняя граница из токенов
                      color: active
                        ? colors.semantic.text.inverse  // ✅ Белый текст для активных
                        : colors.primary[400],  // ✅ Светлый синий для неактивных
                      padding: '8px 16px',
                      borderRadius: '6px',
                      fontWeight: '500',
                      cursor: 'pointer',
                      fontSize: '14px'
                    }}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="font-medium">{item.label}</span>
                  </button>
                </NavLink>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};

export default AdminNavigation;

