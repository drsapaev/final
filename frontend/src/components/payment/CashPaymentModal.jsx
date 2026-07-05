import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { CheckCircle, XCircle, Lightbulb } from 'lucide-react';
import {
  Button,
  Input } from '../ui/macos';
import notify from '../../services/notify';
// UX Audit Registrar #4: все inline-стили перенесены в CashPaymentModal.css.
// Также: hardcoded #007AFF → var(--mac-accent-blue), 💡 emoji → lucide Lightbulb icon,
// boxShadow: var(--mac-shadow-lg) → var(--mac-shadow-md) (нет --mac-shadow-lg в tokens).
import './CashPaymentModal.css';

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
        <div className="cpm-overlay">
            <div className="cpm-modal">
                <div className="cpm-header">
                    <h3 className="cpm-title">Обработка оплаты</h3>
                    <button
                        onClick={onClose}
                        aria-label="Закрыть окно обработки оплаты"
                        className="cpm-close-btn">
                        <XCircle className="cpm-close-icon" />
                    </button>
                </div>

                <div className="cpm-patient-info">
                    <p className="cpm-patient-label">Пациент:</p>
                    <p className="cpm-patient-name">
                        {appointment?.patient_name || `Пациент #${appointment?.patient_id}`}
                    </p>
                    <p className="cpm-patient-meta">
                        {appointment?.department} • {appointment?.appointment_date} {appointment?.appointment_time}
                    </p>
                    {/* Recommended amount hint */}
                    {defaultAmount > 0 && (
                        <p className="cpm-amount-hint">
                            <Lightbulb size={14} className="cpm-amount-hint-icon" aria-hidden="true" />
                            <span>Сумма к оплате: {formatAmount(defaultAmount)} сум</span>
                        </p>
                    )}
                </div>

                <form onSubmit={handleSubmit}>
                    <div className="cpm-field-group">
                        <label htmlFor="cash-payment-amount" className="cpm-field-label">
                            Сумма (сум)
                        </label>
                        <Input
                            id="cash-payment-amount"
                            type="number"
                            aria-label="Сумма оплаты"
                            value={paymentData.amount}
                            onChange={(e) => setPaymentData(prev => ({ ...prev, amount: e.target.value }))}
                            className="cpm-input"
                            placeholder="Введите сумму"
                            required
                        />
                    </div>

                    <div className="cpm-field-group">
                        <label htmlFor="cash-payment-method" className="cpm-field-label">
                            Способ оплаты
                        </label>
                        <select
                            id="cash-payment-method"
                            value={paymentData.method}
                            onChange={(e) => setPaymentData(prev => ({ ...prev, method: e.target.value }))}
                            className="cpm-select"
                        >
                            <option value="cash">Наличные</option>
                            <option value="card">Карта</option>
                        </select>
                    </div>

                    <div className="cpm-actions-group">
                        <label htmlFor="cash-payment-note" className="cpm-field-label">
                            Примечание (необязательно)
                        </label>
                        <textarea
                            id="cash-payment-note"
                            aria-label="Примечание к оплате"
                            value={paymentData.note}
                            onChange={(e) => setPaymentData(prev => ({ ...prev, note: e.target.value }))}
                            className="cpm-textarea"
                            placeholder="Дополнительная информация"
                        />
                    </div>

                    <div className="cpm-button-row">
                        <Button type="submit" variant="primary">
                            <CheckCircle className="cpm-submit-icon" />
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
