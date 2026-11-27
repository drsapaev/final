/**
 * QUEUEPRINT-FE-003 + QUEUEPRINT-FE-004 (audit group97, 2026-11-15):
 * honest queue number and honest price rendering on the panel ticket.
 *
 * Red-first (до фикса): extractQueueNumberCandidate fell back to the nested
 * obj.id — the GLOBAL queue-entry PK was printed as «Очередь №42» when no
 * true number existed; resolveServicePriceForTicket returned {} (truthy
 * nonprice) on a service-label mismatch — Number({}) is NaN, NaN !== 0 kept
 * the price block visible and formatMoney({}) rendered a FALSE «0 UZS»
 * (unknown price labeled free) under show_price=true; meanwhile a GENUINE
 * 0 price was hidden by the `!== 0` guard (genuine 0 vs missing not
 * distinguished).
 */
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../api/adminSettings', () => ({
  fetchClinicSettings: vi.fn(async () => ({})),
}));

vi.mock('../../api/ticketPrintSettings', () => {
  const DEFAULTS = {
    show_clinic_name: false,
    show_logo: false,
    show_patient_name: true,
    show_service_name: true,
    show_queue_number: true,
    show_doctor_name: false,
    show_cabinet: false,
    show_price: true,
    show_qr_code: false,
    show_printed_at: false,
  };
  return {
    TICKET_PRINT_SETTINGS_DEFAULTS: DEFAULTS,
    normalizeTicketPrintSettings: vi.fn((value: Record<string, unknown> | null) => ({
      ...DEFAULTS,
      ...(value || {}),
    })),
    fetchTicketPrintSettings: vi.fn(async () => ({ show_price: true })),
  };
});

import { buildPanelTicketPayload, buildPanelTicketsBatchPrintableHtml, buildPanelTicketPrintableHtml } from '../panelPrint';

const SETTINGS_MOCK = '../../api/ticketPrintSettings';
void SETTINGS_MOCK;

describe('QUEUEPRINT-FE-003 — honest queue number', () => {
  it('REFUSES to build a ticket whose only "number" is the queue-entry PK', () => {
    // Honest fail-closed contract: buildPanelTicketPayload throws instead
    // of printing a false «Очередь №42» from the entry PK.
    expect(() => buildPanelTicketPayload({ queue_entry: { id: 42 } })).toThrow(
      'Не удалось определить номер талона',
    );
  });

  it('still resolves the true issued number ahead of nested ids', () => {
    const payload = buildPanelTicketPayload({
      queue_entry: { queue_number: 'A12', id: 42 },
    });
    expect(payload.queue_number).toBe('A12');
  });

  it('renders NO ticket html at all when no true number exists (no PK fallback)', async () => {
    await expect(
      buildPanelTicketPrintableHtml({ queue_entry: { id: 42 } }),
    ).rejects.toThrow('Не удалось определить номер талона');
  });
});

describe('QUEUEPRINT-FE-004 — honest price under show_price=true', () => {
  it('unknown service (label mismatch) does NOT render a false «0 UZS»', async () => {
    const html = await buildPanelTicketsBatchPrintableHtml([
      {
        queue_name: 'Кардиолог',
        print_tickets: [{ queue_name: 'Кардиолог', queue_number: 4 }],
        services: [{ name: 'Консультация кардиолога', price: 50000 }],
      },
    ]);
    expect(String(html)).not.toContain('0 UZS');
    // Честное отсутствие цены: строка «Цена» не рендерится вовсе.
    expect(String(html)).not.toContain('>Цена:<');
  });

  it('omits the ticket price when multiple services match the label', async () => {
    const html = await buildPanelTicketsBatchPrintableHtml([
      {
        print_tickets: [{ queue_name: 'ЭКГ', queue_number: 4 }],
        services: [
          { code: 'ECG01', name: 'ЭКГ', price: 50000 },
          { code: 'ECG02', name: 'ЭКГ', price: 75000 },
        ],
      },
    ]);
    expect(String(html)).not.toContain('>Цена:<');
  });

  it('genuine 0 price IS rendered as 0 UZS (genuine 0 vs missing distinguished)', async () => {
    const html = await buildPanelTicketsBatchPrintableHtml([
      {
        queue_name: 'Консультация кардиолога',
        print_tickets: [{ queue_name: 'Консультация кардиолога', queue_number: 4 }],
        services: [{ name: 'Консультация кардиолога', price: 0 }],
      },
    ]);
    expect(String(html)).toContain('0 UZS');
  });

  it('a known numeric price still renders with its real amount', async () => {
    const html = await buildPanelTicketsBatchPrintableHtml([
      {
        print_tickets: [{ service_price: 50000, queue_number: 4 }],
        services: [{ name: 'Консультация кардиолога', price: 50000 }],
      },
    ]);
    expect(String(html)).toMatch(/50[\s\u00A0]?000\s*UZS/);
  });
});
