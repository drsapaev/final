/**
 * Registrar Panel — worklist view (appointments table page region).
 *
 * PR-UI-13-4: extracted verbatim from RegistrarPanel.tsx JSX — the worklist
 * section: workflow header (current worklist label + calendar date + counts +
 * status-filter badge + loading badge + new-appointment CTA), the three-state
 * content region (loading skeleton → QW-04 empty state / filtered-empty
 * state / EnhancedAppointmentsTable) and the load-more bar.
 *
 * Pure composition view: all state stays in the panel's hooks; row-action
 * routing is delegated to the panel via onActionClick.
 */
import EnhancedAppointmentsTable from '../../../components/tables/EnhancedAppointmentsTable';
import { Button, Badge, Icon } from '../../../components/ui/macos';
import { AnimatedLoader } from '../../../components/ui';
import logger from '../../../utils/logger';
import { formatRegistrarDate } from '../../../utils/dateUtils';
import type { WorklistPaginationInfo } from '../useRegistrarWorklistData';

interface WorklistViewProps {
  // presentation inputs
  activeTab: string | null;
  currentWorklistLabel: string;
  statusFilterLabel: string | null;
  showCalendar: boolean;
  historyDate: string;
  /** Full i18n language code (e.g. 'ru-RU' vs 'uz-Latn' decides date format). */
  language: string | undefined;
  legacyLanguage: string;
  isMobile: boolean;
  theme?: string;
  services: Record<string, unknown>;
  filteredAppointments: Record<string, unknown>[];
  appointmentsLoading: boolean;
  dataSource: string;
  paginationInfo: WorklistPaginationInfo;
  // callbacks
  onActionClick: (action: string, row: Record<string, unknown>, event?: unknown) => void | Promise<void>;
  loadMoreAppointments: () => void | Promise<void>;
  /** New-appointment CTA (panel replays the original three-setter sequence). */
  onNewAppointment: () => void;
  /** Empty-state CTA (original: setShowWizard(true)). */
  onEmptyStateCta: () => void;
  tI18n: (key: string, options?: Record<string, unknown>) => string;
}

