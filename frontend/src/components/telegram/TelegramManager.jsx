import React, { useState, useEffect } from 'react';
import { Card, Button } from '../../design-system/components';
import { 
  MessageSquare, 
  Settings, 
  Users, 
  Send, 
  Bot, 
  CheckCircle, 
  AlertCircle, 
  RefreshCw,
  Plus,
  Edit,
  Trash2,
  Eye,
  EyeOff,
  Copy,
  Download,
  Upload,
  TestTube,
  BarChart3,
  Clock,
  Globe,
  Key,
  Smartphone,
  Mail,
  Phone,
  Calendar,
  FileText,
  QrCode,
  Bell,
  Shield,
  Activity
} from 'lucide-react';

/**
 * Менеджер Telegram интеграции
 * Полное управление ботом, шаблонами и уведомлениями
 */
const TelegramManager = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [activeTab, setActiveTab] = useState('overview');
  const [botStatus, setBotStatus] = useState(null);
  const [settings, setSettings] = useState({});
  const [templates, setTemplates] = useState({});
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState(null);
  const [showTestModal, setShowTestModal] = useState(false);
  const [testMessage, setTestMessage] = useState('');
  const [testChatId, setTestChatId] = useState('');

  useEffect(() => {
    loadBotStatus();
    loadSettings();
    loadTemplates();
    loadUsers();
    loadStats();
  }, []);

  const loadBotStatus = async () => {
    try {
      const response = await fetch('/api/v1/telegram/bot-status', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      const data = await response.json();
      setBotStatus(data);
    } catch (err) {
      setError('Ошибка загрузки статуса бота');
    }
  };

  const loadSettings = async () => {
    try {
      const response = await fetch('/api/v1/admin/telegram/settings', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      const data = await response.json();
      setSettings(data);
    } catch (err) {
      setError('Ошибка загрузки настроек');
    }
  };

  const loadTemplates = async () => {
    try {
      const response = await fetch('/api/v1/admin/telegram/templates?language=ru', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      const data = await response.json();
      setTemplates(data);
    } catch (err) {
      setError('Ошибка загрузки шаблонов');
    }
  };

  const loadUsers = async () => {
    try {
      const response = await fetch('/api/v1/telegram/users?limit=50', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      const data = await response.json();
      setUsers(data.users || []);
    } catch (err) {
      setError('Ошибка загрузки пользователей');
    }
  };

  const loadStats = async () => {
    try {
      const response = await fetch('/api/v1/admin/telegram/stats?days_back=30', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      const data = await response.json();
      setStats(data);
    } catch (err) {
      setError('Ошибка загрузки статистики');
    }
  };

  const testBotConnection = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/v1/admin/telegram/test-bot', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      const data = await response.json();
      
      if (response.ok) {
        setSuccess('Подключение к боту успешно');
        loadBotStatus();
      } else {
        setError(data.detail || 'Ошибка подключения к боту');
      }
    } catch (err) {
      setError('Ошибка подключения к боту');
    } finally {
      setLoading(false);
    }
  };

  const sendTestMessage = async () => {
    if (!testChatId || !testMessage) {
      setError('Введите chat ID и сообщение');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/v1/admin/telegram/send-test-message', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({
          chat_id: parseInt(testChatId),
          message: testMessage
        })
      });

      const data = await response.json();
      
      if (response.ok) {
        setSuccess('Тестовое сообщение отправлено');
        setShowTestModal(false);
        setTestMessage('');
        setTestChatId('');
      } else {
        setError(data.detail || 'Ошибка отправки сообщения');
      }
    } catch (err) {
      setError('Ошибка отправки сообщения');
    } finally {
      setLoading(false);
    }
  };

  const updateSettings = async (newSettings) => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/v1/admin/telegram/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify(newSettings)
      });

      const data = await response.json();
      
      if (response.ok) {
        setSuccess('Настройки обновлены');
        loadSettings();
      } else {
        setError(data.detail || 'Ошибка обновления настроек');
      }
    } catch (err) {
      setError('Ошибка обновления настроек');
    } finally {
      setLoading(false);
    }
  };

  const setWebhook = async (webhookUrl) => {
    setLoading(true);
    setError('');

    try {
      const response = await fetch('/api/v1/admin/telegram/set-webhook', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({ webhook_url: webhookUrl })
      });

      const data = await response.json();
      
      if (response.ok) {
        setSuccess('Webhook установлен успешно');
        loadBotStatus();
      } else {
        setError(data.detail || 'Ошибка установки webhook');
      }
    } catch (err) {
      setError('Ошибка установки webhook');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString('ru-RU');
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'text-green-600 bg-green-50';
      case 'inactive': return 'text-red-600 bg-red-50';
      case 'error': return 'text-yellow-600 bg-yellow-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'active': return 'Активен';
      case 'inactive': return 'Неактивен';
      case 'error': return 'Ошибка';
      default: return 'Неизвестно';
    }
  };

  const renderOverview = () => (
    <div className="space-y-6">
      {/* Статус бота */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <Bot className="w-6 h-6 text-blue-600" />
            <h3 className="text-lg font-semibold">Статус Telegram бота</h3>
          </div>
          <div className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(botStatus?.active ? 'active' : 'inactive')}`}>
            {getStatusLabel(botStatus?.active ? 'active' : 'inactive')}
          </div>
        </div>

        {botStatus?.configured ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="text-center p-4 bg-blue-50 rounded-lg">
                <Users className="w-8 h-8 text-blue-600 mx-auto mb-2" />
                <div className="text-sm font-medium text-blue-800">Пользователи</div>
                <div className="text-xs text-blue-600">{botStatus.stats?.total_users || 0} всего</div>
              </div>
              <div className="text-center p-4 bg-green-50 rounded-lg">
                <Activity className="w-8 h-8 text-green-600 mx-auto mb-2" />
                <div className="text-sm font-medium text-green-800">Активные</div>
                <div className="text-xs text-green-600">{botStatus.stats?.active_users || 0} пользователей</div>
              </div>
              <div className="text-center p-4 bg-purple-50 rounded-lg">
                <FileText className="w-8 h-8 text-purple-600 mx-auto mb-2" />
                <div className="text-sm font-medium text-purple-800">Шаблоны</div>
                <div className="text-xs text-purple-600">{botStatus.stats?.templates || 0} шаблонов</div>
              </div>
            </div>

            <div className="flex space-x-2">
              <Button
                onClick={testBotConnection}
                variant="outline"
                size="sm"
                disabled={loading}
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Проверить подключение
              </Button>
              <Button
                onClick={() => setShowTestModal(true)}
                variant="outline"
                size="sm"
              >
                <TestTube className="w-4 h-4 mr-2" />
                Отправить тест
              </Button>
            </div>
          </div>
        ) : (
          <div className="text-center py-8">
            <Bot className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h4 className="text-lg font-medium text-gray-900 mb-2">
              Telegram бот не настроен
            </h4>
            <p className="text-gray-600 mb-4">
              Настройте бота для отправки уведомлений пациентам
            </p>
            <Button
              onClick={() => setActiveTab('settings')}
            >
              <Settings className="w-4 h-4 mr-2" />
              Настроить бота
            </Button>
          </div>
        )}
      </Card>

      {/* Статистика */}
      {stats && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Статистика за последние 30 дней</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">{stats.messages_sent || 0}</div>
              <div className="text-sm text-gray-600">Отправлено</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">{stats.messages_delivered || 0}</div>
              <div className="text-sm text-gray-600">Доставлено</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">{stats.messages_failed || 0}</div>
              <div className="text-sm text-gray-600">Ошибок</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">{stats.total_users || 0}</div>
              <div className="text-sm text-gray-600">Пользователей</div>
            </div>
          </div>
        </Card>
      )}
    </div>
  );

  const renderSettings = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Настройки бота</h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Токен бота
            </label>
            <div className="flex space-x-2">
              <input
                type="password"
                value={settings.bot_token || ''}
                onChange={(e) => setSettings({...settings, bot_token: e.target.value})}
                placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <Button
                onClick={() => setSettings({...settings, bot_token: ''})}
                variant="outline"
                size="sm"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Получите токен у @BotFather в Telegram
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Webhook URL
            </label>
            <input
              type="url"
              value={settings.webhook_url || ''}
              onChange={(e) => setSettings({...settings, webhook_url: e.target.value})}
              placeholder="https://yourdomain.com/api/v1/telegram/webhook"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              URL для получения обновлений от Telegram
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Уведомления включены
              </label>
              <select
                value={settings.notifications_enabled ? 'true' : 'false'}
                onChange={(e) => setSettings({...settings, notifications_enabled: e.target.value === 'true'})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="true">Включены</option>
                <option value="false">Отключены</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Язык по умолчанию
              </label>
              <select
                value={settings.default_language || 'ru'}
                onChange={(e) => setSettings({...settings, default_language: e.target.value})}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="ru">Русский</option>
                <option value="uz">Узбекский</option>
                <option value="en">Английский</option>
              </select>
            </div>
          </div>

          <div className="flex space-x-2">
            <Button
              onClick={() => updateSettings(settings)}
              disabled={loading}
            >
              <Save className="w-4 h-4 mr-2" />
              Сохранить настройки
            </Button>
            <Button
              onClick={testBotConnection}
              variant="outline"
              disabled={loading}
            >
              <TestTube className="w-4 h-4 mr-2" />
              Проверить бота
            </Button>
            <Button
              onClick={() => setWebhook(settings.webhook_url)}
              variant="outline"
              disabled={loading}
            >
              <Globe className="w-4 h-4 mr-2" />
              Установить webhook
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );

  const renderTemplates = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Шаблоны сообщений</h3>
        <Button
          onClick={loadTemplates}
          variant="outline"
          size="sm"
          disabled={loading}
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Обновить
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(templates).map(([key, template]) => (
          <Card key={key} className="p-4">
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-medium capitalize">{key.replace('_', ' ')}</h4>
              <Button variant="ghost" size="sm">
                <Edit className="w-4 h-4" />
              </Button>
            </div>
            <p className="text-sm text-gray-600 mb-3">
              {template.subject || 'Без темы'}
            </p>
            <div className="text-xs text-gray-500">
              {template.message_text?.length || 0} символов
            </div>
          </Card>
        ))}
      </div>
    </div>
  );

  const renderUsers = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Пользователи бота</h3>
        <Button
          onClick={loadUsers}
          variant="outline"
          size="sm"
          disabled={loading}
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Обновить
        </Button>
      </div>

      {users.length === 0 ? (
        <Card className="p-8 text-center">
          <Users className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h4 className="text-lg font-medium text-gray-900 mb-2">
            Нет пользователей
          </h4>
          <p className="text-gray-600">
            Пользователи появятся здесь после регистрации в боте
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {users.map((user) => (
            <Card key={user.id} className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
                    <span className="text-blue-600 font-medium">
                      {user.first_name?.[0] || 'U'}
                    </span>
                  </div>
                  <div>
                    <div className="font-medium">
                      {user.first_name} {user.last_name}
                    </div>
                    <div className="text-sm text-gray-600">
                      @{user.username || 'без username'}
                    </div>
                    <div className="text-xs text-gray-500">
                      ID: {user.chat_id} • {user.language_code?.toUpperCase()}
                    </div>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    user.active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                  }`}>
                    {user.active ? 'Активен' : 'Неактивен'}
                  </span>
                  <Button variant="ghost" size="sm">
                    <MessageSquare className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Telegram интеграция</h2>
          <p className="text-gray-600">Управление ботом и уведомлениями</p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            onClick={loadBotStatus}
            variant="outline"
            size="sm"
            disabled={loading}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Обновить
          </Button>
        </div>
      </div>

      {/* Навигация */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {[
            { id: 'overview', label: 'Обзор', icon: Bot },
            { id: 'settings', label: 'Настройки', icon: Settings },
            { id: 'templates', label: 'Шаблоны', icon: FileText },
            { id: 'users', label: 'Пользователи', icon: Users }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Уведомления */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-5 h-5 text-red-600" />
            <span className="text-red-800">{error}</span>
          </div>
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-center space-x-2">
            <CheckCircle className="w-5 h-5 text-green-600" />
            <span className="text-green-800">{success}</span>
          </div>
        </div>
      )}

      {/* Контент */}
      {activeTab === 'overview' && renderOverview()}
      {activeTab === 'settings' && renderSettings()}
      {activeTab === 'templates' && renderTemplates()}
      {activeTab === 'users' && renderUsers()}

      {/* Модальное окно тестового сообщения */}
      {showTestModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-md w-full mx-4 p-6">
            <h3 className="text-lg font-semibold mb-4">Отправить тестовое сообщение</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Chat ID
                </label>
                <input
                  type="number"
                  value={testChatId}
                  onChange={(e) => setTestChatId(e.target.value)}
                  placeholder="123456789"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Сообщение
                </label>
                <textarea
                  value={testMessage}
                  onChange={(e) => setTestMessage(e.target.value)}
                  placeholder="Введите тестовое сообщение..."
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="flex justify-end space-x-2 mt-6">
              <Button
                onClick={() => setShowTestModal(false)}
                variant="outline"
              >
                Отмена
              </Button>
              <Button
                onClick={sendTestMessage}
                disabled={loading}
              >
                <Send className="w-4 h-4 mr-2" />
                Отправить
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TelegramManager;
