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
  Input,
  Checkbox } from '../ui/macos';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';
const DisplayBoardSettings = () => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [boards, setBoards] = useState([]); // P2 fix: restored value (was const [, setX]; used in loadDisplayData L75)
  const [selectedBoard, setSelectedBoard] = useState(null);
  const [themes, setThemes] = useState([]);
  const [stats, setStats] = useState<Record<string, unknown>>({});
  const [banners] = useState([]);
  const [showBannerForm, setShowBannerForm] = useState(false); // P2 fix: restored value (used at L545 onClick)
  const [testResults, setTestResults] = useState<Record<string, { testing?: boolean; success?: boolean; message?: string; error?: string; [k: string]: unknown }>>({});
  const [message, setMessage] = useState({ type: '', text: '' });

  // Опции конфиденциальности
  const privacyOptions = [
  { value: 'full', label: t('admin2.db_privacy_full_label'), description: t('admin2.db_privacy_full_desc') },
  { value: 'initials', label: t('admin2.db_privacy_initials_label'), description: t('admin2.db_privacy_initials_desc') },
  { value: 'none', label: t('admin2.db_privacy_none_label'), description: t('admin2.db_privacy_none_desc') }];


  // Языки озвучки
  const voiceLanguages = [
  { value: 'ru', label: t('admin2.db_voice_ru') },
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
      setMessage({ type: 'error', text: t('admin2.db_error_load_boards') });
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

      const response = (await api.put(`/admin/display/boards/${selectedBoard.id}`, selectedBoard)) as import('axios').AxiosResponse<Record<string, unknown>>;

      if (response.status >= 200 && response.status < 300) {
        const result = response.data;
        setMessage({ type: 'success', text: String(result.message ?? '') });
      } else {
        throw new Error(t('admin2.db2_save_error'));
      }
    } catch (error) {
      logger.error('Ошибка сохранения:', error);
      setMessage({ type: 'error', text: t('admin2.db_error_save_settings') });
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
          patient_name: t('admin2.db2_test_patient_name'),
          doctor_name: t('admin2.db2_test_doctor_name'),
          cabinet: '101'
        } : {
          message: t('admin2.db2_test_announcement')
        }
      };

      const response = (await api.post(`/admin/display/boards/${selectedBoard.id}/test`, testData)) as import('axios').AxiosResponse<Record<string, unknown>>;

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
        setMessage({ type: 'success', text: t('admin2.db_test_success', { type: testType }) });
      } else {
        throw new Error(t('admin2.db2_test_error'));
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
      setMessage({ type: 'error', text: t('admin2.db_error_test') });
    }
  };

  if (loading) {
    return (
      <MacOSCard className="p-8">
        <div className="flex items-center justify-center">
          <RefreshCw className="animate-spin mr-2" size={20} />
          <span>{t('admin2.db_loading')}</span>
        </div>
      </MacOSCard>);

  }

  if (!selectedBoard) {
    return (
      <MacOSCard className="p-8">
        <div className="text-center">
          <Monitor size={48} className="mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            {t('admin2.db_no_boards')}
          </h3>
          <p className="text-gray-500">{t('admin2.db_no_boards_desc')}</p>
        </div>
      </MacOSCard>);

  }

  return (
    <div className="space-y-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white">
            {t('admin2.db_title')}
          </h2>
          <p className="text-gray-600 dark:text-gray-400">
            {t('admin2.db_subtitle')}
          </p>
        </div>

        <div className="flex gap-3">
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw size={16} className="mr-2" />
            {t('admin2.db_refresh')}
          </Button>
          <Button onClick={saveBoard} disabled={saving}>
            {saving ?
            <RefreshCw size={16} className="animate-spin mr-2" /> :

            <Save size={16} className="mr-2" />
            }
            {t('admin2.db_save')}
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
          <div className="text-2xl font-bold text-blue-600">{Number(stats.total_boards ?? 0)}</div>
          <div className="text-sm text-gray-600">{t('admin2.db_stat_total_boards')}</div>
        </MacOSCard>
        <MacOSCard className="p-4 text-center">
          <div className="text-2xl font-bold text-green-600">{Number(stats.total_calls_today ?? 0)}</div>
          <div className="text-sm text-gray-600">{t('admin2.db_stat_calls_today')}</div>
        </MacOSCard>
        <MacOSCard className="p-4 text-center">
          <div className="text-2xl font-bold text-orange-600">{Number(stats.total_announcements ?? 0)}</div>
          <div className="text-sm text-gray-600">{t('admin2.db_stat_announcements')}</div>
        </MacOSCard>
        <MacOSCard className="p-4 text-center">
          <div className="text-2xl font-bold text-purple-600">{Math.round(Number(stats.uptime_percentage ?? 0))}%</div>
          <div className="text-sm text-gray-600">{t('admin2.db_stat_uptime')}</div>
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
                {t('admin2.db_field_location')}
              </label>
              <Input
                type="text"
                aria-label="Display board location"
                value={selectedBoard.location || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleBoardSettingChange('location', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                placeholder={t('admin2.db_field_location_placeholder')} />
              
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Palette size={16} className="inline mr-1" />
                {t('admin2.db_field_theme')}
              </label>
              <Select
                value={selectedBoard.theme}
                onChange={(value: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleBoardSettingChange('theme', value)}
                options={themes.map((theme) => ({
                  value: theme.name,
                  label: theme.display_name
                }))}
                size="large"
                className="w-full" />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Eye size={16} className="inline mr-1" />
                {t('admin2.db_field_patient_display')}
              </label>
              <Select
                value={selectedBoard.show_patient_names}
                onChange={(value: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleBoardSettingChange('show_patient_names', value)}
                options={privacyOptions.map((option) => ({
                  value: option.value,
                  label: `${option.label} - ${option.description}`
                }))}
                size="large"
                className="w-full" />
              <p className="text-sm text-gray-500 mt-1">
                {t('admin2.db_field_patient_display_desc')}
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                <Users size={16} className="inline mr-1" />
                {t('admin2.db_field_queue_count')}
              </label>
              <Input
                type="number"
                aria-label="Displayed queue number count"
                min="1"
                max="20"
                value={selectedBoard.queue_display_count}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleBoardSettingChange('queue_display_count', parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white" />
              
              <p className="text-sm text-gray-500 mt-1">
                {t('admin2.db_field_queue_count_desc')}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <label className="flex items-center">
                <Checkbox aria-label="Show doctor photos" checked={selectedBoard.show_doctor_photos} onChange={(checked: boolean) => handleBoardSettingChange('show_doctor_photos', checked)}
                  className="mr-2" />
                
                <span className="text-sm font-medium">{t('admin2.db_field_doctor_photos')}</span>
              </label>

              <label className="flex items-center">
                <Checkbox aria-label="Show announcements" checked={selectedBoard.show_announcements} onChange={(checked: boolean) => handleBoardSettingChange('show_announcements', checked)}
                  className="mr-2" />
                
                <span className="text-sm font-medium">{t('admin2.db_announcements')}</span>
              </label>

              <label className="flex items-center">
                <Checkbox aria-label="Show banners" checked={selectedBoard.show_banners} onChange={(checked: boolean) => handleBoardSettingChange('show_banners', checked)}
                  className="mr-2" />
                
                <span className="text-sm font-medium">{t('admin2.db_banners')}</span>
              </label>

              <label className="flex items-center">
                <Checkbox aria-label="Show videos" checked={selectedBoard.show_videos} onChange={(checked: boolean) => handleBoardSettingChange('show_videos', checked)}
                  className="mr-2" />
                
                <span className="text-sm font-medium">{t('admin2.db_field_videos')}</span>
              </label>
            </div>
          </div>
        </MacOSCard>

        {/* Настройки звука */}
        <MacOSCard className="p-6">
          <h3 className="text-lg font-medium mb-4 flex items-center">
            <Volume2 size={20} className="mr-2 text-green-600" />
            {t('admin2.db_sound_settings')}
          </h3>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {t('admin2.db_field_call_duration')}
              </label>
              <Input
                type="number"
                aria-label="Call display duration seconds"
                min="5"
                max="300"
                value={selectedBoard.call_display_duration}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleBoardSettingChange('call_display_duration', parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white" />
              
            </div>

            <div className="grid grid-cols-2 gap-4">
              <label className="flex items-center">
                <Checkbox aria-label="Enable sound signals" checked={selectedBoard.sound_enabled} onChange={(checked: boolean) => handleBoardSettingChange('sound_enabled', checked)}
                  className="mr-2" />
                
                <span className="text-sm font-medium">{t('admin2.db_field_sound_signals')}</span>
              </label>

              <label className="flex items-center">
                <Checkbox aria-label="Enable voice announcements" checked={selectedBoard.voice_announcements} onChange={(checked: boolean) => handleBoardSettingChange('voice_announcements', checked)}
                  className="mr-2" />
                
                <span className="text-sm font-medium">{t('admin2.db_field_voice_announcements')}</span>
              </label>
            </div>

            {selectedBoard.voice_announcements &&
            <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    {t('admin2.db_field_voice_language')}
                  </label>
                  <Select
                  value={selectedBoard.voice_language}
                  onChange={(value: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleBoardSettingChange('voice_language', value)}
                  options={voiceLanguages.map((lang) => ({
                    value: lang.value,
                    label: lang.label
                  }))}
                  size="large"
                  className="w-full" />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    {t('admin2.db_field_volume', { level: selectedBoard.volume_level })}
                  </label>
                  <Input
                  type="range"
                  aria-label="Volume level"
                  min="0"
                  max="100"
                  value={selectedBoard.volume_level}
                  onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleBoardSettingChange('volume_level', parseInt(e.target.value))}
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
          {t('admin2.db_testing')}
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
              {t('admin2.db_test_call')}
            </Button>
            {testResults.call && !testResults.call.testing &&
            <div className={`text-sm ${testResults.call.success ? 'text-green-600' : 'text-red-600'}`}>
                {testResults.call.success ? t('admin2.db_test_success_label') : t('admin2.db_test_error_label')}
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
              {t('admin2.db_test_announcement')}
            </Button>
            {testResults.announcement && !testResults.announcement.testing &&
            <div className={`text-sm ${testResults.announcement.success ? 'text-green-600' : 'text-red-600'}`}>
                {testResults.announcement.success ? t('admin2.db_test_success_label') : t('admin2.db_test_error_label')}
              </div>
            }
          </div>

          <div className="text-center">
            <Button
              onClick={() => window.open('/display-board', '_blank')}
              className="w-full mb-2"
              variant="outline">
              
              <Eye size={16} className="mr-2" />
              {t('admin2.db_open_board')}
            </Button>
            <div className="text-sm text-gray-500">
              {t('admin2.db_open_board_desc')}
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
              {t('admin2.db_banners')}
            </h3>
            <Button size="small" onClick={() => setShowBannerForm(true)}>
              <Plus size={14} className="mr-1" />
              {t('admin2.db_add')}
            </Button>
          </div>

          <div className="space-y-3">
            {banners.length === 0 ?
            <div className="text-center py-8 text-gray-500">
                <Image size={32} className="mx-auto mb-2 opacity-50" />
                <p>{t('admin2.db_banners_empty')}</p>
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
                      size="small"
                      variant="outline"
                      title={`Edit banner ${banner.title}`}
                      aria-label={`Edit banner ${banner.title}`}>
                      <Edit aria-hidden="true" size={14} />
                    </Button>
                    <Button
                      type="button"
                      size="small"
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
              {t('admin2.db_announcements')}
            </h3>
            <Button size="small">
              <Plus size={14} className="mr-1" />
              {t('admin2.db_add')}
            </Button>
          </div>

          <div className="space-y-3">
            <div className="text-center py-8 text-gray-500">
              <MessageCircle size={32} className="mx-auto mb-2 opacity-50" />
              <p>{t('admin2.db_announcements_empty')}</p>
            </div>
          </div>
        </MacOSCard>
      </div>

      {/* Информация */}
      <MacOSCard className="p-6 bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-700">
        <h3 className="text-lg font-medium mb-2 flex items-center text-blue-800 dark:text-blue-400">
          <Monitor size={20} className="mr-2" />
          {t('admin2.db_info_title')}
        </h3>
        <div className="text-sm text-blue-700 dark:text-blue-300 space-y-2">
          <p>{t('admin2.db_info_queue')}</p>
          <p>{t('admin2.db_info_sync')}</p>
          <p>{t('admin2.db_info_schedule')}</p>
          <p>{t('admin2.db_info_privacy')}</p>
          <p>{t('admin2.db_info_voice')}</p>
        </div>
      </MacOSCard>
    </div>);

};

export default DisplayBoardSettings;
