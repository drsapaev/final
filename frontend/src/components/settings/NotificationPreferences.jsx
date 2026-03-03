import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Bell,
  Clock3,
  Mail,
  MessageSquareText,
  RefreshCw,
  RotateCcw,
  Save,
  Smartphone,
} from 'lucide-react';

import { api, me } from '../../api/client';
import {
  Alert,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  MacOSButton,
  MacOSInput,
  Switch,
} from '../ui/macos';
import { getState as getAuthState } from '../../stores/auth';
import logger from '../../utils/logger';

const notificationSections = [
  {
    key: 'email',
    title: 'Email уведомления',
    description: 'Письма для рабочих сценариев и подтверждений.',
    icon: Mail,
    accent: 'linear-gradient(135deg, #0a84ff, #3b82f6)',
    fields: [
      {
        key: 'email_appointment_reminder',
        label: 'Напоминания о записи',
        hint: 'Письмо перед приёмом с датой, временем и специалистом.',
      },
      {
        key: 'email_appointment_confirmation',
        label: 'Подтверждение записи',
        hint: 'Подтверждение новой или перенесённой записи.',
      },
      {
        key: 'email_appointment_cancellation',
        label: 'Отмена записи',
        hint: 'Оповещение об отмене или переносе приёма.',
      },
      {
        key: 'email_payment_receipt',
        label: 'Чек об оплате',
        hint: 'Финансовые документы и подтверждение платежа.',
      },
      {
        key: 'email_system_updates',
        label: 'Системные обновления',
        hint: 'Технические уведомления и продуктовые изменения.',
      },
      {
        key: 'email_security_alerts',
        label: 'Оповещения безопасности',
        hint: 'Критичные события входа, 2FA и смены пароля.',
      },
    ],
  },
  {
    key: 'sms',
    title: 'SMS уведомления',
    description: 'Короткие и срочные сообщения на телефон.',
    icon: MessageSquareText,
    accent: 'linear-gradient(135deg, #34c759, #10b981)',
    note: 'SMS-канал может тарифицироваться отдельно у оператора или провайдера.',
    fields: [
      {
        key: 'sms_appointment_reminder',
        label: 'Напоминания о записи',
        hint: 'Короткое SMS перед визитом в клинику.',
      },
      {
        key: 'sms_emergency',
        label: 'Экстренные оповещения',
        hint: 'Критичные уведомления, которые нельзя пропустить.',
      },
    ],
  },
  {
    key: 'push',
    title: 'Push уведомления',
    description: 'Оповещения для мобильного приложения и PWA.',
    icon: Smartphone,
    accent: 'linear-gradient(135deg, #7c3aed, #0ea5e9)',
    note: 'Работает только если устройство уже дало разрешение на push-уведомления.',
    fields: [
      {
        key: 'push_appointment_reminder',
        label: 'Напоминания о записи',
        hint: 'Мобильное уведомление перед приёмом.',
      },
      {
        key: 'push_appointment_confirmation',
        label: 'Обновления очереди',
        hint: 'Изменения статуса записи и очереди без захода в приложение.',
      },
      {
        key: 'push_payment_receipt',
        label: 'Чек об оплате',
        hint: 'Подтверждение оплаты в виде push-сообщения.',
      },
    ],
  },
];

const generalFields = [
  {
    key: 'reminder_time_before',
    label: 'Напоминать за',
    description: 'Количество минут до приёма.',
    type: 'number',
    min: 15,
    step: 15,
    suffix: 'мин',
  },
  {
    key: 'quiet_hours_start',
    label: 'Тихие часы: начало',
    description: 'В это время некритичные уведомления будут приглушены.',
    type: 'time',
  },
  {
    key: 'quiet_hours_end',
    label: 'Тихие часы: конец',
    description: 'Время завершения тихого режима.',
    type: 'time',
  },
];

const NOTIFICATION_SETTINGS_CACHE_MS = 30_000;
const notificationSettingsCache = new Map();
const notificationSettingsRequests = new Map();

function resolveCurrentUserId() {
  const authState = getAuthState();
  return authState?.profile?.id || null;
}

function rememberNotificationSettings(userId, settings) {
  notificationSettingsCache.set(userId, {
    data: settings,
    cachedAt: Date.now(),
  });
  return settings;
}

function getFreshNotificationSettings(userId) {
  const cached = notificationSettingsCache.get(userId);
  if (!cached) {
    return null;
  }

  if (Date.now() - cached.cachedAt > NOTIFICATION_SETTINGS_CACHE_MS) {
    notificationSettingsCache.delete(userId);
    return null;
  }

  return cached.data;
}

async function fetchNotificationSettings(userId, { force = false } = {}) {
  if (!force) {
    const cached = getFreshNotificationSettings(userId);
    if (cached) {
      logger.info('[FIX:PROFILE] Using cached notification preferences', { userId });
      return cached;
    }
  }

  if (notificationSettingsRequests.has(userId)) {
    return notificationSettingsRequests.get(userId);
  }

  const request = api
    .get(`/notifications/settings/${userId}`)
    .then((response) => rememberNotificationSettings(userId, response.data))
    .finally(() => {
      notificationSettingsRequests.delete(userId);
    });

  notificationSettingsRequests.set(userId, request);
  return request;
}

