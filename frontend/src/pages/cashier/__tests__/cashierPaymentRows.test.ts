/**
 * PR-UI-14-2 unit contract: cashierPaymentRows — the payment history
 * view-model (grouping + presentation-only sort) moved verbatim from
 * CashierPanel.
 *
 * Pins the externally observable semantics:
 *  - same patient + same date/time → one display row; total_amount summed;
 *    grouped_payments collects member ids; services/services_names deduped
 *  - grouping is within-page only (input passthrough order preserved)
 *  - falsy input returns []
 *  - sort by amount (numeric, total_amount ?? amount ?? 0)
 *  - sort by patient (case-insensitive)
 *  - sort by date (date+time string), desc default direction
 *  - sortCashierPayments does not mutate the input array
 */
import { describe, expect, it } from 'vitest';

import {
  groupPaymentsByPatientAndTime,
  sortCashierPayments,
} from '../cashierPaymentRows';
import type { CashierPaymentRow } from '../cashierPaymentContracts';

const payment = (overrides: Record<string, unknown>): Record<string, unknown> => ({
  created_at: '2026-08-30T10:00:00',
  ...overrides,
});

describe('groupPaymentsByPatientAndTime (PR-UI-14-2)', () => {
  it('returns [] for falsy input', () => {
    expect(groupPaymentsByPatientAndTime(null)).toEqual([]);
    expect(groupPaymentsByPatientAndTime(undefined)).toEqual([]);
  });

  it('merges same patient + same date/time into one row with summed amount and member ids', () => {
    const rows = groupPaymentsByPatientAndTime([
      payment({ id: 1, patient_id: 7, patient_name: 'Иванов Иван', amount: 100, services: ['A'], services_names: ['Консультация'] }),
      payment({ id: 2, patient_id: 7, patient_name: 'Иванов Иван', amount: 50, services: ['B'], services_names: ['УЗИ'] }),
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0].total_amount).toBe(150);
    expect(rows[0].grouped_payments).toEqual([1, 2]);
    expect(rows[0].services).toEqual(['A', 'B']);
    expect(rows[0].services_names).toEqual(['Консультация', 'УЗИ']);
    expect(rows[0].patient).toBe('Иванов Иван');
  });

  it('keeps different patients / different times as separate rows', () => {
    const rows = groupPaymentsByPatientAndTime([
      payment({ id: 1, patient_id: 7, patient_name: 'A', amount: 10 }),
      payment({ id: 2, patient_id: 8, patient_name: 'B', amount: 20 }),
      payment({ id: 3, patient_id: 7, patient_name: 'A', amount: 30, created_at: '2026-08-30T12:30:00' }),
    ]);
    expect(rows).toHaveLength(3);
  });

  it('dedupes services/services_names and falls back to first name for service', () => {
    const rows = groupPaymentsByPatientAndTime([
      payment({ id: 1, patient_id: 9, amount: 5, services: ['A', 'A'], services_names: ['X', 'X'] }),
      payment({ id: 2, patient_id: 9, amount: 5, services: ['A'], services_names: ['X'] }),
    ]);
    expect(rows).toHaveLength(1);
    expect(rows[0].services).toEqual(['A']);
    expect(rows[0].services_names).toEqual(['X']);
    expect(rows[0].service).toBe('X');
  });

  it('service falls back through service → services_names[0] → services[0] → null', () => {
    const withDirect = groupPaymentsByPatientAndTime([
      payment({ id: 1, patient_id: 1, amount: 1, service: 'direct', services_names: ['N'], services: ['S'] }),
    ]);
    expect(withDirect[0].service).toBe('direct');

    const viaName = groupPaymentsByPatientAndTime([
      payment({ id: 1, patient_id: 2, amount: 1, services_names: ['N2'], services: ['S2'] }),
    ]);
    expect(viaName[0].service).toBe('N2');

    const viaService = groupPaymentsByPatientAndTime([
      payment({ id: 1, patient_id: 3, amount: 1, services: ['S3'] }),
    ]);
    expect(viaService[0].service).toBe('S3');

    const none = groupPaymentsByPatientAndTime([
      payment({ id: 1, patient_id: 4, amount: 1 }),
    ]);
    expect(none[0].service).toBeNull();
  });
});

describe('sortCashierPayments (PR-UI-14-2)', () => {
  const base = (overrides: Record<string, unknown>): CashierPaymentRow =>
    ({ id: 1, amount: 0, ...overrides }) as CashierPaymentRow;

  it('sorts by amount numerically (asc)', () => {
    const rows = [base({ total_amount: 300 }), base({ total_amount: 100 }), base({ total_amount: 200 })];
    const sorted = sortCashierPayments(rows, 'amount', 'asc');
    expect(sorted.map((r) => r.total_amount)).toEqual([100, 200, 300]);
  });

  it('sorts by amount desc and treats missing total_amount as amount then 0', () => {
    const rows = [
      base({ amount: 50, total_amount: undefined }),
      base({ amount: 0, total_amount: undefined }),
      base({ amount: 0, total_amount: 500 }),
    ];
    const sorted = sortCashierPayments(rows, 'amount', 'desc');
    expect(sorted.map((r) => Number(r.total_amount || r.amount || 0))).toEqual([500, 50, 0]);
  });

  it('sorts by patient case-insensitively (asc)', () => {
    const rows = [base({ patient: 'власов' }), base({ patient: 'Антонов' }), base({ patient: 'Борисов' })];
    const sorted = sortCashierPayments(rows, 'patient', 'asc');
    expect(sorted.map((r) => r.patient)).toEqual(['Антонов', 'Борисов', 'власов']);
  });

  it('sorts by date+time string (desc default direction semantics)', () => {
    const rows = [
      base({ date: '2026-08-30', time: '09:00' }),
      base({ date: '2026-08-31', time: '08:00' }),
      base({ date: '2026-08-30', time: '10:00' }),
    ];
    const desc = sortCashierPayments(rows, 'date', 'desc');
    expect(desc.map((r) => `${r.date} ${r.time}`)).toEqual([
      '2026-08-31 08:00',
      '2026-08-30 10:00',
      '2026-08-30 09:00',
    ]);
    const asc = sortCashierPayments(rows, 'date', 'asc');
    expect(asc.map((r) => `${r.date} ${r.time}`)).toEqual([
      '2026-08-30 09:00',
      '2026-08-30 10:00',
      '2026-08-31 08:00',
    ]);
  });

  it('does not mutate the input array', () => {
    const rows = [base({ total_amount: 3 }), base({ total_amount: 1 }), base({ total_amount: 2 })];
    const snapshot = [...rows];
    sortCashierPayments(rows, 'amount', 'asc');
    expect(rows).toEqual(snapshot);
  });
});
