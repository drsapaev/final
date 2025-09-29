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
import { Card, Button, Badge } from '../ui/native';
import { toast } from 'react-toastify';

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
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/system/monitoring/health', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setSystemHealth(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки состояния системы:', error);
    }
  };

  const loadSystemMetrics = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/system/monitoring/metrics/system', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setSystemMetrics(data.metrics);
      }
    } catch (error) {
      console.error('Ошибка загрузки метрик системы:', error);
    }
  };

  const loadAlerts = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/system/monitoring/alerts?limit=50', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setAlerts(data.alerts || []);
      }
    } catch (error) {
      console.error('Ошибка загрузки алертов:', error);
    }
  };

  const loadThresholds = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/system/monitoring/thresholds', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setThresholds(data.thresholds || {});
      }
    } catch (error) {
      console.error('Ошибка загрузки порогов:', error);
    }
  };

  const collectMetricsNow = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/system/monitoring/collect', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
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
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/system/backup/list', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setBackups(data.backups || []);
      }
    } catch (error) {
      console.error('Ошибка загрузки бэкапов:', error);
    }
  };

  const createBackup = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/system/backup/create', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(backupForm)
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          toast.success('Бэкап создается...');
          setTimeout(() => loadBackups(), 2000); // Обновляем список через 2 секунды
        } else {
          toast.error(data.error || 'Ошибка создания бэкапа');
        }
      } else {
        toast.error('Ошибка создания бэкапа');
      }
    } catch (error) {
      console.error('Ошибка создания бэкапа:', error);
      toast.error('Ошибка создания бэкапа');
    } finally {
      setLoading(false);
    }
  };

  const deleteBackup = async (backupName) => {
    if (!window.confirm(`Удалить бэкап ${backupName}?`)) {
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/system/backup/${backupName}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          toast.success('Бэкап удален');
          loadBackups();
        } else {
          toast.error(data.error || 'Ошибка удаления бэкапа');
        }
      } else {
        toast.error('Ошибка удаления бэкапа');
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
      case 'healthy': return 'text-green-600';
      case 'warning': return 'text-yellow-600';
      case 'critical': return 'text-red-600';
      default: return 'text-gray-600';
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
      case 'critical': return 'bg-red-100 text-red-800';
      case 'warning': return 'bg-yellow-100 text-yellow-800';
      case 'info': return 'bg-blue-100 text-blue-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  // ===================== РЕНДЕРИНГ =====================

  const renderMonitoringTab = () => (
    <div className="space-y-6">
      {/* Общее состояние системы */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center">
            <Activity className="w-5 h-5 mr-2" />
            Состояние системы
          </h3>
          <Button
            onClick={collectMetricsNow}
            variant="outline"
            size="sm"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Обновить
          </Button>
        </div>

        {systemHealth && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="text-center">
              <div className={`text-2xl font-bold ${getStatusColor(systemHealth.overall_status)}`}>
                {systemHealth.overall_status?.toUpperCase()}
              </div>
              <div className="text-sm text-gray-500">Общий статус</div>
            </div>
            
            {systemHealth.components && Object.entries(systemHealth.components).map(([component, status]) => {
              const StatusIcon = getStatusIcon(status);
              return (
                <div key={component} className="text-center">
                  <StatusIcon className={`w-8 h-8 mx-auto mb-2 ${getStatusColor(status)}`} />
                  <div className="font-medium">{component}</div>
                  <div className={`text-sm ${getStatusColor(status)}`}>{status}</div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Системные метрики */}
      {systemMetrics && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* CPU */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h4 className="font-semibold flex items-center">
                <Cpu className="w-4 h-4 mr-2" />
                CPU
              </h4>
              <Badge variant={systemMetrics.cpu?.usage_percent > 80 ? 'error' : 'success'}>
                {systemMetrics.cpu?.usage_percent?.toFixed(1)}%
              </Badge>
            </div>
            <div className="space-y-2 text-sm">
              <div>Ядер: {systemMetrics.cpu?.count}</div>
              {systemMetrics.cpu?.frequency && (
                <div>Частота: {systemMetrics.cpu.frequency.toFixed(0)} MHz</div>
              )}
            </div>
          </Card>

          {/* Память */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h4 className="font-semibold flex items-center">
                <MemoryStick className="w-4 h-4 mr-2" />
                Память
              </h4>
              <Badge variant={systemMetrics.memory?.usage_percent > 85 ? 'error' : 'success'}>
                {systemMetrics.memory?.usage_percent?.toFixed(1)}%
              </Badge>
            </div>
            <div className="space-y-2 text-sm">
              <div>Всего: {formatBytes(systemMetrics.memory?.total)}</div>
              <div>Используется: {formatBytes(systemMetrics.memory?.used)}</div>
              <div>Доступно: {formatBytes(systemMetrics.memory?.available)}</div>
            </div>
          </Card>

          {/* Диск */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h4 className="font-semibold flex items-center">
                <HardDrive className="w-4 h-4 mr-2" />
                Диск
              </h4>
              <Badge variant={systemMetrics.disk?.usage_percent > 90 ? 'error' : 'success'}>
                {systemMetrics.disk?.usage_percent?.toFixed(1)}%
              </Badge>
            </div>
            <div className="space-y-2 text-sm">
              <div>Всего: {formatBytes(systemMetrics.disk?.total)}</div>
              <div>Используется: {formatBytes(systemMetrics.disk?.used)}</div>
              <div>Свободно: {formatBytes(systemMetrics.disk?.free)}</div>
            </div>
          </Card>
        </div>
      )}

      {/* Алерты */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center">
          <AlertTriangle className="w-5 h-5 mr-2" />
          Последние алерты
        </h3>
        
        {alerts.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <CheckCircle className="w-12 h-12 mx-auto mb-4 text-green-500" />
            <p>Нет активных алертов</p>
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.slice(0, 10).map((alert, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div className="flex items-center">
                  <Badge className={getSeverityColor(alert.severity)}>
                    {alert.severity}
                  </Badge>
                  <span className="ml-3">{alert.message}</span>
                </div>
                <div className="text-sm text-gray-500">
                  {new Date(alert.timestamp).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );

  const renderBackupsTab = () => (
    <div className="space-y-6">
      {/* Создание бэкапа */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center">
          <Database className="w-5 h-5 mr-2" />
          Создание бэкапа
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium mb-2">Тип бэкапа</label>
            <select
              value={backupForm.backup_type}
              onChange={(e) => setBackupForm(prev => ({ ...prev, backup_type: e.target.value }))}
              className="w-full p-2 border border-gray-300 rounded-md"
            >
              <option value="database">База данных</option>
              <option value="full">Полный бэкап</option>
              <option value="configuration">Конфигурация</option>
            </select>
          </div>

          <div className="flex items-center">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={backupForm.include_files}
                onChange={(e) => setBackupForm(prev => ({ ...prev, include_files: e.target.checked }))}
                className="mr-2"
              />
              Включить файлы
            </label>
          </div>

          <div>
            <Button
              onClick={createBackup}
              disabled={loading}
              className="w-full"
            >
              {loading ? (
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Download className="w-4 h-4 mr-2" />
              )}
              Создать бэкап
            </Button>
          </div>
        </div>
      </Card>

      {/* Список бэкапов */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center">
            <Shield className="w-5 h-5 mr-2" />
            Список бэкапов
          </h3>
          <Button
            onClick={loadBackups}
            variant="outline"
            size="sm"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Обновить
          </Button>
        </div>

        {backups.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Database className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>Бэкапы не найдены</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2">Название</th>
                  <th className="text-left py-2">Тип</th>
                  <th className="text-left py-2">Размер</th>
                  <th className="text-left py-2">Создан</th>
                  <th className="text-right py-2">Действия</th>
                </tr>
              </thead>
              <tbody>
                {backups.map((backup, index) => (
                  <tr key={index} className="border-b hover:bg-gray-50">
                    <td className="py-3">
                      <div className="flex items-center">
                        <Database className="w-4 h-4 mr-2 text-gray-500" />
                        <span className="font-medium">{backup.name}</span>
                      </div>
                    </td>
                    <td className="py-3">
                      <Badge variant="outline">{backup.type}</Badge>
                    </td>
                    <td className="py-3 text-gray-600">
                      {formatBytes(backup.size)}
                    </td>
                    <td className="py-3 text-gray-600">
                      {new Date(backup.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 text-right">
                      <div className="flex justify-end space-x-2">
                        <Button
                          size="sm"
                          variant="outline"
                        >
                          <Eye className="w-4 h-4" />
                        </Button>
                        <Button
                          onClick={() => deleteBackup(backup.name)}
                          size="sm"
                          variant="outline"
                          className="text-red-600 hover:text-red-700"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );

  const renderSettingsTab = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center">
          <Settings className="w-5 h-5 mr-2" />
          Настройки мониторинга
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h4 className="font-medium mb-3">Пороговые значения</h4>
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium mb-1">CPU (%)</label>
                <input
                  type="number"
                  value={thresholds.cpu_usage || 80}
                  className="w-full p-2 border border-gray-300 rounded-md"
                  min="0"
                  max="100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Память (%)</label>
                <input
                  type="number"
                  value={thresholds.memory_usage || 85}
                  className="w-full p-2 border border-gray-300 rounded-md"
                  min="0"
                  max="100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Диск (%)</label>
                <input
                  type="number"
                  value={thresholds.disk_usage || 90}
                  className="w-full p-2 border border-gray-300 rounded-md"
                  min="0"
                  max="100"
                />
              </div>
            </div>
          </div>
          
          <div>
            <h4 className="font-medium mb-3">Автоматизация</h4>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <div className="font-medium">Автоматические бэкапы</div>
                  <div className="text-sm text-gray-600">Ежедневно в 02:00</div>
                </div>
                <Button size="sm" variant="outline">
                  Настроить
                </Button>
              </div>
              
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <div className="font-medium">Уведомления</div>
                  <div className="text-sm text-gray-600">Email при критических алертах</div>
                </div>
                <Button size="sm" variant="outline">
                  Настроить
                </Button>
              </div>
            </div>
          </div>
        </div>
        
        <div className="mt-6">
          <Button>
            Сохранить настройки
          </Button>
        </div>
      </Card>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Управление системой</h2>
        <div className="flex items-center space-x-2">
          {systemHealth && (
            <Badge variant={systemHealth.overall_status === 'healthy' ? 'success' : 'error'}>
              {systemHealth.overall_status}
            </Badge>
          )}
        </div>
      </div>

      {/* Табы */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {[
            { id: 'monitoring', label: 'Мониторинг', icon: Activity },
            { id: 'backups', label: 'Бэкапы', icon: Database },
            { id: 'settings', label: 'Настройки', icon: Settings }
          ].map(tab => {
            const IconComponent = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <IconComponent className="w-4 h-4 mr-2" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Контент табов */}
      {activeTab === 'monitoring' && renderMonitoringTab()}
      {activeTab === 'backups' && renderBackupsTab()}
      {activeTab === 'settings' && renderSettingsTab()}
    </div>
  );
};

export default SystemManagement;

