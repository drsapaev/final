// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import React from 'react';
import ErrorBoundary from '../common/ErrorBoundary';
import { MacOSTab } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';

// Lazy-load child panels for bundle optimization
const LazyWebhookManager = React.lazy(() => import('./WebhookManager'));
const LazyGraphQLExplorer = React.lazy(() => import('./GraphQLExplorer'));
const LazyCloudPrintingManager = React.lazy(() => import('./CloudPrintingManager'));
const LazyMedicalEquipmentManager = React.lazy(() => import('./MedicalEquipmentManager'));
const LazyFileManager = React.lazy(() => import('../files/FileManager'));

// IA PR-2: Integrations hub — consolidates 5 previously-separate sidebar items
// (webhooks, graphql, cloud-printing, medical-equipment, file-management) into
// one tabbed surface. The 5 routes are demoted to nav:false (bookmark-only);
// this hub is the single sidebar entry under "Система".

const INTEGRATION_TABS = (t) => [
  { id: 'webhooks', label: t('admin2.ui_tab_webhooks') },
  { id: 'graphql', label: 'GraphQL API' },
  { id: 'cloud-printing', label: t('admin2.ui_tab_cloud_printing') },
  { id: 'medical-equipment', label: t('admin2.ui_tab_medical_equipment') },
  { id: 'files', label: t('admin2.ui_tab_files') },
];

const UnifiedIntegrations = () => {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const section = searchParams.get('tab') || 'webhooks';
  const [activeTab, setActiveTab] = useState(section);

  useEffect(() => {
    setActiveTab(section);
  }, [section]);

  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    setSearchParams({ tab: tabId }, { replace: true });
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'webhooks':
        return <LazyWebhookManager />;
      case 'graphql':
        return <LazyGraphQLExplorer />;
      case 'cloud-printing':
        return <LazyCloudPrintingManager />;
      case 'medical-equipment':
        return <LazyMedicalEquipmentManager />;
      case 'files':
        return <LazyFileManager />;
      default:
        return <LazyWebhookManager />;
    }
  };

  return (
    <div className="admin-unified-root-no-color">
      <MacOSTab
        tabs={INTEGRATION_TABS(t)}
        activeTab={activeTab}
        onTabChange={handleTabChange} />

      <div
        id={`integrations-panel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`integrations-tab-${activeTab}`}
        className="admin-unified-content"
      >
        <ErrorBoundary>
          <React.Suspense fallback={<div className="admin-p-24 admin-text-secondary">{t('admin2.ui_loading')}</div>}>
            {renderContent()}
          </React.Suspense>
        </ErrorBoundary>
      </div>
    </div>);
};

export default UnifiedIntegrations;
