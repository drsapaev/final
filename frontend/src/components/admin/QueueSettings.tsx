import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect, useCallback } from 'react';
import type { CSSProperties } from 'react';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import {
  Clock,
  Users,
  Hash,
  Settings,
  Save,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  TestTube,
  Heart,
  Scissors,
  Stethoscope,
  QrCode,
  Play,
  Sparkles,
  Smile,
  Activity,
  Package,
  Zap,
  ToggleLeft,
  ToggleRight } from
'lucide-react';
import {
  MacOSCard,
  Button,
  Input,
  Select,
} from '../ui/macos';

const ICON_MAP = {
  'Heart': Heart,
  'Activity': Activity,
  'Sparkles': Sparkles,
  'Smile': Smile,
  'TestTube': TestTube,
  'Stethoscope': Stethoscope,
  'Users': Users,
  'Package': Package,
  'Scissors': Scissors,
  'Zap': Zap
};

const TIMEZONE_OPTIONS = [
  { value: 'Asia/Tashkent', labelKey: 'admin2.qs_tz_tashkent' },
  { value: 'Asia/Almaty', labelKey: 'admin2.qs_tz_almaty' },
  { value: 'Europe/Moscow', labelKey: 'admin2.qs_tz_moscow' },
  { value: 'Asia/Dubai', labelKey: 'admin2.qs_tz_dubai' }
];

const normalizeNumber = (value, fallback) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const getNumberSetting = (collection, key, fallback) => (
  normalizeNumber(collection?.[key], fallback)
);

const normalizeText = (value) => String(value || '').trim().toLowerCase();

const getDoctorDisplayName = (doctor, t) => (
  doctor?.user?.full_name || doctor?.user?.username || t('admin2.qs_doctor_fallback', { id: doctor?.id || '—' })
);

const pickCanonicalDoctorForSpecialty = (doctorsList, specialtyKey) => {
  const specialty = normalizeText(specialtyKey);
  const candidates = (Array.isArray(doctorsList) ? doctorsList : [])
    .filter((doctor) => normalizeText(doctor?.specialty) === specialty)
    .sort((left, right) => {
      const leftScore = [
        left?.active === false ? 1 : 0,
        left?.user ? 0 : 1,
        left?.cabinet ? 0 : 1,
        normalizeNumber(left?.id, Number.MAX_SAFE_INTEGER),
      ];
      const rightScore = [
        right?.active === false ? 1 : 0,
        right?.user ? 0 : 1,
        right?.cabinet ? 0 : 1,
        normalizeNumber(right?.id, Number.MAX_SAFE_INTEGER),
      ];

      for (let index = 0; index < leftScore.length; index += 1) {
        if (leftScore[index] !== rightScore[index]) {
          return leftScore[index] - rightScore[index];
        }
      }

      return 0;
    });

  return {
    doctor: candidates[0] || null,
    candidates,
  };
};

