import { useTranslation } from '../i18n/useTranslation';
import { useEffect, useMemo, useState } from 'react';
import PropTypes from 'prop-types';
import RoleGate from '../components/RoleGate.jsx';
import { api } from '../api/client.js';
import { useTheme } from '../contexts/ThemeContext';
import TwoFactorManager from '../components/security/TwoFactorManager';
import ColorSchemeSelector from '../components/admin/ColorSchemeSelector.jsx';
import { AccentPicker } from '../components/ui/macos';

import PhoneVerification from '../components/auth/PhoneVerification';

import logger from '../utils/logger';
import NotificationSystemStatus from '../components/settings/NotificationSystemStatus.jsx';
// P-013 fix: shared ConfirmDialog hook replacing native confirm() calls.
import { useConfirm } from '../components/common/ConfirmDialog';
import './SettingsAnalytics.css';
import { Input,
  Checkbox } from '../components/ui/macos';
import { notify } from '../services/notify.js';
function TabButton({ active, onClick, children }) {
  // Используем CSS переменные вместо хардкод стилей
  const st = {
    padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
    borderRadius: 10,
    border: '1px solid var(--border-color)',
    background: active ? 'var(--accent-color)' : 'var(--bg-primary)',
    color: active ? 'white' : 'var(--text-primary)',
    cursor: 'pointer',
    transition: 'all 0.2s ease'
  };
  return (
    <button onClick={onClick} style={st}>{children}</button>);

}

function Row({ k, v, onSave }) {
  const [val, setVal] = useState(String(v ?? ''));
  useEffect(() => setVal(String(v ?? '')), [v]);
  return (
    <div className="settings-row">
      <div className="settings-label-semibold">{k}</div>
      <Input aria-label={`Setting value for ${k}`} value={val} onChange={(e) => setVal(e.target.value)} className="settings-input" />
      <button onClick={() => onSave(k, val)} className="settings-btn">Сохранить</button>
    </div>);

}

/**
 * Settings:
 *  - Вкладка "license": активация сервера и статус (работает даже при REQUIRE_LICENSE=1)
 *  - Вкладка "printer": простые пары key/value (если backend поддерживает PUT /settings)
 *  - Вкладка "online_queue": простые пары key/value
 */
