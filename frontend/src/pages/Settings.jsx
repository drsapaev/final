import React, { useEffect, useMemo, useState } from 'react';
import RoleGate from '../components/RoleGate.jsx';
import { api } from '../api/client.js';
import { useTheme } from '../contexts/ThemeContext';
import TwoFactorManager from '../components/security/TwoFactorManager';
import TwoFactorSetupWizard from '../components/security/TwoFactorSetupWizard';
import PhoneVerification from '../components/auth/PhoneVerification';

import logger from '../utils/logger';
function TabButton({ active, onClick, children }) {
  // Используем CSS переменные вместо хардкод стилей
  const st = {
    padding: '8px 12px',
    borderRadius: 10,
    border: '1px solid var(--border-color)',
    background: active ? 'var(--accent-color)' : 'var(--bg-primary)',
    color: active ? 'white' : 'var(--text-primary)',
    cursor: 'pointer',
    transition: 'all 0.2s ease'
  };
  return (
    <button onClick={onClick} style={st}>{children}</button>
  );
}

function Row({ k, v, onSave }) {
  const [val, setVal] = useState(String(v ?? ''));
  useEffect(() => setVal(String(v ?? '')), [v]);
  return (
    <div style={row}>
      <div style={{ fontWeight: 600 }}>{k}</div>
      <input value={val} onChange={(e)=>setVal(e.target.value)} style={inp} />
      <button onClick={()=>onSave(k, val)} style={btn}>Сохранить</button>
    </div>
  );
}

/**
 * Settings:
 *  - Вкладка "license": активация сервера и статус (работает даже при REQUIRE_LICENSE=1)
 *  - Вкладка "printer": простые пары key/value (если backend поддерживает PUT /settings)
 *  - Вкладка "online_queue": простые пары key/value
 */
