/**
 * ForceMajeureModal - Modal for mass queue operations
 * 
 * Features:
 * - Transfer all waiting patients to tomorrow
 * - Mass cancellation with refund
 * - Safety confirmation (dry run + type CONFIRM)
 */
import React, { useState, useEffect } from 'react';
import {
    AlertTriangle,
    ArrowRight,
    XCircle,
    RefreshCw,
    Calendar,
    DollarSign,
    Users,
    Loader2
} from 'lucide-react';
import { Button, Card, Badge } from '../ui/macos';
import logger from '../../utils/logger';

const ForceMajeureModal = ({
    isOpen,
    onClose,
    specialistId,
    specialistName = 'Специалист',
    onSuccess
}) => {
    const [activeTab, setActiveTab] = useState('transfer'); // 'transfer' | 'cancel'
    const [reason, setReason] = useState('');
    const [refundType, setRefundType] = useState('deposit'); // 'deposit' | 'bank_transfer'
    const [confirmText, setConfirmText] = useState('');
    const [loading, setLoading] = useState(false);
    const [dryRunResult, setDryRunResult] = useState(null);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);

    // Reset state when modal opens
    useEffect(() => {
        if (isOpen) {
            setReason('');
            setConfirmText('');
            setError(null);
            setSuccess(null);
            setDryRunResult(null);
            loadPendingEntries();
        }
    }, [isOpen, specialistId]);

    const getAuthToken = () => {
        return localStorage.getItem('access_token') || localStorage.getItem('auth_token') || '';
    };

    // Load pending entries (dry run)
    const loadPendingEntries = async () => {
        if (!specialistId) return;

        try {
            const token = getAuthToken();
            const response = await fetch(
                `/api/v1/force-majeure/pending-entries?specialist_id=${specialistId}`,
                {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                }
            );

            if (response.ok) {
                const data = await response.json();
                setDryRunResult({
                    count: data.length,
                    entries: data,
                    totalAmount: data.reduce((sum, e) => sum + (e.total_amount || 0), 0)
                });
            }
        } catch (err) {
            logger.error('[ForceMajeureModal] Error loading pending entries:', err);
        }
    };

    // Transfer to tomorrow
    const handleTransfer = async () => {
        if (!reason.trim() || reason.length < 5) {
            setError('Укажите причину (минимум 5 символов)');
            return;
        }

        if (confirmText !== 'ПОДТВЕРЖДАЮ') {
            setError('Введите "ПОДТВЕРЖДАЮ" для подтверждения');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const token = getAuthToken();
            const response = await fetch('/api/v1/force-majeure/transfer', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    specialist_id: specialistId,
                    reason: reason,
                    send_notifications: true
                })
            });

            if (response.ok) {
                const result = await response.json();
                setSuccess(`Перенесено записей: ${result.transferred || 0}`);
                logger.log('[ForceMajeureModal] Transfer successful:', result);
                if (onSuccess) onSuccess('transfer', result);
            } else {
                const errorData = await response.json();
                setError(errorData.detail || 'Ошибка переноса');
            }
        } catch (err) {
            logger.error('[ForceMajeureModal] Transfer error:', err);
            setError(err.message || 'Ошибка сети');
        } finally {
            setLoading(false);
        }
    };

    // Cancel with refund
    const handleCancel = async () => {
        if (!reason.trim() || reason.length < 5) {
            setError('Укажите причину (минимум 5 символов)');
            return;
        }

        if (confirmText !== 'ПОДТВЕРЖДАЮ') {
            setError('Введите "ПОДТВЕРЖДАЮ" для подтверждения');
            return;
        }

        setLoading(true);
        setError(null);

        try {
            const token = getAuthToken();
            const response = await fetch('/api/v1/force-majeure/cancel-with-refund', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    specialist_id: specialistId,
                    reason: reason,
                    refund_type: refundType,
                    send_notifications: true
                })
            });

            if (response.ok) {
                const result = await response.json();
                setSuccess(`Отменено записей: ${result.cancelled || 0}, возвратов: ${result.refunds_created || 0}`);
                logger.log('[ForceMajeureModal] Cancel successful:', result);
                if (onSuccess) onSuccess('cancel', result);
            } else {
                const errorData = await response.json();
                setError(errorData.detail || 'Ошибка отмены');
            }
        } catch (err) {
            logger.error('[ForceMajeureModal] Cancel error:', err);
            setError(err.message || 'Ошибка сети');
        } finally {
            setLoading(false);
        }
    };

    if (!isOpen) return null;

    const isConfirmValid = confirmText === 'ПОДТВЕРЖДАЮ';
    const isReasonValid = reason.trim().length >= 5;

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 10000,
            backdropFilter: 'blur(4px)'
        }}>
            <div style={{
                background: 'white',
                borderRadius: '16px',
                width: '100%',
                maxWidth: '560px',
                maxHeight: '90vh',
                overflow: 'auto',
                boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)'
            }}>
                {/* Header */}
                <div style={{
                    padding: '20px 24px',
                    borderBottom: '1px solid #e5e7eb',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    background: '#fef3c7'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <AlertTriangle size={24} color="#d97706" />
                        <div>
                            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 600, color: '#92400e' }}>
                                Форс-мажор
                            </h2>
                            <p style={{ margin: 0, fontSize: '13px', color: '#b45309' }}>
                                {specialistName}
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        style={{
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            padding: '4px'
                        }}
                    >
                        <XCircle size={24} color="#9ca3af" />
                    </button>
                </div>

                {/* Tabs */}
                <div style={{
                    display: 'flex',
                    borderBottom: '1px solid #e5e7eb'
                }}>
                    <button
                        onClick={() => setActiveTab('transfer')}
                        style={{
                            flex: 1,
                            padding: '12px',
                            border: 'none',
                            background: activeTab === 'transfer' ? '#f0f9ff' : 'white',
                            borderBottom: activeTab === 'transfer' ? '2px solid #3b82f6' : '2px solid transparent',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '8px',
                            color: activeTab === 'transfer' ? '#1d4ed8' : '#6b7280'
                        }}
                    >
                        <Calendar size={18} />
                        Перенести на завтра
                    </button>
                    <button
                        onClick={() => setActiveTab('cancel')}
                        style={{
                            flex: 1,
                            padding: '12px',
                            border: 'none',
                            background: activeTab === 'cancel' ? '#fef2f2' : 'white',
                            borderBottom: activeTab === 'cancel' ? '2px solid #ef4444' : '2px solid transparent',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '8px',
                            color: activeTab === 'cancel' ? '#dc2626' : '#6b7280'
                        }}
                    >
                        <DollarSign size={18} />
                        Отменить с возвратом
                    </button>
                </div>

                {/* Content */}
                <div style={{ padding: '24px' }}>
                    {/* Dry Run Info */}
                    {dryRunResult && (
                        <div style={{
                            background: '#f3f4f6',
                            borderRadius: '8px',
                            padding: '16px',
                            marginBottom: '20px',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '16px'
                        }}>
                            <Users size={32} color="#6b7280" />
                            <div>
                                <p style={{ margin: 0, fontSize: '24px', fontWeight: 700, color: '#111827' }}>
                                    {dryRunResult.count} записей
                                </p>
                                <p style={{ margin: 0, fontSize: '13px', color: '#6b7280' }}>
                                    будут {activeTab === 'transfer' ? 'перенесены' : 'отменены'}
                                    {dryRunResult.totalAmount > 0 && ` • ${dryRunResult.totalAmount.toLocaleString()} сум`}
                                </p>
                            </div>
                            <button
                                onClick={loadPendingEntries}
                                style={{
                                    marginLeft: 'auto',
                                    background: 'none',
                                    border: 'none',
                                    cursor: 'pointer',
                                    padding: '8px'
                                }}
                            >
                                <RefreshCw size={18} color="#6b7280" />
                            </button>
                        </div>
                    )}

                    {/* Reason */}
                    <div style={{ marginBottom: '20px' }}>
                        <label style={{ display: 'block', marginBottom: '6px', fontWeight: 500, color: '#374151' }}>
                            Причина *
                        </label>
                        <textarea
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            placeholder="Опишите причину форс-мажора..."
                            style={{
                                width: '100%',
                                padding: '12px',
                                border: '1px solid #d1d5db',
                                borderRadius: '8px',
                                fontSize: '14px',
                                minHeight: '80px',
                                resize: 'vertical'
                            }}
                        />
                        {!isReasonValid && reason.length > 0 && (
                            <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#ef4444' }}>
                                Минимум 5 символов
                            </p>
                        )}
                    </div>

                    {/* Refund Type (only for cancel) */}
                    {activeTab === 'cancel' && (
                        <div style={{ marginBottom: '20px' }}>
                            <label style={{ display: 'block', marginBottom: '6px', fontWeight: 500, color: '#374151' }}>
                                Тип возврата
                            </label>
                            <div style={{ display: 'flex', gap: '12px' }}>
                                <label style={{
                                    flex: 1,
                                    padding: '12px',
                                    border: refundType === 'deposit' ? '2px solid #3b82f6' : '1px solid #d1d5db',
                                    borderRadius: '8px',
                                    cursor: 'pointer',
                                    background: refundType === 'deposit' ? '#eff6ff' : 'white'
                                }}>
                                    <input
                                        type="radio"
                                        name="refundType"
                                        value="deposit"
                                        checked={refundType === 'deposit'}
                                        onChange={(e) => setRefundType(e.target.value)}
                                        style={{ display: 'none' }}
                                    />
                                    <div style={{ fontWeight: 500, color: '#111827' }}>На депозит</div>
                                    <div style={{ fontSize: '12px', color: '#6b7280' }}>Мгновенно на баланс</div>
                                </label>
                                <label style={{
                                    flex: 1,
                                    padding: '12px',
                                    border: refundType === 'bank_transfer' ? '2px solid #3b82f6' : '1px solid #d1d5db',
                                    borderRadius: '8px',
                                    cursor: 'pointer',
                                    background: refundType === 'bank_transfer' ? '#eff6ff' : 'white'
                                }}>
                                    <input
                                        type="radio"
                                        name="refundType"
                                        value="bank_transfer"
                                        checked={refundType === 'bank_transfer'}
                                        onChange={(e) => setRefundType(e.target.value)}
                                        style={{ display: 'none' }}
                                    />
                                    <div style={{ fontWeight: 500, color: '#111827' }}>На карту</div>
                                    <div style={{ fontSize: '12px', color: '#6b7280' }}>Заявка на возврат</div>
                                </label>
                            </div>
                        </div>
                    )}

                    {/* Safety Confirmation */}
                    <div style={{
                        background: '#fef2f2',
                        border: '1px solid #fecaca',
                        borderRadius: '8px',
                        padding: '16px',
                        marginBottom: '20px'
                    }}>
                        <p style={{ margin: '0 0 12px', fontSize: '14px', color: '#991b1b', fontWeight: 500 }}>
                            ⚠️ Это действие нельзя отменить!
                        </p>
                        <label style={{ display: 'block', marginBottom: '6px', fontSize: '13px', color: '#7f1d1d' }}>
                            Введите <strong>ПОДТВЕРЖДАЮ</strong> для продолжения:
                        </label>
                        <input
                            type="text"
                            value={confirmText}
                            onChange={(e) => setConfirmText(e.target.value.toUpperCase())}
                            placeholder="ПОДТВЕРЖДАЮ"
                            style={{
                                width: '100%',
                                padding: '10px 12px',
                                border: `2px solid ${isConfirmValid ? '#22c55e' : '#fca5a5'}`,
                                borderRadius: '6px',
                                fontSize: '14px',
                                fontWeight: 600,
                                textAlign: 'center',
                                letterSpacing: '2px'
                            }}
                        />
                    </div>

                    {/* Error / Success Messages */}
                    {error && (
                        <div style={{
                            background: '#fef2f2',
                            color: '#dc2626',
                            padding: '12px',
                            borderRadius: '8px',
                            marginBottom: '16px',
                            fontSize: '14px'
                        }}>
                            {error}
                        </div>
                    )}

                    {success && (
                        <div style={{
                            background: '#f0fdf4',
                            color: '#16a34a',
                            padding: '12px',
                            borderRadius: '8px',
                            marginBottom: '16px',
                            fontSize: '14px'
                        }}>
                            ✅ {success}
                        </div>
                    )}

                    {/* Actions */}
                    <div style={{ display: 'flex', gap: '12px' }}>
                        <button
                            onClick={onClose}
                            style={{
                                flex: 1,
                                padding: '12px',
                                border: '1px solid #d1d5db',
                                borderRadius: '8px',
                                background: 'white',
                                cursor: 'pointer',
                                fontSize: '14px',
                                fontWeight: 500
                            }}
                        >
                            Отмена
                        </button>
                        <button
                            onClick={activeTab === 'transfer' ? handleTransfer : handleCancel}
                            disabled={loading || !isConfirmValid || !isReasonValid || success}
                            style={{
                                flex: 1,
                                padding: '12px',
                                border: 'none',
                                borderRadius: '8px',
                                background: activeTab === 'transfer' ? '#3b82f6' : '#ef4444',
                                color: 'white',
                                cursor: (loading || !isConfirmValid || !isReasonValid || success) ? 'not-allowed' : 'pointer',
                                opacity: (loading || !isConfirmValid || !isReasonValid || success) ? 0.5 : 1,
                                fontSize: '14px',
                                fontWeight: 600,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                gap: '8px'
                            }}
                        >
                            {loading ? (
                                <>
                                    <Loader2 size={18} className="animate-spin" />
                                    Обработка...
                                </>
                            ) : activeTab === 'transfer' ? (
                                <>
                                    <ArrowRight size={18} />
                                    Перенести
                                </>
                            ) : (
                                <>
                                    <XCircle size={18} />
                                    Отменить и вернуть
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ForceMajeureModal;
