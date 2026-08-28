
import { useTranslation } from '../../i18n/useTranslation';
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
  Loader2,
  User,
  CreditCard
} from 'lucide-react';
import {
  AppEmpty, AppError, AppLoading, Badge, Button, Select,
} from '../ui/macos';
import { DataTable, type DataTableColumn } from '../ui/DataTable';
import notify from '../../services/notify';
import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
import { formatUZS } from '../../utils/formatCurrency';
// UX Audit #3.4: inline-стили перенесены в CSS-классы.
import './RefundRequestsTable.css';

const getRefundFilterOptions = (t: RefundTranslationFn) => [
  { value: 'all', label: t('misc.rrt_filter_all') },
  { value: 'pending', label: t('misc.rrt_filter_pending') },
  { value: 'approved', label: t('misc.rrt_filter_approved') },
  { value: 'completed', label: t('misc.rrt_filter_completed') },
  { value: 'rejected', label: t('misc.rrt_filter_rejected') },
];

// UX Audit #3.4: inline-стили перенесены в RefundRequestsTable.css.
// Раньше было 8 объектов style={...}, что не консистентно с остальным UI
// и усложняло поддержку тёмной темы.

// Minimal translation fn signature accepted by the helpers below. Mirrors the
// `useTranslation` adapter shape without coupling this file to its concrete type.
export type RefundTranslationFn = (key: string, options?: Record<string, unknown>) => string;

// Shape of a refund request row surfaced by `/force-majeure/refund-requests`.
// All fields are optional because the backend may omit context fields depending
// on the request status and the caller's permissions.
export interface RefundRequest {
  id?: string | number;
  patient_id?: string | number;
  patient_name?: string;
  amount?: number | string;
  refund_type?: string;
  reason?: string;
  status?: string;
  created_at?: string;
  available_actions?: unknown[];
  can_approve?: boolean;
  can_reject?: boolean;
  can_complete?: boolean;
  [key: string]: unknown;
}

export interface RefundRequestsTableProps {
  onRefresh?: () => void;
}

const REFUND_ACTION_CAN_FIELD = {
  approve: 'can_approve',
  reject: 'can_reject',
  complete: 'can_complete'
};

const hasBackendRefundAction = (request: RefundRequest | null | undefined, action: string): boolean => {
  const normalizedAction = String(action || '').trim().toLowerCase();
  if (!normalizedAction) {
    return false;
  }

  if (Array.isArray(request?.available_actions)) {
    return request.available_actions.some(
      (availableAction: unknown) => String(availableAction || '').trim().toLowerCase() === normalizedAction
    );
  }

  const canField = REFUND_ACTION_CAN_FIELD[normalizedAction as keyof typeof REFUND_ACTION_CAN_FIELD];
  if (canField && request && Object.prototype.hasOwnProperty.call(request, canField)) {
    return Boolean(request[canField]);
  }

  return false;
};

