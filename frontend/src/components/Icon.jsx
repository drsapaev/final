import React from 'react';
import iconsMap from '../assets/iconsMap';

/**
 * Универсальный компонент иконок
 * Использует глобальный набор иконок из iconsMap.js
 */
const Icon = ({ 
  name, 
  size = 24, 
  color = 'currentColor', 
  className = '', 
  style = {},
  ...props 
}) => {
  // Получаем компонент иконки из iconsMap
  const IconComponent = iconsMap[name];
  
  // Если иконка не найдена, возвращаем fallback
  if (!IconComponent) {
    console.warn(`Иконка "${name}" не найдена в iconsMap`);
    return (
      <span 
        className={className}
        style={{ 
          fontSize: `${size}px`, 
          color,
          ...style 
        }}
        {...props}
      >
        ❓
      </span>
    );
  }
  
  // Рендерим найденную иконку
  return (
    <IconComponent
      size={size}
      color={color}
      className={className}
      style={style}
      {...props}
    />
  );
};

export default Icon;
