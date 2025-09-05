import React, { useState, useEffect } from 'react';
import { 
  Key, 
  Smartphone, 
  Calendar, 
  Shield, 
  Plus,
  Edit,
  Trash2,
  Save, 
  RefreshCw, 
  AlertCircle, 
  CheckCircle,
  Copy,
  Download,
  Search,
  Filter,
  Clock,
  MapPin,
  User,
  Activity
} from 'lucide-react';
import { Card, Button, Badge } from '../../design-system/components';

const ActivationSystem = () => {
  const [loading, setLoading] = useState(true);
  const [activations, setActivations] = useState([]);
  const [devices, setDevices] = useState([]);
  const [stats, setStats] = useState({});
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  // Статусы активации
  const statusLabels = {
    active: { label: 'Активна', color: 'success' },
    expired: { label: 'Истекла', color: 'warning' },
    revoked: { label: 'Отозвана', color: 'error' },
    trial: { label: 'Пробная', color: 'info' }
  };

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      
      // Загружаем активации, устройства и статистику
      const [activationsRes, devicesRes, statsRes] = await Promise.all([
        fetch('/api/v1/admin/activation/keys', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        }),
        fetch('/api/v1/admin/activation/devices', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        }),
        fetch('/api/v1/admin/activation/stats', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        })
      ]);

      if (activationsRes.ok) {
        const activationsData = await activationsRes.json();
        setActivations(activationsData);
      }

      if (devicesRes.ok) {
        const devicesData = await devicesRes.json();
        setDevices(devicesData);
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

    } catch (error) {
      console.error('Ошибка загрузки данных активации:', error);
      setMessage({ type: 'error', text: 'Ошибка загрузки данных активации' });
    } finally {
      setLoading(false);
    }
  };

  const generateActivationKey = async (keyData) => {
    try {
      const response = await fetch('/api/v1/admin/activation/keys', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(keyData)
      });

      if (response.ok) {
        const result = await response.json();
        setMessage({ type: 'success', text: 'Ключ активации создан' });
        setShowCreateForm(false);
        await loadData();
        return result;
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }
    } catch (error) {
      console.error('Ошибка создания ключа:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  const revokeActivation = async (activationId) => {
    if (!confirm('Отозвать активацию? Устройство будет заблокировано.')) return;

    try {
      const response = await fetch(`/api/v1/admin/activation/keys/${activationId}/revoke`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Активация отозвана' });
        await loadData();
      } else {
        throw new Error('Ошибка отзыва активации');
      }
    } catch (error) {
      console.error('Ошибка отзыва:', error);
      setMessage({ type: 'error', text: 'Ошибка отзыва активации' });
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setMessage({ type: 'success', text: 'Скопировано в буфер обмена' });
  };

  const filteredActivations = activations.filter(activation => {
    const matchesSearch = activation.key?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         activation.machine_hash?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || activation.status === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

  if (loading) {
    return (
      <Card className="p-8">
        <div className="flex items-center justify-center">
          <RefreshCw className="animate-spin mr-2" size={20} />
          <span>Загрузка системы активации...</span>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Система активации
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Управление лицензиями и активированными устройствами
          </p>
        </div>
        
        <div className="flex gap-3">
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw size={16} className="mr-2" />
            Обновить
          </Button>
          <Button onClick={() => setShowCreateForm(true)}>
            <Plus size={16} className="mr-2" />
            Создать ключ
          </Button>
        </div>
      </div>

      {/* Сообщения */}
      {message.text && (
        <div className={`flex items-center p-4 rounded-lg ${
          message.type === 'success' 
            ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
            : 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
        }`}>
          {message.type === 'success' ? (
            <CheckCircle size={20} className="mr-2" />
          ) : (
            <AlertCircle size={20} className="mr-2" />
          )}
          {message.text}
        </div>
      )}

      {/* Статистика */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-blue-600">{stats.total_activations || 0}</div>
          <div className="text-sm text-gray-600">Всего активаций</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-green-600">{stats.active_activations || 0}</div>
          <div className="text-sm text-gray-600">Активных</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-orange-600">{stats.trial_activations || 0}</div>
          <div className="text-sm text-gray-600">Пробных</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-red-600">{stats.expired_activations || 0}</div>
          <div className="text-sm text-gray-600">Истекших</div>
        </Card>
      </div>

      {/* Фильтры */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              <Search size={16} className="inline mr-1" />
              Поиск
            </label>
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              placeholder="Ключ или ID устройства..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              <Filter size={16} className="inline mr-1" />
              Статус
            </label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            >
              <option value="all">Все статусы</option>
              <option value="active">Активные</option>
              <option value="trial">Пробные</option>
              <option value="expired">Истекшие</option>
              <option value="revoked">Отозванные</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Таблица активаций */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Ключ активации
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Устройство
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Статус
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Срок действия
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Создан
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Действия
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
              {filteredActivations.map(activation => {
                const status = statusLabels[activation.status] || { label: activation.status, color: 'secondary' };
                const isExpired = new Date(activation.expiry_date) < new Date();
                
                return (
                  <tr key={activation.id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <Key size={16} className="mr-2 text-blue-500" />
                        <div>
                          <div className="text-sm font-mono font-medium text-gray-900 dark:text-white">
                            {activation.key?.slice(0, 8)}...{activation.key?.slice(-4)}
                          </div>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => copyToClipboard(activation.key)}
                            className="text-xs mt-1"
                          >
                            <Copy size={12} className="mr-1" />
                            Копировать
                          </Button>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <Smartphone size={16} className="mr-2 text-gray-400" />
                        <div>
                          <div className="text-sm font-medium text-gray-900 dark:text-white">
                            {activation.machine_hash?.slice(0, 12)}...
                          </div>
                          <div className="text-sm text-gray-500">
                            ID: {activation.id}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant={status.color}>
                        {status.label}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900 dark:text-white">
                        {new Date(activation.expiry_date).toLocaleDateString('ru-RU')}
                      </div>
                      {isExpired && (
                        <div className="text-xs text-red-500">
                          Истек {Math.floor((new Date() - new Date(activation.expiry_date)) / (1000 * 60 * 60 * 24))} дн. назад
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900 dark:text-white">
                        {new Date(activation.created_at).toLocaleDateString('ru-RU')}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {/* Продлить лицензию */}}
                          disabled={activation.status === 'revoked'}
                        >
                          <Calendar size={14} />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => revokeActivation(activation.id)}
                          disabled={activation.status === 'revoked'}
                        >
                          <Shield size={14} />
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {filteredActivations.length === 0 && (
          <div className="text-center py-12">
            <Key size={48} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              Активации не найдены
            </h3>
            <p className="text-gray-500">
              {searchTerm || statusFilter !== 'all'
                ? 'Попробуйте изменить критерии поиска'
                : 'Создайте первый ключ активации'
              }
            </p>
          </div>
        )}
      </Card>

      {/* Форма создания ключа */}
      {showCreateForm && (
        <ActivationKeyForm
          onSave={generateActivationKey}
          onCancel={() => setShowCreateForm(false)}
        />
      )}

      {/* Информация */}
      <Card className="p-6 bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-700">
        <h3 className="text-lg font-medium mb-2 flex items-center text-blue-800 dark:text-blue-400">
          <Shield size={20} className="mr-2" />
          Как работает система активации
        </h3>
        <div className="text-sm text-blue-700 dark:text-blue-300 space-y-2">
          <p>• Каждое устройство требует уникальный ключ активации</p>
          <p>• Ключи имеют срок действия и могут быть отозваны</p>
          <p>• Пробные лицензии ограничены по функциональности</p>
          <p>• Система работает офлайн после успешной активации</p>
          <p>• Все активации логируются для аудита</p>
        </div>
      </Card>
    </div>
  );
};

// Компонент формы создания ключа
const ActivationKeyForm = ({ onSave, onCancel }) => {
  const [formData, setFormData] = useState({
    key_type: 'full',
    duration_days: 365,
    max_devices: 1,
    description: '',
    features: {
      full_access: true,
      ai_features: true,
      telegram_integration: true,
      print_system: true
    }
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(formData);
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleFeatureChange = (feature, enabled) => {
    setFormData(prev => ({
      ...prev,
      features: { ...prev.features, [feature]: enabled }
    }));
  };

  return (
    <Card className="p-6">
      <h3 className="text-lg font-medium mb-4">
        Создание ключа активации
      </h3>
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Тип лицензии
            </label>
            <select
              value={formData.key_type}
              onChange={(e) => handleChange('key_type', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            >
              <option value="trial">Пробная (30 дней)</option>
              <option value="full">Полная лицензия</option>
              <option value="enterprise">Корпоративная</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Срок действия (дни)
            </label>
            <input
              type="number"
              min="1"
              max="3650"
              value={formData.duration_days}
              onChange={(e) => handleChange('duration_days', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Максимум устройств
            </label>
            <input
              type="number"
              min="1"
              max="100"
              value={formData.max_devices}
              onChange={(e) => handleChange('max_devices', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Описание
            </label>
            <input
              type="text"
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              placeholder="Клиника №1, основная лицензия"
            />
          </div>
        </div>

        {/* Функции */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
            Включенные функции:
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="flex items-center">
              <input
                type="checkbox"
                checked={formData.features.full_access}
                onChange={(e) => handleFeatureChange('full_access', e.target.checked)}
                className="mr-2"
              />
              <span className="text-sm">Полный доступ</span>
            </label>

            <label className="flex items-center">
              <input
                type="checkbox"
                checked={formData.features.ai_features}
                onChange={(e) => handleFeatureChange('ai_features', e.target.checked)}
                className="mr-2"
              />
              <span className="text-sm">AI функции</span>
            </label>

            <label className="flex items-center">
              <input
                type="checkbox"
                checked={formData.features.telegram_integration}
                onChange={(e) => handleFeatureChange('telegram_integration', e.target.checked)}
                className="mr-2"
              />
              <span className="text-sm">Telegram интеграция</span>
            </label>

            <label className="flex items-center">
              <input
                type="checkbox"
                checked={formData.features.print_system}
                onChange={(e) => handleFeatureChange('print_system', e.target.checked)}
                className="mr-2"
              />
              <span className="text-sm">Система печати</span>
            </label>
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={onCancel}>
            Отменить
          </Button>
          <Button type="submit">
            <Key size={16} className="mr-2" />
            Создать ключ
          </Button>
        </div>
      </form>
    </Card>
  );
};

export default ActivationSystem;
