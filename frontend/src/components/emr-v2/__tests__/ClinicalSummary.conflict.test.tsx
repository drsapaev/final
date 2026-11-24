import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { getClinicalHistory, saveClinicalEntry, type ClinicalEntry, type EMRWorkspaceData } from '@/api/emrWorkspace';
import i18n from '@/i18n';
import { ClinicalSummary } from '../workspace/ClinicalSummary';

vi.mock('@/api/emrWorkspace', () => ({
  getClinicalHistory: vi.fn(),
  saveClinicalEntry: vi.fn(),
}));

const entry: ClinicalEntry = {
  entry_id: 'synthetic-entry',
  version: 1,
  schema_version: 1,
  visit_id: 501,
  author_id: 1,
  source: 'clinician',
  clinical_details: { kind: 'medication', name: 'SYNTHETIC medication', status: 'taking', dose: '1' },
  recorded_at: '2026-06-15T10:00:00Z',
  confirmed_at: null,
};

const workspace: EMRWorkspaceData = {
  patient: { id: 101, full_name: 'SYNTHETIC patient', birth_date: null, legacy_allergies: null, legacy_conditions: null },
  visit: { id: 501, date: '2026-06-15', status: 'open' },
  allergy_state: 'not_checked',
  clinical_entries: [entry],
  history: [],
  has_more_history: false,
};

beforeEach(async () => {
  vi.resetAllMocks();
  await i18n.changeLanguage('en');
});

it('preserves a conflicting draft and submits it against the displayed revision only on explicit confirmation', async () => {
  const latest: ClinicalEntry = { ...entry, version: 2, clinical_details: {
    kind: 'medication', name: 'SYNTHETIC updated medication', status: 'taking', dose: '2',
  } };
  vi.mocked(saveClinicalEntry)
    .mockRejectedValueOnce({ response: { status: 409, data: { detail: { code: 'CLINICAL_ENTRY_CONFLICT' } } } })
    .mockResolvedValueOnce(undefined);
  vi.mocked(getClinicalHistory)
    .mockRejectedValueOnce(new Error('Synthetic transport error'))
    .mockResolvedValueOnce([latest, entry]);
  const reload = vi.fn();
  const { rerender } = render(<ClinicalSummary workspace={workspace} readOnly={false} reload={reload} />);

  fireEvent.click(screen.getByRole('button', { name: 'Edit', exact: true }));
  const dose = screen.getByRole('textbox', { name: 'Dose', exact: true });
  fireEvent.change(dose, { target: { value: '3' } });
  const save = screen.getByRole('button', { name: i18n.t('common.save'), exact: true });
  fireEvent.click(save);

  await screen.findByText('This entry changed. Compare the server version with your draft.');
  expect(save).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Open version', exact: true }));
  await screen.findByText('Unable to load the information');
  expect(dose).toHaveValue('3');
  expect(reload).not.toHaveBeenCalled();

  fireEvent.click(screen.getByRole('button', { name: 'Open version', exact: true }));
  await screen.findByText('Server version 2');
  expect(screen.getByText('SYNTHETIC updated medication')).toBeInTheDocument();
  expect(dose).toHaveValue('3');
  expect(getClinicalHistory).toHaveBeenLastCalledWith(501, 101, entry.entry_id);
  expect(save).toBeDisabled();

  rerender(<ClinicalSummary workspace={{ ...workspace, clinical_entries: [latest] }} readOnly={false} reload={reload} />);
  const edit = screen.getByRole('button', { name: 'Edit', exact: true });
  expect(edit).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Add entry for Current therapy' })).toBeDisabled();
  fireEvent.click(edit);
  expect(dose).toHaveValue('3');
  expect(save).toBeDisabled();

  const form = dose.closest('form')!;
  fireEvent.submit(form);
  expect(saveClinicalEntry).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Save my version', exact: true }));
  await waitFor(() => expect(reload).toHaveBeenCalledTimes(1));
  expect(saveClinicalEntry).toHaveBeenLastCalledWith(501, 101, entry.entry_id, 2,
    expect.objectContaining({ name: 'SYNTHETIC medication', dose: '3' }), 'clinician', false);
});
