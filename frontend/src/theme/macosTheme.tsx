import PropTypes from 'prop-types';
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ensureMinContrast, getReadableTextColor, mixColors, toRgbaString } from './colorUtils.js';

type AccentName = 'blue' | 'purple' | 'pink' | 'red' | 'orange' | 'yellow' | 'green' | 'graphite';
type ThemeMode = 'light' | 'dark';

interface MacOSThemeContextValue {
  accent: AccentName;
  setAccent: (name: AccentName) => void;
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  ensureContrast: (fgHex: string, bgHex: string) => string;
}

interface MacOSThemeProviderProps {
  children?: ReactNode;
}

const ACCENTS: Record<AccentName, string> = {
  blue: 'var(--mac-accent-blue)',
  purple: 'var(--mac-accent-purple)',
  pink: '#ff2d55',
  red: 'var(--mac-error)',
  orange: 'var(--mac-warning)',
  yellow: '#ffcc00',
  green: 'var(--mac-success)',
  graphite: 'var(--mac-text-tertiary)'
};

const STORAGE_KEY = 'ui.accent';

const MacOSThemeContext = createContext<MacOSThemeContextValue>({
  accent: 'blue',
  setAccent: () => {},
  mode: 'light',
  setMode: () => {},
  ensureContrast: (fg) => fg
});

function getSystemMode(): ThemeMode {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function getStoredMode(): ThemeMode {
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

export function MacOSThemeProvider({ children }: MacOSThemeProviderProps) {
  const [accent, setAccentState] = useState<AccentName>(() => {
    try {
      const s = localStorage.getItem(STORAGE_KEY);
      if (s && (s in ACCENTS)) {
        return s as AccentName;
      }
      return 'blue';
    } catch {
      return 'blue';
    }
  });
  const [mode, setMode] = useState<ThemeMode>(getStoredMode);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e: MediaQueryListEvent) => {
      const selectedScheme = localStorage.getItem('colorScheme');
      if (!selectedScheme || selectedScheme === 'auto') {
        setMode(e.matches ? 'dark' : 'light');
      }
    };
    const syncModeFromTheme = () => setMode(getStoredMode());
    if (mq.addEventListener) mq.addEventListener('change', handler);
    else (mq as unknown as { addListener: (cb: (e: MediaQueryListEvent) => void) => void }).addListener(handler);
    window.addEventListener('colorSchemeChanged', syncModeFromTheme);
    window.addEventListener('storage', syncModeFromTheme);
    return () => {
      if (mq.removeEventListener) mq.removeEventListener('change', handler);
      else (mq as unknown as { removeListener: (cb: (e: MediaQueryListEvent) => void) => void }).removeListener(handler);
      window.removeEventListener('colorSchemeChanged', syncModeFromTheme);
      window.removeEventListener('storage', syncModeFromTheme);
    };
  }, []);

  useEffect(() => {
    // Apply CSS vars on root
    const root = document.documentElement;

    // Define adaptive accent colors for light/dark mode
    const ACCENT_ADAPTIVE: Record<AccentName, string> = {
      blue: mode === 'dark' ? '#0a84ff' : 'var(--mac-accent-blue)',
      purple: mode === 'dark' ? '#5e5ce6' : 'var(--mac-accent-purple)',
      pink: mode === 'dark' ? '#ff375f' : '#ff2d55',
      red: mode === 'dark' ? '#ff453a' : 'var(--mac-error)',
      orange: mode === 'dark' ? '#ff9f0a' : 'var(--mac-warning)',
      yellow: mode === 'dark' ? '#ffd60a' : '#ffcc00',
      green: mode === 'dark' ? '#30d158' : 'var(--mac-success)',
      graphite: mode === 'dark' ? '#636366' : 'var(--mac-text-tertiary)'
    };

    const adaptiveAccent = ACCENT_ADAPTIVE[accent] || ACCENTS[accent];
    const hoverAccent = mixColors(adaptiveAccent, mode === 'dark' ? 'var(--mac-bg-primary)' : '#06101d', mode === 'dark' ? 0.12 : 0.18);
    const activeAccent = mixColors(adaptiveAccent, mode === 'dark' ? 'var(--mac-bg-primary)' : '#02060c', mode === 'dark' ? 0.2 : 0.28);
    const accentFg = getReadableTextColor(adaptiveAccent, {
      light: 'var(--mac-bg-primary)',
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
    root.style.setProperty('--mac-accent-blue-light', mixColors(adaptiveAccent, 'var(--mac-bg-primary)', mode === 'dark' ? 0.18 : 0.78));
    root.style.setProperty('--mac-accent-border', toRgbaString(adaptiveAccent, mode === 'dark' ? 0.38 : 0.24));
    root.style.setProperty('--mac-text-on-accent', accentFg);
    root.style.setProperty('--accent-foreground', accentFg);

    (Object.entries(ACCENTS) as Array<[AccentName, string]>).forEach(([k, v]) => {
      const adaptive = ACCENT_ADAPTIVE[k] || v;
      root.style.setProperty(`--accent-${k}`, adaptive);
      if (k !== 'blue') {
        root.style.setProperty(`--mac-accent-${k}`, adaptive);
        root.style.setProperty(`--mac-accent-${k}-bg`, toRgbaString(adaptive, mode === 'dark' ? 0.24 : 0.14));
        root.style.setProperty(`--mac-accent-${k}-light`, mixColors(adaptive, 'var(--mac-bg-primary)', mode === 'dark' ? 0.18 : 0.78));
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

  const setAccent = (name: AccentName): void => {
    if (ACCENTS[name]) setAccentState(name);
  };

  const ensureContrast = useMemo(() => (fgHex: string, bgHex: string) => ensureMinContrast(fgHex, bgHex, 4.5), []);

  const value = useMemo<MacOSThemeContextValue>(() => ({ accent, setAccent, mode, setMode, ensureContrast }), [accent, mode, ensureContrast]);

  return (
    <MacOSThemeContext.Provider value={value}>
      {children}
    </MacOSThemeContext.Provider>
  );

}

export function useMacOSTheme(): MacOSThemeContextValue {
  return useContext(MacOSThemeContext);
}

export const ACCENT_OPTIONS = Object.keys(ACCENTS);

MacOSThemeProvider.propTypes = {
  children: PropTypes.node,
};

export default MacOSThemeProvider;
