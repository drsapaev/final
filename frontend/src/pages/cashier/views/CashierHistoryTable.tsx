/**
 * PR-UI-14-5: cashier payment-history table (verbatim JSX move from
 * CashierPanel — sortable headers, grouped rows, overflow action menu,
 * server-side pagination, inline empty state).
 *
 * UX Audit #4.2: clickable sortable headers (client-side sort).
 * UX Audit #2.2: primary «Принять» + overflow menu for the other 3
 * commands (native <details>) — fixes weak visual hierarchy and
 * narrow-screen flex-wrap breakage.
 * Action availability is fail-closed: hasBackendPaymentAction(row, ...)
 * only — never row.status inference (contract-pinned).
 */

import { useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { CheckCircle, Loader2, MoreVertical, Receipt, Undo2, XCircle } from 'lucide-react';

import { AppError, Badge, Button, Skeleton } from '../../../components/ui/macos';
import { formatUZS } from '../../../utils/formatCurrency';
import {
  getPaymentStatusMeta,
  getPaymentStatusLabel,
  hasBackendPaymentAction,
  type CashierPaymentRow,
  type CashierTranslationFn,
} from '../cashierPaymentContracts';
import type { CashierSortField, CashierSortDir } from '../cashierPaymentRows';

interface CashierHistoryTableProps {
  historyLoading: boolean;
  /** CSH-FE-001: last history-read failure (null = last load succeeded).
   * A failed read must never render as a server-confirmed empty history. */
  historyError?: string | null;
  /** CSH-FE-001: retry action for the error/stale banners (panel passes
   * triggerDataReload). */
  onRetryLoad?: () => void;
  filteredPayments: CashierPaymentRow[];
  sortField: CashierSortField;
  sortDir: CashierSortDir;
  onToggleSort: (field: CashierSortField) => void;
  /** Verbatim handler names — keeps the moved JSX byte-identical to the
   * original panel JSX (contract-test pins reference these identifiers). */
  confirmPayment: (paymentId: string | number | undefined) => void;
  openCancelDialog: (payment: CashierPaymentRow) => void;
  openRefundDialog: (payment: CashierPaymentRow) => void;
  handlePrintReceipt: (payment: CashierPaymentRow) => void;
  processingAction: { type?: string; id?: string | number } | null;
  currentPage: number;
  onCurrentPageChange: (updater: (p: number) => number) => void;
  totalPages: number;
  totalItems: number;
  tI18n: CashierTranslationFn;
}

// CSH-FE-046 (follow-up audit 2026-11-02): меню действий строки истории
// рендерится ПОРТАЛОМ в document.body с position:fixed и коллизией по
// вьюпорту. Прежде .cashier-overflow-popover был position:absolute внутри
// .cashier-table-scroll (overflow-x:auto ⇒ вычисляемый overflow-y:auto):
// меню последней строки обрезалось скролл-предком — z-index не спасает от
// клиппинга предка. Портал живёт вне скролл-контейнера, поэтому меню видно
// целиком на любой строке; свертывание вверх при нехватке места снизу.
interface OverflowMenuActionItem {
  itemClassName: string;
  onClick: () => void;
  disabled: boolean;
  ariaLabel: string;
  label: string;
  icon: ReactNode;
}

function OverflowMenuPortal({
  getTrigger,
  actions,
}: {
  getTrigger: () => HTMLElement | null;
  actions: OverflowMenuActionItem[];
}) {
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const [placement, setPlacement] = useState<{ top: number; left: number } | null>(null);

  useLayoutEffect(() => {
    const computePlacement = () => {
      const trigger = getTrigger();
      if (!trigger) return;
      const rect = trigger.getBoundingClientRect();
      // Оценка высоты/ширины меню до первого измерения (3 пункта ≈ 38px
      // каждый + паддинги); после рендера уточняется по реальным размерам.
      const measuredHeight = popoverRef.current?.offsetHeight || actions.length * 38 + 12;
      const measuredWidth = Math.max(popoverRef.current?.offsetWidth || 0, 200);
      const viewportWidth = window.innerWidth || 1024;
      const viewportHeight = window.innerHeight || 768;
      const spaceBelow = viewportHeight - rect.bottom;
      const spaceAbove = rect.top;
      // Коллизия: внизу не хватает места и сверху достаточно — раскрываемся вверх.
      const openUpward = spaceBelow < measuredHeight + 8 && spaceAbove > measuredHeight + 8;
      const top = openUpward
        ? Math.max(8, rect.top - measuredHeight - 4)
        : Math.min(rect.bottom + 4, Math.max(8, viewportHeight - measuredHeight - 8));
      // Выравнивание по правому краю триггера с ограничением вьюпортом.
      const left = Math.min(
        Math.max(8, rect.right - measuredWidth),
        Math.max(8, viewportWidth - measuredWidth - 8)
      );
      setPlacement({ top, left });
    };

    computePlacement();
    // Пересчёт при ресайзе (поворот экрана/зум) — меню остаётся во вьюпорте.
    window.addEventListener('resize', computePlacement);
    return () => window.removeEventListener('resize', computePlacement);
  }, [getTrigger, actions.length]);

  // CSH-FE-046: единый рендер — до вычисления координат меню скрыто
  // (visibility:hidden), после — fixed-координаты. Без мигания.
  const menuStyle: CSSProperties = placement === null
    ? { position: 'fixed', top: 0, left: 0, visibility: 'hidden' }
    : { position: 'fixed', top: `${placement.top}px`, left: `${placement.left}px` };

  return createPortal(
    <div
      ref={popoverRef}
      className="cashier-overflow-popover"
      role="menu"
      data-testid="cashier-overflow-popover"
      style={menuStyle}>
      {actions.map((action) => (
        <button
          key={action.ariaLabel}
          type="button"
          className={action.itemClassName}
          onClick={action.onClick}
          disabled={action.disabled}
          role="menuitem"
          aria-label={action.ariaLabel}>
          {action.icon} {action.label}
        </button>
      ))}
    </div>,
    document.body
  );
}

const CashierHistoryTable = ({
  historyLoading,
  historyError,
  onRetryLoad,
  filteredPayments,
  sortField,
  sortDir,
  onToggleSort,
  confirmPayment,
  openCancelDialog,
  openRefundDialog,
  handlePrintReceipt,
  processingAction,
  currentPage,
  onCurrentPageChange,
  totalPages,
  totalItems,
  tI18n,
}: CashierHistoryTableProps) => {
  const format = formatUZS;

  // CSH-FE-046 (follow-up audit 2026-11-02): открытая строка меню хранит ключ
  // строки и ссылку на её <details>; само меню рендерится порталом в body.
  const [openMenuRowKey, setOpenMenuRowKey] = useState<string | number | null>(null);
  const openMenuDetailsRef = useRef<HTMLDetailsElement | null>(null);

  // CSH-FE-001: a failed read is not a confirmed empty. With rows kept from
  // the last successful load the banner is a stale-data warning above them;
  // with no rows at all it replaces the «genuine empty» state entirely.
  const loadFailed = historyError !== null && historyError !== undefined;
  const hasRows = filteredPayments.length > 0;
  const retryAction = onRetryLoad ? (
    <Button size="small" variant="outline" onClick={onRetryLoad}>
      {tI18n('cashier.retry_load_btn')}
    </Button>
  ) : undefined;

  return (
    <div className="cashier-section-gap">
      {historyLoading ?
      (/* UX Audit #4.4: skeleton rows для history-tab — сохраняют заголовки таблицы. */
      <div className="cashier-table-scroll">
        <table className="cashier-table">
          <thead>
            <tr className="cashier-table-row">
              <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_date_time')}</th>
              <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_patient')}</th>
              <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_service')}</th>
              <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_method_short')}</th>
              <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_amount')}</th>
              <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_status')}</th>
              <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_actions')}</th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, i) => (
              <tr key={`skeleton-history-${i}`} className="cashier-table-row">
                {Array.from({ length: 7 }).map((_, j) => (
                  <td key={j} className="cashier-cell-padded"><Skeleton height={20} /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      ) :
      (loadFailed && !hasRows) ?
      (/* CSH-FE-001: failed initial load — error + retry, never the
          «empty history» state over a dead request. */
      <AppError
        title={tI18n('cashier.load_error_title')}
        description={historyError || tI18n('cashier.load_error_text')}
        action={retryAction}
      />
      ) :
      <>
      {loadFailed && hasRows &&
      (/* CSH-FE-001: failed refresh — kept rows stay visible under a
          stale-data warning with retry. */
      <AppError
        severity="warning"
        title={tI18n('cashier.load_error_title')}
        description={[historyError, tI18n('cashier.stale_data_note')].filter(Boolean).join(' ')}
        action={retryAction}
        className="cashier-mb-4"
      />
      )}

      <div className="cashier-table-scroll">
            <table className="cashier-table">
              <thead>
                <tr className="cashier-table-row">
                  {/* UX Audit #4.2: кликабельные заголовки с сортировкой. */}
                  <th className="cashier-text-sm cashier-text-primary cashier-th-sortable" onClick={() => onToggleSort('date')}>
                    {tI18n('cashier.col_date_time')} {sortField === 'date' && (sortDir === 'asc' ? '↑' : '↓')}
                  </th>
                  <th className="cashier-text-sm cashier-text-primary cashier-th-sortable" onClick={() => onToggleSort('patient')}>
                    {tI18n('cashier.col_patient')} {sortField === 'patient' && (sortDir === 'asc' ? '↑' : '↓')}
                  </th>
                  <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_service')}</th>
                  <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_method_short')}</th>
                  <th className="cashier-text-sm cashier-text-primary cashier-th-sortable" onClick={() => onToggleSort('amount')}>
                    {tI18n('cashier.col_amount')} {sortField === 'amount' && (sortDir === 'asc' ? '↑' : '↓')}
                  </th>
                  <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_status')}</th>
                  <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_actions')}</th>
                </tr>
              </thead>
              <tbody>
                {filteredPayments.length > 0 ?
            filteredPayments.map((row, index) => {
            // CSH-FE-046/047: ключ строки — единый для tr, меню-состояния и портала.
            const rowKey = row.id || row.payment_id || index;
            return (
            <tr key={`payment-${rowKey}`} className="cashier-table-row">

                  <td
                    aria-label={tI18n('cashier.payment_history_date_aria')}
                    className="cashier-text-sm cashier-text-primary">
                    <div className="cashier-date-stack">
                      <span className="cashier-date-main">{row.date || '—'}</span>
                      <span className="cashier-date-sub">{row.time || '—'}</span>
                    </div>
                  </td>
                  <td className="cashier-text-sm cashier-text-primary">
                    {String(row.patient ?? '')}
                  </td>
                  <td className="cashier-text-sm cashier-text-primary">
                    {/* PR-43 / Medium-24: services info rendered from row.service
                        (single service name). Multi-service breakdown requires
                        backend changes to the history endpoint payload. */}
                     {String(row.service ?? '—')}
                  </td>
                  <td className="cashier-text-sm cashier-text-primary">
                    {String(row.method ?? '')}
                  </td>
                  <td className="cashier-text-sm cashier-text-primary">
                    {format(row.total_amount || row.amount || 0)}
                  </td>
                  <td className="cashier-cell-padded">
                    <Badge
                      variant={getPaymentStatusMeta(row.status, tI18n).variant}
                      role="status"
                      aria-label={getPaymentStatusMeta(row.status, tI18n).ariaLabel}>
                      {getPaymentStatusLabel(row.status, tI18n)}
                    </Badge>
                  </td>
                  {/* CSH-FE-047 (follow-up audit 2026-11-02): <td> остаётся
                      нативной table-cell: прежде display:flex назначался
                      ПРЯМО на <td> (класс cashier-cell-actions на ячейке),
                      ломая табличный layout (анонимные box'ы, рассинхрон
                      колонок/границ). Теперь flex — на внутреннем div. */}
                  <td className="cashier-cell-padded">
                    <div className="cashier-cell-actions">
                    {/* UX Audit #2.2: primary action + overflow menu.
                        Раньше: 4 равноправные кнопки — слабая иерархия (Nielsen #4).
                        Теперь: primary «Принять» видна всегда, остальные 3 —
                        в overflow menu через нативный <details>. */}
                    <Button
                      size="small"
                      variant="primary"
                      onClick={() => confirmPayment(row.id)}
                      disabled={!hasBackendPaymentAction(row, 'confirm') || processingAction?.id === row.id}
                      aria-label={tI18n('cashier.confirm_payment_aria')}>
                      {processingAction?.id === row.id && processingAction?.type === 'confirm' ?
                        <Loader2 size={14} className="animate-spin" aria-hidden="true" /> :
                        <CheckCircle size={14} />}
                      {tI18n('cashier.confirm_payment_confirm')}
                    </Button>
                    <details
                      className="cashier-overflow-menu"
                      onToggle={(event) => {
                        const detailsEl = event.currentTarget;
                        if (detailsEl.open) {
                          openMenuDetailsRef.current = detailsEl;
                          setOpenMenuRowKey(rowKey);
                        } else if (openMenuRowKey === rowKey) {
                          openMenuDetailsRef.current = null;
                          setOpenMenuRowKey(null);
                        }
                      }}>
                      <summary className="cashier-overflow-trigger" aria-label={tI18n('cashier.more_actions_aria')}>
                        <MoreVertical size={16} aria-hidden="true" />
                      </summary>
                      {/* CSH-FE-046: контент меню — портал в document.body
                          (position:fixed + коллизия вьюпорта); прежний
                          absolute-поповер внутри .cashier-table-scroll
                          обрезался скролл-предком на нижних строках. */}
                      {openMenuRowKey === rowKey && (
                        <OverflowMenuPortal
                          getTrigger={() => openMenuDetailsRef.current?.querySelector('summary') ?? null}
                          actions={[
                            {
                              itemClassName: 'cashier-overflow-item cashier-overflow-item--danger',
                              onClick: () => openCancelDialog(row),
                              disabled: !hasBackendPaymentAction(row, 'cancel') || processingAction?.id === row.id,
                              ariaLabel: tI18n('cashier.btn_cancel'),
                              label: tI18n('cashier.btn_cancel'),
                              icon: <XCircle size={14} aria-hidden="true" />
                            },
                            {
                              itemClassName: 'cashier-overflow-item cashier-overflow-item--warning',
                              onClick: () => openRefundDialog(row),
                              disabled: !hasBackendPaymentAction(row, 'refund') || processingAction?.id === row.id,
                              ariaLabel: tI18n('cashier.refund_aria'),
                              label: tI18n('cashier.refund_confirm'),
                              icon: <Undo2 size={14} aria-hidden="true" />
                            },
                            {
                              itemClassName: 'cashier-overflow-item',
                              onClick: () => handlePrintReceipt(row),
                              disabled: !hasBackendPaymentAction(row, 'print_receipt') || processingAction?.id === row.id,
                              ariaLabel: tI18n('cashier.print_receipt_aria'),
                              label: tI18n('cashier.print_receipt_btn'),
                              icon: <Receipt size={14} aria-hidden="true" />
                            }
                          ]}
                        />
                      )}
                    </details>
                    </div>
                  </td>
                </tr>
            );
            }) :

            <tr className="cashier-empty-row">
                    <td colSpan={7} className="cashier-empty-cell">
                      {/* UX Audit #4.3: actionable empty state для истории. */}
                      <div className="cashier-empty-state cashier-empty-state--inline" role="status">
                        <div className="cashier-empty-state-title">{tI18n('cashier.empty_history_title')}</div>
                        <div className="cashier-empty-state-text">
                          {tI18n('cashier.empty_history_text')}
                        </div>
                      </div>
                    </td>
                  </tr>
            }
              </tbody>
            </table>

            {/* ✅ УЛУЧШЕНИЕ: Пагинация c Server-Side логикой */}
            {totalPages > 1 &&
        <div className="cashier-pagination">
                <Button
            size="small"
            variant="outline"
            disabled={currentPage === 1 || historyLoading}
            onClick={() => onCurrentPageChange((p) => Math.max(1, p - 1))}>

                  {tI18n('cashier.prev_page')}
                </Button>
                <span className="cashier-pagination-info">
                  {tI18n('cashier.pagination_info', { current: currentPage, total: totalPages, total_items: totalItems })}
                </span>
                <Button
            size="small"
            variant="outline"
            disabled={currentPage === totalPages || historyLoading}
            onClick={() => onCurrentPageChange((p) => Math.min(totalPages, p + 1))}>

                  {tI18n('cashier.next_page')}
                </Button>
              </div>
        }
          </div>
      </>
      }
      </div>
  );
};

export default CashierHistoryTable;
