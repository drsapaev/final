import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect } from 'react';
import type { CSSProperties } from 'react';
import {
  FileText,
  Download,
  Calendar,

  BarChart3,


  Clock,
  Activity,
  Trash2,
  RefreshCw,
  Settings,

  AlertCircle,

  FileSpreadsheet,
  FileX,
  Loader2 } from
'lucide-react';
import { MacOSCard, Button, Badge } from '../ui/macos';
import {
  MacOSStatCard,
  Table,
  Input,
  MacOSEmptyState,
  Select,
  SegmentedControl,
} from '../ui/macos';
import { toast } from 'react-toastify';

import { api } from '../../api/client';
import logger from '../../utils/logger';
import { getReportEndpoint } from '../../utils/reportEndpoints';
// P-013 fix: shared ConfirmDialog hook replacing window.confirm() calls.
import { useConfirm } from '../common/ConfirmDialog';

const ReportsManager = () => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirmRaw, confirmDialog] = useConfirm();
  const confirm = confirmRaw as unknown as (opts: Record<string, unknown>) => Promise<boolean>;
  const [activeTab, setActiveTab] = useState('generate');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null); // Global error state
  const [reports, setReports] = useState([]);
  const [files, setFiles] = useState([]);
  const [availableReports, setAvailableReports] = useState([]);

  // Состояние для генерации отчетов
  const [reportForm, setReportForm] = useState({
    type: '',
    format: 'excel',
    start_date: '',
    end_date: '',
    filters: {}
  } as any);

  // Состояние для быстрых отчетов
  const [quickReports, setQuickReports] = useState({ daily: null });

  useEffect(() => {
    loadAvailableReports();
    loadReportFiles();
    loadQuickReports();
  }, []);

  const loadAvailableReports = async () => {
    try {
      const response = await api.get('/reports/available-reports') as any;
      const reports = response.data?.reports || [];
      setAvailableReports(reports);
      setReportForm((prev) => ({
        ...prev,
        type: reports.some((report) => report.type === prev.type) ? prev.type : ''
      }));
    } catch (error) {
      logger.error('Failed to load available reports:', error);
      setError('Failed to load report catalog');
      setAvailableReports([]);
      setReportForm((prev) => ({ ...prev, type: '' }));
    }
  };

  const loadReportFiles = async () => {
    try {
      const response = await api.get('/reports/files') as any;
      setFiles(response.data?.files || []);
    } catch (error) {
      logger.error('Ошибка загрузки файлов отчетов:', error);
      setError(t('admin2.rm_load_files_error')); // Set error state
      setFiles([]);
    }
  };

  const loadQuickReports = async () => {
    try {
      // P1 fix: only daily-summary endpoint exists in backend. Weekly/monthly
      // endpoints do not exist (verified via backend/openapi.json), so the
      // weekly/monthly KPI cards showed a perpetual loading spinner. Removed
      // those cards; this loader now only fetches daily.
      const response = await api.get('/reports/daily-summary') as any;
      setQuickReports((prev) => ({ ...prev, daily: response.data }));
    } catch (error) {
      logger.error('Ошибка загрузки быстрых отчетов:', error);
      setError(t('admin2.rm_load_stats_error'));
      setQuickReports({ daily: null });
    }
  };

  const handleRetry = () => {
    setError(null);
    loadAvailableReports();
    loadReportFiles();
    loadQuickReports();
  };

  const generateReport = async () => {
    const endpoint = getReportEndpoint(reportForm.type);
    if (!reportForm.type || !endpoint) {
      toast.error(t('admin2.rm_select_report_type'));
      return;
    }

    setLoading(true);
    try {
      const response = await api.post(`/reports/${endpoint}`, {
        start_date: reportForm.start_date || null,
        end_date: reportForm.end_date || null,
        format: reportForm.format,
        filters: reportForm.filters
      }) as any;

      const data = response.data;
      if (data.success) {
        toast.success(t('admin2.rm_report_generated_success'));
        if (data.filename) {
          // Если есть файл, обновляем список файлов
          loadReportFiles();
        }
        // Показываем результат
        setReports((prev) => [data, ...prev]);
      } else {
        toast.error(data.error || t('admin2.rm_report_generation_error'));
      }
    } catch (error) {
      logger.error('Ошибка генерации отчета:', error);
      toast.error(error.response?.data?.detail || t('admin2.rm_report_generation_error'));
    } finally {
      setLoading(false);
    }
  };













  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const downloadFile = async (filename) => {
    try {
      const response = await api.get(`/reports/download/${filename}`, {
        responseType: 'blob'
      }) as any;

      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success(t('admin2.rm_file_downloaded_success'));
    } catch (error) {
      logger.error('Ошибка загрузки файла:', error);
      toast.error(t('admin2.rm_file_download_error'));
    }
  };

  const cleanupOldReports = async () => {
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: t('admin2.clean_reports_title'),
      message: t('admin2.rm_clean_reports_message'),
      description: t('admin2.rm_clean_reports_description'),
      confirmLabel: t('admin2.delete_confirm'),
      cancelLabel: t('admin2.cancel'),
      intent: 'danger',
    });
    if (!ok) {
      return;
    }

    try {
      const response = await api.post('/reports/cleanup') as any;
      toast.success(response.data?.message || t('admin2.rm_files_cleaned_success'));
      loadReportFiles();
    } catch (error) {
      logger.error('Ошибка очистки файлов:', error);
      toast.error(t('admin2.rm_files_clean_error'));
    }
  };

  const renderGenerateTab = () =>
  <div className="flex flex-col gap-6">
      {/* Форма генерации отчета */}
      <MacOSCard className="admin-card-p-24-bg-card-12">
        <h3 className="admin-h3-18-600-primary-mb-20">
          <BarChart3 className="admin-icon-20-mr-10-blue" />
          {t('admin2.rm_generation_title')}
        </h3>

        <div className="admin-grid-2col-20-mb-24">
          <div>
            <label className="admin-label-block-13-500-secondary-mb-8">{t('admin2.rm_label_type')}</label>
            <Select
            value={reportForm.type}
            onChange={(value) => setReportForm((prev) => ({ ...prev, type: value }))}
            options={availableReports.map((report) => ({
              value: report.type,
              label: report.name
            }))}
            size="large"
            placeholder={t('admin2.rm_select_type_ph')} />

          </div>

          <div>
            <label className="admin-label-block-13-500-secondary-mb-8">{t('admin2.rm_label_format')}</label>
            <Select
            value={reportForm.format}
            onChange={(value) => setReportForm((prev) => ({ ...prev, format: value }))}
            options={[
            { value: 'json', label: 'JSON' },
            { value: 'excel', label: 'Excel' },
            { value: 'csv', label: 'CSV' },
            { value: 'pdf', label: 'PDF' }]
            }
            size="large" />

          </div>

          <div>
            <label className="admin-label-block-13-500-secondary-mb-8">{t('admin2.rm_label_start_date')}</label>
            <Input
            type="date"
            value={reportForm.start_date}
            onChange={(e) => setReportForm((prev) => ({ ...prev, start_date: e.target.value }))} />

          </div>

          <div>
            <label className="admin-label-block-13-500-secondary-mb-8">{t('admin2.rm_label_end_date')}</label>
            <Input
            type="date"
            value={reportForm.end_date}
            onChange={(e) => setReportForm((prev) => ({ ...prev, end_date: e.target.value }))} />

          </div>
        </div>

        <div className="admin-flex-justify-end">
          <Button
          type="button"
          title={loading ? t('admin2.rm_generating_aria') : t('admin2.rm_generate_btn_aria')}
          aria-label={loading ? t('admin2.rm_generating_aria') : t('admin2.rm_generate_btn_aria')}
          onClick={generateReport}
          disabled={loading || !reportForm.type}
          className="admin-btn-blue-w-full-h-44-flex-center admin-opacity-dynamic"
          style={{ '--admin-opacity': loading ? 0.7 : 1 } as CSSProperties}>

            {loading ?
          <>
                <Loader2 aria-hidden="true" className="admin-icon-18-spin animate-spin" />
                <span>{t('admin2.rm_generating')}</span>
              </> :

          <>
                <FileText aria-hidden="true" className="w-4.5 h-4.5" />
                <span>{t('admin2.rm_generate_btn')}</span>
              </>
          }
          </Button>
        </div>
      </MacOSCard>

      {/* Быстрые отчеты */}
      <MacOSCard className="admin-card-p-24-bg-card-12">
        <h3 className="admin-h3-18-600-primary-mb-20">
          <Clock className="admin-icon-20-mr-10-blue" />
          {t('admin2.rm_quick_reports_title')}
        </h3>

        <div className="admin-grid-auto-240-16">
          <MacOSStatCard
          title={t('admin2.rm_today_stat_title')}
          value={quickReports.daily?.summary?.total_patients_served || 0}
          subtitle={`${quickReports.daily?.summary?.total_revenue || 0} ${t('admin2.rm_currency')}`}
          icon={Clock}
          color="blue"
          trend={quickReports.daily ? `+${quickReports.daily.summary?.new_patients || 0}` : undefined}
          trendType={quickReports.daily ? 'positive' : 'neutral'}
          loading={!quickReports.daily} />

        </div>
      </MacOSCard>

      {/* Последние отчеты */}
      {reports.length > 0 &&
    <MacOSCard className="p-6">
          <h3 className="admin-h4-lg-semi-primary-mb-16">{t('admin2.rm_recent_reports_title')}</h3>
          <Table
        columns={[
        {
          key: 'type',
          header: t('admin2.rm_col_type'),
          render: (value: any) =>
          <span className="admin-text-med-primary">
                    {availableReports.find((r) => r.type === value)?.name || value}
                  </span>

        },
        {
          key: 'generated_at',
          header: t('admin2.rm_col_generated_at'),
          render: (value: any) =>
          <span className="admin-span-13-secondary">
                    {new Date(value).toLocaleString()}
                  </span>

        },
        {
          key: 'actions',
          header: t('admin2.rm_col_actions'),
          align: 'right',
          render: (row: any) =>
          <Button
            type="button"
            size="small"
            variant="outline"
            title={t('admin2.rm_download_report_aria', { filename: row.filename })}
            aria-label={t('admin2.rm_download_report_aria', { filename: row.filename })}
            onClick={() => downloadFile(row.filename)}>
                    <Download aria-hidden="true" className="w-4 h-4" />
                  </Button>

        }]
        }
        data={reports.slice(0, 5) as any[]}
        hoverable={true}
        striped={true} />

        </MacOSCard>
    }
    </div>;


  const renderFilesTab = () =>
  <div className="flex flex-col gap-6">
      <MacOSCard className="admin-card-p-24-bg-card-12-min-h-400">
        <div className="admin-flex-between-mb-24">
          <h3 className="admin-h3-18-600-primary-m0-flex">
            <FileSpreadsheet className="admin-icon-22-mr-10-blue" />
            {t('admin2.rm_files_title')}
          </h3>
          <div className="admin-flex-gap-12">
            <Button
            onClick={loadReportFiles}
            variant="outline"
            size="small"
            className="admin-btn-min-w-100-h-36">

              <RefreshCw className="w-4 h-4 mr-2" />
              {t('admin2.rm_refresh_btn')}
            </Button>
            <Button
            onClick={cleanupOldReports}
            variant="outline"
            size="small"
            className="admin-btn-error-min-w-140-h-36">

              <Trash2 className="w-4 h-4 mr-2" />
              {t('admin2.rm_clean_old_btn')}
            </Button>
          </div>
        </div>

        {files.length === 0 ?
      <div className="admin-flex-center-justify-h-300">
            <MacOSEmptyState
          icon={FileX}
          title={t('admin2.rm_empty_files_title')}
          description={t('admin2.rm_empty_files_desc')} />

          </div> :

      <Table
        columns={[
        {
          key: 'filename',
          header: t('admin2.rm_col_file'),
          render: (value: any) =>
          <div className="admin-flex-center-gap-10">
                    <FileText className="admin-icon-18-tertiary" />
                    <span className="admin-text-med-primary">
                      {value}
                    </span>
                  </div>

        },
        {
          key: 'size',
          header: t('admin2.rm_col_size'),
          render: (value: any) =>
          <span className="admin-span-13-secondary">
                    {formatFileSize(value)}
                  </span>

        },
        {
          key: 'created_at',
          header: t('admin2.rm_col_created'),
          render: (value: any) =>
          <span className="admin-span-13-secondary">
                    {new Date(value).toLocaleString()}
                  </span>

        },
        {
          key: 'actions',
          header: t('admin2.rm_col_actions'),
          align: 'right',
          render: (row: any) =>
          <Button
            type="button"
            size="small"
            variant="ghost"
            title={t('admin2.rm_download_file_aria', { filename: row.filename })}
            aria-label={t('admin2.rm_download_file_aria', { filename: row.filename })}
            onClick={() => downloadFile(row.filename)}>

                    <Download aria-hidden="true" className="admin-icon-18-secondary" />
                  </Button>

        }]
        }
        data={files as any[]}
        hoverable={true}
        striped={true} />

      }
      </MacOSCard>
    </div>;


  const renderSettingsTab = () =>
  <div className="flex flex-col gap-6">
      {/* Автоматические отчеты */}
      <MacOSCard className="admin-card-p-24-bg-card-12">
        <div className="admin-flex-start-16-mb-24">
          <div className="admin-icon-box-56-gradient-blue">
            <Clock className="admin-icon-32-white" />
          </div>
          <div className="admin-flex-1-pt-4">
            <h3 className="admin-h3-18-600-primary-mb-4">
              {t('admin2.rm_auto_reports_title')}
            </h3>
            <p className="admin-p-14-secondary-m0-lh-15">
              {t('admin2.rm_auto_reports_desc')}
            </p>
          </div>
        </div>

        <div className="admin-grid-2col-min-16">
          <Button
          onClick={() => toast.info(t('admin2.rm_schedule_in_dev'))}
          className="admin-btn-blue-h-44-flex-center">

            <Calendar className="w-4.5 h-4.5" />
            {t('admin2.rm_schedule_btn')}
          </Button>

          <Button
          variant="outline"
          onClick={() => toast.info(t('admin2.rm_notifications_in_dev'))}
          className="admin-btn-outline-h-44-flex-center">

            <Activity className="w-4.5 h-4.5" />
            {t('admin2.rm_notifications_btn')}
          </Button>
        </div>
      </MacOSCard>

      {/* Хранение и очистка */}
      <MacOSCard className="admin-card-p-24-bg-card-12">
        <div className="admin-flex-start-16-mb-24">
          <div className="admin-icon-box-56-gradient-green">
            <FileSpreadsheet className="admin-icon-32-white" />
          </div>
          <div className="admin-flex-1-pt-4">
            <h3 className="admin-h3-18-600-primary-mb-4">
              {t('admin2.rm_storage_title')}
            </h3>
            <p className="admin-p-14-secondary-m0-lh-15">
              {t('admin2.rm_storage_desc')}
            </p>
          </div>
        </div>

        <div className="admin-grid-2col-min-16">
          <Button
          onClick={cleanupOldReports}
          className="admin-btn-orange-h-44-flex-center">

            <Trash2 className="w-4.5 h-4.5" />
            {t('admin2.rm_clean_old_files_btn')}
          </Button>

          <Button
          variant="outline"
          onClick={() => toast.info(t('admin2.rm_export_in_dev'))}
          className="admin-btn-outline-h-44-flex-center">

            <Download className="w-4.5 h-4.5" />
            {t('admin2.rm_export_btn')}
          </Button>
        </div>
      </MacOSCard>

      {/* Статистика хранения */}
      <MacOSCard className="admin-card-p-24-bg-card-12">
        <h3 className="admin-h3-18-600-primary-mb-20">{t('admin2.rm_storage_stats_title')}</h3>

        <div className="admin-grid-3col-24">
          <div>
            <div className="admin-stat-label-13-secondary-mb-4">
              {t('admin2.rm_stat_total_files')}
            </div>
            <div className="admin-stat-num-24-600-primary">
              {files.length}
            </div>
          </div>

          <div>
            <div className="admin-stat-label-13-secondary-mb-4">
              {t('admin2.rm_stat_total_size')}
            </div>
            <div className="admin-stat-num-24-600-primary">
              {formatFileSize(files.reduce((sum, f) => sum + (f.size || 0), 0))}
            </div>
          </div>

          <div>
            <div className="admin-stat-label-13-secondary-mb-4">
              {t('admin2.rm_stat_retention_days')}
            </div>
            <div className="admin-stat-num-24-600-primary">
              30
            </div>
          </div>
        </div>
      </MacOSCard>
    </div>;


  return (
    <div className="flex flex-col gap-6">
      {error ?
      <MacOSCard className="admin-card-p-48-flex-justify-center">
          <MacOSEmptyState
          icon={AlertCircle}
          title={t('admin2.rm_error_title')}
          description={t('admin2.rm_error_desc')}>

            <Button onClick={handleRetry} className="mt-4">
              <RefreshCw className="w-4 h-4 mr-2" />
              {t('admin2.rm_retry_btn')}
            </Button>
          </MacOSEmptyState>
        </MacOSCard> :

      <>
          <div className="flex items-center justify-between">
            <h2 className="admin-h2-2xl-bold-primary-m0">{t('admin2.rm_system_title')}</h2>
            <Badge variant="info">
              {t('admin2.rm_files_count', { count: files.length })}
            </Badge>
          </div>

          {/* Табы */}
          <SegmentedControl
          aria-label="Reports sections"
          options={[
          { value: 'generate', label: t('admin2.rm_tab_generate'), icon: BarChart3 },
          { value: 'files', label: t('admin2.rm_tab_files'), icon: FileSpreadsheet },
          { value: 'settings', label: t('admin2.rm_tab_settings'), icon: Settings }]
          }
          value={activeTab}
          onChange={(v: unknown) => setActiveTab(String(v))}
          size="large"
          variant="default" />


          {/* Контент табов */}
          {activeTab === 'generate' && renderGenerateTab()}
          {activeTab === 'files' && renderFilesTab()}
          {activeTab === 'settings' && renderSettingsTab()}
        </>
      }
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog as unknown as React.ReactNode}
    </div>);

};

export default ReportsManager;
