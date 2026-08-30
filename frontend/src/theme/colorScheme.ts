// (legacy banner kept blank for git diff readability)

import logger from '../utils/logger';

export type ThemeMode = 'light' | 'dark' | 'system';
export type ColorSchemeId = 'light' | 'dark' | 'auto' | string;

interface ColorSchemePreview {
  background: string;
  surface: string;
  surfaceAlt: string;
  accent: string;
  text: string;
  border: string;
}

interface ColorSchemeDefinition {
  id: ColorSchemeId;
  name: string;
  kind: 'standard' | 'custom';
  resolvedTheme: ThemeMode;
  description: string;
  mood: string;
  surfaces: string;
  contrast: string;
  bestFor: string;
  preview: ColorSchemePreview;
  tokens?: Record<string, string>;
  rootStyles?: Record<string, string>;
  bodyStyles?: Record<string, string>;
}

export const THEME_STORAGE_KEYS = {
  theme: 'theme',
  uiTheme: 'ui_theme',
  colorScheme: 'colorScheme',
  customColorScheme: 'customColorScheme',
  activeColorSchemeId: 'activeColorSchemeId',
};

const COLOR_SCHEME_DEFINITIONS: Record<string, ColorSchemeDefinition> = {
  light: {
    id: 'light',
    name: 'Светлая',
    kind: 'standard',
    resolvedTheme: 'light',
    description: 'Светлая рабочая среда с мягкими серо-голубыми поверхностями и читаемыми границами.',
    mood: 'Спокойная',
    surfaces: 'Плотные',
    contrast: 'Высокий',
    bestFor: 'Регистратура, дневные кабинеты, длинные формы',
    preview: {
      background: 'linear-gradient(180deg, #f7f9fc 0%, #e7edf4 100%)',
      surface: 'rgba(255, 255, 255, 0.86)',
      surfaceAlt: '#e7edf4',
      accent: '#0a7cff',
      text: '#111315',
      border: 'rgba(15, 23, 42, 0.14)',
    },
  },
  dark: {
    id: 'dark',
    name: 'Темная',
    kind: 'standard',
    resolvedTheme: 'dark',
    description: 'Тёмные панели с плотным контрастом и акцентом на читаемость вечером.',
    mood: 'Собранная',
    surfaces: 'Плотные',
    contrast: 'Высокий',
    bestFor: 'Вечерние смены, концентрированная работа, контрольные панели',
    preview: {
      background: 'linear-gradient(180deg, #12151b 0%, #1b2230 100%)',
      surface: 'rgba(26, 31, 40, 0.88)',
      surfaceAlt: '#273040',
      accent: '#59b6ff',
      text: '#f7fbff',
      border: 'rgba(255, 255, 255, 0.12)',
    },
  },
  auto: {
    id: 'auto',
    name: 'Авто',
    kind: 'standard',
    resolvedTheme: 'system',
    description: 'Подстраивается под системную тему устройства без ручного переключения.',
    mood: 'Адаптивная',
    surfaces: 'Системные',
    contrast: 'Зависит от ОС',
    bestFor: 'Общие рабочие станции и shared devices',
    preview: {
      background: 'linear-gradient(140deg, #f7f9fc 0%, #e8edf5 40%, #1a2230 100%)',
      surface: 'rgba(255, 255, 255, 0.18)',
      surfaceAlt: 'rgba(17, 24, 39, 0.58)',
      accent: '#4aa3ff',
      text: '#f7fbff',
      border: 'rgba(255, 255, 255, 0.18)',
    },
  },
};

export const COLOR_SCHEMES = Object.values(COLOR_SCHEME_DEFINITIONS).map((scheme) => ({
  id: scheme.id,
  name: scheme.name,
  kind: scheme.kind,
  resolvedTheme: scheme.resolvedTheme,
  description: scheme.description,
  mood: scheme.mood,
  surfaces: scheme.surfaces,
  contrast: scheme.contrast,
  bestFor: scheme.bestFor,
  preview: scheme.preview,
}));

