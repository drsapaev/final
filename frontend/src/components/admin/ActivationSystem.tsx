import { useTranslation } from '../../i18n/useTranslation';
import { useCallback, useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import PropTypes from 'prop-types';
import {
  Key,
  Smartphone,
  Calendar,
  Shield,
  Plus,



  RefreshCw,
  AlertCircle,
  CheckCircle,
  Copy,

  Search,
  Filter } from




'lucide-react';
import {
  AppError, AppLoading, MacOSCard, Button, Badge, Input, Table, Checkbox, Select,
} from '../ui/macos';
// UX Audit: ModernDialog для extend-activation диалога (вместо window.prompt).
import ModernDialog from '../dialogs/ModernDialog';

import logger from '../../utils/logger';
import api from '../../api/client';
// P-013 fix: shared ConfirmDialog hook replacing native confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';

const buildStats = (items = []) => ({
  total_activations: items.length,
  active_activations: items.filter((item) => item.status === 'active').length,
  trial_activations: items.filter((item) => item.status === 'trial').length,
  expired_activations: items.filter((item) => item.status === 'expired').length
});

const parseMeta = (meta) => {
  if (!meta) return {};
  if (typeof meta === 'object') return meta;
  try {
    return JSON.parse(meta);
  } catch {
    return {};
  }
};

const ActivationSystem = () => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // P-013 fix: shared ConfirmDialog hook (replaces 1 native confirm() call).
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;
  const [loading, setLoading] = useState(true);
  
interface Activation {
  key?: string;
  machine_hash?: string;
  status?: string;
  expiry_date?: string;
  meta?: Record<string, unknown>;
  issued_at?: string;
  activated_at?: string;
  revoked_at?: string;
  [k: string]: unknown;
}

const [activations, setActivations] = useState<Activation[]>([]);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [serverStatus, setServerStatus] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [loadError, setLoadError] = useState('');

  // Статусы активации
  const statusLabels = {
    issued: { label: t('admin2.act_status_issued'), color: 'info' },
    active: { label: t('admin2.act_status_active'), color: 'success' },
    expired: { label: t('admin2.act_status_expired'), color: 'warning' },
    revoked: { label: t('admin2.act_status_revoked'), color: 'error' },
    trial: { label: t('admin2.act_status_trial'), color: 'info' }
  };

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setLoadError('');

      const [activationsRes, statusRes] = await Promise.all([
        api.get('/activation/list', { params: { limit: 100 } }),
        api.get('/activation/status')
      ]);

      const activationsData = activationsRes.data?.items || [];
      setActivations(activationsData);
      setStats(buildStats(activationsData));
      setServerStatus(statusRes.data || null);

    } catch (error) {
      logger.error('Ошибка загрузки данных активации:', error);
      const errorText = t('admin2.act_load_error');
      setLoadError(errorText);
      setMessage({ type: 'error', text: errorText });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const generateActivationKey = async (keyData) => {
    try {
      const payload = {
        days: Number(keyData.duration_days) || 365,
        status: keyData.key_type === 'trial' ? 'trial' : 'active',
        meta: JSON.stringify({
          key_type: keyData.key_type,
          duration_days: keyData.duration_days,
          max_devices: keyData.max_devices,
          description: keyData.description,
          features: keyData.features
        })
      };

      const response = (await api.post('/activation/issue', payload)) as import('axios').AxiosResponse<Record<string, unknown>>;
      const result = response.data || {};
      setMessage({ type: 'success', text: t('admin2.act_key_created') });
      setShowCreateForm(false);
      await loadData();
      return result;
    } catch (error) {
      logger.error('Ошибка создания ключа:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  const revokeActivation = async (activationKey) => {
    // P-013 fix: replaced native confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: t('admin2.revoke_activation_title'),
      message: t('admin2.act_revoke_message'),
      description: t('admin2.act_revoke_description'),
      confirmLabel: t('admin2.revoke_confirm'),
      cancelLabel: t('admin2.cancel'),
      intent: 'warning',
    });
    if (!ok) return;

    try {
      await api.post('/activation/revoke', { key: activationKey });
      setMessage({ type: 'success', text: t('admin2.act_revoked') });
      await loadData();
    } catch (error) {
      logger.error('Ошибка отзыва:', error);
      setMessage({ type: 'error', text: t('admin2.act_revoke_error') });
    }
  };

  // UX Audit: window.prompt() → модальный диалог с input полем.
  // state для extend dialog: { key, days } | null.
  const [extendDialog, setExtendDialog] = useState(null);

  const openExtendDialog = (activationKey) => {
    setExtendDialog({ key: activationKey, days: '30', error: '' });
  };

  const handleExtendDaysChange = (e) => {
    setExtendDialog((prev) => ({ ...prev, days: e.target.value, error: '' }));
  };

  const submitExtendActivation = async () => {
    if (!extendDialog) return;
    const days = Number.parseInt(extendDialog.days, 10);
    if (!Number.isFinite(days) || days <= 0) {
      setExtendDialog((prev) => ({ ...prev, error: t('admin2.act_invalid_days') }));
      return;
    }

    try {
      await api.post('/activation/extend', { key: extendDialog.key, days });
      setMessage({ type: 'success', text: t('admin2.act_extended') });
      setExtendDialog(null);
      await loadData();
    } catch (error) {
      logger.error('Ошибка продления:', error);
      setMessage({ type: 'error', text: t('admin2.act_extend_error') });
      setExtendDialog(null);
    }
  };

  const extendActivation = (activationKey) => {
    openExtendDialog(activationKey);
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setMessage({ type: 'success', text: t('admin2.act_copied') });
  };

  const filteredActivations = activations.filter((activation: Activation) => {
    const matchesSearch = activation.key?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    activation.machine_hash?.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || activation.status === statusFilter;

    return matchesSearch && matchesStatus;
  });
  const showInitialLoadError = loadError && activations.length === 0 && !serverStatus;

  if (loading) {
    return (
      <MacOSCard className="admin-card-p-32">
        <AppLoading
          title={t('admin2.act_loading_title')}
          description={t('admin2.act_loading_desc')}
          size="small"
        />
      </MacOSCard>);

  }

  if (showInitialLoadError) {
    return (
      <MacOSCard className="admin-card-p-32">
        <AppError
          title={t('admin2.act_load_failed_title')}
          description={loadError}
          action={
            <Button type="button" variant="outline" onClick={loadData} disabled={loading} loading={loading}>
              {t('admin2.act_retry')}
            </Button>
          }
        />
      </MacOSCard>);

  }

  return (
    <div className="flex flex-col gap-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="admin-h2-2xl-semi-primary-mb-4">
            {t('admin2.act_title')}
          </h2>
          <p className="admin-p-sm-secondary-m0">
            {t('admin2.act_subtitle')}
          </p>
        </div>

        <div className="admin-form-row-gap-12">
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw className="w-4 h-4 mr-2" />
            {t('admin2.act_refresh')}
          </Button>
          <Button onClick={() => setShowCreateForm(true)}>
            <Plus className="w-4 h-4 mr-2" />
            {t('admin2.act_create_key')}
          </Button>
        </div>
      </div>

      {serverStatus &&
      <div className="admin-status-banner" style={{
        '--admin-banner-bg': serverStatus.ok ? 'var(--mac-success-bg)' : 'var(--mac-warning-bg)',
        '--admin-banner-color': serverStatus.ok ? 'var(--mac-success)' : 'var(--mac-warning)',
        '--admin-banner-border': serverStatus.ok ? 'var(--mac-success-border)' : 'var(--mac-warning-border)'
      } as CSSProperties}>
          <Badge variant={serverStatus.ok ? 'success' : 'warning'}>
            {serverStatus.ok ? t('admin2.act_server_activated') : t('admin2.act_server_not_activated')}
          </Badge>
          <span className="text-sm">
            {serverStatus.ok ?
            t('admin2.act_key_value', { key: serverStatus.key || t('admin2.act_not_specified') }) :
            (serverStatus.reason || t('admin2.act_status_requires_check'))}
          </span>
        </div>
      }

      {/* Сообщения */}
      {message.text &&
      <div className="admin-message-banner" style={{
        '--admin-banner-bg': message.type === 'success' ? 'var(--mac-success-bg)' : 'var(--mac-error-bg)',
        '--admin-banner-color': message.type === 'success' ? 'var(--mac-success)' : 'var(--mac-error)',
        '--admin-banner-border': message.type === 'success' ? 'var(--mac-success-border)' : 'var(--mac-error-border)'
      } as CSSProperties}>
          {message.type === 'success' ?
        <CheckCircle className="w-5 h-5 mr-2" /> :

        <AlertCircle className="w-5 h-5 mr-2" />
        }
          {message.text}
        </div>
      }

      {/* Статистика */}
      <div className="admin-grid-auto-200">
        <MacOSCard className="admin-card-p-24-center">
          <div className="admin-stat-num-2xl-bold-dynamic-mb-8 admin-stat-blue">
            {Number(stats.total_activations ?? 0)}
          </div>
          <div className="admin-stat-label-sm-secondary-block-activation">
            {t('admin2.act_stat_total')}
          </div>
        </MacOSCard>
        <MacOSCard className="admin-card-p-24-center">
          <div className="admin-stat-num-2xl-bold-dynamic-mb-8 admin-stat-success">
            {Number(stats.active_activations ?? 0)}
          </div>
          <div className="admin-stat-label-sm-secondary-block-activation">
            {t('admin2.act_stat_active')}
          </div>
        </MacOSCard>
        <MacOSCard className="admin-card-p-24-center">
          <div className="admin-stat-num-2xl-bold-dynamic-mb-8 admin-stat-warning">
            {Number(stats.trial_activations ?? 0)}
          </div>
          <div className="admin-stat-label-sm-secondary-block-activation">
            {t('admin2.act_stat_trial')}
          </div>
        </MacOSCard>
        <MacOSCard className="admin-card-p-24-center">
          <div className="admin-stat-num-2xl-bold-dynamic-mb-8 admin-stat-error">
            {Number(stats.expired_activations ?? 0)}
          </div>
          <div className="admin-stat-label-sm-secondary-block-activation">
            {t('admin2.act_stat_expired')}
          </div>
        </MacOSCard>
      </div>

      {/* Фильтры */}
      <MacOSCard className="p-6">
        <div className="admin-grid-auto-300">
          <div>
            <label className="admin-label-block-sm-med-primary-mb-8">
              <Search className="admin-icon-16-inline-mr-4" />
              {t('admin2.act_search_label')}
            </label>
            <Input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder={t('admin2.act_search_placeholder')}
              className="w-full" />
          </div>

          <div>
            <label className="admin-label-block-sm-med-primary-mb-8">
              <Filter className="admin-icon-16-inline-mr-4" />
              {t('admin2.act_status_label')}
            </label>
            <Select
              value={statusFilter}
              onChange={(value: unknown) => setStatusFilter(String(value))}
              options={[
              { value: 'all', label: t('admin2.act_filter_all') },
              { value: 'issued', label: t('admin2.act_filter_issued') },
              { value: 'active', label: t('admin2.act_filter_active') },
              { value: 'trial', label: t('admin2.act_filter_trial') },
              { value: 'expired', label: t('admin2.act_filter_expired') },
              { value: 'revoked', label: t('admin2.act_filter_revoked') }]
              }
              size="large"
              className="w-full" />
          </div>
        </div>
      </MacOSCard>

      {/* Таблица активаций */}
      <MacOSCard className="admin-card-p-0-overflow-hidden">
        <div className="p-4">
          <Table
            columns={[
            {
              key: 'key',
              title: t('admin2.col_activation_key'),
              render: (activation: Activation) =>
              <div className="flex items-center justify-center">
                    <Key className="admin-icon-16-mr-8-blue" />
                    <div>
                      <div className="admin-key-field">
                        {(activation || {}).key?.slice(0, 8)}...{(activation || {}).key?.slice(-4)}
                      </div>
                      <Button
                    size="small"
                    variant="ghost"
                    onClick={() => copyToClipboard((activation || {}).key)}
                    className="admin-btn-ghost-xs-mt-4">
                        <Copy className="admin-icon-12-mr-4" />
                        {t('admin2.act_copy_btn')}
                      </Button>
                    </div>
                  </div>

            },
            {
              key: 'device',
              title: t('admin2.col_device'),
              render: (activation: Activation) =>
              <div className="flex items-center justify-center">
                    <Smartphone className="admin-icon-16-mr-8-tertiary" />
                    <div>
                      <div className="admin-device-title">
                        {(activation || {}).machine_hash ? `${(activation || {}).machine_hash.slice(0, 12)}...` : t('admin2.act_not_linked')}
                      </div>
                      <div className="admin-device-sub">
                        {parseMeta((activation || {}).meta).description || parseMeta((activation || {}).meta).key_type || t('admin2.act_no_description')}
                      </div>
                    </div>
                  </div>

            },
            {
              key: 'status',
              title: t('admin2.col_active'),
              render: (activation: Activation) => {
                const row = activation || {};
                const status = statusLabels[row.status] || { label: row.status, color: 'secondary' };
                return <Badge variant={status.color}>{status.label}</Badge>;
              }
            },
            {
              key: 'expiry',
              title: t('admin2.col_expiry'),
              render: (activation: Activation) => {
                const row = activation || {};
                const isExpired = row.expiry_date ? new Date(row.expiry_date) < new Date() : false;
                return (
                  <div>
                      <div className="admin-expiry-date">
                        {row.expiry_date ? new Date(row.expiry_date).toLocaleDateString('ru-RU') : '—'}
                      </div>
                      {isExpired &&
                    <div className="admin-expiry-expired">
                          {t('admin2.act_expired_ago', { days: Math.floor((new Date().getTime() - new Date(row.expiry_date).getTime()) / (1000 * 60 * 60 * 24)) })}
                        </div>
                    }
                    </div>);

              }
            },
            {
              key: 'created',
              title: t('admin2.col_created'),
              render: (activation: Activation) =>
              <div className="admin-created-date">
                    {(activation || {}).created_at ? new Date(String((activation || {}).created_at)).toLocaleDateString('ru-RU') : '—'}
                  </div>

            },
            {
              key: 'actions',
              title: t('admin2.col_actions'),
              render: (_actionValue, activation) =>
              <div className="admin-form-row-gap-8">
                    <Button
                  size="small"
                  variant="outline"
                  onClick={() => extendActivation((activation || {}).key)}
                  disabled={(activation || {}).status === 'revoked'}
                  type="button"
                  title={t('admin2.act_extend_title')}
                  aria-label={t('admin2.act_extend_aria', { key: (activation || {}).key || '' }).trim()}>
                  
                      <Calendar aria-hidden="true" className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                  size="small"
                  variant="outline"
                  onClick={() => revokeActivation((activation || {}).key)}
                  disabled={(activation || {}).status === 'revoked'}
                  type="button"
                  title={t('admin2.act_revoke_title')}
                  aria-label={t('admin2.act_revoke_aria', { key: (activation || {}).key || '' }).trim()}>
                  
                      <Shield aria-hidden="true" className="w-3.5 h-3.5" />
                    </Button>
                  </div>

            }]
            }
            data={filteredActivations}
            emptyState={
            <div className="admin-empty-p-48-24-center-secondary">
                <Key className="admin-icon-48-mb-16-mx-auto-tertiary" />
                <h3 className="admin-empty-h3-lg-med-primary-mb-8">
                  {t('admin2.act_empty_title')}
                </h3>
                <p className="admin-empty-p-sm-secondary">
                  {searchTerm || statusFilter !== 'all' ?
                t('admin2.act_empty_desc_filtered') :
                t('admin2.act_empty_desc_initial')
                }
                </p>
              </div>
            } />
          
        </div>
      </MacOSCard>

      {/* Форма создания ключа */}
      {showCreateForm &&
      <ActivationKeyForm
        onSave={generateActivationKey}
        onCancel={() => setShowCreateForm(false)} />

      }

      {/* Информация */}
      <MacOSCard className="admin-card-info-bg">
        <h3 className="admin-shield-h3-info">
          <Shield className="w-5 h-5 mr-2" />
          {t('admin2.act_info_title')}
        </h3>
        <div className="admin-info-list-secondary">
          <p className="admin-p-list-item-m0">{t('admin2.act_info_1')}</p>
          <p className="admin-p-list-item-m0">{t('admin2.act_info_2')}</p>
          <p className="admin-p-list-item-m0">{t('admin2.act_info_3')}</p>
          <p className="admin-p-list-item-m0">{t('admin2.act_info_4')}</p>
          <p className="admin-p-list-item-m0">{t('admin2.act_info_5')}</p>
        </div>
      </MacOSCard>
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog as unknown as React.ReactNode}

      {/* UX Audit: Extend activation dialog (replaces window.prompt). */}
      <ModernDialog
        isOpen={!!extendDialog}
        onClose={() => setExtendDialog(null)}
        title={t('admin2.act_extend_title')}
        actions={[
          { label: t('admin2.cancel'), variant: 'secondary', onClick: () => setExtendDialog(null) },
          { label: t('admin2.act_extend_btn'), variant: 'primary', onClick: submitExtendActivation },
        ]}>
        <div className="admin-extend-dialog-body">
          <label htmlFor="extend-days-input" className="admin-extend-dialog-label">
            {t('admin2.act_extend_dialog_label')}
          </label>
          <Input
            id="extend-days-input"
            type="number"
            min="1"
            value={extendDialog?.days || ''}
            onChange={handleExtendDaysChange}
            aria-label={t('admin2.act_extend_days_aria')}
            autoFocus
          />
          {extendDialog?.error && (
            <p className="admin-extend-dialog-error">
              {extendDialog.error}
            </p>
          )}
        </div>
      </ModernDialog>
    </div>);

};

