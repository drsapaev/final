import { useState, useEffect, useCallback } from 'react';

const useSettings = () => {
  const [settings, setSettings] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('general');

  // Моковые данные для настроек
  const mockSettings = {
    // Общие настройки
    name: 'Медицинский центр "Здоровье"',
    description: 'Современный медицинский центр с полным спектром услуг',
    address: 'ул. Навои, 15',
    city: 'Ташкент',
    country: 'Узбекистан',
    postalCode: '100000',
    phone: '+998 90 123 45 67',
    email: 'info@clinic.uz',
    website: 'https://clinic.uz',
    
    // Рабочее время
    workingHours: {
      monday: { start: '09:00', end: '18:00', isWorking: true },
      tuesday: { start: '09:00', end: '18:00', isWorking: true },
      wednesday: { start: '09:00', end: '18:00', isWorking: true },
      thursday: { start: '09:00', end: '18:00', isWorking: true },
      friday: { start: '09:00', end: '18:00', isWorking: true },
      saturday: { start: '10:00', end: '16:00', isWorking: true },
      sunday: { start: '10:00', end: '14:00', isWorking: false }
    },
    
    // Системные настройки
    timezone: 'Asia/Tashkent',
    currency: 'UZS',
    language: 'ru',
    dateFormat: 'DD.MM.YYYY',
    timeFormat: '24',
    
    // Медицинские настройки
    appointmentDuration: 30,
    maxAppointmentsPerDay: 50,
    allowOnlineBooking: true,
    requirePaymentConfirmation: true,
    autoConfirmAppointments: false,
    
    // Уведомления
    emailNotifications: true,
    smsNotifications: true,
    pushNotifications: true,
    reminderBeforeAppointment: 24,
    
    // Брендинг
    logo: null,
    primaryColor: '#3B82F6',
    secondaryColor: '#10B981',
    accentColor: '#F59E0B',
    
    // Безопасность
    twoFactorEnabled: false,
    twoFactorMethod: 'sms',
    maxSessions: 5,
    sessionTimeout: 30,
    autoLogout: true,
    passwordMinLength: 8,
    passwordRequireUppercase: true,
    passwordRequireNumbers: true,
    passwordRequireSymbols: true,
    passwordExpiryDays: 90,
    allowedIPs: [],
    blockSuspiciousIPs: true,
    maxLoginAttempts: 5,
    lockoutDuration: 15,
    logAllActions: true,
    logRetentionDays: 365,
    alertOnSuspiciousActivity: true,
    autoBackup: true,
    backupFrequency: 'daily',
    backupRetention: 30,
    encryptBackups: true
  };

  // Загрузка настроек
  const loadSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      setSettings(mockSettings);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Сохранение настроек
  const saveSettings = useCallback(async (newSettings) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      setSettings(prev => ({ ...prev, ...newSettings }));
      
      // Имитация успешного сохранения
      console.log('Settings saved:', newSettings);
      
      return newSettings;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Сброс настроек к значениям по умолчанию
  const resetSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      
      setSettings(mockSettings);
      
      return mockSettings;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Экспорт настроек
  const exportSettings = useCallback(async () => {
    try {
      const settingsData = JSON.stringify(settings, null, 2);
      const blob = new Blob([settingsData], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      
      const link = document.createElement('a');
      link.href = url;
      link.download = `clinic-settings-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err);
      throw err;
    }
  }, [settings]);

  // Импорт настроек
  const importSettings = useCallback(async (file) => {
    setLoading(true);
    setError(null);
    
    try {
      const text = await file.text();
      const importedSettings = JSON.parse(text);
      
      // Валидация импортированных настроек
      if (typeof importedSettings !== 'object' || importedSettings === null) {
        throw new Error('Некорректный формат файла настроек');
      }
      
      setSettings(prev => ({ ...prev, ...importedSettings }));
      
      return importedSettings;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Получение настроек по категории
  const getSettingsByCategory = useCallback((category) => {
    const categoryMap = {
      general: ['name', 'description', 'address', 'city', 'country', 'postalCode', 'phone', 'email', 'website'],
      workingHours: ['workingHours'],
      system: ['timezone', 'currency', 'language', 'dateFormat', 'timeFormat'],
      medical: ['appointmentDuration', 'maxAppointmentsPerDay', 'allowOnlineBooking', 'requirePaymentConfirmation', 'autoConfirmAppointments'],
      notifications: ['emailNotifications', 'smsNotifications', 'pushNotifications', 'reminderBeforeAppointment'],
      branding: ['logo', 'primaryColor', 'secondaryColor', 'accentColor'],
      security: ['twoFactorEnabled', 'twoFactorMethod', 'maxSessions', 'sessionTimeout', 'autoLogout', 'passwordMinLength', 'passwordRequireUppercase', 'passwordRequireNumbers', 'passwordRequireSymbols', 'passwordExpiryDays', 'allowedIPs', 'blockSuspiciousIPs', 'maxLoginAttempts', 'lockoutDuration'],
      audit: ['logAllActions', 'logRetentionDays', 'alertOnSuspiciousActivity'],
      backup: ['autoBackup', 'backupFrequency', 'backupRetention', 'encryptBackups']
    };
    
    const fields = categoryMap[category] || [];
    const result = {};
    
    fields.forEach(field => {
      if (settings.hasOwnProperty(field)) {
        result[field] = settings[field];
      }
    });
    
    return result;
  }, [settings]);

  // Валидация настроек
  const validateSettings = useCallback((settingsToValidate) => {
    const errors = {};
    
    // Валидация общих настроек
    if (settingsToValidate.name && !settingsToValidate.name.trim()) {
      errors.name = 'Название клиники обязательно';
    }
    
    if (settingsToValidate.email && !/\S+@\S+\.\S+/.test(settingsToValidate.email)) {
      errors.email = 'Некорректный email';
    }
    
    if (settingsToValidate.phone && !/^\+?[\d\s\-\(\)]+$/.test(settingsToValidate.phone)) {
      errors.phone = 'Некорректный номер телефона';
    }
    
    if (settingsToValidate.website && !/^https?:\/\/.+/.test(settingsToValidate.website)) {
      errors.website = 'Некорректный URL сайта';
    }
    
    // Валидация медицинских настроек
    if (settingsToValidate.appointmentDuration && (settingsToValidate.appointmentDuration < 15 || settingsToValidate.appointmentDuration > 120)) {
      errors.appointmentDuration = 'Длительность приема должна быть от 15 до 120 минут';
    }
    
    if (settingsToValidate.maxAppointmentsPerDay && (settingsToValidate.maxAppointmentsPerDay < 1 || settingsToValidate.maxAppointmentsPerDay > 200)) {
      errors.maxAppointmentsPerDay = 'Максимум записей в день должен быть от 1 до 200';
    }
    
    // Валидация настроек безопасности
    if (settingsToValidate.passwordMinLength && (settingsToValidate.passwordMinLength < 6 || settingsToValidate.passwordMinLength > 32)) {
      errors.passwordMinLength = 'Минимальная длина пароля должна быть от 6 до 32 символов';
    }
    
    if (settingsToValidate.maxLoginAttempts && (settingsToValidate.maxLoginAttempts < 3 || settingsToValidate.maxLoginAttempts > 10)) {
      errors.maxLoginAttempts = 'Максимум попыток входа должен быть от 3 до 10';
    }
    
    return errors;
  }, []);

  // Получение статистики настроек
  const getSettingsStats = useCallback(() => {
    const stats = {
      totalSettings: Object.keys(settings).length,
      configuredSettings: Object.values(settings).filter(value => 
        value !== null && value !== undefined && value !== ''
      ).length,
      securityEnabled: settings.twoFactorEnabled || false,
      notificationsEnabled: settings.emailNotifications || settings.smsNotifications || settings.pushNotifications || false,
      autoBackupEnabled: settings.autoBackup || false
    };
    
    stats.configurationPercentage = Math.round((stats.configuredSettings / stats.totalSettings) * 100);
    
    return stats;
  }, [settings]);

  // Загрузка при монтировании
  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  return {
    settings,
    loading,
    error,
    activeTab,
    setActiveTab,
    loadSettings,
    saveSettings,
    resetSettings,
    exportSettings,
    importSettings,
    getSettingsByCategory,
    validateSettings,
    getSettingsStats,
    refresh: loadSettings
  };
};

export default useSettings;
