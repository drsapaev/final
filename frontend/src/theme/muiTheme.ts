/**
 * Unified MUI v5 Theme
 * Single createTheme() implementation using tokens
 */

import { createTheme, ThemeOptions } from '@mui/material/styles';
import {
  spacing,
  borderRadius,
  fontSize,
  fontWeight,
  lineHeight,
  letterSpacing,
  shadows,
  shadowsDark,
  transitions,
  easing,
  colorsLight,
  colorsDark,
} from './tokens';

// ============================================================================
// LIGHT MODE THEME
// ============================================================================
const lightThemeConfig: ThemeOptions = {
  palette: {
    mode: 'light',
    primary: {
      main: colorsLight.primary[500],
      light: colorsLight.primary[300],
      dark: colorsLight.primary[700],
      contrastText: '#ffffff',
    },
    secondary: {
      main: colorsLight.secondary[500],
      light: colorsLight.secondary[300],
      dark: colorsLight.secondary[700],
      contrastText: '#ffffff',
    },
    success: {
      main: colorsLight.success[500],
      light: colorsLight.success[300],
      dark: colorsLight.success[700],
      contrastText: '#ffffff',
    },
    warning: {
      main: colorsLight.warning[500],
      light: colorsLight.warning[300],
      dark: colorsLight.warning[700],
      contrastText: '#ffffff',
    },
    error: {
      main: colorsLight.danger[500],
      light: colorsLight.danger[300],
      dark: colorsLight.danger[700],
      contrastText: '#ffffff',
    },
    info: {
      main: colorsLight.info[500],
      light: colorsLight.info[300],
      dark: colorsLight.info[700],
      contrastText: '#ffffff',
    },
    background: {
      default: colorsLight.neutral[50],
      paper: colorsLight.neutral[0],
    },
    text: {
      primary: colorsLight.neutral[900],
      secondary: colorsLight.neutral[600],
      disabled: colorsLight.neutral[400],
    },
    divider: colorsLight.neutral[200],
    action: {
      active: colorsLight.primary[500],
      hover: colorsLight.primary[50],
      selected: colorsLight.primary[100],
      disabled: colorsLight.neutral[400],
      disabledBackground: colorsLight.neutral[100],
    },
  },

  typography: {
    fontFamily: [
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
    
    h1: {
      fontSize: fontSize['5xl'],
      fontWeight: fontWeight.bold,
      lineHeight: lineHeight.tight,
      letterSpacing: letterSpacing.tight,
    },
    h2: {
      fontSize: fontSize['4xl'],
      fontWeight: fontWeight.bold,
      lineHeight: lineHeight.tight,
      letterSpacing: letterSpacing.tight,
    },
    h3: {
      fontSize: fontSize['3xl'],
      fontWeight: fontWeight.semibold,
      lineHeight: lineHeight.snug,
      letterSpacing: letterSpacing.normal,
    },
    h4: {
      fontSize: fontSize['2xl'],
      fontWeight: fontWeight.semibold,
      lineHeight: lineHeight.snug,
      letterSpacing: letterSpacing.normal,
    },
    h5: {
      fontSize: fontSize.xl,
      fontWeight: fontWeight.semibold,
      lineHeight: lineHeight.normal,
      letterSpacing: letterSpacing.normal,
    },
    h6: {
      fontSize: fontSize.lg,
      fontWeight: fontWeight.semibold,
      lineHeight: lineHeight.normal,
      letterSpacing: letterSpacing.normal,
    },
    body1: {
      fontSize: fontSize.base,
      fontWeight: fontWeight.normal,
      lineHeight: lineHeight.normal,
      letterSpacing: letterSpacing.normal,
    },
    body2: {
      fontSize: fontSize.sm,
      fontWeight: fontWeight.normal,
      lineHeight: lineHeight.normal,
      letterSpacing: letterSpacing.normal,
    },
    subtitle1: {
      fontSize: fontSize.base,
      fontWeight: fontWeight.medium,
      lineHeight: lineHeight.normal,
      letterSpacing: letterSpacing.normal,
    },
    subtitle2: {
      fontSize: fontSize.sm,
      fontWeight: fontWeight.medium,
      lineHeight: lineHeight.normal,
      letterSpacing: letterSpacing.normal,
    },
    caption: {
      fontSize: fontSize.xs,
      fontWeight: fontWeight.normal,
      lineHeight: lineHeight.tight,
      letterSpacing: letterSpacing.wide,
    },
    overline: {
      fontSize: fontSize.xs,
      fontWeight: fontWeight.semibold,
      lineHeight: lineHeight.tight,
      letterSpacing: letterSpacing.widest,
      textTransform: 'uppercase',
    },
    button: {
      fontSize: fontSize.sm,
      fontWeight: fontWeight.semibold,
      lineHeight: lineHeight.tight,
      letterSpacing: letterSpacing.normal,
      textTransform: 'none',
    },
  },

  shape: {
    borderRadius: parseInt(borderRadius.default.replace('rem', '')) * 16,
  },

  spacing: (factor: number) => `${0.25 * factor}rem`,

  components: {
    // ========================================================================
    // Button
    // ========================================================================
    MuiButton: {
      defaultProps: {
        disableElevation: false,
        variant: 'contained',
      },
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: fontWeight.semibold,
          borderRadius: borderRadius.md,
          transition: `all ${transitions.base} ${easing.easeInOut}`,
          '&:hover': {
            transform: 'translateY(-2px)',
          },
        },
        containedPrimary: {
          backgroundColor: colorsLight.primary[500],
          color: '#ffffff',
          '&:hover': {
            backgroundColor: colorsLight.primary[600],
            boxShadow: shadows.lg,
          },
          '&:active': {
            backgroundColor: colorsLight.primary[700],
          },
          '&:disabled': {
            backgroundColor: colorsLight.neutral[200],
            color: colorsLight.neutral[400],
          },
        },
        containedSecondary: {
          backgroundColor: colorsLight.secondary[500],
          color: '#ffffff',
          '&:hover': {
            backgroundColor: colorsLight.secondary[600],
            boxShadow: shadows.lg,
          },
          '&:disabled': {
            backgroundColor: colorsLight.neutral[200],
            color: colorsLight.neutral[400],
          },
        },
        outlinedPrimary: {
          borderColor: colorsLight.primary[300],
          color: colorsLight.primary[600],
          '&:hover': {
            borderColor: colorsLight.primary[500],
            backgroundColor: colorsLight.primary[50],
          },
          '&:disabled': {
            borderColor: colorsLight.neutral[200],
            color: colorsLight.neutral[400],
          },
        },
        textPrimary: {
          color: colorsLight.primary[600],
          '&:hover': {
            backgroundColor: colorsLight.primary[50],
          },
          '&:disabled': {
            color: colorsLight.neutral[400],
          },
        },
        sizeSmall: {
          padding: '0.375rem 0.75rem',
          fontSize: fontSize.sm,
        },
        sizeMedium: {
          padding: '0.5rem 1rem',
          fontSize: fontSize.base,
        },
        sizeLarge: {
          padding: '0.75rem 1.5rem',
          fontSize: fontSize.lg,
        },
      },
    },

    // ========================================================================
    // Card / Paper
    // ========================================================================
    MuiCard: {
      defaultProps: {
        elevation: 0,
      },
      styleOverrides: {
        root: {
          backgroundColor: colorsLight.neutral[0],
          border: `1px solid ${colorsLight.neutral[200]}`,
          borderRadius: borderRadius.lg,
          boxShadow: shadows.base,
          transition: `all ${transitions.base} ${easing.easeInOut}`,
          '&:hover': {
            boxShadow: shadows.md,
            borderColor: colorsLight.neutral[300],
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: colorsLight.neutral[0],
          borderRadius: borderRadius.lg,
        },
        elevation0: {
          boxShadow: 'none',
          border: `1px solid ${colorsLight.neutral[200]}`,
        },
        elevation1: {
          boxShadow: shadows.sm,
        },
        elevation2: {
          boxShadow: shadows.base,
        },
        elevation3: {
          boxShadow: shadows.md,
        },
      },
    },

    // ========================================================================
    // TextField / Input
    // ========================================================================
    MuiTextField: {
      defaultProps: {
        variant: 'outlined',
        size: 'small',
      },
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: borderRadius.md,
            backgroundColor: colorsLight.neutral[0],
            transition: `all ${transitions.base} ${easing.easeInOut}`,
            '&:hover fieldset': {
              borderColor: colorsLight.primary[300],
            },
            '&.Mui-focused fieldset': {
              borderColor: colorsLight.primary[500],
              borderWidth: '2px',
            },
            '&.Mui-error fieldset': {
              borderColor: colorsLight.danger[500],
            },
          },
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          '& fieldset': {
            borderColor: colorsLight.neutral[200],
          },
          '&:hover fieldset': {
            borderColor: colorsLight.primary[300],
          },
          '&.Mui-focused fieldset': {
            borderColor: colorsLight.primary[500],
          },
        },
        input: {
          fontSize: fontSize.sm,
          padding: '10px 12px',
        },
      },
    },

    // ========================================================================
    // Dialog
    // ========================================================================
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: borderRadius.xl,
          boxShadow: shadows['2xl'],
        },
      },
    },
    MuiDialogContent: {
      styleOverrides: {
        root: {
          padding: spacing[6],
        },
      },
    },

    // ========================================================================
    // Chip
    // ========================================================================
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: borderRadius.md,
          fontWeight: fontWeight.medium,
          transition: `all ${transitions.base} ${easing.easeInOut}`,
        },
        filledPrimary: {
          backgroundColor: colorsLight.primary[100],
          color: colorsLight.primary[700],
          '&:hover': {
            backgroundColor: colorsLight.primary[200],
          },
        },
        outlinedPrimary: {
          borderColor: colorsLight.primary[300],
          color: colorsLight.primary[600],
          '&:hover': {
            backgroundColor: colorsLight.primary[50],
          },
        },
      },
    },

    // ========================================================================
    // Table
    // ========================================================================
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderColor: colorsLight.neutral[200],
          fontSize: fontSize.sm,
        },
        head: {
          backgroundColor: colorsLight.neutral[100],
          fontWeight: fontWeight.semibold,
          color: colorsLight.neutral[700],
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: colorsLight.neutral[50],
          },
        },
      },
    },

    // ========================================================================
    // Dropdown / Menu
    // ========================================================================
    MuiMenuItem: {
      styleOverrides: {
        root: {
          fontSize: fontSize.sm,
          '&:hover': {
            backgroundColor: colorsLight.primary[50],
          },
          '&.Mui-selected': {
            backgroundColor: colorsLight.primary[100],
            '&:hover': {
              backgroundColor: colorsLight.primary[150],
            },
          },
        },
      },
    },

    // ========================================================================
    // Badge
    // ========================================================================
    MuiBadge: {
      styleOverrides: {
        badge: {
          backgroundColor: colorsLight.danger[500],
          color: '#ffffff',
          fontWeight: fontWeight.bold,
        },
      },
    },
  },
};

