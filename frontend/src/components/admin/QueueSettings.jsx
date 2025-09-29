import React, { useState, useEffect } from 'react';
import { 
  Clock, 
  Users, 
  Hash, 
  Settings, 
  Save, 
  RefreshCw, 
  AlertCircle, 
  CheckCircle,
  TestTube,
  Heart,
  Scissors,
  Stethoscope,
  QrCode,
  Play
} from 'lucide-react';
import { Card, Button, Badge } from '../ui/native';

const QueueSettings = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [settings, setSettings] = useState({
    timezone: 'Asia/Tashkent',
    queue_start_hour: 7,
    auto_close_time: '09:00',
    start_numbers: {
      cardiology: 1,
      dermatology: 15,
      stomatology: 3
    },
    max_per_day: {
      cardiology: 15,
      dermatology: 20,
      stomatology: 12
    }
  });
  const [message, setMessage] = useState({ type: '', text: '' });
  const [testResult, setTestResult] = useState(null);

  // Конфигурация специальностей
  const specialties = [
    { 
      key: 'cardiology', 
      name: 'Кардиология', 
      icon: Heart, 
      color: 'text-red-600',
      description: 'Консультации и ЭхоКГ' 
    },
    { 
      key: 'dermatology', 
      name: 'Дерматология', 
      icon: Stethoscope, 
      color: 'text-orange-600',
      description: 'Дерматология и косметология' 
    },
    { 
      key: 'stomatology', 
      name: 'Стоматология', 
      icon: Scissors, 
      color: 'text-blue-600',
      description: 'Стоматологические услуги' 
    }
  ];

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/admin/queue/settings', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setSettings(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки настроек очередей:', error);
      setMessage({ type: 'error', text: 'Ошибка загрузки настроек очередей' });
    } finally {
      setLoading(false);
    }
  };

  const handleSettingChange = (path, value) => {
    setSettings(prev => {
      const newSettings = { ...prev };
      const keys = path.split('.');
      
      if (keys.length === 1) {
        newSettings[keys[0]] = value;
      } else if (keys.length === 2) {
        newSettings[keys[0]] = { ...newSettings[keys[0]], [keys[1]]: value };
      }
      
      return newSettings;
    });
  };

  const saveSettings = async () => {
    try {
      setSaving(true);
      setMessage({ type: '', text: '' });

      const response = await fetch('/api/v1/admin/queue/settings', {
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
        setSettings(result.settings);
      } else {
        throw new Error('Ошибка сохранения настроек');
      }
    } catch (error) {
      console.error('Ошибка сохранения:', error);
      setMessage({ type: 'error', text: 'Ошибка сохранения настроек очередей' });
    } finally {
      setSaving(false);
    }
  };

  const testQueueGeneration = async (specialty) => {
    try {
      setTesting(true);
      setTestResult(null);

      // Здесь нужно получить ID врача по специальности
      // Для демо используем фиксированные ID
      const doctorIds = {
        cardiology: 1,
        dermatology: 2,
        stomatology: 3
      };

      const response = await fetch('/api/v1/admin/queue/test', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          doctor_id: doctorIds[specialty] || 1,
          date: new Date().toISOString().split('T')[0]
        })
      });

      if (response.ok) {
        const result = await response.json();
        setTestResult(result.test_data);
        setMessage({ type: 'success', text: 'Тест очереди выполнен успешно' });
      } else {
        throw new Error('Ошибка тестирования');
      }
    } catch (error) {
      console.error('Ошибка тестирования:', error);
      setMessage({ type: 'error', text: 'Ошибка тестирования очереди' });
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-8">
        <div className="flex items-center justify-center">
          <RefreshCw className="animate-spin mr-2" size={20} />
          <span>Загрузка настроек очередей...</span>
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
            Настройки очередей
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Управление онлайн-очередью и стартовыми номерами
          </p>
        </div>
        
        <div className="flex gap-3">
          <Button variant="outline" onClick={loadSettings} disabled={loading}>
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Общие настройки */}
        <Card className="p-6">
          <h3 className="text-lg font-medium mb-4 flex items-center">
            <Settings size={20} className="mr-2 text-blue-600" />
            Общие настройки
          </h3>
          
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Clock size={16} className="inline mr-1" />
                Час начала онлайн-очереди
              </label>
              <select
                value={settings.queue_start_hour}
                onChange={(e) => handleSettingChange('queue_start_hour', parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              >
                {Array.from({ length: 24 }, (_, i) => (
                  <option key={i} value={i}>
                    {String(i).padStart(2, '0')}:00
                  </option>
                ))}
              </select>
              <p className="text-sm text-gray-500 mt-1">
                С этого времени доступна онлайн-запись через QR-код
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Время автозакрытия
              </label>
              <input
                type="time"
                value={settings.auto_close_time}
                onChange={(e) => handleSettingChange('auto_close_time', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              />
              <p className="text-sm text-gray-500 mt-1">
                Автоматическое закрытие онлайн-записи (опционально)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Часовой пояс
              </label>
              <select
                value={settings.timezone}
                onChange={(e) => handleSettingChange('timezone', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              >
                <option value="Asia/Tashkent">Ташкент (UTC+5)</option>
                <option value="Asia/Almaty">Алматы (UTC+6)</option>
                <option value="Europe/Moscow">Москва (UTC+3)</option>
                <option value="Asia/Dubai">Дубай (UTC+4)</option>
              </select>
            </div>
          </div>
        </Card>

        {/* Тестирование */}
        <Card className="p-6">
          <h3 className="text-lg font-medium mb-4 flex items-center">
            <TestTube size={20} className="mr-2 text-green-600" />
            Тестирование очереди
          </h3>
          
          <div className="space-y-4">
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Протестируйте генерацию QR-кода для каждой специальности
            </p>

            {specialties.map(specialty => (
              <div key={specialty.key} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg dark:border-gray-700">
                <div className="flex items-center">
                  <specialty.icon size={20} className={`mr-3 ${specialty.color}`} />
                  <div>
                    <div className="font-medium">{specialty.name}</div>
                    <div className="text-sm text-gray-500">{specialty.description}</div>
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => testQueueGeneration(specialty.key)}
                  disabled={testing}
                >
                  {testing ? (
                    <RefreshCw size={14} className="animate-spin" />
                  ) : (
                    <Play size={14} />
                  )}
                </Button>
              </div>
            ))}

            {testResult && (
              <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg dark:bg-green-900/20 dark:border-green-700">
                <h4 className="font-medium text-green-800 dark:text-green-400 mb-2">
                  Результат тестирования:
                </h4>
                <div className="text-sm space-y-1">
                  <div><strong>Токен:</strong> <code className="bg-green-100 px-1 rounded dark:bg-green-800">{testResult.token?.slice(0, 8)}...</code></div>
                  <div><strong>Специальность:</strong> {testResult.doctor_specialty}</div>
                  <div><strong>Кабинет:</strong> {testResult.doctor_cabinet}</div>
                  <div><strong>Стартовый номер:</strong> {testResult.start_number}</div>
                  <div><strong>Лимит в день:</strong> {testResult.max_per_day}</div>
                  <div><strong>QR URL:</strong> <code className="bg-green-100 px-1 rounded dark:bg-green-800">{testResult.qr_url}</code></div>
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>

      {/* Настройки по специальностям */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {specialties.map(specialty => (
          <Card key={specialty.key} className="p-6">
            <h3 className="text-lg font-medium mb-4 flex items-center">
              <specialty.icon size={20} className={`mr-2 ${specialty.color}`} />
              {specialty.name}
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  <Hash size={16} className="inline mr-1" />
                  Стартовый номер
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={settings.start_numbers[specialty.key]}
                  onChange={(e) => handleSettingChange(`start_numbers.${specialty.key}`, parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                />
                <p className="text-sm text-gray-500 mt-1">
                  С какого номера начинается онлайн-очередь
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  <Users size={16} className="inline mr-1" />
                  Лимит в день
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={settings.max_per_day[specialty.key]}
                  onChange={(e) => handleSettingChange(`max_per_day.${specialty.key}`, parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                />
                <p className="text-sm text-gray-500 mt-1">
                  Максимум онлайн-записей в день
                </p>
              </div>

              {/* Текущие настройки */}
              <div className="pt-2 border-t border-gray-200 dark:border-gray-700">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-gray-600 dark:text-gray-400">Диапазон номеров:</span>
                  <Badge variant="outline">
                    {settings.start_numbers[specialty.key]} - {settings.start_numbers[specialty.key] + settings.max_per_day[specialty.key] - 1}
                  </Badge>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Информационная панель */}
      <Card className="p-6 bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-700">
        <h3 className="text-lg font-medium mb-2 flex items-center text-blue-800 dark:text-blue-400">
          <QrCode size={20} className="mr-2" />
          Как работает онлайн-очередь
        </h3>
        <div className="text-sm text-blue-700 dark:text-blue-300 space-y-2">
          <p>• Пациенты сканируют QR-код с {settings.queue_start_hour}:00 до открытия приема</p>
          <p>• Каждый телефон/Telegram может получить только один номер в день</p>
          <p>• При повторном запросе возвращается тот же номер</p>
          <p>• Кнопка "Открыть прием" в регистратуре закрывает онлайн-набор</p>
          <p>• Стартовые номера позволяют избежать конфликтов между специалистами</p>
        </div>
      </Card>
    </div>
  );
};

export default QueueSettings;

