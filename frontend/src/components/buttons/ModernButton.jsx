import React, { useState, useRef } from 'react';
import { Loader } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import './ModernButton.css';

const ModernButton = ({
  children,
  variant = 'primary',
  size = 'medium',
  disabled = false,
  loading = false,
  icon,
  iconPosition = 'left',
  fullWidth = false,
  rounded = false,
  outlined = false,
  ghost = false,
  ripple = true,
  onClick,
  className = '',
  type = 'button',
  ...props
}) => {
  const { theme, getColor } = useTheme();
  const [rippleEffect, setRippleEffect] = useState([]);
  const buttonRef = useRef(null);

  // Создание эффекта ripple
  const createRipple = (event) => {
    if (!ripple || disabled || loading) return;

    const button = buttonRef.current;
    const rect = button.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = event.clientX - rect.left - size / 2;
    const y = event.clientY - rect.top - size / 2;

    const newRipple = {
      x,
      y,
      size,
      id: Date.now()
    };

    setRippleEffect(prev => [...prev, newRipple]);

    // Удаление эффекта через 600мс
    setTimeout(() => {
      setRippleEffect(prev => prev.filter(r => r.id !== newRipple.id));
    }, 600);
  };

  // Обработка клика
  const handleClick = (event) => {
    if (disabled || loading) return;
    
    createRipple(event);
    onClick?.(event);
  };

  // Получение цветов для варианта
  const getVariantColors = () => {
    const colors = {
      primary: {
        bg: getColor('primary'),
        text: 'white',
        hover: getColor('primaryDark'),
        border: getColor('primary')
      },
      secondary: {
        bg: getColor('secondary'),
        text: 'white',
        hover: getColor('secondaryDark'),
        border: getColor('secondary')
      },
      success: {
        bg: getColor('success'),
        text: 'white',
        hover: getColor('successDark'),
        border: getColor('success')
      },
      warning: {
        bg: getColor('warning'),
        text: 'white',
        hover: getColor('warningDark'),
        border: getColor('warning')
      },
      danger: {
        bg: getColor('danger'),
        text: 'white',
        hover: getColor('dangerDark'),
        border: getColor('danger')
      },
      info: {
        bg: getColor('info'),
        text: 'white',
        hover: getColor('infoDark'),
        border: getColor('info')
      },
      light: {
        bg: getColor('gray100'),
        text: getColor('textPrimary'),
        hover: getColor('gray200'),
        border: getColor('gray300')
      },
      dark: {
        bg: getColor('gray800'),
        text: 'white',
        hover: getColor('gray900'),
        border: getColor('gray800')
      }
    };

    return colors[variant] || colors.primary;
  };

  const variantColors = getVariantColors();

  // Стили кнопки
  const buttonStyles = {
    backgroundColor: ghost 
      ? 'transparent' 
      : outlined 
        ? 'transparent' 
        : disabled 
          ? getColor('gray300')
          : variantColors.bg,
    color: ghost
      ? variantColors.bg
      : outlined
        ? variantColors.bg
        : disabled
          ? getColor('gray500')
          : variantColors.text,
    borderColor: outlined || ghost
      ? variantColors.border
      : 'transparent',
    opacity: disabled ? 0.6 : 1,
    cursor: disabled || loading ? 'not-allowed' : 'pointer'
  };

  // Классы CSS
  const cssClasses = [
    'modern-button',
    `variant-${variant}`,
    `size-${size}`,
    outlined && 'outlined',
    ghost && 'ghost',
    fullWidth && 'full-width',
    rounded && 'rounded',
    disabled && 'disabled',
    loading && 'loading',
    className
  ].filter(Boolean).join(' ');

  return (
    <button
      ref={buttonRef}
      type={type}
      className={cssClasses}
      style={buttonStyles}
      onClick={handleClick}
      disabled={disabled || loading}
      {...props}
    >
      {/* Иконка слева */}
      {icon && iconPosition === 'left' && !loading && (
        <span className="button-icon left">
          {React.isValidElement(icon) ? icon : <icon size={size === 'small' ? 14 : size === 'large' ? 20 : 16} />}
        </span>
      )}

      {/* Индикатор загрузки */}
      {loading && (
        <span className="button-loader">
          <Loader size={size === 'small' ? 14 : size === 'large' ? 20 : 16} className="spinning" />
        </span>
      )}

      {/* Текст кнопки */}
      <span className={`button-text ${loading ? 'loading' : ''}`}>
        {children}
      </span>

      {/* Иконка справа */}
      {icon && iconPosition === 'right' && !loading && (
        <span className="button-icon right">
          {React.isValidElement(icon) ? icon : <icon size={size === 'small' ? 14 : size === 'large' ? 20 : 16} />}
        </span>
      )}

      {/* Эффект ripple */}
      {ripple && (
        <span className="button-ripple-container">
          {rippleEffect.map(ripple => (
            <span
              key={ripple.id}
              className="button-ripple"
              style={{
                left: ripple.x,
                top: ripple.y,
                width: ripple.size,
                height: ripple.size
              }}
            />
          ))}
        </span>
      )}
    </button>
  );
};

export default ModernButton;

