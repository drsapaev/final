import { useEffect, useMemo, useState } from 'react';
import type { CSSProperties } from 'react';
import PropTypes from 'prop-types';
import {
  BadgeCheck,
  Bell,
  CalendarDays,
  Clock3,
  Globe,
  Languages,
  Mail,
  Phone,
  RefreshCw,
  Save,
  ShieldCheck,
  UserCircle2,
  UserRound,
} from 'lucide-react';

import { api } from '../api/client';
import {
  Alert,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Input,
  Select,
  Textarea,
} from '../components/ui/macos';
import NotificationPreferences from '../components/settings/NotificationPreferences';
import TwoFactorManager from '../components/security/TwoFactorManager';
import { getState as getAuthState, setProfile as setAuthProfile } from '../stores/auth';
import { getErrorMessage } from '../utils/errorHandler';
import logger from '../utils/logger';
import { useTranslation } from '../i18n/useTranslation';

const SELF_PROFILE_CACHE_MS = 30_000;
let selfProfileCache = null;
let selfProfileCacheAt = 0;
let selfProfilePromise = null;

const editableFields = [
  'full_name',
  'first_name',
  'last_name',
  'middle_name',
  'email',
  'phone',
  'date_of_birth',
  'gender',
  'nationality',
  'language',
  'timezone',
  'website',
  'bio',
  'avatar_url',
];





const timezoneOptions = [
  { value: 'Asia/Tashkent', label: 'Asia/Tashkent' },
  { value: 'Europe/Moscow', label: 'Europe/Moscow' },
  { value: 'UTC', label: 'UTC' },
];

function formatDateTime(value, emptyLabel) {
  if (!value) {
    return emptyLabel;
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return emptyLabel;
  }

  return parsed.toLocaleString('ru-RU');
}

function toDateInputValue(value) {
  if (!value) {
    return '';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return '';
  }

  return parsed.toISOString().slice(0, 10);
}

function normalizeProfileForDraft(profile) {
  return {
    full_name: profile?.full_name || '',
    first_name: profile?.first_name || '',
    last_name: profile?.last_name || '',
    middle_name: profile?.middle_name || '',
    email: profile?.email || '',
    phone: profile?.phone || '',
    date_of_birth: toDateInputValue(profile?.date_of_birth),
    gender: profile?.gender || '',
    nationality: profile?.nationality || '',
    language: profile?.language || 'ru',
    timezone: profile?.timezone || 'Asia/Tashkent',
    website: profile?.website || '',
    bio: profile?.bio || '',
    avatar_url: profile?.avatar_url || '',
  };
}

function buildProfilePayload(draft) {
  const payload = {};

  for (const field of editableFields) {
    const value = draft[field];
    if (field === 'date_of_birth') {
      payload[field] = value ? `${value}T00:00:00` : null;
      continue;
    }

    if (typeof value === 'string') {
      const trimmed = value.trim();
      payload[field] = trimmed || null;
      continue;
    }

    payload[field] = value ?? null;
  }

  return payload;
}

function rememberSelfProfile(profile) {
  selfProfileCache = profile;
  selfProfileCacheAt = Date.now();
  return profile;
}

function getFreshSelfProfileCache() {
  if (!selfProfileCache) {
    return null;
  }

  if (Date.now() - selfProfileCacheAt > SELF_PROFILE_CACHE_MS) {
    return null;
  }

  return selfProfileCache;
}

function getFallbackAuthProfile() {
  const fallbackProfile = getAuthState()?.profile || null;
  if (fallbackProfile) {
    logger.warn('[FIX:PROFILE] Falling back to cached auth profile');
  }
  return fallbackProfile;
}

async function fetchSelfProfile(force = false) {
  const cachedProfile = !force ? getFreshSelfProfileCache() : null;
  if (cachedProfile) {
    logger.info('[FIX:PROFILE] Using cached self profile without extra network request');
    return cachedProfile;
  }

  if (selfProfilePromise) {
    return selfProfilePromise;
  }

  selfProfilePromise = (async () => {
    logger.info('[FIX:PROFILE] Loading self profile from /authentication/profile');
    const response = (await api.get('/authentication/profile')) as import('axios').AxiosResponse<Record<string, unknown>>;
    return rememberSelfProfile(response.data);
  })();

  try {
    return await selfProfilePromise;
  } finally {
    selfProfilePromise = null;
  }
}

