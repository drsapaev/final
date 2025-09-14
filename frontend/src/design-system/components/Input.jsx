/**
 * Унифицированный компонент Input
 * Согласно MASTER_TODO_LIST строка 216
 */
import React from 'react';
import { colors, typography, spacing } from '../theme';

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
  // Размеры
  const sizes = {
    small: {
      height: '32px',
      padding: `${spacing.spacing[1]} ${spacing.spacing[3]}`,
      fontSize: typography.fontSizes.sm,
    },
    medium: {
      height: '40px',
      padding: `${spacing.spacing[2]} ${spacing.spacing[4]}`,
      fontSize: typography.fontSizes.base,
    },
    large: {
      height: '48px',
      padding: `${spacing.spacing[3]} ${spacing.spacing[5]}`,
      fontSize: typography.fontSizes.lg,
    },
  };

  // Варианты стилей
  const variants = {
    outlined: {
      border: `1px solid ${error ? colors.brand.error[500] : colors.neutral.gray[300]}`,
      borderRadius: '6px',
      backgroundColor: colors.neutral.white,
      '&:focus': {
        borderColor: error ? colors.brand.error[500] : colors.brand.primary[500],
        boxShadow: `0 0 0 2px ${error ? colors.brand.error[100] : colors.brand.primary[100]}`,
      },
      '&:hover': {
        borderColor: error ? colors.brand.error[400] : colors.neutral.gray[400],
      },
    },
    filled: {
      border: 'none',
      borderRadius: '6px',
      backgroundColor: colors.neutral.gray[100],
      borderBottom: `2px solid ${error ? colors.brand.error[500] : colors.neutral.gray[300]}`,
      '&:focus': {
        backgroundColor: colors.neutral.gray[50],
        borderBottomColor: error ? colors.brand.error[500] : colors.brand.primary[500],
      },
    },
    standard: {
      border: 'none',
      borderBottom: `1px solid ${error ? colors.brand.error[500] : colors.neutral.gray[300]}`,
      borderRadius: '0',
      backgroundColor: 'transparent',
      '&:focus': {
        borderBottomColor: error ? colors.brand.error[500] : colors.brand.primary[500],
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
    color: colors.neutral.gray[900],
    outline: 'none',
    transition: 'all 200ms ease-in-out',
    
    // Состояния
    ...(disabled && {
      backgroundColor: colors.neutral.gray[100],
      color: colors.neutral.gray[500],
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
    color: error ? colors.brand.error[700] : colors.neutral.gray[700],
    marginBottom: spacing.spacing[1],
  };

  const errorStyles = {
    fontSize: typography.fontSizes.xs,
    color: colors.brand.error[600],
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
    color: colors.neutral.gray[500],
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
          {required && <span style={{ color: colors.brand.error[500] }}> *</span>}
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
