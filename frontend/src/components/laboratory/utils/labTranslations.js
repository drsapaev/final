/**
 * DEPRECATED: Use `../i18n/useTranslation` and `../i18n` instead.
 *
 * This file is kept as a backward-compatibility shim so existing lab module
 * consumers (LabQueueWorkbench, ReportEditor, etc.) continue to work
 * while they are migrated to the unified i18n system.
 *
 * Migration path:
 *   - Replace:  import { t, tInterpolate, TRANSLATIONS, i18n } from './utils/labTranslations';
 *   - With:     import { useTranslation } from '../i18n/useTranslation';
 *               const { t, i18n } = useTranslation();
 *   - For non-React contexts: import i18n from '../i18n'; i18n.t('key');
 *
 * This shim will be removed once all lab consumers are migrated.
 */

import i18n from '../../../i18n';

// Re-export the i18n instance (react-i18next) for backward compat.
export { i18n };

// Standalone t() — delegates to react-i18next's fixed-language t.
// Works for non-React contexts (PropTypes defaults, module-level constants).
// Preserves legacy behavior: null/undefined/non-string input returned as-is.
export function t(key) {
  if (key === null || key === undefined || typeof key !== 'string') return key;
  return i18n.t(key);
}

// tInterpolate — substitutes {param} placeholders in the translated string.
// NOTE: react-i18next uses {{param}} (double braces) by default, but our
// locale files use {param} (single brace) for backward compat with the
// old labTranslations.tInterpolate. We do manual substitution to preserve
// the single-brace contract.
export function tInterpolate(key, params = {}) {
  const template = i18n.t(key);
  if (!params || typeof params !== 'object') return template;
  return template.replace(/\{(\w+)\}/g, (match, paramName) => {
    return params[paramName] !== undefined ? String(params[paramName]) : match;
  });
}

// TRANSLATIONS — re-export the Russian locale as the "dictionary" for tests
// that import it directly. New code should not use this; use t() instead.
import ru from '../../../i18n/locales/ru';
export { ru as TRANSLATIONS };
