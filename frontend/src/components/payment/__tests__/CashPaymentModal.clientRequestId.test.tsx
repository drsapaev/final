/**
 * CSH-FE-008 remainder (P1 issue 3859) — client_request_id lifecycle.
 *
 * Fail-first proven against the pre-fix source: the modal's submit payload
 * carried no idempotency key, so a network-loss retry (the response never
 * reached the cashier, the single-flight guard released, the cashier
 * pressed "Оплатить" again) posted a brand-new request the server could
 * not distinguish from a deliberate second charge.
 *
 * Fix contract (issue 3859):
 *   - the modal generates ONE UUID per modal session (per mount): every
 *     submit inside the same modal — including retries after a failed
 *     round-trip — reuses the same key, so the server replays the
 *     original payment response instead of charging twice;
 *   - a deliberate new attempt (modal closed and reopened = remount)
 *     gets a fresh key;
 *   - the key is a UUID so the backend request validation accepts it.
 */
import { fireEvent, render, screen } from '@testing-library/react';
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

import CashPaymentModal from '../CashPaymentModal';

const payableVisit = {
  id: 52,
  patient_id: 13,
  patient_name: 'Идемпотентный Игорь Игоревич',
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

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const submitOnce = () => {
  fireEvent.change(getAmountInput(), { target: { value: '250000' } });
  fireEvent.submit(getForm());
};

describe('CashPaymentModal — client_request_id lifecycle (issue 3859)', () => {
  it('every submit payload carries a UUID client_request_id', () => {
    const onProcessPayment = vi.fn().mockResolvedValue(undefined);
    render(
      <CashPaymentModal
        appointment={payableVisit}
        onProcessPayment={onProcessPayment}
        onClose={vi.fn()}
      />,
    );

    submitOnce();

    expect(onProcessPayment).toHaveBeenCalledTimes(1);
    const payload = onProcessPayment.mock.calls[0][1] as Record<string, unknown>;
    expect(String(payload.client_request_id)).toMatch(UUID_RE);
  });

  it('reuses the same key across retries inside one modal session (network-loss retry)', async () => {
    // First round-trip "fails" from the modal's perspective (the parent
    // surfaces the error and keeps the modal open); the cashier retries.
    const onProcessPayment = vi
      .fn()
      .mockRejectedValueOnce(new Error('network lost'))
      .mockResolvedValueOnce(undefined);
    render(
      <CashPaymentModal
        appointment={payableVisit}
        onProcessPayment={onProcessPayment}
        onClose={vi.fn()}
      />,
    );

    submitOnce();
    await vi.waitFor(() => expect(onProcessPayment).toHaveBeenCalledTimes(1));

    submitOnce();
    await vi.waitFor(() => expect(onProcessPayment).toHaveBeenCalledTimes(2));

    const first = onProcessPayment.mock.calls[0][1] as Record<string, unknown>;
    const second = onProcessPayment.mock.calls[1][1] as Record<string, unknown>;
    expect(second.client_request_id).toBe(first.client_request_id);
  });

  it('regenerates the key when the modal is reopened (deliberate new attempt)', () => {
    const onProcessPayment = vi.fn().mockResolvedValue(undefined);
    const first = render(
      <CashPaymentModal
        appointment={payableVisit}
        onProcessPayment={onProcessPayment}
        onClose={vi.fn()}
      />,
    );
    submitOnce();
    const firstKey = (onProcessPayment.mock.calls[0][1] as Record<string, unknown>)
      .client_request_id;

    // Close (unmount) and reopen (remount) — a new payment intent.
    first.unmount();
    render(
      <CashPaymentModal
        appointment={payableVisit}
        onProcessPayment={onProcessPayment}
        onClose={vi.fn()}
      />,
    );
    submitOnce();

    expect(onProcessPayment).toHaveBeenCalledTimes(2);
    const secondKey = (onProcessPayment.mock.calls[1][1] as Record<string, unknown>)
      .client_request_id;
    expect(secondKey).toMatch(UUID_RE);
    expect(secondKey).not.toBe(firstKey);
  });
});
