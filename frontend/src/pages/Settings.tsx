import { useTranslation } from '../i18n/useTranslation';
import { useEffect, useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import PropTypes from 'prop-types';
import RoleGate from '../components/RoleGate';
import { api } from '../api/client';
import { useTheme } from '../contexts/ThemeContext';
import TwoFactorManager from '../components/security/TwoFactorManager';
import ColorSchemeSelector from '../components/admin/ColorSchemeSelector';
import { AccentPicker } from '../components/ui/macos';

import PhoneVerification from '../components/auth/PhoneVerification';

import logger from '../utils/logger';
import NotificationSystemStatus from '../components/settings/NotificationSystemStatus';
// P-013 fix: shared ConfirmDialog hook replacing native confirm() calls.
import { useConfirm } from '../components/common/ConfirmDialog';
import './SettingsAnalytics.css';
import { Input,
  Checkbox } from '../components/ui/macos';
import { notify } from '../services/notify';
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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [val, setVal] = useState(String(v ?? ''));
  useEffect(() => setVal(String(v ?? '')), [v]);
  return (
    <div className="settings-row">
      <div className="settings-label-semibold">{k}</div>
      <Input aria-label={`Setting value for ${k}`} value={val} onChange={(e) => setVal(e.target.value)} className="settings-input" />
      <button onClick={() => onSave(k, val)} className="settings-btn">{t('misc.save')}</button>
    </div>);

}

/**
 * Settings:
 *  - Вкладка "license": активация сервера и статус (работает даже при REQUIRE_LICENSE=1)
 *  - Вкладка "printer": простые пары key/value (если backend поддерживает PUT /settings)
 *  - Вкладка "online_queue": простые пары key/value
 */
