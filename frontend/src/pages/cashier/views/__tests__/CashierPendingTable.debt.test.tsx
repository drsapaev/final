/**
 * CSH-FE-007 regression tests — remaining-debt amount column in
 * CashierPendingTable.
 *
 * Fail-first proven on the pre-fix source (total_amount-first chain):
 * after a partial payment the pending row displayed the FULL original
 * price, overstating the outstanding debt.
 *
 * Canonical basis (audit ledger 2026-11-01, CSH-FE-007):
 *   displayed = remaining_amount ?? total_amount ?? payment_amount ?? 0
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { formatUZS } from '../../../../utils/formatCurrency';
// testing-library нормализует неразрывные пробелы Intl (U+00A0) в обычные
// пробелы при текстовом поиске — готовим матчер с обычными пробелами.
const fmt = (amount: number) => formatUZS(amount).replace(/\u00A0/g, ' ');
import type { Appointment } from '../../../../types/domain/clinic';
import CashierPendingTable from '../CashierPendingTable';

const baseProps = {
  pendingLoading: false,
  pendingPage: 1,
  onPendingPageChange: vi.fn(),
  pendingTotalPages: 1,
  pendingTotalItems: 2,
  openPaymentWidget: vi.fn(),
  onOpenCashPaymentModal: vi.fn(),
  onOpenHistory: vi.fn(),
  tI18n: (key: string) => key,
};

const partiallyPaidRow = {
  id: 101,
  record_type: 'appointment',
  patient_id: 7,
  patient_name: 'Тестов Тест',
  total_amount: '100000',
  paid_amount: '70000',
  remaining_amount: '30000',
  can_create_direct_payment: true,
  created_at: '2026-11-02T10:00:00',
} as unknown as Appointment;

const noRemainingRow = {
  id: 102,
  record_type: 'appointment',
  patient_id: 8,
  patient_name: 'Примеров Пример',
  total_amount: '80000',
  can_create_direct_payment: true,
  created_at: '2026-11-02T11:00:00',
} as unknown as Appointment;

describe('CashierPendingTable — CSH-FE-007 remaining debt column', () => {
  it('shows the remaining debt for a partially paid visit (100000 total → 30000 remaining)', () => {
    render(<CashierPendingTable {...baseProps} appointments={[partiallyPaidRow]} />);
    expect(screen.getByText(fmt(30000))).toBeInTheDocument();
    expect(screen.queryByText(fmt(100000))).toBeNull();
  });

  it('falls back to total_amount when remaining_amount is absent', () => {
    render(<CashierPendingTable {...baseProps} appointments={[noRemainingRow]} />);
    expect(screen.getByText(fmt(80000))).toBeInTheDocument();
  });

  it('renders both semantics side by side without confusing the columns', () => {
    render(<CashierPendingTable {...baseProps} appointments={[partiallyPaidRow, noRemainingRow]} />);
    expect(screen.getByText(fmt(30000))).toBeInTheDocument();
    expect(screen.getByText(fmt(80000))).toBeInTheDocument();
    // The stale full price of the partially paid row must not be shown anywhere.
    expect(screen.queryByText(fmt(100000))).toBeNull();
  });
});