export default function Settings() {void
  useTheme();void
  useState('Settings');
  // P-013 fix: shared ConfirmDialog hook (replaces 1 native confirm() call).
  const [confirm, confirmDialog] = useConfirm();
  const [tab, setTab] = useState('license');

  // license tab
  const [status, setStatus] = useState(null);
  const [key, setKey] = useState('');
  const [busyAct, setBusyAct] = useState(false);
  const [errAct, setErrAct] = useState('');

  // payment providers tab
  const [providers, setProviders] = useState([]);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [showAddProvider, setShowAddProvider] = useState(false);
  const [editingProvider, setEditingProvider] = useState(null);

  async function loadStatus() {
    try {
      const st = await api.get('/activation/status');
      setStatus(st?.data ?? st ?? null);
    } catch {
      setStatus(null);
    }
  }

  async function doActivate() {
    setBusyAct(true);
    setErrAct('');
    try {
      const response = await api.post('/activation/activate', { key });
      const res = response?.data ?? response;
      if (!res?.ok) {
        setErrAct(res?.reason || 'Не удалось активировать');
      }
      await loadStatus();
    } catch (e) {
      setErrAct(e?.data?.detail || e?.message || 'Ошибка активации');
    } finally {
      setBusyAct(false);
    }
  }

  // Payment providers functions
  async function loadProviders() {
    setLoadingProviders(true);
    try {
      const response = await api.get('/admin/providers');
      setProviders(response || []);
    } catch (error) {
      logger.error('Ошибка загрузки провайдеров:', error);
    } finally {
      setLoadingProviders(false);
    }
  }

  async function createProvider(providerData) {
    try {
      await api.post('/admin/providers', providerData);
      await loadProviders();
      setShowAddProvider(false);
    } catch (error) {
      logger.error('Ошибка создания провайдера:', error);
      throw error;
    }
  }

  async function updateProvider(providerId, providerData) {
    try {
      await api.put(`/admin/providers/${providerId}`, providerData);
      await loadProviders();
      setEditingProvider(null);
    } catch (error) {
      logger.error('Ошибка обновления провайдера:', error);
      throw error;
    }
  }

  async function deleteProvider(providerId) {
    // P-013 fix: replaced native confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: 'Удаление провайдера',
      message: 'Удалить этого провайдера?',
      description: 'Это действие необратимо.',
      confirmLabel: t('misc.delete'),
      cancelLabel: t('misc.cancel'),
      intent: 'danger',
    });
    if (!ok) {
      return;
    }
    try {
      await api.delete(`/admin/providers/${providerId}`);
      await loadProviders();
    } catch (error) {
      logger.error('Ошибка удаления провайдера:', error);
    }
  }

  useEffect(() => {if (tab === 'license') loadStatus();}, [tab]);
  useEffect(() => {if (tab === 'payment_providers') loadProviders();}, [tab]);

  // generic category settings (printer / online_queue)
  const [cat, setCat] = useState('printer');
  const [items, setItems] = useState([]);
  const [busyCat, setBusyCat] = useState(false);
  const [errCat, setErrCat] = useState('');

  async function loadCat(category) {
    setBusyCat(true);
    setErrCat('');
    try {
      // Ожидаем форму {items:[{key,value}]} или массив объектов
      const res = await api.get('/settings', { params: { category } });
      const data = res?.data ?? res;
      let arr = [];
      if (Array.isArray(data?.items)) arr = data.items;else
      if (Array.isArray(data)) arr = data;else
      if (data && typeof data === 'object') {
        // возможный словарь
        arr = Object.entries(data).map(([k, v]) => ({ key: k, value: v }));
      }
      setItems(arr.map((x) => ({ key: x.key ?? x.name ?? '', value: x.value ?? '' })));
    } catch (e) {
      setErrCat(e?.data?.detail || e?.message || 'Ошибка загрузки настроек');
      setItems([]);
    } finally {
      setBusyCat(false);
    }
  }

  async function saveKV(category, key, value) {
    try {
      await api.put('/settings', { category, key, value });
      await loadCat(category);
    } catch (e) {
      notify.error(e?.data?.detail || e?.message || 'Ошибка сохранения');
    }
  }

  useEffect(() => {
    if (tab === 'printer' || tab === 'online_queue' || tab === 'display_board') {
      const c = tab === 'printer' ? 'printer' : tab === 'online_queue' ? 'online_queue' : 'display_board';
      setCat(c);
      loadCat(c);
    }

  }, [tab]);

  const licenseOk = !!status?.ok;
  const badge = useMemo(() => {
    const st = status?.status || status?.reason || 'unknown';
    return (
      <span style={{
        padding: '2px 8px', borderRadius: 999,
        background: licenseOk ? 'var(--mac-success-bg)' : 'var(--mac-error-bg)',
        color: licenseOk ? 'var(--mac-success)' : 'var(--mac-error)',
        border: `1px solid ${licenseOk ? 'var(--mac-success-border, color-mix(in srgb, var(--mac-success), transparent 70%))' : 'var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))'}`,
        fontSize: 12,
        whiteSpace: 'nowrap'
      }}>{st}</span>);

  }, [status, licenseOk]);

  return (
    <div>
      <RoleGate roles={['Admin']}>
        <div className="settings-page">
          <h2 className="settings-h2">Настройки</h2>

          <div className="settings-tab-bar">
            <TabButton active={tab === 'license'} onClick={() => setTab('license')}>Лицензия</TabButton>
            <TabButton active={tab === 'printer'} onClick={() => setTab('printer')}>Принтер</TabButton>
            <TabButton active={tab === 'online_queue'} onClick={() => setTab('online_queue')}>Онлайн-очередь</TabButton>
            <TabButton active={tab === 'display_board'} onClick={() => setTab('display_board')}>Табло очереди</TabButton>
            <TabButton active={tab === 'payment_providers'} onClick={() => setTab('payment_providers')}>Провайдеры оплаты</TabButton>
            <TabButton active={tab === 'notifications'} onClick={() => setTab('notifications')}>Уведомления (System)</TabButton>
            <TabButton active={tab === 'appearance'} onClick={() => setTab('appearance')}>Тема и стиль</TabButton>
            <TabButton active={tab === 'security'} onClick={() => setTab('security')}>Безопасность</TabButton>
          </div>

          {tab === 'appearance' &&
          <div className="settings-tab-content">
              <ColorSchemeSelector />

              <div className="settings-card">
                <div className="settings-card-title">Accent color</div>
                <div className="settings-card-body">
                  <AccentPicker />
                  <div className="settings-hint">
                    Акцентный цвет перекрашивает кнопки, focus states, badges и первичные действия. Он сохраняется локально в браузере, отдельно от theme preference.
                  </div>
                </div>
              </div>

              <div className="settings-card">
                <div className="settings-card-title">Как использовать вместе</div>
                <div className="settings-card-body-gap8">
                  <div>1. Сначала выберите theme для фона, sidebar и карточек.</div>
                  <div>2. Потом подберите accent для primary actions и focus состояний.</div>
                  <div className="settings-hint-75">
                    Theme сохраняется в вашем профиле. Accent хранится только в текущем браузере.
                  </div>
                </div>
              </div>
            </div>
          }

          {tab === 'notifications' &&
          <div className="settings-tab-content">
              <div className="settings-card">
                <div className="settings-card-title">Статус системы уведомлений</div>
                <NotificationSystemStatus />
              </div>
            </div>
          }

          {tab === 'license' &&
          <div className="settings-tab-content">
              <div className="settings-card">
                <div className="settings-card-title-mb6">Статус активации</div>
                <div className="settings-info-grid">
                  <div>Состояние: {badge}</div>
                  <div>Ключ: <code>{status?.key || '—'}</code></div>
                  <div>Machine hash: <code>{status?.machine_hash || '—'}</code></div>
                  <div>Действует до: <b>{status?.expiry_date || '—'}</b></div>
                </div>
              </div>

              <div className="settings-card">
                <div className="settings-card-title-mb6">Активация сервера</div>
                {errAct && <div className="settings-error-box">{String(errAct)}</div>}
                <div className="settings-activation-row">
                  <Input
                  placeholder="Вставьте ключ активации"
                  aria-label="Activation key"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  className="settings-input" />
                
                  <button onClick={doActivate} disabled={busyAct || !key.trim()} className="settings-btn-primary">
                    {busyAct ? '...' : 'Активировать'}
                  </button>
                  <button onClick={loadStatus} className="settings-btn">Обновить статус</button>
                </div>
                <div style={{ fontSize: 12, opacity: .7, marginTop: 6 }}>
                  При отсутствии ключа — обратитесь к администратору для выдачи.
                </div>
              </div>
            </div>
          }

          {(tab === 'printer' || tab === 'online_queue' || tab === 'display_board') &&
          <div className="settings-tab-content">
              <div className="settings-card">
                <div className="settings-card-title-mb6">
                  Категория: <code>{cat}</code>
                </div>
                {busyCat && <div style={{ opacity: .7 }}>Загрузка…</div>}
                {errCat && <div className="settings-error-box">{String(errCat)}</div>}
                <div className="settings-role-map-list">
                  {items.map((it) =>
                <Row
                  key={it.key}
                  k={it.key}
                  v={it.value}
                  onSave={(k, v) => saveKV(cat, k, v)} />

                )}
                  {!busyCat && items.length === 0 &&
                <div style={{ opacity: .7 }}>Записей нет</div>
                }
                </div>
              </div>

              {tab === 'display_board' &&
            <>
                  <div className="settings-card">
                    <div className="settings-card-title-mb6">Табло: бренд и объявления</div>
                    <div className="settings-role-map-list">
                      <KVField label="Бренд (brand)" defKey="brand" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label="Логотип (logo URL)" defKey="logo" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label="Объявление RU (announcement_ru)" defKey="announcement_ru" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label="Объявление UZ (announcement_uz)" defKey="announcement_uz" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label="Объявление EN (announcement_en)" defKey="announcement_en" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label="Основной цвет (primary_color)" defKey="primary_color" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label="Цвет фона (bg_color)" defKey="bg_color" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label="Цвет текста (text_color)" defKey="text_color" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label="Контраст по умолчанию (contrast_default=true/false)" defKey="contrast_default" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label="Киоск по умолчанию (kiosk_default=true/false)" defKey="kiosk_default" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label="Звук по умолчанию (sound_default=true/false)" defKey="sound_default" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                    </div>
                  </div>

                  <div className="settings-card">
                    <div className="settings-card-title-mb6">Табло: мэппинг Роль → Отделение</div>
                    <RoleMapEditor items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                  </div>
                </>
            }

              {tab === 'payment_providers' &&
            <div className="settings-tab-content">
                  <div className="settings-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <div className="settings-label-semibold">Провайдеры оплаты</div>
                      <button
                    onClick={() => setShowAddProvider(true)}
                    style={{
                      padding: 'var(--mac-spacing-2) var(--mac-spacing-4)',
                      background: 'var(--accent-color)',
                      color: 'white',
                      border: 'none',
                      borderRadius: 6,
                      cursor: 'pointer'
                    }}>
                    
                        + Добавить провайдера
                      </button>
                    </div>

                    {loadingProviders ?
                <div style={{ opacity: 0.7 }}>Загрузка...</div> :

                <div className="settings-role-map-list">
                        {providers.map((provider) =>
                  <ProviderCard
                    key={provider.id}
                    provider={provider}
                    onEdit={() => setEditingProvider(provider)}
                    onDelete={() => deleteProvider(provider.id)} />

                  )}
                        {providers.length === 0 &&
                  <div style={{ opacity: 0.7 }}>Провайдеры не найдены</div>
                  }
                      </div>
                }
                  </div>
                </div>
            }

              {showAddProvider &&
            <ProviderModal
              onClose={() => setShowAddProvider(false)}
              onSave={createProvider}
              title="Добавить провайдера" />

            }

              {editingProvider &&
            <ProviderModal
              provider={editingProvider}
              onClose={() => setEditingProvider(null)}
              onSave={(data) => updateProvider(editingProvider.id, data)}
              title="Редактировать провайдера" />

            }
            </div>
          }

          {tab === 'security' &&
          <div className="settings-tab-content">
              <div className="settings-card">
                <div className="settings-card-title">Двухфакторная аутентификация (2FA)</div>
                <TwoFactorManager />
              </div>

              <div className="settings-card">
                <div className="settings-card-title">Верификация телефона</div>
                <PhoneVerification
                showPhoneInput={true}
                title="Верификация телефона"
                onVerified={() => notify.success('Телефон успешно подтверждён!')} />

              </div>
            </div>
          }
        </div>
      </RoleGate>
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </div>);

}

