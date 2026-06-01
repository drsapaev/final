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
  MacOSBadge,
  MacOSEmptyState,
  MacOSButton,
  MacOSLoadingSkeleton,
  MacOSStatCard,
} from '../ui/macos';
import useAdminData from '../../hooks/useAdminData';
import AdminRouteSwitcher from './AdminRouteSwitcher';
import ErrorBoundary from './ErrorBoundary';

const adminSurface = 'linear-gradient(180deg, color-mix(in srgb, var(--mac-card-bg), white 72%) 0%, color-mix(in srgb, var(--mac-card-bg), white 64%) 100%)';
const adminSurfaceStrong = 'linear-gradient(180deg, color-mix(in srgb, var(--mac-card-bg), white 78%) 0%, color-mix(in srgb, var(--mac-card-bg), white 70%) 100%)';
const adminInsetSurface = 'color-mix(in srgb, var(--mac-card-bg), white 82%)';
const adminBorder = '1px solid color-mix(in srgb, var(--mac-card-border), white 12%)';
const adminTextSecondary = 'color-mix(in srgb, var(--mac-text-secondary), black 42%)';

const adminSectionShellStyle = {
  background: 'var(--mac-gradient-sidebar)',
  border: '1px solid var(--mac-main-shell-border)',
  borderRadius: '24px',
  boxShadow: 'none',
  backdropFilter: 'var(--mac-blur-light)',
  WebkitBackdropFilter: 'var(--mac-blur-light)',
};

const adminKpiGridStyle = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
  gap: 'var(--mac-spacing-6)',
};

const adminKpiCardStyle = {
  minHeight: '112px',
  background: adminSurfaceStrong,
  border: adminBorder,
};

const defaultStats = {
  totalUsers: 0,
  totalDoctors: 0,
  totalPatients: 0,
  totalRevenue: 0,
  appointmentsToday: 0,
  pendingApprovals: 0,
};

