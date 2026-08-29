import { useState, useEffect, useCallback, useRef, useMemo, memo } from 'react';
import type { CSSProperties } from 'react';
import { useSearchParams, useLocation, useNavigate } from 'react-router-dom';
// PR-UI-13-4: EnhancedAppointmentsTable import moved to views/WorklistView.tsx.
import AppointmentContextMenu from '../components/tables/AppointmentContextMenu';
import ModernTabs from '../components/navigation/ModernTabs';
// PR-UI-13-4: Button/Badge moved to views/WorklistView.tsx; Icon stays
// (breadcrumb + tab separators).
import { Icon } from '../components/ui/macos';
// PR-UI-13-4: AnimatedLoader import moved to views/WorklistView.tsx.
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import { useTheme } from '../contexts/ThemeContext';
import '../components/ui/animations.css';
import '../styles/responsive.css';
import '../styles/animations.css';
import '../styles/dark-theme-visibility-fix.css';
// DS-3: utility classes for common inline style patterns
import './registrar/registrar.css';
import logger from '../utils/logger';
// Note: getApiOrigin moved to ./registrar/registrarHelpers.js (decomp step 1)
// PR-UI-13-1: tokenManager/api imports moved to useRegistrarWorklistData
// (loadAppointments extraction — no other panel call-sites existed).
import notify from '../services/notify';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../components/common/ConfirmDialog';
// PR-UI-13-4: local ErrorBoundary around the wizard (plan §PR-UI-13 item 4).
import ErrorBoundary from '../components/common/ErrorBoundary';
// Unified i18n: single useTranslation hook for all UI strings (registrarPanel.*)
// and confirm/notify strings (registrar.*). Replaces the legacy split between
// getRegistrarTranslator (flat keys) and adapter (namespaced keys).
import { useTranslation } from '../i18n/useTranslation';
import type { Appointment } from '../types/domain/clinic';
import type { QueueEntry } from '../types/domain/queue';
// Decomp 2: hotkeys extracted to useRegistrarHotkeys hook
import { useRegistrarHotkeys } from './registrar/useRegistrarHotkeys';
// Decomp 3: reschedule helpers extracted to useRegistrarReschedule hook
import { useRegistrarReschedule } from './registrar/useRegistrarReschedule';
// Decomp 4: data-loading functions extracted to useRegistrarData hook
import { useRegistrarData } from './registrar/useRegistrarData';
// Decomp 8 (PR-UI-13-1): worklist data lifecycle extracted to
// useRegistrarWorklistData hook (fetch + reducer state machine + refresh
// lifecycle: initial load / queueUpdated / departments:updated /
// 30s auto-refresh / calendar date change).
import { useRegistrarWorklistData } from './registrar/useRegistrarWorklistData';
// Decomp 9 (PR-UI-13-2): view-model row computation + department stats
// extracted to registrarWorklistRows.ts; service filtering to
// registrarServiceFilter.ts.
import {
  computeDepartmentStats,
  computeRegistrarWorklistRows,
  type QueueProfileItem,
} from './registrar/registrarWorklistRows';
// Decomp 10 (PR-UI-13-3): dialog + wizard state machines.
import { useRegistrarDialogs } from './registrar/useRegistrarDialogs';
import { useRegistrarWizard } from './registrar/useRegistrarWizard';
// Decomp 10 views (PR-UI-13-3): extracted dialog-composition views.
import RecordPreview from './registrar/views/RecordPreview';
import RescheduleSlots from './registrar/views/RescheduleSlots';
// Decomp 11 (PR-UI-13-4): worklist section view.
import WorklistView from './registrar/views/WorklistView';
// Decomp 5: record action handlers extracted to useRegistrarActions hook
import { useRegistrarActions } from './registrar/useRegistrarActions';
// Decomp 6a: QueueView extracted to component
import QueueView from './registrar/views/QueueView';
// Decomp 6b: WelcomeView extracted to component
import WelcomeView from './registrar/views/WelcomeView';
// Strategic Direction 3: navigation helpers for canonical nested routes
import { getViewFromPath } from './registrar/registrarNavigation';

// Decomp step 1: helpers extracted to ./registrar/registrarHelpers.js
import {
  // PR-UI-13-3: buildPostWizardPaymentRow moved to useRegistrarWizard;
  // normalizePatientGender + formatPreviewList moved to RecordPreviewDialog.
  REGISTRAR_TAB_LABEL_KEYS,
  REGISTRAR_STATUS_LABEL_KEYS,
  isMultiRecordAggregateRow,
} from './registrar/registrarHelpers';


// Современные диалоги
import PaymentDialog from '../components/dialogs/PaymentDialog';
import CancelDialog from '../components/dialogs/CancelDialog';
import PrintDialog from '../components/dialogs/PrintDialog';
// PR-UI-13-3: ModernDialog import moved to RecordPreviewDialog +
// RescheduleSlotsDialog (both dialog JSX blocks extracted).
import { printPanelTicketInBrowserAsync } from '../services/panelPrint';

// Современный мастер
// ✅ Используется только новый мастер (V2)
import AppointmentWizardV2 from '../components/wizard/AppointmentWizardV2';
import PaymentManager from '../components/payment/PaymentManager';

// Modern queue manager — extracted to QueueView component (Decomp 6a)
// Modern statistics — extracted to WelcomeView component (Decomp 7a)

// Модальное окно редактирования пациента
// ✨ ЗАКОММЕНТИРОВАНО: Теперь используется AppointmentWizardV2 для редактирования
// import EditPatientModal from '../components/common/EditPatientModal';

// Утилиты для работы с датами
// PR-UI-13-4: formatRegistrarDate moved to views/WorklistView.tsx.
import { getLocalDateString } from '../utils/dateUtils';
// PR-UI-13-3: rescheduleTomorrow/rescheduleVisit moved to
// registrar/views/RescheduleSlotsDialog.tsx.
// Note: formatNetworkErrorMessage + isNetworkFetchError moved to useRegistrarData.js (Decomp 4)
import { getErrorMessage } from '../utils/errorHandler';
// PR-UI-13-2: aggregation/sorting imports moved to
// registrar/registrarWorklistRows.ts (view-model increment).

// PR-UI-13-2: SSOT service-code resolver import moved to
// registrar/registrarServiceFilter.ts.

