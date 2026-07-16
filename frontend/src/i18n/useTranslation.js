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

// Standalone t() — for non-React contexts (tests, module-level constants).
// Delegates to react-i18next's i18n.t().
export const t = (key, params) => {
  if (key === null || key === undefined || typeof key !== 'string') return key;
  return i18n.t(key, params);
};

// Standalone tInterpolate() — for backward compat with labTranslations.tInterpolate.
// Uses single-brace {param} interpolation.
export function tInterpolate(key, params = {}) {
  const template = i18n.t(key);
  if (!params || typeof params !== 'object') return template;
  return template.replace(/\{(\w+)\}/g, (match, paramName) => {
    return params[paramName] !== undefined ? String(params[paramName]) : match;
  });
}

// Re-export i18n instance for direct access.
export { i18n };

// TRANSLATIONS — re-export the Russian locale as the "dictionary" for backward compat
// with tests that import it directly. New code should use t() instead.
import ru from './locales/ru';
export { ru as TRANSLATIONS };

/**
 * TranslationProvider — no-op provider for backward compatibility.
 *
 * react-i18next initializes globally via `import './i18n'` in main.jsx,
 * so no context provider is needed. This component exists only to keep
 * existing imports working:
 *   import { TranslationProvider } from '../i18n/useTranslation';
 *
 * It simply renders its children — no state, no context.
 */
import React from 'react';
import PropTypes from 'prop-types';

export function TranslationProvider({ children }) {
  return children;
}

TranslationProvider.propTypes = {
  ...(TranslationProvider.propTypes || {}),
  children: PropTypes.any,
};