const QueueSettings = () => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [settings, setSettings] = useState({
    timezone: 'Asia/Tashkent',
    queue_start_hour: 7,
    auto_close_time: '09:00',
    start_numbers: {},
    max_per_day: {},
    dev_mode_enabled: false
  });
  const [message, setMessage] = useState({ type: '', text: '' });
  const [testResult, setTestResult] = useState(null);

  // ⭐ SSOT: Загружаем специальности из QueueProfiles API
  const [specialties, setSpecialties] = useState([]);
  const [doctors, setDoctors] = useState([]);

  // Загрузка профилей и докторов
  const loadProfiles = useCallback(async () => {
    try {
      const [profilesRes, doctorsRes] = await Promise.all([
      api.get('/queues/profiles?active_only=true'),
      api.get('/admin/doctors').catch(() => ({ data: [] }))]
      );

      const profiles = profilesRes.data.profiles || [];
      setSpecialties(profiles.map((p) => ({
        key: p.key,
        name: p.title_ru || p.title,
        icon: ICON_MAP[p.icon] || Stethoscope,
        color: p.color || 'var(--mac-text-primary)',
        description: (p.queue_tags || []).join(', ')
      })));

      setDoctors(doctorsRes.data || []);

      logger.info(`Loaded ${profiles.length} queue profiles and ${doctorsRes.data?.length || 0} doctors`);
    } catch (error) {
      logger.error('Error loading profiles:', error);
      // Не устанавливаем fallback данные - показываем пустой список
    }
  }, []);

  useEffect(() => {
    loadProfiles();
    loadSettings();
  }, [loadProfiles]);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/queue/settings');
      const data = response.data || {};
      setSettings({
        timezone: data.timezone || 'Asia/Tashkent',
        queue_start_hour: normalizeNumber(data.queue_start_hour, 7),
        auto_close_time: data.auto_close_time || '09:00',
        start_numbers: data.start_numbers || {},
        max_per_day: data.max_per_day || {},
        dev_mode_enabled: Boolean(data.dev_mode_enabled),
      });
    } catch (error) {
      logger.error('Ошибка загрузки настроек очередей:', error);
      setMessage({ type: 'error', text: t('admin2.qs_load_error') });
    } finally {
      setLoading(false);
    }
  };

  const handleSettingChange = (path, value) => {
    setSettings((prev) => {
      const newSettings = { ...prev };
      const keys = path.split('.');

      if (keys.length === 1) {
        newSettings[keys[0]] = value;
      } else if (keys.length === 2) {
        newSettings[keys[0]] = { ...newSettings[keys[0]], [keys[1]]: value };
      }

      return newSettings;
    });
  };

  const saveSettings = async () => {
    try {
      setSaving(true);
      setMessage({ type: '', text: '' });

      const response = await api.put('/admin/queue/settings', settings);

      setMessage({ type: 'success', text: response.data.message });
      setSettings(response.data.settings);
    } catch (error) {
      logger.error('Ошибка сохранения:', error);
      setMessage({ type: 'error', text: t('admin2.qs_save_error') });
    } finally {
      setSaving(false);
    }
  };

  const testQueueGeneration = async (specialty) => {
    try {
      setTesting(true);
      setTestResult(null);

      // ⭐ SSOT: Выбираем врача детерминированно среди докторов этой специальности.
      const { doctor, candidates } = pickCanonicalDoctorForSpecialty(doctors, specialty);
      const doctorId = doctor?.id;

      if (!doctorId) {
        setMessage({ type: 'error', text: t('admin2.qs_doctor_not_found', { specialty }) });
        setTesting(false);
        return;
      }

      const response = await api.post('/admin/queue/test', {
        doctor_id: doctorId,
        date: new Date().toISOString().split('T')[0]
      });

      setTestResult({
        ...(response.data.test_data || {}),
        selected_doctor_id: doctor.id,
        selected_doctor_name: getDoctorDisplayName(doctor, t),
        selected_doctor_cabinet: doctor.cabinet || t('admin2.qs_not_specified'),
        matched_doctors_count: candidates.length,
      });
      setMessage({
        type: 'success',
        text:
          candidates.length > 1
            ? t('admin2.qs_test_done_multi', { doctor: getDoctorDisplayName(doctor, t), count: candidates.length })
            : t('admin2.qs_test_done'),
      });
    } catch (error) {
      logger.error('Ошибка тестирования:', error);
      setMessage({ type: 'error', text: t('admin2.qs_test_error') });
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="admin-outer-container-p-0">
        <MacOSCard className="admin-card-p-0-text-center">
          <div className="admin-flex-center-justify admin-gap-12">
            <RefreshCw className="admin-icon-32-blue-spin" />
            <span className="admin-span-lg-secondary-med">
              {t('admin2.qs_loading')}
            </span>
          </div>
        </MacOSCard>
      </div>);

  }

  return (
    <div className="admin-outer-container-p-0">
      <MacOSCard className="p-6">
        {/* Заголовок */}
        <div className="admin-header-flex-between-pb-24-border-bottom">
          <div>
            <h2 className="admin-h1-2xl-semi-primary-mb-8-flex">
              <Clock className="admin-icon-32-blue" />
              {t('admin2.qs_title')}
            </h2>
            <p className="admin-p-sm-secondary-m0">
              {t('admin2.qs_subtitle')}
            </p>
          </div>

          <div className="admin-flex-gap-12">
            <Button
              variant="outline"
              onClick={loadSettings}
              disabled={loading}
              className="admin-action-btn">
              
              <RefreshCw className="w-4 h-4" />
              {t('admin2.qs_refresh')}
            </Button>
            <Button
              onClick={saveSettings}
              disabled={saving}
              className="admin-action-btn-primary">
              
              {saving ?
              <RefreshCw className="admin-icon-16-spin" /> :

              <Save className="w-4 h-4" />
              }
              {t('admin2.qs_save')}
            </Button>
          </div>
        </div>

        {/* Сообщения */}
        {message.text &&
        <MacOSCard
          className="admin-dynamic-banner-p-16 mb-6"
          style={{
            '--admin-banner-bg': message.type === 'success' ? 'var(--mac-success-bg)' : 'var(--mac-error-bg)',
            '--admin-banner-border': message.type === 'success' ? 'var(--mac-success-border)' : 'var(--mac-error-border)'
          } as CSSProperties}
        >
            <div className="flex items-center justify-center gap-2">
              {message.type === 'success' ?
            <CheckCircle className="admin-icon-20-success" /> :

            <AlertCircle className="admin-icon-20-error" />
            }
              <span
                className="admin-span-sm-med-dynamic-color"
                style={{ '--admin-span-color': message.type === 'success' ? 'var(--mac-success)' : 'var(--mac-error)'  } as CSSProperties}
              >
                {message.text}
              </span>
            </div>
          </MacOSCard>
        }

        {/* ⭐ Dev Mode Toggle */}
        <MacOSCard
          className="admin-dev-mode-card"
          style={{
            '--admin-card-bg': settings.dev_mode_enabled ? 'var(--mac-error-bg)' : 'var(--mac-bg-secondary)',
            '--admin-card-border': settings.dev_mode_enabled ? 'var(--mac-error-border, color-mix(in srgb, var(--mac-error), transparent 70%))' : 'var(--mac-border)'
          } as CSSProperties}
        >
          <div className="flex items-center justify-between">
            <div className="admin-flex-center-12">
              <Zap
                className="admin-icon-24-dynamic"
                style={{ '--admin-icon-color': settings.dev_mode_enabled ? 'var(--mac-error)' : 'var(--mac-text-tertiary)'  } as CSSProperties}
              />
              <div>
                <div className="admin-span-sm-semi-primary">
                  {t('admin2.qs_dev_mode_title')}
                </div>
                <div className="admin-text-xs-secondary">
                  {settings.dev_mode_enabled ?
                  t('admin2.qs_dev_mode_on') :
                  t('admin2.qs_dev_mode_off')
                  }
                </div>
              </div>
            </div>
            <button
              onClick={() => handleSettingChange('dev_mode_enabled', !settings.dev_mode_enabled)}
              aria-label={settings.dev_mode_enabled ? t('admin2.qs_dev_mode_disable') : t('admin2.qs_dev_mode_enable')}
              className="admin-dev-mode-btn"
              style={{
                '--admin-btn-bg': settings.dev_mode_enabled ? 'var(--mac-error)' : 'var(--mac-bg-tertiary)',
                '--admin-btn-color': settings.dev_mode_enabled ? 'white' : 'var(--mac-text-primary)'
              } as CSSProperties}>
              
              {settings.dev_mode_enabled ?
              <>
                  <ToggleRight className="w-4.5 h-4.5" />
                  {t('admin2.qs_enabled')}
                </> :

              <>
                  <ToggleLeft className="w-4.5 h-4.5" />
                  {t('admin2.qs_disabled')}
                </>
              }
            </button>
          </div>
        </MacOSCard>

        <div className="admin-grid-auto-400-24-mb-24">

          {/* Общие настройки */}
          <MacOSCard className="p-6">
            <h3 className="admin-h3-lg-semi-primary-mb-16-flex">
              <Settings className="admin-icon-20-blue" />
              {t('admin2.qs_general')}
            </h3>

            <div className="flex flex-col gap-4">
              <div>
                <label className="admin-label-flex-center-4-sm-med-primary-mb-8">
                  <Clock className="w-4 h-4" />
                  {t('admin2.qs_start_hour')}
                </label>
                <Select
                  value={Number(settings.queue_start_hour)}
                  onChange={(value: unknown) => handleSettingChange('queue_start_hour', parseInt(String(value), 10))}
                  options={Array.from({ length: 24 }, (_, i) => ({
                    value: i,
                    label: `${String(i).padStart(2, '0')}:00`
                  }))}
                  className="w-full"></Select>
                
                <p className="admin-p-xs-tertiary-mt-4">
                  {t('admin2.qs_start_hour_hint')}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                  {t('admin2.qs_auto_close')}
                </label>
                <Input
                  type="time"
                  value={settings.auto_close_time}
                  onChange={(e) => handleSettingChange('auto_close_time', e.target.value)}
                  className="w-full" />
                
                <p className="admin-p-xs-tertiary-mt-4">
                  {t('admin2.qs_auto_close_hint')}
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                  {t('admin2.qs_timezone')}
                </label>
                <Select
                  value={settings.timezone}
                  onChange={(value) => handleSettingChange('timezone', value)}
                  options={TIMEZONE_OPTIONS.map((o) => ({ value: o.value, label: t(o.labelKey) }))}
                  className="w-full"></Select>
                
              </div>
            </div>
          </MacOSCard>

          {/* Тестирование */}
          <MacOSCard className="p-6">
            <h3 className="admin-h3-lg-semi-primary-mb-16-flex">
              <TestTube className="admin-icon-20-success" />
              {t('admin2.qs_testing')}
            </h3>

            <div className="flex flex-col gap-4">
              <p className="admin-p-sm-secondary-m0">
                {t('admin2.qs_testing_hint')}
              </p>

              {specialties.map((specialty) =>
              <div key={specialty.key} className="admin-specialty-test-row">
                  <div className="admin-flex-center-12">
                    <specialty.icon className="admin-icon-20-blue" />
                    <div>
                      <div className="admin-text-sm-med-primary">
                        {specialty.name}
                      </div>
                      <div className="admin-text-xs-secondary">
                        {specialty.description}
                      </div>
                    </div>
                  </div>
                  <Button
                  variant="outline"
                  onClick={() => testQueueGeneration(specialty.key)}
                  disabled={testing}
                  title={`Test queue generation for ${specialty.name}`}
                  aria-label={`Test queue generation for ${specialty.name}`}
                  className="admin-btn-test-p-6-12-min-w-auto">
                  
                    {testing ?
                  <RefreshCw className="admin-icon-14-spin" /> :

                  <Play className="w-3.5 h-3.5" />
                  }
                  </Button>
                </div>
              )}

              {testResult &&
              <MacOSCard className="admin-card-success-p-16">
                  <h4 className="admin-h4-med-success-mb-8">
                    {t('admin2.qs_result_title')}
                  </h4>
                  <div className="admin-div-xs-success-flex-col-4">
                    <div><strong>{t('admin2.qs_label_token')}</strong> <code className="admin-code-success-xs">{testResult.token?.slice(0, 8)}...</code></div>
                    <div><strong>{t('admin2.qs_label_doctor')}</strong> {testResult.selected_doctor_name || '—'}</div>
                    <div><strong>{t('admin2.qs_label_specialty')}</strong> {testResult.doctor_specialty}</div>
                    <div><strong>{t('admin2.qs_label_doctor_id')}</strong> {testResult.selected_doctor_id || testResult.doctor_id}</div>
                    <div><strong>{t('admin2.qs_label_cabinet')}</strong> {testResult.doctor_cabinet}</div>
                    <div><strong>{t('admin2.qs_label_selected_cabinet')}</strong> {testResult.selected_doctor_cabinet || '—'}</div>
                    <div><strong>{t('admin2.qs_label_start_number')}</strong> {testResult.start_number}</div>
                    <div><strong>{t('admin2.qs_label_max_per_day')}</strong> {testResult.max_per_day}</div>
                    <div><strong>{t('admin2.qs_label_candidates')}</strong> {testResult.matched_doctors_count ?? 0}</div>
                    <div><strong>QR URL:</strong> <code className="admin-code-success-xs">{testResult.qr_url}</code></div>
                  </div>
                </MacOSCard>
              }
            </div>
          </MacOSCard>
        </div>

        {/* Настройки по специальностям */}
        <div className="admin-grid-auto-280-24-mb-24">
          {specialties.map((specialty) =>
          <MacOSCard key={specialty.key} className="admin-card-p-20">
              <h3 className="admin-h3-lg-semi-primary-mb-16-flex">
                <specialty.icon className="admin-icon-20-blue" />
                {specialty.name}
              </h3>

              <div className="flex flex-col gap-4">
                <div>
                  <label className="admin-label-flex-center-4-sm-med-primary-mb-8">
                    <Hash className="w-4 h-4" />
                    {t('admin2.qs_label_start_number_short')}
                </label>
                  <Input
                  type="number"
                  min="1"
                  max="100"
                  value={getNumberSetting(settings.start_numbers, specialty.key, 1)}
                  onChange={(e) => handleSettingChange(`start_numbers.${specialty.key}`, parseInt(e.target.value))}
                  className="w-full" />
                
                  <p className="admin-p-xs-tertiary-mt-4">
                    {t('admin2.qs_start_number_hint')}
                  </p>
                </div>

                <div>
                  <label className="admin-label-flex-center-4-sm-med-primary-mb-8">
                    <Users className="w-4 h-4" />
                    {t('admin2.qs_label_max_per_day_short')}
                </label>
                  <Input
                  type="number"
                  min="1"
                  max="100"
                  value={getNumberSetting(settings.max_per_day, specialty.key, 1)}
                  onChange={(e) => handleSettingChange(`max_per_day.${specialty.key}`, parseInt(e.target.value))}
                  className="w-full" />
                
                  <p className="admin-p-xs-tertiary-mt-4">
                    {t('admin2.qs_max_per_day_hint')}
                  </p>
                </div>

                {/* Текущие настройки */}
                <div className="admin-section-divider-pt-16-border-top">
                  <div className="admin-flex-between-sm">
                    <span className="text-[var(--mac-text-secondary)]">{t('admin2.qs_range_label')}</span>
                    <div className="admin-range-badge">
                      {getNumberSetting(settings.start_numbers, specialty.key, 1)} - {getNumberSetting(settings.start_numbers, specialty.key, 1) + getNumberSetting(settings.max_per_day, specialty.key, 1) - 1}
                    </div>
                  </div>
                </div>
              </div>
            </MacOSCard>
          )}
        </div>

        {/* Информационная панель */}
        <MacOSCard className="admin-card-info-p-24">
          <h3 className="admin-h3-lg-semi-info-mb-12-flex">
            <QrCode className="w-5 h-5" />
            {t('admin2.qs_info_title')}
          </h3>
          <div className="admin-div-sm-info-flex-col-8">
            <p className="admin-m-0">{t('admin2.qs_info_1', { hour: settings.queue_start_hour })}</p>
            <p className="admin-m-0">{t('admin2.qs_info_2')}</p>
            <p className="admin-m-0">{t('admin2.qs_info_3')}</p>
            <p className="admin-m-0">{t('admin2.qs_info_4')}</p>
            <p className="admin-m-0">{t('admin2.qs_info_5')}</p>
          </div>
        </MacOSCard>
      </MacOSCard>
    </div>);

};

export default QueueSettings;
