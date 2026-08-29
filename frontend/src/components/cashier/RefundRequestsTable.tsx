
import { useTranslation } from '../../i18n/useTranslation';
/**
 * RefundRequestsTable - Table for managing refund requests
 *
 * Features:
 * - Display pending, approved, rejected refund requests
 * - Approve/Reject actions for pending requests
 * - Complete action for approved requests
 *
 * PR-UI-14-6 decomposition (behavior-preserving): contracts + fail-closed
 * guards → ./refundRequestsContracts.ts; data lifecycle + process actions
 * → ./useRefundRequests.ts; badges/formatters/actions/columns →
 * ./refundRequestsColumns.tsx. Renders via the canonical DataTable
 * (PR-UI-09). Plan §PR-UI-14 AC: ≤150 LOC.
 */
import { DollarSign } from 'lucide-react';
import {
  AppEmpty, AppError, AppLoading, Badge, Button, Select,
} from '../ui/macos';
import { DataTable } from '../ui/DataTable';
// UX Audit #3.4: inline-стили перенесены в CSS-классы.
import './RefundRequestsTable.css';
import {
  getRefundFilterOptions,
  type RefundRequestsTableProps,
  type RefundTranslationFn,
} from './refundRequestsContracts';
import { useRefundRequests } from './useRefundRequests';
import { buildRefundRequestColumns } from './refundRequestsColumns';

const RefundRequestsTable = ({ onRefresh }: RefundRequestsTableProps) => {
  const { t: rawT } = useTranslation(); const t = rawT as RefundTranslationFn;
  const {
    requests, loading, error, processingId,
    filter, setFilter, loadRequests,
    handleApprove, handleReject, handleComplete,
  } = useRefundRequests(t, onRefresh);

  const columns = buildRefundRequestColumns(t, processingId, { handleApprove, handleReject, handleComplete });

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
