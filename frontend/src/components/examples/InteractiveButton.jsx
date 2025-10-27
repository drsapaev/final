import React, { useState } from 'react';
import { Button } from '../ui/native';
import { useTheme } from '../../contexts/ThemeContext';
import { useHover } from '../../hooks/useUtils';

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
        backgroundColor: isPressed
          ? getColor('primary', 700)
          : isHovered
          ? getColor('primary', 600)
          : getColor('primary', 500),
        color: 'white',
        border: 'none'
      };
    }

    if (variant === 'outline') {
      return {
        ...baseStyle,
        backgroundColor: isPressed
          ? getColor('primary', 50)
          : isHovered
          ? getColor('primary', 50)
          : 'transparent',
        color: isPressed
          ? getColor('primary', 700)
          : isHovered
          ? getColor('primary', 600)
          : getColor('primary', 500),
        border: `1px solid ${isPressed
          ? getColor('primary', 300)
          : isHovered
          ? getColor('primary', 400)
          : getColor('primary', 200)}`
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
        borderRadius: '6px',
        fontSize: getSpacing('base'),
        fontWeight: '500',
        cursor: 'pointer',
        outline: 'none',
        ...getButtonStyle(),
        ...props.style
      }}
      {...props}
    >
      {/* Эффект пульсации при нажатии */}
      {isPressed && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          width: '100px',
          height: '100px',
          backgroundColor: 'rgba(255, 255, 255, 0.3)',
          borderRadius: '50%',
          transform: 'translate(-50%, -50%) scale(0)',
          animation: 'ripple 0.6s linear',
          pointerEvents: 'none'
        }} />
      )}

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
    </button>
  );
};

export default InteractiveButton;
