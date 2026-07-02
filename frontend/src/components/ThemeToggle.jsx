import { useState } from 'react';
import { Sun, Moon } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import { colors } from '../theme/tokens';
import PropTypes from 'prop-types';

const ThemeToggle = ({ size = 'md', className = '', style = {} }) => {
  const { isDark, toggleTheme, getSpacing } = useTheme();
  const [isHovered, setIsHovered] = useState(false);
  const [isFocused, setIsFocused] = useState(false);

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
    border: `1px solid ${isDark ? colors.border.medium : colors.border.light}`,
    background: isDark ?
    colors.semantic.surface.card :
    colors.semantic.surface.card,
    color: isDark ? colors.semantic.text.primary : colors.semantic.text.primary,
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    backdropFilter: 'blur(10px)',
    ...style
  };

  const hoverStyle = {
    transform: 'scale(1.05)',
    background: isDark ?
    colors.semantic.surface.hover :
    colors.semantic.surface.hover,
    boxShadow: isDark ?
    `0 4px 20px ${colors.semantic.surface.overlay}` :
    `0 4px 20px ${colors.semantic.surface.overlay}`
  };
  const activeStyle = isHovered || isFocused ? { ...buttonStyle, ...hoverStyle } : buttonStyle;

  return (
    <button
      onClick={toggleTheme}
      className={`clinic-theme-toggle ${className}`}
      style={activeStyle}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onFocus={() => setIsFocused(true)}
      onBlur={() => setIsFocused(false)}
      title={`Переключить на ${isDark ? 'светлую' : 'темную'} тему`}
      aria-label={`Переключить на ${isDark ? 'светлую' : 'темную'} тему`}>
      
      {isDark ? <Sun size={iconSize} /> : <Moon size={iconSize} />}
    </button>);

};


ThemeToggle.propTypes = {
  ...(ThemeToggle.propTypes || {}),
  className: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
};

export default ThemeToggle;