export const lightTheme = createTheme(lightThemeConfig);

// ============================================================================
// DARK MODE THEME
// ============================================================================
const darkThemeConfig: ThemeOptions = {
  palette: {
    mode: 'dark',
    primary: {
      main: colorsDark.primary[400],
      light: colorsDark.primary[300],
      dark: colorsDark.primary[500],
      contrastText: colorsDark.neutral[900],
    },
    secondary: {
      main: colorsDark.secondary[400],
      light: colorsDark.secondary[300],
      dark: colorsDark.secondary[500],
      contrastText: colorsDark.neutral[900],
    },
    success: {
      main: colorsDark.success[400],
      light: colorsDark.success[300],
      dark: colorsDark.success[500],
      contrastText: colorsDark.neutral[900],
    },
    warning: {
      main: colorsDark.warning[400],
      light: colorsDark.warning[300],
      dark: colorsDark.warning[500],
      contrastText: colorsDark.neutral[900],
    },
    error: {
      main: colorsDark.danger[400],
      light: colorsDark.danger[300],
      dark: colorsDark.danger[500],
      contrastText: colorsDark.neutral[900],
    },
    info: {
      main: colorsDark.info[400],
      light: colorsDark.info[300],
      dark: colorsDark.info[500],
      contrastText: colorsDark.neutral[900],
    },
    background: {
      default: colorsDark.neutral[50],
      paper: colorsDark.neutral[100],
    },
    text: {
      primary: colorsDark.neutral[900],
      secondary: colorsDark.neutral[600],
      disabled: colorsDark.neutral[400],
    },
    divider: colorsDark.neutral[200],
    action: {
      active: colorsDark.primary[400],
      hover: colorsDark.primary[900],
      selected: colorsDark.primary[800],
      disabled: colorsDark.neutral[400],
      disabledBackground: colorsDark.neutral[200],
    },
  },

  typography: {
    fontFamily: [
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
    
    h1: {
      fontSize: fontSize['5xl'],
      fontWeight: fontWeight.bold,
      lineHeight: lineHeight.tight,
      letterSpacing: letterSpacing.tight,
      color: colorsDark.neutral[900],
    },
    h2: {
      fontSize: fontSize['4xl'],
      fontWeight: fontWeight.bold,
      lineHeight: lineHeight.tight,
      letterSpacing: letterSpacing.tight,
      color: colorsDark.neutral[900],
    },
    h3: {
      fontSize: fontSize['3xl'],
      fontWeight: fontWeight.semibold,
      lineHeight: lineHeight.snug,
      color: colorsDark.neutral[900],
    },
    h4: {
      fontSize: fontSize['2xl'],
      fontWeight: fontWeight.semibold,
      lineHeight: lineHeight.snug,
      color: colorsDark.neutral[900],
    },
    h5: {
      fontSize: fontSize.xl,
      fontWeight: fontWeight.semibold,
      lineHeight: lineHeight.normal,
      color: colorsDark.neutral[900],
    },
    h6: {
      fontSize: fontSize.lg,
      fontWeight: fontWeight.semibold,
      lineHeight: lineHeight.normal,
      color: colorsDark.neutral[900],
    },
    body1: {
      fontSize: fontSize.base,
      fontWeight: fontWeight.normal,
      lineHeight: lineHeight.normal,
      color: colorsDark.neutral[900],
    },
    body2: {
      fontSize: fontSize.sm,
      fontWeight: fontWeight.normal,
      lineHeight: lineHeight.normal,
      color: colorsDark.neutral[800],
    },
  },

  shape: {
    borderRadius: parseInt(borderRadius.default.replace('rem', '')) * 16,
  },

  spacing: (factor: number) => `${0.25 * factor}rem`,

  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: borderRadius.md,
          transition: `all ${transitions.base} ${easing.easeInOut}`,
        },
        containedPrimary: {
          backgroundColor: colorsDark.primary[400],
          color: colorsDark.neutral[900],
          '&:hover': {
            backgroundColor: colorsDark.primary[300],
            boxShadow: shadowsDark.lg,
          },
        },
        outlinedPrimary: {
          borderColor: colorsDark.primary[600],
          color: colorsDark.primary[400],
          '&:hover': {
            backgroundColor: colorsDark.neutral[200],
            borderColor: colorsDark.primary[400],
          },
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: colorsDark.neutral[100],
          borderColor: colorsDark.neutral[200],
          boxShadow: shadowsDark.base,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: colorsDark.neutral[100],
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            backgroundColor: colorsDark.neutral[150],
            '&.Mui-focused fieldset': {
              borderColor: colorsDark.primary[400],
            },
          },
        },
      },
    },
  },
};

export const darkTheme = createTheme(darkThemeConfig);

// ============================================================================
// HELPER: GET THEME BY MODE
// ============================================================================
export const getTheme = (mode: 'light' | 'dark') => {
  return mode === 'light' ? lightTheme : darkTheme;
};
