/**
 * Component Overrides
 * Consistent styling for all MUI components via theme
 * Prevents wrapper components and scattered inline styles
 */

import { Components, Theme } from '@mui/material/styles';
import { spacing, borderRadius, transitions, easing } from './tokens';

export const createComponentOverrides = (theme: Theme): Components => ({
  // ========================================================================
  // BUTTON OVERRIDES
  // ========================================================================
  MuiButton: {
    defaultProps: {
      disableElevation: false,
      disableTouchRipple: false,
    },
    styleOverrides: {
      root: {
        borderRadius: borderRadius.md,
        textTransform: 'none',
        fontWeight: 600,
        transition: `all ${transitions.base}ms ${easing.easeInOut}`,
        padding: `${spacing[2]}px ${spacing[4]}px`,

        '&:focus-visible': {
          outline: `2px solid ${theme.palette.primary.main}`,
          outlineOffset: '2px',
        },

        '&:disabled': {
          opacity: 0.6,
        },
      },
      contained: {
        boxShadow: 'none',
        '&:hover': {
          boxShadow: theme.palette.mode === 'light'
            ? '0 4px 12px rgba(0, 0, 0, 0.15)'
            : '0 4px 12px rgba(0, 0, 0, 0.3)',
        },
      },
      outlined: {
        borderWidth: 2,
        '&:hover': {
          borderWidth: 2,
        },
      },
      sizeSmall: {
        padding: `${spacing[1]}px ${spacing[3]}px`,
        fontSize: '0.875rem',
      },
      sizeLarge: {
        padding: `${spacing[3]}px ${spacing[6]}px`,
        fontSize: '1rem',
      },
    },
  },

  // ========================================================================
  // CARD OVERRIDES
  // ========================================================================
  MuiCard: {
    styleOverrides: {
      root: {
        borderRadius: borderRadius.lg,
        transition: `all ${transitions.base}ms ${easing.easeInOut}`,
        backdropFilter: 'blur(8px)',

        '&:focus-within': {
          outline: `2px solid ${theme.palette.primary.main}`,
          outlineOffset: '2px',
        },
      },
    },
  },

  // ========================================================================
  // TEXTFIELD OVERRIDES
  // ========================================================================
  MuiTextField: {
    defaultProps: {
      variant: 'outlined',
      fullWidth: true,
    },
  },

  MuiOutlinedInput: {
    styleOverrides: {
      root: {
        borderRadius: borderRadius.md,
        transition: `border-color ${transitions.base}ms ${easing.easeInOut}`,

        '&:focus-within': {
          outline: 'none',
        },

        '&.Mui-focused': {
          '& .MuiOutlinedInput-notchedOutline': {
            borderColor: theme.palette.primary.main,
            borderWidth: 2,
          },
        },

        '&:disabled': {
          backgroundColor: theme.palette.action.disabledBackground,
        },
      },
      input: {
        padding: `${spacing[2]}px ${spacing[3]}px`,
        fontSize: fontSize.base,
      },
    },
  },

  // ========================================================================
  // DIALOG OVERRIDES
  // ========================================================================
  MuiDialog: {
    styleOverrides: {
      paper: {
        borderRadius: borderRadius.lg,
        transition: `all ${transitions.slow}ms ${easing.easeInOut}`,
      },
    },
  },

  // ========================================================================
  // CHIP OVERRIDES
  // ========================================================================
  MuiChip: {
    styleOverrides: {
      root: {
        borderRadius: borderRadius.xl,
        fontWeight: 500,
        height: 'auto',
        padding: `${spacing[1]}px ${spacing[3]}px`,
      },
      filled: {
        backgroundColor: theme.palette.action.hover,
      },
      outlined: {
        borderWidth: 2,
      },
    },
  },

  // ========================================================================
  // TABLE OVERRIDES
  // ========================================================================
  MuiTableCell: {
    styleOverrides: {
      root: {
        borderColor: theme.palette.divider,
        padding: `${spacing[3]}px`,
      },
      head: {
        fontWeight: 700,
        backgroundColor: theme.palette.mode === 'light'
          ? theme.palette.grey[100]
          : theme.palette.grey[800],
      },
    },
  },

  // ========================================================================
  // MENU ITEM OVERRIDES
  // ========================================================================
  MuiMenuItem: {
    styleOverrides: {
      root: {
        borderRadius: borderRadius.sm,
        margin: `${spacing[1]}px ${spacing[1]}px`,
        transition: `all ${transitions.fast}ms ${easing.easeInOut}`,

        '&:focus-visible': {
          outline: `2px solid ${theme.palette.primary.main}`,
          outlineOffset: '-2px',
        },
      },
    },
  },

  // ========================================================================
  // BADGE OVERRIDES
  // ========================================================================
  MuiBadge: {
    styleOverrides: {
      badge: {
        borderRadius: borderRadius.full,
        fontWeight: 700,
        padding: `0 ${spacing[1]}px`,
      },
    },
  },

  // ========================================================================
  // AVATAR OVERRIDES
  // ========================================================================
  MuiAvatar: {
    styleOverrides: {
      root: {
        borderRadius: borderRadius.md,
      },
    },
  },

  // ========================================================================
  // ALERT OVERRIDES
  // ========================================================================
  MuiAlert: {
    styleOverrides: {
      root: {
        borderRadius: borderRadius.lg,
        borderWidth: 2,
        borderStyle: 'solid',
      },
    },
  },
});

// Re-export for convenience
export { fontSize } from './tokens';
