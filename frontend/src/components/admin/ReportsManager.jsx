import { t } from '../../i18n/adapter';
import { useState, useEffect } from 'react';
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
  // P-013 fix: shared ConfirmDialog hook (replaces 1 window.confirm() call).
  const [confirm, confirmDialog] = useConfirm();
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
  });

  // Состояние для быстрых отчетов
  const [quickReports, setQuickReports] = useState({ daily: null });

  useEffect(() => {
    loadAvailableReports();
    loadReportFiles();
    loadQuickReports();
  }, []);

  const loadAvailableReports = async () => {
    try {
      const response = await api.get('/reports/available-reports');
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
      const response = await api.get('/reports/files');
      setFiles(response.data?.files || []);
    } catch (error) {
      logger.error('Ошибка загрузки файлов отчетов:', error);
      setError('Не удалось загрузить файлы'); // Set error state
      setFiles([]);
    }
  };

  const loadQuickReports = async () => {
    try {
      // P1 fix: only daily-summary endpoint exists in backend. Weekly/monthly
      // endpoints do not exist (verified via backend/openapi.json), so the
      // weekly/monthly KPI cards showed a perpetual loading spinner. Removed
      // those cards; this loader now only fetches daily.
      const response = await api.get('/reports/daily-summary');
      setQuickReports((prev) => ({ ...prev, daily: response.data }));
    } catch (error) {
      logger.error('Ошибка загрузки быстрых отчетов:', error);
      setError('Не удалось загрузить статистику');
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
      toast.error('Выберите доступный тип отчёта');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post(`/reports/${endpoint}`, {
        start_date: reportForm.start_date || null,
        end_date: reportForm.end_date || null,
        format: reportForm.format,
        filters: reportForm.filters
      });

      const data = response.data;
      if (data.success) {
        toast.success('Отчет успешно сгенерирован!');
        if (data.filename) {
          // Если есть файл, обновляем список файлов
          loadReportFiles();
        }
        // Показываем результат
        setReports((prev) => [data, ...prev]);
      } else {
        toast.error(data.error || 'Ошибка генерации отчета');
      }
    } catch (error) {
      logger.error('Ошибка генерации отчета:', error);
      toast.error(error.response?.data?.detail || 'Ошибка генерации отчета');
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
      });

      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success('Файл загружен!');
    } catch (error) {
      logger.error('Ошибка загрузки файла:', error);
      toast.error('Ошибка загрузки файла');
    }
  };

  const cleanupOldReports = async () => {
    // P-013 fix: replaced window.confirm() with shared useConfirm hook.
    const ok = await confirm({
      title: t('admin2.clean_reports_title'),
      message: 'Удалить старые файлы отчётов (старше 30 дней)?',
      description: 'Это действие необратимо. Файлы будут удалены навсегда.',
      confirmLabel: t('admin2.delete_confirm'),
      cancelLabel: t('admin2.cancel'),
      intent: 'danger',
    });
    if (!ok) {
      return;
    }

    try {
      const response = await api.post('/reports/cleanup');
      toast.success(response.data?.message || 'Файлы очищены');
      loadReportFiles();
    } catch (error) {
      logger.error('Ошибка очистки файлов:', error);
      toast.error('Ошибка очистки файлов');
    }
  };

  const renderGenerateTab = () =>
  <div className="flex flex-col gap-6">
      {/* Форма генерации отчета */}
      <MacOSCard className="admin-card-p-24-bg-card-12">
        <h3 className="admin-h3-18-600-primary-mb-20">
          <BarChart3 className="admin-icon-20-mr-10-blue" />
          Генерация отчета
        </h3>

        <div className="admin-grid-2col-20-mb-24">
          <div>
            <label className="admin-label-block-13-500-secondary-mb-8">Тип отчета</label>
            <Select
            value={reportForm.type}
            onChange={(value) => setReportForm((prev) => ({ ...prev, type: value }))}
            options={availableReports.map((report) => ({
              value: report.type,
              label: report.name
            }))}
            size="large"
            placeholder="Выберите тип отчета" />

          </div>

          <div>
            <label className="admin-label-block-13-500-secondary-mb-8">Формат</label>
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
            <label className="admin-label-block-13-500-secondary-mb-8">Дата начала</label>
            <Input
            type="date"
            value={reportForm.start_date}
            onChange={(e) => setReportForm((prev) => ({ ...prev, start_date: e.target.value }))} />

          </div>

          <div>
            <label className="admin-label-block-13-500-secondary-mb-8">Дата окончания</label>
            <Input
            type="date"
            value={reportForm.end_date}
            onChange={(e) => setReportForm((prev) => ({ ...prev, end_date: e.target.value }))} />

          </div>
        </div>

        <div className="admin-flex-justify-end">
          <Button
          type="button"
          title={loading ? 'Генерация отчёта' : 'Сгенерировать отчёт'}
          aria-label={loading ? 'Генерация отчёта' : 'Сгенерировать отчёт'}
          onClick={generateReport}
          disabled={loading || !reportForm.type}
          className="admin-btn-blue-w-full-h-44-flex-center admin-opacity-dynamic"
          style={{ '--admin-opacity': loading ? 0.7 : 1 }}>

            {loading ?
          <>
                <Loader2 aria-hidden="true" className="admin-icon-18-spin animate-spin" />
                <span>Генерация...</span>
              </> :

          <>
                <FileText aria-hidden="true" className="w-4.5 h-4.5" />
                <span>Сгенерировать отчет</span>
              </>
          }
          </Button>
        </div>
      </MacOSCard>

      {/* Быстрые отчеты */}
      <MacOSCard className="admin-card-p-24-bg-card-12">
        <h3 className="admin-h3-18-600-primary-mb-20">
          <Clock className="admin-icon-20-mr-10-blue" />
          Быстрые отчеты (сегодня)
        </h3>

        <div className="admin-grid-auto-240-16">
          <MacOSStatCard
          title="Сегодня"
          value={quickReports.daily?.summary?.total_patients_served || 0}
          subtitle={`${quickReports.daily?.summary?.total_revenue || 0} сум`}
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
          <h3 className="admin-h4-lg-semi-primary-mb-16">Последние отчеты</h3>
          <Table
        columns={[
        {
          key: 'type',
          header: 'Тип отчета',
          render: (value) =>
          <span className="admin-text-med-primary">
                    {availableReports.find((r) => r.type === value)?.name || value}
                  </span>

        },
        {
          key: 'generated_at',
          header: 'Дата генерации',
          render: (value) =>
          <span className="admin-span-13-secondary">
                    {new Date(value).toLocaleString()}
                  </span>

        },
        {
          key: 'actions',
          header: 'Действия',
          align: 'right',
          render: (row) =>
          <Button
            type="button"
            size="sm"
            variant="outline"
            title={`Скачать отчёт ${row.filename}`}
            aria-label={`Скачать отчёт ${row.filename}`}
            onClick={() => downloadFile(row.filename)}>
                    <Download aria-hidden="true" className="w-4 h-4" />
                  </Button>

        }]
        }
        data={reports.slice(0, 5)}
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
            Файлы отчетов
          </h3>
          <div className="admin-flex-gap-12">
            <Button
            onClick={loadReportFiles}
            variant="outline"
            size="sm"
            className="admin-btn-min-w-100-h-36">

              <RefreshCw className="w-4 h-4 mr-2" />
              Обновить
            </Button>
            <Button
            onClick={cleanupOldReports}
            variant="outline"
            size="sm"
            className="admin-btn-error-min-w-140-h-36">

              <Trash2 className="w-4 h-4 mr-2" />
              Очистить старые
            </Button>
          </div>
        </div>

        {files.length === 0 ?
      <div className="admin-flex-center-justify-h-300">
            <MacOSEmptyState
          icon={FileX}
          title="Файлы отчетов ещё не сформированы"
          description="Готовые файлы будут отображаться здесь после формирования отчета." />

          </div> :

      <Table
        columns={[
        {
          key: 'filename',
          header: 'Файл',
          render: (value) =>
          <div className="admin-flex-center-gap-10">
                    <FileText className="admin-icon-18-tertiary" />
                    <span className="admin-text-med-primary">
                      {value}
                    </span>
                  </div>

        },
        {
          key: 'size',
          header: 'Размер',
          render: (value) =>
          <span className="admin-span-13-secondary">
                    {formatFileSize(value)}
                  </span>

        },
        {
          key: 'created_at',
          header: 'Создан',
          render: (value) =>
          <span className="admin-span-13-secondary">
                    {new Date(value).toLocaleString()}
                  </span>

        },
        {
          key: 'actions',
          header: 'Действия',
          align: 'right',
          render: (row) =>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            title={`Скачать файл отчёта ${row.filename}`}
            aria-label={`Скачать файл отчёта ${row.filename}`}
            onClick={() => downloadFile(row.filename)}>

                    <Download aria-hidden="true" className="admin-icon-18-secondary" />
                  </Button>

        }]
        }
        data={files}
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
              Автоматические отчеты
            </h3>
            <p className="admin-p-14-secondary-m0-lh-15">
              Настройте автоматическую генерацию и отправку отчетов по расписанию
            </p>
          </div>
        </div>

        <div className="admin-grid-2col-min-16">
          <Button
          onClick={() => toast.info('Функция настройки расписания в разработке')}
          className="admin-btn-blue-h-44-flex-center">

            <Calendar className="w-4.5 h-4.5" />
            Настроить расписание
          </Button>

          <Button
          variant="outline"
          onClick={() => toast.info('Настройки уведомлений в разработке')}
          className="admin-btn-outline-h-44-flex-center">

            <Activity className="w-4.5 h-4.5" />
            Настроить уведомления
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
              Хранение файлов
            </h3>
            <p className="admin-p-14-secondary-m0-lh-15">
              Управление старыми отчетами и настройка их автоматического удаления
            </p>
          </div>
        </div>

        <div className="admin-grid-2col-min-16">
          <Button
          onClick={cleanupOldReports}
          className="admin-btn-orange-h-44-flex-center">

            <Trash2 className="w-4.5 h-4.5" />
            Очистить старые файлы
          </Button>

          <Button
          variant="outline"
          onClick={() => toast.info('Функция экспорта в разработке')}
          className="admin-btn-outline-h-44-flex-center">

            <Download className="w-4.5 h-4.5" />
            Экспорт в облако
          </Button>
        </div>
      </MacOSCard>

      {/* Статистика хранения */}
      <MacOSCard className="admin-card-p-24-bg-card-12">
        <h3 className="admin-h3-18-600-primary-mb-20">Статистика хранения</h3>

        <div className="admin-grid-3col-24">
          <div>
            <div className="admin-stat-label-13-secondary-mb-4">
              Всего файлов
            </div>
            <div className="admin-stat-num-24-600-primary">
              {files.length}
            </div>
          </div>

          <div>
            <div className="admin-stat-label-13-secondary-mb-4">
              Общий размер
            </div>
            <div className="admin-stat-num-24-600-primary">
              {formatFileSize(files.reduce((sum, f) => sum + (f.size || 0), 0))}
            </div>
          </div>

          <div>
            <div className="admin-stat-label-13-secondary-mb-4">
              Хранение (дней)
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
          title="Ошибка загрузки данных"
          description="Не удалось загрузить отчеты. Пожалуйста, попробуйте еще раз.">

            <Button onClick={handleRetry} className="mt-4">
              <RefreshCw className="w-4 h-4 mr-2" />
              Повторить попытку
            </Button>
          </MacOSEmptyState>
        </MacOSCard> :

      <>
          <div className="flex items-center justify-between">
            <h2 className="admin-h2-2xl-bold-primary-m0">Система отчетов</h2>
            <Badge variant="info">
              {files.length} файлов
            </Badge>
          </div>

          {/* Табы */}
          <SegmentedControl
          aria-label="Reports sections"
          options={[
          { value: 'generate', label: 'Генерация', icon: BarChart3 },
          { value: 'files', label: 'Файлы', icon: FileSpreadsheet },
          { value: 'settings', label: 'Настройки', icon: Settings }]
          }
          value={activeTab}
          onChange={setActiveTab}
          size="large"
          variant="default" />


          {/* Контент табов */}
          {activeTab === 'generate' && renderGenerateTab()}
          {activeTab === 'files' && renderFilesTab()}
          {activeTab === 'settings' && renderSettingsTab()}
        </>
      }
      {/* P-013 fix: portal-mounted ConfirmDialog rendered once per panel */}
      {confirmDialog}
    </div>);

};

export default ReportsManager;
