/**
 * PR-UI-14-5: cashier pending-payments table (verbatim JSX move from
 * CashierPanel — skeleton rows, appointment rows, pagination, actionable
 * empty state).
 *
 * UX Audit #4.4: skeleton rows inside tbody keep the table headers.
 * UX Audit #4.3: actionable empty state instead of bare text.
 */

import { CheckCircle } from 'lucide-react';

import { Badge, Button, Skeleton } from '../../../components/ui/macos';
import { formatUZS } from '../../../utils/formatCurrency';
import { formatRegistrarDate, formatRegistrarTime } from '../../../utils/dateUtils';
import type { Appointment } from '../../../types/domain/clinic';
import {
  canCreateCashierPayment,
  canCreateDirectCashierPayment,
  isBackendGroupedCashierPayment,
  type CashierTranslationFn,
} from '../cashierPaymentContracts';
import CashierServiceBadges from './CashierServiceBadges';

interface CashierPendingTableProps {
  appointments: Appointment[];
  pendingLoading: boolean;
  pendingPage: number;
  onPendingPageChange: (updater: (p: number) => number) => void;
  pendingTotalPages: number;
  pendingTotalItems: number;
  /** Verbatim handler name — keeps the moved JSX byte-identical
   * (contract-test pins reference this identifier). */
  openPaymentWidget: (appointment: Appointment) => void;
  onOpenCashPaymentModal: (appointment: Appointment) => void;
  onOpenHistory: () => void;
  tI18n: CashierTranslationFn;
}

