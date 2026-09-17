import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import type { CSSProperties } from 'react';
import type { LucideIcon } from 'lucide-react';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import {
  Clock,
  Users,
  Hash,
  Settings,
  Save,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  TestTube,
  Heart,
  Scissors,
  Stethoscope,
  QrCode,
  Play,
  Sparkles,
  Smile,
  Activity,
  Package,
  Zap,
  Layers,
  ToggleLeft,
  ToggleRight } from
'lucide-react';
import {
  Card,
  Button,
  Input,
  Select,
} from '../ui/macos';
import type { SelectChangeEvent } from '../ui/macos/Select';
import {
  parseEffectiveQueueSettingsReport,
  buildEffectiveReportUrl,
  SOURCE_LEVEL_KEYS,
  APPLIED_WHEN_KEYS,
} from '../../utils/queueSettingsEffective';
import type {
  EffectiveQueueSettingsReport,
  EffectiveField,
  DepartmentQueueSettingsStatus,
  OwnerOverride,
  ResourceRow,
  ActiveDayRow,
} from '../../utils/queueSettingsEffective';

type TranslationFn = (key: string, options?: Record<string, unknown>) => string;

// Local doctor-list shape for the queue-settings dropdown. Named `DoctorRecord`
// to avoid shadowing the canonical `Doctor` domain type in @/types/domain/clinic.
interface DoctorRecord {
  id?: number;
  active?: boolean;
  cabinet?: string;
  specialty?: string;
  user?: {
    full_name?: string;
    username?: string;
  };
}

// Local queue-profile shape returned by /admin/queue/profiles. Named `QueueProfileDto`
// because `QueueProfile` and `QueueProfilesResponse` are canonical domain types
// in @/types/domain/queue.
interface QueueProfileDto {
  key: string;
  title_ru?: string;
  title?: string;
  icon?: string;
  color?: string;
  queue_tags?: string[];
  // PR 3291 P2-3: archived profiles are loaded too (active_only=false) so
  // the report tag scope can address frozen day rows of deactivated
  // directions (D-06); is_active === false keeps them out of edit cards.
  is_active?: boolean;
  // D-1: canonical clinic_settings segment for this profile's
  // start_number_*/max_per_day_* rows (backend-computed via
  // core/specialties.canonical_specialty). The profile key itself may
  // stay a legacy machinery value ("stomatology") while the settings
  // rows live under the canonical "dentistry" after migration 0049.
  settings_key?: string;
}

interface Specialty {
  key: string;
  name: string;
  icon: LucideIcon;
  color: string;
  description: string;
  tags: string[];
  // Settings reads AND edits use this key, never `key` (Codex round-3 P1).
  settingsKey: string;
}

interface QueueSettingsState {
  timezone: string;
  queue_start_hour: number;
  auto_close_time: string;
  start_numbers: Record<string, number>;
  max_per_day: Record<string, number>;
  dev_mode_enabled: boolean;
}

interface TestResult {
  token?: string;
  selected_doctor_id?: number;
  selected_doctor_name?: string;
  selected_doctor_cabinet?: string;
  doctor_id?: number;
  doctor_specialty?: string;
  doctor_cabinet?: string;
  start_number?: number;
  max_per_day?: number;
  matched_doctors_count?: number;
  qr_url?: string;
}

const ICON_MAP: Record<string, LucideIcon> = {
  'Heart': Heart,
  'Activity': Activity,
  'Sparkles': Sparkles,
  'Smile': Smile,
  'TestTube': TestTube,
  'Stethoscope': Stethoscope,
  'Users': Users,
  'Package': Package,
  'Scissors': Scissors,
  'Zap': Zap
};

const TIMEZONE_OPTIONS = [
  { value: 'Asia/Tashkent', labelKey: 'admin2.qs_tz_tashkent' },
  { value: 'Asia/Almaty', labelKey: 'admin2.qs_tz_almaty' },
  { value: 'Europe/Moscow', labelKey: 'admin2.qs_tz_moscow' },
  { value: 'Asia/Dubai', labelKey: 'admin2.qs_tz_dubai' }
];

const normalizeNumber = (value: unknown, fallback: number): number => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const getNumberSetting = (
  collection: Record<string, unknown> | null | undefined,
  key: string,
  fallback: number
): number => normalizeNumber(collection?.[key], fallback);

const normalizeText = (value: unknown): string => String(value ?? '').trim().toLowerCase();

// RQ-23.ui (S-20): display names for report fields; unknown fields fall
// back to the raw backend name (honest fallback, never invented labels).
const EFFECTIVE_FIELD_NAME_KEYS: Record<string, string> = {
  timezone: 'admin2.qs_eff_field_timezone',
  queue_start_hour: 'admin2.qs_eff_field_queue_start_hour',
  auto_close_time: 'admin2.qs_eff_field_auto_close_time',
  start_numbers: 'admin2.qs_eff_field_start_numbers',
  max_per_day: 'admin2.qs_eff_field_max_per_day',
};

