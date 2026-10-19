
import { useTranslation } from '../../i18n/useTranslation';
import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { FolderTree, Package } from 'lucide-react';

import {
  Skeleton,
} from '../ui/macos';
import { useTheme } from '../../contexts/ThemeContext';
import type {
  QueueSetupEditorDestination,
  QueueSetupEntityRef,
  QueueSetupReturnContext,
  QueueSetupSection,
} from './AdminSetupDirections';

const LazyQueueProfilesManager = React.lazy(() => import('./QueueProfilesManager'));
const LazyServiceCatalog = React.lazy(() => import('./ServiceCatalog'));

const getServiceTabs = (t: (key: string, options?: Record<string, unknown>) => string) => [
  { key: 'catalog', label: t('admin2.asv_tab_catalog'), icon: Package },
  { key: 'queue-profiles', label: t('admin2.asv_tab_queue_profiles'), icon: FolderTree },
];

const getInitialServicesTab = (search: string) => {
  const params = new URLSearchParams(search);
  return params.get('servicesTab') || localStorage.getItem('servicesTab') || 'catalog';
};

const isValidSetupDay = (value: string) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00.000Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
};

const isValidSetupKey = (value: string) =>
  value.length > 0 && value.length <= 128 && value.trim() === value &&
  !Array.from(value).some((character) => {
    const code = character.charCodeAt(0);
    return code <= 0x1f || code === 0x7f;
  });

const parseSetupEntity = (
  params: URLSearchParams,
  destination: Exclude<QueueSetupEditorDestination, 'user-management'>,
): { valid: boolean; entity: QueueSetupEntityRef | null } => {
  const kind = params.get('setupEntityKind');
  const key = params.get('setupEntityKey');
  const id = params.get('setupEntityId');
  if (kind === null) return { valid: key === null && id === null, entity: null };
  if (kind === 'queue_profile' || kind === 'queue_tag') {
    const allowed = destination === 'queue-profiles' || kind === 'queue_tag';
    return {
      valid: allowed && key !== null && isValidSetupKey(key) && id === null,
      entity: allowed && key && isValidSetupKey(key) && id === null ? { kind, key } : null,
    };
  }
  if (kind === 'service') {
    const numericId = id !== null && /^[1-9]\d*$/.test(id) ? Number(id) : 0;
    const valid = destination === 'service-catalog' && Number.isSafeInteger(numericId) && numericId > 0 && key === null;
    return { valid, entity: valid ? { kind, id: numericId } : null };
  }
  return { valid: false, entity: null };
};

export const parseSetupReturnContext = (
  search: string,
  destination: Exclude<QueueSetupEditorDestination, 'user-management'>,
): QueueSetupReturnContext | null => {
  const params = new URLSearchParams(search);
  const setupParams = [
    'setupReturn', 'setupSection', 'setupProfile', 'setupDay',
    'setupEntityKind', 'setupEntityKey', 'setupEntityId',
  ];
  if (setupParams.some((name) => params.getAll(name).length > 1)) return null;
  if (params.get('setupReturn') !== 'queue-directions-v1') return null;
  const sectionValue = params.get('setupSection');
  if (sectionValue !== 'checklist' && sectionValue !== 'resources') return null;
  const profileKey = params.get('setupProfile');
  if (profileKey !== null && !isValidSetupKey(profileKey)) return null;
  const day = params.get('setupDay');
  if (day !== null && !isValidSetupDay(day)) return null;
  const parsedEntity = parseSetupEntity(params, destination);
  if (!parsedEntity.valid) return null;
  return {
    version: 1,
    destination,
    profileKey,
    section: sectionValue as QueueSetupSection,
    day,
    entity: parsedEntity.entity,
  };
};

export const buildSetupReturnLocation = (context: QueueSetupReturnContext) => {
  const params = new URLSearchParams();
  if (context.profileKey) params.set('profile', context.profileKey);
  params.set('section', context.section);
  if (context.day) params.set('day', context.day);
  return { pathname: '/admin/setup-directions', search: `?${params.toString()}` };
};

const AdminServices = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { isDark } = useTheme();
  const { t: rawT } = useTranslation(); const t = rawT;
  const [servicesTab, setServicesTab] = useState(() => getInitialServicesTab(location.search));
  const serviceTabs = getServiceTabs(t);
  const setupReturnContext = servicesTab === 'catalog' || servicesTab === 'queue-profiles'
    ? parseSetupReturnContext(location.search, servicesTab === 'catalog' ? 'service-catalog' : 'queue-profiles')
    : null;

  useEffect(() => {
    localStorage.setItem('servicesTab', servicesTab);
  }, [servicesTab]);

  const selectTab = (tabKey: string) => {
    setServicesTab(tabKey);
    const params = new URLSearchParams(location.search);
    params.set('servicesTab', tabKey);
    const destination = tabKey === 'catalog'
      ? 'service-catalog'
      : tabKey === 'queue-profiles'
        ? 'queue-profiles'
        : null;
    if (destination && !parseSetupEntity(params, destination).valid) {
      params.delete('setupEntityKind');
      params.delete('setupEntityKey');
      params.delete('setupEntityId');
    }
    navigate({
      pathname: location.pathname,
      search: `?${params.toString()}`,
    }, { replace: true });
  };

  return (
    <div>
      {setupReturnContext && (
        <div className="admin-sdx-step-nav" data-testid="queue-setup-return">
          <Link
            className="admin-sdx-link"
            to={buildSetupReturnLocation(setupReturnContext)}
            data-testid="queue-setup-return-link"
          >
            {t('admin2.sdx_title')}
          </Link>
        </div>
      )}
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
              onMouseEnter={(event: React.MouseEvent<HTMLElement>) => {
                if (!isActive) {
                  event.currentTarget.style.color = 'var(--mac-text-primary)';
                }
              }}
              onMouseLeave={(event: React.MouseEvent<HTMLElement>) => {
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
