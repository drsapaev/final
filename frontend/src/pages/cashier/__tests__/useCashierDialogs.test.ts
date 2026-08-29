/**
 * PR-UI-14-3 unit contract: cashierDialogsReducer — the dialog state
 * machine consolidating 12 CashierPanel useState hooks into one useReducer
 * (13-3 precedent: useRegistrarDialogs).
 *
 * Each action maps 1:1 to the original setState sequence. These tests pin
 * the transition table, including the intentional verbatim quirks:
 *  - CANCEL_DIALOG_CLOSED keeps the context (only the success path resets)
 *  - REFUND_DIALOG_RESET does NOT clear refundPaymentAmount
 *  - openers always blank the reason fields
 */
import { describe, expect, it } from 'vitest';

import {
  cashierDialogsReducer,
  initialCashierDialogsState,
  type CashierDialogsState,
} from '../useCashierDialogs';

const withState = (patch: Partial<CashierDialogsState>): CashierDialogsState => ({
  ...initialCashierDialogsState,
  ...patch,
});

const paymentRow = (overrides: Record<string, unknown> = {}) =>
  ({ id: 42, amount: 100, refunded_amount: 30, ...overrides });

describe('cashierDialogsReducer (PR-UI-14-3)', () => {
  it('initial state: all dialogs closed, feedback nulled, reasons blank', () => {
    expect(initialCashierDialogsState).toEqual({
      paymentSuccess: null,
      paymentError: null,
      cancelPaymentContext: null,
      cancelDialogOpen: false,
      cancelReason: '',
      refundDialogOpen: false,
      refundPaymentId: null,
      refundPaymentAmount: 0,
      refundAmount: '',
      refundReason: '',
      hourlyStats: [],
      showHourlyChart: false,
    });
  });

  describe('payment widget feedback', () => {
    it('PAYMENT_SUCCESS_SET stores the payload; null closes the success dialog', () => {
      const data = { id: 1 };
      let s = cashierDialogsReducer(initialCashierDialogsState, { type: 'PAYMENT_SUCCESS_SET', paymentData: data });
      expect(s.paymentSuccess).toBe(data);
      s = cashierDialogsReducer(s, { type: 'PAYMENT_SUCCESS_SET', paymentData: null });
      expect(s.paymentSuccess).toBeNull();
    });

    it('PAYMENT_ERROR_SET stores the message', () => {
      const s = cashierDialogsReducer(initialCashierDialogsState, { type: 'PAYMENT_ERROR_SET', message: 'fail' });
      expect(s.paymentError).toBe('fail');
    });

    it('PAYMENT_FEEDBACK_CLEARED nulls both feedback fields', () => {
      const s = withState({ paymentSuccess: { id: 1 }, paymentError: 'err' });
      const next = cashierDialogsReducer(s, { type: 'PAYMENT_FEEDBACK_CLEARED' });
      expect(next.paymentSuccess).toBeNull();
      expect(next.paymentError).toBeNull();
    });
  });

  describe('cancel-payment dialog', () => {
    it('CANCEL_DIALOG_OPENED sets context + open + blanks reason', () => {
      const s = withState({ cancelReason: 'old reason' });
      const next = cashierDialogsReducer(s, { type: 'CANCEL_DIALOG_OPENED', context: { id: 9, patient: 'X', amount: 5 } });
      expect(next.cancelDialogOpen).toBe(true);
      expect(next.cancelPaymentContext).toEqual({ id: 9, patient: 'X', amount: 5 });
      expect(next.cancelReason).toBe('');
    });

    it('CANCEL_DIALOG_CLOSED closes but KEEPS the context (verbatim quirk)', () => {
      const s = withState({ cancelDialogOpen: true, cancelPaymentContext: { id: 9 }, cancelReason: 'reason text' });
      const next = cashierDialogsReducer(s, { type: 'CANCEL_DIALOG_CLOSED' });
      expect(next.cancelDialogOpen).toBe(false);
      expect(next.cancelPaymentContext).toEqual({ id: 9 });
      expect(next.cancelReason).toBe('reason text');
    });

    it('CANCEL_DIALOG_RESET clears open + context + reason (success path)', () => {
      const s = withState({ cancelDialogOpen: true, cancelPaymentContext: { id: 9 }, cancelReason: 'reason text' });
      const next = cashierDialogsReducer(s, { type: 'CANCEL_DIALOG_RESET' });
      expect(next.cancelDialogOpen).toBe(false);
      expect(next.cancelPaymentContext).toBeNull();
      expect(next.cancelReason).toBe('');
    });

    it('CANCEL_REASON_SET updates the reason', () => {
      const next = cashierDialogsReducer(initialCashierDialogsState, { type: 'CANCEL_REASON_SET', reason: 'abc' });
      expect(next.cancelReason).toBe('abc');
    });
  });

  describe('refund dialog', () => {
    it('REFUND_DIALOG_OPENED computes refundAmount as amount minus refunded and blanks reason', () => {
      const next = cashierDialogsReducer(
        withState({ refundReason: 'stale' }),
        { type: 'REFUND_DIALOG_OPENED', payment: paymentRow() as never },
      );
      expect(next.refundDialogOpen).toBe(true);
      expect(next.refundPaymentId).toBe(42);
      expect(next.refundPaymentAmount).toBe(100);
      expect(next.refundAmount).toBe('70');
      expect(next.refundReason).toBe('');
    });

    it('REFUND_DIALOG_OPENED tolerates missing id/amount fields (verbatim quirk: amount 0 minus refunded stays negative)', () => {
      const next = cashierDialogsReducer(
        initialCashierDialogsState,
        { type: 'REFUND_DIALOG_OPENED', payment: paymentRow({ id: undefined, amount: undefined }) as never },
      );
      expect(next.refundPaymentId).toBeNull();
      expect(next.refundPaymentAmount).toBe(0);
      // Verbatim original formula: String(Number(amount ?? 0) - Number(refunded ?? 0))
      // with amount missing and refunded 30 -> '-30' (pre-existing semantics,
      // preserved 1:1 by PR-UI-14-3).
      expect(next.refundAmount).toBe('-30');
    });

    it('REFUND_DIALOG_CLOSED closes but keeps values', () => {
      const s = withState({ refundDialogOpen: true, refundAmount: '70', refundReason: 'r' });
      const next = cashierDialogsReducer(s, { type: 'REFUND_DIALOG_CLOSED' });
      expect(next.refundDialogOpen).toBe(false);
      expect(next.refundAmount).toBe('70');
    });

    it('REFUND_DIALOG_RESET clears open/id/reason/amount-string but KEEPS paymentAmount (verbatim quirk)', () => {
      const s = withState({
        refundDialogOpen: true,
        refundPaymentId: 42,
        refundPaymentAmount: 100,
        refundAmount: '70',
        refundReason: 'r',
      });
      const next = cashierDialogsReducer(s, { type: 'REFUND_DIALOG_RESET' });
      expect(next.refundDialogOpen).toBe(false);
      expect(next.refundPaymentId).toBeNull();
      expect(next.refundReason).toBe('');
      expect(next.refundAmount).toBe('');
      expect(next.refundPaymentAmount).toBe(100); // intentionally preserved
    });

    it('REFUND_AMOUNT_SET / REFUND_REASON_SET update inputs', () => {
      let s = cashierDialogsReducer(initialCashierDialogsState, { type: 'REFUND_AMOUNT_SET', amount: '55' });
      expect(s.refundAmount).toBe('55');
      s = cashierDialogsReducer(s, { type: 'REFUND_REASON_SET', reason: 'because' });
      expect(s.refundReason).toBe('because');
    });
  });

  describe('hourly stats chart dialog', () => {
    it('HOURLY_STATS_SHOWN stores stats and opens the chart', () => {
      const stats = [{ hour: 10, amount: 5 }];
      const next = cashierDialogsReducer(initialCashierDialogsState, { type: 'HOURLY_STATS_SHOWN', stats });
      expect(next.hourlyStats).toBe(stats);
      expect(next.showHourlyChart).toBe(true);
    });

    it('HOURLY_CHART_CLOSED closes the chart but keeps the stats', () => {
      const stats = [{ hour: 10, amount: 5 }];
      const s = withState({ hourlyStats: stats, showHourlyChart: true });
      const next = cashierDialogsReducer(s, { type: 'HOURLY_CHART_CLOSED' });
      expect(next.showHourlyChart).toBe(false);
      expect(next.hourlyStats).toBe(stats);
    });
  });

  it('unknown action returns the same state (exhaustive default)', () => {
    const s = withState({ cancelDialogOpen: true });
    expect(cashierDialogsReducer(s, { type: 'UNKNOWN' } as never)).toBe(s);
  });
});
