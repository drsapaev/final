import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useSearchParams } from 'react-router-dom';
import { Database, Download, Shield, Users } from 'lucide-react';
import { SegmentedControl } from '../ui/macos';
import UserManagement from './UserManagement';
import UserDataTransferManager from './UserDataTransferManager';
import UserExportManager from './UserExportManager';
import GroupPermissionsManager from './GroupPermissionsManager';

const TAB_ICONS = {
  Users,
  Database,
  Download,
  Shield
};

const AdminTabs = ({ tabs, activeTab, onTabChange }) => {
  const options = tabs.map((tab) => {
    const Icon = TAB_ICONS[tab.icon];

    return {
      value: tab.id,
      label: (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
          {Icon ? <Icon size={14} aria-hidden="true" /> : null}
          {tab.label}
        </span>
      )
    };
  });

  return (
    <div style={{
      maxWidth: '100%',
      overflowX: 'auto',
      paddingBottom: '6px',
      marginBottom: '20px',
      scrollbarWidth: 'thin'
    }}>
      <SegmentedControl
        aria-label="Разделы управления пользователями"
        value={activeTab}
        onChange={onTabChange}
        options={options}
        size="large"
        style={{
          minWidth: 'max-content',
          background: 'var(--mac-gradient-sidebar)',
          border: '1px solid var(--mac-main-shell-border)',
          borderRadius: '14px',
          boxShadow: 'var(--mac-main-shell-shadow)'
        }} />
    </div>);

};

AdminTabs.propTypes = {
  tabs: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.string.isRequired,
    label: PropTypes.string.isRequired,
    icon: PropTypes.string
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
