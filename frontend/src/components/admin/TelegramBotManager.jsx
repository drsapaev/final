import React, { useState, useEffect, useRef } from 'react';
import {
  MacOSCard,
  MacOSButton,
  MacOSBadge,
  MacOSLoadingSkeleton,
  MacOSTextarea,
  MacOSCheckbox
} from '../ui/macos';
import {
  Bot,
  Send,
  Users,
  MessageSquare,
  Settings,
  AlertTriangle,
  CheckCircle,
  Activity,
  Zap,
  Bell,
  Shield,
  BarChart3,
  RefreshCw,
  Play,
  Pause,
  TestTube
} from 'lucide-react';
import { api } from '../../api/client';
import { toast } from 'react-toastify';

import logger from '../../utils/logger';
const TelegramBotManager = () => {
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [commands, setCommands] = useState({ user_commands: [], admin_commands: [] });
  const [activeTab, setActiveTab] = useState('overview');
  const [notificationForm, setNotificationForm] = useState({
    message: '',
    send_to_all_admins: false,
    send_to_all_users: false,
    user_ids: []
  });
  const [statsError, setStatsError] = useState('');
  const [usersError, setUsersError] = useState('');
  const inFlight = useRef(false);

  useEffect(() => {
    if (inFlight.current) return;
    inFlight.current = true;
    loadData().finally(() => {
      // allow subsequent manual reloads via button
      inFlight.current = false;
    });
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      setStatsError('');
      setUsersError('');
      await Promise.all([loadStats(), loadUsers(), loadCommands()]);
    } catch (error) {
      logger.error('Error loading data:', error);
      toast.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await api.get('/admin/telegram/stats', { params: { days_back: 30 } });
      setStats(response.data);
      setStatsError('');
    } catch (error) {
      logger.error('Error loading stats:', error);
      setStatsError('Не удалось загрузить статистику');
    }
  };

  const loadUsers = async () => {
    try {
      const response = await api.get('/admin/telegram/users', { params: { limit: 50 } });
      const data = response.data || {};
      setUsers(data.users || data || []);
      setUsersError('');
    } catch (error) {
      logger.error('Error loading users:', error);
      setUsersError('Не удалось загрузить пользователей');
    }
  };

  const loadCommands = async () => {
    try {
      const response = await api.get('/telegram-bot/bot-commands');
      setCommands(response.data);
    } catch (error) {
      logger.error('Error loading commands:', error);
    }
  };

  const testBot = async () => {
    try {
      setLoading(true);
      const response = await api.post('/telegram-bot/test-bot');
      if (response.data.success) {
        toast.success('Тестовое сообщение отправлено!');
      }
    } catch (error) {
      logger.error('Error testing bot:', error);
      toast.error('Ошибка тестирования бота');
    } finally {
      setLoading(false);
    }
  };

  const sendNotification = async () => {
    if (!notificationForm.message.trim()) {
      toast.error('Введите текст сообщения');
      return;
    }

    try {
      setLoading(true);
      const response = await api.post('/telegram-bot/send-notification', notificationForm);
      
      if (response.data.success) {
        toast.success(`Уведомление отправлено ${response.data.sent_count} пользователям`);
        setNotificationForm({
          message: '',
          send_to_all_admins: false,
          send_to_all_users: false,
          user_ids: []
        });
      }
    } catch (error) {
      logger.error('Error sending notification:', error);
      toast.error('Ошибка отправки уведомления');
    } finally {
      setLoading(false);
    }
  };

  const sendAdminAlert = async () => {
    const message = prompt('Введите текст срочного уведомления для администраторов:');
    if (!message) return;

    try {
      setLoading(true);
      const response = await api.post('/telegram-bot/send-admin-alert', { message });
      
      if (response.data.success) {
        toast.success('Срочное уведомление отправлено администраторам');
      }
    } catch (error) {
      logger.error('Error sending admin alert:', error);
      toast.error('Ошибка отправки срочного уведомления');
    } finally {
      setLoading(false);
    }
  };

  const broadcastSystemMessage = async () => {
    const message = prompt('Введите системное сообщение для всех пользователей:');
    if (!message) return;

    const messageType = prompt('Тип сообщения (info/warning/error/success):', 'info');

    try {
      setLoading(true);
      const response = await api.post('/telegram-bot/broadcast-system-message', {
        message,
        message_type: messageType
      });
      
      if (response.data.success) {
        toast.success(`Системное сообщение отправлено ${response.data.sent_count} пользователям`);
      }
    } catch (error) {
      logger.error('Error broadcasting system message:', error);
      toast.error('Ошибка отправки системного сообщения');
    } finally {
      setLoading(false);
    }
  };

  const renderOverview = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Статистика */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
        gap: '16px' 
      }}>
        <MacOSCard style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)',
                margin: '0 0 8px 0'
              }}>
                Всего пользователей
              </p>
              <p style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)',
                color: 'var(--mac-text-primary)',
                margin: 0
              }}>
                {stats?.total_users || 0}
              </p>
              </div>
            <Users style={{ width: '24px', height: '24px', color: 'var(--mac-accent-blue)' }} />
            </div>
        </MacOSCard>

        <MacOSCard style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)',
                margin: '0 0 8px 0'
              }}>
                Активные пользователи
              </p>
              <p style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)',
                color: 'var(--mac-text-primary)',
                margin: 0
              }}>
                {stats?.active_users || 0}
              </p>
              </div>
            <Activity style={{ width: '24px', height: '24px', color: 'var(--mac-success)' }} />
            </div>
        </MacOSCard>

        <MacOSCard style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)',
                margin: '0 0 8px 0'
              }}>
                Администраторы
              </p>
              <p style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)',
                color: 'var(--mac-text-primary)',
                margin: 0
              }}>
                {stats?.admin_users || 0}
              </p>
              </div>
            <Shield style={{ width: '24px', height: '24px', color: 'var(--mac-warning)' }} />
            </div>
        </MacOSCard>

        <MacOSCard style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)',
                margin: '0 0 8px 0'
              }}>
                Сообщений сегодня
              </p>
              <p style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)',
                color: 'var(--mac-text-primary)',
                margin: 0
              }}>
                {stats?.messages_sent_today || 0}
              </p>
              </div>
            <MessageSquare style={{ width: '24px', height: '24px', color: 'var(--mac-warning)' }} />
            </div>
        </MacOSCard>
      </div>

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
              onClick={testBot} 
              disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
            <TestTube style={{ width: '16px', height: '16px' }} />
              Тест бота
          </MacOSButton>

          <MacOSButton 
              onClick={sendAdminAlert} 
              disabled={loading}
              variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
            <AlertTriangle style={{ width: '16px', height: '16px' }} />
              Срочное уведомление
          </MacOSButton>

          <MacOSButton 
              onClick={broadcastSystemMessage} 
              disabled={loading}
              variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            >
            <Bell style={{ width: '16px', height: '16px' }} />
              Системное сообщение
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
            Отправка уведомлений
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
              Текст сообщения
            </label>
            <MacOSTextarea
              value={notificationForm.message}
              onChange={(e) => setNotificationForm(prev => ({ ...prev, message: e.target.value }))}
              placeholder="Введите текст уведомления..."
              style={{ width: '100%', minHeight: '100px' }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
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
              <label style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                cursor: 'pointer'
              }}>
                <MacOSCheckbox
                  checked={notificationForm.send_to_all_admins}
                  onChange={(checked) => setNotificationForm(prev => ({ 
                    ...prev, 
                    send_to_all_admins: checked,
                    send_to_all_users: false
                  }))}
                />
                <span style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-primary)'
                }}>
                  Всем администраторам
                </span>
              </label>

              <label style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                cursor: 'pointer'
              }}>
                <MacOSCheckbox
                  checked={notificationForm.send_to_all_users}
                  onChange={(checked) => setNotificationForm(prev => ({ 
                    ...prev, 
                    send_to_all_users: checked,
                    send_to_all_admins: false
                  }))}
                />
                <span style={{ 
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-primary)'
                }}>
                  Всем пользователям
                </span>
              </label>
            </div>
          </div>

          <MacOSButton 
            onClick={sendNotification} 
            disabled={loading || !notificationForm.message.trim()}
            style={{ width: '100%' }}
          >
            {loading ? 'Отправка...' : 'Отправить уведомление'}
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
            Пользователи с Telegram ({users.length})
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {users.map(user => (
            <div key={user.id} style={{ 
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
                    margin: 0
                  }}>
                    @{user.username}
                  </p>
                  </div>
                </div>
                
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <MacOSBadge variant={user.is_active ? 'success' : 'secondary'}>
                    {user.is_active ? 'Активен' : 'Неактивен'}
                </MacOSBadge>
                  
                <MacOSBadge variant={user.role === 'Admin' || user.role === 'SuperAdmin' ? 'primary' : 'outline'}>
                    {user.role}
                </MacOSBadge>
                </div>
              </div>
            ))}
            
            {users.length === 0 && (
            <div style={{ 
              textAlign: 'center', 
              padding: '32px 0', 
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-sm)'
            }}>
                Нет пользователей с настроенным Telegram
              </div>
            )}
          </div>
      </MacOSCard>
    </div>
  );

  const renderCommands = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
        gap: '24px' 
      }}>
        <MacOSCard style={{ padding: '24px' }}>
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)',
            margin: '0 0 16px 0'
          }}>
            Пользовательские команды
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {commands.user_commands.map(cmd => (
              <div key={cmd.command} style={{ 
                display: 'flex', 
                alignItems: 'flex-start', 
                gap: '12px', 
                padding: '12px',
                border: '1px solid var(--mac-border)', 
                borderRadius: 'var(--mac-radius-md)',
                backgroundColor: 'var(--mac-bg-secondary)'
              }}>
                <code style={{ 
                  backgroundColor: 'var(--mac-bg-tertiary)', 
                  padding: '4px 8px', 
                  borderRadius: 'var(--mac-radius-sm)', 
                  fontSize: 'var(--mac-font-size-xs)', 
                  fontFamily: 'var(--mac-font-mono)',
                  color: 'var(--mac-text-primary)',
                  fontWeight: 'var(--mac-font-weight-medium)'
                }}>
                    {cmd.command}
                  </code>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0,
                  flex: 1
                }}>
                  {cmd.description}
                </p>
                </div>
              ))}
            </div>
        </MacOSCard>

        <MacOSCard style={{ padding: '24px' }}>
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)',
            margin: '0 0 16px 0'
          }}>
            Административные команды
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {commands.admin_commands.map(cmd => (
              <div key={cmd.command} style={{ 
                display: 'flex', 
                alignItems: 'flex-start', 
                gap: '12px', 
                padding: '12px',
                border: '1px solid var(--mac-border)', 
                borderRadius: 'var(--mac-radius-md)',
                backgroundColor: 'var(--mac-bg-secondary)'
              }}>
                <code style={{ 
                  backgroundColor: 'var(--mac-error-bg)', 
                  padding: '4px 8px', 
                  borderRadius: 'var(--mac-radius-sm)', 
                  fontSize: 'var(--mac-font-size-xs)', 
                  fontFamily: 'var(--mac-font-mono)',
                  color: 'var(--mac-error)',
                  fontWeight: 'var(--mac-font-weight-medium)'
                }}>
                    {cmd.command}
                  </code>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-text-secondary)',
                  margin: 0,
                  flex: 1
                }}>
                  {cmd.description}
                </p>
                </div>
              ))}
            </div>
        </MacOSCard>
      </div>
    </div>
  );

  const tabs = [
    { id: 'overview', label: 'Обзор', icon: BarChart3 },
    { id: 'notifications', label: 'Уведомления', icon: Bell },
    { id: 'users', label: 'Пользователи', icon: Users },
    { id: 'commands', label: 'Команды', icon: Bot }
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
          <Bot style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
          <div>
            <h1 style={{ 
              fontSize: 'var(--mac-font-size-2xl)', 
              fontWeight: 'var(--mac-font-weight-semibold)', 
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
              Telegram Bot
            </h1>
            <p style={{ 
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-sm)',
              margin: 0
            }}>
              Управление Telegram ботом клиники
            </p>
          </div>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <MacOSBadge variant="success" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <CheckCircle style={{ width: '12px', height: '12px' }} />
            Активен
          </MacOSBadge>
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
      {loading && !stats ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <MacOSLoadingSkeleton height="128px" style={{ width: '100%' }} />
          <MacOSLoadingSkeleton height="256px" style={{ width: '100%' }} />
        </div>
      ) : (
        <>
          {activeTab === 'overview' && renderOverview()}
          {activeTab === 'notifications' && renderNotifications()}
          {activeTab === 'users' && renderUsers()}
          {activeTab === 'commands' && renderCommands()}
        </>
      )}
    </div>
  );
};

export default TelegramBotManager;


