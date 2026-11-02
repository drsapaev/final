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

  it('REG-FE-057: registrar № sorting follows the visible selected ticket, not another queue ticket', () => {
    const rows: AppointmentRow[] = [
      { id: 'lab-9', queue_number: 9, queue_numbers: [{ number: 1, queue_tag: 'cardiology' } as never] },
      { id: 'ecg-2', queue_number: 2, queue_numbers: [{ number: 50, queue_tag: 'cardiology' } as never] },
      { id: 'fallback-7', queue_numbers: [{ number: 7, queue_tag: 'lab' } as never] },
      { id: 'unassigned', queue_number: 0, queue_numbers: [{ number: 0, queue_tag: 'lab' } as never] },
    ];
    expect(sortAppointmentsData(rows, { key: 'queue_number', direction: 'asc' }, true).map((r) => r.id))
      .toEqual(['ecg-2', 'fallback-7', 'lab-9', 'unassigned']);
    expect(sortAppointmentsData(rows, { key: 'queue_number', direction: 'desc' }, true).map((r) => r.id))
      .toEqual(['lab-9', 'fallback-7', 'ecg-2', 'unassigned']);
    // Existing non-registrar sort compatibility is intentionally preserved.
    expect(sortAppointmentsData(rows, { key: 'queue_number', direction: 'asc' }).map((r) => r.id))
      .toEqual(['unassigned', 'lab-9', 'fallback-7', 'ecg-2']);
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
  // REG-FE-055 (audit ledger 3803): the key no longer embeds the
  // page-relative index for records with a canonical id — the index made the
  // same record remount on every reorder/page change.
  it('builds the composite type:id:session:doctor:time key without the page index', () => {
    const row = {
      record_type: 'appointment', appointment_id: 42, session_id: 's1',
      doctor_id: 9, appointment_time: '10:00',
    } as AppointmentRow;
    expect(getEnhancedAppointmentRowKey(row as never, 3)).toBe('appointment:42:s1:9:10:00');
  });

  it('falls back through the id chain when appointment_id is missing', () => {
    const row = { visit_id: 7 } as AppointmentRow;
    expect(getEnhancedAppointmentRowKey(row as never, 0)).toBe('appointment:7:::');
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

// REG-FE-050/053/055/061 (registrar audit ledger 3803) — table contract
// truthfulness: sortable text/date/status columns actually sort, search
// matches the nested service names it renders, row keys stay stable across
// reordering, and truncated 998 phones are not dressed up as complete
// numbers.
describe('appointmentsTableContracts — REG-FE-050 typed sorting', () => {
  const rows: AppointmentRow[] = [
    { id: 1, patient_fio: 'Янов Ярослав' },
    { id: 2, patient_fio: 'Ivanov Ivan' },
    { id: 3, patient_fio: 'Абрамов Абрам' },
  ];

  it('sorts Cyrillic/Latin patient names instead of leaving the input order (NaN comparator)', () => {
    const asc = sortAppointmentsData(rows, { key: 'patient_fio', direction: 'asc' });
    // ru collation: Cyrillic sorts before Latin (Абрамов < Янов < Ivanov);
    // the contract is a real ordering, not the frozen input order.
    expect(asc.map((r) => r.id)).toEqual([3, 1, 2]);
    const desc = sortAppointmentsData(rows, { key: 'patient_fio', direction: 'desc' });
    expect(desc.map((r) => r.id)).toEqual([2, 1, 3]);
  });

  it('sorts ISO appointment dates chronologically', () => {
    const dateRows: AppointmentRow[] = [
      { id: 1, appointment_date: '2026-11-03' },
      { id: 2, appointment_date: '2026-01-15' },
      { id: 3, appointment_date: '2026-10-01' },
    ];
    expect(sortAppointmentsData(dateRows, { key: 'appointment_date', direction: 'asc' }).map((r) => r.id))
      .toEqual([2, 3, 1]);
  });

  it('sorts canonical status strings alphabetically', () => {
    const statusRows: AppointmentRow[] = [
      { id: 1, status: 'waiting' },
      { id: 2, status: 'in_service' },
      { id: 3, status: 'diagnostics' },
    ];
    expect(sortAppointmentsData(statusRows, { key: 'status', direction: 'asc' }).map((r) => r.id))
      .toEqual([3, 2, 1]);
  });

  it('keeps numeric sorting for cost (missing cost coerces to 0 by the cost special case)', () => {
    const mixed: AppointmentRow[] = [
      { id: 1, patient_fio: 'a' },
      { id: 2, cost: 200 },
      { id: 3, cost: 100 },
    ];
    expect(sortAppointmentsData(mixed, { key: 'cost', direction: 'asc' }).map((r) => r.id))
      .toEqual([1, 3, 2]);
    expect(sortAppointmentsData(mixed, { key: 'cost', direction: 'desc' }).map((r) => r.id))
      .toEqual([2, 3, 1]);
  });

  it('pushes missing text values last regardless of direction', () => {
    const mixed: AppointmentRow[] = [
      { id: 1, patient_fio: undefined },
      { id: 2, patient_fio: 'b' },
      { id: 3, patient_fio: 'a' },
    ];
    expect(sortAppointmentsData(mixed, { key: 'patient_fio', direction: 'asc' }).map((r) => r.id))
      .toEqual([3, 2, 1]);
    expect(sortAppointmentsData(mixed, { key: 'patient_fio', direction: 'desc' }).map((r) => r.id))
      .toEqual([2, 3, 1]);
  });
});

describe('appointmentsTableContracts — REG-FE-053 nested service search', () => {
  const rows: AppointmentRow[] = [
    { id: 1, services: [{ name: 'ЭхоКГ', code: 'K11' }] as never },
    { id: 2, services: ['Терапия'] as never },
    { id: 3, patient_fio: 'Другой Пациент' },
  ];

  it('matches a query against nested service object names and codes', () => {
    expect(filterAppointmentsData(rows, { search: 'эхокг', status: '', dateFrom: '', dateTo: '', doctor: '', department: '' }).map((r) => r.id))
      .toEqual([1]);
    expect(filterAppointmentsData(rows, { search: 'K11', status: '', dateFrom: '', dateTo: '', doctor: '', department: '' }).map((r) => r.id))
      .toEqual([1]);
  });

  it('still matches flat patient names and plain-string services', () => {
    expect(filterAppointmentsData(rows, { search: 'терапия', status: '', dateFrom: '', dateTo: '', doctor: '', department: '' }).map((r) => r.id))
      .toEqual([2]);
    expect(filterAppointmentsData(rows, { search: 'другой', status: '', dateFrom: '', dateTo: '', doctor: '', department: '' }).map((r) => r.id))
      .toEqual([3]);
  });
});

describe('appointmentsTableContracts — REG-FE-055 stable row keys', () => {
  it('the same record keeps its key when reordering changes its index', () => {
    const row = { appointment_id: 42, record_type: 'visit' } as never;
    const keyAtPosition0 = getEnhancedAppointmentRowKey(row, 0);
    const keyAtPosition7 = getEnhancedAppointmentRowKey(row, 7);
    expect(keyAtPosition7).toBe(keyAtPosition0);
  });

  it('rows without any canonical id keep the index discriminator', () => {
    const bare = {} as never;
    expect(getEnhancedAppointmentRowKey(bare, 3)).not.toBe(getEnhancedAppointmentRowKey(bare, 4));
  });
});

describe('appointmentsTableContracts — REG-FE-061 phone formatting length guards', () => {
  it('formats a complete 12-digit 998 number', () => {
    expect(formatPhoneNumber('+998 90 123 45 67')).toBe('+998 (90) 123-45-67');
  });

  it('formats a complete 9-digit local number', () => {
    expect(formatPhoneNumber('901234567')).toBe('+998 (90) 123-45-67');
  });

  it.each(['998', '99890', '9989012345', '+998 90 123 45'])(
    'an incomplete 998-prefixed input %j is NOT dressed up as a complete number',
    (input) => {
      const formatted = formatPhoneNumber(input);
      expect(formatted).toBe(input);
      expect(formatted).not.toMatch(/\(\d+\)\s*--/);
    },
  );
});
