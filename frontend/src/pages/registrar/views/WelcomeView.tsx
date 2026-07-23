// i18n-unification: `t` is now passed as a prop from RegistrarPanel (wrapper
// around tI18n that routes flat keys to registrarPanel.* namespace).
// No direct import needed.
/**
 * Registrar Panel — Welcome View.
 *
 * Decomposition step 6b: extracted from RegistrarPanel.jsx (lines 1586-2020).
 *
 * Mirrors the QueueView.jsx extraction pattern (decomp 6a): the inline
 * welcome dashboard — hero header, ModernStatistics, quick-action buttons,
 * calendar widget, history table, and empty-state CTA — is lifted into a
 * dedicated presentational component. All state, setters, handlers, and
 * inline-defined helpers (DataSourceIndicator, generateCSV, downloadCSV)
 * are now passed as explicit props from RegistrarPanel.jsx so the welcome
 * view itself is pure / side-effect free.
 *
 * @param {Object} props
 * @param {Function} props.t - translation function from getRegistrarTranslator
 * @param {string} props.language - UI language code ('ru' | 'uz' | 'en')
 * @param {string} props.theme - 'light' or 'dark' from useTheme
 * @param {string} props.textColor - resolved CSS color string ('var(--mac-text-primary)')
 * @param {Array} props.appointments - all loaded appointment rows (raw)
 * @param {Object} props.departmentStats - aggregated department statistics for ModernStatistics
 * @param {string} props.dataSource - 'loading' | 'api' | 'error' (drives empty state + indicator)
 * @param {boolean} props.appointmentsLoading - whether appointments are currently loading
 * @param {Array} props.filteredAppointments - filtered rows for the active tab + status + search
 * @param {Object} props.services - services map for EnhancedAppointmentsTable
 * @param {string|null} props.activeTab - active department tab key (null = all departments)
 * @param {string} props.historyDate - selected calendar history date (YYYY-MM-DD)
 * @param {boolean} props.showCalendar - whether the calendar widget is open
 * @param {string} props.tempDateInput - temp value being typed into the date Input before blur
 * @param {Function} props.loadAppointments - reload appointments ({ source, force })
 * @param {Function} props.setShowWizard - open/close the appointment wizard
 * @param {Function} props.setWizardEditMode - toggle wizard edit vs create mode
 * @param {Function} props.setWizardInitialData - seed wizard with row data for editing
 * @param {Function} props.setShowPaymentManager - open/close the payment manager modal
 * @param {Function} props.setHistoryDate - commit a new history date
 * @param {Function} props.setShowCalendar - toggle calendar widget visibility
 * @param {Function} props.setTempDateInput - update temp date input value
 * @param {Function} props.setSearchParams - replace URL search params (filters / queue navigation)
 * @param {Function} props.navigate - react-router navigate function
 * @param {Function} props.setPaymentDialog - open/close payment dialog ({ open, row, paid, source })
 * @param {Function} props.setPrintDialog - open/close print dialog ({ open, type, data })
 * @param {Function} props.setContextMenu - open/close row context menu ({ open, row, position })
 * @param {Function} props.openRecordPreview - open a read-only record preview
 * @param {Function} props.openRecordEditor - open the wizard in edit mode for a row
 * @param {Function} props.updateAppointmentStatus - patch a row status (e.g. 'in_cabinet', 'done')
 * @param {Function} props.handleStartVisit - call the patient into the cabinet (start visit)
 * @param {Function} props.generateCSV - serialize appointment rows to a CSV string (parent-defined)
 * @param {Function} props.downloadCSV - trigger a browser CSV download (parent-defined)
 * @param {React.ComponentType<{count: number}>} props.DataSourceIndicator - memoized data-source
 *   badge rendered above the history table (parent-defined, closes over dataSource / paginationInfo)
 */
