import { t } from '../../i18n/adapter';
import React from 'react';
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


function formatTimeAgo(date) {
  if (!date) return 'Недавно';

  const dateObj = typeof date === 'string' ? new Date(date) : date;
  if (Number.isNaN(dateObj.getTime())) return 'Недавно';

  const now = new Date();
  const diff = now - dateObj;
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (seconds < 60) return 'только что';
  if (minutes < 60) return `${minutes} ${minutes === 1 ? 'минуту' : minutes < 5 ? 'минуты' : 'минут'} назад`;
  if (hours < 24) return `${hours} ${hours === 1 ? 'час' : hours < 5 ? 'часа' : 'часов'} назад`;
  if (days < 7) return `${days} ${days === 1 ? 'день' : days < 5 ? 'дня' : 'дней'} назад`;
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

  if (status === 'success') return <CheckCircle className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.success }} />;
  if (status === 'warning') return <AlertTriangle className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.warning }} />;
  if (status === 'error') return <AlertTriangle className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.error }} />;
  if (status === 'info') return <Clock className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.info }} />;
  return <Clock className="admin-w-16-h-16-col-dyn" style={{ '--admin-col0': colorMap.default }} />;
}

function buildSystemAlerts(systemAlertsData) {
  if (!systemAlertsData?.recent_activity) return [];

  return systemAlertsData.recent_activity.slice(0, 5).map((alert, index) => ({
    id: alert.id || index + 1,
    type: alert.status === 'failed' ? 'error' : alert.status === 'pending' ? 'warning' : 'info',
    message: alert.message || alert.notification_type || 'Системное уведомление',
    priority: alert.status === 'failed' ? 'high' : alert.status === 'pending' ? 'medium' : 'low',
    time: alert.created_at ? formatTimeAgo(new Date(alert.created_at)) : 'Недавно',
  }));
}

// UX Audit Stage 3 (Dashboard issue 4.2): локализация приоритета уведомлений.
// Раньше отображались английские 'high'/'medium'/'low' в русском UI.
const PRIORITY_LABELS = {
  high: 'Высокий',
  medium: 'Средний',
  low: 'Низкий',
};

function getPriorityLabel(priority) {
  return PRIORITY_LABELS[priority] || priority;
}

