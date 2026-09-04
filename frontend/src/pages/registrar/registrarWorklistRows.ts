/**
 * Registrar worklist — view-model row computation (pure).
 *
 * PR-UI-13-2: extracted verbatim from RegistrarPanel.tsx — the
 * filteredAppointments useMemo body and the departmentStats useMemo body.
 * The panel keeps thin memo wrappers (identical dependency triggers) that
 * call these pure functions.
 *
 * PRESENTATION-ONLY layer (SSOT):
 * - Backend owns queue facts; this module only filters/groups/sorts rows
 *   for display (tab filter via queue_tags from API profiles, status filter,
 *   client-side search by FIO/id/phone, patient aggregation for the
 *   "all departments" tab, presentation-only ordering).
 * - ⚠️ Do NOT use aggregate grouping for: filtering, routing, department
 *   decisions (registrarAggregation SSOT note).
 *
 * Contract (pinned by RegistrarPanel.contract.test.tsx
 * 'uses presentation-only sorting from backend queue_time facts'):
 * - exactly 5 sortRegistrarRowsForPresentation call-sites with the original
 *   argument shapes (entriesForTab / appointments.filter / searched /
 *   aggregatedPatients / appointments).
 */
import logger from '../../utils/logger';
import type { Appointment } from '../../types/domain/clinic';
import {
  aggregatePatientsForAllDepartments as aggregateRegistrarPatients,
  sortRegistrarRowsForPresentation,
} from '../../utils/registrarAggregation';
import { filterServicesByDepartment } from './registrarServiceFilter';

export interface QueueProfileItem {
  key?: string;
  title?: string;
  title_ru?: string;
  queue_tags?: string[];
  is_active?: boolean;
  [key: string]: unknown;
}

export interface RegistrarDepartmentStats {
  [profileKey: string]: {
    todayCount: number;
    hasActiveQueue: boolean;
    hasPendingPayments: boolean;
  };
}

// Мемоизированные счетчики и индикаторы по отделам
export const computeDepartmentStats = (
  appointments: Appointment[],
  todayStr: string,
  queueProfiles: QueueProfileItem[],
): RegistrarDepartmentStats => {
  const stats: Record<string, unknown> = {};

  // ⭐ SSOT: Use queue profile keys from API, not hardcoded department keys
  // queueProfiles is loaded from GET /queues/profiles via Tabs (renamed from ModernTabs in PR-UI-17-5)
  const profileKeys = queueProfiles.length > 0 ?
  queueProfiles.map((p) => p.key) :
  ['cardiology', 'ecg', 'dermatology', 'stomatology', 'lab', 'procedures']; // Fallback

  // Get queue_tags for each profile for accurate matching
  const profileTagsMap: Record<string, string[]> = {};
  queueProfiles.forEach((p) => {
    const profileKey = p.key || '';
    if (profileKey) {
      profileTagsMap[profileKey] = p.queue_tags || [profileKey];
    }
  });

  profileKeys.forEach((profileKey) => {
    // ⭐ SSOT: Match entries by queue_tags from profile
    const safeProfileKey = String(profileKey || '');
    const possibleTags = profileTagsMap[safeProfileKey] || [safeProfileKey];

    const profileAppointments = appointments.filter((a) => {
      const entryTag = String(a.queue_tag || a.specialty || '').toLowerCase().trim();
      return possibleTags.some((tag: string) => tag.toLowerCase() === entryTag);
    });

    const todayAppointments = profileAppointments.filter((a) => {
      const appointmentDate = a.date || a.appointment_date;
      return appointmentDate === todayStr;
    });

    stats[safeProfileKey] = {
      todayCount: todayAppointments.length,
      hasActiveQueue: profileAppointments.some((a) =>
      a.queue_numbers && a.queue_numbers.length > 0 &&
      ['waiting', 'called', 'in_service'].includes(String(a.status || ''))
      ),
      hasPendingPayments: profileAppointments.some((a) =>
      a.status === 'paid_pending' || a.payment_status === 'pending'
      )
    };
  });

  return stats as RegistrarDepartmentStats;
};

/**
 * View-model rows for the worklist table.
 * Mirrors the original filteredAppointments useMemo body verbatim:
 * - tab filter (queue_tags from API profiles; fallback: tabKey itself)
 * - status filter + client-side search (FIO / record id / phone digits)
 * - "all departments" tab: patient aggregation + search over aggregated rows
 * - presentation-only ordering via sortRegistrarRowsForPresentation
 */
