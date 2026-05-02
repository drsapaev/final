import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useSearchParams } from 'react-router-dom';
import UserManagement from './UserManagement';
import UserDataTransferManager from './UserDataTransferManager';
import UserExportManager from './UserExportManager';
import GroupPermissionsManager from './GroupPermissionsManager';

// Простой компонент вкладок для админки
const AdminTabs = ({ tabs, activeTab, onTabChange }) => {
  return (
    <div style={{
      display: 'flex',
      gap: '4px',
      padding: '8px',
      background: 'var(--mac-gradient-sidebar)',
      borderRadius: '18px',
      border: '1px solid var(--mac-main-shell-border)',
      boxShadow: 'var(--mac-main-shell-shadow)',
      backdropFilter: 'var(--mac-blur-light)',
      WebkitBackdropFilter: 'var(--mac-blur-light)',
      marginBottom: '20px'
    }}>
      {tabs.map((tab) =>
      <button
        key={tab.id}
        onClick={() => onTabChange(tab.id)}
        style={{
          padding: '8px 16px',
          borderRadius: '10px',
          border: activeTab === tab.id ? '1px solid var(--mac-nav-item-active-border)' : '1px solid transparent',
          background: activeTab === tab.id ? 'var(--mac-nav-item-active)' : 'var(--mac-nav-item-bg)',
          color: activeTab === tab.id ? 'var(--mac-nav-item-active-text)' : 'var(--mac-text-primary)',
          fontSize: '14px',
          fontWeight: activeTab === tab.id ? '600' : '400',
          cursor: 'pointer',
          transition: 'all 0.2s ease',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          boxShadow: activeTab === tab.id ? 'var(--mac-shadow-sm)' : 'none'
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

const UnifiedUserManagement = () => {
  const [searchParams] = useSearchParams();
  const section = searchParams.get('section') || 'users';

  const getActiveTab = (section) => {
    switch (section) {
      case 'users':return 'management';
      case 'user-data-transfer':return 'transfer';
      case 'user-export':return 'export';
      case 'group-permissions':return 'permissions';
      default:return 'management';
    }
  };

  const [activeTab, setActiveTab] = useState(getActiveTab(section));

  // Обновляем активную вкладку при изменении секции
  useEffect(() => {
    setActiveTab(getActiveTab(section));
  }, [section]);

  const tabs = [
  { id: 'management', label: 'User Management', icon: 'Users' },
  { id: 'transfer', label: 'Data Transfer', icon: 'Database' },
  { id: 'export', label: 'Export Users', icon: 'Download' },
  { id: 'permissions', label: 'Group Permissions', icon: 'Shield' }];


  const renderContent = () => {
    switch (activeTab) {
      case 'management':
        return <UserManagement />;
      case 'transfer':
        return <UserDataTransferManager />;
      case 'export':
        return <UserExportManager />;
      case 'permissions':
        return <GroupPermissionsManager />;
      default:
        return <UserManagement />;
    }
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', color: 'var(--mac-text-primary)' }}>
      <AdminTabs
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab} />
      
      <div style={{ flex: 1, overflow: 'auto' }}>
        {renderContent()}
      </div>
    </div>);

};

UnifiedUserManagement.propTypes = {};

export default UnifiedUserManagement;
