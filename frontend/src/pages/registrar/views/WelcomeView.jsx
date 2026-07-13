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
}) => {
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
              <Icon name="person" size="default" className="registrar-text-accent" />
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
            <div style={{ marginBottom: 'var(--mac-spacing-8)' }}>
                <h2 className="registrar-section-heading">
                  <Icon name="gear" size="default" className="registrar-text-accent" />
                  Панель управления
                </h2>

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

                      <Icon name="plus" size="small" className="registrar-text-white" />
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
                    <Icon name="magnifyingglass" size="default" className="registrar-text-accent" />
                    Фильтры и навигация
                  </h3>

                  <div className="registrar-grid-auto">
                    <Button
                    variant={showCalendar ? 'warning' : 'outline'}
                    size="default"
                    onClick={() => {
                      logger.info('Кнопка "Календарь" нажата');
                      setShowCalendar(!showCalendar);
                    }}
                    className="registrar-flex">

                      <Icon name="magnifyingglass" size="small" style={{ color: showCalendar ? 'white' : 'var(--mac-text-primary)' }} />
                      Календарь
                    </Button>

                    <Button
                    variant="success"
                    size="default"
                    onClick={() => setSearchParams({ status: 'queued' })}
                    className="registrar-flex">

                      <Icon name="checkmark.circle" size="small" className="registrar-text-white" />
                      Активная очередь
                    </Button>

                    <Button
                    variant="primary"
                    size="default"
                    onClick={() => setSearchParams({ status: 'paid_pending' })}
                    className="registrar-flex">

                      <Icon name="creditcard" size="small" className="registrar-text-white" />
                      Ожидают оплаты
                    </Button>

                    <Button
                    variant="outline"
                    size="default"
                    onClick={() => setSearchParams({})}
                    className="registrar-flex">

                      <Icon name="eye" size="small" />
                      Все записи
                    </Button>

                    <Button
                    variant="outline"
                    size="default"
                    onClick={() => navigate('/registrar/queue')}
                    className="registrar-flex">

                      <Icon name="bell" size="small" />
                      Онлайн-очередь
                    </Button>

                    <Button
                    variant="outline"
                    size="default"
                    onClick={() => {loadAppointments({ source: 'manual_refresh_button' });notify.success('Данные обновлены');}}
                    className="registrar-flex">

                      <Icon name="gear" size="small" />
                      Обновить данные
                    </Button>
                  </div>

                  {/* Календарный виджет */}
                  {showCalendar &&
                <div className="registrar-info-card" style={{ padding: 'var(--mac-spacing-5)', boxShadow: 'var(--mac-shadow-sm)' }}>
                      <div className="registrar-flex-col">
                        <label className="registrar-picker-label">
                          <Icon name="magnifyingglass" size="small" className="registrar-text-secondary" />
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
                <Icon name="eye" size="default" className="registrar-text-accent" />
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
                  className="registrar-btn-lg registrar-btn-accent"
                  onMouseOver={(e) => e.target.style.background = 'var(--mac-accent-blue-hover)'}
                  onMouseOut={(e) => e.target.style.background = 'var(--mac-accent-blue)'}>

                          <Icon name="key" size="small" className="registrar-icon-mr" />Войти снова
                        </button>

                        <button
                  onClick={() => {
                    // Обновляем данные
                    loadAppointments({ source: 'manual_refresh_button' });
                  }}
                  className="registrar-btn-lg registrar-btn-success"
                  onMouseOver={(e) => e.target.style.background = 'var(--mac-accent-green-hover)'}
                  onMouseOut={(e) => e.target.style.background = 'var(--mac-accent-green)'}>

                          <Icon name="arrow.up.arrow.down" size="small" className="registrar-icon-mr" />Обновить данные
                        </button>

                        <button
                  onClick={() => {
                    // Перезапускаем приложение
                    window.location.reload();
                  }}
                  className="registrar-btn-lg registrar-btn-neutral"
                  onMouseOver={(e) => e.target.style.background = 'var(--mac-text-secondary)'}
                  onMouseOut={(e) => e.target.style.background = 'var(--mac-text-tertiary)'}>

                          <Icon name="arrow.up.arrow.down" size="small" className="registrar-icon-mr" />Перезапустить приложение
                        </button>
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

                      <Icon name="plus" size="small" className="registrar-icon-mr" />Создать первую запись
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
                      const rect = event?.target?.getBoundingClientRect();
                      setContextMenu({
                        open: true,
                        row,
                        position: {
                          x: rect?.right || event?.clientX || 0,
                          y: rect?.top || event?.clientY || 0
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

export default WelcomeView;
