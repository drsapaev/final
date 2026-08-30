import { useState, useEffect } from 'react';
import './dentistry.css';
import { useLocation } from 'react-router-dom';
// P-009 fix: shared doctor panel state hook
import { useDoctorPanelState } from '../hooks/useDoctorPanelState';
import auth from '../stores/auth';
// apiClient/tokenManager/queueService/printPanelTicket consumers moved to
// ./dentist/useDentistActions in PR-UI-15-5.
import DentalDashboardTab, { type DentalDashboardAppointment } from '../components/dental/DentalDashboardTab';
import DentalPatientsTab from '../components/dental/DentalPatientsTab';
import QueueIntegration from '../components/QueueIntegration';

import '../styles/animations.css';
// printPanelTicket consumer moved to ./dentist/useDentistActions (PR-UI-15-5).
import notify from '../services/notify';
// STRAT#34: useTranslation adapter for confirm/notify i18n.
import { useTranslation } from '../i18n/useTranslation';
import type { Appointment } from '../types/domain/clinic';
import { useConfirm } from '../components/common/ConfirmDialog';
import { useSessionTimeoutWarning } from '../hooks/useSessionTimeoutWarning';
import { useDentalHotkeys } from '../hooks/useDentalHotkeys';
import logger from '../utils/logger';
// tokenManager consumer moved to ./dentist/useDentistActions (PR-UI-15-5).
import { useVisitLifecycle } from '../hooks/useVisitLifecycle';
// getErrorMessage consumers moved to ./dentist/useDentistActions (PR-UI-15-5).

// PR-UI-15-3: module-level contracts infra (types, status constants, caches +
// BS-42 invalidation, queue-id resolution, patient derivation, localStorage
// bootstrap) extracted verbatim to ./dentist/dentistContracts.
import {
  invalidateDentistPanelCaches,
  type SelectedPatient,
  type DoctorPanelState,
} from './dentist/dentistContracts';
// PR-UI-15-3: worklist data lifecycle (queues/today fetch + DTO mapping +
// services + patients + queueUpdated listener) extracted verbatim to
// ./dentist/useDentistWorklistData.
import { useDentistWorklistData } from './dentist/useDentistWorklistData';
// PR-UI-15-4: dialog view-state + EMR v2 visit-protocol lifecycle extracted
// verbatim to ./dentist/useDentistDialogs + ./dentist/useDentistVisitProtocols.
import { useDentistDialogs } from './dentist/useDentistDialogs';
import { useDentistUrlPatient } from './dentist/useDentistUrlPatient';
import { useDentistVisitProtocols } from './dentist/useDentistVisitProtocols';
// PR-UI-15-5: business-action handlers (appointment table actions, patient
// routing, C-3 critical ICD-10 gate + handleCompleteVisit, dialog-opening
// handlers, protocol-template drafting) extracted verbatim to
// ./dentist/useDentistActions.
import { useDentistActions } from './dentist/useDentistActions';
// PR-UI-15-6: views + dialogs layer (verbatim JSX extraction) and the local
// ErrorBoundary around tab content (PR-UI-15 plan item 5; registrar 13-4 /
// cashier 14-5 / doctor 15-2 precedent).
import ErrorBoundary from '../components/common/ErrorBoundary';
import DentistVisitsView from './dentist/views/DentistVisitsView';
import DentistPhotosView from './dentist/views/DentistPhotosView';
import DentistAIAssistantView from './dentist/views/DentistAIAssistantView';
import DentistDialogsLayer from './dentist/views/DentistDialogsLayer';

/**
 * Объединенная стоматологическая панель с полным функционалом
 * Включает:
 * - Схемы зубов и планирование лечения
 * - AI помощник
 * - Управление пациентами
 * - Интеграция с очередями
 * - Современный UI
 */
