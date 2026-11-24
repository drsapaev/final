import { act, fireEvent, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { EMRContainerV2 } from '../EMRContainerV2';

const mocks = vi.hoisted(() => ({
  data: {} as Record<string, unknown>,
  dirty: false,
  setField: vi.fn(),
  getPrescription: vi.fn(),
  issuePrescription: vi.fn(),
  noOp: () => {},
  scope: { visit: { id: 11 }, patient: { id: 22, full_name: 'SYNTHETIC patient' } },
}));

vi.mock('../../../hooks/useEMR', () => ({
  useEMR: () => ({
    data: mocks.data,
    emr: { id: 1, status: 'in_progress' },
    status: 'idle',
    isDirty: mocks.dirty,
    rowVersion: 19,
    version: 7,
    setField: mocks.setField,
  }),
}));
vi.mock('../../../hooks/useEMRWorkspace', () => ({
  useEMRWorkspace: () => ({ status: 'ready', scope: '11:22', data: mocks.scope, reload: mocks.noOp }),
}));
vi.mock('../../../hooks/useEMRAutosave', () => ({
  useEMRAutosave: () => ({ config: {}, suppressOnDiscard: mocks.noOp }),
}));
vi.mock('../../../hooks/useEMRLeaveGuard', () => ({ useEMRLeaveGuard: mocks.noOp }));
vi.mock('../../../hooks/useNavigationGuard', () => ({ useBeforeUnload: mocks.noOp }));
vi.mock('../../../hooks/useEMRKeyboard', () => ({ useEMRKeyboard: mocks.noOp }));
vi.mock('../../../contexts/AppDataContext', () => ({ useAppData: () => ({}) }));
vi.mock('../../../hooks/useMcpClient', () => ({ useMcpClient: () => ({}) }));
vi.mock('../../../api/emrWorkspace', () => ({
  getWorkspacePrescription: mocks.getPrescription,
  issueWorkspacePrescription: mocks.issuePrescription,
}));
vi.mock('../workspace/VisitHistory', () => ({ FollowUpEditor: mocks.noOp, WorkspaceSidePanel: mocks.noOp }));
vi.mock('../workspace/FieldDictation', () => ({ FieldDictation: mocks.noOp }));
vi.mock('../sections/LabResultsSection', () => ({ default: mocks.noOp }));
vi.mock('../sections', () => ({
  ComplaintsSection: mocks.noOp,
  AnamnesisMorbiSection: mocks.noOp,
  AnamnesisVitaeSection: mocks.noOp,
  ExaminationSection: mocks.noOp,
  DiagnosisSection: mocks.noOp,
  RecommendationsSection: mocks.noOp,
  NotesSection: mocks.noOp,
  TreatmentSection: ({
    value, medications, onChange, onMedicationsChange,
  }: {
    value: string;
    medications: Array<{ drug: string }>;
    onChange: (value: string) => void;
    onMedicationsChange: (value: unknown[]) => void;
  }) => (
    <>
      <label>
        Treatment note
        <textarea aria-label="Treatment note" value={value} onChange={event => onChange(event.target.value)} />
      </label>
      {medications.map(item => <p key={item.drug}>{item.drug}</p>)}
      <button type="button" onClick={() => onMedicationsChange(medications.slice(0, 1))}>
        Remove last medication
      </button>
    </>
  ),
}));

const legacyMedications = [
  { drug: 'SYNTHETIC medication 1', dosage: '1 test unit', freq: 'test interval', duration: 'test course', reference: 'SYNTHETIC origin' },
  { drug: 'SYNTHETIC medication 2', dosage: '2 test units', freq: 'test interval', duration: 'test course' },
];
async function renderEditor() {
  await act(async () => {
    renderWithProviders(<EMRContainerV2 visitId={11} patientId={22} specialty="general" />);
  });
}

beforeEach(() => {
  mocks.data = { medications: legacyMedications };
  mocks.dirty = false;
  mocks.setField.mockReset();
  mocks.getPrescription.mockReset().mockResolvedValue(null);
  mocks.issuePrescription.mockReset().mockResolvedValue({ id: 5, visit_id: 11, emr_version: 7, is_draft: false });
});

describe('Legacy medications in the EMR', () => {
  it('shows the original list and issues from the saved row version', async () => {
    await renderEditor();
    expect(screen.getByText('SYNTHETIC medication 1')).toBeVisible();
    expect(mocks.setField).not.toHaveBeenCalled();

    const issue = screen.getByRole('button', { name: /Оформить рецепт/ });
    expect(issue).toBeEnabled();
    await act(async () => { fireEvent.click(issue); });
    expect(mocks.issuePrescription).toHaveBeenCalledOnce();
    expect(mocks.issuePrescription).toHaveBeenCalledWith(11, 22, 19);
    expect(screen.getByText('Оформлен рецепт №5, версия ЭМК 7')).toBeVisible();
  });

  it('preserves medication entries when editing the legacy list or its treatment note', async () => {
    await renderEditor();
    fireEvent.click(screen.getByRole('button', { name: 'Remove last medication' }));
    expect(mocks.setField).toHaveBeenLastCalledWith('medications', [legacyMedications[0]], undefined);

    fireEvent.change(screen.getByLabelText('Treatment note'), { target: { value: 'SYNTHETIC note' } });
    expect(mocks.setField).toHaveBeenLastCalledWith('medications', {
      list: legacyMedications, text: 'SYNTHETIC note',
    }, undefined);
  });

  it('preserves wrapper metadata and blocks issue while there are unsaved edits', async () => {
    const wrapper = { list: legacyMedications, text: 'SYNTHETIC existing note', source: { id: 4 } };
    mocks.data.medications = wrapper;
    mocks.dirty = true;
    await renderEditor();

    fireEvent.click(screen.getByRole('button', { name: 'Remove last medication' }));
    expect(mocks.setField).toHaveBeenLastCalledWith('medications', { ...wrapper, list: [legacyMedications[0]] }, undefined);
    expect(screen.getByLabelText('Treatment note')).toHaveValue(wrapper.text);
    const issue = screen.getByRole('button', { name: /Оформить рецепт/ });
    expect(issue).toBeDisabled();
    fireEvent.click(issue);
    expect(mocks.issuePrescription).not.toHaveBeenCalled();
    expect(mocks.getPrescription).toHaveBeenCalledOnce();
  });
});