export default function Settings() {
  const { isDark, isLight, getColor, getSpacing } = useTheme();
  const [page, setPage] = useState('Settings');
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
      setStatus(st || null);
    } catch {
      setStatus(null);
    }
  }

  async function doActivate() {
    setBusyAct(true);
    setErrAct('');
    try {
      const res = await api.post('/activation/activate', { body: { key } });
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
    if (!confirm('Вы уверены, что хотите удалить этого провайдера?')) {
      return;
    }
    try {
      await api.delete(`/admin/providers/${providerId}`);
      await loadProviders();
    } catch (error) {
      logger.error('Ошибка удаления провайдера:', error);
    }
  }

  useEffect(() => { if (tab === 'license') loadStatus(); }, [tab]);
  useEffect(() => { if (tab === 'payment_providers') loadProviders(); }, [tab]);

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
      let arr = [];
      if (Array.isArray(res?.items)) arr = res.items;
      else if (Array.isArray(res)) arr = res;
      else if (res && typeof res === 'object') {
        // возможный словарь
        arr = Object.entries(res).map(([k, v]) => ({ key: k, value: v }));
      }
      setItems(arr.map(x => ({ key: x.key ?? x.name ?? '', value: x.value ?? '' })));
    } catch (e) {
      setErrCat(e?.data?.detail || e?.message || 'Ошибка загрузки настроек');
      setItems([]);
    } finally {
      setBusyCat(false);
    }
  }

  async function saveKV(category, key, value) {
    try {
      await api.put('/settings', { body: { category, key, value } });
      await loadCat(category);
    } catch (e) {
      alert(e?.data?.detail || e?.message || 'Ошибка сохранения');
    }
  }

  useEffect(() => {
    if (tab === 'printer' || tab === 'online_queue' || tab === 'display_board') {
      const c = tab === 'printer' ? 'printer' : (tab === 'online_queue' ? 'online_queue' : 'display_board');
      setCat(c);
      loadCat(c);
    }
     
  }, [tab]);

  const licenseOk = !!status?.ok;
  const badge = useMemo(() => {
    const st = status?.status || (licenseOk ? 'active' : 'not_active');
    return (
      <span style={{
        padding: '2px 8px', borderRadius: 999,
        background: licenseOk ? '#ecfdf5' : '#fef2f2',
        color: licenseOk ? '#065f46' : '#7f1d1d',
        border: `1px solid ${licenseOk ? '#a7f3d0' : '#fecaca'}`,
        fontSize: 12,
        whiteSpace: 'nowrap',
      }}>{st}</span>
    );
  }, [status, licenseOk]);

  return (
    <div>
      <RoleGate roles={['Admin']}>
        <div style={{ padding: 16, display: 'grid', gap: 12 }}>
          <h2 style={{ margin: 0 }}>Настройки</h2>

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <TabButton active={tab==='license'} onClick={()=>setTab('license')}>Лицензия</TabButton>
            <TabButton active={tab==='printer'} onClick={()=>setTab('printer')}>Принтер</TabButton>
            <TabButton active={tab==='online_queue'} onClick={()=>setTab('online_queue')}>Онлайн-очередь</TabButton>
            <TabButton active={tab==='display_board'} onClick={()=>setTab('display_board')}>Табло очереди</TabButton>
            <TabButton active={tab==='payment_providers'} onClick={()=>setTab('payment_providers')}>Провайдеры оплаты</TabButton>
            <TabButton active={tab==='security'} onClick={()=>setTab('security')}>Безопасность</TabButton>
          </div>

          {tab === 'license' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div style={card}>
                <div style={{ fontWeight: 700, marginBottom: 6 }}>Статус активации</div>
                <div style={{ display: 'grid', gap: 4 }}>
                  <div>Состояние: {badge}</div>
                  <div>Ключ: <code>{status?.key || '—'}</code></div>
                  <div>Machine hash: <code>{status?.machine_hash || '—'}</code></div>
                  <div>Действует до: <b>{status?.expiry_date || '—'}</b></div>
                </div>
              </div>

              <div style={card}>
                <div style={{ fontWeight: 700, marginBottom: 6 }}>Активация сервера</div>
                {errAct && <div style={errBox}>{String(errAct)}</div>}
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <input
                    placeholder="Вставьте ключ активации"
                    value={key}
                    onChange={(e)=>setKey(e.target.value)}
                    style={{ ...inp, minWidth: 320 }}
                  />
                  <button onClick={doActivate} disabled={busyAct || !key.trim()} style={btnPrimary}>
                    {busyAct ? '...' : 'Активировать'}
                  </button>
                  <button onClick={loadStatus} style={btn}>Обновить статус</button>
                </div>
                <div style={{ fontSize: 12, opacity: .7, marginTop: 6 }}>
                  При отсутствии ключа — обратитесь к администратору для выдачи.
                </div>
              </div>
            </div>
          )}

          {(tab === 'printer' || tab === 'online_queue' || tab === 'display_board') && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div style={card}>
                <div style={{ fontWeight: 700, marginBottom: 6 }}>
                  Категория: <code>{cat}</code>
                </div>
                {busyCat && <div style={{ opacity: .7 }}>Загрузка…</div>}
                {errCat && <div style={errBox}>{String(errCat)}</div>}
                <div style={{ display: 'grid', gap: 8 }}>
                  {items.map((it) => (
                    <Row
                      key={it.key}
                      k={it.key}
                      v={it.value}
                      onSave={(k, v) => saveKV(cat, k, v)}
                    />
                  ))}
                  {!busyCat && items.length === 0 && (
                    <div style={{ opacity: .7 }}>Записей нет</div>
                  )}
                </div>
              </div>

              {tab === 'display_board' && (
                <>
                  <div style={card}>
                    <div style={{ fontWeight: 700, marginBottom: 6 }}>Табло: бренд и объявления</div>
                    <div style={{ display: 'grid', gap: 8 }}>
                      <KVField label="Бренд (brand)" defKey="brand" items={items} onSave={(k,v)=>saveKV('display_board', k, v)} />
                      <KVField label="Логотип (logo URL)" defKey="logo" items={items} onSave={(k,v)=>saveKV('display_board', k, v)} />
                      <KVField label="Объявление RU (announcement_ru)" defKey="announcement_ru" items={items} onSave={(k,v)=>saveKV('display_board', k, v)} />
                      <KVField label="Объявление UZ (announcement_uz)" defKey="announcement_uz" items={items} onSave={(k,v)=>saveKV('display_board', k, v)} />
                      <KVField label="Объявление EN (announcement_en)" defKey="announcement_en" items={items} onSave={(k,v)=>saveKV('display_board', k, v)} />
                      <KVField label="Основной цвет (primary_color)" defKey="primary_color" items={items} onSave={(k,v)=>saveKV('display_board', k, v)} />
                      <KVField label="Цвет фона (bg_color)" defKey="bg_color" items={items} onSave={(k,v)=>saveKV('display_board', k, v)} />
                      <KVField label="Цвет текста (text_color)" defKey="text_color" items={items} onSave={(k,v)=>saveKV('display_board', k, v)} />
                      <KVField label="Контраст по умолчанию (contrast_default=true/false)" defKey="contrast_default" items={items} onSave={(k,v)=>saveKV('display_board', k, v)} />
                      <KVField label="Киоск по умолчанию (kiosk_default=true/false)" defKey="kiosk_default" items={items} onSave={(k,v)=>saveKV('display_board', k, v)} />
                      <KVField label="Звук по умолчанию (sound_default=true/false)" defKey="sound_default" items={items} onSave={(k,v)=>saveKV('display_board', k, v)} />
                    </div>
                  </div>

                  <div style={card}>
                    <div style={{ fontWeight: 700, marginBottom: 6 }}>Табло: мэппинг Роль → Отделение</div>
                    <RoleMapEditor items={items} onSave={(k,v)=>saveKV('display_board', k, v)} />
                  </div>
                </>
              )}

          {tab === 'payment_providers' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div style={card}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <div style={{ fontWeight: 700 }}>Провайдеры оплаты</div>
                  <button 
                    onClick={() => setShowAddProvider(true)}
                    style={{
                      padding: '8px 16px',
                      background: 'var(--accent-color)',
                      color: 'white',
                      border: 'none',
                      borderRadius: 6,
                      cursor: 'pointer'
                    }}
                  >
                    + Добавить провайдера
                  </button>
                </div>

                {loadingProviders ? (
                  <div style={{ opacity: 0.7 }}>Загрузка...</div>
                ) : (
                  <div style={{ display: 'grid', gap: 8 }}>
                    {providers.map((provider) => (
                      <ProviderCard
                        key={provider.id}
                        provider={provider}
                        onEdit={() => setEditingProvider(provider)}
                        onDelete={() => deleteProvider(provider.id)}
                      />
                    ))}
                    {providers.length === 0 && (
                      <div style={{ opacity: 0.7 }}>Провайдеры не найдены</div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {showAddProvider && (
            <ProviderModal
              onClose={() => setShowAddProvider(false)}
              onSave={createProvider}
              title="Добавить провайдера"
            />
          )}

          {editingProvider && (
            <ProviderModal
              provider={editingProvider}
              onClose={() => setEditingProvider(null)}
              onSave={(data) => updateProvider(editingProvider.id, data)}
              title="Редактировать провайдера"
            />
              )}
            </div>
          )}

          {tab === 'security' && (
            <div style={{ display: 'grid', gap: 12 }}>
              <div style={card}>
                <div style={{ fontWeight: 700, marginBottom: 12 }}>Двухфакторная аутентификация (2FA)</div>
                <TwoFactorManager />
              </div>

              <div style={card}>
                <div style={{ fontWeight: 700, marginBottom: 12 }}>Верификация телефона</div>
                <PhoneVerification
                  showPhoneInput={true}
                  title="Верификация телефона"
                  onVerified={() => alert('Телефон успешно подтверждён!')}
                />
              </div>
            </div>
          )}
        </div>
      </RoleGate>
    </div>
  );
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
        <div style={{ fontWeight: 600 }}>{provider.name}</div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={onEdit}
            style={{
              padding: '4px 8px',
              background: 'var(--accent-color)',
              color: 'white',
              border: 'none',
              borderRadius: 4,
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            Редактировать
          </button>
          <button
            onClick={onDelete}
            style={{
              padding: '4px 8px',
              background: '#dc3545',
              color: 'white',
              border: 'none',
              borderRadius: 4,
              cursor: 'pointer',
              fontSize: '12px'
            }}
          >
            Удалить
          </button>
        </div>
      </div>
      <div style={{ fontSize: '14px', opacity: 0.8 }}>
        <div>Код: {provider.code}</div>
        <div>Активен: {provider.is_active ? 'Да' : 'Нет'}</div>
        {provider.description && <div>Описание: {provider.description}</div>}
      </div>
    </div>
  );
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
      alert('Ошибка сохранения: ' + (error.message || 'Неизвестная ошибка'));
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0,0,0,0.5)',
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
          <h3 style={{ margin: 0 }}>{title}</h3>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              fontSize: '20px',
              cursor: 'pointer',
              color: 'var(--text-primary)'
            }}
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'grid', gap: 12 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>Название *</label>
            <input
              type="text"
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
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>Код *</label>
            <input
              type="text"
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
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>Описание</label>
            <textarea
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
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>Секретный ключ *</label>
            <input
              type="password"
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
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>Webhook URL</label>
            <input
              type="url"
              value={formData.webhook_url}
              onChange={(e) => setFormData({ ...formData, webhook_url: e.target.value })}
              style={{
                width: '100%',
                padding: 8,
                border: '1px solid var(--border-color)',
                borderRadius: 6,
                background: 'var(--bg-primary)',
                color: 'var(--text-primary)'
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 4, fontWeight: 600 }}>API URL</label>
            <input
              type="url"
              value={formData.api_url}
              onChange={(e) => setFormData({ ...formData, api_url: e.target.value })}
              style={{
                width: '100%',
                padding: 8,
                border: '1px solid var(--border-color)',
                borderRadius: 6,
                background: 'var(--bg-primary)',
                color: 'var(--text-primary)'
              }}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              id="is_active"
              checked={formData.is_active}
              onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
            />
            <label htmlFor="is_active" style={{ fontWeight: 600 }}>Активен</label>
          </div>

          <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 16 }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: '8px 16px',
                background: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-color)',
                borderRadius: 6,
                cursor: 'pointer'
              }}
            >
              Отмена
            </button>
            <button
              type="submit"
              style={{
                padding: '8px 16px',
                background: 'var(--accent-color)',
                color: 'white',
                border: 'none',
                borderRadius: 6,
                cursor: 'pointer'
              }}
            >
              Сохранить
            </button>
          </div>
        </form>
      </div>
    </div>
  );
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
  background: 'rgba(239, 68, 68, 0.1)', 
  border: '1px solid var(--danger-color)', 
  borderRadius: 8, 
  padding: 8 
};

