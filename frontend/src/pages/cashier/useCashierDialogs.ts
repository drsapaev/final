/**
 * PR-UI-14-3: cashier dialog state machines.
 *
 * Verbatim consolidation of 12 dialog-scoped useState hooks from
 * CashierPanel into a single useReducer (PR-UI-13-3 precedent:
 * useRegistrarDialogs — 8 dialog-useState → 1 useReducer with verbatim
 * reset-shapes). No behavior changes; every action maps 1:1 to the original
 * setState sequence at its call site.
 *
 * Owned slices:
 *  - payment widget feedback (paymentSuccess / paymentError)
 *  - cancel-payment dialog (context / open / reason)
 *  - refund dialog (open / paymentId / paymentAmount / amount / reason)
 *  - hourly stats chart dialog (stats / open)
 *
 * Verbatim reset-shape quirks preserved intentionally:
 *  - resetRefundDialog does NOT clear refundPaymentAmount (original code
 *    only reset open/paymentId/reason/amount-string);
 *  - closeCancelDialog keeps the context (only the success path resets it);
 *  - openCancelDialog / openRefundDialog always blank the reason.
 */

import { useReducer } from 'react';

import type { CashierPaymentRow } from './cashierPaymentContracts';

export interface CashierCancelPaymentContext {
  id?: string | number;
  [k: string]: unknown;
}

export interface CashierDialogsState {
  paymentSuccess: Record<string, unknown> | null;
  paymentError: string | null;
  cancelPaymentContext: CashierCancelPaymentContext | null;
  cancelDialogOpen: boolean;
  cancelReason: string;
  refundDialogOpen: boolean;
  refundPaymentId: string | number | null;
  refundPaymentAmount: number;
  refundAmount: string;
  refundReason: string;
  hourlyStats: unknown[];
  showHourlyChart: boolean;
}

export const initialCashierDialogsState: CashierDialogsState = {
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
};

export type CashierDialogsAction =
  // payment widget feedback
  | { type: 'PAYMENT_SUCCESS_SET'; paymentData: Record<string, unknown> | null }
  | { type: 'PAYMENT_ERROR_SET'; message: string | null }
  | { type: 'PAYMENT_FEEDBACK_CLEARED' }
  // cancel-payment dialog
  | { type: 'CANCEL_DIALOG_OPENED'; context: CashierCancelPaymentContext }
  | { type: 'CANCEL_DIALOG_CLOSED' }
  | { type: 'CANCEL_DIALOG_RESET' }
  | { type: 'CANCEL_REASON_SET'; reason: string }
  // refund dialog
  | { type: 'REFUND_DIALOG_OPENED'; payment: CashierPaymentRow }
  | { type: 'REFUND_DIALOG_CLOSED' }
  | { type: 'REFUND_DIALOG_RESET' }
  | { type: 'REFUND_AMOUNT_SET'; amount: string }
  | { type: 'REFUND_REASON_SET'; reason: string }
  // hourly stats chart dialog
  | { type: 'HOURLY_STATS_SHOWN'; stats: unknown[] }
  | { type: 'HOURLY_CHART_CLOSED' };

