import { useState, useEffect } from 'react';
import {
  Monitor,
  Palette,
  Image,

  Volume2,

  Eye,

  Users,
  MessageCircle,

  Save,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  TestTube,

  Play,

  Trash2,
  Plus,
  Edit } from
'lucide-react';
import {
  MacOSCard, Button, Select,
} from '../ui/macos';
import { api } from '../../api/client';

import logger from '../../utils/logger';
const DisplayBoardSettings = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [boards, setBoards] = useState([]); // P2 fix: restored value (was const [, setX]; used in loadDisplayData L75)
  const [selectedBoard, setSelectedBoard] = useState(null);
  const [themes, setThemes] = useState([]);
  const [stats, setStats] = useState({});
  const [banners] = useState([]);
  const [showBannerForm, setShowBannerForm] = useState(false); // P2 fix: restored value (used at L545 onClick)
  const [testResults, setTestResults] = useState({});
  const [message, setMessage] = useState({ type: '', text: '' });

  // Опции конфиденциальности
  const privacyOptions = [
  { value: 'full', label: 'Полное ФИО', description: 'Иванов Иван Иванович' },
  { value: 'initials', label: 'Инициалы', description: 'Иванов И.И.' },
  { value: 'none', label: 'Только номер', description: 'Номер A007' }];


  // Языки озвучки
  const voiceLanguages = [
  { value: 'ru', label: 'Русский' },
  { value: 'uz', label: 'O\'zbekcha' },
  { value: 'en', label: 'English' }];


  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);

      // Загружаем табло, темы и статистику
      const [boardsRes, themesRes, statsRes] = await Promise.all([
      api.get('/admin/display/boards'),
      api.get('/admin/display/themes'),
      api.get('/admin/display/stats')]
      );

      if (boardsRes.status >= 200 && boardsRes.status < 300) {
        const boardsData = boardsRes.data;
        setBoards(boardsData);
        if (boardsData.length > 0) {
          setSelectedBoard(boardsData[0]);
        }
      }

      if (themesRes.status >= 200 && themesRes.status < 300) {
        const themesData = themesRes.data;
        setThemes(themesData);
      }

      if (statsRes.status >= 200 && statsRes.status < 300) {
        const statsData = statsRes.data;
        setStats(statsData);
      }

    } catch (error) {
      logger.error('Ошибка загрузки данных табло:', error);
      setMessage({ type: 'error', text: 'Ошибка загрузки данных табло' });
    } finally {
      setLoading(false);
    }
  };

  const handleBoardSettingChange = (key, value) => {
    setSelectedBoard((prev) => ({ ...prev, [key]: value }));
  };

  const saveBoard = async () => {
    if (!selectedBoard) return;

    try {
      setSaving(true);
      setMessage({ type: '', text: '' });

      const response = await api.put(`/admin/display/boards/${selectedBoard.id}`, selectedBoard);

      if (response.status >= 200 && response.status < 300) {
        const result = response.data;
        setMessage({ type: 'success', text: result.message });
      } else {
        throw new Error('Ошибка сохранения настроек табло');
      }
    } catch (error) {
      logger.error('Ошибка сохранения:', error);
      setMessage({ type: 'error', text: 'Ошибка сохранения настроек табло' });
    } finally {
      setSaving(false);
    }
  };

  const testBoard = async (testType) => {
    if (!selectedBoard) return;

    try {
      setTestResults((prev) => ({ ...prev, [testType]: { testing: true } }));

      const testData = {
        test_type: testType,
        test_data: testType === 'call' ? {
          ticket_number: 'A007',
          patient_name: 'Тестовый П.',
          doctor_name: 'Доктор Тест',
          cabinet: '101'
        } : {
          message: 'Тестовое объявление от админ панели'
        }
      };

      const response = await api.post(`/admin/display/boards/${selectedBoard.id}/test`, testData);

      if (response.status >= 200 && response.status < 300) {
        const result = response.data;
        setTestResults((prev) => ({
          ...prev,
          [testType]: {
            success: true,
            message: result.message,
            data: result.test_data
          }
        }));
        setMessage({ type: 'success', text: `Тест "${testType}" выполнен успешно` });
      } else {
        throw new Error('Ошибка тестирования');
      }
    } catch (error) {
      logger.error('Ошибка тестирования:', error);
      setTestResults((prev) => ({
        ...prev,
        [testType]: {
          success: false,
          error: error.message
        }
      }));
      setMessage({ type: 'error', text: 'Ошибка тестирования табло' });
    }
  };

  if (loading) {
    return (
      <MacOSCard className="p-8">
        <div className="flex items-center justify-center">
          <RefreshCw className="animate-spin mr-2" size={20} />
          <span>Загрузка настроек табло...</span>
        </div>
      </MacOSCard>);

  }

  if (!selectedBoard) {
    return (
      <MacOSCard className="p-8">
        <div className="text-center">
          <Monitor size={48} className="mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            Табло не найдены
          </h3>
          <p className="text-gray-500">Создайте первое табло для отображения очереди</p>
        </div>
      </MacOSCard>);

  }

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            Управление табло
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            Настройка информационных экранов и вызовов пациентов
          </p>
        </div>

        <div className="flex gap-3">
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw size={16} className="mr-2" />
            Обновить
          </Button>
          <Button onClick={saveBoard} disabled={saving}>
            {saving ?
            <RefreshCw size={16} className="animate-spin mr-2" /> :

            <Save size={16} className="mr-2" />
            }
            Сохранить
          </Button>
        </div>
      </div>

      {/* Сообщения */}
      {message.text &&
      <div className={`flex items-center p-4 rounded-lg ${message.type === 'success' ?
      'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400' :
      'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'}`
      }>
          {message.type === 'success' ?
        <CheckCircle size={20} className="mr-2" /> :

        <AlertCircle size={20} className="mr-2" />
        }
          {message.text}
        </div>
      }

      {/* Статистика */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MacOSCard className="p-4 text-center">
          <div className="text-2xl font-bold text-blue-600">{stats.total_boards || 0}</div>
          <div className="text-sm text-gray-600">Всего табло</div>
        </MacOSCard>
        <MacOSCard className="p-4 text-center">
          <div className="text-2xl font-bold text-green-600">{stats.total_calls_today || 0}</div>
          <div className="text-sm text-gray-600">Вызовов сегодня</div>
        </MacOSCard>
        <MacOSCard className="p-4 text-center">
          <div className="text-2xl font-bold text-orange-600">{stats.total_announcements || 0}</div>
          <div className="text-sm text-gray-600">Объявлений</div>
        </MacOSCard>
        <MacOSCard className="p-4 text-center">
          <div className="text-2xl font-bold text-purple-600">{Math.round(stats.uptime_percentage || 0)}%</div>
          <div className="text-sm text-gray-600">Время работы</div>
        </MacOSCard>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Основные настройки */}
        <MacOSCard className="p-6">
          <h3 className="text-lg font-medium mb-4 flex items-center">
            <Monitor size={20} className="mr-2 text-blue-600" />
            {selectedBoard.display_name}
          </h3>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Расположение
              </label>
              <input
                type="text"
                aria-label="Display board location"
                value={selectedBoard.location || ''}
                onChange={(e) => handleBoardSettingChange('location', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                placeholder="Зона ожидания, 1 этаж" />
              
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Palette size={16} className="inline mr-1" />
                Тема оформления
              </label>
              <Select
                value={selectedBoard.theme}
                onChange={(value) => handleBoardSettingChange('theme', value)}
                options={themes.map((theme) => ({
                  value: theme.name,
                  label: theme.display_name
                }))}
                size="large"
                className="admin-w-full" />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Eye size={16} className="inline mr-1" />
                Отображение пациентов
              </label>
              <Select
                value={selectedBoard.show_patient_names}
                onChange={(value) => handleBoardSettingChange('show_patient_names', value)}
                options={privacyOptions.map((option) => ({
                  value: option.value,
                  label: `${option.label} - ${option.description}`
                }))}
                size="large"
                className="admin-w-full" />
              <p className="text-sm text-gray-500 mt-1">
                Уровень конфиденциальности для пациентов
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Users size={16} className="inline mr-1" />
                Количество номеров в очереди
              </label>
              <input
                type="number"
                aria-label="Displayed queue number count"
                min="1"
                max="20"
                value={selectedBoard.queue_display_count}
                onChange={(e) => handleBoardSettingChange('queue_display_count', parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white" />
              
              <p className="text-sm text-gray-500 mt-1">
                Сколько номеров показывать в ожидании
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  aria-label="Show doctor photos"
                  checked={selectedBoard.show_doctor_photos}
                  onChange={(e) => handleBoardSettingChange('show_doctor_photos', e.target.checked)}
                  className="mr-2" />
                
                <span className="text-sm font-medium">Фото врачей</span>
              </label>

              <label className="flex items-center">
                <input
                  type="checkbox"
                  aria-label="Show announcements"
                  checked={selectedBoard.show_announcements}
                  onChange={(e) => handleBoardSettingChange('show_announcements', e.target.checked)}
                  className="mr-2" />
                
                <span className="text-sm font-medium">Объявления</span>
              </label>

              <label className="flex items-center">
                <input
                  type="checkbox"
                  aria-label="Show banners"
                  checked={selectedBoard.show_banners}
                  onChange={(e) => handleBoardSettingChange('show_banners', e.target.checked)}
                  className="mr-2" />
                
                <span className="text-sm font-medium">Баннеры</span>
              </label>

              <label className="flex items-center">
                <input
                  type="checkbox"
                  aria-label="Show videos"
                  checked={selectedBoard.show_videos}
                  onChange={(e) => handleBoardSettingChange('show_videos', e.target.checked)}
                  className="mr-2" />
                
                <span className="text-sm font-medium">Видеоролики</span>
              </label>
            </div>
          </div>
        </MacOSCard>

        {/* Настройки звука */}
        <MacOSCard className="p-6">
          <h3 className="text-lg font-medium mb-4 flex items-center">
            <Volume2 size={20} className="mr-2 text-green-600" />
            Звуковые настройки
          </h3>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Длительность показа вызова (сек)
              </label>
              <input
                type="number"
                aria-label="Call display duration seconds"
                min="5"
                max="300"
                value={selectedBoard.call_display_duration}
                onChange={(e) => handleBoardSettingChange('call_display_duration', parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white" />
              
            </div>

            <div className="grid grid-cols-2 gap-4">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  aria-label="Enable sound signals"
                  checked={selectedBoard.sound_enabled}
                  onChange={(e) => handleBoardSettingChange('sound_enabled', e.target.checked)}
                  className="mr-2" />
                
                <span className="text-sm font-medium">Звуковые сигналы</span>
              </label>

              <label className="flex items-center">
                <input
                  type="checkbox"
                  aria-label="Enable voice announcements"
                  checked={selectedBoard.voice_announcements}
                  onChange={(e) => handleBoardSettingChange('voice_announcements', e.target.checked)}
                  className="mr-2" />
                
                <span className="text-sm font-medium">Голосовые объявления</span>
              </label>
            </div>

            {selectedBoard.voice_announcements &&
            <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Язык озвучки
                  </label>
                  <Select
                  value={selectedBoard.voice_language}
                  onChange={(value) => handleBoardSettingChange('voice_language', value)}
                  options={voiceLanguages.map((lang) => ({
                    value: lang.value,
                    label: lang.label
                  }))}
                  size="large"
                  className="admin-w-full" />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Громкость: {selectedBoard.volume_level}%
                  </label>
                  <input
                  type="range"
                  aria-label="Volume level"
                  min="0"
                  max="100"
                  value={selectedBoard.volume_level}
                  onChange={(e) => handleBoardSettingChange('volume_level', parseInt(e.target.value))}
                  className="w-full" />
                
                </div>
              </>
            }
          </div>
        </MacOSCard>
      </div>

      {/* Тестирование */}
      <MacOSCard className="p-6">
        <h3 className="text-lg font-medium mb-4 flex items-center">
          <TestTube size={20} className="mr-2 text-purple-600" />
          Тестирование табло
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="text-center">
            <Button
              onClick={() => testBoard('call')}
              disabled={testResults.call?.testing}
              className="w-full mb-2">
              
              {testResults.call?.testing ?
              <RefreshCw size={16} className="animate-spin mr-2" /> :

              <Play size={16} className="mr-2" />
              }
              Тест вызова
            </Button>
            {testResults.call && !testResults.call.testing &&
            <div className={`text-sm ${testResults.call.success ? 'text-green-600' : 'text-red-600'}`}>
                {testResults.call.success ? '✅ Успешно' : '❌ Ошибка'}
              </div>
            }
          </div>

          <div className="text-center">
            <Button
              onClick={() => testBoard('announcement')}
              disabled={testResults.announcement?.testing}
              className="w-full mb-2"
              variant="outline">
              
              {testResults.announcement?.testing ?
              <RefreshCw size={16} className="animate-spin mr-2" /> :

              <MessageCircle size={16} className="mr-2" />
              }
              Тест объявления
            </Button>
            {testResults.announcement && !testResults.announcement.testing &&
            <div className={`text-sm ${testResults.announcement.success ? 'text-green-600' : 'text-red-600'}`}>
                {testResults.announcement.success ? '✅ Успешно' : '❌ Ошибка'}
              </div>
            }
          </div>

          <div className="text-center">
            <Button
              onClick={() => window.open('/display?board=main_board', '_blank')}
              className="w-full mb-2"
              variant="outline">
              
              <Eye size={16} className="mr-2" />
              Открыть табло
            </Button>
            <div className="text-sm text-gray-500">
              Просмотр в новой вкладке
            </div>
          </div>
        </div>
      </MacOSCard>

      {/* Управление контентом */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Баннеры */}
        <MacOSCard className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium flex items-center">
              <Image size={20} className="mr-2 text-orange-600" />
              Баннеры
            </h3>
            <Button size="sm" onClick={() => setShowBannerForm(true)}>
              <Plus size={14} className="mr-1" />
              Добавить
            </Button>
          </div>

          <div className="space-y-3">
            {banners.length === 0 ?
            <div className="text-center py-8 text-gray-500">
                <Image size={32} className="mx-auto mb-2 opacity-50" />
                <p>Баннеры не добавлены</p>
              </div> :

            banners.map((banner) =>
            <div key={banner.id} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg dark:border-gray-700">
                  <div className="flex items-center">
                    {banner.image_url &&
                <img
                  src={banner.image_url}
                  alt={banner.title}
                  className="w-12 h-8 object-cover rounded mr-3" />

                }
                    <div>
                      <div className="font-medium">{banner.title}</div>
                      <div className="text-sm text-gray-500">{banner.description}</div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      title={`Edit banner ${banner.title}`}
                      aria-label={`Edit banner ${banner.title}`}>
                      <Edit aria-hidden="true" size={14} />
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      title={`Delete banner ${banner.title}`}
                      aria-label={`Delete banner ${banner.title}`}>
                      <Trash2 aria-hidden="true" size={14} />
                    </Button>
                  </div>
                </div>
            )
            }
          </div>
        </MacOSCard>

        {/* Объявления */}
        <MacOSCard className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-medium flex items-center">
              <MessageCircle size={20} className="mr-2 text-green-600" />
              Объявления
            </h3>
            <Button size="sm">
              <Plus size={14} className="mr-1" />
              Добавить
            </Button>
          </div>

          <div className="space-y-3">
            <div className="text-center py-8 text-gray-500">
              <MessageCircle size={32} className="mx-auto mb-2 opacity-50" />
              <p>Объявления не добавлены</p>
            </div>
          </div>
        </MacOSCard>
      </div>

      {/* Информация */}
      <MacOSCard className="p-6 bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-700">
        <h3 className="text-lg font-medium mb-2 flex items-center text-blue-800 dark:text-blue-400">
          <Monitor size={20} className="mr-2" />
          Информация о табло
        </h3>
        <div className="text-sm text-blue-700 dark:text-blue-300 space-y-2">
          <p>• Табло отображает текущую очередь по специалистам и кабинетам</p>
          <p>• Вызовы пациентов синхронизируются с панелями врачей</p>
          <p>• Баннеры и объявления можно планировать по времени</p>
          <p>• Настройки конфиденциальности защищают персональные данные</p>
          <p>• Голосовые объявления поддерживают несколько языков</p>
        </div>
      </MacOSCard>
    </div>);

};

export default DisplayBoardSettings;
