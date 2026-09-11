import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const paymentApiMocks = vi.hoisted(() => ({
  getPendingInvoices: vi.fn(),
  createPaymentInvoice: vi.fn(),
  getPaymentProviders: vi.fn(),
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
  default: ({ isOpen, invoiceId }: { isOpen: boolean; invoiceId: string | number }) =>
    isOpen ? <div data-testid="click-payment">{String(invoiceId)}</div> : null,
}));
vi.mock('../PaymentPayMe', () => ({ default: () => null }));

import PaymentManager from '../PaymentManager';

describe('PaymentManager provider capabilities', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    paymentApiMocks.getPaymentProviders.mockResolvedValue([
      {
        name: 'click',
        code: 'click',
        supported_currencies: ['UZS'],
        is_active: true,
        features: { registrar_invoice_payment: true },
      },
      {
        name: 'payme',
        code: 'payme',
        supported_currencies: ['UZS'],
        is_active: true,
        features: { registrar_invoice_payment: false },
      },
    ]);
    paymentApiMocks.getPendingInvoices.mockResolvedValue([
      {
        invoice_id: 42,
        amount: 125000,
        currency: 'UZS',
        provider: 'payme',
        status: 'pending',
      },
    ]);
  });

  it('loads once, omits linkless invoice creation, and disables an unavailable legacy invoice', async () => {
    render(<PaymentManager isOpen />);

    await waitFor(() => {
      expect(paymentApiMocks.getPaymentProviders).toHaveBeenCalledTimes(1);
      expect(paymentApiMocks.getPendingInvoices).toHaveBeenCalledTimes(1);
    });

    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 25));
    });

    expect(paymentApiMocks.getPaymentProviders).toHaveBeenCalledTimes(1);
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
      currency: 'UZS',
      provider: 'click',
      status: 'pending',
    }]);

    render(<PaymentManager isOpen />);

    const payButton = await screen.findByRole('button', {
      name: 'payment.pay_mgr_pay_btn',
    });
    expect(payButton).toBeEnabled();

    fireEvent.click(payButton);

    await waitFor(() => {
      expect(screen.getByTestId('click-payment')).toHaveTextContent('73');
    });
    expect(paymentApiMocks.createPaymentInvoice).not.toHaveBeenCalled();
  });
});
