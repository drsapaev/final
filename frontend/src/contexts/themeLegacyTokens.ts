/**
 * PR-UI-17-4: private legacy token maps for ThemeContext.
 *
 * These values are inlined byte-identical from the deleted
 * `src/theme/tokens-legacy.ts` (its only live importer was ThemeContext).
 * They are token VALUE DATA (a .ts data module, not component code) —
 * exactly the layering the old file had, now scoped privately to the
 * context that consumes it.
 *
 * The ThemeContext DOM effect reads CSS variables FIRST and uses these
 * maps only as fallbacks. Full getColor migration to var(--mac-*) would
 * change rendered colors (legacy palette ≠ macOS palette: #0ea5e9 vs
 * #007aff) and requires a dedicated visual-regression-verified effort —
 * recorded in Plan-SSOT (§PR-UI-17 item 10 note).
 */

export const legacyColors = {
  primary: {
    50: '#f0f9ff',
    100: '#e0f2fe',
    200: '#bae6fd',
    300: '#7dd3fc',
    400: '#38bdf8',
    500: '#0ea5e9',
    600: '#0284c7',
    700: '#0369a1',
    800: '#075985',
    900: '#0c4a6e'
  },
  secondary: {
    50: '#f8fafc',
    100: '#f1f5f9',
    200: '#e2e8f0',
    300: '#cbd5e1',
    400: '#94a3b8',
    500: '#64748b',
    600: '#475569',
    700: '#334155',
    800: '#1e293b',
    900: '#0f172a'
  },
  status: {
    success: '#10b981',
    warning: '#f59e0b',
    danger: '#ef4444',
    info: '#3b82f6',
    pending: '#f59e0b',
    completed: '#10b981',
    cancelled: '#6b7280'
  },
  semantic: {
    background: {
      primary: '#ffffff',
      secondary: '#f8fafc',
      tertiary: '#f1f5f9',
      elevated: '#ffffff',
      overlay: 'rgba(0, 0, 0, 0.5)',
      disabled: '#f3f4f6'
    },
    text: {
      primary: '#0f172a',
      secondary: '#374151',
      tertiary: '#6b7280',
      inverse: '#ffffff',
      disabled: '#9ca3af'
    },
    border: {
      light: '#e5e7eb',
      medium: '#d1d5db',
      dark: '#9ca3af',
      focus: '#0ea5e9'
    },
    surface: {
      card: '#ffffff',
      input: '#ffffff',
      button: '#ffffff',
      hover: '#f8fafc',
      active: '#f1f5f9',
      selected: '#e0f2fe'
    }
  }
};

export const legacySpacing: Record<string, string> = {
  0: '0px',
  1: '4px',
  2: '8px',
  3: '12px',
  4: '16px',
  5: '20px',
  6: '24px',
  8: '32px',
  10: '40px',
  12: '48px',
  16: '64px',
  20: '80px',
  24: '96px',
  32: '128px'
};

export const legacyFontSize: Record<string, string> = {
  xs: '12px',
  sm: '14px',
  base: '16px',
  lg: '18px',
  xl: '20px',
  '2xl': '24px',
  '3xl': '30px',
  '4xl': '36px',
  '5xl': '48px'
};

export const legacyShadows: Record<string, string> = {
  sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
  base: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
  md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
  lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
  xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
  '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
  inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)'
};
