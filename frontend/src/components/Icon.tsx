import type { CSSProperties, ReactNode } from 'react';
import iconsMap from '../assets/iconsMap';

import logger from '../utils/logger';

interface IconProps {
  name: string;
  size?: number;
  color?: string;
  className?: string;
  style?: CSSProperties;
  [key: string]: unknown;
}

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
}: IconProps) => {
  // Получаем компонент иконки из iconsMap
  const IconComponent = (iconsMap as Record<string, React.ComponentType<{ size?: number; color?: string; className?: string; style?: CSSProperties }>>)[name];

  // Если иконка не найдена, возвращаем fallback
  if (!IconComponent) {
    logger.warn(`Иконка "${name}" не найдена в iconsMap`);
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
