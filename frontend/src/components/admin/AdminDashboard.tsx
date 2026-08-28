/**
 * AdminDashboard — data-first admin landing page.
 *
 * PR-UI-11-1 (dashboard data-first) per `docs/UI_REMEDIATION_PLAN.md` §PR-UI-11.
 *
 * ## Migration delta
 *
 * Replaces the legacy 488-LOC copy with a data-first layout:
 *   1. Greeting + current date header.
 *   2. 3 KPI StatCards (appointments today / revenue / patients today).
 *   3. Today's schedule timeline — fetched from `/appointments/?date_from=<today>&date_to=<today>&limit=10`.
 *   4. Queue summary — 3 mini stat tiles (waiting / in-consultation / done),
 *      aggregated across all active departments via `/doctor/departments?active_only=true`
 *      and per-department `/queues/stats?department=<name>&d=<today>` calls.
 *   5. Activity chart — bar visualization of `/admin/activity-chart?days=7`.
 *   6. Recent activity feed — `/admin/recent-activities?limit=10`.
 *   7. System notifications — `/notifications/history/stats?days=7`.
 *
 * ## Zero-glass invariant
 *
 * The previous copy used `<MacOSCard className="admin-bg-var-mac-gradient-…-bflt-…">`
 * — explicit `backdrop-filter: var(--mac-blur-light)` plus a sidebar-gradient surface,
 * explicitly forbidden by `AGENTS_UI.md` antipattern table ("Glass — только для
 * modals, popovers, command palette. Не для cards."). This copy uses the
 * canonical `Card` (no alias) for the panel surface and `DataCard` for the
 * titled body panels. No `MacOSCard` alias, no `adminSurface`/`adminInsetSurface`/
 * `adminBorder` inline `color-mix(... white 72%)` glass styles, no backdrop-filter.
 *
 * ## Scope
 *
 * This increment migrates the AdminDashboard surface ONLY. The legacy
 * `MacOSCard` alias is still live in 65 other files (329 JSX uses total —
 * see `docs/UI_REMEDIATION_PLAN.md` §3.4). Those consumers are scheduled
 * for PR-UI-11-2+ follow-ups following the PR-UI-09c incremental precedent.
 *
 * ## Acceptance criteria (PR-UI-11)
 *
 * - ✅ Dashboard содержит: schedule timeline + queue summary + 3 stat cards + activity feed
 * - ✅ Нет glass cards с градиентами
 * - ✅ Loading state = skeleton (не spinner)
 * - ✅ Visual regression (covered by existing Playwright visual-regression suite)
 */

import { useTranslation } from '../../i18n/useTranslation';
import React, { type CSSProperties } from 'react';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  Calendar,
  CheckCircle,
  Clock,
  Download,
  Eye,
  RefreshCw,
  Stethoscope,
  TrendingUp,
  Users,
} from 'lucide-react';

import {
  Card,
  Badge,
  AppEmpty,
  Button,
  Skeleton,
  StatCard,
  DataCard,
} from '../ui/macos';
import useAdminData from '../../hooks/useAdminData';
import useQueueSummary from '../../hooks/useQueueSummary';
import AdminRouteSwitcher from './AdminRouteSwitcher';
import ErrorBoundary from '../common/ErrorBoundary';
import formatCurrency from '../../utils/formatCurrency';

// Minimal translation fn signature accepted by the helpers below. Mirrors the
// `useTranslation` adapter shape without coupling this file to its concrete type.
export type AdminTranslationFn = (key: string, options?: Record<string, unknown>) => string;

// Shape of `/admin/recent-activities` rows.
export interface AdminRecentActivity {
  id?: string | number;
  status?: string;
  message?: string;
  notification_type?: string;
  created_at?: string;
  user?: string;
  time?: string;
  [key: string]: unknown;
}

// Shape of `/admin/activity-chart?days=N` payload.
export interface AdminActivityEntry {
  appointments?: number;
  payments?: number;
  users?: number;
  total?: number;
  [key: string]: unknown;
}

