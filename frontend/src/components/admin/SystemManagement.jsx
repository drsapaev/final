import React, { useState, useEffect } from 'react';
import { 
  Server, 
  Database, 
  Shield, 
  Download, 
  Upload, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  HardDrive, 
  Cpu, 
  MemoryStick,
  Activity,
  Settings,
  Trash2,
  Eye,
  Play,
  Pause,
  BarChart3,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  Info
} from 'lucide-react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSBadge, 
  MacOSInput, 
  MacOSSelect, 
  MacOSCheckbox, 
  MacOSTable,
  MacOSEmptyState,
  MacOSLoadingSkeleton
} from '../ui/macos';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

const SystemManagement = () => {
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
      console.error('Ошибка загрузки состояния системы:', error);
    }
  };

  const loadSystemMetrics = async () => {
    try {
      const { data } = await api.get('/system/monitoring/metrics/system');
        setSystemMetrics(data.metrics);
    } catch (error) {
      console.error('Ошибка загрузки метрик системы:', error);
    }
  };

  const loadAlerts = async () => {
    try {
      const { data } = await api.get('/system/monitoring/alerts', { params: { limit: 50 } });
        setAlerts(data.alerts || []);
    } catch (error) {
      console.error('Ошибка загрузки алертов:', error);
    }
  };

  const loadThresholds = async () => {
    try {
      const { data } = await api.get('/system/monitoring/thresholds');
        setThresholds(data.thresholds || {});
    } catch (error) {
      console.error('Ошибка загрузки порогов:', error);
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
      console.error('Ошибка сбора метрик:', error);
      toast.error('Ошибка сбора метрик');
    }
  };

  // ===================== БЭКАПЫ =====================

  const loadBackups = async () => {
    try {
      const response = await api.get('/system/backup/list');
      setBackups(response.data?.backups || []);
    } catch (error) {
      console.error('Ошибка загрузки бэкапов:', error);
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
      console.error('Ошибка создания бэкапа:', error);
      toast.error(error.response?.data?.detail || 'Ошибка создания бэкапа');
    } finally {
      setLoading(false);
    }
  };

  const deleteBackup = async (backupName) => {
    if (!window.confirm(`Удалить бэкап ${backupName}?`)) {
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
      console.error('Ошибка удаления бэкапа:', error);
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
      case 'healthy': return 'var(--mac-success)';
      case 'warning': return 'var(--mac-warning)';
      case 'critical': return 'var(--mac-error)';
      default: return 'var(--mac-text-tertiary)';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy': return CheckCircle;
      case 'warning': return AlertTriangle;
      case 'critical': return AlertCircle;
      default: return Info;
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical': return 'error';
      case 'warning': return 'warning';
      case 'info': return 'info';
      default: return 'default';
    }
  };

  // ===================== РЕНДЕРИНГ =====================

  const renderMonitoringTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Общее состояние системы */}
      <MacOSCard style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Activity style={{ width: '20px', height: '20px' }} />
            Состояние системы
          </h3>
          <MacOSButton
            onClick={collectMetricsNow}
            variant="outline"
            size="sm"
          >
            <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Обновить
          </MacOSButton>
        </div>

        {systemHealth && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ 
                fontSize: 'var(--mac-font-size-xl)', 
                fontWeight: 'var(--mac-font-weight-bold)',
                color: getStatusColor(systemHealth.overall_status)
              }}>
                {systemHealth.overall_status?.toUpperCase()}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)' 
              }}>
                Общий статус
              </div>
            </div>
            
            {systemHealth.components && Object.entries(systemHealth.components).map(([component, status]) => {
              const StatusIcon = getStatusIcon(status);
              return (
                <div key={component} style={{ textAlign: 'center' }}>
                  <StatusIcon style={{ 
                    width: '32px', 
                    height: '32px', 
                    margin: '0 auto 8px auto',
                    color: getStatusColor(status)
                  }} />
                  <div style={{ 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)'
                  }}>
                    {component}
                  </div>
                  <div style={{ 
                    fontSize: 'var(--mac-font-size-sm)',
                    color: getStatusColor(status)
                  }}>
                    {status}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </MacOSCard>

      {/* Системные метрики */}
      {systemMetrics && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
          {/* CPU */}
          <MacOSCard style={{ padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h4 style={{ 
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                margin: 0
              }}>
                <Cpu style={{ width: '16px', height: '16px' }} />
                CPU
              </h4>
              <MacOSBadge variant={systemMetrics.cpu?.usage_percent > 80 ? 'error' : 'success'}>
                {systemMetrics.cpu?.usage_percent?.toFixed(1)}%
              </MacOSBadge>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-primary)'
              }}>
                Ядер: {systemMetrics.cpu?.count}
            </div>
              {systemMetrics.cpu?.frequency && (
                <div style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-primary)'
                }}>
                  Частота: {systemMetrics.cpu.frequency.toFixed(0)} MHz
                </div>
              )}
            </div>
          </MacOSCard>

          {/* Память */}
          <MacOSCard style={{ padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h4 style={{ 
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                margin: 0
              }}>
                <MemoryStick style={{ width: '16px', height: '16px' }} />
                Память
              </h4>
              <MacOSBadge variant={systemMetrics.memory?.usage_percent > 85 ? 'error' : 'success'}>
                {systemMetrics.memory?.usage_percent?.toFixed(1)}%
              </MacOSBadge>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-primary)'
              }}>
                Всего: {formatBytes(systemMetrics.memory?.total)}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-primary)'
              }}>
                Используется: {formatBytes(systemMetrics.memory?.used)}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-primary)'
              }}>
                Доступно: {formatBytes(systemMetrics.memory?.available)}
            </div>
            </div>
          </MacOSCard>

          {/* Диск */}
          <MacOSCard style={{ padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h4 style={{ 
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                margin: 0
              }}>
                <HardDrive style={{ width: '16px', height: '16px' }} />
                Диск
              </h4>
              <MacOSBadge variant={systemMetrics.disk?.usage_percent > 90 ? 'error' : 'success'}>
                {systemMetrics.disk?.usage_percent?.toFixed(1)}%
              </MacOSBadge>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-primary)'
              }}>
                Всего: {formatBytes(systemMetrics.disk?.total)}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-primary)'
              }}>
                Используется: {formatBytes(systemMetrics.disk?.used)}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-primary)'
              }}>
                Свободно: {formatBytes(systemMetrics.disk?.free)}
            </div>
            </div>
          </MacOSCard>
        </div>
      )}

      {/* Алерты */}
      <MacOSCard style={{ padding: '24px' }}>
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)', 
          fontWeight: 'var(--mac-font-weight-semibold)', 
          color: 'var(--mac-text-primary)',
          margin: '0 0 16px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <AlertTriangle style={{ width: '20px', height: '20px' }} />
          Последние алерты
        </h3>
        
        {alerts.length === 0 ? (
          <MacOSEmptyState
            icon={CheckCircle}
            title="Нет активных алертов"
            description="Система работает стабильно"
            iconStyle={{ width: '48px', height: '48px', color: 'var(--mac-success)' }}
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {alerts.slice(0, 10).map((alert, index) => (
              <div key={index} style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between', 
                padding: '12px', 
                backgroundColor: 'var(--mac-bg-secondary)', 
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <MacOSBadge variant={getSeverityColor(alert.severity)}>
                    {alert.severity}
                  </MacOSBadge>
                  <span style={{ 
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-primary)'
                  }}>
                    {alert.message}
                  </span>
                </div>
                <div style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-secondary)' 
                }}>
                  {new Date(alert.timestamp).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </MacOSCard>
    </div>
  );

  const renderBackupsTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Создание бэкапа */}
      <MacOSCard style={{ padding: '24px' }}>
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)', 
          fontWeight: 'var(--mac-font-weight-semibold)', 
          color: 'var(--mac-text-primary)',
          margin: '0 0 16px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Database style={{ width: '20px', height: '20px' }} />
          Создание бэкапа
        </h3>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '16px' }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Тип бэкапа
            </label>
            <MacOSSelect
              value={backupForm.backup_type}
              onChange={(e) => setBackupForm(prev => ({ ...prev, backup_type: e.target.value }))}
              options={[
                { value: 'database', label: 'База данных' },
                { value: 'full', label: 'Полный бэкап' },
                { value: 'configuration', label: 'Конфигурация' }
              ]}
              style={{ width: '100%' }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center' }}>
            <label style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              cursor: 'pointer',
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              <MacOSCheckbox
                checked={backupForm.include_files}
                onChange={(checked) => setBackupForm(prev => ({ ...prev, include_files: checked }))}
                style={{ marginRight: '8px' }}
              />
              Включить файлы
            </label>
          </div>

          <div>
            <MacOSButton
              onClick={createBackup}
              disabled={loading}
              style={{ width: '100%' }}
            >
              {loading ? (
                <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px', animation: 'spin 1s linear infinite' }} />
              ) : (
                <Download style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              )}
              Создать бэкап
            </MacOSButton>
          </div>
        </div>
      </MacOSCard>

      {/* Список бэкапов */}
      <MacOSCard style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Shield style={{ width: '20px', height: '20px' }} />
            Список бэкапов
          </h3>
          <MacOSButton
            onClick={loadBackups}
            variant="outline"
            size="sm"
          >
            <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Обновить
          </MacOSButton>
        </div>

        {backups.length === 0 ? (
          <MacOSEmptyState
            icon={Database}
            title="Бэкапы не найдены"
            description="Создайте первый бэкап системы"
            iconStyle={{ width: '48px', height: '48px', color: 'var(--mac-text-tertiary)' }}
          />
        ) : (
          <MacOSTable
            columns={[
              { key: 'name', label: 'Название' },
              { key: 'type', label: 'Тип' },
              { key: 'size', label: 'Размер' },
              { key: 'created_at', label: 'Создан' },
              { key: 'actions', label: 'Действия' }
            ]}
            data={backups.map(backup => ({
              ...backup,
              name: (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Database style={{ width: '16px', height: '16px', color: 'var(--mac-text-tertiary)' }} />
                  <span style={{ fontWeight: 'var(--mac-font-weight-medium)' }}>{backup.name}</span>
                      </div>
              ),
              type: <MacOSBadge variant="outline">{backup.type}</MacOSBadge>,
              size: formatBytes(backup.size),
              created_at: new Date(backup.created_at).toLocaleString(),
              actions: (
                <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                  <MacOSButton size="sm" variant="outline">
                    <Eye style={{ width: '14px', height: '14px' }} />
                  </MacOSButton>
                  <MacOSButton
                          onClick={() => deleteBackup(backup.name)}
                          size="sm"
                          variant="outline"
                    style={{ color: 'var(--mac-error)' }}
                        >
                    <Trash2 style={{ width: '14px', height: '14px' }} />
                  </MacOSButton>
                      </div>
              )
            }))}
            emptyState={
              <MacOSEmptyState
                icon={Database}
                title="Бэкапы не найдены"
                description="Создайте первый бэкап системы"
              />
            }
          />
        )}
      </MacOSCard>
    </div>
  );

  const renderSettingsTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{ padding: '24px' }}>
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)', 
          fontWeight: 'var(--mac-font-weight-semibold)', 
          color: 'var(--mac-text-primary)',
          margin: '0 0 16px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Settings style={{ width: '20px', height: '20px' }} />
          Настройки мониторинга
        </h3>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
          <div>
            <h4 style={{ 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)',
              marginBottom: '12px'
            }}>
              Пороговые значения
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  CPU (%)
                </label>
                <MacOSInput
                  type="number"
                  value={thresholds.cpu_usage || 80}
                  onChange={(e) => setThresholds(prev => ({ ...prev, cpu_usage: parseInt(e.target.value) }))}
                  min="0"
                  max="100"
                  style={{ width: '100%' }}
                />
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Память (%)
                </label>
                <MacOSInput
                  type="number"
                  value={thresholds.memory_usage || 85}
                  onChange={(e) => setThresholds(prev => ({ ...prev, memory_usage: parseInt(e.target.value) }))}
                  min="0"
                  max="100"
                  style={{ width: '100%' }}
                />
              </div>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '4px' 
                }}>
                  Диск (%)
                </label>
                <MacOSInput
                  type="number"
                  value={thresholds.disk_usage || 90}
                  onChange={(e) => setThresholds(prev => ({ ...prev, disk_usage: parseInt(e.target.value) }))}
                  min="0"
                  max="100"
                  style={{ width: '100%' }}
                />
              </div>
            </div>
          </div>
          
          <div>
            <h4 style={{ 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)',
              marginBottom: '12px'
            }}>
              Автоматизация
            </h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between', 
                padding: '12px', 
                backgroundColor: 'var(--mac-bg-secondary)', 
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)'
              }}>
                <div>
                  <div style={{ 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)'
                  }}>
                    Автоматические бэкапы
                  </div>
                  <div style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)' 
                  }}>
                    Ежедневно в 02:00
                  </div>
                </div>
                <MacOSButton size="sm" variant="outline">
                  Настроить
                </MacOSButton>
              </div>
              
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between', 
                padding: '12px', 
                backgroundColor: 'var(--mac-bg-secondary)', 
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)'
              }}>
                <div>
                  <div style={{ 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)'
                  }}>
                    Уведомления
                  </div>
                  <div style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)' 
                  }}>
                    Email при критических алертах
                  </div>
                </div>
                <MacOSButton size="sm" variant="outline">
                  Настроить
                </MacOSButton>
              </div>
            </div>
          </div>
        </div>
        
        <div style={{ marginTop: '24px' }}>
          <MacOSButton>
            Сохранить настройки
          </MacOSButton>
        </div>
      </MacOSCard>
    </div>
  );

  return (
    <div style={{ padding: 0, maxWidth: '1400px', margin: '0 auto' }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: 'space-between',
        marginBottom: '24px'
      }}>
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '16px'
        }}>
          <Server style={{ width: '32px', height: '32px', color: 'var(--mac-accent)' }} />
          <div>
            <h1 style={{ 
              margin: 0, 
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}>
              Управление системой
            </h1>
            <p style={{ 
              margin: '4px 0 0 0',
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-sm)'
            }}>
              Мониторинг, бэкапы и системные настройки
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {systemHealth && (
            <MacOSBadge variant={systemHealth.overall_status === 'healthy' ? 'success' : 'error'}>
              {systemHealth.overall_status}
            </MacOSBadge>
          )}
        </div>
      </div>

      {/* Табы */}
      <div style={{ 
        display: 'flex', 
        marginBottom: '24px'
      }}>
          {[
            { id: 'monitoring', label: 'Мониторинг', icon: Activity },
            { id: 'backups', label: 'Бэкапы', icon: Database },
            { id: 'settings', label: 'Настройки', icon: Settings }
          ].map(tab => {
            const IconComponent = tab.icon;
          const isActive = activeTab === tab.id;
          
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '12px 20px',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)',
                fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                fontSize: 'var(--mac-font-size-sm)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                position: 'relative',
                marginBottom: '-1px'
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.target.style.color = 'var(--mac-text-primary)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.target.style.color = 'var(--mac-text-secondary)';
                }
              }}
            >
              <IconComponent style={{ 
                width: '16px', 
                height: '16px',
                color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
              }} />
                {tab.label}
              {isActive && (
                <div style={{
                  position: 'absolute',
                  bottom: '0',
                  left: '0',
                  right: '0',
                  height: '3px',
                  backgroundColor: 'var(--mac-accent-blue)',
                  borderRadius: '2px 2px 0 0'
                }} />
              )}
              </button>
            );
          })}
      </div>
      
      {/* Разделительная линия */}
      <div style={{ 
        borderBottom: '1px solid var(--mac-border)',
        marginBottom: '24px'
      }} />

      {/* Контент табов */}
      {activeTab === 'monitoring' && renderMonitoringTab()}
      {activeTab === 'backups' && renderBackupsTab()}
      {activeTab === 'settings' && renderSettingsTab()}
    </div>
  );
};

export default SystemManagement;