const RefundRequestsTable = ({ onRefresh }: RefundRequestsTableProps) => {
  const { t: rawT } = useTranslation(); const t = rawT as RefundTranslationFn;
  const [requests, setRequests] = useState<RefundRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [processingId, setProcessingId] = useState<string | number | null>(null);
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

      const response = await fetch(`/force-majeure/refund-requests?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json() as RefundRequest[] | { requests?: RefundRequest[] };
        setRequests(Array.isArray(data) ? data : data.requests || []);
      } else {
        throw new Error('Failed to load refund requests');
      }
    } catch (err) {
      logger.error('[RefundRequestsTable] Error loading requests:', err);
      setError((err instanceof Error ? err.message : String(err)));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    loadRequests();
  }, [loadRequests]);

  const processRefundRequest = async (
    requestId: string | number,
    action: string,
    extraPayload: Record<string, unknown> = {}
  ) => {
    setProcessingId(requestId);
    try {
      const token = getAuthToken();
      const response = await fetch(`/force-majeure/refund-requests/${requestId}/process`, {
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
      notify.error(t('payment.refund_error') + ((err instanceof Error ? err.message : String(err)) || t('payment.unknown_error')));
    } finally {
      setProcessingId(null);
    }
  };

  // Approve request
  const handleApprove = async (requestId: string | number | undefined) => {
    if (requestId === undefined) return;
    await processRefundRequest(requestId, 'approve');
  };

  // Reject request
  const handleReject = async (requestId: string | number | undefined, reason: string = t('misc.rrt_otkloneno_kassirom')) => {
    if (requestId === undefined) return;
    await processRefundRequest(requestId, 'reject', { rejection_reason: reason });
  };

  // Complete request (mark as refunded)
  const handleComplete = async (requestId: string | number | undefined) => {
    if (requestId === undefined) return;
    await processRefundRequest(requestId, 'complete');
  };

  const getStatusBadge = (status: unknown) => {
    const statusConfig = {
      pending: { variant: 'warning', label: t('misc.rrt_ozhidaet'), icon: Clock },
      approved: { variant: 'info', label: t('misc.rrt_odobreno'), icon: Check },
      rejected: { variant: 'danger', label: t('misc.rrt_otkloneno'), icon: X },
      completed: { variant: 'success', label: t('misc.rrt_vozvrascheno'), icon: CheckCircle }
    };

    const config = (typeof status === 'string' && status in statusConfig
      ? statusConfig[status as keyof typeof statusConfig]
      : null) || { variant: 'default', label: String(status ?? ''), icon: Clock };
    const IconComponent = config.icon;

    return (
      <Badge variant={config.variant} className="refund-status-icon">
        <IconComponent size={12} aria-hidden="true" />
        {config.label}
      </Badge>
    );
  };

  const getRefundTypeBadge = (type: unknown) => {
    return type === 'deposit' ? (
      <Badge variant="primary">{t('misc.rrt_na_depozit')}</Badge>
    ) : (
      <Badge variant="secondary">{t('misc.rrt_na_kartu')}</Badge>
    );
  };

  const formatDate = (dateStr: unknown) => {
    if (!dateStr) return '—';
    return new Date(String(dateStr)).toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // UX Audit #2.3: используем единый formatUZS из utils/formatCurrency.js.
  const formatAmount = (amount: unknown) => amount ? formatUZS(amount as number | string) : '—';

  const renderActions = (request: RefundRequest) => {
    if (processingId === request.id) {
      return (
        <span role="status" aria-live="polite" className="refund-inline-cluster">
          <Loader2 size={16} className="animate-spin" aria-hidden="true" />
          <span className="refund-cell-muted">{t('misc.rrt_obrabotka')}</span>
        </span>
      );
    }

    const canApprove = hasBackendRefundAction(request, 'approve');
    const canReject = hasBackendRefundAction(request, 'reject');
    const canComplete = hasBackendRefundAction(request, 'complete');

    if (canApprove || canReject || canComplete) {
      return (
        <div className="refund-action-cluster">
          {canApprove && (
            <Button
              variant="secondary"
              color="success"
              size="md"
              onClick={() => handleApprove(request.id)}
              title={t('misc.rrt_odobrit')}
              aria-label={t('misc.rrt_odobrit_zayavku_na_vozvrat_r', { id: request.id })}
            >
              <Check size={14} aria-hidden="true" />
            </Button>
          )}
          {canReject && (
            <Button
              variant="danger"
              size="md"
              onClick={() => handleReject(request.id)}
              title={t('misc.rrt_otklonit')}
              aria-label={t('misc.rrt_otklonit_zayavku_na_vozvrat_', { id: request.id })}
            >
              <X size={14} aria-hidden="true" />
            </Button>
          )}
          {canComplete && (
            <Button
              variant="primary"
              size="md"
              onClick={() => handleComplete(request.id)}
              aria-label={t('misc.rrt_otmetit_zayavku_na_vozvrat_r', { id: request.id })}
            >
              <CreditCard size={14} aria-hidden="true" />
              Выплатить
            </Button>
          )}
        </div>
      );
    }

    return <span className="refund-cell-muted">—</span>;
  };

  const columns: DataTableColumn<RefundRequest>[] = [
    {
      key: 'id',
      title: 'ID',
      render: (id: unknown) => <span className="refund-cell-text">#{String(id ?? '')}</span>
    },
    {
      key: 'patient_name',
      title: t('payment.col_patient'),
      render: (_value: unknown, request: RefundRequest) => (
        <span className="refund-inline-cluster">
          <User size={16} color="var(--mac-text-secondary)" aria-hidden="true" />
          <span>{request.patient_name || t('misc.rrt_patsient_request_patient_id', { patient_id: request.patient_id })}</span>
        </span>
      )
    },
    {
      key: 'amount',
      title: t('payment.col_amount'),
      render: (amount: unknown) => <span className="refund-cell-amount">{formatAmount(amount)}</span>
    },
    {
      key: 'refund_type',
      title: t('payment.col_type'),
      render: (type: unknown) => getRefundTypeBadge(type)
    },
    {
      key: 'reason',
      title: t('payment.col_reason'),
      render: (reason: unknown) => (
        <span className="refund-cell-reason" title={String(reason ?? '')}>
          {reason ? String(reason) : '—'}
        </span>
      )
    },
    {
      key: 'status',
      title: t('payment.col_status'),
      render: (status: unknown) => getStatusBadge(status)
    },
    {
      key: 'created_at',
      title: t('payment.col_date'),
      render: (createdAt: unknown) => <span className="refund-cell-muted">{formatDate(createdAt)}</span>
    },
    {
      key: 'actions',
      title: t('payment.col_actions'),
      render: (_value: unknown, request: RefundRequest) => renderActions(request)
    }
  ];

  return (
    <section aria-labelledby="refund-requests-title">
      <div className="refund-header">
        <div className="refund-inline-cluster">
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

        <div className="refund-inline-cluster">
          <Select
            id="refund-request-filter"
            value={filter}
            onChange={(v: unknown) => setFilter(String(v))}
            options={getRefundFilterOptions(t)}
            size="default"
            aria-label={t('misc.rrt_filtr_zayavok_na_vozvrat')}
          />
          {/* UX Audit #1.3: дублирующая кнопка «Обновить» убрана.
              Глобальная кнопка «Обновить» в stats-card CashierPanel
              вызывает onRefresh → loadRequests. Лишний триггер (Nielsen #8 —
              эстетический и минималистичный дизайн) создавал когнитивную
              неоднозначность: «обновляет ли кнопка весь экран или только
              эту таблицу?». При смене фильтра список всё равно
              авто-обновляется через useEffect → loadRequests. */}
        </div>
      </div>

      {error && (
        <AppError
          title={t('misc.rrt_ne_udalos_zagruzit_zayavki_n')}
          description={error}
          action={
            <Button variant="secondary" size="md" onClick={loadRequests}>
              Повторить
            </Button>
          }
          style={{ marginBottom: 'var(--mac-spacing-4)' }}
        />
      )}

      {loading && (
        <AppLoading
          title={t('misc.rrt_zagruzka_zayavok_na_vozvrat')}
          size="md"
          style={{ minHeight: 144 }}
        />
      )}

      {!loading && requests.length === 0 && (
        <AppEmpty
          title={t('misc.rrt_net_zayavok_na_vozvrat')}
          description={t('misc.rrt_kogda_poyavyatsya_novye_zapr')}
          icon={<DollarSign />}
        />
      )}

      {!loading && requests.length > 0 && (
        <DataTable
          columns={columns}
          data={requests}
          sortable={false}
          hoverable={false}
          size="md"
          variant="default"
        />
      )}
    </section>
  );
};


export default RefundRequestsTable;
