/**
 * DERMARX-FE-001 / DERMARX-FE-002 / DERMARX-FE-003 (audit 3892, post-merge
 * group 8 «dermatology prescription write integrity») — fail-first
 * regressions for the PrescriptionSystem editor:
 *
 * - DERMARX-FE-001: Print must not accept a modified unsaved prescription
 *   while the record is still labeled as saved. The printed clinical
 *   document must reflect the backend-acknowledged content, not a dirty
 *   local draft.
 * - DERMARX-FE-002: a canonical status refresh that recreates the
 *   `appointment` / `initialPrescription` prop objects with identical
 *   values must NOT rehydrate the editor and silently discard locally
 *   edited (dirty) fields.
 * - DERMARX-FE-003: edits made while a save POST is in flight must survive
 *   the save acknowledgement as visibly unsaved — they were not part of
 *   the submitted request — instead of being silently reverted or
 *   falsely marked saved.
 *
 * Red-first: on the pre-fix source every bug-case assertion below fails
 * for the documented reason; the positive controls pass on both.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../contexts/ThemeContext';
import PrescriptionSystem from '../PrescriptionSystem';

vi.mock('../../i18n/useTranslation', () => ({
  useTranslation: () => ({ t: (key: string) => key }),
}));

const SAVED_MEDICATION = {
  id: 1,
  name: 'Synthetic ointment',
  dosage: '1%',
  frequency: 'daily',
  duration: '10 days',
  instructions: '',
  quantity: 1,
};

const SAVED_PRESCRIPTION = {
  medications: [SAVED_MEDICATION],
  instructions: 'base instructions',
  doctorNotes: '',
  isDraft: false,
  createdAt: '2026-01-01T00:00:00Z',
  printedAt: null,
};

const APPOINTMENT = {
  id: 42,
  doctor_id: 7,
  patient_name: 'SYNTHETIC PATIENT',
  specialist: 'dermatology',
};

type EditorProps = Parameters<typeof PrescriptionSystem>[0];

function renderEditor(overrides: Partial<EditorProps> = {}) {
  const props: EditorProps = {
    appointment: APPOINTMENT,
    emr: { isDraft: false },
    prescription: SAVED_PRESCRIPTION,
    canCreatePrescription: true,
    onSave: vi.fn(),
    ...overrides,
  };
  return render(
    <ThemeProvider>
      <PrescriptionSystem {...props} />
    </ThemeProvider>,
  );
}

function rerenderEditor(rerender: (node: React.ReactElement) => void, overrides: Partial<EditorProps> = {}) {
  const props: EditorProps = {
    appointment: { ...APPOINTMENT },
    emr: { isDraft: false },
    prescription: { ...SAVED_PRESCRIPTION, medications: [{ ...SAVED_MEDICATION }] },
    canCreatePrescription: true,
    onSave: vi.fn(),
    ...overrides,
  };
  rerender(
    <ThemeProvider>
      <PrescriptionSystem {...props} />
    </ThemeProvider>,
  );
}

function dosageInput(): HTMLInputElement {
  return screen.getByLabelText('Medication 1 dosage') as HTMLInputElement;
}

function clickByName(name: string): void {
  fireEvent.click(screen.getByRole('button', { name: new RegExp(name) }));
}

describe('DERMARX-FE-001 — Print gate for unsaved prescription edits', () => {
  it('does not print a prescription with unsaved edits (pre-fix: onPrint receives the dirty draft)', () => {
    const onPrint = vi.fn();
    renderEditor({ onPrint });

    fireEvent.change(dosageInput(), { target: { value: '2%' } });
    // The editor honestly reports unsaved changes.
    expect(screen.getByText('misc.ps_has_changes')).toBeTruthy();

    clickByName('misc.ps_print');
    expect(onPrint).not.toHaveBeenCalled();
  });

  it('positive control: prints the saved record when there are no unsaved edits', () => {
    const onPrint = vi.fn();
    renderEditor({ onPrint });

    clickByName('misc.ps_print');
    expect(onPrint).toHaveBeenCalledTimes(1);
    expect(((onPrint.mock.calls[0] as unknown[])[0] as { medications: Array<{ dosage: string }> }).medications[0].dosage).toBe('1%');
  });
});

describe('DERMARX-FE-002 — canonical refresh with identical values keeps local edits', () => {
  it('keeps dirty fields when the parent recreates prop objects with the same canonical values', () => {
    const { rerender } = renderEditor();

    fireEvent.change(dosageInput(), { target: { value: '9%' } });
    expect(screen.getByText('misc.ps_has_changes')).toBeTruthy();

    // refreshCanonicalStatus() recreates appointment + prescription objects
    // with fresh identities and identical values on the same visit.
    rerenderEditor(rerender);

    expect(dosageInput().value).toBe('9%');
    expect(screen.getByText('misc.ps_has_changes')).toBeTruthy();
  });

  it('positive control: a clean editor re-renders without fabricating unsaved state', () => {
    const { rerender } = renderEditor();

    rerenderEditor(rerender);

    expect(dosageInput().value).toBe('1%');
    expect(screen.queryByText('misc.ps_has_changes')).toBeNull();
  });
});

describe('DERMARX-FE-003 — edits made during an in-flight save stay visibly unsaved', () => {
  it('keeps the mid-flight edit dirty after the save resolves (pre-fix: silently reverted / marked saved)', async () => {
    let resolveSave!: (value: void) => void;
    const onSave = vi.fn(() => new Promise<void>((complete) => { resolveSave = complete; }));
    renderEditor({ onSave });

    clickByName('misc.ps_save');

    // The submitted request captured the pre-save value X.
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(((onSave.mock.calls[0] as unknown[])[0] as { medications: Array<{ dosage: string }> }).medications[0].dosage).toBe('1%');

    // The clinician keeps typing while the POST is in flight.
    fireEvent.change(dosageInput(), { target: { value: '3%' } });

    await act(async () => {
      resolveSave();
    });

    // The newer edit was NOT part of the request: it must survive as dirty.
    expect(dosageInput().value).toBe('3%');
    expect(screen.getByText('misc.ps_has_changes')).toBeTruthy();
  });

  it('positive control: a save without mid-flight edits is acknowledged as clean', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderEditor({ onSave });

    clickByName('misc.ps_save');
    await waitFor(() => expect(screen.getByText('misc.ps_saved')).toBeTruthy());
    expect(screen.queryByText('misc.ps_has_changes')).toBeNull();
    expect(onSave).toHaveBeenCalledTimes(1);
  });
});
