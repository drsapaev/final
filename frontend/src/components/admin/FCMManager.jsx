import React, { useState, useEffect } from 'react';
import {
  MacOSCard,
  MacOSButton,
  MacOSBadge,
  MacOSLoadingSkeleton,
  MacOSInput,
  MacOSSelect,
  MacOSTextarea,
  MacOSCheckbox
} from '../ui/macos';
import {
  Bell,
  Send,
  Users,
  Settings,
  CheckCircle,
  AlertTriangle,
  Activity,
  Smartphone,
  MessageSquare,
  RefreshCw,
  TestTube,
  Zap
} from 'lucide-react';
import { api } from '../../api/client';
import { toast } from 'react-toastify';

import logger from '../../utils/logger';
const FCMManager = () => {
  const [loading, setLoading] = useState(false);
  const [fcmStatus, setFcmStatus] = useState(null);
  const [usersWithTokens, setUsersWithTokens] = useState([]);
  const [activeTab, setActiveTab] = useState('overview');
  const [notificationForm, setNotificationForm] = useState({
    title: '',
    body: '',
    user_ids: [],
    data: {},
    image: '',
    sound: 'default'
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      await Promise.all([
        loadFCMStatus(),
        loadUsersWithTokens()
      ]);
    } catch (error) {
      logger.error('Error loading FCM data:', error);
      toast.error('Ошибка загрузки данных FCM');
    } finally {
      setLoading(false);
    }
  };

  const loadFCMStatus = async () => {
    try {
      const response = await api.get('/fcm/status');
      setFcmStatus(response.data.fcm_service);
    } catch (error) {
      logger.error('Error loading FCM status:', error);
    }
  };

  const loadUsersWithTokens = async () => {
    try {
      const response = await api.get('/fcm/user-tokens');
      setUsersWithTokens(response.data.users || []);
    } catch (error) {
      logger.error('Error loading users with tokens:', error);
    }
  };

  const testFCMNotification = async () => {
    try {
      setLoading(true);
      const response = await api.post('/fcm/send-test-notification');
      
      if (response.data.success) {
        toast.success('Тестовое FCM уведомление отправлено!');
      } else {
        toast.error(`Ошибка: ${response.data.message}`);
      }
    } catch (error) {
      logger.error('Error testing FCM:', error);
      toast.error('Ошибка тестирования FCM');
    } finally {
      setLoading(false);
    }
  };

  const sendNotification = async () => {
    if (!notificationForm.title.trim() || !notificationForm.body.trim()) {
      toast.error('Заполните заголовок и текст уведомления');
      return;
    }

    try {
      setLoading(true);
      
      const payload = {
        title: notificationForm.title,
        body: notificationForm.body,
        sound: notificationForm.sound
      };

      // Добавляем пользователей если выбраны
      if (notificationForm.user_ids.length > 0) {
        payload.user_ids = notificationForm.user_ids;
      }

      // Добавляем дополнительные данные
      if (Object.keys(notificationForm.data).length > 0) {
        payload.data = notificationForm.data;
      }

      // Добавляем изображение если указано
      if (notificationForm.image.trim()) {
        payload.image = notificationForm.image;
      }

      const response = await api.post('/fcm/send-notification', payload);
      
      if (response.data.success) {
        toast.success(`Уведомление отправлено! ${response.data.message}`);
        setNotificationForm({
          title: '',
          body: '',
          user_ids: [],
          data: {},
          image: '',
          sound: 'default'
        });
      } else {
        toast.error(`Ошибка отправки: ${response.data.message}`);
      }
    } catch (error) {
      logger.error('Error sending FCM notification:', error);
      toast.error('Ошибка отправки FCM уведомления');
    } finally {
      setLoading(false);
    }
  };

  const renderOverview = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Статус FCM */}
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
          <Activity style={{ width: '20px', height: '20px' }} />
          Статус FCM сервиса
        </h3>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between', 
            padding: '16px',
            border: '1px solid var(--mac-border)', 
            borderRadius: 'var(--mac-radius-md)',
            backgroundColor: 'var(--mac-bg-secondary)'
          }}>
            <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)',
                margin: '0 0 8px 0'
              }}>
                Статус сервиса
              </p>
              <p style={{ 
                fontWeight: 'var(--mac-font-weight-medium)',
                margin: 0
              }}>
                {fcmStatus?.active ? (
                  <MacOSBadge variant="success" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <CheckCircle style={{ width: '12px', height: '12px' }} />
                    Активен
                  </MacOSBadge>
                ) : (
                  <MacOSBadge variant="secondary" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <AlertTriangle style={{ width: '12px', height: '12px' }} />
                    Неактивен
                  </MacOSBadge>
                )}
              </p>
            </div>
          </div>

          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between', 
            padding: '16px',
            border: '1px solid var(--mac-border)', 
            borderRadius: 'var(--mac-radius-md)',
            backgroundColor: 'var(--mac-bg-secondary)'
          }}>
            <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)',
                margin: '0 0 8px 0'
              }}>
                Server Key
              </p>
              <p style={{ 
                fontWeight: 'var(--mac-font-weight-medium)',
                margin: 0
              }}>
                {fcmStatus?.server_key_configured ? (
                  <MacOSBadge variant="success">Настроен</MacOSBadge>
                ) : (
                  <MacOSBadge variant="secondary">Не настроен</MacOSBadge>
                )}
              </p>
            </div>
          </div>

          <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between', 
            padding: '16px',
            border: '1px solid var(--mac-border)', 
            borderRadius: 'var(--mac-radius-md)',
            backgroundColor: 'var(--mac-bg-secondary)'
          }}>
            <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)',
                margin: '0 0 8px 0'
              }}>
                Пользователей с токенами
              </p>
              <p style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)',
                color: 'var(--mac-text-primary)',
                margin: 0
              }}>
                {usersWithTokens.length}
              </p>
            </div>
            <Smartphone style={{ width: '24px', height: '24px', color: 'var(--mac-accent-blue)' }} />
          </div>
        </div>
      </MacOSCard>

      {/* Быстрые действия */}
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
          <Zap style={{ width: '20px', height: '20px' }} />
          Быстрые действия
        </h3>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <MacOSButton 
            onClick={testFCMNotification} 
            disabled={loading || !fcmStatus?.active}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <TestTube style={{ width: '16px', height: '16px' }} />
            Тест FCM
          </MacOSButton>

          <MacOSButton 
            onClick={loadData} 
            disabled={loading}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <RefreshCw style={{ width: '16px', height: '16px' }} />
            Обновить данные
          </MacOSButton>

          <MacOSButton 
            onClick={() => setActiveTab('notifications')} 
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
          >
            <Send style={{ width: '16px', height: '16px' }} />
            Отправить уведомление
          </MacOSButton>
        </div>
      </MacOSCard>
    </div>
  );

  const renderNotifications = () => (
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
          Отправка FCM уведомлений
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
              Заголовок
            </label>
            <MacOSInput
              type="text"
              value={notificationForm.title}
              onChange={(e) => setNotificationForm(prev => ({ ...prev, title: e.target.value }))}
              placeholder="Заголовок уведомления"
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
              Текст сообщения
            </label>
            <MacOSTextarea
              value={notificationForm.body}
              onChange={(e) => setNotificationForm(prev => ({ ...prev, body: e.target.value }))}
              placeholder="Текст уведомления..."
              style={{ width: '100%', minHeight: '100px' }}
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
              Изображение (URL)
            </label>
            <MacOSInput
              type="url"
              value={notificationForm.image}
              onChange={(e) => setNotificationForm(prev => ({ ...prev, image: e.target.value }))}
              placeholder="https://example.com/image.jpg"
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
              Звук
            </label>
            <MacOSSelect
              value={notificationForm.sound}
              onChange={(e) => setNotificationForm(prev => ({ ...prev, sound: e.target.value }))}
              options={[
                { value: 'default', label: 'По умолчанию' },
                { value: 'notification', label: 'Уведомление' },
                { value: 'alert', label: 'Предупреждение' },
                { value: 'chime', label: 'Звонок' }
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
              Получатели
            </label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <p style={{ 
                fontSize: 'var(--mac-font-size-xs)', 
                color: 'var(--mac-text-secondary)',
                margin: 0
              }}>
                Если не выбрать пользователей, уведомление будет отправлено всем активным пользователям
              </p>
              
              <div style={{ 
                maxHeight: '160px', 
                overflowY: 'auto', 
                border: '1px solid var(--mac-border)', 
                borderRadius: 'var(--mac-radius-md)', 
                padding: '8px',
                backgroundColor: 'var(--mac-bg-secondary)'
              }}>
                {usersWithTokens.map(user => (
                  <label key={user.user_id} style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px', 
                    padding: '8px',
                    borderRadius: 'var(--mac-radius-sm)',
                    cursor: 'pointer',
                    transition: 'background-color var(--mac-duration-normal) var(--mac-ease)'
                  }}
                  onMouseEnter={(e) => e.target.style.backgroundColor = 'var(--mac-bg-tertiary)'}
                  onMouseLeave={(e) => e.target.style.backgroundColor = 'transparent'}
                  >
                    <MacOSCheckbox
                      checked={notificationForm.user_ids.includes(user.user_id)}
                      onChange={(checked) => {
                        if (checked) {
                          setNotificationForm(prev => ({
                            ...prev,
                            user_ids: [...prev.user_ids, user.user_id]
                          }));
                        } else {
                          setNotificationForm(prev => ({
                            ...prev,
                            user_ids: prev.user_ids.filter(id => id !== user.user_id)
                          }));
                        }
                      }}
                    />
                    <span style={{ 
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-primary)'
                    }}>
                      {user.full_name || user.username}
                    </span>
                    <MacOSBadge variant={user.push_enabled ? 'success' : 'secondary'} style={{ marginLeft: 'auto' }}>
                      {user.device_type}
                    </MacOSBadge>
                  </label>
                ))}
              </div>
            </div>
          </div>

          <MacOSButton 
            onClick={sendNotification} 
            disabled={loading || !fcmStatus?.active || !notificationForm.title.trim() || !notificationForm.body.trim()}
            style={{ width: '100%' }}
          >
            {loading ? 'Отправка...' : 'Отправить FCM уведомление'}
          </MacOSButton>
        </div>
      </MacOSCard>
    </div>
  );

  const renderUsers = () => (
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
          <Users style={{ width: '20px', height: '20px' }} />
          Пользователи с FCM токенами ({usersWithTokens.length})
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {usersWithTokens.map(user => (
            <div key={user.user_id} style={{ 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'space-between', 
              padding: '16px',
              border: '1px solid var(--mac-border)', 
              borderRadius: 'var(--mac-radius-md)',
              backgroundColor: 'var(--mac-bg-secondary)',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)'
            }}
            onMouseEnter={(e) => e.target.style.backgroundColor = 'var(--mac-bg-tertiary)'}
            onMouseLeave={(e) => e.target.style.backgroundColor = 'var(--mac-bg-secondary)'}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <Smartphone style={{ width: '20px', height: '20px', color: 'var(--mac-text-tertiary)' }} />
                <div>
                  <p style={{ 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-primary)',
                    margin: '0 0 4px 0'
                  }}>
                    {user.full_name || user.username}
                  </p>
                  <p style={{ 
                    fontSize: 'var(--mac-font-size-xs)', 
                    color: 'var(--mac-text-secondary)',
                    margin: '0 0 4px 0'
                  }}>
                    Токен: {user.fcm_token}
                  </p>
                  {user.last_login && (
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-xs)', 
                      color: 'var(--mac-text-tertiary)',
                      margin: 0
                    }}>
                      Последний вход: {new Date(user.last_login).toLocaleString()}
                    </p>
                  )}
                </div>
              </div>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <MacOSBadge variant={user.push_enabled ? 'success' : 'secondary'}>
                  {user.push_enabled ? 'Push включен' : 'Push отключен'}
                </MacOSBadge>
                
                <MacOSBadge variant="outline">
                  {user.device_type || 'web'}
                </MacOSBadge>
              </div>
            </div>
          ))}
          
          {usersWithTokens.length === 0 && (
            <div style={{ 
              textAlign: 'center', 
              padding: '32px 0', 
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-sm)'
            }}>
              Нет пользователей с зарегистрированными FCM токенами
            </div>
          )}
        </div>
      </MacOSCard>
    </div>
  );

  const tabs = [
    { id: 'overview', label: 'Обзор', icon: Activity },
    { id: 'notifications', label: 'Уведомления', icon: Bell },
    { id: 'users', label: 'Пользователи', icon: Users }
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
          <Bell style={{ width: '32px', height: '32px', color: 'var(--mac-warning)' }} />
          <div>
            <h1 style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              Firebase Cloud Messaging
            </h1>
            <p style={{ 
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-sm)',
              margin: 0
            }}>
              Управление push-уведомлениями
            </p>
          </div>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {fcmStatus?.active ? (
            <MacOSBadge variant="success" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <CheckCircle style={{ width: '12px', height: '12px' }} />
              FCM активен
            </MacOSBadge>
          ) : (
            <MacOSBadge variant="secondary" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <AlertTriangle style={{ width: '12px', height: '12px' }} />
              FCM неактивен
            </MacOSBadge>
          )}
        </div>
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
      {loading && !fcmStatus ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <MacOSLoadingSkeleton height="128px" style={{ width: '100%' }} />
          <MacOSLoadingSkeleton height="256px" style={{ width: '100%' }} />
        </div>
      ) : (
        <>
          {activeTab === 'overview' && renderOverview()}
          {activeTab === 'notifications' && renderNotifications()}
          {activeTab === 'users' && renderUsers()}
        </>
      )}
    </div>
  );
};

export default FCMManager;


