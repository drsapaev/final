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
    <div className="space-y-6">
      {/* Форма генерации отчета */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center">
          <BarChart3 className="w-5 h-5 mr-2" />
          Генерация отчета
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium mb-2">Тип отчета</label>
            <select
              value={reportForm.type}
              onChange={(e) => setReportForm(prev => ({ ...prev, type: e.target.value }))}
              className="w-full p-2 border border-gray-300 rounded-md"
            >
              {availableReports.map(report => (
                <option key={report.type} value={report.type}>
                  {report.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Формат</label>
            <select
              value={reportForm.format}
              onChange={(e) => setReportForm(prev => ({ ...prev, format: e.target.value }))}
              className="w-full p-2 border border-gray-300 rounded-md"
            >
              <option value="json">JSON</option>
              <option value="excel">Excel</option>
              <option value="csv">CSV</option>
              <option value="pdf">PDF</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Дата начала</label>
            <input
              type="date"
              value={reportForm.start_date}
              onChange={(e) => setReportForm(prev => ({ ...prev, start_date: e.target.value }))}
              className="w-full p-2 border border-gray-300 rounded-md"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Дата окончания</label>
            <input
              type="date"
              value={reportForm.end_date}
              onChange={(e) => setReportForm(prev => ({ ...prev, end_date: e.target.value }))}
              className="w-full p-2 border border-gray-300 rounded-md"
            />
          </div>
        </div>

        <Button
          onClick={generateReport}
          disabled={loading}
          className="w-full md:w-auto"
        >
          {loading ? (
            <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
          ) : (
            <FileText className="w-4 h-4 mr-2" />
          )}
          Сгенерировать отчет
        </Button>
      </Card>

      {/* Быстрые отчеты */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center">
          <Clock className="w-5 h-5 mr-2" />
          Быстрые отчеты
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {quickReports.daily && (
            <div className="p-4 bg-blue-50 rounded-lg">
              <h4 className="font-medium text-blue-900 mb-2">Сегодня</h4>
              <div className="space-y-1 text-sm text-blue-700">
                <div>Записи: {quickReports.daily.summary?.total_patients_served || 0}</div>
                <div>Доход: {quickReports.daily.summary?.total_revenue || 0} сум</div>
                <div>Новые пациенты: {quickReports.daily.summary?.new_patients || 0}</div>
              </div>
            </div>
          )}
          
          <div className="p-4 bg-green-50 rounded-lg">
            <h4 className="font-medium text-green-900 mb-2">Эта неделя</h4>
            <div className="space-y-1 text-sm text-green-700">
              <div>Загрузка...</div>
            </div>
          </div>
          
          <div className="p-4 bg-purple-50 rounded-lg">
            <h4 className="font-medium text-purple-900 mb-2">Этот месяц</h4>
            <div className="space-y-1 text-sm text-purple-700">
              <div>Загрузка...</div>
            </div>
          </div>
        </div>
      </Card>

      {/* Последние отчеты */}
      {reports.length > 0 && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4">Последние отчеты</h3>
          <div className="space-y-3">
            {reports.slice(0, 5).map((report, index) => {
              const IconComponent = getReportIcon(report.report_type);
              return (
                <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center">
                    <IconComponent className="w-5 h-5 mr-3 text-gray-600" />
                    <div>
                      <div className="font-medium">{report.report_type}</div>
                      <div className="text-sm text-gray-500">{report.generated_at}</div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Badge variant={report.success ? 'success' : 'error'}>
                      {report.success ? 'Успешно' : 'Ошибка'}
                    </Badge>
                    {report.filename && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => downloadFile(report.filename)}
                      >
                        <Download className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}
    </div>
  );

  const renderFilesTab = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center">
            <FileSpreadsheet className="w-5 h-5 mr-2" />
            Файлы отчетов
          </h3>
          <div className="flex space-x-2">
            <Button
              onClick={loadReportFiles}
              variant="outline"
              size="sm"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Обновить
            </Button>
            <Button
              onClick={cleanupOldReports}
              variant="outline"
              size="sm"
              className="text-red-600 hover:text-red-700"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Очистить старые
            </Button>
          </div>
        </div>

        {files.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <FileX className="w-12 h-12 mx-auto mb-4 text-gray-300" />
            <p>Файлы отчетов не найдены</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2">Файл</th>
                  <th className="text-left py-2">Размер</th>
                  <th className="text-left py-2">Создан</th>
                  <th className="text-left py-2">Изменен</th>
                  <th className="text-right py-2">Действия</th>
                </tr>
              </thead>
              <tbody>
                {files.map((file, index) => (
                  <tr key={index} className="border-b hover:bg-gray-50">
                    <td className="py-3">
                      <div className="flex items-center">
                        <FileText className="w-4 h-4 mr-2 text-gray-500" />
                        <span className="font-medium">{file.filename}</span>
                      </div>
                    </td>
                    <td className="py-3 text-gray-600">
                      {formatFileSize(file.size)}
                    </td>
                    <td className="py-3 text-gray-600">
                      {new Date(file.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 text-gray-600">
                      {new Date(file.modified_at).toLocaleString()}
                    </td>
                    <td className="py-3 text-right">
                      <Button
                        onClick={() => downloadFile(file.filename)}
                        size="sm"
                        variant="outline"
                      >
                        <Download className="w-4 h-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );

  const renderSettingsTab = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center">
          <Settings className="w-5 h-5 mr-2" />
          Настройки отчетов
        </h3>
        
        <div className="space-y-4">
          <div>
            <h4 className="font-medium mb-2">Автоматические отчеты</h4>
            <p className="text-sm text-gray-600 mb-4">
              Настройка автоматической генерации и отправки отчетов
            </p>
            <Button variant="outline">
              Настроить расписание
            </Button>
          </div>
          
          <div>
            <h4 className="font-medium mb-2">Хранение файлов</h4>
            <p className="text-sm text-gray-600 mb-4">
              Управление хранением файлов отчетов
            </p>
            <div className="flex space-x-2">
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
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Система отчетов</h2>
        <Badge variant="info">
          {files.length} файлов
        </Badge>
      </div>

      {/* Табы */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {[
            { id: 'generate', label: 'Генерация', icon: BarChart3 },
            { id: 'files', label: 'Файлы', icon: FileSpreadsheet },
            { id: 'settings', label: 'Настройки', icon: Settings }
          ].map(tab => {
            const IconComponent = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <IconComponent className="w-4 h-4 mr-2" />
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Контент табов */}
      {activeTab === 'generate' && renderGenerateTab()}
      {activeTab === 'files' && renderFilesTab()}
      {activeTab === 'settings' && renderSettingsTab()}
    </div>
  );
};

export default ReportsManager;

