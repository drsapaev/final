import React, { useState, useEffect } from 'react';
import logger from '../../utils/logger';
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
import { 
  MacOSInput, 
  MacOSSelect,
  MacOSButton,
  MacOSCheckbox,
  MacOSBadge,
  MacOSTab,
  MacOSCard
} from '../ui/macos';

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
      logger.error('Ошибка сохранения настроек безопасности:', error);
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
    logger.log('Terminating session:', sessionId);
  };

  const terminateAllOtherSessions = () => {
    // Логика завершения всех других сессий
    logger.log('Terminating all other sessions');
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
      success: 'var(--mac-success)',
      failed: 'var(--mac-danger)',
      blocked: 'var(--mac-warning)'
    };
    return colorMap[status] || 'var(--mac-text-secondary)';
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Вкладки */}
      <MacOSTab
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Смена пароля */}
        {activeTab === 'password' && (
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              marginBottom: '20px',
              color: 'var(--mac-text-primary)'
            }}>
              Смена пароля
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  marginBottom: '8px',
                  color: 'var(--mac-text-primary)'
                }}>
                  Текущий пароль *
                </label>
                <div style={{ position: 'relative' }}>
                  <MacOSInput
                    type={showPasswords.current ? 'text' : 'password'}
                    value={formData.currentPassword}
                    onChange={(e) => handleChange('currentPassword', e.target.value)}
                    placeholder="Введите текущий пароль"
                    style={{ paddingLeft: '40px', paddingRight: '40px' }}
                  />
                  <Lock style={{ 
                    position: 'absolute', 
                    left: '12px', 
                    top: '50%', 
                    transform: 'translateY(-50%)',
                    width: '16px', 
                    height: '16px', 
                    color: 'var(--mac-text-tertiary)' 
                  }} />
                  <button
                    type="button"
                    onClick={() => togglePasswordVisibility('current')}
                    style={{ 
                      position: 'absolute', 
                      right: '12px', 
                      top: '50%', 
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      color: 'var(--mac-text-tertiary)'
                    }}
                  >
                    {showPasswords.current ? <EyeOff style={{ width: '16px', height: '16px' }} /> : <Eye style={{ width: '16px', height: '16px' }} />}
                  </button>
                </div>
                {errors.currentPassword && (
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-danger)', 
                    marginTop: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}>
                    <AlertCircle style={{ width: '16px', height: '16px' }} />
                    {errors.currentPassword}
                  </p>
                )}
              </div>

              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  marginBottom: '8px',
                  color: 'var(--mac-text-primary)'
                }}>
                  Новый пароль *
                </label>
                <div style={{ position: 'relative' }}>
                  <MacOSInput
                    type={showPasswords.new ? 'text' : 'password'}
                    value={formData.newPassword}
                    onChange={(e) => handleChange('newPassword', e.target.value)}
                    placeholder="Введите новый пароль"
                    style={{ paddingLeft: '40px', paddingRight: '40px' }}
                  />
                  <Key style={{ 
                    position: 'absolute', 
                    left: '12px', 
                    top: '50%', 
                    transform: 'translateY(-50%)',
                    width: '16px', 
                    height: '16px', 
                    color: 'var(--mac-text-tertiary)' 
                  }} />
                  <button
                    type="button"
                    onClick={() => togglePasswordVisibility('new')}
                    style={{ 
                      position: 'absolute', 
                      right: '12px', 
                      top: '50%', 
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      color: 'var(--mac-text-tertiary)'
                    }}
                  >
                    {showPasswords.new ? <EyeOff style={{ width: '16px', height: '16px' }} /> : <Eye style={{ width: '16px', height: '16px' }} />}
                  </button>
                </div>
                {errors.newPassword && (
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-danger)', 
                    marginTop: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}>
                    <AlertCircle style={{ width: '16px', height: '16px' }} />
                    {errors.newPassword}
                  </p>
                )}
              </div>

              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  marginBottom: '8px',
                  color: 'var(--mac-text-primary)'
                }}>
                  Подтвердите новый пароль *
                </label>
                <div style={{ position: 'relative' }}>
                  <MacOSInput
                    type={showPasswords.confirm ? 'text' : 'password'}
                    value={formData.confirmPassword}
                    onChange={(e) => handleChange('confirmPassword', e.target.value)}
                    placeholder="Подтвердите новый пароль"
                    style={{ paddingLeft: '40px', paddingRight: '40px' }}
                  />
                  <Key style={{ 
                    position: 'absolute', 
                    left: '12px', 
                    top: '50%', 
                    transform: 'translateY(-50%)',
                    width: '16px', 
                    height: '16px', 
                    color: 'var(--mac-text-tertiary)' 
                  }} />
                  <button
                    type="button"
                    onClick={() => togglePasswordVisibility('confirm')}
                    style={{ 
                      position: 'absolute', 
                      right: '12px', 
                      top: '50%', 
                      transform: 'translateY(-50%)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      color: 'var(--mac-text-tertiary)'
                    }}
                  >
                    {showPasswords.confirm ? <EyeOff style={{ width: '16px', height: '16px' }} /> : <Eye style={{ width: '16px', height: '16px' }} />}
                  </button>
                </div>
                {errors.confirmPassword && (
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-danger)', 
                    marginTop: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px'
                  }}>
                    <AlertCircle style={{ width: '16px', height: '16px' }} />
                    {errors.confirmPassword}
                  </p>
                )}
              </div>
            </div>
          </MacOSCard>
        )}

        {/* Двухфакторная аутентификация */}
        {activeTab === 'two-factor' && (
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              marginBottom: '20px',
              color: 'var(--mac-text-primary)'
            }}>
              Двухфакторная аутентификация
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between', 
                padding: '16px', 
                borderRadius: 'var(--mac-radius-md)', 
                border: '1px solid var(--mac-border)', 
                backgroundColor: 'var(--mac-bg-secondary)' 
              }}>
                <div>
                  <h4 style={{ 
                    fontSize: 'var(--mac-font-size-base)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)',
                    marginBottom: '4px'
                  }}>
                    Включить 2FA
                  </h4>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    color: 'var(--mac-text-secondary)',
                    margin: 0
                  }}>
                    Дополнительная защита вашего аккаунта
                  </p>
                </div>
                <MacOSCheckbox
                  checked={formData.twoFactorEnabled}
                  onChange={(checked) => handleChange('twoFactorEnabled', checked)}
                />
              </div>

              {formData.twoFactorEnabled && (
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    marginBottom: '8px',
                    color: 'var(--mac-text-primary)'
                  }}>
                    Метод аутентификации
                  </label>
                  <MacOSSelect
                    value={formData.twoFactorMethod}
                    onChange={(e) => handleChange('twoFactorMethod', e.target.value)}
                    options={[
                      { value: 'sms', label: 'SMS' },
                      { value: 'email', label: 'Email' },
                      { value: 'app', label: 'Приложение-аутентификатор' }
                    ]}
                    placeholder="Выберите метод"
                  />
                </div>
              )}
            </div>
          </MacOSCard>
        )}

        {/* Активные сессии */}
        {activeTab === 'sessions' && (
          <MacOSCard style={{ padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <h3 style={{ 
                fontSize: 'var(--mac-font-size-lg)', 
                fontWeight: 'var(--mac-font-weight-semibold)', 
                color: 'var(--mac-text-primary)',
                margin: 0
              }}>
                Активные сессии
              </h3>
              <MacOSButton
                variant="outline"
                onClick={terminateAllOtherSessions}
                size="sm"
              >
                <Trash2 style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                Завершить все остальные
              </MacOSButton>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {activeSessions.map((session) => (
                <div key={session.id} style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'space-between', 
                  padding: '16px', 
                  borderRadius: 'var(--mac-radius-md)', 
                  border: '1px solid var(--mac-border)', 
                  backgroundColor: 'var(--mac-bg-secondary)' 
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <div style={{ 
                      width: '40px', 
                      height: '40px', 
                      borderRadius: '50%', 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'center', 
                      backgroundColor: 'var(--mac-accent-blue)' 
                    }}>
                      <User style={{ width: '20px', height: '20px', color: 'white' }} />
                    </div>
                    <div>
                      <p style={{ 
                        fontSize: 'var(--mac-font-size-base)', 
                        fontWeight: 'var(--mac-font-weight-medium)', 
                        color: 'var(--mac-text-primary)',
                        margin: 0,
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                      }}>
                        {session.device}
                        {session.current && (
                          <MacOSBadge variant="success" size="sm">Текущая</MacOSBadge>
                        )}
                      </p>
                      <p style={{ 
                        fontSize: 'var(--mac-font-size-sm)', 
                        color: 'var(--mac-text-secondary)',
                        margin: '4px 0 0 0'
                      }}>
                        {session.location} • {session.ip}
                      </p>
                      <p style={{ 
                        fontSize: 'var(--mac-font-size-xs)', 
                        color: 'var(--mac-text-tertiary)',
                        margin: '4px 0 0 0'
                      }}>
                        Последняя активность: {formatDateTime(session.lastActive)}
                      </p>
                    </div>
                  </div>
                  
                  {!session.current && (
                    <MacOSButton
                      variant="outline"
                      size="sm"
                      onClick={() => terminateSession(session.id)}
                      style={{ color: 'var(--mac-danger)', borderColor: 'var(--mac-danger)' }}
                    >
                      <Trash2 style={{ width: '16px', height: '16px' }} />
                    </MacOSButton>
                  )}
                </div>
              ))}
            </div>
          </MacOSCard>
        )}

        {/* Настройки безопасности */}
        {activeTab === 'security' && (
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              marginBottom: '20px',
              color: 'var(--mac-text-primary)'
            }}>
              Настройки безопасности
            </h3>
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
              gap: '16px',
              marginBottom: '24px'
            }}>
              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  marginBottom: '8px',
                  color: 'var(--mac-text-primary)'
                }}>
                  Минимальная длина пароля
                </label>
                <MacOSInput
                  type="number"
                  value={formData.passwordMinLength}
                  onChange={(e) => handleChange('passwordMinLength', parseInt(e.target.value))}
                  min="6"
                  max="32"
                />
              </div>

              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  marginBottom: '8px',
                  color: 'var(--mac-text-primary)'
                }}>
                  Срок действия пароля (дни)
                </label>
                <MacOSInput
                  type="number"
                  value={formData.passwordExpiryDays}
                  onChange={(e) => handleChange('passwordExpiryDays', parseInt(e.target.value))}
                  min="30"
                  max="365"
                />
              </div>

              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  marginBottom: '8px',
                  color: 'var(--mac-text-primary)'
                }}>
                  Максимум попыток входа
                </label>
                <MacOSInput
                  type="number"
                  value={formData.maxLoginAttempts}
                  onChange={(e) => handleChange('maxLoginAttempts', parseInt(e.target.value))}
                  min="3"
                  max="10"
                />
              </div>

              <div>
                <label style={{ 
                  display: 'block', 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  marginBottom: '8px',
                  color: 'var(--mac-text-primary)'
                }}>
                  Время блокировки (минуты)
                </label>
                <MacOSInput
                  type="number"
                  value={formData.lockoutDuration}
                  onChange={(e) => handleChange('lockoutDuration', parseInt(e.target.value))}
                  min="5"
                  max="60"
                />
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <MacOSCheckbox
                checked={formData.passwordRequireUppercase}
                onChange={(checked) => handleChange('passwordRequireUppercase', checked)}
                label="Требовать заглавные буквы в пароле"
              />

              <MacOSCheckbox
                checked={formData.passwordRequireNumbers}
                onChange={(checked) => handleChange('passwordRequireNumbers', checked)}
                label="Требовать цифры в пароле"
              />

              <MacOSCheckbox
                checked={formData.passwordRequireSymbols}
                onChange={(checked) => handleChange('passwordRequireSymbols', checked)}
                label="Требовать специальные символы в пароле"
              />

              <MacOSCheckbox
                checked={formData.blockSuspiciousIPs}
                onChange={(checked) => handleChange('blockSuspiciousIPs', checked)}
                label="Блокировать подозрительные IP адреса"
              />
            </div>
          </MacOSCard>
        )}

        {/* Логи безопасности */}
        {activeTab === 'audit' && (
          <MacOSCard style={{ padding: '24px' }}>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              marginBottom: '20px',
              color: 'var(--mac-text-primary)'
            }}>
              Логи безопасности
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {securityLogs.map((log) => {
                const StatusIcon = getStatusIcon(log.status);
                return (
                  <div key={log.id} style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between', 
                    padding: '16px', 
                    borderRadius: 'var(--mac-radius-md)', 
                    border: '1px solid var(--mac-border)', 
                    backgroundColor: 'var(--mac-bg-secondary)' 
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                      <StatusIcon style={{ width: '20px', height: '20px', color: getStatusColor(log.status) }} />
                      <div>
                        <p style={{ 
                          fontSize: 'var(--mac-font-size-base)', 
                          fontWeight: 'var(--mac-font-weight-medium)', 
                          color: 'var(--mac-text-primary)',
                          margin: 0
                        }}>
                          {log.action}
                        </p>
                        <p style={{ 
                          fontSize: 'var(--mac-font-size-sm)', 
                          color: 'var(--mac-text-secondary)',
                          margin: '4px 0 0 0'
                        }}>
                          {log.user} • {log.ip}
                        </p>
                        <p style={{ 
                          fontSize: 'var(--mac-font-size-xs)', 
                          color: 'var(--mac-text-tertiary)',
                          margin: '4px 0 0 0'
                        }}>
                          {formatDateTime(log.timestamp)}
                        </p>
                      </div>
                    </div>
                    
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <MacOSBadge 
                        variant={log.status === 'success' ? 'success' : log.status === 'failed' ? 'error' : 'warning'}
                        size="sm"
                      >
                        {getStatusLabel(log.status)}
                      </MacOSBadge>
                      <span style={{ 
                        fontSize: 'var(--mac-font-size-xs)', 
                        color: 'var(--mac-text-tertiary)' 
                      }}>
                        {log.details}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </MacOSCard>
        )}

        {/* Кнопки действий */}
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between', 
          paddingTop: '24px', 
          borderTop: '1px solid var(--mac-border)' 
        }}>
          <div style={{ 
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-text-secondary)' 
          }}>
            Настройки безопасности сохраняются автоматически
          </div>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <MacOSButton
              variant="outline"
              onClick={() => window.location.reload()}
              disabled={isSubmitting}
            >
              <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Сбросить
            </MacOSButton>
            
            <MacOSButton
              type="submit"
              disabled={isSubmitting || loading}
              loading={isSubmitting}
            >
              <Save style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Сохранить настройки
            </MacOSButton>
          </div>
        </div>
      </form>
    </div>
  );
};

export default SecuritySettings;