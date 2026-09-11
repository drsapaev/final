import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const paymentApiMocks = vi.hoisted(() => ({
  getPendingInvoices: vi.fn(),
  createPaymentInvoice: vi.fn(),
}));

vi.mock('../../../hooks/usePaymentsApi', () => ({
  usePaymentsApi: () => ({
    ...paymentApiMocks,
    formatUZS: (amount: number) => `${amount} UZS`,
    normalizePaymentAmount: (amount: unknown) => Number(amount),
    isValidPaymentAmount: (amount: unknown) => Number(amount) > 0,
  }),
}));

vi.mock('../../../i18n/useTranslation', () => ({
  // The project wrapper currently returns a new `t` function on every render.
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('react-toastify', () => ({
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

vi.mock('../PaymentClick', () => ({
  default: ({ isOpen, invoiceId, totalAmount }: { isOpen: boolean; invoiceId: string | number; totalAmount: number }) =>
    isOpen ? (
      <div data-testid="click-payment">
        {String(invoiceId)}:{String(totalAmount)}
      </div>
    ) : null,
}));
vi.mock('../PaymentPayMe', () => ({ default: () => null }));

import PaymentManager from '../PaymentManager';

describe('PaymentManager backend-owned invoice actions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    paymentApiMocks.getPendingInvoices.mockResolvedValue([
      {
        invoice_id: 42,
        amount: 125000,
        currency: 'UZS',
        provider: 'payme',
        status: 'pending',
        available_actions: [],
        online_payment_block_reason: 'provider_unavailable',
      },
    ]);
  });

  it('loads once, omits linkless invoice creation, and disables an unavailable legacy invoice', async () => {
    render(<PaymentManager isOpen />);

    await waitFor(() => {
      expect(paymentApiMocks.getPendingInvoices).toHaveBeenCalledTimes(1);
    });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 25));
    });

    expect(paymentApiMocks.getPendingInvoices).toHaveBeenCalledTimes(1);

    expect(screen.queryByRole('radio')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'payment.pay_mgr_create_btn' })).not.toBeInTheDocument();
    expect(paymentApiMocks.createPaymentInvoice).not.toHaveBeenCalled();
    expect(screen.getByText('payment.pay_mgr_provider_unavailable')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'payment.pay_mgr_provider_unavailable' })
    ).toBeDisabled();
  });

  it('opens checkout for an existing invoice with an authorized provider', async () => {
    paymentApiMocks.getPendingInvoices.mockResolvedValue([{
      invoice_id: 73,
      amount: 50000,
      remaining_amount: 32000,
      currency: 'UZS',
      provider: null,
      status: 'pending',
      available_actions: [
        { action: 'start_online_payment', provider: 'click' },
      ],
      online_payment_block_reason: null,
    }]);

    render(<PaymentManager isOpen />);

    const payButton = await screen.findByRole('button', {
      name: 'payment.pay_mgr_provider_aria',
    });
    expect(payButton).toBeEnabled();

    fireEvent.click(payButton);

    await waitFor(() => {
      expect(screen.getByTestId('click-payment')).toHaveTextContent('73:32000');
    });
    expect(paymentApiMocks.createPaymentInvoice).not.toHaveBeenCalled();
  });
});