export default function Settings() {void
  useTheme();
  useState('Settings');
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // P-013 fix: shared ConfirmDialog hook (replaces 1 native confirm() call).
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;
  const [tab, setTab] = useState<'license' | 'printer' | 'online_queue' | 'display_board' | 'payment_providers' | 'notifications' | 'appearance' | 'security'>('license');

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
      const st = (await api.get('/activation/status')) as import('axios').AxiosResponse<Record<string, unknown>>;
      setStatus(st?.data ?? st ?? null);
    } catch {
      setStatus(null);
    }
  }

  async function doActivate() {
    setBusyAct(true);
    setErrAct('');
    try {
      const response = (await api.post('/activation/activate', { key })) as import('axios').AxiosResponse<Record<string, unknown>>;
      const res = (response?.data ?? response) as { ok?: boolean; reason?: string };
      if (!res?.ok) {
        setErrAct(res?.reason || t('misc.settings_activation_failed'));
      }
      await loadStatus();
    } catch (e) {
      setErrAct(e?.data?.detail || e?.message || t('misc.settings_activation_error'));
    } finally {
      setBusyAct(false);
    }
  }

  // Payment providers functions
  async function loadProviders() {
    setLoadingProviders(true);
    try {
      const response = (await api.get('/admin/providers')) as import('axios').AxiosResponse<Record<string, unknown>>;
      setProviders((response?.data as unknown as unknown[]) || []);
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
      title: t('misc.settings_provider_delete_title'),
      message: t('misc.settings_provider_delete_message'),
      description: t('misc.settings_irreversible_action'),
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
      const res = await api.get('/settings', { params: { category } }) as import('axios').AxiosResponse<Record<string, unknown>>;
      const data = (res?.data ?? res) as { items?: unknown[]; [k: string]: unknown };
      let arr: unknown[] = [];
      if (Array.isArray(data?.items)) arr = data.items;else
      if (Array.isArray(data)) arr = data;else
      if (data && typeof data === 'object') {
        // возможный словарь
        arr = Object.entries(data).map(([k, v]) => ({ key: k, value: v }));
      }
      setItems(arr.map((x) => ({ key: (x as { key?: string }).key ?? (x as { name?: string }).name ?? '', value: (x as { value?: unknown }).value ?? '' })));
    } catch (e) {
      setErrCat(e?.data?.detail || e?.message || t('misc.settings_load_error'));
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
      notify.error(e?.data?.detail || e?.message || t('misc.settings_save_error'));
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
          <h2 className="settings-h2">{t('misc.settings_page_title')}</h2>

          <div className="settings-tab-bar">
            <TabButton active={tab === 'license'} onClick={() => setTab('license')}>{t('misc.settings_tab_license')}</TabButton>
            <TabButton active={tab === 'printer'} onClick={() => setTab('printer')}>{t('misc.settings_tab_printer')}</TabButton>
            <TabButton active={tab === 'online_queue'} onClick={() => setTab('online_queue')}>{t('misc.settings_tab_online_queue')}</TabButton>
            <TabButton active={tab === 'display_board'} onClick={() => setTab('display_board')}>{t('misc.settings_tab_display_board')}</TabButton>
            <TabButton active={tab === 'payment_providers'} onClick={() => setTab('payment_providers')}>{t('misc.settings_tab_payment_providers')}</TabButton>
            <TabButton active={tab === 'notifications'} onClick={() => setTab('notifications')}>{t('misc.settings_tab_notifications')}</TabButton>
            <TabButton active={tab === 'appearance'} onClick={() => setTab('appearance')}>{t('misc.settings_tab_appearance')}</TabButton>
            <TabButton active={tab === 'security'} onClick={() => setTab('security')}>{t('misc.settings_tab_security')}</TabButton>
          </div>

          {tab === 'appearance' &&
          <div className="settings-tab-content">
              <ColorSchemeSelector />

              <div className="settings-card">
                <div className="settings-card-title">Accent color</div>
                <div className="settings-card-body">
                  <AccentPicker />
                  <div className="settings-hint">
                    {t('misc.settings_accent_hint')}
                  </div>
                </div>
              </div>

              <div className="settings-card">
                <div className="settings-card-title">{t('misc.settings_use_together_title')}</div>
                <div className="settings-card-body-gap8">
                  <div>{t('misc.settings_use_together_step1')}</div>
                  <div>{t('misc.settings_use_together_step2')}</div>
                  <div className="settings-hint-75">
                    {t('misc.settings_use_together_hint')}
                  </div>
                </div>
              </div>
            </div>
          }

          {tab === 'notifications' &&
          <div className="settings-tab-content">
              <div className="settings-card">
                <div className="settings-card-title">{t('misc.settings_notifications_status_title')}</div>
                <NotificationSystemStatus />
              </div>
            </div>
          }

          {tab === 'license' &&
          <div className="settings-tab-content">
              <div className="settings-card">
                <div className="settings-card-title-mb6">{t('misc.settings_activation_status')}</div>
                <div className="settings-info-grid">
                  <div>{t('misc.settings_state_label')} {badge}</div>
                  <div>{t('misc.settings_key_label')} <code>{status?.key || '—'}</code></div>
                  <div>Machine hash: <code>{status?.machine_hash || '—'}</code></div>
                  <div>{t('misc.settings_expiry_label')} <b>{status?.expiry_date || '—'}</b></div>
                </div>
              </div>

              <div className="settings-card">
                <div className="settings-card-title-mb6">{t('misc.settings_activation_title')}</div>
                {errAct && <div className="settings-error-box">{String(errAct)}</div>}
                <div className="settings-activation-row">
                  <Input
                  placeholder={t('misc.settings_activation_key_placeholder')}
                  aria-label="Activation key"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  className="settings-input" />
                
                  <button onClick={doActivate} disabled={busyAct || !key.trim()} className="settings-btn-primary">
                    {busyAct ? '...' : t('misc.settings_activate_btn')}
                  </button>
                  <button onClick={loadStatus} className="settings-btn">{t('misc.settings_refresh_status_btn')}</button>
                </div>
                <div style={{ fontSize: 12, opacity: .7, marginTop: 6 }}>
                  {t('misc.settings_no_key_hint')}
                </div>
              </div>
            </div>
          }

          {(tab === 'printer' || tab === 'online_queue' || tab === 'display_board') &&
          <div className="settings-tab-content">
              <div className="settings-card">
                <div className="settings-card-title-mb6">
                  {t('misc.settings_category_label')} <code>{cat}</code>
                </div>
                {busyCat && <div style={{ opacity: .7 }}>{t('misc.settings_loading')}</div>}
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
                <div style={{ opacity: .7 }}>{t('misc.settings_no_entries')}</div>
                }
                </div>
              </div>

              {tab === 'display_board' &&
            <>
                  <div className="settings-card">
                    <div className="settings-card-title-mb6">{t('misc.settings_board_brand_title')}</div>
                    <div className="settings-role-map-list">
                      <KVField label={t('misc.settings_board_brand_label')} defKey="brand" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label={t('misc.settings_board_logo_label')} defKey="logo" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label={t('misc.settings_board_announcement_ru_label')} defKey="announcement_ru" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label={t('misc.settings_board_announcement_uz_label')} defKey="announcement_uz" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label={t('misc.settings_board_announcement_en_label')} defKey="announcement_en" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label={t('misc.settings_board_primary_color_label')} defKey="primary_color" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label={t('misc.settings_board_bg_color_label')} defKey="bg_color" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label={t('misc.settings_board_text_color_label')} defKey="text_color" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label={t('misc.settings_board_contrast_label')} defKey="contrast_default" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label={t('misc.settings_board_kiosk_label')} defKey="kiosk_default" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                      <KVField label={t('misc.settings_board_sound_label')} defKey="sound_default" items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                    </div>
                  </div>

                  <div className="settings-card">
                    <div className="settings-card-title-mb6">{t('misc.settings_board_role_map_title')}</div>
                    <RoleMapEditor items={items} onSave={(k, v) => saveKV('display_board', k, v)} />
                  </div>
                </>
            }

              {(tab as string) === 'payment_providers' &&
            <div className="settings-tab-content">
                  <div className="settings-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                      <div className="settings-label-semibold">{t('misc.settings_payment_providers_title')}</div>
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
                    
                        {t('misc.settings_add_provider_btn')}
                      </button>
                    </div>

                    {loadingProviders ?
                <div style={{ opacity: 0.7 }}>{t('misc.settings_loading_providers')}</div> :

                <div className="settings-role-map-list">
                        {providers.map((provider) =>
                  <ProviderCard
                    key={provider.id}
                    provider={provider}
                    onEdit={() => setEditingProvider(provider)}
                    onDelete={() => deleteProvider(provider.id)} />

                  )}
                        {providers.length === 0 &&
                  <div style={{ opacity: 0.7 }}>{t('misc.settings_no_providers')}</div>
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
              title={t('misc.settings_add_provider_title')} />

            }

              {editingProvider &&
            <ProviderModal
              provider={editingProvider}
              onClose={() => setEditingProvider(null)}
              onSave={(data) => updateProvider(editingProvider.id, data)}
              title={t('misc.settings_edit_provider_title')} />

            }
            </div>
          }

          {tab === 'security' &&
          <div className="settings-tab-content">
              <div className="settings-card">
                <div className="settings-card-title">{t('misc.settings_2fa_title')}</div>
                <TwoFactorManager />
              </div>

              <div className="settings-card">
                <div className="settings-card-title">{t('misc.settings_phone_verification_title')}</div>
                <PhoneVerification
                showPhoneInput={true}
                title={t('misc.settings_phone_verification_title')}
                onVerified={() => notify.success(t('misc.settings_phone_verified'))} />

              </div>
            </div>
          }
        </div>
      </RoleGate>
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog as unknown as React.ReactNode}
    </div>);

}

