/**
 * PR-UI-14-5: cashier dialogs layer (verbatim JSX move from CashierPanel).
 *
 * Renders every modal surface: cancel-payment dialog (UX Audit #2.1
 * context + min-10-char reason), CashPaymentModal + online PaymentWidget
 * dialogs, payment-success dialog, refund dialog (v2.0), hourly-stats
 * chart (UX Audit #4.6 Recharts) and the session-timeout warning overlay
 * (UX Audit #2.5).
 *
 * Props use the ORIGINAL handler/state names so the moved JSX stays
 * byte-identical to the panel source (contract-test pins reference these
 * identifiers, e.g. the PaymentWidget block).
 */

import { CheckCircle, Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Box,
  Alert,
  Button,
} from '../../../components/ui/macos';
import PaymentWidget from '../../../components/payment/PaymentWidget';
import CashPaymentModal from '../../../components/payment/CashPaymentModal';
import notify from '../../../services/notify';
import { formatUZS } from '../../../utils/formatCurrency';
import type { Appointment } from '../../../types/domain/clinic';
import {
  canCreateDirectCashierPayment,
  resolveSingleCashierVisitId,
  type CashierTranslationFn,
} from '../cashierPaymentContracts';
import type { CashierCancelPaymentContext } from '../useCashierDialogs';
import type { CashierSessionWarning } from '../useCashierSessionWarning';
// UX Audit #4.6: Recharts для почасовой статистики (вместо inline-баров на Box sx).
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
} from 'recharts';

/**
 * Structural mirror of useModal()'s return (selectedItem is typed `null` —
 * callers cast to Appointment at use sites, matching the original panel JSX).
 */
interface ModalLike {
  isOpen: boolean;
  selectedItem: null;
  closeModal: () => void;
}

interface CashierDialogsLayerProps {
  // cancel-payment dialog
  cancelDialogOpen: boolean;
  closeCancelDialog: () => void;
  cancelPaymentContext: CashierCancelPaymentContext | null;
  cancelReason: string;
  setCancelReason: (reason: string) => void;
  handleCancelPayment: () => void;
  processingAction: { type?: string; id?: string | number } | null;
  // cash payment modal + online payment widget
  paymentModal: ModalLike;
  processPayment: (appointment: unknown, paymentData: unknown) => Promise<void>;
  paymentWidget: ModalLike;
  handlePaymentSuccess: (paymentData: unknown) => void;
  handlePaymentError: (error: unknown) => void;
  handlePaymentCancel: () => void;
  paymentError: string | null;
  // payment success dialog
  paymentSuccess: Record<string, unknown> | null;
  setPaymentSuccess: (data: Record<string, unknown> | null) => void;
  // refund dialog
  refundDialogOpen: boolean;
  closeRefundDialog: () => void;
  refundPaymentAmount: number;
  refundAmount: string;
  setRefundAmount: (amount: string) => void;
  refundReason: string;
  setRefundReason: (reason: string) => void;
  handleRefund: () => void;
  // hourly stats chart
  showHourlyChart: boolean;
  closeHourlyChart: () => void;
  hourlyStats: unknown[];
  selectedDate: string;
  // session timeout warning
  sessionWarning: CashierSessionWarning | null;
  sessionSecondsLeft: number | null;
  dismissSessionWarning: () => void;
  // shared confirm dialog node (portal-mounted, rendered once per panel)
  confirmDialog: React.ReactNode;
  tI18n: CashierTranslationFn;
}