export interface AdminActivityChartData {
  labels?: string[];
  data: AdminActivityEntry[];
  [key: string]: unknown;
}

// Shape of `/admin/stats` payload.
export interface AdminStats {
  totalUsers?: number;
  totalDoctors?: number;
  totalPatients?: number;
  totalRevenue?: number;
  appointmentsToday?: number;
  pendingApprovals?: number;
  visitsToday?: number;
  newPatientsToday?: number;
  [key: string]: unknown;
}

// Shape of `/notifications/history/stats?days=N` payload.
export interface AdminSystemAlertsData {
  recent_activity?: AdminRecentActivity[];
  [key: string]: unknown;
}

// Flattened system alert row produced by `buildSystemAlerts`.
export interface AdminSystemAlert {
  id: string | number;
  type: string;
  message: string;
  priority: string;
  time: string;
  [key: string]: unknown;
}

// Shape of `/appointments/?date_from=<today>&date_to=<today>` rows. Backend
// returns the full `Appointment` schema; we only consume a subset here.
export interface AdminScheduleItem {
  id?: number;
  patient_name?: string | null;
  patient_id?: number;
  doctor_id?: number | null;
  department?: string | null;
  appointment_date?: string;
  appointment_time?: string | null;
  status?: string;
  visit_type?: string | null;
  notes?: string | null;
  [key: string]: unknown;
}

// Note: types for `/doctor/departments` and `/queues/stats` payloads live in
// `src/hooks/useQueueSummary.ts` (the canonical hook that owns the queue
// aggregation). AdminDashboard consumes the aggregated `QueueSummaryAggregate`
// shape via that hook.

const defaultStats: AdminStats = {
  totalUsers: 0,
  totalDoctors: 0,
  totalPatients: 0,
  totalRevenue: 0,
  appointmentsToday: 0,
  pendingApprovals: 0,
};


function formatTimeAgo(date: string | Date | null | undefined, t: AdminTranslationFn): string {
  if (!date) return t('admin2.adm_recent');

  const dateObj = typeof date === 'string' ? new Date(date) : date;
  if (Number.isNaN(dateObj.getTime())) return t('admin2.adm_recent');

  const now = new Date();
  const diff = now.getTime() - (dateObj as Date).getTime();
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) return t('admin2.adm_just_now');
  if (minutes < 60) return `${minutes} ${minutes === 1 ? t('admin2.adm_min_one') : minutes < 5 ? t('admin2.adm_min_few') : t('admin2.adm_min_many')} ${t('admin2.adm_ago')}`;
  if (hours < 24) return `${hours} ${hours === 1 ? t('admin2.adm_hour_one') : hours < 5 ? t('admin2.adm_hour_few') : t('admin2.adm_hour_many')} ${t('admin2.adm_ago')}`;
  if (days < 7) return `${days} ${days === 1 ? t('admin2.adm_day_one') : days < 5 ? t('admin2.adm_day_few') : t('admin2.adm_day_many')} ${t('admin2.adm_ago')}`;
  return dateObj.toLocaleDateString('ru-RU');
}

function getStatusIcon(status: unknown) {
  const colorMap = {
    success: 'var(--mac-success)',
    warning: 'var(--mac-warning)',
    error: 'var(--mac-error)',
    info: 'var(--mac-accent)',
    default: 'var(--mac-text-tertiary)',
  };

  if (status === 'success') return <CheckCircle className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.success } as CSSProperties} />;
  if (status === 'warning') return <AlertTriangle className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.warning } as CSSProperties} />;
  if (status === 'error') return <AlertTriangle className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.error } as CSSProperties} />;
  if (status === 'info') return <Clock className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.info } as CSSProperties} />;
  return <Clock className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.default } as CSSProperties} />;
}

