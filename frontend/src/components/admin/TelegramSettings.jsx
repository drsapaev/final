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
import { Card, Button, Badge } from '../../design-system/components';

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
      <Card className="p-8">
        <div className="flex items-center justify-center">
          <RefreshCw className="animate-spin mr-2" size={20} />
          <span>Загрузка Telegram настроек...</span>
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
            Настройки Telegram
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Управление Telegram ботом и уведомлениями
          </p>
        </div>
        
        <div className="flex gap-3">
          <Button variant="outline" onClick={loadData} disabled={loading}>
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

      {/* Статистика */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-blue-600">{stats.total_users || 0}</div>
          <div className="text-sm text-gray-600">Всего пользователей</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-green-600">{stats.messages_sent || 0}</div>
          <div className="text-sm text-gray-600">Сообщений отправлено</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-orange-600">{stats.messages_delivered || 0}</div>
          <div className="text-sm text-gray-600">Доставлено</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-red-600">{stats.messages_failed || 0}</div>
          <div className="text-sm text-gray-600">Ошибок</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Основные настройки */}
        <Card className="p-6">
          <h3 className="text-lg font-medium mb-4 flex items-center">
            <Bot size={20} className="mr-2 text-blue-600" />
            Настройки бота
          </h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Key size={16} className="inline mr-1" />
                Токен бота
              </label>
              <div className="flex">
                <input
                  type={showToken ? "text" : "password"}
                  value={settings.bot_token}
                  onChange={(e) => handleSettingChange('bot_token', e.target.value)}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                  placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                />
                <Button
                  variant="outline"
                  onClick={() => setShowToken(!showToken)}
                  className="border-l-0 rounded-l-none"
                >
                  {showToken ? <EyeOff size={16} /> : <Eye size={16} />}
                </Button>
              </div>
              <p className="text-sm text-gray-500 mt-1">
                Получите токен у @BotFather в Telegram
              </p>
            </div>

            {/* Информация о боте */}
            {botInfo && (
              <div className="p-3 bg-green-50 border border-green-200 rounded-lg dark:bg-green-900/20">
                <h4 className="font-medium text-green-800 dark:text-green-400 mb-2">
                  Информация о боте:
                </h4>
                <div className="text-sm space-y-1">
                  <div><strong>Username:</strong> @{botInfo.username}</div>
                  <div><strong>Имя:</strong> {botInfo.first_name}</div>
                  <div><strong>ID:</strong> {botInfo.id}</div>
                  <div><strong>Группы:</strong> {botInfo.can_join_groups ? 'Да' : 'Нет'}</div>
                </div>
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                ID чатов администраторов
              </label>
              <textarea
                value={settings.admin_chat_ids?.join(', ') || ''}
                onChange={(e) => handleSettingChange('admin_chat_ids', e.target.value.split(',').map(id => id.trim()).filter(id => id))}
                rows={2}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                placeholder="123456789, 987654321"
              />
              <p className="text-sm text-gray-500 mt-1">
                ID чатов для получения служебных уведомлений
              </p>
            </div>

            <div className="flex gap-3">
              <Button onClick={testBot} disabled={!settings.bot_token}>
                <TestTube size={16} className="mr-2" />
                Тест бота
              </Button>
              <Button onClick={setWebhook} disabled={!settings.bot_token}>
                <Webhook size={16} className="mr-2" />
                Установить webhook
              </Button>
            </div>
          </div>
        </Card>

        {/* Настройки уведомлений */}
        <Card className="p-6">
          <h3 className="text-lg font-medium mb-4 flex items-center">
            <Bell size={20} className="mr-2 text-green-600" />
            Уведомления
          </h3>
          
          <div className="space-y-4">
            <div className="space-y-3">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={settings.notifications_enabled}
                  onChange={(e) => handleSettingChange('notifications_enabled', e.target.checked)}
                  className="mr-3"
                />
                <span className="text-sm font-medium">Уведомления включены</span>
              </label>

              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={settings.appointment_reminders}
                  onChange={(e) => handleSettingChange('appointment_reminders', e.target.checked)}
                  className="mr-3"
                />
                <span className="text-sm font-medium">Напоминания о приемах</span>
              </label>

              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={settings.lab_results_notifications}
                  onChange={(e) => handleSettingChange('lab_results_notifications', e.target.checked)}
                  className="mr-3"
                />
                <span className="text-sm font-medium">Готовность анализов</span>
              </label>

              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={settings.payment_notifications}
                  onChange={(e) => handleSettingChange('payment_notifications', e.target.checked)}
                  className="mr-3"
                />
                <span className="text-sm font-medium">Уведомления об оплате</span>
              </label>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Globe size={16} className="inline mr-1" />
                Язык по умолчанию
              </label>
              <select
                value={settings.default_language}
                onChange={(e) => handleSettingChange('default_language', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              >
                <option value="ru">Русский</option>
                <option value="uz">O'zbekcha</option>
                <option value="en">English</option>
              </select>
            </div>

            {/* Информация о webhook */}
            {webhookInfo && (
              <div className={`p-3 rounded-lg border ${
                webhookInfo.webhook_set 
                  ? 'bg-green-50 border-green-200 dark:bg-green-900/20'
                  : 'bg-yellow-50 border-yellow-200 dark:bg-yellow-900/20'
              }`}>
                <h4 className={`font-medium mb-2 ${
                  webhookInfo.webhook_set 
                    ? 'text-green-800 dark:text-green-400'
                    : 'text-yellow-800 dark:text-yellow-400'
                }`}>
                  Webhook: {webhookInfo.webhook_set ? 'Настроен' : 'Не настроен'}
                </h4>
                {webhookInfo.webhook_info && (
                  <div className="text-sm space-y-1">
                    <div><strong>URL:</strong> {webhookInfo.webhook_info.url || 'Не установлен'}</div>
                    <div><strong>Обновления:</strong> {webhookInfo.webhook_info.pending_update_count || 0}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Тестирование */}
      <Card className="p-6">
        <h3 className="text-lg font-medium mb-4 flex items-center">
          <Send size={20} className="mr-2 text-purple-600" />
          Тестирование отправки сообщений
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Chat ID получателя
            </label>
            <input
              type="text"
              value={testChatId}
              onChange={(e) => setTestChatId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              placeholder="123456789"
            />
            <p className="text-sm text-gray-500 mt-1">
              ID чата для отправки тестового сообщения
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Текст сообщения
            </label>
            <textarea
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
          </div>
        </div>

        <div className="flex justify-end mt-4">
          <Button 
            onClick={sendTestMessage} 
            disabled={!settings.bot_token || !testChatId || !testMessage}
          >
            <Send size={16} className="mr-2" />
            Отправить тест
          </Button>
        </div>
      </Card>

      {/* Инструкция */}
      <Card className="p-6 bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-700">
        <h3 className="text-lg font-medium mb-2 flex items-center text-blue-800 dark:text-blue-400">
          <MessageSquare size={20} className="mr-2" />
          Настройка Telegram бота
        </h3>
        <div className="text-sm text-blue-700 dark:text-blue-300 space-y-2">
          <p>1. Создайте бота через @BotFather в Telegram</p>
          <p>2. Получите токен бота и вставьте его выше</p>
          <p>3. Нажмите "Тест бота" для проверки подключения</p>
          <p>4. Установите webhook для получения сообщений</p>
          <p>5. Добавьте ID чатов администраторов для служебных уведомлений</p>
        </div>
      </Card>
    </div>
  );
};

export default TelegramSettings;