const COLOR_SCHEME_MAP = new Map<string, ColorSchemeDefinition>(COLOR_SCHEMES.map((scheme) => [scheme.id, scheme] as const));
const CUSTOM_SCHEME_IDS = new Set<string>(
  COLOR_SCHEMES.filter((scheme) => scheme.kind === 'custom').map((scheme) => scheme.id)
);
const CUSTOM_STYLE_PROPERTIES: string[] = [
  ...new Set(
    Object.values(COLOR_SCHEME_DEFINITIONS)
      .filter((scheme) => scheme.kind === 'custom')
      .flatMap((scheme) => Object.keys(scheme.tokens || {}))
  ),
];
const ROOT_STYLE_PROPERTIES = ['background', 'backdropFilter', 'webkitBackdropFilter'];
const THEME_MODE_CLASSES = ['light-theme', 'dark-theme', 'theme-light', 'theme-dark'];
const SCHEME_CLASSES = Object.keys(COLOR_SCHEME_DEFINITIONS).flatMap((schemeId) => [
  `scheme-${schemeId}`,
  `color-scheme-${schemeId}`,
]);

export function getColorSchemeDefinition(value: unknown): ColorSchemeDefinition {
  const normalized = normalizeColorScheme(value) || 'light';
  return COLOR_SCHEME_DEFINITIONS[normalized] || COLOR_SCHEME_DEFINITIONS.light;
}

export function isSupportedColorScheme(value: unknown): boolean {
  return typeof value === 'string' && COLOR_SCHEME_MAP.has(value);
}

export function isCustomColorScheme(value: unknown): boolean {
  return typeof value === 'string' && CUSTOM_SCHEME_IDS.has(value);
}

export function normalizeColorScheme(value: unknown): string | null {
  if (!value || typeof value !== 'string') {
    return null;
  }

  if (value === 'system') {
    return 'auto';
  }

  // PR-UI-02: migrate deleted custom schemes to 'auto'.
  // Users who previously selected vibrant/glass/gradient (deleted in PR-UI-02)
  // will have these values stored in localStorage or /users/me/preferences.
  // Map them to 'auto' so the theme system falls back to prefers-color-scheme.
  const DELETED_CUSTOM_SCHEMES = new Set(['vibrant', 'glass', 'gradient']);
  if (DELETED_CUSTOM_SCHEMES.has(value)) {
    return 'auto';
  }

  return isSupportedColorScheme(value) ? value : null;
}

export function getSystemTheme(): ThemeMode {
  if (typeof window === 'undefined') {
    return 'light';
  }

  return window.matchMedia &&
    window.matchMedia('(prefers-color-scheme: dark)').matches ?
    'dark' :
    'light';
}

export function resolveThemeMode(colorScheme: unknown, systemTheme: ThemeMode = getSystemTheme()): ThemeMode {
  const scheme = getColorSchemeDefinition(colorScheme);
  return scheme.resolvedTheme === 'system' ? systemTheme : scheme.resolvedTheme;
}

export function getStoredColorScheme(): string {
  if (typeof window === 'undefined') {
    return 'light';
  }

  try {
    const explicitScheme = normalizeColorScheme(localStorage.getItem(THEME_STORAGE_KEYS.colorScheme));
    if (explicitScheme) {
      return explicitScheme;
    }

    const activeCustomScheme = normalizeColorScheme(localStorage.getItem(THEME_STORAGE_KEYS.activeColorSchemeId));
    // PR-UI-02: migrate legacy custom-scheme keys before isCustomColorScheme check.
    // normalizeColorScheme('glass') returns 'auto', but isCustomColorScheme('auto')
    // is false, so the legacy branch would fall through to ui_theme. Check the
    // raw value directly for deleted custom schemes (per Codex review feedback).
    const DELETED_CUSTOM_SCHEME_IDS = ['vibrant', 'glass', 'gradient'];
    const rawActiveSchemeId = localStorage.getItem(THEME_STORAGE_KEYS.activeColorSchemeId);
    if (
      localStorage.getItem(THEME_STORAGE_KEYS.customColorScheme) === 'true' &&
      rawActiveSchemeId &&
      DELETED_CUSTOM_SCHEME_IDS.includes(rawActiveSchemeId)
    ) {
      return 'auto';
    }
    if (
      localStorage.getItem(THEME_STORAGE_KEYS.customColorScheme) === 'true' &&
      activeCustomScheme &&
      isCustomColorScheme(activeCustomScheme)
    ) {
      return activeCustomScheme;
    }

    const storedTheme = normalizeColorScheme(
      localStorage.getItem(THEME_STORAGE_KEYS.uiTheme) ||
      localStorage.getItem(THEME_STORAGE_KEYS.theme)
    );

    return storedTheme || 'light';
  } catch (error) {
    logger.warn('[FIX:THEME] Failed to read stored color scheme', error);
    return 'light';
  }
}