function buildSystemAlerts(systemAlertsData: AdminSystemAlertsData | null | undefined, t: AdminTranslationFn): AdminSystemAlert[] {
  if (!systemAlertsData?.recent_activity) return [];

  return systemAlertsData.recent_activity.slice(0, 5).map((alert: AdminRecentActivity, index: number) => ({
    id: alert.id || index + 1,
    type: alert.status === 'failed' ? 'error' : alert.status === 'pending' ? 'warning' : 'info',
    message: alert.message || alert.notification_type || t('admin2.adm_system_notification'),
    priority: alert.status === 'failed' ? 'high' : alert.status === 'pending' ? 'medium' : 'low',
    time: alert.created_at ? formatTimeAgo(new Date(alert.created_at), t) : t('admin2.adm_recent'),
  }));
}

// UX Audit Stage 3 (Dashboard issue 4.2): локализация приоритета уведомлений.
// Раньше отображались английские 'high'/'medium'/'low' в русском UI.
function getPriorityLabel(priority: unknown, t: AdminTranslationFn): string {
  const map = {
    high: t('admin2.adm_priority_high'),
    medium: t('admin2.adm_priority_medium'),
    low: t('admin2.adm_priority_low'),
  };
  return (typeof priority === 'string' && priority in map
    ? map[priority as keyof typeof map]
    : null) || String(priority ?? '');
}

