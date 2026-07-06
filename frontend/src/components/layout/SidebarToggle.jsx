import { Menu, X } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import PropTypes from 'prop-types';

/**
 * Кнопка переключения сайдбара
 */
const SidebarToggle = ({ isCollapsed, onToggle, className = '' }) => {
  const { isDark } = useTheme();

  return (
    <button
      onClick={onToggle}
      className={`sidebar-toggle ${className}`}
      aria-label={isCollapsed ? 'Развернуть сайдбар' : 'Свернуть сайдбар'}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: '40px',
        height: '40px',
        borderRadius: 'var(--mac-radius-md)',
        border: 'none',
        backgroundColor: isDark ? 'var(--mac-text-primary)' : '#f1f5f9',
        color: isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-text-primary)',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        position: 'fixed',
        top: '20px',
        left: isCollapsed ? '20px' : '300px',
        zIndex: 1001,
        boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)'
      }}
      onMouseEnter={(e) => {
        e.target.style.backgroundColor = isDark ? 'var(--mac-text-secondary)' : 'var(--mac-border)';
        e.target.style.transform = 'scale(1.05)';
      }}
      onMouseLeave={(e) => {
        e.target.style.backgroundColor = isDark ? 'var(--mac-text-primary)' : '#f1f5f9';
        e.target.style.transform = 'scale(1)';
      }}
      title={isCollapsed ? 'Развернуть сайдбар' : 'Свернуть сайдбар'}
    >
      {isCollapsed ? <Menu size={20} /> : <X size={20} />}
    </button>
  );
};


SidebarToggle.propTypes = {
  ...(SidebarToggle.propTypes || {}),
  className: PropTypes.any,
  isCollapsed: PropTypes.any,
  onToggle: PropTypes.any,
};

export default SidebarToggle;

