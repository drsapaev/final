import { useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

import logger from '../../utils/logger';
import BenefitSettings from './BenefitSettings';
import PaymentProviderSettings from './PaymentProviderSettings';
import QueueSettings from './QueueSettings';
import QueueLimitsManager from './QueueLimitsManager';
import AISettings from './AISettings';
import DisplayBoardSettings from './DisplayBoardSettings';
import SecuritySettings from './SecuritySettings';
import WizardSettings from './WizardSettings';
import ClinicSettings from './ClinicSettings';
import ColorSchemeSelector from './ColorSchemeSelector.jsx';
import AccentPicker from '../ui/macos/AccentPicker.jsx';

const UnifiedSettings = () => {
  const [searchParams] = useSearchParams();
  const section = searchParams.get('section') || 'general';
  const [securitySettings, setSecuritySettings] = useState({});
  const [securityLoading, setSecurityLoading] = useState(false);

  // Handler for saving security settings
  const handleSaveSecuritySettings = useCallback(async (formData) => {
    try {
      setSecurityLoading(true);
      // For now, just log the settings - in production this would call an API
      logger.log('Saving security settings:', formData);

      // Update local state
      setSecuritySettings(formData);

      // Here you would typically save to the backend:
      // await api.put('/admin/security/settings', formData);

      logger.log('Security settings saved successfully');
    } catch (error) {
      logger.error('Error saving security settings:', error);
      throw error;
    } finally {
      setSecurityLoading(false);
    }
  }, []);

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
      case 'queue-limits':
        return <QueueLimitsManager />;
      case 'ai-settings':
        return <AISettings />;
      case 'display-settings':
        return <DisplayBoardSettings />;
      case 'security':
        return (
          <SecuritySettings
            settings={securitySettings}
            onSave={handleSaveSecuritySettings}
            loading={securityLoading} />);


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
