import React, { useId } from 'react';
import { Button, Card, CardHeader, CardContent, Badge, Input } from '@/components/ui/macos';
import EnhancedAppointmentsTable from '@/components/tables/EnhancedAppointmentsTable';
import { getLocalDateString, parseRegistrarTimestamp, REGISTRAR_TIME_ZONE } from '@/utils/dateUtils';
import logger from '@/utils/logger';
import notify from '@/services/notify';
import tokenManager from '@/utils/tokenManager';
import { Bell, Calendar, CreditCard, Plus, RotateCw, Search } from 'lucide-react';
import type { RegistrarWorklistLoadOutcome } from '../useRegistrarWorklistData';

// === REG-FE-032 (registrar audit ledger): clinic-timezone date labels ===
// A date-only history value IS a Tashkent calendar day; rendering it through
// the browser's local zone re-based UTC-midnight into the previous day for
// UTC-negative operators. Both helpers pin the display zone to the clinic.
export const formatClinicDayLong = (isoDay: string, locale: string): string => {
  const parsed = parseRegistrarTimestamp(isoDay);
  return parsed
    ? parsed.toLocaleDateString(locale, {
      day: 'numeric', month: 'long', year: 'numeric', timeZone: REGISTRAR_TIME_ZONE,
    })
    : isoDay;
};

export const formatClinicTodayLong = (locale: string, now: Date = new Date()): string =>
  now.toLocaleDateString(locale, {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', timeZone: REGISTRAR_TIME_ZONE,
  });

// === Domain types ===
// WelcomeView is a registrar-facing dashboard. Most state lives in the
// parent (RegistrarPanel); WelcomeView receives props and renders.
// Function signatures mirror the parent's setter / callback types.

interface ContextMenuPosition { x: number; y: number; }
interface ContextMenuState { open: boolean; row: unknown; position: ContextMenuPosition; }
interface PaymentDialogState { open: boolean; row: unknown; paid: boolean; source: unknown; }
interface PrintDialogState { open: boolean; type: string; data: unknown; }

interface WelcomeViewDataSourceIndicatorProps {
  count?: number;
  [key: string]: unknown;
}

interface WelcomeViewDataSourceIndicator {
  (props: WelcomeViewDataSourceIndicatorProps): React.JSX.Element;
}

export interface WelcomeViewProps {
  // i18n + theming
  t: (key: string, options?: Record<string, unknown>) => string;
  language: string;
  theme: string;
  // Data — appointment shape is dynamic; component reads arbitrary fields.
  appointments: Record<string, unknown>[];
  dataSource: string;
  appointmentsLoading: boolean;
  filteredAppointments: Record<string, unknown>[];
  services: Record<string, unknown>;
  // Filters
  today: string;
  selectedDate: string;
  loadedDate: string | null;
  stale: boolean;
  hasUrlFilters: boolean;
  showCalendar: boolean;
  // Action: data load — accepts an options object per caller convention.
  // REG-FE-008: the shared hook resolves a typed outcome so callers can
  // reward only a verified refresh; void stays valid for stub/legacy callers.
  loadAppointments: (options?: unknown) => void | Promise<RegistrarWorklistLoadOutcome | void>;
  // Action: wizard
  setShowWizard: (open: boolean) => void;
  setWizardEditMode: (edit: boolean) => void;
  setWizardInitialData: (data: Record<string, unknown> | null) => void;
  // Action: payment manager
  setShowPaymentManager: (open: boolean) => void;
  // Action: filter changes
  setShowCalendar: (open: boolean) => void;
  // Action: URL search params — react-router's SetURLSearchParams signature
  // (accepts URLSearchParams, plain object, or updater function).
  setSearchParams: (
    next:
      | URLSearchParams
      | Record<string, string>
      | ((prev: URLSearchParams) => URLSearchParams),
    options?: { replace?: boolean }
  ) => void;
  // Action: navigation
  navigate: (path: string, options?: { replace?: boolean; state?: unknown }) => void;
  // Action: dialogs
  setPaymentDialog: React.Dispatch<React.SetStateAction<PaymentDialogState>>;
  setPrintDialog: React.Dispatch<React.SetStateAction<PrintDialogState>>;
  setContextMenu: React.Dispatch<React.SetStateAction<ContextMenuState>>;
  // Action: records
  openRecordPreview: (row: unknown) => void;
  openRecordEditor: (row: unknown) => void;
  handleTableAction: (action: string, row: Record<string, unknown>, event?: unknown) => void | Promise<void>;
  handleStartVisit: (row: unknown) => void | Promise<void>;
  // Action: CSV — actual signatures come from registrarCsv.ts; loosened here.
  generateCSV: (rows: Record<string, unknown>[], options?: Record<string, unknown>) => string;
  downloadCSV: (content: string, filename: string) => void;
  // Memoized data-source badge component
  DataSourceIndicator: WelcomeViewDataSourceIndicator;
  // REG-FE-028: same SSOT scope fact the worklist uses — filters narrowing a
  // non-empty scope to zero rows must read as "no matches", not "empty queue".
  emptyScopeKind?: 'queue-empty' | 'filtered-empty';
}