// Компонент карточки провайдера
function ProviderCard({ provider, onEdit, onDelete }) {
  return (
    <div style={{
      border: '1px solid var(--border-color)',
      borderRadius: 8,
      padding: 12,
      display: 'grid',
      gap: 8
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div className="settings-label-semibold">{provider.name}</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={onEdit}
            style={{
              padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
              background: 'var(--accent-color)',
              color: 'white',
              border: 'none',
              borderRadius: 4,
              cursor: 'pointer',
              fontSize: 'var(--mac-font-size-xs)'
            }}>
            
            Редактировать
          </button>
          <button
            onClick={onDelete}
            style={{
              padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
              background: 'var(--mac-error)',
              color: 'white',
              border: 'none',
              borderRadius: 4,
              cursor: 'pointer',
              fontSize: 'var(--mac-font-size-xs)'
            }}>
            
            Удалить
          </button>
        </div>
      </div>
      <div style={{ fontSize: 'var(--mac-font-size-base)', opacity: 0.8 }}>
        <div>Код: {provider.code}</div>
        <div>Активен: {provider.is_active ? 'Да' : 'Нет'}</div>
        {provider.description && <div>Описание: {provider.description}</div>}
      </div>
    </div>);

}

// Модальное окно для добавления/редактирования провайдера
function ProviderModal({ provider, onClose, onSave, title }) {
  const [formData, setFormData] = useState({
    name: provider?.name || '',
    code: provider?.code || '',
    description: provider?.description || '',
    is_active: provider?.is_active ?? true,
    secret_key: provider?.secret_key || '',
    webhook_url: provider?.webhook_url || '',
    api_url: provider?.api_url || ''
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await onSave(formData);
    } catch (error) {
      notify.error(t('misc.operation_error') + ' сохранения: ' + (error.message || 'Неизвестная ошибка'));
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'color-mix(in srgb, black, transparent 50%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    }}>
      <div style={{
        background: 'var(--bg-primary)',
        border: '1px solid var(--border-color)',
        borderRadius: 12,
        padding: 24,
        width: '90%',
        maxWidth: 500,
        maxHeight: '90vh',
        overflow: 'auto'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 className="settings-h2">{title}</h3>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: 'var(--mac-font-size-2xl)',
              cursor: 'pointer',
              color: 'var(--text-primary)'
            }}>
            
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="settings-tab-content">
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'var(--mac-font-weight-semibold)' }}>Название *</label>
            <Input
              type="text"
              aria-label="Provider name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              style={{
                width: '100%',
                padding: 8,
                border: '1px solid var(--border-color)',
                borderRadius: 6,
                background: 'var(--bg-primary)',
                color: 'var(--text-primary)'
              }} />
            
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'var(--mac-font-weight-semibold)' }}>Код *</label>
            <Input
              type="text"
              aria-label="Provider code"
              value={formData.code}
              onChange={(e) => setFormData({ ...formData, code: e.target.value })}
              required
              style={{
                width: '100%',
                padding: 8,
                border: '1px solid var(--border-color)',
                borderRadius: 6,
                background: 'var(--bg-primary)',
                color: 'var(--text-primary)'
              }} />
            
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'var(--mac-font-weight-semibold)' }}>Описание</label>
            <textarea
              aria-label="Provider description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={3}
              style={{
                width: '100%',
                padding: 8,
                border: '1px solid var(--border-color)',
                borderRadius: 6,
                background: 'var(--bg-primary)',
                color: 'var(--text-primary)',
                resize: 'vertical'
              }} />
            
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'var(--mac-font-weight-semibold)' }}>Секретный ключ *</label>
            <Input
              type="password"
              aria-label="Provider secret key"
              value={formData.secret_key}
              onChange={(e) => setFormData({ ...formData, secret_key: e.target.value })}
              required
              style={{
                width: '100%',
                padding: 8,
                border: '1px solid var(--border-color)',
                borderRadius: 6,
                background: 'var(--bg-primary)',
                color: 'var(--text-primary)'
              }} />
            
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'var(--mac-font-weight-semibold)' }}>Webhook URL</label>
            <Input
              type="url"
              aria-label="Provider webhook URL"
              value={formData.webhook_url}
              onChange={(e) => setFormData({ ...formData, webhook_url: e.target.value })}
              style={{
                width: '100%',
                padding: 8,
                border: '1px solid var(--border-color)',
                borderRadius: 6,
                background: 'var(--bg-primary)',
                color: 'var(--text-primary)'
              }} />
            
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'var(--mac-font-weight-semibold)' }}>API URL</label>
            <Input
              type="url"
              aria-label="Provider API URL"
              value={formData.api_url}
              onChange={(e) => setFormData({ ...formData, api_url: e.target.value })}
              style={{
                width: '100%',
                padding: 8,
                border: '1px solid var(--border-color)',
                borderRadius: 6,
                background: 'var(--bg-primary)',
                color: 'var(--text-primary)'
              }} />
            
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Checkbox id="is_active" aria-label="Provider active" checked={formData.is_active} onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })} />
            
            <label htmlFor="is_active" className="settings-label-semibold">Активен</label>
          </div>

          <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 16 }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: 'var(--mac-spacing-2) var(--mac-spacing-4)',
                background: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 6,
                cursor: 'pointer'
              }}>
              
              Отмена
            </button>
            <button
              type="submit"
              style={{
                padding: 'var(--mac-spacing-2) var(--mac-spacing-4)',
                background: 'var(--accent-color)',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                cursor: 'pointer'
              }}>
              
              Сохранить
            </button>
          </div>
        </form>
      </div>
    </div>);

}

