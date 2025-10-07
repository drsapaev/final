import React, { useState, useRef } from 'react';
import { Loader } from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { colors } from '../../theme/tokens';
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

  // Получение цветов для варианта (используем новую структуру токенов)
  const getVariantColors = () => {
    const colorMap = {
      primary: {
        bg: colors.primary[500],        // Основной синий
        text: colors.semantic.text.inverse, // Белый текст
        hover: colors.primary[600],     // Темнее при hover
        border: colors.primary[500]
      },
      secondary: {
        bg: colors.secondary[500],      // Серый
        text: colors.semantic.text.inverse,
        hover: colors.secondary[600],   // Темнее при hover
        border: colors.secondary[500]
      },
      success: {
        bg: colors.status.success,      // Зеленый успех
        text: colors.semantic.text.inverse,
        hover: colors.status.success,   // Тот же цвет при hover (для консистентности)
        border: colors.status.success
      },
      warning: {
        bg: colors.status.warning,      // Оранжевый предупреждение
        text: colors.semantic.text.primary, // Темный текст для контраста
        hover: colors.status.warning,   // Тот же цвет при hover
        border: colors.status.warning
      },
      danger: {
        bg: colors.status.danger,       // Красный ошибка
        text: colors.semantic.text.inverse,
        hover: colors.status.danger,    // Тот же цвет при hover
        border: colors.status.danger
      },
      info: {
        bg: colors.status.info,         // Синий информация
        text: colors.semantic.text.inverse,
        hover: colors.status.info,      // Тот же цвет при hover
        border: colors.status.info
      },
      light: {
        bg: colors.semantic.background.secondary, // Светлый фон
        text: colors.semantic.text.primary,      // Темный текст
        hover: colors.semantic.surface.hover,    // Hover состояние
        border: colors.semantic.border.light
      },
      dark: {
        bg: colors.gray[800],           // Темный серый
        text: colors.semantic.text.inverse,
        hover: colors.gray[900],        // Еще темнее при hover
        border: colors.gray[800]
      }
    };

    return colorMap[variant] || colorMap.primary;
  };

  const variantColors = getVariantColors();

  // Стили кнопки (используем токены цветов)
  const buttonStyles = {
    backgroundColor: ghost
      ? 'transparent'
      : outlined
        ? 'transparent'
        : disabled
          ? colors.gray[300]  // Отключенное состояние
          : variantColors.bg,
    color: ghost
      ? variantColors.bg
      : outlined
        ? variantColors.bg
        : disabled
          ? colors.gray[500]  // Отключенный текст
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


