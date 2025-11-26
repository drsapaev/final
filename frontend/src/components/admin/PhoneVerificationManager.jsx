import React, { useState, useEffect } from 'react';
import {
  MacOSCard,
  MacOSButton,
  MacOSBadge,
  MacOSLoadingSkeleton,
  MacOSInput,
  MacOSSelect,
  MacOSTextarea
} from '../ui/macos';
import {
  Phone,
  Shield,
  Send,
  BarChart3,
  Users,
  Clock,
  CheckCircle,
  AlertTriangle,
  RefreshCw,
  Settings,
  MessageSquare
} from 'lucide-react';
import { api } from '../../api/client';
import { toast } from 'react-toastify';

const PhoneVerificationManager = () => {
  const [loading, setLoading] = useState(false);
  const [statistics, setStatistics] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [adminForm, setAdminForm] = useState({
    phone: '',
    purpose: 'verification',
    provider: '',
    message: ''
  });

  useEffect(() => {
    loadStatistics();
  }, []);

  const loadStatistics = async () => {
    setLoading(true);
    try {
      const response = await api.get('/phone-verification/statistics');
      setStatistics(response.data.statistics);
    } catch (error) {
      console.error('Error loading verification statistics:', error);
      toast.error('Ошибка загрузки статистики верификации');
    } finally {
      setLoading(false);
    }
  };

  const sendAdminCode = async () => {
    if (!adminForm.phone.trim()) {
      toast.error('Введите номер телефона');
      return;
    }

    setLoading(true);
    try {
      const params = {
        phone: adminForm.phone,
        purpose: adminForm.purpose
      };

      if (adminForm.provider) {
        params.provider = adminForm.provider;
      }

      if (adminForm.message.trim()) {
        params.message = adminForm.message;
      }

      const response = await api.post('/phone-verification/admin/send-code', null, { params });

      if (response.data.success) {
        toast.success(`Код отправлен на ${adminForm.phone}`);
        setAdminForm({
          phone: '',
          purpose: 'verification',
          provider: '',
          message: ''
        });
        loadStatistics(); // Обновляем статистику
      }
    } catch (error) {
      console.error('Error sending admin verification code:', error);
      toast.error('Ошибка отправки кода верификации');
    } finally {
      setLoading(false);
    }
  };

  const formatPhone = (value) => {
    const digits = value.replace(/\D/g, '');
    if (digits.startsWith('9') && digits.length <= 9) {
      return `+998${digits}`;
    }
    if (digits.startsWith('998')) {
      return `+${digits}`;
    }
    return value;
  };

  const renderOverview = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Основная статистика */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
        gap: '16px' 
      }}>
        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)',
                margin: '0 0 8px 0'
              }}>
                Активные коды
              </p>
              <p style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)',
                color: 'var(--mac-text-primary)',
                margin: 0
              }}>
                {statistics?.total_active_codes || 0}
              </p>
            </div>
            <Shield style={{ width: '24px', height: '24px', color: 'var(--mac-accent-blue)' }} />
          </div>
        </MacOSCard>

        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)',
                margin: '0 0 8px 0'
              }}>
                Подтверждено
              </p>
              <p style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)',
                color: 'var(--mac-success)',
                margin: 0
              }}>
                {statistics?.verified_codes || 0}
              </p>
            </div>
            <CheckCircle style={{ width: '24px', height: '24px', color: 'var(--mac-success)' }} />
          </div>
        </MacOSCard>

        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)',
                margin: '0 0 8px 0'
              }}>
                Ожидают
              </p>
              <p style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)',
                color: 'var(--mac-warning)',
                margin: 0
              }}>
                {statistics?.pending_codes || 0}
              </p>
            </div>
            <Clock style={{ width: '24px', height: '24px', color: 'var(--mac-warning)' }} />
          </div>
        </MacOSCard>

        <MacOSCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)',
                margin: '0 0 8px 0'
              }}>
                Истекают скоро
              </p>
              <p style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)',
                color: 'var(--mac-error)',
                margin: 0
              }}>
                {statistics?.expiring_soon || 0}
              </p>
            </div>
            <AlertTriangle style={{ width: '24px', height: '24px', color: 'var(--mac-error)' }} />
          </div>
        </MacOSCard>
      </div>

      {/* Статистика по целям */}
      <MacOSCard style={{ padding: '24px' }}>
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)', 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-text-primary)',
          margin: '0 0 16px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <BarChart3 style={{ width: '20px', height: '20px' }} />
          Статистика по целям верификации
        </h3>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', 
          gap: '16px' 
        }}>
          {statistics?.by_purpose && Object.entries(statistics.by_purpose).map(([purpose, count]) => (
            <div key={purpose} style={{ 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'space-between', 
              padding: '12px',
              border: '1px solid var(--mac-border)', 
              borderRadius: 'var(--mac-radius-md)',
              backgroundColor: 'var(--mac-bg-secondary)'
            }}>
              <div>
                <p style={{ 
                  fontWeight: 'var(--mac-font-weight-medium)',
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-primary)',
                  margin: '0 0 4px 0',
                  textTransform: 'capitalize'
                }}>
                  {purpose}
                </p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-xs)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>
                  {purpose === 'verification' && 'Подтверждение номера'}
                  {purpose === 'password_reset' && 'Сброс пароля'}
                  {purpose === 'phone_change' && 'Смена номера'}
                  {purpose === 'registration' && 'Регистрация'}
                </p>
              </div>
              <MacOSBadge variant="outline">{count}</MacOSBadge>
            </div>
          ))}
        </div>
      </MacOSCard>

      {/* Статистика по провайдерам */}
      <MacOSCard style={{ padding: '24px' }}>
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)', 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-text-primary)',
          margin: '0 0 16px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Send style={{ width: '20px', height: '20px' }} />
          Статистика по SMS провайдерам
        </h3>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          {statistics?.by_provider && Object.entries(statistics.by_provider).map(([provider, count]) => (
            <div key={provider} style={{ 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'space-between', 
              padding: '12px',
              border: '1px solid var(--mac-border)', 
              borderRadius: 'var(--mac-radius-md)',
              backgroundColor: 'var(--mac-bg-secondary)'
            }}>
              <div>
                <p style={{ 
                  fontWeight: 'var(--mac-font-weight-medium)',
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-primary)',
                  margin: 0,
                  textTransform: 'capitalize'
                }}>
                  {provider}
                </p>
              </div>
              <MacOSBadge variant={provider === 'mock' ? 'secondary' : 'success'}>{count}</MacOSBadge>
            </div>
          ))}
        </div>
      </MacOSCard>
    </div>
  );

  const renderAdminTools = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{ padding: '24px' }}>
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)', 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-text-primary)',
          margin: '0 0 16px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Send style={{ width: '20px', height: '20px' }} />
          Отправка кода администратором
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
              Номер телефона
            </label>
            <MacOSInput
              type="tel"
              value={adminForm.phone}
              onChange={(e) => setAdminForm(prev => ({ ...prev, phone: formatPhone(e.target.value) }))}
              placeholder="+998XXXXXXXXX"
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Цель верификации
            </label>
            <MacOSSelect
              value={adminForm.purpose}
              onChange={(e) => setAdminForm(prev => ({ ...prev, purpose: e.target.value }))}
              options={[
                { value: 'verification', label: 'Подтверждение номера' },
                { value: 'password_reset', label: 'Сброс пароля' },
                { value: 'phone_change', label: 'Смена номера' },
                { value: 'registration', label: 'Регистрация' }
              ]}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              SMS провайдер (опционально)
            </label>
            <MacOSSelect
              value={adminForm.provider}
              onChange={(e) => setAdminForm(prev => ({ ...prev, provider: e.target.value }))}
              options={[
                { value: '', label: 'По умолчанию' },
                { value: 'eskiz', label: 'Eskiz' },
                { value: 'playmobile', label: 'PlayMobile' },
                { value: 'mock', label: 'Mock (тест)' }
              ]}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Кастомное сообщение (опционально)
            </label>
            <MacOSTextarea
              value={adminForm.message}
              onChange={(e) => setAdminForm(prev => ({ ...prev, message: e.target.value }))}
              placeholder="Ваш код подтверждения: {code}. Код действителен 5 минут."
              style={{ minHeight: '80px', width: '100%' }}
            />
            <p style={{ 
              fontSize: 'var(--mac-font-size-xs)', 
              color: 'var(--mac-text-secondary)',
              margin: '4px 0 0 0'
            }}>
              Используйте {'{code}'} для вставки кода верификации
            </p>
          </div>

          <MacOSButton
            onClick={sendAdminCode}
            disabled={loading || !adminForm.phone.trim()}
            style={{ width: '100%' }}
          >
            {loading ? (
              <>
                <RefreshCw style={{ 
                  width: '16px', 
                  height: '16px', 
                  marginRight: '8px',
                  animation: 'spin 1s linear infinite'
                }} />
                Отправка...
              </>
            ) : (
              <>
                <Send style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                Отправить код
              </>
            )}
          </MacOSButton>
        </div>
      </MacOSCard>
    </div>
  );

  const renderSettings = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{ padding: '24px' }}>
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)', 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-text-primary)',
          margin: '0 0 16px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Settings style={{ width: '20px', height: '20px' }} />
          Настройки верификации
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {statistics?.settings && (
            <div style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
              gap: '16px' 
            }}>
              <div style={{ 
                padding: '16px',
                border: '1px solid var(--mac-border)', 
                borderRadius: 'var(--mac-radius-md)',
                backgroundColor: 'var(--mac-bg-secondary)'
              }}>
                <p style={{ 
                  fontWeight: 'var(--mac-font-weight-medium)',
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-primary)',
                  margin: '0 0 8px 0'
                }}>
                  Длина кода
                </p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-accent-blue)',
                  margin: '0 0 4px 0'
                }}>
                  {statistics.settings.code_length}
                </p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-xs)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>
                  цифр
                </p>
              </div>

              <div style={{ 
                padding: '16px',
                border: '1px solid var(--mac-border)', 
                borderRadius: 'var(--mac-radius-md)',
                backgroundColor: 'var(--mac-bg-secondary)'
              }}>
                <p style={{ 
                  fontWeight: 'var(--mac-font-weight-medium)',
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-primary)',
                  margin: '0 0 8px 0'
                }}>
                  Время жизни кода
                </p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-success)',
                  margin: '0 0 4px 0'
                }}>
                  {statistics.settings.ttl_minutes}
                </p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-xs)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>
                  минут
                </p>
              </div>

              <div style={{ 
                padding: '16px',
                border: '1px solid var(--mac-border)', 
                borderRadius: 'var(--mac-radius-md)',
                backgroundColor: 'var(--mac-bg-secondary)'
              }}>
                <p style={{ 
                  fontWeight: 'var(--mac-font-weight-medium)',
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-primary)',
                  margin: '0 0 8px 0'
                }}>
                  Максимум попыток
                </p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-warning)',
                  margin: '0 0 4px 0'
                }}>
                  {statistics.settings.max_attempts}
                </p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-xs)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>
                  попыток
                </p>
              </div>

              <div style={{ 
                padding: '16px',
                border: '1px solid var(--mac-border)', 
                borderRadius: 'var(--mac-radius-md)',
                backgroundColor: 'var(--mac-bg-secondary)'
              }}>
                <p style={{ 
                  fontWeight: 'var(--mac-font-weight-medium)',
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-primary)',
                  margin: '0 0 8px 0'
                }}>
                  Лимит частоты
                </p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-2xl)', 
                  fontWeight: 'var(--mac-font-weight-bold)', 
                  color: 'var(--mac-error)',
                  margin: '0 0 4px 0'
                }}>
                  {statistics.settings.rate_limit_minutes}
                </p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-xs)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0
                }}>
                  минут
                </p>
              </div>
            </div>
          )}

          <div style={{ 
            padding: '16px', 
            backgroundColor: 'var(--mac-info-bg)', 
            border: '1px solid var(--mac-info-border)', 
            borderRadius: 'var(--mac-radius-md)' 
          }}>
            <h4 style={{ 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-info)',
              fontSize: 'var(--mac-font-size-sm)',
              margin: '0 0 8px 0'
            }}>
              Информация
            </h4>
            <ul style={{ 
              fontSize: 'var(--mac-font-size-xs)', 
              color: 'var(--mac-info)',
              margin: 0,
              paddingLeft: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              <li>• Коды верификации хранятся в памяти сервера</li>
              <li>• Для production рекомендуется использовать Redis</li>
              <li>• Истекшие коды автоматически удаляются</li>
              <li>• Лимит частоты предотвращает спам</li>
            </ul>
          </div>
        </div>
      </MacOSCard>
    </div>
  );

  const tabs = [
    { id: 'overview', label: 'Обзор', icon: BarChart3 },
    { id: 'admin-tools', label: 'Инструменты', icon: Send },
    { id: 'settings', label: 'Настройки', icon: Settings }
  ];

  return (
    <div style={{ 
      padding: '24px',
      backgroundColor: 'var(--mac-bg-primary)',
      minHeight: '100vh'
    }}>
      {/* Заголовок */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Phone style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
          <div>
            <h1 style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              Верификация телефонов
            </h1>
            <p style={{ 
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-sm)',
              margin: 0
            }}>
              Управление SMS верификацией
            </p>
          </div>
        </div>
        
        <MacOSButton onClick={loadStatistics} disabled={loading} variant="outline">
          <RefreshCw style={{ 
            width: '16px', 
            height: '16px', 
            marginRight: '8px',
            animation: loading ? 'spin 1s linear infinite' : 'none'
          }} />
          Обновить
        </MacOSButton>
      </div>

      {/* Вкладки */}
      <div style={{ 
        display: 'flex', 
        marginBottom: '24px'
      }}>
        {tabs.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '12px 20px',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)',
                fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                fontSize: 'var(--mac-font-size-sm)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                position: 'relative',
                marginBottom: '-1px'
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.target.style.color = 'var(--mac-text-primary)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.target.style.color = 'var(--mac-text-secondary)';
                }
              }}
            >
              <Icon style={{ 
                width: '16px', 
                height: '16px',
                color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
              }} />
              {tab.label}
              {isActive && (
                <div style={{
                  position: 'absolute',
                  bottom: '0',
                  left: '0',
                  right: '0',
                  height: '3px',
                  backgroundColor: 'var(--mac-accent-blue)',
                  borderRadius: '2px 2px 0 0'
                }} />
              )}
            </button>
          );
        })}
      </div>
      
      {/* Разделительная линия */}
      <div style={{ 
        borderBottom: '1px solid var(--mac-border)',
        marginBottom: '24px'
      }} />

      {/* Контент вкладок */}
      {loading && !statistics ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <MacOSLoadingSkeleton height="128px" style={{ width: '100%' }} />
          <MacOSLoadingSkeleton height="256px" style={{ width: '100%' }} />
        </div>
      ) : (
        <>
          {activeTab === 'overview' && renderOverview()}
          {activeTab === 'admin-tools' && renderAdminTools()}
          {activeTab === 'settings' && renderSettings()}
        </>
      )}
    </div>
  );
};

export default PhoneVerificationManager;


