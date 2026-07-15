import { t } from '../../i18n/adapter';
import { useState, useEffect, useCallback } from 'react';
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
  { value: 'Asia/Tashkent', label: '\u0422\u0430\u0448\u043a\u0435\u043d\u0442 (UTC+5)' },
  { value: 'Asia/Almaty', label: '\u0410\u043b\u043c\u0430\u0442\u044b (UTC+6)' },
  { value: 'Europe/Moscow', label: '\u041c\u043e\u0441\u043a\u0432\u0430 (UTC+3)' },
  { value: 'Asia/Dubai', label: '\u0414\u0443\u0431\u0430\u0439 (UTC+4)' }
];

const normalizeNumber = (value, fallback) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const getNumberSetting = (collection, key, fallback) => (
  normalizeNumber(collection?.[key], fallback)
);

const normalizeText = (value) => String(value || '').trim().toLowerCase();

const getDoctorDisplayName = (doctor) => (
  doctor?.user?.full_name || doctor?.user?.username || `Врач #${doctor?.id || '—'}`
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
      setMessage({ type: 'error', text: 'Ошибка загрузки настроек очередей' });
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
      setMessage({ type: 'error', text: 'Ошибка сохранения настроек очередей' });
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
        setMessage({ type: 'error', text: `Врач для специальности "${specialty}" не найден` });
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
        selected_doctor_name: getDoctorDisplayName(doctor),
        selected_doctor_cabinet: doctor.cabinet || 'Не указан',
        matched_doctors_count: candidates.length,
      });
      setMessage({
        type: 'success',
        text:
          candidates.length > 1
            ? `Тест выполнен: использован врач "${getDoctorDisplayName(doctor)}" из ${candidates.length} кандидатов`
            : 'Тест очереди выполнен успешно',
      });
    } catch (error) {
      logger.error('Ошибка тестирования:', error);
      setMessage({ type: 'error', text: 'Ошибка тестирования очереди' });
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
              Загрузка настроек очередей...
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
              Настройки очередей
            </h2>
            <p className="admin-p-sm-secondary-m0">
              Управление онлайн-очередью и стартовыми номерами
            </p>
          </div>

          <div className="admin-flex-gap-12">
            <Button
              variant="outline"
              onClick={loadSettings}
              disabled={loading}
              className="admin-action-btn">
              
              <RefreshCw className="w-4 h-4" />
              Обновить
            </Button>
            <Button
              onClick={saveSettings}
              disabled={saving}
              className="admin-action-btn-primary">
              
              {saving ?
              <RefreshCw className="admin-icon-16-spin" /> :

              <Save className="w-4 h-4" />
              }
              Сохранить
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
          }}
        >
            <div className="flex items-center justify-center gap-2">
              {message.type === 'success' ?
            <CheckCircle className="admin-icon-20-success" /> :

            <AlertCircle className="admin-icon-20-error" />
            }
              <span
                className="admin-span-sm-med-dynamic-color"
                style={{ '--admin-span-color': message.type === 'success' ? 'var(--mac-success)' : 'var(--mac-error)' }}
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
          }}
        >
          <div className="flex items-center justify-between">
            <div className="admin-flex-center-12">
              <Zap
                className="admin-icon-24-dynamic"
                style={{ '--admin-icon-color': settings.dev_mode_enabled ? 'var(--mac-error)' : 'var(--mac-text-tertiary)' }}
              />
              <div>
                <div className="admin-span-sm-semi-primary">
                  Режим разработки (Dev Mode)
                </div>
                <div className="admin-text-xs-secondary">
                  {settings.dev_mode_enabled ?
                  '⚠️ Временные ограничения QR отключены!' :
                  'Отключает проверку времени для QR-регистрации'
                  }
                </div>
              </div>
            </div>
            <button
              onClick={() => handleSettingChange('dev_mode_enabled', !settings.dev_mode_enabled)}
              aria-label={settings.dev_mode_enabled ? 'Отключить режим разработки очереди' : 'Включить режим разработки очереди'}
              className="admin-dev-mode-btn"
              style={{
                '--admin-btn-bg': settings.dev_mode_enabled ? 'var(--mac-error)' : 'var(--mac-bg-tertiary)',
                '--admin-btn-color': settings.dev_mode_enabled ? 'white' : 'var(--mac-text-primary)'
              }}>
              
              {settings.dev_mode_enabled ?
              <>
                  <ToggleRight className="w-4.5 h-4.5" />
                  Включён
                </> :

              <>
                  <ToggleLeft className="w-4.5 h-4.5" />
                  Выключен
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
              Общие настройки
            </h3>

            <div className="flex flex-col gap-4">
              <div>
                <label className="admin-label-flex-center-4-sm-med-primary-mb-8">
                  <Clock className="w-4 h-4" />
                  Час начала онлайн-очереди
                </label>
                <Select
                  value={Number(settings.queue_start_hour)}
                  onChange={(value) => handleSettingChange('queue_start_hour', parseInt(value, 10))}
                  options={Array.from({ length: 24 }, (_, i) => ({
                    value: i,
                    label: `${String(i).padStart(2, '0')}:00`
                  }))}
                  className="w-full"></Select>
                
                <p className="admin-p-xs-tertiary-mt-4">
                  С этого времени доступна онлайн-запись через QR-код
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                  Время автозакрытия
                </label>
                <Input
                  type="time"
                  value={settings.auto_close_time}
                  onChange={(e) => handleSettingChange('auto_close_time', e.target.value)}
                  className="w-full" />
                
                <p className="admin-p-xs-tertiary-mt-4">
                  Автоматическое закрытие онлайн-записи (опционально)
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--mac-text-secondary)] mb-2">
                  Часовой пояс
                </label>
                <Select
                  value={settings.timezone}
                  onChange={(value) => handleSettingChange('timezone', value)}
                  options={TIMEZONE_OPTIONS}
                  className="w-full"></Select>
                
              </div>
            </div>
          </MacOSCard>

          {/* Тестирование */}
          <MacOSCard className="p-6">
            <h3 className="admin-h3-lg-semi-primary-mb-16-flex">
              <TestTube className="admin-icon-20-success" />
              Тестирование очереди
            </h3>

            <div className="flex flex-col gap-4">
              <p className="admin-p-sm-secondary-m0">
                Протестируйте генерацию QR-кода для каждой специальности
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
                    Результат тестирования:
                  </h4>
                  <div className="admin-div-xs-success-flex-col-4">
                    <div><strong>Токен:</strong> <code className="admin-code-success-xs">{testResult.token?.slice(0, 8)}...</code></div>
                    <div><strong>Врач:</strong> {testResult.selected_doctor_name || '—'}</div>
                    <div><strong>Специальность:</strong> {testResult.doctor_specialty}</div>
                    <div><strong>Врач ID:</strong> {testResult.selected_doctor_id || testResult.doctor_id}</div>
                    <div><strong>Кабинет:</strong> {testResult.doctor_cabinet}</div>
                    <div><strong>Выбранный кабинет:</strong> {testResult.selected_doctor_cabinet || '—'}</div>
                    <div><strong>Стартовый номер:</strong> {testResult.start_number}</div>
                    <div><strong>Лимит в день:</strong> {testResult.max_per_day}</div>
                    <div><strong>Кандидатов:</strong> {testResult.matched_doctors_count ?? 0}</div>
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
                    Стартовый номер
                </label>
                  <Input
                  type="number"
                  min="1"
                  max="100"
                  value={getNumberSetting(settings.start_numbers, specialty.key, 1)}
                  onChange={(e) => handleSettingChange(`start_numbers.${specialty.key}`, parseInt(e.target.value))}
                  className="w-full" />
                
                  <p className="admin-p-xs-tertiary-mt-4">
                    С какого номера начинается онлайн-очередь
                  </p>
                </div>

                <div>
                  <label className="admin-label-flex-center-4-sm-med-primary-mb-8">
                    <Users className="w-4 h-4" />
                    Лимит в день
                </label>
                  <Input
                  type="number"
                  min="1"
                  max="100"
                  value={getNumberSetting(settings.max_per_day, specialty.key, 1)}
                  onChange={(e) => handleSettingChange(`max_per_day.${specialty.key}`, parseInt(e.target.value))}
                  className="w-full" />
                
                  <p className="admin-p-xs-tertiary-mt-4">
                    Максимум онлайн-записей в день
                  </p>
                </div>

                {/* Текущие настройки */}
                <div className="admin-section-divider-pt-16-border-top">
                  <div className="admin-flex-between-sm">
                    <span className="text-[var(--mac-text-secondary)]">Диапазон номеров:</span>
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
            Как работает онлайн-очередь
          </h3>
          <div className="admin-div-sm-info-flex-col-8">
            <p className="admin-m-0">• Пациенты сканируют QR-код с {settings.queue_start_hour}:00 до открытия приема</p>
            <p className="admin-m-0">• Каждый телефон/Telegram может получить только один номер в день</p>
            <p className="admin-m-0">• При повторном запросе возвращается тот же номер</p>
            <p className="admin-m-0">• Кнопка &quot;Открыть прием&quot; в регистратуре закрывает онлайн-набор</p>
            <p className="admin-m-0">• Стартовые номера позволяют избежать конфликтов между специалистами</p>
          </div>
        </MacOSCard>
      </MacOSCard>
    </div>);

};

export default QueueSettings;
