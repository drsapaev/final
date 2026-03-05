import { useEffect, useMemo, useState } from 'react';
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
  MacOSButton,
  MacOSInput,
  MacOSSelect,
  MacOSTextarea,
} from '../components/ui/macos';
import NotificationPreferences from '../components/settings/NotificationPreferences.jsx';
import TwoFactorManager from '../components/security/TwoFactorManager';
import { getState as getAuthState, setProfile as setAuthProfile } from '../stores/auth';
import logger from '../utils/logger';

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

const genderOptions = [
  { value: '', label: 'Не указан' },
  { value: 'male', label: 'Мужской' },
  { value: 'female', label: 'Женский' },
  { value: 'other', label: 'Другой' },
];

const languageOptions = [
  { value: 'ru', label: 'Русский' },
  { value: 'uz', label: 'O`zbekcha' },
  { value: 'en', label: 'English' },
];

const timezoneOptions = [
  { value: 'Asia/Tashkent', label: 'Asia/Tashkent' },
  { value: 'Europe/Moscow', label: 'Europe/Moscow' },
  { value: 'UTC', label: 'UTC' },
];

function formatDateTime(value) {
  if (!value) {
    return 'Не указано';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return 'Не указано';
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
    const response = await api.get('/authentication/profile');
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
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--mac-text-primary)' }}>
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
          fontWeight: 600,
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
  const [profile, setProfile] = useState(null);
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
        label: profile.email_verified ? 'Email подтвержден' : 'Email не подтвержден',
        tone: profile.email_verified ? 'success' : 'warning',
      },
      {
        label: profile.phone_verified ? 'Телефон подтвержден' : 'Телефон не подтвержден',
        tone: profile.phone_verified ? 'success' : 'warning',
      },
      {
        label: profile.two_factor_enabled ? '2FA включена' : '2FA выключена',
        tone: profile.two_factor_enabled ? 'success' : 'info',
      },
      {
        label: profile.is_active ? 'Аккаунт активен' : 'Аккаунт выключен',
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
          setError('Показаны кешированные данные профиля. Лимит backend временно исчерпан.');
          logger.warn('[FIX:PROFILE] Self profile request hit rate limit, using cached auth profile fallback');
          return;
        }
      }

      logger.error('[FIX:PROFILE] Failed to load self profile', err);
      setError(
        err?.response?.data?.detail || 'Не удалось загрузить профиль. Проверьте соединение и повторите попытку.'
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

      const response = await api.put('/authentication/profile', payload);
      const updatedProfile = response.data;

      rememberSelfProfile(updatedProfile);
      setProfile(updatedProfile);
      setDraft(normalizeProfileForDraft(updatedProfile));
      setAuthProfile(updatedProfile);
      setSuccess('Профиль успешно сохранен.');
    } catch (err) {
      logger.error('[FIX:PROFILE] Failed to save self profile', err);
      setError(
        err?.response?.data?.detail || 'Не удалось сохранить профиль. Проверьте поля формы и повторите попытку.'
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div style={{ padding: 24 }}>Загрузка профиля...</div>;
  }

  if (!profile) {
    return (
      <div style={{ maxWidth: 760, margin: '0 auto', padding: '24px 20px' }}>
        <Alert severity="error" style={{ marginBottom: 16 }}>
          {error || 'Профиль не удалось загрузить.'}
        </Alert>
        <MacOSButton onClick={() => loadProfile({ force: true })} startIcon={<RefreshCw size={16} />}>
          Повторить загрузку
        </MacOSButton>
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
                fontWeight: 700,
                boxShadow: '0 18px 36px color-mix(in srgb, var(--mac-accent), transparent 72%)',
              }}
            >
              {profile.full_name?.[0]?.toUpperCase() || profile.username?.[0]?.toUpperCase() || 'U'}
            </div>

            <div style={{ flex: '1 1 280px', minWidth: 240 }}>
              <h1 style={{ margin: '0 0 8px 0', fontSize: 30, lineHeight: 1.1 }}>
                {profile.full_name || profile.username}
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
                      fontWeight: 600,
                      ...(toneChipStyles[badge.tone] || toneChipStyles.info),
                    }}
                  >
                    <BadgeCheck size={14} />
                    {badge.label}
                  </span>
                ))}
              </div>
              <div style={{ color: 'var(--mac-text-secondary)', fontSize: 14 }}>
                {profile.role} · {profile.email || 'Email не указан'}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <MacOSButton
                variant="outline"
                onClick={() => loadProfile({ force: true })}
                disabled={saving}
                startIcon={<RefreshCw size={16} />}
              >
                Обновить
              </MacOSButton>
              <MacOSButton
                variant="primary"
                onClick={handleSaveProfile}
                disabled={!hasChanges}
                loading={saving}
                startIcon={<Save size={16} />}
              >
                Сохранить профиль
              </MacOSButton>
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
              label="Логин"
              value={profile.username}
              accent="linear-gradient(135deg, var(--mac-accent), color-mix(in srgb, var(--mac-accent), white 20%))"
            />
            <ProfileMetaCard
              icon={CalendarDays}
              label="Создан"
              value={formatDateTime(profile.created_at)}
              accent="linear-gradient(135deg, var(--mac-success), color-mix(in srgb, var(--mac-success), white 18%))"
            />
            <ProfileMetaCard
              icon={Clock3}
              label="Последний вход"
              value={formatDateTime(profile.last_login)}
              accent="linear-gradient(135deg, var(--mac-warning), color-mix(in srgb, var(--mac-warning), white 18%))"
            />
            <ProfileMetaCard
              icon={ShieldCheck}
              label="Безопасность"
              value={profile.two_factor_enabled ? '2FA активна' : '2FA не настроена'}
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
          label="Личные данные"
          onClick={() => setActiveTab('info')}
        />
        <ProfileTabButton
          active={activeTab === 'notifications'}
          icon={Bell}
          label="Уведомления"
          onClick={() => setActiveTab('notifications')}
        />
        <ProfileTabButton
          active={activeTab === 'security'}
          icon={ShieldCheck}
          label="Безопасность"
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
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>
                  Основной профиль
                </div>
                <div style={{ fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                  Сначала заполните имя, email и телефон. Остальные поля улучшают карточку
                  пользователя, но не обязательны для базовой работы в системе.
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
                  ? 'Есть несохранённые изменения. После сохранения обновится и профиль в auth store.'
                  : 'Форма синхронизирована с сервером. Можно безопасно переключаться между вкладками.'}
              </div>
            </CardContent>
          </Card>

          <Card shadow="default">
            <CardHeader style={{ paddingBottom: 12 }}>
              <div>
                <CardTitle>Основные данные</CardTitle>
                <div style={{ marginTop: 6, fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                  Эти поля чаще всего видят коллеги и другие модули системы.
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
                <ProfileField label="Полное имя">
                  <MacOSInput
                    value={draft.full_name}
                    onChange={(event) => updateDraft('full_name', event.target.value)}
                    icon={UserRound}
                    placeholder="Как отображать имя в системе"
                  />
                </ProfileField>
                <ProfileField label="Email">
                  <MacOSInput
                    type="email"
                    value={draft.email}
                    onChange={(event) => updateDraft('email', event.target.value)}
                    icon={Mail}
                    placeholder="user@example.com"
                  />
                </ProfileField>
                <ProfileField label="Телефон">
                  <MacOSInput
                    value={draft.phone}
                    onChange={(event) => updateDraft('phone', event.target.value)}
                    icon={Phone}
                    placeholder="+998901234567"
                  />
                </ProfileField>
                <ProfileField label="Дата рождения">
                  <MacOSInput
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
                <CardTitle>Детали профиля</CardTitle>
                <div style={{ marginTop: 6, fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                  Дополнительные сведения для персонализации, локализации и внутреннего профиля.
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
                <ProfileField label="Имя">
                  <MacOSInput
                    value={draft.first_name}
                    onChange={(event) => updateDraft('first_name', event.target.value)}
                    placeholder="Имя"
                  />
                </ProfileField>
                <ProfileField label="Фамилия">
                  <MacOSInput
                    value={draft.last_name}
                    onChange={(event) => updateDraft('last_name', event.target.value)}
                    placeholder="Фамилия"
                  />
                </ProfileField>
                <ProfileField label="Отчество">
                  <MacOSInput
                    value={draft.middle_name}
                    onChange={(event) => updateDraft('middle_name', event.target.value)}
                    placeholder="Отчество"
                  />
                </ProfileField>
                <ProfileField label="Пол">
                  <MacOSSelect
                    value={draft.gender}
                    onChange={(event) => updateDraft('gender', event.target.value)}
                    options={genderOptions}
                  />
                </ProfileField>
                <ProfileField label="Язык интерфейса">
                  <MacOSSelect
                    value={draft.language}
                    onChange={(event) => updateDraft('language', event.target.value)}
                    options={languageOptions}
                  />
                </ProfileField>
                <ProfileField label="Часовой пояс">
                  <MacOSSelect
                    value={draft.timezone}
                    onChange={(event) => updateDraft('timezone', event.target.value)}
                    options={timezoneOptions}
                  />
                </ProfileField>
                <ProfileField label="Национальность">
                  <MacOSInput
                    value={draft.nationality}
                    onChange={(event) => updateDraft('nationality', event.target.value)}
                    icon={Languages}
                    placeholder="Например, Uzbek"
                  />
                </ProfileField>
                <ProfileField label="Сайт">
                  <MacOSInput
                    value={draft.website}
                    onChange={(event) => updateDraft('website', event.target.value)}
                    icon={Globe}
                    placeholder="https://example.com"
                  />
                </ProfileField>
              </div>

              <div style={{ display: 'grid', gap: 16 }}>
                <ProfileField label="URL аватара">
                  <MacOSInput
                    value={draft.avatar_url}
                    onChange={(event) => updateDraft('avatar_url', event.target.value)}
                    icon={Globe}
                    placeholder="https://..."
                  />
                </ProfileField>
                <ProfileField label="О себе">
                  <MacOSTextarea
                    value={draft.bio}
                    onChange={(event) => updateDraft('bio', event.target.value)}
                    placeholder="Краткая информация о пользователе"
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
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>
                  Завершение редактирования
                </div>
                <div style={{ fontSize: 13, color: 'var(--mac-text-secondary)' }}>
                  Верните исходные значения или сохраните изменения без прокрутки к верхней панели.
                </div>
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <MacOSButton
                  variant="ghost"
                  onClick={() => setDraft(normalizeProfileForDraft(profile))}
                  disabled={!hasChanges || saving}
                >
                  Вернуть исходные данные
                </MacOSButton>
                <MacOSButton
                  variant="primary"
                  onClick={handleSaveProfile}
                  disabled={!hasChanges || saving}
                  loading={saving}
                  startIcon={<Save size={16} />}
                >
                  Сохранить изменения
                </MacOSButton>
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
