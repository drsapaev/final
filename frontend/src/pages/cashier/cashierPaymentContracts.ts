/**
 * PR-UI-14-1: cashier payment contracts & pure helpers.
 *
 * Verbatim move from src/pages/CashierPanel.tsx (module scope, lines 62-412
 * at main `d5b339309`) — behavior-preserving decomposition per PR-UI-13
 * registrar pattern. No logic changes; declarations gained `export`.
 *
 * Ownership map:
 *  - date presets (shift/DATE_PRESETS) — filter-layer pure helpers
 *  - payment method/status presentation (labels, meta, status label)
 *  - receipt print payload builders (resolvePaymentId/extract/build*)
 *  - backend payment contract guards (fail-closed hasBackendPaymentAction,
 *    grouped-payment allocation via /cashier/payments/grouped)
 */

import { api } from '../../api/client';  // PR-53: replace raw fetch with axios
import type { Appointment } from '../../types/domain/clinic';
import tokenManager from '../../utils/tokenManager';
import { formatRegistrarDate, formatRegistrarTime, parseRegistrarTimestamp } from '../../utils/dateUtils';

// Функция для получения даты в формате YYYY-MM-DD
export const getLocalDateString = (date = new Date()) => {
  const d = new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

// STRAT#31 i18n: minimal translation fn signature accepted by the helpers below.
// The real `t` from useTranslation accepts (key, params?) and returns string;
// this loose signature keeps the helpers decoupled from the i18n adapter.
export type CashierTranslationFn = (key: string, params?: Record<string, unknown>) => string;

// Shape of a payment row surfaced by the cashier/payments endpoints.
// All fields are optional because the backend returns different shapes for
// grouped vs. direct payments, and the panel must tolerate both.
export interface CashierPaymentRow {
  id?: string | number;
  payment_id?: string | number;
  grouped_payments?: unknown[];
  paid_at?: string;
  created_at?: string;
  date?: string;
  time?: string;
  currency?: string;
  services_names?: unknown[];
  services?: unknown[];
  service?: unknown;
  total_amount?: number | string;
  amount?: number | string;
  method?: string;
  change_due?: number;
  change?: number;
  received_amount?: number;
  receipt_no?: string;
  status?: string;
  patient?: unknown;
  patient_name?: unknown;
  patient_phone?: string;
  patient_id?: string | number;
  refunded_amount?: number;
  available_actions?: unknown[];
  can_cancel?: boolean;
  can_refund?: boolean;
  can_print_receipt?: boolean;
  can_confirm?: boolean;
  [key: string]: unknown;
}

// A payment identifier may be passed either as a primitive or as the row object.
// `null` / `undefined` are permitted so helpers can be called from optional chains.
export type CashierPaymentRowOrId = string | number | CashierPaymentRow | null | undefined;

// Payment payload sent from PaymentWidget/CashPaymentModal to the panel handlers.
export interface CashierPaymentData {
  amount: number | string;
  method: string;
  note?: string;
}

// UX Audit #1.4: Quick date presets for typical financial reporting ranges.
// Replaces single "Сегодня" button with a 4-option segmented control.
// Saves cashier clicks when reconciling shifts (typical: «Вчера» / «Неделя»).
export const shiftDay = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return getLocalDateString(d);
};

// STRAT#31 i18n: DATE_PRESETS uses stable `id` for option value matching.
// The user-visible label is computed inside the component via tI18n('cashier.range_<id>').
export const DATE_PRESETS = [
  { id: 'today',   getRange: () => ({ from: getLocalDateString(), to: getLocalDateString() }) },
  { id: 'yesterday', getRange: () => ({ from: shiftDay(-1), to: shiftDay(-1) }) },
  { id: 'week',    getRange: () => ({ from: shiftDay(-6), to: getLocalDateString() }) },
  { id: 'month',   getRange: () => ({ from: shiftDay(-29), to: getLocalDateString() }) },
];

// Вспомогательная функция для создания прозрачного цвета была удалена (MEDIUM #14 dead code cleanup)
// STRAT#31 i18n: PAYMENT_METHOD_LABELS converted to a factory that takes `t` (the unified
// useTranslation t function) so that cash/card labels are reactive to language changes.
export const buildPaymentMethodLabels = (t: CashierTranslationFn) => ({
  cash: t('cashier.method_cash'),
  card: t('cashier.method_card'),
  payme: 'PayMe',
  click: 'Click',
});

export const resolvePaymentId = (paymentRowOrId: CashierPaymentRowOrId): string | number | null => {
  if (typeof paymentRowOrId === 'number' || typeof paymentRowOrId === 'string') {
    return paymentRowOrId;
  }

  const fromArray = paymentRowOrId?.grouped_payments?.[0];
  if (typeof fromArray === 'string' || typeof fromArray === 'number') {
    return fromArray;
  }

  return (
    paymentRowOrId?.id ||
    paymentRowOrId?.payment_id ||
    null
  );
};

