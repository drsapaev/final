/**
 * Унифицированный компонент Input
 * Согласно MASTER_TODO_LIST строка 216
 */
import React from 'react';
import { colors, typography, spacing } from '../theme';
import { colors as designColors } from '../../theme/tokens';

const Input = ({
  type = 'text',
  value,
  onChange,
  placeholder,
  disabled = false,
  error = false,
  errorMessage,
  label,
  required = false,
  size = 'medium',
  variant = 'outlined',
  fullWidth = false,
  startIcon,
  endIcon,
  className = '',
  style = {},
  ...props
}) => {
  // Размеры (обновлены для touch-friendly интерфейса)
  const sizes = {
    small: {
      height: '44px',  // Минимум 44px для мобильных устройств
      padding: `${spacing.spacing[2]} ${spacing.spacing[3]}`, // Увеличен padding
      fontSize: typography.fontSizes.base, // Увеличен размер шрифта для читаемости
    },
    medium: {
      height: '48px',  // Оптимальный размер для мобильных и десктоп
      padding: `${spacing.spacing[3]} ${spacing.spacing[4]}`, // Увеличен padding
      fontSize: typography.fontSizes.base,
    },
    large: {
      height: '56px',  // Большой размер для важных полей
      padding: `${spacing.spacing[4]} ${spacing.spacing[5]}`,
      fontSize: typography.fontSizes.lg,
    },
  };

  // Варианты стилей (обновлены на новую цветовую систему)
  const variants = {
    outlined: {
      border: `1px solid ${error ? designColors.status.danger : designColors.border.medium}`,
      borderRadius: '6px',
      backgroundColor: designColors.semantic.background.primary,
      '&:focus': {
        borderColor: error ? designColors.status.danger : designColors.border.focus,
        boxShadow: `0 0 0 2px ${error ? designColors.status.danger : designColors.primary[100]}`,
      },
      '&:hover': {
        borderColor: error ? designColors.status.danger : designColors.border.dark,
      },
    },
    filled: {
      border: 'none',
      borderRadius: '6px',
      backgroundColor: designColors.gray[100],
      borderBottom: `2px solid ${error ? designColors.status.danger : designColors.border.medium}`,
      '&:focus': {
        backgroundColor: designColors.gray[50],
        borderBottomColor: error ? designColors.status.danger : designColors.primary[500],
      },
    },
    standard: {
      border: 'none',
      borderBottom: `1px solid ${error ? designColors.status.danger : designColors.border.medium}`,
      borderRadius: '0',
      backgroundColor: 'transparent',
      '&:focus': {
        borderBottomColor: error ? designColors.status.danger : designColors.primary[500],
        borderBottomWidth: '2px',
      },
    },
  };

  const sizeStyles = sizes[size];
  const variantStyles = variants[variant];

  const inputStyles = {
    ...sizeStyles,
    ...variantStyles,
    width: fullWidth ? '100%' : 'auto',
    fontFamily: typography.fontFamilies.primary,
    fontWeight: typography.fontWeights.normal,
    lineHeight: typography.lineHeights.input,
    color: designColors.semantic.text.primary,
    outline: 'none',
    transition: 'all 200ms ease-in-out',
    
    // Состояния
    ...(disabled && {
      backgroundColor: designColors.gray[100],
      color: designColors.gray[500],
      cursor: 'not-allowed',
    }),
    
    ...style,
  };

  const containerStyles = {
    display: 'flex',
    flexDirection: 'column',
    gap: spacing.spacing[1],
    width: fullWidth ? '100%' : 'auto',
  };

  const labelStyles = {
    fontSize: typography.fontSizes.sm,
    fontWeight: typography.fontWeights.medium,
    color: error ? designColors.status.danger : designColors.semantic.text.primary,
    marginBottom: spacing.spacing[1],
  };

  const errorStyles = {
    fontSize: typography.fontSizes.xs,
    color: designColors.status.danger,
    marginTop: spacing.spacing[1],
  };

  const inputWrapperStyles = {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
  };

  const iconStyles = {
    position: 'absolute',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: designColors.semantic.text.secondary,
    pointerEvents: 'none',
  };

  const startIconStyles = {
    ...iconStyles,
    left: spacing.spacing[3],
  };

  const endIconStyles = {
    ...iconStyles,
    right: spacing.spacing[3],
  };

  return (
    <div style={containerStyles} className={className}>
      {label && (
        <label style={labelStyles}>
          {label}
          {required && <span style={{ color: designColors.status.danger }}> *</span>}
        </label>
      )}
      
      <div style={inputWrapperStyles}>
        {startIcon && (
          <div style={startIconStyles}>
            {startIcon}
          </div>
        )}
        
        <input
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          disabled={disabled}
          required={required}
          style={{
            ...inputStyles,
            paddingLeft: startIcon ? spacing.spacing[10] : inputStyles.padding.split(' ')[1],
            paddingRight: endIcon ? spacing.spacing[10] : inputStyles.padding.split(' ')[1],
          }}
          {...props}
        />
        
        {endIcon && (
          <div style={endIconStyles}>
            {endIcon}
          </div>
        )}
      </div>
      
      {error && errorMessage && (
        <div style={errorStyles}>
          {errorMessage}
        </div>
      )}
    </div>
  );
};

export default Input;
