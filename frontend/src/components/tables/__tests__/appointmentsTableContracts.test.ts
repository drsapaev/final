/**
 * PR-UI-09e-2: unit tests for appointmentsTableContracts — the pure helpers
 * moved verbatim out of EnhancedAppointmentsTable.tsx (plan §PR-UI-09 AC2).
 *
 * These pin the EXTRACTED semantics exactly as they behaved inside the
 * component: sorting special-cases (cost / queue_number), the filter
 * predicate, backend action-availability gating with aliases, the composite
 * row key, phone formatting and the service mapping indexes.
 */

import { describe, expect, it } from 'vitest';

import {
  getBackendActionAvailability,
  getEnhancedAppointmentRowKey,
  getDisplayAmount,
  getSessionColorIndex,
  createServiceMapping,
  formatPhoneNumber,
  sortAppointmentsData,
  filterAppointmentsData,
  withOpacity,
  type AppointmentRow,
} from '../appointmentsTableContracts';

describe('appointmentsTableContracts — sortAppointmentsData (PR-UI-09e-2)', () => {
  const rows: AppointmentRow[] = [
    { id: 1, cost: 300 },
    { id: 2, payment_amount: 100 },
    { id: 3, cost: 200 },
  ];

  it('returns the input unchanged when no sort key is set', () => {
    const sorted = sortAppointmentsData(rows, { key: null, direction: 'asc' });
    expect(sorted.map((r) => r.id)).toEqual([1, 2, 3]);
  });

  it('sorts by cost falling back to payment_amount (asc)', () => {
    const sorted = sortAppointmentsData(rows, { key: 'cost', direction: 'asc' });
    expect(sorted.map((r) => r.id)).toEqual([2, 3, 1]);
  });

  it('sorts by cost descending', () => {
    const sorted = sortAppointmentsData(rows, { key: 'cost', direction: 'desc' });
    expect(sorted.map((r) => r.id)).toEqual([1, 3, 2]);
  });

  it('queue_number sorts by the first queue_numbers entry, missing numbers sink (999999)', () => {
    const withQueues: AppointmentRow[] = [
      { id: 'a' },
      { id: 'b', queue_numbers: [{ number: 5 } as never] },
      { id: 'c', queue_numbers: [{ number: 2 } as never] },
    ];
    const sorted = sortAppointmentsData(withQueues, { key: 'queue_number', direction: 'asc' });
    expect(sorted.map((r) => r.id)).toEqual(['c', 'b', 'a']);
  });
});

describe('appointmentsTableContracts — filterAppointmentsData (PR-UI-09e-2)', () => {
  const rows: AppointmentRow[] = [
    { id: 1, status: 'waiting', doctor_id: 7, department: 'K', patient_fio: 'Ivanov Ivan' },
    { id: 2, status: 'done', doctor_id: 8, department: 'D', patient_fio: 'Petr Petrov' },
  ];
  const empty = { search: '', status: '', dateFrom: '', dateTo: '', doctor: '', department: '' };

  it('empty filters keep every row', () => {
    expect(filterAppointmentsData(rows, empty)).toHaveLength(2);
  });

  it('search matches any field case-insensitively', () => {
    expect(filterAppointmentsData(rows, { ...empty, search: 'IVANOV' })).toHaveLength(1);
  });

  it('status / doctor / department are exact matches (doctor via String())', () => {
    const byStatus = filterAppointmentsData(rows, { ...empty, status: 'done' });
    expect(byStatus).toHaveLength(1);
    expect(byStatus[0].id).toBe(2);
    expect(filterAppointmentsData(rows, { ...empty, doctor: '7' })).toHaveLength(1);
    const byDept = filterAppointmentsData(rows, { ...empty, department: 'D' });
    expect(byDept).toHaveLength(1);
    expect(byDept[0].id).toBe(2);
  });
});

