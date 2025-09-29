import React, { useState, useEffect } from 'react';
import { 
  Download, 
  Calendar, 
  BarChart3, 
  PieChart, 
  TrendingUp, 
  Users, 
  DollarSign, 
  FileText,
  Filter,
  RefreshCw,
  Eye,
  Printer
} from 'lucide-react';
import { Card, Button, Badge } from '../ui/native';

const ReportGenerator = ({ 
  onGenerateReport,
  loading = false,
  reportTypes = [],
  dateRange = { start: '', end: '' },
  onDateRangeChange,
  selectedReportType = '',
  onReportTypeChange
}) => {
  const [filters, setFilters] = useState({
    department: '',
    doctor: '',
    status: '',
    paymentMethod: '',
    patientAgeRange: '',
    appointmentType: ''
  });

  const [reportFormat, setReportFormat] = useState('pdf');
  const [includeCharts, setIncludeCharts] = useState(true);
  const [includeDetails, setIncludeDetails] = useState(true);

  const handleFilterChange = (filterName, value) => {
    setFilters(prev => ({
      ...prev,
      [filterName]: value
    }));
  };

  const handleGenerate = () => {
    const reportConfig = {
      type: selectedReportType,
      dateRange,
      filters,
      format: reportFormat,
      includeCharts,
      includeDetails
    };
    
    onGenerateReport(reportConfig);
  };

  const getReportTypeIcon = (type) => {
    const iconMap = {
      'financial': DollarSign,
      'appointments': Calendar,
      'patients': Users,
      'doctors': Users,
      'analytics': BarChart3,
      'revenue': TrendingUp,
      'performance': PieChart
    };
    return iconMap[type] || FileText;
  };

  const getReportTypeLabel = (type) => {
    const labelMap = {
      'financial': 'Финансовый отчет',
      'appointments': 'Отчет по записям',
      'patients': 'Отчет по пациентам',
      'doctors': 'Отчет по врачам',
      'analytics': 'Аналитический отчет',
      'revenue': 'Отчет по доходам',
      'performance': 'Отчет по эффективности'
    };
    return labelMap[type] || type;
  };

  const getReportTypeDescription = (type) => {
    const descMap = {
      'financial': 'Детальный анализ доходов и расходов клиники',
      'appointments': 'Статистика записей, загруженности и эффективности',
      'patients': 'Анализ пациентской базы и демографии',
      'doctors': 'Производительность и загруженность врачей',
      'analytics': 'Общая аналитика и ключевые показатели',
      'revenue': 'Анализ доходов по источникам и периодам',
      'performance': 'KPI и метрики эффективности работы'
    };
    return descMap[type] || 'Отчет по выбранным параметрам';
  };

  return (
    <div className="space-y-6">
      {/* Выбор типа отчета */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
          Тип отчета
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {reportTypes.map((type) => {
            const Icon = getReportTypeIcon(type);
            const isSelected = selectedReportType === type;
            
            return (
              <button
                key={type}
                onClick={() => onReportTypeChange(type)}
                className={`p-4 rounded-lg border-2 transition-all text-left ${
                  isSelected 
                    ? 'border-blue-500 bg-blue-50' 
                    : 'border-gray-200 hover:border-gray-300'
                }`}
                style={{
                  borderColor: isSelected ? 'var(--accent-color)' : 'var(--border-color)',
                  background: isSelected ? 'var(--accent-color-10)' : 'var(--bg-primary)'
                }}
              >
                <div className="flex items-center space-x-3">
                  <Icon className="w-6 h-6" style={{ color: 'var(--accent-color)' }} />
                  <div>
                    <h4 className="font-medium" style={{ color: 'var(--text-primary)' }}>
                      {getReportTypeLabel(type)}
                    </h4>
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                      {getReportTypeDescription(type)}
                    </p>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Период отчета */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
          Период отчета
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
              Дата начала
            </label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                        style={{ color: 'var(--text-tertiary)' }} />
              <input
                type="date"
                value={dateRange.start}
                onChange={(e) => onDateRangeChange({ ...dateRange, start: e.target.value })}
                className="w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                style={{ 
                  border: '1px solid var(--border-color)', 
                  background: 'var(--bg-primary)', 
                  color: 'var(--text-primary)' 
                }}
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
              Дата окончания
            </label>
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4" 
                        style={{ color: 'var(--text-tertiary)' }} />
              <input
                type="date"
                value={dateRange.end}
                onChange={(e) => onDateRangeChange({ ...dateRange, end: e.target.value })}
                className="w-full pl-10 pr-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                style={{ 
                  border: '1px solid var(--border-color)', 
                  background: 'var(--bg-primary)', 
                  color: 'var(--text-primary)' 
                }}
              />
            </div>
          </div>
        </div>
        
        {/* Быстрый выбор периода */}
        <div className="mt-4">
          <p className="text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
            Быстрый выбор:
          </p>
          <div className="flex flex-wrap gap-2">
            {[
              { label: 'Сегодня', days: 0 },
              { label: 'Неделя', days: 7 },
              { label: 'Месяц', days: 30 },
              { label: 'Квартал', days: 90 },
              { label: 'Год', days: 365 }
            ].map(({ label, days }) => {
              const today = new Date();
              const startDate = new Date(today.getTime() - days * 24 * 60 * 60 * 1000);
              const endDate = days === 0 ? today : today;
              
              return (
                <button
                  key={label}
                  onClick={() => onDateRangeChange({
                    start: startDate.toISOString().split('T')[0],
                    end: endDate.toISOString().split('T')[0]
                  })}
                  className="px-3 py-1 text-sm rounded-lg border hover:bg-gray-50"
                  style={{ 
                    borderColor: 'var(--border-color)', 
                    color: 'var(--text-secondary)',
                    background: 'var(--bg-primary)'
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>
      </Card>

      {/* Фильтры */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
          Дополнительные фильтры
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
              Отделение
            </label>
            <select
              value={filters.department}
              onChange={(e) => handleFilterChange('department', e.target.value)}
              className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              style={{ 
                border: '1px solid var(--border-color)', 
                background: 'var(--bg-primary)', 
                color: 'var(--text-primary)' 
              }}
            >
              <option value="">Все отделения</option>
              <option value="cardiology">Кардиология</option>
              <option value="dermatology">Дерматология</option>
              <option value="neurology">Неврология</option>
              <option value="pediatrics">Педиатрия</option>
              <option value="surgery">Хирургия</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
              Статус
            </label>
            <select
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              style={{ 
                border: '1px solid var(--border-color)', 
                background: 'var(--bg-primary)', 
                color: 'var(--text-primary)' 
              }}
            >
              <option value="">Все статусы</option>
              <option value="completed">Завершено</option>
              <option value="pending">Ожидает</option>
              <option value="cancelled">Отменено</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
              Способ оплаты
            </label>
            <select
              value={filters.paymentMethod}
              onChange={(e) => handleFilterChange('paymentMethod', e.target.value)}
              className="w-full px-3 py-2 rounded-lg border focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              style={{ 
                border: '1px solid var(--border-color)', 
                background: 'var(--bg-primary)', 
                color: 'var(--text-primary)' 
              }}
            >
              <option value="">Все способы</option>
              <option value="cash">Наличные</option>
              <option value="card">Карта</option>
              <option value="transfer">Перевод</option>
              <option value="mobile">Мобильный</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Настройки отчета */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
          Настройки отчета
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
              Формат файла
            </label>
            <div className="flex space-x-4">
              {[
                { value: 'pdf', label: 'PDF', icon: FileText },
                { value: 'excel', label: 'Excel', icon: BarChart3 },
                { value: 'csv', label: 'CSV', icon: FileText }
              ].map(({ value, label, icon: Icon }) => (
                <button
                  key={value}
                  onClick={() => setReportFormat(value)}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg border ${
                    reportFormat === value 
                      ? 'border-blue-500 bg-blue-50' 
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  style={{
                    borderColor: reportFormat === value ? 'var(--accent-color)' : 'var(--border-color)',
                    background: reportFormat === value ? 'var(--accent-color-10)' : 'var(--bg-primary)'
                  }}
                >
                  <Icon className="w-4 h-4" />
                  <span style={{ color: 'var(--text-primary)' }}>{label}</span>
                </button>
              ))}
            </div>
          </div>
          
          <div className="space-y-4">
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="includeCharts"
                checked={includeCharts}
                onChange={(e) => setIncludeCharts(e.target.checked)}
                className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
              />
              <label htmlFor="includeCharts" className="text-sm" style={{ color: 'var(--text-primary)' }}>
                Включить графики и диаграммы
              </label>
            </div>
            
            <div className="flex items-center space-x-3">
              <input
                type="checkbox"
                id="includeDetails"
                checked={includeDetails}
                onChange={(e) => setIncludeDetails(e.target.checked)}
                className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
              />
              <label htmlFor="includeDetails" className="text-sm" style={{ color: 'var(--text-primary)' }}>
                Включить детальную информацию
              </label>
            </div>
          </div>
        </div>
      </Card>

      {/* Кнопки действий */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Button
            onClick={handleGenerate}
            disabled={!selectedReportType || loading}
            className="flex items-center space-x-2"
            style={{ 
              background: 'var(--accent-color)',
              color: 'white'
            }}
          >
            {loading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Генерация...</span>
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                <span>Сгенерировать отчет</span>
              </>
            )}
          </Button>
          
          <Button
            variant="outline"
            onClick={() => window.print()}
            disabled={loading}
            className="flex items-center space-x-2"
          >
            <Printer className="w-4 h-4" />
            <span>Печать</span>
          </Button>
        </div>
        
        <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          {selectedReportType && (
            <span>
              Будет сгенерирован: <strong>{getReportTypeLabel(selectedReportType)}</strong>
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export default ReportGenerator;

