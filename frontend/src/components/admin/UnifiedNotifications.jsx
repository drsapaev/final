import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import FCMManager from './FCMManager';
import RegistrarNotificationManager from './RegistrarNotificationManager';
import ErrorBoundary from '../common/ErrorBoundary';
import { MacOSTab } from '../ui/macos';
import { useTranslation } from '../../i18n/adapter';


const UnifiedNotifications = () => {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const section = searchParams.get('section') || 'fcm';

  const getActiveTab = (section) => {
    return section === 'registrar-notifications' ? 'registrar' : 'fcm';
  };

  const [activeTab, setActiveTab] = useState(getActiveTab(section));

  // Обновляем активную вкладку при изменении секции
  useEffect(() => {
    setActiveTab(getActiveTab(section));
  }, [section]);

  const tabs = [
  { id: 'fcm', label: 'Push (FCM)', icon: 'Bell' },
  { id: 'registrar', label: 'Регистратор', icon: 'Users' }];


  const renderContent = () => {
    switch (activeTab) {
      case 'fcm':
        return <FCMManager />;
      case 'registrar':
        return <RegistrarNotificationManager />;
      default:
        return <FCMManager />;
    }
  };

  return (
    <div className="admin-unified-root-no-color">
      <MacOSTab
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab} />
      
      <div
        id={`notifications-panel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`notifications-tab-${activeTab}`}
        className="admin-unified-content"
      >
        <ErrorBoundary>
          {/* P-025 fix: catch runtime errors in child panels */}
          {renderContent()}
        </ErrorBoundary>
      </div>
    </div>);

};

export default UnifiedNotifications;
