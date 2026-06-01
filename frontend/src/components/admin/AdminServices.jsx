import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { FolderTree, Package } from 'lucide-react';

import { MacOSLoadingSkeleton } from '../ui/macos';
import { useTheme } from '../../contexts/ThemeContext';

const LazyQueueProfilesManager = React.lazy(() => import('./QueueProfilesManager'));
const LazyServiceCatalog = React.lazy(() => import('./ServiceCatalog'));

const SERVICE_TABS = [
  { key: 'catalog', label: 'Справочник услуг', icon: Package },
  { key: 'queue-profiles', label: 'Вкладки регистратуры', icon: FolderTree },
];

const getInitialServicesTab = (search) => {
  const params = new URLSearchParams(search);
  return params.get('servicesTab') || localStorage.getItem('servicesTab') || 'catalog';
};

const AdminServices = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { isDark } = useTheme();
  const [servicesTab, setServicesTab] = useState(() => getInitialServicesTab(location.search));

  useEffect(() => {
    localStorage.setItem('servicesTab', servicesTab);
  }, [servicesTab]);

  const selectTab = (tabKey) => {
    setServicesTab(tabKey);
    const params = new URLSearchParams(location.search);
    params.set('servicesTab', tabKey);
    navigate({
      pathname: location.pathname,
      search: `?${params.toString()}`,
    }, { replace: true });
  };

  return (
    <div>
      <div style={{
        display: 'flex',
        gap: '8px',
        marginBottom: '24px',
        borderBottom: '1px solid var(--mac-border)',
        paddingBottom: '0',
      }}>
        {SERVICE_TABS.map((tab) => {
          const TabIcon = tab.icon;
          const isActive = servicesTab === tab.key;
          return (
            <button
              type="button"
              key={tab.key}
              aria-label={tab.label}
              onClick={() => selectTab(tab.key)}
              style={{
                padding: '12px 20px',
                background: 'transparent',
                border: 'none',
                borderBottom: isActive ? '2px solid var(--mac-accent)' : '2px solid transparent',
                color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '14px',
                fontWeight: isActive ? '600' : '500',
                transition: 'all 0.2s ease',
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
              }}
              onMouseEnter={(event) => {
                if (!isActive) {
                  event.currentTarget.style.color = 'var(--mac-text-primary)';
                }
              }}
              onMouseLeave={(event) => {
                if (!isActive) {
                  event.currentTarget.style.color = 'var(--mac-text-secondary)';
                }
              }}
            >
              <TabIcon size={18} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {servicesTab === 'catalog' && (
        <React.Suspense fallback={<MacOSLoadingSkeleton style={{ height: '384px' }} />}>
          <LazyServiceCatalog />
        </React.Suspense>
      )}
      {servicesTab === 'queue-profiles' && (
        <React.Suspense fallback={<MacOSLoadingSkeleton style={{ height: '384px' }} />}>
          <LazyQueueProfilesManager theme={isDark ? 'dark' : 'light'} />
        </React.Suspense>
      )}
    </div>
  );
};

export default AdminServices;
