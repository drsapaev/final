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

const belongsToDoctor = (entry: Appointment, doctorId: number): boolean => {
  return entry.queue_owner_kind === 'doctor' && entry.queue_owner_id === doctorId;
};

/** Doctor tabs use the entry's own queue owner, never a specialty bucket. */
export const computeDoctorStats = (
  appointments: Appointment[],
  date: string,
  doctorIds: number[],
): RegistrarDepartmentStats => Object.fromEntries(doctorIds.map((id) => {
  const rows = appointments.filter((entry) => belongsToDoctor(entry, id));
  return [String(id), {
    todayCount: rows.filter((entry) => (entry.date || entry.appointment_date) === date).length,
    hasActiveQueue: rows.some((entry) =>
      entry.queue_numbers && entry.queue_numbers.length > 0 &&
      ['waiting', 'called', 'in_service'].includes(String(entry.status || ''))),
    hasPendingPayments: rows.some((entry) =>
      entry.status === 'paid_pending' || entry.payment_status === 'pending'),
  }];
})) as RegistrarDepartmentStats;

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
/**
 * SSOT tag resolution shared by computeRegistrarWorklistRows and
 * resolveRegistrarWorklistEmptyScopeKind (single source — no drift):
 * profile queue_tags from the API, fallback to the tabKey itself
 * (⚠️ TEMPORARY ADAPTER for backwards compatibility during transition).
 */
const getQueueTagsForTabKey = (tabKey: string, queueProfiles: QueueProfileItem[]): string[] => {
  if (!tabKey) return [];

  const profile = queueProfiles.find((p) => p.key === tabKey);
  if (profile && profile.queue_tags && profile.queue_tags.length > 0) {
    return profile.queue_tags;
  }

  return [tabKey];
};

/** Normalized queue-tag value of a worklist entry (same normalization as rows). */
const appointmentQueueTagValue = (entry: Appointment): string => (
  entry.queue_tag ||
  entry.specialty ||
  entry.queue_numbers && entry.queue_numbers[0]?.queue_tag ||
  '').
  toString().toLowerCase().trim();

