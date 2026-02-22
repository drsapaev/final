import { useState, useEffect, useCallback } from 'react';
import { Bell, BellOff, Settings, Check } from 'lucide-react';
import { Button, Card, Badge } from '../ui/native';
import { tokenManager } from '../../utils/tokenManager';
import logger from '../../utils/logger';

/**
 * Компонент для управления мобильными уведомлениями
 */
const MobileNotifications = () => {
  const [notifications, setNotifications] = useState([]);
  const [permission, setPermission] = useState('default');
  const [loading, setLoading] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  const loadNotifications = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/mobile/notifications', {
        headers: {
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        setNotifications(data);
        setUnreadCount(data.filter((n) => !n.is_read).length);
      }
    } catch (error) {
      logger.error('Ошибка загрузки уведомлений:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleServiceWorkerMessage = useCallback((event) => {
    if (event.data && event.data.type === 'NOTIFICATION_RECEIVED') {
      // Обновляем список уведомлений
      loadNotifications();
    }
  }, [loadNotifications]);

  useEffect(() => {
    if ('Notification' in window) {
      setPermission(Notification.permission);
    }
    loadNotifications();

    // Слушаем push уведомления
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('message', handleServiceWorkerMessage);
    }

    return () => {
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.removeEventListener('message', handleServiceWorkerMessage);
      }
    };
  }, [loadNotifications, handleServiceWorkerMessage]);

  const requestNotificationPermission = async () => {
    if (!('Notification' in window)) {
      alert('Уведомления не поддерживаются в этом браузере');
      return;
    }

    try {
      const permission = await Notification.requestPermission();
      setPermission(permission);

      if (permission === 'granted') {
        // Подписываемся на push уведомления
        await subscribeToPushNotifications();
      }
    } catch (error) {
      logger.error('Ошибка запроса разрешения:', error);
    }
  };

  const subscribeToPushNotifications = async () => {
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: process.env.REACT_APP_VAPID_PUBLIC_KEY
      });

      // Отправляем подписку на сервер
      await fetch('/api/v1/mobile/notifications/subscribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        },
        body: JSON.stringify(subscription)
      });

      logger.log('Подписка на push уведомления создана');
    } catch (error) {
      logger.error('Ошибка подписки на push уведомления:', error);
    }
  };

  const markAsRead = async (notificationId) => {
    try {
      await fetch(`/api/v1/mobile/notifications/${notificationId}/read`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        }
      });

      // Обновляем локальное состояние
      setNotifications((prev) =>
      prev.map((n) =>
      n.id === notificationId ? { ...n, is_read: true } : n
      )
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (error) {
      logger.error('Ошибка отметки уведомления как прочитанного:', error);
    }
  };

  const markAllAsRead = async () => {
    try {
      await fetch('/api/v1/mobile/notifications/mark-all-read', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${tokenManager.getAccessToken()}`
        }
      });

      setNotifications((prev) =>
      prev.map((n) => ({ ...n, is_read: true }))
      );
      setUnreadCount(0);
    } catch (error) {
      logger.error('Ошибка отметки всех уведомлений как прочитанных:', error);
    }
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInHours = (now - date) / (1000 * 60 * 60);

    if (diffInHours < 1) {
      return 'Только что';
    } else if (diffInHours < 24) {
      return `${Math.floor(diffInHours)}ч назад`;
    } else {
      return date.toLocaleDateString('ru-RU');
    }
  };

  const getNotificationIcon = (type) => {
    switch (type) {
      case 'appointment':
        return '📅';
      case 'payment':
        return '💳';
      case 'lab_result':
        return '🧪';
      case 'reminder':
        return '⏰';
      default:
        return '🔔';
    }
  };

  if (permission === 'denied') {
    return (
      <Card className="p-4 text-center">
        <BellOff className="w-8 h-8 mx-auto mb-2 text-gray-400" />
        <p className="text-gray-600 mb-3">
          Уведомления заблокированы. Разрешите их в настройках браузера.
        </p>
        <Button
          onClick={() => window.open('chrome://settings/content/notifications')}
          variant="outline"
          size="sm">
          
          <Settings className="w-4 h-4 mr-2" />
          Открыть настройки
        </Button>
      </Card>);

  }

  return (
    <div className="space-y-4">
      {/* Заголовок с кнопками */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Bell className="w-5 h-5" />
          <h3 className="font-semibold">Уведомления</h3>
          {unreadCount > 0 &&
          <Badge variant="destructive" className="text-xs">
              {unreadCount}
            </Badge>
          }
        </div>

        <div className="flex space-x-2">
          {permission === 'default' &&
          <Button
            onClick={requestNotificationPermission}
            size="sm"
            variant="outline">
            
              Включить
            </Button>
          }

          {unreadCount > 0 &&
          <Button
            onClick={markAllAsRead}
            size="sm"
            variant="ghost">
            
              <Check className="w-4 h-4 mr-1" />
              Все прочитано
            </Button>
          }
        </div>
      </div>

      {/* Список уведомлений */}
      <div className="space-y-2">
        {loading ?
        <div className="text-center py-4">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500 mx-auto"></div>
          </div> :
        notifications.length === 0 ?
        <Card className="p-4 text-center text-gray-500">
            <Bell className="w-8 h-8 mx-auto mb-2 text-gray-300" />
            <p>Нет уведомлений</p>
          </Card> :

        notifications.map((notification) =>
        <Card
          key={notification.id}
          className={`p-3 cursor-pointer transition-colors ${notification.is_read ?
          'bg-gray-50' :
          'bg-blue-50 border-blue-200'}`
          }
          onClick={() => markAsRead(notification.id)}>
          
              <div className="flex items-start space-x-3">
                <div className="text-lg">
                  {getNotificationIcon(notification.type)}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <h4 className={`font-medium ${notification.is_read ? 'text-gray-700' : 'text-gray-900'}`
                }>
                      {notification.title}
                    </h4>
                    <span className="text-xs text-gray-500">
                      {formatDate(notification.created_at)}
                    </span>
                  </div>

                  <p className={`text-sm mt-1 ${notification.is_read ? 'text-gray-600' : 'text-gray-700'}`
              }>
                    {notification.message}
                  </p>

                  {!notification.is_read &&
              <div className="mt-2">
                      <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
                    </div>
              }
                </div>
              </div>
            </Card>
        )
        }
      </div>
    </div>);

};

export default MobileNotifications;
