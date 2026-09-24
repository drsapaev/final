import { useCallback, useRef } from 'react';

import notify from '../../services/notify';
import logger from '../../utils/logger';
import { apiClient } from '../../api/client';
import { queueService } from '../../services/queue';
import { printPanelTicket } from '../../services/panelPrint';
import { getErrorMessage } from '../../utils/type-guards';
import type { Appointment } from '../../types/domain/clinic';
import { SPECIALTY_KEYS } from '../../utils/doctorPanelShared';
import {
  resolveDoctorQueueEntryId,
  type SelectedPatient,
} from './dentistContracts';

/**
 * PR-UI-15-5: the dentist business-action handler slice extracted verbatim
 * from pages/DentistPanelUnified.tsx (registrar/cashier decomposition
 * precedent: useRegistrarRowActions / useCashierActions — deps-object hook,
 * verbatim handler bodies, panel stays the single composition point).
 *
 * Owns:
 *  - resolvePatientId / resolvePatientName (patient field normalization)
 *  - appointment-table handlers: handleAppointmentRowClick +
 *    handleAppointmentActionClick (view / call / payment / print / complete)
 *  - handlePatientSelect (queue → visit tab routing with no-visit guard)
 *  - C-3 critical ICD-10 gate: CRITICAL_ICD10_CODES (K04/K10) +
 *    getCriticalDiagnosisWarning (prefix matching)
 *  - handleCompleteVisit (tiered confirm C-1 + C-3 danger intent,
 *    queueService.completeVisit + callNextWaiting auto-invite)
 *  - dialog-opening patient handlers: handleDiagnosis / handleVisitProtocol /
 *    handlePhotoArchive / handleProtocolTemplates / handleReports /
 *    handleDentalChart / handleTreatmentPlanner
 *  - protocol-template drafting: buildVisitProtocolDraftFromTemplate +
 *    handleProtocolTemplateSelect
 *
 * NOT extracted (remain in the panel): handleCardKeyDown (render-adjacent),
 * the URL deep-link patient effect (location-bound), session warning /
 * hotkeys wiring, stats and render functions (PR-UI-15-6 surface).
 */

export type UseDentistActionsParams = {
  tI18n: (key: string, params?: Record<string, unknown>) => string;
  confirm: (options: Record<string, unknown>) => Promise<boolean>;
  setLoading: (value: boolean) => void;
  selectedPatient: SelectedPatient | null;
  setSelectedPatient: (patient: SelectedPatient | Record<string, unknown> | null) => void;
  handleTabChange: (tab: string) => void;
  ensureCanonicalVisitId: (row: Appointment | Record<string, unknown>) => Promise<string | number | null>;
  loadDentistryAppointments: (forceRefresh?: boolean) => Promise<Appointment[]>;
  loadDentistVisitProtocolByVisitId: (
    visitId: string | number,
    patient: SelectedPatient | Record<string, unknown> | null,
  ) => Promise<Record<string, unknown> | null>;
  setShowDiagnosisForm: (value: boolean) => void;
  setShowVisitProtocol: (value: boolean) => void;
  setShowPhotoArchive: (value: boolean) => void;
  setShowProtocolTemplates: (value: boolean) => void;
  setShowReports: (value: boolean) => void;
  setShowDentalChart: (value: boolean) => void;
  setShowTreatmentPlanner: (value: boolean) => void;
  setDentalChartData: (value: Record<string, unknown> | null) => void;
  setProtocolTemplateDraft: (value: SelectedPatient | null) => void;
};