export const computeRegistrarWorklistRows = ({
  appointments,
  activeTab,
  activeDoctorId = null,
  statusFilter,
  searchQuery,
  queueProfiles,
  services,
  fallbackPatientLabel,
}: {
  appointments: Appointment[];
  activeTab: string | null;
  activeDoctorId?: number | null;
  statusFilter: string | null;
  searchQuery: string;
  queueProfiles: QueueProfileItem[];
  services: Record<string, unknown>;
  fallbackPatientLabel: string;
}): Record<string, unknown>[] => {
  // Если выбрана конкретная вкладка (не "Все отделения"), используем appointments с фильтрацией по queue_tag
  if (activeTab || activeDoctorId != null) {
    // ⭐ SSOT: queue_tags from API profiles, not hardcoded
    const possibleTags = activeDoctorId == null ? getQueueTagsForTabKey(activeTab as string, queueProfiles) : [];

    // Фильтруем appointments по queue_tag вкладки
    const entriesForTab = (appointments).filter((entry) => {
      // Определяем queue_tag записи
      const entryQueueTag = appointmentQueueTagValue(entry);

      // Проверяем соответствие вкладке
      const matchesTab = activeDoctorId != null
        ? belongsToDoctor(entry, activeDoctorId)
        : possibleTags.some((tag: string) => tag.toLowerCase() === entryQueueTag);
      if (!matchesTab) return false;

      // Фильтр по статусу
      if (statusFilter && entry.status !== statusFilter) return false;

      // Фильтр по поиску
      if (searchQuery) {
        const inFio = (entry.patient_fio || entry.patient_name || '').toLowerCase().includes(searchQuery);
        const inId = String(entry.id).includes(searchQuery);
        const phoneDigits = String(entry.patient_phone || entry.phone || '').replace(/\D/g, '');
        const searchDigits = searchQuery.replace(/\D/g, '');
        // RQ-02: the phone branch participates only when the query has digits.
        // Previously a letter-only query produced searchDigits='' and
        // phoneDigits.includes('') === true, so inPhone passed for EVERY row
        // and letter search never filtered (F-01).
        const inPhone = searchDigits.length > 0 && phoneDigits.includes(searchDigits);
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

        const inPhone = searchDigits.length > 0 && (
        originalPhone.includes(searchQuery) ||
        phoneDigits.includes(searchDigits) ||
        searchDigits.length >= 3 && phoneDigits.includes(searchDigits));

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

/**
 * RQ-21.a (F-17): scope fact for the worklist empty state.
 *
 * 'queue-empty' — the loaded date scope itself holds zero entries for the
 * active tab (specific tab: no appointment matches the tab's queue_tags;
 * "all departments": no appointments loaded at all). A "no matches" message
 * here would wrongly imply there was something to match.
 *
 * 'filtered-empty' — the scope holds entries, so when the final rows are
 * empty the cause is the active narrowing (status filter / search query).
 * Presenting that as "queue is empty" was the F-17 defect: a failed search
 * looked like an empty queue and invited a duplicate appointment.
 *
 * Contract: the caller combines this fact with its own
 * `filteredAppointments.length === 0` render condition (the empty state is
 * reached only then). This helper intentionally does NOT re-run the search
 * predicate — duplicating it would drift against computeRegistrarWorklistRows;
 * the scope fact above is exactly what the two states need to differ.
 */
export type RegistrarWorklistEmptyScopeKind = 'queue-empty' | 'filtered-empty';

export const resolveRegistrarWorklistEmptyScopeKind = ({
  appointments,
  activeTab,
  activeDoctorId = null,
  queueProfiles,
}: {
  appointments: Appointment[];
  activeTab: string | null;
  activeDoctorId?: number | null;
  queueProfiles: QueueProfileItem[];
}): RegistrarWorklistEmptyScopeKind => {
  // "All departments": every loaded appointment is in scope; aggregation
  // never loses patients, so any entry means zero rows can only be narrowing.
  if (!activeTab && activeDoctorId == null) {
    return appointments.length === 0 ? 'queue-empty' : 'filtered-empty';
  }

  // Specific tab: same SSOT tag resolution and entry normalization as rows.
  const possibleTags = activeDoctorId == null ? getQueueTagsForTabKey(activeTab as string, queueProfiles) : [];
  const scopeHasEntries = appointments.some((entry) => activeDoctorId != null
    ? belongsToDoctor(entry, activeDoctorId)
    : possibleTags.some((tag: string) => tag.toLowerCase() === appointmentQueueTagValue(entry)));

  return scopeHasEntries ? 'filtered-empty' : 'queue-empty';
};

/**
 * RQ-21.b (D-07 APPROVED): signed-counter facts for the worklist counters.
 *
 * The worklist has TWO row kinds that must never share one counter label:
 * - a specific tab lists individual queue ENTRIES → unit «записей» (records);
 * - the "all departments" tab lists AGGREGATED PATIENTS → unit «пациентов».
 *   Calling patients «записи» was the D-07 unit-mixing defect (the old
 *   `${length} tabs_appointments` label served both surfaces).
 *
 * The descriptor is derived from the SAME data the list under the counter
 * uses (SSOT helpers above — one source, no drift when the date/filter
 * changes): `count` is the displayed rows; `scopeCount` is the loaded
 * day+tab scope BEFORE status/search narrowing; `narrowed` (count <
 * scopeCount) makes the UI say «показано N из M» instead of presenting a
 * narrowed sample as the whole queue (same family of honesty as RQ-21.a);
 * `loadedPage` mirrors paginationInfo.hasMore so a PAGE of rows is never
 * presented as the total (the registrar/queues/today contract returns the
 * full day today — the flag is structural honesty for future paging).
 */
export type RegistrarWorklistCounterUnit = 'records' | 'patients';

export interface RegistrarWorklistCounterDescriptor {
  unit: RegistrarWorklistCounterUnit;
  /** Rows the list under the counter shows (after status/search narrowing). */
  count: number;
  /** Loaded day+tab scope rows BEFORE narrowing (honest «из M» denominator). */
  scopeCount: number;
  /** True when narrowing reduced the scope (status filter / search query). */
  narrowed: boolean;
  /** True when the loaded sample is a page (hasMore), not the full scope. */
  loadedPage: boolean;
}

export const describeRegistrarWorklistCounter = ({
  appointments,
  activeTab,
  activeDoctorId = null,
  queueProfiles,
  rows,
  hasMore,
}: {
  appointments: Appointment[];
  activeTab: string | null;
  activeDoctorId?: number | null;
  queueProfiles: QueueProfileItem[];
  rows: Record<string, unknown>[];
  hasMore: boolean;
}): RegistrarWorklistCounterDescriptor => {
  if (!activeTab && activeDoctorId == null) {
    // All-departments: the scope is the AGGREGATED PATIENT count of the
    // loaded day (aggregation cannot lose patients — RQ-21.a note), taken
    // BEFORE the status/search narrowing the rows already embody.
    const scopeCount = aggregateRegistrarPatients(
      appointments as Record<string, unknown>[],
    ).length;
    return {
      unit: 'patients',
      count: rows.length,
      scopeCount,
      narrowed: rows.length < scopeCount,
      loadedPage: hasMore,
    };
  }

  // Specific tab: same SSOT tag resolution as rows/emptyScopeKind — the
  // scope is every entry matching the tab's queue_tags, before narrowing.
  const possibleTags = activeDoctorId == null ? getQueueTagsForTabKey(activeTab as string, queueProfiles) : [];
  const scopeCount = appointments.filter((entry) => activeDoctorId != null
    ? belongsToDoctor(entry, activeDoctorId)
    : possibleTags.some((tag: string) => tag.toLowerCase() === appointmentQueueTagValue(entry)),
  ).length;
  return {
    unit: 'records',
    count: rows.length,
    scopeCount,
    narrowed: rows.length < scopeCount,
    loadedPage: hasMore,
  };
};

/**
 * RQ-21.b (D-07): compose the signed counter string for BOTH worklist
 * counter surfaces (header meta line + status badge) — one formatter, no
 * drift. The unit word is pluralized by i18next from the count it agrees
 * with: the displayed count on the plain form, the SCOPE count on the
 * narrowed form («показано 3 из 50 записей» — the unit belongs to 50).
 */
export const formatRegistrarWorklistCounter = (
  t: (key: string, options?: Record<string, unknown>) => string,
  d: RegistrarWorklistCounterDescriptor,
): string => {
  const unitWord = d.unit === 'records'
    ? t('registrarPanel.rp_counter_records', { count: d.narrowed ? d.scopeCount : d.count })
    : t('registrarPanel.rp_counter_patients', { count: d.narrowed ? d.scopeCount : d.count });
  const head = d.narrowed
    ? t('registrarPanel.rp_counter_shown_of', { shown: d.count, scope: d.scopeCount, unit: unitWord })
    : `${d.count} ${unitWord}`;
  return d.loadedPage ? `${t('registrarPanel.rp_counter_loaded')} ${head}` : head;
};

/**
 * RQ-21.b (D-07): one SSOT call for BOTH worklist presentation facts — the
 * empty-scope kind (RQ-21.a) and the signed counter (above) — so the panel
 * computes them from the SAME data in ONE place (no drift, no extra panel
 * LOC beyond the plan §PR-UI-13 size pin).
 */
export const resolveRegistrarWorklistPresentationFacts = ({
  appointments,
  activeTab,
  activeDoctorId = null,
  queueProfiles,
  rows,
  hasMore,
}: {
  appointments: Appointment[];
  activeTab: string | null;
  activeDoctorId?: number | null;
  queueProfiles: QueueProfileItem[];
  rows: Record<string, unknown>[];
  hasMore: boolean;
}): {
  emptyScopeKind: RegistrarWorklistEmptyScopeKind;
  counter: RegistrarWorklistCounterDescriptor;
} => ({
  emptyScopeKind: resolveRegistrarWorklistEmptyScopeKind({ appointments, activeTab, activeDoctorId, queueProfiles }),
  counter: describeRegistrarWorklistCounter({ appointments, activeTab, activeDoctorId, queueProfiles, rows, hasMore }),
});

export default computeRegistrarWorklistRows;
