import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DentistDialogsLayer from '../DentistDialogsLayer';
import type { SelectedPatient } from '../../dentistContracts';

/**
 * DENTPLAN-FE-002 / DENTPHOTO-FE-001 / DENTPHOTO-FE-002 (audit 2026-11-06,
 * PR 3892): patient-scoped dialogs (treatment planner, photo archive,
 * dental chart + tooth modal, diagnosis form, patient card, price manager)
 * must not survive a patient/visit identity switch with stale local state —
 * the layer closes them fail-closed on identity change.
 */
vi.mock('@/components/dental/TreatmentPlanner', () => ({
  default: () => <div>mock-treatment-planner</div>,
}));
vi.mock('@/components/dental/PhotoArchive', () => ({
  default: () => <div>mock-photo-archive</div>,
}));
vi.mock('@/components/dental/PatientCard', () => ({
  default: () => <div>mock-patient-card</div>,
}));
vi.mock('@/components/dental/DiagnosisForm', () => ({
  default: () => <div>mock-diagnosis-form</div>,
}));
vi.mock('@/components/dental/TeethChart', () => ({
  default: () => <div>mock-teeth-chart</div>,
}));
vi.mock('@/components/dental/ToothModal', () => ({
  default: () => <div>mock-tooth-modal</div>,
}));
vi.mock('@/components/dental/DentalPriceManager', () => ({
  default: () => <div>mock-price-manager</div>,
}));
vi.mock('@/components/dental/ProtocolTemplates', () => ({
  default: () => <div>mock-protocol-templates</div>,
}));
vi.mock('@/components/common/ScheduleNextModal', () => ({
  default: () => <div>mock-schedule-next</div>,
}));
vi.mock('@/components/common/SessionWarningModal', () => ({
  default: () => <div>mock-session-warning</div>,
}));
vi.mock('@/components/ui/macos', () => ({
  Card: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock('@/contexts/ThemeContext', () => ({
  useTheme: () => ({ isDark: false, getColor: () => '', getSpacing: () => '', getFontSize: () => '' }),
}));
vi.mock('@/services/notify', () => ({
  default: { info: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));
vi.mock('@/utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));

const patientA: SelectedPatient = { id: 101, patient_id: 7, visit_id: 41, patient_name: 'SYNTHETIC Patient A' };
const patientB: SelectedPatient = { id: 102, patient_id: 8, visit_id: 42, patient_name: 'SYNTHETIC Patient B' };

// One setter set per test: the same functions survive rerenders exactly the
// way the real panel's state setters do.
const makeSetters = () => ({
  setShowPatientCard: vi.fn(),
  setShowDiagnosisForm: vi.fn(),
  setShowPhotoArchive: vi.fn(),
  setShowProtocolTemplates: vi.fn(),
  setShowReports: vi.fn(),
  setShowDentalChart: vi.fn(),
  setShowTreatmentPlanner: vi.fn(),
  setShowPriceManager: vi.fn(),
  setToothModalOpen: vi.fn(),
  setSelectedTooth: vi.fn(),
  setDentalChartData: vi.fn(),
  setSelectedServiceForPrice: vi.fn(),
  setScheduleNextModal: vi.fn(),
  setSessionWarning: vi.fn(),
});

type Setters = ReturnType<typeof makeSetters>;

const makeLayerProps = (
  selectedPatient: SelectedPatient | null,
  setters: Setters,
  overrides: Record<string, unknown> = {},
) => ({
  tI18n: (key: string) => key,
  user: { id: 1, clinic_id: 1 },
  selectedPatient,
  dentalChartData: {},
  selectedTooth: null as { number: string | number; data: unknown } | string | number | null,
  selectedServiceForPrice: null,
  scheduleNextModal: { open: false, patient: null },
  sessionWarning: null,
  confirmDialog: null,
  showPatientCard: false,
  showDiagnosisForm: false,
  showPhotoArchive: false,
  showProtocolTemplates: false,
  showReports: false,
  showDentalChart: false,
  showTreatmentPlanner: true,
  showPriceManager: false,
  toothModalOpen: false,
  handleProtocolTemplateSelect: vi.fn(),
  ...setters,
  ...overrides,
});

beforeEach(() => {
  vi.clearAllMocks();
});

describe('DentistDialogsLayer — patient-context isolation (DENTPLAN-FE-002 / DENTPHOTO-FE-001/002)', () => {
  it('closes the open treatment planner when the patient identity switches', async () => {
    const setters = makeSetters();
    const { rerender } = render(<DentistDialogsLayer {...makeLayerProps(patientA, setters)} />);
    expect(await screen.findByText('mock-treatment-planner')).toBeTruthy();

    rerender(<DentistDialogsLayer {...makeLayerProps(patientB, setters)} />);
    await waitFor(() => expect(setters.setShowTreatmentPlanner).toHaveBeenCalledWith(false));

    // The parent applies the close: the dialog (with its stale stage draft) unmounts.
    rerender(<DentistDialogsLayer {...makeLayerProps(patientB, setters, { showTreatmentPlanner: false })} />);
    await waitFor(() => expect(screen.queryByText('mock-treatment-planner')).toBeNull());
  });

  it('closes the open photo archive when the patient identity switches', async () => {
    const setters = makeSetters();
    const { rerender } = render(
      <DentistDialogsLayer {...makeLayerProps(patientA, setters, { showTreatmentPlanner: false, showPhotoArchive: true })} />,
    );
    expect(await screen.findByText('mock-photo-archive')).toBeTruthy();

    rerender(
      <DentistDialogsLayer {...makeLayerProps(patientB, setters, { showTreatmentPlanner: false, showPhotoArchive: true })} />,
    );
    await waitFor(() => expect(setters.setShowPhotoArchive).toHaveBeenCalledWith(false));

    rerender(
      <DentistDialogsLayer {...makeLayerProps(patientB, setters, { showTreatmentPlanner: false, showPhotoArchive: false })} />,
    );
    await waitFor(() => expect(screen.queryByText('mock-photo-archive')).toBeNull());
  });

  it('closes the open dental chart and its tooth modal when the patient identity switches', async () => {
    const setters = makeSetters();
    const toothSelection = { number: 11, data: {} };
    const { rerender } = render(
      <DentistDialogsLayer {...makeLayerProps(patientA, setters, {
        showTreatmentPlanner: false,
        showDentalChart: true,
        toothModalOpen: true,
        selectedTooth: toothSelection,
      })} />,
    );
    expect(await screen.findByText('mock-teeth-chart')).toBeTruthy();
    expect(screen.getByText('mock-tooth-modal')).toBeTruthy();

    rerender(
      <DentistDialogsLayer {...makeLayerProps(patientB, setters, {
        showTreatmentPlanner: false,
        showDentalChart: true,
        toothModalOpen: true,
        selectedTooth: toothSelection,
      })} />,
    );
    await waitFor(() => expect(setters.setShowDentalChart).toHaveBeenCalledWith(false));
    await waitFor(() => expect(setters.setToothModalOpen).toHaveBeenCalledWith(false));
    await waitFor(() => expect(setters.setSelectedTooth).toHaveBeenCalledWith(null));
  });

  it('keeps non-patient-scoped dialogs (protocol templates) open across an identity switch', async () => {
    const setters = makeSetters();
    const { rerender } = render(
      <DentistDialogsLayer {...makeLayerProps(patientA, setters, { showTreatmentPlanner: false, showProtocolTemplates: true })} />,
    );
    expect(await screen.findByText('mock-protocol-templates')).toBeTruthy();

    rerender(
      <DentistDialogsLayer {...makeLayerProps(patientB, setters, { showTreatmentPlanner: false, showProtocolTemplates: true })} />,
    );

    await waitFor(() => expect(setters.setShowTreatmentPlanner).toHaveBeenCalledWith(false));
    expect(screen.getByText('mock-protocol-templates')).toBeTruthy();
    expect(setters.setShowProtocolTemplates).not.toHaveBeenCalled();
  });

  it('does not close dialogs when the identity has not actually changed', async () => {
    const setters = makeSetters();
    const { rerender } = render(<DentistDialogsLayer {...makeLayerProps(patientA, setters)} />);
    expect(await screen.findByText('mock-treatment-planner')).toBeTruthy();

    rerender(<DentistDialogsLayer {...makeLayerProps({ ...patientA, patient_name: 'SYNTHETIC Patient A renamed' }, setters)} />);

    expect(screen.getByText('mock-treatment-planner')).toBeTruthy();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(setters.setShowTreatmentPlanner).not.toHaveBeenCalled();
  });

  it('closes dialogs when the patient is deselected (selection cleared to null)', async () => {
    const setters = makeSetters();
    const { rerender } = render(<DentistDialogsLayer {...makeLayerProps(patientA, setters)} />);
    expect(await screen.findByText('mock-treatment-planner')).toBeTruthy();

    rerender(<DentistDialogsLayer {...makeLayerProps(null, setters)} />);

    await waitFor(() => expect(setters.setShowTreatmentPlanner).toHaveBeenCalledWith(false));
  });
});
