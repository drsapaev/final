import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Button } from '../../design-system/components';
import { useFade, useSlide } from '../../design-system/hooks/useAnimation';

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
                  <Button
                    variant={active ? 'default' : 'outline'}
                    size="sm"
                    className={`flex items-center space-x-2 transition-all duration-200 ${
                      active 
                        ? 'shadow-md transform scale-105' 
                        : 'hover:shadow-sm hover:transform hover:scale-102'
                    }`}
                    style={{
                      background: active 
                        ? 'linear-gradient(135deg, var(--accent-color) 0%, #1d4ed8 100%)'
                        : undefined,
                      borderColor: active ? 'var(--accent-color)' : 'var(--border-color)',
                      color: active ? 'white' : 'var(--text-primary)'
                    }}
                  >
                    <Icon className="w-4 h-4" />
                    <span className="font-medium">{item.label}</span>
                  </Button>
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