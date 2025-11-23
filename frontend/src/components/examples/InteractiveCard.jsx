import React from 'react';
import { Card } from '../ui/native';
import { useTheme } from '../../contexts/ThemeContext';
import { useHover } from '../../hooks/useUtils';

/**
 * Пример интерактивной карточки с эффектами наведения
 */
const InteractiveCard = ({
  children,
  onClick,
  className = '',
  style = {},
  ...props
}) => {
  const { getColor, getSpacing, getShadow, getBorderRadius } = useTheme();
  const { ref, isHovered } = useHover();

  const cardStyle = {
    position: 'relative',
    overflow: 'hidden',
    transition: 'all 0.3s ease',
    cursor: onClick ? 'pointer' : 'default',
    transform: isHovered ? 'translateY(-4px)' : 'translateY(0)',
    boxShadow: isHovered ? getShadow('lg') : getShadow('md'),
    borderColor: isHovered ? getColor('primary', 200) : getColor('border'),
    backgroundColor: getColor('surface'),
    ...style
  };

  const overlayStyle = {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: `linear-gradient(135deg, ${getColor('primary', 500)}15 0%, ${getColor('primary', 600)}05 100%)`,
    opacity: isHovered ? 1 : 0,
    transition: 'opacity 0.3s ease',
    pointerEvents: 'none',
    borderRadius: getBorderRadius('md')
  };

  return (
    <Card
      ref={ref}
      onClick={onClick}
      className={className}
      style={{
        padding: getSpacing('lg'),
        borderRadius: getBorderRadius('lg'),
        ...cardStyle
      }}
      {...props}
    >
      {/* Overlay эффект */}
      <div style={overlayStyle} />

      {/* Основное содержимое */}
      <div style={{ position: 'relative', zIndex: 1 }}>
        {children}
      </div>

      {/* Эффект свечения при наведении */}
      {isHovered && (
        <div style={{
          position: 'absolute',
          top: '-2px',
          left: '-2px',
          right: '-2px',
          bottom: '-2px',
          background: `linear-gradient(135deg, ${getColor('primary', 400)}, ${getColor('primary', 600)})`,
          borderRadius: getBorderRadius('lg'),
          zIndex: -1,
          opacity: 0.1,
          filter: 'blur(8px)'
        }} />
      )}
    </Card>
  );
};

/**
 * Пример интерактивного элемента списка
 */
export const InteractiveListItem = ({
  title,
  subtitle,
  icon,
  onClick,
  ...props
}) => {
  const { getColor, getSpacing, getFontSize } = useTheme();
  const { ref, isHovered } = useHover();

  return (
    <div
      ref={ref}
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: getSpacing('md'),
        borderRadius: '8px',
        backgroundColor: isHovered ? getColor('primary', 50) : getColor('surface'),
        border: `1px solid ${isHovered ? getColor('primary', 200) : getColor('border')}`,
        cursor: onClick ? 'pointer' : 'default',
        transition: 'all 0.2s ease',
        transform: isHovered ? 'scale(1.02)' : 'scale(1)',
        boxShadow: isHovered ? getShadow('sm') : 'none'
      }}
      {...props}
    >
      {/* Иконка */}
      {icon && (
        <div style={{
          width: '40px',
          height: '40px',
          borderRadius: '50%',
          backgroundColor: isHovered ? getColor('primary', 100) : getColor('secondary', 100),
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginRight: getSpacing('md'),
          transition: 'all 0.2s ease'
        }}>
          {icon}
        </div>
      )}

      {/* Текст */}
      <div style={{ flex: 1 }}>
        <div style={{
          fontSize: getFontSize('base'),
          fontWeight: '600',
          color: getColor('text'),
          marginBottom: getSpacing('xs')
        }}>
          {title}
        </div>
        {subtitle && (
          <div style={{
            fontSize: getFontSize('sm'),
            color: getColor('textSecondary')
          }}>
            {subtitle}
          </div>
        )}
      </div>

      {/* Стрелка */}
      <div style={{
        color: isHovered ? getColor('primary', 500) : getColor('textSecondary'),
        transition: 'all 0.2s ease',
        transform: isHovered ? 'translateX(4px)' : 'translateX(0)'
      }}>
        →
      </div>
    </div>
  );
};

export default InteractiveCard;
