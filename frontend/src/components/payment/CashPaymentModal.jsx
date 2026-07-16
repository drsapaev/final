import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect, useMemo } from 'react';
import PropTypes from 'prop-types';
import { CheckCircle, XCircle, Info } from 'lucide-react';
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
// UX Audit #4 regression fix: inline-стили → CSS-классы (после PR #1910 regression).
import './CashPaymentModal.css';

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
const getPaymentMethodOptions = (t) => [
  { value: 'cash', label: t('payment.pay_cash_method_cash') },
  { value: 'card', label: t('payment.pay_cash_method_card') },
  { value: 'click', label: t('payment.pay_cash_method_click') },
  { value: 'payme', label: t('payment.pay_cash_method_payme') },
];

// UX Audit #1.2: Quick cash denominations (UZS banknotes) + "exact amount" button.
// Cuts ~10s per cash transaction × 200 tx/shift = ~30 min saved per cashier shift.
const QUICK_CASH_DENOMINATIONS = [50000, 100000, 200000, 500000];

const CashPaymentModal = ({ appointment, onProcessPayment, onClose }) => {
    const { t } = useTranslation();
    // Auto-fill amount from appointment data
    const defaultAmount = appointment?.total_amount ||
        appointment?.remaining_amount ||
        appointment?.payment_amount ||
        '';

    const [paymentData, setPaymentData] = useState({
        amount: defaultAmount,
        receivedAmount: '',
        method: 'cash',
        note: ''
    });

    // Update amount when appointment changes
    useEffect(() => {
        const newAmount = appointment?.total_amount ||
            appointment?.remaining_amount ||
            appointment?.payment_amount ||
            '';
        setPaymentData(prev => ({ ...prev, amount: newAmount, receivedAmount: '' }));
    }, [appointment]);

    const numericAmount = Number(paymentData.amount) || 0;
    const numericReceived = Number(paymentData.receivedAmount) || 0;
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

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!paymentData.amount || Number(paymentData.amount) <= 0) {
            notify.warning(t('payment.invalid_amount'));
            return;
        }
        if (insufficientCash) {
            notify.warning(t('payment.insufficient_amount'));
            return;
        }
        // Pass change due up to parent for receipt printing (HIGH #9 fix).
        onProcessPayment(appointment, {
            ...paymentData,
            amount: Number(paymentData.amount),
            change_due: changeDue,
            received_amount: paymentData.method === 'cash' ? numericReceived : numericAmount,
        });
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
                        {appointment?.patient_name || t('payment.pay_cash_patient_fallback', { id: appointment?.patient_id })}
                    </Typography>
                    <Typography variant="body2" color="textSecondary">
                        {appointment?.department} • {appointment?.appointment_date} {appointment?.appointment_time}
                    </Typography>
                    {defaultAmount > 0 && (
                        <Box
                            mt={1}
                            px={1.5}
                            py={1}
                            display="flex"
                            alignItems="center"
                            gap={1}
                            className="cpm-amount-hint-box">
                            <Info size={14} aria-hidden="true" />
                            {t('payment.pay_cash_amount_due')} {formatUZS(defaultAmount)}
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
                            value={paymentData.amount}
                            onChange={(e) => setPaymentData(prev => ({ ...prev, amount: e.target.value }))}
                            placeholder={t('payment.pay_cash_amount_placeholder')}
                            required
                        />
                    </Box>

                    <Box mb={2}>
                        <Label htmlFor="cash-payment-method" className="cpm-field-label">
                            {t('payment.pay_cash_method_label')}
                        </Label>
                        <Select
                            id="cash-payment-method"
                            aria-label={t('payment.pay_cash_method_aria')}
                            value={paymentData.method}
                            onChange={(value) => setPaymentData(prev => ({ ...prev, method: value }))}
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
                                onChange={(e) => setPaymentData(prev => ({ ...prev, receivedAmount: e.target.value }))}
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
                            onChange={(e) => setPaymentData(prev => ({ ...prev, note: e.target.value }))}
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
                <Button type="submit" variant="primary" form="cash-payment-form">
                    <CheckCircle size={16} className="cpm-submit-icon" aria-hidden="true" />
                    {t('payment.pay_cash_submit')}
                </Button>
            </DialogActions>
        </Dialog>
    );
};

CashPaymentModal.propTypes = {
    appointment: PropTypes.shape({
        total_amount: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        remaining_amount: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        payment_amount: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        patient_name: PropTypes.string,
        patient_id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
        department: PropTypes.string,
        appointment_date: PropTypes.string,
        appointment_time: PropTypes.string
    }),
    onProcessPayment: PropTypes.func,
    onClose: PropTypes.func
};

export default CashPaymentModal;
