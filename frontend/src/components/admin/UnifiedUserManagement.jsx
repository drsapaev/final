import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Database, Download, Shield, Users } from 'lucide-react';
import {
  SegmentedControl,
  MacOSTab } from '../ui/macos';
import UserManagement from './UserManagement';
import UserDataTransferManager from './UserDataTransferManager';
import UserExportManager from './UserExportManager';
import GroupPermissionsManager from './GroupPermissionsManager';
// P-025 fix: wrap child panels in ErrorBoundary to catch unexpected render errors.
import ErrorBoundary from '../common/ErrorBoundary';

const TAB_ICONS = {
  Users,
  Database,
  Download,
  Shield
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
  { id: 'management', label: 'Пользователи', icon: 'Users' },
  { id: 'transfer', label: 'Передача данных', icon: 'Database' },
  { id: 'export', label: 'Экспорт', icon: 'Download' },
  { id: 'permissions', label: 'Разрешения', icon: 'Shield' }];


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
    <div className="admin-unified-root">
      <MacOSTab
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab} />
      
      <div className="admin-unified-content">
        {/* P-025 fix: ErrorBoundary catches runtime errors in child panels
            (UserManagement, UserDataTransferManager, etc.) so the user sees
            a recovery UI instead of a blank screen. */}
        <ErrorBoundary>
          {renderContent()}
        </ErrorBoundary>
      </div>
    </div>);

};

UnifiedUserManagement.propTypes = {};

export default UnifiedUserManagement;
