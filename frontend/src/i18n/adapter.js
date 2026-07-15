/**
 * STRAT#29: i18n adapter — lightweight useTranslation hook compatible with
 * react-i18next API, backed by labTranslations.js dictionary.
 *
 * react-i18next НЕ установлен в проекте. Этот модуль предоставляет
 * совместимый API (useTranslation().t), чтобы другие модули могли
 * начать миграцию на translation pattern без новой зависимости.
 *
 * Когда react-i18next будет установлен, этот файл заменяется на:
 *   import { useTranslation } from 'react-i18next';
 *   export { useTranslation };
 * — все call sites продолжат работать без изменений.
 *
 * Current implementation:
 *   - t(key) — возвращает перевод из labTranslations TRANSLATIONS dictionary
 *   - tInterpolate(key, params) — подстановка {param} плейсхолдеров
 *   - i18n.language — всегда 'ru' (пока нет locale switcher)
 *   - i18n.changeLanguage(lang) — no-op (заглушка для будущего locale switcher)
 *
 * Usage:
 *   import { useTranslation } from '../../i18n/adapter';
 *   const { t } = useTranslation();
 *   <Button>{t('common.save')}</Button>
 */

import { t, tInterpolate, TRANSLATIONS } from '../components/laboratory/utils/labTranslations';

// Stub i18n object — compatible with react-i18next's i18n interface.
// When react-i18next is adopted, this is replaced by the real i18n instance.
const i18n = {
  language: 'ru',
  languages: ['ru'],
  changeLanguage: async (lang) => {
    // STRAT#31: when locale switcher is added, this will dispatch
    // a language change event that updates the TRANSLATIONS dictionary.
    // For now, it's a no-op — only Russian is supported.
    if (typeof window !== 'undefined' && window.console) {
      // eslint-disable-next-line no-console
      console.warn('[i18n] changeLanguage is a no-op — only "ru" is supported');
    }
    return lang;
  },
  exists: (key) => {
    const parts = key.split('.');
    let current = TRANSLATIONS;
    for (const part of parts) {
      if (current && typeof current === 'object' && part in current) {
        current = current[part];
      } else {
        return false;
      }
    }
    return typeof current === 'string';
  },
  t: (key, params) => {
    if (params) return tInterpolate(key, params);
    return t(key);
  },
};

/**
 * useTranslation — React hook compatible with react-i18next.
 *
 * Returns { t, i18n } where:
 *   - t(key, params?) — translation function with optional interpolation
 *   - i18n — i18n instance (language, changeLanguage, exists)
 *
 * When react-i18next is installed, replace this file with:
 *   export { useTranslation } from 'react-i18next';
 */
export function useTranslation() {
  const tFunc = (key, params) => {
    if (params) return tInterpolate(key, params);
    return t(key);
  };

  return {
    t: tFunc,
    i18n,
    // react-i18next compatibility: ready flag
    ready: true,
  };
}

// Export raw t and tInterpolate for non-hook contexts (module-level constants,
// PropTypes defaults, etc.)
export { t, tInterpolate };

// Export i18n instance for app-level configuration
export { i18n };
