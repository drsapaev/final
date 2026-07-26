import React from 'react';
import type { CSSProperties, MouseEvent, ReactNode } from 'react';
import { ChevronRight, Home } from 'lucide-react';

interface BreadcrumbItem {
  label: ReactNode;
  href?: string;
  icon?: ReactNode;
  [key: string]: unknown;
}

interface MacOSBreadcrumbProps {
  items?: BreadcrumbItem[];
  separator?: 'chevron' | 'slash' | 'arrow' | string;
  size?: 'sm' | 'md' | 'lg' | string;
  className?: string;
  style?: CSSProperties;
  onItemClick?: (item: BreadcrumbItem, index: number) => void;
}

const MacOSBreadcrumb = ({
  items = [],
  separator = 'chevron',
  size = 'md',
  className,
  style,
  onItemClick
}: MacOSBreadcrumbProps) => {
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

  const currentSize = sizeStyles[size as 'sm' | 'md' | 'lg'];

  const containerStyle = {
    display: 'flex',
    alignItems: 'center',
    padding: currentSize.padding,
    fontSize: currentSize.fontSize,
    color: 'var(--mac-text-secondary)',
    ...style
  };

  const itemStyle = (isLast: boolean) => ({
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

  const handleItemClick = (item: BreadcrumbItem, index: number) => {
    if (!item.disabled && onItemClick) {
      onItemClick(item, index);
    }
  };

  const handleMouseEnter = (e: MouseEvent<HTMLElement>, isLast: boolean) => {
    if (!isLast) {
      (e.target as HTMLElement).style.color = 'var(--mac-text-primary)';
    }
  };

  const handleMouseLeave = (e: MouseEvent<HTMLElement>, isLast: boolean) => {
    if (!isLast) {
      (e.target as HTMLElement).style.color = 'var(--mac-text-secondary)';
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

  const renderItem = (item: BreadcrumbItem, index: number) => {
    const isLast = index === items.length - 1;
    const isFirst = index === 0;
    const isClickable = !isLast && !item.disabled && Boolean(onItemClick);
    const itemContent = (
      <>
        {isFirst && item.showHome && (
          <Home
            size={size === 'sm' ? 12 : size === 'md' ? 14 : 16}
            style={{ marginRight: '4px' }}
          />
        )}
        {item.icon && !isFirst && (
          <span style={{ display: 'inline-flex', marginRight: '4px' }}>{item.icon}</span>
        )}
        {item.label}
      </>
    );
    
    return (
      <React.Fragment key={index}>
        {isClickable ? (
          <button
            type="button"
            onClick={() => handleItemClick(item, index)}
            onMouseEnter={(e: React.MouseEvent<HTMLElement>) => handleMouseEnter(e, isLast)}
            onMouseLeave={(e: React.MouseEvent<HTMLElement>) => handleMouseLeave(e, isLast)}
            style={{
              ...itemStyle(isLast),
              border: 'none',
              background: 'transparent',
              padding: 0
            }}
            title={item.title as string | undefined}
          >
            {itemContent}
          </button>
        ) : (
          <span style={itemStyle(isLast)} title={item.title as string | undefined}>
            {itemContent}
          </span>
        )}
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
