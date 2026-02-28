/**
 * Unified Button Component
 * Example of proper MUI component using theme tokens
 */

import React from 'react';
import Button from '@mui/material/Button';
import { styled } from '@mui/material/styles';
import { spacing, colorsLight, colorsDark, transitions, easing } from '@/theme/tokens';
import { useTheme } from '@mui/material/styles';

// ============================================================================
// STYLED VARIANT EXAMPLE
// ============================================================================
const StyledMedicalButton = styled(Button)(({ theme }) => ({
  borderRadius: theme.shape.borderRadius,
  fontWeight: 600,
  textTransform: 'none',
  transition: `all ${transitions.base} ${easing.easeInOut}`,
  
  '&:hover': {
    transform: 'translateY(-2px)',
    boxShadow: theme.palette.mode === 'light' 
      ? '0 10px 15px -3px rgba(0, 0, 0, 0.1)'
      : '0 10px 15px -3px rgba(0, 0, 0, 0.4)',
  },
  
  '&:active': {
    transform: 'translateY(0)',
  },
}));

// ============================================================================
// MEDICAL SPECIALTY BUTTON VARIANT
// ============================================================================
type MedicalSpecialty = 'cardiology' | 'dermatology' | 'neurology' | 'dentistry' | 'orthopedics';

interface UnifiedButtonProps extends React.ComponentProps<typeof Button> {
  medical?: MedicalSpecialty;
  loading?: boolean;
}

export const UnifiedButton = React.forwardRef<HTMLButtonElement, UnifiedButtonProps>(
  ({ medical, loading, children, disabled, variant = 'contained', ...props }, ref) => {
    const muiTheme = useTheme();
    const isDark = muiTheme.palette.mode === 'dark';

    const getMedicalColor = (specialty: MedicalSpecialty) => {
      const colors = isDark ? colorsDark : colorsLight;
      const specialtyMap: Record<MedicalSpecialty, keyof typeof colors> = {
        cardiology: 'cardiology',
        dermatology: 'dermatology',
        neurology: 'neurology',
        dentistry: 'dentistry',
        orthopedics: 'orthopedics',
      };

      const colorPalette = colors[specialtyMap[specialty]];
      return {
        main: colorPalette[500],
        light: colorPalette[300],
        dark: colorPalette[700],
      };
    };

    const buttonSx = medical ? {
      backgroundColor: getMedicalColor(medical).main,
      color: '#ffffff',
      '&:hover': {
        backgroundColor: getMedicalColor(medical).dark,
      },
      '&:disabled': {
        backgroundColor: muiTheme.palette.action.disabledBackground,
        color: muiTheme.palette.action.disabled,
      },
    } : {};

    return (
      <StyledMedicalButton
        ref={ref}
        variant={variant}
        disabled={disabled || loading}
        sx={buttonSx}
        {...props}
      >
        {loading ? '⏳ Loading...' : children}
      </StyledMedicalButton>
    );
  }
);

UnifiedButton.displayName = 'UnifiedButton';

// ============================================================================
// USAGE EXAMPLES
// ============================================================================
export const UnifiedButtonShowcase = () => {
  return (
    <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', padding: '24px' }}>
      {/* Standard variants */}
      <UnifiedButton variant="contained">Default Primary</UnifiedButton>
      <UnifiedButton variant="outlined">Outlined</UnifiedButton>
      <UnifiedButton variant="text">Text</UnifiedButton>

      {/* Medical specialties */}
      <UnifiedButton medical="cardiology">Cardiology</UnifiedButton>
      <UnifiedButton medical="dermatology">Dermatology</UnifiedButton>
      <UnifiedButton medical="neurology">Neurology</UnifiedButton>
      <UnifiedButton medical="dentistry">Dentistry</UnifiedButton>
      <UnifiedButton medical="orthopedics">Orthopedics</UnifiedButton>

      {/* States */}
      <UnifiedButton disabled>Disabled</UnifiedButton>
      <UnifiedButton loading>Loading...</UnifiedButton>

      {/* Sizes */}
      <UnifiedButton size="small">Small</UnifiedButton>
      <UnifiedButton size="medium">Medium</UnifiedButton>
      <UnifiedButton size="large">Large</UnifiedButton>
    </div>
  );
};
