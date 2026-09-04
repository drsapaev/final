import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { DOCTOR_PANEL_TABS } from './doctorStatus';

/**
 * PR-UI-15-1: tab/URL/filter view-state slice extracted verbatim from
 * pages/DoctorPanel.tsx (registrar/cashier decomposition precedent).
 *
 * Owns:
 *  - activeTab + initial-tab resolution from URL (?tab= / ?patientId=)
 *  - setDoctorTab (guard + QW#2 filter reset + QW#1 replace:false navigate)
 *  - the URL-sync effect (deep-link support, verbatim)
 *  - searchQuery / filterStatus (reset on tab change — QW#2)
 *
 * Behavior contract (byte-identical to the original inline code):
 *  - unknown ?tab= values fall back to patientId→'patients'→'dashboard'
 *  - Back button works between tabs (replace: false, P-029 fix)
 *  - switching tabs resets search + status filter
 */
export function useDoctorTabState() {
  const location = useLocation();
  const navigate = useNavigate();

  // Состояние
  const [activeTab, setActiveTab] = useState<string>(() => {
    // Если есть patientId, переходим на вкладку пациентов
    const params = new URLSearchParams(window.location.search);
    const requestedTab = params.get('tab');
    if (requestedTab && DOCTOR_PANEL_TABS.has(requestedTab)) {
      return requestedTab;
    }
    if (params.get('patientId')) {
      return 'patients';
    }
    return 'dashboard';
  });

  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');

  const setDoctorTab = useCallback((tabId: string) => {
    if (!DOCTOR_PANEL_TABS.has(tabId)) {
      return;
    }

    setActiveTab(tabId);
    // UX Audit Doctor QW#2: сброс фильтров при смене вкладки.
    setFilterStatus('all');
    setSearchQuery('');
    const params = new URLSearchParams(location.search);
    params.set('tab', tabId);
    // UX Audit Doctor QW#1: replace: false — Back-кнопка браузера работает между вкладками (P-029 fix).
    navigate({ pathname: location.pathname, search: `?${params.toString()}` }, { replace: false });
  }, [location.pathname, location.search, navigate]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const requestedTab = params.get('tab');
    const patientId = params.get('patientId');
    const nextTab = requestedTab && DOCTOR_PANEL_TABS.has(requestedTab)
      ? requestedTab
      : patientId
        ? 'patients'
        : 'dashboard';

    if (!requestedTab && patientId) {
      params.set('tab', nextTab);
      navigate({ pathname: location.pathname, search: `?${params.toString()}` }, { replace: false });
    }

    if (activeTab !== nextTab) {
      setActiveTab(nextTab);
    }
  }, [activeTab, location.pathname, location.search, navigate]);

  return {
    activeTab,
    setActiveTab,
    setDoctorTab,
    searchQuery,
    setSearchQuery,
    filterStatus,
    setFilterStatus,
  };
}
