/**
 * PR-UI-09e-2: EnhancedAppointmentsTable decomposition — pure contracts.
 *
 * Types, constants and pure helpers moved verbatim from
 * EnhancedAppointmentsTable.tsx (plan §PR-UI-09 AC2 "EAT ≤ 400 LOC";
 * registrar/RRT extraction pattern — §4.1.9 deferral record).
 *
 * Pure by construction: no React, no state, no network.
 * EnhancedAppointmentsTable.tsx stays the single public entry point
 * and re-exports AppointmentRow for existing consumers.
 */

import type { Appointment, QueueNumberInfo } from '../../types/domain/clinic';

/** Translation fn shape (same contract as RefundTranslationFn, PR-UI-14-6). */
export type AppointmentsTranslationFn = (key: string, options?: Record<string, unknown>) => string;

export interface AppointmentsTableSortConfig {
  key: string | null;
  direction: string;
}

export interface AppointmentsTableFilterConfig {
  search: string;
  status: string;
  dateFrom: string;
  dateTo: string;
  doctor: string;
  department: string;
}

const SESSION_COLORS = [
  'var(--mac-accent-blue)', // blue
  'var(--mac-success)', // emerald
  'var(--mac-warning)', // amber
  'var(--mac-error)', // red
  '#8B5CF6', // violet
  '#EC4899', // pink
  'var(--mac-accent-blue-light)', // cyan
  '#84CC16' // lime
];

const ACTION_ALIASES = {
  payment: ['payment', 'mark_paid', 'mark-paid'],
  call: ['call', 'start_visit', 'start-visit'],
  print: ['print', 'print_ticket', 'print-ticket'],
  complete: ['complete', 'complete_visit', 'complete-visit'],
  view_emr: ['view_emr', 'view-emr'],
  schedule_next: ['schedule_next', 'schedule-next']
} as const;

type ActionAliasKey = keyof typeof ACTION_ALIASES;

export const getBackendActionAvailability = (row: Record<string, unknown> | null | undefined, action: string, flagName?: string) => {
  if (row && flagName && Object.prototype.hasOwnProperty.call(row, flagName)) {
    return Boolean(row[flagName]);
  }

  if (!Array.isArray(row?.available_actions)) {
    return null;
  }

  const actions = new Set(row.available_actions.map((item: unknown) => String(item).trim().toLowerCase()));
  const aliasesRaw = ACTION_ALIASES[action as ActionAliasKey];
  const aliases: string[] = aliasesRaw ? Array.from(aliasesRaw) : [action];
  return aliases.some((alias: string) => actions.has(alias));
};

export const getEnhancedAppointmentRowKey = (row: Appointment, index: number) => {
  const parts = [
    row?.record_type || row?.source_type || row?.source || row?.entity_type || 'appointment',
    row?.appointment_id ?? row?.visit_id ?? row?.queue_entry_id ?? row?.queue_id ?? row?.payment_id ?? row?.id ?? 'no-id',
    row?.session_id || row?.queue_number || row?.number || '',
    row?.doctor_id || row?.specialist_id || row?.department_id || row?.department || '',
    row?.appointment_time || row?.visit_time || row?.time || row?.start_time || '',
    index
  ];

  return parts.map((part) => String(part)).join(':');
};

export interface AppointmentRow {
  id?: string | number | import('../../types/domain/branded').AppointmentId;
  patient_id?: string | number | import('../../types/domain/branded').PatientId;
  patient_fio?: string;
  patient_name?: string;
  patient_phone?: string;
  patient_birth_year?: number;
  patient_address?: string;
  doctor_id?: string | number | import('../../types/domain/branded').DoctorId;
  doctor_name?: string;
  department?: string;
  status?: string;
  payment_status?: string;
  date?: string;
  appointment_date?: string;
  time?: string;
  appointment_time?: string;
  cost?: number;
  payment_amount?: number;
  queue_numbers?: QueueNumberInfo[];
  session_id?: string;
  service?: string;
  services?: Array<{ name?: string; [k: string]: unknown }>;
  template_name?: string;
  flagged_findings_count?: number;
  [k: string]: unknown;
}

export interface EnhancedAppointmentsTableProps {
  data?: AppointmentRow[];
  loading?: boolean;
  onRowClick?: (row: AppointmentRow) => void;
  onActionClick?: (action: string, row: AppointmentRow, event?: unknown) => void;
  theme?: string;
  language?: string;
  selectedRows?: Set<unknown>;
  onRowSelect?: (id: unknown, checked?: boolean) => void;
  services?: Record<string, unknown>;
  outerBorder?: boolean;
  showCheckboxes?: boolean;
  view?: string;
  rawEntries?: AppointmentRow[];
  appointments?: AppointmentRow[];
  appointmentsSelected?: Set<unknown>;
  setAppointmentsSelected?: (rows: Set<unknown>) => void;
  updateAppointmentStatus?: (id: unknown, status: unknown) => void;
  setShowWizard?: (show: boolean) => void;
}

// Вспомогательная функция для добавления прозрачности к CSS переменной
export const withOpacity = (cssVar: string, opacity: number) => {
  // Используем color-mix если доступен, иначе fallback
  return `color-mix(in srgb, ${cssVar} ${opacity * 100}%, transparent)`;
};

