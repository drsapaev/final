import React from "react";
import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import FCMManager from './FCMManager';
import RegistrarNotificationManager from './RegistrarNotificationManager';
import ErrorBoundary from '../common/ErrorBoundary';
import { MacOSTab as MacOSTabRaw } from '../ui/macos';
const MacOSTab = MacOSTabRaw as unknown as React.ComponentType<Record<string, unknown>>;
import { useTranslation } from '../../i18n/useTranslation';

type NotificationSection = 'fcm' | 'registrar';

const UnifiedNotifications = () => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [searchParams] = useSearchParams();
  const section = searchParams.get('section') || 'fcm';

  const getActiveTab = (s: string): NotificationSection => {
    return s === 'registrar-notifications' ? 'registrar' : 'fcm';
  };

  const [activeTab, setActiveTab] = useState<NotificationSection>(getActiveTab(section));

  useEffect(() => {
    setActiveTab(getActiveTab(section));
  }, [section]);

  const tabs = [
    { id: 'fcm' as const, label: 'Push (FCM)', icon: 'Bell' },
    { id: 'registrar' as const, label: t('admin2.un_tab_registrar'), icon: 'Users' }
  ];

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
        tabs={tabs as unknown as Array<{ id: string; label: string; icon: string; badge?: unknown }>}
        activeTab={activeTab as unknown as string | number}
        onTabChange={(id) => setActiveTab(id as NotificationSection)} />
      
      <div
        id={`notifications-panel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`notifications-tab-${activeTab}`}
        className="admin-unified-content"
      >
        <ErrorBoundary>
          {renderContent()}
        </ErrorBoundary>
      </div>
    </div>);
};

export default UnifiedNotifications;
