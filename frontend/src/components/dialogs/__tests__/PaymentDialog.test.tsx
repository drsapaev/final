import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import PaymentDialog from '../PaymentDialog';
import { getRegistrarPaymentSummary } from '../../../api/registrarPayments';
import type { RegistrarPaymentSummary } from '../../../api/registrarPayments';
import { toast } from 'react-toastify';
import type { AppointmentId } from '../../../types/domain/branded';

vi.mock('../../../api/registrarPayments', () => ({ getRegistrarPaymentSummary: vi.fn() }));
vi.mock('../../../i18n/useTranslation', () => ({ useTranslation: () => ({ t: (key: string) => key }) }));
vi.mock('../../../hooks/usePaymentMethods', () => ({ usePaymentMethods: () => ({ paymentMethods: [{ value: 'cash', label: 'SYNTHETIC cash' }] }) }));
vi.mock('../../../utils/logger', () => ({ default: { error: vi.fn() } }));
vi.mock('react-toastify', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock('../../ui/macos', () => ({ Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} /> }));

const before: RegistrarPaymentSummary = { total_amount: '100000', paid_amount: '0', remaining_amount: '100000', payment_status: 'pending', can_pay: true, snapshot: 'before', visits: [] };
const after: RegistrarPaymentSummary = { ...before, paid_amount: '30000', remaining_amount: '70000', payment_status: 'partial', snapshot: 'after' };
const appointment = { id: '1' as AppointmentId, patient_fio: 'SYNTHETIC-Test', cost: 25000 };

describe('PaymentDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getRegistrarPaymentSummary).mockResolvedValue(before);
  });

  it('uses current server debt instead of the wizard delta and shows remaining debt', async () => {
    const onPaymentSuccess = vi.fn().mockResolvedValue(after);
    render(<PaymentDialog isOpen onClose={vi.fn()} appointment={appointment} onPaymentSuccess={onPaymentSuccess} />);
    const input = await screen.findByRole('spinbutton');
    await waitFor(() => expect(input).toHaveValue(100000));
    fireEvent.change(input, { target: { value: '30000' } });
    fireEvent.click(screen.getByRole('button', { name: 'misc.pd_oplatit' }));
    await screen.findByText('admin2.bill_status_partially_paid');
    expect(onPaymentSuccess).toHaveBeenCalledExactlyOnceWith({ amount: 30000, method: 'cash', payment_snapshot: 'before' });
    expect(screen.getByText(/70.000/)).toBeInTheDocument();
    expect(toast.success).toHaveBeenCalledOnce();
  });

  it('keeps failures out of the success state and requires refreshing debt before another attempt', async () => {
    render(<PaymentDialog isOpen onClose={vi.fn()} appointment={appointment} onPaymentSuccess={vi.fn().mockRejectedValue(new Error('network'))} />);
    const button = screen.getByRole('button', { name: 'misc.pd_oplatit' });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    await screen.findByRole('alert');
    expect(toast.success).not.toHaveBeenCalled();
    expect(button).toBeDisabled();
    expect(screen.queryByText('admin2.bill_status_paid')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'common.refresh' }));
    await waitFor(() => expect(button).toBeEnabled());
  });

  it('sends one command on double click and disables closing while it is pending', async () => {
    let finish!: (value: RegistrarPaymentSummary) => void;
    const onPaymentSuccess = vi.fn(() => new Promise<RegistrarPaymentSummary>((resolve) => { finish = resolve; }));
    const onClose = vi.fn();
    render(<PaymentDialog isOpen onClose={onClose} appointment={appointment} onPaymentSuccess={onPaymentSuccess} />);
    const button = screen.getByRole('button', { name: 'misc.pd_oplatit' });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    fireEvent.click(button);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onPaymentSuccess).toHaveBeenCalledOnce();
    expect(onClose).not.toHaveBeenCalled();
    await act(async () => { finish(after); });
  });

  it('does not accept payment when loading the balance failed', async () => {
    vi.mocked(getRegistrarPaymentSummary).mockRejectedValue(new Error('network'));
    render(<PaymentDialog isOpen onClose={vi.fn()} appointment={appointment} onPaymentSuccess={vi.fn()} />);
    await screen.findByRole('alert');
    expect(screen.getByRole('button', { name: 'misc.pd_oplatit' })).toBeDisabled();
  });
});
