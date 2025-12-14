import React, { useState, useEffect } from 'react';
import { CheckCircle, XCircle } from 'lucide-react';
import { Button } from '../ui/macos';

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
            alert('Введите корректную сумму');
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
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999
        }}>
            <div style={{
                backgroundColor: 'var(--mac-bg-secondary)',
                borderRadius: 'var(--mac-radius-md)',
                padding: '24px',
                width: '100%',
                maxWidth: '400px',
                margin: '16px',
                border: '1px solid var(--mac-border)',
                boxShadow: 'var(--mac-shadow-lg)'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                    <h3 style={{ fontSize: '18px', fontWeight: '600', color: 'var(--mac-text-primary)' }}>Обработка оплаты</h3>
                    <button onClick={onClose} style={{ color: 'var(--mac-text-secondary)', cursor: 'pointer', border: 'none', background: 'none' }}>
                        <XCircle style={{ width: '24px', height: '24px' }} />
                    </button>
                </div>

                <div style={{ marginBottom: '16px' }}>
                    <p style={{ fontSize: '14px', color: 'var(--mac-text-secondary)', marginBottom: '8px' }}>Пациент:</p>
                    <p style={{ fontSize: '16px', fontWeight: '500', color: 'var(--mac-text-primary)' }}>
                        {appointment?.patient_name || `Пациент #${appointment?.patient_id}`}
                    </p>
                    <p style={{ fontSize: '14px', color: 'var(--mac-text-secondary)' }}>
                        {appointment?.department} • {appointment?.appointment_date} {appointment?.appointment_time}
                    </p>
                    {/* Recommended amount hint */}
                    {defaultAmount > 0 && (
                        <p style={{
                            fontSize: '13px',
                            color: '#007AFF',
                            marginTop: '8px',
                            padding: '8px 12px',
                            backgroundColor: 'rgba(0, 122, 255, 0.1)',
                            borderRadius: 'var(--mac-radius-sm)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px'
                        }}>
                            💡 Сумма к оплате: {formatAmount(defaultAmount)} сум
                        </p>
                    )}
                </div>

                <form onSubmit={handleSubmit}>
                    <div style={{ marginBottom: '16px' }}>
                        <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: 'var(--mac-text-primary)', marginBottom: '4px' }}>
                            Сумма (сум)
                        </label>
                        <input
                            type="number"
                            value={paymentData.amount}
                            onChange={(e) => setPaymentData(prev => ({ ...prev, amount: e.target.value }))}
                            style={{
                                width: '100%',
                                padding: '8px 12px',
                                border: '1px solid var(--mac-border)',
                                borderRadius: 'var(--mac-radius-sm)',
                                fontSize: '16px',
                                backgroundColor: 'var(--mac-bg-primary)',
                                color: 'var(--mac-text-primary)'
                            }}
                            placeholder="Введите сумму"
                            required
                        />
                    </div>

                    <div style={{ marginBottom: '16px' }}>
                        <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: 'var(--mac-text-primary)', marginBottom: '4px' }}>
                            Способ оплаты
                        </label>
                        <select
                            value={paymentData.method}
                            onChange={(e) => setPaymentData(prev => ({ ...prev, method: e.target.value }))}
                            style={{
                                width: '100%',
                                padding: '8px 12px',
                                border: '1px solid var(--mac-border)',
                                borderRadius: 'var(--mac-radius-sm)',
                                fontSize: '16px',
                                backgroundColor: 'var(--mac-bg-primary)',
                                color: 'var(--mac-text-primary)'
                            }}
                        >
                            <option value="cash">Наличные</option>
                            <option value="card">Карта</option>
                        </select>
                    </div>

                    <div style={{ marginBottom: '24px' }}>
                        <label style={{ display: 'block', fontSize: '14px', fontWeight: '500', color: 'var(--mac-text-primary)', marginBottom: '4px' }}>
                            Примечание (необязательно)
                        </label>
                        <textarea
                            value={paymentData.note}
                            onChange={(e) => setPaymentData(prev => ({ ...prev, note: e.target.value }))}
                            style={{
                                width: '100%',
                                padding: '8px 12px',
                                border: '1px solid var(--mac-border)',
                                borderRadius: 'var(--mac-radius-sm)',
                                fontSize: '16px',
                                minHeight: '80px',
                                resize: 'vertical',
                                backgroundColor: 'var(--mac-bg-primary)',
                                color: 'var(--mac-text-primary)'
                            }}
                            placeholder="Дополнительная информация"
                        />
                    </div>

                    <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                        <Button type="submit" variant="primary">
                            <CheckCircle style={{ width: '16px', height: '16px', marginRight: '8px' }} />
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

export default CashPaymentModal;