// Стили с использованием CSS переменных
const card = {
  border: '1px solid var(--border-color)',
  borderRadius: 12,
  padding: 12,
  background: 'var(--bg-primary)',
  boxShadow: 'var(--shadow-sm)'
};

const row = {
  display: 'grid',
  gridTemplateColumns: '1fr 2fr auto',
  gap: 8,
  alignItems: 'center'
};

const inp = {
  padding: '6px 10px',
  border: '1px solid var(--border-color)',
  borderRadius: 8,
  background: 'var(--bg-primary)',
  color: 'var(--text-primary)'
};

const btn = {
  padding: '6px 10px',
  borderRadius: 8,
  border: '1px solid var(--border-color)',
  background: 'var(--bg-secondary)',
  color: 'var(--text-primary)',
  cursor: 'pointer',
  transition: 'all 0.2s ease'
};

const btnPrimary = {
  ...btn,
  borderColor: 'var(--accent-color)',
  background: 'var(--accent-color)',
  color: 'white'
};

const errBox = {
  color: 'var(--danger-color)',
  background: 'var(--mac-error-bg)',
  border: '1px solid var(--danger-color)',
  borderRadius: 8,
  padding: 8
};

function KVField({ label, defKey, items, onSave }) {
  const found = (items || []).find((x) => x.key === defKey);
  const [val, setVal] = useState(found?.value || '');
  useEffect(() => setVal(found?.value || ''), [found?.value]);
  return (
    <div className="settings-row">
      <div className="settings-label-semibold">{label}</div>
      <Input aria-label={`${label} setting value`} value={val} onChange={(e) => setVal(e.target.value)} className="settings-input" />
      <button onClick={() => onSave(defKey, val)} className="settings-btn">Сохранить</button>
    </div>);

}

