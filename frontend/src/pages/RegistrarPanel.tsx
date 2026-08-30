import { useState, useCallback, useRef, useMemo } from 'react';
import ModernTabs from '../components/navigation/ModernTabs';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import { useTheme } from '../contexts/ThemeContext';
import '../components/ui/animations.css';
import '../styles/responsive.css';
import '../styles/animations.css';
import '../styles/dark-theme-visibility-fix.css';
// DS-3: utility classes for common inline style patterns
import './registrar/registrar.css';
// P-013: shared ConfirmDialog hook (replaces window.confirm).
import { useConfirm } from '../components/common/ConfirmDialog';
// Unified i18n: single useTranslation for registrarPanel.* + registrar.* keys.
import { useTranslation } from '../i18n/useTranslation';
// Registrar domain modules (see the migration map below for the full trail).
import { useRegistrarHotkeys } from './registrar/useRegistrarHotkeys';
import { useRegistrarReschedule } from './registrar/useRegistrarReschedule';
import { useRegistrarData } from './registrar/useRegistrarData';
import { useRegistrarWorklistData } from './registrar/useRegistrarWorklistData';
import {
  computeDepartmentStats,
  computeRegistrarWorklistRows,
  type QueueProfileItem,
} from './registrar/registrarWorklistRows';
import { useRegistrarDialogs } from './registrar/useRegistrarDialogs';
import { useRegistrarWizard } from './registrar/useRegistrarWizard';
import WorklistView from './registrar/views/WorklistView';
import { useRegistrarNavigation } from './registrar/useRegistrarNavigation';
import { useRegistrarCalendar } from './registrar/useRegistrarCalendar';
import { useRegistrarRowActions } from './registrar/useRegistrarRowActions';
import RegistrarBreadcrumb from './registrar/views/RegistrarBreadcrumb';
import RegistrarDialogsLayer from './registrar/views/RegistrarDialogsLayer';
import { useRegistrarActions } from './registrar/useRegistrarActions';
import QueueView from './registrar/views/QueueView';
import WelcomeView from './registrar/views/WelcomeView';
// Migration map (PR-UI-13 decomp trail): queue adapter + data lifecycle →
// registrarQueueAdapter/useRegistrarWorklistData; view-model →
// registrarWorklistRows/registrarServiceFilter; dialogs + wizard state →
// useRegistrarDialogs/useRegistrarWizard; row actions → useRegistrarRowActions;
// navigation + launch triggers → useRegistrarNavigation; calendar →
// useRegistrarCalendar; worklist/breadcrumb/dialogs JSX → views/*; helpers →
// registrarHelpers; reference data → useRegistrarData.
import {
  REGISTRAR_TAB_LABEL_KEYS,
  REGISTRAR_STATUS_LABEL_KEYS,
} from './registrar/registrarHelpers';
import { getLocalDateString } from '../utils/dateUtils';
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
  // ✅ ДИНАМИЧЕСКИЕ ОТДЕЛЕНИЯ: PR-UI-13-4 — reference-data state (doctors,
  // services, dynamicDepartments) is owned by useRegistrarData below.

  const todayStr = getLocalDateString();
  // PR-UI-13-5 (Decomp 15): calendar slice (showCalendar/historyDate/tempDateInput).
  const {
    showCalendar, setShowCalendar,
    historyDate, setHistoryDate,
    tempDateInput, setTempDateInput,
  } = useRegistrarCalendar();

  // ⭐ SSOT: Queue profiles loaded from API (via ModernTabs)
  // Used for filtering entries by queue_tags instead of hardcoded mapping
  const [queueProfiles, setQueueProfiles] = useState<QueueProfileItem[]>([]);

  // PR-UI-09c-4: onProfilesLoaded MUST be referentially stable — an unstable
  // identity caused an infinite profiles-fetch refetch loop (CI flake root cause).
  const handleProfilesLoaded = useCallback((profiles: unknown[]) => {
    setQueueProfiles(profiles as QueueProfileItem[]);
  }, []);

  // PR-UI-13-5 (Decomp 15): calendar date-selection slice → useRegistrarCalendar.
  // Unified i18n: registrarPanel.* (flat UI keys) + registrar.* (confirm/notify).
  const { t: tI18n, language } = useTranslation();
  const legacyLanguage = language?.startsWith('uz') ? 'uz' : language?.split('-')[0] || 'ru';
  // Compat wrapper: WelcomeView/QueueView call t('key') for registrarPanel.* flat keys.
  const t = (key: string) => {
    if (key.includes('.')) return tI18n(key);
    return tI18n('registrarPanel.' + key);
  };
  const { theme, getSpacing, getFontSize, getColor } = useTheme();
  // Адаптивные цвета из централизованной системы темизации
  // DS-2 fix: replaced --color-* variables with --mac-* canonical tokens
  const textColor = 'var(--mac-text-primary)';

  // Reference data (doctors/services/departments) — owned by useRegistrarData.
  const {
    doctors,
    services,
    dynamicDepartments,
    loadIntegratedData,
    enrichAppointmentsWithPatientData,
  } = useRegistrarData();

  // Dialog + wizard state machines (PR-UI-13-3). loadAppointmentsRef breaks
  // the wizard↔worklist wiring cycle with identical call-time semantics.
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
// Decomp 12 (PR-UI-13-5): navigation/URL state + wizard launch triggers
// → useRegistrarNavigation (verbatim port).
  const {
    searchParams,
    setSearchParams,
    navigate,
    activeTab,
    setActiveTab,
    currentView,
    searchQuery,
    statusFilter,
  } = useRegistrarNavigation({
    showWizard,
    setShowWizard,
    setWizardEditMode,
    setWizardInitialData,
  });

  // Worklist header labels (moved after nav wiring — PR-UI-13-5).
  const currentWorklistLabel = tI18n('registrarPanel.' + (REGISTRAR_TAB_LABEL_KEYS[activeTab as keyof typeof REGISTRAR_TAB_LABEL_KEYS] || 'tabs_appointments'));
  const statusFilterLabel = statusFilter ? tI18n('registrarPanel.' + (REGISTRAR_STATUS_LABEL_KEYS[statusFilter as keyof typeof REGISTRAR_STATUS_LABEL_KEYS] || statusFilter)) : null;

  // Legacy aliases over the consolidated reschedule slice { open, data }.
  const showSlotsModal = rescheduleDialog.open;
  const rescheduleData = rescheduleDialog.data;
  // Hotkeys adapter: hotkeys only close the slots dialog (Esc); opening
  // goes through openRescheduleDialog with row data.
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

