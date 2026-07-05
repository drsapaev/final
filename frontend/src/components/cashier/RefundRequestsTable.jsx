/**
 * RefundRequestsTable - Table for managing refund requests
 *
 * Features:
 * - Display pending, approved, rejected refund requests
 * - Approve/Reject actions for pending requests
 * - Complete action for approved requests
 */
import { api } from '../../api/client';
import { useState, useEffect, useCallback } from 'react';
import {
  Check,
  X,
  DollarSign,
  Clock,
  CheckCircle,
  RefreshCw,
  Loader2,
  User,
  CreditCard
} from 'lucide-react';
import {
  AppEmpty, AppError, AppLoading, Badge, Button, Table, Select,
} from '../ui/macos';
import notify from '../../services/notify';
import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
import PropTypes from 'prop-types';

const REFUND_FILTER_OPTIONS = [
  { value: 'all', label: 'Все' },
  { value: 'pending', label: 'Ожидают' },
  { value: 'approved', label: 'Одобренные' },
  { value: 'completed', label: 'Завершённые' },
  { value: 'rejected', label: 'Отклонённые' }
];

const textCellStyle = {
  color: 'var(--mac-text-primary)'
};

const mutedCellStyle = {
  color: 'var(--mac-text-secondary)',
  fontSize: 'var(--mac-font-size-xs)'
};

const amountCellStyle = {
  color: 'var(--mac-success)',
  fontWeight: 'var(--mac-font-weight-semibold)'
};

const reasonCellStyle = {
  display: 'block',
  maxWidth: '220px',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
  whiteSpace: 'nowrap'
};

const inlineClusterStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 'var(--mac-spacing-2)'
};

const actionClusterStyle = {
  display: 'flex',
  justifyContent: 'center',
  gap: 'var(--mac-spacing-1)',
  flexWrap: 'wrap'
};

const headerStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 'var(--mac-spacing-3)',
  marginBottom: 'var(--mac-spacing-4)',
  flexWrap: 'wrap'
};

const statusIconStyle = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 'var(--mac-spacing-1)'
};

const REFUND_ACTION_CAN_FIELD = {
  approve: 'can_approve',
  reject: 'can_reject',
  complete: 'can_complete'
};