export const resolvePaymentMethodCode = (method: string | undefined) => {
  const normalizedMethod = String(method || '').trim().toLowerCase();

  if (!normalizedMethod) return 'cash';
  if (normalizedMethod === 'наличные') return 'cash';
  if (normalizedMethod === 'карта') return 'card';

  return normalizedMethod;
};

export const resolvePaymentMethodLabel = (method: unknown, labels: Record<string, string>): string => {
  const methodCode = resolvePaymentMethodCode(String(method ?? ''));
  return labels[methodCode] || String(method || labels.cash);
};

export const extractReceiptDateTime = (paymentRow: CashierPaymentRow | null | undefined) => {
  const sourceTimestamp = paymentRow?.paid_at || paymentRow?.created_at || null;
  const parsedDate = sourceTimestamp ? parseRegistrarTimestamp(sourceTimestamp) : null;
  const hasValidDate = parsedDate && !Number.isNaN(parsedDate.getTime());

  return {
    date: paymentRow?.date || (hasValidDate ? formatRegistrarDate(parsedDate) : ''),
    time: paymentRow?.time || (
      hasValidDate
        ? formatRegistrarTime(parsedDate)
        : ''
    )
  };
};

export const buildReceiptServices = (
  paymentRow: CashierPaymentRow | null | undefined,
  totalAmount: number
): Array<{ name: string; quantity: number; price: number; total: number; currency: string }> => {
  const currency = String(paymentRow?.currency || 'UZS');
  const namedServices = Array.isArray(paymentRow?.services_names) ? paymentRow.services_names : [];

  if (namedServices.length > 0) {
    return namedServices
      .filter(Boolean)
      .map((serviceName: unknown) => ({
      name: String(serviceName ?? ''),
      quantity: 1,
      price: totalAmount,
      total: totalAmount,
      currency
      }));
  }

  if (Array.isArray(paymentRow?.services) && paymentRow.services.length > 0) {
    return paymentRow.services.flatMap((serviceItem: unknown) => {
      if (typeof serviceItem === 'object' && serviceItem !== null) {
        const svc = serviceItem as { name?: string; code?: string; quantity?: number; price?: number; total?: number; currency?: string };
        const displayName = svc.name || svc.code || null;
        if (!displayName) {
          return [];
        }
        const quantity = Number(svc.quantity || 1);
        const price = Number(svc.price || totalAmount);
        return {
          name: displayName,
          quantity,
          price,
          total: Number(svc.total || price * quantity),
          currency: svc.currency || currency
        };
      }

      if (!serviceItem) {
        return [];
      }

      return {
        name: String(serviceItem),
        quantity: 1,
        price: totalAmount,
        total: totalAmount,
        currency
      };
    });
  }

  return [];
};

export const buildReceiptPrintPayload = (
  paymentRow: CashierPaymentRow | null | undefined,
  labels: Record<string, string>,
  defaultPatientLabel: string
) => {
  const paymentId = resolvePaymentId(paymentRow);
  const totalAmount = Number(paymentRow?.total_amount || paymentRow?.amount || 0);
  const services = buildReceiptServices(paymentRow, totalAmount);
  const { date, time } = extractReceiptDateTime(paymentRow);
  const methodCode = resolvePaymentMethodCode(paymentRow?.method);
  // HIGH #9 fix: use real change_due if provided by CashPaymentModal, otherwise 0.
  const changeDue = Number(paymentRow?.change_due || paymentRow?.change || 0);
  const receivedAmount = Number(paymentRow?.received_amount || totalAmount);

  return {
    payment: {
      number: paymentRow?.receipt_no || `PAY-${paymentId}`,
      date,
      time,
      services,
      subtotal: totalAmount,
      discount: 0,
      total: totalAmount,
      method: methodCode,
      method_name: resolvePaymentMethodLabel(paymentRow?.method, labels),
      status: paymentRow?.status ?? null,
      paid_amount: receivedAmount,
      change: changeDue
    },
    patient: {
      full_name: paymentRow?.patient || paymentRow?.patient_name || defaultPatientLabel,
      phone: paymentRow?.patient_phone || null
    },
    services,
    clinic: null
  };
};