// API client
// PR-UI-13-1: api import moved to useRegistrarWorklistData (loadAppointments
// extraction — no other panel call-sites existed).
// UX Audit Registrar #1: getPatient() — централизованный доступ к /patients/{id}.
// Раньше здесь был raw fetch() с ручным Authorization-хедером.
import { getPatient } from '../api/patients';
// ⭐ BATCH API: Для атомарных операций с записями пациента (см. BATCH_UPDATE_ARCHITECTURE.md)


// ✅ Форс-мажор модальное окно
import ForceMajeureModal from '../components/registrar/ForceMajeureModal';
// UX Audit Registrar #14: extracted DataSourceIndicator and CSV utilities.
import DataSourceIndicator from './registrar/DataSourceIndicator';
import { generateCSV, downloadCSV } from './registrar/registrarCsv';

// ADR-0016: canonical error types from types/errors.ts.
import type { HttpApiError } from '../types/errors';

// PR-UI-13-2: QueueProfileItem moved to ./registrar/registrarWorklistRows.ts

const RegistrarPanel = () => {
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw;
  // Рендер компонента (debug отключен)
  // Адаптивные хуки
  const { isMobile, isTablet } = useBreakpoint();

  // Основные состояния
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  // R-02 fix: activeTab синхронизирован с URL (?dept=...).
  // Раньше был useState(null) — F5 сбрасывал выбранное отделение.
  const [activeTab, setActiveTabRaw] = useState(() => searchParams.get('dept') || null);
  const setActiveTab = useCallback((tab: string | null) => {
    setActiveTabRaw(tab);
    // R-02: пишем в URL для shareable links + back button
    const params = new URLSearchParams(window.location.search);
    if (tab) {
      params.set('dept', tab);
    } else {
      params.delete('dept');
    }
    setSearchParams(params, { replace: true });
  }, [setSearchParams]);
  const currentView = useMemo(() => {
    // Phase 3: rely solely on canonical path-derived view.
    // Legacy ?view= and ?tab= params are auto-redirected to canonical paths
    // by the Phase 2 redirect useEffect below, so they never need to be
    // parsed here. The redirect preserves all other query params.
    return getViewFromPath(location.pathname);
  }, [location.pathname]);

  // ✅ Phase 2: redirect legacy ?view=welcome|queue to canonical paths
  // /registrar?view=welcome → /registrar/welcome
  // /registrar?view=queue   → /registrar/queue
  // Preserves all other query params (q, status, date, patientId, dept).
  // The redirect is replace-only (no history pollution) and runs once per
  // legacy-view occurrence.
  useEffect(() => {
    const legacyView = searchParams.get('view');
    if (legacyView !== 'welcome' && legacyView !== 'queue') return;
    // Only redirect when on the bare /registrar path (not already on a sub-path)
    if (location.pathname !== '/registrar') return;

    const params = new URLSearchParams(searchParams);
    params.delete('view');
    params.delete('tab');
    const qs = params.toString();
    const target = qs ? `/registrar/${legacyView}?${qs}` : `/registrar/${legacyView}`;
    navigate(target, { replace: true });
  }, [searchParams, location.pathname, navigate]);

  const searchQuery = useMemo(() => (searchParams.get('q') || '').toLowerCase(), [searchParams]);
  const statusFilter = useMemo(() => searchParams.get('status'), [searchParams]);
  const todayStr = getLocalDateString();

  // ✅ Получаем patientId из URL для автоматического поиска
  const patientIdFromUrl = useMemo(() => {
    const id = searchParams.get('patientId');
    return id ? parseInt(id, 10) : null;
  }, [searchParams]);

  // ✅ Эффект для автоматической загрузки пациента из URL
  useEffect(() => {
    const loadPatientFromUrl = async () => {
      if (!patientIdFromUrl) return;

      try {
        // UX Audit Registrar #1: raw fetch() с ручным Authorization-хедером
        // заменён на getPatient() из api/patients.
        // Auth-token добавляется автоматически axios-interceptor'ом в api/client.js.
        // 401/403 обрабатываются интерсептором (redirect to login или refresh).
        const patientData = await getPatient(patientIdFromUrl);
        const patientName = `${patientData.last_name || ''} ${patientData.first_name || ''}`.trim();

        // Устанавливаем поисковый запрос с именем пациента
        setSearchParams((prev) => {
          const newParams = new URLSearchParams(prev);
          newParams.set('q', patientName);
          return newParams;
        });

        // UX Audit R-3.6: убрано логирование patientName (PII leak).
        logger.info('[Registrar] Загружен пациент из URL (patientId matched)');
      } catch (error: unknown) {
        // 404 — пациент не найден, не логируем как error.
        const status = (error as HttpApiError)?.response?.status;
        if (status !== 404) {
          logger.error('[Registrar] Не удалось загрузить пациента:', error);
        }
      }
    };

    loadPatientFromUrl();
  }, [patientIdFromUrl, setSearchParams]);

  // ✅ ДИНАМИЧЕСКИЕ ОТДЕЛЕНИЯ: PR-UI-13-4 — reference-data state (doctors,
  // services, dynamicDepartments) is owned by useRegistrarData below.

  // ⭐ SSOT: Queue profiles loaded from API (via ModernTabs)
  // Used for filtering entries by queue_tags instead of hardcoded mapping
  const [queueProfiles, setQueueProfiles] = useState<QueueProfileItem[]>([]);

  // PR-UI-09c-4 (CI-flake root cause): onProfilesLoaded MUST be referentially
  // stable. ModernTabs' loadQueueProfiles useCallback depends on it and its
  // effect re-runs on every identity change — the previous inline arrow got a
  // new identity on every RegistrarPanel render, so each profiles fetch
  // triggered a parent re-render that re-triggered the fetch: an infinite
  // load → loaded → load flicker (and unbounded API refetch loop) on the
  // registrar page. Stable identity (useState setter is stable) breaks the
  // cycle; surfaced by the visual-regression Surface 4 timing race.
  const handleProfilesLoaded = useCallback((profiles: unknown[]) => {
    setQueueProfiles(profiles as QueueProfileItem[]);
  }, []);

  // PR-UI-13-3 (Decomp 10): dialog + wizard state (useRegistrarDialogs +
  // useRegistrarWizard) wired below, after the data hooks they depend on
  // (loadAppointments / loadIntegratedData / tI18n).
  // PR-UI-13-1: autoRefresh const + reschedule wiring moved below — the
  // reschedule hook consumes setAppointments from useRegistrarWorklistData.
  // PR-UI-13-4: doctors/services/dynamicDepartments moved into useRegistrarData.
  const [showCalendar, setShowCalendar] = useState(false);
  const [historyDate, setHistoryDate] = useState(getLocalDateString());
  const [tempDateInput, setTempDateInput] = useState(getLocalDateString()); // Выбор врача остаётся явным: URL-параметр или ручной выбор в очереди
  // Unified i18n hook: single source of truth for all translations.
  // - registrarPanel.* — flat UI keys (tabs, statuses, headings, buttons)
  // - registrar.*      — confirm dialog titles/messages + notify messages
  // Language is read from react-i18next state (not localStorage directly).
  // Reading `language` from the i18n instance is safe: useTranslation()
  // subscribes to languageChanged events and triggers a re-render, so
  // i18n.language is always current when this component renders.
  const { t: tI18n, language } = useTranslation();
  // Normalize language for legacy components that expect 'uz' not 'uz-Latn'
  const legacyLanguage = language?.startsWith('uz') ? 'uz' : language?.split('-')[0] || 'ru';
  // Backward-compat wrapper: WelcomeView and QueueView receive `t` as a prop
  // and call t('key') for registrarPanel.* flat keys. Wrap tI18n to accept
  // flat keys and route them to the registrarPanel namespace.
  // Also handles 'misc.*' and 'registrar.*' namespaced keys passed through.
  const t = (key: string) => {
    if (key.includes('.')) return tI18n(key);
    return tI18n('registrarPanel.' + key);
  };
  const currentWorklistLabel = tI18n('registrarPanel.' + (REGISTRAR_TAB_LABEL_KEYS[activeTab as keyof typeof REGISTRAR_TAB_LABEL_KEYS] || 'tabs_appointments'));
  const statusFilterLabel = statusFilter ? tI18n('registrarPanel.' + (REGISTRAR_STATUS_LABEL_KEYS[statusFilter as keyof typeof REGISTRAR_STATUS_LABEL_KEYS] || statusFilter)) : null;
  const { theme, getSpacing, getFontSize, getColor } = useTheme();
  // Адаптивные цвета из централизованной системы темизации
  // DS-2 fix: replaced --color-* variables with --mac-* canonical tokens
  const textColor = 'var(--mac-text-primary)';

  // Phase 3: pageStyle, tableContainerStyle, tableContentStyle constants
  // removed — replaced by .registrar-page-root, .registrar-table-container,
  // .registrar-table-content CSS classes with data-breakpoint attribute
  // for responsive font-size / padding / border-radius variants.

  // Decomp 4: data-loading functions extracted to useRegistrarData hook.
  const {
    doctors,
    services,
    dynamicDepartments,
    loadIntegratedData,
    enrichAppointmentsWithPatientData,
  } = useRegistrarData();

  // ──────────────────────────────────────────────────────────────────────
  // PR-UI-13-3 (Decomp 10): dialog + wizard state consolidated into
  // useReducer state machines — useRegistrarDialogs (print/cancel/payment/
  // preview/force-majeure/context-menu/reschedule/payment-manager slices;
  // original reset shapes preserved) and useRegistrarWizard (open/editMode/
  // initialData + completion flow). Setter-compatible shims keep the exact
  // original call shapes for WelcomeView, QueueView, hotkeys and JSX.
  // ──────────────────────────────────────────────────────────────────────
  // Ref indirection for the wizard completion flow (PR-UI-13-3):
  // useRegistrarWizard needs loadAppointments (owned by
  // useRegistrarWorklistData below), while the worklist hook needs the
  // wizard's showWizard flag — a cycle. The ref breaks it with identical
  // call-time semantics.
  const loadAppointmentsRef = useRef<(options?: unknown) => Promise<void> | void>(() => {});

  const {
    printDialog, setPrintDialog,
    cancelDialog, setCancelDialog,
    paymentDialog, setPaymentDialog,
    recordPreviewDialog, setRecordPreviewDialog,
    forceMajeureModal, setForceMajeureModal,
    contextMenu, setContextMenu,
    rescheduleDialog,
    openRescheduleDialog, closeRescheduleDialog,
    showPaymentManager, setShowPaymentManager,
  } = useRegistrarDialogs();

  const {
    showWizard, wizardEditMode, wizardInitialData,
    isProcessing, setIsProcessing,
    setShowWizard, setWizardEditMode, setWizardInitialData,
    // NOTE: openWizardForCreate/openWizardForEdit/closeWizard helpers exist on
    // the hook; the panel keeps the original three-setter sequences at call
    // sites (contract-pinned shapes, identical semantics).
    handleWizardComplete,
  } = useRegistrarWizard({
    setPaymentDialog,
    setPrintDialog,
    // Ref indirection breaks the loadAppointments↔showWizard wiring cycle.
    // Behaviorally identical: React events fire against the latest committed
    // render, so ref.current at call time IS the closure the original inline
    // onComplete captured.
    loadAppointmentsRef,
    loadIntegratedData,
    tI18n,
  });

  // Legacy aliases: the consolidated reschedule slice { open, data } replaces
  // the former separate showSlotsModal / rescheduleData pair. The open action
  // is openRescheduleDialog(row) (former setRescheduleData(row) +
  // setShowSlotsModal(true)); the data-only setter shim handles the legacy
  // clear-on-success sequence.
  const showSlotsModal = rescheduleDialog.open;
  const rescheduleData = rescheduleDialog.data;
  // Hotkeys adapter: useRegistrarHotkeys only ever calls setShowSlotsModal(false)
  // (Esc closes the dialog); opening requires row data and goes through
  // openRescheduleDialog. Adapter preserves the hook's typed contract.
  const setShowSlotsModal = useCallback((show: boolean) => {
    if (!show) closeRescheduleDialog();
  }, [closeRescheduleDialog]);

  const anyDialogOpenRef = useRef(false);
  anyDialogOpenRef.current = Boolean(
    paymentDialog.open ||
    cancelDialog.open ||
    printDialog.open ||
    recordPreviewDialog.open ||
    contextMenu.open ||
    forceMajeureModal.open ||
    rescheduleDialog.open ||
    showPaymentManager
  );

  // ──────────────────────────────────────────────────────────────────────
  // PR-UI-13-1 (Decomp 8): worklist data lifecycle — appointments fetching,
  // reducer state machine (appointments / dataSource / loading / pagination)
  // and the full refresh lifecycle (initial load, queueUpdated WebSocket
  // listener, departments:updated listener, 30s auto-refresh with 429
  // cooldown + WS-freshness skip, calendar date change).
  // anyDialogOpenRef mirrors the original stale-closure semantics: dialog
  // flags were intentionally NOT in the auto-refresh effect deps; only
  // showWizard was. The ref is read at effect-run time, exactly like the
  // original closure read them.
  // ──────────────────────────────────────────────────────────────────────

  const {
    appointments,
    setAppointments,
    dataSource,
    appointmentsLoading,
    paginationInfo,
    loadAppointments,
    loadMoreAppointments,
  } = useRegistrarWorklistData({
    searchParams,
    activeTab,
    showCalendar,
    historyDate,
    showWizard,
    anyDialogOpenRef,
    enrichAppointmentsWithPatientData,
    loadIntegratedData,
    tI18n,
  });
  loadAppointmentsRef.current = loadAppointments;


  // Decomp 3: reschedule helpers extracted to useRegistrarReschedule hook.
  // PR-UI-13-1: wired to the worklist hook's setAppointments shim
  // (functional-updater API preserved).
  const {
    resolveRescheduleVisitId,
    removeRescheduledAppointmentFromView,
  } = useRegistrarReschedule({ setAppointments: setAppointments as unknown as (updater: (prev: Record<string, unknown>[]) => Record<string, unknown>[]) => void });

  // Синхронизация tempDateInput с historyDate при открытии календаря
  useEffect(() => {
    if (showCalendar) {
      setTempDateInput(historyDate);
    }
  }, [showCalendar, historyDate]);

  // UX Audit R-1.3: debounce 1000ms удалён.
  // Раньше: setTimeout 1s + onBlur дублировали применение даты, создавая
  // «мёртвую» секунду без визуального отклика (Nielsen #2).
  // Теперь: дата применяется только через onBlur в WelcomeView (стандартный
  // паттерн для date-picker'ов) или через нативный onChange календаря.

  // Обработчик события из хедера для открытия мастера записи
  useEffect(() => {
    const handleOpenWizard = () => {
      setShowWizard(true);
    };

    window.addEventListener('openAppointmentWizard', handleOpenWizard);
    return () => {
      window.removeEventListener('openAppointmentWizard', handleOpenWizard);
    };
  }, [setShowWizard]);

  // P-008 companion: when the user clicks "Новая запись" from another page,
  // HeaderNew navigates to /registrar?action=new. Detect that query param on
  // mount / route change and auto-open the wizard, then clear the param so
  // a refresh does not re-trigger it.
  useEffect(() => {
    const action = searchParams.get('action');
    if (action === 'new' && !showWizard) {
      setShowWizard(true);
      // Clean the URL so a refresh or back-navigation does not re-open the wizard
      const next = new URLSearchParams(searchParams);
      next.delete('action');
      setSearchParams(next, { replace: true });
    }
    // setSearchParams is a stable identity from useSearchParams — React Router 6.3+
    // guarantees referential stability, so it is safe to omit from deps.
  }, [searchParams, showWizard, setShowWizard]); // eslint-disable-line react-hooks/exhaustive-deps

  // UX Audit Registrar #17: Keyboard shortcuts для продуктивности регистратора.
  // Ctrl+N — новая запись (открыть wizard)
  // Esc — закрыть wizard/dialogs (если открыт)
  // Не срабатывает когда фокус в input/textarea (чтобы не мешать вводу).
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Ctrl+N — новая запись
      if ((event.ctrlKey || event.metaKey) && event.key === 'n') {
        // Не срабатываем в input/textarea/select
        const tag = (event.target as HTMLElement | null)?.tagName?.toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
        event.preventDefault();
        if (!showWizard) {
          setWizardEditMode(false);
          setWizardInitialData(null);
          setShowWizard(true);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showWizard, setShowWizard, setWizardEditMode, setWizardInitialData]);

  // UX Audit R-1.7: lastQueueJoin polling (2s) удалён.
  // Раньше: setInterval(checkLastQueueJoin, 2000) проверял localStorage
  // каждые 2 секунды — 60 проверок в минуту, даже когда очередь не используется.
  // Теперь: обновление приходит через `queueUpdated` window-event listener
  // (строки ниже), который запускается WebSocket'ом ModernQueueManager.
  // Для fallback между вкладками можно использовать BroadcastChannel,
  // но polling localStorage — это неэффективный паттерн.

  // Функции для жесткого потока
  // Decomp 5: record action handlers extracted to useRegistrarActions hook.
  // openRecordPreview, openRecordEditor, handleContextMenuAction remain
  // inline because they are simple state setters (1-3 lines each).
  // R-33 fix: RU messages applied in useRegistrarActions hook.
  const {
    runRegistrarRecordAction,
    handleStartVisit,
    handlePayment,
    updateAppointmentStatus,
  } = useRegistrarActions({ appointments, loadAppointments });

  // QW-01 fix: handleBulkAction removed along with bulk-action UI.

  // ✅ ИСПОЛЬЗУЕМ useRef для хранения filteredAppointments, чтобы избежать ошибки "Cannot access before initialization"
  const filteredAppointmentsRef = useRef<Appointment[]>([]);

  // Горячие клавиши — extracted to useRegistrarHotkeys hook (Decomp 2)
  // Phase 2: navigate replaces setSearchParams for canonical routes
  useRegistrarHotkeys({
    setShowWizard,
    setShowSlotsModal,
    setActiveTab,
    navigate,
    showWizard,
    showSlotsModal,
    appointments,
  });

  // Мемоизированные счетчики и индикаторы по отделам
  // PR-UI-13-2: computation extracted to registrarWorklistRows.ts
  // (computeDepartmentStats) — pure function, same deps.
  const departmentStats = useMemo(
    () => computeDepartmentStats(appointments, todayStr, queueProfiles),
    [appointments, todayStr, queueProfiles],
  );
  // 🎨 PRESENTATION-ONLY: view-model computation extracted to
  // registrarWorklistRows.ts (PR-UI-13-2) — pure functions:
  // computeRegistrarWorklistRows (tab/status/search filtering, patient
  // aggregation for the all-departments tab, presentation-only
  // ordering) + registrarServiceFilter.filterServicesByDepartment.
  // Deps triggers identical to the original memo (services replaces the
  // filterServicesByDepartment callback that changed identity on
  // services change; fallbackPatientLabel is computed inside the memo
  // body exactly like the original tI18n closure read).
  const filteredAppointments = useMemo(() => computeRegistrarWorklistRows({
    appointments,
    activeTab,
    statusFilter,
    searchQuery,
    queueProfiles,
    services,
    fallbackPatientLabel: tI18n('registrarPanel.rp_unknown_patient'),
  }), [appointments, activeTab, statusFilter, searchQuery, queueProfiles, services]);
  // ✅ Сохраняем filteredAppointments в ref для использования в handleKeyDown
  filteredAppointmentsRef.current = filteredAppointments as Appointment[];

  // Мемоизированный компонент индикатора источника данных (для всех вкладок)
  // UX Audit Registrar #14: DataSourceIndicator, generateCSV, downloadCSV
  // extracted to ./registrar/DataSourceIndicator.jsx and ./registrar/registrarCsv.js.

  // Обработчик действий контекстного меню

  const openRecordPreview = useCallback((row: unknown) => {
    setRecordPreviewDialog({ open: true, row: row as Appointment });
  }, [setRecordPreviewDialog]);

  const openRecordEditor = useCallback((row: unknown) => {
    const appt = row as Appointment;
    if (isMultiRecordAggregateRow(appt as Record<string, unknown>)) {
      logger.info('[RegistrarPanel] Opening edit wizard for aggregate all-departments row', {
        patient: appt?.patient_fio || appt?.patient_name,
        groupedRecords: appt?.grouped_records?.length || 0,
        recordRefs: appt?.grouped_record_refs?.length || 0,
        aggregatedIds: appt?.aggregated_ids?.length || 0
      });
    }

    // UX Audit R-3.6: убрано логирование patient_fio (PII leak).
    logger.info('[RegistrarPanel] Opening edit wizard for appointment:', appt?.id);
    setWizardEditMode(true);
    setWizardInitialData(appt as Record<string, unknown>);
    setShowWizard(true);
  }, [setWizardEditMode, setWizardInitialData, setShowWizard]);

  // PR-UI-13-4: table row-action routing extracted from the EAT JSX prop into
  // a panel-level callback (verbatim switch body) — passed to WorklistView.
  const handleTableAction = useCallback(async (action: string, row: Record<string, unknown>, event?: unknown) => {
    switch (action) {
        case 'view':
          logger.info('Просмотр записи:', row);
          openRecordPreview(row as unknown as Appointment);
          break;
        case 'edit':
          // UX Audit R-3.6: убрано логирование patient_fio (PII leak).
          logger.info('[RegistrarPanel] Открытие мастера редактирования для appointment:', row.id);
          openRecordEditor(row);
          break;
        case 'payment':
          logger.info('Открытие модального окна оплаты для записи:', row);
          setPaymentDialog({ open: true, row: row as unknown as Appointment, paid: false, source: 'table' });
          break;
        case 'in_cabinet': {
          // UX Audit Registrar #2: window.confirm() → useConfirm hook.
          // Раньше: if (!window.confirm(`Отправить пациента "..." в кабинет?`)) break;
          // Теперь: macOS-style ConfirmDialog через useConfirm.
          const inCabinetName = row.patient_fio || row.patient_name || '';
          const inCabinetOk = await confirm({
            title: tI18n('registrar.send_to_cabinet_title'),
            message: tI18n('registrar.send_to_cabinet_message', { name: inCabinetName }),
            confirmLabel: tI18n('registrar.send_to_cabinet_confirm'),
            cancelLabel: tI18n('registrar.cancel'),
            intent: 'primary',
          });
          if (!inCabinetOk) break;
          logger.info('Отправка пациента в кабинет:', row);
          updateAppointmentStatus(row.id, 'in_cabinet', '', row as Record<string, unknown>);
          break;
        }
        case 'call':
          logger.info('Вызов пациента:', row);
          handleStartVisit(row as Record<string, unknown>);
          break;
        case 'complete': {
          // UX Audit Registrar #2: window.confirm() → useConfirm hook.
          const completeName = row.patient_fio || row.patient_name || '';
          const completeOk = await confirm({
            title: tI18n('registrar.complete_visit_title'),
            message: tI18n('registrar.complete_visit_message', { name: completeName }),
            confirmLabel: tI18n('registrar.complete_visit_confirm'),
            cancelLabel: tI18n('registrar.cancel'),
            intent: 'primary',
          });
          if (!completeOk) break;
          logger.info('Завершение приёма:', row);
          updateAppointmentStatus(row.id, 'done', '', row as Record<string, unknown>);
          break;
        }
        case 'print':
          logger.info('Печать талона:', row);
          setPrintDialog({ open: true, type: 'ticket', data: row as Record<string, unknown> });
          break;
        // UX Audit Registrar #4: cancel и reschedule теперь доступны
        // как inline кнопки, а не только через context menu.
        case 'reschedule':
          // PR-UI-13-3: former setRescheduleData(row) + setShowSlotsModal(true)
          // consolidated into one reducer action.
          openRescheduleDialog(row as Record<string, unknown>);
          break;
        case 'cancel':
          setCancelDialog({ open: true, row: row as unknown as Appointment, reason: '' });
          break;
        case 'more':{
            // Показать контекстное меню с дополнительными действиями
            const evt = event as { target?: HTMLElement; clientX?: number; clientY?: number } | undefined;
            const rect = evt?.target?.getBoundingClientRect();
            setContextMenu({
              open: true,
              row,
              position: {
                x: rect?.right || evt?.clientX || 0,
                y: rect?.top || evt?.clientY || 0
              }
            });
            break;
          }
        default:
          break;
    }
  }, [openRecordPreview, openRecordEditor, confirm, updateAppointmentStatus, handleStartVisit, setPaymentDialog, setPrintDialog, setCancelDialog, setContextMenu, openRescheduleDialog]);

  const handleContextMenuAction = useCallback(async (action: string, row: Appointment) => {
    switch (action) {
      case 'view':
        openRecordPreview(row as unknown as Appointment);
        break;
      case 'edit':
        openRecordEditor(row);
        logger.info('Редактирование записи:', row);
        break;
      case 'in_cabinet': {
        // UX Audit R-1.2: добавлен confirm для критичных действий в context menu.
        // Раньше: handleContextMenuAction вызывал updateAppointmentStatus напрямую,
        // без подтверждения. В то же время inline onActionClick в таблице требовал
        // confirm. Это нарушение Nielsen #4 (consistency) + #5 (error prevention).
        const inCabinetName = row.patient_fio || row.patient_name || '';
        const inCabinetOk = await confirm({
          title: tI18n('registrar.send_to_cabinet_title'),
          message: tI18n('registrar.send_to_cabinet_message', { name: inCabinetName }),
          confirmLabel: tI18n('registrar.send_to_cabinet_confirm'),
          cancelLabel: tI18n('registrar.cancel'),
          intent: 'primary',
        });
        if (!inCabinetOk) break;
        await updateAppointmentStatus(row.id, 'in_cabinet', '', row as Record<string, unknown>);
        notify.success(tI18n('registrar.sent_to_cabinet'));
        break;
      }
      case 'call':
        await handleStartVisit(row as Record<string, unknown>);
        break;
      case 'complete': {
        // UX Audit R-1.2: confirm для завершения приёма в context menu.
        const completeName = row.patient_fio || row.patient_name || '';
        const completeOk = await confirm({
          title: tI18n('registrar.complete_visit_title'),
          message: tI18n('registrar.complete_visit_message', { name: completeName }),
          confirmLabel: tI18n('registrar.complete_visit_confirm'),
          cancelLabel: tI18n('registrar.cancel'),
          intent: 'primary',
        });
        if (!completeOk) break;
        await updateAppointmentStatus(row.id, 'done', '', row as Record<string, unknown>);
        notify.success(tI18n('registrar.visit_completed'));
        break;
      }
      case 'payment':
        setPaymentDialog({ open: true, row: row as unknown as Appointment, paid: false, source: 'context' });
        break;
      case 'print':
        setPrintDialog({ open: true, type: 'ticket', data: row as Record<string, unknown> });
        break;
      case 'reschedule':
        // PR-UI-13-3: former setRescheduleData(row) + setShowSlotsModal(true)
        // consolidated into one reducer action.
        openRescheduleDialog(row as Record<string, unknown>);
        break;
      case 'cancel':
        setCancelDialog({ open: true, row: row as unknown as Appointment, reason: '' });
        break;
      case 'call_patient':
        if (row.patient_phone) {
          // R-24 fix: санитизация tel: URL — оставляем только digits и +.
          // Предотвращает injection через специальные символы в phone field.
          const sanitizedPhone = String(row.patient_phone).replace(/[^\d+]/g, '');
          // UX Audit R-2.5: используем нативный <a> anchor вместо window.open().
          // window.open() может блокироваться браузером как pop-up, т.к. этот
          // handler вызывается не из прямого user-gesture (через context menu).
          // Нативный anchor — стандартный паттерн для tel: ссылок.
          const link = document.createElement('a');
          link.href = `tel:${sanitizedPhone}`;
          link.style.display = 'none';
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        }
        break;
      case 'force_majeure':
        // Открываем модальное окно форс-мажора для специалиста
        setForceMajeureModal({
          open: true,
          specialistId: row.doctor_id || row.specialist_id || null,
          specialistName: row.doctor_name || row.specialist_name || tI18n('registrarPanel.rp_all_specialists')
        });
        break;
      default:
        logger.info('Неизвестное действие:', action);
        break;
    }
  }, [updateAppointmentStatus, handleStartVisit, openRecordPreview, openRecordEditor, confirm, setPaymentDialog, setPrintDialog, setCancelDialog, setForceMajeureModal, openRescheduleDialog]);

  return (
    <div
      className="registrar-page-root"
      data-breakpoint={isMobile ? 'mobile' : isTablet ? 'tablet' : 'desktop'}
      role="main"
      aria-label={tI18n('registrarPanel.rp_aria_panel')}>
      {/* Skip to content link for screen readers */}
      <a
        href="#main-content"
        className="registrar-hidden-visually"
        onFocus={(e: React.FocusEvent<HTMLElement>) => {
          e.currentTarget.style.left = '0';
        }}
        onBlur={(e: React.FocusEvent<HTMLElement>) => {
          e.currentTarget.style.left = '-9999px';
        }}>

        {tI18n('registrarPanel.rp_skip_to_content')}
      </a>

      {/* R-03 fix: breadcrumb навигация для wayfinding.
          Показывает текущую view, выбранное отделение, поисковый запрос. */}
      <nav aria-label={tI18n('registrarPanel.rp_aria_breadcrumb_nav')} className="registrar-breadcrumb-nav">
        <button
          type="button"
          onClick={() => {
            // Phase 2: navigate to canonical path (replaces legacy ?view=welcome)
            const p = new URLSearchParams(searchParams);
            p.delete('q');
            p.delete('status');
            p.delete('view');
            p.delete('tab');
            const qs = p.toString();
            navigate(qs ? `/registrar/welcome?${qs}` : '/registrar/welcome', { replace: true });
          }}
          className="registrar-breadcrumb-link"
        >
          {tI18n('registrarPanel.rp_breadcrumb_root')}
        </button>
        {activeTab && (
          <>
            <Icon name="chevron.right" size="small" className="registrar-breadcrumb-separator" aria-hidden="true" />
            <span>{queueProfiles.find(p => p.key === activeTab)?.title || activeTab}</span>
          </>
        )}
        {searchQuery && (
          <>
            <Icon name="chevron.right" size="small" className="registrar-breadcrumb-separator" aria-hidden="true" />
            <span>{tI18n('registrarPanel.rp_breadcrumb_search', { query: searchQuery })}</span>
          </>
        )}
        {showWizard && (
          <>
            <Icon name="chevron.right" size="small" className="registrar-breadcrumb-separator" aria-hidden="true" />
            <span>{wizardEditMode ? tI18n('registrarPanel.rp_breadcrumb_edit') : tI18n('registrarPanel.rp_breadcrumb_new')}</span>
          </>
        )}
      </nav>

      {/* Современные вкладки */}
      {(!currentView || currentView !== 'welcome' && currentView !== 'queue') &&
      <div className="registrar-tabs-wrapper">
          <ModernTabs
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onProfilesLoaded={handleProfilesLoaded} // ⭐ SSOT: Store profiles for filtering
          departmentStats={departmentStats}
          theme={theme}
          language={legacyLanguage}
          dynamicDepartments={dynamicDepartments} />

        </div>
      }

      {/* Старые вкладки удалены - используется ModernTabs компонент */}

      {/* Основной контент без отступа сверху */}
      <div className="registrar-overflow-hidden">
        {/* Экран приветствия — extracted to WelcomeView component (Decomp 6b) */}
        {currentView === 'welcome' && (
          <WelcomeView
            t={t}
            language={legacyLanguage}
            theme={theme}
            textColor={textColor}
            appointments={appointments as Record<string, unknown>[]}
            departmentStats={departmentStats}
            dataSource={dataSource}
            appointmentsLoading={appointmentsLoading}
            filteredAppointments={filteredAppointments}
            services={services}
            activeTab={activeTab}
            historyDate={historyDate}
            showCalendar={showCalendar}
            tempDateInput={tempDateInput}
            loadAppointments={loadAppointments}
            setShowWizard={setShowWizard}
            setWizardEditMode={setWizardEditMode}
            setWizardInitialData={setWizardInitialData}
            setShowPaymentManager={setShowPaymentManager}
            setHistoryDate={setHistoryDate}
            setShowCalendar={setShowCalendar}
            setTempDateInput={setTempDateInput}
            setSearchParams={setSearchParams}
            navigate={navigate}
            setPaymentDialog={setPaymentDialog as unknown as React.Dispatch<React.SetStateAction<{ open: boolean; row: unknown; paid: boolean; source: unknown }>>}
            setPrintDialog={setPrintDialog as unknown as React.Dispatch<React.SetStateAction<{ open: boolean; type: string; data: unknown }>>}
            setContextMenu={setContextMenu as unknown as React.Dispatch<React.SetStateAction<{ open: boolean; row: unknown; position: { x: number; y: number } }>>}
            openRecordPreview={openRecordPreview}
            openRecordEditor={openRecordEditor}
            updateAppointmentStatus={updateAppointmentStatus as unknown as (id: unknown, status: string, note: string, row?: unknown) => void | Promise<void>}
            handleStartVisit={handleStartVisit as unknown as (row: unknown) => void | Promise<void>}
            generateCSV={generateCSV as unknown as (...args: unknown[]) => unknown}
            downloadCSV={downloadCSV as unknown as (...args: unknown[]) => void}
            DataSourceIndicator={() => (
              <DataSourceIndicator
                dataSource={dataSource}
                count={appointments.length}
                paginationInfo={paginationInfo}
                onRetry={loadAppointments}
              />
            )}
          />
        )}

        {/* Онлайн-очередь — extracted to QueueView component (Decomp 6a) */}
        {currentView === 'queue' &&
          <QueueView
            searchParams={searchParams}
            setSearchParams={setSearchParams}
            loadAppointments={loadAppointments}
            getSpacing={getSpacing}
            getFontSize={getFontSize}
            getColor={getColor}
            language={legacyLanguage}
            theme={theme}
            doctors={doctors}
          />
        }


        {/* Основная панель с записями — extracted to WorklistView (PR-UI-13-4) */}
        {(!currentView || currentView !== 'welcome' && currentView !== 'queue') &&
          <WorklistView
            activeTab={activeTab}
            currentWorklistLabel={currentWorklistLabel}
            statusFilterLabel={statusFilterLabel}
            showCalendar={showCalendar}
            historyDate={historyDate}
            language={language}
            legacyLanguage={legacyLanguage}
            isMobile={isMobile}
            theme={theme}
            services={services}
            filteredAppointments={filteredAppointments}
            appointmentsLoading={appointmentsLoading}
            dataSource={dataSource}
            paginationInfo={paginationInfo}
            onActionClick={handleTableAction}
            loadMoreAppointments={loadMoreAppointments}
            onNewAppointment={() => {
              setWizardEditMode(false);
              setWizardInitialData(null);
              setShowWizard(true);
            }}
            onEmptyStateCta={() => setShowWizard(true)}
            tI18n={tI18n}
          />
        }
      </div> {/* Закрытие скроллируемого контента */}

      {/* Мастер создания записи */}

      {/* Современные диалоги */}
{/* Decomp 10 (PR-UI-13-3): record preview extracted to
    registrar/views/RecordPreviewDialog.tsx (state stays in
    useRegistrarDialogs.recordPreviewDialog). */}
      <RecordPreview
        isOpen={recordPreviewDialog.open}
        row={recordPreviewDialog.row}
        onClose={() => setRecordPreviewDialog({ open: false, row: null })}
        onEdit={(row) => {
          setRecordPreviewDialog({ open: false, row: null });
          openRecordEditor(row);
        }}
        tI18n={tI18n}
      />

      <CancelDialog
        isOpen={cancelDialog.open}
        onClose={() => setCancelDialog({ open: false, row: null, reason: '' })}
        appointment={cancelDialog.row}
        onCancel={async (appointmentId, reason) => {
          try {
            const data = appointmentId === cancelDialog.row?.id
              ? cancelDialog.row
              : appointments.find((a) => a.id === appointmentId);
            const result = await runRegistrarRecordAction(data as Record<string, unknown>, 'cancel', { reason });
            if (!result) return;
            if (!result.success) {
              const successCount = Number(result.success_count || 0);
              const failedCount = Number(result.failed_count || 0);
              if (successCount === 0) {
                throw new Error(result.results?.find((item: { success?: boolean; error?: string }) => !item.success)?.error || 'cancel_failed');
              }
              notify.warning('Cancelled ' + successCount + '; failed ' + failedCount);
            }
            await loadAppointments({ silent: true, source: 'cancel_complete' } as Record<string, unknown>);
          } catch (error: unknown) {
            logger.error('RegistrarPanel: cancellation failed:', error);
            notify.error(getErrorMessage(error, 'Could not cancel record. Check connection and try again.'));
            throw error;
          }
        }} />


      <PaymentDialog
        isOpen={paymentDialog.open}
        onClose={() => setPaymentDialog({ open: false, row: null, paid: false, source: null })}
        appointment={paymentDialog.row}
        onPaymentSuccess={async (paymentData) => {
          // ✅ ИСПРАВЛЕНО: используем реальный API вызов через handlePayment
          const appointment = paymentDialog.row;
          if (appointment) {
            const updated = await handlePayment(appointment as Record<string, unknown>, paymentData as { amount?: number | null; method?: string | null } | null);
            if (updated) {
              // Canonical state is refreshed by handlePayment via loadAppointments.
              logger.info('PaymentDialog: Оплата успешна, данные обновлены:', updated);
            }
          }
        }}
        onPrintTicket={(appointment: unknown) => {
          const rowObj = (paymentDialog.row && typeof paymentDialog.row === 'object' ? paymentDialog.row : {}) as Record<string, unknown>;
          const apptObj = (appointment && typeof appointment === 'object' ? appointment : {}) as Record<string, unknown>;
          const printSource = {
            ...rowObj,
            ...apptObj
          };
          // UX Audit: закрываем PaymentDialog при открытии PrintDialog.
          setPaymentDialog({ open: false, row: null, paid: false, source: null });
          setPrintDialog({
            open: true,
            type: 'ticket',
            data: printSource
          });
        }} />


      {/* Модальное окно редактирования пациента */}
      {/* ✨ ЗАКОММЕНТИРОВАНО: Теперь используется AppointmentWizardV2 для редактирования */}
      {/*
           {editPatientModal.open && (
            <EditPatientModal
              isOpen={editPatientModal.open}
              onClose={() => setEditPatientModal({ open: false, patient: null })}
              patient={editPatientModal.patient}
              onSave={async () => {
                // Обновляем список записей после сохранения
                logger.info('[RegistrarPanel] EditPatientModal: onSave вызван, обновляем список');
                await loadAppointments({ source: 'edit_patient_save', silent: false });
              }}
              theme={{ isDark, getColor, getSpacing, getFontSize }}
            />
           )}
           */}

      <PrintDialog
        isOpen={printDialog.open}
        onClose={() => setPrintDialog({ open: false, type: 'ticket', data: null })}
        documentType={printDialog.type || 'ticket'}
        documentData={printDialog.data}
        onPrint={async (data, printerId) => {
          logger.info('Printing:', { printerId, documentType: printDialog.type, data });

          if (printDialog.type !== 'ticket') {
            throw new Error(tI18n('registrarPanel.rp_err_unsupported_doc_type', { docType: printDialog.type }));
          }

          const result = await printPanelTicketInBrowserAsync((data ?? {}) as Record<string, unknown>);
          if (result?.opened && result?.success) {
            return;
          }

          if (!result?.opened) {
            throw new Error(tI18n('registrarPanel.rp_err_print_blocked'));
          }

          throw result?.error || new Error(tI18n('registrarPanel.rp_err_print_prepare'));
        }} />


      {/* ✅ Используется только новый мастер (V2) */}
      {/* ✅ PR-UI-13 (plan item 4): локальный ErrorBoundary вокруг wizard —
          сбой в мастере записи не должен ронять весь рабочий стол регистратора;
          fallback UI отрендерится внутри контейнера панели. */}
      <ErrorBoundary
        onError={(error, errorInfo) => {
          logger.error('[RegistrarPanel] AppointmentWizardV2 crashed:', error, errorInfo);
        }}
        theme={{ theme }}>
        <AppointmentWizardV2
        isOpen={showWizard}
        editMode={wizardEditMode} // ✨ НОВОЕ: Передаем режим
        initialData={wizardInitialData as unknown as null} // ✨ НОВОЕ: Передаем данные
        activeTab={activeTab as unknown as null} // ✅ ПЕРЕДАЕМ activeTab для фильтрации услуг
        onClose={() => {
          logger.info('AppointmentWizardV2 closing');
          setShowWizard(false);
          setWizardEditMode(false); // ✨ Сброс режима
          setWizardInitialData(null); // ✨ Сброс данных
        }}
        isProcessing={isProcessing}
        setIsProcessing={setIsProcessing}
        // PR-UI-13-3: completion flow extracted to useRegistrarWizard
        // (handleWizardComplete — verbatim port: optimistic close + notify +
        // payment/print handoff, then background reload with one silent retry).
        onComplete={handleWizardComplete} />
      </ErrorBoundary>


      {/* Старые диалоги удалены - используются современные компоненты CancelDialog, PaymentDialog, PrintDialog */}
      {/* Встроенное модальное окно оплаты удалено - используется PaymentDialog компонент */}
      {/* Встроенный мастер удален - используется AppointmentWizard компонент */}

{/* Decomp 10 (PR-UI-13-3): reschedule slots dialog extracted to
      registrar/views/RescheduleSlotsDialog.tsx (QW-02 inline date picker,
      R-27 optional time, R-43 confirms — ported verbatim; open/close +
      payload state in useRegistrarDialogs.rescheduleDialog, form fields
      owned by the component). */}
      <RescheduleSlots
        isOpen={showSlotsModal}
        rescheduleData={rescheduleData}
        onClose={closeRescheduleDialog}
        confirm={confirm}
        resolveRescheduleVisitId={resolveRescheduleVisitId}
        removeRescheduledAppointmentFromView={removeRescheduledAppointmentFromView}
        loadAppointments={loadAppointments}
        tI18n={tI18n}
      />

      {/* Контекстное меню */}
      {contextMenu.open && contextMenu.row &&
      <AppointmentContextMenu
        row={contextMenu.row}
        position={contextMenu.position}
        theme={theme}
        onClose={() => setContextMenu({ open: false, row: null, position: { x: 0, y: 0 } })}
        onAction={handleContextMenuAction} />

      }

      {/* Модуль оплаты */}
      <PaymentManager
        isOpen={showPaymentManager}
        onClose={(result: unknown) => {
          setShowPaymentManager(false);
          if ((result as Record<string, unknown>)?.success) {
            // Обновляем данные после успешной оплаты
            loadAppointments();
            loadIntegratedData();
          }
        }} />


      {/* ✅ Форс-мажор модальное окно */}
      <ForceMajeureModal
        isOpen={forceMajeureModal.open}
        onClose={() => setForceMajeureModal({ open: false, specialistId: null, specialistName: '' })}
        specialistId={forceMajeureModal.specialistId}
        specialistName={forceMajeureModal.specialistName}
        onSuccess={(action, result) => {
          logger.info('[RegistrarPanel] Force majeure action completed:', action, result);
          notify.success(action === 'transfer' ? tI18n('registrarPanel.rp_notify_force_majeure_transfer') : tI18n('registrarPanel.rp_notify_force_majeure_cancel'));
          loadAppointments({ source: 'force_majeure' });
        }} />

      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}

    </div>);

};

export default RegistrarPanel;
