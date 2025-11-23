import React from 'react';
import { ChevronRight, Home } from 'lucide-react';

const MacOSBreadcrumb = ({ 
  items = [], 
  separator = 'chevron',
  size = 'md',
  className,
  style,
  onItemClick
}) => {
  const sizeStyles = {
    sm: {
      fontSize: 'var(--mac-font-size-xs)',
      padding: '4px 0',
      gap: '4px'
    },
    md: {
      fontSize: 'var(--mac-font-size-sm)',
      padding: '6px 0',
      gap: '6px'
    },
    lg: {
      fontSize: 'var(--mac-font-size-base)',
      padding: '8px 0',
      gap: '8px'
    }
  };

  const currentSize = sizeStyles[size];

  const containerStyle = {
    display: 'flex',
    alignItems: 'center',
    padding: currentSize.padding,
    fontSize: currentSize.fontSize,
    color: 'var(--mac-text-secondary)',
    ...style
  };

  const itemStyle = (isLast) => ({
    color: isLast ? 'var(--mac-text-primary)' : 'var(--mac-text-secondary)',
    fontWeight: isLast ? 'var(--mac-font-weight-medium)' : 'var(--mac-font-weight-normal)',
    cursor: isLast ? 'default' : 'pointer',
    textDecoration: 'none',
    transition: 'color var(--mac-duration-normal) var(--mac-ease)',
    display: 'flex',
    alignItems: 'center'
  });

  const separatorStyle = {
    margin: `0 ${currentSize.gap}`,
    color: 'var(--mac-text-tertiary)',
    display: 'flex',
    alignItems: 'center'
  };

  const handleItemClick = (item, index) => {
    if (!item.disabled && onItemClick) {
      onItemClick(item, index);
    }
  };

  const handleMouseEnter = (e, isLast) => {
    if (!isLast) {
      e.target.style.color = 'var(--mac-text-primary)';
    }
  };

  const handleMouseLeave = (e, isLast) => {
    if (!isLast) {
      e.target.style.color = 'var(--mac-text-secondary)';
    }
  };

  const renderSeparator = () => {
    if (separator === 'chevron') {
      return (
        <ChevronRight 
          size={size === 'sm' ? 12 : size === 'md' ? 14 : 16} 
          style={separatorStyle} 
        />
      );
    } else if (separator === 'slash') {
      return <span style={separatorStyle}>/</span>;
    } else if (separator === 'arrow') {
      return <span style={separatorStyle}>→</span>;
    }
    return <span style={separatorStyle}>{separator}</span>;
  };

  const renderItem = (item, index) => {
    const isLast = index === items.length - 1;
    const isFirst = index === 0;
    
    return (
      <React.Fragment key={index}>
        <span
          onClick={() => handleItemClick(item, index)}
          onMouseEnter={(e) => handleMouseEnter(e, isLast)}
          onMouseLeave={(e) => handleMouseLeave(e, isLast)}
          style={itemStyle(isLast)}
          title={item.title}
        >
          {isFirst && item.showHome && (
            <Home 
              size={size === 'sm' ? 12 : size === 'md' ? 14 : 16} 
              style={{ marginRight: '4px' }} 
            />
          )}
          {item.icon && !isFirst && (
            <item.icon 
              size={size === 'sm' ? 12 : size === 'md' ? 14 : 16} 
              style={{ marginRight: '4px' }} 
            />
          )}
          {item.label}
        </span>
        {!isLast && renderSeparator()}
      </React.Fragment>
    );
  };

  if (items.length === 0) {
    return null;
  }

  return (
    <nav className={className} style={containerStyle} aria-label="breadcrumb">
      {items.map(renderItem)}
    </nav>
  );
};

export default MacOSBreadcrumb;
