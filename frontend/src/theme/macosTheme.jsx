import PropTypes from 'prop-types';
import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { ensureMinContrast, getReadableTextColor, mixColors, toRgbaString } from './colorUtils.js';
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
  ensureContrast: (fg) => fg
});

function getSystemMode() {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function getStoredMode() {
  if (typeof window === 'undefined') return 'light';

  const domMode = document.documentElement.getAttribute('data-theme');
  if (domMode === 'light' || domMode === 'dark') {
    return domMode;
  }

  const storedTheme = localStorage.getItem('ui_theme') || localStorage.getItem('theme');
  if (storedTheme === 'light' || storedTheme === 'dark') {
    return storedTheme;
  }

  return getSystemMode();
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
  const [mode, setMode] = useState(getStoredMode);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e) => {
      const selectedScheme = localStorage.getItem('colorScheme');
      if (!selectedScheme || selectedScheme === 'auto') {
        setMode(e.matches ? 'dark' : 'light');
      }
    };
    const syncModeFromTheme = () => setMode(getStoredMode());
    if (mq.addEventListener) mq.addEventListener('change', handler);else
    mq.addListener(handler);
    window.addEventListener('colorSchemeChanged', syncModeFromTheme);
    window.addEventListener('storage', syncModeFromTheme);
    return () => {
      if (mq.removeEventListener) mq.removeEventListener('change', handler);else
      mq.removeListener(handler);
      window.removeEventListener('colorSchemeChanged', syncModeFromTheme);
      window.removeEventListener('storage', syncModeFromTheme);
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
    const hoverAccent = mixColors(adaptiveAccent, mode === 'dark' ? '#ffffff' : '#06101d', mode === 'dark' ? 0.12 : 0.18);
    const activeAccent = mixColors(adaptiveAccent, mode === 'dark' ? '#ffffff' : '#02060c', mode === 'dark' ? 0.2 : 0.28);
    const accentFg = getReadableTextColor(adaptiveAccent, {
      light: '#ffffff',
      dark: '#081018',
    });

    root.style.setProperty('--accent', adaptiveAccent);
    root.style.setProperty('--mac-accent', adaptiveAccent);
    root.style.setProperty('--mac-accent-blue', adaptiveAccent);
    root.style.setProperty('--mac-accent-blue-500', adaptiveAccent);
    root.style.setProperty('--mac-accent-blue-600', hoverAccent);
    root.style.setProperty('--mac-accent-blue-700', activeAccent);
    root.style.setProperty('--mac-accent-blue-hover', hoverAccent);
    root.style.setProperty('--mac-accent-blue-active', activeAccent);
    root.style.setProperty('--mac-accent-bg', toRgbaString(adaptiveAccent, mode === 'dark' ? 0.22 : 0.12));
    root.style.setProperty('--mac-accent-blue-bg', toRgbaString(adaptiveAccent, mode === 'dark' ? 0.24 : 0.14));
    root.style.setProperty('--mac-accent-blue-light', mixColors(adaptiveAccent, '#ffffff', mode === 'dark' ? 0.18 : 0.78));
    root.style.setProperty('--mac-accent-border', toRgbaString(adaptiveAccent, mode === 'dark' ? 0.38 : 0.24));
    root.style.setProperty('--mac-text-on-accent', accentFg);
    root.style.setProperty('--accent-foreground', accentFg);

    Object.entries(ACCENTS).forEach(([k, v]) => {
      const adaptive = ACCENT_ADAPTIVE[k] || v;
      root.style.setProperty(`--accent-${k}`, adaptive);
      if (k !== 'blue') {
        root.style.setProperty(`--mac-accent-${k}`, adaptive);
        root.style.setProperty(`--mac-accent-${k}-bg`, toRgbaString(adaptive, mode === 'dark' ? 0.24 : 0.14));
        root.style.setProperty(`--mac-accent-${k}-light`, mixColors(adaptive, '#ffffff', mode === 'dark' ? 0.18 : 0.78));
      }
    });

    // Avoid clobbering app color schemes (light/dark/vibrant/glass/gradient).
    root.setAttribute('data-macos-mode', mode);
    try {
      localStorage.setItem(STORAGE_KEY, accent);
    } catch (error) {
      void error;
    }
  }, [accent, mode]);

  const setAccent = (name) => {
    if (ACCENTS[name]) setAccentState(name);
  };

  const ensureContrast = useMemo(() => (fgHex, bgHex) => ensureMinContrast(fgHex, bgHex, 4.5), []);

  const value = useMemo(() => ({ accent, setAccent, mode, setMode, ensureContrast }), [accent, mode, ensureContrast]);

  return (
    <MacOSThemeContext.Provider value={value}>
      {children}
    </MacOSThemeContext.Provider>);

}

export function useMacOSTheme() {
  return useContext(MacOSThemeContext);
}

export const ACCENT_OPTIONS = Object.keys(ACCENTS);

MacOSThemeProvider.propTypes = {
  children: PropTypes.node,
};

export default MacOSThemeProvider;
