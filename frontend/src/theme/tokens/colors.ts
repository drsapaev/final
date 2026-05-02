/**
 * Color Palette - Semantic & Medical
 * Light mode as base; dark mode inverts automatically via MUI
 */

export interface ColorScale {
  50: string;
  100: string;
  200: string;
  300: string;
  400: string;
  500: string;
  600: string;
  700: string;
  800: string;
  900: string;
}

// ============================================================================
// BRAND COLORS
// ============================================================================

export const primary: ColorScale = {
  50: '#f0f9ff',
  100: '#e0f2fe',
  200: '#bae6fd',
  300: '#7dd3fc',
  400: '#38bdf8',
  500: '#0ea5e9',
  600: '#0284c7',
  700: '#0369a1',
  800: '#075985',
  900: '#0c3d66',
};

export const secondary: ColorScale = {
  50: '#f5f3ff',
  100: '#ede9fe',
  200: '#ddd6fe',
  300: '#c4b5fd',
  400: '#a78bfa',
  500: '#8b5cf6',
  600: '#7c3aed',
  700: '#6d28d9',
  800: '#5b21b6',
  900: '#4c1d95',
};

// ============================================================================
// SEMANTIC COLORS
// ============================================================================

export const success: ColorScale = {
  50: '#f0fdf4',
  100: '#dcfce7',
  200: '#bbf7d0',
  300: '#86efac',
  400: '#4ade80',
  500: '#22c55e',
  600: '#16a34a',
  700: '#15803d',
  800: '#166534',
  900: '#145231',
};

export const warning: ColorScale = {
  50: '#fffbeb',
  100: '#fef3c7',
  200: '#fde68a',
  300: '#fcd34d',
  400: '#fbbf24',
  500: '#f59e0b',
  600: '#d97706',
  700: '#b45309',
  800: '#92400e',
  900: '#78350f',
};

export const danger: ColorScale = {
  50: '#fef2f2',
  100: '#fee2e2',
  200: '#fecaca',
  300: '#fca5a5',
  400: '#f87171',
  500: '#ef4444',
  600: '#dc2626',
  700: '#b91c1c',
  800: '#991b1b',
  900: '#7f1d1d',
};

export const info: ColorScale = {
  50: '#eff6ff',
  100: '#dbeafe',
  200: '#bfdbfe',
  300: '#93c5fd',
  400: '#60a5fa',
  500: '#3b82f6',
  600: '#2563eb',
  700: '#1d4ed8',
  800: '#1e40af',
  900: '#1e3a8a',
};

// ============================================================================
// NEUTRALS (Grayscale)
// ============================================================================

export const neutral: ColorScale = {
  50: '#f9fafb',
  100: '#f3f4f6',
  200: '#e5e7eb',
  300: '#d1d5db',
  400: '#9ca3af',
  500: '#6b7280',
  600: '#4b5563',
  700: '#374151',
  800: '#1f2937',
  900: '#111827',
};

// ============================================================================
// MEDICAL SPECIALTY COLORS
// Semantic colors for different medical departments
// ============================================================================

export const medical = {
  cardiology: {
    light: '#ffe0e6',
    main: '#e91e63',
    dark: '#880e4f',
  },
  dermatology: {
    light: '#f3e5f5',
    main: '#9c27b0',
    dark: '#4a148c',
  },
  neurology: {
    light: '#e3f2fd',
    main: '#2196f3',
    dark: '#0d47a1',
  },
  orthopedics: {
    light: '#fff3e0',
    main: '#ff9800',
    dark: '#e65100',
  },
  ophthalmology: {
    light: '#fce4ec',
    main: '#c2185b',
    dark: '#880e4f',
  },
  dentistry: {
    light: '#f1f8e9',
    main: '#8bc34a',
    dark: '#33691e',
  },
} as const;

// ============================================================================
// LIGHT MODE COLOR PALETTE (exports)
// ============================================================================

export const colorsLight = {
  primary,
  secondary,
  success,
  warning,
  danger,
  info,
  neutral,
  medical,
};

// ============================================================================
// DARK MODE COLOR PALETTE (inverted)
// ============================================================================

const invertColorScale = (scale: ColorScale): ColorScale => ({
  50: scale[900],
  100: scale[800],
  200: scale[700],
  300: scale[600],
  400: scale[500],
  500: scale[400],
  600: scale[300],
  700: scale[200],
  800: scale[100],
  900: scale[50],
});

export const colorsDark = {
  primary: invertColorScale(primary),
  secondary: invertColorScale(secondary),
  success: invertColorScale(success),
  warning: invertColorScale(warning),
  danger: invertColorScale(danger),
  info: invertColorScale(info),
  neutral: invertColorScale(neutral),
  medical: Object.fromEntries(
    Object.entries(medical).map(([dept, colors]) => [
      dept,
      {
        light: colors.dark,
        main: colors.main,
        dark: colors.light,
      },
    ])
  ) as typeof medical,
};
