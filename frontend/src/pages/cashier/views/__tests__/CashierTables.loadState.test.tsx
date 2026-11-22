/**
 * CSH-FE-001 regression tests — cashier table load-state truthfulness.
 *
 * Fail-first proven on the pre-fix source: a failed pending/history/stats
 * read was indistinguishable from a server-confirmed empty result. The
 * tables rendered the genuine «no pending payments» / «empty history»
 * empty states straight over a dead request, and there was no way to
 * surface a failure or offer a retry from the tables at all.
 *
 * Post-fix contract (audit ledger 2026-11-01, CSH-FE-001/002):
 *  - failed read + NO rows   -> error state with retry, NEVER the genuine
 *    empty state (a dead request is not an empty list)
 *  - failed read + kept rows -> stale-data warning banner above the rows
 *    (rows survive the failed refresh)
 *  - successful empty read   -> the genuine empty state, unchanged
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { Appointment } from '../../../../types/domain/clinic';
import { ThemeProvider } from '../../../../contexts/ThemeContext';
import CashierPendingTable from '../CashierPendingTable';
import CashierHistoryTable from '../CashierHistoryTable';
import CashierStatsCard from '../CashierStatsCard';
import type { CashierStatsSnapshot } from '../../useCashierWorklistData';
import type { CashierPaymentRow } from '../../cashierPaymentContracts';

const tI18n = (key: string) => key;

const pendingRow = {
  id: 101,
  record_type: 'appointment',
  patient_id: 7,
  patient_name: 'Тестов Тест',
  total_amount: '100000',
  can_create_direct_payment: true,
  created_at: '2026-11-02T10:00:00',
} as unknown as Appointment;

const historyRow = {
  id: 'p1',
  patient: 'Тестов Тест',
  date: '02.11.2026',
  time: '10:00',
  service: 'Приём',
  method: 'cash',
  total_amount: 100000,
  status: 'paid',
} as CashierPaymentRow;

const pendingBase = {
  pendingLoading: false,
  pendingPage: 1,
  onPendingPageChange: vi.fn(),
  pendingTotalPages: 1,
  pendingTotalItems: 2,
  openPaymentWidget: vi.fn(),
  onOpenCashPaymentModal: vi.fn(),
  onOpenHistory: vi.fn(),
  tI18n,
};

const historyBase = {
  historyLoading: false,
  filteredPayments: [] as CashierPaymentRow[],
  sortField: 'date' as const,
  sortDir: 'desc' as const,
  onToggleSort: vi.fn(),
  confirmPayment: vi.fn(),
  openCancelDialog: vi.fn(),
  openRefundDialog: vi.fn(),
  handlePrintReceipt: vi.fn(),
  processingAction: null,
  currentPage: 1,
  onCurrentPageChange: vi.fn(),
  totalPages: 1,
  totalItems: 0,
  tI18n,
};

const emptyStats: CashierStatsSnapshot = {
  total_amount: 0,
  cash_amount: 0,
  card_amount: 0,
  pending_count: 0,
  pending_amount: 0,
  paid_count: 0,
  cancelled_count: 0,
};

describe('CashierPendingTable — CSH-FE-001 load-state truthfulness', () => {
  it('renders an error state with retry instead of the genuine empty state when the initial load failed', () => {
    render(
      <CashierPendingTable
        {...pendingBase}
        appointments={[]}
        pendingError="backend down"
        onRetryLoad={vi.fn()}
      />,
    );

    expect(screen.getByText('cashier.load_error_title')).toBeInTheDocument();
    expect(screen.getByText('cashier.retry_load_btn')).toBeInTheDocument();
    // The dead request must NOT be presented as a confirmed empty queue.
    expect(screen.queryByText('cashier.empty_pending_title')).toBeNull();
  });

  it('keeps the previously loaded rows visible with a stale-data banner when a refresh failed', () => {
    render(
      <CashierPendingTable
        {...pendingBase}
        appointments={[pendingRow]}
        pendingError="backend down"
        onRetryLoad={vi.fn()}
      />,
    );

    expect(screen.getByText('cashier.load_error_title')).toBeInTheDocument();
    expect(screen.getByText(/cashier\.stale_data_note/)).toBeInTheDocument();
    // The previously loaded row survives the failed refresh.
    expect(screen.getByText('Тестов Тест')).toBeInTheDocument();
    expect(screen.queryByText('cashier.empty_pending_title')).toBeNull();
  });

  it('still renders the genuine empty state after a successful empty load', () => {
    render(<CashierPendingTable {...pendingBase} appointments={[]} />);

    expect(screen.getByText('cashier.empty_pending_title')).toBeInTheDocument();
    expect(screen.queryByText('cashier.load_error_title')).toBeNull();
  });
});

describe('CashierHistoryTable — CSH-FE-001 load-state truthfulness', () => {
  it('renders an error state with retry instead of the genuine empty state when the initial load failed', () => {
    render(
      <CashierHistoryTable
        {...historyBase}
        filteredPayments={[]}
        historyError="boom"
        onRetryLoad={vi.fn()}
      />,
    );

    expect(screen.getByText('cashier.load_error_title')).toBeInTheDocument();
    expect(screen.getByText('cashier.retry_load_btn')).toBeInTheDocument();
    expect(screen.queryByText('cashier.empty_history_title')).toBeNull();
  });

  it('keeps the previously loaded rows visible with a stale-data banner when a refresh failed', () => {
    render(
      <CashierHistoryTable
        {...historyBase}
        filteredPayments={[historyRow]}
        historyError="boom"
        onRetryLoad={vi.fn()}
      />,
    );

    expect(screen.getByText('cashier.load_error_title')).toBeInTheDocument();
    expect(screen.getByText(/cashier\.stale_data_note/)).toBeInTheDocument();
    expect(screen.getByText('Тестов Тест')).toBeInTheDocument();
    expect(screen.queryByText('cashier.empty_history_title')).toBeNull();
  });

  it('still renders the genuine empty state after a successful empty load', () => {
    render(<CashierHistoryTable {...historyBase} filteredPayments={[]} />);

    expect(screen.getByText('cashier.empty_history_title')).toBeInTheDocument();
    expect(screen.queryByText('cashier.load_error_title')).toBeNull();
  });
});

describe('CashierStatsCard — CSH-FE-001 stats error surfacing', () => {
  it('renders a stats error banner with the refresh action when the stats read failed', () => {
    render(
      <ThemeProvider>
        <CashierStatsCard
          isHistoryTab={false}
          stats={emptyStats}
          statsError="boom"
          onRefresh={vi.fn()}
          onExport={vi.fn()}
          onHourlyStats={vi.fn()}
          tI18n={tI18n}
        />
      </ThemeProvider>,
    );

    expect(screen.getByText('cashier.stats_load_error_title')).toBeInTheDocument();
    expect(screen.getByText(/cashier\.stats_stale_note/)).toBeInTheDocument();
  });

  it('renders no error banner after a successful stats load', () => {
    render(
      <ThemeProvider>
        <CashierStatsCard
          isHistoryTab={false}
          stats={emptyStats}
          onRefresh={vi.fn()}
          onExport={vi.fn()}
          onHourlyStats={vi.fn()}
          tI18n={tI18n}
        />
      </ThemeProvider>,
    );

    expect(screen.queryByText('cashier.stats_load_error_title')).toBeNull();
  });
});
