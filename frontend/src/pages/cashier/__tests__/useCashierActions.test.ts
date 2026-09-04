/**
 * PR-UI-14-4 unit contract: useCashierActions — the business-action
 * handler slice moved verbatim from CashierPanel (13-5 deps-object
 * precedent: useRegistrarRowActions).
 *
 * Pins the externally observable action semantics:
 *  - openPaymentWidget: grouped/direct guard fails closed (error + notify,
 *    widget NOT opened); direct rows open the widget with cleared feedback
 *  - processPayment: single-visit → createPayment(visit_id); backend-grouped
 *    → grouped allocation call; failure → paymentError + notify.error
 *  - confirmPayment: missing id → error; declined confirm → no API call;
 *    accepted → confirmPayment API + refresh
 *  - handleCancelPayment: short reason → warning; success → dialog reset +
 *    full reload; failed result → error notify
 *  - handleRefund: missing fields → warning; success → dialog reset +
 *    notify.success + full reload
 *  - handlePrintReceipt: missing id → error; browser print success →
 *    success notify and no receipt API fallback call
 *  - exportToCSV: failed export → error notify
 *  - loadHourlyStats: success → showHourlyStats(data)
 *  - openCancelDialog: builds {id, patient, amount} with row fallbacks
 */
import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import notify from '../../../services/notify';
import { printPanelReceiptInBrowser } from '../../../services/panelPrint';
import type { UsePaymentsReturn } from '../../../hooks/usePayments';
import { useCashierActions } from '../useCashierActions';
import type { CashierPaymentRow } from '../cashierPaymentContracts';

vi.mock('../../../services/notify', () => ({
  default: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() },
}));

vi.mock('../../../services/panelPrint', () => ({
  printPanelReceiptInBrowser: vi.fn(),
}));

// Mock only the grouped-payment network call; keep the pure helpers real.
vi.mock('../cashierPaymentContracts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../cashierPaymentContracts')>();
  return {
    ...actual,
    createGroupedCashierPayment: vi.fn(),
  };
});

import { createGroupedCashierPayment } from '../cashierPaymentContracts';

const mk = (v: unknown): ReturnType<typeof vi.fn> => vi.fn().mockResolvedValue(v);

interface Deps {
  confirm: ReturnType<typeof vi.fn>;
  paymentsApi: Record<string, ReturnType<typeof vi.fn>>;
  worklist: Record<string, ReturnType<typeof vi.fn>>;
  dialogs: Record<string, ReturnType<typeof vi.fn>>;
  paymentModal: Record<string, unknown>;
  paymentWidget: Record<string, unknown>;
}

const makeDeps = (): Deps => ({
  confirm: vi.fn().mockResolvedValue(true),
  paymentsApi: {
    createPayment: mk({ success: true }),
    confirmPayment: mk({ success: true }),
    cancelPayment: mk({ success: true }),
    refundPayment: mk({ success: true, data: { refunded_amount: 50 } }),
    getReceipt: mk({ success: true }),
    getHourlyStats: mk({ success: true, data: [{ hour: 9 }] }),
    exportPayments: mk({ success: true }),
  },
  worklist: {
    getDateParams: vi.fn(() => ({ date_from: '2026-08-30', date_to: '2026-08-30' })),
    setPendingPage: vi.fn(),
    bumpRefreshKey: vi.fn(),
    triggerDataReload: vi.fn(),
  },
  dialogs: {
    setPaymentSuccess: vi.fn(),
    setPaymentError: vi.fn(),
    clearPaymentFeedback: vi.fn(),
    openCancelDialog: vi.fn(),
    resetCancelDialog: vi.fn(),
    openRefundDialog: vi.fn(),
    resetRefundDialog: vi.fn(),
    showHourlyStats: vi.fn(),
  },
  paymentModal: { closeModal: vi.fn(), openModal: vi.fn(), isOpen: false, selectedItem: null },
  paymentWidget: { closeModal: vi.fn(), openModal: vi.fn(), isOpen: false, selectedItem: null },
});