const hasBackendRefundAction = (request, action) => {
  const normalizedAction = String(action || '').trim().toLowerCase();
  if (!normalizedAction) {
    return false;
  }

  if (Array.isArray(request?.available_actions)) {
    return request.available_actions.some(
      (availableAction) => String(availableAction || '').trim().toLowerCase() === normalizedAction
    );
  }

  const canField = REFUND_ACTION_CAN_FIELD[normalizedAction];
  if (canField && Object.prototype.hasOwnProperty.call(request || {}, canField)) {
    return Boolean(request[canField]);
  }

  return false;
};

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
        params.append('status_filter', filter);
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

  const processRefundRequest = async (requestId, action, extraPayload = {}) => {
    setProcessingId(requestId);
    try {
      const token = getAuthToken();
      const response = await fetch(`/api/v1/force-majeure/refund-requests/${requestId}/process`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ action, ...extraPayload })
      });

      if (response.ok) {
        logger.log('[RefundRequestsTable] Processed request:', { requestId, action });
        await loadRequests();
        if (onRefresh) onRefresh();
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to process refund request');
      }
    } catch (err) {
      logger.error('[RefundRequestsTable] Process error:', err);
      notify.error('Ошибка: ' + (err.message || 'Неизвестная ошибка'));
    } finally {
      setProcessingId(null);
    }
  };

  // Approve request
  const handleApprove = async (requestId) => {
    await processRefundRequest(requestId, 'approve');
  };

  // Reject request
  const handleReject = async (requestId, reason = 'Отклонено кассиром') => {
    await processRefundRequest(requestId, 'reject', { rejection_reason: reason });
  };

  // Complete request (mark as refunded)
  const handleComplete = async (requestId) => {
    await processRefundRequest(requestId, 'complete');
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
      <Badge variant={config.variant} style={statusIconStyle}>
        <IconComponent size={12} aria-hidden="true" />
        {config.label}
      </Badge>
    );
  };

  const getRefundTypeBadge = (type) => {
    return type === 'deposit' ? (
      <Badge variant="primary">На депозит</Badge>
    ) : (
      <Badge variant="secondary">На карту</Badge>
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

  const renderActions = (request) => {
    if (processingId === request.id) {
      return (
        <span role="status" aria-live="polite" style={inlineClusterStyle}>
          <Loader2 size={16} className="animate-spin" aria-hidden="true" />
          <span style={mutedCellStyle}>Обработка</span>
        </span>
      );
    }

    const canApprove = hasBackendRefundAction(request, 'approve');
    const canReject = hasBackendRefundAction(request, 'reject');
    const canComplete = hasBackendRefundAction(request, 'complete');

    if (canApprove || canReject || canComplete) {
      return (
        <div style={actionClusterStyle}>
          {canApprove && (
            <Button
              variant="success"
              size="small"
              onClick={() => handleApprove(request.id)}
              title="Одобрить"
              aria-label={`Одобрить заявку на возврат ${request.id}`}
            >
              <Check size={14} aria-hidden="true" />
            </Button>
          )}
          {canReject && (
            <Button
              variant="danger"
              size="small"
              onClick={() => handleReject(request.id)}
              title="Отклонить"
              aria-label={`Отклонить заявку на возврат ${request.id}`}
            >
              <X size={14} aria-hidden="true" />
            </Button>
          )}
          {canComplete && (
            <Button
              variant="primary"
              size="small"
              onClick={() => handleComplete(request.id)}
              aria-label={`Отметить заявку на возврат ${request.id} как выплаченную`}
            >
              <CreditCard size={14} aria-hidden="true" />
              Выплатить
            </Button>
          )}
        </div>
      );
    }

    return <span style={mutedCellStyle}>—</span>;
  };

  const columns = [
    {
      key: 'id',
      title: 'ID',
      render: (id) => <span style={textCellStyle}>#{id}</span>
    },
    {
      key: 'patient_name',
      title: 'Пациент',
      render: (_value, request) => (
        <span style={inlineClusterStyle}>
          <User size={16} color="var(--mac-text-secondary)" aria-hidden="true" />
          <span>{request.patient_name || `Пациент #${request.patient_id}`}</span>
        </span>
      )
    },
    {
      key: 'amount',
      title: 'Сумма',
      render: (amount) => <span style={amountCellStyle}>{formatAmount(amount)}</span>
    },
    {
      key: 'refund_type',
      title: 'Тип',
      render: (type) => getRefundTypeBadge(type)
    },
    {
      key: 'reason',
      title: 'Причина',
      render: (reason) => (
        <span style={reasonCellStyle} title={reason}>
          {reason || '—'}
        </span>
      )
    },
    {
      key: 'status',
      title: 'Статус',
      render: (status) => getStatusBadge(status)
    },
    {
      key: 'created_at',
      title: 'Дата',
      render: (createdAt) => <span style={mutedCellStyle}>{formatDate(createdAt)}</span>
    },
    {
      key: 'actions',
      title: 'Действия',
      render: (_value, request) => renderActions(request)
    }
  ];

  return (
    <section aria-labelledby="refund-requests-title">
      <div style={headerStyle}>
        <div style={inlineClusterStyle}>
          <DollarSign size={20} color="var(--mac-success)" aria-hidden="true" />
          <h3
            id="refund-requests-title"
            style={{
              margin: 0,
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)'
            }}
          >
            Заявки на возврат
          </h3>
          <Badge variant="default">{requests.length}</Badge>
        </div>

        <div style={inlineClusterStyle}>
          <Select
            id="refund-request-filter"
            value={filter}
            onChange={setFilter}
            options={REFUND_FILTER_OPTIONS}
            size="small"
            aria-label="Фильтр заявок на возврат"
          />

          <Button
            variant="secondary"
            size="small"
            onClick={loadRequests}
            disabled={loading}
            aria-label="Обновить список заявок на возврат"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} aria-hidden="true" />
          </Button>
        </div>
      </div>

      {error && (
        <AppError
          title="Не удалось загрузить заявки на возврат"
          description={error}
          action={
            <Button variant="secondary" size="small" onClick={loadRequests}>
              Повторить
            </Button>
          }
          style={{ marginBottom: 'var(--mac-spacing-4)' }}
        />
      )}

      {loading && (
        <AppLoading
          title="Загрузка заявок на возврат"
          size="sm"
          style={{ minHeight: 144 }}
        />
      )}

      {!loading && requests.length === 0 && (
        <AppEmpty
          title="Нет заявок на возврат"
          description="Когда появятся новые запросы на возврат, они будут показаны здесь."
          icon={<DollarSign />}
        />
      )}

      {!loading && requests.length > 0 && (
        <Table
          columns={columns}
          data={requests}
          sortable={false}
          hoverable={false}
          size="sm"
          variant="default"
        />
      )}
    </section>
  );
};

RefundRequestsTable.propTypes = {
  onRefresh: PropTypes.func
};

export default RefundRequestsTable;
