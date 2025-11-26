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
  FileX
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

const ReportsManager = () => {
  const [activeTab, setActiveTab] = useState('generate');
  const [loading, setLoading] = useState(false);
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
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/reports/available-reports', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setAvailableReports(data.reports || []);
      }
    } catch (error) {
      console.error('Ошибка загрузки доступных отчетов:', error);
    }
  };

  const loadReportFiles = async () => {
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/reports/files', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setFiles(data.files || []);
      }
    } catch (error) {
      console.error('Ошибка загрузки файлов отчетов:', error);
    }
  };

  const loadQuickReports = async () => {
    try {
      const token = localStorage.getItem('access_token');
      
      // Загружаем ежедневную сводку
      const dailyResponse = await fetch('/api/v1/reports/daily-summary', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (dailyResponse.ok) {
        const dailyData = await dailyResponse.json();
        setQuickReports(prev => ({ ...prev, daily: dailyData }));
      }
    } catch (error) {
      console.error('Ошибка загрузки быстрых отчетов:', error);
    }
  };

  const generateReport = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const endpoint = getReportEndpoint(reportForm.type);
      
      const response = await fetch(`/api/v1/reports/${endpoint}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          start_date: reportForm.start_date || null,
          end_date: reportForm.end_date || null,
          format: reportForm.format,
          filters: reportForm.filters
        })
      });

      if (response.ok) {
        const data = await response.json();
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
      } else {
        toast.error('Ошибка генерации отчета');
      }
    } catch (error) {
      console.error('Ошибка генерации отчета:', error);
      toast.error('Ошибка генерации отчета');
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
      const token = localStorage.getItem('access_token');
      const response = await fetch(`/api/v1/reports/download/${filename}`, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        toast.success('Файл загружен!');
      } else {
        toast.error('Ошибка загрузки файла');
      }
    } catch (error) {
      console.error('Ошибка загрузки файла:', error);
      toast.error('Ошибка загрузки файла');
    }
  };

  const cleanupOldReports = async () => {
    if (!window.confirm('Удалить старые файлы отчетов (старше 30 дней)?')) {
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('/api/v1/reports/cleanup', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        toast.success(data.message);
        loadReportFiles();
      } else {
        toast.error('Ошибка очистки файлов');
      }
    } catch (error) {
      console.error('Ошибка очистки файлов:', error);
      toast.error('Ошибка очистки файлов');
    }
  };

  const renderGenerateTab = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Форма генерации отчета */}
      <Card style={{ padding: '24px' }}>
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)', 
          fontWeight: 'var(--mac-font-weight-semibold)', 
          marginBottom: '16px', 
          display: 'flex', 
          alignItems: 'center',
          color: 'var(--mac-text-primary)',
          margin: 0
        }}>
          <BarChart3 style={{ width: '20px', height: '20px', marginRight: '8px', color: 'var(--mac-accent-blue)' }} />
          Генерация отчета
        </h3>
        
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px', 
          marginBottom: '16px' 
        }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              marginBottom: '8px',
              color: 'var(--mac-text-primary)'
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
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              marginBottom: '8px',
              color: 'var(--mac-text-primary)'
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
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              marginBottom: '8px',
              color: 'var(--mac-text-primary)'
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
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              marginBottom: '8px',
              color: 'var(--mac-text-primary)'
            }}>Дата окончания</label>
            <MacOSInput
              type="date"
              value={reportForm.end_date}
              onChange={(e) => setReportForm(prev => ({ ...prev, end_date: e.target.value }))}
            />
          </div>
        </div>

        <Button
          onClick={generateReport}
          disabled={loading}
          style={{ width: '100%', maxWidth: '200px' }}
        >
          {loading ? (
            <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
          ) : (
            <FileText style={{ width: '16px', height: '16px', marginRight: '8px' }} />
          )}
          Сгенерировать отчет
        </Button>
      </Card>

      {/* Быстрые отчеты */}
      <Card style={{ padding: '24px' }}>
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)', 
          fontWeight: 'var(--mac-font-weight-semibold)', 
          marginBottom: '16px', 
          display: 'flex', 
          alignItems: 'center',
          color: 'var(--mac-text-primary)',
          margin: 0
        }}>
          <Clock style={{ width: '20px', height: '20px', marginRight: '8px', color: 'var(--mac-accent-blue)' }} />
          Быстрые отчеты
        </h3>
        
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', 
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
                key: 'report_type',
                title: 'Тип отчета',
                render: (value, row) => (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {React.createElement(getReportIcon(row.report_type), {
                      style: { width: '16px', height: '16px', color: 'var(--mac-text-tertiary)' }
                    })}
                    <span style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>
                      {value}
                    </span>
                  </div>
                )
              },
              {
                key: 'generated_at',
                title: 'Дата генерации',
                render: (value) => (
                  <span style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
                    {value}
                  </span>
                )
              },
              {
                key: 'status',
                title: 'Статус',
                render: (_, row) => (
                  <Badge variant={row.success ? 'success' : 'error'}>
                    {row.success ? 'Успешно' : 'Ошибка'}
                  </Badge>
                )
              },
              {
                key: 'actions',
                title: 'Действия',
                align: 'right',
                render: (_, row) => (
                  row.filename ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => downloadFile(row.filename)}
                    >
                      <Download style={{ width: '16px', height: '16px' }} />
                    </Button>
                  ) : null
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
      <Card style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            display: 'flex', 
            alignItems: 'center',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
            <FileSpreadsheet style={{ width: '20px', height: '20px', marginRight: '8px', color: 'var(--mac-accent-blue)' }} />
            Файлы отчетов
          </h3>
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button
              onClick={loadReportFiles}
              variant="outline"
              size="sm"
            >
              <RefreshCw style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Обновить
            </Button>
            <Button
              onClick={cleanupOldReports}
              variant="outline"
              size="sm"
              style={{ color: 'var(--mac-error)' }}
            >
              <Trash2 style={{ width: '16px', height: '16px', marginRight: '8px' }} />
              Очистить старые
            </Button>
          </div>
        </div>

        {files.length === 0 ? (
          <MacOSEmptyState
            icon={FileX}
            title="Файлы отчетов не найдены"
            description="Сгенерируйте первый отчет, чтобы увидеть файлы здесь"
          />
        ) : (
          <MacOSTable
            columns={[
              {
                key: 'filename',
                title: 'Файл',
                render: (value, row) => (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <FileText style={{ width: '16px', height: '16px', color: 'var(--mac-text-tertiary)' }} />
                    <span style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>
                      {value}
                    </span>
                  </div>
                )
              },
              {
                key: 'size',
                title: 'Размер',
                render: (value) => (
                  <span style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
                    {formatFileSize(value)}
                  </span>
                )
              },
              {
                key: 'created_at',
                title: 'Создан',
                render: (value) => (
                  <span style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
                    {new Date(value).toLocaleString()}
                  </span>
                )
              },
              {
                key: 'modified_at',
                title: 'Изменен',
                render: (value) => (
                  <span style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
                    {new Date(value).toLocaleString()}
                  </span>
                )
              },
              {
                key: 'actions',
                title: 'Действия',
                align: 'right',
                render: (_, row) => (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => downloadFile(row.filename)}
                  >
                    <Download style={{ width: '16px', height: '16px' }} />
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
      <Card style={{ padding: '24px' }}>
        <h3 style={{ 
          fontSize: 'var(--mac-font-size-lg)', 
          fontWeight: 'var(--mac-font-weight-semibold)', 
          marginBottom: '16px', 
          display: 'flex', 
          alignItems: 'center',
          color: 'var(--mac-text-primary)',
          margin: 0
        }}>
          <Settings style={{ width: '20px', height: '20px', marginRight: '8px', color: 'var(--mac-accent-blue)' }} />
          Настройки отчетов
        </h3>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <h4 style={{ 
              fontSize: 'var(--mac-font-size-base)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              marginBottom: '8px',
              color: 'var(--mac-text-primary)'
            }}>Автоматические отчеты</h4>
            <p style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)', 
              marginBottom: '16px',
              margin: 0
            }}>
              Настройка автоматической генерации и отправки отчетов
            </p>
            <Button variant="outline">
              Настроить расписание
            </Button>
          </div>
          
          <div>
            <h4 style={{ 
              fontSize: 'var(--mac-font-size-base)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              marginBottom: '8px',
              color: 'var(--mac-text-primary)'
            }}>Хранение файлов</h4>
            <p style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              color: 'var(--mac-text-secondary)', 
              marginBottom: '16px',
              margin: 0
            }}>
              Управление хранением файлов отчетов
            </p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <Button variant="outline" size="sm">
                Настроить очистку
              </Button>
              <Button variant="outline" size="sm">
                Экспорт в облако
              </Button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
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
    </div>
  );
};

export default ReportsManager;

