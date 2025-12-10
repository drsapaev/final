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
  Zap,
  Users,
  Calendar,
  CreditCard,
  UserPlus
} from 'lucide-react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSBadge, 
  MacOSTab, 
  MacOSStatCard, 
  MacOSTable, 
  MacOSInput, 
  MacOSSelect,
  MacOSEmptyState,
  MacOSLoadingSkeleton,
  MacOSAlert,
  MacOSModal
} from '../ui/macos';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';
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
      const { data } = await api.get('/webhooks/');
      setWebhooks(data.items || data || []);
    } catch (error) {
      logger.error('Ошибка загрузки webhook\'ов:', error);
      toast.error('Ошибка загрузки webhook\'ов');
    }
  }, []);

  const loadSystemStats = useCallback(async () => {
    try {
      const { data } = await api.get('/webhooks/system/stats');
        setStats(data);
    } catch (error) {
      logger.error('Ошибка загрузки статистики:', error);
    }
  }, []);

  const loadWebhookCalls = useCallback(async (webhookId) => {
    try {
      const { data } = await api.get(`/webhooks/${webhookId}/calls`);
      setCalls(data.items || data || []);
    } catch (error) {
      logger.error('Ошибка загрузки вызовов:', error);
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
      await api.post(`/webhooks/${webhookId}/activate`);
      toast.success('Webhook активирован');
      loadWebhooks();
    } catch (error) {
      logger.error('Ошибка активации:', error);
      toast.error(error.response?.data?.detail || 'Ошибка активации webhook\'а');
    }
  };

  const handleDeactivateWebhook = async (webhookId) => {
    try {
      await api.post(`/webhooks/${webhookId}/deactivate`);
      toast.success('Webhook деактивирован');
      loadWebhooks();
    } catch (error) {
      logger.error('Ошибка деактивации:', error);
      toast.error(error.response?.data?.detail || 'Ошибка деактивации webhook\'а');
    }
  };

  const handleTestWebhook = async (webhookId, eventType, testData) => {
    try {
      const result = await api.post(`/webhooks/${webhookId}/test`, {
        webhook_id: webhookId,
        event_type: eventType,
        test_data: testData
      });

      if (result.data?.success) {
        toast.success('Тестовый webhook отправлен');
      } else {
        toast.error(`Ошибка тестирования: ${result.data?.error_message || 'Неизвестная ошибка'}`);
      }
    } catch (error) {
      logger.error('Ошибка тестирования:', error);
      toast.error(error.response?.data?.detail || 'Ошибка тестирования webhook\'а');
    }
  };

  const handleDeleteWebhook = async (webhookId) => {
    if (!confirm('Вы уверены, что хотите удалить этот webhook?')) {
      return;
    }

    try {
      await api.delete(`/webhooks/${webhookId}`);
      toast.success('Webhook удален');
      loadWebhooks();
    } catch (error) {
      logger.error('Ошибка удаления:', error);
      toast.error(error.response?.data?.detail || 'Ошибка удаления webhook\'а');
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
      return <MacOSBadge variant="secondary">Неактивен</MacOSBadge>;
    }
    
    switch (status) {
      case 'active':
        return <MacOSBadge variant="success">Активен</MacOSBadge>;
      case 'suspended':
        return <MacOSBadge variant="warning">Приостановлен</MacOSBadge>;
      case 'failed':
        return <MacOSBadge variant="error">Ошибка</MacOSBadge>;
      default:
        return <MacOSBadge variant="secondary">{status}</MacOSBadge>;
    }
  };

  const getCallStatusBadge = (status) => {
    switch (status) {
      case 'success':
        return <MacOSBadge variant="success">Успех</MacOSBadge>;
      case 'failed':
        return <MacOSBadge variant="error">Ошибка</MacOSBadge>;
      case 'pending':
        return <MacOSBadge variant="secondary">Ожидание</MacOSBadge>;
      case 'retrying':
        return <MacOSBadge variant="warning">Повтор</MacOSBadge>;
      default:
        return <MacOSBadge variant="secondary">{status}</MacOSBadge>;
    }
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <MacOSLoadingSkeleton style={{ height: '32px', width: '256px' }} />
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <MacOSLoadingSkeleton style={{ height: '128px' }} />
          <MacOSLoadingSkeleton style={{ height: '128px' }} />
          <MacOSLoadingSkeleton style={{ height: '128px' }} />
        </div>
        <MacOSLoadingSkeleton style={{ height: '384px' }} />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Заголовок */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ 
            fontSize: 'var(--mac-font-size-2xl)', 
            fontWeight: 'var(--mac-font-weight-bold)', 
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>Управление Webhook'ами</h1>
          <p style={{ 
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-base)',
            margin: '4px 0 0 0'
          }}>Настройка и мониторинг внешних интеграций</p>
        </div>
        <MacOSButton onClick={() => setShowCreateModal(true)} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Plus style={{ width: '16px', height: '16px' }} />
          Создать Webhook
        </MacOSButton>
      </div>

      {/* Статистика */}
      {stats && (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <MacOSStatCard
            title="Всего Webhook'ов"
            value={stats.total_webhooks}
            icon={Globe}
            color="blue"
          />
          
          <MacOSStatCard
            title="Активных"
            value={stats.active_webhooks}
            icon={CheckCircle}
            color="green"
          />
          
          <MacOSStatCard
            title="Вызовов за 24ч"
            value={stats.recent_24h.total_calls}
            icon={Activity}
            color="orange"
          />
          
          <MacOSStatCard
            title="Успешность"
            value={`${stats.recent_24h.success_rate.toFixed(1)}%`}
            icon={Zap}
            color="blue"
          />
        </div>
      )}

      {/* Табы */}
      <MacOSTab
        tabs={[
          { id: 'webhooks', label: 'Webhook\'и', icon: Globe },
          { id: 'calls', label: 'Вызовы', icon: Activity },
          { id: 'events', label: 'События', icon: Clock }
        ]}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        size="md"
        variant="default"
      />

      {/* Контент табов */}
      {activeTab === 'webhooks' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Фильтры */}
          <MacOSCard style={{ padding: '16px' }}>
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
              gap: '16px' 
            }}>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)',
                  marginBottom: '4px'
                }}>
                  Поиск
                </label>
                <MacOSInput
                  type="text"
                  placeholder="Название или URL..."
                  value={filters.search}
                  onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                  icon={Search}
                  iconPosition="left"
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
                  Статус
                </label>
                <MacOSSelect
                  value={filters.status}
                  onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                  options={[
                    { value: '', label: 'Все статусы' },
                    { value: 'active', label: 'Активен' },
                    { value: 'inactive', label: 'Неактивен' },
                    { value: 'suspended', label: 'Приостановлен' },
                    { value: 'failed', label: 'Ошибка' }
                  ]}
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
                  Тип события
                </label>
                <MacOSSelect
                  value={filters.event_type}
                  onChange={(e) => setFilters({ ...filters, event_type: e.target.value })}
                  options={[
                    { value: '', label: 'Все события' },
                    { value: 'patient.created', label: 'Пациент создан' },
                    { value: 'appointment.created', label: 'Запись создана' },
                    { value: 'visit.completed', label: 'Визит завершен' },
                    { value: 'payment.completed', label: 'Платеж завершен' }
                  ]}
                />
              </div>
              
              <div style={{ display: 'flex', alignItems: 'end' }}>
                <MacOSButton 
                  onClick={() => setFilters({ status: '', event_type: '', search: '' })}
                  variant="outline"
                  style={{ width: '100%' }}
                >
                  Сбросить
                </MacOSButton>
              </div>
            </div>
          </MacOSCard>

          {/* Список webhook'ов */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {filteredWebhooks.map((webhook) => (
              <MacOSCard key={webhook.id} style={{ padding: '24px' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                  <div style={{ flex: '1' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                      <h3 style={{ 
                        fontSize: 'var(--mac-font-size-lg)', 
                        fontWeight: 'var(--mac-font-weight-semibold)', 
                        color: 'var(--mac-text-primary)',
                        margin: 0
                      }}>
                        {webhook.name}
                      </h3>
                      {getStatusBadge(webhook.status, webhook.is_active)}
                    </div>
                    
                    {webhook.description && (
                      <p style={{ 
                        color: 'var(--mac-text-secondary)',
                        fontSize: 'var(--mac-font-size-sm)',
                        marginBottom: '8px'
                      }}>
                        {webhook.description}
                      </p>
                    )}
                    
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-tertiary)', marginBottom: '12px' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Globe style={{ width: '16px', height: '16px' }} />
                        {webhook.url}
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Activity style={{ width: '16px', height: '16px' }} />
                        {webhook.total_calls} вызовов
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <CheckCircle style={{ width: '16px', height: '16px' }} />
                        {((webhook.successful_calls / webhook.total_calls) * 100 || 0).toFixed(1)}% успешных
                      </span>
                    </div>
                    
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {webhook.events.map((event, index) => (
                        <MacOSBadge key={index} variant="outline" style={{ fontSize: 'var(--mac-font-size-xs)' }}>
                          {event}
                        </MacOSBadge>
                      ))}
                    </div>
                  </div>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '16px' }}>
                    <MacOSButton
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelectedWebhook(webhook);
                        loadWebhookCalls(webhook.id);
                      }}
                    >
                      <Eye style={{ width: '16px', height: '16px' }} />
                    </MacOSButton>
                    
                    <MacOSButton
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelectedWebhook(webhook);
                        setShowTestModal(true);
                      }}
                    >
                      <TestTube style={{ width: '16px', height: '16px' }} />
                    </MacOSButton>
                    
                    <MacOSButton
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setSelectedWebhook(webhook);
                        setShowEditModal(true);
                      }}
                    >
                      <Edit style={{ width: '16px', height: '16px' }} />
                    </MacOSButton>
                    
                    {webhook.is_active ? (
                      <MacOSButton
                        size="sm"
                        variant="outline"
                        onClick={() => handleDeactivateWebhook(webhook.id)}
                      >
                        <Pause style={{ width: '16px', height: '16px' }} />
                      </MacOSButton>
                    ) : (
                      <MacOSButton
                        size="sm"
                        variant="outline"
                        onClick={() => handleActivateWebhook(webhook.id)}
                      >
                        <Play style={{ width: '16px', height: '16px' }} />
                      </MacOSButton>
                    )}
                    
                    <MacOSButton
                      size="sm"
                      variant="outline"
                      onClick={() => handleDeleteWebhook(webhook.id)}
                      style={{ color: 'var(--mac-error)' }}
                    >
                      <Trash2 style={{ width: '16px', height: '16px' }} />
                    </MacOSButton>
                  </div>
                </div>
              </MacOSCard>
            ))}
          </div>

          {filteredWebhooks.length === 0 && (
            <MacOSEmptyState
              icon={Globe}
              title="Webhook'и не найдены"
              description={
                webhooks.length === 0 
                  ? 'Создайте первый webhook для начала работы с внешними интеграциями'
                  : 'Попробуйте изменить фильтры поиска'
                }
              action={
                webhooks.length === 0 ? (
                  <MacOSButton onClick={() => setShowCreateModal(true)}>
                  Создать Webhook
                  </MacOSButton>
                ) : null
              }
              iconStyle={{ width: '48px', height: '48px', color: 'var(--mac-text-tertiary)' }}
            />
          )}
        </div>
      )}

      {activeTab === 'calls' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              Все вызовы webhook'ов
            </h2>
            <MacOSButton
              onClick={() => {
                // Загружаем вызовы для всех webhook'ов
                Promise.all(webhooks.map(webhook => loadWebhookCalls(webhook.id)));
              }}
              variant="outline"
              size="sm"
            >
              <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Обновить
            </MacOSButton>
          </div>

          {/* Фильтры для вызовов */}
          <MacOSCard style={{ padding: '16px' }}>
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
              gap: '16px' 
            }}>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)',
                  marginBottom: '4px'
                }}>
                  Webhook
                </label>
                <MacOSSelect
                  value={selectedWebhook?.id || ''}
                  onChange={(e) => {
                    const webhook = webhooks.find(w => w.id === e.target.value);
                    setSelectedWebhook(webhook);
                    if (webhook) loadWebhookCalls(webhook.id);
                  }}
                  options={[
                    { value: '', label: 'Все webhook\'и' },
                    ...webhooks.map(webhook => ({ value: webhook.id, label: webhook.name }))
                  ]}
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
                  Статус вызова
                </label>
                <MacOSSelect
                  value={filters.call_status || ''}
                  onChange={(e) => setFilters({ ...filters, call_status: e.target.value })}
                  options={[
                    { value: '', label: 'Все статусы' },
                    { value: 'success', label: 'Успешные' },
                    { value: 'failed', label: 'Ошибки' },
                    { value: 'pending', label: 'Ожидание' },
                    { value: 'retrying', label: 'Повтор' }
                  ]}
                />
              </div>
            </div>
          </MacOSCard>

          {/* Список вызовов */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {calls.map((call) => (
              <MacOSCard key={call.id} style={{ padding: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ flex: '1' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                      <span style={{ 
                        fontWeight: 'var(--mac-font-weight-medium)',
                        color: 'var(--mac-text-primary)'
                      }}>
                        {call.event_type}
                      </span>
                      {getCallStatusBadge(call.status)}
                      {call.response_status_code && (
                        <MacOSBadge variant="outline">
                          HTTP {call.response_status_code}
                        </MacOSBadge>
                      )}
                      {selectedWebhook && (
                        <MacOSBadge variant="secondary" style={{ fontSize: 'var(--mac-font-size-xs)' }}>
                          {selectedWebhook.name}
                        </MacOSBadge>
                      )}
                    </div>
                    
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-tertiary)' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Clock style={{ width: '16px', height: '16px' }} />
                        {new Date(call.created_at).toLocaleString()}
                      </span>
                      {call.duration_ms && (
                        <span>{call.duration_ms}ms</span>
                      )}
                      <span>Попытка {call.attempt_number}/{call.max_attempts}</span>
                    </div>
                    
                    {call.error_message && (
                      <div style={{ 
                        marginTop: '8px', 
                        padding: '8px', 
                        backgroundColor: 'var(--mac-error-bg)', 
                        border: '1px solid var(--mac-error-border)', 
                        borderRadius: 'var(--mac-radius-sm)', 
                        fontSize: 'var(--mac-font-size-sm)', 
                        color: 'var(--mac-error)' 
                      }}>
                        {call.error_message}
                      </div>
                    )}
                  </div>
                </div>
              </MacOSCard>
            ))}
          </div>

          {calls.length === 0 && (
            <MacOSEmptyState
              icon={Activity}
              title="Вызовы не найдены"
              description={selectedWebhook ? 'Для этого webhook\'а еще не было вызовов' : 'Выберите webhook для просмотра его вызовов'}
              iconStyle={{ width: '48px', height: '48px', color: 'var(--mac-text-tertiary)' }}
            />
          )}
        </div>
      )}

      {activeTab === 'events' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              Типы событий
            </h2>
            <MacOSButton
              onClick={() => {
                // Обновляем список событий
                loadWebhooks();
              }}
              variant="outline"
              size="sm"
            >
              <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Обновить
            </MacOSButton>
          </div>

          {/* Статистика событий */}
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
            gap: '16px' 
          }}>
            <MacOSStatCard
              title="Всего типов событий"
              value={new Set(webhooks.flatMap(w => w.events)).size}
              icon={Clock}
              color="blue"
            />
            
            <MacOSStatCard
              title="Активных событий"
              value={webhooks.filter(w => w.is_active).flatMap(w => w.events).length}
              icon={CheckCircle}
              color="green"
            />
            
            <MacOSStatCard
              title="Пациентские события"
              value={webhooks.flatMap(w => w.events).filter(e => e.includes('patient')).length}
              icon={Users}
              color="orange"
            />
            
            <MacOSStatCard
              title="Платежные события"
              value={webhooks.flatMap(w => w.events).filter(e => e.includes('payment')).length}
              icon={CreditCard}
              color="purple"
            />
          </div>

          {/* Список типов событий */}
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: '0 0 16px 0'
            }}>
              Доступные типы событий
            </h3>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
              {[
                { 
                  type: 'patient.created', 
                  name: 'Создание пациента', 
                  description: 'Отправляется при создании нового пациента',
                  icon: UserPlus,
                  color: 'var(--mac-success)'
                },
                { 
                  type: 'patient.updated', 
                  name: 'Обновление пациента', 
                  description: 'Отправляется при изменении данных пациента',
                  icon: Edit,
                  color: 'var(--mac-info)'
                },
                { 
                  type: 'appointment.created', 
                  name: 'Создание записи', 
                  description: 'Отправляется при создании новой записи на прием',
                  icon: Calendar,
                  color: 'var(--mac-accent-blue)'
                },
                { 
                  type: 'appointment.updated', 
                  name: 'Обновление записи', 
                  description: 'Отправляется при изменении записи на прием',
                  icon: Edit,
                  color: 'var(--mac-info)'
                },
                { 
                  type: 'visit.completed', 
                  name: 'Завершение визита', 
                  description: 'Отправляется при завершении визита пациента',
                  icon: CheckCircle,
                  color: 'var(--mac-success)'
                },
                { 
                  type: 'payment.completed', 
                  name: 'Завершение платежа', 
                  description: 'Отправляется при успешном завершении платежа',
                  icon: CreditCard,
                  color: 'var(--mac-success)'
                },
                { 
                  type: 'payment.failed', 
                  name: 'Ошибка платежа', 
                  description: 'Отправляется при неудачной попытке платежа',
                  icon: AlertTriangle,
                  color: 'var(--mac-error)'
                },
                { 
                  type: 'system.maintenance', 
                  name: 'Техническое обслуживание', 
                  description: 'Отправляется при начале/завершении технических работ',
                  icon: Settings,
                  color: 'var(--mac-warning)'
                }
              ].map((event) => {
                const IconComponent = event.icon;
                const webhookCount = webhooks.filter(w => w.events.includes(event.type)).length;
                
                return (
                  <div key={event.type} style={{ 
                    padding: '16px', 
                    border: '1px solid var(--mac-border)', 
                    borderRadius: 'var(--mac-radius-md)',
                    backgroundColor: 'var(--mac-bg-secondary)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                      <IconComponent style={{ width: '20px', height: '20px', color: event.color }} />
                      <h4 style={{ 
                        fontSize: 'var(--mac-font-size-base)', 
                        fontWeight: 'var(--mac-font-weight-semibold)', 
                        color: 'var(--mac-text-primary)',
                        margin: 0
                      }}>
                        {event.name}
                      </h4>
                      <MacOSBadge variant="outline" style={{ fontSize: 'var(--mac-font-size-xs)' }}>
                        {event.type}
                      </MacOSBadge>
                    </div>
                    
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)',
                      margin: '0 0 8px 0'
                    }}>
                      {event.description}
                    </p>
                    
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ 
                        fontSize: 'var(--mac-font-size-xs)', 
                        color: 'var(--mac-text-tertiary)' 
                      }}>
                        {webhookCount} webhook{webhookCount === 1 ? '' : webhookCount < 5 ? 'а' : 'ов'} используют это событие
                      </span>
                      {webhookCount > 0 && (
                        <MacOSBadge variant="success" style={{ fontSize: 'var(--mac-font-size-xs)' }}>
                          Активно
                        </MacOSBadge>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </MacOSCard>
        </div>
      )}

      {/* Модальные окна */}
      {showCreateModal && (
        <MacOSModal
          isOpen={showCreateModal}
          onClose={() => setShowCreateModal(false)}
          title="Создать Webhook"
          size="lg"
        >
          <div style={{ padding: '24px' }}>
            <p style={{ 
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-sm)',
              marginBottom: '16px'
            }}>
              Функционал создания webhook'а будет добавлен в следующей итерации
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <MacOSButton onClick={() => setShowCreateModal(false)}>
              Закрыть
              </MacOSButton>
            </div>
          </div>
        </MacOSModal>
      )}
    </div>
  );
};

export default WebhookManager;

