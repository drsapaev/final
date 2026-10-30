/**
 * #3808 (CR-01 / REG-FE-025) — ForceMajeureModal fail-first contract.
 *
 * The destructive whole-queue transfer / cancel-with-refund commands are
 * financial mutations. They may only be enabled when the server scope was
 * validated by a successful non-empty dry-run preview, and the mutation
 * must stay bound to the same specialist + queue date that was previewed.
 *
 * Pins:
 * - preview requests the canonical target: specialist_id + target_date
 *   + the row's daily_queue_id (round 2: the backend targets EXACTLY that
 *   queue instead of resolving the specialist onto a shared surface)
 * - failed / in-flight / stale / empty previews never enable the primary
 *   action, even after typing ПОДТВЕРЖДАЮ + a valid reason
 * - re-targeting the modal (another row/day/queue) re-locks the action until
 *   the new preview succeeds and binds the mutation to the NEW target
 * - an OUT-OF-ORDER late preview response for a previous target never
 *   authorizes the current one (round 2 P1: deferred A/B regression)
 * - a preview refresh that fails re-locks a previously authorized action
 * - a synchronous double submit fires exactly one financial mutation
 * - POST bodies carry the same specialist_id + target_date + daily_queue_id
 *   as the preview
 */
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../api/client', () => ({
  api: { get: vi.fn(), post: vi.fn() },
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

import { api } from '../../../api/client';
import ForceMajeureModal from '../ForceMajeureModal';

const apiGet = vi.mocked(api.get);
const apiPost = vi.mocked(api.post);

const REASON = 'Затопление кабинета';

function renderModal(props: Partial<React.ComponentProps<typeof ForceMajeureModal>> = {}) {
  return render(
    <ForceMajeureModal
      isOpen
      onClose={vi.fn()}
      specialistId={3}
      specialistName="Dr X"
      targetDate="2026-10-30"
      dailyQueueId={41}
      {...props}
    />,
  );
}

function submitButton() {
  return screen.getByRole('button', { name: 'misc.fm_transfer_button' });
}

function cancelButton() {
  return screen.getByRole('button', { name: 'misc.fm_cancel_button' });
}

async function fillConfirmation() {
  fireEvent.change(screen.getByLabelText('Force majeure reason'), { target: { value: REASON } });
  fireEvent.change(screen.getByLabelText('Type confirmation phrase'), { target: { value: 'ПОДТВЕРЖДАЮ' } });
}

