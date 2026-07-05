import { useCallback, useEffect, useState } from 'react';
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
  // P-013 fix: shared ConfirmDialog hook (replaces 1 native confirm() call).
  const [confirm, confirmDialog] = useConfirm();
  const [loading, setLoading] = useState(true);
  const [activations, setActivations] = useState([]);
  const [stats, setStats] = useState({});
  const [serverStatus, setServerStatus] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [loadError, setLoadError] = useState('');

  // Статусы активации
  const statusLabels = {
    issued: { label: 'Создана', color: 'info' },
    active: { label: 'Активна', color: 'success' },
    expired: { label: 'Истекла', color: 'warning' },
    revoked: { label: 'Отозвана', color: 'error' },
    trial: { label: 'Пробная', color: 'info' }
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
      const errorText = 'Ошибка загрузки данных активации';
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

      const response = await api.post('/activation/issue', payload);
      const result = response.data || {};
      setMessage({ type: 'success', text: 'Ключ активации создан' });
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
      title: 'Отзыв активации',
      message: 'Отозвать активацию?',
      description: 'Устройство будет заблокировано.',
      confirmLabel: 'Отозвать',
      cancelLabel: 'Отмена',
      intent: 'warning',
    });
    if (!ok) return;

    try {
      await api.post('/activation/revoke', { key: activationKey });
      setMessage({ type: 'success', text: 'Активация отозвана' });
      await loadData();
    } catch (error) {
      logger.error('Ошибка отзыва:', error);
      setMessage({ type: 'error', text: 'Ошибка отзыва активации' });
    }
  };

  const extendActivation = async (activationKey) => {
    const rawDays = window.prompt('На сколько дней продлить ключ?', '30');
    if (!rawDays) return;
    const days = Number.parseInt(rawDays, 10);
    if (!Number.isFinite(days) || days <= 0) {
      setMessage({ type: 'error', text: 'Введите корректное число дней' });
      return;
    }

    try {
      await api.post('/activation/extend', { key: activationKey, days });
      setMessage({ type: 'success', text: 'Активация продлена' });
      await loadData();
    } catch (error) {
      logger.error('Ошибка продления:', error);
      setMessage({ type: 'error', text: 'Ошибка продления активации' });
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setMessage({ type: 'success', text: 'Скопировано в буфер обмена' });
  };

  const filteredActivations = activations.filter((activation) => {
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
          title="Загрузка системы активации"
          description="Получаем список ключей и статус сервера."
          size="sm"
        />
      </MacOSCard>);

  }

  if (showInitialLoadError) {
    return (
      <MacOSCard className="admin-card-p-32">
        <AppError
          title="Не удалось загрузить систему активации"
          description={loadError}
          action={
            <Button type="button" variant="outline" onClick={loadData} disabled={loading} loading={loading}>
              Повторить
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
            Система активации
          </h2>
          <p className="admin-p-sm-secondary-m0">
            Управление лицензиями и активированными устройствами
          </p>
        </div>

        <div className="admin-form-row-gap-12">
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Обновить
          </Button>
          <Button onClick={() => setShowCreateForm(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Создать ключ
          </Button>
        </div>
      </div>

      {serverStatus &&
      <div className="admin-status-banner" style={{
        '--admin-banner-bg': serverStatus.ok ? 'var(--mac-success-bg)' : 'var(--mac-warning-bg)',
        '--admin-banner-color': serverStatus.ok ? 'var(--mac-success)' : 'var(--mac-warning)',
        '--admin-banner-border': serverStatus.ok ? 'var(--mac-success-border)' : 'var(--mac-warning-border)'
      }}>
          <Badge variant={serverStatus.ok ? 'success' : 'warning'}>
            {serverStatus.ok ? 'Сервер активирован' : 'Сервер не активирован'}
          </Badge>
          <span className="text-sm">
            {serverStatus.ok ?
            `Ключ ${serverStatus.key || 'не указан'}` :
            (serverStatus.reason || 'Статус активации требует проверки')}
          </span>
        </div>
      }

      {/* Сообщения */}
      {message.text &&
      <div className="admin-message-banner" style={{
        '--admin-banner-bg': message.type === 'success' ? 'var(--mac-success-bg)' : 'var(--mac-error-bg)',
        '--admin-banner-color': message.type === 'success' ? 'var(--mac-success)' : 'var(--mac-error)',
        '--admin-banner-border': message.type === 'success' ? 'var(--mac-success-border)' : 'var(--mac-error-border)'
      }}>
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
          <div className="admin-stat-num-2xl-bold-dynamic-mb-8" style={{ '--admin-stat-color': 'var(--mac-accent-blue)' }}>
            {stats.total_activations || 0}
          </div>
          <div className="admin-stat-label-sm-secondary-block-activation">
            Всего активаций
          </div>
        </MacOSCard>
        <MacOSCard className="admin-card-p-24-center">
          <div className="admin-stat-num-2xl-bold-dynamic-mb-8" style={{ '--admin-stat-color': 'var(--mac-success)' }}>
            {stats.active_activations || 0}
          </div>
          <div className="admin-stat-label-sm-secondary-block-activation">
            Активных
          </div>
        </MacOSCard>
        <MacOSCard className="admin-card-p-24-center">
          <div className="admin-stat-num-2xl-bold-dynamic-mb-8" style={{ '--admin-stat-color': 'var(--mac-warning)' }}>
            {stats.trial_activations || 0}
          </div>
          <div className="admin-stat-label-sm-secondary-block-activation">
            Пробных
          </div>
        </MacOSCard>
        <MacOSCard className="admin-card-p-24-center">
          <div className="admin-stat-num-2xl-bold-dynamic-mb-8" style={{ '--admin-stat-color': 'var(--mac-error)' }}>
            {stats.expired_activations || 0}
          </div>
          <div className="admin-stat-label-sm-secondary-block-activation">
            Истекших
          </div>
        </MacOSCard>
      </div>

      {/* Фильтры */}
      <MacOSCard className="p-6">
        <div className="admin-grid-auto-300">
          <div>
            <label className="admin-label-block-sm-med-primary-mb-8">
              <Search className="admin-icon-16-inline-mr-4" />
              Поиск
            </label>
            <Input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Ключ или ID устройства..."
              className="w-full" />
          </div>

          <div>
            <label className="admin-label-block-sm-med-primary-mb-8">
              <Filter className="admin-icon-16-inline-mr-4" />
              Статус
            </label>
            <Select
              value={statusFilter}
              onChange={(value) => setStatusFilter(value)}
              options={[
              { value: 'all', label: 'Все статусы' },
              { value: 'issued', label: 'Созданные' },
              { value: 'active', label: 'Активные' },
              { value: 'trial', label: 'Пробные' },
              { value: 'expired', label: 'Истекшие' },
              { value: 'revoked', label: 'Отозванные' }]
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
              title: 'Ключ активации',
              render: (activation) =>
              <div className="flex items-center justify-center">
                    <Key className="admin-icon-16-mr-8-blue" />
                    <div>
                      <div className="admin-key-field">
                        {(activation || {}).key?.slice(0, 8)}...{(activation || {}).key?.slice(-4)}
                      </div>
                      <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => copyToClipboard((activation || {}).key)}
                    className="admin-btn-ghost-xs-mt-4">
                        <Copy className="admin-icon-12-mr-4" />
                        Копировать
                      </Button>
                    </div>
                  </div>

            },
            {
              key: 'device',
              title: 'Устройство',
              render: (activation) =>
              <div className="flex items-center justify-center">
                    <Smartphone className="admin-icon-16-mr-8-tertiary" />
                    <div>
                      <div className="admin-device-title">
                        {(activation || {}).machine_hash ? `${(activation || {}).machine_hash.slice(0, 12)}...` : 'Не привязано'}
                      </div>
                      <div className="admin-device-sub">
                        {parseMeta((activation || {}).meta).description || parseMeta((activation || {}).meta).key_type || 'Без описания'}
                      </div>
                    </div>
                  </div>

            },
            {
              key: 'status',
              title: 'Статус',
              render: (activation) => {
                const row = activation || {};
                const status = statusLabels[row.status] || { label: row.status, color: 'secondary' };
                return <Badge variant={status.color}>{status.label}</Badge>;
              }
            },
            {
              key: 'expiry',
              title: 'Срок действия',
              render: (activation) => {
                const row = activation || {};
                const isExpired = row.expiry_date ? new Date(row.expiry_date) < new Date() : false;
                return (
                  <div>
                      <div className="admin-expiry-date">
                        {row.expiry_date ? new Date(row.expiry_date).toLocaleDateString('ru-RU') : '—'}
                      </div>
                      {isExpired &&
                    <div className="admin-expiry-expired">
                          Истек {Math.floor((new Date() - new Date(row.expiry_date)) / (1000 * 60 * 60 * 24))} дн. назад
                        </div>
                    }
                    </div>);

              }
            },
            {
              key: 'created',
              title: 'Создан',
              render: (activation) =>
              <div className="admin-created-date">
                    {(activation || {}).created_at ? new Date((activation || {}).created_at).toLocaleDateString('ru-RU') : '—'}
                  </div>

            },
            {
              key: 'actions',
              title: 'Действия',
              render: (_actionValue, activation) =>
              <div className="admin-form-row-gap-8">
                    <Button
                  size="sm"
                  variant="outline"
                  onClick={() => extendActivation((activation || {}).key)}
                  disabled={(activation || {}).status === 'revoked'}
                  type="button"
                  title="Продлить активацию"
                  aria-label={`Продлить активацию ${(activation || {}).key || ''}`.trim()}>
                  
                      <Calendar aria-hidden="true" className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                  size="sm"
                  variant="outline"
                  onClick={() => revokeActivation((activation || {}).key)}
                  disabled={(activation || {}).status === 'revoked'}
                  type="button"
                  title="Отозвать активацию"
                  aria-label={`Отозвать активацию ${(activation || {}).key || ''}`.trim()}>
                  
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
                  Активации не найдены
                </h3>
                <p className="admin-empty-p-sm-secondary">
                  {searchTerm || statusFilter !== 'all' ?
                'Попробуйте изменить критерии поиска' :
                'Создайте первый ключ активации'
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
          Как работает система активации
        </h3>
        <div className="admin-info-list-secondary">
          <p className="admin-p-list-item-m0">• Каждое устройство требует уникальный ключ активации</p>
          <p className="admin-p-list-item-m0">• Ключи имеют срок действия и могут быть отозваны</p>
          <p className="admin-p-list-item-m0">• Пробные лицензии ограничены по функциональности</p>
          <p className="admin-p-list-item-m0">• Система работает офлайн после успешной активации</p>
          <p className="admin-p-list-item-m0">• Все активации логируются для аудита</p>
        </div>
      </MacOSCard>
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </div>);

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
        Создание ключа активации
      </h3>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div className="admin-grid-auto-250">
          <div>
            <label className="admin-label-block-sm-med-primary-mb-8">
              Тип лицензии
            </label>
            <Select
              value={formData.key_type}
              onChange={(value) => handleChange('key_type', value)}
              options={[
              { value: 'trial', label: 'Пробная (30 дней)' },
              { value: 'full', label: 'Полная лицензия' },
              { value: 'enterprise', label: 'Корпоративная' }]
              }
              size="large"
              className="w-full" />
          </div>

          <div>
            <label className="admin-label-block-sm-med-primary-mb-8">
              Срок действия (дни)
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
              Максимум устройств
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
              Описание
            </label>
            <Input
              type="text"
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              placeholder="Клиника №1, основная лицензия"
              className="w-full" />
          </div>
        </div>

        {/* Функции */}
        <div>
          <label className="admin-label-block-sm-med-primary-mb-12">
            Включенные функции:
          </label>
          <div className="admin-grid-auto-200-12">
            <label className="admin-label-flex-center-activation">
              <Checkbox
                checked={formData.features.full_access}
                onChange={(e) => handleFeatureChange('full_access', e.target.checked)}
                className="mr-2" />
              <span className="admin-span-sm-primary">Полный доступ</span>
            </label>

            <label className="admin-label-flex-center-activation">
              <Checkbox
                checked={formData.features.ai_features}
                onChange={(e) => handleFeatureChange('ai_features', e.target.checked)}
                className="mr-2" />
              <span className="admin-span-sm-primary">AI функции</span>
            </label>

            <label className="admin-label-flex-center-activation">
              <Checkbox
                checked={formData.features.telegram_integration}
                onChange={(e) => handleFeatureChange('telegram_integration', e.target.checked)}
                className="mr-2" />
              <span className="admin-span-sm-primary">Telegram интеграция</span>
            </label>

            <label className="admin-label-flex-center-activation">
              <Checkbox
                checked={formData.features.print_system}
                onChange={(e) => handleFeatureChange('print_system', e.target.checked)}
                className="mr-2" />
              <span className="admin-span-sm-primary">Система печати</span>
            </label>
          </div>
        </div>

        <div className="admin-flex-end-12">
          <Button type="button" variant="outline" onClick={onCancel}>
            Отменить
          </Button>
          <Button type="submit">
            <Key className="w-4 h-4 mr-2" />
            Создать ключ
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
