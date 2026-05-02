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
import { Card, Button, Badge, MacOSInput, MacOSSelect, MacOSTable, MacOSCheckbox } from '../ui/macos';

import logger from '../../utils/logger';
import api from '../../api/client';

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
  const [loading, setLoading] = useState(true);
  const [activations, setActivations] = useState([]);
  const [stats, setStats] = useState({});
  const [serverStatus, setServerStatus] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

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
      setMessage({ type: 'error', text: 'Ошибка загрузки данных активации' });
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
    if (!confirm('Отозвать активацию? Устройство будет заблокировано.')) return;

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

  if (loading) {
    return (
      <Card style={{ padding: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <RefreshCw style={{
            width: '20px',
            height: '20px',
            marginRight: '8px',
            animation: 'spin 1s linear infinite'
          }} />
          <span style={{ color: 'var(--mac-text-primary)' }}>Загрузка системы активации...</span>
        </div>
      </Card>);

  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Заголовок */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{
            fontSize: 'var(--mac-font-size-2xl)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            margin: 0,
            marginBottom: '4px'
          }}>
            Система активации
          </h2>
          <p style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-secondary)',
            margin: 0
          }}>
            Управление лицензиями и активированными устройствами
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Обновить
          </Button>
          <Button onClick={() => setShowCreateForm(true)}>
            <Plus style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Создать ключ
          </Button>
        </div>
      </div>

      {serverStatus &&
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        padding: '12px 16px',
        borderRadius: 'var(--mac-radius-md)',
        backgroundColor: serverStatus.ok ? 'var(--mac-success-bg)' : 'var(--mac-warning-bg)',
        color: serverStatus.ok ? 'var(--mac-success)' : 'var(--mac-warning)',
        border: `1px solid ${serverStatus.ok ? 'var(--mac-success-border)' : 'var(--mac-warning-border)'}`
      }}>
          <Badge variant={serverStatus.ok ? 'success' : 'warning'}>
            {serverStatus.ok ? 'Сервер активирован' : 'Сервер не активирован'}
          </Badge>
          <span style={{ fontSize: 'var(--mac-font-size-sm)' }}>
            {serverStatus.ok ?
            `Ключ ${serverStatus.key || 'не указан'}` :
            (serverStatus.reason || 'Статус активации требует проверки')}
          </span>
        </div>
      }

      {/* Сообщения */}
      {message.text &&
      <div style={{
        display: 'flex',
        alignItems: 'center',
        padding: '16px',
        borderRadius: 'var(--mac-radius-md)',
        backgroundColor: message.type === 'success' ?
        'var(--mac-success-bg)' :
        'var(--mac-error-bg)',
        color: message.type === 'success' ?
        'var(--mac-success)' :
        'var(--mac-error)',
        border: `1px solid ${message.type === 'success' ?
        'var(--mac-success-border)' :
        'var(--mac-error-border)'}`
      }}>
          {message.type === 'success' ?
        <CheckCircle style={{ width: '20px', height: '20px', marginRight: '8px' }} /> :

        <AlertCircle style={{ width: '20px', height: '20px', marginRight: '8px' }} />
        }
          {message.text}
        </div>
      }

      {/* Статистика */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        <Card style={{ padding: '24px', textAlign: 'center' }}>
          <div style={{
            fontSize: 'var(--mac-font-size-2xl)',
            fontWeight: 'var(--mac-font-weight-bold)',
            color: 'var(--mac-accent-blue)',
            marginBottom: '8px'
          }}>
            {stats.total_activations || 0}
          </div>
          <div style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-secondary)'
          }}>
            Всего активаций
          </div>
        </Card>
        <Card style={{ padding: '24px', textAlign: 'center' }}>
          <div style={{
            fontSize: 'var(--mac-font-size-2xl)',
            fontWeight: 'var(--mac-font-weight-bold)',
            color: 'var(--mac-success)',
            marginBottom: '8px'
          }}>
            {stats.active_activations || 0}
          </div>
          <div style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-secondary)'
          }}>
            Активных
          </div>
        </Card>
        <Card style={{ padding: '24px', textAlign: 'center' }}>
          <div style={{
            fontSize: 'var(--mac-font-size-2xl)',
            fontWeight: 'var(--mac-font-weight-bold)',
            color: 'var(--mac-warning)',
            marginBottom: '8px'
          }}>
            {stats.trial_activations || 0}
          </div>
          <div style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-secondary)'
          }}>
            Пробных
          </div>
        </Card>
        <Card style={{ padding: '24px', textAlign: 'center' }}>
          <div style={{
            fontSize: 'var(--mac-font-size-2xl)',
            fontWeight: 'var(--mac-font-weight-bold)',
            color: 'var(--mac-error)',
            marginBottom: '8px'
          }}>
            {stats.expired_activations || 0}
          </div>
          <div style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-secondary)'
          }}>
            Истекших
          </div>
        </Card>
      </div>

      {/* Фильтры */}
      <Card style={{ padding: '24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>
              <Search style={{ width: '16px', height: '16px', display: 'inline', marginRight: '4px' }} />
              Поиск
            </label>
            <MacOSInput
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Ключ или ID устройства..."
              style={{ width: '100%' }} />
            
          </div>

          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>
              <Filter style={{ width: '16px', height: '16px', display: 'inline', marginRight: '4px' }} />
              Статус
            </label>
            <MacOSSelect
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              options={[
              { value: 'all', label: 'Все статусы' },
              { value: 'issued', label: 'Созданные' },
              { value: 'active', label: 'Активные' },
              { value: 'trial', label: 'Пробные' },
              { value: 'expired', label: 'Истекшие' },
              { value: 'revoked', label: 'Отозванные' }]
              }
              style={{ width: '100%' }} />
            
          </div>
        </div>
      </Card>

      {/* Таблица активаций */}
      <Card style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{ padding: '16px' }}>
          <MacOSTable
            columns={[
            {
              key: 'key',
              title: 'Ключ активации',
              render: (activation) =>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                    <Key style={{ width: '16px', height: '16px', marginRight: '8px', color: 'var(--mac-accent-blue)' }} />
                    <div>
                      <div style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    fontFamily: 'monospace',
                    color: 'var(--mac-text-primary)'
                  }}>
                        {(activation || {}).key?.slice(0, 8)}...{(activation || {}).key?.slice(-4)}
                      </div>
                      <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => copyToClipboard((activation || {}).key)}
                    style={{ fontSize: 'var(--mac-font-size-xs)', marginTop: '4px' }}>
                    
                        <Copy style={{ width: '12px', height: '12px', marginRight: '4px' }} />
                        Копировать
                      </Button>
                    </div>
                  </div>

            },
            {
              key: 'device',
              title: 'Устройство',
              render: (activation) =>
              <div style={{ display: 'flex', alignItems: 'center' }}>
                    <Smartphone style={{ width: '16px', height: '16px', marginRight: '8px', color: 'var(--mac-text-tertiary)' }} />
                    <div>
                      <div style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)'
                  }}>
                        {(activation || {}).machine_hash ? `${(activation || {}).machine_hash.slice(0, 12)}...` : 'Не привязано'}
                      </div>
                      <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
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
                      <div style={{
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-primary)'
                    }}>
                        {row.expiry_date ? new Date(row.expiry_date).toLocaleDateString('ru-RU') : '—'}
                      </div>
                      {isExpired &&
                    <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-error)' }}>
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
              <div style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-primary)'
              }}>
                    {(activation || {}).created_at ? new Date((activation || {}).created_at).toLocaleDateString('ru-RU') : '—'}
                  </div>

            },
            {
              key: 'actions',
              title: 'Действия',
              render: (activation) =>
              <div style={{ display: 'flex', gap: '8px' }}>
                    <Button
                  size="sm"
                  variant="outline"
                  onClick={() => extendActivation((activation || {}).key)}
                  disabled={(activation || {}).status === 'revoked'}>
                  
                      <Calendar style={{ width: '14px', height: '14px' }} />
                    </Button>
                    <Button
                  size="sm"
                  variant="outline"
                  onClick={() => revokeActivation((activation || {}).key)}
                  disabled={(activation || {}).status === 'revoked'}>
                  
                      <Shield style={{ width: '14px', height: '14px' }} />
                    </Button>
                  </div>

            }]
            }
            data={filteredActivations}
            emptyState={
            <div style={{
              textAlign: 'center',
              padding: '48px 24px',
              color: 'var(--mac-text-secondary)'
            }}>
                <Key style={{ width: '48px', height: '48px', color: 'var(--mac-text-tertiary)', margin: '0 auto 16px' }} />
                <h3 style={{
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)',
                margin: '0 0 8px 0'
              }}>
                  Активации не найдены
                </h3>
                <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)',
                margin: 0
              }}>
                  {searchTerm || statusFilter !== 'all' ?
                'Попробуйте изменить критерии поиска' :
                'Создайте первый ключ активации'
                }
                </p>
              </div>
            } />
          
        </div>
      </Card>

      {/* Форма создания ключа */}
      {showCreateForm &&
      <ActivationKeyForm
        onSave={generateActivationKey}
        onCancel={() => setShowCreateForm(false)} />

      }

      {/* Информация */}
      <Card style={{
        padding: '24px',
        backgroundColor: 'var(--mac-info-bg)',
        border: '1px solid var(--mac-info-border)'
      }}>
        <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)',
          marginBottom: '8px',
          display: 'flex',
          alignItems: 'center',
          color: 'var(--mac-info)'
        }}>
          <Shield style={{ width: '20px', height: '20px', marginRight: '8px' }} />
          Как работает система активации
        </h3>
        <div style={{
          fontSize: 'var(--mac-font-size-sm)',
          color: 'var(--mac-text-secondary)',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px'
        }}>
          <p style={{ margin: 0 }}>• Каждое устройство требует уникальный ключ активации</p>
          <p style={{ margin: 0 }}>• Ключи имеют срок действия и могут быть отозваны</p>
          <p style={{ margin: 0 }}>• Пробные лицензии ограничены по функциональности</p>
          <p style={{ margin: 0 }}>• Система работает офлайн после успешной активации</p>
          <p style={{ margin: 0 }}>• Все активации логируются для аудита</p>
        </div>
      </Card>
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
    <Card style={{ padding: '24px' }}>
      <h3 style={{
        fontSize: 'var(--mac-font-size-lg)',
        fontWeight: 'var(--mac-font-weight-medium)',
        marginBottom: '16px',
        color: 'var(--mac-text-primary)',
        margin: 0
      }}>
        Создание ключа активации
      </h3>

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>
              Тип лицензии
            </label>
            <MacOSSelect
              value={formData.key_type}
              onChange={(e) => handleChange('key_type', e.target.value)}
              options={[
              { value: 'trial', label: 'Пробная (30 дней)' },
              { value: 'full', label: 'Полная лицензия' },
              { value: 'enterprise', label: 'Корпоративная' }]
              }
              style={{ width: '100%' }} />
            
          </div>

          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>
              Срок действия (дни)
            </label>
            <MacOSInput
              type="number"
              min="1"
              max="3650"
              value={formData.duration_days}
              onChange={(e) => handleChange('duration_days', parseInt(e.target.value))}
              style={{ width: '100%' }} />
            
          </div>

          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>
              Максимум устройств
            </label>
            <MacOSInput
              type="number"
              min="1"
              max="100"
              value={formData.max_devices}
              onChange={(e) => handleChange('max_devices', parseInt(e.target.value))}
              style={{ width: '100%' }} />
            
          </div>

          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: '8px'
            }}>
              Описание
            </label>
            <MacOSInput
              type="text"
              value={formData.description}
              onChange={(e) => handleChange('description', e.target.value)}
              placeholder="Клиника №1, основная лицензия"
              style={{ width: '100%' }} />
            
          </div>
        </div>

        {/* Функции */}
        <div>
          <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: '12px'
          }}>
            Включенные функции:
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
            <label style={{ display: 'flex', alignItems: 'center' }}>
              <MacOSCheckbox
                checked={formData.features.full_access}
                onChange={(e) => handleFeatureChange('full_access', e.target.checked)}
                style={{ marginRight: '8px' }} />
              
              <span style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-primary)' }}>Полный доступ</span>
            </label>

            <label style={{ display: 'flex', alignItems: 'center' }}>
              <MacOSCheckbox
                checked={formData.features.ai_features}
                onChange={(e) => handleFeatureChange('ai_features', e.target.checked)}
                style={{ marginRight: '8px' }} />
              
              <span style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-primary)' }}>AI функции</span>
            </label>

            <label style={{ display: 'flex', alignItems: 'center' }}>
              <MacOSCheckbox
                checked={formData.features.telegram_integration}
                onChange={(e) => handleFeatureChange('telegram_integration', e.target.checked)}
                style={{ marginRight: '8px' }} />
              
              <span style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-primary)' }}>Telegram интеграция</span>
            </label>

            <label style={{ display: 'flex', alignItems: 'center' }}>
              <MacOSCheckbox
                checked={formData.features.print_system}
                onChange={(e) => handleFeatureChange('print_system', e.target.checked)}
                style={{ marginRight: '8px' }} />
              
              <span style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-primary)' }}>Система печати</span>
            </label>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <Button type="button" variant="outline" onClick={onCancel}>
            Отменить
          </Button>
          <Button type="submit">
            <Key style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Создать ключ
          </Button>
        </div>
      </form>
    </Card>);

};

ActivationKeyForm.propTypes = {
  onSave: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired
};

export default ActivationSystem;
