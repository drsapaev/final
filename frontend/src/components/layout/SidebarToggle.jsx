import React from 'react';
import { Menu, X } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

/**
 * Кнопка переключения сайдбара
 */
const SidebarToggle = ({ isCollapsed, onToggle, className = '' }) => {
  const { isDark } = useTheme();

  return (
    <button
      onClick={onToggle}
      className={`sidebar-toggle ${className}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '40px',
        height: '40px',
        borderRadius: '8px',
        border: 'none',
        backgroundColor: isDark ? '#334155' : '#f1f5f9',
        color: isDark ? '#f8fafc' : '#1e293b',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        position: 'fixed',
        top: '20px',
        left: isCollapsed ? '20px' : '300px',
        zIndex: 1001,
        boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)'
      }}
      onMouseEnter={(e) => {
        e.target.style.backgroundColor = isDark ? '#475569' : '#e2e8f0';
        e.target.style.transform = 'scale(1.05)';
      }}
      onMouseLeave={(e) => {
        e.target.style.backgroundColor = isDark ? '#334155' : '#f1f5f9';
        e.target.style.transform = 'scale(1)';
      }}
      title={isCollapsed ? 'Развернуть сайдбар' : 'Свернуть сайдбар'}
    >
      {isCollapsed ? <Menu size={20} /> : <X size={20} />}
    </button>
  );
};

export default SidebarToggle;

