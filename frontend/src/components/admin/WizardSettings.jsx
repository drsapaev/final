import { useState, useEffect } from 'react';
import {
  MacOSCard,
  Button,
  Checkbox,
  Skeleton,
  MacOSEmptyState,
  Alert,
  Badge,
  Modal,
  MacOSStatCard,
} from '../ui/macos';
import { Settings, Save, AlertCircle, CheckCircle, RefreshCw } from 'lucide-react';
import { toast } from 'react-toastify';
import { fetchWizardSettings, saveWizardSettings } from '../../api/adminSettings';

import logger from '../../utils/logger';
import { useTranslation } from '../../i18n/useTranslation';
const WizardSettings = () => {
  const { t } = useTranslation();
  const [settings, setSettings] = useState({
    use_new_wizard: false,
    updated_at: null
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);
  const [error, setError] = useState(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);

  // Загрузка настроек
  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const data = await fetchWizardSettings();
      setSettings(data);
      setHasChanges(false);
    } catch (error) {
      logger.error('Error fetching wizard settings:', error);
      setError(t('admin2.ws_load_error_desc'));
      // Fallback данные при ошибке
      setSettings({
        use_new_wizard: false,
        updated_at: new Date().toISOString()
      });
      setHasChanges(false);
      toast.error(t('admin2.ws_load_error_toast'));
    } finally {
      setLoading(false);
    }
  };

  const handleToggleWizard = () => {
    setSettings((prev) => ({
      ...prev,
      use_new_wizard: !prev.use_new_wizard
    }));
    setHasChanges(true);
  };

  const handleSave = async () => {
    setShowConfirmModal(true);
  };

  const confirmSave = async () => {
    try {
      setSaving(true);
      setShowConfirmModal(false);
      const response = await saveWizardSettings({
        use_new_wizard: settings.use_new_wizard
      });

      if (response.success) {
        toast.success(response.message);
        setSettings(response.settings);
        setHasChanges(false);
      } else {
        throw new Error(response.message || t('admin2.ws_save_error_short'));
      }
    } catch (error) {
      logger.error('Error saving wizard settings:', error);
      toast.error(t('admin2.ws_save_error_toast'));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <MacOSCard className="admin-p-24-bgc-bg-primary-minh-100vh">
          <div className="admin-d-flex-ai-center-gap-8-mb-24">
            <Settings className="admin-w-32-h-32-blue" />
            <h2 className="admin-fs-2xl-fw-semi-primary-m-0">
              {t('admin2.ws_title')}
            </h2>
          </div>
          <Skeleton height="400px" />
      </MacOSCard>);

  }

  // Критическая ошибка загрузки
  if (error && !settings.updated_at) {
    return (
      <MacOSCard className="admin-p-24-bgc-bg-primary-minh-100vh">
          <div className="admin-d-flex-ai-center-gap-8-mb-24">
            <Settings className="admin-w-32-h-32-blue" />
            <h2 className="admin-fs-2xl-fw-semi-primary-m-0">
              {t('admin2.ws_title')}
            </h2>
          </div>
          <MacOSEmptyState
          icon={AlertCircle}
          title={t('admin2.ws_load_error_title')}
          description={t('admin2.ws_load_error_hint')}
          action={
          <Button onClick={fetchSettings} variant="primary">
                <RefreshCw className="admin-w-16-h-16-mr-4" />
                {t('admin2.ws_try_again')}
              </Button>
          } />

      </MacOSCard>);

  }

  return (
    <MacOSCard className="admin-p-24-bgc-bg-primary-minh-100vh">
      <div className="admin-d-flex-ai-center-gap-8-mb-24-fw-wrap">
          <Settings className="admin-w-32-h-32-blue" />
          <h2 className="admin-fs-2xl-fw-semi-primary-m-0-flex-1-minw-200">
            {t('admin2.ws_title')}
          </h2>

        <div className="admin-flex-col-24">
          {/* Критическая ошибка */}
          {error &&
          <Alert
            type="error"
            title={t('admin2.ws_load_alert_title')}
            message={error}
            onClose={() => setError(null)} />

          }

          {/* A/B Переключатель */}
          <MacOSCard className="admin-p-24-bgc-bg-secondary-bd-1px-solid-var-mac-bo">
            <div className="admin-d-flex-ai-center-jc-between-mb-16">
              <div className="admin-flex-1">
                <h3 className="admin-fs-lg-fw-semi-primary-m-0-0-4px-0">
                  {t('admin2.ws_version_section_title')}
                </h3>
                <p className="admin-fs-sm-secondary-m-0">
                  {settings.use_new_wizard ?
                  t('admin2.ws_new_desc') :
                  t('admin2.ws_classic_desc')
                  }
                </p>
              </div>
              
              <div className="admin-flex-center-8">
                <Checkbox
                  checked={settings.use_new_wizard}
                  onChange={handleToggleWizard} />

                <span className="admin-fs-sm-fw-med-col-dyn" style={{ '--admin-col0': settings.use_new_wizard ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)' }}>
                  {settings.use_new_wizard ? t('admin2.ws_new_label') : t('admin2.ws_old_label')}
                </span>
              </div>
            </div>
          </MacOSCard>

          {/* Статистика использования */}
          <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
            <MacOSStatCard
              title={t('admin2.ws_stat_usage_title')}
              value={settings.use_new_wizard ? '100%' : '0%'}
              icon={settings.use_new_wizard ? CheckCircle : AlertCircle}
              color={settings.use_new_wizard ? 'green' : 'orange'}
              trend={settings.use_new_wizard ? t('admin2.ws_status_active') : t('admin2.ws_status_inactive')}
              trendColor={settings.use_new_wizard ? 'var(--mac-success)' : 'var(--mac-warning)'} />

            
            <MacOSStatCard
              title={t('admin2.ws_stat_updated_title')}
              value={settings.updated_at ? new Date(settings.updated_at).toLocaleDateString('ru-RU') : t('admin2.ws_unknown')}
              icon={RefreshCw}
              color="blue"
              trend={t('admin2.ws_stat_trend_settings')}
              trendColor="var(--mac-text-secondary)" />

          </div>

          {/* Информация о версиях */}
          <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
            <MacOSCard className="admin-p-24-tr-all-var-mac-duration-bd-dyn-bgc-dyn-tf-dyn" style={{ '--admin-bd0': !settings.use_new_wizard ? '2px solid var(--mac-accent-blue)' : '1px solid var(--mac-border)', '--admin-bgc1': !settings.use_new_wizard ? 'var(--mac-accent-bg)' : 'var(--mac-bg-primary)', '--admin-tf2': !settings.use_new_wizard ? 'scale(1.02)' : 'scale(1)' }}>
              <div className="admin-d-flex-ai-center-gap-4-mb-8">
                <h4 className="admin-fs-lg-fw-semi-primary-m-0">
                  {t('admin2.ws_classic_card_title')}
                </h4>
                <Badge
                  variant={!settings.use_new_wizard ? 'primary' : 'secondary'}
                  size="sm">

                  {!settings.use_new_wizard ? t('admin2.ws_status_active') : t('admin2.ws_status_inactive')}
                </Badge>
              </div>
              <ul className="admin-fs-sm-secondary-m-0-pl-16-d-flex-fd-column-gap-4">
                <li>{t('admin2.ws_classic_feat_1')}</li>
                <li>{t('admin2.ws_classic_feat_2')}</li>
                <li>{t('admin2.ws_classic_feat_3')}</li>
                <li>{t('admin2.ws_classic_feat_4')}</li>
              </ul>
            </MacOSCard>

            <MacOSCard className="admin-p-24-tr-all-var-mac-duration-bd-dyn-bgc-dyn-tf-dyn" style={{ '--admin-bd0': settings.use_new_wizard ? '2px solid var(--mac-success)' : '1px solid var(--mac-border)', '--admin-bgc1': settings.use_new_wizard ? 'var(--mac-success-bg)' : 'var(--mac-bg-primary)', '--admin-tf2': settings.use_new_wizard ? 'scale(1.02)' : 'scale(1)' }}>
              <div className="admin-d-flex-ai-center-gap-4-mb-8">
                <h4 className="admin-fs-lg-fw-semi-primary-m-0">
                  {t('admin2.ws_new_card_title')}
                </h4>
                <Badge
                  variant={settings.use_new_wizard ? 'success' : 'secondary'}
                  size="sm">

                  {settings.use_new_wizard ? t('admin2.ws_status_active') : t('admin2.ws_status_inactive')}
                </Badge>
              </div>
              <ul className="admin-fs-sm-secondary-m-0-pl-16-d-flex-fd-column-gap-4">
                <li>{t('admin2.ws_new_feat_1')}</li>
                <li>{t('admin2.ws_new_feat_2')}</li>
                <li>{t('admin2.ws_new_feat_3')}</li>
                <li>{t('admin2.ws_new_feat_4')}</li>
                <li>{t('admin2.ws_new_feat_5')}</li>
                <li>{t('admin2.ws_new_feat_6')}</li>
              </ul>
            </MacOSCard>
          </div>

          {/* Предупреждение */}
          {hasChanges &&
          <MacOSCard className="admin-p-16-bgc-var-mac-warning-bg-bd-1px-solid-var-mac-wa">
              <div className="admin-flex-center-8">
                <AlertCircle className="admin-w-20-h-20-warning-fsk-0" />
                <p className="admin-fs-sm-warning-m-0-fw-med">
                  {t('admin2.ws_unsaved_changes')}
                </p>
              </div>
            </MacOSCard>
          }

          {/* Информация об обновлении */}
          {settings.updated_at &&
          <div className="admin-fs-xs-tertiary-ta-center-p-8px-0">
              {t('admin2.ws_last_updated', { date: new Date(settings.updated_at).toLocaleString('ru-RU') })}
            </div>
          }

          {/* Кнопки действий */}
          <div className="admin-d-flex-jc-end-gap-8-pt-16-bd-t-1px-solid-var-mac-bo-fw-wrap">
            <Button
              variant="outline"
              onClick={fetchSettings}
              disabled={saving}
              className="admin-d-flex-ai-center-gap-4-p-4px-16px-minw-120">

              {t('admin2.ws_cancel_button')}
            </Button>
            
            <Button
              type="button"
              title={saving ? 'Saving wizard settings' : 'Save wizard settings'}
              aria-label={saving ? 'Saving wizard settings' : 'Save wizard settings'}
              onClick={handleSave}
              disabled={!hasChanges || saving}
              className="admin-d-flex-ai-center-gap-4-bgc-blue-bd-none-p-4px-16px-minw-120">

              {saving ?
              <>
                  <RefreshCw aria-hidden="true" className="admin-w-16-h-16-anim-spin-1s-linear-infin" />
                  {t('admin2.ws_saving')}
                </> :

              <>
                  <Save aria-hidden="true" className="admin-icon-16" />
                  {t('admin2.ws_save_button')}
                </>
              }
            </Button>
          </div>
        </div>
      </div>

      {/* Модальное окно подтверждения */}
      <Modal
        isOpen={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        title={t('admin2.ws_confirm_title')}
        size="sm">

        <div className="admin-p-24">
          <p className="admin-fs-base-primary-mb-24-lh-var-mac-line-height">
            {t('admin2.ws_confirm_message', { action: settings.use_new_wizard ? t('admin2.ws_action_enable') : t('admin2.ws_action_disable') })}
          </p>
          
          <div className="admin-d-flex-jc-end-gap-var-mac-spacing-sm">
            <Button
              variant="outline"
              onClick={() => setShowConfirmModal(false)}
              disabled={saving}>

              {t('admin2.ws_cancel_modal_button')}
            </Button>
            <Button
              type="button"
              title={saving ? 'Saving wizard settings' : 'Confirm wizard settings save'}
              aria-label={saving ? 'Saving wizard settings' : 'Confirm wizard settings save'}
              onClick={confirmSave}
              disabled={saving}
              className="admin-bgc-blue-bd-none">

              {saving ?
              <>
                  <RefreshCw aria-hidden="true" className="admin-w-16-h-16-anim-spin-1s-linear-infin-mr-4" />
                  {t('admin2.ws_saving')}
                </> :

              <>
                  <Save aria-hidden="true" className="admin-w-16-h-16-mr-4" />
                  {t('admin2.ws_confirm_button')}
                </>
              }
            </Button>
          </div>
        </div>
      </Modal>
    </MacOSCard>);

};

export default WizardSettings;
