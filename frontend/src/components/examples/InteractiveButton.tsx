// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useState } from 'react';

import { useTheme } from '../../contexts/ThemeContext';
import { useHover } from '../../hooks/useUtils';
import PropTypes from 'prop-types';

/**
 * Пример интерактивной кнопки с эффектами наведения
 */
const InteractiveButton = ({
  children,
  variant = 'primary',
  size = 'md',
  onClick,
  ...props
}) => {
  const { getColor, getSpacing, getShadow } = useTheme();
  void size;
  const { ref, isHovered } = useHover();
  const [isPressed, setIsPressed] = useState(false);

  const handleMouseDown = () => setIsPressed(true);
  const handleMouseUp = () => setIsPressed(false);
  const handleMouseLeave = () => setIsPressed(false);

  const getButtonStyle = () => {
    const baseStyle = {
      position: 'relative',
      overflow: 'hidden',
      transition: 'all 0.2s ease',
      transform: isPressed ? 'scale(0.98)' : isHovered ? 'scale(1.02)' : 'scale(1)',
      boxShadow: isHovered ? getShadow('md') : getShadow('sm')
    };

    if (variant === 'primary') {
      return {
        ...baseStyle,
        backgroundColor: isPressed ?
        getColor('primary', 700) :
        isHovered ?
        getColor('primary', 600) :
        getColor('primary', 500),
        color: 'white',
        border: 'none'
      };
    }

    if (variant === 'outline') {
      return {
        ...baseStyle,
        backgroundColor: isPressed ?
        getColor('primary', 50) :
        isHovered ?
        getColor('primary', 50) :
        'transparent',
        color: isPressed ?
        getColor('primary', 700) :
        isHovered ?
        getColor('primary', 600) :
        getColor('primary', 500),
        border: `1px solid ${isPressed ?
        getColor('primary', 300) :
        isHovered ?
        getColor('primary', 400) :
        getColor('primary', 200)}`
      };
    }

    return baseStyle;
  };

  return (
    <button
      ref={ref}
      onClick={onClick}
      onMouseDown={handleMouseDown}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseLeave}
      style={{
        padding: getSpacing('sm') + ' ' + getSpacing('lg'),
        borderRadius: 'var(--mac-radius-sm)',
        fontSize: getSpacing('base'),
        fontWeight: 'var(--mac-font-weight-medium)',
        cursor: 'pointer',
        outline: 'none',
        ...getButtonStyle(),
        ...props.style
      }}
      {...props}>
      
      {/* Эффект пульсации при нажатии */}
      {isPressed &&
      <div style={{
        position: 'absolute',
        top: '50%',
        left: '50%',
        width: '100px',
        height: '100px',
        backgroundColor: 'color-mix(in srgb, white, transparent 70%)',
        borderRadius: '50%',
        transform: 'translate(-50%, -50%) scale(0)',
        animation: 'ripple 0.6s linear',
        pointerEvents: 'none'
      }} />
      }

      {/* Содержимое кнопки */}
      <span style={{ position: 'relative', zIndex: 1 }}>
        {children}
      </span>

      <style>
        {`
          @keyframes ripple {
            to {
              transform: translate(-50%, -50%) scale(4);
              opacity: 0;
            }
          }
        `}
      </style>
    </button>);

};


InteractiveButton.propTypes = {
  ...(InteractiveButton.propTypes || {}),
  children: PropTypes.any,
  onClick: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
  variant: PropTypes.any,
};

export default InteractiveButton;
