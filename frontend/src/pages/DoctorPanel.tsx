import { useState } from 'react';
import '../styles/dark-theme-visibility-fix.css';
import AIAssistant from '../components/ai/AIAssistant';
import { Button, Card, CardContent, CardHeader, AnimatedTransition } from '../components/ui/macos';
import './doctor.css';
import '../styles/animations.css';
import {
  Activity,
  Calendar,
  Download,
  FileText,
  Heart,
  Pill } from
'lucide-react';

// ✅ УЛУЧШЕНИЕ: Универсальные хуки для устранения дублирования
import { useTouchDevice } from '../hooks/useEnhancedMediaQuery';
import useDoctorQueue from '../hooks/useDoctorQueue';
// i18n-unification: useTranslation hook from unified i18n (replaces adapter shim)
import { useTranslation } from '../i18n/useTranslation';
// UX Audit Doctor H-30: import DoctorQueuePanel instead of inline queue rendering.
import DoctorQueuePanel from '../components/doctor/DoctorQueuePanel';
// PR-UI-15 (plan item 5): локальный ErrorBoundary вокруг контента вкладок
// (registrar 13-4 / cashier 14-5 precedent).
import ErrorBoundary from '../components/common/ErrorBoundary';
import useModal from '../hooks/useModal';
import logger from '../utils/logger';
// PR-UI-15-1: types/status maps + tab & data lifecycle extracted to ./doctor/*
// (registrar/cashier decomposition precedent).
import type { PatientRecord } from './doctor/doctorStatus';
import { useDoctorTabState } from './doctor/useDoctorTabState';
import { useDoctorPanelData } from './doctor/useDoctorPanelData';
// PR-UI-15-2: styles hook + presentation-only view-model + verbatim views.
import { useDoctorStyles } from './doctor/useDoctorStyles';
import { filterAppointments, filterPatients } from './doctor/doctorViewmodel';
import DoctorTabsNav from './doctor/views/DoctorTabsNav';
import DoctorDashboardTab from './doctor/views/DoctorDashboardTab';
import DoctorPatientsTab from './doctor/views/DoctorPatientsTab';
import DoctorAppointmentsTab from './doctor/views/DoctorAppointmentsTab';
import DoctorPatientInfo from './doctor/views/DoctorPatientInfo';
import DoctorDialogsLayer from './doctor/views/DoctorDialogsLayer';

