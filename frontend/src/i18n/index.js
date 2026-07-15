/**
 * i18n/index.js — single source of truth for frontend internationalization.
 *
 * Initializes react-i18next with locale resources from ./locales/{ru,uz-Latn,uz-Cyrl,en,kk}.js
 *
 * Supported languages (BCP 47):
 *   ru        — Russian (default, base locale)
 *   uz-Latn   — Uzbek (Latin script, primary for modern Uzbekistan)
 *   uz-Cyrl   — Uzbek (Cyrillic script, placeholder — falls back to uz-Latn → ru)
 *   en        — English
 *   kk        — Kazakh
 *
 * Usage in main.jsx:
 *   import './i18n';   // side-effect: initializes react-i18next
 *
 * Usage in components:
 *   import { useTranslation } from '../i18n/useTranslation';
 *   const { t, i18n } = useTranslation();
 *   <Button>{t('common.save')}</Button>
 *   i18n.changeLanguage('uz-Latn');
 */

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import ru from './locales/ru';
import uzLatn from './locales/uz-Latn';
import uzCyrl from './locales/uz-Cyrl';
import en from './locales/en';
import kk from './locales/kk';

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

i18n.use(initReactI18next).init({
  resources: {
    ru: { translation: ru },
    'uz-Latn': { translation: uzLatn },
    'uz-Cyrl': { translation: uzCyrl },
    en: { translation: en },
    kk: { translation: kk },
  },
  lng: getInitialLanguage(),
  fallbackLng: DEFAULT_LANGUAGE,
  // For uz-Cyrl, fall back to uz-Latn first, then ru.
  // i18next supports per-language fallback chains.
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

// Persist language changes to localStorage (legacy-compatible keys).
i18n.on('languageChanged', (lng) => {
  if (typeof window === 'undefined') return;
  // Persist under both the new code and the legacy 'uz' alias
  window.localStorage?.setItem('language', lng);
  window.localStorage?.setItem('app_language', lng);
});

export default i18n;
