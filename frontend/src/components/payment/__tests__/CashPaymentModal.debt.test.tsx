/**
 * CSH-FE-007 regression tests — remaining-debt default in CashPaymentModal.
 *
 * Fail-first proven on the pre-fix source (total_amount-first chain):
 * a visit with total=100000, paid=70000, remaining=30000 used to prefill
 * the FULL 100000, silently overpaying 70000 into an advance.
 *
 * Canonical basis (audit ledger 2026-11-01, CSH-FE-007):
 *   default = remaining_amount ?? total_amount ?? payment_amount
 *   deliberate overpay must be visible as an explicit advance notice.
 */
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { formatUZS } from '../../../utils/formatCurrency';

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

const partiallyPaidVisit = {
  id: 42,
  patient_id: 7,
  patient_name: 'Тестов Тест Тестович',
  department: 'Терапия',
  appointment_date: '2026-11-02',
  appointment_time: '10:00',
  total_amount: '100000',
  paid_amount: '70000',
  remaining_amount: '30000',
};

const getAmountInput = () =>
  screen.getByLabelText('payment.pay_cash_amount_aria') as HTMLInputElement;

const getReceivedInput = () =>
  screen.getByLabelText('payment.pay_cash_received_aria') as HTMLInputElement;

describe('CashPaymentModal — CSH-FE-007 remaining debt default', () => {
  it('prefills the remaining debt, not the original total (100000 → 30000)', () => {
    render(<CashPaymentModal appointment={partiallyPaidVisit} onProcessPayment={vi.fn()} onClose={vi.fn()} />);
    expect(getAmountInput().value).toBe('30000');
  });

  it('shows the remaining debt in the amount hint box', () => {
    render(<CashPaymentModal appointment={partiallyPaidVisit} onProcessPayment={vi.fn()} onClose={vi.fn()} />);
    const hint = document.querySelector('.cpm-amount-hint-box');
    expect(hint).not.toBeNull();
    expect(hint?.textContent).toContain(formatUZS(30000));
  });

  it('submits the remaining debt and the change for the default cash flow', () => {
    const onProcessPayment = vi.fn().mockResolvedValue(undefined);
    render(<CashPaymentModal appointment={partiallyPaidVisit} onProcessPayment={onProcessPayment} onClose={vi.fn()} />);

    fireEvent.change(getReceivedInput(), { target: { value: '50000' } });
    fireEvent.submit(document.getElementById('cash-payment-form')!);

    expect(onProcessPayment).toHaveBeenCalledTimes(1);
    const [appointmentArg, paymentArg] = onProcessPayment.mock.calls[0] as [
      Record<string, unknown>,
      Record<string, unknown>,
    ];
    expect(appointmentArg.remaining_amount).toBe('30000');
    expect(paymentArg.amount).toBe(30000);
    expect(paymentArg.received_amount).toBe(50000);
    expect(paymentArg.change_due).toBe(20000);
  });

  it('warns explicitly when the entered amount exceeds the remaining debt (advance)', () => {
    render(<CashPaymentModal appointment={partiallyPaidVisit} onProcessPayment={vi.fn()} onClose={vi.fn()} />);
    fireEvent.change(getAmountInput(), { target: { value: '40000' } });

    const notice = screen.getByTestId('cash-advance-notice');
    expect(notice.getAttribute('role')).toBe('alert');
    expect(notice.textContent).toContain(formatUZS(10000));
    expect(notice.textContent).toContain('payment.pay_cash_advance_notice');
  });

  it('shows no advance notice when the entered amount equals the remaining debt', () => {
    render(<CashPaymentModal appointment={partiallyPaidVisit} onProcessPayment={vi.fn()} onClose={vi.fn()} />);
    fireEvent.change(getAmountInput(), { target: { value: '30000' } });
    expect(screen.queryByTestId('cash-advance-notice')).toBeNull();
  });

  it('falls back to total_amount when remaining_amount is absent', () => {
    render(
      <CashPaymentModal
        appointment={{ id: 43, patient_id: 8, total_amount: '100000' }}
        onProcessPayment={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(getAmountInput().value).toBe('100000');
  });

  it('keeps a legitimate remaining_amount of 0 (does not fall through to total)', () => {
    render(
      <CashPaymentModal
        appointment={{ id: 44, patient_id: 9, total_amount: '100000', remaining_amount: '0' }}
        onProcessPayment={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(getAmountInput().value).toBe('0');
  });

  it('does not show the advance notice when no debt basis exists', () => {
    render(
      <CashPaymentModal
        appointment={{ id: 45, patient_id: 10 }}
        onProcessPayment={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    fireEvent.change(getAmountInput(), { target: { value: '40000' } });
    expect(screen.queryByTestId('cash-advance-notice')).toBeNull();
  });

  it('recomputes the prefill when the appointment prop changes', () => {
    const { rerender } = render(
      <CashPaymentModal appointment={partiallyPaidVisit} onProcessPayment={vi.fn()} onClose={vi.fn()} />,
    );
    expect(getAmountInput().value).toBe('30000');

    rerender(
      <CashPaymentModal
        appointment={{ id: 46, patient_id: 11, total_amount: '90000', remaining_amount: '15000' }}
        onProcessPayment={vi.fn()}
        onClose={vi.fn()}
      />,
    );
    expect(getAmountInput().value).toBe('15000');
  });

  it('recomputes the advance notice when the amount grows past the debt', () => {
    render(<CashPaymentModal appointment={partiallyPaidVisit} onProcessPayment={vi.fn()} onClose={vi.fn()} />);
    expect(screen.queryByTestId('cash-advance-notice')).toBeNull();
    fireEvent.change(getAmountInput(), { target: { value: '35000' } });
    expect(screen.getByTestId('cash-advance-notice').textContent).toContain(formatUZS(5000));
    fireEvent.change(getAmountInput(), { target: { value: '20000' } });
    expect(screen.queryByTestId('cash-advance-notice')).toBeNull();
  });
});
