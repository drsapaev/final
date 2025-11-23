import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

const ACCENTS = {
  blue: '#007aff',
  purple: '#5856d6',
  pink: '#ff2d55',
  red: '#ff3b30',
  orange: '#ff9500',
  yellow: '#ffcc00',
  green: '#34c759',
  graphite: '#8e8e93'
};

const STORAGE_KEY = 'ui.accent';

const MacOSThemeContext = createContext({
  accent: 'blue',
  setAccent: () => {},
  mode: 'light',
  setMode: () => {},
  ensureContrast: (fg, bg) => fg
});

function getSystemMode() {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function getLuminance(hex) {
  const c = hex.replace('#', '');
  const r = parseInt(c.substring(0, 2), 16) / 255;
  const g = parseInt(c.substring(2, 4), 16) / 255;
  const b = parseInt(c.substring(4, 6), 16) / 255;
  const srgb = [r, g, b].map(v => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)));
  return 0.2126 * srgb[0] + 0.7152 * srgb[1] + 0.0722 * srgb[2];
}

function contrastRatio(fgHex, bgHex) {
  const L1 = getLuminance(fgHex) + 0.05;
  const L2 = getLuminance(bgHex) + 0.05;
  return L1 > L2 ? L1 / L2 : L2 / L1;
}

function adjustForContrast(colorHex, bgHex, min = 4.5) {
  // Try mixing towards black or white to reach min contrast
  let c = colorHex.replace('#', '');
  let r = parseInt(c.substring(0, 2), 16);
  let g = parseInt(c.substring(2, 4), 16);
  let b = parseInt(c.substring(4, 6), 16);
  const bg = bgHex.replace('#', '');
  const bgIsDark = getLuminance('#' + bg) < 0.5;
  for (let i = 0; i <= 20; i++) {
    const t = i / 20;
    const mixR = Math.round(bgIsDark ? r + (255 - r) * t : r * (1 - t));
    const mixG = Math.round(bgIsDark ? g + (255 - g) * t : g * (1 - t));
    const mixB = Math.round(bgIsDark ? b + (255 - b) * t : b * (1 - t));
    const candidate = '#' + [mixR, mixG, mixB].map(x => x.toString(16).padStart(2, '0')).join('');
    if (contrastRatio(candidate, '#' + bg) >= min) return candidate;
  }
  return '#' + c;
}

export function MacOSThemeProvider({ children }) {
  const [accent, setAccentState] = useState(() => {
    try {
      const s = localStorage.getItem(STORAGE_KEY);
      return s && ACCENTS[s] ? s : 'blue';
    } catch {
      return 'blue';
    }
  });
  const [mode, setMode] = useState(getSystemMode());

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e) => setMode(e.matches ? 'dark' : 'light');
    if (mq.addEventListener) mq.addEventListener('change', handler);
    else mq.addListener(handler);
    return () => {
      if (mq.removeEventListener) mq.removeEventListener('change', handler);
      else mq.removeListener(handler);
    };
  }, []);

  useEffect(() => {
    // Apply CSS vars on root
    const root = document.documentElement;
    
    // Define adaptive accent colors for light/dark mode
    const ACCENT_ADAPTIVE = {
      blue: mode === 'dark' ? '#0a84ff' : '#007aff',
      purple: mode === 'dark' ? '#5e5ce6' : '#5856d6',
      pink: mode === 'dark' ? '#ff375f' : '#ff2d55',
      red: mode === 'dark' ? '#ff453a' : '#ff3b30',
      orange: mode === 'dark' ? '#ff9f0a' : '#ff9500',
      yellow: mode === 'dark' ? '#ffd60a' : '#ffcc00',
      green: mode === 'dark' ? '#30d158' : '#34c759',
      graphite: mode === 'dark' ? '#636366' : '#8e8e93'
    };
    
    const adaptiveAccent = ACCENT_ADAPTIVE[accent] || ACCENTS[accent];
    root.style.setProperty('--accent', adaptiveAccent);
    Object.entries(ACCENTS).forEach(([k, v]) => {
      const adaptive = ACCENT_ADAPTIVE[k] || v;
      root.style.setProperty(`--accent-${k}`, adaptive);
    });
    
    // Ensure readable foreground on accent backgrounds (AA >= 4.5)
    const white = '#ffffff';
    const black = '#000000';
    const accentHex = adaptiveAccent;
    const whiteContrast = contrastRatio(white, accentHex);
    const blackContrast = contrastRatio(black, accentHex);
    const accentFg = whiteContrast >= blackContrast ? white : black;
    root.style.setProperty('--accent-foreground', accentFg);
    root.setAttribute('data-color-scheme', mode);
    try { localStorage.setItem(STORAGE_KEY, accent); } catch {}
  }, [accent, mode]);

  const setAccent = (name) => {
    if (ACCENTS[name]) setAccentState(name);
  };

  const ensureContrast = useMemo(() => (fgHex, bgHex) => adjustForContrast(fgHex, bgHex, 4.5), []);

  const value = useMemo(() => ({ accent, setAccent, mode, setMode, ensureContrast }), [accent, mode, ensureContrast]);

  return React.createElement(MacOSThemeContext.Provider, { value }, children);
}

export function useMacOSTheme() {
  return useContext(MacOSThemeContext);
}

export const ACCENT_OPTIONS = Object.keys(ACCENTS);

export default MacOSThemeProvider;


