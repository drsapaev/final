import React, { useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../../api/client';
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
            loading={securityLoading}
          />
        );
      case 'settings':
      default:
        return <ClinicSettings />;
    }
  };

  return (
    <div style={{ height: '100%', overflow: 'auto' }}>
      {renderSettings()}
    </div>
  );
};

export default UnifiedSettings;
