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
import ColorSchemeSelector from './ColorSchemeSelector.jsx';
import AccentPicker from '../ui/macos/AccentPicker.jsx';
// P-025 fix: shared loading/error/empty wrapper for Unified* panels.
import StateWrapper from '../common/StateWrapper.jsx';

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
      setSecurityError(error?.message || 'Не удалось загрузить настройки безопасности. Проверьте соединение с сервером.');
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
      case 'ai-settings':
        return <AISettings />;
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
            emptyTitle="Настройки безопасности не загружены"
            emptyMessage="Нажмите «Повторить», чтобы загрузить настройки безопасности."
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
          <div style={{ display: 'grid', gap: '20px' }}>
            <ColorSchemeSelector />
            <div style={{
              padding: '20px',
              borderRadius: 'var(--mac-radius-lg)',
              background: 'var(--mac-bg-primary)',
              border: '1px solid var(--mac-border)',
              boxShadow: 'var(--mac-shadow-sm)',
            }}>
              <div style={{ fontWeight: 700, marginBottom: 12, color: 'var(--mac-text-primary)' }}>
                Accent color
              </div>
              <div style={{ display: 'grid', gap: '10px' }}>
                <AccentPicker />
                <div style={{ fontSize: 12, color: 'var(--mac-text-secondary)' }}>
                  Accent color влияет на кнопки, focus states и primary states в админ-панели. Он хранится локально в текущем браузере.
                </div>
              </div>
            </div>
            <div style={{
              padding: '20px',
              borderRadius: 'var(--mac-radius-lg)',
              background: 'linear-gradient(180deg, var(--mac-bg-primary), var(--mac-bg-secondary))',
              border: '1px solid var(--mac-border)',
              boxShadow: 'var(--mac-shadow-sm)',
              display: 'grid',
              gap: '10px',
            }}>
              <div style={{ fontWeight: 700, color: 'var(--mac-text-primary)' }}>
                Логика применения
              </div>
              <div style={{ fontSize: 13, color: 'var(--mac-text-secondary)', lineHeight: 1.55 }}>
                Цветовая схема задаёт пространство интерфейса: фон, поверхности, header и sidebar. Accent управляет цветом действий и выделений. Theme preference синхронизируется через профиль пользователя, accent остаётся локальной настройкой рабочего места.
              </div>
            </div>
            <ClinicSettings />
          </div>);
    }
  };

  return (
    <div style={{ height: '100%', overflow: 'auto' }}>
      {renderSettings()}
    </div>);

};

export default UnifiedSettings;
