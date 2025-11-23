import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

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
}) => {
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
      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1)'
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

  const trendStyles = {
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

  const cardStyle = {
    padding: currentSize.padding,
    background: currentVariant.background,
    border: currentVariant.border,
    borderRadius: currentVariant.borderRadius,
    boxShadow: currentVariant.boxShadow,
    cursor: onClick ? 'pointer' : 'default',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    position: 'relative',
    overflow: 'hidden',
    ...style
  };

  const headerStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '8px'
  };

  const titleStyle = {
    fontSize: currentSize.fontSize,
    fontWeight: 'var(--mac-font-weight-medium)',
    color: 'var(--mac-text-secondary)',
    margin: 0
  };

  const valueStyle = {
    fontSize: currentSize.valueFontSize,
    fontWeight: 'var(--mac-font-weight-bold)',
    color: 'var(--mac-text-primary)',
    margin: '4px 0',
    lineHeight: 1.2
  };

  const subtitleStyle = {
    fontSize: 'var(--mac-font-size-xs)',
    color: 'var(--mac-text-tertiary)',
    margin: 0
  };

  const trendStyle = {
    display: 'flex',
    alignItems: 'center',
    marginTop: '8px',
    fontSize: 'var(--mac-font-size-xs)',
    fontWeight: 'var(--mac-font-weight-medium)',
    color: currentTrend.color
  };

  const iconStyle = {
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

  const handleMouseEnter = (e) => {
    if (onClick) {
      e.currentTarget.style.transform = 'translateY(-2px)';
      e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15)';
    }
  };

  const handleMouseLeave = (e) => {
    if (onClick) {
      e.currentTarget.style.transform = 'translateY(0)';
      e.currentTarget.style.boxShadow = currentVariant.boxShadow || 'none';
    }
  };

  const renderTrend = () => {
    if (!trend) return null;

    const TrendIcon = currentTrend.icon;
    
    return (
      <div style={trendStyle}>
        <TrendIcon size={12} style={{ marginRight: '4px' }} />
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
    <div style={cardStyle}>
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

  return (
    <div
      className={className}
      style={cardStyle}
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div style={headerStyle}>
        <h3 style={titleStyle}>{title}</h3>
        {Icon && <Icon style={iconStyle} />}
      </div>
      
      <div style={valueStyle}>{value}</div>
      
      {subtitle && (
        <p style={subtitleStyle}>{subtitle}</p>
      )}
      
      {renderTrend()}
    </div>
  );
};

export default MacOSStatCard;