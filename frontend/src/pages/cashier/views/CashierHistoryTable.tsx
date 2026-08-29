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

import { CheckCircle, Loader2, MoreVertical, Receipt, Undo2, XCircle } from 'lucide-react';

import { Badge, Button, Skeleton } from '../../../components/ui/macos';
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

const CashierHistoryTable = ({
  historyLoading,
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
            filteredPayments.map((row, index) =>
            <tr key={`payment-${row.id || row.payment_id || index}`} className="cashier-table-row">

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
                  <td className="cashier-cell-actions">
                    {/* UX Audit #2.2: primary action + overflow menu.
                        Раньше: 4 равноправные кнопки (success/danger/warning/ghost) —
                        слабая визуальная иерархия (Nielsen #4),
                        на узких экранах ломалось flex-wrap.
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
                    <details className="cashier-overflow-menu">
                      <summary className="cashier-overflow-trigger" aria-label={tI18n('cashier.more_actions_aria')}>
                        <MoreVertical size={16} aria-hidden="true" />
                      </summary>
                      <div className="cashier-overflow-popover" role="menu">
                        <button
                          type="button"
                          className="cashier-overflow-item cashier-overflow-item--danger"
                          onClick={() => openCancelDialog(row)}
                          disabled={!hasBackendPaymentAction(row, 'cancel') || processingAction?.id === row.id}
                          role="menuitem"
                          aria-label={tI18n('cashier.btn_cancel')}>
                          <XCircle size={14} aria-hidden="true" /> {tI18n('cashier.btn_cancel')}
                        </button>
                        <button
                          type="button"
                          className="cashier-overflow-item cashier-overflow-item--warning"
                          onClick={() => openRefundDialog(row)}
                          disabled={!hasBackendPaymentAction(row, 'refund') || processingAction?.id === row.id}
                          role="menuitem"
                          aria-label={tI18n('cashier.refund_aria')}>
                          <Undo2 size={14} aria-hidden="true" /> {tI18n('cashier.refund_confirm')}
                        </button>
                        <button
                          type="button"
                          className="cashier-overflow-item"
                          onClick={() => handlePrintReceipt(row)}
                          disabled={!hasBackendPaymentAction(row, 'print_receipt') || processingAction?.id === row.id}
                          role="menuitem"
                          aria-label={tI18n('cashier.print_receipt_aria')}>
                          <Receipt size={14} aria-hidden="true" /> {tI18n('cashier.print_receipt_btn')}
                        </button>
                      </div>
                    </details>
                  </td>
                </tr>
            ) :

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
      }
      </div>
  );
};

export default CashierHistoryTable;
