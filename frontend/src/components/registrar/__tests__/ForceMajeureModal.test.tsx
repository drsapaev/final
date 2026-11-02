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
    t: (key: string, options?: Record<string, unknown>) => {
      if (!options) return key;
      if ('count' in options) return `${key}:${String(options.count)}`;
      // 3808 review round 13 (residual P2): success-сообщение отмены —
      // раздельные части, интерполирующие cancelled/count; без этих
      // веток тесты счётчиков не видят подставленных значений.
      if ('cancelled' in options) {
        return `${key}:${String(options.cancelled)}`;
      }
      return key;
    },
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
    // round 11: этот мок намеренно БЕЗ заголовка X-Error-Code — тест
    // пинирует фолбэк-дискриминатор по точному префиксу текста дрейфа
    // (ответ старого бэкенда или прокси, стрипающего заголовки)

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

  it('an owner-conflict 409 shows the server refusal instead of a drift message (round 11 P2)', async () => {
    // Round 10 made the server refuse an owner-mismatched transfer as
    // 409 force_majeure_domain_refusal. That is NOT a snapshot drift:
    // the registrar must see the server's explanation as is — refreshing
    // the preview cannot fix an owner conflict, so attributing it to
    // «состав изменился» traps the operator in a misleading loop.
    apiGet.mockResolvedValueOnce({ data: [{ id: 101, total_amount: 1 }] } as never);
    renderModal();
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument());
    await fillConfirmation();
    expect(submitButton()).toBeEnabled();

    const refusal =
      'Операция отклонена: перенос отклонён — поверхность назначения (id=77, тег lab, 2026-10-31) ' +
      'принадлежит другому владельцу: активная врачебная очередь того же тега; ' +
      'перенос ресурсных пациентов в неё запрещён';
    apiPost.mockRejectedValueOnce({
      response: {
        status: 409,
        headers: { 'x-error-code': 'force_majeure_domain_refusal' },
        data: { detail: refusal },
      },
    } as never);

    fireEvent.click(submitButton());
    await waitFor(() => expect(screen.getByText(refusal)).toBeInTheDocument());

    // NOT attributed to snapshot drift: no misleading «состав изменился»,
    // the valid preview card is kept and the action stays available —
    // the server's refusal explains itself, a re-preview would not help.
    expect(screen.queryByText('misc.fm_queue_changed')).not.toBeInTheDocument();
    expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument();
    expect(submitButton()).toBeEnabled();
  });

  it('an owner-conflict 409 on cancel-with-refund shows the server refusal too (round 11 P2)', async () => {
    // The same refusal class through the SECOND financial mutation: the
    // cancel handler shares the drift predicate, so a domain refusal
    // must not be labelled as snapshot drift there either.
    apiGet.mockResolvedValueOnce({ data: [{ id: 101, total_amount: 1 }] } as never);
    renderModal();
    fireEvent.click(screen.getByRole('button', { name: 'misc.fm_tab_cancel' }));
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument());
    await fillConfirmation();
    expect(cancelButton()).toBeEnabled();

    const refusal =
      'Операция отклонена: отмена отклонена — очередь принадлежит другому владельцу, ' +
      'возврат средств не выполнен';
    apiPost.mockRejectedValueOnce({
      response: {
        status: 409,
        headers: { 'x-error-code': 'force_majeure_domain_refusal' },
        data: { detail: refusal },
      },
    } as never);

    fireEvent.click(cancelButton());
    await waitFor(() => expect(screen.getByText(refusal)).toBeInTheDocument());

    expect(screen.queryByText('misc.fm_queue_changed')).not.toBeInTheDocument();
    expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument();
  });

  it('a 409 carrying the drift error code is drift even when the detail text differs (round 11)', async () => {
    // The machine-readable X-Error-Code wins over the detail wording: a
    // drift refusal keeps its re-lock semantics whatever the server's
    // phrasing (here deliberately NOT matching the drift text prefix).
    apiGet.mockResolvedValueOnce({ data: [{ id: 101, total_amount: 1 }] } as never);
    renderModal();
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument());
    await fillConfirmation();
    expect(submitButton()).toBeEnabled();

    apiPost.mockRejectedValueOnce({
      response: {
        status: 409,
        headers: { 'x-error-code': 'force_majeure_preview_drift' },
        data: {
          detail:
            'Queue composition changed after the preview (added: 1, removed: 0). Re-run the preview and confirm the new set',
        },
      },
    } as never);

    fireEvent.click(submitButton());
    await waitFor(() => expect(screen.getByText('misc.fm_queue_changed')).toBeInTheDocument());

    // drift semantics: the stale card is dropped and the action re-locks
    expect(screen.queryByText('misc.fm_entries_count:1')).not.toBeInTheDocument();
    expect(submitButton()).toBeDisabled();
  });

  it('cancel success shows SPLIT messages: bank requests vs deposit credits — never one merged "refunds" number (#3809 P2)', async () => {
    apiGet.mockResolvedValueOnce({ data: [{ id: 101, total_amount: 1 }] } as never);
    renderModal();
    fireEvent.click(screen.getByRole('button', { name: 'misc.fm_tab_cancel' }));
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument());
    await fillConfirmation();
    expect(cancelButton()).toBeEnabled();

    // Контракт API: refund_requests_created + deposit_credits_created.
    // Поля refunds_created в ответе НЕТ. Банковская заявка — pending
    // (деньги ЕЩЁ не возвращены) — показываем отдельной строкой,
    // НЕ суммируем с зачислениями на депозит.
    apiPost.mockResolvedValueOnce({
      data: {
        success: true,
        cancelled: 3,
        refund_requests_created: 1,
        refund_requests_existing: 1,
        deposit_credits_created: 2,
        deposit_credits_existing: 0,
      },
    } as never);

    fireEvent.click(cancelButton());
    // Раздельные части: 3 отмены, 1 заявка, 2 зачисления — и НИКАКОЙ
    // объединённой суммы «возвратов: 3».
    await waitFor(() =>
      expect(screen.getByText(/misc\.fm_cancel_success_cancelled:3/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/misc\.fm_cancel_success_bank_requests:1/)).toBeInTheDocument();
    expect(screen.getByText(/misc\.fm_cancel_success_deposit_credits:2/)).toBeInTheDocument();
    expect(screen.queryByText(/fm_cancel_success_no_refunds/)).not.toBeInTheDocument();
  });

  it('deposit-only cancel counts deposit credits, not the absent bank counter (#3809 P2)', async () => {
    apiGet.mockResolvedValueOnce({ data: [{ id: 101, total_amount: 1 }] } as never);
    renderModal();
    fireEvent.click(screen.getByRole('button', { name: 'misc.fm_tab_cancel' }));
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument());
    await fillConfirmation();

    // Только депозитные зачисления: банковских заявок нет — 0
    apiPost.mockResolvedValueOnce({
      data: {
        success: true,
        cancelled: 2,
        refund_requests_created: 0,
        refund_requests_existing: 0,
        deposit_credits_created: 2,
        deposit_credits_existing: 0,
      },
    } as never);

    fireEvent.click(cancelButton());
    await waitFor(() =>
      expect(screen.getByText(/misc\.fm_cancel_success_deposit_credits:2/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/misc\.fm_cancel_success_cancelled:2/)).toBeInTheDocument();
    // Банковской ветки нет — части про заявки быть не должно
    expect(screen.queryByText(/fm_cancel_success_bank_requests/)).not.toBeInTheDocument();
  });

  it('bank-only cancel: a pending request is a REQUEST, money is not refunded yet (#3809 round 13)', async () => {
    apiGet.mockResolvedValueOnce({ data: [{ id: 101, total_amount: 1 }] } as never);
    renderModal();
    fireEvent.click(screen.getByRole('button', { name: 'misc.fm_tab_cancel' }));
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument());
    await fillConfirmation();

    // Только банковские заявки: зачислений на депозит нет
    apiPost.mockResolvedValueOnce({
      data: {
        success: true,
        cancelled: 2,
        refund_requests_created: 2,
        refund_requests_existing: 0,
        deposit_credits_created: 0,
        deposit_credits_existing: 0,
      },
    } as never);

    fireEvent.click(cancelButton());
    await waitFor(() =>
      expect(screen.getByText(/misc\.fm_cancel_success_bank_requests:2/)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/fm_cancel_success_deposit_credits/)).not.toBeInTheDocument();
  });

  it('idempotent replay (only existing counters) shows no new money movements (#3809 round 13)', async () => {
    apiGet.mockResolvedValueOnce({ data: [{ id: 101, total_amount: 1 }] } as never);
    renderModal();
    fireEvent.click(screen.getByRole('button', { name: 'misc.fm_tab_cancel' }));
    await waitFor(() => expect(screen.getByText('misc.fm_entries_count:1')).toBeInTheDocument());
    await fillConfirmation();

    // Идемпотентный повтор: все возвраты уже существовали — новых
    // движений денег нет, сообщение не приписывает ни заявок, ни зачислений
    apiPost.mockResolvedValueOnce({
      data: {
        success: true,
        cancelled: 1,
        refund_requests_created: 0,
        refund_requests_existing: 1,
        deposit_credits_created: 0,
        deposit_credits_existing: 1,
      },
    } as never);

    fireEvent.click(cancelButton());
    await waitFor(() =>
      expect(screen.getByText(/misc\.fm_cancel_success_no_refunds/)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/fm_cancel_success_bank_requests/)).not.toBeInTheDocument();
    expect(screen.queryByText(/fm_cancel_success_deposit_credits/)).not.toBeInTheDocument();
  });
});
