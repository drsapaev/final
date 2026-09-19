/**
 * queueSettingsEffective.ts — SSOT types + normalizer for the effective
 * queue-settings report (RQ-23.ui, S-20; backend RQ-23.a, PR 3289, E-050).
 *
 * The backend endpoint `GET /admin/queue/settings/effective` is a pure
 * read-model over existing rows (D-06 APPROVED owner wording): every
 * managed setting carries a source level (clinic → department → owner →
 * day snapshot), a live flag ("does the runtime read this at all?"),
 * applied-when codes, and an honest note for dead fields (F-19: the
 * DepartmentQueueSettings block except queue_prefix; the clinic
 * auto_close_time display-only field).
 *
 * This module is presentation-agnostic: types + defensive parsing +
 * i18n key maps. The React panel in QueueSettings.tsx consumes it.
 */

export interface EffectiveField {
  field: string;
  level: string;
  value: unknown;
  live: boolean;
  applied_when: string[];
  runtime_consumers: string[];
  snapshot_field: string | null;
  note: string | null;
}

export interface OwnerOverride {
  doctor_id: number;
  specialty: string | null;
  active: boolean;
  start_number_online: number;
  max_online_per_day: number;
  effective_start_number: number;
  source: string;
}

export interface DepartmentQueueSettingsStatus {
  value: unknown;
  live: boolean;
  runtime_consumers: string[];
  note: string | null;
}

export interface DepartmentReport {
  department_id: number;
  key: string;
  name_ru: string | null;
  active: boolean;
  queue_settings: Record<string, DepartmentQueueSettingsStatus>;
  owner_overrides: OwnerOverride[];
}

export interface ResourceRow {
  queue_resource_id: number;
  code: string;
  display_name: string | null;
  start_number_online: number;
  max_online_per_day: number;
  effective_start_number: number;
  source: string;
}

export interface ActiveDayRow {
  daily_queue_id: number;
  day: string;
  specialist_id: number | null;
  queue_resource_id: number | null;
  queue_tag: string | null;
  active: boolean;
  opened_at: string | null;
  start_number: number;
  online_start_time: string | null;
  online_end_time: string | null;
  max_online_entries: number;
  source: string;
  note: string | null;
}

export interface EffectiveQueueSettingsReport {
  timezone: string;
  clinic_today: string;
  chain_order: string[];
  clinic_settings: Record<string, unknown>;
  fields: EffectiveField[];
  department: DepartmentReport | null;
  resources: ResourceRow[];
  active_day: ActiveDayRow[];
}

/** Source level code → i18n key (admin2.qs_eff_source_*). */
export const SOURCE_LEVEL_KEYS: Record<string, string> = {
  clinic: 'admin2.qs_eff_source_clinic',
  department: 'admin2.qs_eff_source_department',
  owner: 'admin2.qs_eff_source_owner',
  registry: 'admin2.qs_eff_source_registry',
  day_snapshot: 'admin2.qs_eff_source_day',
};

/** Applied-when code → i18n key (admin2.qs_eff_applied_*). */
export const APPLIED_WHEN_KEYS: Record<string, string> = {
  immediate: 'admin2.qs_eff_applied_immediate',
  day_creation_snapshot: 'admin2.qs_eff_applied_day_creation',
};

const asRecord = (value: unknown): Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};

const asArray = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

const asString = (value: unknown): string | null =>
  typeof value === 'string' ? value : null;

const asNumber = (value: unknown): number =>
  typeof value === 'number' && Number.isFinite(value) ? value : 0;

const parseField = (raw: unknown): EffectiveField | null => {
  const rec = asRecord(raw);
  const field = asString(rec.field);
  if (!field) return null;
  return {
    field,
    level: asString(rec.level) ?? 'clinic',
    value: rec.value ?? null,
    live: rec.live === true,
    applied_when: asArray(rec.applied_when).filter(
      (code): code is string => typeof code === 'string',
    ),
    runtime_consumers: asArray(rec.runtime_consumers).filter(
      (code): code is string => typeof code === 'string',
    ),
    snapshot_field: asString(rec.snapshot_field),
    note: asString(rec.note),
  };
};

const parseOwnerOverride = (raw: unknown): OwnerOverride | null => {
  const rec = asRecord(raw);
  const doctorId = asNumber(rec.doctor_id);
  if (!doctorId) return null;
  return {
    doctor_id: doctorId,
    specialty: asString(rec.specialty),
    active: rec.active !== false,
    start_number_online: asNumber(rec.start_number_online),
    max_online_per_day: asNumber(rec.max_online_per_day),
    effective_start_number: asNumber(rec.effective_start_number),
    source: asString(rec.source) ?? 'clinic',
  };
};