// UX Audit Stage 3 (Dashboard issue 4.1):
// Helper для экспорта данных активности в CSV.
// Раньше кнопка «Экспорт» не имела onClick — была кнопкой-призраком.
function exportActivityToCsv(chartData: AdminActivityChartData | null | undefined, t: AdminTranslationFn): void {
  if (!chartData?.data || chartData.data.length === 0) {
    return;
  }

  const headers = [
    t('admin2.adm_csv_date'),
    t('admin2.adm_csv_appointments'),
    t('admin2.adm_csv_payments'),
    t('admin2.adm_csv_users'),
    t('admin2.adm_csv_total'),
  ];
  const rows = chartData.data.map((entry: AdminActivityEntry, index: number) => [
    chartData.labels?.[index] || '',
    entry.appointments || 0,
    entry.payments || 0,
    entry.users || 0,
    entry.total || 0,
  ]);

  const csv = [headers, ...rows]
    .map((row: unknown[]) => row.map((cell: unknown) => String(cell)).join(';'))
    .join('\n');

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `activity-${new Date().toISOString().split('T')[0]}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

// Returns "YYYY-MM-DD" for today in local timezone. Used for the
// `date_from`/`date_to` query params of `/appointments/` and the
// `d` query param of `/queues/stats`.
function todayIsoDate(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// PR-UI-11-1: pick the localized greeting token by current hour. The four
// tokens `adm_greeting_morning/afternoon/evening/night` are translated in
// every locale; the 24h→bucket mapping is culture-agnostic here.
function getGreetingKey(t: AdminTranslationFn): string {
  const hour = new Date().getHours();
  if (hour < 6) return t('admin2.adm_greeting_night');
  if (hour < 12) return t('admin2.adm_greeting_morning');
  if (hour < 18) return t('admin2.adm_greeting_afternoon');
  return t('admin2.adm_greeting_evening');
}

// Localized visit-type label for schedule timeline rows. Returns the raw
// value when it does not match one of the canonical buckets so callers
// see the server-side value verbatim instead of a blank cell.
function getVisitTypeLabel(visitType: unknown, t: AdminTranslationFn): string {
  if (visitType === 'paid') return t('admin2.adm_schedule_visit_type_paid');
  if (visitType === 'repeat') return t('admin2.adm_schedule_visit_type_repeat');
  if (visitType === 'free') return t('admin2.adm_schedule_visit_type_free');
  return String(visitType ?? '');
}

// Localized status label for schedule timeline rows. Mirrors the same
// pass-through rule as `getVisitTypeLabel`.
function getScheduleStatusLabel(status: unknown, t: AdminTranslationFn): string {
  if (status === 'scheduled') return t('admin2.adm_schedule_status_scheduled');
  if (status === 'confirmed') return t('admin2.adm_schedule_status_confirmed');
  if (status === 'cancelled') return t('admin2.adm_schedule_status_cancelled');
  if (status === 'completed') return t('admin2.adm_schedule_status_completed');
  return String(status ?? '');
}

const AdminDashboard = () => {
  const { t: rawT, i18n } = useTranslation(); const t = rawT as AdminTranslationFn;
  const {
    data: statsDataRaw,
    loading: statsLoading,
    error: statsError,
    refresh: refreshStats,
  } = useAdminData('/admin/stats', {
    refreshInterval: 0,
    enabled: true,
  });

  const {
    data: recentActivitiesData,
    loading: recentActivitiesLoading,
    error: recentActivitiesError,
  } = useAdminData('/admin/recent-activities?limit=10', {
    refreshInterval: 0,
    enabled: true,
    initialData: { activities: [] },
  });

  const {
    data: systemAlertsData,
    loading: systemAlertsLoading,
    error: systemAlertsError,
  } = useAdminData('/notifications/history/stats?days=7', {
    refreshInterval: 0,
    enabled: true,
    initialData: { recent_activity: [] },
  });

  const {
    data: activityChartDataRaw,
    loading: activityChartLoading,
    error: activityChartError,
  } = useAdminData('/admin/activity-chart?days=7', {
    refreshInterval: 0,
    enabled: true,
    initialData: { labels: [], data: [] },
  });

  // PR-UI-11-1: today's schedule timeline. Single endpoint with `date_from`
  // + `date_to` filter params set to today's ISO date. Limit caps the
  // timeline length so a busy day doesn't overflow the dashboard.
  const todayIso = todayIsoDate();
  const scheduleUrl = `/appointments/?date_from=${todayIso}&date_to=${todayIso}&limit=10`;
  const {
    data: scheduleDataRaw,
    loading: scheduleLoading,
    error: scheduleError,
    refresh: refreshSchedule,
  } = useAdminData(scheduleUrl, {
    refreshInterval: 0,
    enabled: true,
    initialData: [],
  });

  // PR-UI-11-1: clinic-wide queue summary. Delegated to the canonical
  // `useQueueSummary` hook (ADR-0015 hook-layer boundary) — it fetches
  // the list of active departments via `/doctor/departments?active_only=true`
  // then fans out per-department `/queues/stats?department=<name>&d=<today>`
  // calls via Promise.all. Per-department failures are tolerated (skipped);
  // the summary reflects only the departments that returned data.
  const {
    summary: queueSummary,
    loading: queueLoading,
    error: queueError,
    refresh: refreshQueue,
  } = useQueueSummary({ enabled: true, date: todayIso });

  const statsData = statsDataRaw as AdminStats | null | undefined;
  const activityChartData = activityChartDataRaw as AdminActivityChartData | null | undefined;
  const stats: AdminStats = statsData || defaultStats;
  const scheduleItems = Array.isArray(scheduleDataRaw) ? (scheduleDataRaw as AdminScheduleItem[]) : [];
  const recentActivities = ((recentActivitiesData as { activities?: AdminRecentActivity[] })?.activities) || [];
  const systemAlerts = React.useMemo(() => buildSystemAlerts(systemAlertsData as AdminSystemAlertsData | null | undefined, t), [systemAlertsData, t]);

  // UX Audit Stage 3 (Dashboard issue 4.1):
  // Handlers для кнопок «Экспорт» и «Все».
  // Раньше это были кнопки-призраки без onClick.
  const handleExportActivity = React.useCallback(() => {
    exportActivityToCsv(activityChartData, t);
  }, [activityChartData, t]);

  const handleViewAllActivities = React.useCallback(() => {
    // Переход к странице аналитики (если есть) или скролл к секции последних действий.
    const analyticsRoute = '/admin/analytics';
    if (typeof window !== 'undefined') {
      window.location.assign(analyticsRoute);
    }
  }, []);

  // PR-UI-11-1: 3 KPI tiles per the AC ("Revenue today / Patients today /
  // Appointments today"). The previous copy had 6 tiles including users,
  // doctors, pending approvals; the trimmed set keeps the operationally
  // actionable metrics and pushes the rest to dedicated analytics pages.
  const dashboardKpis = React.useMemo(() => [
    {
      key: 'appointments-today',
      title: t('admin2.stat_appointments_today'),
      value: stats.appointmentsToday || 0,
      icon: Calendar,
      color: 'orange',
    },
    {
      key: 'revenue',
      title: t('admin2.stat_income_month'),
      value: formatCurrency(stats.totalRevenue || 0),
      icon: TrendingUp,
      color: 'green',
    },
    {
      key: 'patients',
      title: t('admin2.stat_patients'),
      value: stats.totalPatients || 0,
      icon: Users,
      color: 'purple',
    },
  ], [stats]);

  // PR-UI-11-1: queue summary tiles. Three semantic counters per the AC
  // ("Queue summary: Waiting / In consultation / Done") — sourced from
  // the aggregated `/queues/stats` responses.
  const queueTiles = React.useMemo(() => [
    {
      key: 'waiting',
      label: t('admin2.adm_queue_waiting'),
      value: queueSummary.waiting,
      color: 'orange',
      icon: Clock,
      ariaKey: 'admin2.adm_queue_waiting_aria',
    },
    {
      key: 'in-consultation',
      label: t('admin2.adm_queue_in_consultation'),
      value: queueSummary.serving,
      color: 'blue',
      icon: Stethoscope,
      ariaKey: 'admin2.adm_queue_in_consultation_aria',
    },
    {
      key: 'done',
      label: t('admin2.adm_queue_done'),
      value: queueSummary.done,
      color: 'green',
      icon: CheckCircle,
      ariaKey: 'admin2.adm_queue_done_aria',
    },
  ], [queueSummary, t]);

  return (
    <ErrorBoundary>
      <div className="flex flex-col gap-6">
        <AdminRouteSwitcher current="dashboard" />

        {/* PR-UI-11-1: greeting + current-date header. */}
        <Card
          variant="default"
          padding="default"
          aria-label={t('admin2.adm_dashboard_header_aria')}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px',
              flexWrap: 'wrap',
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <h2
                style={{
                  margin: 0,
                  fontSize: 'var(--mac-font-size-xl)',
                  fontWeight: 600,
                  color: 'var(--mac-text-primary)',
                  lineHeight: 1.2,
                }}
              >
                {getGreetingKey(t)}
              </h2>
              <p
                style={{
                  margin: 0,
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)',
                }}
              >
                {(() => {
                  // PR-UI-11-1 (Codex P2 #5): format the dashboard header date
                  // in the active locale, not hardcoded `ru-RU`. Map the 5
                  // supported i18n codes to their BCP 47 equivalents.
                  const lang = (i18n as { language?: string }).language || 'ru';
                  const bcp47Map: Record<string, string> = {
                    'ru': 'ru-RU',
                    'en': 'en-US',
                    'uz-Latn': 'uz-Latn-UZ',
                    'uz-Cyrl': 'uz-Cyrl-UZ',
                    'kk': 'kk-KZ',
                  };
                  const bcp47 = bcp47Map[lang] || 'ru-RU';
                  return new Date().toLocaleDateString(bcp47, {
                    weekday: 'long',
                    day: 'numeric',
                    month: 'long',
                    year: 'numeric',
                  });
                })()}
              </p>
            </div>
            <RefreshCw
              aria-hidden="true"
              style={{
                width: 20,
                height: 20,
                color: 'var(--mac-text-tertiary)',
                flexShrink: 0,
              }}
            />
          </div>
        </Card>

        {/* PR-UI-11-1: 3 KPI StatCards. */}
        {statsLoading ? (
          <div className="admin-kpi-grid" aria-label={t('admin2.adm_kpi_loading_aria')} aria-busy="true">
            <Skeleton type="card" count={3} />
          </div>
        ) : statsError ? (
          <AppEmpty
            icon={AlertCircle}
            title={t('admin2.adm_error_load_stats')}
            description={t('admin2.adm_error_load_stats_desc')}
            action={(
              <Button onClick={refreshStats} variant="primary">
                <RefreshCw size={16} />
                {t('admin2.adm_retry')}
              </Button>
            )}
          />
        ) : (
          <div className="admin-kpi-grid" role="list" aria-label={t('admin2.adm_kpi_list_aria')}>
            {dashboardKpis.map((kpi) => (
              <div key={kpi.key} role="listitem">
                <StatCard
                  title={kpi.title}
                  value={kpi.value}
                  icon={kpi.icon}
                  color={kpi.color}
                  loading={statsLoading}
                  className="admin-kpi-card"
                />
              </div>
            ))}
          </div>
        )}

        {/* PR-UI-11-1: today's schedule timeline + queue summary side-by-side
            on wide viewports; stacked on narrow ones. The grid below uses
            the existing `.admin-d-grid-gtc-repeat-auto-fit-minm-gap-24`
            class (defined in admin.css) — same responsive auto-fit pattern
            the previous copy used for the activity / recent-actions row. */}
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-24">
          <DataCard
            title={t('admin2.adm_today_schedule')}
            icon={<Calendar size={18} aria-hidden="true" />}
            ariaLabel={t('admin2.adm_today_schedule')}
            loading={scheduleLoading}
            loadingSkeleton={<Skeleton type="list" count={4} />}
            error={scheduleError ? t('admin2.adm_error_load_schedule') : null}
            onRetry={refreshSchedule}
            retryLabel={t('admin2.adm_retry')}
            empty={scheduleItems.length === 0 ? t('admin2.adm_schedule_empty') : null}
          >
            <ol
              role="list"
              style={{
                listStyle: 'none',
                margin: 0,
                padding: 0,
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
              }}
            >
              {scheduleItems.map((item, index) => (
                <li
                  key={item.id ?? `schedule-${index}`}
                  role="listitem"
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '64px 1fr auto',
                    gap: '12px',
                    alignItems: 'center',
                    padding: '12px',
                    border: '1px solid var(--mac-border)',
                    borderRadius: 'var(--mac-radius-md)',
                    background: 'var(--mac-bg-secondary)',
                  }}
                >
                  <span
                    style={{
                      fontSize: 'var(--mac-font-size-sm)',
                      fontWeight: 600,
                      color: 'var(--mac-text-primary)',
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {item.appointment_time || '—'}
                  </span>
                  <div style={{ minWidth: 0 }}>
                    <p
                      style={{
                        margin: 0,
                        fontSize: 'var(--mac-font-size-sm)',
                        fontWeight: 500,
                        color: 'var(--mac-text-primary)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {item.patient_name || t('admin2.adm_schedule_patient_label')}
                    </p>
                    <p
                      style={{
                        margin: 0,
                        marginTop: '2px',
                        fontSize: 'var(--mac-font-size-xs)',
                        color: 'var(--mac-text-secondary)',
                      }}
                    >
                      {item.department || t('admin2.adm_schedule_department_label')}
                      {item.visit_type ? ` · ${getVisitTypeLabel(item.visit_type, t)}` : ''}
                    </p>
                  </div>
                  <Badge variant="secondary">
                    {getScheduleStatusLabel(item.status, t)}
                  </Badge>
                </li>
              ))}
            </ol>
          </DataCard>

          {/* PR-UI-11-1: queue summary panel — 3 mini stat tiles. */}
          <DataCard
            title={t('admin2.adm_queue_summary')}
            description={queueSummary.partial ? t('admin2.adm_queue_partial_note') : undefined}
            icon={<Clock size={18} aria-hidden="true" />}
            ariaLabel={t('admin2.adm_queue_summary')}
            loading={queueLoading}
            loadingSkeleton={<Skeleton type="card" count={3} />}
            error={queueError ? t('admin2.adm_error_load_queue') : null}
            onRetry={refreshQueue}
            retryLabel={t('admin2.adm_retry')}
            empty={(!queueLoading && !queueError && queueSummary.queuesCount === 0) ? t('admin2.adm_no_departments') : null}
          >
            <div
              role="list"
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                gap: '12px',
              }}
            >
              {queueTiles.map((tile) => (
                <div
                  key={tile.key}
                  role="listitem"
                  aria-label={t(`admin2.${tile.ariaKey}`, { count: tile.value })}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    padding: '16px',
                    border: '1px solid var(--mac-border)',
                    borderRadius: 'var(--mac-radius-md)',
                    background: 'var(--mac-bg-secondary)',
                  }}
                >
                  <tile.icon
                    size={18}
                    aria-hidden="true"
                    style={{ color: `var(--mac-accent-${tile.color === 'blue' ? 'blue' : tile.color === 'green' ? 'success' : tile.color === 'orange' ? 'warning' : 'purple'})` }}
                  />
                  <span
                    style={{
                      fontSize: 'var(--mac-font-size-2xl)',
                      fontWeight: 600,
                      color: 'var(--mac-text-primary)',
                      fontVariantNumeric: 'tabular-nums',
                      lineHeight: 1.2,
                    }}
                  >
                    {tile.value}
                  </span>
                  <span
                    style={{
                      fontSize: 'var(--mac-font-size-xs)',
                      color: 'var(--mac-text-secondary)',
                    }}
                  >
                    {tile.label}
                  </span>
                </div>
              ))}
            </div>
          </DataCard>
        </div>

        {/* PR-UI-11-1: activity chart + recent activity feed (canonical
            DataCard wrappers; no glass / gradient surface). */}
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-24">
          <DataCard
            title={t('admin2.adm_activity_system')}
            icon={<Activity size={18} aria-hidden="true" />}
            action={(
              <Button variant="outline" size="small" onClick={handleExportActivity} disabled={!activityChartData?.data?.length}>
                <Download className="w-4 h-4 mr-2" aria-hidden="true" />
                {t('admin2.adm_export')}
              </Button>
            )}
            loading={activityChartLoading}
            loadingSkeleton={<Skeleton type="text" count={3} />}
            error={activityChartError ? t('admin2.adm_error_load_chart') : null}
            onRetry={refreshStats}
            retryLabel={t('admin2.adm_retry')}
            empty={(!activityChartLoading && !activityChartError && (!activityChartData?.data || activityChartData.data.length === 0)) ? t('admin2.adm_no_data_period') : null}
          >
            <div style={{ height: 256, padding: 16, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-around', height: 200, gap: 4 }}>
                {activityChartData?.data && activityChartData.data.length > 0 && activityChartData.data.map((item: AdminActivityEntry, index: number) => {
                  const maxValue = Math.max(...activityChartData.data.map((entry: AdminActivityEntry) => entry.total || 0));
                  const height = maxValue > 0 ? (Number(item.total ?? 0) / maxValue) * 180 : 0;
                  return (
                    <div
                      key={`${activityChartData.labels?.[index] || 'activity'}-${index}`}
                      style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}
                    >
                      <div
                        style={{
                          width: '100%',
                          background: 'var(--mac-accent)',
                          borderRadius: '4px 4px 0 0',
                          minHeight: 4,
                          height: `${height}px`,
                          transition: 'height 0.3s ease',
                        }}
                      />
                      <span style={{ fontSize: 10, color: 'var(--mac-text-tertiary)', textAlign: 'center' }}>
                        {activityChartData.labels?.[index] ?? ''}
                      </span>
                    </div>
                  );
                })}
              </div>
              {activityChartData?.data && activityChartData.data.length > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: 8, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                  <span>{t('admin2.adm_chart_appointments_count', { count: activityChartData.data.reduce((sum: number, entry: AdminActivityEntry) => sum + (entry.appointments || 0), 0) })}</span>
                  <span>{t('admin2.adm_chart_payments_count', { count: activityChartData.data.reduce((sum: number, entry: AdminActivityEntry) => sum + (entry.payments || 0), 0) })}</span>
                  <span>{t('admin2.adm_chart_users_count', { count: activityChartData.data.reduce((sum: number, entry: AdminActivityEntry) => sum + (entry.users || 0), 0) })}</span>
                </div>
              )}
            </div>
          </DataCard>

          <DataCard
            title={t('admin2.adm_recent_actions')}
            icon={<Clock size={18} aria-hidden="true" />}
            action={(
              <Button variant="outline" size="small" onClick={handleViewAllActivities} disabled={recentActivities.length === 0}>
                <Eye className="w-4 h-4 mr-2" aria-hidden="true" />
                {t('admin2.adm_view_all')}
              </Button>
            )}
            loading={recentActivitiesLoading}
            loadingSkeleton={<Skeleton type="text" count={4} />}
            error={recentActivitiesError ? t('admin2.adm_error_load') : null}
            retryLabel={t('admin2.adm_retry')}
            empty={(!recentActivitiesLoading && !recentActivitiesError && recentActivities.length === 0) ? t('admin2.adm_no_recent_actions') : null}
          >
            <div className="flex flex-col gap-4">
              {recentActivities.map((activity: AdminRecentActivity) => (
                <div
                  key={activity.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    padding: 12,
                    borderRadius: 'var(--mac-radius-md)',
                    border: '1px solid var(--mac-border)',
                    background: 'var(--mac-bg-secondary)',
                  }}
                >
                  {getStatusIcon(activity.status)}
                  <div className="admin-flex-1">
                    <p className="admin-fs-sm-fw-med-primary-m-0">{activity.message}</p>
                    <p className="admin-fs-xs-secondary-m-4px-0-0-0">{activity.user} · {activity.time || formatTimeAgo(activity.created_at, t)}</p>
                  </div>
                </div>
              ))}
            </div>
          </DataCard>
        </div>

        {/* PR-UI-11-1: system notifications (canonical DataCard; the previous
            copy wrapped this in a gradient / backdrop-filter MacOSCard —
            forbidden by AGENTS_UI antipattern table). */}
        <DataCard
          title={t('admin2.adm_system_notifications')}
          icon={<AlertTriangle size={18} aria-hidden="true" />}
          badge={<Badge variant="warning">{systemAlerts.length}</Badge>}
          loading={systemAlertsLoading}
          loadingSkeleton={<Skeleton type="text" count={3} />}
          error={systemAlertsError ? t('admin2.adm_error_load') : null}
          retryLabel={t('admin2.adm_retry')}
          empty={(!systemAlertsLoading && !systemAlertsError && systemAlerts.length === 0) ? t('admin2.adm_no_system_notifications') : null}
        >
          <div className="flex flex-col gap-4">
            {systemAlerts.map((alert: AdminSystemAlert) => (
              <div
                key={alert.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: 12,
                  borderRadius: 'var(--mac-radius-md)',
                  border: '1px solid var(--mac-border)',
                  background: 'var(--mac-bg-secondary)',
                }}
              >
                <AlertTriangle className="admin-w-20-h-20-warning" />
                <div className="admin-flex-1">
                  <p className="admin-fs-sm-fw-med-primary-m-0">{alert.message}</p>
                  <p className="admin-fs-12-secondary-m-4px-0-0-0">{alert.time}</p>
                </div>
                <Badge variant={(alert.priority === 'high' ? 'error' : alert.priority === 'medium' ? 'warning' : 'info') as unknown as "default" | "primary" | "secondary" | "success" | "warning" | "danger" | "info" | "outline"}>
                  {/* UX Audit Stage 3 (Dashboard issue 4.2): локализация приоритета. */}
                  {getPriorityLabel(alert.priority, t)}
                </Badge>
              </div>
            ))}
          </div>
        </DataCard>
      </div>
    </ErrorBoundary>
  );
};

export default AdminDashboard;