const CashierPendingTable = ({
  appointments,
  pendingLoading,
  pendingPage,
  onPendingPageChange,
  pendingTotalPages,
  pendingTotalItems,
  openPaymentWidget,
  onOpenCashPaymentModal,
  onOpenHistory,
  tI18n,
}: CashierPendingTableProps) => {
  const format = formatUZS;

  return (
    <div className="cashier-section-gap">
      {pendingLoading ?
      (/* UX Audit #4.4: skeleton rows внутри tbody сохраняют заголовки таблицы. */
      <div className="cashier-table-scroll">
        <table className="cashier-table">
          <thead>
            <tr className="cashier-table-row">
              <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_date_time')}</th>
              <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_patient')}</th>
              <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_services')}</th>
              <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_amount')}</th>
              <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_status')}</th>
              <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_actions')}</th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, i) => (
              <tr key={`skeleton-pending-${i}`} className="cashier-table-row">
                {Array.from({ length: 6 }).map((_, j) => (
                  <td key={j} className="cashier-cell-padded"><Skeleton height={20} /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      ) :
      appointments.length > 0 ?
      <div className="cashier-table-scroll">
            <table className="cashier-table">
              <thead>
                <tr className="cashier-table-row">
                  <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_date_time')}</th>
                  <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_patient')}</th>
                  <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_services')}</th>
                  <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_amount')}</th>
                  <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_status')}</th>
                  <th className="cashier-text-sm cashier-text-primary">{tI18n('cashier.col_actions')}</th>
                </tr>
              </thead>
              <tbody>
                {appointments.map((appointment, index) =>
            <tr
              key={`${appointment.record_type || 'appointment'}-${appointment.id || index}-${Array.isArray(appointment.visit_ids) ? (appointment.visit_ids as unknown[]).join('-') : ''}`}
              className="cashier-table-row">

                  <td
                    aria-label={tI18n('cashier.appointment_date_aria')}
                    className="cashier-text-sm cashier-text-primary">
                    <div className="cashier-date-stack">
                      <span className="cashier-date-main">
                        {appointment.created_at ?
                    formatRegistrarDate(appointment.created_at) :
                    appointment.appointment_date || '—'
                    }
                      </span>
                      <span className="cashier-date-sub">
                        {appointment.created_at ?
                    formatRegistrarTime(appointment.created_at) :
                    appointment.appointment_time || '—'
                    }
                      </span>
                    </div>
                  </td>
                  <td className="cashier-text-sm cashier-text-primary">
                    {appointment.patient_last_name && appointment.patient_first_name ?
              `${appointment.patient_last_name} ${appointment.patient_first_name}` :
              appointment.patient_name || tI18n('cashier.patient_with_id', { id: appointment.patient_id })
              }
                    {/* UX Audit #2.6: badge «Групповой» для grouped-платежей,
                        чтобы было видно, почему кнопка «Онлайн» дизейблится. */}
                    {isBackendGroupedCashierPayment(appointment) && (
                      <span className="cashier-badge cashier-badge-grouped" title={tI18n('cashier.grouped_payment_title')}>
                        {tI18n('cashier.grouped_badge')}
                      </span>
                    )}
                  </td>
                  <td className="cashier-text-sm cashier-text-primary">
                    <CashierServiceBadges serviceCodes={appointment.services} serviceNames={appointment.services_names} tI18n={tI18n} />
                  </td>
                  <td className="cashier-text-sm cashier-text-accent">
                    {format(Number(appointment.total_amount || appointment.remaining_amount || appointment.payment_amount || 0))}
                  </td>
                  <td className="cashier-cell-padded">
                    <Badge
                      variant="warning"
                      role="status"
                      aria-label={tI18n('cashier.status_pending_aria')}>
                      {tI18n('cashier.pending_payment_badge')}
                    </Badge>
                  </td>
                  <td className="cashier-cell-padded">
                    <div className="cashier-refresh-row">
                      <Button
                  size="small"
                  variant="outline"
                  onClick={() => openPaymentWidget(appointment)}
                  disabled={!canCreateDirectCashierPayment(appointment) || isBackendGroupedCashierPayment(appointment)}
                  aria-label={tI18n('cashier.start_online_payment_aria')}
                  title={!canCreateDirectCashierPayment(appointment) || isBackendGroupedCashierPayment(appointment)
                    ? tI18n('cashier.online_payment_disabled_title')
                    : tI18n('cashier.online_payment_enabled_title')}>

                        {tI18n('cashier.online_btn')}
                      </Button>
                      <Button
                  size="small"
                  onClick={() => {
                    onOpenCashPaymentModal(appointment);
                  }}
                  disabled={!canCreateCashierPayment(appointment)}
                  aria-label={tI18n('cashier.cash_payment_aria')}
                  title={!canCreateCashierPayment(appointment) ? tI18n('cashier.cash_payment_disabled_title') : tI18n('cashier.cash_payment_aria')}>

                        {tI18n('cashier.cash_btn')}
                      </Button>
                    </div>
                  </td>
                </tr>
            )}
              </tbody>
            </table>

            {/* ✅ v2.0: Пагинация для ожидающих оплаты */}
            {pendingTotalPages > 1 &&
        <div className="cashier-pagination">
                <Button
            size="small"
            variant="outline"
            disabled={pendingPage === 1 || pendingLoading}
            onClick={() => onPendingPageChange((p) => Math.max(1, p - 1))}>

                  {tI18n('cashier.prev_page')}
                </Button>
                <span className="cashier-pagination-info">
                  {tI18n('cashier.pagination_info', { current: pendingPage, total: pendingTotalPages, total_items: pendingTotalItems })}
                </span>
                <Button
            size="small"
            variant="outline"
            disabled={pendingPage === pendingTotalPages || pendingLoading}
            onClick={() => onPendingPageChange((p) => Math.min(pendingTotalPages, p + 1))}>

                  {tI18n('cashier.next_page')}
                </Button>
              </div>
        }
          </div> :

      (/* UX Audit #4.3: actionable empty state вместо голого текста. */
      <div className="cashier-empty-state" role="status">
        <CheckCircle size={32} className="cashier-empty-state-icon" aria-hidden="true" />
        <div className="cashier-empty-state-title">{tI18n('cashier.empty_pending_title')}</div>
        <div className="cashier-empty-state-text">
          {tI18n('cashier.empty_pending_text')}
        </div>
        <Button size="small" variant="outline" onClick={onOpenHistory}>
          {tI18n('cashier.open_history_btn')}
        </Button>
      </div>
      )}
      </div>
  );
};

export default CashierPendingTable;
