import React, { useState, useEffect } from 'react';
import { 
  Building2, 
  Wrench, 
  Key, 
  HardDrive, 
  Settings, 
  BarChart3,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Activity,
  Shield,
  Database,
  Save
} from 'lucide-react';
import { Card, Button, Badge } from '../../design-system/components';
import BranchManagement from './BranchManagement';
import EquipmentManagement from './EquipmentManagement';
import LicenseManagement from './LicenseManagement';
import BackupManagement from './BackupManagement';

const ClinicManagement = () => {
  const [activeTab, setActiveTab] = useState('overview');
  const [systemHealth, setSystemHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState({ type: '', text: '' });

  const tabs = [
    { id: 'overview', label: 'Обзор', icon: BarChart3 },
    { id: 'branches', label: 'Филиалы', icon: Building2 },
    { id: 'equipment', label: 'Оборудование', icon: Wrench },
    { id: 'licenses', label: 'Лицензии', icon: Key },
    { id: 'backups', label: 'Резервные копии', icon: HardDrive },
    { id: 'settings', label: 'Настройки', icon: Settings }
  ];

  useEffect(() => {
    loadSystemData();
  }, []);

  const loadSystemData = async () => {
    try {
      setLoading(true);
      
      // Загружаем статистику и состояние системы параллельно
      const [statsResponse, healthResponse] = await Promise.all([
        fetch('/api/v1/clinic/stats', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }),
        fetch('/api/v1/clinic/health', {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        })
      ]);

      if (statsResponse.ok) {
        const statsData = await statsResponse.json();
        setStats(statsData);
      }

      if (healthResponse.ok) {
        const healthData = await healthResponse.json();
        setSystemHealth(healthData);
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Ошибка загрузки данных системы' });
    } finally {
      setLoading(false);
    }
  };

  const getHealthColor = (status) => {
    switch (status) {
      case 'healthy': return 'green';
      case 'warning': return 'yellow';
      case 'critical': return 'red';
      default: return 'gray';
    }
  };

  const getHealthLabel = (status) => {
    switch (status) {
      case 'healthy': return 'Здорово';
      case 'warning': return 'Предупреждение';
      case 'critical': return 'Критично';
      default: return 'Неизвестно';
    }
  };

  const renderOverview = () => (
    <div className="space-y-6">
      {/* Состояние системы */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Состояние системы</h3>
          <Button
            variant="outline"
            size="sm"
            onClick={loadSystemData}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
        </div>
        
        {systemHealth ? (
          <div className="space-y-4">
            <div className="flex items-center space-x-3">
              <Badge color={getHealthColor(systemHealth.status)}>
                {getHealthLabel(systemHealth.status)}
              </Badge>
              <span className="text-sm text-gray-600">
                Последняя проверка: {new Date().toLocaleString()}
              </span>
            </div>
            
            {systemHealth.warnings && systemHealth.warnings.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-gray-700">Предупреждения:</h4>
                {systemHealth.warnings.map((warning, index) => (
                  <div key={index} className="flex items-center space-x-2 text-sm text-yellow-600">
                    <AlertTriangle className="w-4 h-4" />
                    <span>{warning}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-8">
            <Activity className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">Загрузка состояния системы...</p>
          </div>
        )}
      </Card>

      {/* Статистика */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Филиалы</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_branches}</p>
                <p className="text-xs text-green-600">{stats.active_branches} активных</p>
              </div>
              <Building2 className="w-8 h-8 text-blue-500" />
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Оборудование</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_equipment}</p>
                <p className="text-xs text-green-600">{stats.active_equipment} активного</p>
              </div>
              <Wrench className="w-8 h-8 text-green-500" />
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Лицензии</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_licenses}</p>
                <p className="text-xs text-green-600">{stats.active_licenses} активных</p>
              </div>
              <Key className="w-8 h-8 text-purple-500" />
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">Резервные копии</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_backups}</p>
                <p className="text-xs text-blue-600">{stats.recent_backups} за неделю</p>
              </div>
              <HardDrive className="w-8 h-8 text-orange-500" />
            </div>
          </Card>
        </div>
      )}

      {/* Быстрые действия */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Быстрые действия</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Button
            onClick={() => setActiveTab('branches')}
            className="flex items-center space-x-2 h-16"
          >
            <Building2 className="w-5 h-5" />
            <span>Управление филиалами</span>
          </Button>
          
          <Button
            onClick={() => setActiveTab('equipment')}
            variant="outline"
            className="flex items-center space-x-2 h-16"
          >
            <Wrench className="w-5 h-5" />
            <span>Управление оборудованием</span>
          </Button>
          
          <Button
            onClick={() => setActiveTab('licenses')}
            variant="outline"
            className="flex items-center space-x-2 h-16"
          >
            <Key className="w-5 h-5" />
            <span>Управление лицензиями</span>
          </Button>
          
          <Button
            onClick={() => setActiveTab('backups')}
            variant="outline"
            className="flex items-center space-x-2 h-16"
          >
            <HardDrive className="w-5 h-5" />
            <span>Резервное копирование</span>
          </Button>
        </div>
      </Card>

      {/* Системная информация */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Системная информация</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Версия системы:</span>
              <span className="text-sm font-medium">1.0.0</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">База данных:</span>
              <span className="text-sm font-medium">SQLite</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Статус БД:</span>
              <Badge color="green">Подключена</Badge>
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Последнее обновление:</span>
              <span className="text-sm font-medium">{new Date().toLocaleDateString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Время работы:</span>
              <span className="text-sm font-medium">24/7</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Безопасность:</span>
              <Badge color="green">Активна</Badge>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );

  const renderSettings = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Настройки системы</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Автоматическое резервное копирование
            </label>
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                defaultChecked
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-600">Включить ежедневное резервное копирование</span>
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Уведомления о состоянии системы
            </label>
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                defaultChecked
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-600">Получать уведомления о проблемах</span>
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Мониторинг оборудования
            </label>
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                defaultChecked
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-600">Отслеживать сроки обслуживания</span>
            </div>
          </div>
        </div>
        
        <div className="mt-6 flex justify-end">
          <Button>
            <Save className="w-4 h-4 mr-2" />
            Сохранить настройки
          </Button>
        </div>
      </Card>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Управление клиникой</h1>
          <p className="text-gray-600">Централизованное управление всеми аспектами клиники</p>
        </div>
        <div className="flex items-center space-x-2">
          <Badge color={systemHealth ? getHealthColor(systemHealth.status) : 'gray'}>
            {systemHealth ? getHealthLabel(systemHealth.status) : 'Загрузка...'}
          </Badge>
        </div>
      </div>

      {/* Сообщения */}
      {message.text && (
        <div className={`p-4 rounded-lg flex items-center space-x-2 ${
          message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
        }`}>
          {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
          <span>{message.text}</span>
        </div>
      )}

      {/* Навигация по вкладкам */}
      <Card className="p-1">
        <div className="flex space-x-1">
          {tabs.map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Содержимое вкладок */}
      {activeTab === 'overview' && renderOverview()}
      {activeTab === 'branches' && <BranchManagement />}
      {activeTab === 'equipment' && <EquipmentManagement />}
      {activeTab === 'licenses' && <LicenseManagement />}
      {activeTab === 'backups' && <BackupManagement />}
      {activeTab === 'settings' && renderSettings()}
    </div>
  );
};

export default ClinicManagement;
