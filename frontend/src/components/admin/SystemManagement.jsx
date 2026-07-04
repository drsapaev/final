import { useState, useEffect } from 'react';
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
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirm, confirmDialog] = useConfirm();
  const [activeTab, setActiveTab] = useState('monitoring');
  const [loading, setLoading] = useState(false);

  // Состояние мониторинга
  const [systemHealth, setSystemHealth] = useState(null);
  const [systemMetrics, setSystemMetrics] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [thresholds, setThresholds] = useState({});

  // Состояние бэкапов
  const [backups, setBackups] = useState([]);
  const [backupForm, setBackupForm] = useState({
    backup_type: 'database',
    include_files: true,
    description: ''
  });

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
        toast.success('Метрики собраны');
        loadSystemMetrics();
        loadSystemHealth();
      } else {
        toast.error('Ошибка сбора метрик');
      }
    } catch (error) {
      logger.error('Ошибка сбора метрик:', error);
      toast.error('Ошибка сбора метрик');
    }
  };

  // ===================== БЭКАПЫ =====================

  const loadBackups = async () => {
    try {
      const response = await api.get('/system/backup/list');
      setBackups(response.data?.backups || []);
    } catch (error) {
      logger.error('Ошибка загрузки бэкапов:', error);
    }
  };

  const createBackup = async () => {
    setLoading(true);
    try {
      const response = await api.post('/system/backup/create', backupForm);
      if (response.data?.success) {
        toast.success('Бэкап создается...');
        setTimeout(() => loadBackups(), 2000); // Обновляем список через 2 секунды
      } else {
        toast.error(response.data?.error || 'Ошибка создания бэкапа');
      }
    } catch (error) {
      logger.error('Ошибка создания бэкапа:', error);
      toast.error(error.response?.data?.detail || 'Ошибка создания бэкапа');
    } finally {
      setLoading(false);
    }
  };

  const deleteBackup = async (backupName) => {
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: 'Удаление бэкапа',
      message: `Удалить бэкап ${backupName}?`,
      description: 'Это действие необратимо.',
      confirmLabel: 'Удалить',
      cancelLabel: 'Отмена',
      intent: 'danger',
    });
    if (!ok) {
      return;
    }

    try {
      const response = await api.delete(`/system/backup/${backupName}`);
      if (response.data?.success) {
        toast.success('Бэкап удален');
        loadBackups();
      } else {
        toast.error(response.data?.error || 'Ошибка удаления бэкапа');
      }
    } catch (error) {
      logger.error('Ошибка удаления бэкапа:', error);
      toast.error('Ошибка удаления бэкапа');
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

  // ===================== РЕНДЕРИНГ =====================

  const renderMonitoringTab = () =>
  <div className="admin-flex-col-24">
      {/* Общее состояние системы */}
      <MacOSCard className="admin-p-24">
        <div className="admin-flex-between-mb-16">
          <h3 className="admin-h3-icon-m0">
            <Activity className="admin-icon-20" />
            Состояние системы
          </h3>
          <Button
          onClick={collectMetricsNow}
          variant="outline"
          size="sm">

            <RefreshCw className="admin-icon-16-mr-8" />
            Обновить
          </Button>
        </div>

        {systemHealth &&
      <div className="admin-grid-auto-200">
            <div className="admin-text-center">
              <div className="admin-stat-value-dynamic" style={{ '--admin-stat-color': getStatusColor(systemHealth.overall_status) }}>
                {systemHealth.overall_status?.toUpperCase()}
              </div>
              <div className="admin-text-sm-secondary">
                Общий статус
              </div>
            </div>
            
            {systemHealth.components && Object.entries(systemHealth.components).map(([component, status]) => {
          const StatusIcon = getStatusIcon(status);
          return (
            <div key={component} className="admin-text-center">
                  <StatusIcon className="admin-status-icon-32" style={{ '--admin-icon-color': getStatusColor(status) }} />
                  <div className="admin-text-med-primary-block">
                    {component}
                  </div>
                  <div className="admin-stat-value-sm-dynamic" style={{ '--admin-stat-color': getStatusColor(status) }}>
                    {status}
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
          <MacOSCard className="admin-p-24">
            <div className="admin-flex-between-mb-16">
              <h4 className="admin-metric-h4">
                <Cpu className="admin-icon-16" />
                CPU
              </h4>
              <Badge variant={systemMetrics.cpu?.usage_percent > 80 ? 'error' : 'success'}>
                {systemMetrics.cpu?.usage_percent?.toFixed(1)}%
              </Badge>
            </div>
            <div className="admin-flex-col-8">
              <div className="admin-text-sm-primary">
                Ядер: {systemMetrics.cpu?.count}
            </div>
              {systemMetrics.cpu?.frequency &&
          <div className="admin-text-sm-primary">
                  Частота: {systemMetrics.cpu.frequency.toFixed(0)} MHz
                </div>
          }
            </div>
          </MacOSCard>

          {/* Память */}
          <MacOSCard className="admin-p-24">
            <div className="admin-flex-between-mb-16">
              <h4 className="admin-metric-h4">
                <MemoryStick className="admin-icon-16" />
                Память
              </h4>
              <Badge variant={systemMetrics.memory?.usage_percent > 85 ? 'error' : 'success'}>
                {systemMetrics.memory?.usage_percent?.toFixed(1)}%
              </Badge>
            </div>
            <div className="admin-flex-col-8">
              <div className="admin-text-sm-primary">
                Всего: {formatBytes(systemMetrics.memory?.total)}
              </div>
              <div className="admin-text-sm-primary">
                Используется: {formatBytes(systemMetrics.memory?.used)}
              </div>
              <div className="admin-text-sm-primary">
                Доступно: {formatBytes(systemMetrics.memory?.available)}
            </div>
            </div>
          </MacOSCard>

          {/* Диск */}
          <MacOSCard className="admin-p-24">
            <div className="admin-flex-between-mb-16">
              <h4 className="admin-metric-h4">
                <HardDrive className="admin-icon-16" />
                Диск
              </h4>
              <Badge variant={systemMetrics.disk?.usage_percent > 90 ? 'error' : 'success'}>
                {systemMetrics.disk?.usage_percent?.toFixed(1)}%
              </Badge>
            </div>
            <div className="admin-flex-col-8">
              <div className="admin-text-sm-primary">
                Всего: {formatBytes(systemMetrics.disk?.total)}
              </div>
              <div className="admin-text-sm-primary">
                Используется: {formatBytes(systemMetrics.disk?.used)}
              </div>
              <div className="admin-text-sm-primary">
                Свободно: {formatBytes(systemMetrics.disk?.free)}
            </div>
            </div>
          </MacOSCard>
        </div>
    }

      {/* Алерты */}
      <MacOSCard className="admin-p-24">
        <h3 className="admin-h3-icon-mb-16">
          <AlertTriangle className="admin-icon-20" />
          Последние алерты
        </h3>
        
        {alerts.length === 0 ?
      <MacOSEmptyState
        icon={CheckCircle}
        title="Нет активных алертов"
        description="Система работает стабильно"
        iconStyle={{ width: '48px', height: '48px', color: 'var(--mac-success)' }} /> :


      <div className="admin-flex-col-12">
            {alerts.slice(0, 10).map((alert, index) =>
        <div key={index} className="admin-alert-row">
                <div className="admin-flex-center-12">
                  <Badge variant={getSeverityColor(alert.severity)}>
                    {alert.severity}
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
      }
      </MacOSCard>
    </div>;


  const renderBackupsTab = () =>
  <div className="admin-flex-col-24">
      {/* Создание бэкапа */}
      <MacOSCard className="admin-p-24">
        <h3 className="admin-h3-icon-mb-16">
          <Database className="admin-icon-20" />
          Создание бэкапа
        </h3>
        
        <div className="admin-grid-auto-200-mb-16">
          <div>
            <label className="admin-form-label">
              Тип бэкапа
            </label>
            <Select
            value={backupForm.backup_type}
            onChange={(value) => setBackupForm((prev) => ({ ...prev, backup_type: value }))}
            options={[
            { value: 'database', label: 'База данных' },
            { value: 'full', label: 'Полный бэкап' },
            { value: 'configuration', label: 'Конфигурация' }]
            }
            size="large"
            className="admin-w-full" />

          </div>

          <div className="admin-flex-center">
            <label className="admin-label-flex-pointer">
              <Checkbox
              checked={backupForm.include_files}
              onChange={(checked) => setBackupForm((prev) => ({ ...prev, include_files: checked }))}
              className="admin-mr-8" />

              Включить файлы
            </label>
          </div>

          <div>
            <Button
            onClick={createBackup}
            disabled={loading}
            className="admin-w-full">

              {loading ?
            <RefreshCw className="admin-icon-16-spin-mr-8" /> :

            <Download className="admin-icon-16-mr-8" />
            }
              Создать бэкап
            </Button>
          </div>
        </div>
      </MacOSCard>

      {/* Список бэкапов */}
      <MacOSCard className="admin-p-24">
        <div className="admin-flex-between-mb-16">
          <h3 className="admin-h3-icon-m0">
            <Shield className="admin-icon-20" />
            Список бэкапов
          </h3>
          <Button
          onClick={loadBackups}
          variant="outline"
          size="sm">

            <RefreshCw className="admin-icon-16-mr-8" />
            Обновить
          </Button>
        </div>

        {backups.length === 0 ?
      <MacOSEmptyState
        icon={Database}
        title="Бэкапы не найдены"
        description="Создайте первый бэкап системы"
        iconStyle={{ width: '48px', height: '48px', color: 'var(--mac-text-tertiary)' }} /> :


      <Table
        columns={[
        { key: 'name', label: 'Название' },
        { key: 'type', label: 'Тип' },
        { key: 'size', label: 'Размер' },
        { key: 'created_at', label: 'Создан' },
        { key: 'actions', label: 'Действия' }]
        }
        data={backups.map((backup) => ({
          ...backup,
          name:
          <div className="admin-flex-center-8">
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
                    size="sm"
                    variant="outline"
                    title={`View backup ${backup.name}`}
                    aria-label={`View backup ${backup.name}`}>
                    <Eye aria-hidden="true" className="admin-icon-14" />
                  </Button>
                  <Button
              type="button"
              onClick={() => deleteBackup(backup.name)}
              size="sm"
              variant="outline"
              title={`Delete backup ${backup.name}`}
              aria-label={`Delete backup ${backup.name}`}
              className="admin-text-error">

                    <Trash2 aria-hidden="true" className="admin-icon-14" />
                  </Button>
                      </div>

        }))}
        emptyState={
        <MacOSEmptyState
          icon={Database}
          title="Бэкапы не найдены"
          description="Создайте первый бэкап системы" />

        } />

      }
      </MacOSCard>
    </div>;


  const renderSettingsTab = () =>
  <div className="admin-flex-col-24">
      <MacOSCard className="admin-p-24">
        <h3 className="admin-h3-icon-mb-16">
          <Settings className="admin-icon-20" />
          Настройки мониторинга
        </h3>
        
        <div className="admin-grid-auto-300-24">
          <div>
            <h4 className="admin-settings-h4">
              Пороговые значения
            </h4>
            <div className="admin-flex-col-12">
              <div>
                <label className="admin-form-label admin-mb-4">
                  CPU (%)
                </label>
                <Input
                type="number"
                value={thresholds.cpu_usage || 80}
                onChange={(e) => setThresholds((prev) => ({ ...prev, cpu_usage: parseInt(e.target.value) }))}
                min="0"
                max="100"
                className="admin-w-full" />

              </div>
              <div>
                <label className="admin-form-label admin-mb-4">
                  Память (%)
                </label>
                <Input
                type="number"
                value={thresholds.memory_usage || 85}
                onChange={(e) => setThresholds((prev) => ({ ...prev, memory_usage: parseInt(e.target.value) }))}
                min="0"
                max="100"
                className="admin-w-full" />

              </div>
              <div>
                <label className="admin-form-label admin-mb-4">
                  Диск (%)
                </label>
                <Input
                type="number"
                value={thresholds.disk_usage || 90}
                onChange={(e) => setThresholds((prev) => ({ ...prev, disk_usage: parseInt(e.target.value) }))}
                min="0"
                max="100"
                className="admin-w-full" />

              </div>
            </div>
          </div>
          
          <div>
            <h4 className="admin-settings-h4">
              Автоматизация
            </h4>
            <div className="admin-flex-col-12">
              <div className="admin-automation-row">
                <div>
                  <div className="admin-text-med-primary-block">
                    Автоматические бэкапы
                  </div>
                  <div className="admin-text-sm-secondary">
                    Ежедневно в 02:00
                  </div>
                </div>
                <Button size="sm" variant="outline">
                  Настроить
                </Button>
              </div>
              
              <div className="admin-automation-row">
                <div>
                  <div className="admin-text-med-primary-block">
                    Уведомления
                  </div>
                  <div className="admin-text-sm-secondary">
                    Email при критических алертах
                  </div>
                </div>
                <Button size="sm" variant="outline">
                  Настроить
                </Button>
              </div>
            </div>
          </div>
        </div>
        
        <div className="admin-mt-24">
          <Button>
            Сохранить настройки
          </Button>
        </div>
      </MacOSCard>
    </div>;


  return (
    <div className="admin-p-0-max-1400">
      <div className="admin-flex-between admin-mb-24">
        <div className="admin-flex-center-16">
          <Server className="admin-icon-32-accent" />
          <div>
            <h1 className="admin-text-2xl admin-text-semi admin-text-primary admin-m-0">
              Управление системой
            </h1>
            <p className="admin-page-subtitle">
              Мониторинг, бэкапы и системные настройки
            </p>
          </div>
        </div>
        <div className="admin-flex-center-8">
          {systemHealth &&
          <Badge variant={systemHealth.overall_status === 'healthy' ? 'success' : 'error'}>
              {systemHealth.overall_status}
            </Badge>
          }
        </div>
      </div>

      {/* Табы */}
      <div className="admin-tab-bar-simple">
          {[
        { id: 'monitoring', label: 'Мониторинг', icon: Activity },
        { id: 'backups', label: 'Бэкапы', icon: Database },
        { id: 'settings', label: 'Настройки', icon: Settings }].
        map((tab) => {
          const IconComponent = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="admin-tab-btn"
              data-active={isActive}>

              <IconComponent className="admin-icon-16 admin-icon-16-color" style={{ '--admin-icon-color': isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)' }} />
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
      {activeTab === 'backups' && renderBackupsTab()}
      {activeTab === 'settings' && renderSettingsTab()}
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </div>);

};

export default SystemManagement;