export const computeRegistrarWorklistRows = ({
  appointments,
  activeTab,
  statusFilter,
  searchQuery,
  queueProfiles,
  services,
  fallbackPatientLabel,
}: {
  appointments: Appointment[];
  activeTab: string | null;
  statusFilter: string | null;
  searchQuery: string;
  queueProfiles: QueueProfileItem[];
  services: Record<string, unknown>;
  fallbackPatientLabel: string;
}): Record<string, unknown>[] => {
  // ⭐ SSOT: Get queue_tags from loaded profiles instead of hardcoded mapping
  // queueProfiles is populated by ModernTabs via onProfilesLoaded callback
  const getQueueTagsForTab = (tabKey: string) => {
    if (!tabKey) return [];

    // Find profile by key
    const profile = queueProfiles.find((p) => p.key === tabKey);
    if (profile && profile.queue_tags && profile.queue_tags.length > 0) {
      return profile.queue_tags;
    }

    // Fallback: use tabKey itself as the only tag
    // ⚠️ TEMPORARY ADAPTER: for backwards compatibility during transition
    return [tabKey];
  };

  // Если выбрана конкретная вкладка (не "Все отделения"), используем appointments с фильтрацией по queue_tag
  if (activeTab) {
    // ⭐ SSOT: queue_tags from API profiles, not hardcoded
    const possibleTags = getQueueTagsForTab(activeTab);

    // Фильтруем appointments по queue_tag вкладки
    const entriesForTab = (appointments).filter((entry) => {
      // Определяем queue_tag записи
      const entryQueueTag = (
      entry.queue_tag ||
      entry.specialty ||
      entry.queue_numbers && entry.queue_numbers[0]?.queue_tag ||
      '').
      toString().toLowerCase().trim();

      // Проверяем соответствие вкладке
      const matchesTab = possibleTags.some((tag: string) => tag.toLowerCase() === entryQueueTag);
      if (!matchesTab) return false;

      // Фильтр по статусу
      if (statusFilter && entry.status !== statusFilter) return false;

      // Фильтр по поиску
      if (searchQuery) {
        const inFio = (entry.patient_fio || entry.patient_name || '').toLowerCase().includes(searchQuery);
        const inId = String(entry.id).includes(searchQuery);
        const phoneDigits = String(entry.patient_phone || entry.phone || '').replace(/\D/g, '');
        const searchDigits = searchQuery.replace(/\D/g, '');
        const inPhone = phoneDigits.includes(searchDigits);
        if (!inFio && !inId && !inPhone) return false;
      }

      return true;
    });

    // Сортируем по queue_time ASC
    const sorted = sortRegistrarRowsForPresentation(entriesForTab as Record<string, unknown>[]);

    logger.info('⭐ FIX 16: Вкладка', activeTab, '- найдено', sorted.length, 'записей из',
    appointments.length, 'appointments');

    // ⭐ FIX 16: Подробный лог queue_time для каждой entry
    sorted.forEach((entry, idx) => {
      // UX Audit R-3.6: убрано логирование patient_fio (PII leak).
      logger.info(`  📌 Entry[${idx}]: id=${entry.id}, queue_tag=${entry.queue_tag}, queue_time=${entry.queue_time}`);
    });

    // Каждая entry уже содержит свой queue_time — никакого переопределения не нужно
    return sorted.map((entry) => ({
      ...entry,
      // Нормализуем поля для совместимости с EnhancedAppointmentsTable
      patient_fio: entry.patient_fio || entry.patient_name || fallbackPatientLabel,
      queue_number: entry.number || entry.queue_number,
      queue_numbers: entry.queue_numbers || [{
        number: entry.number,
        queue_tag: entry.queue_tag || entry.specialty,
        status: entry.status,
        queue_time: entry.queue_time
      }]
    }));
  }

  // Для вкладки "Все отделения" (activeTab === null или undefined) - агрегируем пациентов
  if (!activeTab) {
    // Сначала фильтруем по статусу, если задан
    const filtered = sortRegistrarRowsForPresentation(appointments.filter((appointment: Appointment) => {
      // Фильтр по статусу (если задан)
      if (statusFilter && appointment.status !== statusFilter) return false;
      return true;
    }) as Record<string, unknown>[]);

    // Затем агрегируем пациентов
    logger.info(`📊 Для вкладки "Все отделения": ${filtered.length} записей до агрегации`);
    const qrInFiltered = filtered.filter((a) => a.source === 'online');
    logger.info(`🔍 QR-записей в фильтре: ${qrInFiltered.length}`);
    qrInFiltered.forEach((a) => {
      // UX Audit R-3.6: убрано логирование patient_fio (PII leak).
      logger.info(`  - appointment_id=${a.id}: ${(a.queue_numbers as unknown[] | undefined)?.length || 0} queue_numbers`);
    });

    const aggregatedPatients = aggregateRegistrarPatients(filtered);
    logger.info(`📊 После агрегации: ${aggregatedPatients.length} пациентов`);

    // Применяем поиск к агрегированным данным
    if (searchQuery) {
      const searched = aggregatedPatients.filter((patient) => {
        const p = patient as Record<string, unknown>;
        const inFio = String(p.patient_fio || '').toLowerCase().includes(searchQuery);

        // Поиск по ID записи
        const inId = String(p.id).includes(searchQuery);

        // Улучшенный поиск по телефону
        const originalPhone = String(p.patient_phone || '').toLowerCase();
        const phoneDigits = originalPhone.replace(/\D/g, '');
        const searchDigits = searchQuery.replace(/\D/g, '');

        const inPhone = originalPhone.includes(searchQuery) ||
        phoneDigits.includes(searchDigits) ||
        searchDigits.length >= 3 && phoneDigits.includes(searchDigits);

        // Поиск по услугам (теперь ищем в агрегированном списке)
        const inServices = Array.isArray(patient.services) && patient.services.some((s: string) => String(s).toLowerCase().includes(searchQuery));

        return inFio || inPhone || inServices || inId;
      });
      // Presentation-only order: backend queue_time first, then created_at.
      return sortRegistrarRowsForPresentation(searched);
    }

    // ⭐ ВАЖНО: Сортируем агрегированных пациентов по queue_time ASC (согласно cursor.yaml)
    const sortedAggregated = sortRegistrarRowsForPresentation(aggregatedPatients);

    // ✅ ИСПРАВЛЕНО: Применяем правильное форматирование услуг для вкладки "Все отделения"
    // Это гарантирует, что для QR-записей будут показаны все коды услуг (K01, S01 и т.д.)
    return sortedAggregated.map((patient) => ({
      ...patient,
      services: filterServicesByDepartment(patient as unknown as Appointment, null, services)
    }));
  }

  // Presentation-only order on a copy; backend remains owner of queue facts.
  return sortRegistrarRowsForPresentation(appointments as Record<string, unknown>[]);
};

export default computeRegistrarWorklistRows;
