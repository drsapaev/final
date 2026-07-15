import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import {
  Badge, Button, Icon,
} from '../ui/macos';
import { api } from '../../api/client';
import {
  readTelegramMiniAppInitData,
  describePatientError,
} from './patientUtils';
import PanelEmptyState from './PanelEmptyState';

/**
 * L-H-4 fix: PatientCabinetSummary выделен в отдельный файл (~200 строк).
 *
 * L-H-1 fix: все строки на русском.
 * L-H-2 fix: Tailwind classes → CSS-классы .pp-*
 * L-H-5 fix: skeleton-loading вместо EmptyState "Loading..."
 * L-H-8 fix: lucide-direct → macos <Icon>
 * L-M-2 fix: PDF-download имеет retry-кнопку при ошибке.
 *
 * Показывает сводку кабинета пациента в 3 режимах:
 *   - mode='cabinet': полная сводка (appointments/visits/queue/reports)
 *   - mode='payments': только платежи
 *   - mode='reports': только отчёты с PDF-download
 */
function PatientCabinetSummary({ mode = 'cabinet' }) {
  const [cabinetStatus, setCabinetStatus] = useState('idle');
  const [cabinetSummary, setCabinetSummary] = useState(null);
  const [cabinetError, setCabinetError] = useState('');
  const [cabinetInitData, setCabinetInitData] = useState('');
  const [reportDownloads, setReportDownloads] = useState({});

  useEffect(() => {
    const initData = readTelegramMiniAppInitData();
    if (!initData) {
      setCabinetStatus('missing-init-data');
      setCabinetSummary(null);
      setCabinetError('');
      setCabinetInitData('');
      return undefined;
    }

    let cancelled = false;
    setCabinetStatus('loading');
    setCabinetSummary(null);
    setCabinetError('');
    setCabinetInitData(initData);

    api.post('/telegram/mini-app/cabinet/summary', { initData })
      .then((response) => {
        if (cancelled) return;
        setCabinetSummary(response.data);
        setCabinetStatus('ready');
      })
      .catch((err) => {
        if (cancelled) return;
        const reason = err?.response?.data?.detail?.reason || 'cabinet_summary_failed';
        setCabinetError(describePatientError('cabinet', reason));
        setCabinetStatus('error');
      });

    return () => { cancelled = true; };
  }, []);

  // L-H-5 fix: skeleton-loading вместо misleading "Loading cabinet..."
  if (cabinetStatus === 'missing-init-data') {
    return (
      <PanelEmptyState
        icon="doc.text"
        title="Откройте из Telegram"
        description="Защищённый кабинет требует Telegram Mini App identity перед показом данных пациента."
      />
    );
  }

  if (cabinetStatus === 'loading') {
    return (
      <PanelEmptyState
        icon="doc.text"
        title="Загрузка кабинета…"
        description="Проверяем защищённый Telegram Mini App identity."
        variant="loading"
      />
    );
  }

  if (cabinetStatus === 'error') {
    return (
      <PanelEmptyState
        icon="exclamationmark.triangle"
        title="Кабинет недоступен"
        description={cabinetError || 'Не удалось загрузить защищённый кабинет пациента.'}
        variant="error"
      />
    );
  }

  const isPaymentsMode = mode === 'payments';
  const isReportsMode = mode === 'reports';
  const payments = cabinetSummary?.payments || {};
  const appointments = Array.isArray(cabinetSummary?.appointments) ? cabinetSummary.appointments : [];
  const visits = Array.isArray(cabinetSummary?.visits) ? cabinetSummary.visits : [];
  const queue = Array.isArray(cabinetSummary?.queue) ? cabinetSummary.queue : [];
  const reports = Array.isArray(cabinetSummary?.reports) ? cabinetSummary.reports : [];

  // L-M-2 fix: retry для PDF-download при ошибке
  const downloadReport = async (report) => {
    setReportDownloads((current) => ({ ...current, [report.id]: 'loading' }));

    try {
      const response = await api.post(
        '/telegram/mini-app/reports/download',
        { initData: cabinetInitData, reportId: report.id },
        { responseType: 'blob' },
      );
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = `kosmed-report-${report.id}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
      setReportDownloads((current) => ({ ...current, [report.id]: 'ready' }));
    } catch {
      setReportDownloads((current) => ({ ...current, [report.id]: 'error' }));
    }
  };

  const cabinetTitle = isPaymentsMode
    ? 'Платежи и долг'
    : isReportsMode
      ? 'Отчёты и документы'
      : (cabinetSummary?.patient?.name || 'Привязанный пациент');

  const cabinetSubtitle = isPaymentsMode
    ? `Защищённая сумма платежей для ${cabinetSummary?.patient?.name || 'привязанного пациента'}.`
    : isReportsMode
      ? `Готовые файлы отчётов для ${cabinetSummary?.patient?.name || 'привязанного пациента'}.`
      : 'Защищённая сводка кабинета из привязанного Telegram-профиля пациента.';

  return (
    <div className="pp-cabinet-root">
      <div className="pp-card">
        <div className="pp-card-header">
          <div>
            <div className="pp-card-title">{cabinetTitle}</div>
            <p className="pp-card-subtitle">{cabinetSubtitle}</p>
          </div>
          <Badge variant="success">Mini App защищено</Badge>
        </div>

        <div className="pp-card-body">
          {/* Payment totals */}
          <div className="pp-payments-grid">
            <div className="pp-payment-card">
              <div className="pp-payment-label">Счёт</div>
              <div className="pp-payment-value">{payments.billed ?? '0'} UZS</div>
            </div>
            <div className="pp-payment-card">
              <div className="pp-payment-label">Оплачено</div>
              <div className="pp-payment-value">{payments.paid ?? '0'} UZS</div>
            </div>
            <div className="pp-payment-card">
              <div className="pp-payment-label">Ожидает</div>
              <div className="pp-payment-value">{payments.pending ?? '0'} UZS</div>
            </div>
            <div className="pp-payment-card">
              <div className="pp-payment-label">Долг</div>
              <div className="pp-payment-value">{payments.debt ?? '0'} UZS</div>
            </div>
          </div>

          {isPaymentsMode && (
            <div className="pp-info-box">
              <div className="pp-info-title">Связанная активность</div>
              <div className="pp-info-grid">
                <div>Связанные визиты: {payments.linked_visit_count ?? 0}</div>
                <div>Активные записи в очереди: {payments.active_queue_count ?? 0}</div>
              </div>
              <div className="pp-info-hint">
                Онлайн-оплата и возврат недоступны в Telegram; персонал клиники выполняет платёжные операции в приложении клиники.
              </div>
            </div>
          )}

          {isReportsMode && (
            <div className="pp-reports-section">
              <div className="pp-section-title">Готовые отчёты</div>
              <div className="pp-reports-list">
                {reports.length > 0 ? reports.map((report) => (
                  <div key={report.id} className="pp-report-card">
                    <div className="pp-report-info">
                      <div className="pp-report-name">{report.name || 'Лабораторный отчёт'}</div>
                      <div className="pp-report-date">{report.ready_at || 'Дата готовности ожидается'}</div>
                      {reportDownloads[report.id] === 'error' && (
                        <div className="pp-message pp-message--error" role="alert">
                          <Icon name="exclamationmark.triangle" size={14} />
                          Не удалось открыть отчёт. Попробуйте снова из Telegram.
                        </div>
                      )}
                    </div>
                    {/* L-M-2 fix: retry-кнопка при ошибке */}
                    {reportDownloads[report.id] === 'error' ? (
                      <Button
                        variant="outline"
                        size="small"
                        onClick={() => downloadReport(report)}
                      >
                        <Icon name="arrow.clockwise" size={16} />
                        Повторить
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        size="small"
                        loading={reportDownloads[report.id] === 'loading'}
                        disabled={reportDownloads[report.id] === 'loading'}
                        onClick={() => downloadReport(report)}
                      >
                        <Icon name="doc.text" size={16} />
                        Открыть PDF
                      </Button>
                    )}
                  </div>
                )) : (
                  <div className="pp-empty-hint">Готовых отчётов пока нет.</div>
                )}
              </div>
            </div>
          )}

          {!isPaymentsMode && !isReportsMode && (
            <div className="pp-cabinet-grid">
              {/* Appointments */}
              <div className="pp-subsection">
                <div className="pp-section-title">Записи</div>
                <div className="pp-subsection-list">
                  {appointments.length > 0 ? appointments.map((appointment) => (
                    <div key={appointment.id} className="pp-list-item">
                      <div>
                        <div className="pp-list-item-primary">{appointment.date || 'Дата ожидается'}</div>
                        <div className="pp-list-item-secondary">{appointment.time || 'Время ожидается'} · {appointment.department || 'Отделение ожидается'}</div>
                      </div>
                      <Badge variant={appointment.status ? 'info' : 'outline'}>
                        {appointment.status || 'статус недоступен'}
                      </Badge>
                    </div>
                  )) : (
                    <div className="pp-empty-hint">Записей пока нет.</div>
                  )}
                </div>
              </div>

              {/* Visits */}
              <div className="pp-subsection">
                <div className="pp-section-title">Визиты</div>
                <div className="pp-subsection-list">
                  {visits.length > 0 ? visits.map((visit) => (
                    <div key={visit.id} className="pp-list-item">
                      <div className="pp-list-item-primary">Визит #{visit.id}</div>
                      <div className="pp-list-item-secondary">{visit.date || 'Дата ожидается'} · {visit.status || 'статус недоступен'}</div>
                    </div>
                  )) : (
                    <div className="pp-empty-hint">Недавних визитов пока нет.</div>
                  )}
                </div>
              </div>

              {/* Queue */}
              <div className="pp-subsection">
                <div className="pp-section-title">Очередь сегодня</div>
                <div className="pp-subsection-list">
                  {queue.length > 0 ? queue.map((entry) => (
                    <div key={`${entry.number}-${entry.status}`} className="pp-list-item">
                      <div className="pp-list-item-primary">#{entry.number}</div>
                      <div className="pp-list-item-secondary">{entry.status}{entry.cabinet ? ` · ${entry.cabinet}` : ''}</div>
                    </div>
                  )) : (
                    <div className="pp-empty-hint">Сегодня нет активной записи в очереди.</div>
                  )}
                </div>
              </div>

              {/* Reports */}
              <div className="pp-subsection">
                <div className="pp-section-title">Готовые отчёты</div>
                <div className="pp-subsection-list">
                  {reports.length > 0 ? reports.map((report) => (
                    <div key={report.id} className="pp-list-item">
                      <div>
                        <div className="pp-list-item-primary">{report.name || 'Лабораторный отчёт'}</div>
                        <div className="pp-list-item-secondary">{report.ready_at || 'Дата готовности ожидается'}</div>
                      </div>
                      <Badge variant={report.status ? 'success' : 'outline'}>
                        {report.status || 'статус недоступен'}
                      </Badge>
                    </div>
                  )) : (
                    <div className="pp-empty-hint">Готовых отчётов пока нет.</div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

PatientCabinetSummary.propTypes = {
  mode: PropTypes.oneOf(['cabinet', 'payments', 'reports']),
};

export default PatientCabinetSummary;
