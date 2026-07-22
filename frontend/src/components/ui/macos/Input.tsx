import React, { type CSSProperties, type FocusEvent, type MouseEvent, type ComponentType } from 'react';
import { XCircle } from 'lucide-react';
import PropTypes from 'prop-types';

type InputSize = 'sm' | 'md' | 'lg';
type InputVariant = 'default' | 'filled' | 'error';
type IconPosition = 'left' | 'right';

interface IconProps {
  style?: CSSProperties;
  size?: number | string;
}

type IconComponent = ComponentType<IconProps>;

interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'children' | 'style' | 'size'> {
  className?: string;
  style?: CSSProperties;
  icon?: IconComponent;
  iconPosition?: IconPosition;
  size?: InputSize | string;
  variant?: InputVariant | string;
  error?: boolean | string;
  disabled?: boolean;
  clearable?: boolean;
  onClear?: () => void;
  label?: React.ReactNode;
  hint?: React.ReactNode;
  sx?: Record<string, unknown>;
}

interface InputStyle extends CSSProperties {
  transition?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(({
  className,
  style,
  icon: Icon,
  iconPosition = 'left',
  size = 'md',
  variant = 'default',
  error,
  disabled,
  clearable, // Extract to prevent passing to input
  onClear,   // Extract to prevent passing to input
  ...props
}, ref) => {
  const [isFocused, setIsFocused] = React.useState<boolean>(false);
  const sizeStyles: Record<InputSize, CSSProperties> = {
    sm: {
      padding: '6px 12px',
      fontSize: 'var(--mac-font-size-sm)',
      height: '32px'
    },
    md: {
      padding: '8px 12px',
      fontSize: 'var(--mac-font-size-sm)',
      height: '36px'
    },
    lg: {
      padding: '12px 16px',
      fontSize: 'var(--mac-font-size-base)',
      height: '44px'
    }
  };

  const variantStyles: Record<InputVariant, CSSProperties> = {
    default: {
      border: '1px solid var(--mac-border)',
      background: 'var(--mac-bg-primary)',
      color: 'var(--mac-text-primary)'
    },
    filled: {
      border: '1px solid transparent',
      background: 'var(--mac-bg-secondary)',
      color: 'var(--mac-text-primary)'
    },
    error: {
      border: '1px solid var(--mac-error)',
      background: 'var(--mac-bg-primary)',
      color: 'var(--mac-text-primary)'
    }
  };

  const currentVariant = error ? 'error' : variant;
  const currentSize = sizeStyles[size];
  const currentVariantStyle = variantStyles[currentVariant];
  const hasRightIcon = Boolean(Icon) && iconPosition === 'right';
  const hasValue = props.value !== undefined && props.value !== null && String(props.value).length > 0;
  const showClearButton = clearable && typeof onClear === 'function' && hasValue && !disabled;
  let paddingRight: string | number = (currentSize.padding as string).split(' ')[1];

  if (hasRightIcon && showClearButton) {
    paddingRight = '60px';
  } else if (hasRightIcon || showClearButton) {
    paddingRight = '40px';
  }

  const inputStyle: InputStyle = {
    width: '100%',
    boxSizing: 'border-box',
    paddingLeft: Icon && iconPosition === 'left' ? '40px' : (currentSize.padding as string).split(' ')[1],
    paddingRight,
    paddingTop: (currentSize.padding as string).split(' ')[0],
    paddingBottom: (currentSize.padding as string).split(' ')[0],
    borderRadius: 'var(--mac-radius-md)',
    fontSize: currentSize.fontSize,
    height: currentSize.height,
    outline: 'none',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    ...currentVariantStyle,
    ...(disabled && {
      opacity: 0.6,
      cursor: 'not-allowed',
      background: 'var(--mac-bg-tertiary)'
    }),
    ...style
  };

  const iconStyle: CSSProperties = {
    position: 'absolute',
    top: '50%',
    transform: 'translateY(-50%)',
    color: error ? 'var(--mac-error)' : 'var(--mac-text-tertiary)',
    width: '16px',
    height: '16px',
    pointerEvents: 'none',
    ...(iconPosition === 'left' ? { left: '12px' } : { right: '12px' })
  };

  const handleFocus = (e: FocusEvent<HTMLInputElement>) => {
    setIsFocused(true);
    if (!disabled) {
      e.currentTarget.style.borderColor = error ? 'var(--mac-error)' : 'var(--mac-accent-blue)';
      e.currentTarget.style.boxShadow = `0 0 0 3px ${error ? 'rgba(255, 59, 48, 0.1)' : 'rgba(0, 122, 255, 0.1)'}`;
    }
    if (props.onFocus) props.onFocus(e);
  };

  const handleBlur = (e: FocusEvent<HTMLInputElement>) => {
    setIsFocused(false);
    const borderVal = (currentVariantStyle.border as string | undefined) || '';
    e.currentTarget.style.borderColor = borderVal.split(' ')[2] || '';
    e.currentTarget.style.boxShadow = 'none';
    if (props.onBlur) props.onBlur(e);
  };

  const clearButtonStyle: CSSProperties = {
    position: 'absolute',
    top: '50%',
    transform: 'translateY(-50%)',
    right: hasRightIcon ? '40px' : '12px',
    background: 'none',
    border: 'none',
    padding: '2px',
    cursor: 'pointer',
    color: 'var(--mac-text-tertiary)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: '50%',
    outline: 'none',
    opacity: isFocused || hasValue ? 0.7 : 0,
    transition: 'opacity 0.2s ease, color 0.2s ease',
  };

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      {Icon && (
        <Icon style={iconStyle} />
      )}
      <input
        ref={ref}
        className={className}
        style={inputStyle}
        disabled={disabled}
        onFocus={handleFocus}
        onBlur={handleBlur}
        {...props}
      />
      {showClearButton && (
        <button
          type="button"
          aria-label="Clear input"
          title="Clear input"
          style={clearButtonStyle}
          onClick={(e: MouseEvent<HTMLButtonElement>) => {
            e.stopPropagation();
            onClear?.();
          }}
          onMouseEnter={(e: MouseEvent<HTMLButtonElement>) => {
            e.currentTarget.style.color = 'var(--mac-text-secondary)';
            e.currentTarget.style.opacity = '1';
          }}
          onMouseLeave={(e: MouseEvent<HTMLButtonElement>) => {
            e.currentTarget.style.color = 'var(--mac-text-tertiary)';
            e.currentTarget.style.opacity = '0.7';
          }}
          onFocus={(e: FocusEvent<HTMLButtonElement>) => {
            e.currentTarget.style.boxShadow = '0 0 0 2px var(--mac-accent-blue)';
            e.currentTarget.style.opacity = '1';
          }}
          onBlur={(e: FocusEvent<HTMLButtonElement>) => {
            e.currentTarget.style.boxShadow = 'none';
            e.currentTarget.style.opacity = '0.7';
          }}
        >
          <XCircle size={16} />
        </button>
      )}
    </div>
  );
});


Input.propTypes = {
  ...(Input.propTypes || {}),
  className: PropTypes.any,
  clearable: PropTypes.any,
  disabled: PropTypes.any,
  error: PropTypes.any,
  icon: PropTypes.any,
  iconPosition: PropTypes.any,
  onBlur: PropTypes.any,
  onClear: PropTypes.any,
  onFocus: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
  value: PropTypes.any,
  variant: PropTypes.any,
};

Input.displayName = 'Input';

export default Input;
