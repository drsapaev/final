/**
 * i18n/index.ts — single source of truth for frontend internationalization.
 *
 * Bundles Russian as the fallback and loads other locale resources on demand.
 *
 * Supported languages (BCP 47):
 *   ru        — Russian (default, base locale)
 *   uz-Latn   — Uzbek (Latin script, primary for modern Uzbekistan)
 *   uz-Cyrl   — Uzbek (Cyrillic script, placeholder — falls back to uz-Latn → ru)
 *   en        — English
 *   kk        — Kazakh
 *
 * Usage in main.tsx (after extracting activation credentials from the URL):
 *   await loadPersistedLanguage();
 *
 * Usage in components:
 *   import { useTranslation } from '../i18n/useTranslation';
 *   const { t, i18n } = useTranslation();
 *   <Button>{t('common.save')}</Button>
 *   i18n.changeLanguage('uz-Latn');
 */

import i18n from 'i18next';
import type { BackendModule } from 'i18next';
import { initReactI18next } from 'react-i18next';
import ru from './locales/ru';

export const SUPPORTED_LANGUAGES = ['ru', 'uz-Latn', 'uz-Cyrl', 'en', 'kk'];
export const DEFAULT_LANGUAGE = 'ru';

/**
 * Read the initial language from localStorage. Accepts legacy keys
 * ('language', 'app_language') and legacy codes ('uz' → 'uz-Latn').
 */
function getInitialLanguage() {
  if (typeof window === 'undefined') return DEFAULT_LANGUAGE;
  const saved =
    window.localStorage?.getItem('language') ||
    window.localStorage?.getItem('app_language') ||
    null;
  if (!saved) return DEFAULT_LANGUAGE;
  // Legacy compatibility: bare 'uz' → 'uz-Latn'
  if (saved === 'uz') return 'uz-Latn';
  if (SUPPORTED_LANGUAGES.includes(saved)) return saved;
  return DEFAULT_LANGUAGE;
}

// Capture this before Russian initialization can emit languageChanged. Importing
// this module must not request a locale chunk: the activation URL is scrubbed in
// main.tsx before loadPersistedLanguage() starts any dynamic import.
const initialLanguage = getInitialLanguage();

const lazyLocales: Record<string, () => Promise<{ default: Record<string, unknown> }>> = {
  'uz-Latn': () => import('./locales/uz-Latn'),
  'uz-Cyrl': () => import('./locales/uz-Cyrl'),
  en: () => import('./locales/en'),
  kk: () => import('./locales/kk'),
};

const localeBackend: BackendModule = {
  type: 'backend',
  init() {},
  read(language, namespace, callback) {
    const load = namespace === 'translation' ? lazyLocales[language] : undefined;
    if (!load) {
      callback(new Error(`Unsupported locale resource: ${language}/${namespace}`), null);
      return;
    }
    void load().then(
      ({ default: translations }) => callback(null, translations),
      (error: unknown) => callback(error instanceof Error ? error : new Error('Locale load failed'), null),
    );
  },
};

const initialization = i18n.use(localeBackend).use(initReactI18next).init({
  resources: {
    ru: { translation: ru },
  },
  partialBundledLanguages: true,
  initAsync: false,
  maxRetries: 0,
  lng: DEFAULT_LANGUAGE,
  supportedLngs: SUPPORTED_LANGUAGES,
  load: 'currentOnly',
  fallbackLng: DEFAULT_LANGUAGE,
  ns: ['translation'],
  fallbackNS: 'translation',
  defaultNS: 'translation',
  interpolation: {
    escapeValue: false, // React already escapes by default
    // Use single-brace {param} interpolation (NOT the react-i18next default {{param}})
    // to match the existing locale files migrated from labTranslations.tInterpolate.
    prefix: '{',
    suffix: '}',
  },
  react: {
    useSuspense: false,
  },
  returnEmptyString: false, // empty string → fall back to key
  // Save language changes to localStorage
  saveMissing: false,
});

function persistLanguage(language: string) {
  if (typeof window === 'undefined') return;
  window.localStorage?.setItem('language', language);
  window.localStorage?.setItem('app_language', language);
}

let startupLanguageResolved = false;

// Keep direct changeLanguage() callers working, including after a chunk fails.
i18n.on('languageChanged', (lng) => {
  if (!startupLanguageResolved) return;
  if (lng !== DEFAULT_LANGUAGE && !i18n.hasResourceBundle(lng, 'translation')) {
    void i18n.changeLanguage(DEFAULT_LANGUAGE);
    return;
  }
  persistLanguage(lng);
});

/** Resolve the saved language before React mounts, or render in Russian. */
export async function loadPersistedLanguage(): Promise<void> {
  try {
    await initialization;
    if (initialLanguage !== DEFAULT_LANGUAGE) {
      await i18n.changeLanguage(initialLanguage);
      if (!i18n.hasResourceBundle(initialLanguage, 'translation')) {
        await i18n.changeLanguage(DEFAULT_LANGUAGE);
      }
    }
  } catch {
    await i18n.changeLanguage(DEFAULT_LANGUAGE);
  } finally {
    startupLanguageResolved = true;
    if (initialLanguage !== DEFAULT_LANGUAGE) persistLanguage(i18n.language);
  }
}

export default i18n;
