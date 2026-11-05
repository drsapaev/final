
import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect, useMemo, useRef } from 'react';
import { CheckCircle, XCircle, Info, AlertTriangle } from 'lucide-react';
import {
  Button,
  Input,
  Select,
  Textarea,
  Label,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Box,
} from '../ui/macos';
import notify from '../../services/notify';
import { formatUZS } from '../../utils/formatCurrency';
import { generateCashierClientRequestId } from '../../pages/cashier/cashierPaymentContracts';
// UX Audit #4 regression fix: inline-стили → CSS-классы (после PR #1910 regression).
import './CashPaymentModal.css';
import React from "react";

/**
 * Cash Payment Modal Component
 * Extracted from CashierPanel for better code organization.
 *
 * Refactored to use macOS UI kit components (was 100% inline styles, HIGH #6),
 * adds change-due calculation for cash payments (HIGH #9),
 * unified payment method options (MEDIUM #16),
 * and uses consistent Russian aria-labels (HIGH #8).
 */
// i18n: payment method labels are translated at call time via getPaymentMethodOptions(t).
// CSH-FE-039 (follow-up audit 2026-11-02): this modal feeds the DIRECT
// cashier payment command, which settles immediately (status='paid')
// with no provider verification. Only manually receipted methods may
// take that path — cash (наличные) and card (ручной терминал с чеком).
// Click/PayMe are hosted provider methods: they must be initiated via
// the online PaymentWidget (pending → provider → webhook → paid) and
// must never be offered as one-click "paid" entries here. The backend
// enforces the same boundary on the DTO (cashier/_helpers.py).
const getPaymentMethodOptions = (t: (key: string) => string) => [
  { value: 'cash', label: t('payment.pay_cash_method_cash') },
  { value: 'card', label: t('payment.pay_cash_method_card') },
];

// UX Audit #1.2: Quick cash denominations (UZS banknotes) + "exact amount" button.
// Cuts ~10s per cash transaction × 200 tx/shift = ~30 min saved per cashier shift.
const QUICK_CASH_DENOMINATIONS = [50000, 100000, 200000, 500000];

interface CashPaymentModalProps {
  appointment?: Record<string, unknown> | null;
  onProcessPayment?: (...args: unknown[]) => Promise<void>;
  onClose?: () => void;
}

