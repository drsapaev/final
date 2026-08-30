
import {
  Badge, Icon,
} from '../ui/macos';
import { formatRegistrarTime } from '../../utils/dateUtils';
import { DataTable, type DataTableColumn } from '../ui/DataTable';
// UX Audit Registrar #3: inline-стили перенесены в QueueTable.css.
import './QueueTable.css';

// === Domain types ===
// QueueTable is a pure display component driven by ModernQueueManager.
// It receives a pre-translated strings object (queueTableT) plus the
// queue snapshot and the effective doctor selection.

export interface QueueTableEntry {
  id?: string | number;
  patient_name?: string;
  name?: string;
  patient_phone?: string;
  phone?: string;
  queue_number?: number | string;
  number?: number | string;
  queue_time?: string;
  created_at?: string;
  timestamp?: string;
  status?: string;
  source?: string;
  source_kind?: string;
  [key: string]: unknown;
}

export interface QueueTableData {
  entries?: QueueTableEntry[];
  is_open?: boolean;
  [key: string]: unknown;
}

export interface QueueTableDoctor {
  id?: string | number;
  full_name?: string;
  name?: string;
  specialty?: string;
  [key: string]: unknown;
}

export interface QueueTableT {
  selectDoctor?: string;
  patient?: string;
  phone?: string;
  time?: string;
  status?: string;
  actions?: string;
  called?: string;
  queueEmpty?: string;
  queueNotFound?: string;
  [key: string]: unknown;
}

export interface QueueTableProps {
  queueData?: QueueTableData | null;
  effectiveDoctor?: QueueTableDoctor | string | null;
  loading?: boolean;
  /** Pre-translated strings object (built by ModernQueueManager). */
  t?: QueueTableT;
  [key: string]: unknown;
}

// PR-UI-09c-2: status → {variant, label, icon} mapping (moved out of component
// body for stable identity). 6 statuses preserved verbatim from original.
const STATUS_MAP: Record<string, { variant: string; label: string; icon: string }> = {
  'waiting':     { variant: 'warning',   label: 'Ожидает',   icon: 'clock' },
  'called':      { variant: 'info',      label: 'Вызван',    icon: 'bell' },
  'in_progress': { variant: 'primary',   label: 'На приеме', icon: 'person.fill' },
  'completed':   { variant: 'success',   label: 'Завершен',  icon: 'checkmark.circle' },
  'cancelled':   { variant: 'secondary', label: 'Отменен',   icon: 'xmark.circle' },
  'no_show':     { variant: 'secondary', label: 'Не явился', icon: 'person.crop.circle.badge.xmark' }
};

// PR-UI-09c-2: formatTime helper (moved out of component body). Fixes the
// original mojibake typo `'вЂ”'` (corrupted em-dash) → proper `'—'` per §5.
const formatTime = (timestamp: string | number | null | undefined): string => {
  if (!timestamp) return '—';
  try {
    return formatRegistrarTime(timestamp) || '—';
  } catch {
    return '—';
  }
};

// PR-UI-09c-2: renderStatusBadge helper — uses STATUS_MAP.
const renderStatusBadge = (status: string) => {
  const config = STATUS_MAP[status] || {
    variant: 'secondary', label: status || '—', icon: 'questionmark.circle'
  };
  return (
    <Badge variant={config.variant}>
      <Icon name={config.icon} size="small" className="qt-status-badge-icon" />
      {config.label}
    </Badge>
  );
};

// PR-UI-09c-2: source classification (QR vs Desk) — used to pick CSS class.
const isOnlineSource = (entry: QueueTableEntry): boolean =>
  entry.source === 'online' ||
  entry.source_kind === 'online_queue' ||
  entry.source === 'qr';

/**
 * PR-UI-12-4: bounded scroll-viewport height (px) for the queue table.
 *
 * Layout parameter for the sticky-header viewport (see DataTable
 * "Sticky header viewport" doc note) — NOT a sticky offset; the kit measures
 * header/filter row offsets itself. 480px ≈ 9 visible rows (md size ≈ 48px
 * per row incl. borders): the queue stays inside the registrar queue card on
 * a 720px viewport while the manager's call-next controls remain reachable,
 * and queues longer than ~9 entries scroll internally under a sticky header.
 */
const QUEUE_TABLE_VIEWPORT_MAX_HEIGHT = 480;

/**
 * QueueTable Component — displays the current queue entries in a canonical
 * DataTable format.
 *
 * PR-UI-09c-2 migration:
 * - Replaced bespoke native <table> with canonical DataTable + column config
 * - Preserved 4 external early-return states (selectDoctor / loading /
 *   queueNotFound / queueEmpty) per QueueTable 4-state strategy (NOT
 *   collapsed into single DataTable emptyState)
 * - Moved inline QR/Desk badge styles to CSS classes (.qt-source-badge-*)
 * - Preserved "called" row highlight via CSS :has() on .qt-called-marker
 *   (canonical DataTable has no rowClassName prop — CSS-only solution)
 * - Contract invariants preserved (see QueueManager.contract.test.tsx):
 *   no row-level action invocations, no early-return collapsed branches.
 */
