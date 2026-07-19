import React, { useEffect, useRef, useCallback, type CSSProperties, type FocusEvent, type FormEvent } from 'react';
import PropTypes from 'prop-types';

type TextareaSize = 'sm' | 'md' | 'lg';
type TextareaVariant = 'default' | 'filled' | 'error';

interface TextareaProps extends Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, 'children' | 'style' | 'size'> {
  className?: string;
  style?: CSSProperties;
  size?: TextareaSize | string;
  variant?: TextareaVariant | string;
  error?: boolean;
  disabled?: boolean;
  autoResize?: boolean;
  minRows?: number;
  maxRows?: number;
  textareaStyle?: CSSProperties;
  // Backward-compat: many callers pass label/rows
  label?: React.ReactNode;
  rows?: number;
  hint?: React.ReactNode;
  maxLength?: number;
}

interface TextareaStyle extends CSSProperties {
  transition?: string;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(({
  className,
  style,
  size = 'md',
  variant = 'default',
  error,
  disabled,
  autoResize = true,
  minRows = 3,
  maxRows = 10,
  textareaStyle = {},
  ...props
}, ref) => {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const internalRef = (ref || textareaRef) as React.RefObject<HTMLTextAreaElement>;

  const sizeStyles: Record<TextareaSize, CSSProperties> = {
    sm: {
      padding: '8px 12px',
      fontSize: 'var(--mac-font-size-sm)',
      lineHeight: '1.4'
    },
    md: {
      padding: '12px 16px',
      fontSize: 'var(--mac-font-size-sm)',
      lineHeight: '1.5'
    },
    lg: {
      padding: '16px 20px',
      fontSize: 'var(--mac-font-size-base)',
      lineHeight: '1.6'
    }
  };

  const variantStyles: Record<TextareaVariant, CSSProperties> = {
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

  const textareaStyles: TextareaStyle = {
    width: '100%',
    borderRadius: 'var(--mac-radius-md)',
    fontSize: currentSize.fontSize,
    lineHeight: currentSize.lineHeight,
    outline: 'none',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    resize: autoResize ? 'none' : 'vertical',
    overflow: autoResize ? 'hidden' : 'auto',
    ...currentSize,
    ...currentVariantStyle,
    ...(disabled && {
      opacity: 0.6,
      cursor: 'not-allowed',
      background: 'var(--mac-bg-tertiary)'
    }),
    ...style,
    ...textareaStyle
  };

  const handleFocus = (e: FocusEvent<HTMLTextAreaElement>) => {
    if (!disabled) {
      e.currentTarget.style.borderColor = error ? 'var(--mac-error)' : 'var(--mac-accent-blue)';
      e.currentTarget.style.boxShadow = `0 0 0 3px ${error ? 'rgba(255, 59, 48, 0.1)' : 'rgba(0, 122, 255, 0.1)'}`;
    }
  };

  const handleBlur = (e: FocusEvent<HTMLTextAreaElement>) => {
    const borderVal = (currentVariantStyle.border as string | undefined) || '';
    e.currentTarget.style.borderColor = borderVal.split(' ')[2] || '';
    e.currentTarget.style.boxShadow = 'none';
  };

  const adjustHeight = useCallback(() => {
    if (autoResize && internalRef.current) {
      const textarea = internalRef.current;
      textarea.style.height = 'auto';

      const scrollHeight = textarea.scrollHeight;
      const lineHeight = parseInt(String(currentSize.lineHeight)) * parseInt(String(currentSize.fontSize));
      const minHeight = lineHeight * minRows;
      const maxHeight = lineHeight * maxRows;

      const newHeight = Math.min(Math.max(scrollHeight, minHeight), maxHeight);
      textarea.style.height = `${newHeight}px`;
    }
  }, [autoResize, internalRef, currentSize.lineHeight, currentSize.fontSize, minRows, maxRows]);

  useEffect(() => {
    if (autoResize) {
      adjustHeight();
    }
  }, [autoResize, adjustHeight, props.value, props.defaultValue]);

  return (
    <textarea
      ref={internalRef}
      className={className}
      style={textareaStyles}
      disabled={disabled}
      onFocus={handleFocus}
      onBlur={handleBlur}
      onInput={(e: FormEvent<HTMLTextAreaElement>) => adjustHeight()}
      rows={minRows}
      {...props}
    />
  );
});


Textarea.propTypes = {
  ...(Textarea.propTypes || {}),
  autoResize: PropTypes.any,
  className: PropTypes.any,
  defaultValue: PropTypes.any,
  disabled: PropTypes.any,
  error: PropTypes.any,
  maxRows: PropTypes.any,
  minRows: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
  textareaStyle: PropTypes.object,
  value: PropTypes.any,
  variant: PropTypes.any,
};

Textarea.displayName = 'Textarea';

export default Textarea;
