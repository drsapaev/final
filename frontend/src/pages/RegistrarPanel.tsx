import { useState, useEffect, useCallback, useRef, useMemo, memo } from 'react';
import type { CSSProperties } from 'react';
// PR-UI-13-5: useSearchParams/useLocation/useNavigate moved to
// useRegistrarRouting (routing slice extraction).
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
// PR-UI-13-5: routing slice (URL state + deep-link effects) extracted to
// useRegistrarRouting hook.
import { useRegistrarRouting } from './registrar/useRegistrarRouting';
// PR-UI-13-5: row-action routing (table + context menu) extracted to
// useRegistrarRowActions hook.
import { useRegistrarRowActions } from './registrar/useRegistrarRowActions';

// Decomp step 1: helpers extracted to ./registrar/registrarHelpers.js
// PR-UI-13-5: isMultiRecordAggregateRow moved to useRegistrarRowActions
// (openRecordEditor extraction).
import {
  // PR-UI-13-3: buildPostWizardPaymentRow moved to useRegistrarWizard;
  // normalizePatientGender + formatPreviewList moved to RecordPreviewDialog.
  REGISTRAR_TAB_LABEL_KEYS,
  REGISTRAR_STATUS_LABEL_KEYS,
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
// PR-UI-13-5: getPatient import moved to useRegistrarRouting (patientId
// deep-link effect extraction — no other panel call-sites existed).
// ⭐ BATCH API: Для атомарных операций с записями пациента (см. BATCH_UPDATE_ARCHITECTURE.md)


// ✅ Форс-мажор модальное окно
import ForceMajeureModal from '../components/registrar/ForceMajeureModal';
// UX Audit Registrar #14: extracted DataSourceIndicator and CSV utilities.
import DataSourceIndicator from './registrar/DataSourceIndicator';
import { generateCSV, downloadCSV } from './registrar/registrarCsv';


// PR-UI-13-2: QueueProfileItem moved to ./registrar/registrarWorklistRows.ts

const RegistrarPanel = () => {
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw;
  // Рендер компонента (debug отключен)
  // Адаптивные хуки
  const { isMobile, isTablet } = useBreakpoint();

  // Основные состояния
  // PR-UI-13-5: routing slice extracted to useRegistrarRouting (verbatim
  // port): activeTab + ?dept= URL sync (R-02), canonical path-derived
  // currentView (Phase 3), legacy ?view= redirect (Phase 2), searchQuery /
  // statusFilter memos, patientId deep-link auto-search effect.
  const {
    searchParams,
    setSearchParams,
    navigate,
    activeTab,
    setActiveTab,
    currentView,
    searchQuery,
    statusFilter,
  } = useRegistrarRouting();
  const todayStr = getLocalDateString();

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
  // PR-UI-13-5: row-action routing extracted to useRegistrarRowActions
  // (verbatim port): openRecordPreview / openRecordEditor /
  // handleTableAction (EAT onActionClick router, incl. confirm-gated
  // in_cabinet/complete branches) / handleContextMenuAction (context-menu
  // router + call_patient tel: link + force-majeure modal).
  const {
    openRecordPreview,
    openRecordEditor,
    handleTableAction,
    handleContextMenuAction,
  } = useRegistrarRowActions({
    confirm,
    tI18n,
    updateAppointmentStatus,
    handleStartVisit,
    setRecordPreviewDialog,
    setPaymentDialog,
    setPrintDialog,
    setCancelDialog,
    setContextMenu,
    setForceMajeureModal,
    openRescheduleDialog,
    setWizardEditMode,
    setWizardInitialData,
    setShowWizard,
  });

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
          // Codex P2-1 (PR-UI-13-4): reset the wizard-open state from the crash
          // path — otherwise showWizard stays true while the boundary holds
          // hasError, the auto-refresh effect keeps treating the wizard as an
          // open dialog, and the wizard cannot be reopened normally.
          setWizardEditMode(false);
          setWizardInitialData(null);
          setShowWizard(false);
        }}
        theme={{
          // Codex P2-2 (PR-UI-13-4): ErrorBoundary's fallback styles read the
          // theme helper functions — passing only the mode string left the
          // recovery screen with unstyled raw fallback values.
          theme,
          getColor,
          getSpacing,
          getFontSize,
        }}>
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
