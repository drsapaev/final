import React from 'react';

const LoadingSkeleton = ({ 
  type = 'default', 
  count = 1, 
  className = '',
  width,
  height,
  ...props 
}) => {
  const renderSkeleton = () => {
    switch (type) {
      case 'card':
        return (
          <div 
            className={`p-4 rounded-lg animate-pulse ${className}`}
            style={{ 
              background: 'var(--bg-primary)',
              border: '1px solid var(--border-color)',
              width: width || '100%',
              height: height || '120px'
            }}
            {...props}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="h-4 bg-gray-200 rounded w-24" style={{ background: 'var(--bg-secondary)' }}></div>
              <div className="w-8 h-8 bg-gray-200 rounded" style={{ background: 'var(--bg-secondary)' }}></div>
            </div>
            <div className="h-6 bg-gray-200 rounded w-16 mb-2" style={{ background: 'var(--bg-secondary)' }}></div>
            <div className="h-3 bg-gray-200 rounded w-12" style={{ background: 'var(--bg-secondary)' }}></div>
          </div>
        );
        
      case 'table':
        return (
          <div className={`animate-pulse ${className}`} {...props}>
            <div className="space-y-3">
              {Array.from({ length: count }).map((_, i) => (
                <div key={i} className="flex items-center space-x-4 p-3">
                  <div className="w-8 h-8 bg-gray-200 rounded-full" style={{ background: 'var(--bg-secondary)' }}></div>
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-gray-200 rounded w-3/4" style={{ background: 'var(--bg-secondary)' }}></div>
                    <div className="h-3 bg-gray-200 rounded w-1/2" style={{ background: 'var(--bg-secondary)' }}></div>
                  </div>
                  <div className="h-6 bg-gray-200 rounded w-16" style={{ background: 'var(--bg-secondary)' }}></div>
                </div>
              ))}
            </div>
          </div>
        );
        
      case 'text':
        return (
          <div className={`animate-pulse ${className}`} {...props}>
            <div className="space-y-2">
              {Array.from({ length: count }).map((_, i) => (
                <div 
                  key={i} 
                  className="h-4 bg-gray-200 rounded" 
                  style={{ 
                    background: 'var(--bg-secondary)',
                    width: width || (i === count - 1 ? '60%' : '100%')
                  }}
                ></div>
              ))}
            </div>
          </div>
        );
        
      case 'button':
        return (
          <div 
            className={`h-10 bg-gray-200 rounded animate-pulse ${className}`}
            style={{ 
              background: 'var(--bg-secondary)',
              width: width || '120px'
            }}
            {...props}
          ></div>
        );
        
      case 'chart':
        return (
          <div 
            className={`animate-pulse ${className}`}
            style={{ 
              background: 'var(--bg-secondary)',
              width: width || '100%',
              height: height || '200px',
              borderRadius: '8px'
            }}
            {...props}
          >
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div className="w-12 h-12 bg-gray-300 rounded-full mx-auto mb-2" style={{ background: 'var(--bg-primary)' }}></div>
                <div className="h-4 bg-gray-300 rounded w-24 mx-auto" style={{ background: 'var(--bg-primary)' }}></div>
              </div>
            </div>
          </div>
        );
        
      default:
        return (
          <div 
            className={`animate-pulse ${className}`}
            style={{ 
              background: 'var(--bg-secondary)',
              width: width || '100%',
              height: height || '20px',
              borderRadius: '4px'
            }}
            {...props}
          ></div>
        );
    }
  };

  if (count === 1) {
    return renderSkeleton();
  }

  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i}>
          {renderSkeleton()}
        </div>
      ))}
    </div>
  );
};

export default LoadingSkeleton;

