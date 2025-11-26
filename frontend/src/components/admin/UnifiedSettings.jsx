import React from 'react';
import { useSearchParams } from 'react-router-dom';
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
        return <SecuritySettings />;
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
