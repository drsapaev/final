/**
 * useDoctorPanelState — shared state hook for doctor panels.
 *
 * P-009 fix: extract common logic from DoctorPanel, CardiologistPanelUnified,
 * DermatologistPanelUnified, and DentistPanelUnified. Each panel previously
 * duplicated:
 *   - URL <-> activeTab sync (different implementations: getInitialTab vs
 *     getActiveTabFromURL useCallback)
 *   - patientId / visitId parsing from URL
 *   - selectedPatient state + setter
 *   - handleTabChange with URL update
 *
 * The hook consolidates these into one tested implementation. Specialty panels
 * pass their defaultTab and visitDeepLinkTab to control URL-driven routing:
 *   - Cardiology/Dermatology: visitId in URL opens 'visit' tab
 *   - Dentistry: visitId in URL opens 'visits' tab (plural)
 *   - All: patientId in URL opens 'appointments' tab
 */
import { useState, useEffect, useCallback, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

const DEFAULT_DEFAULT_TAB = 'appointments';
const DEFAULT_VISIT_DEEP_LINK_TAB = 'visit';

export function useDoctorPanelState({
  defaultTab = DEFAULT_DEFAULT_TAB,
  visitDeepLinkTab = DEFAULT_VISIT_DEEP_LINK_TAB,
  patientDeepLinkTab = 'appointments',
  initialTab = null,
} = {}) {
  const location = useLocation();
  const navigate = useNavigate();

  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);

  const patientIdFromUrl = useMemo(() => {
    const raw = searchParams.get('patientId');
    if (!raw) return null;
    const parsed = parseInt(raw, 10);
    return Number.isFinite(parsed) ? parsed : null;
  }, [searchParams]);

  const visitIdFromUrl = useMemo(() => {
    const raw = searchParams.get('visitId') || searchParams.get('visit_id');
    if (!raw) return null;
    const parsed = parseInt(raw, 10);
    return Number.isFinite(parsed) ? parsed : null;
  }, [searchParams]);

  const resolveTabFromUrl = useCallback(() => {
    const explicitTab = searchParams.get('tab');
    if (explicitTab) return explicitTab;
    if (visitIdFromUrl) return visitDeepLinkTab;
    if (patientIdFromUrl) return patientDeepLinkTab;
    return defaultTab;
  }, [searchParams, visitIdFromUrl, patientIdFromUrl, visitDeepLinkTab, patientDeepLinkTab, defaultTab]);

  const [activeTab, setActiveTab] = useState(() => {
    if (initialTab) return initialTab;
    return resolveTabFromUrl();
  });

  useEffect(() => {
    const urlTab = resolveTabFromUrl();
    if (urlTab !== activeTab) {
      setActiveTab(urlTab);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolveTabFromUrl]);

  const handleTabChange = useCallback((tabId) => {
    setActiveTab(tabId);
    const params = new URLSearchParams(location.search);
    params.set('tab', tabId);
    // P-029 (UX audit): use push instead of replace so the browser Back
    // button navigates between tabs intuitively. Previously used replace:
    // true, which meant Back always exited the panel entirely.
    navigate({ pathname: location.pathname, search: params.toString() }, { replace: false });
  }, [location.pathname, location.search, navigate]);

  const [selectedPatient, setSelectedPatient] = useState(null);

  return {
    activeTab,
    setActiveTab,
    handleTabChange,
    patientIdFromUrl,
    visitIdFromUrl,
    searchParams,
    selectedPatient,
    setSelectedPatient,
  };
}

export default useDoctorPanelState;
