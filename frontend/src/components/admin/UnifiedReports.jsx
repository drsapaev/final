import React, { useState } from 'react';
import PropTypes from 'prop-types';
import ReportsManager from './ReportsManager';
import ReportGenerator from './ReportGenerator';
import { useTheme } from '../../contexts/ThemeContext';

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
      <div style={{
        display: 'flex',
        gap: '4px',
        padding: '8px',
        background: colors.bg,
        borderRadius: '8px',
        border: `1px solid ${colors.border}`,
        marginBottom: '20px'
      }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            style={{
              padding: '8px 16px',
              border: 'none',
              borderRadius: '6px',
              background: activeTab === tab.id ? colors.active : 'transparent',
              color: activeTab === tab.id ? colors.activeText : colors.text,
              fontSize: '14px',
              fontWeight: activeTab === tab.id ? '600' : '400',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
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
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <AdminTabs
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />
      <div style={{ flex: 1, overflow: 'auto' }}>
        {renderContent()}
      </div>
    </div>
  );
};

export default UnifiedReports;
