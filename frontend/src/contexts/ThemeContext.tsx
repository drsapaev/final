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
// PR-UI-17-4: theme/tokens-legacy.ts deleted — its only live importer was this
// context. The legacy token values ThemeContext actually reads are inlined
// below as private constants (byte-identical values; lookup logic untouched).
// The context effect already reads CSS variables FIRST and uses these maps
// only as fallbacks. Full getColor migration to var(--mac-*) would change
// rendered colors (legacy palette ≠ macOS palette: #0ea5e9 vs #007aff) and
// requires a dedicated visual-regression-verified effort — recorded in
// Plan-SSOT. The unused `designTokens` context property is dropped (0
// external consumers).
import {
  applyColorSchemeToDom,
  getStoredColorScheme,
  getSystemTheme,
  normalizeColorScheme,
  persistColorSchemeLocally,
  resolveThemeMode,
} from '../theme/colorScheme';
import { legacyColors, legacySpacing, legacyFontSize, legacyShadows } from './themeLegacyTokens';
import apiClient from '../api/client';
import { mixColors, toRgbaString } from '../theme/colorUtils';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
import { isPublicRoutePath } from '../routing/routeSelectors';
import type { HttpApiError } from '../types/errors';

// PR-UI-17-4: legacy token maps live in ./themeLegacyTokens.ts (private
// data module; values byte-identical to the deleted theme/tokens-legacy.ts).
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
const themePreferenceCache = new Map<string, { cachedAt: number; theme: ColorScheme }>();
const themePreferenceRequestPromiseByToken = new Map<string, Promise<ColorScheme | null>>();

