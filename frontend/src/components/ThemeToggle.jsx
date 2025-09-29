import React from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

const ThemeToggle = ({ size = 'md', className = '', style = {} }) => {
  const { theme, isDark, toggleTheme, getColor, getSpacing } = useTheme();

  const sizes = {
    sm: { size: 16, padding: getSpacing('xs') },
    md: { size: 20, padding: getSpacing('sm') },
    lg: { size: 24, padding: getSpacing('md') }
  };

  const { size: iconSize, padding } = sizes[size] || sizes.md;

  const buttonStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding,
    borderRadius: '50%',
    border: `1px solid ${isDark ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.1)'}`,
    background: isDark 
      ? 'rgba(255, 255, 255, 0.1)' 
      : 'rgba(255, 255, 255, 0.8)',
    color: isDark ? '#f8fafc' : '#1e293b',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    backdropFilter: 'blur(10px)',
    ...style
  };

  const hoverStyle = {
    transform: 'scale(1.05)',
    background: isDark 
      ? 'rgba(255, 255, 255, 0.2)' 
      : 'rgba(255, 255, 255, 0.9)',
    boxShadow: isDark
      ? '0 4px 20px rgba(0, 0, 0, 0.3)'
      : '0 4px 20px rgba(0, 0, 0, 0.1)'
  };

  return (
    <button
      onClick={toggleTheme}
      className={`clinic-theme-toggle ${className}`}
      style={buttonStyle}
      onMouseEnter={(e) => Object.assign(e.target.style, hoverStyle)}
      onMouseLeave={(e) => Object.assign(e.target.style, buttonStyle)}
      title={`Переключить на ${isDark ? 'светлую' : 'темную'} тему`}
      aria-label={`Переключить на ${isDark ? 'светлую' : 'темную'} тему`}
    >
      {isDark ? <Sun size={iconSize} /> : <Moon size={iconSize} />}
    </button>
  );
};

export default ThemeToggle;

