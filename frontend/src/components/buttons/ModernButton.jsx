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

  // Получение цветов для варианта (расширенная система с медицинской семантикой)
  const getVariantColors = () => {
    const colorMap = {
      // Основные варианты
      primary: {
        bg: colors.primary[500],
        text: colors.semantic.text.inverse,
        hover: colors.primary[600],
        border: colors.primary[500]
      },
      secondary: {
        bg: colors.secondary[500],
        text: colors.semantic.text.inverse,
        hover: colors.secondary[600],
        border: colors.secondary[500]
      },

      // Статусные варианты
      success: {
        bg: colors.status.success,
        text: colors.semantic.text.inverse,
        hover: colors.status.success,
        border: colors.status.success
      },
      warning: {
        bg: colors.status.warning,
        text: colors.semantic.text.primary,
        hover: colors.status.warning,
        border: colors.status.warning
      },
      danger: {
        bg: colors.status.danger,
        text: colors.semantic.text.inverse,
        hover: colors.status.danger,
        border: colors.status.danger
      },
      info: {
        bg: colors.status.info,
        text: colors.semantic.text.inverse,
        hover: colors.status.info,
        border: colors.status.info
      },

      // Медицинские варианты по отделам
      cardiology: {
        bg: colors.medical.cardiology,
        text: colors.semantic.text.inverse,
        hover: '#b91c1c',
        border: colors.medical.cardiology
      },
      dermatology: {
        bg: colors.medical.dermatology,
        text: colors.semantic.text.inverse,
        hover: '#6d28d9',
        border: colors.medical.dermatology
      },
      dentistry: {
        bg: colors.medical.dentistry,
        text: colors.semantic.text.inverse,
        hover: '#047857',
        border: colors.medical.dentistry
      },
      laboratory: {
        bg: colors.medical.laboratory,
        text: colors.semantic.text.inverse,
        hover: '#0e7490',
        border: colors.medical.laboratory
      },

      // Семантические медицинские действия
      emergency: {
        bg: colors.actions.emergency,
        text: colors.semantic.text.inverse,
        hover: '#b91c1c',
        border: colors.actions.emergency
      },
      diagnose: {
        bg: colors.actions.diagnose,
        text: colors.semantic.text.inverse,
        hover: '#1d4ed8',
        border: colors.actions.diagnose
      },
      treat: {
        bg: colors.actions.treat,
        text: colors.semantic.text.inverse,
        hover: '#047857',
        border: colors.actions.treat
      },
      approve: {
        bg: colors.actions.approve,
        text: colors.semantic.text.inverse,
        hover: '#1f2937',
        border: colors.actions.approve
      },
      reject: {
        bg: colors.actions.reject,
        text: colors.semantic.text.inverse,
        hover: '#374151',
        border: colors.actions.reject
      },

      // Системные варианты
      light: {
        bg: colors.semantic.background.secondary,
        text: colors.semantic.text.primary,
        hover: colors.semantic.surface.hover,
        border: colors.semantic.border.light
      },
      dark: {
        bg: colors.gray[800],
        text: colors.semantic.text.inverse,
        hover: colors.gray[900],
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


