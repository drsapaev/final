/**
 * Shape/Border Radius Scale
 * Consistent corner rounding for modern, cohesive appearance
 */

export const borderRadius = {
  none: 0,
  sm: 4,       // 0.25rem
  default: 6,  // 0.375rem
  md: 8,       // 0.5rem
  lg: 12,      // 0.75rem
  xl: 16,      // 1rem
  '2xl': 24,   // 1.5rem
  '3xl': 32,   // 2rem
  full: 9999,
} as const;

export type BorderRadiusToken = keyof typeof borderRadius;
