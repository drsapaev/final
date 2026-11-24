import { describe, expect, it } from 'vitest';
import { resolvePanelTicketPayloads } from '../../../services/panelPrint';
import { buildPostWizardPaymentRow } from '../registrarHelpers';

const registration = {
  success: true,
  visit_ids: [101, 202],
  created_visits: [
    { visit_id: 101, doctor_name: 'Synthetic A', visit_date: '2026-11-23', visit_time: '08:30', department: 'cardiology' },
    { visit_id: 202, doctor_name: 'Synthetic B', visit_date: '2026-11-23', visit_time: '09:30', department: 'lab' },
  ],
  queue_numbers: {
    101: [{ queue_id: 11, queue_tag: 'cardiology_common', number: 1, queue_cabinet: '6' }],
    202: [{ queue_id: 22, queue_tag: 'lab', number: 2, queue_cabinet: '7' }],
  },
};

const print = (overrides = {}) =>
  resolvePanelTicketPayloads(buildPostWizardPaymentRow({ ...registration, ...overrides })!);

describe('post-registration printing preserves the exact visit and daily queue', () => {
  it('joins the cart response to visit details when print_tickets is empty', () => {
    expect(print()).toMatchObject([
      { queue_number: '1', doctor_name: 'Synthetic A', cabinet: '6', time_window: '23.11.2026 08:30' },
      { queue_number: '2', doctor_name: 'Synthetic B', cabinet: '7', time_window: '23.11.2026 09:30' },
    ]);
  });

  it('does not attach numbers by array position to reversed partial tickets', () => {
    expect(print({
      print_tickets: [{ visit_id: 202, queue_id: 22 }, { visit_id: 101, queue_id: 11 }],
    })).toMatchObject([
      { queue_number: '2', doctor_name: 'Synthetic B', cabinet: '7' },
      { queue_number: '1', doctor_name: 'Synthetic A', cabinet: '6' },
    ]);
  });

  it('keeps issued assignments if an explicit slip points to an unrelated queue', () => {
    expect(print({ print_tickets: [{ visit_id: 101, queue_id: 99 }] }))
      .toMatchObject([{ queue_number: '1', cabinet: '6' }, { queue_number: '2', cabinet: '7' }]);
  });

  it('does not guess a number when multiple queues belong to the same visit', () => {
    expect(print({
      print_tickets: [{ visit_id: 101 }],
      queue_numbers: {
        101: [
          { queue_id: 11, queue_tag: 'cardiology_common', number: 1, queue_cabinet: '6' },
          { queue_id: 22, queue_tag: 'lab', number: 1, queue_cabinet: '7' },
        ],
      },
    })).toMatchObject([{ queue_number: '1', cabinet: '6' }, { queue_number: '1', cabinet: '7' }]);
  });

  it('keeps two issued tickets even if only the second has explicit print metadata', () => {
    expect(print({ print_tickets: [{ visit_id: 202, queue_id: 22, queue_number: 2 }] }))
      .toMatchObject([{ queue_number: '2', cabinet: '7' }, { queue_number: '1', cabinet: '6' }]);
  });
});