import React from 'react';
import PropTypes from 'prop-types';
import {
  Button, Card, CardHeader, CardContent, Badge, Icon, Input,
} from '../../../components/ui/macos';
import { AnimatedTransition } from '../../../components/ui';
import ModernStatistics from '../../../components/statistics/ModernStatistics';
import EnhancedAppointmentsTable from '../../../components/tables/EnhancedAppointmentsTable';
import { getLocalDateString, getYesterdayDateString } from '../../../utils/dateUtils';
import logger from '../../../utils/logger';
import notify from '../../../services/notify';
import tokenManager from '../../../utils/tokenManager';

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
  textColor?: string;
  // Data — appointment shape is dynamic; component reads arbitrary fields.
  appointments: Record<string, unknown>[];
  departmentStats: unknown;
  dataSource: string;
  appointmentsLoading: boolean;
  filteredAppointments: Record<string, unknown>[];
  services: Record<string, unknown>;
  // Filters
  activeTab: string | null;
  historyDate: string;
  showCalendar: boolean;
  tempDateInput: string;
  // Action: data load — accepts an options object per caller convention.
  loadAppointments: (options?: unknown) => void | Promise<void>;
  // Action: wizard
  setShowWizard: (open: boolean) => void;
  setWizardEditMode: (edit: boolean) => void;
  setWizardInitialData: (data: Record<string, unknown> | null) => void;
  // Action: payment manager
  setShowPaymentManager: (open: boolean) => void;
  // Action: filter changes
  setHistoryDate: (date: string) => void;
  setShowCalendar: (open: boolean) => void;
  setTempDateInput: (date: string) => void;
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
  updateAppointmentStatus: (id: unknown, status: string, note: string, row?: unknown) => void | Promise<void>;
  handleStartVisit: (row: unknown) => void | Promise<void>;
  // Action: CSV — actual signatures come from registrarCsv.ts; loosened here.
  generateCSV: (...args: unknown[]) => unknown;
  downloadCSV: (...args: unknown[]) => void;
  // Memoized data-source badge component
  DataSourceIndicator: WelcomeViewDataSourceIndicator;
  [key: string]: unknown;
}

