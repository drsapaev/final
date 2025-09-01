import React from 'react';

const Skeleton = ({
  width = '100%',
  height = '20px',
  variant = 'rectangular',
  animation = 'pulse',
  className = '',
  style = {},
  ...props
}) => {
  // Варианты скелетонов
  const variants = {
    rectangular: {
      borderRadius: '4px'
    },
    circular: {
      borderRadius: '50%'
    },
    rounded: {
      borderRadius: '12px'
    }
  };

  // Анимации
  const animations = {
    pulse: {
      animation: 'skeleton-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
    },
    wave: {
      animation: 'skeleton-wave 1.6s linear infinite'
    }
  };

  // Базовые стили
  const baseStyles = {
    backgroundColor: '#e2e8f0',
    width,
    height,
    display: 'block',
    ...variants[variant],
    ...animations[animation]
  };

  return (
    <div
      style={{
        ...baseStyles,
        ...style
      }}
      className={className}
      {...props}
    />
  );
};

// Компонент для скелетона таблицы
const TableSkeleton = ({ rows = 5, columns = 4 }) => {
  return (
    <div style={{ padding: '16px' }}>
      {/* Заголовок таблицы */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '16px' }}>
        {Array.from({ length: columns }, (_, i) => (
          <Skeleton key={i} width="120px" height="16px" />
        ))}
      </div>
      
      {/* Строки таблицы */}
      {Array.from({ length: rows }, (_, rowIndex) => (
        <div key={rowIndex} style={{ display: 'flex', gap: '16px', marginBottom: '12px' }}>
          {Array.from({ length: columns }, (_, colIndex) => (
            <Skeleton key={colIndex} width="120px" height="20px" />
          ))}
        </div>
      ))}
    </div>
  );
};

// Компонент для скелетона карточки
const CardSkeleton = () => {
  return (
    <div style={{ padding: '24px' }}>
      <Skeleton width="60%" height="24px" style={{ marginBottom: '16px' }} />
      <Skeleton width="100%" height="16px" style={{ marginBottom: '8px' }} />
      <Skeleton width="80%" height="16px" style={{ marginBottom: '8px' }} />
      <Skeleton width="40%" height="16px" />
    </div>
  );
};

// Экспортируем все компоненты
Skeleton.Table = TableSkeleton;
Skeleton.Card = CardSkeleton;

export default Skeleton;