// Компонент формы создания ключа
const ActivationKeyForm = ({ onSave, onCancel }) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleFeatureChange = (feature, enabled) => {
    setFormData((prev) => ({
      ...prev,
      features: { ...prev.features, [feature]: enabled }
    }));
  };

  return (
    <MacOSCard className="p-6">
      <h3 className="admin-h3-lg-med-primary-mb-16">
        {t('admin2.act_form_title')}
      </h3>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="admin-grid-auto-250">
          <div>
            <label className="admin-label-block-sm-med-primary-mb-8">
              {t('admin2.act_form_type_label')}
            </label>
            <Select
              value={formData.key_type}
              onChange={(value) => handleChange('key_type', value)}
              options={[
              { value: 'trial', label: t('admin2.act_form_type_trial') },
              { value: 'full', label: t('admin2.act_form_type_full') },
              { value: 'enterprise', label: t('admin2.act_form_type_enterprise') }]
              }
              size="large"
              className="w-full" />
          </div>

          <div>
            <label className="admin-label-block-sm-med-primary-mb-8">
              {t('admin2.act_form_duration_label')}
            </label>
            <Input
              type="number"
              min="1"
              max="3650"
              value={formData.duration_days}
              onChange={(e) => handleChange('duration_days', parseInt(e.target.value))}
              className="w-full" />
          </div>

          <div>
            <label className="admin-label-block-sm-med-primary-mb-8">
              {t('admin2.act_form_max_devices_label')}
            </label>
            <Input
              type="number"
              min="1"
              max="100"
              value={formData.max_devices}
              onChange={(e) => handleChange('max_devices', parseInt(e.target.value))}
              className="w-full" />
          </div>

          <div>
            <label className="admin-label-block-sm-med-primary-mb-8">
              {t('admin2.act_form_description_label')}
            </label>
            <Input
              type="text"
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              placeholder={t('admin2.act_form_description_ph')}
              className="w-full" />
          </div>
        </div>

        {/* Функции */}
        <div>
          <label className="admin-label-block-sm-med-primary-mb-12">
            {t('admin2.act_form_features_label')}
          </label>
          <div className="admin-grid-auto-200-12">
            <label className="admin-label-flex-center-activation">
              <Checkbox
                checked={formData.features.full_access}
                onChange={(checked: boolean) => handleFeatureChange('full_access', checked)}
                className="mr-2" />
              <span className="admin-span-sm-primary">{t('admin2.act_form_feature_full_access')}</span>
            </label>

            <label className="admin-label-flex-center-activation">
              <Checkbox
                checked={formData.features.ai_features}
                onChange={(checked: boolean) => handleFeatureChange('ai_features', checked)}
                className="mr-2" />
              <span className="admin-span-sm-primary">{t('admin2.act_form_feature_ai')}</span>
            </label>

            <label className="admin-label-flex-center-activation">
              <Checkbox
                checked={formData.features.telegram_integration}
                onChange={(checked: boolean) => handleFeatureChange('telegram_integration', checked)}
                className="mr-2" />
              <span className="admin-span-sm-primary">{t('admin2.act_form_feature_telegram')}</span>
            </label>

            <label className="admin-label-flex-center-activation">
              <Checkbox
                checked={formData.features.print_system}
                onChange={(checked: boolean) => handleFeatureChange('print_system', checked)}
                className="mr-2" />
              <span className="admin-span-sm-primary">{t('admin2.act_form_feature_print')}</span>
            </label>
          </div>
        </div>

        <div className="admin-flex-end-12">
          <Button type="button" variant="outline" onClick={onCancel}>
            {t('admin2.act_form_cancel')}
          </Button>
          <Button type="submit">
            <Key className="w-4 h-4 mr-2" />
            {t('admin2.act_create_key')}
          </Button>
        </div>
      </form>
    </MacOSCard>);

};

ActivationKeyForm.propTypes = {
  onSave: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired
};

export default ActivationSystem;
