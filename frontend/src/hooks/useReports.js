import { useState, useEffect, useCallback } from 'react';

const useReports = () => {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterDateRange, setFilterDateRange] = useState('');

  // Моковые данные для демонстрации
  const mockReports = [
    {
      id: 1,
      name: 'Финансовый отчет за январь 2024',
      type: 'financial',
      status: 'completed',
      createdAt: '2024-02-01T10:00:00Z',
      generatedAt: '2024-02-01T10:05:00Z',
      fileSize: '2.4 MB',
      format: 'pdf',
      dateRange: { start: '2024-01-01', end: '2024-01-31' },
      filters: { department: 'all', status: 'all' },
      downloadCount: 15,
      description: 'Детальный анализ доходов и расходов клиники за январь'
    },
    {
      id: 2,
      name: 'Отчет по записям за неделю',
      type: 'appointments',
      status: 'completed',
      createdAt: '2024-02-05T14:30:00Z',
      generatedAt: '2024-02-05T14:32:00Z',
      fileSize: '1.8 MB',
      format: 'excel',
      dateRange: { start: '2024-01-29', end: '2024-02-04' },
      filters: { department: 'cardiology', status: 'completed' },
      downloadCount: 8,
      description: 'Статистика записей по кардиологическому отделению'
    },
    {
      id: 3,
      name: 'Аналитический отчет Q4 2023',
      type: 'analytics',
      status: 'completed',
      createdAt: '2024-01-15T09:00:00Z',
      generatedAt: '2024-01-15T09:15:00Z',
      fileSize: '5.2 MB',
      format: 'pdf',
      dateRange: { start: '2023-10-01', end: '2023-12-31' },
      filters: { department: 'all', status: 'all' },
      downloadCount: 23,
      description: 'Комплексный аналитический отчет за 4 квартал 2023 года'
    },
    {
      id: 4,
      name: 'Отчет по пациентам за месяц',
      type: 'patients',
      status: 'generating',
      createdAt: '2024-02-10T16:45:00Z',
      generatedAt: null,
      fileSize: null,
      format: 'csv',
      dateRange: { start: '2024-01-01', end: '2024-01-31' },
      filters: { department: 'all', status: 'all' },
      downloadCount: 0,
      description: 'Демографический анализ пациентской базы'
    },
    {
      id: 5,
      name: 'Отчет по доходам за декабрь',
      type: 'revenue',
      status: 'failed',
      createdAt: '2024-01-05T11:20:00Z',
      generatedAt: null,
      fileSize: null,
      format: 'excel',
      dateRange: { start: '2023-12-01', end: '2023-12-31' },
      filters: { department: 'all', status: 'all' },
      downloadCount: 0,
      description: 'Анализ доходов по источникам за декабрь 2023',
      error: 'Ошибка при обработке данных'
    },
    {
      id: 6,
      name: 'Отчет по эффективности врачей',
      type: 'performance',
      status: 'completed',
      createdAt: '2024-02-08T13:15:00Z',
      generatedAt: '2024-02-08T13:18:00Z',
      fileSize: '3.1 MB',
      format: 'pdf',
      dateRange: { start: '2024-01-01', end: '2024-01-31' },
      filters: { department: 'all', status: 'completed' },
      downloadCount: 12,
      description: 'Анализ производительности и KPI врачей'
    }
  ];

  // Загрузка отчетов
  const loadReports = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      setReports(mockReports);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Генерация отчета
  const generateReport = useCallback(async (reportConfig) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const newReport = {
        id: Date.now(),
        name: `${getReportTypeLabel(reportConfig.type)} за ${formatDateRange(reportConfig.dateRange)}`,
        type: reportConfig.type,
        status: 'generating',
        createdAt: new Date().toISOString(),
        generatedAt: null,
        fileSize: null,
        format: reportConfig.format,
        dateRange: reportConfig.dateRange,
        filters: reportConfig.filters,
        downloadCount: 0,
        description: getReportTypeDescription(reportConfig.type)
      };
      
      setReports(prev => [newReport, ...prev]);
      
      // Имитация завершения генерации
      setTimeout(() => {
        setReports(prev => prev.map(report => 
          report.id === newReport.id 
            ? { 
                ...report, 
                status: 'completed',
                generatedAt: new Date().toISOString(),
                fileSize: `${(Math.random() * 5 + 1).toFixed(1)} MB`
              }
            : report
        ));
      }, 3000);
      
      return newReport;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Скачивание отчета
  const downloadReport = useCallback(async (reportId) => {
    try {
      // Имитация скачивания
      const report = reports.find(r => r.id === reportId);
      if (report && report.status === 'completed') {
        // Обновляем счетчик скачиваний
        setReports(prev => prev.map(r => 
          r.id === reportId 
            ? { ...r, downloadCount: r.downloadCount + 1 }
            : r
        ));
        
        // Имитация скачивания файла
        const link = document.createElement('a');
        link.href = `#download-${reportId}`;
        link.download = `${report.name}.${report.format}`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
    } catch (err) {
      setError(err);
      throw err;
    }
  }, [reports]);

  // Удаление отчета
  const deleteReport = useCallback(async (reportId) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      
      setReports(prev => prev.filter(report => report.id !== reportId));
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Повторная генерация отчета
  const regenerateReport = useCallback(async (reportId) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      setReports(prev => prev.map(report => 
        report.id === reportId 
          ? { 
              ...report, 
              status: 'generating',
              generatedAt: null,
              error: null
            }
          : report
      ));
      
      // Имитация завершения генерации
      setTimeout(() => {
        setReports(prev => prev.map(report => 
          report.id === reportId 
            ? { 
                ...report, 
                status: 'completed',
                generatedAt: new Date().toISOString(),
                fileSize: `${(Math.random() * 5 + 1).toFixed(1)} MB`
              }
            : report
        ));
      }, 3000);
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Фильтрация отчетов
  const filteredReports = reports.filter(report => {
    const matchesSearch = !searchTerm || 
      report.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      report.description.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesType = !filterType || report.type === filterType;
    const matchesStatus = !filterStatus || report.status === filterStatus;
    
    const matchesDateRange = !filterDateRange || (() => {
      const reportDate = new Date(report.createdAt);
      const today = new Date();
      
      switch (filterDateRange) {
        case 'today':
          return reportDate.toDateString() === today.toDateString();
        case 'week':
          const weekAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
          return reportDate >= weekAgo;
        case 'month':
          const monthAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
          return reportDate >= monthAgo;
        default:
          return true;
      }
    })();
    
    return matchesSearch && matchesType && matchesStatus && matchesDateRange;
  });

  // Получение статистики отчетов
  const getReportStats = () => {
    const stats = {
      total: reports.length,
      completed: reports.filter(r => r.status === 'completed').length,
      generating: reports.filter(r => r.status === 'generating').length,
      failed: reports.filter(r => r.status === 'failed').length,
      totalDownloads: reports.reduce((sum, r) => sum + r.downloadCount, 0)
    };
    
    return stats;
  };

  // Получение типов отчетов
  const getReportTypes = () => [
    { value: 'financial', label: 'Финансовый отчет' },
    { value: 'appointments', label: 'Отчет по записям' },
    { value: 'patients', label: 'Отчет по пациентам' },
    { value: 'doctors', label: 'Отчет по врачам' },
    { value: 'analytics', label: 'Аналитический отчет' },
    { value: 'revenue', label: 'Отчет по доходам' },
    { value: 'performance', label: 'Отчет по эффективности' }
  ];

  // Вспомогательные функции
  const getReportTypeLabel = (type) => {
    const typeMap = {
      financial: 'Финансовый отчет',
      appointments: 'Отчет по записям',
      patients: 'Отчет по пациентам',
      doctors: 'Отчет по врачам',
      analytics: 'Аналитический отчет',
      revenue: 'Отчет по доходам',
      performance: 'Отчет по эффективности'
    };
    return typeMap[type] || type;
  };

  const getReportTypeDescription = (type) => {
    const descMap = {
      financial: 'Детальный анализ доходов и расходов клиники',
      appointments: 'Статистика записей, загруженности и эффективности',
      patients: 'Анализ пациентской базы и демографии',
      doctors: 'Производительность и загруженность врачей',
      analytics: 'Общая аналитика и ключевые показатели',
      revenue: 'Анализ доходов по источникам и периодам',
      performance: 'KPI и метрики эффективности работы'
    };
    return descMap[type] || 'Отчет по выбранным параметрам';
  };

  const getStatusLabel = (status) => {
    const statusMap = {
      completed: 'Завершен',
      generating: 'Генерируется',
      failed: 'Ошибка',
      pending: 'Ожидает'
    };
    return statusMap[status] || status;
  };

  const getStatusVariant = (status) => {
    const variantMap = {
      completed: 'success',
      generating: 'warning',
      failed: 'error',
      pending: 'info'
    };
    return variantMap[status] || 'secondary';
  };

  const formatDateRange = (dateRange) => {
    if (!dateRange.start || !dateRange.end) return '';
    const start = new Date(dateRange.start).toLocaleDateString('ru-RU');
    const end = new Date(dateRange.end).toLocaleDateString('ru-RU');
    return `${start} - ${end}`;
  };

  // Загрузка при монтировании
  useEffect(() => {
    loadReports();
  }, [loadReports]);

  return {
    reports: filteredReports,
    allReports: reports,
    loading,
    error,
    searchTerm,
    setSearchTerm,
    filterType,
    setFilterType,
    filterStatus,
    setFilterStatus,
    filterDateRange,
    setFilterDateRange,
    generateReport,
    downloadReport,
    deleteReport,
    regenerateReport,
    refresh: loadReports,
    getReportStats,
    getReportTypes,
    getReportTypeLabel,
    getStatusLabel,
    getStatusVariant,
    formatDateRange
  };
};

export default useReports;
