/**
 * EnhancedAppointmentsTable — orchestrator (PR-UI-09e-2 decomposition).
 *
 * Public contract unchanged: default export + AppointmentRow re-export
 * (6 consumers: Appointments.tsx, Dentist/Dermatologist panels, registrar
 * WorklistView/WelcomeView). Implementation extracted to:
 *   - appointmentsTableContracts.ts     — types, constants, pure helpers
 *   - useAppointmentsTableState.ts      — state, memos, selection handlers
 *   - appointmentsTableColumns.tsx      — renderers + canonical DataTable columns
 */

import { useCallback } from 'react';
import { Search, Download } from 'lucide-react';
import { Input, Button, Badge, Select } from '../ui/macos';
import type { SelectChangeEvent } from '../ui/macos/Select';
import { DataTable } from '../ui/DataTable';
import './EnhancedAppointmentsTable.css';
import { generateCSV, downloadCSV } from '../../pages/registrar/registrarCsv';
import { getLocalDateString } from '../../utils/dateUtils';
import type { Appointment } from '../../types/domain/clinic';
import { useTranslation } from '../../i18n/useTranslation';
import {
  type AppointmentRow,
  type EnhancedAppointmentsTableProps,
  formatPhoneNumber,
  getDisplayAmount,
  getEnhancedAppointmentRowKey,
} from './appointmentsTableContracts';
import { useAppointmentsTableState } from './useAppointmentsTableState';
import { useAppointmentsTableRenderers, buildAppointmentsTableColumns } from './appointmentsTableColumns';

/**
 * PR-UI-12-4: bounded scroll-viewport height (px) for the EAT table body.
 *
 * Layout parameter for the sticky-header viewport (see the DataTable
 * "Sticky header viewport" doc note) — NOT a sticky offset; the kit measures
 * header/filter row offsets itself. 560px ≈ 10 visible EAT rows (~52px per
 * row incl. borders): full 20-row pages scroll internally under the sticky
 * column header (sort controls stay reachable), while lists that fit within
 * the bound render pixel-identically to the unbounded table.
 */
const EAT_TABLE_VIEWPORT_MAX_HEIGHT = 560;

