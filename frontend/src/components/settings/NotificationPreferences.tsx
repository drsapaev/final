// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Bell,
  Clock3,
  Mail,
  MessageSquareText,
  Moon,
  RefreshCw,
  RotateCcw,
  Save,
  Smartphone,
} from 'lucide-react';

import { api, me } from '../../api/client';
import { notificationsService } from '../../api/services';
import {
  Alert,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Input,
  Switch,
} from '../ui/macos';
import { getState as getAuthState } from '../../stores/auth';
import { useTranslation } from '../../i18n/useTranslation';
import logger from '../../utils/logger';

const accentGradients = {
  info: 'linear-gradient(135deg, var(--mac-accent), color-mix(in srgb, var(--mac-accent), white 18%))',
  success: 'linear-gradient(135deg, var(--mac-success), color-mix(in srgb, var(--mac-success), white 18%))',
  warning: 'linear-gradient(135deg, var(--mac-warning), color-mix(in srgb, var(--mac-warning), white 18%))',
  purple: 'linear-gradient(135deg, var(--mac-accent-purple), color-mix(in srgb, var(--mac-accent), white 12%))',
};

const notificationSections = [
  {
    key: 'email',
    titleKey: 'misc.np_email_title',
    descriptionKey: 'misc.np_email_desc',
    icon: Mail,
    accent: accentGradients.info,
    fields: [
      {
        key: 'email_appointment_reminder',
        labelKey: 'misc.np_email_appointment_reminder_label',
        hintKey: 'misc.np_email_appointment_reminder_hint',
      },
      {
        key: 'email_appointment_confirmation',
        labelKey: 'misc.np_email_appointment_confirmation_label',
        hintKey: 'misc.np_email_appointment_confirmation_hint',
      },
      {
        key: 'email_appointment_cancellation',
        labelKey: 'misc.np_email_appointment_cancellation_label',
        hintKey: 'misc.np_email_appointment_cancellation_hint',
      },
      {
        key: 'email_payment_receipt',
        labelKey: 'misc.np_email_payment_receipt_label',
        hintKey: 'misc.np_email_payment_receipt_hint',
      },
      {
        key: 'email_system_updates',
        labelKey: 'misc.np_email_system_updates_label',
        hintKey: 'misc.np_email_system_updates_hint',
      },
      {
        key: 'email_security_alerts',
        labelKey: 'misc.np_email_security_alerts_label',
        hintKey: 'misc.np_email_security_alerts_hint',
      },
    ],
  },
  {
    key: 'sms',
    titleKey: 'misc.np_sms_title',
    descriptionKey: 'misc.np_sms_desc',
    noteKey: 'misc.np_sms_note',
    icon: MessageSquareText,
    accent: accentGradients.success,
    fields: [
      {
        key: 'sms_appointment_reminder',
        labelKey: 'misc.np_sms_appointment_reminder_label',
        hintKey: 'misc.np_sms_appointment_reminder_hint',
      },
      {
        key: 'sms_emergency',
        labelKey: 'misc.np_sms_emergency_label',
        hintKey: 'misc.np_sms_emergency_hint',
      },
    ],
  },
  {
    key: 'push',
    titleKey: 'misc.np_push_title',
    descriptionKey: 'misc.np_push_desc',
    noteKey: 'misc.np_push_note',
    icon: Smartphone,
    accent: accentGradients.purple,
    fields: [
      {
        key: 'push_appointment_reminder',
        labelKey: 'misc.np_push_appointment_reminder_label',
        hintKey: 'misc.np_push_appointment_reminder_hint',
      },
      {
        key: 'push_appointment_confirmation',
        labelKey: 'misc.np_push_appointment_confirmation_label',
        hintKey: 'misc.np_push_appointment_confirmation_hint',
      },
      {
        key: 'push_payment_receipt',
        labelKey: 'misc.np_push_payment_receipt_label',
        hintKey: 'misc.np_push_payment_receipt_hint',
      },
    ],
  },
];