describe('appointmentsTableContracts — getBackendActionAvailability (PR-UI-09e-2)', () => {
  it('explicit flag field wins when present on the row', () => {
    expect(getBackendActionAvailability({ can_mark_paid: true }, 'payment', 'can_mark_paid')).toBe(true);
    expect(getBackendActionAvailability({ can_mark_paid: 0 }, 'payment', 'can_mark_paid')).toBe(false);
  });

  it('returns null when the row has no available_actions array', () => {
    expect(getBackendActionAvailability({}, 'payment')).toBeNull();
    expect(getBackendActionAvailability(null, 'payment')).toBeNull();
  });

  it('aliases resolve against a trimmed/lowercased available_actions set', () => {
    const row = { available_actions: [' mark_paid ', 'Start_Visit'] };
    expect(getBackendActionAvailability(row, 'payment')).toBe(true);
    expect(getBackendActionAvailability(row, 'call')).toBe(true);
    expect(getBackendActionAvailability(row, 'complete')).toBe(false);
  });

  it('unknown action key still matches its own name in available_actions', () => {
    expect(getBackendActionAvailability({ available_actions: ['custom-op'] }, 'custom-op')).toBe(true);
  });
});

describe('appointmentsTableContracts — getEnhancedAppointmentRowKey (PR-UI-09e-2)', () => {
  it('builds the composite type:id:session:doctor:time:index key', () => {
    const row = {
      record_type: 'appointment', appointment_id: 42, session_id: 's1',
      doctor_id: 9, appointment_time: '10:00',
    } as AppointmentRow;
    expect(getEnhancedAppointmentRowKey(row as never, 3)).toBe('appointment:42:s1:9:10:00:3');
  });

  it('falls back through the id chain when appointment_id is missing', () => {
    const row = { visit_id: 7 } as AppointmentRow;
    expect(getEnhancedAppointmentRowKey(row as never, 0)).toBe('appointment:7::::0');
  });
});

describe('appointmentsTableContracts — pure display helpers (PR-UI-09e-2)', () => {
  it('withOpacity builds a color-mix() string', () => {
    expect(withOpacity('var(--mac-success)', 0.12)).toBe(
      'color-mix(in srgb, var(--mac-success) 12%, transparent)'
    );
  });

  it('formatPhoneNumber normalizes full and local UZ numbers', () => {
    expect(formatPhoneNumber('+998 90 123-45-67')).toBe('+998 (90) 123-45-67');
    expect(formatPhoneNumber('901234567')).toBe('+998 (90) 123-45-67');
  });

  it('formatPhoneNumber passes through short/unknown numbers and renders em-dash for empty', () => {
    expect(formatPhoneNumber('123')).toBe('123');
    expect(formatPhoneNumber('')).toBe('—');
  });

  it('getDisplayAmount prefers cost for shared invoices and falls back otherwise', () => {
    expect(getDisplayAmount({ has_shared_invoice: true, cost: 5, payment_amount: 9 } as never)).toBe(5);
    expect(getDisplayAmount({ cost: 0, invoice_amount: 4, payment_amount: 7 } as never)).toBe(4);
    expect(getDisplayAmount({} as never)).toBe(0);
  });

  it('getSessionColorIndex: -1 for empty, stable in [0..7] otherwise', () => {
    expect(getSessionColorIndex('')).toBe(-1);
    const a = getSessionColorIndex('session-abc');
    expect(a).toBe(getSessionColorIndex('session-abc'));
    expect(a).toBeGreaterThanOrEqual(0);
    expect(a).toBeLessThan(8);
  });
});

describe('appointmentsTableContracts — createServiceMapping (PR-UI-09e-2)', () => {
  const services = {
    'Кардиология': [
      { id: 11, name: 'ЭКГ', service_code: 'K01' },
      { id: 12, name: 'ЭхоКГ', code: 'K11' },
    ],
  };

  it('builds id→name, lowercase name→service and uppercase code→service indexes', () => {
    const { mapping, nameToService, codeToService } = createServiceMapping(services);
    expect(mapping['11']).toBe('ЭКГ');
    expect(nameToService['экг']).toMatchObject({ id: 11 });
    expect(codeToService['K01']).toMatchObject({ id: 11 });
    expect(codeToService['K11']).toMatchObject({ id: 12 });
  });

  it('returns empty maps for empty services', () => {
    const m = createServiceMapping({});
    expect(m.mapping).toEqual({});
    expect(m.nameToService).toEqual({});
    expect(m.codeToService).toEqual({});
  });
});
