/**
 * Unified Card Component
 * Example of proper MUI Card using theme tokens with variants
 */

import React from 'react';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CardHeader from '@mui/material/CardHeader';
import CardActions from '@mui/material/CardActions';
import Typography from '@mui/material/Typography';
import { styled } from '@mui/material/styles';
import { spacing, borderRadius, shadows, shadowsDark, transitions, easing } from '@/theme/tokens';
import { useTheme } from '@mui/material/styles';

// ============================================================================
// CARD VARIANTS
// ============================================================================
type CardVariant = 'elevated' | 'outlined' | 'filled' | 'soft' | 'glass' | 'interactive';

interface UnifiedCardProps {
  variant?: CardVariant;
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
  onClick?: () => void;
  interactive?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

// ============================================================================
// STYLED VARIANTS
// ============================================================================
const ElevatedCard = styled(Card)(({ theme }) => ({
  border: 'none',
  boxShadow: theme.palette.mode === 'light' ? shadows.md : shadowsDark.md,
  transition: `all ${transitions.base} ${easing.easeInOut}`,
  '&:hover': {
    boxShadow: theme.palette.mode === 'light' ? shadows.lg : shadowsDark.lg,
  },
}));

const OutlinedCard = styled(Card)(({ theme }) => ({
  border: `1px solid ${theme.palette.divider}`,
  boxShadow: 'none',
  backgroundColor: theme.palette.background.paper,
  transition: `all ${transitions.base} ${easing.easeInOut}`,
  '&:hover': {
    borderColor: theme.palette.primary.main,
    boxShadow: theme.palette.mode === 'light' ? shadows.sm : shadowsDark.sm,
  },
}));

const FilledCard = styled(Card)(({ theme }) => ({
  backgroundColor: theme.palette.action.hover,
  border: 'none',
  boxShadow: 'none',
  transition: `all ${transitions.base} ${easing.easeInOut}`,
  '&:hover': {
    backgroundColor: theme.palette.action.selected,
  },
}));

const SoftCard = styled(Card)(({ theme }) => ({
  backgroundColor: theme.palette.mode === 'light'
    ? 'rgba(59, 130, 246, 0.05)'
    : 'rgba(147, 51, 234, 0.1)',
  border: `1px solid ${theme.palette.mode === 'light'
    ? 'rgba(59, 130, 246, 0.2)'
    : 'rgba(147, 51, 234, 0.3)'}`,
  boxShadow: 'none',
  transition: `all ${transitions.base} ${easing.easeInOut}`,
  '&:hover': {
    backgroundColor: theme.palette.mode === 'light'
      ? 'rgba(59, 130, 246, 0.1)'
      : 'rgba(147, 51, 234, 0.15)',
  },
}));

const GlassCard = styled(Card)(({ theme }) => ({
  backdropFilter: 'blur(10px)',
  backgroundColor: theme.palette.mode === 'light'
    ? 'rgba(255, 255, 255, 0.7)'
    : 'rgba(30, 30, 40, 0.7)',
  border: `1px solid ${theme.palette.mode === 'light'
    ? 'rgba(255, 255, 255, 0.5)'
    : 'rgba(255, 255, 255, 0.1)'}`,
  boxShadow: 'none',
  transition: `all ${transitions.base} ${easing.easeInOut}`,
  '&:hover': {
    backgroundColor: theme.palette.mode === 'light'
      ? 'rgba(255, 255, 255, 0.8)'
      : 'rgba(40, 40, 50, 0.8)',
    borderColor: theme.palette.mode === 'light'
      ? 'rgba(255, 255, 255, 0.7)'
      : 'rgba(255, 255, 255, 0.2)',
  },
}));

const InteractiveCard = styled(Card)(({ theme }) => ({
  border: `1px solid ${theme.palette.divider}`,
  boxShadow: theme.palette.mode === 'light' ? shadows.sm : shadowsDark.sm,
  cursor: 'pointer',
  transition: `all ${transitions.base} ${easing.easeInOut}`,
  '&:hover': {
    transform: 'translateY(-4px)',
    boxShadow: theme.palette.mode === 'light' ? shadows.lg : shadowsDark.lg,
    borderColor: theme.palette.primary.main,
  },
  '&:active': {
    transform: 'translateY(-2px)',
  },
}));

// ============================================================================
// MAIN COMPONENT
// ============================================================================
export const UnifiedCard = React.forwardRef<HTMLDivElement, UnifiedCardProps>(
  ({ 
    variant = 'outlined', 
    title, 
    subtitle, 
    children, 
    actions,
    onClick,
    size = 'md',
  }, ref) => {
    const theme = useTheme();

    // Get padding based on size
    const getPadding = (size: 'sm' | 'md' | 'lg') => {
      switch (size) {
        case 'sm':
          return spacing[3];
        case 'md':
          return spacing[4];
        case 'lg':
          return spacing[6];
        default:
          return spacing[4];
      }
    };

    // Select variant component
    const CardComponent = {
      elevated: ElevatedCard,
      outlined: OutlinedCard,
      filled: FilledCard,
      soft: SoftCard,
      glass: GlassCard,
      interactive: InteractiveCard,
    }[variant];

    return (
      <CardComponent
        ref={ref}
        onClick={onClick}
        sx={{
          borderRadius: borderRadius.lg,
        }}
      >
        {(title || subtitle) && (
          <CardHeader
            title={title}
            subheader={subtitle}
            titleTypographyProps={{ variant: 'h5' }}
            subheaderTypographyProps={{ variant: 'body2' }}
            sx={{
              paddingBottom: spacing[3],
            }}
          />
        )}

        <CardContent
          sx={{
            padding: getPadding(size),
            '&:last-child': {
              paddingBottom: getPadding(size),
            },
          }}
        >
          {children}
        </CardContent>

        {actions && (
          <CardActions
            sx={{
              padding: spacing[4],
              paddingTop: 0,
              borderTop: `1px solid ${theme.palette.divider}`,
            }}
          >
            {actions}
          </CardActions>
        )}
      </CardComponent>
    );
  }
);

UnifiedCard.displayName = 'UnifiedCard';

// ============================================================================
// USAGE EXAMPLES
// ============================================================================
import Button from '@mui/material/Button';

export const UnifiedCardShowcase = () => {
  return (
    <div style={{ display: 'grid', gap: '24px', padding: '24px', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
      {/* Elevated variant */}
      <UnifiedCard variant="elevated" title="Elevated Card" subtitle="With shadow">
        <Typography>This card has a subtle shadow elevation.</Typography>
      </UnifiedCard>

      {/* Outlined variant */}
      <UnifiedCard variant="outlined" title="Outlined Card" subtitle="Minimal style">
        <Typography>This card uses just a border for definition.</Typography>
      </UnifiedCard>

      {/* Filled variant */}
      <UnifiedCard variant="filled" title="Filled Card" subtitle="Background colored">
        <Typography>This card has a filled background.</Typography>
      </UnifiedCard>

      {/* Soft variant */}
      <UnifiedCard variant="soft" title="Soft Card" subtitle="Subtle color">
        <Typography>This card uses a soft background tint.</Typography>
      </UnifiedCard>

      {/* Glass variant */}
      <UnifiedCard variant="glass" title="Glass Card" subtitle="Modern blur effect">
        <Typography>This card uses a glassmorphism effect.</Typography>
      </UnifiedCard>

      {/* Interactive variant */}
      <UnifiedCard 
        variant="interactive" 
        title="Interactive Card" 
        subtitle="Hover & click"
        onClick={() => alert('Card clicked!')}
      >
        <Typography>This card responds to interaction with elevation change.</Typography>
      </UnifiedCard>

      {/* With actions */}
      <UnifiedCard 
        variant="outlined"
        title="Card with Actions"
        subtitle="Contains buttons"
        actions={
          <>
            <Button variant="text">Cancel</Button>
            <Button variant="contained" color="primary">Save</Button>
          </>
        }
      >
        <Typography>This card demonstrates the CardActions component.</Typography>
      </UnifiedCard>

      {/* Large card */}
      <UnifiedCard variant="elevated" title="Large Card" size="lg">
        <Typography variant="h6" gutterBottom>Medical Department Card</Typography>
        <Typography>
          This is a larger card variant useful for displaying detailed information like patient records, diagnostic results, or department details.
        </Typography>
      </UnifiedCard>
    </div>
  );
};
