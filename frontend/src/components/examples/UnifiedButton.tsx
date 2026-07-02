/**
 * Unified Button Component
 * Example of a macOS-native button pattern using existing clinic tokens.
 *
 * This example is intentionally MUI-free. Clinic runtime UI should prefer
 * frontend/src/components/ui/macos before copying example code.
 */

import React from 'react';

type MedicalSpecialty = 'cardiology' | 'dermatology' | 'neurology' | 'dentistry' | 'orthopedics';
type UnifiedButtonVariant = 'contained' | 'outlined' | 'text';
type UnifiedButtonSize = 'small' | 'medium' | 'large';

interface UnifiedButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  medical?: MedicalSpecialty;
  loading?: boolean;
  variant?: UnifiedButtonVariant;
  size?: UnifiedButtonSize;
}

const medicalColorMap: Record<MedicalSpecialty, string> = {
  cardiology: 'var(--mac-medical-cardiology, #dc2626)',
  dermatology: 'var(--mac-medical-dermatology, #8b5cf6)',
  neurology: 'var(--mac-medical-neurology, #a855f7)',
  dentistry: 'var(--mac-medical-dentistry, #059669)',
  orthopedics: 'var(--mac-medical-orthopedics, #2563eb)',
};

const sizeStyles: Record<UnifiedButtonSize, React.CSSProperties> = {
  small: {
    minHeight: 28,
    padding: '6px 12px',
    fontSize: 'var(--mac-font-size-sm)',
  },
  medium: {
    minHeight: 32,
    padding: '8px 16px',
    fontSize: 'var(--mac-font-size-base)',
  },
  large: {
    minHeight: 40,
    padding: '12px 20px',
    fontSize: 'var(--mac-font-size-lg)',
  },
};

function getVariantStyles(
  variant: UnifiedButtonVariant,
  medical?: MedicalSpecialty
): React.CSSProperties {
  const accentColor = medical ? medicalColorMap[medical] : 'var(--mac-accent-blue)';

  if (variant === 'outlined') {
    return {
      color: accentColor,
      background: 'transparent',
      border: `1px solid ${accentColor}`,
    };
  }

  if (variant === 'text') {
    return {
      color: accentColor,
      background: 'transparent',
      border: '1px solid transparent',
      paddingInline: 8,
    };
  }

  return {
    color: 'var(--mac-text-on-accent)',
    background: accentColor,
    border: `1px solid ${accentColor}`,
    boxShadow: 'var(--mac-shadow-sm)',
  };
}

export const UnifiedButton = React.forwardRef<HTMLButtonElement, UnifiedButtonProps>(
  (
    {
      medical,
      loading = false,
      children,
      disabled = false,
      variant = 'contained',
      size = 'medium',
      style,
      type = 'button',
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading;

    const buttonStyle: React.CSSProperties = {
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: 8,
      borderRadius: 'var(--mac-radius-md)',
      fontFamily: 'var(--mac-font-family, -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif)',
      fontWeight: 'var(--mac-font-weight-semibold)',
      lineHeight: 1.2,
      cursor: isDisabled ? 'not-allowed' : 'pointer',
      transition: 'all var(--mac-duration-normal) var(--mac-ease)',
      opacity: isDisabled ? 0.58 : 1,
      outlineOffset: 2,
      ...sizeStyles[size],
      ...getVariantStyles(variant, medical),
      ...style,
    };

    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        aria-busy={loading}
        style={buttonStyle}
        {...props}
      >
        {loading ? 'Loading...' : children}
      </button>
    );
  }
);

UnifiedButton.displayName = 'UnifiedButton';

export const UnifiedButtonShowcase = () => {
  return (
    <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', padding: '24px' }}>
      <UnifiedButton variant="contained">Default Primary</UnifiedButton>
      <UnifiedButton variant="outlined">Outlined</UnifiedButton>
      <UnifiedButton variant="text">Text</UnifiedButton>

      <UnifiedButton medical="cardiology">Cardiology</UnifiedButton>
      <UnifiedButton medical="dermatology">Dermatology</UnifiedButton>
      <UnifiedButton medical="neurology">Neurology</UnifiedButton>
      <UnifiedButton medical="dentistry">Dentistry</UnifiedButton>
      <UnifiedButton medical="orthopedics">Orthopedics</UnifiedButton>

      <UnifiedButton disabled>Disabled</UnifiedButton>
      <UnifiedButton loading>Loading...</UnifiedButton>

      <UnifiedButton size="small">Small</UnifiedButton>
      <UnifiedButton size="medium">Medium</UnifiedButton>
      <UnifiedButton size="large">Large</UnifiedButton>
    </div>
  );
};