function getInitialDraft(settings) {
  return settings ? { ...settings } : null;
}

function formatSavedAt(value) {
  if (!value) {
    return 'Изменения ещё не сохранялись в этой сессии';
  }

  return `Сохранено ${value.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  })}`;
}

function NotificationChannelCard({ accent, description, icon: Icon, title, note, children }) {
  return (
    <Card shadow="default">
      <CardHeader style={{ paddingBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: 14,
              background: accent,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              boxShadow: '0 14px 28px rgba(15, 23, 42, 0.14)',
              flexShrink: 0,
            }}
          >
            <Icon size={18} />
          </div>
          <div style={{ minWidth: 0 }}>
            <CardTitle>{title}</CardTitle>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--mac-text-secondary)' }}>
              {description}
            </div>
            {note && (
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                {note}
              </div>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent style={{ display: 'grid', gap: 12 }}>
        {children}
      </CardContent>
    </Card>
  );
}

NotificationChannelCard.propTypes = {
  accent: PropTypes.string.isRequired,
  children: PropTypes.node.isRequired,
  description: PropTypes.string.isRequired,
  icon: PropTypes.elementType.isRequired,
  note: PropTypes.string,
  title: PropTypes.string.isRequired,
};

function PreferenceRow({ checked, description, disabled, label, onChange }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto',
        gap: 16,
        alignItems: 'center',
        padding: '14px 16px',
        border: '1px solid var(--mac-border)',
        borderRadius: 14,
        background: 'linear-gradient(180deg, var(--mac-bg-primary), var(--mac-bg-secondary))',
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--mac-text-primary)' }}>
          {label}
        </div>
        <div style={{ marginTop: 4, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
          {description}
        </div>
      </div>
      <Switch checked={checked} disabled={disabled} onChange={onChange} />
    </div>
  );
}

PreferenceRow.propTypes = {
  checked: PropTypes.bool,
  description: PropTypes.string.isRequired,
  disabled: PropTypes.bool,
  label: PropTypes.string.isRequired,
  onChange: PropTypes.func.isRequired,
};

export function __resetNotificationSettingsCacheForTests() {
  notificationSettingsCache.clear();
  notificationSettingsRequests.clear();
}

export default function NotificationPreferences() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [lastSavedAt, setLastSavedAt] = useState(null);
  const [userId, setUserId] = useState(null);
  const [settings, setSettings] = useState(null);
  const [draft, setDraft] = useState(null);

  useEffect(() => {
    void loadSettings();
  }, []);

  const hasChanges = Boolean(
    settings &&
    draft &&
    JSON.stringify(settings) !== JSON.stringify(draft)
  );

  async function loadSettings({ force = false } = {}) {
    try {
      setLoading(true);
      setError('');
      setSuccess('');

      let resolvedUserId = resolveCurrentUserId();
      if (!resolvedUserId) {
        const user = await me();
        resolvedUserId = user.id;
      }

      setUserId(resolvedUserId);
      const nextSettings = await fetchNotificationSettings(resolvedUserId, { force });
      setSettings(nextSettings);
      setDraft(getInitialDraft(nextSettings));
      setLastSavedAt(new Date());
      logger.info('[FIX:PROFILE] Loaded notification preferences', { userId: resolvedUserId });
    } catch (err) {
      logger.error('Failed to load notification settings:', err);
      setError(err?.response?.data?.detail || 'Не удалось загрузить настройки уведомлений.');
    } finally {
      setLoading(false);
    }
  }

  function updateDraft(key, value) {
    setDraft((prev) => ({
      ...(prev || {}),
      [key]: value,
    }));
    setSuccess('');
  }

  function handleReset() {
    if (!settings) {
      return;
    }
    setDraft(getInitialDraft(settings));
    setSuccess('');
    setError('');
  }

  async function handleSave() {
    if (!draft || !userId) {
      return;
    }

    try {
      setSaving(true);
      setError('');
      setSuccess('');
      const response = await api.put(`/notifications/settings/${userId}`, draft);
      const nextSettings = rememberNotificationSettings(userId, response?.data || draft);
      setSettings(nextSettings);
      setDraft(getInitialDraft(nextSettings));
      setLastSavedAt(new Date());
      setSuccess('Настройки уведомлений сохранены.');
      logger.info('[FIX:PROFILE] Saved notification preferences', { userId });
    } catch (err) {
      logger.error('Failed to save settings:', err);
      setError(err?.response?.data?.detail || 'Не удалось сохранить настройки уведомлений.');
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div style={{ opacity: 0.7 }}>Загрузка настроек уведомлений...</div>;
  }

  if (!draft) {
    return (
      <div style={{ display: 'grid', gap: 16 }}>
        <Alert severity="error">
          {error || 'Не удалось загрузить настройки уведомлений.'}
        </Alert>
        <div>
          <MacOSButton
            variant="outline"
            onClick={() => loadSettings({ force: true })}
            startIcon={<RefreshCw size={16} />}
          >
            Повторить загрузку
          </MacOSButton>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'grid', gap: 20 }}>
      <Card shadow="default">
        <CardHeader style={{ paddingBottom: 12 }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              gap: 16,
              flexWrap: 'wrap',
            }}
          >
            <div>
              <CardTitle>Каналы уведомлений</CardTitle>
              <div style={{ marginTop: 6, fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                Настройте, по каким каналам получать рабочие и системные уведомления.
              </div>
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                {hasChanges ? 'Есть несохранённые изменения' : formatSavedAt(lastSavedAt)}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <MacOSButton
                variant="outline"
                onClick={() => loadSettings({ force: true })}
                disabled={saving}
                startIcon={<RefreshCw size={16} />}
              >
                Обновить
              </MacOSButton>
              <MacOSButton
                variant="ghost"
                onClick={handleReset}
                disabled={!hasChanges || saving}
                startIcon={<RotateCcw size={16} />}
              >
                Сбросить
              </MacOSButton>
              <MacOSButton
                variant="primary"
                onClick={handleSave}
                disabled={!hasChanges}
                loading={saving}
                startIcon={<Save size={16} />}
              >
                Сохранить настройки
              </MacOSButton>
            </div>
          </div>
        </CardHeader>
        <CardContent style={{ display: 'grid', gap: 12 }}>
          {error && <Alert severity="error">{error}</Alert>}
          {success && <Alert severity="success">{success}</Alert>}
          {!error && !success && hasChanges && (
            <Alert severity="info">
              Изменения применятся только после нажатия кнопки «Сохранить настройки».
            </Alert>
          )}
        </CardContent>
      </Card>

      {notificationSections.map((section) => (
        <NotificationChannelCard
          key={section.key}
          accent={section.accent}
          description={section.description}
          icon={section.icon}
          note={section.note}
          title={section.title}
        >
          {section.fields.map((field) => (
            <PreferenceRow
              key={field.key}
              checked={Boolean(draft[field.key])}
              description={field.hint}
              disabled={saving}
              label={field.label}
              onChange={(nextValue) => updateDraft(field.key, nextValue)}
            />
          ))}
        </NotificationChannelCard>
      ))}

      <Card shadow="default">
        <CardHeader style={{ paddingBottom: 12 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
            <div
              style={{
                width: 42,
                height: 42,
                borderRadius: 14,
                background: 'linear-gradient(135deg, #ff9f0a, #f97316)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                flexShrink: 0,
                boxShadow: '0 14px 28px rgba(249, 115, 22, 0.18)',
              }}
            >
              <Clock3 size={18} />
            </div>
            <div>
              <CardTitle>Время и правила доставки</CardTitle>
              <div style={{ marginTop: 6, fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                Общие правила, влияющие на все каналы уведомлений.
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent style={{ display: 'grid', gap: 16 }}>
          {generalFields.map((field) => (
            <div
              key={field.key}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr minmax(120px, 180px)',
                gap: 16,
                alignItems: 'center',
                padding: '14px 16px',
                border: '1px solid var(--mac-border)',
                borderRadius: 14,
                background: 'linear-gradient(180deg, var(--mac-bg-primary), var(--mac-bg-secondary))',
              }}
            >
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--mac-text-primary)' }}>
                  {field.label}
                </div>
                <div style={{ marginTop: 4, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                  {field.description}
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <MacOSInput
                  type={field.type}
                  min={field.min}
                  step={field.step}
                  value={draft[field.key] ?? ''}
                  disabled={saving}
                  onChange={(event) => {
                    if (field.type === 'number') {
                      const parsedValue = Number.parseInt(event.target.value, 10);
                      updateDraft(field.key, Number.isNaN(parsedValue) ? null : parsedValue);
                      return;
                    }
                    updateDraft(field.key, event.target.value || null);
                  }}
                />
                {field.suffix && (
                  <span style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                    {field.suffix}
                  </span>
                )}
              </div>
            </div>
          ))}

          <PreferenceRow
            checked={Boolean(draft.weekend_notifications)}
            description="Если выключить, напоминания и некритичные уведомления по выходным не отправляются."
            disabled={saving}
            label="Уведомления в выходные"
            onChange={(nextValue) => updateDraft('weekend_notifications', nextValue)}
          />
        </CardContent>
      </Card>

      <Card shadow="default">
        <CardContent
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 16,
            flexWrap: 'wrap',
          }}
        >
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--mac-text-primary)' }}>
              Итог по изменениям
            </div>
            <div style={{ marginTop: 4, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
              {hasChanges
                ? 'Есть локальные изменения. Сохраните их перед переходом на другую вкладку.'
                : formatSavedAt(lastSavedAt)}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <MacOSButton
              variant="ghost"
              onClick={handleReset}
              disabled={!hasChanges || saving}
              startIcon={<RotateCcw size={16} />}
            >
              Сбросить изменения
            </MacOSButton>
            <MacOSButton
              variant="primary"
              onClick={handleSave}
              disabled={!hasChanges}
              loading={saving}
              startIcon={<Bell size={16} />}
            >
              Применить настройки
            </MacOSButton>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
