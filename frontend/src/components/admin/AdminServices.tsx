
import { useTranslation } from '../../i18n/useTranslation';
import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { FolderTree, Package } from 'lucide-react';

import {
  Skeleton,
} from '../ui/macos';
import { useTheme } from '../../contexts/ThemeContext';

const LazyQueueProfilesManager = React.lazy(() => import('./QueueProfilesManager'));
const LazyServiceCatalog = React.lazy(() => import('./ServiceCatalog'));

const getServiceTabs = (t) => [
  { key: 'catalog', label: t('admin2.asv_tab_catalog'), icon: Package },
  { key: 'queue-profiles', label: t('admin2.asv_tab_queue_profiles'), icon: FolderTree },
];

const getInitialServicesTab = (search) => {
  const params = new URLSearchParams(search);
  return params.get('servicesTab') || localStorage.getItem('servicesTab') || 'catalog';
};

const AdminServices = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { isDark } = useTheme();
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [servicesTab, setServicesTab] = useState(() => getInitialServicesTab(location.search));
  const serviceTabs = getServiceTabs(t);

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
      <div className="admin-services-tab-bar">
        {serviceTabs.map((tab) => {
          const TabIcon = tab.icon;
          const isActive = servicesTab === tab.key;
          return (
            <button
              type="button"
              key={tab.key}
              aria-label={tab.label}
              onClick={() => selectTab(tab.key)}
              className={isActive ? 'admin-services-tab-btn-active' : 'admin-services-tab-btn'}
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
        <React.Suspense fallback={<Skeleton className="admin-skeleton-h-384" />}>
          <LazyServiceCatalog />
        </React.Suspense>
      )}
      {servicesTab === 'queue-profiles' && (
        <React.Suspense fallback={<Skeleton className="admin-skeleton-h-384" />}>
          <LazyQueueProfilesManager theme={isDark ? 'dark' : 'light'} />
        </React.Suspense>
      )}
    </div>
  );
};

export default AdminServices;
