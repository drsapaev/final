import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect, useCallback } from 'react';
import type { CSSProperties } from 'react';
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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // P-013 fix: shared ConfirmDialog hook (replaces 1 native confirm() call).
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;
  const [activeTab, setActiveTab] = useState('webhooks');
  const [webhooks, setWebhooks] = useState([]);
  const [calls, setCalls] = useState([]);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedWebhook, setSelectedWebhook] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false); // P2 fix: restored value (was const [, setX] codemod artifact; UI not yet implemented — buttons set true but no modal renders)
  const [showTestModal, setShowTestModal] = useState(false); // P2 fix: restored value (same as above)
  const [filters, setFilters] = useState({
    status: '',
    event_type: '',
    search: '',
    call_status: ''
  } as Record<string, unknown>);

  // Загрузка данных
  const loadWebhooks = useCallback(async () => {
    try {
      const { data } = await api.get('/webhooks/');
      setWebhooks(data.items || data || []);
    } catch (error) {
      logger.error('Ошибка загрузки webhook\'ов:', error);
      toast.error(t('admin2.wh_load_error'));
    }
  }, [t]);

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
      toast.success(t('admin2.wh_activated'));
      loadWebhooks();
    } catch (error) {
      logger.error('Ошибка активации:', error);
      toast.error(error.response?.data?.detail || t('admin2.wh_activate_error'));
    }
  };

  const handleDeactivateWebhook = async (webhookId) => {
    try {
      await api.post(`/webhooks/${webhookId}/deactivate`);
      toast.success(t('admin2.wh_deactivated'));
      loadWebhooks();
    } catch (error) {
      logger.error('Ошибка деактивации:', error);
      toast.error(error.response?.data?.detail || t('admin2.wh_deactivate_error'));
    }
  };




















  const handleDeleteWebhook = async (webhookId) => {
    // P-013 fix: replaced native confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: t('admin2.delete_webhook_title'),
      message: t('admin2.wh_delete_message'),
      description: t('admin2.wh_delete_description'),
      confirmLabel: t('admin2.delete_confirm'),
      cancelLabel: t('admin2.cancel'),
      intent: 'danger',
    });
    if (!ok) {
      return;
    }

    try {
      await api.delete(`/webhooks/${webhookId}`);
      toast.success(t('admin2.wh_deleted'));
      loadWebhooks();
    } catch (error) {
      logger.error('Ошибка удаления:', error);
      toast.error(error.response?.data?.detail || t('admin2.wh_delete_error'));
    }
  };

  // Фильтрация webhook'ов
  const filteredWebhooks = webhooks.filter((webhook: Record<string, unknown>) => {
    if (filters.status && String(webhook.status ?? '') !== filters.status) return false;
    if (filters.event_type && !(webhook.events as unknown[])?.includes(filters.event_type)) return false;
    if (filters.search && !String(webhook.name ?? '').toLowerCase().includes(String(filters.search ?? '').toLowerCase()) &&
    !String(webhook.url ?? '').toLowerCase().includes(String(filters.search ?? '').toLowerCase())) return false;
    return true;
  });

  // Получение статуса badge
  const getStatusBadge = (status, isActive) => {
    if (!isActive) {
      return <Badge variant="secondary">{t('admin2.wh_status_inactive')}</Badge>;
    }

    switch (status) {
      case 'active':
        return <Badge variant="success">{t('admin2.wh_status_active')}</Badge>;
      case 'suspended':
        return <Badge variant="warning">{t('admin2.wh_status_suspended')}</Badge>;
      case 'failed':
        return <Badge variant="error">{t('admin2.wh_status_failed')}</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getCallStatusBadge = (status) => {
    switch (status) {
      case 'success':
        return <Badge variant="success">{t('admin2.wh_call_status_success')}</Badge>;
      case 'failed':
        return <Badge variant="error">{t('admin2.wh_call_status_failed')}</Badge>;
      case 'pending':
        return <Badge variant="secondary">{t('admin2.wh_call_status_pending')}</Badge>;
      case 'retrying':
        return <Badge variant="warning">{t('admin2.wh_call_status_retrying')}</Badge>;
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
          <h1 className="admin-2xl-bold-primary-m-0">{t('admin2.wh_page_title')}</h1>
          <p className="admin-secondary-base-m-4px000">{t('admin2.wh_page_subtitle')}</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)} className="flex items-center justify-center gap-2">
          <Plus className="w-4 h-4" />
          {t('admin2.wh_create_btn')}
        </Button>
      </div>

      {/* Статистика */}
      {stats &&
      <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-16">
          <MacOSStatCard
          title={t('admin2.wh_stat_total')}
          value={String((stats as Record<string, unknown>)?.total_webhooks ?? "")}
          icon={Globe}
          color="blue" />

          
          <MacOSStatCard
          title={t('admin2.wh_stat_active')}
          value={String((stats as Record<string, unknown>)?.active_webhooks ?? "")}
          icon={CheckCircle}
          color="green" />

          
          <MacOSStatCard
          title={t('admin2.wh_stat_calls_24h')}
          value={String(((stats as Record<string, unknown>)?.recent_24h as Record<string, unknown>)?.total_calls ?? "")}
          icon={Activity}
          color="orange" />

          
          <MacOSStatCard
          title={t('admin2.wh_stat_success_rate')}
          value={`${Number(((stats as Record<string, unknown>)?.recent_24h as Record<string, unknown>)?.success_rate ?? 0).toFixed(1) ?? '0'}%`}
          icon={Zap}
          color="blue" />

        </div>
      }

      {/* Табы */}
      <SegmentedControl
        value={activeTab}
        onChange={(v: unknown) => setActiveTab(String(v))}
        options={[
        { value: 'webhooks', label: <span className="admin-inline-flex-ai-center-gap-6"><Globe className="w-3.5 h-3.5" />{t('admin2.wh_tab_webhooks')}</span> },
        { value: 'calls', label: <span className="admin-inline-flex-ai-center-gap-6"><Activity className="w-3.5 h-3.5" />{t('admin2.wh_tab_calls')}</span> },
        { value: 'events', label: <span className="admin-inline-flex-ai-center-gap-6"><Clock className="w-3.5 h-3.5" />{t('admin2.wh_tab_events')}</span> }]
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
                  {t('admin2.wh_search_label')}
                </label>
                <Input
                type="text"
                placeholder={t('admin2.wh_search_ph')}
                value={String(filters.search ?? "")}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setFilters({ ...filters, search: e.target.value })}
                icon={Search}
                iconPosition="left" />

              </div>
              
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
                  {t('admin2.wh_status_label')}
                </label>
                <Select
                value={String(filters.status ?? "")}
                onValueChange={(value) => setFilters({ ...filters, status: String(value) })}
                options={[
                { value: '', label: t('admin2.wh_status_all') },
                { value: 'active', label: t('admin2.wh_status_active') },
                { value: 'inactive', label: t('admin2.wh_status_inactive') },
                { value: 'suspended', label: t('admin2.wh_status_suspended') },
                { value: 'failed', label: t('admin2.wh_status_failed') }]
                }></Select>

              </div>
              
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
                  {t('admin2.wh_event_type_label')}
                </label>
                <Select
                value={String(filters.event_type ?? "")}
                onValueChange={(value) => setFilters({ ...filters, event_type: String(value) })}
                options={[
                { value: '', label: t('admin2.wh_events_all') },
                { value: 'patient.created', label: t('admin2.wh_event_patient_created') },
                { value: 'appointment.created', label: t('admin2.wh_event_appointment_created') },
                { value: 'visit.completed', label: t('admin2.wh_event_visit_completed') },
                { value: 'payment.completed', label: t('admin2.wh_event_payment_completed') }]
                }></Select>

              </div>
              
              <div className="admin-flex-ai-end">
                <Button
                onClick={() => setFilters({ status: '', event_type: '', search: '' })}
                variant="outline"
                className="w-full">

                  {t('admin2.wh_reset_filters')}
                </Button>
              </div>
            </div>
          </MacOSCard>

          {/* Список webhook'ов */}
          <div className="flex flex-col gap-4">
            {filteredWebhooks.map((webhook) =>
          <MacOSCard key={String(webhook.id ?? "")} className="p-6">
                <div className="admin-flex-ai-start-jc-between">
                  <div className="admin-flex-1">
                    <div className="admin-flex-ai-center-gap-12-mb-8">
                      <h3 className="admin-lg-semi-primary-m-0">
                        {String(webhook.name ?? "")}
                      </h3>
                      {getStatusBadge(webhook.status, webhook.is_active)}
                    </div>
                    
                    {webhook.description &&
                <p className="admin-secondary-sm-mb-8">
                        {String(webhook.description ?? "")}
                      </p>
                }
                    
                    <div className="admin-flex-ai-center-gap-16-sm-tertiary-mb-12">
                      <span className="flex items-center justify-center admin-gap-4">
                        <Globe className="w-4 h-4" />
                        {String(webhook.url ?? "")}
                      </span>
                      <span className="flex items-center justify-center admin-gap-4">
                        <Activity className="w-4 h-4" />
                        {t('admin2.wh_calls_count', { count: webhook.total_calls })}
                      </span>
                      <span className="flex items-center justify-center admin-gap-4">
                        <CheckCircle className="w-4 h-4" />
                        {t('admin2.wh_success_rate', { rate: (webhook.successful_calls / webhook.total_calls * 100 || 0).toFixed(1) })}
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
                  size="small"
                  variant="outline"
                  type="button"
                  title={t('admin2.wh_view_calls_title')}
                  aria-label={t('admin2.wh_view_calls_aria', { name: webhook.name || webhook.id })}
                  onClick={() => {
                    setSelectedWebhook(webhook);
                    loadWebhookCalls(webhook.id);
                  }}>

                      <Eye aria-hidden="true" className="w-4 h-4" />
                    </Button>
                    
                    <Button
                  size="small"
                  variant="outline"
                  type="button"
                  title={t('admin2.wh_test_webhook_title')}
                  aria-label={t('admin2.wh_test_webhook_aria', { name: webhook.name || webhook.id })}
                  onClick={() => {
                    setSelectedWebhook(webhook);
                    setShowTestModal(true);
                  }}>

                      <TestTube aria-hidden="true" className="w-4 h-4" />
                    </Button>
                    
                    <Button
                  size="small"
                  variant="outline"
                  type="button"
                  title={t('admin2.wh_edit_webhook_title')}
                  aria-label={t('admin2.wh_edit_webhook_aria', { name: webhook.name || webhook.id })}
                  onClick={() => {
                    setSelectedWebhook(webhook);
                    setShowEditModal(true);
                  }}>

                      <Edit aria-hidden="true" className="w-4 h-4" />
                    </Button>
                    
                    {webhook.is_active ?
                <Button
                  size="small"
                  variant="outline"
                  type="button"
                  title={t('admin2.wh_pause_webhook_title')}
                  aria-label={t('admin2.wh_pause_webhook_aria', { name: webhook.name || webhook.id })}
                  onClick={() => handleDeactivateWebhook(webhook.id)}>

                        <Pause aria-hidden="true" className="w-4 h-4" />
                      </Button> :

                <Button
                  size="small"
                  variant="outline"
                  type="button"
                  title={t('admin2.wh_activate_webhook_title')}
                  aria-label={t('admin2.wh_activate_webhook_aria', { name: webhook.name || webhook.id })}
                  onClick={() => handleActivateWebhook(webhook.id)}>

                        <Play aria-hidden="true" className="w-4 h-4" />
                      </Button>
                }
                    
                    <Button
                  size="small"
                  variant="outline"
                  type="button"
                  title={t('admin2.wh_delete_webhook_title')}
                  aria-label={t('admin2.wh_delete_webhook_aria', { name: webhook.name || webhook.id })}
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
          title={t('admin2.wh_empty_title')}
          description={
          webhooks.length === 0 ?
          t('admin2.wh_empty_desc_no_webhooks') :
          t('admin2.wh_empty_desc_filtered')
          }
          action={
          webhooks.length === 0 ?
          <Button onClick={() => setShowCreateModal(true)}>
                  {t('admin2.wh_create_btn')}
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
              {t('admin2.wh_calls_page_title')}
            </h2>
            <Button
            onClick={() => {
              // Загружаем вызовы для всех webhook'ов
              Promise.all(webhooks.map((webhook) => loadWebhookCalls(webhook.id)));
            }}
            variant="outline"
            size="small">

              <RefreshCw className="w-4 h-4 mr-2" />
              {t('admin2.wh_refresh_btn')}
            </Button>
          </div>

          {/* Фильтры для вызовов */}
          <MacOSCard className="p-4">
            <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-16">
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
                  {t('admin2.wh_webhook_label')}
                </label>
                <Select
                value={selectedWebhook?.id ? String(selectedWebhook.id) : ''}
                onChange={(value: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
                  const webhook = webhooks.find((w) => String(w.id) === String(value));
                  setSelectedWebhook(webhook);
                  if (webhook) loadWebhookCalls(webhook.id);
                }}
                options={[
                { value: '', label: t('admin2.wh_all_webhooks') },
                ...webhooks.map((webhook) => ({ value: String(webhook.id), label: webhook.name }))]
                }></Select>

              </div>
              
              <div>
                <label className="admin-block-sm-med-primary-mb-4">
                  {t('admin2.wh_call_status_label')}
                </label>
                <Select
                value={String(filters.call_status ?? '')}
                onValueChange={(value) => setFilters({ ...filters, call_status: String(value) })}
                options={[
                { value: '', label: t('admin2.wh_status_all') },
                { value: 'success', label: t('admin2.wh_call_filter_success') },
                { value: 'failed', label: t('admin2.wh_call_filter_failed') },
                { value: 'pending', label: t('admin2.wh_call_status_pending') },
                { value: 'retrying', label: t('admin2.wh_call_status_retrying') }]
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
                      <span>{t('admin2.wh_attempt', { current: call.attempt_number, max: call.max_attempts })}</span>
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
          title={t('admin2.wh_calls_empty_title')}
          description={selectedWebhook ? t('admin2.wh_calls_empty_desc_with_webhook') : t('admin2.wh_calls_empty_desc_no_webhook')}
          iconStyle={{ width: '48px', height: '48px', color: 'var(--mac-text-tertiary)' }} />

        }
        </div>
      }

      {activeTab === 'events' &&
      <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="admin-lg-semi-primary-m-0">
              {t('admin2.wh_events_page_title')}
            </h2>
            <Button
            onClick={() => {
              // Обновляем список событий
              loadWebhooks();
            }}
            variant="outline"
            size="small">

              <RefreshCw className="w-4 h-4 mr-2" />
              {t('admin2.wh_refresh_btn')}
            </Button>
          </div>

          {/* Статистика событий */}
          <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-16">
            <MacOSStatCard
            title={t('admin2.wh_stat_event_types_total')}
            value={new Set(webhooks.flatMap((w) => w.events)).size}
            icon={Clock}
            color="blue" />

            
            <MacOSStatCard
            title={t('admin2.wh_stat_active_events')}
            value={webhooks.filter((w) => w.is_active).flatMap((w) => w.events).length}
            icon={CheckCircle}
            color="green" />

            
            <MacOSStatCard
            title={t('admin2.wh_stat_patient_events')}
            value={webhooks.flatMap((w) => w.events).filter((e) => e.includes('patient')).length}
            icon={Users}
            color="orange" />

            
            <MacOSStatCard
            title={t('admin2.wh_stat_payment_events')}
            value={webhooks.flatMap((w) => w.events).filter((e) => e.includes('payment')).length}
            icon={CreditCard}
            color="purple" />

          </div>

          {/* Список типов событий */}
          <MacOSCard className="p-6">
            <h3 className="admin-lg-semi-primary-m-0016px0">
              {t('admin2.wh_event_types_heading')}
            </h3>
            
            <div className="admin-grid-gtc-rauto-fitcminmax300pxc1fr-gap-16">
              {[
            {
              type: 'patient.created',
              name: t('admin2.wh_event_name_patient_created'),
              description: t('admin2.wh_event_desc_patient_created'),
              icon: UserPlus,
              color: 'var(--mac-success)'
            },
            {
              type: 'patient.updated',
              name: t('admin2.wh_event_name_patient_updated'),
              description: t('admin2.wh_event_desc_patient_updated'),
              icon: Edit,
              color: 'var(--mac-info)'
            },
            {
              type: 'appointment.created',
              name: t('admin2.wh_event_name_appointment_created'),
              description: t('admin2.wh_event_desc_appointment_created'),
              icon: Calendar,
              color: 'var(--mac-accent-blue)'
            },
            {
              type: 'appointment.updated',
              name: t('admin2.wh_event_name_appointment_updated'),
              description: t('admin2.wh_event_desc_appointment_updated'),
              icon: Edit,
              color: 'var(--mac-info)'
            },
            {
              type: 'visit.completed',
              name: t('admin2.wh_event_name_visit_completed'),
              description: t('admin2.wh_event_desc_visit_completed'),
              icon: CheckCircle,
              color: 'var(--mac-success)'
            },
            {
              type: 'payment.completed',
              name: t('admin2.wh_event_name_payment_completed'),
              description: t('admin2.wh_event_desc_payment_completed'),
              icon: CreditCard,
              color: 'var(--mac-success)'
            },
            {
              type: 'payment.failed',
              name: t('admin2.wh_event_name_payment_failed'),
              description: t('admin2.wh_event_desc_payment_failed'),
              icon: AlertTriangle,
              color: 'var(--mac-error)'
            },
            {
              type: 'system.maintenance',
              name: t('admin2.wh_event_name_system_maintenance'),
              description: t('admin2.wh_event_desc_system_maintenance'),
              icon: Settings,
              color: 'var(--mac-warning)'
            }].
            map((event) => {
              const IconComponent = event.icon;
              const webhookCount = webhooks.filter((w) => w.events.includes(event.type)).length;

              return (
                <div key={event.type} className="admin-p-16-bd-1solidvar-mac-border-radius-var--mac-radius-md-bg-bg-secondary">
                    <div className="admin-flex-ai-center-gap-12-mb-8">
                      <IconComponent className="admin-w-20-h-20" style={{ '--admin-color': event.color } as CSSProperties} />
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
                        {t('admin2.wh_webhooks_using_event', { count: webhookCount })}
                      </span>
                      {webhookCount > 0 &&
                    <Badge variant="success" className="admin-xs">
                          {t('admin2.wh_active_badge')}
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
        title={t('admin2.wh_create_btn')}
        size="lg">

          <div className="p-6">
            <p className="admin-secondary-sm-mb-16">
              {t('admin2.wh_create_modal_desc')}
            </p>
            <div className="admin-flex-jc-end-gap-8">
              <Button onClick={() => setShowCreateModal(false)}>
              {t('admin2.wh_close_btn')}
              </Button>
            </div>
          </div>
        </Modal>
      }
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog as unknown as React.ReactNode}
    </div>);

};

export default WebhookManager;
