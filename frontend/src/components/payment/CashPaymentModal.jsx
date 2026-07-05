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
import formatCurrency from '../../utils/formatCurrency';

/**
 * Cash Payment Modal Component
 * Extracted from CashierPanel for better code organization.
 *
 * Refactored to use macOS UI kit components (was 100% inline styles, HIGH #6),
 * adds change-due calculation for cash payments (HIGH #9),
 * unified payment method options (MEDIUM #16),
 * and uses consistent Russian aria-labels (HIGH #8).
 */
const PAYMENT_METHOD_OPTIONS = [
  { value: 'cash', label: 'Наличные' },
  { value: 'card', label: 'Карта' },
  { value: 'click', label: 'Click' },
  { value: 'payme', label: 'PayMe' },
];

const CashPaymentModal = ({ appointment, onProcessPayment, onClose }) => {
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
            notify.warning('Введите корректную сумму');
            return;
        }
        if (insufficientCash) {
            notify.warning('Полученная сумма меньше суммы к оплате');
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
            aria-label="Диалог обработки оплаты">
            <DialogTitle>
                <Box
                    display="flex"
                    alignItems="center"
                    justifyContent="space-between"
                    style={{ width: '100%' }}>
                    <span>Обработка оплаты</span>
                    <Button
                        variant="ghost"
                        size="small"
                        onClick={onClose}
                        aria-label="Закрыть окно обработки оплаты">
                        <XCircle size={20} aria-hidden="true" />
                    </Button>
                </Box>
            </DialogTitle>

            <DialogContent>
                <Box mb={2}>
                    <Typography variant="body2" color="textSecondary" style={{ marginBottom: 4 }}>
                        Пациент:
                    </Typography>
                    <Typography variant="body1" style={{ fontWeight: 500 }}>
                        {appointment?.patient_name || `Пациент #${appointment?.patient_id}`}
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
                            style={{
                                backgroundColor: 'rgba(0, 122, 255, 0.1)',
                                borderRadius: 'var(--mac-radius-sm)',
                                color: '#007AFF',
                                fontSize: '13px',
                            }}>
                            <Info size={14} aria-hidden="true" />
                            Сумма к оплате: {formatCurrency(defaultAmount)}
                        </Box>
                    )}
                </Box>

                <form onSubmit={handleSubmit} id="cash-payment-form">
                    <Box mb={2}>
                        <Label htmlFor="cash-payment-amount" style={{ display: 'block', marginBottom: 4 }}>
                            Сумма (сум)
                        </Label>
                        <Input
                            id="cash-payment-amount"
                            type="number"
                            aria-label="Сумма оплаты"
                            value={paymentData.amount}
                            onChange={(e) => setPaymentData(prev => ({ ...prev, amount: e.target.value }))}
                            placeholder="Введите сумму"
                            required
                        />
                    </Box>

                    <Box mb={2}>
                        <Label htmlFor="cash-payment-method" style={{ display: 'block', marginBottom: 4 }}>
                            Способ оплаты
                        </Label>
                        <Select
                            id="cash-payment-method"
                            aria-label="Способ оплаты"
                            value={paymentData.method}
                            onChange={(value) => setPaymentData(prev => ({ ...prev, method: value }))}
                            options={PAYMENT_METHOD_OPTIONS}
                            style={{ width: '100%' }}
                        />
                    </Box>

                    {paymentData.method === 'cash' && (
                        <Box mb={2}>
                            <Label htmlFor="cash-payment-received" style={{ display: 'block', marginBottom: 4 }}>
                                Получено от пациента (сум)
                            </Label>
                            <Input
                                id="cash-payment-received"
                                type="number"
                                aria-label="Полученная сумма от пациента"
                                value={paymentData.receivedAmount}
                                onChange={(e) => setPaymentData(prev => ({ ...prev, receivedAmount: e.target.value }))}
                                placeholder="Введите полученную сумму"
                                error={insufficientCash}
                            />
                            {insufficientCash && (
                                <Typography variant="caption" style={{ color: 'var(--mac-error)', marginTop: 4, display: 'block' }}>
                                    Недостаточно средств. Нужно ещё: {formatCurrency(numericAmount - numericReceived)}
                                </Typography>
                            )}
                            {changeDue > 0 && (
                                <Box
                                    mt={1}
                                    px={1.5}
                                    py={1}
                                    style={{
                                        backgroundColor: 'rgba(52, 199, 89, 0.12)',
                                        borderRadius: 'var(--mac-radius-sm)',
                                        color: 'var(--mac-success)',
                                        fontWeight: 600,
                                    }}>
                                    Сдача: {formatCurrency(changeDue)}
                                </Box>
                            )}
                        </Box>
                    )}

                    <Box mb={1}>
                        <Label htmlFor="cash-payment-note" style={{ display: 'block', marginBottom: 4 }}>
                            Примечание (необязательно)
                        </Label>
                        <Textarea
                            id="cash-payment-note"
                            aria-label="Примечание к оплате"
                            value={paymentData.note}
                            onChange={(e) => setPaymentData(prev => ({ ...prev, note: e.target.value }))}
                            placeholder="Дополнительная информация"
                            minRows={3}
                        />
                    </Box>
                </form>
            </DialogContent>

            <DialogActions>
                <Button type="button" variant="outline" onClick={onClose}>
                    Отмена
                </Button>
                <Button type="submit" variant="primary" form="cash-payment-form">
                    <CheckCircle size={16} style={{ marginRight: 8 }} aria-hidden="true" />
                    Обработать оплату
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
