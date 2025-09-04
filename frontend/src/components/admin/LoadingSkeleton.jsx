import React from 'react';
import { useTheme } from '../../contexts/ThemeContext';

const LoadingSkeleton = ({ type = 'card', count = 1, className = '' }) => {
  const { theme, getColor, getSpacing } = useTheme();

  const skeletonStyle = {
    background: theme === 'light' 
      ? 'linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%)'
      : 'linear-gradient(90deg, #1e293b 25%, #334155 50%, #1e293b 75%)',
    backgroundSize: '200% 100%',
    animation: 'skeleton-loading 1.5s infinite',
    borderRadius: '12px'
  };

  const cardSkeletonStyle = {
    ...skeletonStyle,
    height: '140px',
    padding: getSpacing('lg'),
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between'
  };

  const tableSkeletonStyle = {
    ...skeletonStyle,
    height: '60px',
    marginBottom: getSpacing('sm')
  };

  const textSkeletonStyle = {
    ...skeletonStyle,
    height: '20px',
    marginBottom: getSpacing('sm')
  };

  const buttonSkeletonStyle = {
    ...skeletonStyle,
    height: '40px',
    width: '120px',
    borderRadius: '8px'
  };

  const renderCardSkeleton = () => (
    <div style={cardSkeletonStyle} className={className}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          <div style={{ ...textSkeletonStyle, width: '60%', height: '16px', marginBottom: getSpacing('xs') }} />
          <div style={{ ...textSkeletonStyle, width: '40%', height: '24px' }} />
        </div>
        <div style={{ 
          ...skeletonStyle, 
          width: '48px', 
          height: '48px', 
          borderRadius: '12px',
          flexShrink: 0
        }} />
      </div>
      <div style={{ ...textSkeletonStyle, width: '30%', height: '16px' }} />
    </div>
  );

  const renderTableSkeleton = () => (
    <div style={tableSkeletonStyle} className={className}>
      <div style={{ display: 'flex', gap: getSpacing('md'), alignItems: 'center', height: '100%' }}>
        <div style={{ ...textSkeletonStyle, width: '200px', height: '16px', margin: 0 }} />
        <div style={{ ...textSkeletonStyle, width: '150px', height: '16px', margin: 0 }} />
        <div style={{ ...textSkeletonStyle, width: '100px', height: '16px', margin: 0 }} />
        <div style={{ ...textSkeletonStyle, width: '80px', height: '16px', margin: 0 }} />
      </div>
    </div>
  );

  const renderButtonSkeleton = () => (
    <div style={buttonSkeletonStyle} className={className} />
  );

  const renderTextSkeleton = () => (
    <div style={textSkeletonStyle} className={className} />
  );

  const renderSkeleton = () => {
    switch (type) {
      case 'card':
        return renderCardSkeleton();
      case 'table':
        return renderTableSkeleton();
      case 'button':
        return renderButtonSkeleton();
      case 'text':
        return renderTextSkeleton();
      default:
        return renderCardSkeleton();
    }
  };

  return (
    <>
      <style>
        {`
          @keyframes skeleton-loading {
            0% {
              background-position: -200% 0;
            }
            100% {
              background-position: 200% 0;
            }
          }
        `}
      </style>
      {Array.from({ length: count }, (_, index) => (
        <div key={index}>
          {renderSkeleton()}
        </div>
      ))}
    </>
  );
};

export default LoadingSkeleton;
