import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useSearchParams } from 'react-router-dom';
import FCMManager from './FCMManager';
import RegistrarNotificationManager from './RegistrarNotificationManager';
import { useTheme } from '../../contexts/ThemeContext';
import ErrorBoundary from '../common/ErrorBoundary';

// Простой компонент вкладок для админки
const AdminTabs = ({ tabs, activeTab, onTabChange }) => {
  const { isDark } = useTheme();
  const colors = {
    bg: isDark ? 'rgba(15, 23, 42, 0.9)' : 'rgba(255, 255, 255, 0.98)',
    border: isDark ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.1)',
    text: isDark ? '#f8fafc' : '#0f172a',
    textSecondary: isDark ? '#cbd5e1' : '#64748b',
    active: isDark ? 'rgba(59, 130, 246, 0.2)' : 'rgba(59, 130, 246, 0.1)',
    activeText: '#3b82f6'
  };

  return (
    <div role="tablist" aria-label="Notification sections" className="admin-tab-bar-flex-dyn" style={{ '--admin-bg': colors.bg, '--admin-bd': `1px solid ${colors.border}` }}>
      {tabs.map((tab) =>
      <button
        key={tab.id}
        id={`notifications-tab-${tab.id}`}
        type="button"
        role="tab"
        aria-selected={activeTab === tab.id}
        aria-controls={`notifications-panel-${tab.id}`}
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

const UnifiedNotifications = () => {
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
      <AdminTabs
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