const CashierDialogsLayer = ({
  cancelDialogOpen,
  closeCancelDialog,
  cancelPaymentContext,
  cancelReason,
  setCancelReason,
  handleCancelPayment,
  processingAction,
  paymentModal,
  processPayment,
  paymentWidget,
  handlePaymentSuccess,
  handlePaymentError,
  handlePaymentCancel,
  paymentError,
  paymentSuccess,
  setPaymentSuccess,
  refundDialogOpen,
  closeRefundDialog,
  refundPaymentAmount,
  refundAmount,
  setRefundAmount,
  refundReason,
  setRefundReason,
  handleRefund,
  showHourlyChart,
  closeHourlyChart,
  hourlyStats,
  selectedDate,
  sessionWarning,
  sessionSecondsLeft,
  dismissSessionWarning,
  confirmDialog,
  tI18n,
}: CashierDialogsLayerProps) => {
  const format = formatUZS;

  return (
    <>
      {/* ✅ УЛУЧШЕНИЕ: Диалог подтверждения отмены платежа */}
      {/* UX Audit #2.1: показываем контекст платежа + обязательная причина (min 10 chars). */}
      <Dialog
        open={cancelDialogOpen}
        onClose={closeCancelDialog}
        maxWidth="sm"
        fullWidth>

        <DialogTitle>{tI18n('cashier.cancel_dialog_title')}</DialogTitle>
        <DialogContent>
          {cancelPaymentContext && (
            <div className="cashier-cancel-context" role="group" aria-label={tI18n('cashier.cancel_context_aria')}>
              <Typography variant="body2" color="textSecondary">
                {tI18n('cashier.payment_id_label', { id: cancelPaymentContext.id })}
              </Typography>
              {Boolean(cancelPaymentContext.patient) && (
                <Typography variant="body1">
                  {tI18n('cashier.patient_label')} <strong>{String(cancelPaymentContext.patient)}</strong>
                </Typography>
              )}
              {Number(cancelPaymentContext.amount ?? 0) > 0 && (
                <Typography variant="body1">
                  {tI18n('cashier.amount_label')} <strong>{format(Number(cancelPaymentContext.amount ?? 0))}</strong>
                </Typography>
              )}
            </div>
          )}
          <Typography variant="body2" className="cashier-mb-4">
            {tI18n('cashier.cancel_dialog_text')}
          </Typography>
          <textarea
            aria-label={tI18n('cashier.cancel_reason_aria')}
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            placeholder={tI18n('cashier.cancel_reason_placeholder')}
            required
            minLength={10}
            className="cashier-text-sm cashier-text-primary cashier-refund-textarea" />
          <Typography variant="caption" color="textSecondary">
            {tI18n('cashier.char_count', { count: cancelReason.trim().length })}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button variant="outline" onClick={closeCancelDialog}>
            {tI18n('cashier.close_btn')}
          </Button>
          <Button
            variant="danger"
            onClick={handleCancelPayment}
            disabled={processingAction?.type === 'cancel' || cancelReason.trim().length < 10}>
            {processingAction?.type === 'cancel' ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : null}
            {tI18n('cashier.btn_cancel')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ✅ УЛУЧШЕНИЕ: Модальное окно оплаты с универсальным хуком */}
      {paymentModal.isOpen && paymentModal.selectedItem &&
      <CashPaymentModal
        appointment={paymentModal.selectedItem}
        onProcessPayment={processPayment}
        onClose={paymentModal.closeModal} />

      }

      {/* ✅ УЛУЧШЕНИЕ: Диалог онлайн-оплаты с универсальным хуком */}
      <Dialog
        open={paymentWidget.isOpen}
        onClose={handlePaymentCancel}
        maxWidth="md"
        fullWidth>

        <DialogTitle>
          <Typography variant="h6">
            {tI18n('cashier.online_payment_dialog_title')}
          </Typography>
          {paymentWidget.selectedItem &&
          <Typography variant="body2" color="textSecondary">
              {tI18n('cashier.patient_summary', { name: (paymentWidget.selectedItem as unknown as Appointment).patient_name, department: (paymentWidget.selectedItem as unknown as Appointment).department })}
            </Typography>
          }
        </DialogTitle>

        <DialogContent>
          {paymentError &&
          <Alert severity="error" className="cashier-alert-error">
              {paymentError}
            </Alert>
          }

          {paymentWidget.selectedItem &&
          <PaymentWidget
            visitId={canCreateDirectCashierPayment(paymentWidget.selectedItem as unknown as Appointment) ? resolveSingleCashierVisitId(paymentWidget.selectedItem as unknown as Appointment) : null}
            amount={Number((paymentWidget.selectedItem as unknown as Appointment).remaining_amount || (paymentWidget.selectedItem as unknown as Appointment).total_amount || (paymentWidget.selectedItem as unknown as Appointment).cost || 0)}
            currency="UZS"
            description={tI18n('cashier.payment_description', { department: (paymentWidget.selectedItem as unknown as Appointment).department || tI18n('cashier.payment_note_default') })}
            onSuccess={handlePaymentSuccess}
            onError={handlePaymentError}
            onCancel={handlePaymentCancel} />

          }
        </DialogContent>

        <DialogActions>
          <Button onClick={handlePaymentCancel}>
            {tI18n('cashier.close_btn')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Диалог успешной оплаты */}
      <Dialog
        open={!!paymentSuccess}
        onClose={() => setPaymentSuccess(null)}
        maxWidth="sm"
        fullWidth>

        <DialogTitle>
          <Box display="flex" alignItems="center">
            <CheckCircle className="cashier-check-icon" />
            {tI18n('cashier.payment_success_dialog_title')}
          </Box>
        </DialogTitle>

        <DialogContent>
          {paymentSuccess &&
          <Box>
              <Typography variant="body1" gutterBottom>
                {tI18n('cashier.payment_success_dialog_body')}
              </Typography>
              {paymentSuccess.amount !== undefined &&
              <Typography variant="body2" color="textSecondary">
                {tI18n('cashier.amount_label')} {format(Number(paymentSuccess.amount) || 0)}
              </Typography>
              }
              {Number(paymentSuccess.change_due ?? 0) > 0 &&
              <Typography variant="body2" color="textSecondary">
                {tI18n('cashier.change_label')} {format(Number(paymentSuccess.change_due))}
              </Typography>
              }
              <Typography variant="body2" color="textSecondary">
                {tI18n('cashier.payment_id_field', { id: paymentSuccess.payment_id })}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                {tI18n('cashier.provider_label', { provider: paymentSuccess.provider })}
              </Typography>
            </Box>
          }
        </DialogContent>

        <DialogActions>
          <Button onClick={() => setPaymentSuccess(null)} variant="primary">
            OK
          </Button>
        </DialogActions>
      </Dialog>

      {/* ✅ v2.0: Диалог возврата */}
      <Dialog open={refundDialogOpen} onClose={closeRefundDialog}>
        <DialogTitle>
          <Box display="flex" alignItems="center">
            {tI18n('cashier.refund_title')}
          </Box>
        </DialogTitle>
        <DialogContent>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Typography variant="body2" color="textSecondary">
              {tI18n('cashier.refund_dialog_subtitle', { amount: formatUZS(refundPaymentAmount) })}
            </Typography>
            <Box>
              <Typography variant="body2" gutterBottom>{tI18n('cashier.refund_amount_label')}:</Typography>
              <input
                type="number"
                aria-label={tI18n('cashier.refund_amount_label')}
                value={refundAmount}
                onChange={(e) => setRefundAmount(e.target.value)}
                className="cashier-refund-input"
                max={refundPaymentAmount}
                min={1} />

            </Box>
            <Box>
              <Typography variant="body2" gutterBottom>{tI18n('cashier.refund_reason_label')}:</Typography>
              <textarea
                aria-label={tI18n('cashier.refund_reason_label')}
                value={refundReason}
                onChange={(e) => setRefundReason(e.target.value)}
                placeholder={tI18n('cashier.refund_reason_placeholder')}
                rows={3}
                className="cashier-refund-textarea" />

            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button variant="outline" onClick={closeRefundDialog}>
            {tI18n('cashier.cancel')}
          </Button>
          <Button variant="danger" onClick={handleRefund} disabled={processingAction?.type === 'refund'}>
            {processingAction?.type === 'refund' ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : null}
            {tI18n('cashier.refund_execute_btn')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ✅ v2.0: Диалог почасовой статистики */}
      {/* UX Audit #4.6: Recharts вместо inline-баров на Box sx={{...}}.
          Раньше: примитивный bar chart без осей, без интерактива, без tooltip.
          Теперь: полноценный BarChart с XAxis/YAxis/Tooltip/CartesianGrid. */}
      <Dialog open={showHourlyChart} onClose={closeHourlyChart}>
        <DialogTitle>
          {tI18n('cashier.hourly_stats_dialog_title', { date: selectedDate })}
        </DialogTitle>
        <DialogContent>
          {hourlyStats.filter((h) => Number((h as { count?: number }).count ?? 0) > 0).length > 0 ? (
            <div className="cashier-hourly-chart">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={hourlyStats.filter((h) => Number((h as { count?: number }).count ?? 0) > 0)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--mac-border, #d8dde8)" />
                  <XAxis
                    dataKey="hour"
                    tickFormatter={(h) => `${h}:00`}
                    stroke="var(--mac-text-secondary, #6b7280)"
                    fontSize={12}
                  />
                  <YAxis
                    stroke="var(--mac-text-secondary, #6b7280)"
                    fontSize={12}
                    allowDecimals={false}
                  />
                  <RechartsTooltip
                    contentStyle={{
                      background: 'var(--mac-bg-tertiary)',
                      border: '1px solid var(--mac-border, #d8dde8)',
                      borderRadius: '8px',
                      fontSize: '13px',
                    }}
                    labelFormatter={(h) => `${h}:00`}
                    formatter={(value, name) => {
                      if (name === 'count') return [value, tI18n('cashier.hourly_stats_count_label')];
                      if (name === 'amount') return [formatUZS(typeof value === 'number' || typeof value === 'string' ? value : 0), tI18n('cashier.hourly_stats_amount_label')];
                      return [value, name];
                    }}
                  />
                  <Bar dataKey="count" fill="var(--mac-success, #34c759)" radius={[4, 4, 0, 0]} name="count" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <Typography color="textSecondary">{tI18n('cashier.hourly_stats_empty')}</Typography>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeHourlyChart}>{tI18n('cashier.close_btn')}</Button>
        </DialogActions>
      </Dialog>

      {/* Session timeout warning dialog (UX Audit #2.5: явные последствия + таймер). */}
      {sessionWarning && (
        <div
          role="alertdialog"
          aria-label={tI18n('cashier.session_warning_aria')}
          className="cashier-session-warning-overlay">
          <div className="cashier-session-warning-card">
            <h3 className="cashier-session-warning-title">
              {tI18n('cashier.session_warning_title')}
            </h3>
            <p className="cashier-session-warning-text">
              {tI18n('cashier.session_warning_text', { seconds: sessionSecondsLeft ?? '?' })}
            </p>
            <div className="cashier-session-warning-actions">
              <button
                type="button"
                onClick={dismissSessionWarning}
                className="cashier-session-warning-btn cashier-session-warning-btn--secondary">
                {tI18n('cashier.session_warning_dismiss')}
              </button>
              <button
                type="button"
                onClick={() => { dismissSessionWarning(); notify.info(tI18n('cashier.session_extending')); }}
                className="cashier-session-warning-btn cashier-session-warning-btn--primary">
                {tI18n('cashier.session_warning_extend')}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </>
  );
};

export default CashierDialogsLayer;
