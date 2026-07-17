import PropTypes from 'prop-types';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode
} from 'react';
import { useInRouterContext, useLocation } from 'react-router-dom';
import tokens, { colors as tokenColors } from '../theme/tokens-legacy';
// colorScheme.ts / colorUtils.ts are still @ts-nocheck; their functions
// accept (string, string) and return string|null. They'll be migrated in a
// later batch — for now the implicit-any return is acceptable under the
// current tsconfig (noImplicitAny: false).
import {
  applyColorSchemeToDom,
  getStoredColorScheme,
  getSystemTheme,
  normalizeColorScheme,
  persistColorSchemeLocally,
  resolveThemeMode,
} from '../theme/colorScheme.js';
import apiClient from '../api/client.js';
import { mixColors, toRgbaString } from '../theme/colorUtils.js';
import logger from '../utils/logger';
import { isPublicRoutePath } from '../routing/routeSelectors.js';

type ThemeMode = 'light' | 'dark';
type ColorScheme = string;
type Spacing = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | string;
type FontSize = 'xs' | 'sm' | 'base' | 'md' | 'lg' | 'xl' | string;
type ShadowSize = 'sm' | 'md' | 'lg' | 'xl' | string;
type ColorToken =
  | 'primary'
  | 'secondary'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info'
  | 'text'
  | 'background'
  | 'border'
  | 'surface'
  | string;

interface ThemeConfig {
  mode: ThemeMode;
  colorScheme: ColorScheme;
}

interface ThemeContextValue {
  theme: ThemeMode;
  resolvedTheme: ThemeMode;
  colorScheme: ColorScheme;
  setColorScheme: (nextScheme: ColorScheme, options?: SetColorSchemeOptions) => void;
  setTheme: (nextTheme: ColorScheme) => void;
  toggleTheme: () => void;
  isDark: boolean;
  isLight: boolean;
  themeConfig: ThemeConfig;
  designTokens: typeof tokens;
  getColor: (color: ColorToken, shade?: number | string) => string;
  getSpacing: (size: Spacing) => string;
  getFontSize: (size: FontSize) => string;
  getShadow: (size: ShadowSize) => string;
}

interface SetColorSchemeOptions {
  skipRemoteSave?: boolean;
}

interface ThemeRouteSyncProps {
  onPathnameChange: (pathname: string) => void;
}

interface ThemeProviderProps {
  children?: ReactNode;
}

interface AuthStateChangedEvent extends Event {
  detail?: { token?: string | null };
}

const ThemeContext = createContext<ThemeContextValue | null>(null);
const THEME_PREFERENCE_SAVE_DEBOUNCE_MS = 400;
const THEME_PREFERENCE_CACHE_MS = 30_000;
const AUTH_TOKEN_STORAGE_KEY = 'auth_token';
const themePreferenceCache = new Map<string, { cachedAt: number; theme: ColorScheme }>();
const themePreferenceRequestPromiseByToken = new Map<string, Promise<ColorScheme | null>>();

