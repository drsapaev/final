
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
  Card as MacOSCard,
  Badge,
  MacOSEmptyState,
  Button,
  Skeleton,
  MacOSStatCard,
} from '../ui/macos';
import useAdminData from '../../hooks/useAdminData';
import AdminRouteSwitcher from './AdminRouteSwitcher';
import ErrorBoundary from '../common/ErrorBoundary';
import formatCurrency from '../../utils/formatCurrency';

const adminSurface = 'linear-gradient(180deg, color-mix(in srgb, var(--mac-card-bg), white 72%) 0%, color-mix(in srgb, var(--mac-card-bg), white 64%) 100%)';
const adminInsetSurface = 'color-mix(in srgb, var(--mac-card-bg), white 82%)';
const adminBorder = '1px solid color-mix(in srgb, var(--mac-card-border), white 12%)';
const adminTextSecondary = 'color-mix(in srgb, var(--mac-text-secondary), black 42%)';

const defaultStats = {
  totalUsers: 0,
  totalDoctors: 0,
  totalPatients: 0,
  totalRevenue: 0,
  appointmentsToday: 0,
  pendingApprovals: 0,
};


function formatTimeAgo(date, t) {
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

function getStatusIcon(status) {
  const colorMap = {
    success: 'var(--mac-success)',
    warning: 'var(--mac-warning)',
    error: 'var(--mac-error)',
    info: 'var(--mac-info)',
    default: 'var(--mac-text-tertiary)',
  };

  if (status === 'success') return <CheckCircle className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.success } as CSSProperties} />;
  if (status === 'warning') return <AlertTriangle className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.warning } as CSSProperties} />;
  if (status === 'error') return <AlertTriangle className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.error } as CSSProperties} />;
  if (status === 'info') return <Clock className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.info } as CSSProperties} />;
  return <Clock className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.default } as CSSProperties} />;
}

function buildSystemAlerts(systemAlertsData, t) {
  if (!systemAlertsData?.recent_activity) return [];

  return systemAlertsData.recent_activity.slice(0, 5).map((alert, index) => ({
    id: alert.id || index + 1,
    type: alert.status === 'failed' ? 'error' : alert.status === 'pending' ? 'warning' : 'info',
    message: alert.message || alert.notification_type || t('admin2.adm_system_notification'),
    priority: alert.status === 'failed' ? 'high' : alert.status === 'pending' ? 'medium' : 'low',
    time: alert.created_at ? formatTimeAgo(new Date(alert.created_at), t) : t('admin2.adm_recent'),
  }));
}

// UX Audit Stage 3 (Dashboard issue 4.2): локализация приоритета уведомлений.
// Раньше отображались английские 'high'/'medium'/'low' в русском UI.
function getPriorityLabel(priority, t) {
  const map = {
    high: t('admin2.adm_priority_high'),
    medium: t('admin2.adm_priority_medium'),
    low: t('admin2.adm_priority_low'),
  };
  return map[priority] || priority;
}

