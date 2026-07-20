
import { useState, useCallback, useEffect } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';

import { api } from '../../api/client';
import logger from '../../utils/logger';
import BenefitSettings from './BenefitSettings';
import PaymentProviderSettings from './PaymentProviderSettings';
import QueueSettings from './QueueSettings';
import AISettings from './AISettings';
import DisplayBoardSettings from './DisplayBoardSettings';
import SecuritySettings from './SecuritySettings';
import WizardSettings from './WizardSettings';
import ClinicSettings from './ClinicSettings';
import ColorSchemeSelector from './ColorSchemeSelector';
import { AccentPicker } from '../ui/macos';
// P-025 fix: shared loading/error/empty wrapper for Unified* panels.
import StateWrapper from '../common/StateWrapper';
import { useTranslation } from '../../i18n/useTranslation';

const stripPasswordFields = (formData) => {
  const persistedSettings = { ...(formData || {}) };
  delete persistedSettings.currentPassword;
  delete persistedSettings.newPassword;
  delete persistedSettings.confirmPassword;

  return persistedSettings;
};

const ADMIN_SETTINGS_ROUTE_SECTION_MAP = {
  '/admin/benefit-settings': 'benefit-settings',
  '/admin/wizard-settings': 'wizard-settings',
  '/admin/payment-providers': 'payment-providers',
  '/admin/clinic-settings': 'clinic-settings',
  '/admin/queue-settings': 'queue-settings',
  '/admin/display-settings': 'display-settings',
  '/admin/security': 'security',
};

const UnifiedSettings = () => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const routeSection = ADMIN_SETTINGS_ROUTE_SECTION_MAP[location.pathname.replace(/\/$/, '')];
  const section = routeSection || searchParams.get('section') || 'general';
  const [securitySettings, setSecuritySettings] = useState({});
  const [securityLoading, setSecurityLoading] = useState(false);
  // P-025 fix: track load error explicitly so the StateWrapper can render
  // a proper error state instead of silently rendering SecuritySettings
  // with empty {} (which previously made the form look broken without
  // explanation).
  const [securityError, setSecurityError] = useState(null);

  const loadSecuritySettings = useCallback(async () => {
    try {
      setSecurityLoading(true);
      setSecurityError(null);
      const response = await api.get('/users/me/preferences');
      const persistedSecuritySettings = response?.data?.security_settings;
      setSecuritySettings(
        persistedSecuritySettings && typeof persistedSecuritySettings === 'object'
          ? persistedSecuritySettings
          : {}
      );
    } catch (error) {
      logger.warn('Error loading security settings:', error);
      // P-025 fix: capture error for StateWrapper. Keep securitySettings
      // as-is (likely {} on first load) so the user can still see the form
      // structure if they retry.
      setSecurityError(error?.message || t('admin2.us_load_error'));
      setSecuritySettings({});
    } finally {
      setSecurityLoading(false);
    }
  }, []);

  // Handler for saving security settings
  const handleSaveSecuritySettings = useCallback(async (formData, activeTab = 'password') => {
    try {
      setSecurityLoading(true);
      const persistedSecuritySettings = stripPasswordFields(formData);
      await api.put('/users/me/preferences', {
        security_settings: persistedSecuritySettings,
      });

      setSecuritySettings({
        ...persistedSecuritySettings,
        currentPassword: formData.currentPassword || '',
        newPassword: formData.newPassword || '',
        confirmPassword: formData.confirmPassword || '',
      });

      if (activeTab === 'password' && formData.currentPassword && formData.newPassword) {
        await api.post('/authentication/password-change', {
          current_password: formData.currentPassword,
          new_password: formData.newPassword,
        });

        setSecuritySettings({
          ...persistedSecuritySettings,
          currentPassword: '',
          newPassword: '',
          confirmPassword: '',
        });
      }
      logger.log('Security settings saved successfully');
    } catch (error) {
      logger.error('Error saving security settings:', error);
      throw error;
    } finally {
      setSecurityLoading(false);
    }
  }, []);

  useEffect(() => {
    if (section === 'security') {
      void loadSecuritySettings();
    }
  }, [loadSecuritySettings, section]);

  const renderSettings = () => {
    switch (section) {
      case 'benefit-settings':
        return <BenefitSettings />;
      case 'wizard-settings':
        return <WizardSettings />;
      case 'payment-providers':
        return <PaymentProviderSettings />;
      case 'queue-settings':
        return <QueueSettings />;
      // UX Audit Admin #4.9: case 'ai-settings' удалён — мёртвый код.
      // Маршрут admin-ai-settings рендерится отдельным маршрутом, минуя UnifiedSettings.
      case 'display-settings':
        return <DisplayBoardSettings />;
      case 'clinic-settings':
        return <ClinicSettings />;
      case 'security':
        // P-025 fix: wrap SecuritySettings in StateWrapper so loading shows
        // a skeleton, errors show a retry-friendly message, and the actual
        // form only renders once data is available.
        return (
          <StateWrapper
            isLoading={securityLoading}
            error={securityError}
            onRetry={() => { void loadSecuritySettings(); }}
            emptyTitle={t('admin2.us_empty_title')}
            emptyMessage={t('admin2.us_empty_message')}
          >
            <SecuritySettings
              settings={securitySettings}
              onSave={handleSaveSecuritySettings}
              loading={securityLoading} />
          </StateWrapper>
        );


      case 'settings':
      default:
        return (
          <div className="admin-settings-grid-20">
            <ColorSchemeSelector />
            <div className="admin-settings-card-accent">
              <div className="admin-settings-section-title">
                {t('admin2.us_accent_color')}
              </div>
              <div className="admin-settings-grid-10">
                <AccentPicker />
                <div className="admin-settings-hint-12">
                  {t('admin2.us_accent_hint')}
                </div>
              </div>
            </div>
            <div className="admin-settings-card-gradient">
              <div className="admin-settings-section-title-mb-0">
                {t('admin2.us_application_logic')}
              </div>
              <div className="admin-settings-hint-13">
                {t('admin2.us_logic_hint')}
              </div>
            </div>
            {/* UX Audit Admin #2.6: ClinicSettings удалён из default-ветки.
                Дублировал admin-clinic-settings маршрут. Теперь «Настройки» =
                только тема/акцент, «Профиль клиники» = ClinicSettings. */}
          </div>);
    }
  };

  return (
    <div className="admin-settings-root">
      {renderSettings()}
    </div>);

};

export default UnifiedSettings;