// Decomp 8 (PR-UI-13-1): worklist data lifecycle (fetch + reducer +
// refresh lifecycle; anyDialogOpenRef preserves the original stale-closure
// semantics of the auto-refresh deps).

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

  // Reschedule helpers (wired to the worklist setAppointments shim).
  const {
    resolveRescheduleVisitId,
    removeRescheduledAppointmentFromView,
  } = useRegistrarReschedule({ setAppointments: setAppointments as unknown as (updater: (prev: Record<string, unknown>[]) => Record<string, unknown>[]) => void });

  // UX Audit R-1.7: lastQueueJoin localStorage polling removed — the
  // `queueUpdated` WebSocket event (in useRegistrarWorklistData) covers it.

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

  // PR-UI-13-5: filteredAppointmentsRef removed (write-only dead code).

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
  // View-model rows (PR-UI-13-2: pure functions in registrarWorklistRows.ts;
  // memo deps preserve the original recompute triggers).
  const filteredAppointments = useMemo(() => computeRegistrarWorklistRows({
    appointments,
    activeTab,
    statusFilter,
    searchQuery,
    queueProfiles,
    services,
    fallbackPatientLabel: tI18n('registrarPanel.rp_unknown_patient'),
  }), [appointments, activeTab, statusFilter, searchQuery, queueProfiles, services]);

  // Row action routing (PR-UI-13-5 → useRegistrarRowActions).
  const {
    openRecordPreview,
    openRecordEditor,
    handleTableAction,
    handleContextMenuAction,
  } = useRegistrarRowActions({
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
    confirm,
    updateAppointmentStatus,
    handleStartVisit,
    tI18n,
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

      {/* R-03 fix: breadcrumb навигация для wayfinding — extracted to
          RegistrarBreadcrumb (PR-UI-13-5). */}
      <RegistrarBreadcrumb
        activeTab={activeTab}
        queueProfiles={queueProfiles}
        searchQuery={searchQuery}
        wizardEditMode={wizardEditMode}
        showWizard={showWizard}
        onNavigateToWelcome={() => {
          // Phase 2: navigate to canonical path (replaces legacy ?view=welcome)
          const p = new URLSearchParams(searchParams);
          p.delete('q');
          p.delete('status');
          p.delete('view');
          p.delete('tab');
          const qs = p.toString();
          navigate(qs ? `/registrar/welcome?${qs}` : '/registrar/welcome', { replace: true });
        }}
        tI18n={tI18n}
      />

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

      {/* PR-UI-13-5 (Decomp 14): all overlay surfaces extracted to
          RegistrarDialogsLayer (preview / cancel / payment / print /
          ErrorBoundary-guarded wizard / reschedule slots / context menu /
          payment manager / force majeure). */}
      <RegistrarDialogsLayer
        recordPreviewDialog={recordPreviewDialog}
        cancelDialog={cancelDialog}
        paymentDialog={paymentDialog}
        printDialog={printDialog}
        forceMajeureModal={forceMajeureModal}
        contextMenu={contextMenu}
        showSlotsModal={showSlotsModal}
        rescheduleData={rescheduleData}
        showPaymentManager={showPaymentManager}
        showWizard={showWizard}
        wizardEditMode={wizardEditMode}
        wizardInitialData={wizardInitialData}
        isProcessing={isProcessing}
        activeTab={activeTab}
        theme={theme}
        getColor={getColor}
        getSpacing={getSpacing}
        getFontSize={getFontSize}
        setRecordPreviewDialog={setRecordPreviewDialog}
        setPaymentDialog={setPaymentDialog}
        setPrintDialog={setPrintDialog}
        setCancelDialog={setCancelDialog}
        setContextMenu={setContextMenu}
        setForceMajeureModal={setForceMajeureModal}
        setShowPaymentManager={setShowPaymentManager}
        closeRescheduleDialog={closeRescheduleDialog}
        setShowWizard={setShowWizard}
        setWizardEditMode={setWizardEditMode}
        setWizardInitialData={setWizardInitialData}
        setIsProcessing={setIsProcessing}
        appointments={appointments}
        loadAppointments={loadAppointments}
        loadIntegratedData={loadIntegratedData}
        openRecordEditor={openRecordEditor}
        handleContextMenuAction={handleContextMenuAction}
        handleWizardComplete={handleWizardComplete}
        runRegistrarRecordAction={runRegistrarRecordAction}
        handlePayment={handlePayment}
        resolveRescheduleVisitId={resolveRescheduleVisitId}
        removeRescheduledAppointmentFromView={removeRescheduledAppointmentFromView}
        confirm={confirm}
        tI18n={tI18n}
      />

      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}

    </div>);

};

export default RegistrarPanel;