export function persistColorSchemeLocally(colorScheme: string, resolvedTheme: string): void {
  if (typeof window === 'undefined') {
    return;
  }

  try {
    localStorage.setItem(THEME_STORAGE_KEYS.colorScheme, colorScheme);
    localStorage.setItem(THEME_STORAGE_KEYS.uiTheme, resolvedTheme);
    localStorage.setItem(THEME_STORAGE_KEYS.theme, resolvedTheme);

    if (isCustomColorScheme(colorScheme)) {
      localStorage.setItem(THEME_STORAGE_KEYS.customColorScheme, 'true');
      localStorage.setItem(THEME_STORAGE_KEYS.activeColorSchemeId, colorScheme);
    } else {
      localStorage.removeItem(THEME_STORAGE_KEYS.customColorScheme);
      localStorage.removeItem(THEME_STORAGE_KEYS.activeColorSchemeId);
    }
  } catch (error) {
    logger.warn('[FIX:THEME] Failed to persist color scheme locally', error);
  }
}

function clearInlineCustomTheme(root: HTMLElement, body: HTMLElement): void {
  CUSTOM_STYLE_PROPERTIES.forEach((property) => {
    root.style.removeProperty(property);
  });

  ROOT_STYLE_PROPERTIES.forEach((property) => {
    // CSSStyleDeclaration uses camelCase props; index via structural cast.
    (root.style as unknown as Record<string, string>)[property] = '';
    (body.style as unknown as Record<string, string>)[property] = '';
  });
}

export function applyColorSchemeToDom(colorScheme: unknown, resolvedTheme?: string): void {
  if (typeof document === 'undefined') {
    return;
  }

  const root = document.documentElement;
  const body = document.body;
  const definition = getColorSchemeDefinition(colorScheme);
  const themeMode = (resolvedTheme || resolveThemeMode(definition.id)) as ThemeMode;

  root.classList.remove(...THEME_MODE_CLASSES, ...SCHEME_CLASSES);
  body.classList.remove(...THEME_MODE_CLASSES, ...SCHEME_CLASSES);
  root.classList.add(`${themeMode}-theme`, `theme-${themeMode}`, `scheme-${definition.id}`, `color-scheme-${definition.id}`);
  body.classList.add(`${themeMode}-theme`, `theme-${themeMode}`, `scheme-${definition.id}`, `color-scheme-${definition.id}`);
  root.setAttribute('data-theme', themeMode);
  body.setAttribute('data-theme', themeMode);
  root.setAttribute('data-color-scheme', definition.id);
  body.setAttribute('data-color-scheme', definition.id);
  root.style.colorScheme = themeMode;
  body.style.colorScheme = themeMode;
  clearInlineCustomTheme(root, body);

  if (!isCustomColorScheme(definition.id)) {
    return;
  }

  const rootStyle = root.style as unknown as Record<string, string>;
  const bodyStyle = body.style as unknown as Record<string, string>;

  Object.entries(definition.tokens || {}).forEach(([property, value]) => {
    root.style.setProperty(property, value);
  });

  Object.entries(definition.rootStyles || {}).forEach(([property, value]) => {
    rootStyle[property] = value;
  });

  Object.entries(definition.bodyStyles || {}).forEach(([property, value]) => {
    bodyStyle[property] = value;
  });
}

export function bootstrapStoredColorScheme(): { colorScheme: string; resolvedTheme: string } {
  const colorScheme = getStoredColorScheme();
  const resolvedTheme = resolveThemeMode(colorScheme);
  persistColorSchemeLocally(colorScheme, resolvedTheme);
  applyColorSchemeToDom(colorScheme, resolvedTheme);
  return { colorScheme, resolvedTheme };
}