export function __resetSelfProfileCacheForTests() {
  selfProfileCache = null;
  selfProfileCacheAt = 0;
  selfProfilePromise = null;
}

function ProfileTabButton({ active, icon: Icon, label, onClick }) {
  return (
    <button
      className={`theme-tab-button ${active ? 'theme-tab-button--active' : ''}`}
      onClick={onClick}
      type="button"
    >
      <Icon size={16} />
      {label}
    </button>
  );
}

ProfileTabButton.propTypes = {
  active: PropTypes.bool.isRequired,
  icon: PropTypes.elementType.isRequired,
  label: PropTypes.string.isRequired,
  onClick: PropTypes.func.isRequired,
};

function ProfileMetaCard({ icon: Icon, label, value, accent }) {
  return (
    <div
      className="theme-soft-surface"
      style={{
        padding: 16,
      }}
    >
      <div
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 36,
          height: 36,
          borderRadius: 12,
          background: accent,
          color: 'white',
          marginBottom: 12,
        }}
      >
        <Icon size={18} />
      </div>
      <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)', marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ fontSize: 14, fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
        {value}
      </div>
    </div>
  );
}

ProfileMetaCard.propTypes = {
  accent: PropTypes.string.isRequired,
  icon: PropTypes.elementType.isRequired,
  label: PropTypes.string.isRequired,
  value: PropTypes.string.isRequired,
};

function ProfileField({ label, children }) {
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <label
        style={{
          fontSize: 13,
          fontWeight: 'var(--mac-font-weight-semibold)',
          color: 'var(--mac-text-secondary)',
        }}
      >
        {label}
      </label>
      {children}
    </div>
  );
}

ProfileField.propTypes = {
  children: PropTypes.node.isRequired,
  label: PropTypes.string.isRequired,
};

