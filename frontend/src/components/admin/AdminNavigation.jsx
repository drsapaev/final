import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTheme } from '../../contexts/ThemeContext';
import { ChevronRight } from 'lucide-react';

const AdminNavigation = ({ sections }) => {
  const { theme, getColor, getSpacing, getFontSize } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();

  const containerStyle = {
    background: theme === 'light' 
      ? 'rgba(255, 255, 255, 0.9)' 
      : 'rgba(15, 23, 42, 0.9)',
    backdropFilter: 'blur(20px)',
    border: `1px solid ${theme === 'light' ? 'rgba(255, 255, 255, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderRadius: '20px',
    padding: getSpacing('md'),
    boxShadow: theme === 'light' 
      ? '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)'
      : '0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.1)',
    marginBottom: getSpacing('lg')
  };

  return (
    <nav style={containerStyle} className="admin-navigation">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: getSpacing('md') }}>
        {sections.map((section, sectionIndex) => (
          <div key={section.title} style={{ display: 'flex', alignItems: 'center', gap: getSpacing('sm') }}>
            {sectionIndex > 0 && (
              <ChevronRight size={16} style={{ color: 'var(--text-tertiary)', margin: `0 ${getSpacing('xs')}` }} />
            )}
            
            <div className="admin-nav-section" style={{ 
              padding: `${getSpacing('xs')} ${getSpacing('sm')}`,
              borderRadius: '12px',
              background: theme === 'light' ? 'var(--bg-secondary)' : 'var(--bg-tertiary)',
              border: `1px solid var(--border-color)`
            }}>
              <h3 style={{ 
                fontSize: getFontSize('xs'),
                fontWeight: '600',
                color: 'var(--text-secondary)',
                marginBottom: getSpacing('xs'),
                textTransform: 'uppercase',
                letterSpacing: '0.05em'
              }}>
                {section.title}
              </h3>
              
              <div className="admin-nav-buttons" style={{ display: 'flex', gap: getSpacing('xs'), flexWrap: 'wrap' }}>
                {section.items.map((item) => {
                  const isActive = location.pathname === item.to;
                  const Icon = item.icon;
                  
                  const buttonStyle = {
                    display: 'flex',
                    alignItems: 'center',
                    gap: getSpacing('xs'),
                    padding: `${getSpacing('xs')} ${getSpacing('sm')}`,
                    borderRadius: '8px',
                    border: 'none',
                    background: isActive 
                      ? 'linear-gradient(135deg, var(--accent-color) 0%, #2563eb 100%)'
                      : 'transparent',
                    color: isActive ? 'white' : 'var(--text-primary)',
                    fontSize: getFontSize('sm'),
                    fontWeight: isActive ? '600' : '500',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    textDecoration: 'none',
                    boxShadow: isActive ? '0 4px 14px 0 rgba(59, 130, 246, 0.3)' : 'none'
                  };

                  const hoverStyle = {
                    background: isActive 
                      ? 'linear-gradient(135deg, var(--accent-color) 0%, #2563eb 100%)'
                      : theme === 'light' ? 'var(--hover-bg)' : 'var(--bg-secondary)',
                    transform: 'translateY(-1px)'
                  };

                  return (
                    <button
                      key={item.to}
                      style={buttonStyle}
                      onClick={() => navigate(item.to)}
                      onMouseEnter={(e) => Object.assign(e.currentTarget.style, hoverStyle)}
                      onMouseLeave={(e) => Object.assign(e.currentTarget.style, buttonStyle)}
                    >
                      <Icon size={16} />
                      <span>{item.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        ))}
      </div>
    </nav>
  );
};

export default AdminNavigation;
