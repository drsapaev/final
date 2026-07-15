/**
 * i18n/useTranslation.js — unified translation hook for the entire frontend.
 *
 * Re-exports react-i18next's useTranslation and augments it with project-specific
 * helpers (availableLanguages, language, setLanguage) that older code expects.
 *
 * Usage:
 *   import { useTranslation } from '../i18n/useTranslation';
 *   const { t, i18n, language, setLanguage, availableLanguages } = useTranslation();
 *   <Button>{t('common.save')}</Button>
 *   <span>{t('confirm.delete_section_message', { name: 'Гемограмма' })}</span>
 *   setLanguage('uz-Latn');
 *
 * Available languages: ru, uz-Latn, uz-Cyrl, en, kk
 * (see ./index.js for SUPPORTED_LANGUAGES)
 */

import { useTranslation as useReactI18NextTranslation } from 'react-i18next';
import i18n, { SUPPORTED_LANGUAGES, DEFAULT_LANGUAGE } from './index';

// Display metadata for each language — used by language switcher UI.
// Names match the labels used in the legacy useTranslation.jsx so existing
// tests and UI continue to work.
export const AVAILABLE_LANGUAGES = [
  { code: 'ru', name: 'Русский', flag: '🇷🇺' },
  { code: 'uz-Latn', name: "O'zbek", flag: '🇺🇿' },
  { code: 'uz-Cyrl', name: 'Ўзбекча', flag: '🇺🇿' },
  { code: 'en', name: 'English', flag: '🇬🇧' },
  { code: 'kk', name: 'Қазақ', flag: '🇰🇿' },
];

/**
 * Augmented useTranslation hook.
 *
 * Returns everything react-i18next's useTranslation returns, PLUS:
 *   - language: current language code (e.g. 'ru', 'uz-Latn')
 *   - setLanguage(code): change language (wraps i18n.changeLanguage)
 *   - availableLanguages: array of { code, name, flag } for switcher UI
 *
 * Legacy compatibility: if consumer expects `language === 'uz'` (bare code),
 * the hook also exposes `language` normalized to legacy form. BUT new code
 * should use 'uz-Latn' directly.
 */
export function useTranslation() {
  const reactI18n = useReactI18NextTranslation();

  // i18n.language is the current language code (e.g. 'ru', 'uz-Latn').
  const language = i18n.language || DEFAULT_LANGUAGE;

  // setLanguage wraps i18n.changeLanguage (async) — synchronous from caller's POV.
  const setLanguage = (code) => {
    if (SUPPORTED_LANGUAGES.includes(code)) {
      i18n.changeLanguage(code);
    }
  };

  return {
    ...reactI18n,
    t: reactI18n.t,
    i18n,
    // Augmented fields
    language,
    setLanguage,
    availableLanguages: AVAILABLE_LANGUAGES,
    // react-i18next compatibility
    ready: reactI18n.ready !== undefined ? reactI18n.ready : true,
  };
}

export default useTranslation;
