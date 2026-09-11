import { act, render, screen, waitFor } from '@testing-library/react';
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

vi.mock('../PaymentClick', () => ({ default: () => null }));
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

  it('loads once and disables a legacy invoice whose provider is unavailable', async () => {
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

    const providerOptions = screen.getAllByRole('radio');
    expect(providerOptions).toHaveLength(1);
    expect((providerOptions[0] as HTMLInputElement).value).toBe('click');
    expect(providerOptions[0]).toBeChecked();
    expect(screen.getByText('payment.pay_mgr_provider_unavailable')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'payment.pay_mgr_provider_unavailable' })
    ).toBeDisabled();
  });
});
