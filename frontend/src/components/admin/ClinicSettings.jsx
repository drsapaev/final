import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import logger from '../../utils/logger';
import { 
  Building2, 
  MapPin, 
  Phone, 
  Mail, 
  Clock, 
  Globe, 
  Upload,
  Save, 
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Image
} from 'lucide-react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSInput, 
  MacOSSelect,
  MacOSTextarea
} from '../ui/macos';

const ClinicSettings = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState({
    clinic_name: 'Programma Clinic',
    address: '',
    phone: '',
    email: '',
    timezone: 'Asia/Tashkent',
    logo_url: '/static/logo.png'
  });
  const [logoFile, setLogoFile] = useState(null);
  const [logoPreview, setLogoPreview] = useState(null);
  const [message, setMessage] = useState({ type: '', text: '' });

  // Список часовых поясов
  const timezones = [
    { value: 'Asia/Tashkent', label: 'Ташкент (UTC+5)' },
    { value: 'Asia/Almaty', label: 'Алматы (UTC+6)' },
    { value: 'Europe/Moscow', label: 'Москва (UTC+3)' },
    { value: 'Asia/Dubai', label: 'Дубай (UTC+4)' },
    { value: 'UTC', label: 'UTC (UTC+0)' }
  ];

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/clinic/settings', {
        params: { category: 'clinic' }
      });

      const data = response.data;
      const settingsObj = {};
      
      if (Array.isArray(data)) {
        data.forEach(setting => {
          settingsObj[setting.key] = setting.value;
        });
      }
      
      setSettings(prev => ({ ...prev, ...settingsObj }));
    } catch (error) {
      logger.error('Ошибка загрузки настроек:', error);
      setMessage({ type: 'error', text: 'Ошибка загрузки настроек' });
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const handleLogoSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      // Проверяем тип файла
      if (!file.type.startsWith('image/')) {
        setMessage({ type: 'error', text: 'Выберите файл изображения' });
        return;
      }

      // Проверяем размер (макс 5MB)
      if (file.size > 5 * 1024 * 1024) {
        setMessage({ type: 'error', text: 'Размер файла не должен превышать 5MB' });
        return;
      }

      setLogoFile(file);
      
      // Создаем превью
      const reader = new FileReader();
      reader.onload = (e) => {
        setLogoPreview(e.target.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const uploadLogo = async () => {
    if (!logoFile) return null;

    try {
      const formData = new FormData();
      formData.append('file', logoFile);

      const response = await api.post('/admin/clinic/logo', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      return response.data.logo_url;
    } catch (error) {
      logger.error('Ошибка загрузки логотипа:', error);
      throw error;
    }
  };

  const saveSettings = async () => {
    try {
      setSaving(true);
      setMessage({ type: '', text: '' });

      // Сначала загружаем логотип если выбран новый
      let logoUrl = settings.logo_url;
      if (logoFile) {
        logoUrl = await uploadLogo();
      }

      // Подготавливаем настройки для отправки
      const settingsToSave = {
        ...settings,
        logo_url: logoUrl
      };

      await api.put('/admin/clinic/settings', {
        settings: settingsToSave
      });

      setMessage({ type: 'success', text: 'Настройки успешно сохранены' });
      setLogoFile(null);
      setLogoPreview(null);
      
      // Обновляем логотип в настройках
      if (logoUrl !== settings.logo_url) {
        setSettings(prev => ({ ...prev, logo_url: logoUrl }));
      }
    } catch (error) {
      logger.error('Ошибка сохранения:', error);
      setMessage({ type: 'error', text: 'Ошибка сохранения настроек' });
    } finally {
      setSaving(false);
    }
  };

  const resetLogo = () => {
    setLogoFile(null);
    setLogoPreview(null);
  };

  if (loading) {
    return (
      <div style={{ 
        padding: 0,
        backgroundColor: 'var(--mac-bg-primary)'
      }}>
        <MacOSCard style={{ padding: '24px', textAlign: 'center' }}>
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
              Загрузка настроек...
            </span>
          </div>
        </MacOSCard>
      </div>
    );
  }

  return (
    <div style={{ 
      padding: 0,
      backgroundColor: 'var(--mac-bg-primary)'
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
              <Building2 style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
              Настройки клиники
            </h2>
            <p style={{ 
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-sm)',
              margin: 0
            }}>
              Основная информация о медицинском учреждении
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

        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', 
          gap: '24px',
          marginBottom: '24px'
        }}>
          {/* Основная информация */}
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
              <Building2 style={{ width: '20px', height: '20px', color: 'var(--mac-accent-blue)' }} />
              Основная информация
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '8px' 
                }}>
                  Название клиники
                </label>
                <MacOSInput
                  type="text"
                  value={settings.clinic_name || ''}
                  onChange={(e) => handleInputChange('clinic_name', e.target.value)}
                  placeholder="Название медицинского учреждения"
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}>
                  <MapPin style={{ width: '16px', height: '16px' }} />
                  Адрес
                </label>
                <MacOSTextarea
                  value={settings.address || ''}
                  onChange={(e) => handleInputChange('address', e.target.value)}
                  rows={2}
                  placeholder="Полный адрес клиники"
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}>
                  <Phone style={{ width: '16px', height: '16px' }} />
                  Телефон
                </label>
                <MacOSInput
                  type="tel"
                  value={settings.phone || ''}
                  onChange={(e) => handleInputChange('phone', e.target.value)}
                  placeholder="+998 (90) 123-45-67"
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}>
                  <Mail style={{ width: '16px', height: '16px' }} />
                  Email
                </label>
                <MacOSInput
                  type="email"
                  value={settings.email || ''}
                  onChange={(e) => handleInputChange('email', e.target.value)}
                  placeholder="info@clinic.com"
                  style={{ width: '100%' }}
                />
              </div>
            </div>
          </MacOSCard>

          {/* Системные настройки */}
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
              <Globe style={{ width: '20px', height: '20px', color: 'var(--mac-success)' }} />
              Системные настройки
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}>
                  <Clock style={{ width: '16px', height: '16px' }} />
                  Часовой пояс
                </label>
                <MacOSSelect
                  value={settings.timezone || 'Asia/Tashkent'}
                  onChange={(e) => handleInputChange('timezone', e.target.value)}
                  options={timezones}
                  style={{ width: '100%' }}
                />
                <p style={{ 
                  fontSize: 'var(--mac-font-size-xs)', 
                  color: 'var(--mac-text-tertiary)', 
                  marginTop: '4px',
                  margin: '4px 0 0 0'
                }}>
                  Используется для расписания и онлайн-очереди
                </p>
              </div>

              {/* Логотип */}
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)', 
                  marginBottom: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}>
                  <Image style={{ width: '16px', height: '16px' }} />
                  Логотип клиники
                </label>
                
                {/* Текущий логотип */}
                {(settings.logo_url || logoPreview) && (
                  <div style={{ marginBottom: '12px' }}>
                    <div style={{ 
                      width: '128px', 
                      height: '80px', 
                      border: '2px dashed var(--mac-border)', 
                      borderRadius: 'var(--mac-radius-md)', 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      backgroundColor: 'var(--mac-bg-secondary)',
                      padding: '8px'
                    }}>
                      <img
                        src={logoPreview || settings.logo_url}
                        alt="Логотип клиники"
                        style={{ 
                          maxWidth: '100%', 
                          maxHeight: '100%', 
                          objectFit: 'contain' 
                        }}
                      />
                    </div>
                    {logoPreview && (
                      <MacOSButton 
                        variant="outline" 
                        onClick={resetLogo}
                        style={{ 
                          marginTop: '8px',
                          padding: '4px 8px',
                          fontSize: 'var(--mac-font-size-xs)'
                        }}
                      >
                        Отменить
                      </MacOSButton>
                    )}
                  </div>
                )}
                
                {/* Загрузка логотипа */}
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleLogoSelect}
                    style={{ display: 'none' }}
                    id="logo-upload"
                  />
                  <label
                    htmlFor="logo-upload"
                    style={{ 
                      cursor: 'pointer', 
                      display: 'inline-flex', 
                      alignItems: 'center', 
                      padding: '8px 16px', 
                      border: '1px solid var(--mac-border)', 
                      borderRadius: 'var(--mac-radius-md)', 
                      fontSize: 'var(--mac-font-size-sm)', 
                      fontWeight: 'var(--mac-font-weight-medium)', 
                      color: 'var(--mac-text-primary)', 
                      backgroundColor: 'var(--mac-bg-secondary)',
                      transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                    }}
                    onMouseEnter={(e) => {
                      e.target.style.backgroundColor = 'var(--mac-accent-bg)';
                      e.target.style.borderColor = 'var(--mac-accent-blue)';
                    }}
                    onMouseLeave={(e) => {
                      e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
                      e.target.style.borderColor = 'var(--mac-border)';
                    }}
                  >
                    <Upload style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                    Выбрать файл
                  </label>
                </div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-xs)', 
                  color: 'var(--mac-text-tertiary)', 
                  marginTop: '4px',
                  margin: '4px 0 0 0'
                }}>
                  Поддерживаются форматы: JPG, PNG, GIF. Максимальный размер: 5MB
                </p>
              </div>
            </div>
          </MacOSCard>
        </div>
      </MacOSCard>
    </div>
  );
};

export default ClinicSettings;