// PR-UI-09c-4: hash -> stable SESSION_COLORS index. The color VALUE lives in
// EnhancedAppointmentsTable.css (.eat-session-N rules) because the canonical
// DataTable has no row-level style/className prop (CSS :has() marker
// technique, same as QueueTable 09c-2 / PR-2860).
export const getSessionColorIndex = (sessionId: string) => {
  if (!sessionId) return -1;
  // Simple hash to get consistent color for same session_id
  let hash = 0;
  for (let i = 0; i < sessionId.length; i++) {
    hash = (hash << 5) - hash + sessionId.charCodeAt(i);
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash) % SESSION_COLORS.length;
};

// ✅ УНИВЕРСАЛЬНЫЙ МАППИНГ УСЛУГ (работает с любыми данными из админ панели)
// audit/phase-6, BS-61: extended to also build nameToService + codeToService
// maps so the per-row renderServices() can do O(1) lookups instead of
// nested Object.values(services).find() — was O(rows × groups × group_size).
export const createServiceMapping = (services: Record<string, unknown>) => {
  const mapping: Record<string, string> = {};
  const categoryMapping: Record<string, string> = {};
  const nameToService: Record<string, Record<string, unknown>> = {};
  const codeToService: Record<string, Record<string, unknown>> = {};

  // Преобразуем структуру services в плоские маппинги
  Object.entries(services).forEach(([category, group]) => {
    if (Array.isArray(group)) {
      group.forEach((service: Record<string, unknown>) => {
        if (service.id && service.name) {
          const id = String(service.id);
          mapping[id] = String(service.name);
          categoryMapping[id] = category;

          // Дополнительные алиасы для совместимости
          if (service.service_id) {
            mapping[String(service.service_id)] = String(service.name);
            categoryMapping[String(service.service_id)] = category;
          }

          // audit/phase-6, BS-61: index by name (lowercase for case-insensitive lookup)
          nameToService[String(service.name).toLowerCase()] = service;

          // index by service_code + code (uppercase for case-insensitive lookup)
          if (service.service_code) {
            codeToService[String(service.service_code).toUpperCase()] = service;
          }
          if (service.code) {
            codeToService[String(service.code).toUpperCase()] = service;
          }
        }
      });
    }
  });

  return { mapping, categoryMapping, nameToService, codeToService };
};

export const getDisplayAmount = (row: Appointment) => {
  if (row?.has_shared_invoice) {
    return Number(row?.cost || 0);
  }
  return Number(row?.cost || row?.invoice_amount || row?.payment_amount || 0);
};

// Функция для форматирования номера телефона (i18next migration)
export const formatPhoneNumber = (phone: string) => {
  if (!phone) return '—';

  // Убираем все нецифровые символы
  const digits = phone.replace(/\D/g, '');

  // Если номер начинается с 998, добавляем +
  if (digits.startsWith('998')) {
    const formatted = `+998 (${digits.slice(3, 5)}) ${digits.slice(5, 8)}-${digits.slice(8, 10)}-${digits.slice(10, 12)}`;
    return formatted;
  }

  // Если номер начинается с 9 (без кода страны)
  if (digits.startsWith('9') && digits.length >= 9) {
    const formatted = `+998 (${digits.slice(0, 2)}) ${digits.slice(2, 5)}-${digits.slice(5, 7)}-${digits.slice(7, 9)}`;
    return formatted;
  }

  // Если номер короткий или нестандартный, возвращаем как есть
  return phone;
};

// Сортировка данных (sortedData memo body from EnhancedAppointmentsTable, verbatim)
export const sortAppointmentsData = (
  data: AppointmentRow[],
  sortConfig: AppointmentsTableSortConfig,
): AppointmentRow[] => {
  if (!sortConfig.key) return data;

  return [...data].sort((a, b) => {
    const sortKey = sortConfig.key;
    let aVal: unknown = sortKey ? a[sortKey] : undefined;
    let bVal: unknown = sortKey ? b[sortKey] : undefined;

    // Специальная обработка для стоимости
    if (sortConfig.key === 'cost') {
      aVal = a.cost || a.payment_amount || 0;
      bVal = b.cost || b.payment_amount || 0;
    }

    // ✅ Специальная обработка для номера очереди
    if (sortConfig.key === 'queue_number') {
      // Извлекаем первый номер очереди из массива queue_numbers
      aVal = a.queue_numbers && a.queue_numbers.length > 0 ? a.queue_numbers[0].number : 999999;
      bVal = b.queue_numbers && b.queue_numbers.length > 0 ? b.queue_numbers[0].number : 999999;
    }

    const aNum = Number(aVal);
    const bNum = Number(bVal);
    if (aNum < bNum) return sortConfig.direction === 'asc' ? -1 : 1;
    if (aNum > bNum) return sortConfig.direction === 'asc' ? 1 : -1;
    return 0;
  });
};

// Фильтрация данных (filteredData memo body from EnhancedAppointmentsTable, verbatim)
export const filterAppointmentsData = (
  sortedData: AppointmentRow[],
  filterConfig: AppointmentsTableFilterConfig,
): AppointmentRow[] => {
  return sortedData.filter((row: AppointmentRow) => {
    const searchMatch = !filterConfig.search ||
    Object.values(row).some((val) =>
    String(val).toLowerCase().includes(filterConfig.search.toLowerCase())
    );

    const statusMatch = !filterConfig.status || row.status === filterConfig.status;
    const doctorMatch = !filterConfig.doctor || String(row.doctor_id) === filterConfig.doctor;
    const departmentMatch = !filterConfig.department || row.department === filterConfig.department;

    return searchMatch && statusMatch && doctorMatch && departmentMatch;
  });
};
