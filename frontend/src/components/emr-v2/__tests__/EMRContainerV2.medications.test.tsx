import type { ComponentProps } from 'react';
import { act, fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { setProfile } from '../../../stores/auth';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { EMRContainerV2 } from '../EMRContainerV2';

const mocks = vi.hoisted(() => ({
  data: {} as Record<string, unknown>,
  emr: { id: 1, visit_id: 11, patient_id: 22, status: 'in_progress' },
  dirty: false,
  conflict: null as { current_version: number } | null,
  accessDenied: false,
  setField: vi.fn(),
  saveEMR: vi.fn(),
  signEMR: vi.fn(),
  amendEMR: vi.fn(),
  getPrescription: vi.fn(),
  issuePrescription: vi.fn(),
  noOp: () => {},
  scope: { visit: { id: 11, status: 'open' }, patient: { id: 22, full_name: 'SYNTHETIC patient' } },
}));

vi.mock('../../../hooks/useEMR', () => ({
  useEMR: () => ({
    data: mocks.data,
    emr: mocks.emr,
    status: 'idle',
    isDirty: mocks.dirty,
    isSigned: mocks.emr.status === 'signed',
    isAmended: mocks.emr.status === 'amended',
    conflict: mocks.conflict,
    accessDenied: mocks.accessDenied,
    rowVersion: 19,
    version: 7,
    setField: mocks.setField,
    saveEMR: mocks.saveEMR,
    signEMR: mocks.signEMR,
    amendEMR: mocks.amendEMR,
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
vi.mock('../sections/LabResultsSection', () => ({
  default: ({ reviewerId }: { reviewerId: number | null }) => (
    <output aria-label="Laboratory reviewer">{reviewerId}</output>
  ),
}));
vi.mock('../sections', () => ({
  ComplaintsSection: mocks.noOp,
  AnamnesisMorbiSection: mocks.noOp,
  AnamnesisVitaeSection: mocks.noOp,
  ExaminationSection: mocks.noOp,
  DiagnosisSection: mocks.noOp,
  RecommendationsSection: mocks.noOp,
  NotesSection: mocks.noOp,
  TreatmentSection: ({
    value, medications, onChange, onMedicationsChange, disabled,
  }: {
    value: string;
    medications: Array<{ drug: string }>;
    onChange: (value: string) => void;
    onMedicationsChange: (value: unknown[]) => void;
    disabled: boolean;
  }) => (
    <>
      <label>
        Treatment note
        <textarea aria-label="Treatment note" value={value} disabled={disabled} onChange={event => onChange(event.target.value)} />
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
const legacyPrescription = {
  id: 5, visit_id: 11, emr_version: null, is_draft: false, review_token: 'original-review-token',
  instructions: 'SYNTHETIC existing instructions', doctor_notes: 'SYNTHETIC existing notes',
};
type EditorOptions = Pick<ComponentProps<typeof EMRContainerV2>, 'isReadOnly' | 'completionBusy'>;
async function renderEditor(options: EditorOptions = {}) {
  await act(async () => {
    renderWithProviders(<EMRContainerV2 visitId={11} patientId={22} specialty="general" {...options} />);
  });
}

beforeEach(() => {
  mocks.data = { medications: legacyMedications };
  mocks.emr = { id: 1, visit_id: 11, patient_id: 22, status: 'in_progress' };
  mocks.scope = { visit: { id: 11, status: 'open' }, patient: { id: 22, full_name: 'SYNTHETIC patient' } };
  mocks.dirty = false;
  mocks.conflict = null;
  mocks.accessDenied = false;
  mocks.setField.mockReset();
  mocks.saveEMR.mockReset();
  mocks.signEMR.mockReset();
  mocks.amendEMR.mockReset();
  mocks.getPrescription.mockReset().mockResolvedValue(null);
  mocks.issuePrescription.mockReset().mockResolvedValue({ id: 5, visit_id: 11, emr_version: 7, is_draft: false });
});

it('uses the active session for laboratory review and clears the reviewer on logout', async () => {
  await renderEditor();
  expect(screen.getByLabelText('Laboratory reviewer')).toBeEmptyDOMElement();

  try {
    act(() => {
      sessionStorage.setItem('auth_token', 'SYNTHETIC-session');
      setProfile({ id: 42 });
    });
    expect(screen.getByLabelText('Laboratory reviewer')).toHaveTextContent('42');

    act(() => {
      sessionStorage.removeItem('auth_token');
      setProfile({ id: 42 });
    });
    expect(screen.getByLabelText('Laboratory reviewer')).toBeEmptyDOMElement();
  } finally {
    act(() => {
      sessionStorage.removeItem('auth_token');
      setProfile(null);
    });
  }
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
    expect(screen.getByText('Рецепт №5 оформлен. Препараты из ЭМК, версия 7.')).toBeVisible();
  });

  it('requires an explicit review of the old prescription text before issuing', async () => {
    mocks.getPrescription.mockResolvedValue(legacyPrescription);
    await renderEditor();

    const issue = screen.getByRole('button', { name: /Оформить рецепт/ });
    fireEvent.click(issue);
    let dialog = within(screen.getByRole('dialog', { name: 'Проверка инструкций рецепта' }));
    expect(dialog.getByRole('textbox', { name: 'Инструкции к рецепту' })).toHaveValue(legacyPrescription.instructions);
    expect(dialog.getByRole('textbox', { name: 'Заметки врача' })).toHaveValue(legacyPrescription.doctor_notes);
    fireEvent.click(dialog.getByRole('button', { name: 'Отмена' }));
    expect(mocks.issuePrescription).not.toHaveBeenCalled();

    fireEvent.click(issue);
    dialog = within(screen.getByRole('dialog', { name: 'Проверка инструкций рецепта' }));
    fireEvent.change(dialog.getByRole('textbox', { name: 'Инструкции к рецепту' }), {
      target: { value: 'SYNTHETIC reviewed instructions' },
    });
    fireEvent.change(dialog.getByRole('textbox', { name: 'Заметки врача' }), { target: { value: '' } });
    expect(mocks.issuePrescription).not.toHaveBeenCalled();
    await act(async () => { fireEvent.click(dialog.getByRole('button', { name: 'Подтвердить и оформить' })); });

    expect(mocks.issuePrescription).toHaveBeenCalledExactlyOnceWith(11, 22, 19, {
      expected_token: legacyPrescription.review_token,
      instructions: 'SYNTHETIC reviewed instructions',
      doctor_notes: null,
    });
    expect(screen.queryByRole('dialog', { name: 'Проверка инструкций рецепта' })).toBeNull();
  });

  it('blocks issuance until the current prescription can be checked', async () => {
    mocks.getPrescription.mockResolvedValueOnce({ ...legacyPrescription, review_token: undefined })
      .mockResolvedValueOnce({ ...legacyPrescription, review_token: null, instructions: null, doctor_notes: null });
    await renderEditor();

    const issue = screen.getByRole('button', { name: /Оформить рецепт/ });
    expect(issue).toBeDisabled();
    fireEvent.click(issue);
    expect(mocks.issuePrescription).not.toHaveBeenCalled();
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Повторить' })); });
    expect(issue).toBeEnabled();
  });

  it('reloads a changed prescription and requires a fresh explicit review', async () => {
    const changed = { ...legacyPrescription, instructions: 'SYNTHETIC concurrent update', review_token: 'new-review-token' };
    mocks.getPrescription.mockResolvedValueOnce(legacyPrescription).mockResolvedValueOnce(changed);
    mocks.issuePrescription.mockRejectedValueOnce({
      response: { status: 409, data: { detail: { code: 'PRESCRIPTION_TEXT_REVIEW_REQUIRED' } } },
    });
    await renderEditor();

    const issue = screen.getByRole('button', { name: /Оформить рецепт/ });
    fireEvent.click(issue);
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Подтвердить и оформить' })); });
    expect(screen.getByRole('alert')).toHaveTextContent('Инструкции рецепта изменились');
    expect(mocks.getPrescription).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('dialog', { name: 'Проверка инструкций рецепта' })).toBeNull();

    fireEvent.click(issue);
    expect(screen.getByRole('textbox', { name: 'Инструкции к рецепту' })).toHaveValue(changed.instructions);
    expect(mocks.issuePrescription).toHaveBeenCalledOnce();
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Подтвердить и оформить' })); });
    expect(mocks.issuePrescription).toHaveBeenLastCalledWith(11, 22, 19, {
      expected_token: changed.review_token, instructions: changed.instructions, doctor_notes: changed.doctor_notes,
    });
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

  it.each(['signed', 'amended'])('issues a separate prescription from the persisted %s chart during an active visit', async status => {
    mocks.emr.status = status;
    mocks.scope.visit.status = status === 'signed' ? 'open' : 'in_progress';
    const before = structuredClone({ emr: mocks.emr, data: mocks.data });
    await renderEditor();

    expect(screen.getByLabelText('Treatment note')).toBeDisabled();
    const issue = screen.getByRole('button', { name: /Оформить рецепт/ });
    expect(issue).toBeEnabled();
    await act(async () => { fireEvent.click(issue); });
    expect(mocks.issuePrescription).toHaveBeenCalledExactlyOnceWith(11, 22, 19);
    expect(screen.getByText('Рецепт №5 оформлен. Препараты из ЭМК, версия 7.')).toBeVisible();
    expect({ emr: mocks.emr, data: mocks.data }).toEqual(before);
    expect(mocks.setField).not.toHaveBeenCalled();
    expect(mocks.saveEMR).not.toHaveBeenCalled();
    expect(mocks.signEMR).not.toHaveBeenCalled();
    expect(mocks.amendEMR).not.toHaveBeenCalled();
  });

  it.each<EditorOptions>([{ isReadOnly: true }, { completionBusy: true }])(
    'keeps signed prescription issuance unavailable for a restricted editor (%j)', async options => {
      mocks.emr.status = 'signed';
      await renderEditor(options);
      expect(screen.queryByRole('button', { name: /Оформить рецепт/ })).toBeNull();
      expect(mocks.issuePrescription).not.toHaveBeenCalled();
    },
  );

  it.each(['completed', 'closed', 'canceled', 'expired'])('keeps signed prescription issuance unavailable in a %s visit', async status => {
    mocks.emr.status = 'signed';
    mocks.scope.visit.status = status;
    await renderEditor();
    expect(screen.queryByRole('button', { name: /Оформить рецепт/ })).toBeNull();
    expect(mocks.issuePrescription).not.toHaveBeenCalled();
  });

  it('does not offer a signed prescription when the visit identity differs from the workspace', async () => {
    mocks.emr.status = 'signed';
    mocks.emr.visit_id = 44;
    await renderEditor();
    expect(screen.queryByRole('button', { name: /Оформить рецепт/ })).toBeNull();
    expect(mocks.issuePrescription).not.toHaveBeenCalled();
  });

  it('keeps signed prescription issuance unavailable while there is a version conflict', async () => {
    mocks.emr.status = 'signed';
    mocks.conflict = { current_version: 20 };
    await renderEditor();
    expect(screen.queryByRole('button', { name: /Оформить рецепт/ })).toBeNull();
    expect(mocks.issuePrescription).not.toHaveBeenCalled();
  });

  it('keeps signed prescription issuance unavailable after access is denied', async () => {
    mocks.emr.status = 'signed';
    mocks.accessDenied = true;
    await renderEditor();
    expect(screen.queryByRole('button', { name: /Оформить рецепт/ })).toBeNull();
    expect(mocks.issuePrescription).not.toHaveBeenCalled();
  });
});
