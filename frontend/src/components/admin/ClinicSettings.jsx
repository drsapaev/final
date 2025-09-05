import React, { useState, useEffect } from 'react';
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
import { Card, Button, Badge } from '../../design-system/components';

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
      const response = await fetch('/api/v1/admin/clinic/settings?category=clinic', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        const settingsObj = {};
        
        data.forEach(setting => {
          settingsObj[setting.key] = setting.value;
        });
        
        setSettings(prev => ({ ...prev, ...settingsObj }));
      }
    } catch (error) {
      console.error('Ошибка загрузки настроек:', error);
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

      const response = await fetch('/api/v1/admin/clinic/logo', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: formData
      });

      if (response.ok) {
        const result = await response.json();
        return result.logo_url;
      } else {
        throw new Error('Ошибка загрузки логотипа');
      }
    } catch (error) {
      console.error('Ошибка загрузки логотипа:', error);
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

      const response = await fetch('/api/v1/admin/clinic/settings', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          settings: settingsToSave
        })
      });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Настройки успешно сохранены' });
        setLogoFile(null);
        setLogoPreview(null);
        
        // Обновляем логотип в настройках
        if (logoUrl !== settings.logo_url) {
          setSettings(prev => ({ ...prev, logo_url: logoUrl }));
        }
      } else {
        throw new Error('Ошибка сохранения настроек');
      }
    } catch (error) {
      console.error('Ошибка сохранения:', error);
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
      <Card className="p-8">
        <div className="flex items-center justify-center">
          <RefreshCw className="animate-spin mr-2" size={20} />
          <span>Загрузка настроек...</span>
        </div>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Настройки клиники
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Основная информация о медицинском учреждении
          </p>
        </div>
        
        <div className="flex gap-3">
          <Button variant="outline" onClick={loadSettings} disabled={loading}>
            <RefreshCw size={16} className="mr-2" />
            Обновить
          </Button>
          <Button onClick={saveSettings} disabled={saving}>
            {saving ? (
              <RefreshCw size={16} className="animate-spin mr-2" />
            ) : (
              <Save size={16} className="mr-2" />
            )}
            Сохранить
          </Button>
        </div>
      </div>

      {/* Сообщения */}
      {message.text && (
        <div className={`flex items-center p-4 rounded-lg ${
          message.type === 'success' 
            ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
            : 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
        }`}>
          {message.type === 'success' ? (
            <CheckCircle size={20} className="mr-2" />
          ) : (
            <AlertCircle size={20} className="mr-2" />
          )}
          {message.text}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Основная информация */}
        <Card className="p-6">
          <h3 className="text-lg font-medium mb-4 flex items-center">
            <Building2 size={20} className="mr-2 text-blue-600" />
            Основная информация
          </h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Название клиники
              </label>
              <input
                type="text"
                value={settings.clinic_name || ''}
                onChange={(e) => handleInputChange('clinic_name', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                placeholder="Название медицинского учреждения"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <MapPin size={16} className="inline mr-1" />
                Адрес
              </label>
              <textarea
                value={settings.address || ''}
                onChange={(e) => handleInputChange('address', e.target.value)}
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                placeholder="Полный адрес клиники"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Phone size={16} className="inline mr-1" />
                Телефон
              </label>
              <input
                type="tel"
                value={settings.phone || ''}
                onChange={(e) => handleInputChange('phone', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                placeholder="+998 (90) 123-45-67"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Mail size={16} className="inline mr-1" />
                Email
              </label>
              <input
                type="email"
                value={settings.email || ''}
                onChange={(e) => handleInputChange('email', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                placeholder="info@clinic.com"
              />
            </div>
          </div>
        </Card>

        {/* Системные настройки */}
        <Card className="p-6">
          <h3 className="text-lg font-medium mb-4 flex items-center">
            <Globe size={20} className="mr-2 text-green-600" />
            Системные настройки
          </h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Clock size={16} className="inline mr-1" />
                Часовой пояс
              </label>
              <select
                value={settings.timezone || 'Asia/Tashkent'}
                onChange={(e) => handleInputChange('timezone', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              >
                {timezones.map(tz => (
                  <option key={tz.value} value={tz.value}>
                    {tz.label}
                  </option>
                ))}
              </select>
              <p className="text-sm text-gray-500 mt-1">
                Используется для расписания и онлайн-очереди
              </p>
            </div>

            {/* Логотип */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Image size={16} className="inline mr-1" />
                Логотип клиники
              </label>
              
              {/* Текущий логотип */}
              {(settings.logo_url || logoPreview) && (
                <div className="mb-3">
                  <div className="w-32 h-20 border-2 border-dashed border-gray-300 rounded-lg flex items-center justify-center bg-gray-50 dark:bg-gray-800 dark:border-gray-600">
                    <img
                      src={logoPreview || settings.logo_url}
                      alt="Логотип клиники"
                      className="max-w-full max-h-full object-contain"
                    />
                  </div>
                  {logoPreview && (
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={resetLogo}
                      className="mt-2"
                    >
                      Отменить
                    </Button>
                  )}
                </div>
              )}

              {/* Загрузка логотипа */}
              <div className="flex items-center">
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleLogoSelect}
                  className="hidden"
                  id="logo-upload"
                />
                <label
                  htmlFor="logo-upload"
                  className="cursor-pointer inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:hover:bg-gray-600"
                >
                  <Upload size={16} className="mr-2" />
                  Выбрать файл
                </label>
              </div>
              <p className="text-sm text-gray-500 mt-1">
                Поддерживаются форматы: JPG, PNG, GIF. Максимальный размер: 5MB
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default ClinicSettings;