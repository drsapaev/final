/**
 * DEPRECATED: Use `../i18n/useTranslation` and the unified locale files instead.
 *
 * This file is kept as a backward-compatibility shim so existing consumers
 * (RegistrarPanel.jsx and related) continue to work while they are migrated.
 *
 * Migration path:
 *   - Replace:  import { getRegistrarTranslator } from './registrarTranslations';
 *               const t = getRegistrarTranslator(language);
 *               t('welcome');
 *   - With:     import { useTranslation } from '../i18n/useTranslation';
 *               const { t } = useTranslation();
 *               t('registrarPanel.welcome');
 *
 * This shim will be removed once all registrar consumers are migrated.
 */

import i18n from '../i18n';

/**
 * Returns a translator function for the given language.
 * Falls back to Russian, then to the key itself.
 *
 * @param {'ru'|'uz'|'en'|'kk'} language - UI language code (legacy: 'uz' maps to 'uz-Latn')
 * @returns {(key: string) => string} translator function
 */
export const getRegistrarTranslator = (language) => (key) => {
  // Map legacy 'uz' → 'uz-Latn' for the unified i18n system.
  const lang = language === 'uz' ? 'uz-Latn' : language;
  // Use react-i18next's fixed-t with namespace prefix.
  // The registrarPanel namespace is in the unified locale files.
  return i18n.getFixedT(lang)('registrarPanel.' + key);
};

export default {
  ru: 'see ../i18n/locales/ru.js → registrarPanel namespace',
  uz: 'see ../i18n/locales/uz-Latn.js → registrarPanel namespace',
  en: 'see ../i18n/locales/en.js → registrarPanel namespace',
};
