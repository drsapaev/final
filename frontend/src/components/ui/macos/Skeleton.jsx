import React from 'react';

// Simple macOS-style Skeleton placeholder
const Skeleton = ({ width = '100%', height = 16, variant = 'rect', style = {}, ...props }) => {
  const radius = variant === 'circle' ? '50%' : 8;
  const sizeStyle = variant === 'circle'
    ? { width: height, height }
    : { width, height };

  return (
    <div
      style={{
        background: 'linear-gradient(90deg, rgba(0,0,0,0.06), rgba(0,0,0,0.10), rgba(0,0,0,0.06))',
        backgroundSize: '200% 100%',
        animation: 'mac-skeleton 1.2s ease-in-out infinite',
        borderRadius: radius,
        ...sizeStyle,
        ...style
      }}
      {...props}
    />
  );
};

export default Skeleton;


