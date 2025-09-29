import React, { useState } from 'react';
import { Card, Button } from '../ui/native';
import { 
  Download, 
  FileText, 
  FileSpreadsheet, 
  FileImage, 
  Mail,
  Share2,
  Settings,
  CheckCircle,
  AlertCircle,
  Clock,
  BarChart3,
  PieChart,
  TrendingUp
} from 'lucide-react';

/**
 * Компонент для экспорта аналитических данных
 * Поддерживает множественные форматы и настройки
 */
const DataExporter = ({ 
  data, 
  onExport,
  availableFormats = ['json', 'csv', 'xlsx', 'pdf'],
  showAdvanced = true
}) => {
  const [selectedFormat, setSelectedFormat] = useState('json');
  const [selectedData, setSelectedData] = useState('all');
  const [includeCharts, setIncludeCharts] = useState(true);
  const [includeRawData, setIncludeRawData] = useState(true);
  const [emailExport, setEmailExport] = useState(false);
  const [emailAddress, setEmailAddress] = useState('');
  const [isExporting, setIsExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState(null);

  const formatOptions = [
    { 
      id: 'json', 
      label: 'JSON', 
      icon: FileText, 
      description: 'Структурированные данные',
      color: 'blue'
    },
    { 
      id: 'csv', 
      label: 'CSV', 
      icon: FileSpreadsheet, 
      description: 'Табличные данные',
      color: 'green'
    },
    { 
      id: 'xlsx', 
      label: 'Excel', 
      icon: FileSpreadsheet, 
      description: 'Расширенная таблица',
      color: 'green'
    },
    { 
      id: 'pdf', 
      label: 'PDF', 
      icon: FileImage, 
      description: 'Документ с графиками',
      color: 'red'
    }
  ];

  const dataOptions = [
    { id: 'all', label: 'Все данные', description: 'Полный набор аналитики' },
    { id: 'kpi', label: 'KPI метрики', description: 'Ключевые показатели' },
    { id: 'revenue', label: 'Доходы', description: 'Финансовая аналитика' },
    { id: 'patients', label: 'Пациенты', description: 'Данные о пациентах' },
    { id: 'appointments', label: 'Записи', description: 'Расписание и записи' },
    { id: 'doctors', label: 'Врачи', description: 'Производительность врачей' }
  ];

  const handleExport = async () => {
    if (!data) {
      setExportStatus({ type: 'error', message: 'Нет данных для экспорта' });
      return;
    }

    setIsExporting(true);
    setExportStatus({ type: 'info', message: 'Подготовка данных...' });

    try {
      const exportConfig = {
        format: selectedFormat,
        dataType: selectedData,
        includeCharts,
        includeRawData,
        emailExport,
        emailAddress: emailExport ? emailAddress : null
      };

      const result = await onExport(exportConfig);
      
      if (result.success) {
        setExportStatus({ 
          type: 'success', 
          message: `Данные успешно экспортированы в формате ${selectedFormat.toUpperCase()}` 
        });
      } else {
        setExportStatus({ 
          type: 'error', 
          message: result.error || 'Ошибка при экспорте данных' 
        });
      }
    } catch (error) {
      setExportStatus({ 
        type: 'error', 
        message: 'Произошла ошибка при экспорте' 
      });
    } finally {
      setIsExporting(false);
    }
  };

  const getFormatIcon = (format) => {
    const IconComponent = formatOptions.find(f => f.id === format)?.icon || FileText;
    return <IconComponent className="w-5 h-5" />;
  };

  const getStatusIcon = () => {
    if (!exportStatus) return null;
    
    switch (exportStatus.type) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'info':
        return <Clock className="w-5 h-5 text-blue-500" />;
      default:
        return null;
    }
  };

  const getStatusColor = () => {
    if (!exportStatus) return '';
    
    switch (exportStatus.type) {
      case 'success':
        return 'text-green-600 bg-green-50 border-green-200';
      case 'error':
        return 'text-red-600 bg-red-50 border-red-200';
      case 'info':
        return 'text-blue-600 bg-blue-50 border-blue-200';
      default:
        return '';
    }
  };

  return (
    <Card className="p-6">
      <div className="space-y-6">
        {/* Заголовок */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold">Экспорт данных</h3>
            <p className="text-sm text-gray-600">
              Выберите формат и настройки для экспорта аналитики
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              <Settings className="w-4 h-4 mr-2" />
              Настройки
            </Button>
          </div>
        </div>

        {/* Форматы экспорта */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Формат экспорта
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {formatOptions
              .filter(format => availableFormats.includes(format.id))
              .map(format => (
                <button
                  key={format.id}
                  onClick={() => setSelectedFormat(format.id)}
                  className={`p-3 border rounded-lg text-left transition-all ${
                    selectedFormat === format.id
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center space-x-2 mb-1">
                    <format.icon className="w-4 h-4" />
                    <span className="font-medium">{format.label}</span>
                  </div>
                  <p className="text-xs text-gray-600">{format.description}</p>
                </button>
              ))}
          </div>
        </div>

        {/* Тип данных */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            Данные для экспорта
          </label>
          <select
            value={selectedData}
            onChange={(e) => setSelectedData(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {dataOptions.map(option => (
              <option key={option.id} value={option.id}>
                {option.label} - {option.description}
              </option>
            ))}
          </select>
        </div>

        {/* Дополнительные настройки */}
        {showAdvanced && (
          <div className="space-y-4 p-4 bg-gray-50 rounded-lg">
            <h4 className="font-medium text-gray-900">Дополнительные настройки</h4>
            
            <div className="space-y-3">
              <label className="flex items-center space-x-3">
                <input
                  type="checkbox"
                  checked={includeCharts}
                  onChange={(e) => setIncludeCharts(e.target.checked)}
                  className="rounded"
                />
                <div>
                  <span className="text-sm font-medium">Включить графики</span>
                  <p className="text-xs text-gray-600">Добавить визуализации в экспорт</p>
                </div>
              </label>

              <label className="flex items-center space-x-3">
                <input
                  type="checkbox"
                  checked={includeRawData}
                  onChange={(e) => setIncludeRawData(e.target.checked)}
                  className="rounded"
                />
                <div>
                  <span className="text-sm font-medium">Включить исходные данные</span>
                  <p className="text-xs text-gray-600">Добавить необработанные данные</p>
                </div>
              </label>

              <label className="flex items-center space-x-3">
                <input
                  type="checkbox"
                  checked={emailExport}
                  onChange={(e) => setEmailExport(e.target.checked)}
                  className="rounded"
                />
                <div>
                  <span className="text-sm font-medium">Отправить по email</span>
                  <p className="text-xs text-gray-600">Получить файл на почту</p>
                </div>
              </label>

              {emailExport && (
                <div className="ml-6">
                  <input
                    type="email"
                    value={emailAddress}
                    onChange={(e) => setEmailAddress(e.target.value)}
                    placeholder="Введите email адрес"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Статус экспорта */}
        {exportStatus && (
          <div className={`p-3 rounded-lg border ${getStatusColor()}`}>
            <div className="flex items-center space-x-2">
              {getStatusIcon()}
              <span className="text-sm font-medium">{exportStatus.message}</span>
            </div>
          </div>
        )}

        {/* Кнопка экспорта */}
        <div className="flex items-center justify-between pt-4 border-t border-gray-200">
          <div className="text-sm text-gray-600">
            {isExporting ? 'Экспорт в процессе...' : 'Готово к экспорту'}
          </div>
          <Button
            onClick={handleExport}
            disabled={isExporting || !data}
            className="flex items-center space-x-2"
          >
            {isExporting ? (
              <Clock className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            <span>
              {isExporting ? 'Экспорт...' : `Экспорт в ${selectedFormat.toUpperCase()}`}
            </span>
          </Button>
        </div>
      </div>
    </Card>
  );
};

export default DataExporter;

