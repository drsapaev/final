import type { CSSProperties } from 'react';

import { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { fetchClinicSettings, saveClinicSettings } from '../../api/adminSettings';
import {
  fetchTicketPrintSettings,
  saveTicketPrintSettings,
  TICKET_PRINT_SETTINGS_DEFINITIONS,
  TICKET_PRINT_SETTINGS_DEFAULTS,
} from '../../api/ticketPrintSettings';
import logger from '../../utils/logger';
import {
  Building2,
  MapPin,
  Phone,
  Mail,
  Clock,
  Globe,
  Printer,
  Upload,
  Save,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Image
} from 'lucide-react';
import {
  MacOSCard,
  Button as ButtonRaw,
  Input as InputRaw,
  Select as SelectRaw,
  Textarea as TextareaRaw,
  Checkbox,
} from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";
const Textarea = TextareaRaw as unknown as React.ComponentType<Record<string, unknown>>;
const Input = InputRaw as unknown as React.ComponentType<Record<string, unknown>>;
const Select = SelectRaw as unknown as React.ComponentType<Record<string, unknown>>;
const Button = ButtonRaw as unknown as React.ComponentType<Record<string, unknown>>;

const ClinicSettings = () => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settings, setSettings] = useState({
    clinic_name: 'Programma Clinic',
    address: '',
    phone: '',
    email: '',
    timezone: 'Asia/Tashkent',
    logo_url: '/static/logo.png'
  });
  const [logoFile, setLogoFile] = useState(null);
  const [logoPreview, setLogoPreview] = useState(null);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [ticketPrintSettings, setTicketPrintSettings] = useState({ ...TICKET_PRINT_SETTINGS_DEFAULTS });
  const [ticketPrintLoading, setTicketPrintLoading] = useState(true);
  const [ticketPrintSaving, setTicketPrintSaving] = useState(false);
  const [ticketPrintMessage, setTicketPrintMessage] = useState({ type: '', text: '' });

  // Список часовых поясов
  const timezones = [
    { value: 'Asia/Tashkent', label: t('admin2.cset_tz_tashkent') },
    { value: 'Asia/Almaty', label: t('admin2.cset_tz_almaty') },
    { value: 'Europe/Moscow', label: t('admin2.cset_tz_moscow') },
    { value: 'Asia/Dubai', label: t('admin2.cset_tz_dubai') },
    { value: 'UTC', label: 'UTC (UTC+0)' }
  ];

  useEffect(() => {
    loadSettings();
    loadTicketPrintSettings();
  }, []);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const data = await fetchClinicSettings('clinic');
      const settingsObj = {};

      if (Array.isArray(data)) {
        data.forEach(setting => {
          settingsObj[setting.key] = setting.value;
        });
      }

      setSettings(prev => ({ ...prev, ...settingsObj }));
    } catch (error) {
      logger.error('Ошибка загрузки настроек:', error);
      setMessage({ type: 'danger', text: t('admin2.cset_err_load') });
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const loadTicketPrintSettings = async () => {
    try {
      setTicketPrintLoading(true);
      const data = await fetchTicketPrintSettings();
      setTicketPrintSettings({ ...TICKET_PRINT_SETTINGS_DEFAULTS, ...data });
    } catch (error) {
      logger.error('Ошибка загрузки настроек печати талонов:', error);
      setTicketPrintMessage({ type: 'danger', text: t('admin2.cset_err_load_print') });
      setTicketPrintSettings({ ...TICKET_PRINT_SETTINGS_DEFAULTS });
    } finally {
      setTicketPrintLoading(false);
    }
  };

  const handleTicketPrintChange = (key, value) => {
    setTicketPrintSettings(prev => ({ ...prev, [key]: value }));
  };

  const handleLogoSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      // Проверяем тип файла
      if (!file.type.startsWith('image/')) {
        setMessage({ type: 'danger', text: t('admin2.cset_err_logo_type') });
        return;
      }

      // Проверяем размер (макс 5MB)
      if (file.size > 5 * 1024 * 1024) {
        setMessage({ type: 'danger', text: t('admin2.cset_err_logo_size') });
        return;
      }

      setLogoFile(file);

      // Создаем превью
      const reader = new FileReader();
      reader.onload = (e) => {
        setLogoPreview(e.target.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const uploadLogo = async () => {
    if (!logoFile) return null;

    try {
      const formData = new FormData();
      formData.append('file', logoFile);

      const response = await api.post('/admin/clinic/logo', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      return response.data.logo_url;
    } catch (error) {
      logger.error('Ошибка загрузки логотипа:', error);
      throw error;
    }
  };

  const saveSettings = async () => {
    try {
      setSaving(true);
      setMessage({ type: '', text: '' });

      // Сначала загружаем логотип если выбран новый
      let logoUrl = settings.logo_url;
      if (logoFile) {
        logoUrl = await uploadLogo();
      }

      // Подготавливаем настройки для отправки
      const settingsToSave = {
        ...settings,
        logo_url: logoUrl
      };

      await saveClinicSettings({
        settings: settingsToSave
      });

      setMessage({ type: 'success', text: t('admin2.cset_success_save') });
      setLogoFile(null);
      setLogoPreview(null);

      // Обновляем логотип в настройках
      if (logoUrl !== settings.logo_url) {
        setSettings(prev => ({ ...prev, logo_url: logoUrl }));
      }
    } catch (error) {
      logger.error('Ошибка сохранения:', error);
      setMessage({ type: 'danger', text: t('admin2.cset_err_save') });
    } finally {
      setSaving(false);
    }
  };

  const saveTicketPrintSettingsHandler = async () => {
    try {
      setTicketPrintSaving(true);
      setTicketPrintMessage({ type: '', text: '' });
      const savedSettings = await saveTicketPrintSettings(ticketPrintSettings);
      setTicketPrintSettings({ ...TICKET_PRINT_SETTINGS_DEFAULTS, ...savedSettings });
      setTicketPrintMessage({ type: 'success', text: t('admin2.cset_success_save_print') });
    } catch (error) {
      logger.error('Ошибка сохранения настроек печати талонов:', error);
      setTicketPrintMessage({ type: 'danger', text: t('admin2.cset_err_save_print') });
    } finally {
      setTicketPrintSaving(false);
    }
  };

  const resetLogo = () => {
    setLogoFile(null);
    setLogoPreview(null);
  };

  if (loading) {
    return (
      <div className="admin-p-0-bg-bg-primary">
        <MacOSCard className="admin-p-24-ta-center">
          <div className="admin-flex-ai-center-jc-center-gap-12">
            <RefreshCw className="admin-w-32-h-32-blue-anim-spin1slinearinfinite" />
            <span className="admin-lg-secondary-med">
              {t('admin2.cset_loading')}
            </span>
          </div>
        </MacOSCard>
      </div>
    );
  }

  return (
    <div className="admin-p-0-bg-bg-primary">
      <MacOSCard className="p-6">
        {/* Заголовок */}
        <div className="admin-flex-ai-center-jc-between-mb-24-pb-24-borderbottom-0a48a6">
          <div>
            <h2 className="admin-2xl-semi-primary-m-008px0-flex-ai-center-gap-12">
              <Building2 className="admin-w-32-h-32-blue" />
              {t('admin2.cset_title')}
            </h2>
            <p className="admin-secondary-sm-m-0">
              {t('admin2.cset_subtitle')}
            </p>
          </div>

          <div className="admin-flex-gap-12">
            <Button
              variant="outline"
              onClick={loadSettings}
              disabled={loading}
              className="admin-flex-ai-center-gap-8-p-8px16"
            >
              <RefreshCw className="w-4 h-4" />
              {t('admin2.cset_btn_refresh')}
            </Button>
            <Button
              onClick={saveSettings}
              disabled={saving}
              className="admin-flex-ai-center-gap-8-bg-blue-bd-none-p-8px16"
            >
              {saving ? (
                <RefreshCw className="admin-w-16-h-16-anim-spin1slinearinfinite" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              {t('admin2.cset_btn_save')}
            </Button>
          </div>
        </div>

        {/* Сообщения */}
        {message.text && (
          <MacOSCard className="admin-p-16-mb-24" style={{ '--admin-backgroundColor': message.type === 'success' ? 'var(--mac-success-bg)' : 'var(--mac-error-bg)', '--admin-border': message.type === 'success' ? '1px solid var(--mac-success-border)' : '1px solid var(--mac-error-border)' } as CSSProperties}>
            <div className="flex items-center justify-center gap-2">
              {message.type === 'success' ? (
                <CheckCircle className="admin-w-20-h-20-success" />
              ) : (
                <AlertCircle className="admin-w-20-h-20-error" />
              )}
              <span className="admin-sm-med" style={{ '--admin-color': message.type === 'success' ? 'var(--mac-success)' : 'var(--mac-error)' } as CSSProperties}>
                {message.text}
              </span>
            </div>
          </MacOSCard>
        )}

        <div className="admin-grid-gtc-rauto-fitcminmax400pxc1fr-gap-24-mb-24">
          {/* Основная информация */}
          <MacOSCard className="p-6">
            <h3 className="admin-lg-semi-primary-mb-16-flex-ai-center-gap-8">
              <Building2 className="admin-w-20-h-20-blue" />
              {t('admin2.cset_h_basic')}
            </h3>

            <div className="flex flex-col gap-4">
              <div>
                <label className="admin-block-sm-med-primary-mb-8">
                  {t('admin2.cset_label_name')}
                </label>
                <Input
                  type="text"
                  value={settings.clinic_name || ''}
                  onChange={(e) => handleInputChange('clinic_name', e.target.value)}
                  placeholder={t('admin2.cset_ph_name')}
                  className="w-full"
                />
              </div>

              <div>
                <label className="admin-sm-med-primary-mb-8-flex-ai-center-gap-4">
                  <MapPin className="w-4 h-4" />
                  {t('admin2.cset_label_address')}
                </label>
                <Textarea
                  value={settings.address || ''}
                  onChange={(e) => handleInputChange('address', e.target.value)}
                  rows={2}
                  placeholder={t('admin2.cset_ph_address')}
                  className="w-full"
                />
              </div>

              <div>
                <label className="admin-sm-med-primary-mb-8-flex-ai-center-gap-4">
                  <Phone className="w-4 h-4" />
                  {t('admin2.cset_label_phone')}
                </label>
                <Input
                  type="tel"
                  value={settings.phone || ''}
                  onChange={(e) => handleInputChange('phone', e.target.value)}
                  placeholder="+998 (90) 123-45-67"
                  className="w-full"
                />
              </div>

              <div>
                <label className="admin-sm-med-primary-mb-8-flex-ai-center-gap-4">
                  <Mail className="w-4 h-4" />
                  Email
                </label>
                <Input
                  type="email"
                  value={settings.email || ''}
                  onChange={(e) => handleInputChange('email', e.target.value)}
                  placeholder="info@clinic.com"
                  className="w-full"
                />
              </div>
            </div>
          </MacOSCard>

          {/* Системные настройки */}
          <MacOSCard className="p-6">
            <h3 className="admin-lg-semi-primary-mb-16-flex-ai-center-gap-8">
              <Globe className="admin-w-20-h-20-success" />
              {t('admin2.cset_h_system')}
            </h3>

            <div className="flex flex-col gap-4">
              <div>
                <label className="admin-sm-med-primary-mb-8-flex-ai-center-gap-4">
                  <Clock className="w-4 h-4" />
                  {t('admin2.cset_label_timezone')}
                </label>
                <Select
                  aria-label={t('admin2.cset_aria_timezone')}
                  value={settings.timezone || 'Asia/Tashkent'}
                  onChange={(value) => handleInputChange('timezone', value)}
                  options={timezones}
                  size="large"
                  className="w-full"
                />
                <p className="admin-xs-tertiary-mt-4-m-4px000">
                  {t('admin2.cset_hint_timezone')}
                </p>
              </div>

              {/* Логотип */}
              <div>
                <label className="admin-sm-med-primary-mb-8-flex-ai-center-gap-4">
                  <Image className="w-4 h-4" />
                  {t('admin2.cset_label_logo')}
                </label>

                {/* Текущий логотип */}
                {(settings.logo_url || logoPreview) && (
                  <div className="mb-3">
                    <div className="admin-w-128-h-80-bd-2dashedvar-mac-border-radius-var--mac-radius-md-flex-ai-cent-5f1cf18b">
                      <img
                        src={logoPreview || settings.logo_url}
                        alt={t('admin2.cset_alt_logo')}
                        className="admin-maxw-100pct-maxh-100pct-of-contain"
                      />
                    </div>
                    {logoPreview && (
                      <Button
                        variant="outline"
                        onClick={resetLogo}
                        className="admin-mt-8-p-4px8-xs"
                      >
                        {t('admin2.cset_btn_cancel')}
                      </Button>
                    )}
                  </div>
                )}

                {/* Загрузка логотипа */}
                <div className="admin-flex-ai-center">
                  <input
                    type="file"
                    aria-label={t('admin2.cset_aria_logo_upload')}
                    accept="image/*"
                    onChange={handleLogoSelect}
                    className="admin-none"
                    id="logo-upload"
                  />
                  <label
                    htmlFor="logo-upload"
                    className="admin-cursor-pointer-inline-flex-ai-center-p-8px16-bd-1solidvar-mac-border-radiu-832d1430"
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = 'var(--mac-accent-bg)';
                      e.currentTarget.style.borderColor = 'var(--mac-accent-blue)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
                      e.currentTarget.style.borderColor = 'var(--mac-border)';
                    }}
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    {t('admin2.cset_btn_choose_file')}
                  </label>
                </div>
                <p className="admin-xs-tertiary-mt-4-m-4px000">
                  {t('admin2.cset_hint_logo')}
                </p>
              </div>
            </div>
          </MacOSCard>
        </div>

        <MacOSCard className="p-6">
          <div className="admin-flex-ai-center-jc-between-gap-16-mb-20-pb-20-borderbottom-0a48a6">
            <div>
              <h3 className="admin-lg-semi-primary-m-008px0-flex-ai-center-gap-8">
                <Printer className="admin-w-20-h-20-blue" />
                {t('admin2.cset_h_print')}
              </h3>
              <p className="admin-secondary-sm-m-0-maxw-720">
                {t('admin2.cset_print_desc')}
              </p>
              <p className="admin-tertiary-xs-m-8px000-maxw-720">
                {t('admin2.cset_print_cabinet_note')}
              </p>
            </div>

            <div className="admin-flex-gap-12-wrap-jc-end">
              <Button
                variant="outline"
                onClick={loadTicketPrintSettings}
                disabled={ticketPrintLoading}
                className="admin-flex-ai-center-gap-8-p-8px16"
              >
                <RefreshCw className="w-4 h-4" />
                {t('admin2.cset_btn_refresh')}
              </Button>
              <Button
                onClick={saveTicketPrintSettingsHandler}
                disabled={ticketPrintSaving || ticketPrintLoading}
                className="admin-flex-ai-center-gap-8-bg-blue-bd-none-p-8px16"
              >
                {ticketPrintSaving ? (
                  <RefreshCw className="admin-w-16-h-16-anim-spin1slinearinfinite" />
                ) : (
                  <Save className="w-4 h-4" />
                )}
                {t('admin2.cset_btn_save')}
              </Button>
            </div>
          </div>

          {ticketPrintMessage.text && (
            <MacOSCard className="admin-p-16-mb-20" style={{ '--admin-backgroundColor': ticketPrintMessage.type === 'success' ? 'var(--mac-success-bg)' : 'var(--mac-error-bg)', '--admin-border': ticketPrintMessage.type === 'success' ? '1px solid var(--mac-success-border)' : '1px solid var(--mac-error-border)' } as CSSProperties}>
              <div className="flex items-center justify-center gap-2">
                {ticketPrintMessage.type === 'success' ? (
                  <CheckCircle className="admin-w-20-h-20-success" />
                ) : (
                  <AlertCircle className="admin-w-20-h-20-error" />
                )}
                <span className="admin-sm-med" style={{ '--admin-color': ticketPrintMessage.type === 'success' ? 'var(--mac-success)' : 'var(--mac-error)' } as CSSProperties}>
                  {ticketPrintMessage.text}
                </span>
              </div>
            </MacOSCard>
          )}

          {ticketPrintLoading ? (
            <div className="admin-flex-ai-center-jc-center-gap-12-p-24px0-secondary">
              <RefreshCw className="admin-w-24-h-24-anim-spin1slinearinfinite" />
              <span>{t('admin2.cset_loading_print')}</span>
            </div>
          ) : (
            <div className="admin-grid-gtc-rauto-fitcminmax280pxc1fr-gap-12">
              {TICKET_PRINT_SETTINGS_DEFINITIONS.map((item) => (
                <div
                  key={item.key}
                  className="admin-p-14-radius-var--mac-radius-md-bd-1solidvar-mac-border-bg-bg-secondary"
                >
                  <Checkbox
                    checked={Boolean(ticketPrintSettings[item.key])}
                    onChange={(checked) => handleTicketPrintChange(item.key, checked)}
                    label={item.label}
                    description={item.description}
                    disabled={ticketPrintSaving}
                    size="md"
                  />
                </div>
              ))}
            </div>
          )}
        </MacOSCard>
      </MacOSCard>
    </div>
  );
};

export default ClinicSettings;
