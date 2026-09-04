/**
 * PR-UI-14-4: cashier business-action handlers + hotkeys.
 *
 * Verbatim move of the action-handler slice from CashierPanel
 * (main `2a49d6de3`) — behavior-preserving decomposition per the
 * PR-UI-13-5 precedent (useRegistrarRowActions: deps-object hook,
 * verbatim handler bodies).
 *
 * Owns:
 *  - processingAction (UX Audit #4.5 anti-double-click guard state)
 *  - payment widget handlers (success/error/cancel/open)
 *  - processPayment (single-visit vs backend-grouped allocation switch)
 *  - confirmPayment / openCancelDialog / handleCancelPayment
 *  - exportToCSV / handleRefresh
 *  - openRefundDialog / handleRefund
 *  - handlePrintReceipt (browser-print-first with PDF fallback)
 *  - loadHourlyStats
 *  - hotkeys (MEDIUM #15: Ctrl+F search focus, F5/Ctrl+R refresh, Ctrl+E export)
 *
 * Deps are passed in (panel stays the single composition point):
 * confirm/tI18n from their hooks, the mutating usePayments API, the
 * worklist refresh primitives, the dialogs state-machine actions + current
 * dialog values, both useModal instances, and the selected date.
 */

import { useRef, useState } from 'react';

import notify from '../../services/notify';
import logger from '../../utils/logger';
import { useHotkeys } from '../../hooks/useHotkeys';
import { getErrorMessage } from '../../utils/errorHandler';
import { formatUZS } from '../../utils/formatCurrency';
import { printPanelReceiptInBrowser } from '../../services/panelPrint';
import useModal from '../../hooks/useModal';
import type { Appointment } from '../../types/domain/clinic';
import type { UsePaymentsReturn } from '../../hooks/usePayments';
import {
  buildPaymentMethodLabels,
  buildReceiptPrintPayload,
  canCreateDirectCashierPayment,
  createGroupedCashierPayment,
  isBackendGroupedCashierPayment,
  resolvePaymentId,
  resolveSingleCashierVisitId,
  type CashierPaymentData,
  type CashierPaymentRow,
  type CashierPaymentRowOrId,
  type CashierTranslationFn,
} from './cashierPaymentContracts';
import type { CashierCancelPaymentContext } from './useCashierDialogs';

type PaymentsApi = Pick<UsePaymentsReturn,
  'createPayment' | 'confirmPayment' | 'cancelPayment' | 'refundPayment'
  | 'getReceipt' | 'getHourlyStats' | 'exportPayments'>;

export interface UseCashierActionsParams {
  confirm: (options: Record<string, unknown>) => Promise<boolean>;
  tI18n: CashierTranslationFn;
  paymentsApi: PaymentsApi;
  worklist: {
    getDateParams: () => { date_from: string; date_to: string };
    setPendingPage: (page: number) => void;
    bumpRefreshKey: () => void;
    triggerDataReload: () => void;
  };
  dialogs: {
    setPaymentSuccess: (data: Record<string, unknown> | null) => void;
    setPaymentError: (message: string | null) => void;
    clearPaymentFeedback: () => void;
    openCancelDialog: (context: CashierCancelPaymentContext) => void;
    resetCancelDialog: () => void;
    openRefundDialog: (payment: CashierPaymentRow) => void;
    resetRefundDialog: () => void;
    showHourlyStats: (stats: unknown[]) => void;
  };
  dialogValues: {
    cancelPaymentContext: CashierCancelPaymentContext | null;
    cancelReason: string;
    refundPaymentId: string | number | null;
    refundAmount: string;
    refundReason: string;
  };
  paymentModal: ReturnType<typeof useModal>;
  paymentWidget: ReturnType<typeof useModal>;
  selectedDate: string;
}