const DEPARTMENT_FIELD_NAME_KEYS: Record<string, string> = {
  enabled: 'admin2.qs_eff_dept_field_enabled',
  queue_type: 'admin2.qs_eff_dept_field_queue_type',
  queue_prefix: 'admin2.qs_eff_dept_field_queue_prefix',
  max_daily_queue: 'admin2.qs_eff_dept_field_max_daily_queue',
  max_concurrent_queue: 'admin2.qs_eff_dept_field_max_concurrent_queue',
  avg_wait_time: 'admin2.qs_eff_dept_field_avg_wait_time',
  show_on_display: 'admin2.qs_eff_dept_field_show_on_display',
  auto_close_time: 'admin2.qs_eff_dept_field_auto_close_time',
};

const formatReportValue = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    if (!entries.length) return '—';
    return entries.map(([key, entryValue]) => `${key}: ${String(entryValue)}`).join(', ');
  }
  return String(value);
};

const getDoctorDisplayName = (doctor: DoctorRecord | null | undefined, t: TranslationFn): string => (
  doctor?.user?.full_name || doctor?.user?.username || t('admin2.qs_doctor_fallback', { id: doctor?.id ?? '—' })
);

const pickCanonicalDoctorForSpecialty = (
  doctorsList: DoctorRecord[] | null | undefined,
  specialtyKey: string,
  queueTags?: string[]
): { doctor: DoctorRecord | null; candidates: DoctorRecord[] } => {
  // D-1 canonical vocabulary: a doctor's stored specialty is canonical
  // ('dentistry') while the queue profile key keeps its machinery value
  // ('stomatology') — match against the profile key AND its queue_tags
  // (which carry every accepted family spelling) instead of the key alone.
  const accepted = new Set<string>([normalizeText(specialtyKey)]);
  for (const tag of Array.isArray(queueTags) ? queueTags : []) {
    const normalizedTag = normalizeText(tag);
    if (normalizedTag) {
      accepted.add(normalizedTag);
    }
  }
  const candidates = (Array.isArray(doctorsList) ? doctorsList : [])
    .filter((doctor) => accepted.has(normalizeText(doctor?.specialty)))
    .sort((left, right) => {
      const leftScore = [
        left?.active === false ? 1 : 0,
        left?.user ? 0 : 1,
        left?.cabinet ? 0 : 1,
        normalizeNumber(left?.id, Number.MAX_SAFE_INTEGER),
      ];
      const rightScore = [
        right?.active === false ? 1 : 0,
        right?.user ? 0 : 1,
        right?.cabinet ? 0 : 1,
        normalizeNumber(right?.id, Number.MAX_SAFE_INTEGER),
      ];

      for (let index = 0; index < leftScore.length; index += 1) {
        if (leftScore[index] !== rightScore[index]) {
          return leftScore[index] - rightScore[index];
        }
      }

      return 0;
    });

  return {
    doctor: candidates[0] ?? null,
    candidates,
  };
};

