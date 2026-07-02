import { useState, useEffect, useCallback } from 'react';
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

  AlertTriangle,
  RefreshCw,


  Search,
  Eye,
  Settings,
  Globe,
  Zap,
  Users,
  Calendar,
  CreditCard,
  UserPlus } from
'lucide-react';
import {
  MacOSCard,
  Button,
  Badge,
  SegmentedControl,
  MacOSStatCard,
  Input,
  Select,
  MacOSEmptyState,
  Skeleton,
  Modal,
} from '../ui/macos';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';
// P-013 fix: shared ConfirmDialog hook replacing native confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';
const WebhookManager = () => {
  // P-013 fix: shared ConfirmDialog hook (replaces 1 native confirm() call).
  const [confirm, confirmDialog] = useConfirm();
  const [activeTab, setActiveTab] = useState('webhooks');
  const [webhooks, setWebhooks] = useState([]);
  const [calls, setCalls] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedWebhook, setSelectedWebhook] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [, setShowEditModal] = useState(false);
  const [, setShowTestModal] = useState(false);
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
      loadSystemStats()]
      );
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




















  const handleDeleteWebhook = async (webhookId) => {
    // P-013 fix: replaced native confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: 'Удаление webhook',
      message: 'Удалить этот webhook?',
      description: 'Это действие необратимо. Связанные вызовы останутся в журнале.',
      confirmLabel: 'Удалить',
      cancelLabel: 'Отмена',
      intent: 'danger',
    });
    if (!ok) {
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
  const filteredWebhooks = webhooks.filter((webhook) => {
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
        return <Badge variant="error">Ошибка</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getCallStatusBadge = (status) => {
    switch (status) {
      case 'success':
        return <Badge variant="success">Успех</Badge>;
      case 'failed':
        return <Badge variant="error">Ошибка</Badge>;
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
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <Skeleton style={{ height: '32px', width: '256px' }} />
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px'
        }}>
          <Skeleton style={{ height: '128px' }} />
          <Skeleton style={{ height: '128px' }} />
          <Skeleton style={{ height: '128px' }} />
        </div>
        <Skeleton style={{ height: '384px' }} />
      </div>);

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
          }}>Управление webhook-ами</h1>
          <p style={{
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-base)',
            margin: '4px 0 0 0'
          }}>Настройка и мониторинг внешних интеграций</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Plus style={{ width: '16px', height: '16px' }} />
          Создать Webhook
        </Button>
      </div>

      {/* Статистика */}
      {stats &&
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '16px'
      }}>
          <MacOSStatCard
          title="Всего Webhook'ов"
          value={stats.total_webhooks}
          icon={Globe}
          color="blue" />

          
          <MacOSStatCard
          title="Активных"
          value={stats.active_webhooks}
          icon={CheckCircle}
          color="green" />

          
          <MacOSStatCard
          title="Вызовов за 24ч"
          value={stats.recent_24h.total_calls}
          icon={Activity}
          color="orange" />

          
          <MacOSStatCard
          title="Успешность"
          value={`${stats.recent_24h.success_rate.toFixed(1)}%`}
          icon={Zap}
          color="blue" />

        </div>
      }

      {/* Табы */}
      <SegmentedControl
        value={activeTab}
        onChange={setActiveTab}
        options={[
        { value: 'webhooks', label: <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}><Globe style={{ width: '14px', height: '14px' }} />Webhook&apos;{'\u0438'}</span> },
        { value: 'calls', label: <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}><Activity style={{ width: '14px', height: '14px' }} />{'\u0412\u044b\u0437\u043e\u0432\u044b'}</span> },
        { value: 'events', label: <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}><Clock style={{ width: '14px', height: '14px' }} />{'\u0421\u043e\u0431\u044b\u0442\u0438\u044f'}</span> }]
        }
        size="large"
        style={{ flexWrap: 'wrap', rowGap: '4px' }} />


      {/* Контент табов */}
      {activeTab === 'webhooks' &&
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
                <Input
                type="text"
                placeholder="Название или URL..."
                value={filters.search}
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                icon={Search}
                iconPosition="left" />

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
                <Select
                value={filters.status}
                onChange={(value) => setFilters({ ...filters, status: value })}
                options={[
                { value: '', label: '\u0412\u0441\u0435 \u0441\u0442\u0430\u0442\u0443\u0441\u044b' },
                { value: 'active', label: '\u0410\u043a\u0442\u0438\u0432\u0435\u043d' },
                { value: 'inactive', label: '\u041d\u0435\u0430\u043a\u0442\u0438\u0432\u0435\u043d' },
                { value: 'suspended', label: '\u041f\u0440\u0438\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u043b\u0435\u043d' },
                { value: 'failed', label: '\u041e\u0448\u0438\u0431\u043a\u0430' }]
                }></Select>

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
                <Select
                value={filters.event_type}
                onChange={(value) => setFilters({ ...filters, event_type: value })}
                options={[
                { value: '', label: '\u0412\u0441\u0435 \u0441\u043e\u0431\u044b\u0442\u0438\u044f' },
                { value: 'patient.created', label: '\u041f\u0430\u0446\u0438\u0435\u043d\u0442 \u0441\u043e\u0437\u0434\u0430\u043d' },
                { value: 'appointment.created', label: '\u0417\u0430\u043f\u0438\u0441\u044c \u0441\u043e\u0437\u0434\u0430\u043d\u0430' },
                { value: 'visit.completed', label: '\u0412\u0438\u0437\u0438\u0442 \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d' },
                { value: 'payment.completed', label: '\u041f\u043b\u0430\u0442\u0435\u0436 \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d' }]
                }></Select>

              </div>
              
              <div style={{ display: 'flex', alignItems: 'end' }}>
                <Button
                onClick={() => setFilters({ status: '', event_type: '', search: '' })}
                variant="outline"
                style={{ width: '100%' }}>

                  Сбросить
                </Button>
              </div>
            </div>
          </MacOSCard>

          {/* Список webhook'ов */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {filteredWebhooks.map((webhook) =>
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
                    
                    {webhook.description &&
                <p style={{
                  color: 'var(--mac-text-secondary)',
                  fontSize: 'var(--mac-font-size-sm)',
                  marginBottom: '8px'
                }}>
                        {webhook.description}
                      </p>
                }
                    
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
                        {(webhook.successful_calls / webhook.total_calls * 100 || 0).toFixed(1)}% успешных
                      </span>
                    </div>
                    
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {webhook.events.map((event, index) =>
                  <Badge key={index} variant="outline" style={{ fontSize: 'var(--mac-font-size-xs)' }}>
                          {event}
                        </Badge>
                  )}
                    </div>
                  </div>
                  
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '16px' }}>
                    <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  title="Просмотреть вызовы webhook"
                  aria-label={`Просмотреть вызовы webhook ${webhook.name || webhook.id}`}
                  onClick={() => {
                    setSelectedWebhook(webhook);
                    loadWebhookCalls(webhook.id);
                  }}>

                      <Eye aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                    </Button>
                    
                    <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  title="Протестировать webhook"
                  aria-label={`Протестировать webhook ${webhook.name || webhook.id}`}
                  onClick={() => {
                    setSelectedWebhook(webhook);
                    setShowTestModal(true);
                  }}>

                      <TestTube aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                    </Button>
                    
                    <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  title="Редактировать webhook"
                  aria-label={`Редактировать webhook ${webhook.name || webhook.id}`}
                  onClick={() => {
                    setSelectedWebhook(webhook);
                    setShowEditModal(true);
                  }}>

                      <Edit aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                    </Button>
                    
                    {webhook.is_active ?
                <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  title="Приостановить webhook"
                  aria-label={`Приостановить webhook ${webhook.name || webhook.id}`}
                  onClick={() => handleDeactivateWebhook(webhook.id)}>

                        <Pause aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                      </Button> :

                <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  title="Активировать webhook"
                  aria-label={`Активировать webhook ${webhook.name || webhook.id}`}
                  onClick={() => handleActivateWebhook(webhook.id)}>

                        <Play aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                      </Button>
                }
                    
                    <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  title="Удалить webhook"
                  aria-label={`Удалить webhook ${webhook.name || webhook.id}`}
                  onClick={() => handleDeleteWebhook(webhook.id)}
                  style={{ color: 'var(--mac-error)' }}>

                      <Trash2 aria-hidden="true" style={{ width: '16px', height: '16px' }} />
                    </Button>
                  </div>
                </div>
              </MacOSCard>
          )}
          </div>

          {filteredWebhooks.length === 0 &&
        <MacOSEmptyState
          icon={Globe}
          title="Webhook'и не найдены"
          description={
          webhooks.length === 0 ?
          'Создайте первый webhook для начала работы с внешними интеграциями' :
          'Попробуйте изменить фильтры поиска'
          }
          action={
          webhooks.length === 0 ?
          <Button onClick={() => setShowCreateModal(true)}>
                  Создать Webhook
                  </Button> :
          null
          }
          iconStyle={{ width: '48px', height: '48px', color: 'var(--mac-text-tertiary)' }} />

        }
        </div>
      }

      {activeTab === 'calls' &&
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
              Все вызовы webhook-ов
            </h2>
            <Button
            onClick={() => {
              // Загружаем вызовы для всех webhook'ов
              Promise.all(webhooks.map((webhook) => loadWebhookCalls(webhook.id)));
            }}
            variant="outline"
            size="sm">

              <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Обновить
            </Button>
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
                <Select
                value={selectedWebhook?.id ? String(selectedWebhook.id) : ''}
                onChange={(value) => {
                  const webhook = webhooks.find((w) => String(w.id) === value);
                  setSelectedWebhook(webhook);
                  if (webhook) loadWebhookCalls(webhook.id);
                }}
                options={[
                { value: '', label: '\u0412\u0441\u0435 webhook\'\u0438' },
                ...webhooks.map((webhook) => ({ value: String(webhook.id), label: webhook.name }))]
                }></Select>

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
                <Select
                value={filters.call_status || ''}
                onChange={(value) => setFilters({ ...filters, call_status: value })}
                options={[
                { value: '', label: '\u0412\u0441\u0435 \u0441\u0442\u0430\u0442\u0443\u0441\u044b' },
                { value: 'success', label: '\u0423\u0441\u043f\u0435\u0448\u043d\u044b\u0435' },
                { value: 'failed', label: '\u041e\u0448\u0438\u0431\u043a\u0438' },
                { value: 'pending', label: '\u041e\u0436\u0438\u0434\u0430\u043d\u0438\u0435' },
                { value: 'retrying', label: '\u041f\u043e\u0432\u0442\u043e\u0440' }]
                }></Select>

              </div>
            </div>
          </MacOSCard>

          {/* Список вызовов */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {calls.map((call) =>
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
                      {call.response_status_code &&
                  <Badge variant="outline">
                          HTTP {call.response_status_code}
                        </Badge>
                  }
                      {selectedWebhook &&
                  <Badge variant="secondary" style={{ fontSize: 'var(--mac-font-size-xs)' }}>
                          {selectedWebhook.name}
                        </Badge>
                  }
                    </div>
                    
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-tertiary)' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Clock style={{ width: '16px', height: '16px' }} />
                        {new Date(call.created_at).toLocaleString()}
                      </span>
                      {call.duration_ms &&
                  <span>{call.duration_ms}ms</span>
                  }
                      <span>Попытка {call.attempt_number}/{call.max_attempts}</span>
                    </div>
                    
                    {call.error_message &&
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
                }
                  </div>
                </div>
              </MacOSCard>
          )}
          </div>

          {calls.length === 0 &&
        <MacOSEmptyState
          icon={Activity}
          title="Вызовы не найдены"
          description={selectedWebhook ? 'Для этого webhook\'а еще не было вызовов' : 'Выберите webhook для просмотра его вызовов'}
          iconStyle={{ width: '48px', height: '48px', color: 'var(--mac-text-tertiary)' }} />

        }
        </div>
      }

      {activeTab === 'events' &&
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
            <Button
            onClick={() => {
              // Обновляем список событий
              loadWebhooks();
            }}
            variant="outline"
            size="sm">

              <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Обновить
            </Button>
          </div>

          {/* Статистика событий */}
          <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px'
        }}>
            <MacOSStatCard
            title="Всего типов событий"
            value={new Set(webhooks.flatMap((w) => w.events)).size}
            icon={Clock}
            color="blue" />

            
            <MacOSStatCard
            title="Активных событий"
            value={webhooks.filter((w) => w.is_active).flatMap((w) => w.events).length}
            icon={CheckCircle}
            color="green" />

            
            <MacOSStatCard
            title="Пациентские события"
            value={webhooks.flatMap((w) => w.events).filter((e) => e.includes('patient')).length}
            icon={Users}
            color="orange" />

            
            <MacOSStatCard
            title="Платежные события"
            value={webhooks.flatMap((w) => w.events).filter((e) => e.includes('payment')).length}
            icon={CreditCard}
            color="purple" />

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
            }].
            map((event) => {
              const IconComponent = event.icon;
              const webhookCount = webhooks.filter((w) => w.events.includes(event.type)).length;

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
                      <Badge variant="outline" style={{ fontSize: 'var(--mac-font-size-xs)' }}>
                        {event.type}
                      </Badge>
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
                      {webhookCount > 0 &&
                    <Badge variant="success" style={{ fontSize: 'var(--mac-font-size-xs)' }}>
                          Активно
                        </Badge>
                    }
                    </div>
                  </div>);

            })}
            </div>
          </MacOSCard>
        </div>
      }

      {/* Модальные окна */}
      {showCreateModal &&
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Создать Webhook"
        size="lg">

          <div style={{ padding: '24px' }}>
            <p style={{
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
            marginBottom: '16px'
          }}>
              Функционал создания webhook-а будет добавлен в следующей итерации
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <Button onClick={() => setShowCreateModal(false)}>
              Закрыть
              </Button>
            </div>
          </div>
        </Modal>
      }
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </div>);

};

export default WebhookManager;
