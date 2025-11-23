import React from 'react';
import { TrendingUp, TrendingDown, Minus, ArrowUpRight, ArrowDownRight } from 'lucide-react';

const MacOSMetricCard = ({
  title,
  value,
  previousValue,
  unit = '',
  icon: Icon,
  trend,
  trendType = 'neutral',
  trendPeriod = 'vs предыдущий период',
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
      iconSize: 20,
      gap: '8px'
    },
    md: {
      padding: '16px',
      fontSize: 'var(--mac-font-size-sm)',
      valueFontSize: 'var(--mac-font-size-xl)',
      iconSize: 24,
      gap: '12px'
    },
    lg: {
      padding: '20px',
      fontSize: 'var(--mac-font-size-base)',
      valueFontSize: 'var(--mac-font-size-2xl)',
      iconSize: 28,
      gap: '16px'
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

  const currentSize = sizeStyles[size];
  const currentVariant = variantStyles[variant];
  const currentColor = colorStyles[color] || colorStyles.blue;

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
    marginBottom: currentSize.gap
  };

  const titleStyle = {
    fontSize: currentSize.fontSize,
    fontWeight: 'var(--mac-font-weight-medium)',
    color: 'var(--mac-text-secondary)',
    margin: 0
  };

  const valueContainerStyle = {
    display: 'flex',
    alignItems: 'baseline',
    gap: '4px',
    marginBottom: '8px'
  };

  const valueStyle = {
    fontSize: currentSize.valueFontSize,
    fontWeight: 'var(--mac-font-weight-bold)',
    color: 'var(--mac-text-primary)',
    margin: 0,
    lineHeight: 1.2
  };

  const unitStyle = {
    fontSize: currentSize.fontSize,
    fontWeight: 'var(--mac-font-weight-medium)',
    color: 'var(--mac-text-tertiary)',
    margin: 0
  };

  const iconStyle = {
    width: currentSize.iconSize,
    height: currentSize.iconSize,
    color: currentColor,
    flexShrink: 0
  };

  const calculateTrend = () => {
    if (!previousValue || previousValue === 0) return null;
    
    const change = ((value - previousValue) / previousValue) * 100;
    const isPositive = change > 0;
    const isNegative = change < 0;
    
    return {
      percentage: Math.abs(change).toFixed(1),
      isPositive,
      isNegative,
      isNeutral: !isPositive && !isNegative
    };
  };

  const renderTrend = () => {
    const trendData = calculateTrend();
    
    if (!trendData) return null;

    const TrendIcon = trendData.isPositive ? ArrowUpRight : 
                     trendData.isNegative ? ArrowDownRight : Minus;
    
    const trendColor = trendData.isPositive ? 'var(--mac-success)' :
                      trendData.isNegative ? 'var(--mac-error)' :
                      'var(--mac-text-secondary)';

    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        fontSize: 'var(--mac-font-size-xs)',
        fontWeight: 'var(--mac-font-weight-medium)',
        color: trendColor,
        marginTop: '8px'
      }}>
        <TrendIcon size={12} style={{ marginRight: '4px' }} />
        <span>{trendData.percentage}%</span>
        <span style={{ marginLeft: '4px', opacity: 0.8 }}>
          {trendPeriod}
        </span>
      </div>
    );
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
      
      <div style={valueContainerStyle}>
        <div style={valueStyle}>{value}</div>
        {unit && <span style={unitStyle}>{unit}</span>}
      </div>
      
      {renderTrend()}
    </div>
  );
};

export default MacOSMetricCard;
