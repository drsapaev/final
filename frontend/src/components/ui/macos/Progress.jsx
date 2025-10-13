import React from 'react';
import { useTheme } from '../../../contexts/ThemeContext';

/**
 * macOS-style Progress Component
 * Implements Apple's Human Interface Guidelines for progress indicators
 */
const Progress = React.forwardRef(({
  value = 0,
  max = 100,
  variant = 'default',
  size = 'default',
  animated = true,
  showValue = false,
  formatValue,
  className = '',
  style = {},
  ...props
}, ref) => {
  const { theme } = useTheme();

  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  // Size mapping
  const sizeMap = {
    small: { height: '4px', borderRadius: '2px' },
    default: { height: '6px', borderRadius: '3px' },
    large: { height: '8px', borderRadius: '4px' }
  };

  const sizeStyles = sizeMap[size] || sizeMap.default;

  // Variant styles
  const variantStyles = {
    default: {
      backgroundColor: 'var(--mac-bg-tertiary)',
      border: '1px solid var(--mac-border)'
    },
    primary: {
      backgroundColor: 'rgba(0, 122, 255, 0.1)',
      border: '1px solid rgba(0, 122, 255, 0.2)'
    },
    success: {
      backgroundColor: 'rgba(52, 199, 89, 0.1)',
      border: '1px solid rgba(52, 199, 89, 0.2)'
    },
    warning: {
      backgroundColor: 'rgba(255, 149, 0, 0.1)',
      border: '1px solid rgba(255, 149, 0, 0.2)'
    },
    danger: {
      backgroundColor: 'rgba(255, 59, 48, 0.1)',
      border: '1px solid rgba(255, 59, 48, 0.2)'
    }
  };

  const progressStyles = {
    width: '100%',
    backgroundColor: variantStyles[variant]?.backgroundColor || variantStyles.default.backgroundColor,
    border: variantStyles[variant]?.border || variantStyles.default.border,
    borderRadius: sizeStyles.borderRadius,
    overflow: 'hidden',
    position: 'relative',
    ...sizeStyles,
    ...style
  };

  const fillStyles = {
    width: `${percentage}%`,
    height: '100%',
    backgroundColor: getProgressColor(variant),
    borderRadius: sizeStyles.borderRadius,
    transition: animated ? 'width 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)' : 'none',
    position: 'relative'
  };

  const valueTextStyles = {
    position: 'absolute',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    fontSize: '10px',
    fontWeight: '600',
    color: 'white',
    textShadow: '0 1px 2px rgba(0, 0, 0, 0.5)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    userSelect: 'none'
  };

  function getProgressColor(variant) {
    const colorMap = {
      default: 'var(--mac-accent-blue)',
      primary: '#007aff',
      success: '#34c759',
      warning: '#ff9500',
      danger: '#ff3b30'
    };
    return colorMap[variant] || colorMap.default;
  }

  const displayValue = formatValue ? formatValue(value, max) : `${Math.round(percentage)}%`;

  return (
    <div
      ref={ref}
      className={`mac-progress ${className}`}
      style={progressStyles}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={`Progress: ${displayValue}`}
      {...props}
    >
      <div className="mac-progress-fill" style={fillStyles}>
        {showValue && (
          <span className="mac-progress-value" style={valueTextStyles}>
            {displayValue}
          </span>
        )}
      </div>

      <style jsx>{`
        /* Dark mode adjustments */
        @media (prefers-color-scheme: dark) {
          .mac-progress {
            background-color: rgba(255, 255, 255, 0.05) !important;
            border-color: rgba(255, 255, 255, 0.1) !important;
          }
        }

        /* High contrast mode */
        @media (prefers-contrast: high) {
          .mac-progress {
            border-width: 2px !important;
          }

          .mac-progress-fill {
            background-color: var(--mac-accent-blue) !important;
          }
        }

        /* Reduced motion */
        @media (prefers-reduced-motion: reduce) {
          .mac-progress-fill {
            transition: none !important;
          }
        }
      `}</style>
    </div>
  );
});

Progress.displayName = 'macOS Progress';

/**
 * Circular Progress Component
 */
export const CircularProgress = React.forwardRef(({
  value = 0,
  max = 100,
  size = 'default',
  thickness = 'medium',
  variant = 'default',
  animated = true,
  showValue = false,
  formatValue,
  className = '',
  style = {},
  ...props
}, ref) => {
  const { theme } = useTheme();

  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  // Size mapping
  const sizeMap = {
    small: { width: 20, height: 20 },
    default: { width: 32, height: 32 },
    large: { width: 48, height: 48 },
    xlarge: { width: 64, height: 64 }
  };

  const dimensions = sizeMap[size] || sizeMap.default;

  // Thickness mapping
  const thicknessMap = {
    thin: 2,
    medium: 3,
    thick: 4
  };

  const strokeWidth = thicknessMap[thickness] || thicknessMap.medium;
  const radius = (dimensions.width - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDasharray = circumference;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  const containerStyles = {
    position: 'relative',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    ...dimensions,
    ...style
  };

  function getProgressColor(variant) {
    const colorMap = {
      default: 'var(--mac-accent-blue)',
      primary: '#007aff',
      success: '#34c759',
      warning: '#ff9500',
      danger: '#ff3b30'
    };
    return colorMap[variant] || colorMap.default;
  }

  const displayValue = formatValue ? formatValue(value, max) : Math.round(percentage);

  return (
    <div
      ref={ref}
      className={`mac-circular-progress ${className}`}
      style={containerStyles}
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={`Progress: ${displayValue}%`}
      {...props}
    >
      <svg
        width={dimensions.width}
        height={dimensions.height}
        viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
        style={{ transform: 'rotate(-90deg)' }}
      >
        {/* Background circle */}
        <circle
          cx={dimensions.width / 2}
          cy={dimensions.height / 2}
          r={radius}
          stroke="var(--mac-bg-tertiary)"
          strokeWidth={strokeWidth}
          fill="none"
        />

        {/* Progress circle */}
        <circle
          cx={dimensions.width / 2}
          cy={dimensions.height / 2}
          r={radius}
          stroke={getProgressColor(variant)}
          strokeWidth={strokeWidth}
          fill="none"
          strokeDasharray={strokeDasharray}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          style={{
            transition: animated ? 'stroke-dashoffset 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)' : 'none'
          }}
        />
      </svg>

      {/* Value text */}
      {showValue && (
        <div
          className="mac-circular-progress-value"
          style={{
            position: 'absolute',
            fontSize: size === 'small' ? '8px' : size === 'default' ? '10px' : '12px',
            fontWeight: '600',
            color: 'var(--mac-text-primary)',
            fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
            userSelect: 'none'
          }}
        >
          {displayValue}%
        </div>
      )}

      <style jsx>{`
        /* Dark mode adjustments */
        @media (prefers-color-scheme: dark) {
          .mac-circular-progress circle:first-child {
            stroke: rgba(255, 255, 255, 0.1) !important;
          }
        }

        /* Reduced motion */
        @media (prefers-reduced-motion: reduce) {
          .mac-circular-progress circle:last-child {
            transition: none !important;
          }
        }
      `}</style>
    </div>
  );
});

CircularProgress.displayName = 'macOS Circular Progress';

export default Progress;
