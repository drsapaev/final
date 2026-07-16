import { useState, useEffect } from 'react';
import {
  MessageSquare,
  Bot,
  Key,
  Send,

  Bell,
  Save,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  TestTube,
  Eye,
  EyeOff,
  Globe,

  Webhook } from

'lucide-react';
import {
  MacOSCard, Button, Input, Select, Checkbox,
} from '../ui/macos';

import { api } from '../../api/client';
import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';

const getLanguageOptions = (t) => [
  { value: 'ru', label: t('admin2.ts_lang_ru') },
  { value: 'uz', label: 'O\'zbekcha' },
  { value: 'en', label: 'English' }
];

const TelegramSettings = () => {
  const { t } = useTranslation();
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
  const [testMessage, setTestMessage] = useState(t('admin2.ts_default_test_message'));
  const [message, setMessage] = useState({ type: '', text: '' });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);

      // Загружаем настройки, информацию о боте и статистику
      const [settingsRes, webhookRes, statsRes] = await Promise.allSettled([
        api.get('/admin/telegram/settings'),
        api.get('/admin/telegram/webhook-info'),
        api.get('/admin/telegram/stats', { params: { days_back: 7 } }),
      ]);

      if (settingsRes.status === 'fulfilled') {
        setSettings(settingsRes.value.data);
      }

      if (webhookRes.status === 'fulfilled') {
        setWebhookInfo(webhookRes.value.data);
      }

      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value.data);
      }

    } catch (error) {
      logger.error('Ошибка загрузки Telegram данных:', error);
      setMessage({ type: 'error', text: t('admin2.ts_load_data_error') });
    } finally {
      setLoading(false);
    }
  };

  const handleSettingChange = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const saveSettings = async () => {
    try {
      setSaving(true);
      setMessage({ type: '', text: '' });

      const { data: result } = await api.put('/admin/telegram/settings', settings);
      setMessage({ type: 'success', text: result.message || t('admin2.ts_settings_saved') });
    } catch (error) {
      logger.error('Ошибка сохранения:', error);
      setMessage({ type: 'error', text: t('admin2.ts_save_error') });
    } finally {
      setSaving(false);
    }
  };

  const testBot = async () => {
    try {
      setMessage({ type: '', text: '' });

      const { data: result } = await api.post('/admin/telegram/test-bot');
      setBotInfo(result.bot_info);
      setMessage({ type: 'success', text: result.message });
    } catch (error) {
      logger.error('Ошибка тестирования бота:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  const setWebhook = async () => {
    try {
      const webhookUrl = `${window.location.origin}/api/v1/telegram/webhook`;

      const { data: result } = await api.post('/admin/telegram/set-webhook', { webhook_url: webhookUrl });
      setMessage({ type: 'success', text: result.message });
      await loadData(); // Перезагружаем данные
    } catch (error) {
      logger.error('Ошибка установки webhook:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  const sendTestMessage = async () => {
    if (!testChatId || !testMessage) {
      setMessage({ type: 'error', text: t('admin2.ts_test_required') });
      return;
    }

    try {
      const { data: result } = await api.post('/admin/telegram/send-test-message', {
        chat_id: parseInt(testChatId),
        message: testMessage
      });
      setMessage({ type: 'success', text: result.message });
    } catch (error) {
      logger.error('Ошибка отправки:', error);
      setMessage({ type: 'error', text: error.message });
    }
  };

  if (loading) {
    return (
      <MacOSCard className="admin-p-32">
        <div className="admin-flex-ai-center-jc-center">
          <RefreshCw className="admin-w-20-h-20-mr-8-anim-spin1slinearinfinite" />
          <span className="text-[var(--mac-text-primary)]">{t('admin2.ts_loading')}</span>
        </div>
      </MacOSCard>);

  }

  return (
    <div className="flex flex-col gap-6">
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="admin-2xl-semi-primary-m-0-mb-4">
            {t('admin2.ts_page_title')}
          </h2>
          <p className="admin-sm-secondary-m-0">
            {t('admin2.ts_page_subtitle')}
          </p>
        </div>

        <div className="admin-flex-gap-12">
          <Button variant="outline" onClick={loadData} disabled={loading}>
            <RefreshCw className="w-4 h-4 mr-2" />
            {t('admin2.ts_refresh')}
          </Button>
          <Button onClick={saveSettings} disabled={saving}>
            {saving ?
            <RefreshCw className="admin-w-16-h-16-mr-8-anim-spin1slinearinfinite" /> :

            <Save className="w-4 h-4 mr-2" />
            }
            {t('admin2.ts_save')}
          </Button>
        </div>
      </div>

      {/* Сообщения */}
      {message.text &&
      <div className="admin-flex-ai-center-p-16-radius-var--mac-radius-md" style={{ '--admin-backgroundColor': message.type === 'success' ?
        'var(--mac-success-bg)' :
        'var(--mac-error-bg)', '--admin-color': message.type === 'success' ?
        'var(--mac-success)' :
        'var(--mac-error)', '--admin-border': `1px solid ${message.type === 'success' ?
        'var(--mac-success-border)' :
        'var(--mac-error-border)'}` }}>
          {message.type === 'success' ?
        <CheckCircle className="admin-w-20-h-20-mr-8" /> :

        <AlertCircle className="admin-w-20-h-20-mr-8" />
        }
          {message.text}
        </div>
      }

      {/* Статистика */}
      <div className="admin-grid-gtc-rauto-fitcminmax200pxc1fr-gap-16">
        <MacOSCard className="admin-p-24-ta-center">
          <div className="admin-2xl-bold-blue-mb-8">
            {stats.total_users || 0}
          </div>
          <div className="text-sm text-[var(--mac-text-secondary)]">
            {t('admin2.ts_stat_total_users')}
          </div>
        </MacOSCard>
        <MacOSCard className="admin-p-24-ta-center">
          <div className="admin-2xl-bold-success-mb-8">
            {stats.messages_sent || 0}
          </div>
          <div className="text-sm text-[var(--mac-text-secondary)]">
            {t('admin2.ts_stat_messages_sent')}
          </div>
        </MacOSCard>
        <MacOSCard className="admin-p-24-ta-center">
          <div className="admin-2xl-bold-warning-mb-8">
            {stats.messages_delivered || 0}
          </div>
          <div className="text-sm text-[var(--mac-text-secondary)]">
            {t('admin2.ts_stat_messages_delivered')}
          </div>
        </MacOSCard>
        <MacOSCard className="admin-p-24-ta-center">
          <div className="admin-2xl-bold-error-mb-8">
            {stats.messages_failed || 0}
          </div>
          <div className="text-sm text-[var(--mac-text-secondary)]">
            {t('admin2.ts_stat_messages_failed')}
          </div>
        </MacOSCard>
      </div>

      <div className="admin-grid-gtc-rauto-fitcminmax400pxc1fr-gap-24">
        {/* Основные настройки */}
        <MacOSCard className="p-6">
          <h3 className="admin-lg-med-mb-16-flex-ai-center-primary-m-0">
            <Bot className="admin-w-20-h-20-mr-8-blue" />
            {t('admin2.ts_bot_settings_title')}
          </h3>

          <div className="flex flex-col gap-4">
            <div>
              <label className="admin-block-sm-med-primary-mb-8">
                <Key className="admin-w-16-h-16-inline-mr-4" />
                {t('admin2.ts_bot_token_label')}
              </label>
              <div className="admin-flex">
                <Input
                  type={showToken ? 'text' : 'password'}
                  value={settings.bot_token}
                  onChange={(e) => handleSettingChange('bot_token', e.target.value)}
                  placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                  className="admin-flex-1-bordertoprightradius-ba27c5-borderbottomrightradius-8aa152" />
                
                <Button
                  type="button"
                  variant="outline"
                  title={showToken ? 'Hide Telegram bot token' : 'Show Telegram bot token'}
                  aria-label={showToken ? 'Hide Telegram bot token' : 'Show Telegram bot token'}
                  onClick={() => setShowToken(!showToken)}
                  className="admin-bordertopleftradius-e03ef8-borderbottomleftradius-355679">
                  
                  {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </Button>
              </div>
              <p className="admin-sm-secondary-mt-4-m-0">
                {t('admin2.ts_bot_token_hint')}
              </p>
            </div>

            {/* Информация о боте */}
            {botInfo &&
            <div className="admin-p-12-bg-success-bg-bd-1solidvar-mac-success-border-radius-var--mac-radius-md">
                <h4 className="admin-med-success-mb-8-m-0">
                  {t('admin2.ts_bot_info_title')}
                </h4>
                <div className="admin-sm-flex-col-gap-4">
                  <div className="text-[var(--mac-text-primary)]"><strong>Username:</strong> @{botInfo.username}</div>
                  <div className="text-[var(--mac-text-primary)]"><strong>{t('admin2.ts_bot_info_name')}</strong> {botInfo.first_name}</div>
                  <div className="text-[var(--mac-text-primary)]"><strong>ID:</strong> {botInfo.id}</div>
                  <div className="text-[var(--mac-text-primary)]"><strong>{t('admin2.ts_bot_info_groups')}</strong> {botInfo.can_join_groups ? t('admin2.ts_yes') : t('admin2.ts_no')}</div>
                </div>
              </div>
            }

            <div>
              <label className="admin-block-sm-med-primary-mb-8">
                {t('admin2.ts_admin_chat_ids_label')}
              </label>
              <Input
                value={settings.admin_chat_ids?.join(', ') || ''}
                onChange={(e) => handleSettingChange('admin_chat_ids', e.target.value.split(',').map((id) => id.trim()).filter((id) => id))}
                placeholder="123456789, 987654321"
                className="admin-w-100pct-minh-60" />
              
              <p className="admin-sm-secondary-mt-4-m-0">
                {t('admin2.ts_admin_chat_ids_hint')}
              </p>
            </div>

            <div className="admin-flex-gap-12">
              <Button onClick={testBot} disabled={!settings.bot_token}>
                <TestTube className="w-4 h-4 mr-2" />
                {t('admin2.ts_test_bot_button')}
              </Button>
              <Button onClick={setWebhook} disabled={!settings.bot_token}>
                <Webhook className="w-4 h-4 mr-2" />
                {t('admin2.ts_set_webhook_button')}
              </Button>
            </div>
          </div>
        </MacOSCard>

        {/* Настройки уведомлений */}
        <MacOSCard className="p-6">
          <h3 className="admin-lg-med-mb-16-flex-ai-center-primary-m-0">
            <Bell className="admin-w-20-h-20-mr-8-success" />
            {t('admin2.ts_notifications_title')}
          </h3>

          <div className="flex flex-col gap-4">
            <div className="flex flex-col gap-3">
              <label className="admin-flex-ai-center">
                <Checkbox
                  checked={settings.notifications_enabled}
                  onChange={(e) => handleSettingChange('notifications_enabled', e.target.checked)}
                  className="admin-mr-12" />
                
                <span className="admin-sm-med-primary">{t('admin2.ts_notifications_enabled')}</span>
              </label>

              <label className="admin-flex-ai-center">
                <Checkbox
                  checked={settings.appointment_reminders}
                  onChange={(e) => handleSettingChange('appointment_reminders', e.target.checked)}
                  className="admin-mr-12" />
                
                <span className="admin-sm-med-primary">{t('admin2.ts_appointment_reminders')}</span>
              </label>

              <label className="admin-flex-ai-center">
                <Checkbox
                  checked={settings.lab_results_notifications}
                  onChange={(e) => handleSettingChange('lab_results_notifications', e.target.checked)}
                  className="admin-mr-12" />
                
                <span className="admin-sm-med-primary">{t('admin2.ts_lab_results_notifications')}</span>
              </label>

              <label className="admin-flex-ai-center">
                <Checkbox
                  checked={settings.payment_notifications}
                  onChange={(e) => handleSettingChange('payment_notifications', e.target.checked)}
                  className="admin-mr-12" />
                
                <span className="admin-sm-med-primary">{t('admin2.ts_payment_notifications')}</span>
              </label>
            </div>

            <div>
              <label className="admin-block-sm-med-primary-mb-8">
                <Globe className="admin-w-16-h-16-inline-mr-4" />
                {t('admin2.ts_default_language')}
              </label>
              <Select
                value={settings.default_language}
                onChange={(value) => handleSettingChange('default_language', value)}
                options={getLanguageOptions(t)}
                className="w-full"
                aria-label={t('admin2.ts_default_language')}
              ></Select>
              
            </div>

            {/* Информация о webhook */}
            {webhookInfo &&
            <div className="admin-p-12-radius-var--mac-radius-md-bd-1solid" style={{ '--admin-backgroundColor': webhookInfo.webhook_set ?
              'var(--mac-success-bg)' :
              'var(--mac-warning-bg)', '--admin-borderColor': webhookInfo.webhook_set ?
              'var(--mac-success-border)' :
              'var(--mac-warning-border)' }}>
                <h4 className="admin-med-mb-8-m-0" style={{ '--admin-color': webhookInfo.webhook_set ?
                'var(--mac-success)' :
                'var(--mac-warning)' }}>
                  Webhook: {webhookInfo.webhook_set ? t('admin2.ts_webhook_configured') : t('admin2.ts_webhook_not_configured')}
                </h4>
                {webhookInfo.webhook_info &&
              <div className="admin-sm-flex-col-gap-4">
                    <div className="text-[var(--mac-text-primary)]"><strong>URL:</strong> {webhookInfo.webhook_info.url || t('admin2.ts_url_not_set')}</div>
                    <div className="text-[var(--mac-text-primary)]"><strong>{t('admin2.ts_webhook_updates_label')}</strong> {webhookInfo.webhook_info.pending_update_count || 0}</div>
                  </div>
              }
              </div>
            }
          </div>
        </MacOSCard>
      </div>

      {/* Тестирование */}
      <MacOSCard className="p-6">
        <h3 className="admin-lg-med-mb-16-flex-ai-center-primary-m-0">
          <Send className="admin-w-20-h-20-mr-8-purple" />
          {t('admin2.ts_test_send_title')}
        </h3>

        <div className="admin-grid-gtc-rauto-fitcminmax300pxc1fr-gap-16">
          <div>
            <label className="admin-block-sm-med-primary-mb-8">
              {t('admin2.ts_test_chat_id_label')}
            </label>
            <Input
              type="text"
              value={testChatId}
              onChange={(e) => setTestChatId(e.target.value)}
              placeholder="123456789"
              className="w-full" />
            
            <p className="admin-sm-secondary-mt-4-m-0">
              {t('admin2.ts_test_chat_id_hint')}
            </p>
          </div>

          <div>
            <label className="admin-block-sm-med-primary-mb-8">
              {t('admin2.ts_test_message_label')}
            </label>
            <Input
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
              placeholder={t('admin2.ts_test_message_ph')}
              className="admin-w-100pct-minh-80" />
            
          </div>
        </div>

        <div className="admin-flex-jc-end-mt-16">
          <Button
            onClick={sendTestMessage}
            disabled={!settings.bot_token || !testChatId || !testMessage}>
            
            <Send className="w-4 h-4 mr-2" />
            {t('admin2.ts_send_test_button')}
          </Button>
        </div>
      </MacOSCard>

      {/* Инструкция */}
      <MacOSCard className="admin-p-24-bg-info-bg-bd-1solidvar-mac-info-border">
        <h3 className="admin-lg-med-mb-8-flex-ai-center-info-m-0">
          <MessageSquare className="admin-w-20-h-20-mr-8" />
          {t('admin2.ts_setup_title')}
        </h3>
        <div className="admin-sm-secondary-flex-col-gap-8">
          <p className="admin-m-0">{t('admin2.ts_setup_step_1')}</p>
          <p className="admin-m-0">{t('admin2.ts_setup_step_2')}</p>
          <p className="admin-m-0">{t('admin2.ts_setup_step_3')}</p>
          <p className="admin-m-0">{t('admin2.ts_setup_step_4')}</p>
          <p className="admin-m-0">{t('admin2.ts_setup_step_5')}</p>
        </div>
      </MacOSCard>
    </div>);

};

export default TelegramSettings;
