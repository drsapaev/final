/**
 * RETRO-3966-01 (post-merge code review #3968 of round-26 PR #3966) —
 * fail-first regressions for the inspection-only tooth modal.
 *
 * The locked/signed DentalVisitScreen routed locked-record tooth clicks into
 * the fully editable ToothModal: the modal exposed editable controls and an
 * enabled Save that POSTs `/v2/emr/{visitId}` even though the declared
 * clinical UI contract was read-only. The modal now has an explicit
 * inspection-only mode: no editable control, no Save, no POST.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

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
vi.mock('../../../i18n/useTranslation', () => {
  return {
    useTranslation: () => ({ t: (key: string) => key }),
    TranslationProvider: ({ children }: { children: unknown }) => children,
  };
});

const toothData = {
  status: 'filled',
  notes: 'SYNTHETIC signed-record note',
  procedures: [{ id: 'p1', name: 'SYNTHETIC filling', price: 1000 }],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: { data: {}, row_version: 1 } } as never);
  vi.mocked(api.post).mockResolvedValue({ data: { row_version: 2 } } as never);
});

describe('ToothModal inspection-only mode (RETRO-3966-01)', () => {
  it('readOnly modal offers no Save button and shows the inspection-only state', () => {
    render(
      <ToothModal open toothNumber={16} toothData={toothData} visitId={41} readOnly onClose={vi.fn()} onSave={vi.fn()} />,
    );

    // The inspection-only state is honest and visible.
    expect(screen.getByText('dental.dental_tm_inspection_only')).toBeDefined();
    // No save affordance exists at all — pointer and keyboard users alike
    // cannot reach a save action.
    expect(screen.queryByRole('button', { name: 'dental.dental_tm_save' })).toBeNull();
  });

  it('readOnly modal disables every editable control and never POSTs the EMR', () => {
    render(
      <ToothModal open toothNumber={16} toothData={toothData} visitId={41} readOnly onClose={vi.fn()} onSave={vi.fn()} />,
    );

    // Procedure palette (the "Осмотр" add-procedure button) is disabled.
    const addProcedure = screen.getByRole('button', { name: /Осмотр/ });
    expect(addProcedure).toBeDisabled();

    // Delete-procedure control is disabled.
    const removeProcedure = screen.getByRole('button', { name: 'dental.dental_tm_delete' });
    expect(removeProcedure).toBeDisabled();

    // Notes textarea cannot receive input.
    const notes = screen.getByDisplayValue('SYNTHETIC signed-record note');
    expect(notes).toBeDisabled();

    // Follow-up checkbox cannot be toggled.
    const followUp = screen.getByRole('checkbox', { name: 'dental.dental_tm_follow_up_label' });
    expect(followUp).toBeDisabled();

    // Even a forced interaction must never reach the EMR endpoint.
    fireEvent.click(addProcedure);
    fireEvent.click(removeProcedure);
    expect(api.post).not.toHaveBeenCalled();
  });

  it('control: without readOnly the modal still offers Save and POSTs the EMR draft', async () => {
    render(
      <ToothModal open toothNumber={16} toothData={toothData} visitId={41} onClose={vi.fn()} onSave={vi.fn()} />,
    );

    expect(screen.queryByText('dental.dental_tm_inspection_only')).toBeNull();
    const save = screen.getByRole('button', { name: 'dental.dental_tm_save' });
    expect(save).toBeDefined();

    fireEvent.click(save);
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    expect(api.post).toHaveBeenCalledWith('/v2/emr/41', expect.objectContaining({ row_version: 1 }));
  });
});
