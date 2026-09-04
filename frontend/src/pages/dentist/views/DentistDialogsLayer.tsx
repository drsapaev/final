import { Suspense, lazy } from 'react';

import { Card } from '../../../components/ui/macos';
import TeethChart from '../../../components/dental/TeethChart';
import ToothModal from '../../../components/dental/ToothModal';
import TreatmentPlanner from '../../../components/dental/TreatmentPlanner';
import PatientCard from '../../../components/dental/PatientCard';
import type { PatientFormData } from '../../../components/dental/PatientCard';
import DentalPriceManager from '../../../components/dental/DentalPriceManager';
import DiagnosisForm from '../../../components/dental/DiagnosisForm';
import VisitProtocol from '../../../components/dental/VisitProtocol';
import PhotoArchive from '../../../components/dental/PhotoArchive';
import ProtocolTemplates from '../../../components/dental/ProtocolTemplates';
import ScheduleNextModal from '../../../components/common/ScheduleNextModal';
import SessionWarningModal from '../../../components/common/SessionWarningModal';
import { XCircle } from 'lucide-react';
import notify from '../../../services/notify';
import logger from '../../../utils/logger';
import { useTheme } from '../../../contexts/ThemeContext';
import type { SelectedPatient } from '../dentistContracts';

const LazyReportsAndAnalytics = lazy(() => import('../../../components/dental/ReportsAndAnalytics'));

/**
 * PR-UI-15-6: the modal/dialog surfaces extracted verbatim from
 * pages/DentistPanelUnified.tsx (registrar/cashier/doctor decomposition
 * precedent — see cashier views/CashierDialogsLayer + doctor views/
 * DoctorDialogsLayer).
 *
 * Owns: patient card, diagnosis form, EMR v2 visit protocol, photo
 * archive, protocol templates, lazy reports analytics, dental chart
 * (TeethChart) + tooth modal, treatment planner, price manager,
 * schedule-next, the C-1 ConfirmDialog portal slot and the C-2 session
 * timeout warning modal.
 */
export type DentistDialogsLayerProps = {
  tI18n: (key: string, params?: Record<string, unknown>) => string;
  user: Record<string, unknown> | null | undefined;
  selectedPatient: SelectedPatient | null;
  protocolTemplateDraft: SelectedPatient | null;
  dentalChartData: Record<string, unknown> | null;
  selectedTooth: { number: string | number; data: unknown } | string | number | null;
  selectedServiceForPrice: { id?: string | number; name?: string; price?: number; [key: string]: unknown } | null;
  scheduleNextModal: { open: boolean; patient: SelectedPatient | Record<string, unknown> | null };
  sessionWarning: { active: boolean } | null;
  confirmDialog: React.ReactNode;
  showPatientCard: boolean;
  showDiagnosisForm: boolean;
  showVisitProtocol: boolean;
  showPhotoArchive: boolean;
  showProtocolTemplates: boolean;
  showReports: boolean;
  showDentalChart: boolean;
  showTreatmentPlanner: boolean;
  showPriceManager: boolean;
  toothModalOpen: boolean;
  setShowPatientCard: (value: boolean) => void;
  setShowDiagnosisForm: (value: boolean) => void;
  setShowVisitProtocol: (value: boolean) => void;
  setShowPhotoArchive: (value: boolean) => void;
  setShowProtocolTemplates: (value: boolean) => void;
  setShowReports: (value: boolean) => void;
  setShowDentalChart: (value: boolean) => void;
  setShowTreatmentPlanner: (value: boolean) => void;
  setShowPriceManager: (value: boolean) => void;
  setToothModalOpen: (value: boolean) => void;
  setSelectedTooth: (value: { number: string | number; data: unknown } | string | number | null) => void;
  setDentalChartData: React.Dispatch<React.SetStateAction<Record<string, unknown> | null>>;
  setSelectedServiceForPrice: (value: { id?: string | number; name?: string; price?: number; [key: string]: unknown } | null) => void;
  setScheduleNextModal: React.Dispatch<
    React.SetStateAction<{ open: boolean; patient: SelectedPatient | Record<string, unknown> | null }>
  >;
  setSessionWarning: (value: { active: boolean } | null) => void;
  setProtocolTemplateDraft: (value: SelectedPatient | null) => void;
  persistVisitProtocol: (
    patient: SelectedPatient | Record<string, unknown> | null,
    visitData: Record<string, unknown>,
  ) => Promise<Record<string, unknown> | undefined>;
  handleCompleteVisit: () => void;
  handleProtocolTemplateSelect: (template: Record<string, unknown> | null) => void;
};

export default function DentistDialogsLayer({
  tI18n,
  user,
  selectedPatient,
  protocolTemplateDraft,
  dentalChartData,
  selectedTooth,
  selectedServiceForPrice,
  scheduleNextModal,
  sessionWarning,
  confirmDialog,
  showPatientCard,
  showDiagnosisForm,
  showVisitProtocol,
  showPhotoArchive,
  showProtocolTemplates,
  showReports,
  showDentalChart,
  showTreatmentPlanner,
  showPriceManager,
  toothModalOpen,
  setShowPatientCard,
  setShowDiagnosisForm,
  setShowVisitProtocol,
  setShowPhotoArchive,
  setShowProtocolTemplates,
  setShowReports,
  setShowDentalChart,
  setShowTreatmentPlanner,
  setShowPriceManager,
  setToothModalOpen,
  setSelectedTooth,
  setDentalChartData,
  setSelectedServiceForPrice,
  setScheduleNextModal,
  setSessionWarning,
  setProtocolTemplateDraft,
  persistVisitProtocol,
  handleCompleteVisit,
  handleProtocolTemplateSelect,
}: DentistDialogsLayerProps) {
  const {
    isDark,
    getColor,
    getSpacing,
    getFontSize
  } = useTheme();

  const doctorId = user?.id as string | number | undefined;
  const clinicId = user?.clinic_id as string | number | null | undefined;
  const selectedPatientId: string | number | undefined = selectedPatient?.patient?.id || selectedPatient?.patient_id || selectedPatient?.id || undefined;
  const selectedPatientDisplayName =
    selectedPatient?.patient_name || selectedPatient?.patient_fio || selectedPatient?.name || tI18n('dental.dental_panel_patient_default');

  return (
    <>
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
        doctorId={doctorId}
        clinicId={clinicId}
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
    </>
  );
}
