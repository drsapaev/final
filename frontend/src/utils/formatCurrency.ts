// src/utils/formatCurrency.ts
// Phase 1 — migrated from .js. Pure formatter; types added.

import { getLocale } from './dateUtils';

// Cache formatters per-locale to avoid re-creating on every call.
const _formatterCache = new Map<string, Intl.NumberFormat>();

function getFormatter(locale: string): Intl.NumberFormat {
  if (!_formatterCache.has(locale)) {
    _formatterCache.set(
      locale,
      new Intl.NumberFormat(locale, {
        style: 'currency',
        currency: 'UZS',
        minimumFractionDigits: 0,
      }),
    );
  }
  // Map.has() above guarantees the key exists; non-null assertion is safe.
  return _formatterCache.get(locale)!;
}

export function formatCurrency(amount: number | null | undefined | string): string {
  if (amount === null || amount === undefined || Number.isNaN(Number(amount))) {
    return '';
  }
  return getFormatter(getLocale()).format(Number(amount));
}

export default formatCurrency;

/**
 * formatUZS — UX Audit #2.3 — единый форматтер для cashier-панели.
 * Суффикс «сум» для консистентности.
 */
export function formatUZS(amount: number | null | undefined | string): string {
  if (amount === null || amount === undefined || Number.isNaN(Number(amount))) {
    return '0 сум';
  }
  return new Intl.NumberFormat('ru-RU').format(Number(amount)) + ' сум';
}
