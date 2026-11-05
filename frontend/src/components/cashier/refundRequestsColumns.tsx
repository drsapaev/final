/**
 * PR-UI-14-6: refund-request table presentation — status/type badges,
 * date/amount formatters, fail-closed action cluster and the canonical
 * DataTable column builder (verbatim move from RefundRequestsTable.tsx).
 *
 * Presentation only, no network. The table component supplies t, the
 * anti-double-click processingId and the three process handlers; the only
 * local state is the per-cell reason expansion (CSH-FE-049, see below).
 */

import { useId, useState } from 'react';
import {
  Check,
  X,
  Clock,
  CheckCircle,
  Loader2,
  User,
  CreditCard,
} from 'lucide-react';

import { Badge, Button } from '../ui/macos';
import type { DataTableColumn } from '../ui/DataTable';
import { formatUZS } from '../../utils/formatCurrency';
import { hasBackendRefundAction, type RefundRequest, type RefundTranslationFn } from './refundRequestsContracts';

export const getRefundStatusBadge = (status: unknown, t: RefundTranslationFn) => {
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

// CSH-FE-051 (follow-up audit 2026-11-02): прежний маппинг рисовал «На карту»
// для ВСЕГО, кроме deposit — наличный возврат (cash) выдавал себя за
// карточный, а неизвестные/будущие значения enum'а лгали тем же образом.
// Явный словарь по каноническому RefundType бэкенда
// (bank_transfer | deposit | cash) + честное «Неизвестно» для остального.
export const REFUND_TYPE_BADGE_CONFIG: Record<string, { key: string; variant: string }> = {
  deposit: { key: 'misc.rrt_na_depozit', variant: 'primary' },
  bank_transfer: { key: 'misc.rrt_na_kartu', variant: 'secondary' },
  cash: { key: 'misc.rrt_nalichnymi', variant: 'success' },
};

export const getRefundTypeBadge = (type: unknown, t: RefundTranslationFn) => {
  const normalized = String(type ?? '').trim();
  const config = REFUND_TYPE_BADGE_CONFIG[normalized];
  if (!config) {
    return <Badge variant="outline">{t('misc.rrt_unknown')}</Badge>;
  }
  return <Badge variant={config.variant}>{t(config.key)}</Badge>;
};

// CSH-FE-049 (follow-up audit 2026-11-02): ячейка причины возврата с
// фокусируемым раскрытием полного текста. Прежде: ellipsized span с
// hover-title на нефокусируемом элементе — sighted keyboard-only сотрудник
// не мог прочесть полное обоснование перед одобрением/отказом по возврату
// (DOM-текст полон, но визуально обрезан). Порог: строки до ~28 символов
// помещаются в 220px без обрезки — для них кнопка не нужна.
const REASON_EXPAND_THRESHOLD = 28;

function RefundReasonCell({ reason, t }: { reason: unknown; t: RefundTranslationFn }) {
  const [expanded, setExpanded] = useState(false);
  const domId = useId();
  const text = reason ? String(reason) : '—';
  const isLong = text.length > REASON_EXPAND_THRESHOLD;
  return (
    <span
      id={`refund-reason-${domId}`}
      data-testid="refund-cell-reason"
      className={`refund-cell-reason${expanded ? ' refund-cell-reason--expanded' : ''}`}
      title={text}>
      {text}
      {isLong && (
        <button
          type="button"
          className="refund-reason-toggle"
          data-testid="refund-reason-toggle"
          aria-expanded={expanded}
          aria-controls={`refund-reason-${domId}`}
          onClick={() => setExpanded((prev) => !prev)}>
          {t('misc.rrt_reason_expand')}
        </button>
      )}
    </span>
  );
}

export const formatRefundDate = (dateStr: unknown) => {
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
export const formatRefundAmount = (amount: unknown) => amount ? formatUZS(amount as number | string) : '—';

export interface RefundRequestActionHandlers {
  handleApprove: (requestId: string | number | undefined) => Promise<void>;
  handleReject: (requestId: string | number | undefined, reason?: string) => Promise<void>;
  handleComplete: (requestId: string | number | undefined) => Promise<void>;
}

export const buildRefundRequestColumns = (
  t: RefundTranslationFn,
  processingId: string | number | null,
  handlers: RefundRequestActionHandlers,
): DataTableColumn<RefundRequest>[] => {
  const { handleApprove, handleReject, handleComplete } = handlers;

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

  return [
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
      // CSH-FE-050: колонка читает реальное поле ответа `refund_amount`
      // (RefundRequestResponse не отдаёт `amount` — раньше каждая легитимная
      // сумма возврата рендерилась как «—»).
      key: 'refund_amount',
      title: t('payment.col_amount'),
      render: (amount: unknown) => <span className="refund-cell-amount">{formatRefundAmount(amount)}</span>
    },
    {
      key: 'refund_type',
      title: t('payment.col_type'),
      render: (type: unknown) => getRefundTypeBadge(type, t)
    },
    {
      key: 'reason',
      title: t('payment.col_reason'),
      // CSH-FE-049 (follow-up audit 2026-11-02): прежде полный текст причины
      // был доступен только через hover-title на НЕфокусируемом span —
      // клавиатурный сотрудник не мог прочесть обоснование перед
      // одобрением/отказом. Теперь фокусируемая кнопка «Показать полностью»
      // раскрывает текст с переносом (aria-expanded/aria-controls).
      render: (reason: unknown) => <RefundReasonCell reason={reason} t={t} />
    },
    {
      key: 'status',
      title: t('payment.col_status'),
      render: (status: unknown) => getRefundStatusBadge(status, t)
    },
    {
      key: 'created_at',
      title: t('payment.col_date'),
      render: (createdAt: unknown) => <span className="refund-cell-muted">{formatRefundDate(createdAt)}</span>
    },
    {
      key: 'actions',
      title: t('payment.col_actions'),
      render: (_value: unknown, request: RefundRequest) => renderActions(request)
    }
  ];
};
