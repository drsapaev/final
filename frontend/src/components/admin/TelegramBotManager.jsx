import React, { useState, useEffect } from 'react';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Button,
  Badge,
  Skeleton
} from '../ui/native';
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
import api from '../../utils/api';
import { toast } from 'react-toastify';

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

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      await Promise.all([
        loadStats(),
        loadUsers(),
        loadCommands()
      ]);
    } catch (error) {
      console.error('Error loading data:', error);
      toast.error('Ошибка загрузки данных');
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const response = await api.get('/telegram-bot/stats');
      setStats(response.data);
    } catch (error) {
      console.error('Error loading stats:', error);
    }
  };

  const loadUsers = async () => {
    try {
      const response = await api.get('/telegram-bot/users-with-telegram');
      setUsers(response.data.users || []);
    } catch (error) {
      console.error('Error loading users:', error);
    }
  };

  const loadCommands = async () => {
    try {
      const response = await api.get('/telegram-bot/bot-commands');
      setCommands(response.data);
    } catch (error) {
      console.error('Error loading commands:', error);
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
      console.error('Error testing bot:', error);
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
      console.error('Error sending notification:', error);
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
      console.error('Error sending admin alert:', error);
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
      console.error('Error broadcasting system message:', error);
      toast.error('Ошибка отправки системного сообщения');
    } finally {
      setLoading(false);
    }
  };

  const renderOverview = () => (
    <div className="space-y-6">
      {/* Статистика */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Всего пользователей</p>
                <p className="text-2xl font-bold">{stats?.total_users || 0}</p>
              </div>
              <Users className="h-8 w-8 text-blue-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Активные пользователи</p>
                <p className="text-2xl font-bold">{stats?.active_users || 0}</p>
              </div>
              <Activity className="h-8 w-8 text-green-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Администраторы</p>
                <p className="text-2xl font-bold">{stats?.admin_users || 0}</p>
              </div>
              <Shield className="h-8 w-8 text-purple-500" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Сообщений сегодня</p>
                <p className="text-2xl font-bold">{stats?.messages_sent_today || 0}</p>
              </div>
              <MessageSquare className="h-8 w-8 text-orange-500" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Быстрые действия */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            Быстрые действия
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Button 
              onClick={testBot} 
              disabled={loading}
              className="flex items-center gap-2"
            >
              <TestTube className="h-4 w-4" />
              Тест бота
            </Button>

            <Button 
              onClick={sendAdminAlert} 
              disabled={loading}
              variant="outline"
              className="flex items-center gap-2"
            >
              <AlertTriangle className="h-4 w-4" />
              Срочное уведомление
            </Button>

            <Button 
              onClick={broadcastSystemMessage} 
              disabled={loading}
              variant="outline"
              className="flex items-center gap-2"
            >
              <Bell className="h-4 w-4" />
              Системное сообщение
            </Button>

            <Button 
              onClick={loadData} 
              disabled={loading}
              variant="outline"
              className="flex items-center gap-2"
            >
              <RefreshCw className="h-4 w-4" />
              Обновить данные
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );

  const renderNotifications = () => (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Send className="h-5 w-5" />
            Отправка уведомлений
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Текст сообщения</label>
            <textarea
              value={notificationForm.message}
              onChange={(e) => setNotificationForm(prev => ({ ...prev, message: e.target.value }))}
              placeholder="Введите текст уведомления..."
              className="w-full p-3 border border-gray-300 rounded-lg resize-vertical min-h-[100px]"
            />
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-medium">Получатели</label>
            
            <div className="space-y-2">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={notificationForm.send_to_all_admins}
                  onChange={(e) => setNotificationForm(prev => ({ 
                    ...prev, 
                    send_to_all_admins: e.target.checked,
                    send_to_all_users: false
                  }))}
                />
                <span>Всем администраторам</span>
              </label>

              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={notificationForm.send_to_all_users}
                  onChange={(e) => setNotificationForm(prev => ({ 
                    ...prev, 
                    send_to_all_users: e.target.checked,
                    send_to_all_admins: false
                  }))}
                />
                <span>Всем пользователям</span>
              </label>
            </div>
          </div>

          <Button 
            onClick={sendNotification} 
            disabled={loading || !notificationForm.message.trim()}
            className="w-full"
          >
            {loading ? 'Отправка...' : 'Отправить уведомление'}
          </Button>
        </CardContent>
      </Card>
    </div>
  );

  const renderUsers = () => (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            Пользователи с Telegram ({users.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {users.map(user => (
              <div key={user.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                <div className="flex items-center gap-3">
                  <div>
                    <p className="font-medium">{user.full_name || user.username}</p>
                    <p className="text-sm text-gray-600">@{user.username}</p>
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  <Badge variant={user.is_active ? "success" : "secondary"}>
                    {user.is_active ? "Активен" : "Неактивен"}
                  </Badge>
                  
                  <Badge variant={user.role === "Admin" || user.role === "SuperAdmin" ? "primary" : "outline"}>
                    {user.role}
                  </Badge>
                </div>
              </div>
            ))}
            
            {users.length === 0 && (
              <div className="text-center py-8 text-gray-500">
                Нет пользователей с настроенным Telegram
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );

  const renderCommands = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Пользовательские команды</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {commands.user_commands.map(cmd => (
                <div key={cmd.command} className="flex items-start gap-3 p-3 border border-gray-200 rounded-lg">
                  <code className="bg-gray-100 px-2 py-1 rounded text-sm font-mono">
                    {cmd.command}
                  </code>
                  <p className="text-sm text-gray-600 flex-1">{cmd.description}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Административные команды</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {commands.admin_commands.map(cmd => (
                <div key={cmd.command} className="flex items-start gap-3 p-3 border border-gray-200 rounded-lg">
                  <code className="bg-red-100 px-2 py-1 rounded text-sm font-mono">
                    {cmd.command}
                  </code>
                  <p className="text-sm text-gray-600 flex-1">{cmd.description}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
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
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bot className="h-8 w-8 text-blue-500" />
          <div>
            <h1 className="text-2xl font-bold">Telegram Bot</h1>
            <p className="text-gray-600">Управление Telegram ботом клиники</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <Badge variant="success" className="flex items-center gap-1">
            <CheckCircle className="h-3 w-3" />
            Активен
          </Badge>
        </div>
      </div>

      {/* Вкладки */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {tabs.map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Контент вкладок */}
      {loading && !stats ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
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