// Компонент карточки провайдера
function ProviderCard({ provider, onEdit, onDelete }) {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
            
            {t('misc.settings_edit_btn')}
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
            
            {t('misc.delete')}
          </button>
        </div>
      </div>
      <div style={{ fontSize: 'var(--mac-font-size-base)', opacity: 0.8 }}>
        <div>{t('misc.settings_code_label')} {provider.code}</div>
        <div>{t('misc.settings_active_label')} {provider.is_active ? t('misc.yes') : t('misc.no')}</div>
        {provider.description && <div>{t('misc.settings_description_label')} {provider.description}</div>}
      </div>
    </div>);

}

// Модальное окно для добавления/редактирования провайдера
function ProviderModal({ provider, onClose, onSave, title }: { provider?: Record<string, unknown>; onClose?: () => void; onSave?: (data: unknown) => void; title?: string }) {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [formData, setFormData] = useState<Record<string, unknown>>({
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
      notify.error(t('misc.settings_save_operation_error', { msg: error.message || t('misc.settings_unknown_error') }));
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
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'var(--mac-font-weight-semibold)' }}>{t('misc.settings_name_required')}</label>
            <Input
              type="text"
              aria-label="Provider name"
              value={formData.name as string}
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
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'var(--mac-font-weight-semibold)' }}>{t('misc.settings_code_required')}</label>
            <Input
              type="text"
              aria-label="Provider code"
              value={formData.code as string}
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
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'var(--mac-font-weight-semibold)' }}>{t('misc.settings_description')}</label>
            <textarea
              aria-label="Provider description"
              value={formData.description as string}
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
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 'var(--mac-font-weight-semibold)' }}>{t('misc.settings_secret_key_required')}</label>
            <Input
              type="password"
              aria-label="Provider secret key"
              value={formData.secret_key as string}
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
              value={formData.webhook_url as string}
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
              value={formData.api_url as string}
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
            <Checkbox id="is_active" aria-label="Provider active" checked={Boolean(formData.is_active as boolean)} onChange={(checked: boolean) => setFormData({ ...formData, is_active: checked })} />
            
            <label htmlFor="is_active" className="settings-label-semibold">{t('misc.settings_active')}</label>
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
              
              {t('misc.cancel')}
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
              
              {t('misc.save')}
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
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const found = (items || []).find((x) => x.key === defKey);
  const [val, setVal] = useState(found?.value || '');
  useEffect(() => setVal(found?.value || ''), [found?.value]);
  return (
    <div className="settings-row">
      <div className="settings-label-semibold">{label}</div>
      <Input aria-label={`${label} setting value`} value={val} onChange={(e) => setVal(e.target.value)} className="settings-input" />
      <button onClick={() => onSave(defKey, val)} className="settings-btn">{t('misc.save')}</button>
    </div>);

}

// Отдельный компонент для роли чтобы избежать hooks в map
function RoleMapItem({ role, items, onSave }) {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
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
        placeholder={t('misc.settings_role_placeholder')} />
      
      <button onClick={() => onSave(role, val)} className="settings-btn">
        {t('misc.save')}
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
