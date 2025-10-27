import React from 'react';

const MacOSLoadingSkeleton = ({
  variant = 'text',
  width = '100%',
  height = '20px',
  lines = 1,
  spacing = '8px',
  animation = true,
  className,
  style
}) => {
  const baseStyle = {
    background: 'var(--mac-bg-tertiary)',
    borderRadius: 'var(--mac-radius-sm)',
    animation: animation ? 'skeleton-pulse 1.5s ease-in-out infinite' : 'none',
    ...style
  };

  const textStyle = {
    ...baseStyle,
    height: height,
    width: width
  };

  const circleStyle = {
    ...baseStyle,
    width: height,
    height: height,
    borderRadius: '50%'
  };

  const rectStyle = {
    ...baseStyle,
    width: width,
    height: height
  };

  const containerStyle = {
    display: 'flex',
    flexDirection: 'column',
    gap: spacing
  };

  const renderTextSkeleton = () => {
    if (lines === 1) {
      return <div className={className} style={textStyle} />;
    }

    return (
      <div className={className} style={containerStyle}>
        {Array.from({ length: lines }, (_, index) => (
          <div
            key={index}
            style={{
              ...textStyle,
              width: index === lines - 1 ? '60%' : '100%'
            }}
          />
        ))}
      </div>
    );
  };

  const renderCircleSkeleton = () => (
    <div className={className} style={circleStyle} />
  );

  const renderRectSkeleton = () => (
    <div className={className} style={rectStyle} />
  );

  const renderCardSkeleton = () => (
    <div className={className} style={containerStyle}>
      <div style={{ ...rectStyle, height: '16px', width: '60%' }} />
      <div style={{ ...rectStyle, height: '24px', width: '80%' }} />
      <div style={{ ...rectStyle, height: '14px', width: '40%' }} />
    </div>
  );

  const renderTableSkeleton = () => (
    <div className={className} style={containerStyle}>
      {/* Header */}
      <div style={{ display: 'flex', gap: spacing }}>
        {Array.from({ length: 4 }, (_, index) => (
          <div
            key={index}
            style={{ ...rectStyle, height: '16px', flex: 1 }}
          />
        ))}
      </div>
      {/* Rows */}
      {Array.from({ length: 3 }, (_, rowIndex) => (
        <div key={rowIndex} style={{ display: 'flex', gap: spacing }}>
          {Array.from({ length: 4 }, (_, colIndex) => (
            <div
              key={colIndex}
              style={{ ...rectStyle, height: '14px', flex: 1 }}
            />
          ))}
        </div>
      ))}
    </div>
  );

  const renderListSkeleton = () => (
    <div className={className} style={containerStyle}>
      {Array.from({ length: lines }, (_, index) => (
        <div
          key={index}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: spacing,
            padding: '12px 0'
          }}
        >
          <div style={{ ...circleStyle, width: '20px', height: '20px' }} />
          <div style={{ ...textStyle, height: '16px', flex: 1 }} />
        </div>
      ))}
    </div>
  );

  switch (variant) {
    case 'text':
      return renderTextSkeleton();
    case 'circle':
      return renderCircleSkeleton();
    case 'rect':
      return renderRectSkeleton();
    case 'card':
      return renderCardSkeleton();
    case 'table':
      return renderTableSkeleton();
    case 'list':
      return renderListSkeleton();
    default:
      return renderTextSkeleton();
  }
};

// CSS анимация для скелетона
const skeletonStyles = `
  @keyframes skeleton-pulse {
    0% {
      opacity: 1;
    }
    50% {
      opacity: 0.4;
    }
    100% {
      opacity: 1;
    }
  }
`;

// Добавляем стили в head если их еще нет
if (typeof document !== 'undefined' && !document.getElementById('skeleton-styles')) {
  const styleSheet = document.createElement('style');
  styleSheet.id = 'skeleton-styles';
  styleSheet.textContent = skeletonStyles;
  document.head.appendChild(styleSheet);
}

export default MacOSLoadingSkeleton;
