/**
 * MUI Theme Factory
 * Single createTheme implementation - single source of truth
 * All design decisions flow through this file
 */

import { createTheme, ThemeOptions } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';

// Import augmentation to extend MUI types
import './augmentation';

// Import factories
import { createLightPalette, createDarkPalette } from './createPalette';
import { createTypography } from './createTypography';
import { createComponentOverrides } from './componentOverrides';

// Import tokens
import {
  spacing,
  borderRadius,
  transitions,
  easing,
  shadows,
  shadowsDark,
} from './tokens';

// ============================================================================
// LIGHT MODE THEME
// ============================================================================

const lightThemeOptions: ThemeOptions = {
  palette: createLightPalette(),

  typography: createTypography(),

  shape: {
    borderRadius: borderRadius.md,
  },

  spacing: spacing,

  transitions: {
    duration: transitions,
    easing,
  },

  shadows,

  // Component overrides created in createTheme callback
};

// ============================================================================
// DARK MODE THEME
// ============================================================================

const darkThemeOptions: ThemeOptions = {
  palette: createDarkPalette(),

  typography: createTypography(),

  shape: {
    borderRadius: borderRadius.md,
  },

  spacing: spacing,

  transitions: {
    duration: transitions,
    easing,
  },

  shadows: shadowsDark,
};

// ============================================================================
// THEME INSTANTIATION
// ============================================================================

/**
 * Create light theme with component overrides
 */
const lightThemeBase = createTheme(lightThemeOptions);

export const lightTheme = createTheme(lightThemeOptions, {
  components: createComponentOverrides(lightThemeBase),
});

/**
 * Create dark theme with component overrides
 */
const darkThemeBase = createTheme(darkThemeOptions);

export const darkTheme = createTheme(darkThemeOptions, {
  components: createComponentOverrides(darkThemeBase),
});

/**
 * Get theme by mode
 */
export const getTheme = (mode: 'light' | 'dark' = 'light') =>
  mode === 'dark' ? darkTheme : lightTheme;

// ============================================================================
// RE-EXPORTS FOR CONVENIENCE
// ============================================================================

export * from './tokens';
export { CssBaseline };