const DoctorPanel = () => {
  const { t: rawT } = useTranslation();
  const t = rawT;
  const isTouchDevice = useTouchDevice();
  // UX Audit Doctor L-43: isTouchDevice used for disabling hover on touch.
  void isTouchDevice;

  // PR-UI-15-2: all DoctorPanel style objects + resolved theme colors,
  // extracted verbatim to ./doctor/useDoctorStyles.
  const styles = useDoctorStyles();
  const { isMobile, isTablet, pageStyle, contentStyle } = styles;

  // PR-UI-15-1: tab/URL/filter view-state slice (verbatim port).
  const {
    activeTab,
    setActiveTab,
    setDoctorTab,
    searchQuery,
    setSearchQuery,
    filterStatus,
    setFilterStatus,
  } = useDoctorTabState();

  // ✅ УЛУЧШЕНИЕ: Универсальный хук вместо дублированных состояний
  // Cast to a typed shape — useModal is generic-free (selectedItem: null),
  // so we narrow it here for type-safe access in this panel.
  const patientModal = useModal() as unknown as {
    isOpen: boolean;
    isAnimating: boolean;
    selectedItem: PatientRecord | null;
    loading: boolean;
    openModal: (item: PatientRecord | Record<string, unknown> | null) => void;
    closeModal: () => void;
    toggleModal: (item?: PatientRecord | Record<string, unknown> | null) => void;
    setModalLoading: (isLoading: boolean) => void;
  };

  // PR-UI-15-1: data lifecycle (patients/appointments/loading/error +
  // specialty + schedule-next refresh + ?patientId deep-link) — verbatim port.
  const {
    patients,
    appointments,
    loading,
    loadError,
    loadData,
    appointmentStats,
    doctorSpecialty,
    handleScheduleNextSuccess,
  } = useDoctorPanelData({
    t,
    setSearchQuery,
    setActiveTab,
    openPatientModal: patientModal.openModal,
  });
  const [scheduleNextModal, setScheduleNextModal] = useState<{ open: boolean; patient: Record<string, unknown> | null }>({ open: false, patient: null });

  // ✅ НОВОЕ: Получаем данные текущего пользователя и очереди
  // PR-UI-15-1: канонический деструктор сокращён до живых значений —
  // остальные поля (queue/loading/error/loadQueue/callNext/markNoShow/
  // restoreToNext/sendToDiagnostics/markIncomplete/completeVisit) были
  // definition-only в панели (queue-действия живут в DoctorQueuePanel +
  // useDoctorQueue). canCallNext сохранён: SSOT-контракт
  // DoctorPanels.contract.test.tsx ожидает его в DoctorPanel.tsx.
  const {
    stats: queueStats,
    canCallNext,
  } = useDoctorQueue(doctorSpecialty);
  void canCallNext;

  // PR-UI-15-2: presentation-only filters moved verbatim to
  // ./doctor/doctorViewmodel.
  const filteredPatients = filterPatients(patients, searchQuery, filterStatus);
  const filteredAppointments = filterAppointments(appointments, searchQuery, filterStatus);

  // ✅ УЛУЧШЕНИЕ: Обработчик с универсальным хуком
  const handlePatientClick = (patient: PatientRecord | Record<string, unknown> | null) => {
    patientModal.openModal(patient);
  };

  // Рендер
  return (
    <div style={pageStyle}>

      {/* Основной контент */}
      <main style={contentStyle}>
        {/* Вкладки — PR-UI-15-2: verbatim JSX moved to views/DoctorTabsNav */}
        <DoctorTabsNav
          activeTab={activeTab}
          setDoctorTab={setDoctorTab}
          queueStatsWaiting={queueStats.waiting}
          styles={styles}
          t={t} />

        {/* Контент вкладок — PR-UI-15 (plan item 5): локальный ErrorBoundary
            вокруг контента вкладок (падение рендера любого таба не уронит
            всю страницу врача; registrar 13-4 / cashier 14-5 precedent).
            Codex P2 (#2926): key={activeTab} сбрасывает boundary при смене
            вкладки — упавший таб не «отравляет» здоровые (без key
            hasError сохранялся бы до ручного Retry). */}
        <ErrorBoundary key={activeTab}>
          {activeTab === 'dashboard' &&
          <DoctorDashboardTab
            patientsCount={patients.length}
            appointmentStats={appointmentStats}
            styles={styles} />
          }

          {activeTab === 'patients' &&
          <DoctorPatientsTab
            filteredPatients={filteredPatients}
            loading={loading}
            loadError={loadError}
            searchQuery={searchQuery}
            onSearchQueryChange={setSearchQuery}
            filterStatus={filterStatus}
            onFilterStatusChange={setFilterStatus}
            onPatientClick={handlePatientClick}
            onRetry={loadData}
            styles={styles}
            t={t} />
          }

          {activeTab === 'appointments' &&
          <DoctorAppointmentsTab
            filteredAppointments={filteredAppointments}
            loading={loading}
            loadError={loadError}
            searchQuery={searchQuery}
            onSearchQueryChange={setSearchQuery}
            filterStatus={filterStatus}
            onFilterStatusChange={setFilterStatus}
            onScheduleNext={() => setScheduleNextModal({ open: true, patient: null })}
            onRetry={loadData}
            styles={styles}
            t={t} />
          }

          {/* UX Audit Doctor H-30: inline queue replaced with DoctorQueuePanel component. */}
          {activeTab === 'queue' &&
          <AnimatedTransition type="fade" delay={100}>
            <DoctorQueuePanel
              specialty={doctorSpecialty}
              onPatientSelect={(entry: Record<string, unknown>) => {
                // Open patient modal when selecting from queue
                handlePatientClick(entry);
              }}
            />
          </AnimatedTransition>
          }

          {activeTab === 'ai' &&
          <AnimatedTransition type="fade" delay={100}>
            <Card>
              <CardHeader>
                <h2 className="doctor-section-title">
                  AI Помощник врача
                </h2>
              </CardHeader>
              <CardContent>
                <AIAssistant
                  specialty={doctorSpecialty}
                  onSuggestionSelect={(type: string, suggestion: unknown) => {
                    logger.log('AI предложение для общего врача:', type, suggestion);
                  }} />

              </CardContent>
            </Card>
          </AnimatedTransition>
          }

          {activeTab === 'reports' &&
          <AnimatedTransition type="fade" delay={100}>
            <Card>
              <CardHeader>
                <h2 className="doctor-section-title">
                  Отчеты и аналитика
                </h2>
              </CardHeader>
              <CardContent>
                <div className={`doctor-reports-grid doctor-reports-grid-${isMobile ? '1' : isTablet ? '2' : '3'}`}>
                  <Button variant="primary" fullWidth disabled title={t("doctor.feature_in_development")}>
                    <FileText size={20} />
                    Отчет по пациентам
                  </Button>
                  <Button variant="secondary" fullWidth disabled title={t("doctor.feature_in_development")}>
                    <Calendar size={20} />
                    Отчет по записям
                  </Button>
                  <Button variant="secondary" color="success" fullWidth disabled title={t("doctor.feature_in_development")}>
                    <Activity size={20} />
                    Статистика работы
                  </Button>
                  <Button variant="secondary" color="warning" fullWidth disabled title={t("doctor.feature_in_development")}>
                    <Pill size={20} />
                    Отчет по лекарствам
                  </Button>
                  <Button variant="secondary" color="info" fullWidth disabled title={t("doctor.feature_in_development")}>
                    <Heart size={20} />
                    Медицинская статистика
                  </Button>
                  <Button variant="ghost" fullWidth disabled title={t("doctor.feature_in_development")}>
                    <Download size={20} />
                    Экспорт всех данных
                  </Button>
                </div>
              </CardContent>
            </Card>
          </AnimatedTransition>
          }
        </ErrorBoundary>
      </main>

      {/* ✅ УЛУЧШЕНИЕ: Модальное окно пациента с универсальным хуком —
          PR-UI-15-2: verbatim JSX moved to views/DoctorPatientInfo */}
      {patientModal.isOpen && patientModal.selectedItem &&
      <DoctorPatientInfo
        patient={patientModal.selectedItem}
        onClose={patientModal.closeModal}
        t={t} />
      }

      {/* Модальные окна + AI-виджеты — PR-UI-15-2: verbatim JSX moved to
          views/DoctorDialogsLayer (ScheduleNextModal + AIChatWidget +
          RoleNotificationCenter). */}
      <DoctorDialogsLayer
        scheduleNextModalOpen={scheduleNextModal.open}
        scheduleNextModalPatient={scheduleNextModal.patient}
        onScheduleNextClose={() => setScheduleNextModal({ open: false, patient: null })}
        onScheduleNextSuccess={handleScheduleNextSuccess as (result?: unknown, formData?: Record<string, unknown>) => void}
        doctorSpecialty={doctorSpecialty} />
    </div>);

};

export default DoctorPanel;