export const cashierDialogsReducer = (
  state: CashierDialogsState,
  action: CashierDialogsAction,
): CashierDialogsState => {
  switch (action.type) {
    // ── payment widget feedback ─────────────────────────────────────────
    case 'PAYMENT_SUCCESS_SET':
      return { ...state, paymentSuccess: action.paymentData };

    case 'PAYMENT_ERROR_SET':
      return { ...state, paymentError: action.message };

    case 'PAYMENT_FEEDBACK_CLEARED':
      return { ...state, paymentError: null, paymentSuccess: null };

    // ── cancel-payment dialog ───────────────────────────────────────────
    case 'CANCEL_DIALOG_OPENED':
      // Original: setCancelPaymentContext(ctx); setCancelDialogOpen(true); setCancelReason('');
      return {
        ...state,
        cancelPaymentContext: action.context,
        cancelDialogOpen: true,
        cancelReason: '',
      };

    case 'CANCEL_DIALOG_CLOSED':
      // Original: setCancelDialogOpen(false) — context intentionally kept.
      return { ...state, cancelDialogOpen: false };

    case 'CANCEL_DIALOG_RESET':
      // Original success path: setCancelDialogOpen(false);
      // setCancelPaymentContext(null); setCancelReason('');
      return {
        ...state,
        cancelDialogOpen: false,
        cancelPaymentContext: null,
        cancelReason: '',
      };

    case 'CANCEL_REASON_SET':
      return { ...state, cancelReason: action.reason };

    // ── refund dialog ───────────────────────────────────────────────────
    case 'REFUND_DIALOG_OPENED': {
      // Original: setRefundPaymentId(payment.id ?? null);
      // setRefundPaymentAmount(Number(payment.amount ?? 0));
      // setRefundAmount(String(Number(payment.amount ?? 0) - Number(payment.refunded_amount ?? 0)));
      // setRefundReason(''); setRefundDialogOpen(true);
      const payment = action.payment;
      return {
        ...state,
        refundPaymentId: payment.id ?? null,
        refundPaymentAmount: Number(payment.amount ?? 0),
        refundAmount: String(Number(payment.amount ?? 0) - Number(payment.refunded_amount ?? 0)),
        refundReason: '',
        refundDialogOpen: true,
      };
    }

    case 'REFUND_DIALOG_CLOSED':
      return { ...state, refundDialogOpen: false };

    case 'REFUND_DIALOG_RESET':
      // Original success path: setRefundDialogOpen(false);
      // setRefundPaymentId(null); setRefundReason(''); setRefundAmount('');
      // (refundPaymentAmount intentionally NOT reset — verbatim.)
      return {
        ...state,
        refundDialogOpen: false,
        refundPaymentId: null,
        refundReason: '',
        refundAmount: '',
      };

    case 'REFUND_AMOUNT_SET':
      return { ...state, refundAmount: action.amount };

    case 'REFUND_REASON_SET':
      return { ...state, refundReason: action.reason };

    // ── hourly stats chart dialog ───────────────────────────────────────
    case 'HOURLY_STATS_SHOWN':
      // Original: setHourlyStats(data); setShowHourlyChart(true);
      return { ...state, hourlyStats: action.stats, showHourlyChart: true };

    case 'HOURLY_CHART_CLOSED':
      return { ...state, showHourlyChart: false };

    default:
      return state;
  }
};

export const useCashierDialogs = () => {
  const [state, dispatch] = useReducer(cashierDialogsReducer, initialCashierDialogsState);

  return {
    state,
    dispatch,
    // payment widget feedback
    setPaymentSuccess: (paymentData: Record<string, unknown> | null) =>
      dispatch({ type: 'PAYMENT_SUCCESS_SET', paymentData }),
    setPaymentError: (message: string | null) =>
      dispatch({ type: 'PAYMENT_ERROR_SET', message }),
    clearPaymentFeedback: () => dispatch({ type: 'PAYMENT_FEEDBACK_CLEARED' }),
    // cancel-payment dialog
    openCancelDialog: (context: CashierCancelPaymentContext) =>
      dispatch({ type: 'CANCEL_DIALOG_OPENED', context }),
    closeCancelDialog: () => dispatch({ type: 'CANCEL_DIALOG_CLOSED' }),
    resetCancelDialog: () => dispatch({ type: 'CANCEL_DIALOG_RESET' }),
    setCancelReason: (reason: string) => dispatch({ type: 'CANCEL_REASON_SET', reason }),
    // refund dialog
    openRefundDialog: (payment: CashierPaymentRow) =>
      dispatch({ type: 'REFUND_DIALOG_OPENED', payment }),
    closeRefundDialog: () => dispatch({ type: 'REFUND_DIALOG_CLOSED' }),
    resetRefundDialog: () => dispatch({ type: 'REFUND_DIALOG_RESET' }),
    setRefundAmount: (amount: string) => dispatch({ type: 'REFUND_AMOUNT_SET', amount }),
    setRefundReason: (reason: string) => dispatch({ type: 'REFUND_REASON_SET', reason }),
    // hourly stats chart dialog
    showHourlyStats: (stats: unknown[]) => dispatch({ type: 'HOURLY_STATS_SHOWN', stats }),
    closeHourlyChart: () => dispatch({ type: 'HOURLY_CHART_CLOSED' }),
  };
};