function formatCurrency(amount) {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'UZS',
    minimumFractionDigits: 0,
  }).format(amount);
}

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

  if (status === 'success') return <CheckCircle style={{ width: '16px', height: '16px', color: colorMap.success }} />;
  if (status === 'warning') return <AlertTriangle style={{ width: '16px', height: '16px', color: colorMap.warning }} />;
  if (status === 'error') return <AlertTriangle style={{ width: '16px', height: '16px', color: colorMap.error }} />;
  if (status === 'info') return <Clock style={{ width: '16px', height: '16px', color: colorMap.info }} />;
  return <Clock style={{ width: '16px', height: '16px', color: colorMap.default }} />;
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

  const dashboardKpis = React.useMemo(() => [
    {
      key: 'users',
      title: 'Всего пользователей',
      value: stats.totalUsers || 0,
      icon: Users,
      color: 'blue',
    },
    {
      key: 'doctors',
      title: 'Врачи',
      value: stats.totalDoctors || 0,
      icon: Stethoscope,
      color: 'green',
    },
    {
      key: 'patients',
      title: 'Пациенты',
      value: stats.totalPatients || 0,
      icon: Users,
      color: 'purple',
    },
    {
      key: 'revenue',
      title: 'Доход',
      value: formatCurrency(stats.totalRevenue || 0),
      icon: TrendingUp,
      color: 'green',
    },
    {
      key: 'appointments-today',
      title: 'Записи сегодня',
      value: stats.appointmentsToday || 0,
      icon: Calendar,
      color: 'orange',
    },
    {
      key: 'pending-approvals',
      title: 'Ожидают подтверждения',
      value: stats.pendingApprovals || 0,
      icon: Clock,
      color: 'red',
    },
  ], [stats]);

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <AdminRouteSwitcher current="dashboard" />

        {statsLoading ? (
          <div style={adminKpiGridStyle} aria-label="Загрузка ключевых показателей администратора" aria-busy="true">
            <MacOSLoadingSkeleton type="card" count={6} />
          </div>
        ) : statsError ? (
          <MacOSEmptyState
            icon={AlertCircle}
            title="Ошибка загрузки статистики"
            description="Не удалось загрузить данные. Проверьте подключение к серверу."
            action={(
              <MacOSButton onClick={refreshStats} variant="primary">
                <RefreshCw size={16} />
                Повторить попытку
              </MacOSButton>
            )}
          />
        ) : (
          <div style={adminKpiGridStyle} role="list" aria-label="Ключевые показатели администратора">
            {dashboardKpis.map((kpi) => (
              <div key={kpi.key} role="listitem">
                <MacOSStatCard
                  title={kpi.title}
                  value={kpi.value}
                  icon={kpi.icon}
                  color={kpi.color}
                  loading={statsLoading}
                  style={adminKpiCardStyle}
                />
              </div>
            ))}
          </div>
        )}

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px',
        }}>
          <MacOSCard style={{ ...adminSectionShellStyle, padding: '24px' }}>
            <div style={{ padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                margin: 0,
              }}>Активность системы</h3>
              <MacOSButton variant="outline" size="sm">
                <Download style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                Экспорт
              </MacOSButton>
            </div>
            {activityChartLoading ? (
              <div style={{
                height: '256px',
                borderRadius: 'var(--mac-radius-md)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: adminSurface,
              }}>
                <MacOSLoadingSkeleton type="text" count={3} />
              </div>
            ) : activityChartError ? (
              <div style={{
                height: '256px',
                borderRadius: 'var(--mac-radius-md)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: adminSurface,
              }}>
                <MacOSEmptyState
                  icon={AlertTriangle}
                  title="Ошибка загрузки графика"
                  description="Не удалось загрузить данные активности"
                />
              </div>
            ) : activityChartData?.data && activityChartData.data.length > 0 ? (
              <div style={{
                height: '256px',
                borderRadius: 'var(--mac-radius-md)',
                padding: '16px',
                background: adminSurface,
                border: adminBorder,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'flex-end',
                  justifyContent: 'space-around',
                  height: '200px',
                  gap: '4px',
                }}>
                  {activityChartData.data.map((item, index) => {
                    const maxValue = Math.max(...activityChartData.data.map((entry) => entry.total || 0));
                    const height = maxValue > 0 ? (item.total / maxValue) * 180 : 0;
                    return (
                      <div key={`${activityChartData.labels?.[index] || 'activity'}-${index}`} style={{
                        flex: 1,
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: '4px',
                      }}>
                        <div style={{
                          width: '100%',
                          height: `${height}px`,
                          background: 'linear-gradient(to top, #2563eb, #60a5fa)',
                          borderRadius: '4px 4px 0 0',
                          minHeight: '4px',
                          transition: 'height 0.3s ease',
                        }} />
                        <span style={{
                          fontSize: '10px',
                          color: 'var(--mac-text-tertiary)',
                          textAlign: 'center',
                        }}>
                          {activityChartData.labels[index]}
                        </span>
                      </div>
                    );
                  })}
                </div>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-around',
                  marginTop: '8px',
                  fontSize: '12px',
                  color: adminTextSecondary,
                }}>
                  <span>Записи: {activityChartData.data.reduce((sum, entry) => sum + (entry.appointments || 0), 0)}</span>
                  <span>Платежи: {activityChartData.data.reduce((sum, entry) => sum + (entry.payments || 0), 0)}</span>
                  <span>Пользователи: {activityChartData.data.reduce((sum, entry) => sum + (entry.users || 0), 0)}</span>
                </div>
              </div>
            ) : (
              <div style={{
                height: '256px',
                borderRadius: 'var(--mac-radius-md)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: adminSurface,
              }}>
                <div style={{ textAlign: 'center' }}>
                  <Activity style={{
                    width: '48px',
                    height: '48px',
                    margin: '0 auto 16px auto',
                    color: adminTextSecondary,
                  }} />
                  <p style={{ color: adminTextSecondary }}>Нет данных за выбранный период</p>
                </div>
              </div>
            )}
          </MacOSCard>

          <MacOSCard style={{ ...adminSectionShellStyle, padding: 0 }}>
            <div style={{ padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                margin: 0,
              }}>Последние действия</h3>
              <MacOSButton variant="outline" size="sm">
                <Eye style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                Все
              </MacOSButton>
            </div>
            {recentActivitiesLoading ? (
              <div style={{ padding: '16px' }}>
                <MacOSLoadingSkeleton type="text" count={4} />
              </div>
            ) : recentActivitiesError ? (
              <div style={{ padding: '16px' }}>
                <MacOSEmptyState
                  icon={AlertTriangle}
                  title="Ошибка загрузки"
                  description="Не удалось загрузить последние действия"
                />
              </div>
            ) : recentActivities.length === 0 ? (
              <div style={{ padding: '16px', textAlign: 'center' }}>
                <p style={{ color: 'var(--mac-text-secondary)' }}>Нет последних действий</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {recentActivities.map((activity) => (
                  <div key={activity.id} style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '12px',
                    borderRadius: 'var(--mac-radius-md)',
                    background: adminInsetSurface,
                    border: adminBorder,
                  }}>
                    {getStatusIcon(activity.status)}
                    <div style={{ flex: '1' }}>
                      <p style={{
                        fontSize: 'var(--mac-font-size-sm)',
                        fontWeight: 'var(--mac-font-weight-medium)',
                        color: 'var(--mac-text-primary)',
                        margin: 0,
                      }}>{activity.message}</p>
                      <p style={{
                        fontSize: 'var(--mac-font-size-xs)',
                        color: 'var(--mac-text-secondary)',
                        margin: '4px 0 0 0',
                      }}>{activity.user} · {activity.time || formatTimeAgo(activity.created_at)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </MacOSCard>
        </div>

        <MacOSCard style={{ ...adminSectionShellStyle, padding: 0, marginTop: '24px' }}>
          <div style={{ padding: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 style={{
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              margin: 0,
            }}>Системные уведомления</h3>
            <MacOSBadge variant="warning">{systemAlerts.length}</MacOSBadge>
          </div>
          {systemAlertsLoading ? (
            <div style={{ padding: '16px' }}>
              <MacOSLoadingSkeleton type="text" count={3} />
            </div>
          ) : systemAlertsError ? (
            <div style={{ padding: '16px' }}>
              <MacOSEmptyState
                icon={AlertTriangle}
                title="Ошибка загрузки"
                description="Не удалось загрузить системные уведомления"
              />
            </div>
          ) : systemAlerts.length === 0 ? (
            <div style={{ padding: '16px', textAlign: 'center' }}>
              <p style={{ color: 'var(--mac-text-secondary)' }}>Нет системных уведомлений</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {systemAlerts.map((alert) => (
                <div key={alert.id} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '12px',
                  border: adminBorder,
                  borderRadius: 'var(--mac-radius-md)',
                  background: adminInsetSurface,
                }}>
                  <AlertTriangle style={{ width: '20px', height: '20px', color: 'var(--mac-warning)' }} />
                  <div style={{ flex: '1' }}>
                    <p style={{
                      fontSize: 'var(--mac-font-size-sm)',
                      fontWeight: 'var(--mac-font-weight-medium)',
                      color: 'var(--mac-text-primary)',
                      margin: 0,
                    }}>{alert.message}</p>
                    <p style={{
                      fontSize: '12px',
                      color: 'var(--mac-text-secondary)',
                      margin: '4px 0 0 0',
                    }}>{alert.time}</p>
                  </div>
                  <MacOSBadge variant={alert.priority === 'high' ? 'error' : alert.priority === 'medium' ? 'warning' : 'info'}>
                    {alert.priority}
                  </MacOSBadge>
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
