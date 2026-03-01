/**
 * Spacing Scale (4px base)
 * Single source of truth for all spacing values
 * Ensures consistent vertical and horizontal rhythm
 */

export const spacing = {
  0: 0,
  1: 4,      // 4px
  2: 8,      // 8px
  3: 12,     // 12px
  4: 16,     // 16px
  5: 20,     // 20px
  6: 24,     // 24px
  7: 28,     // 28px
  8: 32,     // 32px
  9: 36,     // 36px
  10: 40,    // 40px
  12: 48,    // 48px
  14: 56,    // 56px
  16: 64,    // 64px
  20: 80,    // 80px
  24: 96,    // 96px
} as const;

export type SpacingToken = keyof typeof spacing;