const WelcomeView = React.memo(({
  t,
  language,
  theme,
  textColor,
  appointments,
  departmentStats,
  dataSource,
  appointmentsLoading,
  filteredAppointments,
  services,
  activeTab,
  historyDate,
  showCalendar,
  tempDateInput,
  loadAppointments,
  setShowWizard,
  setWizardEditMode,
  setWizardInitialData,
  setShowPaymentManager,
  setHistoryDate,
  setShowCalendar,
  setTempDateInput,
  setSearchParams,
  navigate,
  setPaymentDialog,
  setPrintDialog,
  setContextMenu,
  openRecordPreview,
  openRecordEditor,
  updateAppointmentStatus,
  handleStartVisit,
  generateCSV,
  downloadCSV,
  DataSourceIndicator,
}: WelcomeViewProps) => {
  return (
    <AnimatedTransition type="fade" delay={100}>
      <Card variant="default" className="registrar-card-surface">
        <CardHeader className="registrar-card-header">
          {/* QW-08 fix: reduced AnimatedTransition from 10 to 3 (100/200/300ms). */}
          {/* Previous delays 400/800/900/1000/1100/1350/1400/1500 blocked first */}
          {/* user intent until 1.5s after page load. */}
          <AnimatedTransition type="slide" direction="up" delay={200}>
            <h1 className="registrar-hero-title">
              {t('welcome')} в панель регистратора!
              <Icon name="person" size="default" style={{ color: 'var(--mac-accent-blue)' }} />
            </h1>
          </AnimatedTransition>
          <AnimatedTransition type="fade" delay={300}>
            <div className="registrar-date-subtitle">
              {new Date().toLocaleDateString(
                // PR-51: fixed date locale — EN users now get en-US (was uz-UZ)
                language === 'ru' ? 'ru-RU' : language === 'en' ? 'en-US' : 'uz-UZ', {
              weekday: 'long',
              year: 'numeric',
              month: 'long',
              day: 'numeric'
            })}
            </div>
          </AnimatedTransition>
        </CardHeader>

        <CardContent>
          {/* UX Audit Registrar #5: Morning checklist — список врачей с
              информацией о том, открыт ли приём. Раньше регистратору нужно
              было проверять каждого врача вручную через QueueView. */}
          {(() => {
            // Группируем записи по врачам и определяем статус приёма.
            const doctorMap = new Map();
            for (const appt of appointments) {
              const doctorId = appt.doctor_id || appt.specialist_id;
              const doctorName = appt.doctor_name || appt.specialist_name || `Врач #${doctorId}`;
              if (!doctorMap.has(doctorId)) {
                doctorMap.set(doctorId, {
                  id: doctorId,
                  name: doctorName,
                  patientCount: 0,
                  hasQueue: false,
                });
              }
              const doc = doctorMap.get(doctorId);
              doc.patientCount++;
              if (appt.queue_entry_id || appt.queue_number) {
                doc.hasQueue = true;
              }
            }
            const doctorsList = Array.from(doctorMap.values());

            if (doctorsList.length === 0) return null;

            return (
              <div style={{
                marginBottom: 'var(--mac-spacing-6)',
                padding: 'var(--mac-spacing-4)',
                borderRadius: 'var(--mac-radius-lg)',
                border: '1px solid var(--mac-card-border)',
                background: 'var(--mac-card-bg)',
              }}>
                <h2 style={{
                  margin: '0 0 var(--mac-spacing-3) 0',
                  fontSize: 'var(--mac-font-size-base)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  color: textColor,
                }}>
                  Утренний статус приёма
                </h2>
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                  gap: 'var(--mac-spacing-3)',
                }}>
                  {doctorsList.map((doc) => (
                    <div
                      key={doc.id}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 'var(--mac-spacing-1)',
                        padding: '10px 12px',
                        borderRadius: 'var(--mac-radius-md)',
                        border: '1px solid var(--mac-card-border)',
                        background: 'var(--mac-bg-secondary)',
                      }}
                    >
                      <span style={{
                        fontSize: 'var(--mac-font-size-sm)',
                        fontWeight: 'var(--mac-font-weight-semibold)',
                        color: textColor,
                      }}>
                        {doc.name}
                      </span>
                      <span style={{
                        fontSize: 'var(--mac-font-size-xs)',
                        color: 'var(--mac-text-secondary)',
                      }}>
                        Пациентов: {doc.patientCount}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            );
          })()}

          {/* Современная статистика */}
          <ModernStatistics
          appointments={appointments}
          departmentStats={departmentStats}
          language={language}
          selectedDate={showCalendar && historyDate ? historyDate : getLocalDateString()}
          onExport={() => {
            logger.info('Экспорт статистики');
          }}
          onRefresh={() => {
            loadAppointments({ source: 'statistics_refresh' });
          }} />


          {/* Панель управления и фильтров */}
          {/* QW-08 fix: unwrapped nested AnimatedTransition (was delays 800-1500). */}
            {/* UX Audit R-4.6: убран мета-заголовок «Панель управления».
                Две группы кнопок ниже сами по себе понятны, лишний
                заголовок создавал визуальный шум (Nielsen #8). */}
            <div style={{ marginBottom: 'var(--mac-spacing-8)' }}>
              {/* Быстрые действия */}
                <div className="registrar-grid-auto" style={{ marginBottom: 'var(--mac-spacing-6)' }}>
                    <Button
                    variant="primary"
                    size="default"
                    onClick={() => {
                      logger.info('Кнопка "Новая запись" нажата');
                      setWizardEditMode(false); // ✅ Сброс режима
                      setWizardInitialData(null); // ✅ Сброс данных
                      setShowWizard(true);
                    }}
                    aria-label="Create new appointment"
                    className="registrar-flex" style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>

                      <Icon name="plus" size="small" style={{ color: 'white' }} />
                      {t('new_appointment')}
                    </Button>

                  {/* Кнопка модуля оплаты */}
                    <Button
                    variant="secondary"
                    size="default"
                    onClick={() => setShowPaymentManager(true)}
                    aria-label="Open payment module"
                    className="registrar-flex">

                      <Icon name="creditcard" size="small" />
                      Модуль оплаты
                    </Button>

                    <Button
                    variant="outline"
                    size="default"
                    onClick={() => {
                      logger.info('Кнопка "Экспорт CSV" нажата');
                      const csvContent = generateCSV(appointments);
                      const filename = `appointments_${getLocalDateString()}.csv`;
                      downloadCSV(csvContent, filename);
                      notify.success(`Экспортировано ${appointments.length} записей`);
                    }}
                    className="registrar-flex">

                      <Icon name="square.and.arrow.up" size="small" />
                      {t('export_csv')}
                    </Button>
                </div>

              {/* Фильтры и навигация */}
                <div className="registrar-surface-toolbar">
                  <h3 className="registrar-subsection-heading">
                    <Icon name="line.3.horizontal.decrease" size="default" style={{ color: 'var(--mac-accent-blue)' }} />
                    Фильтры и навигация
                  </h3>

                  {/* UX Audit R-1.1: 6 кнопок → 2 primary + overflow dropdown.
                      Раньше: 6 кнопок одновременно → Hick's Law violation.
                      Теперь: «Календарь» (toggle) + «Все записи» (default filter) +
                      «Ещё» dropdown с остальными 4 действиями. */}
                  <div className="registrar-grid-auto">
                    <Button
                    variant={showCalendar ? 'primary' : 'outline'}
                    size="default"
                    onClick={() => {
                      logger.info('Кнопка "Календарь" нажата');
                      setShowCalendar(!showCalendar);
                    }}
                    className="registrar-flex">

                      <Icon name="calendar" size="small" className={showCalendar ? 'registrar-text-white' : 'registrar-text-primary'} />
                      Календарь
                    </Button>

                    <Button
                    variant="outline"
                    size="default"
                    onClick={() => setSearchParams({})}
                    className="registrar-flex">

                      <Icon name="eye" size="small" />
                      Все записи
                    </Button>

                    <details className="registrar-overflow-menu">
                      <summary className="registrar-overflow-trigger" aria-label="Дополнительные фильтры и действия">
                        <Icon name="plus" size="small" aria-hidden="true" />
                        Ещё
                      </summary>
                      <div className="registrar-overflow-popover" role="menu">
                        <button
                          type="button"
                          className="registrar-overflow-item"
                          onClick={() => setSearchParams({ status: 'queued' })}
                          role="menuitem">
                          <Icon name="checkmark.circle" size="small" aria-hidden="true" />
                          Активная очередь
                        </button>
                        <button
                          type="button"
                          className="registrar-overflow-item"
                          onClick={() => setSearchParams({ status: 'paid_pending' })}
                          role="menuitem">
                          <Icon name="creditcard" size="small" aria-hidden="true" />
                          Ожидают оплаты
                        </button>
                        <button
                          type="button"
                          className="registrar-overflow-item"
                          onClick={() => navigate('/registrar/queue')}
                          role="menuitem">
                          <Icon name="bell" size="small" aria-hidden="true" />
                          Онлайн-очередь
                        </button>
                        <button
                          type="button"
                          className="registrar-overflow-item"
                          onClick={() => {loadAppointments({ source: 'manual_refresh_button' });notify.success(t('misc.data_updated'));}}
                          role="menuitem">
                          <Icon name="arrow.clockwise" size="small" aria-hidden="true" />
                          Обновить данные
                        </button>
                      </div>
                    </details>
                  </div>

                  {/* Календарный виджет */}
                  {showCalendar &&
                <div className="registrar-info-card" style={{ padding: 'var(--mac-spacing-5)', boxShadow: 'var(--mac-shadow-sm)' }}>
                      <div className="registrar-flex-col">
                        <label className="registrar-picker-label">
                          <Icon name="magnifyingglass" size="small" style={{ color: 'var(--mac-text-secondary)' }} />
                          Выберите дату для просмотра истории:
                        </label>
                        <Input
                      type="date"
                      label=""
                      value={tempDateInput}
                      onChange={(e) => {
                        setTempDateInput(e.target.value);
                        logger.info('Введена дата (debounced):', e.target.value);
                      }}
                      onBlur={(e) => {
                        if (e.target.value && e.target.value !== historyDate) {
                          logger.info('📅 Date input blur - applying immediately:', e.target.value);
                          setHistoryDate(e.target.value);
                        }
                      }} />

                        <div className="registrar-flex-wrap" style={{ gap: 'var(--mac-spacing-2)' }}>
                          <button
                      type="button"
                      onClick={() => {
                        const today = getLocalDateString();
                        setTempDateInput(today);
                        setHistoryDate(today);
                      }}
                      className="registrar-date-btn"
                      style={{
                        background: theme === 'light' ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-quaternary)',
                        color: textColor
                      }}>

                            Сегодня
                          </button>
                          <button
                      type="button"
                      onClick={() => {
                        const yesterdayStr = getYesterdayDateString();
                        setTempDateInput(yesterdayStr);
                        setHistoryDate(yesterdayStr);
                      }}
                      className="registrar-date-btn"
                      style={{
                        background: theme === 'light' ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-quaternary)',
                        color: textColor
                      }}>

                            Вчера
                          </button>
                          <button
                      type="button"
                      onClick={() => {
                        const weekAgo = new Date();
                        weekAgo.setDate(weekAgo.getDate() - 7);
                        const weekAgoStr = getLocalDateString(weekAgo);
                        setTempDateInput(weekAgoStr);
                        setHistoryDate(weekAgoStr);
                      }}
                      className="registrar-date-btn"
                      style={{
                        background: theme === 'light' ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-quaternary)',
                        color: textColor
                      }}>

                            Неделю назад
                          </button>
                        </div>
                      </div>
                    </div>
                }
                </div>
            </div>

          {/* История записей */}
          <div>
            <div className="registrar-flex-between" style={{ marginBottom: 'var(--mac-spacing-4)' }}>
              <h3 className="registrar-history-heading">
                <Icon name="eye" size="default" style={{ color: 'var(--mac-accent-blue)' }} />
                История записей
              </h3>
              {showCalendar &&
            <Badge variant="secondary" className="registrar-badge-date">
                  <Icon name="magnifyingglass" size="small" />
                  {new Date(historyDate).toLocaleDateString(
                    // PR-51: locale-aware date formatting (was hardcoded ru-RU)
                    language === 'ru' ? 'ru-RU' : language === 'en' ? 'en-US' : 'uz-UZ',
                    { day: 'numeric', month: 'long', year: 'numeric' })}
                </Badge>
            }
            </div>
            <div className="registrar-surface-toolbar">
              {/* Индикатор источника данных */}
              {appointments.length > 0 && <DataSourceIndicator count={appointments.length} />}

              {/* ✅ ДОБАВЛЕНО: Сообщение при пустой очереди */}
              {(() => {
              const token = tokenManager.getAccessToken();
              const isNoToken = !token;
              const isEmptyQueue = !appointmentsLoading && dataSource === 'api' && filteredAppointments.length === 0;

              // PR-51: removed logger.info('Empty state render check') — was
              // running on EVERY render (even when table is full), logging
              // PII-adjacent data at info level. Replaced with debug-level
              // log that only fires when the empty state is actually shown.
              if (isEmptyQueue && import.meta.env.MODE === 'development') {
                logger.debug('Empty state shown:', { isNoToken, dataSource, filteredLength: filteredAppointments.length });
              }

              return isEmptyQueue;
            })() &&
            <div className="registrar-empty-state">
                    {/* QW-04: empty state 1 of 3 (session-expired / empty-queue). */}
              {/* Full unification deferred — migrate to MacOSEmptyState from */}
              {/* the macOS design system (components/ui/macos) first. */}
              <div className="registrar-empty-icon-lg">
                      {!tokenManager.hasToken() ?
                <Icon name="lock" size="large" /> :
                <Icon name="doc.text" size="large" />}
                    </div>
                    <h3 className="registrar-empty-heading" style={{ color: textColor }}>
                      {!tokenManager.hasToken() ? 'Сессия истекла' : 'Очередь пуста'}
                    </h3>
                    <p className="registrar-empty-desc-text" style={{ fontSize: 'var(--mac-font-size-lg)', color: textColor }}>
                      {!tokenManager.hasToken() ?
                'Нажмите "Войти снова", чтобы обновить данные.' :
                'На сегодня нет записей в очереди.'}
                    </p>

                    {/* Кнопки действий */}
                    {!tokenManager.hasToken() &&
              <div className="registrar-flex-wrap">
                        <button
                  onClick={() => {
                    // Перенаправляем на страницу входа
                    window.location.href = '/login';
                  }}
                  className="registrar-btn-lg registrar-btn-accent">

                          <Icon name="key" size="small" style={{ marginRight: 'var(--mac-spacing-2)' }} />Войти снова
                        </button>

                        <button
                  onClick={() => {
                    // Обновляем данные
                    loadAppointments({ source: 'manual_refresh_button' });
                  }}
                  className="registrar-btn-lg registrar-btn-success">

                          <Icon name="arrow.up.arrow.down" size="small" style={{ marginRight: 'var(--mac-spacing-2)' }} />Обновить данные
                        </button>

                        {/* UX Audit R-2.2: кнопка «Перезапустить приложение» удалена —
                            это dev-tool, не должен быть в продакшене. */}
              </div>
              }
                    <p style={{
                fontSize: 'var(--mac-font-size-base)',
                color: textColor,
                marginBottom: 'var(--mac-spacing-6)'
              }}>
                      {activeTab ?
                `Сегодня нет записей в отделении ${activeTab === 'cardio' ? 'Кардиология' : activeTab === 'derma' ? 'Дерматология' : activeTab === 'dental' ? 'Стоматология' : activeTab === 'lab' ? 'Лаборатория' : activeTab}` :
                'Сегодня пока нет записей'}
                    </p>
                    {/* QW-04: empty state 3 of 3 (welcome no-records). */}
              {/* See empty state 1 above for unification plan. */}
              <Button
                variant="primary"
                onClick={() => {
                  setWizardEditMode(false); // ✅ Сброс режима
                  setWizardInitialData(null); // ✅ Сброс данных
                  setShowWizard(true);
                }}
                // PR-51: disable CTA when session expired (no token)
                disabled={!tokenManager.hasToken()}
                className="registrar-btn-cta">

                      <Icon name="plus" size="small" style={{ marginRight: 'var(--mac-spacing-2)' }} />Создать первую запись
                    </Button>
                  </div>
            }

              {/* Таблица отображается только если есть данные */}
              {(appointmentsLoading || filteredAppointments.length > 0) &&
            <EnhancedAppointmentsTable
              data={filteredAppointments}
              rawEntries={appointments} // ⭐ SSOT FIX: Сырые данные для полного Tooltip
              loading={appointmentsLoading}
              theme={theme}
              language={language}
              outerBorder={true}
              services={services}
              showCheckboxes={true} // UX Audit Registrar #13: включаем чекбоксы для bulk print
              onRowClick={(row) => {
                logger.info('Открыть детали записи:', row);
                // Здесь можно открыть модальное окно с деталями записи
              }}
              onActionClick={(action, row, event) => {
                switch (action) {
                  case 'view':
                    logger.info('Просмотр записи:', row);
                    openRecordPreview(row);
                    break;
                  case 'edit':
                    logger.info('[RegistrarPanel] Открытие мастера редактирования для:', row.patient_fio || row.patient_name);
                    openRecordEditor(row);
                    break;
                  case 'payment':
                    logger.info('Открытие модального окна оплаты для записи (welcome):', row);
                    setPaymentDialog({ open: true, row, paid: false, source: 'welcome' });
                    break;
                  case 'in_cabinet':
                    logger.info('Отправка пациента в кабинет (welcome):', row);
                    updateAppointmentStatus(row.id, 'in_cabinet', '', row);
                    break;
                  case 'call':
                    logger.info('Вызов пациента (welcome):', row);
                    handleStartVisit(row);
                    break;
                  case 'complete':
                    logger.info('Завершение приёма (welcome):', row);
                    updateAppointmentStatus(row.id, 'done', '', row);
                    break;
                  case 'print':
                    logger.info('Печать талона (welcome):', row);
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
              }} />

            }
            </div>
          </div>
        </CardContent>
      </Card>
    </AnimatedTransition>
  );
});

