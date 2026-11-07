/**
 * Audit 3892 round 3 — fail-first regressions for the ToothModal cluster:
 *
 *  - DENTMODAL-FE-003: a clinically meaningful tooth record (notes, material,
 *    follow-up, next-visit date or status) is saveable without procedures;
 *    a truly empty form is rejected.
 *  - DENTMODAL-FE-004: same-millisecond repeated procedures keep stable,
 *    collision-resistant identities — deleting one never removes both.
 *  - DENTMODAL-FE-005: the dead, never-populated tooth-history panel (and its
 *    never-read state) is removed from the component.
 *  - DENTDIALOG-FE-001 (modal side): without a canonical visit the modal fails
 *    closed — visible "visit required" state, Save disabled, no onSave.
 *  - DENTVISIT-FE-003 (modal side): the palette-suggested status seeds the
 *    editable status field and is confirmed through Save.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from '../../../api/client';
import ToothModal from '../ToothModal';

vi.mock('../../../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));
vi.mock('../../../services/notify', () => ({
  default: { info: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}));
vi.mock('../../../utils/logger', () => ({
  default: { info: vi.fn(), warn: vi.fn(), error: vi.fn() },
}));
vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      (params ? `${key}:${JSON.stringify(params)}` : key),
  }),
}));

const NOTES_PLACEHOLDER = 'dental.dental_tm_notes_placeholder';
const SAVE_BUTTON_NAME = 'dental.dental_tm_save';
const FILLING_BUTTON_NAME = 'Пломба';
const DELETE_LABEL = 'dental.dental_tm_delete';

const getNotesTextarea = () => screen.getByPlaceholderText(NOTES_PLACEHOLDER);
const getSaveButton = () => screen.getByRole('button', { name: SAVE_BUTTON_NAME });

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: { data: {}, row_version: 1 } } as never);
  vi.mocked(api.post).mockResolvedValue({ data: { row_version: 2 } } as never);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('ToothModal completion integrity (audit 3892 round 3)', () => {
  it('DENTMODAL-FE-003: a notes-only change is saveable without any procedure', async () => {
    const onSave = vi.fn();
    render(
      <ToothModal
        open
        toothNumber={16}
        toothData={{}}
        visitId={41}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );

    // A truly empty form offers no Save (no-op protection).
    expect(getSaveButton()).toHaveProperty('disabled', true);

    fireEvent.change(getNotesTextarea(), { target: { value: 'review in 7 days' } });
    expect(getSaveButton()).toHaveProperty('disabled', false);

    fireEvent.click(getSaveButton());
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ notes: 'review in 7 days', toothNumber: 16 }),
      2,
    );
    expect(api.post).toHaveBeenCalledWith('/v2/emr/41', expect.anything());
  });

  it('DENTMODAL-FE-003 (control): a procedure-bearing form stays saveable', () => {
    render(
      <ToothModal
        open
        toothNumber={16}
        toothData={{ procedures: [{ id: 'filling_1', name: 'Пломба', price: 150000 }] }}
        visitId={41}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(getSaveButton()).toHaveProperty('disabled', false);
  });

  it('DENTMODAL-FE-004: same-millisecond duplicate procedures keep distinct identities', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1234);
    render(
      <ToothModal
        open
        toothNumber={16}
        toothData={{}}
        visitId={41}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    // Two fillings added within the same frozen millisecond.
    fireEvent.click(screen.getByRole('button', { name: FILLING_BUTTON_NAME }));
    fireEvent.click(screen.getByRole('button', { name: FILLING_BUTTON_NAME }));
    expect(screen.getAllByLabelText(DELETE_LABEL)).toHaveLength(2);

    // Deleting exactly one must leave exactly one row behind.
    fireEvent.click(screen.getAllByLabelText(DELETE_LABEL)[0]);
    expect(screen.getAllByLabelText(DELETE_LABEL)).toHaveLength(1);
    expect(screen.getAllByRole('listitem')).toHaveLength(1);
  });

  it('DENTMODAL-FE-005: the never-populated tooth-history panel is removed (dead-UI contract)', async () => {
    const fs = await import('node:fs');
    const path = await import('node:path');
    const source = fs.readFileSync(
      path.resolve(process.cwd(), 'src/components/dental/ToothModal.tsx'),
      'utf8',
    );
    expect(source).not.toContain('dental_tm_history_title');
    expect(source).not.toMatch(/useState<HistoryRecord/);

    // And nothing renders a history section for a tooth with procedures.
    render(
      <ToothModal
        open
        toothNumber={16}
        toothData={{ procedures: [{ id: 'filling_1', name: 'Пломба', price: 150000 }] }}
        visitId={41}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(screen.queryByText('dental.dental_tm_history_title')).toBeNull();
  });

  it('DENTDIALOG-FE-001: without a visit the modal fails closed instead of pretending to save', () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(
      <ToothModal
        open
        toothNumber={16}
        toothData={{ procedures: [{ id: 'filling_1', name: 'Пломба', price: 150000 }] }}
        visitId={undefined}
        onSave={onSave}
        onClose={onClose}
      />,
    );

    expect(screen.getByText('dental2.tooth_save_requires_visit')).toBeTruthy();
    expect(getSaveButton()).toHaveProperty('disabled', true);
    expect(onSave).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('DENTVISIT-FE-003 (modal side): the suggested status seeds the confirmed tooth record', async () => {
    const onSave = vi.fn();
    render(
      <ToothModal
        open
        toothNumber={11}
        toothData={{}}
        suggestedStatus="caries"
        visitId={41}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );

    // The suggested status makes the record meaningful and editable.
    expect(getSaveButton()).toHaveProperty('disabled', false);
    fireEvent.click(getSaveButton());

    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'caries', toothNumber: 11 }),
      2,
    );
  });
});
