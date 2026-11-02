/**
 * REG-FE-017 (registrar audit ledger #3803) — CancelDialog result contract.
 *
 * The cancel command can resolve WITHOUT cancelling anything:
 * runRegistrarRecordAction returns null after missing record refs or backend
 * action unavailability, and a partial server batch cancels only some of the
 * records. The dialog used to treat every normally resolved callback as
 * complete success (toast.success + onClose), while the parent re-threw
 * failures so the user could see two contradictory toasts.
 *
 * Contract under test:
 * - all_success     → exactly one success toast + close
 * - partial_success → dialog stays open, inline counts, NO success toast
 *                     (the parent already refreshed the worklist from the
 *                     server-owned read model)
 * - no_op           → stay open, inline error, no second toast from the
 *                     dialog (the shared action hook already reported it)
 * - failed          → stay open, inline error, exactly one error toast
 * - thrown error    → stay open, error toast, entered reason preserved
 * - legacy void     → fail-closed: a bare resolve is NOT proof of
 *                     cancellation — no success claim, dialog stays open
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('react-toastify', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}));

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, options?: Record<string, unknown>) =>
      options && 'count' in options ? `${key}:${String(options.count)}` : key,
    language: 'ru',
    setLanguage: vi.fn(),
    availableLanguages: [],
  }),
}));

import { toast } from 'react-toastify';
import CancelDialog from '../CancelDialog';

const REASON = 'Пациент заболел';

function renderDialog(onCancel: ReturnType<typeof vi.fn>) {
  const onClose = vi.fn();
  render(
    <CancelDialog
      isOpen
      onClose={onClose}
      appointment={{ id: 7, patient_fio: 'Синтетов Синтет' } as never}
      onCancel={onCancel as never}
    />,
  );
  return { onClose };
}

async function confirmCancel() {
  const textarea = screen.getByLabelText('misc.cd_prichina_otmeny_zapisi');
  fireEvent.change(textarea, { target: { value: REASON } });
  fireEvent.click(screen.getByRole('button', { name: 'misc.cd_podtverdit_otmenu' }));
  await waitFor(() => expect(textarea).toBeTruthy());
}

describe('CancelDialog outcome contract (REG-FE-017)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('an explicit all_success outcome is acknowledged once and closes the dialog', async () => {
    const onCancel = vi.fn().mockResolvedValue({ outcome: 'all_success' });
    const { onClose } = renderDialog(onCancel);
    await confirmCancel();
    await waitFor(() => expect(toast.success).toHaveBeenCalledTimes(1));
    expect(toast.success).toHaveBeenCalledWith('misc.cd_zapis_uspeshno_otmenena');
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('a partial batch is NOT reported as a successful cancellation and keeps the dialog open', async () => {
    const onCancel = vi.fn().mockResolvedValue({
      outcome: 'partial_success',
      successCount: 1,
      failedCount: 1,
    });
    const { onClose } = renderDialog(onCancel);
    await confirmCancel();
    await waitFor(() =>
      expect(screen.getByText(/Отменено записей: 1; не отменено: 1/)).toBeTruthy(),
    );
    expect(toast.success).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('a no-op command (record refs / action unavailable) stays open without a success claim', async () => {
    const onCancel = vi.fn().mockResolvedValue({ outcome: 'no_op' });
    const { onClose } = renderDialog(onCancel);
    await confirmCancel();
    await waitFor(() =>
      expect(screen.getByText('misc.cd_oshibka_pri_otmene_zapisi')).toBeTruthy(),
    );
    expect(toast.success).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    // The shared action hook already reported the specific reason — the
    // dialog must not add a second, blander error toast.
    expect(toast.error).not.toHaveBeenCalled();
  });

  it('an all-failed batch shows one error toast with the server reason and stays open', async () => {
    const onCancel = vi.fn().mockResolvedValue({
      outcome: 'failed',
      message: 'visit_already_cancelled',
    });
    const { onClose } = renderDialog(onCancel);
    await confirmCancel();
    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1));
    expect(toast.error).toHaveBeenCalledWith(
      'misc.cd_oshibka_pri_otmene_zapisi: visit_already_cancelled',
    );
    expect(screen.getByText('visit_already_cancelled')).toBeTruthy();
    expect(toast.success).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('a legacy void resolution is not treated as proof of cancellation (fail-closed)', async () => {
    const onCancel = vi.fn().mockResolvedValue(undefined);
    const { onClose } = renderDialog(onCancel);
    await confirmCancel();
    await waitFor(() =>
      expect(screen.getByText('misc.cd_oshibka_pri_otmene_zapisi')).toBeTruthy(),
    );
    expect(toast.success).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('a thrown error keeps the dialog open and preserves the entered reason', async () => {
    const onCancel = vi.fn().mockRejectedValue(new Error('network down'));
    const { onClose } = renderDialog(onCancel);
    await confirmCancel();
    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1));
    expect(toast.success).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    const textarea = screen.getByLabelText('misc.cd_prichina_otmeny_zapisi') as HTMLTextAreaElement;
    expect(textarea.value).toBe(REASON);
  });
});