export const getPaymentStatusMeta = (status: unknown, t: CashierTranslationFn) => {
  const normalizedStatus = String(status || '').trim().toLowerCase();
  const statusMap = {
    paid: { variant: 'success', ariaLabel: t('cashier.status_paid_aria') },
    partial: { variant: 'info', ariaLabel: t('cashier.status_partial_aria') },
    cancelled: { variant: 'danger', ariaLabel: t('cashier.status_cancelled_aria') },
    refunded: { variant: 'danger', ariaLabel: t('cashier.status_refunded_aria') },
    pending: { variant: 'warning', ariaLabel: t('cashier.status_pending_aria') },
    unknown: { variant: 'secondary', ariaLabel: t('cashier.status_unknown_aria') },
  };

  return statusMap[normalizedStatus as keyof typeof statusMap] || statusMap.unknown;
};

export const getPaymentStatusLabel = (status: unknown, t: CashierTranslationFn): string => {
  const normalizedStatus = String(status || '').trim().toLowerCase();
  const statusMap = {
    paid: t('cashier.status_paid'),
    partial: t('cashier.status_partial'),
    cancelled: t('cashier.status_cancelled'),
    refunded: t('cashier.status_refunded'),
    pending: t('cashier.status_pending'),
    unknown: t('cashier.status_unknown'),
  };

  return statusMap[normalizedStatus as keyof typeof statusMap] || statusMap.unknown;
};

// P-018 fix: getPaymentActionContext / getAppointmentPaymentActionContext helpers
// were removed — they leaked patient names (PHI) into aria-labels, and after
// localization all action buttons now use static Russian aria-labels instead.

export const resolveCashierVisitIds = (appointment: Appointment) => {
  const paymentVisitIds = Array.isArray(appointment?.payment_visit_ids)
    ? appointment.payment_visit_ids.filter((visitId) => visitId !== null && visitId !== undefined)
    : [];

  if (paymentVisitIds.length > 0) {
    return [...new Set(paymentVisitIds)];
  }

  if (appointment?.payment_visit_id !== null && appointment?.payment_visit_id !== undefined) {
    return [appointment.payment_visit_id];
  }

  const groupedVisitIds = Array.isArray(appointment?.visit_ids)
    ? appointment.visit_ids.filter((visitId) => visitId !== null && visitId !== undefined)
    : [];

  if (groupedVisitIds.length > 0) {
    return [...new Set(groupedVisitIds)];
  }

  return appointment?.visit_id !== null && appointment?.visit_id !== undefined
    ? [appointment.visit_id]
    : [];
};

export const resolveSingleCashierVisitId = (appointment: Appointment) => {
  const visitIds = resolveCashierVisitIds(appointment);
  return visitIds.length === 1 ? visitIds[0] : null;
};

export const isBackendGroupedCashierPayment = (appointment: Appointment) =>
  appointment?.payment_contract === 'grouped_visits' ||
  appointment?.can_create_grouped_payment === true;

export const canCreateDirectCashierPayment = (appointment: Appointment) => {
  return appointment?.can_create_direct_payment === true;
};

export const canCreateCashierPayment = (appointment: Appointment) =>
  canCreateDirectCashierPayment(appointment) || appointment?.can_create_grouped_payment === true;

export const createGroupedCashierPayment = async (appointment: Appointment, paymentData: CashierPaymentData) => {
  // PR-53: migrated from raw fetch() to axios client
  const token = tokenManager.getAccessToken();
  if (!token) {
    throw new Error('Missing access token for grouped cashier payment.');
  }

  const visitIds = resolveCashierVisitIds(appointment);
  if (visitIds.length === 0 || appointment?.can_create_grouped_payment !== true) {
    throw new Error('Backend did not provide a grouped cashier payment contract for this row.');
  }

  const response = await api.post('/cashier/payments/grouped', {
    patient_id: appointment?.patient_id ?? null,
    visit_ids: visitIds,
    amount: paymentData.amount,
    method: paymentData.method,
    note: paymentData.note || 'Grouped cashier payment'
  }) as import('axios').AxiosResponse<Record<string, unknown>>;

  return response.data;
};

export const PAYMENT_ACTION_CAN_FIELD = {
  cancel: 'can_cancel',
  refund: 'can_refund',
  print_receipt: 'can_print_receipt',
  confirm: 'can_confirm'
};

export const hasBackendPaymentAction = (paymentRow: CashierPaymentRow | null | undefined, action: string): boolean => {
  const normalizedAction = String(action || '').trim().toLowerCase();
  if (!normalizedAction) {
    return false;
  }

  if (Array.isArray(paymentRow?.available_actions)) {
    return paymentRow.available_actions.some(
      (availableAction: unknown) => String(availableAction || '').trim().toLowerCase() === normalizedAction
    );
  }

  const canField = PAYMENT_ACTION_CAN_FIELD[normalizedAction as keyof typeof PAYMENT_ACTION_CAN_FIELD];
  if (canField && paymentRow && Object.prototype.hasOwnProperty.call(paymentRow, canField)) {
    return Boolean(paymentRow[canField]);
  }

  return false;
};
