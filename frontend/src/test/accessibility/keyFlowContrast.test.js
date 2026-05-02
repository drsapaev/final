import { describe, expect, it } from 'vitest';
import { A11Y_COLORS } from '../../constants/a11yTokens';

function hexToRgb(hex) {
  const value = hex.replace('#', '');
  return {
    r: parseInt(value.slice(0, 2), 16),
    g: parseInt(value.slice(2, 4), 16),
    b: parseInt(value.slice(4, 6), 16),
  };
}

function relativeLuminance(hex) {
  const { r, g, b } = hexToRgb(hex);
  const normalize = (channel) => {
    const value = channel / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };
  const rr = normalize(r);
  const gg = normalize(g);
  const bb = normalize(b);
  return 0.2126 * rr + 0.7152 * gg + 0.0722 * bb;
}

function contrastRatio(foreground, background) {
  const fg = relativeLuminance(foreground);
  const bg = relativeLuminance(background);
  const lighter = Math.max(fg, bg);
  const darker = Math.min(fg, bg);
  return (lighter + 0.05) / (darker + 0.05);
}

describe('Key Flow Color Contrast', () => {
  it('primary action text meets WCAG AA (4.5:1)', () => {
    expect(contrastRatio(A11Y_COLORS.primary, A11Y_COLORS.onPrimary)).toBeGreaterThanOrEqual(4.5);
  });

  it('success action text meets WCAG AA (4.5:1)', () => {
    expect(contrastRatio(A11Y_COLORS.success, A11Y_COLORS.onPrimary)).toBeGreaterThanOrEqual(4.5);
  });

  it('danger text meets WCAG AA (4.5:1)', () => {
    expect(contrastRatio(A11Y_COLORS.danger, A11Y_COLORS.onPrimary)).toBeGreaterThanOrEqual(4.5);
  });

  it('body text hierarchy meets WCAG AA on white surfaces', () => {
    expect(contrastRatio(A11Y_COLORS.textPrimary, A11Y_COLORS.onPrimary)).toBeGreaterThanOrEqual(7);
    expect(contrastRatio(A11Y_COLORS.textSecondary, A11Y_COLORS.onPrimary)).toBeGreaterThanOrEqual(4.5);
  });
});

