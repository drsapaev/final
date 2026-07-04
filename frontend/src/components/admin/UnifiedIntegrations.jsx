import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useSearchParams } from 'react-router-dom';
import React from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import ErrorBoundary from '../common/ErrorBoundary';

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
const AdminTabs = ({ tabs, activeTab, onTabChange }) => {
  const { isDark } = useTheme();
  const colors = {
    bg: isDark ? 'rgba(15, 23, 42, 0.9)' : 'rgba(255, 255, 255, 0.98)',
    border: isDark ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.1)',
    text: isDark ? '#f8fafc' : '#0f172a',
    active: isDark ? 'rgba(59, 130, 246, 0.2)' : 'rgba(59, 130, 246, 0.1)',
    activeText: '#3b82f6'
  };

  return (
    <div role="tablist" aria-label="Integration sections" className="admin-tab-bar-flex-dyn" style={{ '--admin-bg': colors.bg, '--admin-bd': `1px solid ${colors.border}` }}>
      {tabs.map((tab) =>
      <button
        key={tab.id}
        id={`integrations-tab-${tab.id}`}
        type="button"
        role="tab"
        aria-selected={activeTab === tab.id}
        aria-controls={`integrations-panel-${tab.id}`}
        onClick={() => onTabChange(tab.id)}
        className="admin-tab-btn-dyn"
        style={{
          '--admin-tab-bg': activeTab === tab.id ? colors.active : 'transparent',
          '--admin-tab-color': activeTab === tab.id ? colors.activeText : colors.text,
          '--admin-tab-fw': activeTab === tab.id ? '600' : '400',
        }}>
          {tab.label}
        </button>
      )}
    </div>);
};

AdminTabs.propTypes = {
  tabs: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired
  })).isRequired,
  activeTab: PropTypes.string.isRequired,
  onTabChange: PropTypes.func.isRequired
};

const INTEGRATION_TABS = [
  { id: 'webhooks', label: 'Вебхуки' },
  { id: 'graphql', label: 'GraphQL API' },
  { id: 'cloud-printing', label: 'Облачная печать' },
  { id: 'medical-equipment', label: 'Медицинское оборудование' },
  { id: 'files', label: 'Файлы' },
];

const UnifiedIntegrations = () => {
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
      <AdminTabs
        tabs={INTEGRATION_TABS}
        activeTab={activeTab}
        onTabChange={handleTabChange} />

      <div
        id={`integrations-panel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`integrations-tab-${activeTab}`}
        className="admin-unified-content"
      >
        <ErrorBoundary>
          <React.Suspense fallback={<div className="admin-p-24 admin-text-secondary">Загрузка...</div>}>
            {renderContent()}
          </React.Suspense>
        </ErrorBoundary>
      </div>
    </div>);
};

export default UnifiedIntegrations;
