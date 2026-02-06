/**
 * RefundRequestsTable - Table for managing refund requests
 * 
 * Features:
 * - Display pending, approved, rejected refund requests
 * - Approve/Reject actions for pending requests
 * - Complete action for approved requests
 */
import { useState, useEffect, useCallback } from 'react';
import {
    Check,
    X,
    DollarSign,
    Clock,
    CheckCircle,
    XCircle,
    RefreshCw,
    Loader2,
    User,
    CreditCard
} from 'lucide-react';
import { Badge } from '../ui/macos';
import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';

const RefundRequestsTable = ({ onRefresh }) => {
    const [requests, setRequests] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [processingId, setProcessingId] = useState(null);
    const [filter, setFilter] = useState('all'); // 'all' | 'pending' | 'approved' | 'rejected' | 'completed'

    const getAuthToken = () => {
        return tokenManager.getAccessToken() || '';
    };

    // Load refund requests
    const loadRequests = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const token = getAuthToken();
            const params = new URLSearchParams();
            if (filter !== 'all') {
                params.append('status', filter);
            }

            const response = await fetch(`/api/v1/force-majeure/refund-requests?${params}`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                setRequests(Array.isArray(data) ? data : data.requests || []);
            } else {
                throw new Error('Failed to load refund requests');
            }
        } catch (err) {
            logger.error('[RefundRequestsTable] Error loading requests:', err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, [filter]);

    useEffect(() => {
        loadRequests();
    }, [loadRequests]);

    // Approve request
    const handleApprove = async (requestId) => {
        setProcessingId(requestId);
        try {
            const token = getAuthToken();
            const response = await fetch(`/api/v1/force-majeure/refund-requests/${requestId}/approve`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                logger.log('[RefundRequestsTable] Approved request:', requestId);
                await loadRequests();
                if (onRefresh) onRefresh();
            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to approve');
            }
        } catch (err) {
            logger.error('[RefundRequestsTable] Approve error:', err);
            alert('Ошибка: ' + err.message);
        } finally {
            setProcessingId(null);
        }
    };

    // Reject request
    const handleReject = async (requestId, reason = 'Отклонено кассиром') => {
        setProcessingId(requestId);
        try {
            const token = getAuthToken();
            const response = await fetch(`/api/v1/force-majeure/refund-requests/${requestId}/reject`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ reason })
            });

            if (response.ok) {
                logger.log('[RefundRequestsTable] Rejected request:', requestId);
                await loadRequests();
                if (onRefresh) onRefresh();
            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to reject');
            }
        } catch (err) {
            logger.error('[RefundRequestsTable] Reject error:', err);
            alert('Ошибка: ' + err.message);
        } finally {
            setProcessingId(null);
        }
    };

    // Complete request (mark as refunded)
    const handleComplete = async (requestId) => {
        setProcessingId(requestId);
        try {
            const token = getAuthToken();
            const response = await fetch(`/api/v1/force-majeure/refund-requests/${requestId}/complete`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                logger.log('[RefundRequestsTable] Completed request:', requestId);
                await loadRequests();
                if (onRefresh) onRefresh();
            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to complete');
            }
        } catch (err) {
            logger.error('[RefundRequestsTable] Complete error:', err);
            alert('Ошибка: ' + err.message);
        } finally {
            setProcessingId(null);
        }
    };

    const getStatusBadge = (status) => {
        const statusConfig = {
            pending: { variant: 'warning', label: 'Ожидает', icon: Clock },
            approved: { variant: 'info', label: 'Одобрено', icon: Check },
            rejected: { variant: 'danger', label: 'Отклонено', icon: X },
            completed: { variant: 'success', label: 'Возвращено', icon: CheckCircle }
        };

        const config = statusConfig[status] || { variant: 'default', label: status, icon: Clock };
        const IconComponent = config.icon;

        return (
            <Badge variant={config.variant} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                <IconComponent size={12} />
                {config.label}
            </Badge>
        );
    };

    const getRefundTypeBadge = (type) => {
        return type === 'deposit' ? (
            <Badge variant="primary" style={{ fontSize: '11px' }}>На депозит</Badge>
        ) : (
            <Badge variant="secondary" style={{ fontSize: '11px' }}>На карту</Badge>
        );
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return '—';
        return new Date(dateStr).toLocaleDateString('ru-RU', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    };

    const formatAmount = (amount) => {
        return amount ? `${amount.toLocaleString()} сум` : '—';
    };

    return (
        <div style={{ padding: '0' }}>
            {/* Header */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '16px',
                flexWrap: 'wrap',
                gap: '12px'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <DollarSign size={20} color="#10b981" />
                    <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>Заявки на возврат</h3>
                    <Badge variant="default">{requests.length}</Badge>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {/* Filter */}
                    <select
                        value={filter}
                        onChange={(e) => setFilter(e.target.value)}
                        style={{
                            padding: '6px 12px',
                            borderRadius: '6px',
                            border: '1px solid #d1d5db',
                            fontSize: '13px',
                            background: 'white'
                        }}
                    >
                        <option value="all">Все</option>
                        <option value="pending">Ожидают</option>
                        <option value="approved">Одобренные</option>
                        <option value="completed">Завершённые</option>
                        <option value="rejected">Отклонённые</option>
                    </select>

                    <button
                        onClick={loadRequests}
                        disabled={loading}
                        style={{
                            padding: '6px 12px',
                            borderRadius: '6px',
                            border: '1px solid #d1d5db',
                            background: 'white',
                            cursor: loading ? 'not-allowed' : 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px'
                        }}
                    >
                        <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                    </button>
                </div>
            </div>

            {/* Error */}
            {error && (
                <div style={{
                    padding: '12px',
                    background: '#fef2f2',
                    borderRadius: '8px',
                    color: '#dc2626',
                    marginBottom: '16px',
                    fontSize: '14px'
                }}>
                    {error}
                </div>
            )}

            {/* Loading */}
            {loading && (
                <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>
                    <Loader2 size={24} className="animate-spin" style={{ margin: '0 auto 8px' }} />
                    <p>Загрузка...</p>
                </div>
            )}

            {/* Empty State */}
            {!loading && requests.length === 0 && (
                <div style={{
                    textAlign: 'center',
                    padding: '40px',
                    background: '#f9fafb',
                    borderRadius: '8px',
                    color: '#6b7280'
                }}>
                    <DollarSign size={32} style={{ opacity: 0.5, margin: '0 auto 8px' }} />
                    <p>Нет заявок на возврат</p>
                </div>
            )}

            {/* Table */}
            {!loading && requests.length > 0 && (
                <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                        <thead>
                            <tr style={{ background: '#f9fafb', borderBottom: '1px solid #e5e7eb' }}>
                                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600 }}>ID</th>
                                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600 }}>Пациент</th>
                                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600 }}>Сумма</th>
                                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600 }}>Тип</th>
                                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600 }}>Причина</th>
                                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600 }}>Статус</th>
                                <th style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600 }}>Дата</th>
                                <th style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 600 }}>Действия</th>
                            </tr>
                        </thead>
                        <tbody>
                            {requests.map((request) => (
                                <tr
                                    key={request.id}
                                    style={{
                                        borderBottom: '1px solid #e5e7eb',
                                        background: processingId === request.id ? '#f3f4f6' : 'white'
                                    }}
                                >
                                    <td style={{ padding: '12px' }}>#{request.id}</td>
                                    <td style={{ padding: '12px' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            <User size={16} color="#6b7280" />
                                            <span>{request.patient_name || `Пациент #${request.patient_id}`}</span>
                                        </div>
                                    </td>
                                    <td style={{ padding: '12px', fontWeight: 600, color: '#059669' }}>
                                        {formatAmount(request.amount)}
                                    </td>
                                    <td style={{ padding: '12px' }}>
                                        {getRefundTypeBadge(request.refund_type)}
                                    </td>
                                    <td style={{ padding: '12px', maxWidth: '200px' }}>
                                        <span style={{
                                            display: 'block',
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            whiteSpace: 'nowrap'
                                        }} title={request.reason}>
                                            {request.reason || '—'}
                                        </span>
                                    </td>
                                    <td style={{ padding: '12px' }}>
                                        {getStatusBadge(request.status)}
                                    </td>
                                    <td style={{ padding: '12px', fontSize: '12px', color: '#6b7280' }}>
                                        {formatDate(request.created_at)}
                                    </td>
                                    <td style={{ padding: '12px', textAlign: 'center' }}>
                                        {processingId === request.id ? (
                                            <Loader2 size={16} className="animate-spin" />
                                        ) : (
                                            <div style={{ display: 'flex', justifyContent: 'center', gap: '6px' }}>
                                                {request.status === 'pending' && (
                                                    <>
                                                        <button
                                                            onClick={() => handleApprove(request.id)}
                                                            title="Одобрить"
                                                            style={{
                                                                padding: '6px',
                                                                borderRadius: '4px',
                                                                border: 'none',
                                                                background: '#dcfce7',
                                                                color: '#16a34a',
                                                                cursor: 'pointer'
                                                            }}
                                                        >
                                                            <Check size={14} />
                                                        </button>
                                                        <button
                                                            onClick={() => handleReject(request.id)}
                                                            title="Отклонить"
                                                            style={{
                                                                padding: '6px',
                                                                borderRadius: '4px',
                                                                border: 'none',
                                                                background: '#fee2e2',
                                                                color: '#dc2626',
                                                                cursor: 'pointer'
                                                            }}
                                                        >
                                                            <X size={14} />
                                                        </button>
                                                    </>
                                                )}
                                                {request.status === 'approved' && (
                                                    <button
                                                        onClick={() => handleComplete(request.id)}
                                                        title="Отметить как возвращено"
                                                        style={{
                                                            padding: '6px 10px',
                                                            borderRadius: '4px',
                                                            border: 'none',
                                                            background: '#3b82f6',
                                                            color: 'white',
                                                            cursor: 'pointer',
                                                            fontSize: '12px',
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            gap: '4px'
                                                        }}
                                                    >
                                                        <CreditCard size={14} />
                                                        Выплатить
                                                    </button>
                                                )}
                                                {(request.status === 'completed' || request.status === 'rejected') && (
                                                    <span style={{ color: '#9ca3af', fontSize: '12px' }}>—</span>
                                                )}
                                            </div>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

export default RefundRequestsTable;
