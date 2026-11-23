/**
 * QUEUEPRINT-FE-003 (audit 3892, queue-ticket print code review group 97)
 * — displayed ticket identity must never be fabricated from unrelated
 * internal record IDs.
 *
 * One trust-boundary root cause, two unsafe fallbacks:
 *
 * 1. `extractQueueNumberCandidate` chain ends in a generic `obj.id`, so a
 *    partial display object `{ queue_entry: { id: 862, queue_id: 17 } }`
 *    (no issued per-DailyQueue number) resolves the GLOBAL queue-entry PK
 *    «862» and prints «Очередь №862». The backend contract stores a
 *    distinct pair `OnlineQueueEntry.id` vs `OnlineQueueEntry.number` — a
 *    missing `number` cannot be derived from the PK.
 * 2. `buildPanelTicketPayload` visit fallback used
 *    `getFirstDefined(row?.visit_id, row?.id)`, but `row.id` is not proven
 *    to be a Visit PK (appointment / payment / aggregate rows) — an
 *    appointment `{ record_kind: 'appointment', id: 701 }` printed as
 *    «В-701».
 *
 * Required behaviour (fail closed, honest):
 * - a nested id-only entry never resolves as a queue number — with an
 *   explicit `visit_id` the ticket falls back to the visit talon «В-<id>»;
 *   without one the print fails honestly;
 * - an appointment/payment id-only row (no `visit_id`) fails honestly —
 *   «В-<row.id>» is no longer fabricated;
 * - genuine server-provided numbers and explicit `visit_id` fallbacks
 *   keep working unchanged.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/adminSettings', () => ({
  fetchClinicSettings: vi.fn(),
}));

vi.mock('../../api/ticketPrintSettings', async () => {
  const actual = await vi.importActual<typeof import('../../api/ticketPrintSettings')>(
    '../../api/ticketPrintSettings',
  );
  return {
    ...actual,
    fetchTicketPrintSettings: vi.fn(),
  };
});

import { buildPanelTicketPayload, resolvePanelTicketPayloads } from '../panelPrint';

describe('QUEUEPRINT-FE-003 — ticket identity is never fabricated from unrelated IDs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('nested id-only queue entry falls back to the explicit visit talon, never the entry PK', () => {
    const payload = buildPanelTicketPayload({
      queue_entry: { id: 862, queue_id: 17 },
      visit_id: 42,
      patient_name: 'СИНТЕТИЧЕСКИЙ ПАЦИЕНТ',
    });
    expect(payload.queue_number).toBe('В-42');
  });

  it('nested id-only queue entry without a visit identifier fails honestly', () => {
    expect(() =>
      buildPanelTicketPayload({
        queue_entry: { id: 862, queue_id: 17 },
        patient_name: 'СИНТЕТИЧЕСКИЙ ПАЦИЕНТ',
      }),
    ).toThrow('Не удалось определить номер талона');
  });

  it('appointment id-only row is not fabricated into a visit talon', () => {
    expect(() =>
      buildPanelTicketPayload({
        record_kind: 'appointment',
        id: 701,
        patient_name: 'СИНТЕТИЧЕСКИЙ ПАЦИЕНТ',
      }),
    ).toThrow('Не удалось определить номер талона');
  });

  it('a genuine issued per-queue number still wins over the entry PK', () => {
    const payload = buildPanelTicketPayload({
      queue_entry: { id: 862, number: 5 },
      patient_name: 'СИНТЕТИЧЕСКИЙ ПАЦИЕНТ',
    });
    expect(payload.queue_number).toBe('5');
  });

  it('a directly issued row number still prints as the queue number', () => {
    const payload = buildPanelTicketPayload({
      id: 501,
      number: 7,
      patient_name: 'СИНТЕТИЧЕСКИЙ ПАЦИЕНТ',
    });
    expect(payload.queue_number).toBe('7');
  });

  it('an explicit visit_id on a queue-less desk/lab row still prints the visit talon', () => {
    const payload = buildPanelTicketPayload({
      visit_id: 25,
      department: 'laboratory',
      patient_name: 'Тест Т.',
      services: [{ name: 'ОАК' }],
    });
    expect(payload.queue_number).toBe('В-25');
  });
});

it('does not print zero or nested cabinet/status as an issued ticket', () => {
  expect(buildPanelTicketPayload({ visit_id: 42, queue_number: 0 })).toMatchObject({ queue_number: 'В-42' });
  expect(() => buildPanelTicketPayload({ queue_numbers: [{ number: null, cabinet: '205', status: 'waiting' }] })).toThrow();
  expect(buildPanelTicketPayload({ queue_number: '0', number: 1, queue_cabinet: '205' })).toMatchObject({
    queue_number: '1', cabinet: '205',
  });
});

it('does not use the aggregate cabinet or ticket for a different child', () => {
  const row = {
    queue_number: 1,
    queue_cabinet: '205',
    queue_numbers: [
      { number: 1, queue_cabinet: '205', visit_id: 21 },
      { number: 2, visit_id: 22 },
    ],
  };
  const [, second] = resolvePanelTicketPayloads(row);
  expect(second).toMatchObject({ queue_number: '2', cabinet: null });
  row.queue_numbers[1].number = 0;
  expect(resolvePanelTicketPayloads(row)[1].queue_number).toBe('В-22');
});