const DentistPanelUnified = () => {
  const location = useLocation();
  // P-009: navigate removed — useDoctorPanelState handles tab URL sync
  const [authState, setAuthState] = useState(auth.getState());

  useEffect(() => {
    const unsubscribe = auth.subscribe(setAuthState);
    return unsubscribe;
  }, []);

  const user = authState.profile;

  // P-009 fix: use shared useDoctorPanelState hook for tab/URL/patient state.
  // Dentistry uses 'visits' (plural) for visitDeepLinkTab.
  const {
    activeTab,
    handleTabChange,
    patientIdFromUrl,
    visitIdFromUrl,
    selectedPatient,
    setSelectedPatient,
  } = useDoctorPanelState({
    // Phase 4: sidebar reduced to 4 tabs — queue / visit / patients / photos.
    defaultTab: 'queue',
    visitDeepLinkTab: 'visit',
    patientDeepLinkTab: 'patients',
  }) as DoctorPanelState;

  // STRAT#34: useTranslation adapter for confirm/notify i18n.
  // PR-UI-15-3: moved above the worklist hook — the hook needs tI18n for the
  // DTO labels (hook order stays consistent across renders).
  const { t: tI18n } = useTranslation();

  // PR-UI-15-6: handleCardKeyDown moved verbatim to ./dentist/dentistCardA11y
  // (shared by the extracted card-grid views).
  const [loading, setLoading] = useState(true);
  // P-009: selectedPatient / setSelectedPatient now come from useDoctorPanelState
  // PR-UI-15-4: savedVisitProtocols + protocol loaders/persist/reopen moved
  // verbatim to ./dentist/useDentistVisitProtocols (EMR v2 lifecycle).

  // PR-UI-15-3: worklist state (patients + appointments table + services +
  // refs) + the queues/today data lifecycle moved verbatim to
  // ./dentist/useDentistWorklistData.
  const {
    patients,
    appointmentsTableData,
    appointmentsTableDataRef,
    loadDentistryAppointments,
    ensureCanonicalVisitId,
    loadData,
  } = useDentistWorklistData({ tI18n, activeTab });
  // PR-UI-15-6: appointmentsLoading / services no longer destructured —
  // their only consumer was the unreachable appointments render (see below).
  // PR-UI-15-6: searchQuery/filterStatus state removed — dead since the
  // Phase 4 sidebar reduction (the only consumer, filteredPatients, fed
  // no reachable render; see dead-render cleanup below).
  // PR-UI-15-4: dialog/tooth/price/schedule view-state slice moved verbatim
  // to ./dentist/useDentistDialogs (plain useState — no cross-field reset
  // shapes, unlike the registrar/cashier dialog state machines).
  const {
    showDentalChart, setShowDentalChart,
    showTreatmentPlanner, setShowTreatmentPlanner,
    showPatientCard, setShowPatientCard,
    showDiagnosisForm, setShowDiagnosisForm,
    showVisitProtocol, setShowVisitProtocol,
    showPhotoArchive, setShowPhotoArchive,
    showProtocolTemplates, setShowProtocolTemplates,
    showReports, setShowReports,
    dentalChartData, setDentalChartData,
    showPriceManager, setShowPriceManager,
    selectedServiceForPrice, setSelectedServiceForPrice,
    selectedTooth, setSelectedTooth,
    toothModalOpen, setToothModalOpen,
    protocolTemplateDraft, setProtocolTemplateDraft,
    scheduleNextModal, setScheduleNextModal,
  } = useDentistDialogs();

  // P-022 (workflow audit): wire useVisitLifecycle so the in-memory cache
  // is invalidated when the doctor switches between visits or patients.
  // Mirrors the CardiologistPanelUnified wiring (commit 5ee3de3).
  //
  // When currentVisitId / currentPatientId change, the hook:
  //   1. aborts all in-flight requests via AbortController
  //   2. calls cacheService.invalidateByVisit(prevVisitId)
  //   3. calls cacheService.invalidateByPatient(prevPatientId)
  //   4. invokes our onCleanup callback (resets local visit-protocol state)
  //
  // This prevents PHI leaks between patients on rapid visit switches.
  // Non-breaking: existing persistVisitProtocol, handleCompleteVisit, and
  // queue handlers are untouched.
  const lifecycleVisitId = selectedPatient?.visit_id || visitIdFromUrl || null;
  const lifecyclePatientId =
    selectedPatient?.patient?.id ||
    selectedPatient?.patient_id ||
    selectedPatient?.id ||
    patientIdFromUrl ||
    null;
  useVisitLifecycle(
    lifecycleVisitId as unknown as string | number,
    lifecyclePatientId as unknown as string | number,
    {
    invalidateCacheOnChange: true,
    onCleanup: () => {
      // Reset local protocol state so stale data does not bleed into the
      // next visit's view. persistVisitProtocol will be re-invoked by the
      // existing useEffect when selectedPatient changes.
      setShowVisitProtocol(false);
      setProtocolTemplateDraft(null);
      // audit/phase-1, BS-42: also clear the 7 module-level mutable caches
      // so the next patient's appointments / services / visit-protocols are
      // refetched from the backend instead of being served stale from the
      // previous patient's session. Without this, on a shared workstation
      // the previous patient's PHI could be displayed to the next clinician.
      invalidateDentistPanelCaches();
    },
  },
  );

  // PR-UI-15-4: EMR v2 visit-protocol lifecycle (saved protocols + loaders +
  // persist + reopen + hydrate) — verbatim port; deps-object wiring keeps the
  // original setSelectedPatient / setShowVisitProtocol semantics.
  // Codex P2, PR 2930: вызов размещён ПОСЛЕ useVisitLifecycle — как в
  // исходной панели (effect-ordering: сначала инвалидация кэшей BS-42,
  // затем hydrate-эффект; иначе протоколы могли бы читаться из устаревшего
  // кэша при быстром переключении пациентов).
  // PR-UI-15-6: savedVisitProtocols / reopenVisitProtocol are no longer
  // destructured here — their only panel consumer was the unreachable
  // reports render removed this increment (the EMR v2 protocol surface
  // stays alive via persistVisitProtocol + the VisitProtocol modal, and the
  // loaders stay available on the hook API).
  const {
    loadDentistVisitProtocolByVisitId,
    persistVisitProtocol,
  } = useDentistVisitProtocols({
    tI18n,
    selectedPatient,
    setSelectedPatient,
    setShowVisitProtocol,
  });
  useEffect(() => {
    appointmentsTableDataRef.current = appointmentsTableData;
  }, [appointmentsTableData]);

  // PR-UI-15-4: loadDentistVisitProtocolsForPatient +
  // loadDentistVisitProtocolByVisitId moved verbatim to
  // ./dentist/useDentistVisitProtocols.

  // Формы данных


  // Refs

  // PR-UI-15-6: useTheme moved into views/DentistDialogsLayer (its only
  // consumer — the ScheduleNextModal theme prop — lives there now).

  // C-1 (UX audit): confirm hook for visit completion
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw;

  // PR-UI-15-5: business-action handler slice (verbatim extraction).
  // Deps-object composition follows the useRegistrarRowActions /
  // useCashierActions precedent — the panel stays the composition point.
  // PR-UI-15-6: handleDiagnosis / handleProtocolTemplates / handleReports /
  // handleTreatmentPlanner / handleAppointmentRowClick /
  // handleAppointmentActionClick are no longer destructured here — their only
  // panel callers were the unreachable Phase-4-reduced renders removed below
  // (the handlers stay available on the hook API).
  const {
    handlePatientSelect,
    handleCompleteVisit,
    handleVisitProtocol,
    handlePhotoArchive,
    handleProtocolTemplateSelect,
    handleDentalChart,
  } = useDentistActions({
    tI18n,
    confirm,
    setLoading,
    selectedPatient,
    setSelectedPatient,
    handleTabChange,
    ensureCanonicalVisitId,
    loadDentistryAppointments,
    loadDentistVisitProtocolByVisitId,
    setShowDiagnosisForm,
    setShowVisitProtocol,
    setShowPhotoArchive,
    setShowProtocolTemplates,
    setShowReports,
    setShowDentalChart,
    setShowTreatmentPlanner,
    setDentalChartData,
    setProtocolTemplateDraft,
  });
  // C-2 (UX audit): session timeout warning
  const [sessionWarning, setSessionWarning] = useState<{ active: boolean } | null>(null);

  useSessionTimeoutWarning({
    onWarning: () => setSessionWarning({ active: true }),
    onExpired: () => {
      setSessionWarning(null);
      notify.error(tI18n('dental.session_expired'));
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    },
  });

  // Deferred #2: keyboard shortcuts for tab switching, refresh, clear selection.
  useDentalHotkeys({
    handleTabChange,
    refreshData: () => loadDentistryAppointments(true),
    clearSelection: () => setSelectedPatient(null),
  });

  // PR-UI-15-3: loadServices / loadDentistryAppointments / getAllPatientServicesCb
  // / queueUpdated-listener / ensureCanonicalVisitId moved verbatim to
  // ./dentist/useDentistWorklistData.

  // PR-UI-15-5: resolvePatientId / resolvePatientName + appointment-table
  // handlers (handleAppointmentRowClick / handleAppointmentActionClick)
  // moved verbatim to ./dentist/useDentistActions.

  // Проверяем демо-режим после всех хуков
  const isDemoMode = window.location.pathname.includes('/medilab-demo');

  // PR-UI-15-3: authHeader (dead, definition-only) + loadPatients +
  // loadTreatmentPlans / loadProsthetics no-op stubs (dead, PR-43/Medium-24
  // endpoints pending backend) dropped; loadData moved verbatim to
  // ./dentist/useDentistWorklistData. The panel keeps only the loading gate
  // around the hook's loadData (verbatim setLoading semantics).
  useEffect(() => {
    const runLoad = async () => {
      setLoading(true);
      try {
        await loadData();
      } catch (error: unknown) {
        logger.error('Ошибка загрузки данных:', error);
      } finally {
        setLoading(false);
      }
    };
    runLoad();
  }, [loadData]);

  // PR-UI-15-6: the ?patientId/?visitId URL deep-link hydration moved
  // verbatim to ./dentist/useDentistUrlPatient (deps array preserved).
  useDentistUrlPatient({
    locationSearch: location.search,
    patientIdFromUrl,
    visitIdFromUrl,
    selectedPatient,
    appointmentsTableData,
    loadDentistryAppointments,
    setSelectedPatient,
    handleTabChange,
    tI18n,
  });

  // PR-UI-15-5: handlePatientSelect moved verbatim to ./dentist/useDentistActions.

  // Сохранение EMR






































  // PR-UI-15-5: C-3 critical ICD-10 gate (CRITICAL_ICD10_CODES +
  // getCriticalDiagnosisWarning) and handleCompleteVisit moved verbatim to
  // ./dentist/useDentistActions (tiered C-1 confirm preserved; see the
  // safety contract union note in the test).

  // PR-UI-15-5: dialog-opening patient handlers (handleDiagnosis /
  // handleVisitProtocol / handlePhotoArchive / handleProtocolTemplates)
  // moved verbatim to ./dentist/useDentistActions.

  // PR-UI-15-5: protocol-template drafting (buildVisitProtocolDraftFromTemplate
  // + handleProtocolTemplateSelect) and handleReports moved verbatim to
  // ./dentist/useDentistActions.

  // PR-UI-15-4: persistVisitProtocol + reopenVisitProtocol moved verbatim
  // to ./dentist/useDentistVisitProtocols (EMR v2 POST + reopen flow).

  // PR-UI-15-5: handleDentalChart + handleTreatmentPlanner moved verbatim
  // to ./dentist/useDentistActions.

  // PR-UI-15-6: filteredPatients / stats / appointmentSummaryItems
  // removed — dead since the Phase 4 sidebar reduction (no reachable
  // render consumed them; eslint unused-var warnings on main).

  // Вкладки
  // Рендер дашборда
  const renderDashboard = () =>
    <DentalDashboardTab
      appointments={appointmentsTableData as unknown as DentalDashboardAppointment[]}
      patients={patients}
      onGoToAppointments={() => handleTabChange('appointments')}
      onGoToPatients={() => handleTabChange('patients')}
    />;
  const renderPatients = () =>
    <DentalPatientsTab
      patients={patients as unknown as Array<Record<string, unknown>>}
      onSelectPatient={handlePatientSelect as unknown as (patient: Record<string, unknown>) => void}
      onDentalChart={handleDentalChart as unknown as (patient: Record<string, unknown>) => void}
    />;
  // PR-UI-15-6: renderAppointments / renderDiagnoses / renderTemplates /
  // renderReports / renderDentalChart removed — unreachable after the
  // Phase 4 sidebar reduction (activeTab switch has no case for them;
  // eslint unused warnings on main; same rationale as renderExaminations
  // removal in PR-UI-15-3).

  // Рендер осмотров удалён (C-2, UI_AUDIT_PLAN.md): вкладка examinations не входит в
  // 5-tab sidebar (routeRegistry Phase 4: «examinations/diagnoses merged into EMR v2
  // visit screen»), renderExaminations не имел reachable caller.


  // PR-UI-15-6: renderDiagnoses removed — unreachable (no activeTab case;
  // eslint unused warning on main; Phase 4 sidebar reduction).

  const renderVisits = () =>
    <DentistVisitsView
      selectedPatient={selectedPatient}
      patients={patients}
      loading={loading}
      onCompleteVisit={handleCompleteVisit}
      onVisitProtocol={handleVisitProtocol}
      onBackToQueue={() => {
        setSelectedPatient(null);
        handleTabChange('queue');
      }}
      tI18n={tI18n} />;

  // PR-UI-15-6: renderPhotos → views/DentistPhotosView (verbatim JSX).
  const renderPhotos = () =>
    <DentistPhotosView
      patients={patients}
      onPhotoArchive={handlePhotoArchive}
      tI18n={tI18n} />;

  // Рендер планов лечения


  // PR-UI-15-6: renderAIAssistant → views/DentistAIAssistantView
  // (verbatim JSX).
  const renderAIAssistant = () => <DentistAIAssistantView tI18n={tI18n} />;

  // Рендер контента
  const renderContent = () => {
    switch (activeTab) {
      case 'queue':
        return (
          <QueueIntegration
            specialistId={String(user?.doctor_id || user?.specialist_id || '')}
            specialty="dentistry"
            onPatientSelect={handlePatientSelect}
            onStartVisit={(appointment: Appointment) => {
              setSelectedPatient(appointment as unknown as SelectedPatient);
              handleTabChange('visit');
            }} />);


      case 'patients':
        return renderPatients();
      case 'visit':
      case 'visits':
        // Phase 4: 'visit' is the new sidebar tab; 'visits' kept as
        // alias for back-compat with deep links and old saved URLs.
        return renderVisits();
      case 'photos':
        return renderPhotos();
      case 'ai-assistant':
        return renderAIAssistant();
      default:
        return renderDashboard();
    }
  };

  if (isDemoMode) {
    logger.info('DentistPanelUnified: Skipping render in demo mode');
    return null;
  }

  if (loading) {
    return (
      <div className="dental-p-8">
        <div className="dental-flex-col dental-gap-24">
          <div className="dental-skeleton-bar"></div>
          <div className="dental-skeleton-grid">
            {[...Array(4)].map((_, i) =>
            <div key={i} className="dental-skeleton-card"></div>
            )}
          </div>
        </div>
      </div>);

  }

  // PR-UI-15-6: selectedPatientId / selectedPatientDisplayName moved into
  // views/DentistDialogsLayer (their only consumers were the modals).

  return (
    <div className="dentist-panel dental-text-primary">
      {/* PR-UI-15 (plan item 5): локальный ErrorBoundary вокруг контента
          вкладок (падение рендера любого таба не уронит всю страницу
          стоматолога; registrar 13-4 / cashier 14-5 / doctor 15-2
          precedent). key={activeTab} сбрасывает boundary при смене вкладки —
          упавший таб не «отравляет» здоровые (Codex P2 #2926 precedent). */}
      <ErrorBoundary key={activeTab}>
        {renderContent()}
      </ErrorBoundary>

      {/* Модальные окна + C-1/C-2 диалоги — PR-UI-15-6: verbatim JSX moved
          to views/DentistDialogsLayer (patient card, diagnosis form, EMR v2
          visit protocol, photo archive, protocol templates, lazy reports,
          dental chart + tooth modal, treatment planner, price manager,
          schedule-next, ConfirmDialog slot, SessionWarningModal). */}
      <DentistDialogsLayer
        tI18n={tI18n}
        user={user as Record<string, unknown> | null | undefined}
        selectedPatient={selectedPatient}
        protocolTemplateDraft={protocolTemplateDraft}
        dentalChartData={dentalChartData}
        selectedTooth={selectedTooth}
        selectedServiceForPrice={selectedServiceForPrice}
        scheduleNextModal={scheduleNextModal}
        sessionWarning={sessionWarning}
        confirmDialog={confirmDialog}
        showPatientCard={showPatientCard}
        showDiagnosisForm={showDiagnosisForm}
        showVisitProtocol={showVisitProtocol}
        showPhotoArchive={showPhotoArchive}
        showProtocolTemplates={showProtocolTemplates}
        showReports={showReports}
        showDentalChart={showDentalChart}
        showTreatmentPlanner={showTreatmentPlanner}
        showPriceManager={showPriceManager}
        toothModalOpen={toothModalOpen}
        setShowPatientCard={setShowPatientCard}
        setShowDiagnosisForm={setShowDiagnosisForm}
        setShowVisitProtocol={setShowVisitProtocol}
        setShowPhotoArchive={setShowPhotoArchive}
        setShowProtocolTemplates={setShowProtocolTemplates}
        setShowReports={setShowReports}
        setShowDentalChart={setShowDentalChart}
        setShowTreatmentPlanner={setShowTreatmentPlanner}
        setShowPriceManager={setShowPriceManager}
        setToothModalOpen={setToothModalOpen}
        setSelectedTooth={setSelectedTooth}
        setDentalChartData={setDentalChartData}
        setSelectedServiceForPrice={setSelectedServiceForPrice}
        setScheduleNextModal={setScheduleNextModal}
        setSessionWarning={setSessionWarning}
        setProtocolTemplateDraft={setProtocolTemplateDraft}
        persistVisitProtocol={persistVisitProtocol}
        handleCompleteVisit={handleCompleteVisit}
        handleProtocolTemplateSelect={handleProtocolTemplateSelect}
      />
    </div>);



};

export default DentistPanelUnified;