export const useCashierActions = ({
  confirm,
  tI18n,
  paymentsApi,
  worklist,
  dialogs,
  dialogValues,
  paymentModal,
  paymentWidget,
  selectedDate,
}: UseCashierActionsParams) => {
  // UX Audit #4.5: anti-double-click state для action-кнопок.
  // Хранит {type, id} текущего action; пока не null — все action-кнопки disabled.
  const [processingAction, setProcessingAction] = useState<{ type?: string; id?: string | number } | null>(null);

  const { getDateParams, setPendingPage, bumpRefreshKey, triggerDataReload } = worklist;
  const {
    setPaymentSuccess, setPaymentError, clearPaymentFeedback,
    openCancelDialog: dispatchOpenCancelDialog, resetCancelDialog,
    openRefundDialog: dispatchOpenRefundDialog, resetRefundDialog,
    showHourlyStats,
  } = dialogs;
  const { cancelPaymentContext, cancelReason, refundPaymentId, refundAmount, refundReason } = dialogValues;

  // STRAT#31 i18n: paymentMethodLabels — replaces module-level
  // PAYMENT_METHOD_LABELS constant (reactive to language changes via tI18n).
  const paymentMethodLabels = buildPaymentMethodLabels(tI18n);

  // MEDIUM #15: CashierPanel hotkeys — focus search (Ctrl+F), refresh (F5 / Ctrl+R), export (Ctrl+E).
  // Only triggers when not focused in input/textarea to avoid hijacking text entry.
  // Note: handlers use lazy references via refs because some callbacks (exportToCSV)
  // are defined further down in the component body.
  const handlersRef = useRef({} as { refresh?: () => void; export?: () => void });
  useHotkeys({
    'ctrl+f': (e) => {
      e.preventDefault();
      const node = document.getElementById('cashier-search-input');
      if (node) node.focus();
    },
    'f5': (e) => {
      e.preventDefault();
      handlersRef.current.refresh?.();
    },
    'ctrl+r': (e) => {
      e.preventDefault();
      handlersRef.current.refresh?.();
    },
    'ctrl+e': (e) => {
      e.preventDefault();
      handlersRef.current.export?.();
    },
  });

  // UX Audit #2.3: используем единый formatUZS из utils/formatCurrency.js.
  // Раньше тут было inline-определение new Intl.NumberFormat('ru-RU').format(n) + ' сум',
  // что приводило к расхождениям с CashPaymentModal (formatCurrency → «UZS»)
  // и RefundRequestsTable (toLocaleString + «сум»).
  const format = formatUZS;

  // ✅ УЛУЧШЕНИЕ: Обработчики с универсальными хуками
  const handlePaymentSuccess = (paymentData: unknown) => {
    setPaymentSuccess(paymentData as Record<string, unknown>);
    paymentWidget.closeModal();
    // Force reload to get fresh data after successful payment.
    triggerDataReload();
  };

  const handlePaymentError = (error: unknown) => {
    const message = getErrorMessage(error, tI18n('cashier.payment_process_failed'));
    setPaymentError(message);
    logger.error('Ошибка платежа:', error);
  };

  const handlePaymentCancel = () => {
    paymentWidget.closeModal();
  };

  const openPaymentWidget = (appointment: Appointment) => {
    if (!canCreateDirectCashierPayment(appointment) || isBackendGroupedCashierPayment(appointment)) {
      const message = tI18n('cashier.online_payment_group_unavailable');
      setPaymentError(message);
      notify.error(message);
      return;
    }
    paymentWidget.openModal(appointment as unknown as null);
    clearPaymentFeedback();
  };

  // ✅ УЛУЧШЕНИЕ: Функции для работы с оплатами через SSOT hook
  // Теперь appointment содержит сгруппированные данные пациента (все его неоплаченные визиты)
  const processPayment = async (appointment: unknown, paymentData: unknown) => {
    // CashPaymentModal declares `onProcessPayment?: (...args: unknown[]) => Promise<void>`
    // so the args arrive as `unknown`. Narrow to domain types for the body.
    const appt = appointment as Appointment;
    const pData = paymentData as CashierPaymentData;
    try {
      const groupedPayment = isBackendGroupedCashierPayment(appt);
      const visitId = resolveSingleCashierVisitId(appt);

      if (!groupedPayment && !visitId) {
        throw new Error('Cannot process payment: backend must provide exactly one visit_id or a backend-owned allocation contract.');
      }

      if (groupedPayment) {
        await createGroupedCashierPayment(appt, pData);
      } else {
        const result = await paymentsApi.createPayment({
          visit_id: visitId,
          amount: pData.amount,
          method: pData.method,
          note: pData.note || tI18n('cashier.payment_note_default')
        });

        if (!(result as { success?: boolean }).success) {
          throw new Error(tI18n('cashier.payment_visit_failed', { visitId, error: (result as { error?: string }).error }));
        }
      }

      notify.success(tI18n('cashier.payment_success', { amount: format(pData.amount) }));
      paymentModal.closeModal();
      setPendingPage(1);
      bumpRefreshKey(); // Принудительное обновление списка

    } catch (error: unknown) {
      logger.error('Ошибка обработки платежа:', error);
      const message = getErrorMessage(error, tI18n('cashier.payment_process_failed'));
      setPaymentError(message);
      notify.error(message);
    }
  };

  // ✅ УЛУЧШЕНИЕ: Функции для работы с кнопками в истории платежей
  const confirmPayment = async (paymentId: string | number | undefined) => {
    if (paymentId === undefined) {
      notify.error(tI18n('cashier.no_payment_for_receipt'));
      return;
    }
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    // The new dialog names the specific action and uses primary intent
    // (Confirm is a constructive action, not destructive).
    const ok = await confirm({
      title: tI18n('cashier.confirm_payment_title'),
      message: tI18n('cashier.confirm_payment_message'),
      description: tI18n('cashier.confirm_payment_description'),
      confirmLabel: tI18n('cashier.confirm_payment_confirm'),
      cancelLabel: tI18n('cashier.cancel'),
      intent: 'primary',
    });
    if (!ok) {
      return;
    }

    try {
      // UX Audit #4.5: anti-double-click protection.
      setProcessingAction({ type: 'confirm', id: paymentId });
      await paymentsApi.confirmPayment(paymentId);
      bumpRefreshKey(); // Обновляем данные
    } catch (err) {
      logger.error('Error confirming payment:', err);
      notify.error(getErrorMessage(err, tI18n('cashier.payment_confirm_failed')));
    } finally {
      setProcessingAction(null);
    }
  };

  const openCancelDialog = (payment: CashierPaymentRowOrId) => {
    // UX Audit #2.1: принимаем объект payment целиком, чтобы показать контекст.
    // Раньше принимали только paymentId, и в диалоге было видно только #{id}.
    const paymentRow = typeof payment === 'object' && payment !== null ? payment : null;
    const paymentId: string | number | undefined = paymentRow
      ? (paymentRow.id || paymentRow.payment_id)
      : (typeof payment === 'string' || typeof payment === 'number' ? payment : undefined);
    const patient = paymentRow
      ? (paymentRow.patient || paymentRow.patient_name || tI18n('cashier.patient_with_id', { id: paymentRow.patient_id }))
      : null;
    const amount = paymentRow
      ? Number(paymentRow.total_amount || paymentRow.amount || 0)
      : 0;
    dispatchOpenCancelDialog({ id: paymentId, patient, amount });
  };

  const handleCancelPayment = async () => {
    if (!cancelPaymentContext?.id) return;
    // UX Audit #2.1: обязательная причина отмены (минимум 10 символов).
    // Раньше textarea была помечена «необязательно» — аудит-лог пустовал.
    if (!cancelReason || cancelReason.trim().length < 10) {
      notify.warning(tI18n('cashier.cancel_reason_required'));
      return;
    }

    try {
      // UX Audit #4.5: anti-double-click protection.
      setProcessingAction({ type: 'cancel', id: cancelPaymentContext.id });
      const result = await paymentsApi.cancelPayment(cancelPaymentContext.id, cancelReason.trim());
      if ((result as { success?: boolean }).success) {
        resetCancelDialog();
        notify.info(tI18n('cashier.payment_cancelled'));
        triggerDataReload();
      } else {
        notify.error(getErrorMessage((result as { error?: string }).error, tI18n('cashier.refund_failed')));
      }
    } catch (error: unknown) {
      notify.error(getErrorMessage(error, tI18n('cashier.cancel_failed')));
    } finally {
      setProcessingAction(null);
    }
  };

  // ✅ УЛУЧШЕНИЕ: Экспорт в CSV через серверный endpoint
  const exportToCSV = async () => {
    const { date_from, date_to } = getDateParams();
    const result = await paymentsApi.exportPayments({
      date_from: date_from || undefined,
      date_to: date_to || undefined
    });

      if (!(result as { success?: boolean }).success) {
        notify.error(
          getErrorMessage(
            (result as { error?: string }).error,
            tI18n('cashier.export_failed')
          )
        );
      }
  };

  // ✅ УЛУЧШЕНИЕ: Кнопка обновления данных
  const handleRefresh = () => {
    triggerDataReload();
  };

  // Sync hotkey handlers ref (MEDIUM #15)
  handlersRef.current.refresh = handleRefresh;
  handlersRef.current.export = exportToCSV;

  // ✅ v2.0: Обработчик возврата
  const handleRefund = async () => {
    if (!refundAmount || !refundReason || refundReason.length < 3) {
      notify.warning(tI18n('cashier.refund_fields_required'));
      return;
    }
    try {
      // UX Audit #4.5: anti-double-click protection.
      setProcessingAction({ type: 'refund', id: refundPaymentId ?? undefined });
      const result = await paymentsApi.refundPayment(refundPaymentId ?? 0, {
        amount: parseFloat(refundAmount),
        reason: refundReason
      });
      if ((result as { success?: boolean }).success) {
        resetRefundDialog();
        notify.success(tI18n('cashier.refund_success_amount', { amount: ((result as { data?: { refunded_amount?: number } }).data?.refunded_amount) }));
        triggerDataReload();
      } else {
        notify.error(getErrorMessage((result as { error?: string }).error, tI18n('cashier.refund_create_failed')));
      }
    } catch (error: unknown) {
      notify.error(getErrorMessage(error, tI18n('cashier.refund_failed')));
    } finally {
      setProcessingAction(null);
    }
  };

  // ✅ v2.0: Обработчик печати чека
  const handlePrintReceipt = async (paymentRowOrId: CashierPaymentRowOrId) => {
    const paymentId = resolvePaymentId(paymentRowOrId);

    if (!paymentId) {
      notify.error(tI18n('cashier.no_payment_for_receipt'));
      return;
    }

    // UX Audit #4.5: anti-double-click protection.
    setProcessingAction({ type: 'print_receipt', id: paymentId });
    try {
      if (paymentRowOrId && typeof paymentRowOrId === 'object') {
        try {
          const opened = printPanelReceiptInBrowser(buildReceiptPrintPayload(paymentRowOrId, paymentMethodLabels, tI18n('cashier.default_patient')));
          if (opened) {
            notify.success(tI18n('cashier.print_dialog_opened'));
            return;
          }

          logger.warn('[Cashier] Browser receipt print popup blocked, falling back to PDF', {
            paymentId
          });
        } catch (error: unknown) {
          logger.error('[Cashier] Unexpected browser receipt print error:', error);
        }
      }

      const result = await paymentsApi.getReceipt(paymentId);
      if (!(result as { success?: boolean }).success) {
        notify.error(getErrorMessage((result as { error?: string }).error, tI18n('cashier.receipt_load_failed')));
        return;
      }

      notify.warning(tI18n('cashier.print_dialog_failed'));
    } finally {
      setProcessingAction(null);
    }
  };

  // ✅ v2.0: Загрузка почасовой статистики
  const loadHourlyStats = async () => {
    const result = await paymentsApi.getHourlyStats({ target_date: selectedDate });
    if ((result as { success?: boolean }).success) {
      showHourlyStats(((result as { data?: unknown }).data as unknown[]) || []);
    } else {
      notify.error(getErrorMessage((result as { error?: string }).error, tI18n('cashier.stats_load_failed')));
    }
  };

  return {
    processingAction,
    handlePaymentSuccess,
    handlePaymentError,
    handlePaymentCancel,
    openPaymentWidget,
    processPayment,
    confirmPayment,
    openCancelDialog,
    handleCancelPayment,
    exportToCSV,
    handleRefresh,
    openRefundDialog: dispatchOpenRefundDialog,
    handleRefund,
    handlePrintReceipt,
    loadHourlyStats,
  };
};
