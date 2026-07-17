import React, { type ReactNode, type CSSProperties } from 'react';
import PropTypes from 'prop-types';

type LabelVariant = 'default' | 'muted' | 'error';
type LabelSize = 'sm' | 'md' | 'lg';

interface LabelProps extends Omit<React.LabelHTMLAttributes<HTMLLabelElement>, 'children'> {
  children?: ReactNode;
  className?: string;
  variant?: LabelVariant;
  size?: LabelSize;
  required?: boolean;
  style?: CSSProperties;
}

interface LabelStyle extends CSSProperties {
  transition?: string;
}

const Label = React.forwardRef<HTMLLabelElement, LabelProps>(({
  children,
  className = '',
  variant = 'default',
  size = 'md',
  required = false,
  style = {},
  ...props
}, ref) => {
  const baseStyles: LabelStyle = {
    fontSize: '14px',
    fontWeight: '500',
    lineHeight: '1',
    cursor: 'pointer',
    transition: 'color var(--mac-duration-normal) var(--mac-ease)'
  };

  const variants: Record<LabelVariant, CSSProperties> = {
    default: { color: 'var(--mac-text-primary)' },
    muted: { color: 'var(--mac-text-secondary)' },
    error: { color: 'var(--mac-error)' }
  };

  const sizes: Record<LabelSize, CSSProperties> = {
    sm: { fontSize: '12px' },
    md: { fontSize: '14px' },
    lg: { fontSize: '16px' }
  };

  const labelStyles: CSSProperties = {
    ...baseStyles,
    ...variants[variant],
    ...sizes[size],
    ...style
  };

  return (
    <label
      ref={ref}
      style={labelStyles}
      className={className}
      {...props}
    >
      {children}
      {required && (
        <span style={{ color: 'var(--mac-error)', marginLeft: '4px' }}>
          *
        </span>
      )}
    </label>
  );
});


Label.propTypes = {
  ...(Label.propTypes || {}),
  children: PropTypes.any,
  className: PropTypes.any,
  required: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
  variant: PropTypes.any,
};

Label.displayName = 'Label';

export default Label;
