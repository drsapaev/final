import { useState, useEffect, useRef } from 'react';
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

  Plus } from
'lucide-react';
import {
  Card, Button, Select,
  type SelectChangeEvent,
  Input,
  Checkbox } from '../ui/macos';
import { api } from '../../api/client';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';
import type { DisplayTestAudioStatus } from '../../api/ws';

interface DisplayBoard {
  id: string | number;
  name?: string;
  display_name?: string;
  location?: string;
  theme?: string;
  show_patient_names?: string;
  queue_display_count?: number;
  show_doctor_photos?: boolean;
  show_announcements?: boolean;
  show_banners?: boolean;
  show_videos?: boolean;
  call_display_duration?: number;
  sound_enabled?: boolean;
  voice_announcements?: boolean;
  voice_language?: string;
  volume_level?: number;
  [key: string]: unknown;
}

interface DisplayTheme {
  name: string;
  display_name: string;
  [key: string]: unknown;
}

interface DisplayBanner {
  id: string | number;
  title?: string;
  description?: string;
  image_url?: string;
  [key: string]: unknown;
}

interface DisplayDevice {
  id: number;
  device_name: string;
  status: string;
}

interface DisplayStats {
  total_boards: number;
  total_calls_today: number | null;
  total_announcements: number;
  uptime_percentage: number | null;
}

type TestType = 'call' | 'announcement';

interface DisplayTestResult {
  status: 'displayed' | 'busy' | 'unconfirmed' | 'dispatch_failed';
  audio_status?: DisplayTestAudioStatus | null;
}

