/**
 * DEPRECATED: Use `../i18n/useTranslation` instead.
 *
 * This file is kept as a backward-compatibility shim so existing consumers
 * (Landing.jsx, HeaderNew.jsx, ChatButton.jsx, etc.) continue to work
 * while they are migrated to the unified i18n system.
 *
 * Migration path:
 *   - Replace:  import { useTranslation, TranslationProvider } from '../hooks/useTranslation';
 *   - With:     import { useTranslation } from '../i18n/useTranslation';
 *   - Remove TranslationProvider (react-i18next initializes globally via main.jsx)
 *
 * This shim will be removed once all consumers are migrated.
 */

// The new unified hook — powered by react-i18next.
// We don't need TranslationProvider anymore: react-i18next initializes
// globally via `import './i18n'` in main.jsx, so useTranslation works
// without a context provider.
export { useTranslation } from '../i18n/useTranslation';

// TranslationProvider is now a no-op — kept for API compatibility.
// React components that wrap children in <TranslationProvider> will still work;
// the provider just renders children directly.
import React from 'react';
import PropTypes from 'prop-types';

export function TranslationProvider({ children }) {
  return children;
}

TranslationProvider.propTypes = {
  ...(TranslationProvider.propTypes || {}),
  children: PropTypes.any,
};
