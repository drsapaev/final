import React, { useState, useEffect, useCallback } from 'react';
import { 
  Plus, 
  Edit, 
  Trash2, 
  Play, 
  Pause, 
  TestTube, 
  Activity, 
  Clock, 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  RefreshCw,
  Download,
  Filter,
  Search,
  Eye,
  Settings,
  Globe,
  Zap
} from 'lucide-react';
import { Card, Button, Badge, Skeleton } from '../ui/native';
import { toast } from 'react-toastify';

const WebhookManager = () => {
  const [activeTab, setActiveTab] = useState('webhooks');
  const [webhooks, setWebhooks] = useState([]);
  const [calls, setCalls] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedWebhook, setSelectedWebhook] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showTestModal, setShowTestModal] = useState(false);
  const [filters, setFilters] = useState({
    status: '',
    event_type: '',
    search: ''
  });

  // Загрузка данных
  const loadWebhooks = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/webhooks/', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setWebhooks(data.items || []);
      } else {
        toast.error('Ошибка загрузки webhook\'ов');
      }
    } catch (error) {
      console.error('Ошибка загрузки webhook\'ов:', error);
      toast.error('Ошибка загрузки данных');
    }
  }, []);

  const loadSystemStats = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/webhooks/system/stats', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
    }
  }, []);

  const loadWebhookCalls = useCallback(async (webhookId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/webhooks/${webhookId}/calls`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setCalls(data.items || []);
      }
    } catch (error) {
      console.error('Ошибка загрузки вызовов:', error);
    }
  }, []);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([
        loadWebhooks(),
        loadSystemStats()
      ]);
      setLoading(false);
    };

    loadData();
  }, [loadWebhooks, loadSystemStats]);

  // Действия с webhook'ами
  const handleActivateWebhook = async (webhookId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/webhooks/${webhookId}/activate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        toast.success('Webhook активирован');
        loadWebhooks();
      } else {
        toast.error('Ошибка активации webhook\'а');
      }
    } catch (error) {
      console.error('Ошибка активации:', error);
      toast.error('Ошибка активации webhook\'а');
    }
  };

  const handleDeactivateWebhook = async (webhookId) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/webhooks/${webhookId}/deactivate`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        toast.success('Webhook деактивирован');
        loadWebhooks();
      } else {
        toast.error('Ошибка деактивации webhook\'а');
      }
    } catch (error) {
      console.error('Ошибка деактивации:', error);
      toast.error('Ошибка деактивации webhook\'а');
    }
  };

  const handleTestWebhook = async (webhookId, eventType, testData) => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/webhooks/${webhookId}/test`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          webhook_id: webhookId,
          event_type: eventType,
          test_data: testData
        })
      });

      if (response.ok) {
        const result = await response.json();
        if (result.success) {
          toast.success('Тестовый webhook отправлен');
        } else {
          toast.error(`Ошибка тестирования: ${result.error_message}`);
        }
      } else {
        toast.error('Ошибка отправки тестового webhook\'а');
      }
    } catch (error) {
      console.error('Ошибка тестирования:', error);
      toast.error('Ошибка тестирования webhook\'а');
    }
  };

  const handleDeleteWebhook = async (webhookId) => {
    if (!confirm('Вы уверены, что хотите удалить этот webhook?')) {
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/webhooks/${webhookId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        toast.success('Webhook удален');
        loadWebhooks();
      } else {
        toast.error('Ошибка удаления webhook\'а');
      }
    } catch (error) {
      console.error('Ошибка удаления:', error);
      toast.error('Ошибка удаления webhook\'а');
    }
  };

  // Фильтрация webhook'ов
  const filteredWebhooks = webhooks.filter(webhook => {
    if (filters.status && webhook.status !== filters.status) return false;
    if (filters.event_type && !webhook.events.includes(filters.event_type)) return false;
    if (filters.search && !webhook.name.toLowerCase().includes(filters.search.toLowerCase()) && 
        !webhook.url.toLowerCase().includes(filters.search.toLowerCase())) return false;
    return true;
  });

  // Получение статуса badge
  const getStatusBadge = (status, isActive) => {
    if (!isActive) {
      return <Badge variant="secondary">Неактивен</Badge>;
    }
    
    switch (status) {
      case 'active':
        return <Badge variant="success">Активен</Badge>;
      case 'suspended':
        return <Badge variant="warning">Приостановлен</Badge>;
      case 'failed':
        return <Badge variant="destructive">Ошибка</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getCallStatusBadge = (status) => {
    switch (status) {
      case 'success':
        return <Badge variant="success">Успех</Badge>;
      case 'failed':
        return <Badge variant="destructive">Ошибка</Badge>;
      case 'pending':
        return <Badge variant="secondary">Ожидание</Badge>;
      case 'retrying':
        return <Badge variant="warning">Повтор</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
          <Skeleton className="h-32" />
        </div>
        <Skeleton className="h-96" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Управление Webhook'ами</h1>
          <p className="text-gray-600">Настройка и мониторинг внешних интеграций</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)} className="flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Создать Webhook
        </Button>
      </div>

      {/* Статистика */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Всего Webhook'ов</p>
                <p className="text-2xl font-bold">{stats.total_webhooks}</p>
              </div>
              <Globe className="w-8 h-8 text-blue-500" />
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Активных</p>
                <p className="text-2xl font-bold text-green-600">{stats.active_webhooks}</p>
              </div>
              <CheckCircle className="w-8 h-8 text-green-500" />
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Вызовов за 24ч</p>
                <p className="text-2xl font-bold">{stats.recent_24h.total_calls}</p>
              </div>
              <Activity className="w-8 h-8 text-purple-500" />
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Успешность</p>
                <p className="text-2xl font-bold text-blue-600">{stats.recent_24h.success_rate.toFixed(1)}%</p>
              </div>
              <Zap className="w-8 h-8 text-yellow-500" />
            </div>
          </Card>
        </div>
      )}

      {/* Табы */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('webhooks')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'webhooks'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Webhook'и
          </button>
          <button
            onClick={() => setActiveTab('calls')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'calls'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Вызовы
          </button>
          <button
            onClick={() => setActiveTab('events')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'events'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            События
          </button>
        </nav>
      </div>

      {/* Контент табов */}
      {activeTab === 'webhooks' && (
        <div className="space-y-4">
          {/* Фильтры */}
          <Card className="p-4">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Поиск
                </label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                  <input
                    type="text"
                    placeholder="Название или URL..."
                    value={filters.search}
                    onChange={(e) => setFilters({...filters, search: e.target.value})}
                    className="pl-10 pr-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 w-full"
                  />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Статус
                </label>
                <select
                  value={filters.status}
                  onChange={(e) => setFilters({...filters, status: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">Все статусы</option>
                  <option value="active">Активен</option>
                  <option value="inactive">Неактивен</option>
                  <option value="suspended">Приостановлен</option>
                  <option value="failed">Ошибка</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Тип события
                </label>
                <select
                  value={filters.event_type}
                  onChange={(e) => setFilters({...filters, event_type: e.target.value})}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">Все события</option>
                  <option value="patient.created">Пациент создан</option>
                  <option value="appointment.created">Запись создана</option>
                  <option value="visit.completed">Визит завершен</option>
                  <option value="payment.completed">Платеж завершен</option>
                </select>
              </div>
              
              <div className="flex items-end">
                <Button 
                  onClick={() => setFilters({status: '', event_type: '', search: ''})}
                  variant="outline"
                  className="w-full"
                >
                  Сбросить
                </Button>
              </div>
            </div>
          </Card>

          {/* Список webhook'ов */}
          <div className="grid grid-cols-1 gap-4">
            {filteredWebhooks.map((webhook) => (
              <Card key={webhook.id} className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-gray-900">{webhook.name}</h3>
                      {getStatusBadge(webhook.status, webhook.is_active)}
                    </div>
                    
                    {webhook.description && (
                      <p className="text-gray-600 mb-2">{webhook.description}</p>
                    )}
                    
                    <div className="flex items-center gap-4 text-sm text-gray-500 mb-3">
                      <span className="flex items-center gap-1">
                        <Globe className="w-4 h-4" />
                        {webhook.url}
                      </span>
                      <span className="flex items-center gap-1">
                        <Activity className="w-4 h-4" />
                        {webhook.total_calls} вызовов
                      </span>
                      <span className="flex items-center gap-1">
                        <CheckCircle className="w-4 h-4" />
                        {((webhook.successful_calls / webhook.total_calls) * 100 || 0).toFixed(1)}% успешных
                      </span>
                    </div>
                    
                    <div className="flex flex-wrap gap-1">
                      {webhook.events.map((event, index) => (
                        <Badge key={index} variant="outline" className="text-xs">
                          {event}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2 ml-4">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelectedWebhook(webhook);
                        loadWebhookCalls(webhook.id);
                      }}
                    >
                      <Eye className="w-4 h-4" />
                    </Button>
                    
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelectedWebhook(webhook);
                        setShowTestModal(true);
                      }}
                    >
                      <TestTube className="w-4 h-4" />
                    </Button>
                    
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelectedWebhook(webhook);
                        setShowEditModal(true);
                      }}
                    >
                      <Edit className="w-4 h-4" />
                    </Button>
                    
                    {webhook.is_active ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeactivateWebhook(webhook.id)}
                      >
                        <Pause className="w-4 h-4" />
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleActivateWebhook(webhook.id)}
                      >
                        <Play className="w-4 h-4" />
                      </Button>
                    )}
                    
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDeleteWebhook(webhook.id)}
                      className="text-red-600 hover:text-red-700"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>

          {filteredWebhooks.length === 0 && (
            <Card className="p-8 text-center">
              <Globe className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">Webhook'и не найдены</h3>
              <p className="text-gray-600 mb-4">
                {webhooks.length === 0 
                  ? 'Создайте первый webhook для начала работы с внешними интеграциями'
                  : 'Попробуйте изменить фильтры поиска'
                }
              </p>
              {webhooks.length === 0 && (
                <Button onClick={() => setShowCreateModal(true)}>
                  Создать Webhook
                </Button>
              )}
            </Card>
          )}
        </div>
      )}

      {activeTab === 'calls' && selectedWebhook && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">
              Вызовы для "{selectedWebhook.name}"
            </h2>
            <Button
              onClick={() => loadWebhookCalls(selectedWebhook.id)}
              variant="outline"
              size="sm"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Обновить
            </Button>
          </div>

          <div className="space-y-2">
            {calls.map((call) => (
              <Card key={call.id} className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <span className="font-medium">{call.event_type}</span>
                      {getCallStatusBadge(call.status)}
                      {call.response_status_code && (
                        <Badge variant="outline">
                          HTTP {call.response_status_code}
                        </Badge>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-4 text-sm text-gray-500">
                      <span className="flex items-center gap-1">
                        <Clock className="w-4 h-4" />
                        {new Date(call.created_at).toLocaleString()}
                      </span>
                      {call.duration_ms && (
                        <span>{call.duration_ms}ms</span>
                      )}
                      <span>Попытка {call.attempt_number}/{call.max_attempts}</span>
                    </div>
                    
                    {call.error_message && (
                      <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                        {call.error_message}
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>

          {calls.length === 0 && (
            <Card className="p-8 text-center">
              <Activity className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">Вызовы не найдены</h3>
              <p className="text-gray-600">
                Для этого webhook'а еще не было вызовов
              </p>
            </Card>
          )}
        </div>
      )}

      {/* Модальные окна будут добавлены позже */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl">
            <h2 className="text-xl font-bold mb-4">Создать Webhook</h2>
            <p className="text-gray-600 mb-4">Функционал создания webhook'а будет добавлен в следующей итерации</p>
            <Button onClick={() => setShowCreateModal(false)}>
              Закрыть
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default WebhookManager;

