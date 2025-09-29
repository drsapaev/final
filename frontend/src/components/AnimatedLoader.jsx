import React from 'react';
import { designTokens, getColor } from '../design-system';

const AnimatedLoader = ({
  size = 'md',
  color = 'primary',
  className = '',
  style = {}
}) => {
  const getSizeStyles = () => {
    const sizes = {
      sm: { width: '16px', height: '16px', borderWidth: '2px' },
      md: { width: '24px', height: '24px', borderWidth: '3px' },
      lg: { width: '32px', height: '32px', borderWidth: '4px' }
    };
    return sizes[size] || sizes.md;
  };

  const getColorStyles = () => {
    const colors = {
      primary: getColor('primary', 500),
      secondary: getColor('secondary', 500),
      success: getColor('success', 500),
      danger: getColor('danger', 500),
      warning: getColor('warning', 500),
      info: getColor('info', 500)
    };
    return colors[color] || colors.primary;
  };

  const loaderStyles = {
    display: 'inline-block',
    border: `${getSizeStyles().borderWidth} solid transparent`,
    borderTop: `${getSizeStyles().borderWidth} solid ${getColorStyles()}`,
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
    ...getSizeStyles(),
    ...style
  };

  return (
    <div
      className={`animated-loader ${className}`}
      style={loaderStyles}
      role="status"
      aria-label="Загрузка"
    />
  );
};

// Компонент для скелетона таблицы
const AnimatedTableSkeleton = ({
  rows = 5,
  columns = 4,
  className = '',
  style = {}
}) => {
  const tableStyles = {
    background: 'white',
    borderRadius: '12px',
    padding: '20px',
    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    ...style
  };

  const skeletonRowStyles = {
    display: 'flex',
    gap: '16px',
    marginBottom: '12px',
    alignItems: 'center'
  };

  const skeletonCellStyles = {
    backgroundColor: getColor('secondary', 200),
    borderRadius: '8px',
    animation: 'skeleton-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
    height: '20px'
  };

  return (
    <div
      className={`animated-table-skeleton ${className}`}
      style={tableStyles}
    >
      {/* Заголовок таблицы */}
      <div style={skeletonRowStyles}>
        {Array.from({ length: columns }, (_, i) => (
          <div
            key={i}
            style={{
              ...skeletonCellStyles,
              width: i === 0 ? '60px' : '120px',
              height: '16px'
            }}
          />
        ))}
      </div>
      
      {/* Строки таблицы */}
      {Array.from({ length: rows }, (_, rowIndex) => (
        <div key={rowIndex} style={skeletonRowStyles}>
          {Array.from({ length: columns }, (_, colIndex) => (
            <div
              key={colIndex}
              style={{
                ...skeletonCellStyles,
                width: colIndex === 0 ? '60px' : '120px'
              }}
            />
          ))}
        </div>
      ))}
    </div>
  );
};

// Компонент для скелетона карточки
const AnimatedCardSkeleton = ({
  className = '',
  style = {}
}) => {
  const cardStyles = {
    background: 'white',
    borderRadius: '12px',
    padding: '20px',
    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    ...style
  };

  const skeletonStyles = {
    backgroundColor: getColor('secondary', 200),
    borderRadius: '8px',
    animation: 'skeleton-pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
  };

  return (
    <div
      className={`animated-card-skeleton ${className}`}
      style={cardStyles}
    >
      <div
        style={{
          ...skeletonStyles,
          width: '60%',
          height: '24px',
          marginBottom: '16px'
        }}
      />
      <div
        style={{
          ...skeletonStyles,
          width: '100%',
          height: '16px',
          marginBottom: '8px'
        }}
      />
      <div
        style={{
          ...skeletonStyles,
          width: '80%',
          height: '16px',
          marginBottom: '8px'
        }}
      />
      <div
        style={{
          ...skeletonStyles,
          width: '60%',
          height: '16px',
          marginBottom: '16px'
        }}
      />
      <div style={{ display: 'flex', gap: '12px' }}>
        <div
          style={{
            ...skeletonStyles,
            width: '80px',
            height: '32px'
          }}
        />
        <div
          style={{
            ...skeletonStyles,
            width: '100px',
            height: '32px'
          }}
        />
      </div>
    </div>
  );
};

// Прикрепляем подкомпоненты к AnimatedLoader
AnimatedLoader.TableSkeleton = AnimatedTableSkeleton;
AnimatedLoader.CardSkeleton = AnimatedCardSkeleton;

export default AnimatedLoader;

