import React, { useState, useEffect } from 'react';
import { 
  Shield, 
  Lock, 
  Key, 
  Eye, 
  EyeOff, 
  Save, 
  RefreshCw,
  AlertCircle,
  CheckCircle,
  User,
  Clock,
  Trash2,
  Plus,
  Edit,
  Ban
} from 'lucide-react';
import { Card, Button, Badge } from '../ui/native';

const SecuritySettings = ({ 
  settings = {},
  onSave,
  loading = false
}) => {
  const [formData, setFormData] = useState({
    // Пароль
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
    
    // Двухфакторная аутентификация
    twoFactorEnabled: false,
    twoFactorMethod: 'sms', // sms, email, app
    
    // Сессии
    maxSessions: 5,
    sessionTimeout: 30, // минуты
    autoLogout: true,
    
    // Безопасность
    passwordMinLength: 8,
    passwordRequireUppercase: true,
    passwordRequireNumbers: true,
    passwordRequireSymbols: true,
    passwordExpiryDays: 90,
    
    // IP ограничения
    allowedIPs: [],
    blockSuspiciousIPs: true,
    maxLoginAttempts: 5,
    lockoutDuration: 15, // минуты
    
    // Аудит
    logAllActions: true,
    logRetentionDays: 365,
    alertOnSuspiciousActivity: true,
    
    // Резервное копирование
    autoBackup: true,
    backupFrequency: 'daily', // daily, weekly, monthly
    backupRetention: 30, // дни
    encryptBackups: true
  });

  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState('password');
  const [showPasswords, setShowPasswords] = useState({
    current: false,
    new: false,
    confirm: false
  });

  // Моковые данные для активных сессий
  const [activeSessions] = useState([
    {
      id: 1,
      device: 'Chrome на Windows',
      location: 'Ташкент, Узбекистан',
      ip: '192.168.1.100',
      lastActive: '2024-02-10T15:30:00Z',
      current: true
    },
    {
      id: 2,
      device: 'Safari на iPhone',
      location: 'Ташкент, Узбекистан',
      ip: '192.168.1.101',
      lastActive: '2024-02-10T14:15:00Z',
      current: false
    },
    {
      id: 3,
      device: 'Firefox на Mac',
      location: 'Самарканд, Узбекистан',
      ip: '10.0.0.50',
      lastActive: '2024-02-09T09:45:00Z',
      current: false
    }
  ]);

  // Моковые данные для логов безопасности
  const [securityLogs] = useState([
    {
      id: 1,
      action: 'Вход в систему',
      user: 'admin@clinic.uz',
      ip: '192.168.1.100',
      timestamp: '2024-02-10T15:30:00Z',
      status: 'success',
      details: 'Успешный вход с Chrome на Windows'
    },
    {
      id: 2,
      action: 'Неудачная попытка входа',
      user: 'admin@clinic.uz',
      ip: '192.168.1.105',
      timestamp: '2024-02-10T15:25:00Z',
      status: 'failed',
      details: 'Неверный пароль'
    },
    {
      id: 3,
      action: 'Изменение пароля',
      user: 'admin@clinic.uz',
      ip: '192.168.1.100',
      timestamp: '2024-02-10T14:00:00Z',
      status: 'success',
      details: 'Пароль успешно изменен'
    },
    {
      id: 4,
      action: 'Подозрительная активность',
      user: 'unknown@example.com',
      ip: '203.0.113.1',
      timestamp: '2024-02-10T13:45:00Z',
      status: 'blocked',
      details: 'Множественные неудачные попытки входа'
    }
  ]);

  // Инициализация формы
  useEffect(() => {
    if (settings && Object.keys(settings).length > 0) {
      setFormData(prev => ({ ...prev, ...settings }));
    }
  }, [settings]);

  const validatePasswordForm = () => {
    const newErrors = {};

    if (!formData.currentPassword) {
      newErrors.currentPassword = 'Текущий пароль обязателен';
    }

    if (!formData.newPassword) {
      newErrors.newPassword = 'Новый пароль обязателен';
    } else if (formData.newPassword.length < formData.passwordMinLength) {
      newErrors.newPassword = `Пароль должен содержать минимум ${formData.passwordMinLength} символов`;
    } else if (formData.passwordRequireUppercase && !/[A-Z]/.test(formData.newPassword)) {
      newErrors.newPassword = 'Пароль должен содержать заглавные буквы';
    } else if (formData.passwordRequireNumbers && !/\d/.test(formData.newPassword)) {
      newErrors.newPassword = 'Пароль должен содержать цифры';
    } else if (formData.passwordRequireSymbols && !/[!@#$%^&*(),.?":{}|<>]/.test(formData.newPassword)) {
      newErrors.newPassword = 'Пароль должен содержать специальные символы';
    }

    if (formData.newPassword !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Пароли не совпадают';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (activeTab === 'password' && !validatePasswordForm()) return;

    setIsSubmitting(true);
    try {
      await onSave(formData);
    } catch (error) {
      console.error('Ошибка сохранения настроек безопасности:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: null }));
    }
  };

  const togglePasswordVisibility = (field) => {
    setShowPasswords(prev => ({ ...prev, [field]: !prev[field] }));
  };

  const terminateSession = (sessionId) => {
    // Логика завершения сессии
    console.log('Terminating session:', sessionId);
  };

  const terminateAllOtherSessions = () => {
    // Логика завершения всех других сессий
    console.log('Terminating all other sessions');
  };

  const getStatusIcon = (status) => {
    const iconMap = {
      success: CheckCircle,
      failed: AlertCircle,
      blocked: Ban
    };
    return iconMap[status] || AlertCircle;
  };

  const getStatusColor = (status) => {
    const colorMap = {
      success: 'var(--success-color)',
      failed: 'var(--danger-color)',
      blocked: 'var(--warning-color)'
    };
    return colorMap[status] || 'var(--text-secondary)';
  };

  const getStatusLabel = (status) => {
    const labelMap = {
      success: 'Успешно',
      failed: 'Ошибка',
      blocked: 'Заблокировано'
    };
    return labelMap[status] || status;
  };

  const formatDateTime = (dateString) => {
    return new Date(dateString).toLocaleString('ru-RU');
  };

  const tabs = [
    { id: 'password', label: 'Пароль', icon: Lock },
    { id: 'two-factor', label: '2FA', icon: Shield },
    { id: 'sessions', label: 'Сессии', icon: User },
    { id: 'security', label: 'Безопасность', icon: Key },
    { id: 'audit', label: 'Аудит', icon: Clock }
  ];

  return (
    <div className="space-y-6">
      {/* Вкладки */}
      <div className="border-b" style={{ borderColor: 'var(--border-color)' }}>
        <nav className="flex space-x-8">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
                style={{
                  borderBottomColor: activeTab === tab.id ? 'var(--accent-color)' : 'transparent',
                  color: activeTab === tab.id ? 'var(--accent-color)' : 'var(--text-secondary)'
                }}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Смена пароля */}
        {activeTab === 'password' && (
          <div className="space-y-6">
            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
                Смена пароля
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
                    Текущий пароль *
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                          style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type={showPasswords.current ? 'text' : 'password'}
                      value={formData.currentPassword}
                      onChange={(e) => handleChange('currentPassword', e.target.value)}
                      className={`w-full pl-10 pr-10 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.currentPassword ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.currentPassword ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                      placeholder="Введите текущий пароль"
                    />
                    <button
                      type="button"
                      onClick={() => togglePasswordVisibility('current')}
                      className="absolute right-3 top-1/2 transform -translate-y-1/2"
                      style={{ color: 'var(--text-tertiary)' }}
                    >
                      {showPasswords.current ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {errors.currentPassword && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.currentPassword}
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
                    Новый пароль *
                  </label>
                  <div className="relative">
                    <Key className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                         style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type={showPasswords.new ? 'text' : 'password'}
                      value={formData.newPassword}
                      onChange={(e) => handleChange('newPassword', e.target.value)}
                      className={`w-full pl-10 pr-10 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.newPassword ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.newPassword ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                      placeholder="Введите новый пароль"
                    />
                    <button
                      type="button"
                      onClick={() => togglePasswordVisibility('new')}
                      className="absolute right-3 top-1/2 transform -translate-y-1/2"
                      style={{ color: 'var(--text-tertiary)' }}
                    >
                      {showPasswords.new ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {errors.newPassword && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.newPassword}
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
                    Подтвердите новый пароль *
                  </label>
                  <div className="relative">
                    <Key className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                         style={{ color: 'var(--text-tertiary)' }} />
                    <input
                      type={showPasswords.confirm ? 'text' : 'password'}
                      value={formData.confirmPassword}
                      onChange={(e) => handleChange('confirmPassword', e.target.value)}
                      className={`w-full pl-10 pr-10 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                        errors.confirmPassword ? 'border-red-500' : 'border-gray-300'
                      }`}
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: errors.confirmPassword ? 'var(--danger-color)' : 'var(--border-color)'
                      }}
                      placeholder="Подтвердите новый пароль"
                    />
                    <button
                      type="button"
                      onClick={() => togglePasswordVisibility('confirm')}
                      className="absolute right-3 top-1/2 transform -translate-y-1/2"
                      style={{ color: 'var(--text-tertiary)' }}
                    >
                      {showPasswords.confirm ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                  {errors.confirmPassword && (
                    <p className="text-sm text-red-500 mt-1 flex items-center">
                      <AlertCircle className="w-4 h-4 mr-1" />
                      {errors.confirmPassword}
                    </p>
                  )}
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* Двухфакторная аутентификация */}
        {activeTab === 'two-factor' && (
          <div className="space-y-6">
            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
                Двухфакторная аутентификация
              </h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-lg border" 
                     style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}>
                  <div>
                    <h4 className="font-medium" style={{ color: 'var(--text-primary)' }}>
                      Включить 2FA
                    </h4>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      Дополнительная защита вашего аккаунта
                    </p>
                  </div>
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      checked={formData.twoFactorEnabled}
                      onChange={(e) => handleChange('twoFactorEnabled', e.target.checked)}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                  </label>
                </div>

                {formData.twoFactorEnabled && (
                  <div>
                    <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
                      Метод аутентификации
                    </label>
                    <select
                      value={formData.twoFactorMethod}
                      onChange={(e) => handleChange('twoFactorMethod', e.target.value)}
                      className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      style={{ 
                        background: 'var(--bg-primary)', 
                        color: 'var(--text-primary)',
                        borderColor: 'var(--border-color)'
                      }}
                    >
                      <option value="sms">SMS</option>
                      <option value="email">Email</option>
                      <option value="app">Приложение-аутентификатор</option>
                    </select>
                  </div>
                )}
              </div>
            </Card>
          </div>
        )}

        {/* Активные сессии */}
        {activeTab === 'sessions' && (
          <div className="space-y-6">
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                  Активные сессии
                </h3>
                <Button
                  type="button"
                  variant="outline"
                  onClick={terminateAllOtherSessions}
                  className="text-sm"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Завершить все остальные
                </Button>
              </div>
              
              <div className="space-y-3">
                {activeSessions.map((session) => (
                  <div key={session.id} className="flex items-center justify-between p-4 rounded-lg border" 
                       style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}>
                    <div className="flex items-center space-x-4">
                      <div className="w-10 h-10 rounded-full flex items-center justify-center" 
                           style={{ background: 'var(--accent-color)' }}>
                        <User className="w-5 h-5 text-white" />
                      </div>
                      <div>
                        <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                          {session.device}
                          {session.current && (
                            <Badge variant="success" className="ml-2">Текущая</Badge>
                          )}
                        </p>
                        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                          {session.location} • {session.ip}
                        </p>
                        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                          Последняя активность: {formatDateTime(session.lastActive)}
                        </p>
                      </div>
                    </div>
                    
                    {!session.current && (
                      <button
                        onClick={() => terminateSession(session.id)}
                        className="p-2 hover:bg-red-100 rounded-lg transition-colors"
                        style={{ color: 'var(--danger-color)' }}
                        title="Завершить сессию"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}

        {/* Настройки безопасности */}
        {activeTab === 'security' && (
          <div className="space-y-6">
            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
                Настройки безопасности
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
                    Минимальная длина пароля
                  </label>
                  <input
                    type="number"
                    value={formData.passwordMinLength}
                    onChange={(e) => handleChange('passwordMinLength', parseInt(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: 'var(--border-color)'
                    }}
                    min="6"
                    max="32"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
                    Срок действия пароля (дни)
                  </label>
                  <input
                    type="number"
                    value={formData.passwordExpiryDays}
                    onChange={(e) => handleChange('passwordExpiryDays', parseInt(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: 'var(--border-color)'
                    }}
                    min="30"
                    max="365"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
                    Максимум попыток входа
                  </label>
                  <input
                    type="number"
                    value={formData.maxLoginAttempts}
                    onChange={(e) => handleChange('maxLoginAttempts', parseInt(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: 'var(--border-color)'
                    }}
                    min="3"
                    max="10"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
                    Время блокировки (минуты)
                  </label>
                  <input
                    type="number"
                    value={formData.lockoutDuration}
                    onChange={(e) => handleChange('lockoutDuration', parseInt(e.target.value))}
                    className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    style={{ 
                      background: 'var(--bg-primary)', 
                      color: 'var(--text-primary)',
                      borderColor: 'var(--border-color)'
                    }}
                    min="5"
                    max="60"
                  />
                </div>
              </div>

              <div className="mt-6 space-y-4">
                <div className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    id="passwordRequireUppercase"
                    checked={formData.passwordRequireUppercase}
                    onChange={(e) => handleChange('passwordRequireUppercase', e.target.checked)}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                  />
                  <label htmlFor="passwordRequireUppercase" className="text-sm" style={{ color: 'var(--text-primary)' }}>
                    Требовать заглавные буквы в пароле
                  </label>
                </div>

                <div className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    id="passwordRequireNumbers"
                    checked={formData.passwordRequireNumbers}
                    onChange={(e) => handleChange('passwordRequireNumbers', e.target.checked)}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                  />
                  <label htmlFor="passwordRequireNumbers" className="text-sm" style={{ color: 'var(--text-primary)' }}>
                    Требовать цифры в пароле
                  </label>
                </div>

                <div className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    id="passwordRequireSymbols"
                    checked={formData.passwordRequireSymbols}
                    onChange={(e) => handleChange('passwordRequireSymbols', e.target.checked)}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                  />
                  <label htmlFor="passwordRequireSymbols" className="text-sm" style={{ color: 'var(--text-primary)' }}>
                    Требовать специальные символы в пароле
                  </label>
                </div>

                <div className="flex items-center space-x-3">
                  <input
                    type="checkbox"
                    id="blockSuspiciousIPs"
                    checked={formData.blockSuspiciousIPs}
                    onChange={(e) => handleChange('blockSuspiciousIPs', e.target.checked)}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                  />
                  <label htmlFor="blockSuspiciousIPs" className="text-sm" style={{ color: 'var(--text-primary)' }}>
                    Блокировать подозрительные IP адреса
                  </label>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* Логи безопасности */}
        {activeTab === 'audit' && (
          <div className="space-y-6">
            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
                Логи безопасности
              </h3>
              
              <div className="space-y-3">
                {securityLogs.map((log) => {
                  const StatusIcon = getStatusIcon(log.status);
                  return (
                    <div key={log.id} className="flex items-center justify-between p-4 rounded-lg border" 
                         style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}>
                      <div className="flex items-center space-x-4">
                        <StatusIcon className="w-5 h-5" style={{ color: getStatusColor(log.status) }} />
                        <div>
                          <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                            {log.action}
                          </p>
                          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                            {log.user} • {log.ip}
                          </p>
                          <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                            {formatDateTime(log.timestamp)}
                          </p>
                        </div>
                      </div>
                      
                      <div className="flex items-center space-x-2">
                        <Badge variant={log.status === 'success' ? 'success' : log.status === 'failed' ? 'error' : 'warning'}>
                          {getStatusLabel(log.status)}
                        </Badge>
                        <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                          {log.details}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          </div>
        )}

        {/* Кнопки действий */}
        <div className="flex items-center justify-between pt-6 border-t" style={{ borderColor: 'var(--border-color)' }}>
          <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Настройки безопасности сохраняются автоматически
          </div>
          
          <div className="flex items-center space-x-3">
            <Button
              type="button"
              variant="outline"
              onClick={() => window.location.reload()}
              disabled={isSubmitting}
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Сбросить
            </Button>
            
            <Button
              type="submit"
              disabled={isSubmitting || loading}
              className="flex items-center space-x-2"
              style={{ 
                background: 'var(--accent-color)',
                color: 'white'
              }}
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Сохранение...</span>
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  <span>Сохранить настройки</span>
                </>
              )}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
};

export default SecuritySettings;