const QueueTable = ({
    queueData = null,
    effectiveDoctor = null,
    loading = false,
    t = {}
}: QueueTableProps) => {
    // State 1: no doctor selected (preserved verbatim per contract test)
    if (!effectiveDoctor) {
        return (
            <div className="qt-empty-state">
                <Icon name="person.crop.circle.badge.questionmark" size="large" className="qt-empty-state-icon" />
                <p>{(t as Record<string, string>)?.selectDoctor || 'Выберите специалиста'}</p>
            </div>
        );
    }

    // State 2: loading (preserved)
    if (loading) {
        return (
            <div className="qt-empty-state">
                <div className="mqm-spinner qt-loading-spinner"></div>
                <p>Загрузка очереди...</p>
            </div>
        );
    }

    // State 3: no queue data (preserved)
    if (!queueData) {
        return (
            <div className="qt-empty-state">
                <Icon name="exclamationmark.triangle" size="large" className="qt-empty-state-icon-warning" />
                <p>{(t as Record<string, string>)?.queueNotFound || 'Очередь не найдена'}</p>
                <p className="qt-empty-state-hint">
                    Попробуйте сгенерировать QR код для создания очереди
                </p>
            </div>
        );
    }

    const entries = queueData?.entries || [];

    // State 4: empty queue (preserved)
    if (entries.length === 0) {
        return (
            <div className="qt-empty-state">
                <Icon name="person.2.slash" size="large" className="qt-empty-state-icon" />
                <p>{(t as Record<string, string>)?.queueEmpty || 'Очередь пуста'}</p>
                <p className="qt-empty-state-hint">
                    Пациенты могут записаться через QR код
                </p>
            </div>
        );
    }

    // PR-UI-09c-2: canonical DataTable column config (replaces native <table>)
    const columns: DataTableColumn<QueueTableEntry>[] = [
        {
            key: 'queue_number',
            title: '№',
            render: (_v: unknown, entry: QueueTableEntry, index: number) => (
                <span className="qt-table-cell-number">
                    {entry.queue_number || entry.number || index + 1}
                </span>
            )
        },
        {
            key: 'patient_name',
            title: (t as Record<string, string>)?.patient || 'Пациент',
            render: (_v: unknown, entry: QueueTableEntry) => {
                const online = isOnlineSource(entry);
                return (
                    <span className="qt-table-cell-primary">
                        {entry.patient_name || entry.name || '—'}
                        <span className={online ? 'qt-source-badge qt-source-badge-qr' : 'qt-source-badge qt-source-badge-desk'}>
                            {online ? 'QR' : 'Desk'}
                        </span>
                    </span>
                );
            }
        },
        {
            key: 'patient_phone',
            title: (t as Record<string, string>)?.phone || 'Телефон',
            render: (_v: unknown, entry: QueueTableEntry) => (
                <span className="qt-table-cell-phone">
                    {entry.patient_phone || entry.phone || '—'}
                </span>
            )
        },
        {
            key: 'queue_time',
            title: (t as Record<string, string>)?.time || 'Время',
            render: (_v: unknown, entry: QueueTableEntry) => (
                <span className="qt-table-cell-secondary">
                    {formatTime(entry.queue_time || entry.created_at || entry.timestamp)}
                </span>
            )
        },
        {
            key: 'status',
            title: (t as Record<string, string>)?.status || 'Статус',
            render: (status: unknown) => renderStatusBadge(String(status ?? ''))
        },
        {
            key: 'actions',
            title: (t as Record<string, string>)?.actions || 'Действия',
            render: (_v: unknown, entry: QueueTableEntry) => (
                <div className="qt-table-cell-actions">
                    {entry.status === 'called' && (
                        <Badge variant="info" className="qt-called-marker">
                            <Icon name="bell.fill" size="small" className="qt-status-badge-icon" />
                            {(t as Record<string, string>)?.called || 'Вызван'}
                        </Badge>
                    )}
                </div>
            )
        }
    ];

    return (
        <div className="qt-table-container">
            <DataTable
                columns={columns}
                data={entries}
                sortable={false}
                hoverable={true}
                size="md"
                variant="default"
                // PR-UI-12-2 (plan §PR-UI-12 item 2): roving keyboard navigation
                // — ArrowUp/ArrowDown/Home/End move focus between queue rows so
                // keyboard and screen-reader users can review the queue without
                // a pointer.
                //
                // Contract reconciliation (AGENTS_UI workflow step 4 / §18):
                // the plan's original wording "Enter для вызова пациента" (a
                // per-row call action) is superseded by the repo invariant in
                // QueueManager.contract.test.tsx — "keeps registrar queue
                // call-next as a backend-owned command, not a row command".
                // Queue calling stays strictly ordered through the manager's
                // call-next button (already keyboard-accessible via Tab+Enter);
                // rows expose focus movement only, no row-level actions.
                keyboardNavigation
                // PR-UI-12-4 (plan §PR-UI-12 item 4 "sticky header при скролле"):
                // sticky header + bounded scroll viewport. The viewport bound
                // is a layout parameter (NOT a sticky offset — the header/filter
                // offsets are measured by the kit): 480px keeps the queue table
                // inside the registrar queue card on a 720px e2e viewport
                // (~9 rows visible) so the call-next controls above it stay
                // reachable; longer operational queues get an internal scrollbar
                // with the header row staying visible. Queues that fit (~9 rows
                // or fewer) render pixel-identically to the unbounded table.
                stickyHeader
                maxHeight={QUEUE_TABLE_VIEWPORT_MAX_HEIGHT}
                getRowId={(row: QueueTableEntry, index: number) => row.id ?? `qt-row-${index}`}
            />
        </div>
    );
};


export default QueueTable;
