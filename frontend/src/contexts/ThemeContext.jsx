import PropTypes from 'prop-types';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import tokens, { colors as tokenColors } from '../theme/tokens';
import {
  applyColorSchemeToDom,
  getStoredColorScheme,
  getSystemTheme,
  normalizeColorScheme,
  persistColorSchemeLocally,
  resolveThemeMode,
} from '../theme/colorScheme.js';
import { mixColors, toRgbaString } from '../theme/colorUtils.js';
import logger from '../utils/logger';

const ThemeContext = createContext();
const THEME_PREFERENCE_SAVE_DEBOUNCE_MS = 400;
const AUTH_TOKEN_STORAGE_KEY = 'auth_token';
let apiClientPromise = null;

function getAuthTokenSnapshot() {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

async function getApiClient() {
  if (!apiClientPromise) {
    apiClientPromise = import('../api/client.js').then((module) => {
      const resolvedApiClient =
        module.api ||
        module.default?.api ||
        module.default ||
        module;

      if (typeof resolvedApiClient?.get !== 'function' || typeof resolvedApiClient?.put !== 'function') {
        throw new Error('ThemeContext could not resolve API client instance');
      }

      return resolvedApiClient;
    });
  }
  return apiClientPromise;
}

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

export const ThemeProvider = ({ children }) => {
  const [systemTheme, setSystemTheme] = useState(() => getSystemTheme());
  const [colorScheme, setColorSchemeState] = useState(() => getStoredColorScheme());
  const [authToken, setAuthToken] = useState(() => getAuthTokenSnapshot());
  const [preferencesReady, setPreferencesReady] = useState(() => !getAuthTokenSnapshot());
  const hydratedTokenRef = useRef(null);
  const skipNextRemoteSaveRef = useRef(false);
  const lastSavedPreferenceRef = useRef(null);
  const saveTimeoutRef = useRef(null);

  const theme = resolveThemeMode(colorScheme, systemTheme);
  const isDark = theme === 'dark';
  const isLight = theme === 'light';
  const themeConfig = useMemo(() => ({ mode: theme, colorScheme }), [theme, colorScheme]);

  const getColor = useCallback((color, shade = 500) => {
    if (color === 'primary' || color === 'secondary') {
      return tokenColors[color]?.[shade] || tokenColors.primary?.[500] || '#0ea5e9';
    }
    if (color === 'success' || color === 'warning' || color === 'danger' || color === 'info') {
      return tokenColors.status?.[color] || tokenColors.primary?.[500] || '#0ea5e9';
    }
    if (color === 'text' || color === 'background' || color === 'border' || color === 'surface') {
      return tokenColors.semantic?.[color]?.primary || '#ffffff';
    }
    return tokenColors.primary?.[500] || '#0ea5e9';
  }, []);

  const getSpacing = useCallback((size) => {
    return tokens?.spacing?.[size] || tokens?.spacing?.md || '16px';
  }, []);

  const getFontSize = useCallback((size) => {
    return tokens?.typography?.fontSize?.[size] || tokens?.typography?.fontSize?.base || '16px';
  }, []);

  const getShadow = useCallback((size) => {
    return tokens?.shadows?.[size] || tokens?.shadows?.md || '0 4px 6px -1px rgba(0, 0, 0, 0.1)';
  }, []);

  const setColorScheme = useCallback((nextScheme, options = {}) => {
    const normalizedScheme = normalizeColorScheme(nextScheme);
    if (!normalizedScheme) {
      logger.warn('[FIX:THEME] Ignoring unsupported color scheme', { nextScheme });
      return;
    }

    if (options.skipRemoteSave) {
      skipNextRemoteSaveRef.current = true;
    }

    setColorSchemeState((prev) => {
      if (prev === normalizedScheme) {
        return prev;
      }

      logger.info('[FIX:THEME] Applying color scheme', { colorScheme: normalizedScheme });
      return normalizedScheme;
    });
  }, []);

  const setTheme = useCallback((nextTheme) => {
    setColorScheme(nextTheme);
  }, [setColorScheme]);

  const toggleTheme = useCallback(() => {
    setColorScheme(theme === 'dark' ? 'light' : 'dark');
  }, [setColorScheme, theme]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const syncAuthToken = (nextToken) => {
      setAuthToken((currentToken) => {
        const resolvedToken = typeof nextToken === 'string' ? nextToken : getAuthTokenSnapshot();
        return currentToken === resolvedToken ? currentToken : resolvedToken;
      });
    };

    const handleStorage = (event) => {
      if (!event.key || event.key === AUTH_TOKEN_STORAGE_KEY) {
        syncAuthToken(event.newValue || null);
      }
    };

    const handleAuthStateChanged = (event) => {
      syncAuthToken(event?.detail?.token || null);
    };

    syncAuthToken();
    window.addEventListener('storage', handleStorage);
    window.addEventListener('authStateChanged', handleAuthStateChanged);

    return () => {
      window.removeEventListener('storage', handleStorage);
      window.removeEventListener('authStateChanged', handleAuthStateChanged);
    };
  }, []);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (event) => {
      setSystemTheme(event.matches ? 'dark' : 'light');
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange);
    } else {
      mediaQuery.addListener(handleChange);
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener('change', handleChange);
      } else {
        mediaQuery.removeListener(handleChange);
      }
    };
  }, []);

  useEffect(() => {
    persistColorSchemeLocally(colorScheme, theme);
    applyColorSchemeToDom(colorScheme, theme);
    window.dispatchEvent(new CustomEvent('colorSchemeChanged', {
      detail: colorScheme,
    }));
  }, [colorScheme, theme]);

  useEffect(() => {
    const root = document.documentElement;
    const computedStyle = window.getComputedStyle(root);
    const macBgPrimary = computedStyle.getPropertyValue('--mac-bg-primary').trim() || tokenColors.semantic.background.primary;
    const macBgSecondary = computedStyle.getPropertyValue('--mac-bg-secondary').trim() || tokenColors.semantic.background.secondary;
    const macBgTertiary = computedStyle.getPropertyValue('--mac-bg-tertiary').trim() || tokenColors.semantic.background.tertiary;
    const macTextPrimary = computedStyle.getPropertyValue('--mac-text-primary').trim() || tokenColors.semantic.text.primary;
    const macTextSecondary = computedStyle.getPropertyValue('--mac-text-secondary').trim() || tokenColors.semantic.text.secondary;
    const macBorder = computedStyle.getPropertyValue('--mac-border').trim() || tokenColors.semantic.border.medium;
    const macHover =
      computedStyle.getPropertyValue('--mac-nav-item-hover').trim() ||
      computedStyle.getPropertyValue('--mac-bg-secondary').trim() ||
      tokenColors.semantic.surface.hover;
    const macAccent =
      computedStyle.getPropertyValue('--mac-accent').trim() ||
      tokenColors.primary[isDark ? 400 : 500];

    root.style.setProperty('--bg-primary', macBgPrimary);
    root.style.setProperty('--bg-secondary', macBgSecondary);
    root.style.setProperty('--bg-tertiary', macBgTertiary);
    root.style.setProperty('--text-primary', macTextPrimary);
    root.style.setProperty('--text-secondary', macTextSecondary);
    root.style.setProperty('--text-tertiary', macTextSecondary);
    root.style.setProperty('--border-color', macBorder);
    root.style.setProperty('--hover-bg', macHover);
    root.style.setProperty('--accent-color', macAccent);

    const success = computedStyle.getPropertyValue('--mac-success').trim() || tokenColors.status.success;
    const warning = computedStyle.getPropertyValue('--mac-warning').trim() || tokenColors.status.warning;
    const error = computedStyle.getPropertyValue('--mac-error').trim() || tokenColors.status.danger;
    const info = computedStyle.getPropertyValue('--mac-accent').trim() || macAccent;

    root.style.setProperty('--success-color', success);
    root.style.setProperty('--warning-color', warning);
    root.style.setProperty('--danger-color', error);
    root.style.setProperty('--info-color', info);
    root.style.setProperty(
      '--shadow-sm',
      computedStyle.getPropertyValue('--mac-shadow-sm').trim() ||
      tokens?.shadows?.sm ||
      '0 1px 2px 0 rgba(0, 0, 0, 0.05)'
    );
    root.style.setProperty(
      '--shadow-md',
      computedStyle.getPropertyValue('--mac-shadow-md').trim() ||
      tokens?.shadows?.md ||
      '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
    );
    root.style.setProperty(
      '--shadow-lg',
      computedStyle.getPropertyValue('--mac-shadow-lg').trim() ||
      tokens?.shadows?.lg ||
      '0 10px 15px -3px rgba(0, 0, 0, 0.1)'
    );
    root.style.setProperty(
      '--shadow-xl',
      computedStyle.getPropertyValue('--mac-shadow-xl').trim() ||
      tokens?.shadows?.xl ||
      '0 20px 25px -5px rgba(0, 0, 0, 0.1)'
    );

    root.style.setProperty('--mac-success-bg', toRgbaString(success, isDark ? 0.22 : 0.12));
    root.style.setProperty('--mac-success-bg-light', mixColors(success, '#ffffff', isDark ? 0.12 : 0.8));
    root.style.setProperty('--mac-success-border', toRgbaString(success, isDark ? 0.34 : 0.22));

    root.style.setProperty('--mac-warning-bg', toRgbaString(warning, isDark ? 0.22 : 0.14));
    root.style.setProperty('--mac-warning-bg-light', mixColors(warning, '#ffffff', isDark ? 0.1 : 0.78));
    root.style.setProperty('--mac-warning-border', toRgbaString(warning, isDark ? 0.36 : 0.24));

    root.style.setProperty('--mac-error-bg', toRgbaString(error, isDark ? 0.22 : 0.12));
    root.style.setProperty('--mac-error-bg-light', mixColors(error, '#ffffff', isDark ? 0.08 : 0.8));
    root.style.setProperty('--mac-error-border', toRgbaString(error, isDark ? 0.36 : 0.24));
    root.style.setProperty('--mac-danger', error);
    root.style.setProperty('--mac-danger-hover', mixColors(error, isDark ? '#ffffff' : '#120708', isDark ? 0.12 : 0.16));
  }, [colorScheme, isDark]);

  useEffect(() => {
    let cancelled = false;

    if (!authToken) {
      hydratedTokenRef.current = null;
      lastSavedPreferenceRef.current = null;
      setPreferencesReady(true);
      return () => {
        cancelled = true;
      };
    }

    if (hydratedTokenRef.current === authToken) {
      setPreferencesReady(true);
      return () => {
        cancelled = true;
      };
    }

    setPreferencesReady(false);

    const loadThemePreference = async () => {
      try {
        const api = await getApiClient();
        const response = await api.get('/users/me/preferences');
        if (cancelled) {
          return;
        }

        const serverTheme = normalizeColorScheme(response?.data?.theme);
        hydratedTokenRef.current = authToken;

        if (serverTheme) {
          lastSavedPreferenceRef.current = serverTheme;
          setColorSchemeState((currentColorScheme) => {
            if (currentColorScheme === serverTheme) {
              return currentColorScheme;
            }

            skipNextRemoteSaveRef.current = true;
            logger.info('[FIX:THEME] Loaded color scheme from user preferences', {
              colorScheme: serverTheme,
            });
            return serverTheme;
          });
        }
      } catch (error) {
        logger.warn('[FIX:THEME] Failed to load user theme preference', error);
      } finally {
        if (!cancelled) {
          setPreferencesReady(true);
        }
      }
    };

    void loadThemePreference();

    return () => {
      cancelled = true;
    };
  }, [authToken]);

  useEffect(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = null;
    }

    if (!authToken || !preferencesReady) {
      return undefined;
    }

    if (skipNextRemoteSaveRef.current) {
      skipNextRemoteSaveRef.current = false;
      lastSavedPreferenceRef.current = colorScheme;
      return undefined;
    }

    if (lastSavedPreferenceRef.current === colorScheme) {
      return undefined;
    }

    saveTimeoutRef.current = window.setTimeout(async () => {
      try {
        const api = await getApiClient();
        await api.put('/users/me/preferences', { theme: colorScheme });
        lastSavedPreferenceRef.current = colorScheme;
        logger.info('[FIX:THEME] Saved color scheme to user preferences', {
          colorScheme,
        });
      } catch (error) {
        logger.warn('[FIX:THEME] Failed to save user theme preference', error);
      }
    }, THEME_PREFERENCE_SAVE_DEBOUNCE_MS);

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
        saveTimeoutRef.current = null;
      }
    };
  }, [authToken, colorScheme, preferencesReady]);

  const value = useMemo(() => ({
    theme,
    resolvedTheme: theme,
    colorScheme,
    setColorScheme,
    setTheme,
    toggleTheme,
    isDark,
    isLight,
    themeConfig,
    designTokens: tokens,
    getColor,
    getSpacing,
    getFontSize,
    getShadow,
  }), [
    colorScheme,
    getColor,
    getFontSize,
    getShadow,
    getSpacing,
    isDark,
    isLight,
    setColorScheme,
    setTheme,
    theme,
    themeConfig,
    toggleTheme,
  ]);

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>);

};

ThemeProvider.propTypes = {
  children: PropTypes.node,
};
