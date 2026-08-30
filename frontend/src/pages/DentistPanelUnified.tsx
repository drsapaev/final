import { lazy, Suspense, useState, useEffect, useCallback, useMemo } from 'react';
import './dentistry.css';
import { useLocation } from 'react-router-dom';
// P-009 fix: shared doctor panel state hook
import { useDoctorPanelState } from '../hooks/useDoctorPanelState';
import { useTheme } from '../contexts/ThemeContext';
import { getLocalDateString, parseRegistrarTimestamp } from '../utils/dateUtils';
import {
  Button, Badge, Card } from '../components/ui/macos';
import AppointmentSummaryBar from '../components/doctor/AppointmentSummaryBar';
import auth from '../stores/auth';
// apiClient/tokenManager/queueService/printPanelTicket consumers moved to
// ./dentist/useDentistActions in PR-UI-15-5.
import AIAssistant from '../components/ai/AIAssistant';
import TeethChart from '../components/dental/TeethChart';
import ToothModal from '../components/dental/ToothModal';
import DentalVisitScreen from '../components/dental/DentalVisitScreen';
import TreatmentPlanner from '../components/dental/TreatmentPlanner';
import PatientCard from '../components/dental/PatientCard';
import type { PatientFormData } from '../components/dental/PatientCard';
import DentalPriceManager from '../components/dental/DentalPriceManager';
import DiagnosisForm from '../components/dental/DiagnosisForm';
import VisitProtocol from '../components/dental/VisitProtocol';
import PhotoArchive from '../components/dental/PhotoArchive';
import ProtocolTemplates from '../components/dental/ProtocolTemplates';
import DentalReportsTab from '../components/dental/DentalReportsTab';
import DentalTemplatesTab from '../components/dental/DentalTemplatesTab';
import DentalDashboardTab, { type DentalDashboardAppointment } from '../components/dental/DentalDashboardTab';
import DentalPatientsTab from '../components/dental/DentalPatientsTab';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import SessionWarningModal from '../components/common/SessionWarningModal';
import EnhancedAppointmentsTable, { type AppointmentRow } from '../components/tables/EnhancedAppointmentsTable';
import QueueIntegration from '../components/QueueIntegration';

import {
  Calendar,
  XCircle } from
'lucide-react';
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
import {
  countAppointmentsByStatuses,
  normalizeNumericId,
} from '../utils/doctorPanelShared';
import { useVisitLifecycle } from '../hooks/useVisitLifecycle';
// getErrorMessage consumers moved to ./dentist/useDentistActions (PR-UI-15-5).

const LazyReportsAndAnalytics = lazy(() => import('../components/dental/ReportsAndAnalytics'));