describe('ForceMajeureModal (#3808 REG-FE-025)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('previews the pending entries bound to the specialist and the target date', async () => {
    apiGet.mockResolvedValueOnce({ data: [{ id: 101, total_amount: 1 }, { id: 102, total_amount: 2 }] } as never);
    renderModal();
    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(1));
    expect(apiGet).toHaveBeenCalledWith(
      '/force-majeure/pending-entries?specialist_id=3&target_date=2026-10-30&daily_queue_id=41',
    );
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:2')).toBeInTheDocument());
  });

  it('enables the destructive action only after a successful non-empty preview', async () => {
    apiGet.mockResolvedValueOnce({ data: [{ total_amount: 1 }] } as never);
    renderModal();
    await fillConfirmation();
    // preview still in flight: typing ПОДТВЕРЖДАЮ alone must not enable it
    expect(submitButton()).toBeDisabled();
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument());
    expect(submitButton()).toBeEnabled();
  });

  it('keeps the destructive action disabled when the preview request fails', async () => {
    apiGet.mockRejectedValueOnce(new Error('boom') as never);
    renderModal();
    await fillConfirmation();
    await waitFor(() => expect(screen.getByText('misc.fm_preview_failed')).toBeInTheDocument());
    expect(submitButton()).toBeDisabled();
  });

  it('keeps the destructive action disabled for an empty preview', async () => {
    apiGet.mockResolvedValueOnce({ data: [] } as never);
    renderModal();
    await fillConfirmation();
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:0')).toBeInTheDocument());
    expect(submitButton()).toBeDisabled();
  });

  it('cannot authorize a mutation from a stale preview while the target row/day changes', async () => {
    apiGet.mockResolvedValueOnce({ data: [{ total_amount: 1 }] } as never);
    const { rerender } = renderModal();
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument());
    await fillConfirmation();
    expect(submitButton()).toBeEnabled();

    // re-target the open modal at another row/day/queue: the old preview is stale
    let resolveSecondPreview!: (value: unknown) => void;
    apiGet.mockImplementationOnce(
      () => new Promise((resolve) => { resolveSecondPreview = resolve; }) as never,
    );
    rerender(
      <ForceMajeureModal
        isOpen
        onClose={vi.fn()}
        specialistId={5}
        specialistName="Dr Y"
        targetDate="2026-10-31"
        dailyQueueId={55}
      />,
    );
    await fillConfirmation();
    // stale preview + new preview in flight: the action stays locked
    expect(submitButton()).toBeDisabled();

    resolveSecondPreview({ data: [{ id: 901, total_amount: 9 }] });
    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(submitButton()).toBeEnabled());

    // the mutation is bound to the NEW specialist + date + queue + SNAPSHOT,
    // not the stale ones (round 3: expected_entry_ids carries the preview set)
    fireEvent.click(submitButton());
    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(1));
    expect(apiPost).toHaveBeenCalledWith('/force-majeure/transfer', {
      specialist_id: 5,
      target_date: '2026-10-31',
      daily_queue_id: 55,
      expected_entry_ids: [901],
      reason: REASON,
      send_notifications: true,
    });
  });

  it('an out-of-order late preview response never authorizes the current target (round 2 P1)', async () => {
    // Row A preview hangs; while it is pending the modal is re-targeted at
    // row B (its preview hangs too); only THEN does A resolve — late.
    let resolvePreviewA!: (value: unknown) => void;
    let resolvePreviewB!: (value: unknown) => void;
    apiGet.mockImplementationOnce(
      () => new Promise((resolve) => { resolvePreviewA = resolve; }) as never,
    );
    const { rerender } = renderModal();
    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(1));

    apiGet.mockImplementationOnce(
      () => new Promise((resolve) => { resolvePreviewB = resolve; }) as never,
    );
    rerender(
      <ForceMajeureModal
        isOpen
        onClose={vi.fn()}
        specialistId={5}
        specialistName="Dr Y"
        targetDate="2026-10-31"
        dailyQueueId={55}
      />,
    );
    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(2));
    await fillConfirmation();

    // A resolves LATE (after B's request started): its data must be discarded —
    // B is still unvalidated, so the destructive action stays locked.
    await act(async () => {
      resolvePreviewA({ data: [{ total_amount: 1 }] });
    });
    expect(screen.queryByText('misc.fm_entries_count:1')).not.toBeInTheDocument();
    expect(submitButton()).toBeDisabled();

    // B resolves: only now the action unlocks, bound to B's target facts.
    await act(async () => {
      resolvePreviewB({ data: [{ id: 711, total_amount: 7 }, { id: 712, total_amount: 8 }] });
    });
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:2')).toBeInTheDocument());
    expect(submitButton()).toBeEnabled();
    fireEvent.click(submitButton());
    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(1));
    expect(apiPost).toHaveBeenCalledWith('/force-majeure/transfer', {
      specialist_id: 5,
      target_date: '2026-10-31',
      daily_queue_id: 55,
      expected_entry_ids: [711, 712],
      reason: REASON,
      send_notifications: true,
    });
  });

  it('re-locks a previously authorized action when the preview refresh fails', async () => {
    apiGet.mockResolvedValueOnce({ data: [{ total_amount: 1 }] } as never);
    renderModal();
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument());
    await fillConfirmation();
    expect(submitButton()).toBeEnabled();

    apiGet.mockRejectedValueOnce(new Error('boom') as never);
    fireEvent.click(screen.getByLabelText('misc.fm_aria_refresh'));
    await waitFor(() => expect(screen.getByText('misc.fm_preview_failed')).toBeInTheDocument());
    expect(submitButton()).toBeDisabled();
  });

  it('sends the previewed specialist and target date to the transfer mutation', async () => {
    apiGet.mockResolvedValueOnce({ data: [{ id: 101, total_amount: 1 }] } as never);
    renderModal();
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument());
    await fillConfirmation();
    fireEvent.click(submitButton());
    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(1));
    expect(apiPost).toHaveBeenCalledWith('/force-majeure/transfer', {
      specialist_id: 3,
      target_date: '2026-10-30',
      daily_queue_id: 41,
      expected_entry_ids: [101],
      reason: REASON,
      send_notifications: true,
    });
  });

  it('sends the previewed specialist and target date to the cancel-with-refund mutation', async () => {
    apiGet.mockResolvedValueOnce({ data: [{ id: 101, total_amount: 1 }] } as never);
    renderModal();
    fireEvent.click(screen.getByRole('button', { name: 'misc.fm_tab_cancel' }));
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument());
    await fillConfirmation();
    fireEvent.click(cancelButton());
    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(1));
    expect(apiPost).toHaveBeenCalledWith('/force-majeure/cancel-with-refund', {
      specialist_id: 3,
      target_date: '2026-10-30',
      daily_queue_id: 41,
      expected_entry_ids: [101],
      reason: REASON,
      refund_type: 'deposit',
      send_notifications: true,
    });
  });

  it('a synchronous double submit fires exactly one financial mutation', async () => {
    apiGet.mockResolvedValueOnce({ data: [{ total_amount: 1 }] } as never);
    renderModal();
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument());
    await fillConfirmation();
    let resolvePost!: (value: unknown) => void;
    apiPost.mockImplementationOnce(
      () => new Promise((resolve) => { resolvePost = resolve; }) as never,
    );

    // two raw synchronous dispatches on the same stack: no re-render may
    // interleave, so only an in-flight guard can prevent the second POST
    const btn = submitButton();
    await act(async () => {
      btn.click();
      btn.click();
    });

    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(1));
    expect(apiPost).toHaveBeenCalledTimes(1);
    await act(async () => {
      resolvePost({ data: { transferred: 1 } } as never);
    });
  });

  it('a 409 drift refusal re-locks the action until a fresh preview (round 3 P1)', async () => {
    // Preview sees one patient; the server reports the queue changed since
    // that preview (a patient joined / disappeared) — the confirmation must
    // NOT stay authorized against the stale snapshot.
    apiGet.mockResolvedValueOnce({ data: [{ id: 101, total_amount: 1 }] } as never);
    renderModal();
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument());
    await fillConfirmation();
    expect(submitButton()).toBeEnabled();

    apiPost.mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          detail:
            'Состав очереди изменился после предпросмотра (добавилось: 1, исчезло: 0). Обновите предпросмотр и подтвердите новый состав',
        },
      },
    } as never);

    fireEvent.click(submitButton());
    await waitFor(() => expect(screen.getByText('misc.fm_queue_changed')).toBeInTheDocument());

    // The stale dry-run card is gone and the action is locked again:
    // typing ПОДТВЕРЖДАЮ must not re-enable it against the stale snapshot.
    expect(screen.queryByText('misc.fm_entries_count:1')).not.toBeInTheDocument();
    expect(submitButton()).toBeDisabled();

    // A fresh preview re-authorizes with the NEW snapshot.
    apiGet.mockResolvedValueOnce({ data: [{ id: 101, total_amount: 1 }, { id: 105, total_amount: 2 }] } as never);
    fireEvent.click(screen.getByLabelText('misc.fm_aria_refresh'));
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:2')).toBeInTheDocument());
    expect(submitButton()).toBeEnabled();

    fireEvent.click(submitButton());
    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(2));
    expect(apiPost).toHaveBeenLastCalledWith('/force-majeure/transfer', {
      specialist_id: 3,
      target_date: '2026-10-30',
      daily_queue_id: 41,
      expected_entry_ids: [101, 105],
      reason: REASON,
      send_notifications: true,
    });
  });
});