export default function UserProfile() {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;

  const genderOptions = [
    { value: '', label: t('misc.up_gender_none') },
    { value: 'male', label: t('misc.up_gender_male') },
    { value: 'female', label: t('misc.up_gender_female') },
    { value: 'other', label: t('misc.up_gender_other') },
  ];

  const languageOptions = [
    { value: 'ru', label: t('misc.up_lang_ru') },
    { value: 'uz', label: 'O`zbekcha' },
    { value: 'en', label: 'English' },
  ];

  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);
  const [draft, setDraft] = useState(() => normalizeProfileForDraft(null));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('info');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const summaryBadges = useMemo(() => {
    if (!profile) {
      return [];
    }

    return [
      {
        label: profile.email_verified ? t('misc.up_email_verified') : t('misc.up_email_not_verified'),
        tone: profile.email_verified ? 'success' : 'warning',
      },
      {
        label: profile.phone_verified ? t('misc.up_phone_verified') : t('misc.up_phone_not_verified'),
        tone: profile.phone_verified ? 'success' : 'warning',
      },
      {
        label: profile.two_factor_enabled ? t('misc.up_2fa_enabled') : t('misc.up_2fa_disabled'),
        tone: profile.two_factor_enabled ? 'success' : 'info',
      },
      {
        label: profile.is_active ? t('misc.up_account_active') : t('misc.up_account_inactive'),
        tone: profile.is_active ? 'success' : 'error',
      },
    ];
  }, [profile]);

  const hasChanges = useMemo(() => {
    if (!profile) {
      return false;
    }

    const original = JSON.stringify(buildProfilePayload(normalizeProfileForDraft(profile)));
    const current = JSON.stringify(buildProfilePayload(draft));
    return original !== current;
  }, [draft, profile]);

  const toneChipStyles = {
    success: {
      background: 'var(--mac-success-bg)',
      color: 'var(--mac-success)',
      border: '1px solid var(--mac-success-border)',
    },
    warning: {
      background: 'var(--mac-warning-bg)',
      color: 'var(--mac-warning)',
      border: '1px solid var(--mac-warning-border)',
    },
    error: {
      background: 'var(--mac-error-bg)',
      color: 'var(--mac-error)',
      border: '1px solid var(--mac-error-border)',
    },
    info: {
      background: 'var(--mac-accent-bg)',
      color: 'var(--mac-accent)',
      border: '1px solid var(--mac-accent-border)',
    },
  };

  useEffect(() => {
    void loadProfile();
  }, []);

  async function loadProfile({ force = false } = {}) {
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const nextProfile = await fetchSelfProfile(force);
      setProfile(nextProfile);
      setDraft(normalizeProfileForDraft(nextProfile));
    } catch (err) {
      if (err?.response?.status === 429) {
        const fallbackProfile = getFallbackAuthProfile();
        if (fallbackProfile) {
          setProfile(fallbackProfile);
          setDraft(normalizeProfileForDraft(fallbackProfile));
          setError(t('misc.up_err_rate_limited'));
          logger.warn('[FIX:PROFILE] Self profile request hit rate limit, using cached auth profile fallback');
          return;
        }
      }

      logger.error('[FIX:PROFILE] Failed to load self profile', err);
      setError(
        getErrorMessage(err, t('misc.up_err_load_profile'))
      );
    } finally {
      setLoading(false);
    }
  }

  function updateDraft(field, value) {
    setDraft((prev) => ({
      ...prev,
      [field]: value,
    }));
    setSuccess('');
  }

  async function handleSaveProfile() {
    setSaving(true);
    setError('');
    setSuccess('');

    try {
      const payload = buildProfilePayload(draft);
      logger.info('[FIX:PROFILE] Saving self profile', {
        changedFields: Object.keys(payload).filter((key) => payload[key] !== buildProfilePayload(normalizeProfileForDraft(profile))[key]),
      });

      const response = (await api.put('/authentication/profile', payload)) as import('axios').AxiosResponse<Record<string, unknown>>;
      const updatedProfile = response.data;

      rememberSelfProfile(updatedProfile);
      setProfile(updatedProfile);
      setDraft(normalizeProfileForDraft(updatedProfile));
      setAuthProfile(updatedProfile);
      setSuccess(t('misc.up_success_profile_saved'));
    } catch (err) {
      logger.error('[FIX:PROFILE] Failed to save self profile', err);
      setError(
        getErrorMessage(err, t('misc.up_err_save_profile'))
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div style={{ padding: 24 }}>{t('misc.up_loading_profile')}</div>;
  }

  if (!profile) {
    return (
      <div style={{ maxWidth: 760, margin: '0 auto', padding: '24px 20px' }}>
        <Alert severity="error" style={{ marginBottom: 16 }}>
          {error || t('misc.up_err_profile_unavailable')}
        </Alert>
        <Button onClick={() => loadProfile({ force: true })} startIcon={<RefreshCw size={16} />}>
          {t('misc.up_btn_retry_load')}
        </Button>
      </div>
    );
  }

  return (
    <div className="theme-page-shell">
      <Card shadow="large" style={{ marginBottom: 24, overflow: 'hidden' }}>
        <div
          style={{
            padding: 24,
            background:
              'radial-gradient(circle at top left, color-mix(in srgb, var(--mac-accent), transparent 82%), transparent 32%), linear-gradient(135deg, color-mix(in srgb, var(--mac-card-bg), white 3%), color-mix(in srgb, var(--mac-bg-secondary), transparent 16%))',
            display: 'grid',
            gap: 24,
          }}
        >
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: 20,
            }}
          >
            <div
              style={{
                width: 84,
                height: 84,
                borderRadius: 24,
                background: 'linear-gradient(135deg, var(--mac-accent), color-mix(in srgb, var(--mac-accent), white 20%))',
                color: 'var(--mac-text-on-accent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 30,
                fontWeight: 'var(--mac-font-weight-bold)',
                boxShadow: '0 18px 36px color-mix(in srgb, var(--mac-accent), transparent 72%)',
              }}
            >
              {profile.full_name?.[0]?.toUpperCase() || profile.username?.[0]?.toUpperCase() || 'U'}
            </div>

            <div style={{ flex: '1 1 280px', minWidth: 240 }}>
              <h1 style={{ margin: '0 0 8px 0', fontSize: 30, lineHeight: 1.1 }}>
                {String(profile.full_name ?? '') || String(profile.username ?? '')}
              </h1>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 10 }}>
                {summaryBadges.map((badge) => (
                  <span
                    key={badge.label}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      borderRadius: 999,
                      padding: '6px 10px',
                      fontSize: 12,
                      fontWeight: 'var(--mac-font-weight-semibold)',
                      ...(toneChipStyles[badge.tone] || toneChipStyles.info),
                    }}
                  >
                    <BadgeCheck size={14} />
                    {badge.label}
                  </span>
                ))}
              </div>
              <div style={{ color: 'var(--mac-text-secondary)', fontSize: 14 }}>
                {String(profile.role ?? '')} · {String(profile.email ?? '') || t('misc.up_email_not_set')}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <Button
                variant="outline"
                onClick={() => loadProfile({ force: true })}
                disabled={saving}
                startIcon={<RefreshCw size={16} />}
              >
                {t('misc.up_btn_refresh')}
              </Button>
              <Button
                variant="primary"
                onClick={handleSaveProfile}
                disabled={!hasChanges}
                loading={saving}
                startIcon={<Save size={16} />}
              >
                {t('misc.up_btn_save_profile')}
              </Button>
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: 12,
            }}
          >
            <ProfileMetaCard
              icon={UserRound}
              label={t('misc.up_label_username')}
              value={String(profile.username ?? '')}
              accent="linear-gradient(135deg, var(--mac-accent), color-mix(in srgb, var(--mac-accent), white 20%))"
            />
            <ProfileMetaCard
              icon={CalendarDays}
              label={t('misc.up_label_created')}
              value={formatDateTime(profile.created_at, t('misc.up_date_not_set'))}
              accent="linear-gradient(135deg, var(--mac-success), color-mix(in srgb, var(--mac-success), white 18%))"
            />
            <ProfileMetaCard
              icon={Clock3}
              label={t('misc.up_label_last_login')}
              value={formatDateTime(profile.last_login, t('misc.up_date_not_set'))}
              accent="linear-gradient(135deg, var(--mac-warning), color-mix(in srgb, var(--mac-warning), white 18%))"
            />
            <ProfileMetaCard
              icon={ShieldCheck}
              label={t('misc.up_label_security')}
              value={profile.two_factor_enabled ? t('misc.up_2fa_active') : t('misc.up_2fa_not_setup')}
              accent="linear-gradient(135deg, var(--mac-accent-purple), color-mix(in srgb, var(--mac-accent), white 12%))"
            />
          </div>
        </div>
      </Card>

      {error && (
        <Alert severity="error" style={{ marginBottom: 16 }}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" style={{ marginBottom: 16 }}>
          {success}
        </Alert>
      )}

      <div className="theme-tab-strip">
        <ProfileTabButton
          active={activeTab === 'info'}
          icon={UserCircle2}
          label={t('misc.up_tab_personal')}
          onClick={() => setActiveTab('info')}
        />
        <ProfileTabButton
          active={activeTab === 'notifications'}
          icon={Bell}
          label={t('misc.up_tab_notifications')}
          onClick={() => setActiveTab('notifications')}
        />
        <ProfileTabButton
          active={activeTab === 'security'}
          icon={ShieldCheck}
          label={t('misc.up_label_security')}
          onClick={() => setActiveTab('security')}
        />
      </div>

      {activeTab === 'info' && (
        <div style={{ display: 'grid', gap: 20 }}>
          <Card shadow="default">
            <CardContent
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                gap: 16,
                alignItems: 'start',
              }}
            >
              <div>
                <div style={{ fontSize: 15, fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 6 }}>
                  {t('misc.up_main_profile_title')}
                </div>
                <div style={{ fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                  {t('misc.up_main_profile_desc')}
                </div>
              </div>
              <div
                className="theme-soft-surface"
                style={{
                  padding: '14px 16px',
                  fontSize: 13,
                  color: 'var(--mac-text-secondary)',
                }}
              >
                {hasChanges
                  ? t('misc.up_changes_unsaved')
                  : t('misc.up_form_synced')}
              </div>
            </CardContent>
          </Card>

          <Card shadow="default">
            <CardHeader style={{ paddingBottom: 12 }}>
              <div>
                <CardTitle>{t('misc.up_card_basic_data')}</CardTitle>
                <div style={{ marginTop: 6, fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                  {t('misc.up_card_basic_data_desc')}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                  gap: 16,
                }}
              >
                <ProfileField label={t('misc.up_label_full_name')}>
                  <Input
                    value={draft.full_name}
                    onChange={(event) => updateDraft('full_name', event.target.value)}
                    icon={UserRound}
                    placeholder={t('misc.up_placeholder_full_name')}
                  />
                </ProfileField>
                <ProfileField label="Email">
                  <Input
                    type="email"
                    value={draft.email}
                    onChange={(event) => updateDraft('email', event.target.value)}
                    icon={Mail}
                    placeholder="user@example.com"
                  />
                </ProfileField>
                <ProfileField label={t('misc.up_label_phone')}>
                  <Input
                    value={draft.phone}
                    onChange={(event) => updateDraft('phone', event.target.value)}
                    icon={Phone}
                    placeholder="+998901234567"
                  />
                </ProfileField>
                <ProfileField label={t('misc.up_label_birth_date')}>
                  <Input
                    type="date"
                    value={draft.date_of_birth}
                    onChange={(event) => updateDraft('date_of_birth', event.target.value)}
                    icon={CalendarDays}
                  />
                </ProfileField>
              </div>
            </CardContent>
          </Card>

          <Card shadow="default">
            <CardHeader style={{ paddingBottom: 12 }}>
              <div>
                <CardTitle>{t('misc.up_card_details')}</CardTitle>
                <div style={{ marginTop: 6, fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                  {t('misc.up_card_details_desc')}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                  gap: 16,
                  marginBottom: 16,
                }}
              >
                <ProfileField label={t('misc.up_label_first_name')}>
                  <Input
                    value={draft.first_name}
                    onChange={(event) => updateDraft('first_name', event.target.value)}
                    placeholder={t('misc.up_placeholder_first_name')}
                  />
                </ProfileField>
                <ProfileField label={t('misc.up_label_last_name')}>
                  <Input
                    value={draft.last_name}
                    onChange={(event) => updateDraft('last_name', event.target.value)}
                    placeholder={t('misc.up_placeholder_last_name')}
                  />
                </ProfileField>
                <ProfileField label={t('misc.up_label_middle_name')}>
                  <Input
                    value={draft.middle_name}
                    onChange={(event) => updateDraft('middle_name', event.target.value)}
                    placeholder={t('misc.up_placeholder_middle_name')}
                  />
                </ProfileField>
                <ProfileField label={t('misc.up_label_gender')}>
                  <Select
                    value={draft.gender}
                    onChange={(event) => updateDraft('gender', event.target.value)}
                    options={genderOptions}
                  />
                </ProfileField>
                <ProfileField label={t('misc.up_label_language')}>
                  <Select
                    value={draft.language}
                    onChange={(event) => updateDraft('language', event.target.value)}
                    options={languageOptions}
                  />
                </ProfileField>
                <ProfileField label={t('misc.up_label_timezone')}>
                  <Select
                    value={draft.timezone}
                    onChange={(event) => updateDraft('timezone', event.target.value)}
                    options={timezoneOptions}
                  />
                </ProfileField>
                <ProfileField label={t('misc.up_label_nationality')}>
                  <Input
                    value={draft.nationality}
                    onChange={(event) => updateDraft('nationality', event.target.value)}
                    icon={Languages}
                    placeholder={t('misc.up_placeholder_nationality')}
                  />
                </ProfileField>
                <ProfileField label={t('misc.up_label_website')}>
                  <Input
                    value={draft.website}
                    onChange={(event) => updateDraft('website', event.target.value)}
                    icon={Globe}
                    placeholder="https://example.com"
                  />
                </ProfileField>
              </div>

              <div style={{ display: 'grid', gap: 16 }}>
                <ProfileField label={t('misc.up_label_avatar_url')}>
                  <Input
                    value={draft.avatar_url}
                    onChange={(event) => updateDraft('avatar_url', event.target.value)}
                    icon={Globe}
                    placeholder="https://..."
                  />
                </ProfileField>
                <ProfileField label={t('misc.up_label_bio')}>
                  <Textarea
                    value={draft.bio}
                    onChange={(event) => updateDraft('bio', event.target.value)}
                    placeholder={t('misc.up_placeholder_bio')}
                    minRows={4}
                    maxRows={8}
                  />
                </ProfileField>
              </div>
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
              <div style={{ minWidth: 240 }}>
                <div style={{ fontSize: 15, fontWeight: 'var(--mac-font-weight-semibold)', marginBottom: 6 }}>
                  {t('misc.up_card_finish_editing')}
                </div>
                <div style={{ fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                  {t('misc.up_card_finish_desc')}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <Button
                  variant="ghost"
                  onClick={() => setDraft(normalizeProfileForDraft(profile))}
                  disabled={!hasChanges || saving}
                >
                  {t('misc.up_btn_reset')}
                </Button>
                <Button
                  variant="primary"
                  onClick={handleSaveProfile}
                  disabled={!hasChanges || saving}
                  loading={saving}
                  startIcon={<Save size={16} />}
                >
                  {t('misc.up_btn_save_changes')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'notifications' && <NotificationPreferences />}

      {activeTab === 'security' && <TwoFactorManager />}
    </div>
  );
}
