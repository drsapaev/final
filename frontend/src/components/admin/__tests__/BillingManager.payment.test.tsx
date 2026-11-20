import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '@/contexts/ThemeContext';
import BillingManager from '../BillingManager';

const { apiGet, apiPost, showError } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  showError: vi.fn(),
}));

vi.mock('../../../api/client', () => ({ api: { get: apiGet, post: apiPost } }));
vi.mock('../../../i18n/useTranslation', () => ({ useTranslation: () => ({
  t: (key: string, values?: { number?: string | number; visitId?: number }) => {
    if (key === 'admin2.bill_pay_number') return `${key} ${values?.number}`;
    if (key === 'misc.srch_visit_id') return `${key} ${values?.visitId}`;
    return key;
  },
}) }));
vi.mock('../../../utils/logger', () => ({
  default: { error: vi.fn(), info: vi.fn(), warn: vi.fn(), debug: vi.fn() },
}));
vi.mock('react-toastify', () => ({ toast: { error: showError, success: vi.fn() } }));

describe('BillingManager payment retries', () => {
  beforeEach(() => {
    apiGet.mockReset().mockResolvedValue({
      data: [{
        id: 73,
        invoice_number: 'SYNTHETIC-INVOICE',
        status: 'pending',
        total_amount: 12.3,
        balance: 12.3,
        paid_amount: 0,
        issue_date: '2026-01-01',
      }],
    });
    apiPost.mockReset();
    showError.mockClear();
  });

  it('retains the exact amount and client key across a failed response and reopening', async () => {
    apiPost.mockRejectedValueOnce(new Error('Synthetic connection loss')).mockResolvedValue({});
    render(<ThemeProvider><BillingManager /></ThemeProvider>);

    const open = await screen.findByRole('button', { name: 'admin2.bill_record_pay_aria' });
    fireEvent.click(open);
    fireEvent.click(screen.getByRole('button', { name: 'admin2.bill_record_btn' }));
    await waitFor(() => expect(showError).toHaveBeenCalledOnce());
    const firstBody = apiPost.mock.calls[0][1];
    expect(firstBody).toMatchObject({
      invoice_id: 73,
      amount: '12.30',
      client_request_id: expect.stringMatching(/^[0-9a-f-]{36}$/),
    });

    fireEvent.click(screen.getByRole('button', { name: 'admin2.bill_close_pay_form_aria' }));
    fireEvent.click(open);
    fireEvent.click(screen.getByRole('button', { name: 'admin2.bill_record_btn' }));
    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(2));
    expect(apiPost.mock.calls[1]).toEqual(['/billing/payments', firstBody]);
    await waitFor(() => expect(screen.queryByRole('button', { name: 'admin2.bill_record_btn' })).toBeNull());

    fireEvent.click(await screen.findByRole('button', { name: 'admin2.bill_record_pay_aria' }));
    fireEvent.click(screen.getByRole('button', { name: 'admin2.bill_record_btn' }));
    await waitFor(() => expect(apiPost).toHaveBeenCalledTimes(3));
    expect(apiPost.mock.calls[2][1].client_request_id).not.toBe(firstBody.client_request_id);
  });

  it('shows the receipt, currency and settlement status from payment history', async () => {
    apiGet.mockImplementation(async (path: string) => ({
      data: path === '/billing/payments' ? [{
        id: 4,
        visit_id: 17,
        receipt_no: 'SYNTHETIC-RECEIPT',
        amount: 12.3,
        currency: 'USD',
        method: 'cash',
        status: 'refunded',
        created_at: '2026-01-01T12:00:00Z',
        paid_at: null,
      }] : [],
    }));
    render(<ThemeProvider><BillingManager /></ThemeProvider>);

    fireEvent.click(screen.getByRole('button', { name: 'admin2.bill_tab_payments' }));
    expect(await screen.findByText('admin2.bill_pay_number SYNTHETIC-RECEIPT')).toBeInTheDocument();
    expect(screen.getByText('misc.srch_visit_id 17')).toBeInTheDocument();
    expect(screen.getByText(`admin2.bill_amount ${(12.3).toLocaleString()} USD`)).toBeInTheDocument();
    expect(screen.getByText('admin2.bill_status_refunded')).toBeInTheDocument();
    expect(screen.queryByText('admin2.bill_pay_pending_confirm')).toBeNull();
  });
});
