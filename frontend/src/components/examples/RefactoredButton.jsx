/**
 * ═══════════════════════════════════════════════════════════════════════════════
 * REFACTORED BUTTON COMPONENT
 * ═══════════════════════════════════════════════════════════════════════════════
 * 
 * This is a BEFORE & AFTER example showing how to migrate from hardcoded
 * styles to the unified design system.
 * 
 * Key changes:
 * 1. All colors use unifiedTheme.colors.*
 * 2. All spacing uses unifiedTheme.spacing.*
 * 3. All borderRadius uses unifiedTheme.borderRadius.*
 * 4. All shadows use unifiedTheme.shadows.*
 * 5. All typography uses unifiedTheme.typography.*
 * 6. Transitions use duration + easing from theme
 */

import React, { useState, useRef } from 'react';
import PropTypes from 'prop-types';
import { Loader } from 'lucide-react';
import { unifiedTheme } from '@/theme/unifiedTheme';

const { colors, spacing, borderRadius, shadows, typography, transitions } = unifiedTheme;

const RefactoredButton = ({
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
  onClick,
  className = '',
  type = 'button',
  ...props
}) => {
  const [rippleEffect, setRippleEffect] = useState([]);
  const buttonRef = useRef(null);

  // ═══════════════════════════════════════════════════════════════════
  // GET VARIANT COLORS (from unified theme)
  // ═══════════════════════════════════════════════════════════════════
  const getVariantStyles = () => {
    const variantMap = {
      // Primary actions
      primary: {
        bg: colors.primary[500],
        text: colors.semantic.text.inverse,
        hover: colors.primary[600],
        active: colors.primary[700],
        shadow: shadows.sm,
        hoverShadow: shadows.md,
      },
      secondary: {
        bg: colors.secondary[100],
        text: colors.secondary[900],
        hover: colors.secondary[200],
        active: colors.secondary[300],
        shadow: 'none',
        hoverShadow: 'none',
      },

      // Status variants (semantic colors)
      success: {
        bg: colors.status.success,
        text: colors.semantic.text.inverse,
        hover: colors.status.success,
        active: colors.status.success,
        shadow: shadows.sm,
        hoverShadow: shadows.md,
      },
      warning: {
        bg: colors.status.warning,
        text: colors.semantic.text.primary,
        hover: colors.status.warning,
        active: colors.status.warning,
        shadow: shadows.sm,
        hoverShadow: shadows.md,
      },
      danger: {
        bg: colors.status.danger,
        text: colors.semantic.text.inverse,
        hover: colors.status.danger,
        active: colors.status.danger,
        shadow: shadows.sm,
        hoverShadow: shadows.md,
      },
      info: {
        bg: colors.status.info,
        text: colors.semantic.text.inverse,
        hover: colors.status.info,
        active: colors.status.info,
        shadow: shadows.sm,
        hoverShadow: shadows.md,
      },

      // Medical specialty variants
      cardiology: {
        bg: colors.medical.cardiology,
        text: colors.semantic.text.inverse,
        hover: '#b91c1c',
        active: '#991b1b',
        shadow: shadows.sm,
        hoverShadow: shadows.md,
      },
      dermatology: {
        bg: colors.medical.dermatology,
        text: colors.semantic.text.inverse,
        hover: '#7c3aed',
        active: '#6d28d9',
        shadow: shadows.sm,
        hoverShadow: shadows.md,
      },
      dentistry: {
        bg: colors.medical.dentistry,
        text: colors.semantic.text.inverse,
        hover: '#047857',
        active: '#065f46',
        shadow: shadows.sm,
        hoverShadow: shadows.md,
      },

      // Light variant (for on-dark backgrounds)
      light: {
        bg: colors.secondary[50],
        text: colors.secondary[900],
        hover: colors.secondary[100],
        active: colors.secondary[200],
        shadow: 'none',
        hoverShadow: 'none',
      },
      ghost: {
        bg: 'transparent',
        text: colors.primary[500],
        hover: colors.primary[50],
        active: colors.primary[100],
        shadow: 'none',
        hoverShadow: 'none',
      },
    };

    return variantMap[variant] || variantMap.primary;
  };

  // ═══════════════════════════════════════════════════════════════════
  // GET SIZE STYLES (using unified spacing scale)
  // ═══════════════════════════════════════════════════════════════════
  const getSizeStyles = () => {
    const sizeMap = {
      small: {
        padding: `${spacing[1]} ${spacing[2]}`,  // 4px 8px
        fontSize: typography.fontSize.xs,
        minHeight: '32px',
      },
      medium: {
        padding: `${spacing[2]} ${spacing[4]}`,  // 8px 16px ★ DEFAULT
        fontSize: typography.fontSize.sm,
        minHeight: '40px',
      },
      large: {
        padding: `${spacing[3]} ${spacing[5]}`,  // 12px 20px
        fontSize: typography.fontSize.base,
        minHeight: '48px',
      },
    };

    return sizeMap[size] || sizeMap.medium;
  };

  const variantStyles = getVariantStyles();
  const sizeStyles = getSizeStyles();

  // ═══════════════════════════════════════════════════════════════════
  // BUTTON STYLES (unified)
  // ═══════════════════════════════════════════════════════════════════
  const buttonStyles = {
    position: 'relative',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing[2],  // Use spacing scale!
    border: outlined ? `2px solid ${variantStyles.bg}` : 'none',
    borderRadius: rounded ? borderRadius.full : borderRadius.md,  // Always use scale!
    fontFamily: typography.fontFamily.sans,
    fontWeight: typography.fontWeight.semibold,
    textDecoration: 'none',
    transition: `all ${transitions.duration.base} ${transitions.easing.smooth}`,  // Use theme timing!
    overflow: 'hidden',
    userSelect: 'none',
    whiteSpace: 'nowrap',
    verticalAlign: 'middle',
    outline: 'none',
    cursor: disabled || loading ? 'not-allowed' : 'pointer',

    // Color & sizing
    backgroundColor: outlined ? 'transparent' : (disabled ? colors.secondary[200] : variantStyles.bg),
    color: outlined ? variantStyles.bg : (disabled ? colors.secondary[400] : variantStyles.text),
    opacity: disabled ? 0.6 : 1,

    // Spacing from scale
    ...sizeStyles,

    // Shadow from unified system
    boxShadow: variantStyles.shadow,

    // Width
    ...(fullWidth && { width: '100%' }),
  };

  const handleClick = (event) => {
    if (disabled || loading) return;
    onClick?.(event);
  };

  return (
    <button
      ref={buttonRef}
      type={type}
      style={buttonStyles}
      onClick={handleClick}
      disabled={disabled || loading}
      onMouseEnter={(e) => {
        if (!disabled && !loading) {
          e.currentTarget.style.boxShadow = variantStyles.hoverShadow;
          e.currentTarget.style.transform = 'translateY(-1px)';
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled && !loading) {
          e.currentTarget.style.boxShadow = variantStyles.shadow;
          e.currentTarget.style.transform = 'translateY(0)';
        }
      }}
      {...props}
    >
      {/* Icon left */}
      {icon && iconPosition === 'left' && !loading && (
        <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {React.isValidElement(icon) ? icon : <icon size={16} />}
        </span>
      )}

      {/* Loading indicator */}
      {loading && (
        <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Loader size={16} style={{ animation: 'spin 1s linear infinite' }} />
        </span>
      )}

      {/* Text */}
      <span style={{ opacity: loading ? 0.7 : 1 }}>
        {children}
      </span>

      {/* Icon right */}
      {icon && iconPosition === 'right' && !loading && (
        <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {React.isValidElement(icon) ? icon : <icon size={16} />}
        </span>
      )}
    </button>
  );
};

RefactoredButton.propTypes = {
  children: PropTypes.node,
  variant: PropTypes.oneOf([
    'primary', 'secondary', 'success', 'warning', 'danger', 'info',
    'cardiology', 'dermatology', 'dentistry', 'light', 'ghost'
  ]),
  size: PropTypes.oneOf(['small', 'medium', 'large']),
  disabled: PropTypes.bool,
  loading: PropTypes.bool,
  icon: PropTypes.node,
  iconPosition: PropTypes.oneOf(['left', 'right']),
  fullWidth: PropTypes.bool,
  rounded: PropTypes.bool,
  outlined: PropTypes.bool,
  onClick: PropTypes.func,
  className: PropTypes.string,
  type: PropTypes.oneOf(['button', 'submit', 'reset']),
};

export default RefactoredButton;
