/**
 * PR-UI-14-1 follow-up unit contract: cashierPaymentContracts — the pure
 * payment-contract module merged in #2914 (extracted verbatim from
 * CashierPanel.tsx).
 *
 * Provenance (#2904 → #2906 precedent): the parallel extraction PR #2913 was
 * closed unmerged as a duplicate of #2914; its 30-test contracts suite is
 * salvaged here 1:1 against the merged module (verified: zero semantic diff
 * between the two extractions) + shiftDay coverage (#2914 exports it).
 *
 * Pins the observable contracts:
 * - payment id resolution (primitive → grouped_payments[0] → id → payment_id → null)
 * - method code/label normalization (ru → canonical codes, PayMe/Click passthrough)
 * - receipt payload building (status is NEVER invented; services precedence;
 *   change_due/received_amount defaults)
 * - status meta/label maps with unknown fallback
 * - visit-id resolution precedence chain + dedup
 * - fail-closed payment-action gate (available_actions array OR can_* field,
 *   nothing else — mirrors the source-pin contract test)
 * - grouped-payment command guards (missing token / missing backend contract throw)
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';

const apiPost = vi.fn();
vi.mock('../../../api/client', () => ({
  api: { post: (...args: unknown[]) => apiPost(...args) },
}));

const getAccessToken = vi.fn();
vi.mock('../../../utils/tokenManager', () => ({
  default: { getAccessToken: () => getAccessToken() },
}));

import {
  DATE_PRESETS,
  buildPaymentMethodLabels,
  shiftDay,
  buildReceiptPrintPayload,
  buildReceiptServices,
  canCreateCashierPayment,
  canCreateDirectCashierPayment,
  createGroupedCashierPayment,
  extractReceiptDateTime,
  getLocalDateString,
  getPaymentStatusMeta,
  getPaymentStatusLabel,
  hasBackendPaymentAction,
  isBackendGroupedCashierPayment,
  resolveCashierVisitIds,
  resolvePaymentId,
  resolvePaymentMethodCode,
  resolvePaymentMethodLabel,
  resolveSingleCashierVisitId,
  type CashierPaymentRow,
} from '../cashierPaymentContracts';

const t = (key: string) => `t:${key}`;

beforeEach(() => {
  apiPost.mockReset();
  getAccessToken.mockReset();
});

describe('resolvePaymentId (PR-UI-14-1)', () => {
  it('passes primitives through', () => {
    expect(resolvePaymentId(42)).toBe(42);
    expect(resolvePaymentId('abc')).toBe('abc');
    expect(resolvePaymentId(null)).toBeNull();
    expect(resolvePaymentId(undefined)).toBeNull();
  });

  it('prefers grouped_payments[0] over row ids', () => {
    const row = { id: 1, payment_id: 2, grouped_payments: [7, 8] } as CashierPaymentRow;
    expect(resolvePaymentId(row)).toBe(7);
  });

  it('falls back id → payment_id → null', () => {
    expect(resolvePaymentId({ id: 5 } as CashierPaymentRow)).toBe(5);
    expect(resolvePaymentId({ payment_id: 'p-1' } as CashierPaymentRow)).toBe('p-1');
    expect(resolvePaymentId({} as CashierPaymentRow)).toBeNull();
  });
});

describe('payment method normalization (PR-UI-14-1)', () => {
  it('maps russian method names to canonical codes', () => {
    expect(resolvePaymentMethodCode(undefined)).toBe('cash');
    expect(resolvePaymentMethodCode('')).toBe('cash');
    expect(resolvePaymentMethodCode('Наличные')).toBe('cash');
    expect(resolvePaymentMethodCode('Карта')).toBe('card');
    expect(resolvePaymentMethodCode('PayMe')).toBe('payme');
  });

  it('resolves labels with fallback to cash', () => {
    const labels = { cash: 'Наличные', card: 'Карта' };
    expect(resolvePaymentMethodLabel('карта', labels)).toBe('Карта');
    expect(resolvePaymentMethodLabel('click', { ...labels, click: 'Click' })).toBe('Click');
    expect(resolvePaymentMethodLabel('', labels)).toBe('Наличные');
    expect(resolvePaymentMethodLabel(undefined, labels)).toBe('Наличные');
  });

  it('buildPaymentMethodLabels localizes cash/card and keeps provider brands', () => {
    const labels = buildPaymentMethodLabels(t);
    expect(labels.cash).toBe('t:cashier.method_cash');
    expect(labels.card).toBe('t:cashier.method_card');
    expect(labels.payme).toBe('PayMe');
    expect(labels.click).toBe('Click');
  });
});

describe('receipt payload building (PR-UI-14-1)', () => {
  it('extracts explicit date/time without reformatting', () => {
    expect(extractReceiptDateTime({ date: '01.02', time: '10:00' } as CashierPaymentRow))
      .toEqual({ date: '01.02', time: '10:00' });
  });

  it('derives date/time from paid_at when explicit fields absent', () => {
    const { date, time } = extractReceiptDateTime({ paid_at: '2026-08-30T10:30:00+05:00' } as CashierPaymentRow);
    expect(date).toMatch(/^\d{2}\.\d{2}\.\d{4}$/);
    expect(time).toMatch(/^\d{2}:\d{2}$/);
  });

  it('returns empty date/time for unparseable timestamps', () => {
    expect(extractReceiptDateTime({ created_at: 'not-a-date' } as CashierPaymentRow)).toEqual({ date: '', time: '' });
  });

  it('buildReceiptServices: services_names branch wraps the total per service', () => {
    const services = buildReceiptServices({ services_names: ['Консультация', 'УЗИ'] } as CashierPaymentRow, 100);
    expect(services).toEqual([
      { name: 'Консультация', quantity: 1, price: 100, total: 100, currency: 'UZS' },
      { name: 'УЗИ', quantity: 1, price: 100, total: 100, currency: 'UZS' },
    ]);
  });

  it('buildReceiptServices: object services keep own prices and quantities', () => {
    const services = buildReceiptServices({
      services: [
        { name: 'Консультация', quantity: 2, price: 50 },
        { code: 'US-01', price: 70, total: 70 },
        null,
        'plain string',
      ],
    } as unknown as CashierPaymentRow, 100);
    expect(services).toEqual([
      { name: 'Консультация', quantity: 2, price: 50, total: 100, currency: 'UZS' },
      { name: 'US-01', quantity: 1, price: 70, total: 70, currency: 'UZS' },
      { name: 'plain string', quantity: 1, price: 100, total: 100, currency: 'UZS' },
    ]);
  });

  it('buildReceiptPrintPayload never invents a paid status', () => {
    const payload = buildReceiptPrintPayload(
      { id: 9, amount: 150, status: 'pending', method: 'карта' } as CashierPaymentRow,
      { card: 'Карта', cash: 'Наличные' },
      'Пациент',
    );
    expect(payload.payment.status).toBe('pending');
    expect(payload.payment.method).toBe('card');
    expect(payload.payment.method_name).toBe('Карта');
    expect(payload.payment.total).toBe(150);
    expect(payload.payment.paid_amount).toBe(150); // received_amount defaults to total
    expect(payload.payment.change).toBe(0);
    expect(payload.patient.full_name).toBe('Пациент');
  });

  it('buildReceiptPrintPayload uses real change_due and receipt number when provided', () => {
    const payload = buildReceiptPrintPayload(
      { id: 9, amount: 100, change_due: 25, received_amount: 125, receipt_no: 'R-001' } as CashierPaymentRow,
      { cash: 'Наличные' },
      'Пациент',
    );
    expect(payload.payment.number).toBe('R-001');
    expect(payload.payment.paid_amount).toBe(125);
    expect(payload.payment.change).toBe(25);
    expect(payload.payment.method).toBe('cash');
  });

  it('buildReceiptPrintPayload falls back to PAY-<id> number and patient label', () => {
    const payload = buildReceiptPrintPayload({ payment_id: 'p7' } as CashierPaymentRow, { cash: 'x' }, 'Неизвестный пациент');
    expect(payload.payment.number).toBe('PAY-p7');
    expect(payload.patient.full_name).toBe('Неизвестный пациент');
  });
});

describe('payment status maps (PR-UI-14-1)', () => {
  it('maps known statuses to badge variants', () => {
    expect(getPaymentStatusMeta('Paid', t).variant).toBe('success');
    expect(getPaymentStatusMeta('partial', t).variant).toBe('info');
    expect(getPaymentStatusMeta('cancelled', t).variant).toBe('danger');
    expect(getPaymentStatusMeta('refunded', t).variant).toBe('danger');
    expect(getPaymentStatusMeta('pending', t).variant).toBe('warning');
  });

  it('falls back to unknown/secondary for unmapped statuses', () => {
    expect(getPaymentStatusMeta('weird', t).variant).toBe('secondary');
    expect(getPaymentStatusMeta('', t).variant).toBe('secondary');
    expect(getPaymentStatusLabel(undefined, t)).toBe('t:cashier.status_unknown');
    expect(getPaymentStatusLabel('paid', t)).toBe('t:cashier.status_paid');
  });
});

describe('visit id resolution precedence (PR-UI-14-1)', () => {
  it('prefers payment_visit_ids, dedups and drops nulls', () => {
    const appt = { payment_visit_ids: [1, null, 1, 2], payment_visit_id: 3, visit_ids: [4], visit_id: 5 };
    expect(resolveCashierVisitIds(appt as never)).toEqual([1, 2]);
  });

  it('falls back payment_visit_id → visit_ids → visit_id', () => {
    expect(resolveCashierVisitIds({ payment_visit_id: 3 } as never)).toEqual([3]);
    expect(resolveCashierVisitIds({ visit_ids: [4, 4] } as never)).toEqual([4]);
    expect(resolveCashierVisitIds({ visit_id: 5 } as never)).toEqual([5]);
    expect(resolveCashierVisitIds({} as never)).toEqual([]);
  });

  it('resolves a single visit id only when exactly one candidate exists', () => {
    expect(resolveSingleCashierVisitId({ payment_visit_id: 3 } as never)).toBe(3);
    expect(resolveSingleCashierVisitId({ visit_ids: [1, 2] } as never)).toBeNull();
    expect(resolveSingleCashierVisitId({} as never)).toBeNull();
  });
});

describe('payment availability predicates (PR-UI-14-1)', () => {
  it('grouped payment detection covers both backend contract signals', () => {
    expect(isBackendGroupedCashierPayment({ payment_contract: 'grouped_visits' } as never)).toBe(true);
    expect(isBackendGroupedCashierPayment({ can_create_grouped_payment: true } as never)).toBe(true);
    expect(isBackendGroupedCashierPayment({} as never)).toBe(false);
  });

  it('direct payment requires the explicit backend flag only', () => {
    expect(canCreateDirectCashierPayment({ can_create_direct_payment: true } as never)).toBe(true);
    expect(canCreateDirectCashierPayment({ visit_id: 1 } as never)).toBe(false);
    expect(canCreateCashierPayment({ can_create_direct_payment: true } as never)).toBe(true);
    expect(canCreateCashierPayment({ can_create_grouped_payment: true } as never)).toBe(true);
    expect(canCreateCashierPayment({} as never)).toBe(false);
  });
});

describe('hasBackendPaymentAction — fail-closed gate (PR-UI-14-1)', () => {
  it('rejects empty actions and missing rows', () => {
    expect(hasBackendPaymentAction(null, '')).toBe(false);
    expect(hasBackendPaymentAction(null, 'cancel')).toBe(false);
    expect(hasBackendPaymentAction({} as CashierPaymentRow, '')).toBe(false);
  });

  it('matches available_actions case-insensitively', () => {
    const row = { available_actions: ['Cancel', ' REFUND '] } as CashierPaymentRow;
    expect(hasBackendPaymentAction(row, 'cancel')).toBe(true);
    expect(hasBackendPaymentAction(row, 'refund')).toBe(true);
    expect(hasBackendPaymentAction(row, 'confirm')).toBe(false);
  });

  it('reads can_* fields only when the backend actually provided them', () => {
    expect(hasBackendPaymentAction({ can_cancel: true } as CashierPaymentRow, 'cancel')).toBe(true);
    expect(hasBackendPaymentAction({ can_cancel: false } as CashierPaymentRow, 'cancel')).toBe(false);
    // absent field → fail closed (hasOwnProperty guard)
    expect(hasBackendPaymentAction({} as CashierPaymentRow, 'cancel')).toBe(false);
    // unknown action name → no can-field mapping → false
    expect(hasBackendPaymentAction({ can_cancel: true } as CashierPaymentRow, 'explode')).toBe(false);
  });

  it('prefers available_actions when both signals present', () => {
    const row = { available_actions: ['cancel'], can_cancel: false } as CashierPaymentRow;
    expect(hasBackendPaymentAction(row, 'cancel')).toBe(true);
  });
});

describe('createGroupedCashierPayment guards (PR-UI-14-1)', () => {
  it('throws when the access token is missing', async () => {
    getAccessToken.mockReturnValue(null);
    await expect(createGroupedCashierPayment({} as never, { amount: 1, method: 'cash' }))
      .rejects.toThrow('Missing access token for grouped cashier payment.');
    expect(apiPost).not.toHaveBeenCalled();
  });

  it('throws when the backend did not grant the grouped contract', async () => {
    getAccessToken.mockReturnValue('token');
    await expect(
      createGroupedCashierPayment({ visit_ids: [1] } as never, { amount: 1, method: 'cash' }),
    ).rejects.toThrow('Backend did not provide a grouped cashier payment contract for this row.');
    expect(apiPost).not.toHaveBeenCalled();
  });

  it('posts the backend-owned allocation payload', async () => {
    getAccessToken.mockReturnValue('token');
    apiPost.mockResolvedValue({ data: { ok: true } });
    const result = await createGroupedCashierPayment(
      { patient_id: 7, visit_ids: [1, 2], can_create_grouped_payment: true } as never,
      { amount: 100, method: 'card', note: 'n' },
    );
    expect(result).toEqual({ ok: true });
    expect(apiPost).toHaveBeenCalledWith('/cashier/payments/grouped', {
      patient_id: 7,
      visit_ids: [1, 2],
      amount: 100,
      method: 'card',
      note: 'n',
    });
  });
});

describe('date helpers (PR-UI-14-1)', () => {
  it('getLocalDateString formats YYYY-MM-DD in local time', () => {
    expect(getLocalDateString(new Date(2026, 7, 5))).toBe('2026-08-05');
  });

  it('shiftDay shifts the local date by N days', () => {
    expect(shiftDay(-1)).toBe(getLocalDateString(new Date(Date.now() - 24 * 60 * 60 * 1000)));
    expect(shiftDay(0)).toBe(getLocalDateString());
  });

  it('DATE_PRESETS expose 4 stable ids with coherent ranges', () => {
    expect(DATE_PRESETS.map((p) => p.id)).toEqual(['today', 'yesterday', 'week', 'month']);
    const today = getLocalDateString();
    expect(DATE_PRESETS[0].getRange()).toEqual({ from: today, to: today });
    expect(DATE_PRESETS[1].getRange().to).not.toBe(today); // yesterday
    expect(DATE_PRESETS[2].getRange().to).toBe(today);     // week ends today
  });
});
