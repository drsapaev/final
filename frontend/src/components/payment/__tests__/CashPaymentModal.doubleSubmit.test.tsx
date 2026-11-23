/**
 * CSH-FE-008 regression tests — single-flight cash submit in CashPaymentModal.
 *
 * Fail-first proven on the pre-fix source: `handleSubmit` fired
 * `onProcessPayment?.()` fire-and-forget with no lock, so a rapid second
 * click / Enter during the server round-trip re-POSTed /cashier/payments.
 * The backend has no idempotency key (PaymentCreateRequest carries no
 * client_request_id), so every duplicate in-flight submit is a live double
 * charge for the patient.
 *
 * Fix contract (audit ledger 2026-11-01, CSH-FE-008):
 *   - a synchronous ref guard swallows duplicate submits in the same tick;
 *   - the submit button is disabled + aria-busy for the whole round-trip;
 *   - the guard releases when the parent handler settles — failure keeps
 *     the modal open and a corrected retry must go through;
 *   - validation warnings never engage the guard.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('../../../i18n/useTranslation', () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params && params.amount !== undefined ? `${key}:${String(params.amount)}` : key,
  }),
}));

vi.mock('../../../services/notify', () => ({
  default: {
    warning: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

import notify from '../../../services/notify';
import CashPaymentModal from '../CashPaymentModal';

const payableVisit = {
  id: 51,
  patient_id: 12,
  patient_name: 'Двойкин Двой Двойович',
  department: 'Хирургия',
  appointment_date: '2026-11-04',
  appointment_time: '12:00',
  total_amount: '250000',
  paid_amount: '0',
  remaining_amount: '250000',
};

const getForm = () => document.getElementById('cash-payment-form') as HTMLFormElement;

const getAmountInput = () =>
  screen.getByLabelText('payment.pay_cash_amount_aria') as HTMLInputElement;

const getSubmitButton = () =>
  screen.getByRole('button', { name: 'payment.pay_cash_submit' }) as HTMLButtonElement;

describe('CashPaymentModal — CSH-FE-008 single-flight submit', () => {
  it('a rapid double submit fires onProcessPayment exactly once', () => {
    const onProcessPayment = vi.fn(() => new Promise<void>(() => { /* in flight forever */ }));
    render(
      <CashPaymentModal
        appointment={payableVisit}
        onProcessPayment={onProcessPayment}
        onClose={vi.fn()}
      />,
    );

    fireEvent.submit(getForm());
    fireEvent.submit(getForm());
    fireEvent.submit(getForm());

    // Synchronous assertion: the pre-fix source fired one call per submit
    // event; the guard must swallow the duplicates in the same tick.
    expect(onProcessPayment).toHaveBeenCalledTimes(1);
  });

  it('locks the submit button (disabled + aria-busy) while the payment is in flight', () => {
    const onProcessPayment = vi.fn(() => new Promise<void>(() => { /* in flight forever */ }));
    render(
      <CashPaymentModal
        appointment={payableVisit}
        onProcessPayment={onProcessPayment}
        onClose={vi.fn()}
      />,
    );

    expect(getSubmitButton()).toBeEnabled();
    fireEvent.submit(getForm());

    expect(onProcessPayment).toHaveBeenCalledTimes(1);
    expect(getSubmitButton()).toBeDisabled();
    expect(getSubmitButton().getAttribute('aria-busy')).toBe('true');
  });

  it('re-enables the button and accepts a new submit after the payment settles', async () => {
    let resolvePayment!: () => void;
    const onProcessPayment = vi.fn(
      () => new Promise<void>((resolve) => { resolvePayment = resolve; }),
    );
    render(
      <CashPaymentModal
        appointment={payableVisit}
        onProcessPayment={onProcessPayment}
        onClose={vi.fn()}
      />,
    );

    fireEvent.submit(getForm());
    expect(onProcessPayment).toHaveBeenCalledTimes(1);
    expect(getSubmitButton()).toBeDisabled();

    resolvePayment();
    await waitFor(() => expect(getSubmitButton()).toBeEnabled());

    fireEvent.submit(getForm());
    expect(onProcessPayment).toHaveBeenCalledTimes(2);
  });

  it('validation failures do not engage the guard — a corrected retry goes through', async () => {
    const onProcessPayment = vi.fn().mockResolvedValue(undefined);
    render(
      <CashPaymentModal
        appointment={payableVisit}
        onProcessPayment={onProcessPayment}
        onClose={vi.fn()}
      />,
    );

    fireEvent.change(getAmountInput(), { target: { value: '' } });
    fireEvent.submit(getForm());

    expect(onProcessPayment).not.toHaveBeenCalled();
    expect(notify.warning).toHaveBeenCalledWith('payment.invalid_amount');
    expect(getSubmitButton()).toBeEnabled();

    fireEvent.change(getAmountInput(), { target: { value: '250000' } });
    fireEvent.submit(getForm());

    await waitFor(() => expect(onProcessPayment).toHaveBeenCalledTimes(1));
    expect(getSubmitButton()).toBeEnabled();
  });

  it('a failed payment unlocks the form so the cashier can retry in place', async () => {
    let rejectPayment!: (reason?: unknown) => void;
    const onProcessPayment = vi.fn(
      () => new Promise<void>((_resolve, reject) => { rejectPayment = reject; }),
    );
    render(
      <CashPaymentModal
        appointment={payableVisit}
        onProcessPayment={onProcessPayment}
        onClose={vi.fn()}
      />,
    );

    fireEvent.submit(getForm());
    expect(getSubmitButton()).toBeDisabled();

    rejectPayment(new Error('declined'));
    await waitFor(() => expect(getSubmitButton()).toBeEnabled());

    // The retry after a rejection must reach the parent handler again.
    onProcessPayment.mockResolvedValue(undefined);
    fireEvent.submit(getForm());
    await waitFor(() => expect(onProcessPayment).toHaveBeenCalledTimes(2));
  });
});
