import logger from '../utils/logger';

export const THEME_STORAGE_KEYS = {
  theme: 'theme',
  uiTheme: 'ui_theme',
  colorScheme: 'colorScheme',
  customColorScheme: 'customColorScheme',
  activeColorSchemeId: 'activeColorSchemeId',
};

const COLOR_SCHEME_DEFINITIONS = {
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
  vibrant: {
    id: 'vibrant',
    name: 'Яркая многоцветная',
    kind: 'custom',
    resolvedTheme: 'dark',
    description: 'Тёплая матовая сцена с мягкими закатными оттенками и выраженными поверхностями.',
    mood: 'Энергичная',
    surfaces: 'Матовые',
    contrast: 'Средне-высокий',
    bestFor: 'Публичные зоны, демонстрации, живые панели ожидания',
    preview: {
      background: 'radial-gradient(circle at 14% 14%, rgba(255, 208, 132, 0.3), transparent 24%), radial-gradient(circle at 84% 16%, rgba(255, 123, 107, 0.24), transparent 20%), linear-gradient(145deg, #4a2729 0%, #92524c 52%, #f0a260 100%)',
      surface: 'rgba(96, 50, 56, 0.5)',
      surfaceAlt: 'rgba(255, 241, 226, 0.16)',
      accent: '#ffc677',
      text: '#f8fbff',
      border: 'rgba(255, 255, 255, 0.2)',
    },
    tokens: {
      '--mac-bg-primary': '#46252a',
      '--mac-bg-secondary': '#69363f',
      '--mac-bg-tertiary': '#8a4a52',
      '--mac-bg-toolbar': 'rgba(104, 52, 57, 0.58)',
      '--mac-text-primary': '#f8fbff',
      '--mac-text-secondary': 'rgba(248, 244, 239, 0.84)',
      '--mac-border': 'rgba(255, 255, 255, 0.2)',
      '--mac-border-secondary': 'rgba(255, 255, 255, 0.14)',
      '--mac-separator': 'rgba(255, 255, 255, 0.16)',
      '--mac-gradient-window': 'radial-gradient(circle at 12% 12%, rgba(255, 220, 156, 0.4), transparent 24%), radial-gradient(circle at 84% 16%, rgba(255, 128, 108, 0.32), transparent 20%), linear-gradient(148deg, rgba(68, 31, 37, 0.98) 0%, rgba(143, 69, 67, 0.9) 46%, rgba(248, 164, 95, 0.9) 100%)',
      '--mac-gradient-sidebar': 'linear-gradient(180deg, rgba(85, 39, 47, 0.86) 0%, rgba(154, 71, 67, 0.78) 100%)',
      '--mac-blur-light': 'saturate(170%) blur(16px)',
      '--mac-success': '#5bcf84',
      '--mac-warning': '#ffca78',
      '--mac-error': '#ff7a6b',
      '--mac-scheme-accent': '#ffca78',
      '--mac-header-bg': 'rgba(112, 52, 58, 0.52)',
      '--mac-card-bg': 'rgba(138, 66, 74, 0.46)',
      '--mac-card-hover-bg': 'rgba(170, 82, 90, 0.62)',
      '--mac-card-border': 'rgba(255, 255, 255, 0.18)',
      '--mac-nav-item-bg': 'rgba(255, 245, 236, 0.08)',
      '--mac-nav-item-hover': 'rgba(255, 202, 120, 0.2)',
      '--mac-nav-item-active': 'linear-gradient(135deg, rgba(255, 214, 153, 0.34) 0%, rgba(255, 139, 105, 0.3) 100%)',
      '--mac-nav-item-active-border': 'rgba(255, 214, 153, 0.42)',
      '--mac-nav-item-active-text': '#fff8f1',
      '--mac-main-shell-bg': 'linear-gradient(180deg, rgba(255, 239, 224, 0.2) 0%, rgba(255, 176, 104, 0.14) 100%)',
      '--mac-main-shell-border': 'rgba(255, 225, 195, 0.26)',
      '--mac-main-shell-shadow': '0 24px 56px rgba(56, 16, 30, 0.4)',
      '--bg': '#35171d',
      '--surface': 'rgba(255, 244, 233, 0.18)',
    },
  },
  glass: {
    id: 'glass',
    name: 'Полупрозрачная стеклянная',
    kind: 'custom',
    resolvedTheme: 'dark',
    description: 'Глубокие стеклянные поверхности с мягким свечением и лёгкой пространственностью.',
    mood: 'Премиальная',
    surfaces: 'Стекло',
    contrast: 'Средний',
    bestFor: 'Кабинеты, дашборды и интерфейсы с упором на атмосферу',
    preview: {
      background: 'radial-gradient(circle at 18% 16%, rgba(125, 211, 252, 0.22), transparent 26%), linear-gradient(145deg, rgba(14, 22, 33, 0.98) 0%, rgba(31, 52, 73, 0.9) 100%)',
      surface: 'rgba(255, 255, 255, 0.14)',
      surfaceAlt: 'rgba(255, 255, 255, 0.08)',
      accent: '#8bd5ff',
      text: '#f7fbff',
      border: 'rgba(255, 255, 255, 0.2)',
    },
    tokens: {
      '--mac-bg-primary': 'rgba(15, 23, 35, 0.72)',
      '--mac-bg-secondary': 'rgba(25, 37, 52, 0.6)',
      '--mac-bg-tertiary': 'rgba(52, 70, 90, 0.46)',
      '--mac-bg-toolbar': 'rgba(15, 23, 35, 0.72)',
      '--mac-text-primary': '#f7fbff',
      '--mac-text-secondary': 'rgba(247, 251, 255, 0.76)',
      '--mac-border': 'rgba(255, 255, 255, 0.18)',
      '--mac-border-secondary': 'rgba(255, 255, 255, 0.11)',
      '--mac-separator': 'rgba(255, 255, 255, 0.14)',
      '--mac-gradient-window': 'radial-gradient(circle at 18% 16%, rgba(125, 211, 252, 0.2), transparent 26%), linear-gradient(160deg, rgba(9, 15, 24, 0.96) 0%, rgba(26, 44, 63, 0.84) 100%)',
      '--mac-gradient-sidebar': 'linear-gradient(180deg, rgba(12, 18, 27, 0.74) 0%, rgba(23, 37, 54, 0.66) 100%)',
      '--mac-blur-light': 'saturate(185%) blur(24px)',
      '--mac-success': '#58d38b',
      '--mac-warning': '#ffc261',
      '--mac-error': '#ff8b7e',
      '--mac-scheme-accent': '#8bd5ff',
      '--mac-header-bg': 'rgba(12, 18, 27, 0.52)',
      '--mac-card-bg': 'rgba(255, 255, 255, 0.1)',
      '--mac-card-hover-bg': 'rgba(255, 255, 255, 0.14)',
      '--mac-card-border': 'rgba(255, 255, 255, 0.18)',
      '--mac-nav-item-bg': 'rgba(255, 255, 255, 0.05)',
      '--mac-nav-item-hover': 'rgba(139, 213, 255, 0.1)',
      '--mac-nav-item-active': 'linear-gradient(135deg, rgba(139, 213, 255, 0.2) 0%, rgba(92, 167, 255, 0.18) 100%)',
      '--mac-nav-item-active-border': 'rgba(139, 213, 255, 0.28)',
      '--mac-nav-item-active-text': '#f7fbff',
      '--mac-main-shell-bg': 'linear-gradient(180deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 100%)',
      '--mac-main-shell-border': 'rgba(255, 255, 255, 0.12)',
      '--mac-main-shell-shadow': '0 24px 54px rgba(0, 0, 0, 0.24)',
      '--bg': '#091018',
      '--surface': 'rgba(255, 255, 255, 0.12)',
    },
    rootStyles: {
      background: 'rgba(8, 12, 18, 0.22)',
      backdropFilter: 'blur(24px) saturate(170%)',
      webkitBackdropFilter: 'blur(24px) saturate(170%)',
    },
    bodyStyles: {
      background: 'rgba(8, 12, 18, 0.22)',
      backdropFilter: 'blur(24px) saturate(170%)',
      webkitBackdropFilter: 'blur(24px) saturate(170%)',
    },
  },
  gradient: {
    id: 'gradient',
    name: 'Градиентная палитра',
    kind: 'custom',
    resolvedTheme: 'dark',
    description: 'Холодная сияющая сцена с длинным aurora-градиентом и более воздушными поверхностями.',
    mood: 'Иммерсивная',
    surfaces: 'Полупрозрачные',
    contrast: 'Средний',
    bestFor: 'Единые workspace-сцены, витрины и дашборды',
    preview: {
      background: 'radial-gradient(circle at 16% 14%, rgba(122, 241, 255, 0.34), transparent 24%), radial-gradient(circle at 84% 16%, rgba(172, 152, 255, 0.3), transparent 22%), linear-gradient(145deg, #133259 0%, #1f63a8 50%, #7063ff 100%)',
      surface: 'rgba(20, 63, 111, 0.34)',
      surfaceAlt: 'rgba(230, 244, 255, 0.16)',
      accent: '#9be7ff',
      text: '#fbfdff',
      border: 'rgba(255, 255, 255, 0.2)',
    },
    tokens: {
      '--mac-bg-primary': '#0b2f5a',
      '--mac-bg-secondary': '#114a84',
      '--mac-bg-tertiary': '#1b6cb3',
      '--mac-bg-toolbar': 'rgba(10, 34, 69, 0.44)',
      '--mac-text-primary': '#fbfdff',
      '--mac-text-secondary': 'rgba(251, 253, 255, 0.82)',
      '--mac-border': 'rgba(255, 255, 255, 0.2)',
      '--mac-border-secondary': 'rgba(255, 255, 255, 0.14)',
      '--mac-separator': 'rgba(255, 255, 255, 0.16)',
      '--mac-gradient-window': 'radial-gradient(circle at 14% 12%, rgba(118, 247, 255, 0.4), transparent 24%), radial-gradient(circle at 84% 16%, rgba(186, 156, 255, 0.34), transparent 22%), linear-gradient(147deg, rgba(10, 46, 91, 0.98) 0%, rgba(17, 100, 181, 0.9) 52%, rgba(113, 92, 255, 0.9) 100%)',
      '--mac-gradient-sidebar': 'linear-gradient(180deg, rgba(8, 42, 79, 0.74) 0%, rgba(22, 90, 161, 0.62) 100%)',
      '--mac-blur-light': 'saturate(165%) blur(14px)',
      '--mac-success': '#4ade80',
      '--mac-warning': '#9fe4ff',
      '--mac-error': '#ff7cb6',
      '--mac-scheme-accent': '#8ce1ff',
      '--mac-header-bg': 'rgba(10, 43, 85, 0.42)',
      '--mac-card-bg': 'rgba(10, 74, 141, 0.32)',
      '--mac-card-hover-bg': 'rgba(27, 98, 176, 0.48)',
      '--mac-card-border': 'rgba(208, 234, 255, 0.2)',
      '--mac-nav-item-bg': 'rgba(242, 248, 255, 0.08)',
      '--mac-nav-item-hover': 'rgba(140, 225, 255, 0.2)',
      '--mac-nav-item-active': 'linear-gradient(135deg, rgba(140, 225, 255, 0.32) 0%, rgba(178, 132, 255, 0.26) 100%)',
      '--mac-nav-item-active-border': 'rgba(140, 225, 255, 0.4)',
      '--mac-nav-item-active-text': '#f7fbff',
      '--mac-main-shell-bg': 'linear-gradient(180deg, rgba(225, 245, 255, 0.22) 0%, rgba(130, 203, 255, 0.12) 100%)',
      '--mac-main-shell-border': 'rgba(198, 233, 255, 0.24)',
      '--mac-main-shell-shadow': '0 24px 52px rgba(4, 28, 69, 0.34)',
      '--bg': '#092746',
      '--surface': 'rgba(225, 242, 255, 0.18)',
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

const COLOR_SCHEME_MAP = new Map(COLOR_SCHEMES.map((scheme) => [scheme.id, scheme]));
const CUSTOM_SCHEME_IDS = new Set(
  COLOR_SCHEMES.filter((scheme) => scheme.kind === 'custom').map((scheme) => scheme.id)
);
const CUSTOM_STYLE_PROPERTIES = [
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

export function getColorSchemeDefinition(value) {
  const normalized = normalizeColorScheme(value) || 'light';
  return COLOR_SCHEME_DEFINITIONS[normalized] || COLOR_SCHEME_DEFINITIONS.light;
}

export function isSupportedColorScheme(value) {
  return COLOR_SCHEME_MAP.has(value);
}

export function isCustomColorScheme(value) {
  return CUSTOM_SCHEME_IDS.has(value);
}

export function normalizeColorScheme(value) {
  if (!value || typeof value !== 'string') {
    return null;
  }

  if (value === 'system') {
    return 'auto';
  }

  return isSupportedColorScheme(value) ? value : null;
}

export function getSystemTheme() {
  if (typeof window === 'undefined') {
    return 'light';
  }

  return window.matchMedia &&
    window.matchMedia('(prefers-color-scheme: dark)').matches ?
    'dark' :
    'light';
}

export function resolveThemeMode(colorScheme, systemTheme = getSystemTheme()) {
  const scheme = getColorSchemeDefinition(colorScheme);
  return scheme.resolvedTheme === 'system' ? systemTheme : scheme.resolvedTheme;
}

export function getStoredColorScheme() {
  if (typeof window === 'undefined') {
    return 'light';
  }

  try {
    const explicitScheme = normalizeColorScheme(localStorage.getItem(THEME_STORAGE_KEYS.colorScheme));
    if (explicitScheme) {
      return explicitScheme;
    }

    const activeCustomScheme = normalizeColorScheme(localStorage.getItem(THEME_STORAGE_KEYS.activeColorSchemeId));
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

export function persistColorSchemeLocally(colorScheme, resolvedTheme) {
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

function clearInlineCustomTheme(root, body) {
  CUSTOM_STYLE_PROPERTIES.forEach((property) => {
    root.style.removeProperty(property);
  });

  ROOT_STYLE_PROPERTIES.forEach((property) => {
    root.style[property] = '';
    body.style[property] = '';
  });
}

export function applyColorSchemeToDom(colorScheme, resolvedTheme) {
  if (typeof document === 'undefined') {
    return;
  }

  const root = document.documentElement;
  const body = document.body;
  const definition = getColorSchemeDefinition(colorScheme);
  const themeMode = resolvedTheme || resolveThemeMode(definition.id);

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

  Object.entries(definition.tokens || {}).forEach(([property, value]) => {
    root.style.setProperty(property, value);
  });

  Object.entries(definition.rootStyles || {}).forEach(([property, value]) => {
    root.style[property] = value;
  });

  Object.entries(definition.bodyStyles || {}).forEach(([property, value]) => {
    body.style[property] = value;
  });
}

export function bootstrapStoredColorScheme() {
  const colorScheme = getStoredColorScheme();
  const resolvedTheme = resolveThemeMode(colorScheme);
  persistColorSchemeLocally(colorScheme, resolvedTheme);
  applyColorSchemeToDom(colorScheme, resolvedTheme);
  return { colorScheme, resolvedTheme };
}
