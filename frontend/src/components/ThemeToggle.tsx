import { useState } from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import PropTypes from 'prop-types';
import type { CSSProperties } from 'react';

type ToggleSize = 'sm' | 'md' | 'lg';

interface ThemeToggleProps {
  size?: ToggleSize;
  className?: string;
  style?: CSSProperties;
}

const ThemeToggle = ({ size = 'md', className = '', style = {} }: ThemeToggleProps) => {
  const { isDark, toggleTheme } = useTheme();
  const [isHovered, setIsHovered] = useState(false);

  const sizes: Record<ToggleSize, { iconSize: number; padding: string }> = {
    sm: { iconSize: 16, padding: 'var(--mac-spacing-1)' },
    md: { iconSize: 20, padding: 'var(--mac-spacing-2)' },
    lg: { iconSize: 24, padding: 'var(--mac-spacing-3)' }
  };

  const { iconSize, padding } = sizes[size] || sizes.md;

  const buttonStyle: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding,
    borderRadius: '50%',
    border: '1px solid var(--mac-border)',
    background: 'var(--mac-bg-primary)',
    color: 'var(--mac-text-primary)',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    backdropFilter: 'blur(10px)',
    ...style
  };

  const hoverStyle: CSSProperties = {
    transform: 'scale(1.05)',
    background: 'var(--mac-bg-secondary)',
    boxShadow: 'var(--mac-shadow-md)',
  };

  const activeStyle: CSSProperties = {
    ...buttonStyle,
    ...(isHovered ? hoverStyle : {})
  };

  return (
    <button
      onClick={toggleTheme}
      className={`clinic-theme-toggle ${className}`}
      style={activeStyle}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      title={`Переключить на ${isDark ? 'светлую' : 'темную'} тему`}
      aria-label={`Переключить на ${isDark ? 'светлую' : 'темную'} тему`}>
      {isDark ? <Sun size={iconSize} /> : <Moon size={iconSize} />}
    </button>
  );
};

ThemeToggle.propTypes = {
  className: PropTypes.string,
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  style: PropTypes.object,
};

export default ThemeToggle;
