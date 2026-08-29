/**
 * PR-UI-14-2: cashier payment history view-model — pure functions.
 *
 * Verbatim move of the client-side grouping + sorting slice from
 * src/pages/CashierPanel.tsx (main `ee87d1b3e`) — behavior-preserving
 * decomposition per the PR-UI-13 registrar pattern (13-2 precedent:
 * registrarWorklistRows). No logic changes.
 *
 * Contract (pinned by unit tests + CashierPanel.contract.test.tsx):
 *  - groupPaymentsByPatientAndTime: payments of one patient created at the
 *    same date+time collapse into one display row (server pagination makes
 *    cross-page grouping impossible — grouping is within-page only);
 *    services/services_names deduped; total_amount summed.
 *  - sortCashierPayments: presentation-only client sort by 'date' |
 *    'patient' | 'amount' with 'asc' | 'desc' direction.
 */

import { formatRegistrarDate, formatRegistrarTime, parseRegistrarTimestamp } from '../../utils/dateUtils';
import type { CashierPaymentRow } from './cashierPaymentContracts';

// ✅ ГРУППИРОВКА: Объединяем платежи одного пациента, созданных в одно время
// NOTE: Server pagination makes grouping across pages impossible.
// We only group within the current page.
export const groupPaymentsByPatientAndTime = (paymentsList: unknown): CashierPaymentRow[] => {
  if (!paymentsList) return [];

  // Convert backend specific date/time format if needed
  // The backend returns 'created_at'. We can use that.

  const grouped: Record<string, { services: unknown[]; services_names: unknown[]; service?: unknown; total_amount?: number; amount?: number; patient?: unknown; date?: string; time?: string; id?: string | number; payment_id?: string | number; method?: string; status?: string; grouped_payments: unknown[]; [k: string]: unknown }> = {};

  (paymentsList as Record<string, unknown>[]).forEach((payment) => {
    // Parse dates from backend
    const createdAt = payment.created_at as string | undefined;
    const dateObj = parseRegistrarTimestamp(createdAt);
    const dateKey = formatRegistrarDate(dateObj || createdAt);
    const timeKey = formatRegistrarTime(dateObj || createdAt);

    const groupKey = `${payment.patient_id}_${dateKey}_${timeKey}`;

    if (!grouped[groupKey]) {
      // Создаём новую группу
      grouped[groupKey] = {
        ...payment,
        services: Array.isArray(payment.services) ? [...(payment.services as unknown[])] : [],
        services_names: Array.isArray(payment.services_names) ? [...(payment.services_names as unknown[])] : [],
        grouped_payments: [payment.id],
        total_amount: Number(payment.amount || 0),
        date: dateKey, // Display helpers
        time: timeKey,
        patient: payment.patient_name,
        service: payment.service || null
      };
    } else {
      grouped[groupKey].grouped_payments.push(payment.id);
      grouped[groupKey].total_amount = Number(grouped[groupKey].total_amount || 0) + Number(payment.amount);
      if (payment.service && !grouped[groupKey].service) {
        grouped[groupKey].service = payment.service;
      }
      if (Array.isArray(payment.services)) {
        grouped[groupKey].services.push(...(payment.services as unknown[]));
      }
      if (Array.isArray(payment.services_names)) {
        grouped[groupKey].services_names.push(...(payment.services_names as unknown[]));
      }
    }
  });

  return Object.values(grouped).map((group) => ({
    ...group,
    services: Array.from(new Set(group.services.filter(Boolean))),
    services_names: Array.from(new Set(group.services_names.filter(Boolean))),
    service: group.service || group.services_names[0] || group.services[0] || null
  }));
};

// UX Audit #4.2: client-side sort по sortField/sortDir (presentation-only).
// Поддерживаемые поля: 'date' | 'patient' | 'amount'.
export type CashierSortField = 'date' | 'patient' | 'amount';
export type CashierSortDir = 'asc' | 'desc';

export const sortCashierPayments = (
  groupedPayments: CashierPaymentRow[],
  sortField: CashierSortField,
  sortDir: CashierSortDir,
): CashierPaymentRow[] =>
  [...groupedPayments].sort((a, b) => {
    let aVal: string | number, bVal: string | number;
    if (sortField === 'amount') {
      aVal = Number(a.total_amount || a.amount || 0);
      bVal = Number(b.total_amount || b.amount || 0);
    } else if (sortField === 'patient') {
      aVal = String(a.patient || '').toLowerCase();
      bVal = String(b.patient || '').toLowerCase();
    } else {
      // 'date' — sortBy date+time string
      aVal = `${a.date || ''} ${a.time || ''}`;
      bVal = `${b.date || ''} ${b.time || ''}`;
    }
    const cmp = aVal < bVal ? -1 : aVal > bVal ? 1 : 0;
    return sortDir === 'asc' ? cmp : -cmp;
  });
