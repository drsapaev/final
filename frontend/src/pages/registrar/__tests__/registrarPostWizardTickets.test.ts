import { describe, expect, it, vi } from 'vitest';
import { buildPanelTicketPrintableHtml, resolvePanelTicketPayloads } from '../../../services/panelPrint';
import { buildPostWizardPaymentRow } from '../registrarHelpers';

vi.mock('../../../api/adminSettings', () => ({ fetchClinicSettings: vi.fn(async () => []) }));
vi.mock('../../../api/ticketPrintSettings', async () => {
  const actual = await vi.importActual<typeof import('../../../api/ticketPrintSettings')>('../../../api/ticketPrintSettings');
  return {
    ...actual,
    fetchTicketPrintSettings: vi.fn(async () => ({ ...actual.TICKET_PRINT_SETTINGS_DEFAULTS, show_price: true })),
  };
});

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

  it('preserves the persisted per-ticket charge, including a true zero, without borrowing the cart total', () => {
    expect(print({
      total_amount: 70000,
      queue_numbers: {
        101: [{ ...registration.queue_numbers[101][0], service_price: '50000.00' }],
        202: [{ ...registration.queue_numbers[202][0], service_price: '0.00' }],
      },
    })).toMatchObject([
      { queue_number: '1', service_price: '50000.00' },
      { queue_number: '2', service_price: '0.00' },
    ]);
  });

  it('prints each exact same-visit charge individually and omits a price for the unknown ticket', async () => {
    const row = buildPostWizardPaymentRow({
      ...registration, visit_ids: [101], total_amount: '83000.00',
      queue_numbers: { 101: [
        { queue_id: 11, queue_tag: 'ecg', number: 1, service_price: '83000.00' },
        { queue_id: 22, queue_tag: 'lab', number: 2, service_price: '0.00' },
        { queue_id: 33, queue_tag: 'procedures', number: 3 },
      ] },
    })!;

    const html = await buildPanelTicketPrintableHtml(row);
    const document = new DOMParser().parseFromString(html, 'text/html');
    const tickets = [...document.querySelectorAll('.ticket')].map(node => node.textContent?.replace(/\s+/g, '') || '');
    expect(tickets).toHaveLength(3);
    expect(tickets[0]).toMatch(/Цена:83000/);
    expect(tickets[1]).toMatch(/Цена:0(?!\d)/);
    expect(tickets[2]).not.toContain('Цена:');
  });

  it.each([null, undefined, '', ' ', 'invalid'])('does not print fabricated 0 on an unnumbered visit when total is %s', async (total) => {
    const row = buildPostWizardPaymentRow({
      success: true, visit_ids: [101], total_amount: total,
    })!;
    expect(await buildPanelTicketPrintableHtml(row)).not.toContain('Цена:');
  });

  it('keeps genuine zero for one unnumbered visit, but not a multi-visit cart amount', async () => {
    const free = buildPostWizardPaymentRow({ success: true, visit_ids: [101], total_amount: '0.00' })!;
    expect(await buildPanelTicketPrintableHtml(free)).toContain('Цена:');
    const combined = buildPostWizardPaymentRow({ success: true, visit_ids: [101, 202], total_amount: '50000' })!;
    expect(combined.cost).toBe(50000);
    expect(await buildPanelTicketPrintableHtml(combined)).not.toContain('Цена:');
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
