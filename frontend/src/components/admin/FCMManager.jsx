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
import api from '../../utils/api';
import { toast } from 'react-toastify';

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
      console.error('Error loading FCM data:', error);
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
      console.error('Error loading FCM status:', error);
    }
  };

  const loadUsersWithTokens = async () => {
    try {
      const response = await api.get('/fcm/user-tokens');
      setUsersWithTokens(response.data.users || []);
    } catch (error) {
      console.error('Error loading users with tokens:', error);
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
      console.error('Error testing FCM:', error);
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
      console.error('Error sending FCM notification:', error);
      toast.error('Ошибка отправки FCM уведомления');
    } finally {
      setLoading(false);
    }
  };

  const renderOverview = () => (
    <div className="space-y-6">
      {/* Статус FCM */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Статус FCM сервиса
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
              <div>
                <p className="text-sm text-gray-600">Статус сервиса</p>
                <p className="font-medium">
                  {fcmStatus?.active ? (
                    <Badge variant="success" className="flex items-center gap-1">
                      <CheckCircle className="h-3 w-3" />
                      Активен
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="flex items-center gap-1">
                      <AlertTriangle className="h-3 w-3" />
                      Неактивен
                    </Badge>
                  )}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
              <div>
                <p className="text-sm text-gray-600">Server Key</p>
                <p className="font-medium">
                  {fcmStatus?.server_key_configured ? (
                    <Badge variant="success">Настроен</Badge>
                  ) : (
                    <Badge variant="secondary">Не настроен</Badge>
                  )}
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
              <div>
                <p className="text-sm text-gray-600">Пользователей с токенами</p>
                <p className="text-2xl font-bold">{usersWithTokens.length}</p>
              </div>
              <Smartphone className="h-8 w-8 text-blue-500" />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Быстрые действия */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            Быстрые действия
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Button 
              onClick={testFCMNotification} 
              disabled={loading || !fcmStatus?.active}
              className="flex items-center gap-2"
            >
              <TestTube className="h-4 w-4" />
              Тест FCM
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

            <Button 
              onClick={() => setActiveTab('notifications')} 
              variant="outline"
              className="flex items-center gap-2"
            >
              <Send className="h-4 w-4" />
              Отправить уведомление
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
            Отправка FCM уведомлений
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Заголовок</label>
            <input
              type="text"
              value={notificationForm.title}
              onChange={(e) => setNotificationForm(prev => ({ ...prev, title: e.target.value }))}
              placeholder="Заголовок уведомления"
              className="w-full p-3 border border-gray-300 rounded-lg"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Текст сообщения</label>
            <textarea
              value={notificationForm.body}
              onChange={(e) => setNotificationForm(prev => ({ ...prev, body: e.target.value }))}
              placeholder="Текст уведомления..."
              className="w-full p-3 border border-gray-300 rounded-lg resize-vertical min-h-[100px]"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Изображение (URL)</label>
            <input
              type="url"
              value={notificationForm.image}
              onChange={(e) => setNotificationForm(prev => ({ ...prev, image: e.target.value }))}
              placeholder="https://example.com/image.jpg"
              className="w-full p-3 border border-gray-300 rounded-lg"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Звук</label>
            <select
              value={notificationForm.sound}
              onChange={(e) => setNotificationForm(prev => ({ ...prev, sound: e.target.value }))}
              className="w-full p-3 border border-gray-300 rounded-lg"
            >
              <option value="default">По умолчанию</option>
              <option value="notification">Уведомление</option>
              <option value="alert">Предупреждение</option>
              <option value="chime">Звонок</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Получатели</label>
            <div className="space-y-2">
              <p className="text-sm text-gray-600">
                Если не выбрать пользователей, уведомление будет отправлено всем активным пользователям
              </p>
              
              <div className="max-h-40 overflow-y-auto border border-gray-200 rounded-lg p-2">
                {usersWithTokens.map(user => (
                  <label key={user.user_id} className="flex items-center gap-2 p-2 hover:bg-gray-50 rounded">
                    <input
                      type="checkbox"
                      checked={notificationForm.user_ids.includes(user.user_id)}
                      onChange={(e) => {
                        if (e.target.checked) {
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
                    <span className="text-sm">{user.full_name || user.username}</span>
                    <Badge variant={user.push_enabled ? "success" : "secondary"} className="ml-auto">
                      {user.device_type}
                    </Badge>
                  </label>
                ))}
              </div>
            </div>
          </div>

          <Button 
            onClick={sendNotification} 
            disabled={loading || !fcmStatus?.active || !notificationForm.title.trim() || !notificationForm.body.trim()}
            className="w-full"
          >
            {loading ? 'Отправка...' : 'Отправить FCM уведомление'}
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
            Пользователи с FCM токенами ({usersWithTokens.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {usersWithTokens.map(user => (
              <div key={user.user_id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                <div className="flex items-center gap-3">
                  <Smartphone className="h-5 w-5 text-gray-400" />
                  <div>
                    <p className="font-medium">{user.full_name || user.username}</p>
                    <p className="text-sm text-gray-600">
                      Токен: {user.fcm_token}
                    </p>
                    {user.last_login && (
                      <p className="text-xs text-gray-500">
                        Последний вход: {new Date(user.last_login).toLocaleString()}
                      </p>
                    )}
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  <Badge variant={user.push_enabled ? "success" : "secondary"}>
                    {user.push_enabled ? "Push включен" : "Push отключен"}
                  </Badge>
                  
                  <Badge variant="outline">
                    {user.device_type || 'web'}
                  </Badge>
                </div>
              </div>
            ))}
            
            {usersWithTokens.length === 0 && (
              <div className="text-center py-8 text-gray-500">
                Нет пользователей с зарегистрированными FCM токенами
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );

  const tabs = [
    { id: 'overview', label: 'Обзор', icon: Activity },
    { id: 'notifications', label: 'Уведомления', icon: Bell },
    { id: 'users', label: 'Пользователи', icon: Users }
  ];

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Bell className="h-8 w-8 text-orange-500" />
          <div>
            <h1 className="text-2xl font-bold">Firebase Cloud Messaging</h1>
            <p className="text-gray-600">Управление push-уведомлениями</p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          {fcmStatus?.active ? (
            <Badge variant="success" className="flex items-center gap-1">
              <CheckCircle className="h-3 w-3" />
              FCM активен
            </Badge>
          ) : (
            <Badge variant="secondary" className="flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" />
              FCM неактивен
            </Badge>
          )}
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
                    ? 'border-orange-500 text-orange-600'
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
      {loading && !fcmStatus ? (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
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


