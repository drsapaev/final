/**
 * formatCurrency — shared currency formatter for admin components (P2 dedup, Sprint 4).
 *
 * Replaces 2 identical copies that lived in AdminDashboard.jsx and
 * AdminFinanceOverview.jsx. Uses Intl.NumberFormat with locale-aware formatting
 * and UZS currency, 0 fractional digits (matches the original behavior).
 *
 * PR-40 / High-20: Locale is now dynamic via getLocale() from dateUtils.
 * Previously hardcoded 'ru-RU' — ignored the user's language selection.
 *
 * Note: useUtils.js has a separate formatCurrency that goes through
 * formatNumber — kept as-is because it has different null-handling and
 * is consumed by hooks with different call sites.
 */
import { getLocale } from './dateUtils';

// PR-40 / High-20: cache formatters per-locale to avoid re-creating on every call
const _formatterCache = new Map();

function getFormatter(locale) {
  if (!_formatterCache.has(locale)) {
    _formatterCache.set(locale, new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'UZS',
      minimumFractionDigits: 0,
    }));
  }
  return _formatterCache.get(locale);
}

function formatCurrency(amount) {
  if (amount === null || amount === undefined || Number.isNaN(amount)) {
    return '';
  }
  return getFormatter(getLocale()).format(amount);
}

export default formatCurrency;
