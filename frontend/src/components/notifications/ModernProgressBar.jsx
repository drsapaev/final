import React, { useState, useEffect } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import './ModernProgressBar.css';

const ModernProgressBar = ({
  value = 0,
  max = 100,
  variant = 'primary',
  size = 'medium',
  animated = false,
  striped = false,
  showLabel = false,
  showPercentage = false,
  label,
  indeterminate = false,
  color,
  backgroundColor,
  className = '',
  ...props
}) => {
  const { theme, getColor } = useTheme();
  const [animatedValue, setAnimatedValue] = useState(0);

  // Анимация значения
  useEffect(() => {
    if (!animated) {
      setAnimatedValue(value);
      return;
    }

    const duration = 1000;
    const steps = 60;
    const stepValue = (value - animatedValue) / steps;
    let currentStep = 0;

    const timer = setInterval(() => {
      currentStep++;
      setAnimatedValue(prev => {
        const newValue = prev + stepValue;
        if (currentStep >= steps) {
          clearInterval(timer);
          return value;
        }
        return newValue;
      });
    }, duration / steps);

    return () => clearInterval(timer);
  }, [value, animated]);

  // Получение цвета для варианта
  const getVariantColor = () => {
    if (color) return color;
    
    const colors = {
      primary: getColor('primary'),
      secondary: getColor('secondary'),
      success: getColor('success'),
      warning: getColor('warning'),
      danger: getColor('danger'),
      info: getColor('info')
    };

    return colors[variant] || colors.primary;
  };

  const progressColor = getVariantColor();
  const percentage = Math.min(Math.max((animatedValue / max) * 100, 0), 100);

  // Стили
  const containerStyles = {
    backgroundColor: backgroundColor || (theme === 'dark' ? '#374151' : '#e5e7eb')
  };

  const barStyles = {
    width: indeterminate ? '100%' : `${percentage}%`,
    backgroundColor: progressColor,
    ...(indeterminate && {
      animation: 'indeterminate 2s linear infinite'
    })
  };

  return (
    <div className={`modern-progress-bar ${className}`} {...props}>
      {/* Лейбл */}
      {(showLabel || label) && (
        <div className="progress-header">
          {label && (
            <span 
              className="progress-label"
              style={{ color: getColor('textPrimary') }}
            >
              {label}
            </span>
          )}
          {showPercentage && !indeterminate && (
            <span 
              className="progress-percentage"
              style={{ color: getColor('textSecondary') }}
            >
              {Math.round(percentage)}%
            </span>
          )}
        </div>
      )}

      {/* Прогресс-бар */}
      <div 
        className={`progress-container ${size} ${striped ? 'striped' : ''} ${animated ? 'animated' : ''} ${indeterminate ? 'indeterminate' : ''}`}
        style={containerStyles}
        role="progressbar"
        aria-valuenow={indeterminate ? undefined : value}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-label={label}
      >
        <div 
          className="progress-bar"
          style={barStyles}
        >
          {/* Внутренний текст */}
          {showPercentage && !indeterminate && size !== 'small' && (
            <span className="progress-text">
              {Math.round(percentage)}%
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

// Компонент кругового прогресс-бара
export const CircularProgressBar = ({
  value = 0,
  max = 100,
  size = 120,
  strokeWidth = 8,
  variant = 'primary',
  showLabel = true,
  showPercentage = true,
  label,
  animated = true,
  color,
  backgroundColor,
  className = '',
  ...props
}) => {
  const { theme, getColor } = useTheme();
  const [animatedValue, setAnimatedValue] = useState(0);

  // Анимация значения
  useEffect(() => {
    if (!animated) {
      setAnimatedValue(value);
      return;
    }

    const duration = 1000;
    const steps = 60;
    const stepValue = (value - animatedValue) / steps;
    let currentStep = 0;

    const timer = setInterval(() => {
      currentStep++;
      setAnimatedValue(prev => {
        const newValue = prev + stepValue;
        if (currentStep >= steps) {
          clearInterval(timer);
          return value;
        }
        return newValue;
      });
    }, duration / steps);

    return () => clearInterval(timer);
  }, [value, animated]);

  // Получение цвета для варианта
  const getVariantColor = () => {
    if (color) return color;
    
    const colors = {
      primary: getColor('primary'),
      secondary: getColor('secondary'),
      success: getColor('success'),
      warning: getColor('warning'),
      danger: getColor('danger'),
      info: getColor('info')
    };

    return colors[variant] || colors.primary;
  };

  const progressColor = getVariantColor();
  const bgColor = backgroundColor || (theme === 'dark' ? '#374151' : '#e5e7eb');
  const percentage = Math.min(Math.max((animatedValue / max) * 100, 0), 100);
  
  // Расчеты для SVG
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const strokeDasharray = circumference;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;

  return (
    <div 
      className={`circular-progress-bar ${className}`}
      style={{ width: size, height: size }}
      {...props}
    >
      <svg
        width={size}
        height={size}
        className="circular-progress-svg"
      >
        {/* Фоновый круг */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={bgColor}
          strokeWidth={strokeWidth}
          fill="transparent"
        />
        
        {/* Прогресс */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={progressColor}
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={strokeDasharray}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          className="progress-circle"
          style={{
            transition: animated ? 'stroke-dashoffset 0.5s ease' : 'none'
          }}
        />
      </svg>
      
      {/* Центральный текст */}
      <div className="circular-progress-content">
        {showPercentage && (
          <div 
            className="circular-progress-percentage"
            style={{ color: getColor('textPrimary') }}
          >
            {Math.round(percentage)}%
          </div>
        )}
        {showLabel && label && (
          <div 
            className="circular-progress-label"
            style={{ color: getColor('textSecondary') }}
          >
            {label}
          </div>
        )}
      </div>
    </div>
  );
};

export default ModernProgressBar;


