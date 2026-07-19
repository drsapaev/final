import React, { useState, useEffect, type CSSProperties, type ReactNode } from 'react';
import PropTypes from 'prop-types';

type SegmentedSize = 'small' | 'default' | 'large' | 'sm' | 'md' | 'lg' | string;
type SegmentedVariant = 'default' | 'filled' | 'outline' | string;
type SegmentedValue = string | number;

interface SegmentedOption {
  value: SegmentedValue;
  label: ReactNode;
  disabled?: boolean;
}

interface SegmentedControlProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'children' | 'style' | 'onChange'> {
  options?: Array<SegmentedOption | SegmentedValue>;
  value?: SegmentedValue;
  defaultValue?: SegmentedValue;
  onChange?: (value: SegmentedValue) => void;
  disabled?: boolean;
  size?: SegmentedSize;
  variant?: SegmentedVariant;
  className?: string;
  style?: CSSProperties;
  label?: ReactNode;
}

interface SegmentedStyle extends CSSProperties {
  transition?: string;
}

interface SegmentedDimensions {
  height: number;
  fontSize: number;
  padding: string;
}

function normalizeOption(option: SegmentedOption | SegmentedValue): SegmentedOption {
  if (option !== null && typeof option === 'object' && 'value' in (option as SegmentedOption)) {
    return option as SegmentedOption;
  }
  const v = option as SegmentedValue;
  return { value: v, label: String(v) };
}

const SegmentedControl = React.forwardRef<HTMLDivElement, SegmentedControlProps>(({
  options = [],
  value: valueProp,
  defaultValue,
  onChange,
  disabled = false,
  size = 'default',
  variant = 'default',
  className = '',
  style = {},
  ...props
}, ref) => {
  void variant;
  const normalizedOptions = options.map(normalizeOption);
  const firstValue = normalizedOptions[0]?.value;
  const [value, setValue] = useState<SegmentedValue | undefined>(valueProp ?? defaultValue ?? firstValue);

  useEffect(() => {
    if (valueProp !== undefined) setValue(valueProp);
  }, [valueProp]);

  const sizes: Record<SegmentedSize, SegmentedDimensions> = {
    small: { height: 24, fontSize: 11, padding: '4px 8px' },
    default: { height: 28, fontSize: 12, padding: '6px 12px' },
    large: { height: 32, fontSize: 13, padding: '8px 16px' }
  };

  const s = sizes[size] || sizes.default;

  const handleSelect = (optionValue: SegmentedValue) => {
    if (disabled) return;
    if (valueProp === undefined) setValue(optionValue);
    onChange && onChange(optionValue);
  };

  const containerStyles: CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    background: 'var(--mac-bg-tertiary)',
    borderRadius: '8px',
    padding: '2px',
    border: '1px solid var(--mac-border)',
    boxShadow: 'var(--mac-shadow-1)',
    ...style
  };

  const segmentStyles: SegmentedStyle = {
    height: s.height,
    fontSize: `${s.fontSize}px`,
    padding: s.padding,
    borderRadius: '6px',
    border: 'none',
    background: 'transparent',
    color: 'var(--mac-text-secondary)',
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all 160ms cubic-bezier(0.2,0.8,0.2,1)',
    fontWeight: '500',
    whiteSpace: 'nowrap',
    position: 'relative',
    outline: 'none'
  };

  const activeSegmentStyles: CSSProperties = {
    background: 'var(--mac-bg-primary)',
    color: 'var(--mac-text-primary)',
    boxShadow: 'var(--mac-shadow-2)',
    fontWeight: '600'
  };

  const disabledStyles: CSSProperties = {
    opacity: 0.5,
    cursor: 'not-allowed'
  };

  return (
    <div
      ref={ref}
      className={`mac-segmented-control ${className}`}
      style={containerStyles}
      role="tablist"
      aria-orientation="horizontal"
      {...props}
    >
      {normalizedOptions.map((option, index) => {
        const optionValue = option.value;
        const optionLabel = option.label;
        const isActive = optionValue === value;
        const isFirst = index === 0;
        const isLast = index === normalizedOptions.length - 1;

        return (
          <button
            key={String(optionValue)}
            type="button"
            role="tab"
            aria-selected={isActive}
            aria-controls={`panel-${String(optionValue)}`}
            className="mac-segment"
            style={{
              ...segmentStyles,
              ...(isActive && activeSegmentStyles),
              ...(disabled && disabledStyles),
              marginLeft: isFirst ? 0 : '1px',
              marginRight: isLast ? 0 : '1px'
            }}
            onClick={() => handleSelect(optionValue)}
            disabled={disabled}
            tabIndex={isActive ? 0 : -1}
          >
            {optionLabel}
            {isActive && (
              <div
                className="mac-segment-indicator"
                style={{
                  position: 'absolute',
                  top: '50%',
                  left: '50%',
                  transform: 'translate(-50%, -50%)',
                  width: 'calc(100% - 4px)',
                  height: 'calc(100% - 4px)',
                  borderRadius: '4px',
                  background: 'var(--mac-accent-blue-500)',
                  opacity: 0.1,
                  pointerEvents: 'none'
                }}
              />
            )}
          </button>
        );
      })}
      <style>{`
        .mac-segment:hover:not(:disabled) {
          background: var(--mac-bg-elev-1);
          color: var(--mac-text-primary);
        }
        .mac-segment:focus-visible {
          outline: 2px solid color-mix(in srgb, var(--mac-accent-blue-500), transparent 60%);
          outline-offset: 2px;
        }
        .mac-segment:active:not(:disabled) {
          transform: scale(0.98);
        }
        @media (prefers-reduced-motion: reduce) {
          .mac-segment {
            transition: none;
          }
        }
        @media (prefers-color-scheme: dark) {
          .mac-segmented-control {
            background: var(--mac-bg-elev-1);
            border-color: var(--mac-border);
          }
        }
      `}</style>
    </div>
  );
});


SegmentedControl.propTypes = {
  ...(SegmentedControl.propTypes || {}),
  className: PropTypes.any,
  defaultValue: PropTypes.any,
  disabled: PropTypes.any,
  onChange: PropTypes.any,
  options: PropTypes.any,
  size: PropTypes.any,
  style: PropTypes.any,
  value: PropTypes.any,
  variant: PropTypes.any,
};

SegmentedControl.displayName = 'SegmentedControl';

export default SegmentedControl;
