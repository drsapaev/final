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
import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useLabDirtyGuard } from '../components/laboratory/LabDirtyGuardContext';

const DEFAULT_DEFAULT_TAB = 'appointments';
const DEFAULT_VISIT_DEEP_LINK_TAB = 'visit';
const EMPTY_TAB_ALIASES: Record<string, string> = {};

export function useDoctorPanelState({
  defaultTab = DEFAULT_DEFAULT_TAB,
  visitDeepLinkTab = DEFAULT_VISIT_DEEP_LINK_TAB,
  patientDeepLinkTab = 'appointments',
  initialTab = null,
  validTabs = null,
  tabAliases = EMPTY_TAB_ALIASES,
}: {
  defaultTab?: string;
  visitDeepLinkTab?: string;
  patientDeepLinkTab?: string;
  initialTab?: string | null;
  validTabs?: string[] | null;
  tabAliases?: Record<string, string>;
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
    if (explicitTab) {
      const resolvedTab = tabAliases[explicitTab] || explicitTab;
      return !validTabs || validTabs.includes(resolvedTab) ? resolvedTab : defaultTab;
    }
    if (visitIdFromUrl) return visitDeepLinkTab;
    if (patientIdFromUrl) return patientDeepLinkTab;
    return defaultTab;
  }, [searchParams, visitIdFromUrl, patientIdFromUrl, visitDeepLinkTab, patientDeepLinkTab, defaultTab, tabAliases, validTabs]);

  const [activeTab, setActiveTab] = useState(() => {
    if (initialTab) return initialTab;
    return resolveTabFromUrl();
  });

  useEffect(() => {
    const urlTab = resolveTabFromUrl();
    const explicitTab = searchParams.get('tab');
    if (explicitTab && explicitTab !== urlTab) {
      const params = new URLSearchParams(location.search);
      params.set('tab', urlTab);
      navigate({ pathname: location.pathname, search: params.toString() }, { replace: true });
    }
    if (urlTab !== activeTab) {
      setActiveTab(urlTab);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolveTabFromUrl, searchParams, location.pathname, location.search, navigate]);

  // RETRO-3971-04 P1 hotfix: таб-переключение (sidebar-клик И Ctrl+1..5 через
  // useCardiologistHotkeys → goToTab) размонтирует VisitTab с keyed
  // EMRContainerV2 — dirty клинический черновик терялся БЕЗ какого-либо
  // решения: pathname не менялся, поэтому browser-Back sentinel вмешаться не
  // мог. Все панельные таб-переходы теперь идут через общий route-level
  // leave guard (pending-блок + Stay/Save/Discard диалог; при чистом
  // реестре переход выполняется немедленно — мгновенная навигация по
  // чистым табам сохранена). Хук используется cardiology/dermatology/
  // dentistry панелями — гвард покрывает все три специализации; standalone
  // fallback (рендер без LabDirtyGuardProvider в тестах) деградирует в
  // прежнее поведение без диалога.
  const guardRouteLeave = useLabDirtyGuard().guardRouteLeave;
  const guardRouteLeaveRef = useRef(guardRouteLeave);
  guardRouteLeaveRef.current = guardRouteLeave;
  const activeTabRef = useRef(activeTab);
  activeTabRef.current = activeTab;

  const handleTabChange = useCallback((tabId: string) => {
    const aliasedTab = tabAliases[tabId] || tabId;
    const resolvedTab = !validTabs || validTabs.includes(aliasedTab) ? aliasedTab : defaultTab;
    // Тот же таб: ни решения, ни дублирующей записи истории (прежний код
    // пушал дубликат URL при повторном клике на активную вкладку).
    if (resolvedTab === activeTabRef.current) return;
    guardRouteLeaveRef.current(() => {
      setActiveTab(resolvedTab);
      const params = new URLSearchParams(location.search);
      params.set('tab', resolvedTab);
      // P-029 (UX audit): use push instead of replace so the browser Back
      // button navigates between tabs intuitively. Previously used replace:
      // true, which meant Back always exited the panel entirely.
      navigate({ pathname: location.pathname, search: params.toString() }, { replace: false });
    });
  }, [defaultTab, location.pathname, location.search, navigate, tabAliases, validTabs]);

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
