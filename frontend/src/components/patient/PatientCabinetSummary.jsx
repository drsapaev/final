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
import { useTranslation } from '../../i18n/useTranslation';

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
  const { t } = useTranslation();
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
        title={t('patient.pat_cab_missing_init_title')}
        description={t('patient.pat_cab_missing_init_desc')}
      />
    );
  }

  if (cabinetStatus === 'loading') {
    return (
      <PanelEmptyState
        icon="doc.text"
        title={t('patient.pat_cab_loading_title')}
        description={t('patient.pat_cab_loading_desc')}
        variant="loading"
      />
    );
  }

  if (cabinetStatus === 'error') {
    return (
      <PanelEmptyState
        icon="exclamationmark.triangle"
        title={t('patient.pat_cab_error_title')}
        description={cabinetError || t('patient.pat_cab_error_desc')}
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
    ? t('patient.pat_cab_title_payments')
    : isReportsMode
      ? t('patient.pat_cab_title_reports')
      : (cabinetSummary?.patient?.name || t('patient.pat_cab_title_default'));

  const cabinetSubtitle = isPaymentsMode
    ? t('patient.pat_cab_subtitle_payments', { name: cabinetSummary?.patient?.name || t('patient.pat_cab_linked_patient_genitive') })
    : isReportsMode
      ? t('patient.pat_cab_subtitle_reports', { name: cabinetSummary?.patient?.name || t('patient.pat_cab_linked_patient_genitive') })
      : t('patient.pat_cab_subtitle_default');

  return (
    <div className="pp-cabinet-root">
      <div className="pp-card">
        <div className="pp-card-header">
          <div>
            <div className="pp-card-title">{cabinetTitle}</div>
            <p className="pp-card-subtitle">{cabinetSubtitle}</p>
          </div>
          <Badge variant="success">{t('patient.pat_cab_secure_badge')}</Badge>
        </div>

        <div className="pp-card-body">
          {/* Payment totals */}
          <div className="pp-payments-grid">
            <div className="pp-payment-card">
              <div className="pp-payment-label">{t('patient.pat_cab_label_billed')}</div>
              <div className="pp-payment-value">{payments.billed ?? '0'} UZS</div>
            </div>
            <div className="pp-payment-card">
              <div className="pp-payment-label">{t('patient.pat_cab_label_paid')}</div>
              <div className="pp-payment-value">{payments.paid ?? '0'} UZS</div>
            </div>
            <div className="pp-payment-card">
              <div className="pp-payment-label">{t('patient.pat_cab_label_pending')}</div>
              <div className="pp-payment-value">{payments.pending ?? '0'} UZS</div>
            </div>
            <div className="pp-payment-card">
              <div className="pp-payment-label">{t('patient.pat_cab_label_debt')}</div>
              <div className="pp-payment-value">{payments.debt ?? '0'} UZS</div>
            </div>
          </div>

          {isPaymentsMode && (
            <div className="pp-info-box">
              <div className="pp-info-title">{t('patient.pat_cab_info_title')}</div>
              <div className="pp-info-grid">
                <div>{t('patient.pat_cab_info_visits', { count: payments.linked_visit_count ?? 0 })}</div>
                <div>{t('patient.pat_cab_info_queue', { count: payments.active_queue_count ?? 0 })}</div>
              </div>
              <div className="pp-info-hint">
                {t('patient.pat_cab_info_hint')}
              </div>
            </div>
          )}

          {isReportsMode && (
            <div className="pp-reports-section">
              <div className="pp-section-title">{t('patient.pat_cab_section_reports')}</div>
              <div className="pp-reports-list">
                {reports.length > 0 ? reports.map((report) => (
                  <div key={report.id} className="pp-report-card">
                    <div className="pp-report-info">
                      <div className="pp-report-name">{report.name || t('patient.pat_cab_report_name_default')}</div>
                      <div className="pp-report-date">{report.ready_at || t('patient.pat_cab_report_date_default')}</div>
                      {reportDownloads[report.id] === 'error' && (
                        <div className="pp-message pp-message--error" role="alert">
                          <Icon name="exclamationmark.triangle" size={14} />
                          {t('patient.pat_cab_report_error')}
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
                        {t('patient.pat_cab_retry')}
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
                        {t('patient.pat_cab_open_pdf')}
                      </Button>
                    )}
                  </div>
                )) : (
                  <div className="pp-empty-hint">{t('patient.pat_cab_no_reports_yet')}</div>
                )}
              </div>
            </div>
          )}

          {!isPaymentsMode && !isReportsMode && (
            <div className="pp-cabinet-grid">
              {/* Appointments */}
              <div className="pp-subsection">
                <div className="pp-section-title">{t('patient.pat_cab_section_appointments')}</div>
                <div className="pp-subsection-list">
                  {appointments.length > 0 ? appointments.map((appointment) => (
                    <div key={appointment.id} className="pp-list-item">
                      <div>
                        <div className="pp-list-item-primary">{appointment.date || t('patient.pat_cab_date_pending')}</div>
                        <div className="pp-list-item-secondary">{appointment.time || t('patient.pat_cab_time_pending')} · {appointment.department || t('patient.pat_cab_dept_pending')}</div>
                      </div>
                      <Badge variant={appointment.status ? 'info' : 'outline'}>
                        {appointment.status || t('patient.pat_cab_status_unavailable')}
                      </Badge>
                    </div>
                  )) : (
                    <div className="pp-empty-hint">{t('patient.pat_cab_no_appointments')}</div>
                  )}
                </div>
              </div>

              {/* Visits */}
              <div className="pp-subsection">
                <div className="pp-section-title">{t('patient.pat_cab_section_visits')}</div>
                <div className="pp-subsection-list">
                  {visits.length > 0 ? visits.map((visit) => (
                    <div key={visit.id} className="pp-list-item">
                      <div className="pp-list-item-primary">{t('patient.pat_cab_visit_n', { id: visit.id })}</div>
                      <div className="pp-list-item-secondary">{visit.date || t('patient.pat_cab_date_pending')} · {visit.status || t('patient.pat_cab_status_unavailable')}</div>
                    </div>
                  )) : (
                    <div className="pp-empty-hint">{t('patient.pat_cab_no_visits')}</div>
                  )}
                </div>
              </div>

              {/* Queue */}
              <div className="pp-subsection">
                <div className="pp-section-title">{t('patient.pat_cab_section_queue')}</div>
                <div className="pp-subsection-list">
                  {queue.length > 0 ? queue.map((entry) => (
                    <div key={`${entry.number}-${entry.status}`} className="pp-list-item">
                      <div className="pp-list-item-primary">#{entry.number}</div>
                      <div className="pp-list-item-secondary">{entry.status}{entry.cabinet ? ` · ${entry.cabinet}` : ''}</div>
                    </div>
                  )) : (
                    <div className="pp-empty-hint">{t('patient.pat_cab_no_queue')}</div>
                  )}
                </div>
              </div>

              {/* Reports */}
              <div className="pp-subsection">
                <div className="pp-section-title">{t('patient.pat_cab_section_reports')}</div>
                <div className="pp-subsection-list">
                  {reports.length > 0 ? reports.map((report) => (
                    <div key={report.id} className="pp-list-item">
                      <div>
                        <div className="pp-list-item-primary">{report.name || t('patient.pat_cab_report_name_default')}</div>
                        <div className="pp-list-item-secondary">{report.ready_at || t('patient.pat_cab_report_date_default')}</div>
                      </div>
                      <Badge variant={report.status ? 'success' : 'outline'}>
                        {report.status || t('patient.pat_cab_status_unavailable')}
                      </Badge>
                    </div>
                  )) : (
                    <div className="pp-empty-hint">{t('patient.pat_cab_no_reports_yet')}</div>
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
