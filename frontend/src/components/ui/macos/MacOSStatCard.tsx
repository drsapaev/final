import React, { useState, type ReactNode, type CSSProperties } from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import PropTypes from 'prop-types';

interface MacOSStatCardProps {
  title?: ReactNode;
  value?: ReactNode;
  subtitle?: ReactNode;
  icon?: React.ComponentType<any> | ReactNode;
  trend?: ReactNode;
  trendType?: 'positive' | 'negative' | 'neutral' | string;
  trendLabel?: ReactNode;
  color?: string;
  size?: 'sm' | 'md' | 'lg' | string;
  variant?: string;
  loading?: boolean;
  onClick?: () => void;
  className?: string;
  style?: CSSProperties;
  detail?: ReactNode;
  trendColor?: string;
  iconColor?: string;
}

const MacOSStatCard = ({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  trendType = 'neutral', // positive, negative, neutral
  trendLabel,
  color = 'blue',
  size = 'md',
  variant = 'default',
  loading = false,
  onClick,
  className,
  style
}: MacOSStatCardProps) => {
  const [isHovered, setIsHovered] = useState(false);
  const [isFocused, setIsFocused] = useState(false);

  const sizeStyles = {
    sm: {
      padding: '12px',
      fontSize: 'var(--mac-font-size-xs)',
      valueFontSize: 'var(--mac-font-size-lg)',
      iconSize: 20
    },
    md: {
      padding: '16px',
      fontSize: 'var(--mac-font-size-sm)',
      valueFontSize: 'var(--mac-font-size-xl)',
      iconSize: 24
    },
    lg: {
      padding: '20px',
      fontSize: 'var(--mac-font-size-base)',
      valueFontSize: 'var(--mac-font-size-2xl)',
      iconSize: 28
    }
  };

  const variantStyles = {
    default: {
      background: 'var(--mac-bg-primary)',
      border: '1px solid var(--mac-border)',
      borderRadius: 'var(--mac-radius-lg)'
    },
    filled: {
      background: 'var(--mac-bg-secondary)',
      border: 'none',
      borderRadius: 'var(--mac-radius-lg)'
    },
    elevated: {
      background: 'var(--mac-bg-primary)',
      border: '1px solid var(--mac-border)',
      borderRadius: 'var(--mac-radius-lg)',
      boxShadow: 'var(--mac-shadow-sm)'
    }
  };

  const colorStyles = {
    blue: 'var(--mac-accent-blue)',
    green: 'var(--mac-success)',
    orange: 'var(--mac-warning)',
    red: 'var(--mac-error)',
    purple: 'var(--mac-accent-purple)',
    gray: 'var(--mac-text-secondary)'
  };

  const trendStyles: Record<string, { color: string; icon: React.ComponentType<any> }> = {
    positive: {
      color: 'var(--mac-success)',
      icon: TrendingUp
    },
    negative: {
      color: 'var(--mac-error)',
      icon: TrendingDown
    },
    neutral: {
      color: 'var(--mac-text-secondary)',
      icon: Minus
    }
  };

  const currentSize = sizeStyles[size];
  const currentVariant = variantStyles[variant];
  const currentColor = colorStyles[color] || colorStyles.blue;
  const currentTrend = trendStyles[trendType];

  const cardStyle: CSSProperties = {
    padding: currentSize.padding,
    background: currentVariant.background,
    border: currentVariant.border,
    borderRadius: currentVariant.borderRadius,
    boxShadow: (isHovered || isFocused) && onClick ? 'var(--mac-shadow-md)' : (currentVariant.boxShadow || 'none'),
    cursor: onClick ? 'pointer' : 'default',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    position: 'relative',
    overflow: 'hidden',
    transform: (isHovered || isFocused) && onClick ? 'translateY(-2px)' : 'translateY(0)',
    outline: isFocused ? '2px solid var(--mac-accent-blue)' : 'none',
    outlineOffset: '2px',
    ...style
  };

  const headerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '8px'
  };

  const titleStyle: CSSProperties = {
    fontSize: currentSize.fontSize,
    fontWeight: 'var(--mac-font-weight-medium)',
    color: 'var(--mac-text-secondary)',
    margin: 0
  };

  const valueStyle: CSSProperties = {
    fontSize: currentSize.valueFontSize,
    fontWeight: 'var(--mac-font-weight-bold)',
    color: 'var(--mac-text-primary)',
    margin: '4px 0',
    lineHeight: 1.2
  };

  const subtitleStyle: CSSProperties = {
    fontSize: 'var(--mac-font-size-xs)',
    color: 'var(--mac-text-tertiary)',
    margin: 0
  };

  const trendStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    marginTop: '8px',
    fontSize: 'var(--mac-font-size-xs)',
    fontWeight: 'var(--mac-font-weight-medium)',
    color: currentTrend.color
  };

  const iconStyle: CSSProperties = {
    width: currentSize.iconSize,
    height: currentSize.iconSize,
    color: currentColor,
    flexShrink: 0
  };

  const handleClick = () => {
    if (onClick) {
      onClick();
    }
  };
  const handleKeyDown = (e) => {
    if ((e.key === 'Enter' || e.key === ' ') && onClick) {
      e.preventDefault();
      onClick();
    }
  };

  const handleMouseEnter = () => {
    setIsHovered(true);
  };

  const handleMouseLeave = () => {
    setIsHovered(false);
  };

  const renderTrend = () => {
    if (!trend) return null;

    const TrendIcon = currentTrend.icon;
    
    return (
      <div style={trendStyle}>
        {TrendIcon && <TrendIcon size={12} style={{ marginRight: '4px' }} />}
        <span>{trend}</span>
        {trendLabel && (
          <span style={{ marginLeft: '4px', opacity: 0.8 }}>
            {trendLabel}
          </span>
        )}
      </div>
    );
  };

  const renderLoading = () => (
    <div style={cardStyle} aria-busy="true">
      <div style={headerStyle}>
        <div style={{ 
          width: '60%', 
          height: '16px', 
          background: 'var(--mac-bg-tertiary)', 
          borderRadius: 'var(--mac-radius-sm)' 
        }} />
        <div style={{ 
          width: '24px', 
          height: '24px', 
          background: 'var(--mac-bg-tertiary)', 
          borderRadius: '50%' 
        }} />
      </div>
      <div style={{ 
        width: '80%', 
        height: '32px', 
        background: 'var(--mac-bg-tertiary)', 
        borderRadius: 'var(--mac-radius-sm)',
        marginBottom: '8px'
      }} />
      <div style={{ 
        width: '40%', 
        height: '12px', 
        background: 'var(--mac-bg-tertiary)', 
        borderRadius: 'var(--mac-radius-sm)' 
      }} />
    </div>
  );

  if (loading) {
    return renderLoading();
  }

  const content = (
    <>
      <div style={headerStyle}>
        <h3 style={titleStyle}>{title}</h3>
        {Icon && typeof Icon === 'function' && <Icon style={iconStyle} />}
        {Icon && typeof Icon !== 'function' && <span>{Icon}</span>}
      </div>
      
      <div style={valueStyle}>{value}</div>
      
      {subtitle && (
        <p style={subtitleStyle}>{subtitle}</p>
      )}
      
      {renderTrend()}
    </>
  );

  if (onClick) {
    return (
      <div
        className={className}
        style={cardStyle}
        onClick={handleClick}
        onMouseEnter={handleMouseEnter}
        onFocus={() => setIsFocused(true)}
        onMouseLeave={handleMouseLeave}
        onBlur={() => setIsFocused(false)}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
        aria-busy={loading}
      >
        {content}
      </div>
    );
  }

  return (
    <div className={className} style={cardStyle} aria-busy={loading}>
      {content}
    </div>
  );
};

MacOSStatCard.propTypes = {
  title: PropTypes.node,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number, PropTypes.node]),
  subtitle: PropTypes.node,
  icon: PropTypes.elementType,
  trend: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  trendType: PropTypes.oneOf(['positive', 'negative', 'neutral']),
  trendLabel: PropTypes.node,
  color: PropTypes.oneOf(['blue', 'green', 'orange', 'red', 'purple', 'gray']),
  size: PropTypes.oneOf(['sm', 'md', 'lg']),
  variant: PropTypes.oneOf(['default', 'filled', 'elevated']),
  loading: PropTypes.bool,
  onClick: PropTypes.func,
  className: PropTypes.string,
  style: PropTypes.object
};

export default MacOSStatCard;