function KVField({ label, defKey, items, onSave }) {
  const found = (items || []).find((x) => x.key === defKey);
  const [val, setVal] = useState(found?.value || '');
  useEffect(() => setVal(found?.value || ''), [found?.value]);
  return (
    <div style={row}>
      <div style={{ fontWeight: 600 }}>{label}</div>
      <input value={val} onChange={(e)=>setVal(e.target.value)} style={inp} />
      <button onClick={()=>onSave(defKey, val)} style={btn}>Сохранить</button>
    </div>
  );
}

// Отдельный компонент для роли чтобы избежать hooks в map
function RoleMapItem({ role, items, onSave }) {
  const found = (items || []).find((x) => x.key === role);
  const [val, setVal] = useState(found?.value || '');
  useEffect(() => setVal(found?.value || ''), [found?.value]);
  
  return (
    <div style={row}>
      <div style={{ fontWeight: 600 }}>{role}</div>
      <input 
        value={val} 
        onChange={(e) => setVal(e.target.value)} 
        style={inp} 
        placeholder="Например: Cardio" 
      />
      <button onClick={() => onSave(role, val)} style={btn}>
        Сохранить
      </button>
    </div>
  );
}

function RoleMapEditor({ items, onSave }) {
  const roles = ['admin','registrar','doctor','cardio','derma','dentist','lab','procedures','cashier','patient'];
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      {roles.map((r) => (
        <RoleMapItem 
          key={r} 
          role={r} 
          items={items} 
          onSave={onSave} 
        />
      ))}
    </div>
  );
}