// Отдельный компонент для роли чтобы избежать hooks в map
function RoleMapItem({ role, items, onSave }) {
  const found = (items || []).find((x) => x.key === role);
  const [val, setVal] = useState(found?.value || '');
  useEffect(() => setVal(found?.value || ''), [found?.value]);

  return (
    <div className="settings-row">
      <div className="settings-label-semibold">{role}</div>
      <Input
        aria-label={`Route target for ${role}`}
        value={val}
        onChange={(e) => setVal(e.target.value)}
        className="settings-input"
        placeholder="Например: Cardio" />
      
      <button onClick={() => onSave(role, val)} className="settings-btn">
        Сохранить
      </button>
    </div>);

}

function RoleMapEditor({ items, onSave }) {
  const roles = ['admin', 'registrar', 'doctor', 'cardio', 'derma', 'dentist', 'lab', 'procedures', 'cashier', 'patient'];
  return (
    <div className="settings-role-map-list">
      {roles.map((r) =>
      <RoleMapItem
        key={r}
        role={r}
        items={items}
        onSave={onSave} />

      )}
    </div>);

}

TabButton.propTypes = {
  active: PropTypes.bool,
  onClick: PropTypes.func,
  children: PropTypes.node
};

Row.propTypes = {
  k: PropTypes.node,
  v: PropTypes.any,
  onSave: PropTypes.func
};

ProviderCard.propTypes = {
  provider: PropTypes.object,
  onEdit: PropTypes.func,
  onDelete: PropTypes.func
};

ProviderModal.propTypes = {
  provider: PropTypes.object,
  onClose: PropTypes.func,
  onSave: PropTypes.func,
  title: PropTypes.node
};

KVField.propTypes = {
  label: PropTypes.node,
  defKey: PropTypes.string,
  items: PropTypes.array,
  onSave: PropTypes.func
};

RoleMapItem.propTypes = {
  role: PropTypes.string,
  items: PropTypes.array,
  onSave: PropTypes.func
};

RoleMapEditor.propTypes = {
  items: PropTypes.array,
  onSave: PropTypes.func
};