// UX Audit Stage 3 (Dashboard issue 4.1):
// Helper для экспорта данных активности в CSV.
// Раньше кнопка «Экспорт» не имела onClick — была кнопкой-призраком.
function exportActivityToCsv(chartData, t) {
  if (!(chartData as Record<string, any>)?.data || chartData.data.length === 0) {
    return;
  }

  const headers = [
    t('admin2.adm_csv_date'),
    t('admin2.adm_csv_appointments'),
    t('admin2.adm_csv_payments'),
    t('admin2.adm_csv_users'),
    t('admin2.adm_csv_total'),
  ];
  const rows = chartData.data.map((entry, index) => [
    chartData.labels?.[index] || '',
    entry.appointments || 0,
    entry.payments || 0,
    entry.users || 0,
    entry.total || 0,
  ]);

  const csv = [headers, ...rows]
    .map((row) => row.map((cell) => String(cell)).join(';'))
    .join('\n');

  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `activity-${new Date().toISOString().split('T')[0]}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

const AdminDashboard = () => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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

  const statsData = statsDataRaw as Record<string, any>;
  const activityChartData = activityChartDataRaw as Record<string, any>;
  const stats = statsData || defaultStats;
  const recentActivities = (recentActivitiesData as Record<string, any>)?.activities || [];
  const systemAlerts = React.useMemo(() => buildSystemAlerts(systemAlertsData, t), [systemAlertsData, t]);

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

  const dashboardKpis = React.useMemo(() => [
    // UX Audit Admin #4.3: KPI разделены на операционные (сегодня) и кумулятивные (всего).
    // Операционные — показывают текущую нагрузку.
    {
      key: 'appointments-today',
      title: t('admin2.stat_appointments_today'),
      value: stats.appointmentsToday || 0,
      icon: Calendar,
      color: 'orange',
    },
    {
      key: 'pending-approvals',
      title: t('admin2.stat_awaiting_confirmation'),
      value: stats.pendingApprovals || 0,
      icon: Clock,
      color: 'red',
    },
    {
      key: 'revenue',
      title: t('admin2.stat_income_month'),
      value: formatCurrency(stats.totalRevenue || 0),
      icon: TrendingUp,
      color: 'green',
    },
    // Кумулятивные — общее количество.
    {
      key: 'users',
      title: t('admin2.stat_total_users'),
      value: stats.totalUsers || 0,
      icon: Users,
      color: 'blue',
    },
    {
      key: 'doctors',
      title: t('admin2.stat_doctors'),
      value: stats.totalDoctors || 0,
      icon: Stethoscope,
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

  return (
    <ErrorBoundary>
      <div className="flex flex-col gap-6">
        <AdminRouteSwitcher current="dashboard" />

        {statsLoading ? (
          <div className="admin-kpi-grid" aria-label={t('admin2.adm_kpi_loading_aria')} aria-busy="true">
            <Skeleton type="card" count={6} />
          </div>
        ) : statsError ? (
          <MacOSEmptyState
            icon={AlertCircle}
            title={t('admin2.adm_error_load_stats')}
            description={t('admin2.adm_error_load_stats_desc')}
            action={(
              <Button onClick={refreshStats} variant="primary">
                <RefreshCw size={16 as unknown as "small" | "default" | "large" | "xlarge"} />
                {t('admin2.adm_retry')}
              </Button>
            )}
          />
        ) : (
          <div className="admin-kpi-grid" role="list" aria-label={t('admin2.adm_kpi_list_aria')}>
            {dashboardKpis.map((kpi) => (
              <div key={kpi.key} role="listitem">
                <MacOSStatCard
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

        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-24">
          <MacOSCard className="admin-bg-var-mac-gradient-sid-bd-1px-solid-var-mac-ma-radius-24-bsh-none-bflt-var-mac-blur-light-webkitba-var-mac-blur-light-p-24">
            <div className="admin-p-16-d-flex-ai-center-jc-between-mb-16">
              <h3 className="admin-fs-lg-fw-semi-primary-m-0">{t('admin2.adm_activity_system')}</h3>
              <Button variant="outline" size="small" onClick={handleExportActivity} disabled={!activityChartData?.data?.length}>
                <Download className="w-4 h-4 mr-2" aria-hidden="true" />
                {t('admin2.adm_export')}
              </Button>
            </div>
            {activityChartLoading ? (
              <div className="admin-h-256-radius-var-mac-radius-md-d-flex-ai-center-jc-center-bg-dyn" style={{ '--admin-bg0': adminSurface } as CSSProperties}>
                <Skeleton type="text" count={3} />
              </div>
            ) : activityChartError ? (
              <div className="admin-h-256-radius-var-mac-radius-md-d-flex-ai-center-jc-center-bg-dyn" style={{ '--admin-bg0': adminSurface } as CSSProperties}>
                <MacOSEmptyState
                  icon={AlertTriangle}
                  title={t('admin2.adm_error_load_chart')}
                  description={t('admin2.adm_error_load_chart_desc')}
                />
              </div>
            ) : activityChartData?.data && activityChartData.data.length > 0 ? (
              <div className="admin-h-256-radius-var-mac-radius-md-p-16-d-flex-fd-column-jc-between-bg-dyn-bd-dyn" style={{ '--admin-bg0': adminSurface, '--admin-bd1': adminBorder } as CSSProperties}>
                <div className="admin-d-flex-ai-end-jc-around-h-200-gap-4">
                  {activityChartData.data.map((item, index) => {
                    const maxValue = Math.max(...activityChartData.data.map((entry) => entry.total || 0));
                    const height = maxValue > 0 ? (item.total / maxValue) * 180 : 0;
                    return (
                      <div key={`${activityChartData.labels?.[index] || 'activity'}-${index}`} className="admin-flex-1-d-flex-fd-column-ai-center-gap-4">
                        <div className="admin-w-100pct-bg-linear-gradient-to-t-radius-4px-4px-0-0-minh-4-tr-height-0-3s-ease-h-dyn" style={{ '--admin-h0': `${height}px` } as CSSProperties} />
                        <span className="admin-fs-10-tertiary-ta-center">
                          {activityChartData.labels[index]}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="admin-d-flex-jc-around-mt-8-fs-12-col-dyn" style={{ '--admin-col0': adminTextSecondary } as CSSProperties}>
                  <span>{t('admin2.adm_chart_appointments_count', { count: activityChartData.data.reduce((sum, entry) => sum + (entry.appointments || 0), 0) })}</span>
                  <span>{t('admin2.adm_chart_payments_count', { count: activityChartData.data.reduce((sum, entry) => sum + (entry.payments || 0), 0) })}</span>
                  <span>{t('admin2.adm_chart_users_count', { count: activityChartData.data.reduce((sum, entry) => sum + (entry.users || 0), 0) })}</span>
                </div>
              </div>
            ) : (
              <div className="admin-h-256-radius-var-mac-radius-md-d-flex-ai-center-jc-center-bg-dyn" style={{ '--admin-bg0': adminSurface } as CSSProperties}>
                <div className="text-center">
                  <Activity className="admin-w-48-h-48-m-0-auto-16px-auto-col-dyn" style={{ '--admin-col0': adminTextSecondary } as CSSProperties} />
                  <p className="admin-col-dyn" style={{ '--admin-col0': adminTextSecondary } as CSSProperties}>{t('admin2.adm_no_data_period')}</p>
                </div>
              </div>
            )}
          </MacOSCard>

          <MacOSCard className="admin-bg-var-mac-gradient-sid-bd-1px-solid-var-mac-ma-radius-24-bsh-none-bflt-var-mac-blur-light-webkitba-var-mac-blur-light-p-0-1">
            <div className="admin-p-16-d-flex-ai-center-jc-between-mb-16">
              <h3 className="admin-fs-lg-fw-semi-primary-m-0">{t('admin2.adm_recent_actions')}</h3>
              <Button variant="outline" size="small" onClick={handleViewAllActivities} disabled={recentActivities.length === 0}>
                <Eye className="w-4 h-4 mr-2" aria-hidden="true" />
                {t('admin2.adm_view_all')}
              </Button>
            </div>
            {recentActivitiesLoading ? (
              <div className="p-4">
                <Skeleton type="text" count={4} />
              </div>
            ) : recentActivitiesError ? (
              <div className="p-4">
                <MacOSEmptyState
                  icon={AlertTriangle}
                  title={t('admin2.adm_error_load')}
                  description={t('admin2.adm_error_load_recent_actions_desc')}
                />
              </div>
            ) : recentActivities.length === 0 ? (
              <div className="admin-p-16-ta-center">
                <p className="text-[var(--mac-text-secondary)]">{t('admin2.adm_no_recent_actions')}</p>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {recentActivities.map((activity) => (
                  <div key={activity.id} className="admin-d-flex-ai-center-gap-12-p-12-radius-var-mac-radius-md-bg-dyn-bd-dyn" style={{ '--admin-bg0': adminInsetSurface, '--admin-bd1': adminBorder } as CSSProperties}>
                    {getStatusIcon(activity.status)}
                    <div className="admin-flex-1">
                      <p className="admin-fs-sm-fw-med-primary-m-0">{activity.message}</p>
                      <p className="admin-fs-xs-secondary-m-4px-0-0-0">{activity.user} · {activity.time || formatTimeAgo(activity.created_at, t)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </MacOSCard>
        </div>

        <MacOSCard className="admin-bg-var-mac-gradient-sid-bd-1px-solid-var-mac-ma-radius-24-bsh-none-bflt-var-mac-blur-light-webkitba-var-mac-blur-light-p-0-mt-24">
          <div className="admin-p-16-d-flex-ai-center-jc-between-mb-16">
            <h3 className="admin-fs-lg-fw-semi-primary-m-0">{t('admin2.adm_system_notifications')}</h3>
            <Badge variant="warning">{systemAlerts.length}</Badge>
          </div>
          {systemAlertsLoading ? (
            <div className="p-4">
              <Skeleton type="text" count={3} />
            </div>
          ) : systemAlertsError ? (
            <div className="p-4">
              <MacOSEmptyState
                icon={AlertTriangle}
                title={t('admin2.adm_error_load')}
                description={t('admin2.adm_error_load_system_notifications_desc')}
              />
            </div>
          ) : systemAlerts.length === 0 ? (
            <div className="admin-p-16-ta-center">
              <p className="text-[var(--mac-text-secondary)]">{t('admin2.adm_no_system_notifications')}</p>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {systemAlerts.map((alert) => (
                <div key={alert.id} className="admin-d-flex-ai-center-gap-12-p-12-radius-var-mac-radius-md-bd-dyn-bg-dyn" style={{ '--admin-bd0': adminBorder, '--admin-bg1': adminInsetSurface } as CSSProperties}>
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
          )}
        </MacOSCard>
      </div>
    </ErrorBoundary>
  );
};

export default AdminDashboard;