const parseDepartmentReport = (raw: unknown): DepartmentReport | null => {
  if (raw === null || raw === undefined) return null;
  const rec = asRecord(raw);
  const departmentId = asNumber(rec.department_id);
  if (!departmentId) return null;
  const queueSettingsRaw = asRecord(rec.queue_settings);
  const queueSettings: Record<string, DepartmentQueueSettingsStatus> = {};
  for (const [fieldName, statusRaw] of Object.entries(queueSettingsRaw)) {
    const status = asRecord(statusRaw);
    queueSettings[fieldName] = {
      value: status.value ?? null,
      live: status.live === true,
      runtime_consumers: asArray(status.runtime_consumers).filter(
        (code): code is string => typeof code === 'string',
      ),
      note: asString(status.note),
    };
  }
  return {
    department_id: departmentId,
    key: asString(rec.key) ?? '',
    name_ru: asString(rec.name_ru),
    active: rec.active !== false,
    queue_settings: queueSettings,
    owner_overrides: asArray(rec.owner_overrides)
      .map(parseOwnerOverride)
      .filter((row): row is OwnerOverride => row !== null),
  };
};

const parseResourceRow = (raw: unknown): ResourceRow | null => {
  const rec = asRecord(raw);
  const resourceId = asNumber(rec.queue_resource_id);
  if (!resourceId) return null;
  return {
    queue_resource_id: resourceId,
    code: asString(rec.code) ?? '',
    display_name: asString(rec.display_name),
    start_number_online: asNumber(rec.start_number_online),
    max_online_per_day: asNumber(rec.max_online_per_day),
    effective_start_number: asNumber(rec.effective_start_number),
    source: asString(rec.source) ?? 'registry',
  };
};

const parseActiveDayRow = (raw: unknown): ActiveDayRow | null => {
  const rec = asRecord(raw);
  const dailyQueueId = asNumber(rec.daily_queue_id);
  if (!dailyQueueId) return null;
  return {
    daily_queue_id: dailyQueueId,
    day: asString(rec.day) ?? '',
    specialist_id: typeof rec.specialist_id === 'number' ? rec.specialist_id : null,
    queue_resource_id:
      typeof rec.queue_resource_id === 'number' ? rec.queue_resource_id : null,
    queue_tag: asString(rec.queue_tag),
    active: rec.active !== false,
    opened_at: asString(rec.opened_at),
    start_number: asNumber(rec.start_number) || 1,
    online_start_time: asString(rec.online_start_time),
    online_end_time: asString(rec.online_end_time),
    max_online_entries: asNumber(rec.max_online_entries),
    source: asString(rec.source) ?? 'day_snapshot',
    note: asString(rec.note),
  };
};

const EMPTY_REPORT: EffectiveQueueSettingsReport = {
  timezone: '',
  clinic_today: '',
  chain_order: [],
  clinic_settings: {},
  fields: [],
  department: null,
  resources: [],
  active_day: [],
};

/**
 * Defensive parse of the raw API payload: malformed shapes degrade to an
 * honest empty report instead of crashing the settings panel.
 */
export const parseEffectiveQueueSettingsReport = (
  raw: unknown,
): EffectiveQueueSettingsReport => {
  if (raw === null || raw === undefined || typeof raw !== 'object') {
    return { ...EMPTY_REPORT };
  }
  const rec = asRecord(raw);
  return {
    timezone: asString(rec.timezone) ?? '',
    clinic_today: asString(rec.clinic_today) ?? '',
    chain_order: asArray(rec.chain_order).filter(
      (code): code is string => typeof code === 'string',
    ),
    clinic_settings: asRecord(rec.clinic_settings),
    fields: asArray(rec.fields)
      .map(parseField)
      .filter((row): row is EffectiveField => row !== null),
    department: parseDepartmentReport(rec.department),
    resources: asArray(rec.resources)
      .map(parseResourceRow)
      .filter((row): row is ResourceRow => row !== null),
    active_day: asArray(rec.active_day)
      .map(parseActiveDayRow)
      .filter((row): row is ActiveDayRow => row !== null),
  };
};

/** Builds the report URL with explicit query parameters (no body, no merge). */
export const buildEffectiveReportUrl = (
  scope: { departmentId?: number | null; tag?: string | null },
): string => {
  const params: string[] = [];
  if (scope.departmentId != null) params.push(`department_id=${scope.departmentId}`);
  if (scope.tag) params.push(`tag=${encodeURIComponent(scope.tag)}`);
  const base = '/admin/queue/settings/effective';
  return params.length ? `${base}?${params.join('&')}` : base;
};