const EnhancedAppointmentsTable = ({
  data = [],
  loading = false,
  onRowClick,
  onActionClick,
  theme = 'light',
  language = 'ru',
  selectedRows: externalSelectedRows,
  onRowSelect,
  services = {},
  outerBorder = true,
  showCheckboxes = true,
  view = 'registrar'
}: EnhancedAppointmentsTableProps): React.JSX.Element | null => {
  const {
    containerRef,
    filterConfig,
    setFilterConfig,
    currentPage,
    setCurrentPage,
    filteredData,
    paginatedData,
    totalPages,
    selectedRows,
    handleSort,
    handleRowSelect,
    handleSelectAll,
  } = useAppointmentsTableState({ data, externalSelectedRows, onRowSelect });

  const isDark = theme === 'dark';
  const isDoctorView = String(view).toLowerCase() === 'doctor';

  // Переводы — i18next unified.
  const { t: rawT } = useTranslation();
  const t = rawT;
  void language; // legacy prop, kept for backward compat; translations come from i18next.

  const {
    renderStatus,
    renderServices,
    renderVisitType,
    renderPaymentType,
    renderQueueNumbers,
  } = useAppointmentsTableRenderers({ t, services, data });

  // Экспорт данных
  // UX Audit R-3.1: используем единую generateCSV из registrarCsv.js с PHI masking.
  // Раньше: inline handleExport с formatPhoneNumber (БЕЗ маски) — PHI leak.
  // Теперь: единая функция с maskPhone=true по умолчанию + опции для extra columns.
  const handleExport = useCallback(() => {
    const csvContent = generateCSV(filteredData, {
      maskPhone: true, // R-05 fix: всегда маскируем телефон в CSV-экспорте
      includeAddress: !isDoctorView, // адрес только для registrar view
      includeTimestamps: true, // дата/время/изменено
    });
    const filename = `appointments_${getLocalDateString()}.csv`;
    downloadCSV(csvContent, filename);
  }, [filteredData, isDoctorView]);

  // Преждевременный возврат перенесён ниже, чтобы не нарушать порядок хуков
  // Инлайновый лоадер без раннего возврата
  const loaderNode =
  <div className="eat-loader">
      <div className="eat-td">
        <div
        className="loading-spinner eat-loader-spinner" />
        {t('misc.eat_loading')}
      </div>
    </div>;

  const columns = buildAppointmentsTableColumns({
    t,
    isDoctorView,
    showCheckboxes,
    selectedRows,
    paginatedData,
    handleRowSelect,
    handleSelectAll,
    onActionClick,
    renderStatus,
    renderServices,
    renderVisitType,
    renderPaymentType,
    renderQueueNumbers,
    formatPhoneNumber,
    getDisplayAmount,
  });

  return (
    <div
      ref={containerRef}
      className={`enhanced-table ${isDark ? 'dark-theme' : ''}`}
      style={{
        overflow: 'hidden',
        border: outerBorder ? '1px solid var(--mac-border)' : 'none',
        borderRadius: outerBorder ? 'var(--mac-radius-lg)' : '0'
      }}>
      
      <div className="eat-toolbar">
        <div className="eat-toolbar-inner">
          
          <div className="eat-search-input-wrap">
            <Input
              type="text"
              placeholder={t('misc.eat_search')}
              value={filterConfig.search}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFilterConfig((prev) => ({ ...prev, search: e.target.value }))}
              icon={Search}
              className="eat-search-input" />

          </div>

          
          <Select
            value={filterConfig.status}
            onChange={(e: SelectChangeEvent) => setFilterConfig((prev) => ({ ...prev, status: e.target.value }))}
            options={[
            { value: '', label: t('misc.eat_filter') },
            { value: 'scheduled', label: t('misc.eat_scheduled') },
            { value: 'confirmed', label: t('misc.eat_confirmed') },
            { value: 'queued', label: t('misc.eat_queued') },
            { value: 'in_cabinet', label: t('misc.eat_in_cabinet') },
            { value: 'done', label: t('misc.eat_done') },
            { value: 'cancelled', label: t('misc.eat_cancelled') },
            { value: 'paid_pending', label: t('misc.eat_paid_pending') },
            { value: 'paid', label: t('misc.eat_payment_paid') }]
            }
            className="eat-filter-select" />


          
          <Button
            variant="outline"
            onClick={handleExport}
            className="eat-export-btn">

            <Download size={16} />
            {t('misc.eat_export')}
          </Button>

          
          {showCheckboxes && selectedRows.size > 0 &&
          <Badge variant="info">
              {t('misc.eat_selected')}: {selectedRows.size}
            </Badge>
          }
        </div>
      </div>

      
      {loading ? loaderNode : null}
      <div className="eat-table-scroll" aria-busy={loading} aria-live="polite">
        <div className="admin-table-wrapper">
          {/* PR-UI-09c-4: canonical DataTable replaces the bespoke native <table>.
              Sorting stays parent-owned: DataTable is a view — it renders rows in
              the given order and delegates header clicks via onSort, so EAT's
              sortedData/filteredData/paginatedData memos and handleSort
              semantics are preserved bit-for-bit. Selection stays explicit via
              the checkbox column (row click keeps onRowClick semantics). */}
          <DataTable
            columns={columns}
            data={paginatedData}
            getRowId={(row: AppointmentRow, index: number) => getEnhancedAppointmentRowKey(row as unknown as Appointment, index)}
            // PR-UI-12-4 (plan §PR-UI-12 item 4 "sticky header при скролле"):
            // sticky header + bounded scroll viewport. Layout parameter only
            // (NOT a sticky offset — the kit measures header/filter offsets):
            // 560px ≈ 10 visible EAT rows, so full 20-row pages scroll
            // internally with the column header (sort controls included)
            // staying visible, while EAT's own pagination below the viewport
            // stays reachable without scrolling the whole page. Pages of ~10
            // rows or fewer render pixel-identically to the unbounded table.
            stickyHeader
            maxHeight={EAT_TABLE_VIEWPORT_MAX_HEIGHT}
            // Codex P2 fix (09c-4): only wire row activation when the consumer
            // supplied onRowClick — a truthy no-op wrapper would give every row
            // tabIndex=0 + Enter/Space activation (misleading keyboard focus
            // stops for consumers like Appointments.tsx that pass no handler).
            onRowClick={onRowClick ? (row: AppointmentRow) => onRowClick(row as unknown as AppointmentRow) : undefined}
            onSort={(key: string) => handleSort(key)}
            emptyState={t('misc.eat_no_data')}
            striped
            hoverable={false}
            variant="minimal"
            className="eat-table-container"
            style={{ minWidth: isDoctorView ? '100%' : '1400px', tableLayout: 'auto' }}
          />
        </div>
      </div>

      
      {totalPages > 1 &&
      <div className="eat-pagination">
          <div className="eat-pagination-info">
            <span>{t('misc.eat_page')}</span>
            <select
            value={currentPage}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setCurrentPage(parseInt(e.target.value))}
            className="eat-pagination-select">

              {Array.from({ length: totalPages }, (_, i) =>
            <option key={i + 1} value={i + 1}>
                  {i + 1}
                </option>
            )}
            </select>
            <span>{t('misc.eat_of')} {totalPages}</span>
          </div>

          <div className="eat-pagination-info">
            <span>{t('misc.eat_shown_of', { shown: paginatedData.length, total: filteredData.length })}</span>
          </div>

          <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <button
            className="pagination-button"
            onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
            disabled={currentPage === 1}
            style={{
              padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-sm)',
              backgroundColor: 'var(--mac-bg-primary)',
              color: currentPage === 1 ? 'var(--mac-text-secondary)' : 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-base)',
              cursor: currentPage === 1 ? 'not-allowed' : 'pointer'
            }}>

              {t('misc.eat_back')}
            </button>
            <button
            className="pagination-button"
            onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
            disabled={currentPage === totalPages}
            style={{
              padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-sm)',
              backgroundColor: 'var(--mac-bg-primary)',
              color: currentPage === totalPages ? 'var(--mac-text-secondary)' : 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-base)',
              cursor: currentPage === totalPages ? 'not-allowed' : 'pointer'
            }}>

              {t('misc.eat_next')}
            </button>
          </div>
        </div>
      }

    </div>);

};

// audit/strict: removed self-referencing propTypes spread

export default EnhancedAppointmentsTable;
export type { AppointmentRow } from './appointmentsTableContracts';
