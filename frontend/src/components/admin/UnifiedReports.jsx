import { useState } from 'react';
import PropTypes from 'prop-types';
import ReportsManager from './ReportsManager';
import ReportGenerator from './ReportGenerator';
import { useTheme } from '../../contexts/ThemeContext';
import ErrorBoundary from '../common/ErrorBoundary';

const UnifiedReports = () => {
  const [activeTab, setActiveTab] = useState('manager');
  const { isDark } = useTheme();

  const tabs = [
    { id: 'manager', label: 'Reports Manager', icon: 'BarChart3' },
    { id: 'generator', label: 'Report Generator', icon: 'FileText' }
  ];

  // Простой компонент вкладок для админки
  const AdminTabs = ({ tabs, activeTab, onTabChange }) => {
    const colors = {
      bg: isDark ? 'rgba(15, 23, 42, 0.9)' : 'rgba(255, 255, 255, 0.98)',
      border: isDark ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.1)',
      text: isDark ? '#f8fafc' : '#0f172a',
      textSecondary: isDark ? '#cbd5e1' : '#64748b',
      active: isDark ? 'rgba(59, 130, 246, 0.2)' : 'rgba(59, 130, 246, 0.1)',
      activeText: '#3b82f6'
    };

    return (
      <div role="tablist" aria-label="Reports sections" className="admin-tab-bar-flex-dyn" style={{ '--admin-bg': colors.bg, '--admin-bd': `1px solid ${colors.border}` }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            id={`reports-tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls={`reports-panel-${tab.id}`}
            onClick={() => onTabChange(tab.id)}
            className="admin-tab-btn-dyn"
            style={{
              '--admin-tab-bg': activeTab === tab.id ? colors.active : 'transparent',
              '--admin-tab-color': activeTab === tab.id ? colors.activeText : colors.text,
              '--admin-tab-fw': activeTab === tab.id ? '600' : '400',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>
    );
  };

  AdminTabs.propTypes = {
    tabs: PropTypes.arrayOf(PropTypes.shape({
      id: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired
    })).isRequired,
    activeTab: PropTypes.string.isRequired,
    onTabChange: PropTypes.func.isRequired
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'manager':
        return <ReportsManager />;
      case 'generator':
        return <ReportGenerator />;
      default:
        return <ReportsManager />;
    }
  };

  return (
    <div className="admin-unified-root-no-color">
      <AdminTabs
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />
      <div
        id={`reports-panel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`reports-tab-${activeTab}`}
        className="admin-unified-content"
      >
        <ErrorBoundary>
          {/* P-025 fix: catch runtime errors in child panels */}
          {renderContent()}
        </ErrorBoundary>
      </div>
    </div>
  );
};

export default UnifiedReports;