WelcomeView.displayName = 'WelcomeView';

// UX Audit: PropTypes for all props used in WelcomeView.
(WelcomeView as unknown as { propTypes: unknown }).propTypes = {
  t: PropTypes.func,
  language: PropTypes.string,
  theme: PropTypes.string,
  textColor: PropTypes.string,
  appointments: PropTypes.array,
  departmentStats: PropTypes.object,
  dataSource: PropTypes.string,
  appointmentsLoading: PropTypes.bool,
  filteredAppointments: PropTypes.array,
  services: PropTypes.object,
  activeTab: PropTypes.string,
  historyDate: PropTypes.string,
  showCalendar: PropTypes.bool,
  tempDateInput: PropTypes.string,
  loadAppointments: PropTypes.func,
  setShowWizard: PropTypes.func,
  setWizardEditMode: PropTypes.func,
  setWizardInitialData: PropTypes.func,
  setShowPaymentManager: PropTypes.func,
  setHistoryDate: PropTypes.func,
  setShowCalendar: PropTypes.func,
  setTempDateInput: PropTypes.func,
  setSearchParams: PropTypes.func,
  navigate: PropTypes.func,
  setPaymentDialog: PropTypes.func,
  setPrintDialog: PropTypes.func,
  setContextMenu: PropTypes.func,
  openRecordPreview: PropTypes.func,
  openRecordEditor: PropTypes.func,
  updateAppointmentStatus: PropTypes.func,
  handleStartVisit: PropTypes.func,
  generateCSV: PropTypes.func,
  downloadCSV: PropTypes.func,
  DataSourceIndicator: PropTypes.elementType,
};

export default WelcomeView;