const generalFields = [
  {
    key: 'reminder_time_before',
    labelKey: 'misc.np_reminder_time_before_label',
    descriptionKey: 'misc.np_reminder_time_before_desc',
    suffixKey: 'misc.np_reminder_time_before_suffix',
    type: 'number',
    min: 15,
    step: 15,
  },
  {
    key: 'quiet_hours_start',
    labelKey: 'misc.np_quiet_hours_start_label',
    descriptionKey: 'misc.np_quiet_hours_start_desc',
    type: 'time',
  },
  {
    key: 'quiet_hours_end',
    labelKey: 'misc.np_quiet_hours_end_label',
    descriptionKey: 'misc.np_quiet_hours_end_desc',
    type: 'time',
  },
];

const policyFamilyFields = [
  {
    key: 'queue',
    labelKey: 'misc.np_family_queue_label',
    hintKey: 'misc.np_family_queue_hint',
  },
  {
    key: 'lab',
    labelKey: 'misc.np_family_lab_label',
    hintKey: 'misc.np_family_lab_hint',
  },
  {
    key: 'all_free',
    labelKey: 'misc.np_family_all_free_label',
    hintKey: 'misc.np_family_all_free_hint',
  },
  {
    key: 'message',
    labelKey: 'misc.np_family_message_label',
    hintKey: 'misc.np_family_message_hint',
  },
  {
    key: 'system',
    labelKey: 'misc.np_family_system_label',
    hintKey: 'misc.np_family_system_hint',
  },
];

const policyEventFields = [
  {
    key: 'lab_critical_result',
    labelKey: 'misc.np_event_lab_critical_result_label',
    hintKey: 'misc.np_event_lab_critical_result_hint',
  },
  {
    key: 'security_alert',
    labelKey: 'misc.np_event_security_alert_label',
    hintKey: 'misc.np_event_security_alert_hint',
  },
  {
    key: 'billing_alert',
    labelKey: 'misc.np_event_billing_alert_label',
    hintKey: 'misc.np_event_billing_alert_hint',
  },
];

const defaultPolicyFamilies = policyFamilyFields.reduce((acc, item) => {
  acc[item.key] = { desktop: true };
  return acc;
}, {});

const defaultPolicyEvents = policyEventFields.reduce((acc, item) => {
  acc[item.key] = { desktop: true };
  return acc;
}, {});

function cloneValue(value) {
  return JSON.parse(JSON.stringify(value));
}

function toDateTimeLocalValue(value) {
  if (!value) {
    return '';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return '';
  }

  const pad = (part) => String(part).padStart(2, '0');
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
}

function normalizePolicyControl(control, fallback = true) {
  if (typeof control === 'boolean') {
    return { desktop: control };
  }

  if (!control || typeof control !== 'object') {
    return { desktop: fallback };
  }

  if (typeof control.desktop === 'boolean') {
    return { desktop: control.desktop };
  }

  if (typeof control.realtime_enabled === 'boolean') {
    return { desktop: control.realtime_enabled };
  }

  if (typeof control.enabled === 'boolean') {
    return { desktop: control.enabled };
  }

  const channelDesktop = control.channels?.desktop;
  if (typeof channelDesktop === 'boolean') {
    return { desktop: channelDesktop };
  }

  return { desktop: fallback };
}

function createDefaultPolicyDraft() {
  return {
    muted_until: null,
    snooze_until: null,
    dnd: {
      enabled: false,
      always_on: false,
      start: '22:00',
      end: '07:00',
    },
    channel_controls: { desktop: true },
    family_controls: cloneValue(defaultPolicyFamilies),
    event_controls: cloneValue(defaultPolicyEvents),
  };
}

