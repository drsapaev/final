import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { CheckCircle, XCircle } from 'lucide-react';
import {
  Button,
  Input } from '../ui/macos';
import notify from '../../services/notify';

/**
 * Cash Payment Modal Component
 * Extracted from CashierPanel for better code organization
 */
const CashPaymentModal = ({ appointment, onProcessPayment, onClose }) => {
    // Auto-fill amount from appointment data
    const defaultAmount = appointment?.total_amount ||
        appointment?.remaining_amount ||
        appointment?.payment_amount ||
        '';

    const [paymentData, setPaymentData] = useState({
        amount: defaultAmount,
        method: 'cash',
        note: ''
    });

    // Update amount when appointment changes
    useEffect(() => {
        const newAmount = appointment?.total_amount ||
            appointment?.remaining_amount ||
            appointment?.payment_amount ||
            '';
        setPaymentData(prev => ({ ...prev, amount: newAmount }));
    }, [appointment]);

    const handleSubmit = (e) => {
        e.preventDefault();
        if (!paymentData.amount || paymentData.amount <= 0) {
            notify.warning('Введите корректную сумму');
            return;
        }
        onProcessPayment(appointment, paymentData);
    };

    const formatAmount = (n) => new Intl.NumberFormat('ru-RU').format(n);

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'color-mix(in srgb, black, transparent 50%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999
        }}>
            <div style={{
                backgroundColor: 'var(--mac-bg-secondary)',
                borderRadius: 'var(--mac-radius-md)',
                padding: 'var(--mac-spacing-6)',
                width: '100%',
                maxWidth: '400px',
                margin: '16px',
                border: '1px solid var(--mac-border)',
                boxShadow: 'var(--mac-shadow-lg)'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--mac-spacing-4)' }}>
                    <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>Обработка оплаты</h3>
                    <button onClick={onClose} aria-label="Закрыть окно обработки оплаты" style={{ color: 'var(--mac-text-secondary)', cursor: 'pointer', border: 'none', background: 'none' }}>
                        <XCircle style={{ width: '24px', height: '24px' }} />
                    </button>
                </div>

                <div style={{ marginBottom: 'var(--mac-spacing-4)' }}>
                    <p style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-2)' }}>Пациент:</p>
                    <p style={{ fontSize: 'var(--mac-font-size-lg)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>
                        {appointment?.patient_name || `Пациент #${appointment?.patient_id}`}
                    </p>
                    <p style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)' }}>
                        {appointment?.department} • {appointment?.appointment_date} {appointment?.appointment_time}
                    </p>
                    {/* Recommended amount hint */}
                    {defaultAmount > 0 && (
                        <p style={{
                            fontSize: 'var(--mac-font-size-sm)',
                            color: '#007AFF',
                            marginTop: 'var(--mac-spacing-2)',
                            padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                            backgroundColor: 'var(--mac-accent-bg)',
                            borderRadius: 'var(--mac-radius-sm)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--mac-spacing-2)'
                        }}>
                            💡 Сумма к оплате: {formatAmount(defaultAmount)} сум
                        </p>
                    )}
                </div>

                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: 'var(--mac-spacing-4)' }}>
                        <label htmlFor="cash-payment-amount" style={{ display: 'block', fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)', marginBottom: 'var(--mac-spacing-1)' }}>
                            Сумма (сум)
                        </label>
                        <Input
                            id="cash-payment-amount"
                            type="number"
                            aria-label="Сумма оплаты"
                            value={paymentData.amount}
                            onChange={(e) => setPaymentData(prev => ({ ...prev, amount: e.target.value }))}
                            style={{
                                width: '100%',
                                padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                                border: '1px solid var(--mac-border)',
                                borderRadius: 'var(--mac-radius-sm)',
                                fontSize: 'var(--mac-font-size-lg)',
                                backgroundColor: 'var(--mac-bg-primary)',
                                color: 'var(--mac-text-primary)'
                            }}
                            placeholder="Введите сумму"
                            required
                        />
                    </div>

                    <div style={{ marginBottom: 'var(--mac-spacing-4)' }}>
                        <label htmlFor="cash-payment-method" style={{ display: 'block', fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)', marginBottom: 'var(--mac-spacing-1)' }}>
                            Способ оплаты
                        </label>
                        <select
                            id="cash-payment-method"
                            value={paymentData.method}
                            onChange={(e) => setPaymentData(prev => ({ ...prev, method: e.target.value }))}
                            style={{
                                width: '100%',
                                padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                                border: '1px solid var(--mac-border)',
                                borderRadius: 'var(--mac-radius-sm)',
                                fontSize: 'var(--mac-font-size-lg)',
                                backgroundColor: 'var(--mac-bg-primary)',
                                color: 'var(--mac-text-primary)'
                            }}
                        >
                            <option value="cash">Наличные</option>
                            <option value="card">Карта</option>
                        </select>
                    </div>

                    <div style={{ marginBottom: 'var(--mac-spacing-6)' }}>
                        <label htmlFor="cash-payment-note" style={{ display: 'block', fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)', marginBottom: 'var(--mac-spacing-1)' }}>
                            Примечание (необязательно)
                        </label>
                        <textarea
                            id="cash-payment-note"
                            aria-label="Примечание к оплате"
                            value={paymentData.note}
                            onChange={(e) => setPaymentData(prev => ({ ...prev, note: e.target.value }))}
                            style={{
                                width: '100%',
                                padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                                border: '1px solid var(--mac-border)',
                                borderRadius: 'var(--mac-radius-sm)',
                                fontSize: 'var(--mac-font-size-lg)',
                                minHeight: '80px',
                                resize: 'vertical',
                                backgroundColor: 'var(--mac-bg-primary)',
                                color: 'var(--mac-text-primary)'
                            }}
                            placeholder="Дополнительная информация"
                        />
                    </div>

                    <div style={{ display: 'flex', gap: 'var(--mac-spacing-3)', justifyContent: 'flex-end' }}>
                        <Button type="submit" variant="primary">
                            <CheckCircle style={{ width: '16px', height: '16px', marginRight: 'var(--mac-spacing-2)' }} />
                            Обработать оплату
                        </Button>
                        <Button type="button" variant="outline" onClick={onClose}>
                            Отмена
                        </Button>
                    </div>
                </form>
            </div>
        </div>
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
