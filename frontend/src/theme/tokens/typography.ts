/**
 * Typography Scale
 * Ensures consistent hierarchy and readability across all text elements
 */

export const fontSize = {
  xs: 12,      // 0.75rem
  sm: 14,      // 0.875rem
  base: 16,    // 1rem
  lg: 18,      // 1.125rem
  xl: 20,      // 1.25rem
  '2xl': 24,   // 1.5rem
  '3xl': 30,   // 1.875rem
  '4xl': 36,   // 2.25rem
  '5xl': 48,   // 3rem
} as const;

export const fontWeight = {
  thin: 100,
  extralight: 200,
  light: 300,
  normal: 400,
  medium: 500,
  semibold: 600,
  bold: 700,
  extrabold: 800,
  black: 900,
} as const;

export const lineHeight = {
  none: 1,
  tight: 1.25,
  snug: 1.375,
  normal: 1.5,
  relaxed: 1.625,
  loose: 2,
} as const;

export const letterSpacing = {
  tighter: '-0.05em',
  tight: '-0.025em',
  normal: '0em',
  wide: '0.025em',
  wider: '0.05em',
  widest: '0.1em',
} as const;

export type FontSizeToken = keyof typeof fontSize;
export type FontWeightToken = keyof typeof fontWeight;
export type LineHeightToken = keyof typeof lineHeight;
export type LetterSpacingToken = keyof typeof letterSpacing;