const QueueSettings = () => {
  const { t: rawT, language } = useTranslation();
  const t = rawT;
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [settings, setSettings] = useState<QueueSettingsState>({
    timezone: 'Asia/Tashkent',
    queue_start_hour: 7,
    auto_close_time: '09:00',
    start_numbers: {},
    max_per_day: {},
    dev_mode_enabled: false
  });
  const [message, setMessage] = useState<{ type: string; text: string }>({ type: '', text: '' });
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  // RQ-23.ui (S-20): effective settings report — read-only SSOT view over
  // GET /admin/queue/settings/effective (backend RQ-23.a, PR 3289, E-050).
  const [departmentsList, setDepartmentsList] = useState<{ id: number; key: string; name_ru: string | null }[]>([]);
  const [reportScope, setReportScope] = useState<{ departmentId: number | null; tag: string | null }>({ departmentId: null, tag: null });
  const [effectiveReport, setEffectiveReport] = useState<EffectiveQueueSettingsReport | null>(null);
  // PR 3291 P2-1: monotonic request sequence — a stale report response
  // that resolves after a newer scope request must never overwrite it.
  const reportRequestSeq = useRef(0);
  const [reportLoading, setReportLoading] = useState(true);
  const [reportError, setReportError] = useState(false);

  // ⭐ SSOT: Загружаем профили (включая архив — PR 3291 P2-3) и врачей
  const [profilesAll, setProfilesAll] = useState<QueueProfileDto[]>([]);
  const [doctors, setDoctors] = useState<DoctorRecord[]>([]);

  // Загрузка профилей и докторов
  const loadProfiles = useCallback(async () => {
    try {
      const [profilesRes, doctorsRes] = await Promise.all([
      // PR 3291 P2-3: активный фильтр применяется на клиенте — архив
      // нужен тег-селектору отчёта (замороженные дни архивных
      // направлений продолжают существовать по D-06).
      api.get('/queues/profiles?active_only=false'),
      api.get('/admin/doctors').catch(() => ({ data: [] }))]
      );

      const profilesRaw = (profilesRes.data?.profiles ?? []) as QueueProfileDto[];
      setProfilesAll(profilesRaw);

      const doctorsData = (doctorsRes.data ?? []) as DoctorRecord[];
      setDoctors(doctorsData);

      logger.info(`Loaded ${profilesRaw.length} queue profiles and ${doctorsData.length} doctors`);
    } catch (error) {
      logger.error('Error loading profiles:', error);
      // Не устанавливаем fallback данные - показываем пустой список
    }
  }, []);

  const loadDepartments = useCallback(async () => {
    try {
      const response = await api.get('/admin/departments');
      // PR 3291 P1: production endpoint answers the envelope
      // { success, data, count } (admin_departments list_departments).
      // Bare arrays and legacy { departments: [...] } shapes are kept for
      // older backends and fixtures.
      const payload = response.data as unknown;
      const payloadRecord = (typeof payload === 'object' && payload !== null ? payload : {}) as Record<string, unknown>;
      const raw = (Array.isArray(payload)
        ? payload
        : Array.isArray(payloadRecord.data)
          ? payloadRecord.data
          : Array.isArray(payloadRecord.departments)
            ? payloadRecord.departments
            : []) as Array<Record<string, unknown>>;
      setDepartmentsList(
        raw
          .map((dept) => ({ id: Number(dept?.id), key: String(dept?.key ?? ''), name_ru: typeof dept?.name_ru === 'string' ? dept.name_ru : null }))
          .filter((dept) => Number.isFinite(dept.id) && dept.id > 0),
      );
    } catch (error) {
      logger.error('Ошибка загрузки отделений для отчёта:', error);
      setDepartmentsList([]);
    }
  }, []);

  const loadEffectiveReport = useCallback(async (scope: { departmentId: number | null; tag: string | null }) => {
    // PR 3291 P2-1: request-sequence guard — только самый свежий запрос
    // имеет право менять состояние отчёта (данные/loading/error).
    const seq = reportRequestSeq.current + 1;
    reportRequestSeq.current = seq;
    try {
      setReportLoading(true);
      setReportError(false);
      const response = await api.get(buildEffectiveReportUrl(scope));
      if (seq !== reportRequestSeq.current) return;
      setEffectiveReport(parseEffectiveQueueSettingsReport(response.data));
    } catch (error) {
      logger.error('Ошибка загрузки отчёта эффективных настроек:', error);
      if (seq !== reportRequestSeq.current) return;
      setEffectiveReport(null);
      setReportError(true);
    } finally {
      if (seq === reportRequestSeq.current) {
        setReportLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadProfiles();
    loadSettings();
    loadDepartments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadProfiles, loadDepartments]);

  useEffect(() => {
    loadEffectiveReport(reportScope);
  }, [reportScope, loadEffectiveReport]);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/queue/settings');
      const data = (response.data ?? {}) as Partial<QueueSettingsState> & Record<string, unknown>;
      setSettings({
        timezone: data.timezone || 'Asia/Tashkent',
        queue_start_hour: normalizeNumber(data.queue_start_hour, 7),
        auto_close_time: data.auto_close_time || '09:00',
        start_numbers: (data.start_numbers as Record<string, number>) || {},
        max_per_day: (data.max_per_day as Record<string, number>) || {},
        dev_mode_enabled: Boolean(data.dev_mode_enabled),
      });
    } catch (error) {
      logger.error('Ошибка загрузки настроек очередей:', error);
      setMessage({ type: 'error', text: t('admin2.qs_load_error') });
    } finally {
      setLoading(false);
    }
  };

  // Активные профили — карточки настроек и тестирование (редактирование
  // остаётся active-only, PR 3291 P2-3).
  const specialties = useMemo<Specialty[]>(() => profilesAll
    .filter((profile) => profile.is_active !== false)
    .map((p) => ({
      key: p.key,
      name: p.title_ru || p.title || p.key,
      icon: ICON_MAP[p.icon ?? ''] || Stethoscope,
      color: p.color || 'var(--mac-text-primary)',
      description: (p.queue_tags || []).join(', '),
      tags: p.queue_tags || [],
      // D-1: settings rows are keyed by the canonical specialty
      // ("dentistry"), not by the profile machinery key
      // ("stomatology"). Fall back to the key for older backends.
      settingsKey: p.settings_key || p.key,
    })), [profilesAll]);

  // Unique queue tags across ALL loaded profiles (включая архивные) —
  // tag scope отчёта должен видеть замороженные дни архивных направлений
  // (PR 3291 P2-3, D-06).
  const tagOptions = useMemo(() => {
    const tags = new Set<string>();
    for (const profile of profilesAll) {
      for (const tag of profile.queue_tags || []) {
        if (tag) tags.add(tag);
      }
    }
    return Array.from(tags).sort();
  }, [profilesAll]);

  const getDoctorNameForReport = (doctorId: number): string => {
    const doctor = doctors.find((candidate) => Number(candidate?.id) === Number(doctorId)) ?? null;
    if (doctor) return getDoctorDisplayName(doctor, t);
    return t('admin2.qs_doctor_fallback', { id: doctorId });
  };

  const handleSettingChange = (path: string, value: unknown) => {
    setSettings((prev) => {
      const newSettings: QueueSettingsState = { ...prev };
      const keys = path.split('.');
      const topKey = keys[0] as keyof QueueSettingsState;
      const newSettingsRecord = newSettings as unknown as Record<string, unknown>;

      if (keys.length === 1) {
        newSettingsRecord[topKey] = value;
      } else if (keys.length === 2) {
        const nested = newSettingsRecord[topKey];
        const nestedRecord = (typeof nested === 'object' && nested !== null ? nested : {}) as Record<string, unknown>;
        newSettingsRecord[topKey] = { ...nestedRecord, [keys[1]]: value };
      }

      return newSettings;
    });
  };

  const saveSettings = async () => {
    try {
      setSaving(true);
      setMessage({ type: '', text: '' });

      const response = await api.put('/admin/queue/settings', settings);
      const data = response.data as { message?: string; settings?: QueueSettingsState };
      setMessage({ type: 'success', text: data.message ?? '' });
      if (data.settings) {
        setSettings(data.settings);
      }
      // PR 3291 P2-2: сохранённые строки клиники входят в отчёт
      // эффективных значений (start_numbers / max_per_day) — перечитываем,
      // чтобы рядом с «сохранено» не оставалось устаревшее effective-значение.
      loadEffectiveReport(reportScope);
    } catch (error) {
      logger.error('Ошибка сохранения:', error);
      setMessage({ type: 'error', text: t('admin2.qs_save_error') });
    } finally {
      setSaving(false);
    }
  };

  const testQueueGeneration = async (specialty: Specialty) => {
    try {
      setTesting(true);
      setTestResult(null);

      // ⭐ SSOT: Выбираем врача детерминированно среди докторов этой специальности.
      const { doctor, candidates } = pickCanonicalDoctorForSpecialty(doctors, specialty.key, specialty.tags);

      if (!doctor || !doctor.id) {
        setMessage({ type: 'error', text: t('admin2.qs_doctor_not_found', { specialty: specialty.name }) });
        setTesting(false);
        return;
      }

      const response = await api.post('/admin/queue/test', {
        doctor_id: doctor.id,
        date: new Date().toISOString().split('T')[0]
      });

      const testData = ((response.data?.test_data ?? {}) as Partial<TestResult>);
      setTestResult({
        ...testData,
        selected_doctor_id: doctor.id,
        selected_doctor_name: getDoctorDisplayName(doctor, t),
        selected_doctor_cabinet: doctor.cabinet || t('admin2.qs_not_specified'),
        matched_doctors_count: candidates.length,
      });
      setMessage({
        type: 'success',
        text:
          candidates.length > 1
            ? t('admin2.qs_test_done_multi', { doctor: getDoctorDisplayName(doctor, t), count: candidates.length })
            : t('admin2.qs_test_done'),
      });
    } catch (error) {
      logger.error('Ошибка тестирования:', error);
      setMessage({ type: 'error', text: t('admin2.qs_test_error') });
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="admin-outer-container-p-0">
        <Card className="admin-card-p-0-text-center">
          <div className="admin-flex-center-justify admin-gap-12">
            <RefreshCw className="admin-icon-32-blue-spin" />
            <span className="admin-span-lg-secondary-med">
              {t('admin2.qs_loading')}
            </span>
          </div>
        </Card>
      </div>);

  }

  return (
    <div className="admin-outer-container-p-0">
      <Card className="p-6">
        {/* Заголовок */}
        <div className="admin-header-flex-between-pb-24-border-bottom">
          <div>
            <h2 className="admin-h1-2xl-semi-primary-mb-8-flex">
              <Clock className="admin-icon-32-blue" />
              {t('admin2.qs_title')}
            </h2>
            <p className="admin-p-sm-secondary-m0">
              {t('admin2.qs_subtitle')}
            </p>
          </div>

          <div className="admin-flex-gap-12">
            <Button
              variant="outline"
              onClick={loadSettings}
              disabled={loading}
              className="admin-action-btn">
              
              <RefreshCw className="w-4 h-4" />
              {t('admin2.qs_refresh')}
            </Button>
            <Button
              onClick={saveSettings}
              disabled={saving}
              className="admin-action-btn-primary">
              
              {saving ?
              <RefreshCw className="admin-icon-16-spin" /> :

              <Save className="w-4 h-4" />
              }
              {t('admin2.qs_save')}
            </Button>
          </div>
        </div>

        {/* Сообщения */}
        {message.text &&
        <Card
          className="admin-dynamic-banner-p-16 mb-6"
          style={{
            '--admin-banner-bg': message.type === 'success' ? 'var(--mac-success-bg)' : 'var(--mac-error-bg)',
            '--admin-banner-border': message.type === 'success' ? 'var(--mac-success-border)' : 'var(--mac-error-border)'
          } as CSSProperties}
        >
            <div className="flex items-center justify-center gap-2">
              {message.type === 'success' ?
            <CheckCircle className="admin-icon-20-success" /> :

            <AlertCircle className="admin-icon-20-error" />
            }
              <span
                className="admin-span-sm-med-dynamic-color"
                style={{ '--admin-span-color': message.type === 'success' ? 'var(--mac-success)' : 'var(--mac-error)'  } as CSSProperties}
              >
                {message.text}
              </span>
            </div>
          </Card>
        }

        {/* ⭐ Dev Mode Toggle */}
        <Card
          className="admin-dev-mode-card"
          style={{
            '--admin-card-bg': settings.dev_mode_enabled ? 'var(--mac-error-bg)' : 'var(--mac-bg-secondary)',
            '--admin-card-border': settings.dev_mode_enabled ? 'var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))' : 'var(--mac-border)'
          } as CSSProperties}
        >
          <div className="flex items-center justify-between">
            <div className="admin-flex-center-12">
              <Zap
                className="admin-icon-24-dynamic"
                style={{ '--admin-icon-color': settings.dev_mode_enabled ? 'var(--mac-error)' : 'var(--mac-text-tertiary)'  } as CSSProperties}
              />
              <div>
                <div className="admin-span-sm-semi-primary">
                  {t('admin2.qs_dev_mode_title')}
                </div>
                <div className="admin-text-xs-secondary">
                  {settings.dev_mode_enabled ?
                  t('admin2.qs_dev_mode_on') :
                  t('admin2.qs_dev_mode_off')
                  }
                </div>
              </div>
            </div>
            <button
              onClick={() => handleSettingChange('dev_mode_enabled', !settings.dev_mode_enabled)}
              aria-label={settings.dev_mode_enabled ? t('admin2.qs_dev_mode_disable') : t('admin2.qs_dev_mode_enable')}
              className="admin-dev-mode-btn"
              style={{
                '--admin-btn-bg': settings.dev_mode_enabled ? 'var(--mac-error)' : 'var(--mac-bg-tertiary)',
                '--admin-btn-color': settings.dev_mode_enabled ? 'white' : 'var(--mac-text-primary)'
              } as CSSProperties}>
              
              {settings.dev_mode_enabled ?
              <>
                  <ToggleRight className="w-4.5 h-4.5" />
                  {t('admin2.qs_enabled')}
                </> :

              <>
                  <ToggleLeft className="w-4.5 h-4.5" />
                  {t('admin2.qs_disabled')}
                </>
              }
            </button>
          </div>
        </Card>

        <div className="admin-grid-auto-400-24-mb-24">

          {/* Общие настройки */}
          <Card className="p-6">
            <h3 className="admin-h3-lg-semi-primary-mb-16-flex">
              <Settings className="admin-icon-20-blue" />
              {t('admin2.qs_general')}
            </h3>

            <div className="flex flex-col gap-4">
              <div>
                <label className="admin-label-flex-center-4-sm-med-primary-mb-8">
                  <Clock className="w-4 h-4" />
                  {t('admin2.qs_start_hour')}
                </label>
                <Select
                  value={Number(settings.queue_start_hour)}
                  onChange={(event: SelectChangeEvent) => handleSettingChange('queue_start_hour', parseInt(event.target.value, 10))}
                  options={Array.from({ length: 24 }, (_, i) => ({
                    value: i,
                    label: `${String(i).padStart(2, '0')}:00`
                  }))}
                  className="w-full"></Select>
                
                <p className="admin-p-xs-tertiary-mt-4">
                  {t('admin2.qs_start_hour_hint')}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                  {t('admin2.qs_auto_close')}
                </label>
                <Input
                  type="time"
                  value={settings.auto_close_time}
                  onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleSettingChange('auto_close_time', e.target.value)}
                  className="w-full" />
                
                <p className="admin-p-xs-tertiary-mt-4">
                  {t('admin2.qs_auto_close_hint')}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                  {t('admin2.qs_timezone')}
                </label>
                <Select
                  value={settings.timezone}
                  onChange={(event: SelectChangeEvent) => handleSettingChange('timezone', event.target.value)}
                  options={TIMEZONE_OPTIONS.map((o) => ({ value: o.value, label: t(o.labelKey) }))}
                  className="w-full"></Select>
                
              </div>
            </div>
          </Card>

          {/* Тестирование */}
          <Card className="p-6">
            <h3 className="admin-h3-lg-semi-primary-mb-16-flex">
              <TestTube className="admin-icon-20-success" />
              {t('admin2.qs_testing')}
            </h3>

            <div className="flex flex-col gap-4">
              <p className="admin-p-sm-secondary-m0">
                {t('admin2.qs_testing_hint')}
              </p>

              {specialties.map((specialty) =>
              <div key={specialty.key} className="admin-specialty-test-row">
                  <div className="admin-flex-center-12">
                    <specialty.icon className="admin-icon-20-blue" />
                    <div>
                      <div className="admin-text-sm-med-primary">
                        {specialty.name}
                      </div>
                      <div className="admin-text-xs-secondary">
                        {specialty.description}
                      </div>
                    </div>
                  </div>
                  <Button
                  variant="outline"
                  onClick={() => testQueueGeneration(specialty)}
                  disabled={testing}
                  title={`Test queue generation for ${specialty.name}`}
                  aria-label={`Test queue generation for ${specialty.name}`}
                  className="admin-btn-test-p-6-12-min-w-auto">
                  
                    {testing ?
                  <RefreshCw className="admin-icon-14-spin" /> :

                  <Play className="w-3.5 h-3.5" />
                  }
                  </Button>
                </div>
              )}

              {testResult &&
              <Card className="admin-card-success-p-16">
                  <h4 className="admin-h4-med-success-mb-8">
                    {t('admin2.qs_result_title')}
                  </h4>
                  <div className="admin-div-xs-success-flex-col-4">
                    <div><strong>{t('admin2.qs_label_token')}</strong> <code className="admin-code-success-xs">{testResult.token?.slice(0, 8)}...</code></div>
                    <div><strong>{t('admin2.qs_label_doctor')}</strong> {testResult.selected_doctor_name || '—'}</div>
                    <div><strong>{t('admin2.qs_label_specialty')}</strong> {testResult.doctor_specialty}</div>
                    <div><strong>{t('admin2.qs_label_doctor_id')}</strong> {testResult.selected_doctor_id || testResult.doctor_id}</div>
                    <div><strong>{t('admin2.qs_label_cabinet')}</strong> {testResult.doctor_cabinet}</div>
                    <div><strong>{t('admin2.qs_label_selected_cabinet')}</strong> {testResult.selected_doctor_cabinet || '—'}</div>
                    <div><strong>{t('admin2.qs_label_start_number')}</strong> {testResult.start_number}</div>
                    <div><strong>{t('admin2.qs_label_max_per_day')}</strong> {testResult.max_per_day}</div>
                    <div><strong>{t('admin2.qs_label_candidates')}</strong> {testResult.matched_doctors_count ?? 0}</div>
                    <div><strong>QR URL:</strong> <code className="admin-code-success-xs">{testResult.qr_url}</code></div>
                  </div>
                </Card>
              }
            </div>
          </Card>
        </div>

        {/* Настройки по специальностям */}
        <div className="admin-grid-auto-280-24-mb-24">
          {specialties.map((specialty) =>
          <Card key={specialty.key} className="admin-card-p-20">
              <h3 className="admin-h3-lg-semi-primary-mb-16-flex">
                <specialty.icon className="admin-icon-20-blue" />
                {specialty.name}
              </h3>

              <div className="flex flex-col gap-4">
                <div>
                  <label className="admin-label-flex-center-4-sm-med-primary-mb-8">
                    <Hash className="w-4 h-4" />
                    {t('admin2.qs_label_start_number_short')}
                </label>
                  <Input
                  type="number"
                  min="1"
                  max="100"
                  value={getNumberSetting(settings.start_numbers, specialty.settingsKey, 1)}
                  onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleSettingChange(`start_numbers.${specialty.settingsKey}`, parseInt(e.target.value))}
                  className="w-full" />
                
                  <p className="admin-p-xs-tertiary-mt-4">
                    {t('admin2.qs_start_number_hint')}
                  </p>
                </div>

                <div>
                  <label className="admin-label-flex-center-4-sm-med-primary-mb-8">
                    <Users className="w-4 h-4" />
                    {t('admin2.qs_label_max_per_day_short')}
                </label>
                  <Input
                  type="number"
                  min="1"
                  max="100"
                  value={getNumberSetting(settings.max_per_day, specialty.settingsKey, 1)}
                  onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleSettingChange(`max_per_day.${specialty.settingsKey}`, parseInt(e.target.value))}
                  className="w-full" />
                
                  <p className="admin-p-xs-tertiary-mt-4">
                    {t('admin2.qs_max_per_day_hint')}
                  </p>
                </div>

                {/* Текущие настройки */}
                <div className="admin-section-divider-pt-16-border-top">
                  <div className="admin-flex-between-sm">
                    <span className="text-[var(--mac-text-secondary)]">{t('admin2.qs_range_label')}</span>
                    <div className="admin-range-badge">
                      {getNumberSetting(settings.start_numbers, specialty.settingsKey, 1)} - {getNumberSetting(settings.start_numbers, specialty.settingsKey, 1) + getNumberSetting(settings.max_per_day, specialty.settingsKey, 1) - 1}
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          )}
        </div>

        {/* Эффективные настройки: источник и время применения (RQ-23.ui, S-20, D-06) — read-only */}
        <Card className="p-6 mb-6">
          <section role="region" aria-label={t('admin2.qs_eff_title')}>
            <div className="admin-header-flex-between-pb-24-border-bottom">
              <div>
                <h3 className="admin-h3-lg-semi-primary-mb-16-flex">
                  <Layers className="admin-icon-20-blue" />
                  {t('admin2.qs_eff_title')}
                </h3>
                <p className="admin-p-sm-secondary-m0">
                  {t('admin2.qs_eff_subtitle')}
                </p>
              </div>
              <div className="admin-flex-gap-12-wrap" data-testid="qs-eff-controls">
                <div className="w-56 max-w-full">
                  <Select
                    label={t('admin2.qs_eff_area_department')}
                    value={reportScope.departmentId ?? 'all'}
                    onChange={(event: SelectChangeEvent) => setReportScope((prev) => ({ ...prev, departmentId: event.target.value === 'all' ? null : Number(event.target.value) }))}
                    options={[
                      { value: 'all', label: t('admin2.qs_eff_area_all_departments') },
                      ...departmentsList.map((dept) => ({ value: dept.id, label: dept.name_ru || dept.key })),
                    ]}
                    className="w-full"></Select>
                </div>
                <div className="w-48 max-w-full">
                  <Select
                    label={t('admin2.qs_eff_area_tag')}
                    value={reportScope.tag ?? 'all'}
                    onChange={(event: SelectChangeEvent) => setReportScope((prev) => ({ ...prev, tag: event.target.value === 'all' ? null : String(event.target.value) }))}
                    options={[
                      { value: 'all', label: t('admin2.qs_eff_area_all_tags') },
                      ...tagOptions.map((tag) => ({ value: tag, label: tag })),
                    ]}
                    className="w-full"></Select>
                </div>
                <Button
                  variant="outline"
                  onClick={() => loadEffectiveReport(reportScope)}
                  disabled={reportLoading}
                  className="admin-action-btn">
                  <RefreshCw className={reportLoading ? 'admin-icon-16-spin' : 'w-4 h-4'} />
                  {t('admin2.qs_eff_refresh')}
                </Button>
              </div>
            </div>

            {reportError &&
            <div className="admin-p-sm-secondary-m0 pt-3 text-[var(--mac-error)]">
                {t('admin2.qs_eff_error')}
              </div>
            }

            {!reportError && effectiveReport &&
            <div className="flex flex-col gap-4 pt-4">
                {/* Клиника-уровень: каждое поле — источник, живость, время применения */}
                {effectiveReport.fields.map((fieldRow: EffectiveField) => {
                  const nameKey = EFFECTIVE_FIELD_NAME_KEYS[fieldRow.field];
                  return (
                    <div key={fieldRow.field} data-field-row className="admin-section-divider-pt-16-border-top">
                      <div className="admin-flex-between-sm">
                        <div>
                          <div className="admin-text-sm-med-primary">{nameKey ? t(nameKey) : fieldRow.field}</div>
                          <div className="admin-text-xs-secondary">{formatReportValue(fieldRow.value)}</div>
                          {fieldRow.snapshot_field &&
                          <div className="admin-text-xs-secondary">→ {fieldRow.snapshot_field}</div>
                          }
                          {language.startsWith('ru') && fieldRow.note &&
                          <div className="admin-text-xs-secondary">{fieldRow.note}</div>
                          }
                        </div>
                        <div className="admin-flex-center-12">
                          <span className="admin-range-badge">{SOURCE_LEVEL_KEYS[fieldRow.level] ? t(SOURCE_LEVEL_KEYS[fieldRow.level]) : fieldRow.level}</span>
                          <span className="admin-range-badge">{fieldRow.live ? t('admin2.qs_eff_live') : t('admin2.qs_eff_not_live')}</span>
                          {fieldRow.applied_when.map((code) => (
                            <span key={code} className="admin-range-badge">{APPLIED_WHEN_KEYS[code] ? t(APPLIED_WHEN_KEYS[code]) : code}</span>
                          ))}
                        </div>
                      </div>
                    </div>
                  );
                })}

                {/* Отделение-уровень: display-only блок + владельцы (когда выбрано) */}
                {effectiveReport.department &&
                <div className="admin-section-divider-pt-16-border-top">
                    <h4 className="admin-text-sm-med-primary">
                      {Object.values(effectiveReport.department.queue_settings).some((status) => status.live)
                        ? t('admin2.qs_eff_department_mixed_title')
                        : t('admin2.qs_eff_department_dead_title')}
                      {' — '}
                      {effectiveReport.department.name_ru || effectiveReport.department.key}
                    </h4>
                    <div className="flex flex-col gap-2">
                      {Object.entries(effectiveReport.department.queue_settings).map(([fieldName, status]: [string, DepartmentQueueSettingsStatus]) => {
                        const deptNameKey = DEPARTMENT_FIELD_NAME_KEYS[fieldName];
                        return (
                          <div key={fieldName} data-dept-field-row className="admin-flex-between-sm">
                            <div>
                              <div className="admin-text-xs-secondary">{deptNameKey ? t(deptNameKey) : fieldName}</div>
                              <div className="admin-text-xs-secondary">{formatReportValue(status.value)}</div>
                              {language.startsWith('ru') && status.note &&
                              <div className="admin-text-xs-secondary">{status.note}</div>
                              }
                            </div>
                            <div className="admin-flex-center-12">
                              <span className="admin-range-badge">{status.live ? t('admin2.qs_eff_live') : t('admin2.qs_eff_not_live')}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    {reportScope.tag === null &&
                    <div className="admin-text-xs-secondary pt-2" data-testid="qs-eff-default-tag-note">
                      {t('admin2.qs_eff_default_tag_note')}
                    </div>
                    }
                    <h4 className="admin-text-sm-med-primary pt-2">
                      {t('admin2.qs_eff_owner_overrides_title')}
                    </h4>
                    <div className="flex flex-col gap-2">
                      {effectiveReport.department.owner_overrides.map((override: OwnerOverride) => (
                        <div key={override.doctor_id} data-owner-row className="admin-flex-between-sm">
                          <div className="admin-text-xs-secondary">{getDoctorNameForReport(override.doctor_id)}</div>
                          <div className="admin-flex-center-12">
                            <span className="admin-range-badge">{t('admin2.qs_eff_owner_effective')}: {override.effective_start_number}</span>
                            <span className="admin-range-badge">{t('admin2.qs_eff_owner_max_per_day', { value: override.max_online_per_day })}</span>
                            <span className="admin-range-badge">{SOURCE_LEVEL_KEYS[override.source] ? t(SOURCE_LEVEL_KEYS[override.source]) : override.source}</span>
                            {override.active === false &&
                            <span className="admin-range-badge">{t('admin2.qs_eff_owner_inactive')}</span>
                            }
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                }

                {/* Ресурсная ось (QD-2C): значение реестра безусловно */}
                {effectiveReport.resources.length > 0 &&
                <div className="admin-section-divider-pt-16-border-top">
                    <h4 className="admin-text-sm-med-primary">{t('admin2.qs_eff_resources_title')}</h4>
                    <div className="flex flex-col gap-2">
                      {effectiveReport.resources.map((resource: ResourceRow) => (
                        <div key={resource.queue_resource_id} data-resource-row className="admin-flex-between-sm">
                          <div className="admin-text-xs-secondary">{resource.display_name || resource.code}</div>
                          <div className="admin-flex-center-12">
                            <span className="admin-range-badge">{t('admin2.qs_eff_owner_effective')}: {resource.effective_start_number}</span>
                            <span className="admin-range-badge">{t('admin2.qs_eff_owner_max_per_day', { value: resource.max_online_per_day })}</span>
                            <span className="admin-range-badge">{SOURCE_LEVEL_KEYS[resource.source] ? t(SOURCE_LEVEL_KEYS[resource.source]) : resource.source}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                }

                {/* Активный день: замороженный снимок (D-06) — read-only */}
                <div className="admin-section-divider-pt-16-border-top">
                  <h4 className="admin-text-sm-med-primary">
                    {t('admin2.qs_eff_active_day_title')}
                    {effectiveReport.clinic_today ? ` (${effectiveReport.clinic_today})` : ''}
                  </h4>
                  {effectiveReport.active_day.length === 0 ?
                  <p className="admin-text-xs-secondary admin-m-0">{t('admin2.qs_eff_active_day_empty')}</p> :

                  <div className="flex flex-col gap-2">
                      {effectiveReport.active_day.map((dayRow: ActiveDayRow) => (
                        <div key={dayRow.daily_queue_id} data-day-row className="admin-flex-between-sm">
                          <div>
                            <div className="admin-text-xs-secondary">{dayRow.queue_tag ?? '—'}</div>
                            <div className="admin-flex-center-12">
                              <span className="admin-text-xs-secondary">{t('admin2.qs_eff_day_start_number')}: </span>
                              <strong>{dayRow.start_number}</strong>
                              <span className="admin-text-xs-secondary">{t('admin2.qs_eff_day_window')}: </span>
                              <strong>{dayRow.online_start_time ?? '—'} – {dayRow.online_end_time ?? '—'}</strong>
                              <span className="admin-text-xs-secondary">{t('admin2.qs_eff_day_max_entries')}: </span>
                              <strong>{dayRow.max_online_entries}</strong>
                            </div>
                            {language.startsWith('ru') && dayRow.note &&
                            <div className="admin-text-xs-secondary">{dayRow.note}</div>
                            }
                          </div>
                          <span className="admin-range-badge">{dayRow.active === false ? t('admin2.qs_eff_day_inactive_badge') : t('admin2.qs_eff_frozen_badge')}</span>
                        </div>
                      ))}
                    </div>
                  }
                </div>
              </div>
            }

            {!reportError && reportLoading && !effectiveReport &&
            <p className="admin-text-xs-secondary admin-m-0">{t('admin2.qs_eff_loading')}</p>
            }
          </section>
        </Card>

        {/* Информационная панель */}
        <Card className="admin-card-info-p-24">
          <h3 className="admin-h3-lg-semi-info-mb-12-flex">
            <QrCode className="w-5 h-5" />
            {t('admin2.qs_info_title')}
          </h3>
          <div className="admin-div-sm-info-flex-col-8">
            <p className="admin-m-0">{t('admin2.qs_info_1', { hour: settings.queue_start_hour })}</p>
            <p className="admin-m-0">{t('admin2.qs_info_2')}</p>
            <p className="admin-m-0">{t('admin2.qs_info_3')}</p>
            <p className="admin-m-0">{t('admin2.qs_info_4')}</p>
            <p className="admin-m-0">{t('admin2.qs_info_5')}</p>
          </div>
        </Card>
      </Card>
    </div>);

};

export default QueueSettings;
