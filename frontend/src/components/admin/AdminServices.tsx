
import { useTranslation } from '../../i18n/useTranslation';
import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { FolderTree, Package } from 'lucide-react';
import { useConfirm } from '../common/ConfirmDialog';

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

const LazyRegistrarTabsManager = React.lazy(() => import('./RegistrarTabsManager'));
const LazyServiceCatalog = React.lazy(() => import('./ServiceCatalog'));

const getServiceTabs = (t: (key: string, options?: Record<string, unknown>) => string) => [
  { key: 'catalog', label: t('admin2.asv_tab_catalog'), icon: Package },
  { key: 'queue-profiles', label: t('admin2.asv_tab_queue_profiles'), icon: FolderTree },
] as const;

type ServiceTabKey = 'catalog' | 'queue-profiles';

const isServiceTab = (value: string | null): value is ServiceTabKey =>
  value === 'catalog' || value === 'queue-profiles';

const getInitialServicesTab = (search: string): ServiceTabKey => {
  const params = new URLSearchParams(search);
  const requestedTabs = params.getAll('servicesTab');
  if (requestedTabs.length > 0) {
    return requestedTabs.length === 1 && isServiceTab(requestedTabs[0])
      ? requestedTabs[0]
      : 'catalog';
  }

  const savedTab = localStorage.getItem('servicesTab');
  return isServiceTab(savedTab) ? savedTab : 'catalog';
};

const isValidSetupDay = (value: string) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000-')) return false;
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
  const [tabsDirty, setTabsDirty] = useState(false);
  const [tabsSaving, setTabsSaving] = useState(false);
  const [confirmDiscard, discardDialog] = useConfirm();
  const [initialLocation] = useState(() => ({
    key: location.key,
    tab: getInitialServicesTab(location.search),
  }));
  const tabValues = new URLSearchParams(location.search).getAll('servicesTab');
  const servicesTab: ServiceTabKey = tabValues.length > 0
    ? (tabValues.length === 1 && isServiceTab(tabValues[0]) ? tabValues[0] : 'catalog')
    : (location.key === initialLocation.key ? initialLocation.tab : 'catalog');
  const serviceTabs = getServiceTabs(t);
  const setupReturnContext = servicesTab === 'catalog' || servicesTab === 'queue-profiles'
    ? parseSetupReturnContext(location.search, servicesTab === 'catalog' ? 'service-catalog' : 'queue-profiles')
    : null;

  useEffect(() => {
    // This is a non-authentication preference; the URL remains the canonical tab state.
    // eslint-disable-next-line no-restricted-properties -- servicesTab contains no authentication data.
    localStorage.setItem('servicesTab', servicesTab);
  }, [servicesTab]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const tabValuesInUrl = params.getAll('servicesTab');
    if (tabValuesInUrl.length !== 1 || tabValuesInUrl[0] !== servicesTab) {
      params.delete('servicesTab');
      params.set('servicesTab', servicesTab);
    }

    const destination = servicesTab === 'catalog' ? 'service-catalog' : 'queue-profiles';
    if (!parseSetupEntity(params, destination).valid) {
      params.delete('setupEntityKind');
      params.delete('setupEntityKey');
      params.delete('setupEntityId');
    }

    const normalizedSearch = params.toString();
    const nextSearch = normalizedSearch ? `?${normalizedSearch}` : '';
    if (nextSearch !== location.search) {
      navigate({
        pathname: location.pathname,
        search: nextSearch,
        hash: location.hash,
      }, { replace: true, state: location.state });
    }
  }, [location.hash, location.pathname, location.search, location.state, navigate, servicesTab]);

  const confirmLeaveTabs = async () => {
    if (tabsSaving) return false;
    if (!tabsDirty) return true;
    return confirmDiscard({
      title: t('registrarPanel.rt_title'),
      message: t('registrarPanel.rt_unsaved_warning'),
      confirmLabel: t('registrarPanel.rt_discard_confirm'),
      cancelLabel: t('common.cancel'),
      intent: 'warning',
    });
  };

  const selectTab = async (tabKey: ServiceTabKey) => {
    if (tabKey === servicesTab) return;
    if (!await confirmLeaveTabs()) return;
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
      hash: location.hash,
    }, { state: location.state });
  };

  return (
    <div>
      {setupReturnContext && (
        <div className="admin-sdx-step-nav" data-testid="queue-setup-return">
          <Link
            className="admin-sdx-link"
            to={buildSetupReturnLocation(setupReturnContext)}
            data-testid="queue-setup-return-link"
            onClick={(event) => {
              if (!tabsDirty && !tabsSaving) return;
              event.preventDefault();
              void confirmLeaveTabs().then((canLeave) => {
                if (canLeave) navigate(buildSetupReturnLocation(setupReturnContext));
              });
            }}
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
              onClick={() => { void selectTab(tab.key); }}
              disabled={tabsSaving && tab.key !== servicesTab}
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
          <LazyRegistrarTabsManager theme={isDark ? 'dark' : 'light'}
            defaultOpenProfiles={setupReturnContext?.entity?.kind === 'queue_profile'}
            onDirtyChange={setTabsDirty} onSavingChange={setTabsSaving} />
        </React.Suspense>
      )}
      {discardDialog}
    </div>
  );
};

export default AdminServices;
