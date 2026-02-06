import React, { useState, useEffect } from 'react';
import {
  FileText,
  Download,
  Calendar,
  Filter,
  BarChart3,
  Users,
  DollarSign,
  Clock,
  Activity,
  Trash2,
  RefreshCw,
  Settings,
  Eye,
  AlertCircle,
  CheckCircle,
  FileSpreadsheet,
  FileX,
  Loader2
} from 'lucide-react';
import { Card, Button, Badge } from '../ui/native';
import {
  MacOSTab,
  MacOSStatCard,
  MacOSTable,
  MacOSInput,
  MacOSSelect,
  MacOSEmptyState,
  MacOSLoadingSkeleton
} from '../ui/macos';
import { toast } from 'react-toastify';

import { api } from '../../api/client';
import logger from '../../utils/logger';

const ReportsManager = () => {
  const [activeTab, setActiveTab] = useState('generate');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null); // Global error state
  const [reports, setReports] = useState([]);
  const [files, setFiles] = useState([]);
  const [availableReports, setAvailableReports] = useState([]);

  // Состояние для генерации отчетов
  const [reportForm, setReportForm] = useState({
    type: 'patient_report',
    format: 'excel',
    start_date: '',
    end_date: '',
    filters: {}
  });

  // Состояние для быстрых отчетов
  const [quickReports, setQuickReports] = useState({
    daily: null,
    weekly: null,
    monthly: null
  });

  useEffect(() => {
    loadAvailableReports();
    loadReportFiles();
    loadQuickReports();
  }, []);

  const loadAvailableReports = async () => {
    try {
      const response = await api.get('/reports/available-reports');
      setAvailableReports(response.data?.reports || []);
    } catch (error) {
      logger.error('Ошибка загрузки доступных отчетов:', error);
      setError('Не удалось загрузить данные'); // Set error state
      // Set default reports if API fails
      setAvailableReports([
        { type: 'patient_report', name: 'Отчет по пациентам' },
        { type: 'appointments_report', name: 'Отчет по записям' },
        { type: 'financial_report', name: 'Финансовый отчет' },
        { type: 'queue_report', name: 'Отчет по очереди' },
        { type: 'doctor_performance_report', name: 'Отчет по врачам' }
      ]);
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
      // Загружаем ежедневную сводку
      const response = await api.get('/reports/daily-summary');
      setQuickReports(prev => ({ ...prev, daily: response.data }));
    } catch (error) {
      logger.error('Ошибка загрузки быстрых отчетов:', error);
      setError('Не удалось загрузить статистику'); // Set error state
      // Set mock data if API fails
      setQuickReports({ daily: null, weekly: null, monthly: null });
    }
  };

  const handleRetry = () => {
    setError(null);
    loadAvailableReports();
    loadReportFiles();
    loadQuickReports();
  };

  const generateReport = async () => {
    setLoading(true);
    try {
      const endpoint = getReportEndpoint(reportForm.type);

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
        setReports(prev => [data, ...prev]);
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

  const getReportEndpoint = (type) => {
    const endpoints = {
      'patient_report': 'patient',
      'appointments_report': 'appointments',
      'financial_report': 'financial',
      'queue_report': 'queue',
      'doctor_performance_report': 'doctor-performance'
    };
    return endpoints[type] || 'patient';
  };

  const getReportIcon = (type) => {
    const icons = {
      'patient_report': Users,
      'appointments_report': Calendar,
      'financial_report': DollarSign,
      'queue_report': Clock,
      'doctor_performance_report': Activity
    };
    return icons[type] || FileText;
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
    if (!window.confirm('Удалить старые файлы отчетов (старше 30 дней)?')) {
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

  const renderGenerateTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Форма генерации отчета */}
      <Card style={{
        padding: '24px',
        background: 'var(--mac-bg-primary)',
        border: '1px solid var(--mac-border-primary)',
        borderRadius: '12px'
      }}>
        <h3 style={{
          fontSize: '18px',
          fontWeight: '600',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          color: 'var(--mac-text-primary)',
          margin: '0 0 20px 0'
        }}>
          <BarChart3 style={{ width: '20px', height: '20px', marginRight: '10px', color: 'var(--mac-accent-blue)' }} />
          Генерация отчета
        </h3>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)', // 2x2 grid as requested
          gap: '20px', // Increased gap
          marginBottom: '24px'
        }}>
          <div>
            <label style={{
              display: 'block',
              fontSize: '13px',
              fontWeight: '500',
              marginBottom: '8px',
              color: 'var(--mac-text-secondary)' // Improved contrast
            }}>Тип отчета</label>
            <MacOSSelect
              value={reportForm.type}
              onChange={(e) => setReportForm(prev => ({ ...prev, type: e.target.value }))}
              options={availableReports.map(report => ({
                value: report.type,
                label: report.name
              }))}
              placeholder="Выберите тип отчета"
            />
          </div>

          <div>
            <label style={{
              display: 'block',
              fontSize: '13px',
              fontWeight: '500',
              marginBottom: '8px',
              color: 'var(--mac-text-secondary)'
            }}>Формат</label>
            <MacOSSelect
              value={reportForm.format}
              onChange={(e) => setReportForm(prev => ({ ...prev, format: e.target.value }))}
              options={[
                { value: 'json', label: 'JSON' },
                { value: 'excel', label: 'Excel' },
                { value: 'csv', label: 'CSV' },
                { value: 'pdf', label: 'PDF' }
              ]}
            />
          </div>

          <div>
            <label style={{
              display: 'block',
              fontSize: '13px',
              fontWeight: '500',
              marginBottom: '8px',
              color: 'var(--mac-text-secondary)'
            }}>Дата начала</label>
            <MacOSInput
              type="date"
              value={reportForm.start_date}
              onChange={(e) => setReportForm(prev => ({ ...prev, start_date: e.target.value }))}
            />
          </div>

          <div>
            <label style={{
              display: 'block',
              fontSize: '13px',
              fontWeight: '500',
              marginBottom: '8px',
              color: 'var(--mac-text-secondary)'
            }}>Дата окончания</label>
            <MacOSInput
              type="date"
              value={reportForm.end_date}
              onChange={(e) => setReportForm(prev => ({ ...prev, end_date: e.target.value }))}
            />
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            onClick={generateReport}
            disabled={loading}
            style={{
              width: '100%',
              height: '44px',
              background: 'var(--mac-accent-blue)',
              color: 'white',
              opacity: loading ? 0.7 : 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px'
            }}
          >
            {loading ? (
              <>
                <Loader2 style={{ width: '18px', height: '18px', animation: 'spin 1s linear infinite' }} className="animate-spin" />
                <span>Генерация...</span>
              </>
            ) : (
              <>
                <FileText style={{ width: '18px', height: '18px' }} />
                <span>Сгенерировать отчет</span>
              </>
            )}
          </Button>
        </div>
      </Card>

      {/* Быстрые отчеты */}
      <Card style={{
        padding: '24px',
        background: 'var(--mac-bg-primary)',
        border: '1px solid var(--mac-border-primary)',
        borderRadius: '12px'
      }}>
        <h3 style={{
          fontSize: '18px',
          fontWeight: '600',
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          color: 'var(--mac-text-primary)',
          margin: '0 0 20px 0'
        }}>
          <Clock style={{ width: '20px', height: '20px', marginRight: '10px', color: 'var(--mac-accent-blue)' }} />
          Быстрые отчеты (сегодня)
        </h3>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '16px'
        }}>
          <MacOSStatCard
            title="Сегодня"
            value={quickReports.daily?.summary?.total_patients_served || 0}
            subtitle={`${quickReports.daily?.summary?.total_revenue || 0} сум`}
            icon={Clock}
            color="blue"
            trend={quickReports.daily ? `+${quickReports.daily.summary?.new_patients || 0}` : undefined}
            trendType={quickReports.daily ? 'positive' : 'neutral'}
            loading={!quickReports.daily}
          />

          <MacOSStatCard
            title="Эта неделя"
            value={quickReports.weekly?.summary?.total_patients_served || 0}
            subtitle={`${quickReports.weekly?.summary?.total_revenue || 0} сум`}
            icon={Calendar}
            color="green"
            trend={quickReports.weekly ? `+${quickReports.weekly.summary?.new_patients || 0}` : undefined}
            trendType={quickReports.weekly ? 'positive' : 'neutral'}
            loading={!quickReports.weekly}
          />

          <MacOSStatCard
            title="Этот месяц"
            value={quickReports.monthly?.summary?.total_patients_served || 0}
            subtitle={`${quickReports.monthly?.summary?.total_revenue || 0} сум`}
            icon={BarChart3}
            color="purple"
            trend={quickReports.monthly ? `+${quickReports.monthly.summary?.new_patients || 0}` : undefined}
            trendType={quickReports.monthly ? 'positive' : 'neutral'}
            loading={!quickReports.monthly}
          />
        </div>
      </Card>

      {/* Последние отчеты */}
      {reports.length > 0 && (
        <Card style={{ padding: '24px' }}>
          <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            marginBottom: '16px',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>Последние отчеты</h3>
          <MacOSTable
            columns={[
              {
                key: 'type',
                header: 'Тип отчета',
                render: (value) => (
                  <span style={{ fontWeight: '500', color: 'var(--mac-text-primary)' }}>
                    {availableReports.find(r => r.type === value)?.name || value}
                  </span>
                )
              },
              {
                key: 'generated_at',
                header: 'Дата генерации',
                render: (value) => (
                  <span style={{ color: 'var(--mac-text-secondary)', fontSize: '13px' }}>
                    {new Date(value).toLocaleString()}
                  </span>
                )
              },
              {
                key: 'actions',
                header: 'Действия',
                align: 'right',
                render: (row) => (
                  <Button size="sm" variant="outline" onClick={() => downloadFile(row.filename)}>
                    <Download style={{ width: '16px', height: '16px' }} />
                  </Button>
                )
              }
            ]}
            data={reports.slice(0, 5)}
            hoverable={true}
            striped={true}
          />
        </Card>
      )}
    </div>
  );

  const renderFilesTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card style={{
        padding: '24px',
        background: 'var(--mac-bg-primary)',
        border: '1px solid var(--mac-border-primary)',
        borderRadius: '12px',
        minHeight: '400px' // Ensure card has some height even when empty
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <h3 style={{
            fontSize: '18px',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
            <FileSpreadsheet style={{ width: '22px', height: '22px', marginRight: '10px', color: 'var(--mac-accent-blue)' }} />
            Файлы отчетов
          </h3>
          <div style={{ display: 'flex', gap: '12px' }}>
            <Button
              onClick={loadReportFiles}
              variant="outline"
              size="sm"
              style={{ minWidth: '100px', height: '36px' }}
            >
              <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Обновить
            </Button>
            <Button
              onClick={cleanupOldReports}
              variant="outline"
              size="sm"
              style={{ color: 'var(--mac-error)', minWidth: '140px', height: '36px', borderColor: 'var(--mac-error)' }}
            >
              <Trash2 style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Очистить старые
            </Button>
          </div>
        </div>

        {files.length === 0 ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '300px' }}>
            <MacOSEmptyState
              icon={FileX}
              title="Файлы отчетов не найдены"
              description="Сгенерированные отчеты появятся здесь"
            />
          </div>
        ) : (
          <MacOSTable
            columns={[
              {
                key: 'filename',
                header: 'Файл',
                render: (value) => (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <FileText style={{ width: '18px', height: '18px', color: 'var(--mac-text-tertiary)' }} />
                    <span style={{ fontWeight: '500', color: 'var(--mac-text-primary)' }}>
                      {value}
                    </span>
                  </div>
                )
              },
              {
                key: 'size',
                header: 'Размер',
                render: (value) => (
                  <span style={{ color: 'var(--mac-text-secondary)', fontSize: '13px' }}>
                    {formatFileSize(value)}
                  </span>
                )
              },
              {
                key: 'created_at',
                header: 'Создан',
                render: (value) => (
                  <span style={{ color: 'var(--mac-text-secondary)', fontSize: '13px' }}>
                    {new Date(value).toLocaleString()}
                  </span>
                )
              },
              {
                key: 'actions',
                header: 'Действия',
                align: 'right',
                render: (row) => (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => downloadFile(row.filename)}
                  >
                    <Download style={{ width: '18px', height: '18px', color: 'var(--mac-text-secondary)' }} />
                  </Button>
                )
              }
            ]}
            data={files}
            hoverable={true}
            striped={true}
          />
        )}
      </Card>
    </div>
  );

  const renderSettingsTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Автоматические отчеты */}
      <Card style={{
        padding: '24px',
        background: 'var(--mac-bg-primary)',
        border: '1px solid var(--mac-border-primary)',
        borderRadius: '12px'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '16px',
          marginBottom: '24px'
        }}>
          <div style={{
            width: '56px', // Increased size
            height: '56px', // Increased size
            borderRadius: '14px',
            background: 'linear-gradient(135deg, var(--mac-accent-blue) 0%, #5856D6 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            boxShadow: '0 4px 12px rgba(0, 122, 255, 0.2)'
          }}>
            <Clock style={{ width: '32px', height: '32px', color: 'white' }} />
          </div>
          <div style={{ flex: 1, paddingTop: '4px' }}>
            <h3 style={{
              fontSize: '18px',
              fontWeight: '600',
              color: 'var(--mac-text-primary)',
              margin: '0 0 4px 0'
            }}>
              Автоматические отчеты
            </h3>
            <p style={{
              fontSize: '14px',
              color: 'var(--mac-text-secondary)',
              margin: 0,
              lineHeight: 1.5
            }}>
              Настройте автоматическую генерацию и отправку отчетов по расписанию
            </p>
          </div>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', // Equal width columns
          gap: '16px'
        }}>
          <Button
            onClick={() => toast.info('Функция настройки расписания в разработке')}
            style={{
              height: '44px',
              background: 'var(--mac-accent-blue)',
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              fontSize: '14px',
              fontWeight: '500'
            }}
          >
            <Calendar style={{ width: '18px', height: '18px' }} />
            Настроить расписание
          </Button>

          <Button
            variant="outline"
            onClick={() => toast.info('Настройки уведомлений в разработке')}
            style={{
              height: '44px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              fontSize: '14px',
              fontWeight: '500',
              color: 'var(--mac-text-primary)',
              border: '1px solid var(--mac-border-primary)',
              background: 'var(--mac-bg-secondary)'
            }}
          >
            <Activity style={{ width: '18px', height: '18px' }} />
            Настроить уведомления
          </Button>
        </div>
      </Card>

      {/* Хранение и очистка */}
      <Card style={{
        padding: '24px',
        background: 'var(--mac-bg-primary)',
        border: '1px solid var(--mac-border-primary)',
        borderRadius: '12px'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '16px',
          marginBottom: '24px'
        }}>
          <div style={{
            width: '56px',
            height: '56px',
            borderRadius: '14px',
            background: 'linear-gradient(135deg, var(--mac-accent-green) 0%, #34C759 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            boxShadow: '0 4px 12px rgba(52, 199, 89, 0.2)'
          }}>
            <FileSpreadsheet style={{ width: '32px', height: '32px', color: 'white' }} />
          </div>
          <div style={{ flex: 1, paddingTop: '4px' }}>
            <h3 style={{
              fontSize: '18px',
              fontWeight: '600',
              color: 'var(--mac-text-primary)',
              margin: '0 0 4px 0'
            }}>
              Хранение файлов
            </h3>
            <p style={{
              fontSize: '14px',
              color: 'var(--mac-text-secondary)',
              margin: 0,
              lineHeight: 1.5
            }}>
              Управление старыми отчетами и настройка их автоматического удаления
            </p>
          </div>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)',
          gap: '16px'
        }}>
          <Button
            onClick={cleanupOldReports}
            style={{
              height: '44px',
              background: '#FF9500', // Explicit hex for visibility
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              fontSize: '14px',
              fontWeight: '500',
              border: 'none'
            }}
          >
            <Trash2 style={{ width: '18px', height: '18px' }} />
            Очистить старые файлы
          </Button>

          <Button
            variant="outline"
            onClick={() => toast.info('Функция экспорта в разработке')}
            style={{
              height: '44px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              fontSize: '14px',
              fontWeight: '500',
              color: 'var(--mac-text-primary)',
              border: '1px solid var(--mac-border-primary)',
              background: 'var(--mac-bg-secondary)'
            }}
          >
            <Download style={{ width: '18px', height: '18px' }} />
            Экспорт в облако
          </Button>
        </div>
      </Card>

      {/* Статистика хранения */}
      <Card style={{
        padding: '24px',
        background: 'var(--mac-bg-primary)',
        border: '1px solid var(--mac-border-primary)',
        borderRadius: '12px'
      }}>
        <h3 style={{
          fontSize: '18px',
          fontWeight: '600',
          marginBottom: '20px',
          color: 'var(--mac-text-primary)',
          margin: '0 0 20px 0'
        }}>Статистика хранения</h3>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: '24px'
        }}>
          <div>
            <div style={{ fontSize: '13px', color: 'var(--mac-text-secondary)', marginBottom: '4px' }}>
              Всего файлов
            </div>
            <div style={{ fontSize: '24px', fontWeight: '600', color: 'var(--mac-text-primary)' }}>
              {files.length}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '13px', color: 'var(--mac-text-secondary)', marginBottom: '4px' }}>
              Общий размер
            </div>
            <div style={{ fontSize: '24px', fontWeight: '600', color: 'var(--mac-text-primary)' }}>
              {formatFileSize(files.reduce((sum, f) => sum + (f.size || 0), 0))}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '13px', color: 'var(--mac-text-secondary)', marginBottom: '4px' }}>
              Хранение (дней)
            </div>
            <div style={{ fontSize: '24px', fontWeight: '600', color: 'var(--mac-text-primary)' }}>
              30
            </div>
          </div>
        </div>
      </Card>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {error ? (
        <Card style={{ padding: '48px', display: 'flex', justifyContent: 'center' }}>
          <MacOSEmptyState
            icon={AlertCircle}
            title="Ошибка загрузки данных"
            description="Не удалось загрузить отчеты. Пожалуйста, попробуйте еще раз."
          >
            <Button onClick={handleRetry} style={{ marginTop: '16px' }}>
              <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Повторить попытку
            </Button>
          </MacOSEmptyState>
        </Card>
      ) : (
        <>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{
              fontSize: 'var(--mac-font-size-2xl)',
              fontWeight: 'var(--mac-font-weight-bold)',
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>Система отчетов</h2>
            <Badge variant="info">
              {files.length} файлов
            </Badge>
          </div>

          {/* Табы */}
          <MacOSTab
            tabs={[
              { id: 'generate', label: 'Генерация', icon: BarChart3 },
              { id: 'files', label: 'Файлы', icon: FileSpreadsheet },
              { id: 'settings', label: 'Настройки', icon: Settings }
            ]}
            activeTab={activeTab}
            onTabChange={setActiveTab}
            size="md"
            variant="default"
          />

          {/* Контент табов */}
          {activeTab === 'generate' && renderGenerateTab()}
          {activeTab === 'files' && renderFilesTab()}
          {activeTab === 'settings' && renderSettingsTab()}
        </>
      )}
    </div>
  );
};

export default ReportsManager;
