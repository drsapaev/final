/**
 * Audit 3892 round 1 — fail-first regressions for ToothModal write integrity.
 *
 * Covers:
 *  - DENTMODAL-FE-001 (modal half): the modal's independent POST response
 *    row_version must be handed back through onSave so the parent can keep
 *    its optimistic-lock version current.
 *  - DENTMODAL-FE-002 (modal half, defense in depth): the local clinical form
 *    re-hydrates from toothData when visitId changes, so a still-open modal
 *    never keeps stale patient-A edits against a new visit context.
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
  notes: 'SYNTHETIC baseline note',
  procedures: [{ id: 'p1', name: 'SYNTHETIC filling', price: 1000 }],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: { data: {}, row_version: 1 } } as never);
  vi.mocked(api.post).mockResolvedValue({ data: { row_version: 2 } } as never);
});

describe('ToothModal write integrity (audit 3892 round 1)', () => {
  it('DENTMODAL-FE-001: onSave receives the row_version returned by the modal POST', async () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(
      <ToothModal open toothNumber={16} toothData={toothData} visitId={41} onSave={onSave} onClose={onClose} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'dental.dental_tm_save' }));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    expect(api.post).toHaveBeenCalledWith('/v2/emr/41', expect.objectContaining({ row_version: 1 }));
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const [payload, rowVersion] = onSave.mock.calls[0];
    expect(payload).toEqual(expect.objectContaining({ toothNumber: 16, status: 'filled' }));
    expect(rowVersion).toBe(2);
  });

  it('DENTMODAL-FE-002: local form edits reset when visitId changes while the modal stays open', async () => {
    const view = render(
      <ToothModal open toothNumber={16} toothData={toothData} visitId={41} onSave={vi.fn()} onClose={vi.fn()} />,
    );

    const notesBox = screen.getByDisplayValue('SYNTHETIC baseline note');
    fireEvent.change(notesBox, { target: { value: 'SYNTHETIC baseline note + local edit for A' } });

    view.rerender(
      <ToothModal open toothNumber={16} toothData={toothData} visitId={42} onSave={vi.fn()} onClose={vi.fn()} />,
    );

    await waitFor(() => expect(screen.getByDisplayValue('SYNTHETIC baseline note'))
      .toHaveProperty('value', 'SYNTHETIC baseline note'));
  });
});