const WelcomeView = React.memo(({
  t,
  language,
  theme,
  appointments,
  dataSource,
  appointmentsLoading,
  filteredAppointments,
  services,
  today,
  selectedDate,
  loadedDate,
  stale,
  hasUrlFilters,
  showCalendar,
  loadAppointments,
  setShowWizard,
  setWizardEditMode,
  setWizardInitialData,
  setShowPaymentManager,
  setShowCalendar,
  setSearchParams,
  navigate,
  setPaymentDialog,
  setPrintDialog,
  setContextMenu,
  openRecordPreview,
  openRecordEditor,
  handleTableAction,
  handleStartVisit,
  generateCSV,
  downloadCSV,
  DataSourceIndicator,
  emptyScopeKind = 'queue-empty',
}: WelcomeViewProps) => {
  const dateInputId = useId();
  const calendarId = useId();
  const locale = language === 'uz' ? 'uz-Latn' : language;
  const sessionExpired = dataSource === 'api' && !tokenManager.hasToken();
  const dateMatches = loadedDate === selectedDate;
  const canSummarize = dateMatches && dataSource === 'api' && !stale && !sessionExpired;
  const loadError = !appointmentsLoading && (dataSource === 'error' || (!dateMatches && stale));
  const loading = !sessionExpired && !loadError && (!dateMatches || appointmentsLoading || dataSource === 'loading');
  // Kept data is shown only under its own date, and cannot be exported until refreshed.
  const showRows = dateMatches && !sessionExpired && filteredAppointments.length > 0;
  const empty = canSummarize && !loading && !showRows;

  const createAppointment = () => {
    setWizardEditMode(false);
    setWizardInitialData(null);
    setShowWizard(true);
  };

  const selectDay = (day: string) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || day === selectedDate) return;
    setSearchParams(prev => {
      const params = new URLSearchParams(prev);
      if (day === today) params.delete('date');
      else params.set('date', day);
      return params;
    });
  };
  // Shift a clinic calendar day, not the operator's browser day (DST).
  const daysBeforeToday = (days: number) => {
    const calendarDay = new Date(`${today}T12:00:00Z`);
    calendarDay.setUTCDate(calendarDay.getUTCDate() - days);
    return getLocalDateString(calendarDay);
  };
  const clearNarrowingFilters = () => {
    setSearchParams(prev => {
      const params = new URLSearchParams(prev);
      params.delete('status');
      params.delete('q');
      return params;
    });
  };
  const refresh = async () => {
    const result = await loadAppointments({ source: 'manual_refresh_button' });
    if (result === 'loaded' || result === 'empty') notify.success(t('misc.data_updated'));
  };

  // These are counts of loaded queue records for the selected day, not
  // unique-patient or revenue totals. No comparison with an unqueried day.
  let waiting = 0;
  let pendingPayment = 0;
  let completed = 0;
  const ownerGroups = new Map<string, { name: string; patients: Set<string>; records: number; unlinked: boolean }>();
  if (canSummarize) {
    for (const row of appointments) {
      const status = row.canonical_status ?? row.status;
      if (status === 'waiting' || status === 'queued') waiting += 1;
      if (row.payment_status === 'pending' || status === 'paid_pending') pendingPayment += 1;
      if (status === 'done' || status === 'completed' || status === 'served') completed += 1;
      if (selectedDate !== today) continue;
      const ownerKind = typeof row.queue_owner_kind === 'string' ? row.queue_owner_kind : null;
      const ownerId = row.queue_owner_id;
      const key = ownerKind && ownerId != null ? `${ownerKind}:${ownerId}` : 'unowned';
      let group = ownerGroups.get(key);
      if (!group) {
        const queueName = typeof row.queue_name === 'string' ? row.queue_name : '';
        const name = key === 'unowned' ? t('rp_welcome_unassigned') :
          queueName || t(ownerKind === 'doctor' ? 'rp_welcome_doctor' : 'rp_welcome_queue', { id: ownerId });
        group = { name, patients: new Set(), records: 0, unlinked: false };
        ownerGroups.set(key, group);
      }
      group.records += 1;
      if (row.patient_id == null || row.patient_id === '') group.unlinked = true;
      else group.patients.add(String(row.patient_id));
    }
  }

  return (
    <Card variant="default" className="registrar-card-surface">
      <CardHeader className="registrar-card-header">
        <h1 className="registrar-hero-title">{t('rp_welcome_title')}</h1>
      </CardHeader>
      <CardContent>
        <div className="registrar-welcome-actions">
          <Button variant="primary" disabled={sessionExpired} onClick={createAppointment}>
            <Plus size={16} aria-hidden="true" />{t('new_appointment')}
          </Button>
          <Button variant="outline" onClick={() => navigate('/clinical/search')}>
            <Search size={16} aria-hidden="true" />{t('rp_welcome_find_patient')}
          </Button>
          <Button variant="outline" onClick={() => navigate('/registrar/queue')}>
            <Bell size={16} aria-hidden="true" />{t('rp_welcome_open_queue')}
          </Button>
        </div>

        <section aria-label={t('rp_welcome_day_tools')} className="registrar-welcome-section">
          <div className="registrar-welcome-toolbar">
            <Badge variant="secondary" className="registrar-badge-date">
              <Calendar size={16} aria-hidden="true" />
              <time dateTime={selectedDate}>{formatClinicDayLong(selectedDate, locale)}</time>
            </Badge>
            <Button variant="outline" aria-expanded={showCalendar} aria-controls={calendarId}
              onClick={() => setShowCalendar(!showCalendar)}>{t('rp_welcome_choose_day')}</Button>
            <Button variant="outline" onClick={() => void refresh()} disabled={loading || sessionExpired}>
              <RotateCw size={16} aria-hidden="true" />{t('rp_welcome_refresh')}
            </Button>
            <Button variant="outline" onClick={() => setShowPaymentManager(true)} disabled={sessionExpired}>
              <CreditCard size={16} aria-hidden="true" />{t('rp_welcome_payments')}
            </Button>
          </div>
          <div id={calendarId} hidden={!showCalendar}>
            {showCalendar && <form key={selectedDate} className="registrar-welcome-toolbar" onSubmit={event => {
              event.preventDefault();
              selectDay(String(new FormData(event.currentTarget).get('day') ?? ''));
            }}>
              <label htmlFor={dateInputId}>{t('rp_welcome_date_label')}</label>
              <Input id={dateInputId} type="date" name="day" required defaultValue={selectedDate} />
              <Button type="submit" variant="outline">{t('rp_welcome_apply_day')}</Button>
              <Button type="button" variant="outline" onClick={() => selectDay(today)}>{t('rp_welcome_today')}</Button>
              <Button type="button" variant="outline" onClick={() => selectDay(daysBeforeToday(1))}>{t('rp_welcome_yesterday')}</Button>
              <Button type="button" variant="outline" onClick={() => selectDay(daysBeforeToday(7))}>{t('rp_welcome_week_ago')}</Button>
            </form>}
          </div>
          {canSummarize && <div className="registrar-welcome-section">
            <h2 className="registrar-subsection-heading">{t('rp_welcome_day_counts')}</h2>
            <dl className="registrar-welcome-actions registrar-welcome-counts">
              <div><dt>{t('rp_welcome_waiting')}</dt><dd>{waiting}</dd></div>
              <div><dt>{t('rp_welcome_payment_pending')}</dt><dd>{pendingPayment}</dd></div>
              <div><dt>{t('status_done')}</dt><dd>{completed}</dd></div>
            </dl>
          </div>}
        </section>

        <section aria-label={t('rp_welcome_records')} className="registrar-welcome-section" aria-busy={loading}>
          <div className="registrar-welcome-toolbar">
            <h2 className="registrar-history-heading">{t('rp_welcome_records')}</h2>
            {hasUrlFilters &&
              <Button variant="outline" onClick={clearNarrowingFilters}>{t('rp_welcome_clear_filters')}</Button>}
            {dateMatches && (showRows || stale) && !sessionExpired && <DataSourceIndicator count={appointments.length} />}
          </div>
          {loading && !showRows && <p role="status">{t('misc.eat_loading')}</p>}
          {sessionExpired && (
            <div className="registrar-empty-state">
              <p role="status">{t('rp_welcome_session_expired')}</p>
              <a href="/login">{t('rp_welcome_log_in')}</a>
            </div>
          )}
          {loadError && !sessionExpired && (
            <div className="registrar-empty-state">
              <p role="alert">{t('ds_error_message')}</p>
              <Button variant="primary" onClick={() => void loadAppointments({ source: 'welcome_retry' })}>
                {t('ds_retry')}
              </Button>
            </div>
          )}
          {empty && (emptyScopeKind === 'filtered-empty' ? (
            <div className="registrar-empty-state">
              <h3>{t('rp_worklist_no_matches')}</h3>
              <p>{t('rp_empty_filter_desc')}</p>
            </div>
          ) : (
            <div className="registrar-empty-state">
              <h3>{t('rp_welcome_empty_day')}</h3>
              {selectedDate === today &&
                <Button variant="outline" onClick={createAppointment}>{t('rp_welcome_create_first')}</Button>}
            </div>
          ))}
          {showRows && (
            <EnhancedAppointmentsTable
              key={selectedDate}
              data={filteredAppointments}
              rawEntries={appointments}
              loading={appointmentsLoading}
              theme={theme}
              language={language}
              outerBorder
              services={services}
              preferCanonicalQueueNumber
              showCheckboxes={false}
              onRowClick={openRecordPreview}
              filteredExport={{
                label: t('rp_welcome_csv'),
                disabled: !canSummarize || loading,
                onExport: rows => {
                  const csv = generateCSV(rows, { includeQueueNumber: true });
                  downloadCSV(csv, `appointments_${selectedDate}.csv`);
                },
              }}
              onActionClick={(action, row, event) => {
                switch (action) {
                  case 'view':
                    logger.info('[Welcome] Row action: view', { recordId: row.id });
                    openRecordPreview(row);
                    break;
                  case 'edit':
                    logger.info('[Welcome] Row action: edit', { recordId: row.id });
                    openRecordEditor(row);
                    break;
                  case 'payment':
                    logger.info('[Welcome] Row action: payment', { recordId: row.id });
                    setPaymentDialog({ open: true, row, paid: false, source: 'welcome' });
                    break;
                  case 'in_cabinet':
                    // REG-FE-006: use the shared confirmation-gated row router.
                    return handleTableAction('in_cabinet', row as Record<string, unknown>, event);
                  case 'call':
                    logger.info('[Welcome] Row action: call', { recordId: row.id });
                    handleStartVisit(row);
                    break;
                  case 'complete':
                    return handleTableAction('complete', row as Record<string, unknown>, event);
                  case 'print':
                    logger.info('[Welcome] Row action: print', { recordId: row.id });
                    setPrintDialog({ open: true, type: 'ticket', data: row });
                    break;
                  case 'more':{
                      // Показать контекстное меню с дополнительными действиями
                      const evt = event as { target?: HTMLElement; clientX?: number; clientY?: number } | undefined;
                      const rect = evt?.target?.getBoundingClientRect();
                      setContextMenu({
                        open: true,
                        row,
                        position: {
                          x: rect?.right || evt?.clientX || 0,
                          y: rect?.top || evt?.clientY || 0
                        }
                      });
                      break;
                    }
                  default:
                    break;
                }
              }}
            />
          )}
        </section>
        {ownerGroups.size > 0 && (
          <details className="registrar-welcome-section">
            <summary>{t('rp_welcome_owner_counts')}</summary>
            <dl className="registrar-welcome-actions registrar-welcome-counts">
              {[...ownerGroups].map(([key, group]) => (
                <div key={key}>
                  <dt>{group.name}</dt>
                  <dd>{t(group.unlinked ? 'rp_welcome_records_count' : 'rp_welcome_patients_count',
                    { total: group.unlinked ? group.records : group.patients.size })}</dd>
                </div>
              ))}
            </dl>
          </details>
        )}
      </CardContent>
    </Card>
  );
});

WelcomeView.displayName = 'WelcomeView';
export default WelcomeView;