// PR-UI-15-3: module-level contracts infra (types, status constants, caches +
// BS-42 invalidation, queue-id resolution, patient derivation, localStorage
// bootstrap) extracted verbatim to ./dentist/dentistContracts.
import {
  DENTISTRY_WAITING_STATUSES,
  DENTISTRY_CALLED_STATUSES,
  DENTISTRY_COMPLETED_STATUSES,
  invalidateDentistPanelCaches,
  dentistCache,
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
import { useDentistVisitProtocols } from './dentist/useDentistVisitProtocols';
// PR-UI-15-5: business-action handlers (appointment table actions, patient
// routing, C-3 critical ICD-10 gate + handleCompleteVisit, dialog-opening
// handlers, protocol-template drafting) extracted verbatim to
// ./dentist/useDentistActions.
import { useDentistActions } from './dentist/useDentistActions';

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

  const handleCardKeyDown = useCallback((event: React.KeyboardEvent<HTMLElement>, action: () => void) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      action();
    }
  }, []);
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
    appointmentsLoading,
    services,
    loadDentistryAppointments,
    ensureCanonicalVisitId,
    loadData,
  } = useDentistWorklistData({ tI18n, activeTab });
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
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
  const {
    savedVisitProtocols,
    loadDentistVisitProtocolByVisitId,
    persistVisitProtocol,
    reopenVisitProtocol,
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

  // Используем централизованную систему темизации
  const {
    isDark,
    getColor,
    getSpacing,
    getFontSize
  } = useTheme();

  // C-1 (UX audit): confirm hook for visit completion
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw;

  // PR-UI-15-5: business-action handler slice (verbatim extraction).
  // Deps-object composition follows the useRegistrarRowActions /
  // useCashierActions precedent — the panel stays the composition point.
  const {
    handleAppointmentRowClick,
    handleAppointmentActionClick,
    handlePatientSelect,
    handleCompleteVisit,
    handleDiagnosis,
    handleVisitProtocol,
    handlePhotoArchive,
    handleProtocolTemplates,
    handleProtocolTemplateSelect,
    handleReports,
    handleDentalChart,
    handleTreatmentPlanner,
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

  // ✅ Автоматическая загрузка пациента из URL параметра patientId
  useEffect(() => {
    const loadPatientFromUrl = async () => {
      // P-009: patientIdFromUrl / visitIdFromUrl come from useDoctorPanelState
      if (!patientIdFromUrl && !visitIdFromUrl) return;

      // Если пациент уже загружен с этим ID/визитом, пропускаем
      const currentPatientId = selectedPatient?.patient_id || null;
      const currentVisitId = normalizeNumericId(selectedPatient?.visit_id);
      if (
        patientIdFromUrl &&
        currentPatientId === patientIdFromUrl &&
        (!visitIdFromUrl || currentVisitId === visitIdFromUrl)
      ) {
        return;
      }
      if (
        visitIdFromUrl &&
        currentVisitId === visitIdFromUrl &&
        (!patientIdFromUrl || currentPatientId === patientIdFromUrl)
      ) {
        return;
      }

      try {
        const findMatchingAppointment = (appointments: Appointment[]) => {
          if (!Array.isArray(appointments)) {
            return null;
          }

          return appointments.find((appointment: Appointment) => {
            if (visitIdFromUrl && normalizeNumericId(appointment.visit_id) === visitIdFromUrl) {
              return true;
            }
            return patientIdFromUrl && String(appointment.patient_id) === String(patientIdFromUrl);
          }) || null;
        };

        let matchingAppointment = findMatchingAppointment(appointmentsTableData);
        if (!matchingAppointment) {
          const refreshedAppointments = await loadDentistryAppointments();
          matchingAppointment = findMatchingAppointment(refreshedAppointments || []);
        }

        if (matchingAppointment) {
          const patientName =
            matchingAppointment.patient_fio ||
            matchingAppointment.patient_name ||
            (matchingAppointment.name as string | undefined) ||
            tI18n('dental.dental_panel_patient_default');

          const patientObj: SelectedPatient = {
            id: (matchingAppointment.appointment_id as string | number | undefined) || matchingAppointment.id || patientIdFromUrl || visitIdFromUrl,
            patient_id: matchingAppointment.patient_id || patientIdFromUrl || matchingAppointment.id,
            appointment_id: (matchingAppointment.appointment_id as string | number | null | undefined) || null,
            visit_id: visitIdFromUrl || normalizeNumericId(matchingAppointment.visit_id) || null,
            patient_name: patientName,
            patient_fio: patientName,
            phone: matchingAppointment.patient_phone || (matchingAppointment.phone as string) || '',
            source: (matchingAppointment.source as string) || 'appointments',
            specialty: matchingAppointment.specialty || 'dental'
          };

          setSelectedPatient(patientObj);
          handleTabChange(patientObj.visit_id ? 'visit' : 'patients');
          logger.info('[Dentist] Загружен пациент из URL:', patientObj.patient_name);
          return;
        }

        if (visitIdFromUrl || patientIdFromUrl) {
          const fallbackLabel = patientIdFromUrl
            ? tI18n('dental.dental_panel_patient_url_fallback', { id: patientIdFromUrl })
            : tI18n('dental.dental_panel_visit_url_fallback', { id: visitIdFromUrl });

          const patientObj: SelectedPatient = {
            id: patientIdFromUrl || visitIdFromUrl,
            patient_id: patientIdFromUrl || visitIdFromUrl,
            appointment_id: null,
            visit_id: visitIdFromUrl || null,
            patient_name: fallbackLabel,
            patient_fio: fallbackLabel,
            phone: '',
            source: 'url',
            specialty: 'dental'
          };

          setSelectedPatient(patientObj);
          handleTabChange(visitIdFromUrl ? 'visit' : 'patients');
          const fallbackLogKey = `${patientIdFromUrl || ''}:${visitIdFromUrl || ''}`;
          if (!dentistCache.fallbackLoggedKeys.has(fallbackLogKey)) {
            dentistCache.fallbackLoggedKeys.add(fallbackLogKey);
            logger.info('[Dentist] Пациент из URL не найден в очереди, использую безопасный URL-fallback:', patientObj.patient_name);
          }
        }
      } catch (error: unknown) {
        logger.error('[Dentist] Не удалось загрузить пациента из URL:', error);
      }
    };

    loadPatientFromUrl();
  }, [location.search, patientIdFromUrl, visitIdFromUrl, appointmentsTableData, loadDentistryAppointments]); // eslint-disable-line react-hooks/exhaustive-deps

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

  // Фильтрация пациентов
  const filteredPatients = patients.filter((patient) => {
    const matchesSearch = !searchQuery ||
    patient.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    patient.phone?.includes(searchQuery);

    const matchesStatus = filterStatus === 'all' || patient.status === filterStatus;

    return matchesSearch && matchesStatus;
  });

  // Статистика
  const stats = useMemo(() => {
    // PR-13: use getLocalDateString() instead of new Date().toDateString()
    // to avoid browser-local timezone issues (off-by-one for early-morning Tashkent)
    const todayString = getLocalDateString();
    const todayAppointmentsCount = appointmentsTableData.filter((apt) => {
      if (!apt.appointment_date && !apt.queue_time && !apt.created_at) {
        return false;
      }
      // Try to get the date from queue_time/created_at (timezone-aware) first,
      // then fall back to appointment_date
      const ts = apt.queue_time || apt.created_at;
      if (ts) {
        const parsedDate = parseRegistrarTimestamp(ts);
        if (!parsedDate) {
          return false;
        }
        const aptDate = getLocalDateString(parsedDate);
        return aptDate === todayString;
      }
      // Fall back to appointment_date (may be YYYY-MM-DD already)
      return apt.appointment_date === todayString;
    }).length;

    const activeTreatmentPlansCount = appointmentsTableData.filter((apt) => apt.status === 'in_progress' || apt.status === 'waiting').length;
    const completedProstheticsCount = appointmentsTableData.filter((apt) => apt.status === 'completed').length;

    return {
      totalPatients: patients.length,
      todayAppointments: todayAppointmentsCount,
      activeTreatmentPlans: activeTreatmentPlansCount,
      completedProsthetics: completedProstheticsCount
    };
  }, [appointmentsTableData, patients]);

  const appointmentSummaryItems = useMemo(() => [
    {
      key: 'total',
      label: tI18n('dental.dental_panel_stat_total'),
      value: appointmentsTableData.length,
      variant: 'info'
    },
    {
      key: 'waiting',
      label: tI18n('dental.dental_panel_stat_waiting'),
      value: countAppointmentsByStatuses(appointmentsTableData, DENTISTRY_WAITING_STATUSES),
      variant: 'warning'
    },
    {
      key: 'called',
      label: tI18n('dental.dental_panel_stat_called'),
      value: countAppointmentsByStatuses(appointmentsTableData, DENTISTRY_CALLED_STATUSES),
      variant: 'primary'
    },
    {
      key: 'completed',
      label: tI18n('dental.dental_panel_stat_completed'),
      value: countAppointmentsByStatuses(appointmentsTableData, DENTISTRY_COMPLETED_STATUSES),
      variant: 'success'
    }
  ], [appointmentsTableData, tI18n]);

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
  const renderAppointments = () =>
  <div className="dental-appointments-root">
      <Card padding="large" className="dental-appointments-card">
        <div className="dental-appointments-header">
          <h3 className="dental-appointments-title">
            <Calendar className="dental-icon-20 dental-text-success dental-mr-8" />
            {tI18n('dental.dental_panel_appointments_title')}
          </h3>
          <AppointmentSummaryBar
            ariaLabel={tI18n('dental.dental_panel_appointments_summary_aria')}
            items={appointmentSummaryItems}
            onRefresh={loadDentistryAppointments}
            refreshDisabled={appointmentsLoading}
            BadgeComponent={Badge}
            ButtonComponent={Button}
            buttonProps={{ variant: 'secondary', size: 'sm' }}
          />
        </div>

        <EnhancedAppointmentsTable
        data={appointmentsTableData as unknown as unknown as AppointmentRow[]}
        loading={appointmentsLoading}
        theme="light"
        language="ru"
        view="doctor"
        selectedRows={new Set()}
        outerBorder={false}
        services={services}
        showCheckboxes={false}
        onRowClick={handleAppointmentRowClick as unknown as (row: unknown) => void}
        onActionClick={handleAppointmentActionClick as unknown as (action: string, row: unknown, event?: unknown) => void} />

      </Card>
    </div>;


  // Рендер осмотров удалён (C-2, UI_AUDIT_PLAN.md): вкладка examinations не входит в
  // 5-tab sidebar (routeRegistry Phase 4: «examinations/diagnoses merged into EMR v2
  // visit screen»), renderExaminations не имел reachable caller.


  // Рендер диагнозов
  const renderDiagnoses = () =>
  <div className="dental-flex-col dental-gap-24">
      <Card padding="large">
        <h3 className="dental-text-primary">{tI18n('dental.dental_panel_diagnoses_title')}</h3>
        <p className="dental-text-desc dental-text-secondary">
          {tI18n('dental.dental_panel_diagnoses_subtitle')}
        </p>

        <div className="dental-grid-auto-fill-250">
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label={tI18n('dental.dental_panel_aria_diagnosis')}
          className="dental-card-btn"
          onClick={() => handleDiagnosis(patient)}
          onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleCardKeyDown(event, () => handleDiagnosis(patient))}
          onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'transparent';
          }}>

              <div className="dental-flex dental-gap-12">
                <div className="dental-icon-bg dental-icon-bg-blue dental-icon-bg-full">
                  <span className="dental-text-value dental-text-white">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="dental-text-primary">{patient.name}</p>
                  <p className="dental-text-desc dental-text-secondary">{tI18n('dental.dental_panel_diagnosis_action')}</p>
                </div>
              </div>
            </div>
        )}
        </div>
      </Card>
    </div>;


  // Рендер протоколов визитов
  const renderVisits = () => {
    // Если выбран пациент из очереди - показываем минималистичный DentalVisitScreen
    if (selectedPatient) {
      return (
        <DentalVisitScreen
          patient={selectedPatient as Record<string, unknown>}
          onCompleteVisit={handleCompleteVisit}
          onBackToQueue={() => {
            setSelectedPatient(null);
            handleTabChange('queue');
          }}
          loading={loading}
        />
      );
    }

    // Иначе показываем список пациентов для выбора протокола
    return (
      <div className="dental-flex-col dental-gap-24">
        <Card padding="large">
          <h3 className="dental-text-primary">{tI18n('dental.dental_panel_visits_title')}</h3>
          <p className="dental-text-desc dental-text-secondary">
            {tI18n('dental.dental_panel_visits_subtitle')}
          </p>

          <div className="dental-grid-auto-fill-250">
            {patients.map((patient) =>
            <div
              key={patient.id}
              role="button"
              tabIndex={0}
              aria-label={tI18n('dental.dental_panel_aria_visit')}
              className="dental-card-btn"
              onClick={() => handleVisitProtocol(patient)}
              onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleCardKeyDown(event, () => handleVisitProtocol(patient))}
              onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.background = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.background = 'transparent';
              }}>

                <div className="dental-flex dental-gap-12">
                  <div className="dental-icon-bg dental-icon-bg-purple dental-icon-bg-full">
                    <span className="dental-text-value dental-text-white">
                      {patient.name?.charAt(0)}
                    </span>
                  </div>
                  <div>
                    <p className="dental-text-primary">{patient.name}</p>
                    <p className="dental-text-desc dental-text-secondary">{tI18n('dental.dental_panel_visit_action')}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>);

  };

  // Рендер фото архива
  const renderPhotos = () =>
  <div className="dental-flex-col dental-gap-24">
      <Card padding="large">
        <h3 className="dental-text-primary">{tI18n('dental.dental_panel_photos_title')}</h3>
        <p className="dental-text-desc dental-text-secondary">
          {tI18n('dental.dental_panel_photos_subtitle')}
        </p>

        <div className="dental-grid-auto-fill-250">
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label={tI18n('dental.dental_panel_aria_photos')}
          className="dental-card-btn"
          onClick={() => handlePhotoArchive(patient)}
          onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleCardKeyDown(event, () => handlePhotoArchive(patient))}
          onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'transparent';
          }}>

              <div className="dental-flex dental-gap-12">
                <div className="dental-icon-bg dental-icon-bg-warning dental-icon-bg-full">
                  <span className="dental-text-value dental-text-white">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="dental-text-primary">{patient.name}</p>
                  <p className="dental-text-desc dental-text-secondary">{tI18n('dental.dental_panel_photos_action')}</p>
                </div>
              </div>
            </div>
        )}
        </div>
      </Card>
    </div>;


  // Рендер шаблонов
  const renderTemplates = () =>
    <DentalTemplatesTab
      onManageTemplates={handleProtocolTemplates}
      templates={[]}
      onApplyTemplate={() => notify.info(tI18n('dental.templates_future'))}
    />;
  const renderReports = () =>
    <DentalReportsTab
      savedVisitProtocols={savedVisitProtocols as unknown as Array<{ visit_id: string | number; patient_name: string; saved_at: string; visitData?: Record<string, unknown> }>}
      onReopenProtocol={reopenVisitProtocol as unknown as (protocol: { visit_id: string | number; patient_name: string; saved_at: string; visitData?: Record<string, unknown> }) => void}
      patients={patients as unknown as Array<Record<string, unknown>>}
      diagnoses={[]}
    />;
  const renderDentalChart = () =>
  <div className="dental-flex-col dental-gap-24">
      <Card padding="large">
        <h3 className="dental-text-primary">{tI18n('dental.dental_panel_chart_title')}</h3>
        <p className="dental-text-desc dental-text-secondary">
          {tI18n('dental.dental_panel_chart_subtitle')}
        </p>

        <div className="dental-grid-auto-fill-250">
          {patients.map((patient) =>
        <div
          key={patient.id}
          role="button"
          tabIndex={0}
          aria-label={tI18n('dental.dental_panel_aria_chart')}
          className="dental-card-btn"
          onClick={() => handleDentalChart(patient)}
          onKeyDown={(event: React.KeyboardEvent<HTMLElement>) => handleCardKeyDown(event, () => handleDentalChart(patient))}
          onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
          }}
          onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
            e.currentTarget.style.background = 'transparent';
          }}>

              <div className="dental-flex dental-gap-12">
                <div className="dental-icon-bg dental-icon-bg-blue dental-icon-bg-full">
                  <span className="dental-text-value dental-text-white">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="dental-text-primary">{patient.name}</p>
                  <p className="dental-text-desc dental-text-secondary">{tI18n('dental.dental_panel_chart_action')}</p>
                </div>
              </div>
            </div>
        )}
        </div>
      </Card>
    </div>;


  // Рендер планов лечения


  const renderAIAssistant = () =>
  <div className="dental-flex-col dental-gap-24">
      <Card padding="large">
        <h3 className="dental-text-primary">{tI18n('dental.dental_panel_ai_title')}</h3>
        <AIAssistant
        specialty="dentistry"
        onSuggestionSelect={(type, suggestion) => {
          logger.info('[Dentistry] AI suggestion:', { type, suggestion });
          if (type === 'icd10') {
            notify.success(tI18n('dental.icd_added_from_ai'));
          }
        }} />

      </Card>
    </div>;


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

  const selectedPatientId: string | number | undefined = selectedPatient?.patient?.id || selectedPatient?.patient_id || selectedPatient?.id || undefined;
  const selectedPatientDisplayName =
    selectedPatient?.patient_name || selectedPatient?.patient_fio || selectedPatient?.name || tI18n('dental.dental_panel_patient_default');

  return (
    <div className="dentist-panel dental-text-primary">
      {renderContent()}

      {/* Модальные окна */}
      {showPatientCard && selectedPatient &&
      <PatientCard
        patient={selectedPatient as unknown as PatientFormData}
        onSave={(updatedPatient: unknown) => {
          logger.info('Сохранение пациента:', updatedPatient);
          setShowPatientCard(false);
        }}
        onClose={() => setShowPatientCard(false)} />

      }

      {showDiagnosisForm && selectedPatient &&
      <DiagnosisForm
        patientId={selectedPatientId}
        patientName={selectedPatientDisplayName}
        initialData={selectedPatient.diagnosisData}
        onSave={(diagnosisData: unknown) => {
          logger.info('Сохранение диагнозов:', diagnosisData);
          setShowDiagnosisForm(false);
        }}
        onClose={() => setShowDiagnosisForm(false)} />

      }

      {showVisitProtocol && (selectedPatient || protocolTemplateDraft) &&
      <VisitProtocol
        patientId={((selectedPatient || protocolTemplateDraft)?.patient_id as string | number | undefined) || selectedPatientId}
        patientName={(selectedPatient || protocolTemplateDraft)?.patient_name || selectedPatientDisplayName}
        visitId={((selectedPatient || protocolTemplateDraft)?.visit_id as string | number | undefined) || (selectedPatient?.visit_id as string | number | undefined)}
        initialData={((selectedPatient || protocolTemplateDraft)?.visitData as Record<string, unknown> | null | undefined) || (selectedPatient?.visitData as Record<string, unknown> | null | undefined)}
        onSave={async (visitData: unknown) => {
          logger.info('Сохранение протокола визита:', visitData);
          await persistVisitProtocol(selectedPatient || protocolTemplateDraft, visitData as Record<string, unknown>);
          setShowVisitProtocol(false);
          setProtocolTemplateDraft(null);
        }}
        onComplete={handleCompleteVisit}
        onClose={() => {
          setShowVisitProtocol(false);
          setProtocolTemplateDraft(null);
        }} />

      }

      {showPhotoArchive && selectedPatient &&
      <PhotoArchive
        patientId={selectedPatientId as string | number}
        patientName={selectedPatientDisplayName}
        initialData={selectedPatient.photoArchive}
        onSave={(archiveData: unknown) => {
          logger.info('Сохранение фото архива:', archiveData);
          setShowPhotoArchive(false);
        }}
        onClose={() => setShowPhotoArchive(false)} />

      }

      {showProtocolTemplates &&
      <ProtocolTemplates
        onSelectTemplate={handleProtocolTemplateSelect as unknown as (template: unknown) => void}
        onClose={() => setShowProtocolTemplates(false)} />

      }

      {showReports &&
      <Suspense
        fallback={
          <Card role="status" aria-live="polite" className="dental-lazy-fallback">
            {tI18n('dental.dental_panel_reports_loading')}
          </Card>
        }>
        <LazyReportsAndAnalytics
        patientId={selectedPatient?.id}
        doctorId={user?.id}
        clinicId={user?.clinic_id as string | number | null | undefined}
        initialData={null}
        onSave={(reportData) => {
          logger.info('Сохранение отчета:', reportData);
          setShowReports(false);
        }}
          onClose={() => setShowReports(false)} />
      </Suspense>

      }

      {showDentalChart && selectedPatient &&
      <div className="dental-modal-overlay">
          <div className="dental-modal-card-xl">
            <div className="dental-flex-between-16">
              <h2 className="dental-heading-xl dental-text-primary">
                {tI18n('dental.dental_panel_chart_modal_title', { name: selectedPatientDisplayName })}
              </h2>
              <button
              onClick={() => setShowDentalChart(false)}
              aria-label={tI18n('dental.dental_panel_chart_modal_close', { name: selectedPatientDisplayName })}
              className="dental-text-desc dental-text-secondary"
              onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.color = 'var(--mac-text-primary)';
                e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.color = 'var(--mac-text-secondary)';
                e.currentTarget.style.backgroundColor = 'transparent';
              }}>

                <XCircle className="dental-icon-20" />
              </button>
            </div>
            <TeethChart
            patientId={selectedPatientId}
            initialData={(dentalChartData ?? {}) as Record<string, { status?: string; updatedAt?: string; [key: string]: unknown }>}
            onToothClick={(toothNumber, toothData) => {
              logger.info('Клик по зубу:', toothNumber, toothData);
              setSelectedTooth({ number: toothNumber, data: toothData });
              setToothModalOpen(true);
            }}
            readOnly={false} />

          </div>
        </div>
      }

      {showTreatmentPlanner && selectedPatient &&
      <div className="dental-modal-overlay">
          <div className="dental-modal-card-xl">
            <div className="dental-flex-between-16">
              <h2 className="dental-heading-xl dental-text-primary">
                {tI18n('dental.dental_panel_plan_modal_title', { name: selectedPatientDisplayName })}
              </h2>
              <button
              onClick={() => setShowTreatmentPlanner(false)}
              aria-label={tI18n('dental.dental_panel_plan_modal_close', { name: selectedPatientDisplayName })}
              className="dental-text-desc dental-text-secondary"
              onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.color = 'var(--mac-text-primary)';
                e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
                e.currentTarget.style.color = 'var(--mac-text-secondary)';
                e.currentTarget.style.backgroundColor = 'transparent';
              }}>

                <XCircle className="dental-icon-20" />
              </button>
            </div>
            <TreatmentPlanner
            patientId={selectedPatientId}
            visitId={(selectedPatient.visit_id as string | number | undefined)}
            teethData={dentalChartData || {}}
            onUpdate={() => {
              logger.info('План лечения обновлен');
            }} />

          </div>
        </div>
      }

      {/* C-2 cleanup (UI_AUDIT_PLAN.md): inline examination modal removed —
           unreachable dead cluster (see git history / renderExaminations note). */}

      {/* Phase 4+ cleanup: treatment + prosthetic forms removed (dead UI) */}

      {/* Модальное окно для работы с зубом */}
      {toothModalOpen && selectedTooth &&
      <ToothModal
        open={toothModalOpen}
        onClose={() => {
          setToothModalOpen(false);
          setSelectedTooth(null);
        }}
        toothNumber={(selectedTooth as { number?: string | number } | null | undefined)?.number}
        toothData={(selectedTooth as { data?: Record<string, unknown> } | null | undefined)?.data}
        onSave={(data: unknown) => {
          logger.info('Сохранение данных зуба:', data);
          // Обновляем данные зубной карты
          setDentalChartData((prev) => ({
            ...prev,
            [(selectedTooth as { number?: string | number })?.number ?? '']: data
          }));
          setToothModalOpen(false);
        }}
        patientId={selectedPatient?.id}
        visitId={(selectedPatient?.visit_id as string | number | undefined)} />

      }

      {/* DentalPriceManager Modal */}
      {showPriceManager && selectedServiceForPrice &&
      <DentalPriceManager
        visitId={(selectedPatient?.visit_id as string | number | undefined)}
        serviceId={selectedServiceForPrice.id}
        serviceName={selectedServiceForPrice.name}
        originalPrice={selectedServiceForPrice.price}
        isOpen={showPriceManager}
        onClose={() => {
          setShowPriceManager(false);
          setSelectedServiceForPrice(null);
        }}
        onPriceSet={(priceData) => {
          logger.info('Price set:', priceData);
          // Можно добавить логику обновления состояния
        }} />

      }

      {/* Модальное окно Schedule Next */}
      {scheduleNextModal.open &&
      <ScheduleNextModal
        isOpen={scheduleNextModal.open}
        onClose={() => setScheduleNextModal({ open: false, patient: null })}
        patient={(scheduleNextModal.patient ?? undefined) as Record<string, unknown> | undefined}
        theme={{ isDark, getColor, getSpacing, getFontSize }}
        specialtyFilter="dentistry" />

      }
      {/* X-13: AIChatWidget removed — AiTab in sidebar provides the same functionality */}


      {/* C-1 (UX audit): portal-mounted ConfirmDialog */}
      {confirmDialog}

      {/* C-2 (UX audit): session timeout warning dialog */}
      {sessionWarning && (
        <SessionWarningModal
          visible={!!sessionWarning}
          onDismiss={() => setSessionWarning(null)}
          onExtend={() => notify.info(tI18n('dental.session_extending'))}
        />
      )}
    </div>);

};

export default DentistPanelUnified;