const CashPaymentModal = ({ appointment, onProcessPayment, onClose }: CashPaymentModalProps) => {
    const { t: rawT } = useTranslation(); const t = rawT;
    // Auto-fill amount from appointment data.
    // CSH-FE-007: the canonical default is the remaining debt (remaining_amount),
    // not the original total — a partially paid visit must not silently re-charge
    // its full price. The `??` chain keeps a legitimate remaining_amount of 0
    // from falling through to the full amount (0 means nothing left to collect).
    const defaultAmount = appointment?.remaining_amount ??
        appointment?.total_amount ??
        appointment?.payment_amount ??
        '';

    const [paymentData, setPaymentData] = useState({
        amount: defaultAmount,
        receivedAmount: '',
        method: 'cash',
        note: ''
    });

    // CSH-FE-008: single-flight submit guard. POST /cashier/payments is not
    // idempotent server-side, so every extra in-flight submit is a potential
    // double charge. The ref is checked synchronously — a `submitting` state
    // alone would lose the race against a rapid second click/Enter, because
    // the re-render (and the resulting disabled button) only happens after
    // the current tick, while `onProcessPayment` is already firing again.
    const [submitting, setSubmitting] = useState(false);
    const submittingRef = useRef(false);

    // Issue 3859 (CSH-FE-008 remainder): server-side idempotency key.
    // Generated ONCE per modal session (per mount) and reused for every
    // submit inside the session — a retry after a lost response must send
    // the SAME key so the server replays the original payment response
    // instead of charging twice. A deliberate new attempt (modal reopened =
    // remount) gets a fresh key. Ref, not state: the key must never reset
    // on re-render and must not trigger one.
    const clientRequestIdRef = useRef(generateCashierClientRequestId());

    // Update amount when appointment changes
    useEffect(() => {
        const newAmount = appointment?.remaining_amount ??
            appointment?.total_amount ??
            appointment?.payment_amount ??
            '';
        setPaymentData(prev => ({ ...prev, amount: newAmount, receivedAmount: '' }));
    }, [appointment]);

    const numericAmount = Number(paymentData.amount) || 0;
    const numericReceived = Number(paymentData.receivedAmount) || 0;
    // CSH-FE-007: canonical debt basis for this visit (remaining first) and the
    // deliberate-overpay (advance) amount derived from what the cashier entered.
    const remainingDebt = useMemo(() => {
        const basis = Number(appointment?.remaining_amount ?? appointment?.total_amount ?? appointment?.payment_amount ?? 0);
        return Number.isFinite(basis) ? basis : 0;
    }, [appointment]);
    const advanceAmount = useMemo(() => {
        if (remainingDebt <= 0) return 0;
        return Math.max(0, numericAmount - remainingDebt);
    }, [remainingDebt, numericAmount]);
    const changeDue = useMemo(() => {
        if (paymentData.method !== 'cash') return 0;
        if (numericReceived <= 0) return 0;
        return Math.max(0, numericReceived - numericAmount);
    }, [paymentData.method, numericReceived, numericAmount]);

    const insufficientCash = useMemo(() => {
        if (paymentData.method !== 'cash') return false;
        if (numericReceived <= 0) return false;
        return numericReceived < numericAmount;
    }, [paymentData.method, numericReceived, numericAmount]);

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!paymentData.amount || Number(paymentData.amount) <= 0) {
            notify.warning(t('payment.invalid_amount'));
            return;
        }
        if (insufficientCash) {
            notify.warning(t('payment.insufficient_amount'));
            return;
        }
        // CSH-FE-008: swallow the duplicate submit instead of re-firing the
        // payment call. Validation failures above must NOT engage the guard —
        // the cashier has to be able to fix the amount and submit again.
        if (submittingRef.current) return;
        submittingRef.current = true;
        setSubmitting(true);
        try {
            // Pass change due up to parent for receipt printing (HIGH #9 fix).
            // CSH-FE-008: await the parent handler so the modal stays locked
            // for the whole server round-trip and unlocks exactly once after
            // it settles (success closes the modal, failure keeps it open for
            // an in-place retry).
            await onProcessPayment?.(appointment, {
                ...paymentData,
                amount: Number(paymentData.amount),
                change_due: changeDue,
                received_amount: paymentData.method === 'cash' ? numericReceived : numericAmount,
                client_request_id: clientRequestIdRef.current,
            });
        } catch {
            // The parent owns error surfacing (notify + paymentError state);
            // the modal owns only the submit lock, released in finally.
            // Swallowing here keeps a rejecting handler from becoming an
            // unhandled rejection out of the form event.
        } finally {
            submittingRef.current = false;
            setSubmitting(false);
        }
    };

    return (
        <Dialog
            open
            onClose={onClose}
            maxWidth="sm"
            fullWidth
            aria-label={t('payment.pay_cash_dialog_aria')}>
            <DialogTitle>
                <Box
                    display="flex"
                    alignItems="center"
                    justifyContent="space-between"
                    className="cpm-dialog-header">
                    <span>{t('payment.pay_cash_title')}</span>
                    <Button
                        variant="ghost"
                        size="small"
                        onClick={onClose}
                        aria-label={t('payment.pay_cash_close_aria')}>
                        <XCircle size={20} aria-hidden="true" />
                    </Button>
                </Box>
            </DialogTitle>

            <DialogContent>
                <Box mb={2}>
                    <Typography variant="body2" color="textSecondary" className="cpm-patient-label-text">
                        {t('payment.pay_cash_patient')}
                    </Typography>
                    <Typography variant="body1" className="cpm-patient-name-text">
                        {String(appointment?.patient_name ?? '') || t('payment.pay_cash_patient_fallback', { id: appointment?.patient_id })}
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                        {String(appointment?.department ?? '')} • {String(appointment?.appointment_date ?? '')} {String(appointment?.appointment_time ?? '')}
                    </Typography>
                    {Number(defaultAmount) > 0 && (
                        <Box
                            mt={1}
                            px={1.5}
                            py={1}
                            display="flex"
                            alignItems="center"
                            gap={1}
                            className="cpm-amount-hint-box">
                            <Info size={14} aria-hidden="true" />
                            {t('payment.pay_cash_amount_due')} {formatUZS(Number(defaultAmount))}
                        </Box>
                    )}
                </Box>

                <form onSubmit={handleSubmit} id="cash-payment-form">
                    <Box mb={2}>
                        <Label htmlFor="cash-payment-amount" className="cpm-field-label">
                            {t('payment.pay_cash_amount_label')}
                        </Label>
                        <Input
                            id="cash-payment-amount"
                            type="number"
                            aria-label={t('payment.pay_cash_amount_aria')}
                            value={String(paymentData.amount ?? '')}
                            onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setPaymentData(prev => ({ ...prev, amount: e.target.value }))}
                            placeholder={t('payment.pay_cash_amount_placeholder')}
                            required
                        />
                        {/* CSH-FE-007: deliberate overpay is an explicit advance — the
                            cashier must see it before submitting, not discover it
                            in the receipt. */}
                        {advanceAmount > 0 && (
                            <Box
                                mt={1}
                                px={1.5}
                                py={1}
                                className="cpm-advance-notice-box"
                                role="alert"
                                data-testid="cash-advance-notice">
                                <AlertTriangle size={14} aria-hidden="true" />{' '}
                                {t('payment.pay_cash_advance_notice', { amount: formatUZS(advanceAmount) })}
                            </Box>
                        )}
                    </Box>

                    <Box mb={2}>
                        <Label htmlFor="cash-payment-method" className="cpm-field-label">
                            {t('payment.pay_cash_method_label')}
                        </Label>
                        <Select
                            id="cash-payment-method"
                            aria-label={t('payment.pay_cash_method_aria')}
                            value={paymentData.method}
                            onChange={(value) => setPaymentData(prev => ({ ...prev, method: value as unknown as string }))}
                            options={getPaymentMethodOptions(t)}
                            className="cpm-select-full"
                        />
                    </Box>

                    {paymentData.method === 'cash' && (
                        <Box mb={2}>
                            <Label htmlFor="cash-payment-received" className="cpm-field-label">
                                {t('payment.pay_cash_received_label')}
                            </Label>
                            <Input
                                id="cash-payment-received"
                                type="number"
                                aria-label={t('payment.pay_cash_received_aria')}
                                value={paymentData.receivedAmount}
                                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setPaymentData(prev => ({ ...prev, receivedAmount: e.target.value }))}
                                placeholder={t('payment.pay_cash_received_placeholder')}
                                error={insufficientCash}
                            />
                            {/* UX Audit #1.2: Quick amount buttons — law of Fitts + Hick.
                                Reduces 6-7 keystrokes per transaction to a single click. */}
                            <div className="cpm-quick-amounts" role="group" aria-label={t('payment.pay_cash_quick_aria')}>
                                {QUICK_CASH_DENOMINATIONS.map((nominal) => (
                                    <Button
                                        key={nominal}
                                        type="button"
                                        size="small"
                                        variant="outline"
                                        onClick={() => setPaymentData(prev => ({ ...prev, receivedAmount: String(nominal) }))}
                                        aria-label={t('payment.pay_cash_quick_nominal_aria', { amount: formatUZS(nominal) })}>
                                        {formatUZS(nominal)}
                                    </Button>
                                ))}
                                <Button
                                    type="button"
                                    size="small"
                                    variant="primary"
                                    onClick={() => setPaymentData(prev => ({ ...prev, receivedAmount: String(numericAmount) }))}
                                    aria-label={t('payment.pay_cash_exact_aria')}>
                                    {t('payment.pay_cash_exact_btn')}
                                </Button>
                            </div>
                            {insufficientCash && (
                                <Typography variant="caption" className="cpm-insufficient-error">
                                    {t('payment.pay_cash_insufficient', { amount: formatUZS(numericAmount - numericReceived) })}
                                </Typography>
                            )}
                            {changeDue > 0 && (
                                <Box
                                    mt={1}
                                    px={1.5}
                                    py={1}
                                    className="cpm-change-due-box">
                                    {t('payment.pay_cash_change_due', { amount: formatUZS(changeDue) })}
                                </Box>
                            )}
                        </Box>
                    )}

                    <Box mb={1}>
                        <Label htmlFor="cash-payment-note" className="cpm-field-label">
                            {t('payment.pay_cash_note_label')}
                        </Label>
                        <Textarea
                            id="cash-payment-note"
                            aria-label={t('payment.pay_cash_note_aria')}
                            value={paymentData.note}
                            onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => setPaymentData(prev => ({ ...prev, note: e.target.value }))}
                            placeholder={t('payment.pay_cash_note_placeholder')}
                            minRows={3}
                        />
                    </Box>
                </form>
            </DialogContent>

            <DialogActions>
                <Button type="button" variant="outline" onClick={onClose}>
                    {t('payment.pay_cash_cancel')}
                </Button>
                {/* CSH-FE-008: `loading` disables the button, sets aria-busy
                    and shows the spinner for the whole server round-trip. */}
                <Button type="submit" variant="primary" form="cash-payment-form" loading={submitting}>
                    <CheckCircle size={16} className="cpm-submit-icon" aria-hidden="true" />
                    {t('payment.pay_cash_submit')}
                </Button>
            </DialogActions>
        </Dialog>
    );
};


export default CashPaymentModal;
