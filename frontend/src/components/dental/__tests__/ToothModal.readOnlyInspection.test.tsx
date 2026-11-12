/**
 * RETRO-3966-01 (post-merge review 3968, P2) — fail-first regressions for
 * the inspection-only ToothModal.
 *
 * The locked/read-only tooth chart (signed EMR, pending hydration or
 * completion) routed its clicks through onInspect into the FULL editable
 * ToothModal: editable fields, enabled Save for a meaningful record, and a
 * direct POST /v2/emr on save. The modal now has an explicit inspection
 * mode:
 *
 *  - an honest read-only banner (dental2.tooth_inspection_only) explains
 *    why nothing is editable;
 *  - NO Save affordance is rendered at all (not merely disabled);
 *  - every editable control is disabled (fieldset) — pointer AND keyboard
 *    activation are impossible;
 *  - handleSave early-returns before any write (defense in depth) —
 *    api.post('/v2/emr/...') is never called in inspection mode;
 *  - persisted tooth data stays visible for inspection.
 */
import { fireEvent, render, screen } from '@testing-library/react';
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

const INSPECTION_BANNER = 'dental2.tooth_inspection_only';
const SAVE_BUTTON_NAME = 'dental.dental_tm_save';
const FILLING_BUTTON_NAME = 'Пломба';
const NOTES_PLACEHOLDER = 'dental.dental_tm_notes_placeholder';

const toothData = {
  status: 'filled',
  notes: 'SYNTHETIC persisted note',
  procedures: [{ id: 'p1', name: 'SYNTHETIC filling', price: 1000 }],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.get).mockResolvedValue({ status: 200, data: { data: {}, row_version: 1 } } as never);
  vi.mocked(api.post).mockResolvedValue({ data: { row_version: 2 } } as never);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe('ToothModal inspection mode (RETRO-3966-01)', () => {
  it('renders the honest inspection banner and NO Save affordance', () => {
    render(
      <ToothModal
        open
        readOnly
        toothNumber={16}
        toothData={toothData}
        visitId={321}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText(INSPECTION_BANNER)).toBeTruthy();
    expect(screen.queryByRole('button', { name: SAVE_BUTTON_NAME })).toBeNull();
  });

  it('keeps the persisted tooth data visible for inspection', () => {
    render(
      <ToothModal
        open
        readOnly
        toothNumber={16}
        toothData={toothData}
        visitId={321}
        onClose={vi.fn()}
      />,
    );

    const notes = screen.getByPlaceholderText(NOTES_PLACEHOLDER) as HTMLTextAreaElement;
    expect(notes.value).toBe('SYNTHETIC persisted note');
  });

  it('disables every editable control — pointer and keyboard activation are impossible', () => {
    render(
      <ToothModal
        open
        readOnly
        toothNumber={16}
        toothData={toothData}
        visitId={321}
        onClose={vi.fn()}
      />,
    );

    const notes = screen.getByPlaceholderText(NOTES_PLACEHOLDER) as HTMLTextAreaElement;
    expect(notes.disabled).toBe(true);

    const fillingButton = screen.getByRole('button', { name: FILLING_BUTTON_NAME }) as HTMLButtonElement;
    expect(fillingButton.disabled).toBe(true);
  });

  it('never reaches the EMR write regardless of interaction attempts', () => {
    const onSave = vi.fn();
    render(
      <ToothModal
        open
        readOnly
        toothNumber={16}
        toothData={toothData}
        visitId={321}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );

    const fillingButton = screen.getByRole('button', { name: FILLING_BUTTON_NAME }) as HTMLButtonElement;
    fireEvent.click(fillingButton);
    // the persisted note stays visible for inspection
    const notes = screen.getByPlaceholderText(NOTES_PLACEHOLDER) as HTMLTextAreaElement;
    expect(notes.value).toBe('SYNTHETIC persisted note');
    // clicking a disabled procedure button adds no second procedure row
    expect(screen.queryByText('SYNTHETIC filling')).toBeTruthy();

    expect(api.post).not.toHaveBeenCalled();
    expect(api.get).not.toHaveBeenCalled();
    expect(onSave).not.toHaveBeenCalled();
  });

  it('control: the default (editable) modal still renders Save', () => {
    render(
      <ToothModal
        open
        toothNumber={16}
        toothData={toothData}
        visitId={321}
        onSave={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.queryByText(INSPECTION_BANNER)).toBeNull();
    expect(screen.getByRole('button', { name: SAVE_BUTTON_NAME })).toBeTruthy();
  });
});