function normalizePolicyDraft(policy) {
  const next = createDefaultPolicyDraft();
  if (!policy || typeof policy !== 'object') {
    return next;
  }

  if (typeof policy.muted_until === 'string' && policy.muted_until.trim()) {
    next.muted_until = policy.muted_until;
  }
  if (typeof policy.snooze_until === 'string' && policy.snooze_until.trim()) {
    next.snooze_until = policy.snooze_until;
  }

  if (policy.dnd && typeof policy.dnd === 'object') {
    if (typeof policy.dnd.enabled === 'boolean') {
      next.dnd.enabled = policy.dnd.enabled;
    }
    if (typeof policy.dnd.always_on === 'boolean') {
      next.dnd.always_on = policy.dnd.always_on;
    }
    if (typeof policy.dnd.start === 'string' && policy.dnd.start) {
      next.dnd.start = policy.dnd.start;
    }
    if (typeof policy.dnd.end === 'string' && policy.dnd.end) {
      next.dnd.end = policy.dnd.end;
    }
  }

  next.channel_controls = normalizePolicyControl(policy.channel_controls, true);

  const policyFamilyControls = policy.family_controls;
  if (policyFamilyControls && typeof policyFamilyControls === 'object') {
    for (const [familyKey, familyControl] of Object.entries(policyFamilyControls)) {
      if (!Object.prototype.hasOwnProperty.call(defaultPolicyFamilies, familyKey)) {
        continue;
      }
      next.family_controls[familyKey] = normalizePolicyControl(
        familyControl,
        next.family_controls[familyKey]?.desktop ?? true
      );
    }
  }

  const policyEventControls = policy.event_controls;
  if (policyEventControls && typeof policyEventControls === 'object') {
    for (const [eventKey, eventControl] of Object.entries(policyEventControls)) {
      if (!Object.prototype.hasOwnProperty.call(defaultPolicyEvents, eventKey)) {
        continue;
      }
      next.event_controls[eventKey] = normalizePolicyControl(
        eventControl,
        next.event_controls[eventKey]?.desktop ?? true
      );
    }
  }

  return next;
}

function buildPolicyPayload(policyDraft) {
  const normalized = normalizePolicyDraft(policyDraft);
  return {
    muted_until: normalized.muted_until,
    snooze_until: normalized.snooze_until,
    dnd: {
      enabled: Boolean(normalized.dnd.enabled),
      always_on: Boolean(normalized.dnd.always_on),
      start: normalized.dnd.start || '22:00',
      end: normalized.dnd.end || '07:00',
    },
    channel_controls: {
      desktop: Boolean(normalized.channel_controls?.desktop ?? true),
    },
    family_controls: Object.fromEntries(
      Object.entries(normalized.family_controls || {}).map(([familyKey, familyControl]) => [
        familyKey,
        { desktop: Boolean(familyControl?.desktop ?? true) },
      ])
    ),
    event_controls: Object.fromEntries(
      Object.entries(normalized.event_controls || {}).map(([eventKey, eventControl]) => [
        eventKey,
        { desktop: Boolean(eventControl?.desktop ?? true) },
      ])
    ),
  };
}


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

function shouldFallbackToDirectApi(error) {
  return !error?.response;
}

async function requestNotificationSettings(userId) {
  try {
    return await notificationsService.getSettings(userId);
  } catch (error) {
    if (!shouldFallbackToDirectApi(error)) {
      throw error;
    }
    const response = await api.get(`/notifications/settings/${userId}`);
    return response.data;
  }
}

async function persistNotificationSettings(userId, payload) {
  try {
    return await notificationsService.updateSettings(userId, payload);
  } catch (error) {
    if (!shouldFallbackToDirectApi(error)) {
      throw error;
    }
    const response = await api.put(`/notifications/settings/${userId}`, payload);
    return response.data;
  }
}

async function requestNotificationPolicy(userId) {
  try {
    const payload = await notificationsService.getPolicy(userId);
    return payload?.policy || {};
  } catch (error) {
    if (!shouldFallbackToDirectApi(error)) {
      throw error;
    }
    const response = await api.get(`/notifications/settings/${userId}/policy`);
    return response?.data?.policy || {};
  }
}

async function persistNotificationPolicy(userId, payload) {
  try {
    const response = await notificationsService.updatePolicy(userId, payload);
    return response?.policy || payload;
  } catch (error) {
    if (!shouldFallbackToDirectApi(error)) {
      throw error;
    }
    const response = await api.put(`/notifications/settings/${userId}/policy`, payload);
    return response?.data?.policy || payload;
  }
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

  const request = requestNotificationSettings(userId)
    .then((response) => rememberNotificationSettings(userId, response))
    .finally(() => {
      notificationSettingsRequests.delete(userId);
    });

  notificationSettingsRequests.set(userId, request);
  return request;
}

