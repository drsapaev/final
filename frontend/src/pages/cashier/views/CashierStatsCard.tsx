/**
 * PR-UI-14-5: cashier stats card + action toolbar (verbatim JSX move from
 * CashierPanel).
 *
 * UX Audit #3.1 + #3.2: stats-card now contains ONLY metrics; the
 * Refresh/Export/Analytics buttons live in a separate toolbar above the
 * tabs (Nielsen #8 — aesthetic and minimalist design + IA separation).
 */

import { Card, Button } from '../../../components/ui/macos';
import { formatUZS } from '../../../utils/formatCurrency';
import type { CashierStatsSnapshot } from '../useCashierWorklistData';
import type { CashierTranslationFn } from '../cashierPaymentContracts';

interface CashierStatsCardProps {
  /** Metrics switch shape by tab (history shows the full grid). */
  isHistoryTab: boolean;
  stats: CashierStatsSnapshot;
  onRefresh: () => void;
  onExport: () => void;
  onHourlyStats: () => void;
  tI18n: CashierTranslationFn;
}

/**
 * CSH-FE-036 P2 (PR 3830 review, comment 4439005298): a MISSING stats
 * field is not a zero. On a rolling frontend/backend deploy this frontend
 * may be served by an older /cashier/stats without refunded_amount /
 * net_* — formatUZS(undefined) would render a fake «0 сум» that
 * misreports real receipts. An absent value renders as «—» (no data);
 * a real zero reported by the current API still renders as «0 сум».
 */
const formatMoneyOrDash = (value: number | undefined | null): string =>
  typeof value === 'number' && Number.isFinite(value) ? formatUZS(value) : '—';

const CashierStatsCard = ({ isHistoryTab, stats, onRefresh, onExport, onHourlyStats, tI18n }: CashierStatsCardProps) => {
  const format = formatUZS;

  return (
    <>
      {/* ✅ УЛУЧШЕНИЕ: Статистика платежей из API */}
      {/* UX Audit #3.1 + #3.2: stats-card теперь содержит ТОЛЬКО метрики.
          Кнопки «Обновить/Экспорт/Аналитика» вынесены в отдельный toolbar над табами —
          Nielsen #8 (эстетический и минималистичный дизайн) + IA-разделение.
          Скрытые плитки (visibility:hidden) удалены — визуальный шум устранён. */}
      <Card variant="outlined" className="cashier-stats-card">
        <div className="cashier-stats-grid">
          {isHistoryTab ?
          <>
              <div className="cashier-text-center">
                <div className="cashier-stat-num cashier-stat-accent">
                  {format(stats.total_amount)}
                </div>
                <div className="cashier-stat-cap">
                  {tI18n('cashier.total_period')}
                </div>
              </div>
              <div className="cashier-text-center">
                <div className="cashier-stat-num cashier-stat-green">
                  {format(stats.cash_amount)}
                </div>
                <div className="cashier-stat-cap">
                  {tI18n('cashier.method_cash')}
                </div>
              </div>
              <div className="cashier-text-center">
                <div className="cashier-stat-num cashier-stat-blue">
                  {format(stats.card_amount)}
                </div>
                <div className="cashier-stat-cap">
                  {tI18n('cashier.method_card')}
                </div>
              </div>
              {/* CSH-FE-036 (PR 3813 follow-up): обе финансовые величины —
                  возвраты и поступления за вычетом возвратов — рядом с
                  валовыми; смысл существующих плиток не меняется молча.
                  P2 (4439005298): отсутствующее поле ≠ ноль — старый API
                  без net-полей получает «—», а не ложный «0 сум». */}
              <div className="cashier-text-center">
                <div className="cashier-stat-num cashier-stat-danger">
                  {formatMoneyOrDash(stats.refunded_amount)}
                </div>
                <div className="cashier-stat-cap">
                  {tI18n('cashier.refunded_total')}
                </div>
              </div>
              <div className="cashier-text-center">
                <div className="cashier-stat-num cashier-stat-green">
                  {formatMoneyOrDash(stats.net_total_amount)}
                </div>
                <div className="cashier-stat-cap">
                  {tI18n('cashier.net_total')}
                </div>
              </div>
              <div className="cashier-text-center">
                <div className="cashier-stat-num cashier-stat-purple">
                  {stats.paid_count}
                </div>
                <div className="cashier-stat-cap">
                  {tI18n('cashier.status_paid')}
                </div>
              </div>
              {stats.cancelled_count > 0 &&
            <div className="cashier-text-center">
                  <div className="cashier-stat-num cashier-stat-danger">
                    {stats.cancelled_count}
                  </div>
                  <div className="cashier-stat-cap">
                    {tI18n('cashier.cancelled_count')}
                  </div>
                </div>
            }
            </> :

          <>
          <div className="cashier-text-center">
              <div className="cashier-stat-num-lg cashier-stat-orange">
                {format(stats.pending_amount || 0)}
              </div>
              <div className="cashier-stat-cap-base">
                {tI18n('cashier.pending_count_caption', { count: stats.pending_count })}
              </div>
            </div>
          </>
          }
        </div>
      </Card>

      {/* UX Audit #3.1: отдельный toolbar для действий над списком. */}
      <div className="cashier-toolbar">
        <div className="cashier-toolbar-actions">
          <Button
            size="small"
            variant="outline"
            onClick={onRefresh}
            title={tI18n('cashier.refresh_title')}>

            {tI18n('cashier.refresh_btn')}
          </Button>
          <Button
            size="small"
            variant="outline"
            onClick={onExport}
            title={tI18n('cashier.export_title')}>

            {tI18n('cashier.export_btn')}
          </Button>
          <Button
            size="small"
            variant="outline"
            onClick={onHourlyStats}
            title={tI18n('cashier.hourly_stats_title')}>

            {tI18n('cashier.analytics_btn')}
          </Button>
        </div>
      </div>
    </>
  );
};

export default CashierStatsCard;