function getAuthTokenSnapshot(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

function ThemeRouteSync({ onPathnameChange }: ThemeRouteSyncProps) {
  const location = useLocation();

  useEffect(() => {
    onPathnameChange(location.pathname);
  }, [location.pathname, onPathnameChange]);

  return null;
}

function getCachedThemePreference(token: string): ColorScheme | null {
  const entry = themePreferenceCache.get(token);
  if (!entry) {
    return null;
  }

  if (Date.now() - entry.cachedAt > THEME_PREFERENCE_CACHE_MS) {
    themePreferenceCache.delete(token);
    return null;
  }

  return entry.theme;
}

function setCachedThemePreference(token: string, theme: ColorScheme): void {
  if (!token || !theme) {
    return;
  }

  themePreferenceCache.set(token, {
    cachedAt: Date.now(),
    theme,
  });
}

function clearCachedThemePreference(token?: string | null): void {
  if (token) {
    themePreferenceCache.delete(token);
    themePreferenceRequestPromiseByToken.delete(token);
    return;
  }

  themePreferenceCache.clear();
  themePreferenceRequestPromiseByToken.clear();
}

export const useTheme = (): ThemeContextValue => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

export const ThemeProvider = ({ children }: ThemeProviderProps) => {
  const hasRouterContext = useInRouterContext();
  const [pathname, setPathname] = useState<string>(() => (
    typeof window !== 'undefined' ? window.location.pathname : '/'
  ));
  const [systemTheme, setSystemTheme] = useState<ThemeMode>(() => getSystemTheme() as ThemeMode);
  const [colorScheme, setColorSchemeState] = useState<ColorScheme>(() => getStoredColorScheme() as ColorScheme);
  const [authToken, setAuthToken] = useState<string | null>(() => getAuthTokenSnapshot());
  const [preferencesReady, setPreferencesReady] = useState<boolean>(() => !getAuthTokenSnapshot());
  const hydratedTokenRef = useRef<string | null>(null);
  const skipNextRemoteSaveRef = useRef<boolean>(false);
  const lastSavedPreferenceRef = useRef<ColorScheme | null>(null);
  // window.setTimeout returns `number` in DOM, but the project's global
  // types (vitest/globals) override setTimeout to return NodeJS.Timeout.
  // Anchor to the DOM signature explicitly so the ref holds a `number`.
  const saveTimeoutRef = useRef<number | null>(null);
  const routerFallbackLoggedRef = useRef<boolean>(false);

  const theme = resolveThemeMode(colorScheme, systemTheme) as ThemeMode;
  const isDark = theme === 'dark';
  const isLight = theme === 'light';
  const themeConfig = useMemo<ThemeConfig>(() => ({ mode: theme, colorScheme }), [theme, colorScheme]);

  const getColor = useCallback((color: ColorToken, shade: number | string = 500): string => {
    const numericShade = typeof shade === 'number' ? shade : 500;
    if (color === 'primary' || color === 'secondary') {
      return (tokenColors as Record<string, Record<number, string>>)[color]?.[numericShade] || (tokenColors as Record<string, Record<number, string>>).primary?.[500] || 'var(--mac-accent-blue)';
    }
    if (color === 'success' || color === 'warning' || color === 'danger' || color === 'info') {
      const status = (tokenColors as unknown as { status?: Record<string, string> }).status;
      return status?.[color] || (tokenColors as Record<string, Record<number, string>>).primary?.[500] || 'var(--mac-accent-blue)';
    }
    if (color === 'text') {
      const semantic = (tokenColors as Record<string, { text?: Record<string, string> }>).semantic;
      const key = typeof shade === 'string' ? shade : 'primary';
      return semantic?.text?.[key] || 'var(--mac-text-primary)';
    }
    if (color === 'background') {
      const semantic = (tokenColors as Record<string, { background?: Record<string, string> }>).semantic;
      const key = typeof shade === 'string' ? shade : 'primary';
      return semantic?.background?.[key] || 'var(--mac-bg-primary)';
    }
    if (color === 'border') {
      const semantic = (tokenColors as Record<string, { border?: Record<string, string> }>).semantic;
      const key = typeof shade === 'string' ? shade : 'medium';
      return semantic?.border?.[key] || 'var(--mac-border)';
    }
    if (color === 'surface') {
      const semantic = (tokenColors as Record<string, { surface?: Record<string, string> }>).semantic;
      const key = typeof shade === 'string' ? shade : 'card';
      return semantic?.surface?.[key] || 'var(--mac-bg-primary)';
    }
    return (tokenColors as Record<string, Record<number, string>>).primary?.[500] || 'var(--mac-accent-blue)';
  }, []);

  const getSpacing = useCallback((size: Spacing): string => {
    const spacing = (tokens as { spacing?: Record<string, string> }).spacing;
    return spacing?.[size] || spacing?.md || '16px';
  }, []);

  const getFontSize = useCallback((size: FontSize): string => {
    const fontSize = (tokens as { typography?: { fontSize?: Record<string, string> } }).typography?.fontSize;
    return fontSize?.[size] || fontSize?.base || '16px';
  }, []);

  const getShadow = useCallback((size: ShadowSize): string => {
    const shadows = (tokens as { shadows?: Record<string, string> }).shadows;
    return shadows?.[size] || shadows?.md || '0 4px 6px -1px rgba(0, 0, 0, 0.1)';
  }, []);

  const setColorScheme = useCallback((nextScheme: ColorScheme, options: SetColorSchemeOptions = {}): void => {
    const normalizedScheme = normalizeColorScheme(nextScheme) as ColorScheme | null;
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

  const setTheme = useCallback((nextTheme: ColorScheme): void => {
    setColorScheme(nextTheme);
  }, [setColorScheme]);

  const toggleTheme = useCallback((): void => {
    setColorScheme(theme === 'dark' ? 'light' : 'dark');
  }, [setColorScheme, theme]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    const syncAuthToken = (nextToken: string | null): void => {
      setAuthToken((currentToken) => {
        const resolvedToken = typeof nextToken === 'string' ? nextToken : getAuthTokenSnapshot();
        return currentToken === resolvedToken ? currentToken : resolvedToken;
      });
    };

    const handleStorage = (event: StorageEvent) => {
      if (!event.key || event.key === AUTH_TOKEN_STORAGE_KEY) {
        syncAuthToken(event.newValue || null);
      }
    };

    const handleAuthStateChanged = (event: Event): void => {
      const detail = (event as AuthStateChangedEvent)?.detail;
      syncAuthToken(detail?.token || null);
    };

    syncAuthToken(getAuthTokenSnapshot());
    window.addEventListener('storage', handleStorage);
    window.addEventListener('authStateChanged', handleAuthStateChanged);

    return () => {
      window.removeEventListener('storage', handleStorage);
      window.removeEventListener('authStateChanged', handleAuthStateChanged);
    };
  }, []);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (event: MediaQueryListEvent): void => {
      setSystemTheme(event.matches ? 'dark' : 'light');
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange);
    } else {
      // Legacy Safari < 14 fallback — addListener is missing from the
      // modern lib.dom typings but exists at runtime on older browsers.
      (mediaQuery as unknown as { addListener: (cb: (e: MediaQueryListEvent) => void) => void }).addListener(handleChange);
    }

    return () => {
      if (mediaQuery.removeEventListener) {
        mediaQuery.removeEventListener('change', handleChange);
      } else {
        (mediaQuery as unknown as { removeListener: (cb: (e: MediaQueryListEvent) => void) => void }).removeListener(handleChange);
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
    if (hasRouterContext || routerFallbackLoggedRef.current) {
      return;
    }

    routerFallbackLoggedRef.current = true;
    logger.info('[FIX:THEME] Router context missing, using window pathname fallback', {
      pathname,
    });
  }, [hasRouterContext, pathname]);

  useEffect(() => {
    const root = document.documentElement;
    const computedStyle = window.getComputedStyle(root);
    const semanticColors = (tokenColors as { semantic?: Record<string, Record<string, string>> }).semantic;
    const primaryColors = (tokenColors as { primary?: Record<number, string> }).primary;
    const statusColors = (tokenColors as { status?: Record<string, string> }).status;
    const macBgPrimary = computedStyle.getPropertyValue('--mac-bg-primary').trim() || semanticColors?.background.primary;
    const macBgSecondary = computedStyle.getPropertyValue('--mac-bg-secondary').trim() || semanticColors?.background.secondary;
    const macBgTertiary = computedStyle.getPropertyValue('--mac-bg-tertiary').trim() || semanticColors?.background.tertiary;
    const macTextPrimary = computedStyle.getPropertyValue('--mac-text-primary').trim() || semanticColors?.text.primary;
    const macTextSecondary = computedStyle.getPropertyValue('--mac-text-secondary').trim() || semanticColors?.text.secondary;
    const macBorder = computedStyle.getPropertyValue('--mac-border').trim() || semanticColors?.border.medium;
    const macHover =
      computedStyle.getPropertyValue('--mac-nav-item-hover').trim() ||
      computedStyle.getPropertyValue('--mac-bg-secondary').trim() ||
      semanticColors?.surface.hover;
    const macAccent =
      computedStyle.getPropertyValue('--mac-accent').trim() ||
      primaryColors?.[isDark ? 400 : 500];

    root.style.setProperty('--bg-primary', macBgPrimary);
    root.style.setProperty('--bg-secondary', macBgSecondary);
    root.style.setProperty('--bg-tertiary', macBgTertiary);
    root.style.setProperty('--text-primary', macTextPrimary);
    root.style.setProperty('--text-secondary', macTextSecondary);
    root.style.setProperty('--text-tertiary', macTextSecondary);
    root.style.setProperty('--border-color', macBorder);
    root.style.setProperty('--hover-bg', macHover);
    root.style.setProperty('--accent-color', macAccent);

    const success = computedStyle.getPropertyValue('--mac-success').trim() || statusColors?.success;
    const warning = computedStyle.getPropertyValue('--mac-warning').trim() || statusColors?.warning;
    const error = computedStyle.getPropertyValue('--mac-error').trim() || statusColors?.danger;
    const info = computedStyle.getPropertyValue('--mac-accent').trim() || macAccent;

    root.style.setProperty('--success-color', success);
    root.style.setProperty('--warning-color', warning);
    root.style.setProperty('--danger-color', error);
    root.style.setProperty('--info-color', info);
    root.style.setProperty(
      '--shadow-sm',
      computedStyle.getPropertyValue('--mac-shadow-sm').trim() ||
      (tokens as { shadows?: Record<string, string> }).shadows?.sm ||
      '0 1px 2px 0 rgba(0, 0, 0, 0.05)'
    );
    root.style.setProperty(
      '--shadow-md',
      computedStyle.getPropertyValue('--mac-shadow-md').trim() ||
      (tokens as { shadows?: Record<string, string> }).shadows?.md ||
      '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
    );
    root.style.setProperty(
      '--shadow-lg',
      computedStyle.getPropertyValue('--mac-shadow-lg').trim() ||
      (tokens as { shadows?: Record<string, string> }).shadows?.lg ||
      '0 10px 15px -3px rgba(0, 0, 0, 0.1)'
    );
    root.style.setProperty(
      '--shadow-xl',
      computedStyle.getPropertyValue('--mac-shadow-xl').trim() ||
      (tokens as { shadows?: Record<string, string> }).shadows?.xl ||
      '0 20px 25px -5px rgba(0, 0, 0, 0.1)'
    );

    root.style.setProperty('--mac-success-bg', toRgbaString(success, isDark ? 0.22 : 0.12));
    root.style.setProperty('--mac-success-bg-light', mixColors(success, 'var(--mac-bg-primary)', isDark ? 0.12 : 0.8));
    root.style.setProperty('--mac-success-border', toRgbaString(success, isDark ? 0.34 : 0.22));

    root.style.setProperty('--mac-warning-bg', toRgbaString(warning, isDark ? 0.22 : 0.14));
    root.style.setProperty('--mac-warning-bg-light', mixColors(warning, 'var(--mac-bg-primary)', isDark ? 0.1 : 0.78));
    root.style.setProperty('--mac-warning-border', toRgbaString(warning, isDark ? 0.36 : 0.24));

    root.style.setProperty('--mac-error-bg', toRgbaString(error, isDark ? 0.22 : 0.12));
    root.style.setProperty('--mac-error-bg-light', mixColors(error, 'var(--mac-bg-primary)', isDark ? 0.08 : 0.8));
    root.style.setProperty('--mac-error-border', toRgbaString(error, isDark ? 0.36 : 0.24));
    root.style.setProperty('--mac-danger', error);
    root.style.setProperty('--mac-danger-hover', mixColors(error, isDark ? 'var(--mac-bg-primary)' : '#120708', isDark ? 0.12 : 0.16));
  }, [colorScheme, isDark]);

  useEffect(() => {
    let cancelled = false;
    const currentPath = pathname;

    if (!authToken || isPublicRoutePath(currentPath)) {
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

    const cachedTheme = getCachedThemePreference(authToken);
    if (cachedTheme) {
      hydratedTokenRef.current = authToken;
      lastSavedPreferenceRef.current = cachedTheme;
      setColorSchemeState((currentColorScheme) => {
        if (currentColorScheme === cachedTheme) {
          return currentColorScheme;
        }

        skipNextRemoteSaveRef.current = true;
        logger.info('[FIX:THEME] Reusing cached color scheme preference', {
          colorScheme: cachedTheme,
        });
        return cachedTheme;
      });
      setPreferencesReady(true);
      return () => {
        cancelled = true;
      };
    }

    const inFlight = themePreferenceRequestPromiseByToken.get(authToken);
    if (inFlight) {
      setPreferencesReady(false);
      void inFlight
        .then((serverTheme: ColorScheme | null) => {
          if (cancelled || !serverTheme) {
            return;
          }
          hydratedTokenRef.current = authToken;
          lastSavedPreferenceRef.current = serverTheme;
          setColorSchemeState((currentColorScheme) => {
            if (currentColorScheme === serverTheme) {
              return currentColorScheme;
            }

            skipNextRemoteSaveRef.current = true;
            logger.info('[FIX:THEME] Reusing in-flight color scheme preference', {
              colorScheme: serverTheme,
            });
            return serverTheme;
          });
        })
        .catch((error: unknown) => {
          const err = error as { response?: { status?: number } };
          if (err?.response?.status === 401 || err?.response?.status === 403) {
            clearCachedThemePreference(authToken);
            logger.info('[FIX:THEME] Skipping theme preference reuse due to auth state', {
              status: err?.response?.status,
            });
            return;
          }
          logger.warn('[FIX:THEME] In-flight theme preference request failed', error);
        })
        .finally(() => {
          if (!cancelled) {
            setPreferencesReady(true);
          }
        });
      return () => {
        cancelled = true;
      };
    }

    const loadThemePreference = async (): Promise<void> => {
      try {
        const requestPromise = apiClient.get('/users/me/preferences').then((response: { data?: { theme?: unknown } }) => {
          const serverTheme = normalizeColorScheme(response?.data?.theme) as ColorScheme | null;
          if (serverTheme) {
            setCachedThemePreference(authToken, serverTheme);
          }
          return serverTheme;
        }) as Promise<ColorScheme | null>;
        themePreferenceRequestPromiseByToken.set(authToken, requestPromise);
        const serverTheme = await requestPromise;
        if (cancelled) {
          return;
        }

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
        const err = error as { response?: { status?: number } };
        if (err?.response?.status === 401 || err?.response?.status === 403) {
          clearCachedThemePreference(authToken);
          logger.info('[FIX:THEME] Skipping theme preference load due to auth state', {
            status: err?.response?.status,
          });
          return;
        }
        logger.warn('[FIX:THEME] Failed to load user theme preference', error);
      } finally {
        themePreferenceRequestPromiseByToken.delete(authToken);
        if (!cancelled) {
          setPreferencesReady(true);
        }
      }
    };

    void loadThemePreference();

    return () => {
      cancelled = true;
    };
  }, [authToken, pathname]);

  useEffect(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
      saveTimeoutRef.current = null;
    }

    if (!authToken || !preferencesReady || isPublicRoutePath(pathname)) {
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

    const capturedAuthToken = authToken;
    const capturedColorScheme = colorScheme;
    saveTimeoutRef.current = window.setTimeout(async () => {
        try {
          await apiClient.put('/users/me/preferences', { theme: capturedColorScheme });
          setCachedThemePreference(capturedAuthToken, capturedColorScheme);
          lastSavedPreferenceRef.current = capturedColorScheme;
          logger.info('[FIX:THEME] Saved color scheme to user preferences', {
            colorScheme: capturedColorScheme,
          });
        } catch (error) {
          const err = error as { response?: { status?: number } };
          if (err?.response?.status === 401 || err?.response?.status === 403) {
            clearCachedThemePreference(capturedAuthToken);
            logger.info('[FIX:THEME] Skipping theme preference save due to auth state', {
              status: err?.response?.status,
            });
            return;
          }
          logger.warn('[FIX:THEME] Failed to save user theme preference', error);
        }
    }, THEME_PREFERENCE_SAVE_DEBOUNCE_MS);

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
        saveTimeoutRef.current = null;
      }
    };
  }, [authToken, colorScheme, preferencesReady, pathname]);

  const value = useMemo<ThemeContextValue>(() => ({
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
      {hasRouterContext ? <ThemeRouteSync onPathnameChange={setPathname} /> : null}
      {children}
    </ThemeContext.Provider>
  );

};

ThemeProvider.propTypes = {
  children: PropTypes.node,
};