function getInitialDraft(settings) {
  return settings ? { ...settings } : null;
}

function formatSavedAt(value, t) {
  if (!value) {
    return t('misc.np_not_saved_yet');
  }

  const time = value.toLocaleTimeString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
  });
  return t('misc.np_saved_at', { time });
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
              boxShadow: 'var(--mac-shadow-md)',
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
      className="theme-soft-surface"
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto',
        gap: 16,
        alignItems: 'center',
        padding: '14px 16px',
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
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
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [lastSavedAt, setLastSavedAt] = useState(null);
  const [userId, setUserId] = useState(null);
  const [settings, setSettings] = useState(null);
  const [draft, setDraft] = useState(null);
  const [policyLoading, setPolicyLoading] = useState(false);
  const [policyError, setPolicyError] = useState('');
  const [policyLoaded, setPolicyLoaded] = useState(false);
  const [policySettings, setPolicySettings] = useState(null);
  const [policyDraft, setPolicyDraft] = useState(null);

  useEffect(() => {
    void loadSettings();
  }, []);

  const hasSettingsChanges = Boolean(
    settings &&
    draft &&
    JSON.stringify(settings) !== JSON.stringify(draft)
  );
  const hasPolicyChanges = Boolean(
    policyLoaded &&
    policySettings &&
    policyDraft &&
    JSON.stringify(policySettings) !== JSON.stringify(policyDraft)
  );
  const hasChanges = hasSettingsChanges || hasPolicyChanges;

  async function loadSettings({ force = false } = {}) {
    try {
      setLoading(true);
      setError('');
      setSuccess('');
      setPolicyError('');
      setPolicyLoaded(false);
      setPolicySettings(null);
      setPolicyDraft(null);

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
      setError(err?.response?.data?.detail || t('misc.np_load_error'));
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

  function updatePolicyDraft(updater) {
    setPolicyDraft((prev) => {
      const base = normalizePolicyDraft(prev || policySettings || createDefaultPolicyDraft());
      return updater(base);
    });
    setSuccess('');
    setPolicyError('');
  }

  async function loadPolicy({ force = false } = {}) {
    if (!userId) {
      return;
    }

    if (policyLoading) {
      return;
    }

    if (!force && policyLoaded && policyDraft) {
      return;
    }

    try {
      setPolicyLoading(true);
      setPolicyError('');

      const policy = await requestNotificationPolicy(userId);
      const normalizedPolicy = normalizePolicyDraft(policy || {});
      setPolicySettings(cloneValue(normalizedPolicy));
      setPolicyDraft(cloneValue(normalizedPolicy));
      setPolicyLoaded(true);
      logger.info('[FIX:PROFILE] Loaded notification runtime policy', { userId });
    } catch (err) {
      logger.warn('[FIX:PROFILE] Failed to load notification runtime policy', err);
      setPolicyError(
        err?.response?.data?.detail ||
          t('misc.np_load_policy_error')
      );
    } finally {
      setPolicyLoading(false);
    }
  }

  function handleReset() {
    if (!settings) {
      return;
    }
    setDraft(getInitialDraft(settings));
    if (policyLoaded && policySettings) {
      setPolicyDraft(cloneValue(policySettings));
    }
    setSuccess('');
    setError('');
    setPolicyError('');
  }

  async function handleSave() {
    if (!draft || !userId) {
      return;
    }

    if (!hasChanges) {
      return;
    }

    const savedParts = [];

    try {
      setSaving(true);
      setError('');
      setSuccess('');
      setPolicyError('');

      if (hasSettingsChanges) {
        const updatedSettings = await persistNotificationSettings(userId, draft);
        const nextSettings = rememberNotificationSettings(userId, updatedSettings || draft);
        setSettings(nextSettings);
        setDraft(getInitialDraft(nextSettings));
        savedParts.push(t('misc.np_saved_part_channels'));
      }

      if (policyLoaded && policyDraft && hasPolicyChanges) {
        const policyPayload = buildPolicyPayload(policyDraft);
        const updatedPolicy = await persistNotificationPolicy(userId, policyPayload);
        const nextPolicy = normalizePolicyDraft(updatedPolicy || policyPayload);
        setPolicySettings(cloneValue(nextPolicy));
        setPolicyDraft(cloneValue(nextPolicy));
        savedParts.push(t('misc.np_saved_part_policy'));
      }

      setLastSavedAt(new Date());
      setSuccess(
        savedParts.length > 1
          ? t('misc.np_saved_combined', { parts: savedParts.join(' + ') })
          : t('misc.np_saved_default')
      );
      logger.info('[FIX:PROFILE] Saved notification preferences', { userId });
    } catch (err) {
      logger.error('Failed to save settings:', err);
      if (savedParts.length > 0) {
        setError(
          t('misc.np_partial_save_error', { parts: savedParts.join(' + ') })
        );
      } else {
        setError(err?.response?.data?.detail || t('misc.np_save_error'));
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div style={{ opacity: 0.7 }}>{t('misc.np_loading')}</div>;
  }

  if (!draft) {
    return (
      <div style={{ display: 'grid', gap: 16 }}>
        <Alert severity="error">
          {error || t('misc.np_load_error')}
        </Alert>
        <div>
          <Button
            variant="outline"
            onClick={() => loadSettings({ force: true })}
            startIcon={<RefreshCw size={16} />}
          >
            {t('misc.np_retry_load')}
          </Button>
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
              <CardTitle>{t('misc.np_channels_title')}</CardTitle>
              <div style={{ marginTop: 6, fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                {t('misc.np_channels_desc')}
              </div>
              <div style={{ marginTop: 8, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                {hasChanges ? t('misc.np_unsaved_changes') : formatSavedAt(lastSavedAt, t)}
              </div>
            </div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <Button
                variant="outline"
                onClick={() => loadSettings({ force: true })}
                disabled={saving}
                startIcon={<RefreshCw size={16} />}
              >
                {t('misc.np_refresh')}
              </Button>
              <Button
                variant="ghost"
                onClick={handleReset}
                disabled={!hasChanges || saving}
                startIcon={<RotateCcw size={16} />}
              >
                {t('misc.np_reset')}
              </Button>
              <Button
                variant="primary"
                onClick={handleSave}
                disabled={!hasChanges}
                loading={saving}
                startIcon={<Save size={16} />}
              >
                {t('misc.np_save_settings')}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent style={{ display: 'grid', gap: 12 }}>
          {error && <Alert severity="error">{error}</Alert>}
          {success && <Alert severity="success">{success}</Alert>}
          {!error && !success && hasChanges && (
            <Alert severity="info">
              {t('misc.np_apply_hint')}
            </Alert>
          )}
        </CardContent>
      </Card>

      {notificationSections.map((section) => (
        <NotificationChannelCard
          key={section.key}
          accent={section.accent}
          description={t(section.descriptionKey)}
          icon={section.icon}
          note={section.noteKey ? t(section.noteKey) : undefined}
          title={t(section.titleKey)}
        >
          {section.fields.map((field) => (
            <PreferenceRow
              key={field.key}
              checked={Boolean(draft[field.key])}
              description={t(field.hintKey)}
              disabled={saving}
              label={t(field.labelKey)}
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
                background: accentGradients.warning,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                flexShrink: 0,
                boxShadow: '0 14px 28px color-mix(in srgb, var(--mac-warning), transparent 76%)',
              }}
            >
              <Clock3 size={18} />
            </div>
            <div>
              <CardTitle>{t('misc.np_time_rules_title')}</CardTitle>
              <div style={{ marginTop: 6, fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                {t('misc.np_time_rules_desc')}
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent style={{ display: 'grid', gap: 16 }}>
          {generalFields.map((field) => (
            <div
              key={field.key}
              className="theme-soft-surface"
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr minmax(120px, 180px)',
                gap: 16,
                alignItems: 'center',
                padding: '14px 16px',
              }}
            >
              <div>
                <div style={{ fontSize: 14, fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                  {t(field.labelKey)}
                </div>
                <div style={{ marginTop: 4, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                  {t(field.descriptionKey)}
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Input
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
                {field.suffixKey && (
                  <span style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                    {t(field.suffixKey)}
                  </span>
                )}
              </div>
            </div>
          ))}

          <PreferenceRow
            checked={Boolean(draft.weekend_notifications)}
            description={t('misc.np_weekend_hint')}
            disabled={saving}
            label={t('misc.np_weekend_label')}
            onChange={(nextValue) => updateDraft('weekend_notifications', nextValue)}
          />
        </CardContent>
      </Card>

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
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <div
                style={{
                  width: 42,
                  height: 42,
                  borderRadius: 14,
                  background: accentGradients.purple,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  flexShrink: 0,
                  boxShadow: 'var(--mac-shadow-md)',
                }}
              >
                <Moon size={18} />
              </div>
              <div>
                <CardTitle>Anti-noise policy</CardTitle>
                <div style={{ marginTop: 6, fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                  {t('misc.np_policy_desc')}
                </div>
              </div>
            </div>

            <Button
              variant="outline"
              onClick={() => loadPolicy({ force: true })}
              disabled={saving || policyLoading || !userId}
              startIcon={<RefreshCw size={16} />}
            >
              {policyLoading
                ? t('misc.np_policy_loading')
                : policyLoaded
                  ? t('misc.np_policy_refresh')
                  : t('misc.np_policy_load')}
            </Button>
          </div>
        </CardHeader>
        <CardContent style={{ display: 'grid', gap: 16 }}>
          {policyError && <Alert severity="warning">{policyError}</Alert>}

          {!policyLoaded && (
            <Alert severity="info">
              {t('misc.np_policy_block_hint')}
            </Alert>
          )}

          {policyLoaded && policyDraft && (
            <>
              <div
                className="theme-soft-surface"
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr minmax(180px, 240px)',
                  gap: 16,
                  alignItems: 'center',
                  padding: '14px 16px',
                }}
              >
                <div>
                  <div style={{ fontSize: 14, fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                    {t('misc.np_muted_until_label')}
                  </div>
                  <div style={{ marginTop: 4, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                    {t('misc.np_muted_until_hint')}
                  </div>
                </div>
                <Input
                  type="datetime-local"
                  value={toDateTimeLocalValue(policyDraft.muted_until)}
                  disabled={saving}
                  onChange={(event) => {
                    const rawValue = event.target.value;
                    updatePolicyDraft((prev) => ({
                      ...prev,
                      muted_until: rawValue ? new Date(rawValue).toISOString() : null,
                    }));
                  }}
                />
              </div>

              <div
                className="theme-soft-surface"
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr minmax(180px, 240px)',
                  gap: 16,
                  alignItems: 'center',
                  padding: '14px 16px',
                }}
              >
                <div>
                  <div style={{ fontSize: 14, fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                    {t('misc.np_snooze_until_label')}
                  </div>
                  <div style={{ marginTop: 4, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                    {t('misc.np_snooze_until_hint')}
                  </div>
                </div>
                <Input
                  type="datetime-local"
                  value={toDateTimeLocalValue(policyDraft.snooze_until)}
                  disabled={saving}
                  onChange={(event) => {
                    const rawValue = event.target.value;
                    updatePolicyDraft((prev) => ({
                      ...prev,
                      snooze_until: rawValue ? new Date(rawValue).toISOString() : null,
                    }));
                  }}
                />
              </div>

              <PreferenceRow
                checked={Boolean(policyDraft.channel_controls?.desktop ?? true)}
                description={t('misc.np_realtime_desktop_hint')}
                disabled={saving}
                label={t('misc.np_realtime_desktop_label')}
                onChange={(nextValue) =>
                  updatePolicyDraft((prev) => ({
                    ...prev,
                    channel_controls: {
                      ...(prev.channel_controls || {}),
                      desktop: nextValue,
                    },
                  }))
                }
              />

              <PreferenceRow
                checked={Boolean(policyDraft.dnd?.enabled)}
                description={t('misc.np_dnd_hint')}
                disabled={saving}
                label="Do Not Disturb"
                onChange={(nextValue) =>
                  updatePolicyDraft((prev) => ({
                    ...prev,
                    dnd: {
                      ...(prev.dnd || {}),
                      enabled: nextValue,
                    },
                  }))
                }
              />

              <PreferenceRow
                checked={Boolean(policyDraft.dnd?.always_on)}
                description={t('misc.np_dnd_always_on_hint')}
                disabled={saving || !policyDraft.dnd?.enabled}
                label={t('misc.np_dnd_always_on_label')}
                onChange={(nextValue) =>
                  updatePolicyDraft((prev) => ({
                    ...prev,
                    dnd: {
                      ...(prev.dnd || {}),
                      always_on: nextValue,
                    },
                  }))
                }
              />

              <div
                className="theme-soft-surface"
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr minmax(180px, 240px)',
                  gap: 16,
                  alignItems: 'center',
                  padding: '14px 16px',
                }}
              >
                <div>
                  <div style={{ fontSize: 14, fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                    {t('misc.np_dnd_window_label')}
                  </div>
                  <div style={{ marginTop: 4, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                    {t('misc.np_dnd_window_hint')}
                  </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                  <Input
                    type="time"
                    value={policyDraft.dnd?.start || '22:00'}
                    disabled={saving || !policyDraft.dnd?.enabled || policyDraft.dnd?.always_on}
                    onChange={(event) =>
                      updatePolicyDraft((prev) => ({
                        ...prev,
                        dnd: {
                          ...(prev.dnd || {}),
                          start: event.target.value || '22:00',
                        },
                      }))
                    }
                  />
                  <Input
                    type="time"
                    value={policyDraft.dnd?.end || '07:00'}
                    disabled={saving || !policyDraft.dnd?.enabled || policyDraft.dnd?.always_on}
                    onChange={(event) =>
                      updatePolicyDraft((prev) => ({
                        ...prev,
                        dnd: {
                          ...(prev.dnd || {}),
                          end: event.target.value || '07:00',
                        },
                      }))
                    }
                  />
                </div>
              </div>

              {policyFamilyFields.map((family) => (
                <PreferenceRow
                  key={family.key}
                  checked={Boolean(policyDraft.family_controls?.[family.key]?.desktop ?? true)}
                  description={t(family.hintKey)}
                  disabled={saving}
                  label={`Realtime: ${t(family.labelKey)}`}
                  onChange={(nextValue) =>
                    updatePolicyDraft((prev) => ({
                      ...prev,
                      family_controls: {
                        ...(prev.family_controls || {}),
                        [family.key]: {
                          ...(prev.family_controls?.[family.key] || {}),
                          desktop: nextValue,
                        },
                      },
                    }))
                  }
                />
              ))}

              {policyEventFields.map((eventField) => (
                <PreferenceRow
                  key={eventField.key}
                  checked={Boolean(policyDraft.event_controls?.[eventField.key]?.desktop ?? true)}
                  description={t(eventField.hintKey)}
                  disabled={saving}
                  label={`Realtime: ${t(eventField.labelKey)}`}
                  onChange={(nextValue) =>
                    updatePolicyDraft((prev) => ({
                      ...prev,
                      event_controls: {
                        ...(prev.event_controls || {}),
                        [eventField.key]: {
                          ...(prev.event_controls?.[eventField.key] || {}),
                          desktop: nextValue,
                        },
                      },
                    }))
                  }
                />
              ))}
            </>
          )}
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
            <div style={{ fontSize: 14, fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
              {t('misc.np_summary_title')}
            </div>
            <div style={{ marginTop: 4, fontSize: 12, color: 'var(--mac-text-secondary)' }}>
              {hasChanges
                ? t('misc.np_summary_unsaved')
                : formatSavedAt(lastSavedAt, t)}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Button
              variant="ghost"
              onClick={handleReset}
              disabled={!hasChanges || saving}
              startIcon={<RotateCcw size={16} />}
            >
              {t('misc.np_reset_changes')}
            </Button>
            <Button
              variant="primary"
              onClick={handleSave}
              disabled={!hasChanges}
              loading={saving}
              startIcon={<Bell size={16} />}
            >
              {t('misc.np_apply_settings')}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
