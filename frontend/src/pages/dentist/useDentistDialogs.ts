import { useState } from 'react';

import type { SelectedPatient } from './dentistContracts';

/**
 * PR-UI-15-4: the dentist dialog/tooth/price/schedule view-state slice
 * extracted verbatim from pages/DentistPanelUnified.tsx (registrar/cashier
 * decomposition precedent).
 *
 * Kept as plain useState (NOT a useReducer state machine) deliberately:
 * unlike the registrar/cashier dialog clusters, these flags have no
 * cross-field reset shapes or pinned quirks — every dialog opens/closes
 * independently. A reducer would add ceremony without state-machine value.
 */
export function useDentistDialogs() {
  const [showDentalChart, setShowDentalChart] = useState(false);
  const [showTreatmentPlanner, setShowTreatmentPlanner] = useState(false);
  const [showPatientCard, setShowPatientCard] = useState(false);
  const [showDiagnosisForm, setShowDiagnosisForm] = useState(false);
  const [showVisitProtocol, setShowVisitProtocol] = useState(false);
  const [showPhotoArchive, setShowPhotoArchive] = useState(false);
  const [showProtocolTemplates, setShowProtocolTemplates] = useState(false);
  const [showReports, setShowReports] = useState(false);
  // Phase 4+ cleanup: showTreatmentForm/showProstheticForm removed (dead UI).
  const [dentalChartData, setDentalChartData] = useState<Record<string, unknown> | null>(null);

  // Состояние для DentalPriceManager
  const [showPriceManager, setShowPriceManager] = useState(false);
  const [selectedServiceForPrice, setSelectedServiceForPrice] = useState<{ id?: string | number; name?: string; price?: number; [key: string]: unknown } | null>(null);
  const [selectedTooth, setSelectedTooth] = useState<{ number: string | number; data: unknown } | string | number | null>(null);
  const [toothModalOpen, setToothModalOpen] = useState(false);

  // PR-UI-15-4: protocol template draft + schedule-next modal state moved
  // verbatim from the panel (dialog-adjacent view state).
  const [protocolTemplateDraft, setProtocolTemplateDraft] = useState<SelectedPatient | null>(null);
  const [scheduleNextModal, setScheduleNextModal] = useState<{ open: boolean; patient: SelectedPatient | Record<string, unknown> | null }>({ open: false, patient: null });

  return {
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
  };
}