// audit/phase-2, BS-32: previously this read `localStorage.getItem('auth_token')`
// directly, but PR-39 / P0-2 migrated tokens to sessionStorage (and the new
// access point is `tokenManager.getAccessToken()`). The localStorage read was
// ALWAYS null in production, so the `if (!authToken) return` guard short-
// circuited every call and theme preferences were never loaded from the
// backend. Delegating to tokenManager ensures we read from the same SSOT the
// rest of the app uses, regardless of which storage backend tokenManager
// internally chooses.
function getAuthTokenSnapshot(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }

  try {
    return tokenManager.getAccessToken();
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
      return (legacyColors as Record<string, Record<number, string>>)[color]?.[numericShade] || (legacyColors as Record<string, Record<number, string>>).primary?.[500] || 'var(--mac-accent-blue)';
    }
    if (color === 'success' || color === 'warning' || color === 'danger' || color === 'info') {
      const status = (legacyColors as unknown as { status?: Record<string, string> }).status;
      return status?.[color] || (legacyColors as Record<string, Record<number, string>>).primary?.[500] || 'var(--mac-accent-blue)';
    }
    if (color === 'text') {
      const semantic = (legacyColors as Record<string, { text?: Record<string, string> }>).semantic;
      const key = typeof shade === 'string' ? shade : 'primary';
      return semantic?.text?.[key] || 'var(--mac-text-primary)';
    }
    if (color === 'background') {
      const semantic = (legacyColors as Record<string, { background?: Record<string, string> }>).semantic;
      const key = typeof shade === 'string' ? shade : 'primary';
      return semantic?.background?.[key] || 'var(--mac-bg-primary)';
    }
    if (color === 'border') {
      const semantic = (legacyColors as Record<string, { border?: Record<string, string> }>).semantic;
      const key = typeof shade === 'string' ? shade : 'medium';
      return semantic?.border?.[key] || 'var(--mac-border)';
    }
    if (color === 'surface') {
      const semantic = (legacyColors as Record<string, { surface?: Record<string, string> }>).semantic;
      const key = typeof shade === 'string' ? shade : 'card';
      return semantic?.surface?.[key] || 'var(--mac-bg-primary)';
    }
    return (legacyColors as Record<string, Record<number, string>>).primary?.[500] || 'var(--mac-accent-blue)';
  }, []);

  const getSpacing = useCallback((size: Spacing): string => {
    return legacySpacing[size] || legacySpacing[4] || '16px';
  }, []);

  const getFontSize = useCallback((size: FontSize): string => {
    return legacyFontSize[size] || legacyFontSize.base || '16px';
  }, []);

  const getShadow = useCallback((size: ShadowSize): string => {
    return legacyShadows[size] || legacyShadows.md || '0 4px 6px -1px rgba(0, 0, 0, 0.1)';
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
      // audit/phase-2, BS-32: AUTH_TOKEN_STORAGE_KEY was removed when we
      // switched to tokenManager. sessionStorage 'storage' events only fire
      // cross-tab for localStorage, but tokenManager uses sessionStorage —
      // so this branch will never fire for token changes. Keep the listener
      // for the `null` key (clear-all) case which signals a logout sweep.
      // The actual cross-component auth sync is handled by the
      // 'authStateChanged' CustomEvent below.
      if (!event.key) {
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
    // PR-UI-01: removed dispatch of 'colorSchemeChanged' CustomEvent.
    // The only consumer was MacOSThemeProvider (deleted in this PR). Components
    // that need to react to theme changes should read useTheme().colorScheme
    // or useTheme().theme directly — React re-renders propagate the change.
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
    const semanticColors = (legacyColors as { semantic?: Record<string, Record<string, string>> }).semantic;
    const primaryColors = (legacyColors as { primary?: Record<number, string> }).primary;
    const statusColors = (legacyColors as { status?: Record<string, string> }).status;
    const macBgPrimary: string = computedStyle.getPropertyValue('--mac-bg-primary').trim() || semanticColors?.background.primary || '';
    const macBgSecondary: string = computedStyle.getPropertyValue('--mac-bg-secondary').trim() || semanticColors?.background.secondary || '';
    const macBgTertiary: string = computedStyle.getPropertyValue('--mac-bg-tertiary').trim() || semanticColors?.background.tertiary || '';
    const macTextPrimary: string = computedStyle.getPropertyValue('--mac-text-primary').trim() || semanticColors?.text.primary || '';
    const macTextSecondary: string = computedStyle.getPropertyValue('--mac-text-secondary').trim() || semanticColors?.text.secondary || '';
    const macBorder: string = computedStyle.getPropertyValue('--mac-border').trim() || semanticColors?.border.medium || '';
    const macHover: string =
      computedStyle.getPropertyValue('--mac-nav-item-hover').trim() ||
      computedStyle.getPropertyValue('--mac-bg-secondary').trim() ||
      semanticColors?.surface.hover ||
      '';
    const macAccent: string =
      computedStyle.getPropertyValue('--mac-accent').trim() ||
      primaryColors?.[isDark ? 400 : 500] ||
      '';

    root.style.setProperty('--bg-primary', macBgPrimary);
    root.style.setProperty('--bg-secondary', macBgSecondary);
    root.style.setProperty('--bg-tertiary', macBgTertiary);
    root.style.setProperty('--text-primary', macTextPrimary);
    root.style.setProperty('--text-secondary', macTextSecondary);
    root.style.setProperty('--text-tertiary', macTextSecondary);
    root.style.setProperty('--border-color', macBorder);
    root.style.setProperty('--hover-bg', macHover);
    root.style.setProperty('--accent-color', macAccent);

    const success: string = computedStyle.getPropertyValue('--mac-success').trim() || statusColors?.success || '';
    const warning: string = computedStyle.getPropertyValue('--mac-warning').trim() || statusColors?.warning || '';
    const error: string = computedStyle.getPropertyValue('--mac-error').trim() || statusColors?.danger || '';
    const info: string = computedStyle.getPropertyValue('--mac-accent').trim() || macAccent;

    root.style.setProperty('--success-color', success);
    root.style.setProperty('--warning-color', warning);
    root.style.setProperty('--danger-color', error);
    root.style.setProperty('--info-color', info);
    root.style.setProperty(
      '--shadow-sm',
      computedStyle.getPropertyValue('--mac-shadow-sm').trim() ||
      legacyShadows.sm ||
      '0 1px 2px 0 rgba(0, 0, 0, 0.05)'
    );
    root.style.setProperty(
      '--shadow-md',
      computedStyle.getPropertyValue('--mac-shadow-md').trim() ||
      legacyShadows.md ||
      '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
    );
    root.style.setProperty(
      '--shadow-lg',
      computedStyle.getPropertyValue('--mac-shadow-lg').trim() ||
      legacyShadows.lg ||
      '0 10px 15px -3px rgba(0, 0, 0, 0.1)'
    );
    root.style.setProperty(
      '--shadow-xl',
      computedStyle.getPropertyValue('--mac-shadow-xl').trim() ||
      legacyShadows.xl ||
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
          const err = error as HttpApiError;
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
        const err = error as HttpApiError;
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
          const err = error as HttpApiError;
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

