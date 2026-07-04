/**
 * formatCurrency — shared currency formatter for admin components (P2 dedup, Sprint 4).
 *
 * Replaces 2 identical copies that lived in AdminDashboard.jsx and
 * AdminFinanceOverview.jsx. Uses Intl.NumberFormat with ru-RU locale
 * and UZS currency, 0 fractional digits (matches the original behavior).
 *
 * Note: useUtils.js has a separate formatCurrency that goes through
 * formatNumber — kept as-is because it has different null-handling and
 * is consumed by hooks with different call sites.
 */
const formatter = new Intl.NumberFormat('ru-RU', {
  style: 'currency',
  currency: 'UZS',
  minimumFractionDigits: 0,
});

function formatCurrency(amount) {
  if (amount === null || amount === undefined || Number.isNaN(amount)) {
    return '';
  }
  return formatter.format(amount);
}

export default formatCurrency;
