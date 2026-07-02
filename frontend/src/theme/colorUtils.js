function clampChannel(value) {
  return Math.max(0, Math.min(255, Math.round(value)));
}

export function parseCssColor(value) {
  if (!value || typeof value !== 'string') {
    return null;
  }

  const normalized = value.trim();

  if (normalized.startsWith('#')) {
    const hex = normalized.slice(1);

    if (hex.length === 3) {
      const [r, g, b] = hex.split('').map((channel) => parseInt(channel + channel, 16));
      return { r, g, b, a: 1 };
    }

    if (hex.length === 6) {
      return {
        r: parseInt(hex.slice(0, 2), 16),
        g: parseInt(hex.slice(2, 4), 16),
        b: parseInt(hex.slice(4, 6), 16),
        a: 1,
      };
    }
  }

  const rgbMatch = normalized.match(/^rgba?\(([^)]+)\)$/i);
  if (!rgbMatch) {
    return null;
  }

  const [r = '0', g = '0', b = '0', a = '1'] = rgbMatch[1]
    .split(',')
    .map((part) => part.trim());

  return {
    r: Number.parseFloat(r),
    g: Number.parseFloat(g),
    b: Number.parseFloat(b),
    a: Number.parseFloat(a),
  };
}

export function toHexString(color) {
  const parsed = typeof color === 'string' ? parseCssColor(color) : color;
  if (!parsed) {
    return '#000000';
  }

  return `#${[parsed.r, parsed.g, parsed.b]
    .map((channel) => clampChannel(channel).toString(16).padStart(2, '0'))
    .join('')}`;
}

export function toRgbaString(color, alpha = 1) {
  const parsed = typeof color === 'string' ? parseCssColor(color) : color;
  if (!parsed) {
    return `rgba(0, 0, 0, ${alpha})`;
  }

  return `rgba(${clampChannel(parsed.r)}, ${clampChannel(parsed.g)}, ${clampChannel(parsed.b)}, ${alpha})`;
}

export function mixColors(source, target, ratio = 0.5) {
  const from = typeof source === 'string' ? parseCssColor(source) : source;
  const to = typeof target === 'string' ? parseCssColor(target) : target;

  if (!from || !to) {
    return typeof source === 'string' ? source : '#000000';
  }

  return toHexString({
    r: from.r + (to.r - from.r) * ratio,
    g: from.g + (to.g - from.g) * ratio,
    b: from.b + (to.b - from.b) * ratio,
    a: 1,
  });
}

export function getLuminance(color) {
  const parsed = typeof color === 'string' ? parseCssColor(color) : color;
  if (!parsed) {
    return 0;
  }

  const channels = [parsed.r, parsed.g, parsed.b].map((channel) => {
    const normalized = clampChannel(channel) / 255;
    return normalized <= 0.03928 ?
      normalized / 12.92 :
      ((normalized + 0.055) / 1.055) ** 2.4;
  });

  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

export function contrastRatio(foreground, background) {
  const lighter = getLuminance(foreground) + 0.05;
  const darker = getLuminance(background) + 0.05;

  return lighter > darker ? lighter / darker : darker / lighter;
}

export function getReadableTextColor(background, options = {}) {
  const light = options.light || '#ffffff';
  const dark = options.dark || '#111315';

  return contrastRatio(light, background) >= contrastRatio(dark, background) ? light : dark;
}

export function ensureMinContrast(foreground, background, min = 4.5) {
  const initial = toHexString(foreground);
  if (contrastRatio(initial, background) >= min) {
    return initial;
  }

  const backgroundIsDark = getLuminance(background) < 0.5;
  const target = backgroundIsDark ? '#ffffff' : '#000000';

  for (let step = 0.1; step <= 1; step += 0.1) {
    const candidate = mixColors(initial, target, step);
    if (contrastRatio(candidate, background) >= min) {
      return candidate;
    }
  }

  return initial;
}