const renderActions = (deps: Deps, dialogValues: Record<string, unknown> = {}) =>
  renderHook(() =>
    useCashierActions({
      confirm: deps.confirm as unknown as (o: Record<string, unknown>) => Promise<boolean>,
      tI18n: (key: string) => key,
      paymentsApi: deps.paymentsApi as unknown as UsePaymentsReturn,
      worklist: deps.worklist as never,
      dialogs: deps.dialogs as never,
      dialogValues: {
        cancelPaymentContext: null,
        cancelReason: '',
        refundPaymentId: null,
        refundAmount: '',
        refundReason: '',
        ...dialogValues,
      } as never,
      paymentModal: deps.paymentModal as never,
      paymentWidget: deps.paymentWidget as never,
      selectedDate: '2026-08-30',
    }),
  );

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useCashierActions (PR-UI-14-4)', () => {
  it('openPaymentWidget fails closed for grouped rows: error state + notify, widget not opened', () => {
    const deps = makeDeps();
    const { result } = renderActions(deps);
    result.current.openPaymentWidget({ can_create_grouped_payment: true } as never);
    expect(deps.dialogs.setPaymentError).toHaveBeenCalled();
    expect(notify.error).toHaveBeenCalled();
    expect(deps.paymentWidget.openModal).not.toHaveBeenCalled();
  });

  it('openPaymentWidget opens the widget for direct-payment rows and clears feedback', () => {
    const deps = makeDeps();
    const { result } = renderActions(deps);
    result.current.openPaymentWidget({ can_create_direct_payment: true } as never);
    expect(deps.paymentWidget.openModal).toHaveBeenCalled();
    expect(deps.dialogs.clearPaymentFeedback).toHaveBeenCalled();
    expect(deps.dialogs.setPaymentError).not.toHaveBeenCalled();
  });

  it('processPayment single-visit path calls createPayment with the resolved visit id', async () => {
    const deps = makeDeps();
    const { result } = renderActions(deps);
    await result.current.processPayment(
      { visit_id: 77, can_create_direct_payment: true },
      { amount: 150, method: 'cash', note: '' },
    );
    expect(deps.paymentsApi.createPayment).toHaveBeenCalledWith(expect.objectContaining({
      visit_id: 77,
      amount: 150,
      method: 'cash',
    }));
    expect(deps.paymentModal.closeModal).toHaveBeenCalled();
    expect(deps.worklist.setPendingPage).toHaveBeenCalledWith(1);
    expect(deps.worklist.bumpRefreshKey).toHaveBeenCalled();
    expect(notify.success).toHaveBeenCalled();
  });

  it('processPayment grouped path delegates to the backend grouped allocation', async () => {
    const deps = makeDeps();
    (createGroupedCashierPayment as ReturnType<typeof vi.fn>).mockResolvedValue({});
    const { result } = renderActions(deps);
    await result.current.processPayment(
      { can_create_grouped_payment: true, payment_visit_ids: [1, 2], patient_id: 5 },
      { amount: 200, method: 'card' },
    );
    expect(createGroupedCashierPayment).toHaveBeenCalled();
    expect(deps.paymentsApi.createPayment).not.toHaveBeenCalled();
    expect(notify.success).toHaveBeenCalled();
  });

  it('processPayment failure sets payment error and notifies', async () => {
    const deps = makeDeps();
    deps.paymentsApi.createPayment.mockResolvedValue({ success: false, error: 'declined' });
    const { result } = renderActions(deps);
    await result.current.processPayment(
      { visit_id: 77, can_create_direct_payment: true },
      { amount: 10, method: 'cash' },
    );
    expect(deps.dialogs.setPaymentError).toHaveBeenCalled();
    expect(notify.error).toHaveBeenCalled();
    expect(deps.paymentModal.closeModal).not.toHaveBeenCalled();
  });

  it('confirmPayment: missing id → error notify, no confirm dialog, no API call', async () => {
    const deps = makeDeps();
    const { result } = renderActions(deps);
    await result.current.confirmPayment(undefined);
    expect(notify.error).toHaveBeenCalled();
    expect(deps.confirm).not.toHaveBeenCalled();
    expect(deps.paymentsApi.confirmPayment).not.toHaveBeenCalled();
  });

  it('confirmPayment: declined confirm → no API call; accepted → API + refresh', async () => {
    const deps = makeDeps();
    deps.confirm.mockResolvedValueOnce(false);
    const { result } = renderActions(deps);
    await result.current.confirmPayment(9);
    expect(deps.paymentsApi.confirmPayment).not.toHaveBeenCalled();

    deps.confirm.mockResolvedValueOnce(true);
    await result.current.confirmPayment(9);
    expect(deps.paymentsApi.confirmPayment).toHaveBeenCalledWith(9);
    expect(deps.worklist.bumpRefreshKey).toHaveBeenCalled();
  });

  it('handleCancelPayment: short reason → warning, no API call', async () => {
    const deps = makeDeps();
    const { result } = renderActions(deps, { cancelPaymentContext: { id: 9 }, cancelReason: 'short' });
    await result.current.handleCancelPayment();
    expect(notify.warning).toHaveBeenCalled();
    expect(deps.paymentsApi.cancelPayment).not.toHaveBeenCalled();
  });

  it('handleCancelPayment: valid reason → API, dialog reset, full reload', async () => {
    const deps = makeDeps();
    const { result } = renderActions(deps, {
      cancelPaymentContext: { id: 9, patient: 'X', amount: 5 },
      cancelReason: 'достаточно длинная причина',
    });
    await result.current.handleCancelPayment();
    expect(deps.paymentsApi.cancelPayment).toHaveBeenCalledWith(9, 'достаточно длинная причина');
    expect(deps.dialogs.resetCancelDialog).toHaveBeenCalled();
    expect(deps.worklist.triggerDataReload).toHaveBeenCalled();
    expect(notify.info).toHaveBeenCalled();
  });

  it('handleRefund: missing fields → warning; success → reset + notify.success + reload', async () => {
    const deps = makeDeps();
    const { result } = renderActions(deps, { refundAmount: '', refundReason: '' });
    await result.current.handleRefund();
    expect(notify.warning).toHaveBeenCalled();
    expect(deps.paymentsApi.refundPayment).not.toHaveBeenCalled();

    const { result: r2 } = renderActions(deps, { refundPaymentId: 3, refundAmount: '50', refundReason: 'ok reason' });
    await r2.current.handleRefund();
    expect(deps.paymentsApi.refundPayment).toHaveBeenCalledWith(3, { amount: 50, reason: 'ok reason' });
    expect(deps.dialogs.resetRefundDialog).toHaveBeenCalled();
    expect(notify.success).toHaveBeenCalled();
    expect(deps.worklist.triggerDataReload).toHaveBeenCalled();
  });

  it('handlePrintReceipt: row with successful browser print → success notify, no receipt API call', async () => {
    const deps = makeDeps();
    (printPanelReceiptInBrowser as ReturnType<typeof vi.fn>).mockReturnValue(true);
    const { result } = renderActions(deps);
    await result.current.handlePrintReceipt({ id: 5, amount: 10 } as CashierPaymentRow);
    expect(notify.success).toHaveBeenCalled();
    expect(deps.paymentsApi.getReceipt).not.toHaveBeenCalled();
  });

  it('handlePrintReceipt: no resolvable id → error notify', async () => {
    const deps = makeDeps();
    const { result } = renderActions(deps);
    await result.current.handlePrintReceipt(null);
    expect(notify.error).toHaveBeenCalled();
  });

  it('exportToCSV: failed export → error notify', async () => {
    const deps = makeDeps();
    deps.paymentsApi.exportPayments.mockResolvedValue({ success: false, error: 'boom' });
    const { result } = renderActions(deps);
    await result.current.exportToCSV();
    expect(notify.error).toHaveBeenCalled();
  });

  it('loadHourlyStats: success → showHourlyStats with data', async () => {
    const deps = makeDeps();
    const { result } = renderActions(deps);
    await result.current.loadHourlyStats();
    expect(deps.dialogs.showHourlyStats).toHaveBeenCalledWith([{ hour: 9 }]);
  });

  it('openCancelDialog builds the context with id/patient/amount fallbacks', () => {
    const deps = makeDeps();
    const { result } = renderActions(deps);
    result.current.openCancelDialog({
      id: 11,
      patient_name: 'Иванов И.',
      amount: 70,
    } as CashierPaymentRow);
    expect(deps.dialogs.openCancelDialog).toHaveBeenCalledWith({
      id: 11,
      patient: 'Иванов И.',
      amount: 70,
    });
  });

  it('processingAction guards flow through state (anti-double-click)', async () => {
    const deps = makeDeps();
    let resolveApi: (v: unknown) => void = () => {};
    deps.paymentsApi.confirmPayment.mockImplementation(
      () => new Promise((res) => { resolveApi = res; }),
    );
    const { result } = renderActions(deps);
    deps.confirm.mockResolvedValueOnce(true);
    const promise = result.current.confirmPayment(9);
    await waitFor(() => expect(result.current.processingAction).toEqual({ type: 'confirm', id: 9 }));
    resolveApi({ success: true });
    await promise;
    await waitFor(() => expect(result.current.processingAction).toBeNull());
  });
});
