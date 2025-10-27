import React, { useState, useEffect } from 'react';
import { 
  MessageSquare, 
  Bot, 
  Key, 
  Send, 
  Users, 
  Bell,
  Save, 
  RefreshCw, 
  AlertCircle, 
  CheckCircle,
  TestTube,
  Eye,
  EyeOff,
  Globe,
  Settings,
  Webhook,
  BarChart3
} from 'lucide-react';
import { Card, Button, Badge, MacOSInput, MacOSSelect, MacOSCheckbox } from '../ui/macos';

const TelegramSettings = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState({
    bot_token: '',
    webhook_url: '',
    admin_chat_ids: [],
    notifications_enabled: true,
    appointment_reminders: true,
    lab_results_notifications: true,
    payment_notifications: true,
    default_language: 'ru',
    supported_languages: ['ru', 'uz', 'en']
  });
  const [botInfo, setBotInfo] = useState(null);
  const [webhookInfo, setWebhookInfo] = useState(null);
  const [stats, setStats] = useState({});
  const [showToken, setShowToken] = useState(false);
  const [testChatId, setTestChatId] = useState('');
  const [testMessage, setTestMessage] = useState('Тестовое сообщение от админ панели');
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      
      // Загружаем настройки, информацию о боте и статистику
      const [settingsRes, webhookRes, statsRes] = await Promise.all([
        fetch('/api/v1/admin/telegram/settings', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        }),
        fetch('/api/v1/admin/telegram/webhook-info', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        }),
        fetch('/api/v1/admin/telegram/stats?days_back=7', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
        })
      ]);

      if (settingsRes.ok) {
        const settingsData = await settingsRes.json();
        setSettings(settingsData);
      }

      if (webhookRes.ok) {
        const webhookData = await webhookRes.json();
        setWebhookInfo(webhookData);
      }

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

    } catch (error) {
      console.error('Ошибка загрузки Telegram данных:', error);
      setMessage({ type: 'error', text: 'Ошибка загрузки Telegram данных' });
    } finally {
      setLoading(false);
    }
  };

  const handleSettingChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const saveSettings = async () => {
    try {
      setSaving(true);
      setMessage({ type: '', text: '' });

      const response = await fetch('/api/v1/admin/telegram/settings', {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(settings)
      });

      if (response.ok) {
        const result = await response.json();
        setMessage({ type: 'success', text: result.message });
      } else {
        throw new Error('Ошибка сохранения настроек');
      }
    } catch (error) {
      console.error('Ошибка сохранения:', error);
      setMessage({ type: 'error', text: 'Ошибка сохранения настроек Telegram' });
    } finally {
      setSaving(false);
    }
  };

  const testBot = async () => {
    try {
      setMessage({ type: '', text: '' });

      const response = await fetch('/api/v1/admin/telegram/test-bot', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });

      if (response.ok) {
        const result = await response.json();
        setBotInfo(result.bot_info);
        setMessage({ type: 'success', text: result.message });
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }
    } catch (error) {
      console.error('Ошибка тестирования бота:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  const setWebhook = async () => {
    try {
      const webhookUrl = `${window.location.origin}/api/v1/telegram/webhook`;
      
      const response = await fetch('/api/v1/admin/telegram/set-webhook', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ webhook_url: webhookUrl })
      });

      if (response.ok) {
        const result = await response.json();
        setMessage({ type: 'success', text: result.message });
        await loadData(); // Перезагружаем данные
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }
    } catch (error) {
      console.error('Ошибка установки webhook:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  const sendTestMessage = async () => {
    if (!testChatId || !testMessage) {
      setMessage({ type: 'error', text: 'Укажите Chat ID и текст сообщения' });
      return;
    }

    try {
      const response = await fetch('/api/v1/admin/telegram/send-test-message', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          chat_id: parseInt(testChatId),
          message: testMessage
        })
      });

      if (response.ok) {
        const result = await response.json();
        setMessage({ type: 'success', text: result.message });
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }
    } catch (error) {
      console.error('Ошибка отправки:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  if (loading) {
    return (
      <Card style={{ padding: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <RefreshCw style={{ 
            width: '20px', 
            height: '20px', 
            marginRight: '8px', 
            animation: 'spin 1s linear infinite' 
          }} />
          <span style={{ color: 'var(--mac-text-primary)' }}>Загрузка Telegram настроек...</span>
        </div>
      </Card>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Заголовок */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2 style={{ 
            fontSize: 'var(--mac-font-size-2xl)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: 0,
            marginBottom: '4px'
          }}>
            Настройки Telegram
          </h2>
          <p style={{ 
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-text-secondary)',
            margin: 0
          }}>
            Управление Telegram ботом и уведомлениями
          </p>
        </div>
        
        <div style={{ display: 'flex', gap: '12px' }}>
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Обновить
          </Button>
          <Button onClick={saveSettings} disabled={saving}>
            {saving ? (
              <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px', animation: 'spin 1s linear infinite' }} />
            ) : (
              <Save style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            )}
            Сохранить
          </Button>
        </div>
      </div>

      {/* Сообщения */}
      {message.text && (
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          padding: '16px', 
          borderRadius: 'var(--mac-radius-md)',
          backgroundColor: message.type === 'success' 
            ? 'var(--mac-success-bg)' 
            : 'var(--mac-error-bg)',
          color: message.type === 'success' 
            ? 'var(--mac-success)' 
            : 'var(--mac-error)',
          border: `1px solid ${message.type === 'success' 
            ? 'var(--mac-success-border)' 
            : 'var(--mac-error-border)'}`
        }}>
          {message.type === 'success' ? (
            <CheckCircle style={{ width: '20px', height: '20px', marginRight: '8px' }} />
          ) : (
            <AlertCircle style={{ width: '20px', height: '20px', marginRight: '8px' }} />
          )}
          {message.text}
        </div>
      )}

      {/* Статистика */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        <Card style={{ padding: '24px', textAlign: 'center' }}>
          <div style={{ 
            fontSize: 'var(--mac-font-size-2xl)', 
            fontWeight: 'var(--mac-font-weight-bold)', 
            color: 'var(--mac-accent-blue)',
            marginBottom: '8px'
          }}>
            {stats.total_users || 0}
          </div>
          <div style={{ 
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-text-secondary)' 
          }}>
            Всего пользователей
          </div>
        </Card>
        <Card style={{ padding: '24px', textAlign: 'center' }}>
          <div style={{ 
            fontSize: 'var(--mac-font-size-2xl)', 
            fontWeight: 'var(--mac-font-weight-bold)', 
            color: 'var(--mac-success)',
            marginBottom: '8px'
          }}>
            {stats.messages_sent || 0}
          </div>
          <div style={{ 
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-text-secondary)' 
          }}>
            Сообщений отправлено
          </div>
        </Card>
        <Card style={{ padding: '24px', textAlign: 'center' }}>
          <div style={{ 
            fontSize: 'var(--mac-font-size-2xl)', 
            fontWeight: 'var(--mac-font-weight-bold)', 
            color: 'var(--mac-warning)',
            marginBottom: '8px'
          }}>
            {stats.messages_delivered || 0}
          </div>
          <div style={{ 
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-text-secondary)' 
          }}>
            Доставлено
          </div>
        </Card>
        <Card style={{ padding: '24px', textAlign: 'center' }}>
          <div style={{ 
            fontSize: 'var(--mac-font-size-2xl)', 
            fontWeight: 'var(--mac-font-weight-bold)', 
            color: 'var(--mac-error)',
            marginBottom: '8px'
          }}>
            {stats.messages_failed || 0}
          </div>
          <div style={{ 
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-text-secondary)' 
          }}>
            Ошибок
          </div>
        </Card>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '24px' }}>
        {/* Основные настройки */}
        <Card style={{ padding: '24px' }}>
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            marginBottom: '16px', 
            display: 'flex', 
            alignItems: 'center',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
            <Bot style={{ width: '20px', height: '20px', marginRight: '8px', color: 'var(--mac-accent-blue)' }} />
            Настройки бота
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
                <Key style={{ width: '16px', height: '16px', display: 'inline', marginRight: '4px' }} />
                Токен бота
              </label>
              <div style={{ display: 'flex' }}>
                <MacOSInput
                  type={showToken ? "text" : "password"}
                  value={settings.bot_token}
                  onChange={(e) => handleSettingChange('bot_token', e.target.value)}
                  placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                  style={{ flex: 1, borderTopRightRadius: 0, borderBottomRightRadius: 0 }}
                />
                <Button
                  variant="outline"
                  onClick={() => setShowToken(!showToken)}
                  style={{ borderTopLeftRadius: 0, borderBottomLeftRadius: 0 }}
                >
                  {showToken ? <EyeOff style={{ width: '16px', height: '16px' }} /> : <Eye style={{ width: '16px', height: '16px' }} />}
                </Button>
              </div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)', 
                marginTop: '4px',
                margin: 0
              }}>
                Получите токен у @BotFather в Telegram
              </p>
            </div>

            {/* Информация о боте */}
            {botInfo && (
              <div style={{ 
                padding: '12px', 
                backgroundColor: 'var(--mac-success-bg)', 
                border: '1px solid var(--mac-success-border)', 
                borderRadius: 'var(--mac-radius-md)' 
              }}>
                <h4 style={{ 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-success)', 
                  marginBottom: '8px',
                  margin: 0
                }}>
                  Информация о боте:
                </h4>
                <div style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  display: 'flex', 
                  flexDirection: 'column', 
                  gap: '4px' 
                }}>
                  <div style={{ color: 'var(--mac-text-primary)' }}><strong>Username:</strong> @{botInfo.username}</div>
                  <div style={{ color: 'var(--mac-text-primary)' }}><strong>Имя:</strong> {botInfo.first_name}</div>
                  <div style={{ color: 'var(--mac-text-primary)' }}><strong>ID:</strong> {botInfo.id}</div>
                  <div style={{ color: 'var(--mac-text-primary)' }}><strong>Группы:</strong> {botInfo.can_join_groups ? 'Да' : 'Нет'}</div>
                </div>
              </div>
            )}

            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                ID чатов администраторов
              </label>
              <MacOSInput
                value={settings.admin_chat_ids?.join(', ') || ''}
                onChange={(e) => handleSettingChange('admin_chat_ids', e.target.value.split(',').map(id => id.trim()).filter(id => id))}
                placeholder="123456789, 987654321"
                style={{ width: '100%', minHeight: '60px' }}
              />
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                color: 'var(--mac-text-secondary)', 
                marginTop: '4px',
                margin: 0
              }}>
                ID чатов для получения служебных уведомлений
              </p>
            </div>

            <div style={{ display: 'flex', gap: '12px' }}>
              <Button onClick={testBot} disabled={!settings.bot_token}>
                <TestTube style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                Тест бота
              </Button>
              <Button onClick={setWebhook} disabled={!settings.bot_token}>
                <Webhook style={{ width: '16px', height: '16px', marginRight: '8px' }} />
                Установить webhook
              </Button>
            </div>
          </div>
        </Card>

        {/* Настройки уведомлений */}
        <Card style={{ padding: '24px' }}>
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-medium)', 
            marginBottom: '16px', 
            display: 'flex', 
            alignItems: 'center',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
            <Bell style={{ width: '20px', height: '20px', marginRight: '8px', color: 'var(--mac-success)' }} />
            Уведомления
          </h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <label style={{ display: 'flex', alignItems: 'center' }}>
                <MacOSCheckbox
                  checked={settings.notifications_enabled}
                  onChange={(e) => handleSettingChange('notifications_enabled', e.target.checked)}
                  style={{ marginRight: '12px' }}
                />
                <span style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>Уведомления включены</span>
              </label>

              <label style={{ display: 'flex', alignItems: 'center' }}>
                <MacOSCheckbox
                  checked={settings.appointment_reminders}
                  onChange={(e) => handleSettingChange('appointment_reminders', e.target.checked)}
                  style={{ marginRight: '12px' }}
                />
                <span style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>Напоминания о приемах</span>
              </label>

              <label style={{ display: 'flex', alignItems: 'center' }}>
                <MacOSCheckbox
                  checked={settings.lab_results_notifications}
                  onChange={(e) => handleSettingChange('lab_results_notifications', e.target.checked)}
                  style={{ marginRight: '12px' }}
                />
                <span style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>Готовность анализов</span>
              </label>

              <label style={{ display: 'flex', alignItems: 'center' }}>
                <MacOSCheckbox
                  checked={settings.payment_notifications}
                  onChange={(e) => handleSettingChange('payment_notifications', e.target.checked)}
                  style={{ marginRight: '12px' }}
                />
                <span style={{ fontSize: 'var(--mac-font-size-sm)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>Уведомления об оплате</span>
              </label>
            </div>

            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '8px' 
              }}>
                <Globe style={{ width: '16px', height: '16px', display: 'inline', marginRight: '4px' }} />
                Язык по умолчанию
              </label>
              <MacOSSelect
                value={settings.default_language}
                onChange={(e) => handleSettingChange('default_language', e.target.value)}
                options={[
                  { value: 'ru', label: 'Русский' },
                  { value: 'uz', label: "O'zbekcha" },
                  { value: 'en', label: 'English' }
                ]}
                style={{ width: '100%' }}
              />
            </div>

            {/* Информация о webhook */}
            {webhookInfo && (
              <div style={{ 
                padding: '12px', 
                borderRadius: 'var(--mac-radius-md)', 
                border: '1px solid',
                backgroundColor: webhookInfo.webhook_set 
                  ? 'var(--mac-success-bg)' 
                  : 'var(--mac-warning-bg)',
                borderColor: webhookInfo.webhook_set 
                  ? 'var(--mac-success-border)' 
                  : 'var(--mac-warning-border)'
              }}>
                <h4 style={{ 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  marginBottom: '8px',
                  color: webhookInfo.webhook_set 
                    ? 'var(--mac-success)' 
                    : 'var(--mac-warning)',
                  margin: 0
                }}>
                  Webhook: {webhookInfo.webhook_set ? 'Настроен' : 'Не настроен'}
                </h4>
                {webhookInfo.webhook_info && (
                  <div style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    display: 'flex', 
                    flexDirection: 'column', 
                    gap: '4px' 
                  }}>
                    <div style={{ color: 'var(--mac-text-primary)' }}><strong>URL:</strong> {webhookInfo.webhook_info.url || 'Не установлен'}</div>
                    <div style={{ color: 'var(--mac-text-primary)' }}><strong>Обновления:</strong> {webhookInfo.webhook_info.pending_update_count || 0}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Тестирование */}
      <Card style={{ padding: '24px' }}>
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)', 
          fontWeight: 'var(--mac-font-weight-medium)', 
          marginBottom: '16px', 
          display: 'flex', 
          alignItems: 'center',
          color: 'var(--mac-text-primary)',
          margin: 0
        }}>
          <Send style={{ width: '20px', height: '20px', marginRight: '8px', color: 'var(--mac-accent-purple)' }} />
          Тестирование отправки сообщений
        </h3>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '8px' 
            }}>
              Chat ID получателя
            </label>
            <MacOSInput
              type="text"
              value={testChatId}
              onChange={(e) => setTestChatId(e.target.value)}
              placeholder="123456789"
              style={{ width: '100%' }}
            />
            <p style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)', 
              marginTop: '4px',
              margin: 0
            }}>
              ID чата для отправки тестового сообщения
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
              Текст сообщения
            </label>
            <MacOSInput
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
              placeholder="Введите текст сообщения..."
              style={{ width: '100%', minHeight: '80px' }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
          <Button 
            onClick={sendTestMessage} 
            disabled={!settings.bot_token || !testChatId || !testMessage}
          >
            <Send style={{ width: '16px', height: '16px', marginRight: '8px' }} />
            Отправить тест
          </Button>
        </div>
      </Card>

      {/* Инструкция */}
      <Card style={{ 
        padding: '24px', 
        backgroundColor: 'var(--mac-info-bg)', 
        border: '1px solid var(--mac-info-border)' 
      }}>
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)', 
          fontWeight: 'var(--mac-font-weight-medium)', 
          marginBottom: '8px', 
          display: 'flex', 
          alignItems: 'center', 
          color: 'var(--mac-info)',
          margin: 0
        }}>
          <MessageSquare style={{ width: '20px', height: '20px', marginRight: '8px' }} />
          Настройка Telegram бота
        </h3>
        <div style={{ 
          fontSize: 'var(--mac-font-size-sm)', 
          color: 'var(--mac-text-secondary)', 
          display: 'flex', 
          flexDirection: 'column', 
          gap: '8px' 
        }}>
          <p style={{ margin: 0 }}>1. Создайте бота через @BotFather в Telegram</p>
          <p style={{ margin: 0 }}>2. Получите токен бота и вставьте его выше</p>
          <p style={{ margin: 0 }}>3. Нажмите "Тест бота" для проверки подключения</p>
          <p style={{ margin: 0 }}>4. Установите webhook для получения сообщений</p>
          <p style={{ margin: 0 }}>5. Добавьте ID чатов администраторов для служебных уведомлений</p>
        </div>
      </Card>
    </div>
  );
};

export default TelegramSettings;

