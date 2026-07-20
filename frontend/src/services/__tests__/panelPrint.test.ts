import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/adminSettings', () => ({
  fetchClinicSettings: vi.fn(),
}));

vi.mock('../../api/ticketPrintSettings', async () => {
  const actual = await vi.importActual<typeof import('../../api/ticketPrintSettings')>('../../api/ticketPrintSettings');
  return {
    ...actual,
    fetchTicketPrintSettings: vi.fn(),
  };
});

import { fetchClinicSettings } from '../../api/adminSettings';
import {
  fetchTicketPrintSettings,
  TICKET_PRINT_SETTINGS_DEFAULTS,
} from '../../api/ticketPrintSettings';
import {
  buildPanelReceiptPrintableHtml,
  buildPanelTicketPrintableHtml,
  resolvePanelTicketPayloads,
} from '../panelPrint';

// Cast the mocked functions through unknown to expose vitest mock methods.
const fetchTicketPrintSettingsMock = fetchTicketPrintSettings as unknown as ReturnType<typeof vi.fn>;
const fetchClinicSettingsMock = fetchClinicSettings as unknown as ReturnType<typeof vi.fn>;

describe('panelPrint ticket renderer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses the default ticket layout with QR enabled when settings are absent', async () => {
    fetchTicketPrintSettingsMock.mockResolvedValueOnce(TICKET_PRINT_SETTINGS_DEFAULTS);
    fetchClinicSettingsMock.mockResolvedValueOnce([
      { key: 'clinic_name', value: 'City Clinic' },
      { key: 'logo_url', value: '/static/logo.png' },
    ]);

    const html = await buildPanelTicketPrintableHtml({
      queue_number: 'A12',
      patient_name: 'Ivan Petrov',
      doctor_name: 'Dr. Smirnova',
      specialty_name: 'Кардиология',
      cabinet: '12',
      service_price: 15000,
      qr_url: 'https://clinic.test/tickets/A12',
    });

    expect(html).toContain('City Clinic');
    expect(html).not.toContain('ТАЛОН НА ПРИЁМ');
    expect(html).toContain('№A12');
    expect(html).not.toContain('Пациент:');
    expect(html).not.toContain('Dr. Smirnova');
    expect(html).not.toContain('15 000 UZS');
    expect(html).toContain('<svg');
  });

  it('renders only the fields enabled in ticket print settings', async () => {
    fetchTicketPrintSettingsMock.mockResolvedValueOnce({
      ...TICKET_PRINT_SETTINGS_DEFAULTS,
      show_logo: true,
      show_patient_name: true,
      show_doctor_name: true,
      show_price: true,
      show_qr_code: true,
    });
    fetchClinicSettingsMock.mockResolvedValueOnce([
      { key: 'clinic_name', value: 'City Clinic' },
      { key: 'logo_url', value: '/static/logo.png' },
    ]);

    const html = await buildPanelTicketPrintableHtml(
      {
        queue_number: 'B07',
        patient_name: 'Ivan Petrov',
        doctor_name: 'Dr. Smirnova',
        specialty_name: 'Стоматология',
        cabinet: '7',
        service_price: 42000,
        qr_url: 'https://clinic.test/tickets/B07',
      },
      { specialtyName: 'Стоматология' }
    );

    expect(html).toContain('City Clinic');
    expect(html).toContain('class="clinic-logo"');
    expect(html).toContain('Пациент:');
    expect(html).toContain('Ivan Petrov');
    expect(html).toContain('Врач:');
    expect(html).toContain('Dr. Smirnova');
    expect(html).toContain('Цена:');
    expect(html).toMatch(/42[\u00a0 ]000 UZS/);
    expect(html).toContain('<svg');
  });

  it('resolves queue number from nested queue_numbers shapes without failing', async () => {
    fetchTicketPrintSettingsMock.mockResolvedValueOnce(TICKET_PRINT_SETTINGS_DEFAULTS);
    fetchClinicSettingsMock.mockResolvedValueOnce([]);

    const html = await buildPanelTicketPrintableHtml({
      queue_numbers: {
        cardiology: {
          queue_number: 'C14',
          specialty_name: 'Кардиология',
        },
      },
      patient_name: 'Ivan Petrov',
      doctor_name: 'Dr. Smirnova',
    });

    expect(html).toContain('№C14');
    expect(html).not.toContain('ТАЛОН НА ПРИЁМ');
  });

  it('builds a multi-ticket document from aggregated queue_numbers in a single printable html', async () => {
    fetchTicketPrintSettingsMock.mockResolvedValueOnce(TICKET_PRINT_SETTINGS_DEFAULTS);
    fetchClinicSettingsMock.mockResolvedValueOnce([
      { key: 'clinic_name', value: 'City Clinic' },
    ]);

    const row = {
      patient_fio: 'Бабаджанова Мавлуда',
      queue_numbers: [
        {
          number: 2,
          queue_tag: 'dermatology',
          specialty: 'dermatology',
          cabinet_number: '101',
          queue_time: '2026-04-10T14:19:23+05:00',
        },
        {
          number: 13,
          queue_tag: 'cardiology',
          specialty: 'cardiology',
          cabinet_number: '202',
          queue_time: '2026-04-10T14:20:23+05:00',
        },
        {
          number: 3,
          queue_tag: 'laboratory',
          specialty: 'laboratory',
          cabinet_number: 'Lab-1',
          queue_time: '2026-04-10T14:21:23+05:00',
        },
      ],
    };

    const payloads = resolvePanelTicketPayloads(row);
    expect(payloads).toHaveLength(3);
    expect(payloads.map((payload) => payload.queue_number)).toEqual(['2', '13', '3']);
    expect(payloads.map((payload) => payload.cabinet)).toEqual(['101', '202', 'Lab-1']);

    const html = await buildPanelTicketPrintableHtml(row);

    expect(html).toContain('Очередь №2');
    expect(html).toContain('Очередь №13');
    expect(html).toContain('Очередь №3');
    expect(html).toContain('Кабинет:</span> 101');
    expect(html).toContain('Кабинет:</span> 202');
    expect(html).toContain('Кабинет:</span> Lab-1');
    expect(html).toContain('Дерматология');
    expect(html).toContain('Кардиология');
    expect(html).toContain('Лаборатория');
    expect((html.match(/class="ticket-page"/g) || [])).toHaveLength(3);
  });

  it('prefers queue/daily effective cabinet over linked doctor cabinet in ticket payload', () => {
    const [payload] = resolvePanelTicketPayloads({
      queue_number: 'Q5',
      specialty_name: 'Кардиология',
      doctor_cabinet: '201',
      effective_cabinet: '204',
      queue_cabinet: '204',
      patient_name: 'Ivan Petrov',
    });

    expect(payload.cabinet).toBe('204');
  });

  it('does not invent a paid payment status in receipt print html', () => {
    const html = buildPanelReceiptPrintableHtml({
      payment: {
        number: 'R-17',
        total: 150000,
      },
      patient: {
        full_name: 'Ivan Petrov',
      },
      services: [],
    });

    expect(html).toContain('<span>unknown</span>');
    expect(html).not.toContain('<span>paid</span>');
    expect(html).not.toContain('payment?.status || \'paid\'');
  });
});