const WorklistView = ({
  activeTab,
  currentWorklistLabel,
  statusFilterLabel,
  showCalendar,
  historyDate,
  language,
  legacyLanguage,
  isMobile,
  theme,
  services,
  filteredAppointments,
  appointmentsLoading,
  dataSource,
  paginationInfo,
  onActionClick,
  loadMoreAppointments,
  onNewAppointment,
  onEmptyStateCta,
  tI18n,
}: WorklistViewProps) => (
  <div
    id="main-content"
    role="tabpanel"
    aria-labelledby={activeTab ? `${activeTab}-tab` : undefined}
    className="registrar-table-container"
    data-breakpoint={isMobile ? 'mobile' : 'desktop'}>
    <div
      className="registrar-table-content"
      data-breakpoint={isMobile ? 'mobile' : 'desktop'}>

      <div
        className="registrar-workflow-header"
        aria-label={tI18n('registrarPanel.rp_aria_worklist_summary')}>
        <div className="registrar-worklist-container">
          <div className="registrar-worklist-meta">
            {tI18n('registrarPanel.rp_worklist_root')}
          </div>
          <h2 className="registrar-workflow-title">
            {tI18n('registrarPanel.rp_worklist_title', { label: currentWorklistLabel })}
          </h2>
          <p className="registrar-workflow-meta">
            {showCalendar ?
            // PR-13: use formatRegistrarDate to avoid browser-local timezone issues
            // historyDate is YYYY-MM-DD (Tashkent), parse as Tashkent midnight
            formatRegistrarDate(`${historyDate}T00:00:00+05:00`, language?.startsWith('ru') ? 'ru-RU' : 'uz-UZ') :
            tI18n('registrarPanel.today')} · {filteredAppointments.length} {tI18n('registrarPanel.tabs_appointments')}
          </p>
        </div>

        <div className="registrar-workflow-actions">
          {statusFilterLabel &&
          <Badge variant="warning" className="registrar-inline-flex-tight">
              <Icon name="magnifyingglass" size="small" />
              {tI18n('registrarPanel.rp_worklist_filter', { label: statusFilterLabel })}
            </Badge>
          }
          <Badge variant={appointmentsLoading ? 'info' : 'secondary'}>
            {appointmentsLoading ? tI18n('registrarPanel.loading') : `${filteredAppointments.length} ${tI18n('registrarPanel.tabs_appointments')}`}
          </Badge>
          <Button
          variant="primary"
          size="default"
          onClick={onNewAppointment}
          aria-label={tI18n('registrarPanel.rp_aria_new_appointment')}
          className="registrar-inline-flex registrar-inline-flex-shrink">
            <Icon name="plus" size="small" style={{ color: 'white' }} />
            {tI18n('registrarPanel.new_appointment')}
          </Button>
        </div>
      </div>

      {/* QW-01 fix: bulk-action bar removed (was dead UI) */}

      {/* Таблица записей */}
      {appointmentsLoading ?
    <AnimatedLoader.TableSkeleton rows={8} columns={10} /> :
    filteredAppointments.length === 0 && dataSource === 'api' ?
    <div className="registrar-empty-state">
          <div className="registrar-empty-icon-lg">
            {/* QW-04: empty state 2 of 3 (worklist empty). */}
            <Icon name="doc.text" size="large" />
          </div>
          <h3 className="registrar-empty-heading registrar-empty-heading-text">
            {tI18n('registrarPanel.rp_empty_queue_title')}
          </h3>
          <p className="registrar-empty-desc-text registrar-empty-desc-fixed">
            {activeTab ?
        tI18n('registrarPanel.rp_empty_queue_dept', { dept: activeTab === 'cardio' ? tI18n('registrarPanel.rp_dept_cardio') : activeTab === 'derma' ? tI18n('registrarPanel.rp_dept_derma') : activeTab === 'dental' ? tI18n('registrarPanel.rp_dept_dental') : activeTab === 'lab' ? tI18n('registrarPanel.rp_dept_lab') : activeTab }) :
        tI18n('registrarPanel.rp_empty_queue_general')}
          </p>
          <Button
        variant="primary"
        onClick={onEmptyStateCta}
        className="registrar-btn-cta">

            <Icon name="plus" size="small" style={{ marginRight: 'var(--mac-spacing-2)' }} />{tI18n('registrarPanel.rp_empty_queue_cta')}
          </Button>
        </div> :
    filteredAppointments.length === 0 ?
    <div className="registrar-empty-state">
          {/* UX Audit R-4.2: unified empty state pattern — иконка + заголовок + описание + кнопка. */}
          <div className="registrar-empty-icon-lg">
            <Icon name="magnifyingglass" size="large" />
          </div>
          <h3 className="registrar-empty-heading registrar-empty-heading-text">
            {tI18n('registrarPanel.empty_table')}
          </h3>
          <p className="registrar-empty-desc-text registrar-empty-desc-fixed">
            {tI18n('registrarPanel.rp_empty_filter_desc')}
          </p>
        </div> :

    <EnhancedAppointmentsTable
      data={filteredAppointments as unknown as NonNullable<Parameters<typeof EnhancedAppointmentsTable>[0]['data']>}
      loading={appointmentsLoading}
      theme={theme}
      language={legacyLanguage}
      outerBorder={false}
      services={services}
      showCheckboxes={false} // UX Audit R-4.7: bulk-action UI удалён (QW-01 fix),
                            // поэтому чекбоксы отключены — они были dead UI
                            // (видны, но ничего не делают). Nielsen #2 + #4.
      onRowClick={(row: unknown) => {
        logger.info('Открыть детали записи:', row);
        // Здесь можно открыть модальное окно с деталями записи
      }}
      onActionClick={onActionClick} />

    }

      {/* Кнопка загрузки дополнительных записей */}
      {paginationInfo.hasMore &&
    <div className="registrar-load-more-bar">
          <button
        onClick={loadMoreAppointments}
        disabled={paginationInfo.loadingMore}
        aria-label={paginationInfo.loadingMore ? 'Loading more appointments' : 'Load more appointments'}
        className={`registrar-btn-base ${paginationInfo.loadingMore ? 'registrar-btn-neutral' : 'registrar-btn-accent'} registrar-load-more-btn`} style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}
        aria-disabled={paginationInfo.loadingMore}>

            {paginationInfo.loadingMore ?
        <>
                <div className="registrar-spinner" />
                {tI18n('registrarPanel.rp_loading_more')}
              </> :

        <>
                <Icon name="arrow.up.arrow.down" size="small" style={{ marginRight: 'var(--mac-spacing-2)' }} />{tI18n('registrarPanel.rp_load_more')}
              </>
        }
          </button>
        </div>
    }

      {/* Старая таблица и прежняя конфигурация удалены - используется EnhancedAppointmentsTable */}
    </div>
  </div>
);

export default WorklistView;
