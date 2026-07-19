import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect } from 'react';
import type { CSSProperties } from 'react';
import {
  Server,
  Database,
  Shield,
  Download,

  RefreshCw,
  AlertTriangle,
  CheckCircle,

  HardDrive,
  Cpu,
  MemoryStick,
  Activity,
  Settings,
  Trash2,
  Eye,





  AlertCircle,
  Info } from
'lucide-react';
import {
  MacOSCard,
  Button,
  Badge,
  Input,
  Checkbox,
  Table,
  MacOSEmptyState,
  Select,
} from '../ui/macos';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';
const SystemManagement = () => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;
  const [activeTab, setActiveTab] = useState('monitoring');
  const [loading, setLoading] = useState(false);

  // Состояние мониторинга
  const [systemHealth, setSystemHealth] = useState(null as any);
  const [systemMetrics, setSystemMetrics] = useState(null as any);
  const [alerts, setAlerts] = useState([]);
  // UX Audit Admin #4.8: alerts display limit for pagination.
  const [alertsLimit, setAlertsLimit] = useState(10);
  const [thresholds, setThresholds] = useState({} as any);

  // Состояние бэкапов
  const [backups, setBackups] = useState([]);
  const [backupForm, setBackupForm] = useState({
    backup_type: 'database',
    include_files: true,
    description: ''
  } as any);

  useEffect(() => {
    if (activeTab === 'monitoring') {
      loadSystemHealth();
      loadSystemMetrics();
      loadAlerts();
      loadThresholds();
    } else if (activeTab === 'backups') {
      loadBackups();
    }
  }, [activeTab]);

  // ===================== МОНИТОРИНГ =====================

  const loadSystemHealth = async () => {
    try {
      const { data } = await api.get('/system/monitoring/health');
      setSystemHealth(data);
    } catch (error) {
      logger.error('Ошибка загрузки состояния системы:', error);
    }
  };

  const loadSystemMetrics = async () => {
    try {
      const { data } = await api.get('/system/monitoring/metrics/system');
      setSystemMetrics(data.metrics);
    } catch (error) {
      logger.error('Ошибка загрузки метрик системы:', error);
    }
  };

  const loadAlerts = async () => {
    try {
      const { data } = await api.get('/system/monitoring/alerts', { params: { limit: 50 } });
      setAlerts(data.alerts || []);
    } catch (error) {
      logger.error('Ошибка загрузки алертов:', error);
    }
  };

  const loadThresholds = async () => {
    try {
      const { data } = await api.get('/system/monitoring/thresholds');
      setThresholds(data.thresholds || {});
    } catch (error) {
      logger.error('Ошибка загрузки порогов:', error);
    }
  };

  const collectMetricsNow = async () => {
    try {
      const { status } = await api.post('/system/monitoring/collect');
      if (status === 200 || status === 202) {
        toast.success(t('admin2.sm_metrics_collected'));
        loadSystemMetrics();
        loadSystemHealth();
      } else {
        toast.error(t('admin2.sm_metrics_collect_error'));
      }
    } catch (error) {
      logger.error('Ошибка сбора метрик:', error);
      toast.error(t('admin2.sm_metrics_collect_error'));
    }
  };

  // ===================== БЭКАПЫ =====================

  const loadBackups = async () => {
    try {
      const response = await api.get('/system/backup/list') as any;
      setBackups(response.data?.backups || []);
    } catch (error) {
      logger.error('Ошибка загрузки бэкапов:', error);
    }
  };

  const createBackup = async () => {
    setLoading(true);
    try {
      const response = await api.post('/system/backup/create', backupForm) as any;
      if (response.data?.success) {
        toast.success(t('admin2.sm_backup_creating'));
        setTimeout(() => loadBackups(), 2000); // Обновляем список через 2 секунды
      } else {
        toast.error(response.data?.error || t('admin2.sm_backup_create_error'));
      }
    } catch (error) {
      logger.error('Ошибка создания бэкапа:', error);
      toast.error(error.response?.data?.detail || t('admin2.sm_backup_create_error'));
    } finally {
      setLoading(false);
    }
  };

  const deleteBackup = async (backupName) => {
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: t('admin2.delete_backup_title'),
      message: t('admin2.sm_delete_backup_message', { name: backupName }),
      description: t('admin2.sm_delete_backup_desc'),
      confirmLabel: t('admin2.delete_confirm'),
      cancelLabel: t('admin2.cancel'),
      intent: 'danger',
    });
    if (!ok) {
      return;
    }

    try {
      const response = await api.delete(`/system/backup/${backupName}`) as any;
      if (response.data?.success) {
        toast.success(t('admin2.sm_backup_deleted'));
        loadBackups();
      } else {
        toast.error(response.data?.error || t('admin2.sm_backup_delete_error'));
      }
    } catch (error) {
      logger.error('Ошибка удаления бэкапа:', error);
      toast.error(t('admin2.sm_backup_delete_error'));
    }
  };

  // ===================== УТИЛИТЫ =====================

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy':return 'var(--mac-success)';
      case 'warning':return 'var(--mac-warning)';
      case 'critical':return 'var(--mac-error)';
      default:return 'var(--mac-text-tertiary)';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy':return CheckCircle;
      case 'warning':return AlertTriangle;
      case 'critical':return AlertCircle;
      default:return Info;
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical':return 'error';
      case 'warning':return 'warning';
      case 'info':return 'info';
      default:return 'default';
    }
  };

  // UX Audit Admin #2.4: русские лейблы для severity (consistency с AdminDashboard).
  const getSeverityLabel = (s) => {
    const map = {
      critical: t('admin2.sm_severity_critical'),
      warning: t('admin2.sm_severity_warning'),
      info: t('admin2.sm_severity_info'),
    };
    return map[s] || t('admin2.sm_severity_info');
  };

  // ===================== РЕНДЕРИНГ =====================

  const renderMonitoringTab = () =>
  <div className="flex flex-col gap-6">
      {/* Общее состояние системы */}
      <MacOSCard className="p-6">
        <div className="admin-flex-between-mb-16">
          <h3 className="admin-h3-icon-m0">
            <Activity className="w-5 h-5" />
            {t('admin2.sm_system_state')}
          </h3>
          <Button
          onClick={collectMetricsNow}
          variant="outline"
          size="small">

            <RefreshCw className="w-4 h-4 mr-2" />
            {t('admin2.sm_refresh')}
          </Button>
        </div>

        {systemHealth &&
      <div className="admin-grid-auto-200">
            <div className="text-center">
              <div className="admin-stat-value-dynamic" style={{ '--admin-stat-color': getStatusColor(systemHealth.overall_status) } as CSSProperties}>
                {systemHealth.overall_status?.toUpperCase()}
              </div>
              <div className="admin-text-sm-secondary">
                {t('admin2.sm_overall_status')}
              </div>
            </div>
            
            {systemHealth.components && Object.entries(systemHealth.components).map(([component, status]) => {
          const StatusIcon = getStatusIcon(status);
          return (
            <div key={component} className="text-center">
                  <StatusIcon className="admin-status-icon-32" style={{ '--admin-icon-color': getStatusColor(status) } as CSSProperties} />
                  <div className="admin-text-med-primary-block">
                    {component}
                  </div>
                  <div className="admin-stat-value-sm-dynamic" style={{ '--admin-stat-color': getStatusColor(status) } as CSSProperties}>
                    {status as React.ReactNode}
                  </div>
                </div>);

        })}
          </div>
      }
      </MacOSCard>

      {/* Системные метрики */}
      {systemMetrics &&
    <div className="admin-grid-auto-300-24">
          {/* CPU */}
          <MacOSCard className="p-6">
            <div className="admin-flex-between-mb-16">
              <h4 className="admin-metric-h4">
                <Cpu className="w-4 h-4" />
                CPU
              </h4>
              <Badge variant={systemMetrics.cpu?.usage_percent > 80 ? 'error' : 'success'}>
                {systemMetrics.cpu?.usage_percent?.toFixed(1)}%
              </Badge>
            </div>
            <div className="flex flex-col gap-2">
              <div className="admin-text-sm-primary">
                {t('admin2.sm_cores', { count: systemMetrics.cpu?.count })}
            </div>
              {systemMetrics.cpu?.frequency &&
          <div className="admin-text-sm-primary">
                  {t('admin2.sm_frequency', { freq: systemMetrics.cpu.frequency.toFixed(0) })}
                </div>
          }
            </div>
          </MacOSCard>

          {/* Память */}
          <MacOSCard className="p-6">
            <div className="admin-flex-between-mb-16">
              <h4 className="admin-metric-h4">
                <MemoryStick className="w-4 h-4" />
                {t('admin2.sm_memory')}
              </h4>
              <Badge variant={systemMetrics.memory?.usage_percent > 85 ? 'error' : 'success'}>
                {systemMetrics.memory?.usage_percent?.toFixed(1)}%
              </Badge>
            </div>
            <div className="flex flex-col gap-2">
              <div className="admin-text-sm-primary">
                {t('admin2.sm_total')} {formatBytes(systemMetrics.memory?.total)}
              </div>
              <div className="admin-text-sm-primary">
                {t('admin2.sm_used')} {formatBytes(systemMetrics.memory?.used)}
              </div>
              <div className="admin-text-sm-primary">
                {t('admin2.sm_available')} {formatBytes(systemMetrics.memory?.available)}
            </div>
            </div>
          </MacOSCard>

          {/* Диск */}
          <MacOSCard className="p-6">
            <div className="admin-flex-between-mb-16">
              <h4 className="admin-metric-h4">
                <HardDrive className="w-4 h-4" />
                {t('admin2.sm_disk')}
              </h4>
              <Badge variant={systemMetrics.disk?.usage_percent > 90 ? 'error' : 'success'}>
                {systemMetrics.disk?.usage_percent?.toFixed(1)}%
              </Badge>
            </div>
            <div className="flex flex-col gap-2">
              <div className="admin-text-sm-primary">
                {t('admin2.sm_total')} {formatBytes(systemMetrics.disk?.total)}
              </div>
              <div className="admin-text-sm-primary">
                {t('admin2.sm_used')} {formatBytes(systemMetrics.disk?.used)}
              </div>
              <div className="admin-text-sm-primary">
                {t('admin2.sm_free')} {formatBytes(systemMetrics.disk?.free)}
            </div>
            </div>
          </MacOSCard>
        </div>
    }

      {/* Алерты */}
      <MacOSCard className="p-6">
        <h3 className="admin-h3-icon-mb-16">
          <AlertTriangle className="w-5 h-5" />
          {t('admin2.sm_recent_alerts')}
        </h3>
        
        {alerts.length === 0 ?
      <MacOSEmptyState
        icon={CheckCircle}
        title={t('admin2.sm_no_active_alerts')}
        description={t('admin2.sm_system_stable')}
        iconStyle={{ width: '48px', height: '48px', color: 'var(--mac-success)' }} /> :
      <>
      {/* UX Audit Admin #4.8: alerts counter + show all button. */}
      {alerts.length > 0 && (
        <div className="admin-sysmgmt-hint">
          {t('admin2.sm_alerts_shown', { shown: Math.min(alertsLimit, alerts.length), total: alerts.length })}
          {alerts.length > alertsLimit && (
            <button
              type="button"
              onClick={() => setAlertsLimit(50)}
              className="admin-sysmgmt-link-btn">
              {t('admin2.sm_show_all')}
            </button>
          )}
        </div>
      )}
      <div className="flex flex-col gap-3">
            {alerts.slice(0, alertsLimit).map((alert, index) =>
        <div key={index} className="admin-alert-row">
                <div className="admin-flex-center-12">
                  <Badge variant={getSeverityColor(alert.severity)}>
                    {getSeverityLabel(alert.severity)}
                  </Badge>
                  <span className="admin-text-sm-primary">
                    {alert.message}
                  </span>
                </div>
                <div className="admin-text-sm-secondary">
                  {new Date(alert.timestamp).toLocaleString()}
                </div>
              </div>
        )}
          </div>
      </>
      }
      </MacOSCard>
    </div>;


  const renderBackupsTab = () =>
  <div className="flex flex-col gap-6">
      {/* Создание бэкапа */}
      <MacOSCard className="p-6">
        <h3 className="admin-h3-icon-mb-16">
          <Database className="w-5 h-5" />
          {t('admin2.sm_create_backup_title')}
        </h3>
        
        <div className="admin-grid-auto-200-mb-16">
          <div>
            <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
              {t('admin2.sm_backup_type')}
            </label>
            <Select
            value={backupForm.backup_type}
            onChange={(value) => setBackupForm((prev) => ({ ...prev, backup_type: value }))}
            options={[
            { value: 'database', label: t('admin2.sm_backup_type_database') },
            { value: 'full', label: t('admin2.sm_backup_type_full') },
            { value: 'configuration', label: t('admin2.sm_backup_type_configuration') }]
            }
            size="large"
            className="w-full" />

          </div>

          <div className="flex items-center justify-center">
            <label className="admin-label-flex-pointer">
              <Checkbox
              checked={backupForm.include_files}
              onChange={(checked) => setBackupForm((prev) => ({ ...prev, include_files: checked }))}
              className="mr-2" />

              {t('admin2.sm_include_files')}
            </label>
          </div>

          <div>
            <Button
            onClick={createBackup}
            disabled={loading}
            className="w-full">

              {loading ?
            <RefreshCw className="admin-icon-16-spin-mr-8" /> :

            <Download className="w-4 h-4 mr-2" />
            }
              {t('admin2.sm_btn_create_backup')}
            </Button>
          </div>
        </div>
      </MacOSCard>

      {/* Список бэкапов */}
      <MacOSCard className="p-6">
        <div className="admin-flex-between-mb-16">
          <h3 className="admin-h3-icon-m0">
            <Shield className="w-5 h-5" />
            {t('admin2.sm_backups_list')}
          </h3>
          <Button
          onClick={loadBackups}
          variant="outline"
          size="small">

            <RefreshCw className="w-4 h-4 mr-2" />
            {t('admin2.sm_refresh')}
          </Button>
        </div>

        {backups.length === 0 ?
      <MacOSEmptyState
        icon={Database}
        title={t('admin2.sm_no_backups')}
        description={t('admin2.sm_no_backups_desc')}
        iconStyle={{ width: '48px', height: '48px', color: 'var(--mac-text-tertiary)' }} /> :


      <Table
        columns={[
        { key: 'name', label: t('admin2.sm_col_name') },
        { key: 'type', label: t('admin2.sm_col_type') },
        { key: 'size', label: t('admin2.sm_col_size') },
        { key: 'created_at', label: t('admin2.sm_col_created') },
        { key: 'actions', label: t('admin2.sm_col_actions') }]
        }
        data={backups.map((backup) => ({
          ...backup,
          name:
          <div className="flex items-center justify-center gap-2">
                  <Database className="admin-icon-16-tertiary" />
                  <span className="admin-span-med">{backup.name}</span>
                      </div>,

          type: <Badge variant="outline">{backup.type}</Badge>,
          size: formatBytes(backup.size),
          created_at: new Date(backup.created_at).toLocaleString(),
          actions:
          <div className="admin-flex-end-center-8">
                  <Button
                    type="button"
                    size="small"
                    variant="outline"
                    title={`View backup ${backup.name}`}
                    aria-label={`View backup ${backup.name}`}>
                    <Eye aria-hidden="true" className="w-3.5 h-3.5" />
                  </Button>
                  <Button
              type="button"
              onClick={() => deleteBackup(backup.name)}
              size="small"
              variant="outline"
              title={`Delete backup ${backup.name}`}
              aria-label={`Delete backup ${backup.name}`}
              className="text-[var(--mac-error)]">

                    <Trash2 aria-hidden="true" className="w-3.5 h-3.5" />
                  </Button>
                      </div>

        }))}
        emptyState={
        <MacOSEmptyState
          icon={Database}
          title={t('admin2.sm_no_backups')}
          description={t('admin2.sm_no_backups_desc')} />

        } />

      }
      </MacOSCard>
    </div>;


  const renderSettingsTab = () =>
  <div className="flex flex-col gap-6">
      <MacOSCard className="p-6">
        <h3 className="admin-h3-icon-mb-16">
          <Settings className="w-5 h-5" />
          {t('admin2.sm_monitoring_settings')}
        </h3>
        
        <div className="admin-grid-auto-300-24">
          <div>
            <h4 className="admin-settings-h4">
              {t('admin2.sm_thresholds')}
            </h4>
            <div className="flex flex-col gap-3">
              <div>
                <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2 mb-1">
                  CPU (%)
                </label>
                <Input
                type="number"
                value={thresholds.cpu_usage || 80}
                onChange={(e) => setThresholds((prev) => ({ ...prev, cpu_usage: parseInt(e.target.value) }))}
                min="0"
                max="100"
                className="w-full" />

              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2 mb-1">
                  {t('admin2.sm_memory_percent')}
                </label>
                <Input
                type="number"
                value={thresholds.memory_usage || 85}
                onChange={(e) => setThresholds((prev) => ({ ...prev, memory_usage: parseInt(e.target.value) }))}
                min="0"
                max="100"
                className="w-full" />

              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2 mb-1">
                  {t('admin2.sm_disk_percent')}
                </label>
                <Input
                type="number"
                value={thresholds.disk_usage || 90}
                onChange={(e) => setThresholds((prev) => ({ ...prev, disk_usage: parseInt(e.target.value) }))}
                min="0"
                max="100"
                className="w-full" />

              </div>
            </div>
          </div>
          
          <div>
            <h4 className="admin-settings-h4">
              {t('admin2.sm_automation')}
            </h4>
            <div className="flex flex-col gap-3">
              <div className="admin-automation-row">
                <div>
                  <div className="admin-text-med-primary-block">
                    {t('admin2.sm_auto_backups')}
                  </div>
                  <div className="admin-text-sm-secondary">
                    {t('admin2.sm_daily_at_2')}
                  </div>
                </div>
                <Button size="small" variant="outline">
                  {t('admin2.sm_configure')}
                </Button>
              </div>
              
              <div className="admin-automation-row">
                <div>
                  <div className="admin-text-med-primary-block">
                    {t('admin2.sm_notifications')}
                  </div>
                  <div className="admin-text-sm-secondary">
                    {t('admin2.sm_email_critical_alerts')}
                  </div>
                </div>
                <Button size="small" variant="outline">
                  {t('admin2.sm_configure')}
                </Button>
              </div>
            </div>
          </div>
        </div>
        
        <div className="mt-6">
          <Button>
            {t('admin2.sm_save_settings')}
          </Button>
        </div>
      </MacOSCard>
    </div>;


  return (
    <div className="admin-p-0-max-1400">
      <div className="flex items-center justify-between mb-6">
        <div className="admin-flex-center-16">
          <Server className="admin-icon-32-accent" />
          <div>
            <h1 className="admin-text-2xl admin-text-semi text-[var(--mac-text-primary)] admin-m-0">
              {t('admin2.sm_title')}
            </h1>
            <p className="admin-page-subtitle">
              {t('admin2.sm_subtitle')}
            </p>
          </div>
        </div>
        <div className="flex items-center justify-center gap-2">
          {systemHealth &&
          <Badge variant={systemHealth.overall_status === 'healthy' ? 'success' : 'error'}>
              {systemHealth.overall_status}
            </Badge>
          }
        </div>
      </div>

      {/* Табы */}
      {/* UX Audit Admin #3.7: hand-rolled tabs — DEPRECATED.
          Future: migrate to <SegmentedControl> for consistency
          with ClinicManagement. Different API prevents immediate migration. */}
      <div className="admin-tab-bar-simple">
          {[
        { id: 'monitoring', label: t('admin2.sm_tab_monitoring'), icon: Activity },
        // UX Audit Admin #3.2: backups-tab удалён — дублирует BackupManagement
        // компонент в ClinicManagement. SystemManagement фокусируется на мониторинге.
        ].map((tab) => {
          const IconComponent = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="admin-tab-btn"
              data-active={isActive}>

              <IconComponent className="w-4 h-4 admin-icon-16-color" style={{ '--admin-icon-color': isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)' } as CSSProperties} />
                {tab.label}
              {isActive &&
              <div className="admin-tab-active-underline" />
              }
              </button>);

        })}
      </div>

      {/* Разделительная линия */}
      <div className="admin-tab-divider" />

      {/* Контент табов */}
      {activeTab === 'monitoring' && renderMonitoringTab()}
      {/* UX Audit Admin #3.2: backups-tab удалён — дублирует ClinicManagement. */}
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog as unknown as React.ReactNode}
    </div>);

};

export default SystemManagement;