const DisplayBoardSettings = () => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [boards, setBoards] = useState<DisplayBoard[]>([]);
  const [selectedBoardId, setSelectedBoardId] = useState<DisplayBoard['id']>();
  const selectedBoard = boards.find((board) => board.id === selectedBoardId);
  const [themes, setThemes] = useState<DisplayTheme[]>([]);
  const [stats, setStats] = useState<DisplayStats | null>(null);
  const [detailsVersion, refreshBoardDetails] = useState(0);
  const [devices, setDevices] = useState<DisplayDevice[]>([]);
  const [devicesLoading, setDevicesLoading] = useState(false);
  const [deviceLoadFailed, setDeviceLoadFailed] = useState(false);
  const [deviceId, setDeviceId] = useState('');
  // DISPLAYBANNER-FE-001 (audit PR #3961): баннеры реальны — загружаются
  // с бэкенда (#4016 CRUD), форма Add действительно создаёт баннер
  // (POST), а мёртвые кнопки Edit/Delete без обработчиков убраны.
  const [banners, setBanners] = useState<DisplayBanner[]>([]);
  const [showBannerForm, setShowBannerForm] = useState(false); // P2 fix: restored value (used at L545 onClick)
  const [bannerTitle, setBannerTitle] = useState('');
  const [bannerDescription, setBannerDescription] = useState('');
  const [bannerDuration, setBannerDuration] = useState('10');
  const [testing, setTesting] = useState<TestType | null>(null);
  const [testResult, setTestResult] = useState<DisplayTestResult | null>(null);
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


  const loadData = async () => {
    setLoading(true);
    try {
      const [profiles, themeResult, statsResult] = await Promise.allSettled([
        api.get<DisplayBoard[]>('/admin/display/boards'),
        api.get<DisplayTheme[]>('/admin/display/themes'),
        api.get<DisplayStats>('/admin/display/stats'),
      ]);
      if (profiles.status === 'rejected') throw profiles.reason;
      const available = profiles.value.data;
      setBoards(available);
      setSelectedBoardId((previous) => available.find((board) => board.id === previous)?.id ?? available[0]?.id);
      setThemes(themeResult.status === 'fulfilled' ? themeResult.value.data : []);
      setStats(statsResult.status === 'fulfilled' ? statsResult.value.data : null);
      refreshBoardDetails((version) => version + 1);
    } catch {
      setMessage({ type: 'error', text: t('admin2.db_error_load_boards') });
    } finally {
      setLoading(false);
    }
  };

  const loadDataRef = useRef(loadData);
  loadDataRef.current = loadData;
  useEffect(() => {
    void loadDataRef.current();
  }, []);

  useEffect(() => {
    setBanners([]);
    setShowBannerForm(false);
    setBannerTitle('');
    setBannerDescription('');
    setBannerDuration('10');
    setDevices([]);
    setDeviceId('');
    setTestResult(null);
    setDeviceLoadFailed(false);
    if (selectedBoardId === undefined) return;

    let stale = false;
    setDevicesLoading(true);
    const path = '/admin/display/boards/' + selectedBoardId;
    void api.get<{ banners?: DisplayBanner[] }>(path + '/banners').then(({ data }) => {
      if (!stale) setBanners(Array.isArray(data?.banners) ? data.banners : []);
    }).catch(() => logger.warn('Не удалось загрузить баннеры табло'));
    void api.get<DisplayDevice[]>(path + '/devices').then(({ data }) => {
      if (!stale) setDevices(Array.isArray(data) ? data.filter((device) => device.status === 'active') : []);
    }).catch(() => {
      if (!stale) setDeviceLoadFailed(true);
    }).finally(() => {
      if (!stale) setDevicesLoading(false);
    });
    return () => { stale = true; };
  }, [selectedBoardId, detailsVersion]);

  // DISPLAYBANNER-FE-001: реальное создание баннера через POST
  // /admin/display/boards/{id}/banners (audit #3961).
  const handleCreateBanner = async () => {
    if (!selectedBoard) return;
    const title = bannerTitle.trim();
    if (!title) {
      setMessage({ type: 'error', text: t('admin2.db_error_load_boards') });
      return;
    }
    try {
      setSaving(true);
      const response = await api.post(
        `/admin/display/boards/${selectedBoard.id}/banners`,
        {
          title,
          description: bannerDescription.trim() || undefined,
          display_duration: Number(bannerDuration) > 0 ? Number(bannerDuration) : 10,
        }
      );
      const payload = response.data as { banner_id?: number | string };
      setBanners((prev) => [
        {
          id: payload?.banner_id ?? Date.now(),
          title,
          description: bannerDescription.trim() || undefined,
        },
        ...prev,
      ]);
      setShowBannerForm(false);
      setBannerTitle('');
      setBannerDescription('');
      setBannerDuration('10');
      setMessage({ type: 'success', text: t('admin2.db_banner_created') });
    } catch (createError) {
      logger.error('Ошибка создания баннера:', createError);
      setMessage({ type: 'error', text: t('admin2.db_banner_error') });
    } finally {
      setSaving(false);
    }
  };

  const handleBoardSettingChange = (key: string, value: unknown) => {
    setBoards((previous) => previous.map((board) =>
      board.id === selectedBoardId ? { ...board, [key]: value } : board));
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

  const testBoard = async (testType: TestType) => {
    if (!selectedBoard || !deviceId || testing) return;
    setTesting(testType);
    setTestResult(null);
    try {
      const { data } = await api.post<DisplayTestResult>('/admin/display/boards/' + selectedBoard.id + '/test', {
        device_id: Number(deviceId),
        test_type: testType,
      });
      setTestResult({ status: data?.status ?? 'unconfirmed', audio_status: data?.audio_status });
    } catch {
      setTestResult({ status: 'dispatch_failed' });
    } finally {
      setTesting(null);
    }
  };

  if (loading) {
    return (
      <Card className="p-8">
        <div className="flex items-center justify-center">
          <RefreshCw className="animate-spin mr-2" size={20} />
          <span>{t('admin2.db_loading')}</span>
        </div>
      </Card>);

  }

  if (!selectedBoard) {
    return (
      <Card className="p-8">
        <div className="text-center">
          <Monitor size={48} className="mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
            {t('admin2.db_no_boards')}
          </h3>
          <p className="text-gray-500">{t('admin2.db_no_boards_desc')}</p>
        </div>
      </Card>);

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
          <Button variant="outline" onClick={loadData} disabled={loading || saving || testing !== null}>
            <RefreshCw size={16} className="mr-2" />
            {t('admin2.db_refresh')}
          </Button>
          <Button onClick={saveBoard} disabled={saving || testing !== null}>
            {saving ?
            <RefreshCw size={16} className="animate-spin mr-2" /> :

            <Save size={16} className="mr-2" />
            }
            {t('admin2.db_save')}
          </Button>
        </div>
      </div>

      <Select
        aria-label={t('admin2.db_board_profile')}
        value={String(selectedBoard.id)}
        options={boards.map((board) => ({
          value: String(board.id), label: board.display_name ?? board.name ?? String(board.id),
        }))}
        disabled={saving || testing !== null}
        onChange={(event: SelectChangeEvent) => {
          setSelectedBoardId(boards.find((board) => String(board.id) === event.target.value)?.id);
          setMessage({ type: '', text: '' });
        }}
      />

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
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-blue-600">{stats?.total_boards ?? '—'}</div>
          <div className="text-sm text-gray-600">{t('admin2.db_stat_total_boards')}</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-sm font-medium">{stats?.total_calls_today ?? t('admin2.db_metrics_unavailable')}</div>
          <div className="text-sm text-gray-600">{t('admin2.db_stat_calls_today')}</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-orange-600">{stats?.total_announcements ?? '—'}</div>
          <div className="text-sm text-gray-600">{t('admin2.db_stat_announcements')}</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-sm font-medium">
            {typeof stats?.uptime_percentage === 'number'
              ? Math.round(stats.uptime_percentage) + '%' : t('admin2.db_metrics_unavailable')}
          </div>
          <div className="text-sm text-gray-600">{t('admin2.db_stat_uptime')}</div>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Основные настройки */}
        <Card className="p-6">
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
                onChange={(value: SelectChangeEvent) => handleBoardSettingChange('theme', value.target.value)}
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
                onChange={(value: SelectChangeEvent) => handleBoardSettingChange('show_patient_names', value.target.value)}
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
        </Card>

        {/* Настройки звука */}
        <Card className="p-6">
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
                  onChange={(value: SelectChangeEvent) => handleBoardSettingChange('voice_language', value.target.value)}
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
        </Card>
      </div>

      {/* Тестирование */}
      <Card className="p-6">
        <h3 className="text-lg font-medium mb-4 flex items-center">
          <TestTube size={20} className="mr-2 text-purple-600" />
          {t('admin2.db_testing')}
        </h3>

        <div className="mb-4">
          <Select
            aria-label={t('admin2.db_test_device')}
            value={deviceId}
            options={[
              { value: '', label: t('admin2.db_test_select_device') },
              ...devices.map((device) => ({ value: String(device.id), label: device.device_name })),
            ]}
            onChange={(event: SelectChangeEvent) => {
              setDeviceId(event.target.value);
              setTestResult(null);
            }}
            disabled={devicesLoading || devices.length === 0 || testing !== null}
          />
          <div className="text-sm text-gray-500" role="status">
            {devicesLoading ? t('admin2.db_loading') : deviceLoadFailed
              ? t('admin2.db_test_devices_error') : devices.length === 0
                ? t('admin2.db_test_no_devices') : null}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Button onClick={() => testBoard('call')} disabled={!deviceId || testing !== null}>
            {testing === 'call' ? <RefreshCw size={16} className="animate-spin mr-2" /> : <Play size={16} className="mr-2" />}
            {t('admin2.db_test_call')}
          </Button>
          <Button onClick={() => testBoard('announcement')} disabled={!deviceId || testing !== null} variant="outline">
            {testing === 'announcement' ? <RefreshCw size={16} className="animate-spin mr-2" /> : <MessageCircle size={16} className="mr-2" />}
            {t('admin2.db_test_announcement')}
          </Button>
          <Button
            disabled={!selectedBoard.name}
            onClick={() => window.open('/display-board?board=' + encodeURIComponent(selectedBoard.name ?? ''), '_blank', 'noopener,noreferrer')}
            variant="outline"
          >
            <Eye size={16} className="mr-2" />
            {t('admin2.db_open_board')}
          </Button>
        </div>
        {testResult &&
          <div className="mt-3 text-sm" role="status">
            {t('admin2.db_test_result_' + testResult.status)}
            {testResult.audio_status && <div>{t('admin2.db_test_audio_' + testResult.audio_status)}</div>}
          </div>
        }
      </Card>

      {/* Управление контентом */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Баннеры */}
        <Card className="p-6">
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
            {/* DISPLAYBANNER-FE-001 (audit PR #3961): форма Add реально
                создаёт баннер; мёртвые Edit/Delete без обработчиков
                убраны — бэкенд пока не предоставляет PATCH/DELETE
                баннеров (честный UI вместо фальшивых кнопок). */}
            {showBannerForm &&
          <div className="p-3 border border-gray-200 rounded-lg dark:border-gray-700 space-y-2" data-testid="banner-form">
              <Input
                type="text"
                value={bannerTitle}
                onChange={(e) => setBannerTitle(e.target.value)}
                placeholder={t('admin2.db_banner_title')}
                aria-label="Banner title" />

              <Input
                type="text"
                value={bannerDescription}
                onChange={(e) => setBannerDescription(e.target.value)}
                placeholder={t('admin2.db_banner_description')}
                aria-label="Banner description" />

              <Input
                type="number"
                min={1}
                value={bannerDuration}
                onChange={(e) => setBannerDuration(e.target.value)}
                placeholder="10"
                aria-label="Banner duration" />

              <div className="flex gap-2">
                <Button
                  type="button"
                  size="small"
                  disabled={saving || !bannerTitle.trim()}
                  onClick={handleCreateBanner}
                  data-testid="banner-save">
                  {saving ? '...' : t('admin2.db_save')}
                </Button>
                <Button
                  type="button"
                  size="small"
                  variant="outline"
                  onClick={() => setShowBannerForm(false)}
                  data-testid="banner-cancel">
                  {t('admin2.db_cancel')}
                </Button>
              </div>
            </div>
            }
            {banners.length === 0 && !showBannerForm ?
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
                </div>
            )
            }
          </div>
        </Card>

        {/* Объявления */}
        <Card className="p-6">
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
        </Card>
      </div>

      {/* Информация */}
      <Card className="p-6 bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-700">
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
      </Card>
    </div>);

};

export default DisplayBoardSettings;
