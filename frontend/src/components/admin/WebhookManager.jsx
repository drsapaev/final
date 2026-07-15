import { t } from '../../i18n/adapter';
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
  const [showEditModal, setShowEditModal] = useState(false); // P2 fix: restored value (was const [, setX] codemod artifact; UI not yet implemented — buttons set true but no modal renders)
  const [showTestModal, setShowTestModal] = useState(false); // P2 fix: restored value (same as above)
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
      title: t('admin2.delete_webhook_title'),
      message: 'Удалить этот webhook?',
      description: 'Это действие необратимо. Связанные вызовы останутся в журнале.',
      confirmLabel: t('admin2.delete_confirm'),
      cancelLabel: t('admin2.cancel'),
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
      <div className="flex flex-col gap-4">
        <Skeleton className="admin-h-32-w-256" />
        <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-16">
          <Skeleton className="admin-h-128" />
          <Skeleton className="admin-h-128" />
          <Skeleton className="admin-h-128" />
        </div>
        <Skeleton className="admin-h-384" />
      </div>);

  }

  return (
    <div className="flex flex-col gap-6">
      {/* Заголовок */}
      <div className="admin-flex-jc-between-ai-center">
        <div>
          <h1 className="admin-2xl-bold-primary-m-0">Управление webhook-ами</h1>
          <p className="admin-secondary-base-m-4px000">Настройка и мониторинг внешних интеграций</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)} className="flex items-center justify-center gap-2">
          <Plus className="w-4 h-4" />
          Создать Webhook
        </Button>
      </div>

      {/* Статистика */}
      {stats &&
      <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-16">
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
        { value: 'webhooks', label: <span className="admin-inline-flex-ai-center-gap-6"><Globe className="w-3.5 h-3.5" />Webhook&apos;{'\u0438'}</span> },
        { value: 'calls', label: <span className="admin-inline-flex-ai-center-gap-6"><Activity className="w-3.5 h-3.5" />{'\u0412\u044b\u0437\u043e\u0432\u044b'}</span> },
        { value: 'events', label: <span className="admin-inline-flex-ai-center-gap-6"><Clock className="w-3.5 h-3.5" />{'\u0421\u043e\u0431\u044b\u0442\u0438\u044f'}</span> }]
        }
        size="large"
        className="admin-wrap-rgap-4" />


      {/* Контент табов */}
      {activeTab === 'webhooks' &&
      <div className="flex flex-col gap-4">
          {/* Фильтры */}
          <MacOSCard className="p-4">
            <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-16">
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
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
                <label className="admin-block-sm-med-primary-mb-4">
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
                <label className="admin-block-sm-med-primary-mb-4">
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
              
              <div className="admin-flex-ai-end">
                <Button
                onClick={() => setFilters({ status: '', event_type: '', search: '' })}
                variant="outline"
                className="w-full">

                  Сбросить
                </Button>
              </div>
            </div>
          </MacOSCard>

          {/* Список webhook'ов */}
          <div className="flex flex-col gap-4">
            {filteredWebhooks.map((webhook) =>
          <MacOSCard key={webhook.id} className="p-6">
                <div className="admin-flex-ai-start-jc-between">
                  <div className="admin-flex-1">
                    <div className="admin-flex-ai-center-gap-12-mb-8">
                      <h3 className="admin-lg-semi-primary-m-0">
                        {webhook.name}
                      </h3>
                      {getStatusBadge(webhook.status, webhook.is_active)}
                    </div>
                    
                    {webhook.description &&
                <p className="admin-secondary-sm-mb-8">
                        {webhook.description}
                      </p>
                }
                    
                    <div className="admin-flex-ai-center-gap-16-sm-tertiary-mb-12">
                      <span className="flex items-center justify-center admin-gap-4">
                        <Globe className="w-4 h-4" />
                        {webhook.url}
                      </span>
                      <span className="flex items-center justify-center admin-gap-4">
                        <Activity className="w-4 h-4" />
                        {webhook.total_calls} вызовов
                      </span>
                      <span className="flex items-center justify-center admin-gap-4">
                        <CheckCircle className="w-4 h-4" />
                        {(webhook.successful_calls / webhook.total_calls * 100 || 0).toFixed(1)}% успешных
                      </span>
                    </div>
                    
                    <div className="admin-flex-wrap-gap-4">
                      {webhook.events.map((event, index) =>
                  <Badge key={index} variant="outline" className="admin-xs">
                          {event}
                        </Badge>
                  )}
                    </div>
                  </div>
                  
                  <div className="admin-flex-ai-center-gap-8-ml-16">
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

                      <Eye aria-hidden="true" className="w-4 h-4" />
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

                      <TestTube aria-hidden="true" className="w-4 h-4" />
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

                      <Edit aria-hidden="true" className="w-4 h-4" />
                    </Button>
                    
                    {webhook.is_active ?
                <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  title="Приостановить webhook"
                  aria-label={`Приостановить webhook ${webhook.name || webhook.id}`}
                  onClick={() => handleDeactivateWebhook(webhook.id)}>

                        <Pause aria-hidden="true" className="w-4 h-4" />
                      </Button> :

                <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  title="Активировать webhook"
                  aria-label={`Активировать webhook ${webhook.name || webhook.id}`}
                  onClick={() => handleActivateWebhook(webhook.id)}>

                        <Play aria-hidden="true" className="w-4 h-4" />
                      </Button>
                }
                    
                    <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  title="Удалить webhook"
                  aria-label={`Удалить webhook ${webhook.name || webhook.id}`}
                  onClick={() => handleDeleteWebhook(webhook.id)}
                  className="admin-error">

                      <Trash2 aria-hidden="true" className="w-4 h-4" />
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
      <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="admin-lg-semi-primary-m-0">
              Все вызовы webhook-ов
            </h2>
            <Button
            onClick={() => {
              // Загружаем вызовы для всех webhook'ов
              Promise.all(webhooks.map((webhook) => loadWebhookCalls(webhook.id)));
            }}
            variant="outline"
            size="sm">

              <RefreshCw className="w-4 h-4 mr-2" />
              Обновить
            </Button>
          </div>

          {/* Фильтры для вызовов */}
          <MacOSCard className="p-4">
            <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-16">
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
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
                <label className="admin-block-sm-med-primary-mb-4">
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
          <div className="flex flex-col gap-2">
            {calls.map((call) =>
          <MacOSCard key={call.id} className="p-4">
                <div className="flex items-center justify-between">
                  <div className="admin-flex-1">
                    <div className="admin-flex-ai-center-gap-12-mb-8">
                      <span className="admin-med-primary">
                        {call.event_type}
                      </span>
                      {getCallStatusBadge(call.status)}
                      {call.response_status_code &&
                  <Badge variant="outline">
                          HTTP {call.response_status_code}
                        </Badge>
                  }
                      {selectedWebhook &&
                  <Badge variant="secondary" className="admin-xs">
                          {selectedWebhook.name}
                        </Badge>
                  }
                    </div>
                    
                    <div className="admin-flex-ai-center-gap-16-sm-tertiary">
                      <span className="flex items-center justify-center admin-gap-4">
                        <Clock className="w-4 h-4" />
                        {new Date(call.created_at).toLocaleString()}
                      </span>
                      {call.duration_ms &&
                  <span>{call.duration_ms}ms</span>
                  }
                      <span>Попытка {call.attempt_number}/{call.max_attempts}</span>
                    </div>
                    
                    {call.error_message &&
                <div className="admin-mt-8-p-8-bg-error-bg-bd-1solidvar-mac-error-border-radius-var--mac-radius--78435787">
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
      <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="admin-lg-semi-primary-m-0">
              Типы событий
            </h2>
            <Button
            onClick={() => {
              // Обновляем список событий
              loadWebhooks();
            }}
            variant="outline"
            size="sm">

              <RefreshCw className="w-4 h-4 mr-2" />
              Обновить
            </Button>
          </div>

          {/* Статистика событий */}
          <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-16">
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
          <MacOSCard className="p-6">
            <h3 className="admin-lg-semi-primary-m-0016px0">
              Доступные типы событий
            </h3>
            
            <div className="admin-grid-gtc-rauto-fitcminmax300pxc1fr-gap-16">
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
                <div key={event.type} className="admin-p-16-bd-1solidvar-mac-border-radius-var--mac-radius-md-bg-bg-secondary">
                    <div className="admin-flex-ai-center-gap-12-mb-8">
                      <IconComponent className="admin-w-20-h-20" style={{ '--admin-color': event.color }} />
                      <h4 className="admin-base-semi-primary-m-0">
                        {event.name}
                      </h4>
                      <Badge variant="outline" className="admin-xs">
                        {event.type}
                      </Badge>
                    </div>
                    
                    <p className="admin-sm-secondary-m-008px0">
                      {event.description}
                    </p>
                    
                    <div className="flex items-center justify-between">
                      <span className="admin-xs-tertiary">
                        {webhookCount} webhook{webhookCount === 1 ? '' : webhookCount < 5 ? 'а' : 'ов'} используют это событие
                      </span>
                      {webhookCount > 0 &&
                    <Badge variant="success" className="admin-xs">
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

          <div className="p-6">
            <p className="admin-secondary-sm-mb-16">
              Функционал создания webhook-а будет добавлен в следующей итерации
            </p>
            <div className="admin-flex-jc-end-gap-8">
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
