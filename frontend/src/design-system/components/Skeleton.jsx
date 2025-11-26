import React, { forwardRef } from 'react';
import { createSkeletonStyles } from './utils';

const Skeleton = forwardRef(({
  width = '100%',
  height = '20px',
  variant = 'rectangular',
  animation = 'pulse',
  className = '',
  style = {},
  ...props
}, ref) => {
  const skeletonStyles = createSkeletonStyles(variant, animation);
  
  const finalStyles = {
    ...skeletonStyles,
    width,
    height,
    ...style
  };

  return (
    <div
      ref={ref}
      className={`design-system-skeleton ${className}`}
      style={finalStyles}
      {...props}
    />
  );
});

Skeleton.displayName = 'Skeleton';

// Компонент для скелетона текста
const TextSkeleton = forwardRef(({
  lines = 3,
  lineHeight = '1.5',
  spacing = '8px',
  className = '',
  style = {},
  ...props
}, ref) => {
  const lineWidths = ['100%', '80%', '60%', '90%', '70%'];

  const containerStyles = {
    display: 'flex',
    flexDirection: 'column',
    gap: spacing,
    ...style
  };

  return (
    <div
      ref={ref}
      className={`design-system-text-skeleton ${className}`}
      style={containerStyles}
      {...props}
    >
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton
          key={index}
          width={lineWidths[index % lineWidths.length]}
          height={lineHeight}
          variant="rectangular"
        />
      ))}
    </div>
  );
});

TextSkeleton.displayName = 'TextSkeleton';

// Компонент для скелетона карточки
const CardSkeleton = forwardRef(({
  className = '',
  style = {},
  ...props
}, ref) => {
  const cardStyles = {
    background: 'white',
    borderRadius: '12px',
    padding: '20px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
    ...style
  };

  return (
    <div
      ref={ref}
      className={`design-system-card-skeleton ${className}`}
      style={cardStyles}
      {...props}
    >
      <Skeleton width="60%" height="24px" style={{ marginBottom: '16px' }} />
      <TextSkeleton lines={3} />
      <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
        <Skeleton width="80px" height="32px" variant="rounded" />
        <Skeleton width="100px" height="32px" variant="rounded" />
      </div>
    </div>
  );
});

CardSkeleton.displayName = 'CardSkeleton';

// Компонент для скелетона таблицы
const TableSkeleton = forwardRef(({
  rows = 5,
  columns = 4,
  className = '',
  style = {},
  ...props
}, ref) => {
  const tableStyles = {
    background: 'white',
    borderRadius: '12px',
    padding: '20px',
    boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
    ...style
  };

  return (
    <div
      ref={ref}
      className={`design-system-table-skeleton ${className}`}
      style={tableStyles}
      {...props}
    >
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
});

TableSkeleton.displayName = 'TableSkeleton';

// Прикрепляем подкомпоненты к Skeleton
Skeleton.Text = TextSkeleton;
Skeleton.Card = CardSkeleton;
Skeleton.Table = TableSkeleton;

export default Skeleton;
