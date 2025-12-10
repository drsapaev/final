import React, { useState, useEffect } from 'react';
import { Card, Button, Badge, MacOSInput, MacOSSelect, MacOSTextarea } from '../ui/macos';
import { 
  Bell, 
  Users, 
  Send, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  Settings,
  BarChart3,
  MessageSquare,
  Phone,
  Mail,
  RefreshCw,
  Filter,
  Calendar,
  Activity
} from 'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';
const RegistrarNotificationManager = () => {
  const [activeTab, setActiveTab] = useState('send');
  const [loading, setLoading] = useState(false);
  const [registrars, setRegistrars] = useState([]);
  const [stats, setStats] = useState(null);

  // Состояние для отправки уведомлений
  const [notificationForm, setNotificationForm] = useState({
    type: 'system_alert',
    alert_type: 'system_error',
    message: '',
    priority: 'normal',
    department: ''
  });

  // Состояние для тестирования
  const [testMessage, setTestMessage] = useState('Тестовое уведомление системы');

  useEffect(() => {
    loadRegistrars();
    loadStats();
  }, []);

  const loadRegistrars = async () => {
    try {
      const response = await api.get('/registrar/notifications/registrars');
      setRegistrars(response.data.registrars || []);
    } catch (error) {
      logger.error('Ошибка загрузки регистраторов:', error);
      toast.error('Ошибка загрузки списка регистраторов');
    }
  };

  const loadStats = async () => {
    try {
      const response = await api.get('/registrar/notifications/stats');
      setStats(response.data);
    } catch (error) {
      logger.error('Ошибка загрузки статистики:', error);
      toast.error('Ошибка загрузки статистики');
    }
  };

  const handleSendNotification = async () => {
    if (!notificationForm.message.trim()) {
      toast.error('Введите текст уведомления');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/registrar/notifications/system-alert', {
        alert_type: notificationForm.alert_type,
        message: notificationForm.message,
        priority: notificationForm.priority,
        department: notificationForm.department || null
      });

      if (response.data.success) {
        toast.success(`Уведомление отправлено ${response.data.sent_count} регистраторам`);
        setNotificationForm({
          ...notificationForm,
          message: ''
        });
        loadStats(); // Обновляем статистику
      } else {
        toast.error('Ошибка отправки уведомления');
      }
    } catch (error) {
      logger.error('Ошибка отправки уведомления:', error);
      toast.error('Ошибка отправки уведомления');
    } finally {
      setLoading(false);
    }
  };

  const handleSendDailySummary = async () => {
    setLoading(true);
    try {
      const response = await api.post('/registrar/notifications/daily-summary');
      
      if (response.data.success) {
        toast.success(`Ежедневная сводка отправлена ${response.data.sent_count} регистраторам`);
        loadStats();
      } else {
        toast.error('Ошибка отправки сводки');
      }
    } catch (error) {
      logger.error('Ошибка отправки сводки:', error);
      toast.error('Ошибка отправки ежедневной сводки');
    } finally {
      setLoading(false);
    }
  };

  const handleTestNotification = async () => {
    if (!testMessage.trim()) {
      toast.error('Введите текст тестового уведомления');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post(`/registrar/notifications/test?message=${encodeURIComponent(testMessage)}`);
      
      if (response.data.success) {
        toast.success(`Тестовое уведомление отправлено ${response.data.sent_count} регистраторам`);
        loadStats();
      } else {
        toast.error('Ошибка отправки тестового уведомления');
      }
    } catch (error) {
      logger.error('Ошибка отправки тестового уведомления:', error);
      toast.error('Ошибка отправки тестового уведомления');
    } finally {
      setLoading(false);
    }
  };

  const renderSendTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Форма отправки уведомления */}
      <Card style={{ padding: '24px' }}>
        <h3 style={{ 
          margin: '0 0 16px 0',
          color: 'var(--mac-text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)'
        }}>
          <Send style={{ width: '20px', height: '20px' }} />
          Отправить уведомление
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Тип уведомления
            </label>
            <MacOSSelect
              value={notificationForm.alert_type}
              onChange={(e) => setNotificationForm({ ...notificationForm, alert_type: e.target.value })}
              options={[
                { value: 'system_error', label: 'Системная ошибка' },
                { value: 'payment_issue', label: 'Проблема с оплатой' },
                { value: 'queue_overflow', label: 'Переполнение очереди' },
                { value: 'equipment_failure', label: 'Неисправность оборудования' },
                { value: 'security_alert', label: 'Безопасность' },
                { value: 'maintenance', label: 'Техническое обслуживание' }
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
              Приоритет
            </label>
            <MacOSSelect
              value={notificationForm.priority}
              onChange={(e) => setNotificationForm({ ...notificationForm, priority: e.target.value })}
              options={[
                { value: 'normal', label: 'Обычный' },
                { value: 'warning', label: 'Предупреждение' },
                { value: 'critical', label: 'Критический' }
              ]}
              style={{ width: '100%' }}
            />
          </div>
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label style={{ 
            display: 'block', 
            fontSize: 'var(--mac-font-size-sm)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '8px' 
          }}>
            Отделение (опционально)
          </label>
          <MacOSInput
            placeholder="Например: Кардиология, Стоматология"
            value={notificationForm.department}
            onChange={(e) => setNotificationForm({ ...notificationForm, department: e.target.value })}
            style={{ width: '100%' }}
          />
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label style={{ 
            display: 'block', 
            fontSize: 'var(--mac-font-size-sm)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)', 
            marginBottom: '8px' 
          }}>
            Текст уведомления
          </label>
          <MacOSTextarea
            placeholder="Введите текст уведомления для регистраторов..."
            value={notificationForm.message}
            onChange={(e) => setNotificationForm({ ...notificationForm, message: e.target.value })}
            rows={4}
            style={{ width: '100%' }}
          />
        </div>

        <Button 
          onClick={handleSendNotification}
          disabled={loading || !notificationForm.message.trim()}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px'
          }}
        >
          {loading ? <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} /> : <Send style={{ width: '16px', height: '16px' }} />}
          Отправить уведомление
        </Button>
      </Card>

      {/* Быстрые действия */}
      <Card style={{ padding: '24px' }}>
        <h3 style={{ 
          margin: '0 0 16px 0',
          color: 'var(--mac-text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)'
        }}>
          <Activity style={{ width: '20px', height: '20px' }} />
          Быстрые действия
        </h3>

        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
          <Button 
            onClick={handleSendDailySummary}
            disabled={loading}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px'
            }}
          >
            <Calendar style={{ width: '16px', height: '16px' }} />
            Отправить ежедневную сводку
          </Button>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <MacOSInput
              placeholder="Текст тестового уведомления"
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
              style={{ minWidth: '200px' }}
            />
            <Button 
              onClick={handleTestNotification}
              disabled={loading || !testMessage.trim()}
              style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px'
              }}
            >
              <MessageSquare style={{ width: '16px', height: '16px' }} />
              Тест
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );

  const renderRegistrarsTab = () => (
    <Card style={{ padding: '24px' }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: '24px'
      }}>
        <h3 style={{ 
          margin: 0,
          color: 'var(--mac-text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)'
        }}>
          <Users style={{ width: '20px', height: '20px' }} />
          Активные регистраторы ({registrars.length})
        </h3>
        <Button 
          onClick={loadRegistrars}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px'
          }}
        >
          <RefreshCw style={{ width: '16px', height: '16px' }} />
          Обновить
        </Button>
      </div>

      <div style={{ display: 'grid', gap: '16px' }}>
        {registrars.map((registrar) => (
          <div
            key={registrar.id}
            style={{
              padding: '16px',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-md)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}
          >
            <div>
              <div style={{ 
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                marginBottom: '4px',
                fontSize: 'var(--mac-font-size-sm)'
              }}>
                {registrar.full_name || registrar.username}
              </div>
              <div style={{ 
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)',
                display: 'flex',
                alignItems: 'center',
                gap: '16px'
              }}>
                {registrar.email && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Mail style={{ width: '14px', height: '14px' }} />
                    {registrar.email}
                  </span>
                )}
                {registrar.phone && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Phone style={{ width: '16px', height: '16px', color: 'var(--mac-accent-blue)' }} />
                    {registrar.phone}
                  </span>
                )}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {registrar.telegram_id && (
                <Badge variant="info">
                  Telegram
                </Badge>
              )}
              <Badge 
                variant={registrar.is_active ? 'success' : 'error'}
              >
                {registrar.is_active ? 'Активен' : 'Неактивен'}
              </Badge>
            </div>
          </div>
        ))}
      </div>

      {registrars.length === 0 && (
        <div style={{ 
          textAlign: 'center', 
          padding: '32px',
          color: 'var(--mac-text-secondary)',
          fontSize: 'var(--mac-font-size-sm)'
        }}>
          Нет активных регистраторов
        </div>
      )}
    </Card>
  );

  const renderStatsTab = () => (
    <Card style={{ padding: '24px' }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: '24px'
      }}>
        <h3 style={{ 
          margin: 0,
          color: 'var(--mac-text-primary)',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-medium)'
        }}>
          <BarChart3 style={{ width: '20px', height: '20px' }} />
          Статистика уведомлений
        </h3>
        <Button 
          onClick={loadStats}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px'
          }}
        >
          <RefreshCw style={{ width: '16px', height: '16px' }} />
          Обновить
        </Button>
      </div>

      {stats ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          <div style={{ 
            padding: '16px',
            backgroundColor: 'var(--mac-info-bg)',
            borderRadius: 'var(--mac-radius-md)',
            textAlign: 'center',
            border: '1px solid var(--mac-info-border)'
          }}>
            <div style={{ fontSize: 'var(--mac-font-size-2xl)', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-accent-blue)' }}>
              {stats.total_sent}
            </div>
            <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>Всего отправлено</div>
          </div>

          <div style={{ 
            padding: '16px',
            backgroundColor: 'var(--mac-success-bg)',
            borderRadius: 'var(--mac-radius-md)',
            textAlign: 'center',
            border: '1px solid var(--mac-success-border)'
          }}>
            <div style={{ fontSize: 'var(--mac-font-size-2xl)', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-success)' }}>
              {stats.successful_deliveries}
            </div>
            <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>Успешно доставлено</div>
          </div>

          <div style={{ 
            padding: '16px',
            backgroundColor: 'var(--mac-error-bg)',
            borderRadius: 'var(--mac-radius-md)',
            textAlign: 'center',
            border: '1px solid var(--mac-error-border)'
          }}>
            <div style={{ fontSize: 'var(--mac-font-size-2xl)', fontWeight: 'var(--mac-font-weight-bold)', color: 'var(--mac-error)' }}>
              {stats.failed_deliveries}
            </div>
            <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>Ошибки доставки</div>
          </div>
        </div>
      ) : (
        <div style={{ 
          textAlign: 'center', 
          padding: '32px',
          color: 'var(--mac-text-secondary)',
          fontSize: 'var(--mac-font-size-sm)'
        }}>
          Загрузка статистики...
        </div>
      )}

      {stats && stats.channels_stats && (
        <div style={{ marginTop: '24px' }}>
          <h4 style={{ 
            margin: '0 0 16px 0',
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-base)',
            fontWeight: 'var(--mac-font-weight-medium)'
          }}>
            Статистика по каналам
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '16px' }}>
            <div style={{ 
              padding: '12px',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-sm)',
              textAlign: 'center'
            }}>
              <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-accent-blue)', fontSize: 'var(--mac-font-size-lg)' }}>
                {stats.channels_stats.telegram}
              </div>
              <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>Telegram</div>
            </div>

            <div style={{ 
              padding: '12px',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-sm)',
              textAlign: 'center'
            }}>
              <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-success)', fontSize: 'var(--mac-font-size-lg)' }}>
                {stats.channels_stats.email}
              </div>
              <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>Email</div>
            </div>

            <div style={{ 
              padding: '12px',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-sm)',
              textAlign: 'center'
            }}>
              <div style={{ fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-warning)', fontSize: 'var(--mac-font-size-lg)' }}>
                {stats.channels_stats.sms}
              </div>
              <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>SMS</div>
            </div>
          </div>
        </div>
      )}
    </Card>
  );

  const tabs = [
    { id: 'send', label: 'Отправка', icon: Send },
    { id: 'registrars', label: 'Регистраторы', icon: Users },
    { id: 'stats', label: 'Статистика', icon: BarChart3 }
  ];

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        gap: '16px',
        marginBottom: '24px'
      }}>
        <Bell style={{ width: '24px', height: '24px', color: 'var(--mac-accent-blue)' }} />
        <h2 style={{ 
          margin: 0, 
          color: 'var(--mac-text-primary)',
          fontSize: 'var(--mac-font-size-2xl)',
          fontWeight: 'var(--mac-font-weight-semibold)'
        }}>
          Уведомления регистратуры
        </h2>
      </div>

      {/* Вкладки */}
      <div style={{ 
        display: 'flex', 
        marginBottom: '24px'
      }}>
        {tabs.map((tab) => {
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

      {/* Содержимое вкладок */}
      {activeTab === 'send' && renderSendTab()}
      {activeTab === 'registrars' && renderRegistrarsTab()}
      {activeTab === 'stats' && renderStatsTab()}
    </div>
  );
};

export default RegistrarNotificationManager;

