import { api } from './client';

export const TICKET_PRINT_SETTINGS_DEFAULTS = {
  show_clinic_name: true,
  show_logo: false,
  show_patient_name: false,
  show_service_name: true,
  show_queue_number: true,
  show_doctor_name: false,
  show_cabinet: true,
  show_price: false,
  show_qr_code: true,
  show_printed_at: true,
};

export const TICKET_PRINT_SETTINGS_DEFINITIONS = [
  {
    key: 'show_clinic_name',
    label: 'Название клиники',
    description: 'Показывать название клиники в шапке талона.',
  },
  {
    key: 'show_logo',
    label: 'Логотип',
    description: 'Показывать логотип клиники, если он загружен.',
  },
  {
    key: 'show_patient_name',
    label: 'Имя пациента',
    description: 'Показывать ФИО пациента на талоне.',
  },
  {
    key: 'show_service_name',
    label: 'Название услуги',
    description: 'Показывать услугу или профиль приема.',
  },
  {
    key: 'show_queue_number',
    label: 'Номер очереди',
    description: 'Показывать крупный номер талона.',
  },
  {
    key: 'show_doctor_name',
    label: 'Врач',
    description: 'Показывать имя врача или специалиста.',
  },
  {
    key: 'show_cabinet',
    label: 'Кабинет',
    description: 'Показывать кабинет или комнату приема.',
  },
  {
    key: 'show_price',
    label: 'Цена услуги',
    description: 'Показывать цену именно этой услуги, а не сумму оплаты.',
  },
  {
    key: 'show_qr_code',
    label: 'QR-код',
    description: 'Показывать QR-код только если в данных талона есть стабильный payload.',
  },
  {
    key: 'show_printed_at',
    label: 'Время печати',
    description: 'Показывать дату и время печати талона.',
  },
];

/**
 * @api-transport
 * Returns a free-form boolean-keyed map because the backend stores ticket
 * print settings as an arbitrary set of feature flags. The shape is
 * dictated by `TICKET_PRINT_SETTINGS_DEFAULTS` (a static const in this
 * file), not by a domain entity — there is no canonical `TicketPrintSettings`
 * in `types/domain/*`. The boolean values come directly from user settings
 * (UI checkboxes), so they cannot be a loose `unknown` at the call site.
 */
export function normalizeTicketPrintSettings(settings: Record<string, unknown> = {}): Record<string, boolean> {
  return Object.keys(TICKET_PRINT_SETTINGS_DEFAULTS).reduce((acc: Record<string, boolean>, key: string) => {
    const fallback = TICKET_PRINT_SETTINGS_DEFAULTS[key as keyof typeof TICKET_PRINT_SETTINGS_DEFAULTS];
    const value = settings?.[key];
    acc[key] = typeof value === 'boolean' ? value : fallback;
    return acc;
  }, {});
}

export async function fetchTicketPrintSettings() {
  const response = await api.get('/admin/clinic/ticket-print-settings');
  return normalizeTicketPrintSettings(response.data);
}

export async function saveTicketPrintSettings(payload: Record<string, unknown>) {
  const response = await api.put('/admin/clinic/ticket-print-settings', payload);
  return normalizeTicketPrintSettings(response.data);
}