// UX Audit Stage 3 (Dashboard issue 4.1):
// Helper для экспорта данных активности в CSV.
// Раньше кнопка «Экспорт» не имела onClick — была кнопкой-призраком.
function exportActivityToCsv(chartData) {
  if (!chartData?.data || chartData.data.length === 0) {
    return;
  }

  const headers = ['Дата', 'Записи', 'Платежи', 'Пользователи', 'Всего'];
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
  const {
    data: statsData,
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
    data: activityChartData,
    loading: activityChartLoading,
    error: activityChartError,
  } = useAdminData('/admin/activity-chart?days=7', {
    refreshInterval: 0,
    enabled: true,
    initialData: { labels: [], data: [] },
  });

  const stats = statsData || defaultStats;
  const recentActivities = recentActivitiesData?.activities || [];
  const systemAlerts = React.useMemo(() => buildSystemAlerts(systemAlertsData), [systemAlertsData]);

  // UX Audit Stage 3 (Dashboard issue 4.1):
  // Handlers для кнопок «Экспорт» и «Все».
  // Раньше это были кнопки-призраки без onClick.
  const handleExportActivity = React.useCallback(() => {
    exportActivityToCsv(activityChartData);
  }, [activityChartData]);

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
          <div className="admin-kpi-grid" aria-label="Загрузка ключевых показателей администратора" aria-busy="true">
            <Skeleton type="card" count={6} />
          </div>
        ) : statsError ? (
          <MacOSEmptyState
            icon={AlertCircle}
            title="Ошибка загрузки статистики"
            description="Не удалось загрузить данные. Проверьте подключение к серверу."
            action={(
              <Button onClick={refreshStats} variant="primary">
                <RefreshCw size={16} />
                Повторить попытку
              </Button>
            )}
          />
        ) : (
          <div className="admin-kpi-grid" role="list" aria-label="Ключевые показатели администратора">
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
              <h3 className="admin-fs-lg-fw-semi-primary-m-0">Активность системы</h3>
              <Button variant="outline" size="sm" onClick={handleExportActivity} disabled={!activityChartData?.data?.length}>
                <Download className="w-4 h-4 mr-2" aria-hidden="true" />
                Экспорт
              </Button>
            </div>
            {activityChartLoading ? (
              <div className="admin-h-256-radius-var-mac-radius-md-d-flex-ai-center-jc-center-bg-dyn" style={{ '--admin-bg0': adminSurface }}>
                <Skeleton type="text" count={3} />
              </div>
            ) : activityChartError ? (
              <div className="admin-h-256-radius-var-mac-radius-md-d-flex-ai-center-jc-center-bg-dyn" style={{ '--admin-bg0': adminSurface }}>
                <MacOSEmptyState
                  icon={AlertTriangle}
                  title="Ошибка загрузки графика"
                  description="Не удалось загрузить данные активности"
                />
              </div>
            ) : activityChartData?.data && activityChartData.data.length > 0 ? (
              <div className="admin-h-256-radius-var-mac-radius-md-p-16-d-flex-fd-column-jc-between-bg-dyn-bd-dyn" style={{ '--admin-bg0': adminSurface, '--admin-bd1': adminBorder }}>
                <div className="admin-d-flex-ai-end-jc-around-h-200-gap-4">
                  {activityChartData.data.map((item, index) => {
                    const maxValue = Math.max(...activityChartData.data.map((entry) => entry.total || 0));
                    const height = maxValue > 0 ? (item.total / maxValue) * 180 : 0;
                    return (
                      <div key={`${activityChartData.labels?.[index] || 'activity'}-${index}`} className="admin-flex-1-d-flex-fd-column-ai-center-gap-4">
                        <div className="admin-w-100pct-bg-linear-gradient-to-t-radius-4px-4px-0-0-minh-4-tr-height-0-3s-ease-h-dyn" style={{ '--admin-h0': `${height}px` }} />
                        <span className="admin-fs-10-tertiary-ta-center">
                          {activityChartData.labels[index]}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div className="admin-d-flex-jc-around-mt-8-fs-12-col-dyn" style={{ '--admin-col0': adminTextSecondary }}>
                  <span>Записи: {activityChartData.data.reduce((sum, entry) => sum + (entry.appointments || 0), 0)}</span>
                  <span>Платежи: {activityChartData.data.reduce((sum, entry) => sum + (entry.payments || 0), 0)}</span>
                  <span>Пользователи: {activityChartData.data.reduce((sum, entry) => sum + (entry.users || 0), 0)}</span>
                </div>
              </div>
            ) : (
              <div className="admin-h-256-radius-var-mac-radius-md-d-flex-ai-center-jc-center-bg-dyn" style={{ '--admin-bg0': adminSurface }}>
                <div className="text-center">
                  <Activity className="admin-w-48-h-48-m-0-auto-16px-auto-col-dyn" style={{ '--admin-col0': adminTextSecondary }} />
                  <p className="admin-col-dyn" style={{ '--admin-col0': adminTextSecondary }}>Нет данных за выбранный период</p>
                </div>
              </div>
            )}
          </MacOSCard>

          <MacOSCard className="admin-bg-var-mac-gradient-sid-bd-1px-solid-var-mac-ma-radius-24-bsh-none-bflt-var-mac-blur-light-webkitba-var-mac-blur-light-p-0-1">
            <div className="admin-p-16-d-flex-ai-center-jc-between-mb-16">
              <h3 className="admin-fs-lg-fw-semi-primary-m-0">Последние действия</h3>
              <Button variant="outline" size="sm" onClick={handleViewAllActivities} disabled={recentActivities.length === 0}>
                <Eye className="w-4 h-4 mr-2" aria-hidden="true" />
                Все
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
                  title="Ошибка загрузки"
                  description="Не удалось загрузить последние действия"
                />
              </div>
            ) : recentActivities.length === 0 ? (
              <div className="admin-p-16-ta-center">
                <p className="text-[var(--mac-text-secondary)]">Нет последних действий</p>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {recentActivities.map((activity) => (
                  <div key={activity.id} className="admin-d-flex-ai-center-gap-12-p-12-radius-var-mac-radius-md-bg-dyn-bd-dyn" style={{ '--admin-bg0': adminInsetSurface, '--admin-bd1': adminBorder }}>
                    {getStatusIcon(activity.status)}
                    <div className="admin-flex-1">
                      <p className="admin-fs-sm-fw-med-primary-m-0">{activity.message}</p>
                      <p className="admin-fs-xs-secondary-m-4px-0-0-0">{activity.user} · {activity.time || formatTimeAgo(activity.created_at)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </MacOSCard>
        </div>

        <MacOSCard className="admin-bg-var-mac-gradient-sid-bd-1px-solid-var-mac-ma-radius-24-bsh-none-bflt-var-mac-blur-light-webkitba-var-mac-blur-light-p-0-mt-24">
          <div className="admin-p-16-d-flex-ai-center-jc-between-mb-16">
            <h3 className="admin-fs-lg-fw-semi-primary-m-0">Системные уведомления</h3>
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
                title="Ошибка загрузки"
                description="Не удалось загрузить системные уведомления"
              />
            </div>
          ) : systemAlerts.length === 0 ? (
            <div className="admin-p-16-ta-center">
              <p className="text-[var(--mac-text-secondary)]">Нет системных уведомлений</p>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {systemAlerts.map((alert) => (
                <div key={alert.id} className="admin-d-flex-ai-center-gap-12-p-12-radius-var-mac-radius-md-bd-dyn-bg-dyn" style={{ '--admin-bd0': adminBorder, '--admin-bg1': adminInsetSurface }}>
                  <AlertTriangle className="admin-w-20-h-20-warning" />
                  <div className="admin-flex-1">
                    <p className="admin-fs-sm-fw-med-primary-m-0">{alert.message}</p>
                    <p className="admin-fs-12-secondary-m-4px-0-0-0">{alert.time}</p>
                  </div>
                  <Badge variant={alert.priority === 'high' ? 'error' : alert.priority === 'medium' ? 'warning' : 'info'}>
                    {/* UX Audit Stage 3 (Dashboard issue 4.2): локализация приоритета. */}
                    {getPriorityLabel(alert.priority)}
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
