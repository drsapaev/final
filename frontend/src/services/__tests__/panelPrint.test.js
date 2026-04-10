import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../api/adminSettings', () => ({
  fetchClinicSettings: vi.fn(),
}));

vi.mock('../../api/ticketPrintSettings', async () => {
  const actual = await vi.importActual('../../api/ticketPrintSettings');
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
import { buildPanelTicketPrintableHtml } from '../panelPrint';

describe('panelPrint ticket renderer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses the default privacy-first ticket layout when settings are absent', async () => {
    fetchTicketPrintSettings.mockResolvedValueOnce(TICKET_PRINT_SETTINGS_DEFAULTS);
    fetchClinicSettings.mockResolvedValueOnce([
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
    expect(html).toContain('ТАЛОН НА ПРИЁМ');
    expect(html).toContain('№A12');
    expect(html).not.toContain('Пациент:');
    expect(html).not.toContain('Dr. Smirnova');
    expect(html).not.toContain('15 000 UZS');
    expect(html).not.toContain('<svg');
  });

  it('renders only the fields enabled in ticket print settings', async () => {
    fetchTicketPrintSettings.mockResolvedValueOnce({
      ...TICKET_PRINT_SETTINGS_DEFAULTS,
      show_logo: true,
      show_patient_name: true,
      show_doctor_name: true,
      show_price: true,
      show_qr_code: true,
    });
    fetchClinicSettings.mockResolvedValueOnce([
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
});