export function useDentistActions({
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
}: UseDentistActionsParams) {
  const resolvePatientId = useCallback((patient: SelectedPatient | Record<string, unknown> | null | undefined) => {
    const record = (patient ?? {}) as Record<string, unknown>;
    const nestedPatient = record.patient as { id?: string | number; [k: string]: unknown } | undefined;
    return nestedPatient?.id || record.patient_id || record.id || null;
  }, []);

  const resolvePatientName = useCallback((patient: SelectedPatient | Record<string, unknown> | null | undefined) => {
    const record = (patient ?? {}) as Record<string, unknown>;
    return (record.patient_name as string) || (record.patient_fio as string) || (record.name as string) || tI18n('dental.dental_panel_patient_default');
  }, [tI18n]);

  // Обработчики для таблицы записей
  const handleAppointmentRowClick = async (row: Appointment) => {
    // Можно открыть детали записи или переключиться на прием
    if (row.patient_fio) {
      const visitId = await ensureCanonicalVisitId(row);
      if (!visitId) {
        logger.warn('[Dentist] Could not resolve canonical visit id');
        return;
      }

      // Создаем объект пациента для переключения на прием
      const patientData: SelectedPatient = {
        id: row.id,
        appointment_id: (row.appointment_id as string | number | null | undefined) || null,
        visit_id: visitId,
        patient_name: row.patient_fio,
        phone: row.patient_phone || (row.phone as string) || '',
        number: row.id,
        doctor_queue_entry_id: resolveDoctorQueueEntryId(row as Record<string, unknown>),
        source: 'appointments'
      };
      setSelectedPatient(patientData);
      handleTabChange('visit');
    }
  };

  const handleAppointmentActionClick = async (action: string, row: Appointment, event: React.MouseEvent<HTMLElement>) => {
    event.stopPropagation();

    switch (action) {
      case 'view':
        await handleAppointmentRowClick(row);
        break;
      case 'call':
        // Вызвать пациента
        try {
          const queueEntryId = resolveDoctorQueueEntryId(row as Record<string, unknown>);
          if (queueEntryId === null) {
            logger.warn('[Dentist] Cannot start visit without queue entry id');
            notify.error(tI18n('dental.no_queue_id_for_visit'));
            break;
          }
          const response = await apiClient.post(`/doctor/queue/${queueEntryId}/start-visit`);

          if (response.status < 400) {
            logger.info('[Dentist] Queue entry started');
            await loadDentistryAppointments(true);
          }
        } catch {
          logger.error('[Dentist] Failed to start queue entry');
        }
        break;
      case 'payment':
        notify.info(tI18n('dental.dental_panel_payment_todo', { name: row.patient_fio }));
        break;
      case 'print':
        try {
          const printResult = await printPanelTicket(row as Record<string, unknown>, {
            specialtyName: tI18n('dental.dental_panel_specialty_name')
          }) as { message?: string } | undefined;
          notify.success(printResult?.message || tI18n('dental.dental_panel_ticket_printed', { name: row.patient_fio }));
        } catch (error: unknown) {
          logger.error('[Dentist] Failed to print ticket');
          notify.error(getErrorMessage(error) || tI18n('dental.dental_panel_ticket_print_failed'));
        }
        break;
      case 'complete':
        // Завершить приём
        try {
          const visitId = await ensureCanonicalVisitId(row);
          if (!visitId) {
            logger.warn('[Dentist] Cannot open visit without canonical visit id');
            break;
          }

          const patient: SelectedPatient = {
            id: row.id,
            appointment_id: (row.appointment_id as string | number | null | undefined) || null,
            visit_id: visitId,
            patient_name: row.patient_fio,
            phone: row.patient_phone || (row.phone as string) || '',
            number: row.id,
            doctor_queue_entry_id: resolveDoctorQueueEntryId(row as Record<string, unknown>),
            source: 'appointments',
            status: 'in_cabinet'
          };
          setSelectedPatient(patient);
          handleTabChange('visit');
        } catch {
          logger.error('[Dentist] Failed to open visit for completion');
        }
        break;
      case 'edit':
        // Логика редактирования записи
        break;
      case 'cancel':
        // Логика отмены записи
        break;
      default:
        break;
    }
  };

  // Обработчики
  const handlePatientSelect = (patient: SelectedPatient | Record<string, unknown> | null) => {
    const normalizedPatient: SelectedPatient = {
      ...(patient as Record<string, unknown>),
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    } as SelectedPatient;
    setSelectedPatient(normalizedPatient);

    if (normalizedPatient.visit_id) {
      handleTabChange('visit');
      return;
    }

    notify.info(tI18n('dental.no_active_visit'));
    handleTabChange('patients');
  };

  // C-3 (UX audit, port of cardio P-020): critical ICD-10 codes that require
  // secondary confirmation before the visit can be completed. These are
  // dental diagnoses with high clinical stakes — an erroneous entry could
  // trigger unnecessary surgical intervention, hospitalization, or IV
  // antibiotics. The doctor must explicitly confirm when one of these codes
  // is present in the visit's icd10 field.
  const CRITICAL_ICD10_CODES = useRef(['K04', 'K10']).current;

  const getCriticalDiagnosisWarning = useCallback(
    (icd10Code: unknown) => {
      if (!icd10Code || typeof icd10Code !== 'string') return null;
      const code = icd10Code.trim().toUpperCase();
      // Match by prefix (e.g. "K04" matches "K04.0", "K04.9", "K049")
      for (const prefix of CRITICAL_ICD10_CODES) {
        if (code.startsWith(prefix)) {
          return {
            code: prefix,
            label: tI18n(`dental.dental_panel_critical_${prefix}`),
            fullCode: code,
          };
        }
      }
      return null;
    },
    [CRITICAL_ICD10_CODES, tI18n]
  );

  // Завершение визита
  //
  // Унифицированная функция завершения приёма для стоматолога.
  // Следует тому же контракту, что и Cardiologist/Dermatologist:
  //   1. resolveDoctorQueueEntryId(selectedPatient) — canonical entry id
  //   2. queueService.completeVisit(entryId, payload) — POST /doctor/queue/{id}/complete
  //   3. Сброс состояния и возврат на вкладку очереди
  //   4. callNextWaiting('dentistry') — автовызов следующего пациента
  //
  // Контракт SSOT (DoctorPanels.contract.test.jsx) требует:
  //   - НЕ использовать row.id / selectedPatient.id напрямую
  //   - НЕ использовать /registrar/queue/${...}/start-visit
  //   - использовать resolveDoctorQueueEntryId + /doctor/queue/${queueEntryId}/complete
  const handleCompleteVisit = async (latestDraft?: Record<string, unknown>) => {
    if (!selectedPatient) {
      notify.error(tI18n('dental.no_patient_for_complete'));
      return;
    }

    const queueEntryId = resolveDoctorQueueEntryId(selectedPatient);
    if (queueEntryId === null) {
      logger.warn('[Dentistry] Cannot complete visit without queue entry id');
      notify.error(tI18n('dental.no_queue_id_for_complete'));
      return;
    }

    if (!latestDraft) {
      notify.error(tI18n('dental2.visit_protocol_save_failed'));
      return;
    }

    // C-1 + C-3 (UX audit): tiered confirmation before completing the visit.
    // C-3: if the ICD-10 code matches a critical dental diagnosis (K04 —
    // pulp/periapical diseases, K10 — jaw diseases including osteomyelitis
    // and abscess), we show the strongest warning (intent='danger') and
    // require explicit confirmation. This prevents accidental entry of a
    // diagnosis that could trigger unnecessary surgical intervention,
    // hospitalization, or IV antibiotics.
    const icd10ForCheck = String(latestDraft.icd10_code || latestDraft.icd10 || latestDraft.icdCode || '');
    const criticalWarning = getCriticalDiagnosisWarning(icd10ForCheck);

    let confirmOptions;
    if (criticalWarning) {
      confirmOptions = {
        title: tI18n('dental.dental_panel_critical_title', { label: criticalWarning.label, code: criticalWarning.code }),
        message: tI18n('dental.dental_panel_critical_message', { fullCode: criticalWarning.fullCode, label: criticalWarning.label }),
        description: tI18n('dental.dental_panel_critical_description'),
        confirmLabel: tI18n('dental.dental_panel_critical_confirm'),
        cancelLabel: tI18n('dental.dental_panel_critical_cancel'),
        intent: 'danger',
      };
    } else {
      confirmOptions = {
        title: tI18n('dental.dental_panel_complete_title'),
        message: tI18n('dental.dental_panel_complete_message'),
        description: tI18n('dental.dental_panel_complete_description'),
        confirmLabel: tI18n('dental.dental_panel_complete_confirm'),
        cancelLabel: tI18n('dental.dental_panel_complete_cancel'),
        intent: 'primary',
      };
    }

    const ok = await confirm(confirmOptions);
    if (!ok) {
      return;
    }

    try {
      setLoading(true);
      logger.info('[Dentistry] Completing queue visit');

      const patientId =
        selectedPatient?.patient?.id ||
        selectedPatient?.patient_id ||
        selectedPatient?.id ||
        null;

      // Минимальный payload: стоматолог использует EMR v2 для протокола визита,
      // а в queue completeVisit передаём только ключевые поля для закрытия очереди.
      const visitPayload = {
        patient_id: patientId,
        complaint: latestDraft.anamnesis_morbi || latestDraft.complaints || latestDraft.chiefComplaint || latestDraft.complaint || '',
        diagnosis: latestDraft.diagnosis || '',
        icd10: latestDraft.icd10_code || latestDraft.icd10 || latestDraft.icdCode || '',
        services: [],
        notes: latestDraft.recommendations || latestDraft.notes || '',
      };

      await queueService.completeVisit(queueEntryId, visitPayload);
      logger.info('[Dentistry] Queue visit completed');
      notify.success(tI18n('dental.visit_completed'));

      // Сброс состояния
      setSelectedPatient(null);
      setShowVisitProtocol(false);
      setProtocolTemplateDraft(null);
      handleTabChange('queue');

      // Автовызов следующего пациента по стоматологии
      try {
        const next = await queueService.callNextWaiting(SPECIALTY_KEYS.DENTISTRY);
        if (next?.success && next?.entry?.number) {
          notify.success(tI18n('dental.dental_panel_next_patient_called', { number: next.entry.number }));
        }
      } catch {
        logger.warn('[Dentistry] Failed to call next queue entry');
        // Не блокируем UI: визит уже завершён, просто информируем
      }
    } catch (error: unknown) {
      logger.error('[Dentistry] Failed to complete queue visit');
      notify.error(
        getErrorMessage(error) || tI18n('dental.dental_panel_complete_failed')
      );
    } finally {
      setLoading(false);
    }
  };

  const handleDiagnosis = (patient: SelectedPatient | Record<string, unknown> | null) => {
    setSelectedPatient({
      ...(patient as Record<string, unknown>),
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    } as SelectedPatient);
    setShowDiagnosisForm(true);
  };

  const handleVisitProtocol = async (patient: SelectedPatient | Record<string, unknown> | null) => {
    const patientRecord = (patient ?? {}) as Record<string, unknown>;
    const visitId = (patientRecord.visit_id as string | number | null | undefined) || await ensureCanonicalVisitId(patientRecord);
    if (!visitId) {
      notify.error(tI18n('dental.protocol_needs_visit_id'));
      return;
    }

    const backendProtocol = await loadDentistVisitProtocolByVisitId(visitId, patient);
    const backendRecord = (backendProtocol ?? {}) as Record<string, unknown>;
    setSelectedPatient({
      ...(patient as Record<string, unknown>),
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient),
      visit_id: visitId,
      visitData: (backendRecord.visitData as Record<string, unknown> | null) || (patientRecord.visitData as Record<string, unknown> | null) || null,
      source: (backendRecord.source as string) || (patientRecord.source as string) || 'appointments',
    } as SelectedPatient);
    setShowVisitProtocol(true);
  };

  const handlePhotoArchive = (patient: SelectedPatient | Record<string, unknown> | null) => {
    setSelectedPatient({
      ...(patient as Record<string, unknown>),
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    } as SelectedPatient);
    setShowPhotoArchive(true);
  };

  const handleProtocolTemplates = () => {
    setShowProtocolTemplates(true);
  };

  const buildVisitProtocolDraftFromTemplate = useCallback((template: Record<string, unknown> | null) => {
    if (!template) {
      return null;
    }

    const templatePhotos = template.photos as Array<Record<string, unknown>> | undefined;
    const templateSteps = template.steps as Array<Record<string, unknown> | string> | undefined;
    const templateMaterials = template.materials as Array<Record<string, unknown>> | undefined;
    const templateAnesthesia = template.anesthesia as Array<Record<string, unknown>> | undefined;
    const templatePrescriptions = template.prescriptions as Array<Record<string, unknown>> | undefined;

    const mapPhotoList = (type: string) => (
      Array.isArray(templatePhotos)
        ? templatePhotos.filter((photo) => photo?.type === type).map((photo: Record<string, unknown>, index: number) => ({
          id: `${type}-${index}-${Date.now()}`,
          url: '',
          filename: (photo.description as string) || `${type} photo ${index + 1}`,
          size: 0,
          type,
          uploadedAt: new Date().toISOString(),
          description: (photo.description as string) || '',
        }))
        : []
    );

    return {
      chiefComplaint: (template.description as string) || (template.name as string) || '',
      historyOfPresentIllness: (template.description as string) || '',
      procedures: Array.isArray(templateSteps)
        ? templateSteps.map((step: Record<string, unknown> | string, index: number) => ({
          name: typeof step === 'string' ? step : (step?.name as string) || tI18n('dental.dental_panel_step_label', { index: index + 1 }),
          teeth: '',
          notes: '',
          duration: typeof step === 'object' && step !== null ? (step as Record<string, unknown>).duration as number || 0 : 0,
        }))
        : [],
      materials: Array.isArray(templateMaterials)
        ? templateMaterials.map((material: Record<string, unknown>) => ({
          name: (material?.name as string) || '',
          quantity: (material?.quantity as string) || '',
          notes: material?.required ? tI18n('dental.dental_panel_required_material') : '',
        }))
        : [],
      anesthesia: Array.isArray(templateAnesthesia)
        ? templateAnesthesia.map((anesthesia: Record<string, unknown>) => ({
          drug: (anesthesia?.drug as string) || '',
          dose: (anesthesia?.dose as string) || '',
          method: (anesthesia?.method as string) || '',
          required: Boolean(anesthesia?.required),
        }))
        : [],
      photos: {
        before: mapPhotoList('before'),
        during: mapPhotoList('during'),
        after: mapPhotoList('after'),
      },
      radiographs: [],
      prescriptions: Array.isArray(templatePrescriptions)
        ? templatePrescriptions.map((prescription: Record<string, unknown>) => ({
          medication: (prescription?.medication as string) || '',
          dosage: (prescription?.dosage as string) || '',
          instructions: (prescription?.instructions as string) || '',
          required: Boolean(prescription?.required),
        }))
        : [],
      recommendations: (template.aftercare as string) || '',
      nextVisit: { date: '', time: '', purpose: '' },
    };
  }, [tI18n]);

  const handleProtocolTemplateSelect = useCallback((template: Record<string, unknown> | null) => {
    const templateName = (template?.name as string) || tI18n('dental.dental_panel_template_default');
    const currentPatientName = resolvePatientName(selectedPatient);
    const draft: SelectedPatient = {
      patient_id: (selectedPatient?.patient_id as string | number | null) || (selectedPatient?.id as string | number | null) || null,
      patient_name: currentPatientName || tI18n('dental.dental_panel_template_label', { name: templateName }),
      patient_fio: currentPatientName || tI18n('dental.dental_panel_template_label', { name: templateName }),
      visit_id: (selectedPatient?.visit_id as string | number | null) || null,
      source: 'protocol-template',
      visitData: buildVisitProtocolDraftFromTemplate(template),
    };

    setProtocolTemplateDraft(draft);
    setShowProtocolTemplates(false);
    setShowVisitProtocol(true);
  }, [buildVisitProtocolDraftFromTemplate, resolvePatientName, selectedPatient, tI18n, setProtocolTemplateDraft, setShowProtocolTemplates, setShowVisitProtocol]);

  const handleReports = () => {
    setShowReports(true);
  };

  const handleDentalChart = (patient: SelectedPatient | Record<string, unknown> | null) => {
    setSelectedPatient({
      ...(patient as Record<string, unknown>),
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient)
    } as SelectedPatient);
    setDentalChartData((patient as Record<string, unknown>)?.dentalChart as Record<string, unknown> | null | undefined || null);
    setShowDentalChart(true);
  };

  const handleTreatmentPlanner = async (patient: SelectedPatient | Record<string, unknown> | null) => {
    const patientRecord = (patient ?? {}) as Record<string, unknown>;
    const visitId = (patientRecord.visit_id as string | number | null | undefined) || await ensureCanonicalVisitId(patientRecord);
    if (!visitId) {
      notify.error(tI18n('dental.treatment_plan_needs_visit_id'));
      return;
    }

    setSelectedPatient({
      ...(patient as Record<string, unknown>),
      patient_id: resolvePatientId(patient),
      patient_name: resolvePatientName(patient),
      patient_fio: resolvePatientName(patient),
      visit_id: visitId
    } as SelectedPatient);
    setShowTreatmentPlanner(true);
  };

  return {
    resolvePatientId,
    resolvePatientName,
    handleAppointmentRowClick,
    handleAppointmentActionClick,
    handlePatientSelect,
    CRITICAL_ICD10_CODES,
    getCriticalDiagnosisWarning,
    handleCompleteVisit,
    handleDiagnosis,
    handleVisitProtocol,
    handlePhotoArchive,
    handleProtocolTemplates,
    buildVisitProtocolDraftFromTemplate,
    handleProtocolTemplateSelect,
    handleReports,
    handleDentalChart,
    handleTreatmentPlanner,
  };
}
