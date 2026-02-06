import React, { useState, useEffect, useCallback } from 'react';
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
  ToggleRight
} from 'lucide-react';
import {
  MacOSCard,
  MacOSButton,
  MacOSInput,
  MacOSSelect,
  MacOSBadge
} from '../ui/macos';

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

  // Icon mapping for profiles
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

  // Загрузка профилей и докторов
  const loadProfiles = useCallback(async () => {
    try {
      const [profilesRes, doctorsRes] = await Promise.all([
        api.get('/queues/profiles?active_only=true'),
        api.get('/admin/doctors').catch(() => ({ data: [] }))
      ]);

      const profiles = profilesRes.data.profiles || [];
      setSpecialties(profiles.map(p => ({
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
      setSettings(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки настроек очередей:', error);
      setMessage({ type: 'error', text: 'Ошибка загрузки настроек очередей' });
    } finally {
      setLoading(false);
    }
  };

  const handleSettingChange = (path, value) => {
    setSettings(prev => {
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

      // ⭐ SSOT: Находим врача по специальности из загруженных данных
      const doctor = doctors.find(d => d.specialty === specialty);
      const doctorId = doctor?.id || doctor?.user_id;

      if (!doctorId) {
        setMessage({ type: 'error', text: `Врач для специальности "${specialty}" не найден` });
        setTesting(false);
        return;
      }

      const response = await api.post('/admin/queue/test', {
        doctor_id: doctorId,
        date: new Date().toISOString().split('T')[0]
      });

      setTestResult(response.data.test_data);
      setMessage({ type: 'success', text: 'Тест очереди выполнен успешно' });
    } catch (error) {
      logger.error('Ошибка тестирования:', error);
      setMessage({ type: 'error', text: 'Ошибка тестирования очереди' });
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div style={{
        padding: 0,
        backgroundColor: 'var(--mac-bg-primary)',
        minHeight: '100vh'
      }}>
        <MacOSCard style={{ padding: 0, textAlign: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px' }}>
            <RefreshCw style={{
              width: '32px',
              height: '32px',
              color: 'var(--mac-accent-blue)',
              animation: 'spin 1s linear infinite'
            }} />
            <span style={{
              fontSize: 'var(--mac-font-size-lg)',
              color: 'var(--mac-text-secondary)',
              fontWeight: 'var(--mac-font-weight-medium)'
            }}>
              Загрузка настроек очередей...
            </span>
          </div>
        </MacOSCard>
      </div>
    );
  }

  return (
    <div style={{
      padding: 0,
      backgroundColor: 'var(--mac-bg-primary)',
      minHeight: '100vh'
    }}>
      <MacOSCard style={{ padding: '24px' }}>
        {/* Заголовок */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '24px',
          paddingBottom: '24px',
          borderBottom: '1px solid var(--mac-border)'
        }}>
          <div>
            <h2 style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              margin: '0 0 8px 0',
              display: 'flex',
              alignItems: 'center',
              gap: '12px'
            }}>
              <Clock style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
              Настройки очередей
            </h2>
            <p style={{
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-sm)',
              margin: 0
            }}>
              Управление онлайн-очередью и стартовыми номерами
            </p>
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <MacOSButton
              variant="outline"
              onClick={loadSettings}
              disabled={loading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px'
              }}
            >
              <RefreshCw style={{ width: '16px', height: '16px' }} />
              Обновить
            </MacOSButton>
            <MacOSButton
              onClick={saveSettings}
              disabled={saving}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                backgroundColor: 'var(--mac-accent-blue)',
                border: 'none',
                padding: '8px 16px'
              }}
            >
              {saving ? (
                <RefreshCw style={{
                  width: '16px',
                  height: '16px',
                  animation: 'spin 1s linear infinite'
                }} />
              ) : (
                <Save style={{ width: '16px', height: '16px' }} />
              )}
              Сохранить
            </MacOSButton>
          </div>
        </div>

        {/* Сообщения */}
        {message.text && (
          <MacOSCard style={{
            padding: '16px',
            marginBottom: '24px',
            backgroundColor: message.type === 'success' ? 'var(--mac-success-bg)' : 'var(--mac-error-bg)',
            border: message.type === 'success' ? '1px solid var(--mac-success-border)' : '1px solid var(--mac-error-border)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {message.type === 'success' ? (
                <CheckCircle style={{ width: '20px', height: '20px', color: 'var(--mac-success)' }} />
              ) : (
                <AlertCircle style={{ width: '20px', height: '20px', color: 'var(--mac-error)' }} />
              )}
              <span style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: message.type === 'success' ? 'var(--mac-success)' : 'var(--mac-error)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}>
                {message.text}
              </span>
            </div>
          </MacOSCard>
        )}

        {/* ⭐ Dev Mode Toggle */}
        <MacOSCard style={{
          padding: '16px 20px',
          marginBottom: '24px',
          backgroundColor: settings.dev_mode_enabled ? 'rgba(239, 68, 68, 0.1)' : 'var(--mac-bg-secondary)',
          border: settings.dev_mode_enabled ? '1px solid rgba(239, 68, 68, 0.3)' : '1px solid var(--mac-border)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Zap style={{
                width: '24px',
                height: '24px',
                color: settings.dev_mode_enabled ? '#EF4444' : 'var(--mac-text-tertiary)'
              }} />
              <div>
                <div style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  color: 'var(--mac-text-primary)'
                }}>
                  Режим разработки (Dev Mode)
                </div>
                <div style={{
                  fontSize: 'var(--mac-font-size-xs)',
                  color: 'var(--mac-text-secondary)'
                }}>
                  {settings.dev_mode_enabled
                    ? '⚠️ Временные ограничения QR отключены!'
                    : 'Отключает проверку времени для QR-регистрации'
                  }
                </div>
              </div>
            </div>
            <button
              onClick={() => handleSettingChange('dev_mode_enabled', !settings.dev_mode_enabled)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 16px',
                borderRadius: '8px',
                border: 'none',
                cursor: 'pointer',
                backgroundColor: settings.dev_mode_enabled ? '#EF4444' : 'var(--mac-bg-tertiary)',
                color: settings.dev_mode_enabled ? 'white' : 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)'
              }}
            >
              {settings.dev_mode_enabled ? (
                <>
                  <ToggleRight style={{ width: '18px', height: '18px' }} />
                  Включён
                </>
              ) : (
                <>
                  <ToggleLeft style={{ width: '18px', height: '18px' }} />
                  Выключен
                </>
              )}
            </button>
          </div>
        </MacOSCard>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
          gap: '24px',
          marginBottom: '24px'
        }}>

          {/* Общие настройки */}
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <Settings style={{ width: '20px', height: '20px', color: 'var(--mac-accent-blue)' }} />
              Общие настройки
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  marginBottom: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}>
                  <Clock style={{ width: '16px', height: '16px' }} />
                  Час начала онлайн-очереди
                </label>
                <MacOSSelect
                  value={settings.queue_start_hour}
                  onChange={(e) => handleSettingChange('queue_start_hour', parseInt(e.target.value))}
                  options={Array.from({ length: 24 }, (_, i) => ({
                    value: i,
                    label: `${String(i).padStart(2, '0')}:00`
                  }))}
                  style={{ width: '100%' }}
                />
                <p style={{
                  fontSize: 'var(--mac-font-size-xs)',
                  color: 'var(--mac-text-tertiary)',
                  marginTop: '4px',
                  margin: '4px 0 0 0'
                }}>
                  С этого времени доступна онлайн-запись через QR-код
                </p>
              </div>

              <div>
                <label style={{
                  display: 'block',
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  marginBottom: '8px'
                }}>
                  Время автозакрытия
                </label>
                <MacOSInput
                  type="time"
                  value={settings.auto_close_time}
                  onChange={(e) => handleSettingChange('auto_close_time', e.target.value)}
                  style={{ width: '100%' }}
                />
                <p style={{
                  fontSize: 'var(--mac-font-size-xs)',
                  color: 'var(--mac-text-tertiary)',
                  marginTop: '4px',
                  margin: '4px 0 0 0'
                }}>
                  Автоматическое закрытие онлайн-записи (опционально)
                </p>
              </div>

              <div>
                <label style={{
                  display: 'block',
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  marginBottom: '8px'
                }}>
                  Часовой пояс
                </label>
                <MacOSSelect
                  value={settings.timezone}
                  onChange={(e) => handleSettingChange('timezone', e.target.value)}
                  options={[
                    { value: 'Asia/Tashkent', label: 'Ташкент (UTC+5)' },
                    { value: 'Asia/Almaty', label: 'Алматы (UTC+6)' },
                    { value: 'Europe/Moscow', label: 'Москва (UTC+3)' },
                    { value: 'Asia/Dubai', label: 'Дубай (UTC+4)' }
                  ]}
                  style={{ width: '100%' }}
                />
              </div>
            </div>
          </MacOSCard>

          {/* Тестирование */}
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              marginBottom: '16px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <TestTube style={{ width: '20px', height: '20px', color: 'var(--mac-success)' }} />
              Тестирование очереди
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)',
                margin: 0
              }}>
                Протестируйте генерацию QR-кода для каждой специальности
              </p>

              {specialties.map(specialty => (
                <div key={specialty.key} style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-md)',
                  backgroundColor: 'var(--mac-bg-secondary)'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <specialty.icon style={{ width: '20px', height: '20px', color: 'var(--mac-accent-blue)' }} />
                    <div>
                      <div style={{
                        fontSize: 'var(--mac-font-size-sm)',
                        fontWeight: 'var(--mac-font-weight-medium)',
                        color: 'var(--mac-text-primary)'
                      }}>
                        {specialty.name}
                      </div>
                      <div style={{
                        fontSize: 'var(--mac-font-size-xs)',
                        color: 'var(--mac-text-secondary)'
                      }}>
                        {specialty.description}
                      </div>
                    </div>
                  </div>
                  <MacOSButton
                    variant="outline"
                    onClick={() => testQueueGeneration(specialty.key)}
                    disabled={testing}
                    style={{
                      padding: '6px 12px',
                      minWidth: 'auto'
                    }}
                  >
                    {testing ? (
                      <RefreshCw style={{
                        width: '14px',
                        height: '14px',
                        animation: 'spin 1s linear infinite'
                      }} />
                    ) : (
                      <Play style={{ width: '14px', height: '14px' }} />
                    )}
                  </MacOSButton>
                </div>
              ))}

              {testResult && (
                <MacOSCard style={{
                  padding: '16px',
                  backgroundColor: 'var(--mac-success-bg)',
                  border: '1px solid var(--mac-success-border)'
                }}>
                  <h4 style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-success)',
                    marginBottom: '8px'
                  }}>
                    Результат тестирования:
                  </h4>
                  <div style={{
                    fontSize: 'var(--mac-font-size-xs)',
                    color: 'var(--mac-success)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px'
                  }}>
                    <div><strong>Токен:</strong> <code style={{
                      backgroundColor: 'var(--mac-success-bg)',
                      padding: '2px 4px',
                      borderRadius: 'var(--mac-radius-sm)',
                      fontSize: 'var(--mac-font-size-xs)'
                    }}>{testResult.token?.slice(0, 8)}...</code></div>
                    <div><strong>Специальность:</strong> {testResult.doctor_specialty}</div>
                    <div><strong>Кабинет:</strong> {testResult.doctor_cabinet}</div>
                    <div><strong>Стартовый номер:</strong> {testResult.start_number}</div>
                    <div><strong>Лимит в день:</strong> {testResult.max_per_day}</div>
                    <div><strong>QR URL:</strong> <code style={{
                      backgroundColor: 'var(--mac-success-bg)',
                      padding: '2px 4px',
                      borderRadius: 'var(--mac-radius-sm)',
                      fontSize: 'var(--mac-font-size-xs)'
                    }}>{testResult.qr_url}</code></div>
                  </div>
                </MacOSCard>
              )}
            </div>
          </MacOSCard>
        </div>

        {/* Настройки по специальностям */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '24px',
          marginBottom: '24px'
        }}>
          {specialties.map(specialty => (
            <MacOSCard key={specialty.key} style={{ padding: '20px' }}>
              <h3 style={{
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                marginBottom: '16px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <specialty.icon style={{ width: '20px', height: '20px', color: 'var(--mac-accent-blue)' }} />
                {specialty.name}
              </h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <label style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}>
                    <Hash style={{ width: '16px', height: '16px' }} />
                    Стартовый номер
                  </label>
                  <MacOSInput
                    type="number"
                    min="1"
                    max="100"
                    value={settings.start_numbers[specialty.key]}
                    onChange={(e) => handleSettingChange(`start_numbers.${specialty.key}`, parseInt(e.target.value))}
                    style={{ width: '100%' }}
                  />
                  <p style={{
                    fontSize: 'var(--mac-font-size-xs)',
                    color: 'var(--mac-text-tertiary)',
                    marginTop: '4px',
                    margin: '4px 0 0 0'
                  }}>
                    С какого номера начинается онлайн-очередь
                  </p>
                </div>

                <div>
                  <label style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}>
                    <Users style={{ width: '16px', height: '16px' }} />
                    Лимит в день
                  </label>
                  <MacOSInput
                    type="number"
                    min="1"
                    max="100"
                    value={settings.max_per_day[specialty.key]}
                    onChange={(e) => handleSettingChange(`max_per_day.${specialty.key}`, parseInt(e.target.value))}
                    style={{ width: '100%' }}
                  />
                  <p style={{
                    fontSize: 'var(--mac-font-size-xs)',
                    color: 'var(--mac-text-tertiary)',
                    marginTop: '4px',
                    margin: '4px 0 0 0'
                  }}>
                    Максимум онлайн-записей в день
                  </p>
                </div>

                {/* Текущие настройки */}
                <div style={{
                  paddingTop: '16px',
                  borderTop: '1px solid var(--mac-border)'
                }}>
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>
                    <span style={{ color: 'var(--mac-text-secondary)' }}>Диапазон номеров:</span>
                    <div style={{
                      backgroundColor: 'var(--mac-bg-secondary)',
                      color: 'var(--mac-text-primary)',
                      padding: '4px 8px',
                      borderRadius: 'var(--mac-radius-full)',
                      fontSize: 'var(--mac-font-size-xs)',
                      fontWeight: 'var(--mac-font-weight-medium)',
                      border: '1px solid var(--mac-border)'
                    }}>
                      {settings.start_numbers[specialty.key]} - {settings.start_numbers[specialty.key] + settings.max_per_day[specialty.key] - 1}
                    </div>
                  </div>
                </div>
              </div>
            </MacOSCard>
          ))}
        </div>

        {/* Информационная панель */}
        <MacOSCard style={{
          padding: '24px',
          backgroundColor: 'var(--mac-info-bg)',
          border: '1px solid var(--mac-info-border)'
        }}>
          <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-info)',
            marginBottom: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <QrCode style={{ width: '20px', height: '20px' }} />
            Как работает онлайн-очередь
          </h3>
          <div style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-info)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px'
          }}>
            <p style={{ margin: 0 }}>• Пациенты сканируют QR-код с {settings.queue_start_hour}:00 до открытия приема</p>
            <p style={{ margin: 0 }}>• Каждый телефон/Telegram может получить только один номер в день</p>
            <p style={{ margin: 0 }}>• При повторном запросе возвращается тот же номер</p>
            <p style={{ margin: 0 }}>• Кнопка &quot;Открыть прием&quot; в регистратуре закрывает онлайн-набор</p>
            <p style={{ margin: 0 }}>• Стартовые номера позволяют избежать конфликтов между специалистами</p>
          </div>
        </MacOSCard>
      </MacOSCard>
    </div>
  );
};

export default QueueSettings;
