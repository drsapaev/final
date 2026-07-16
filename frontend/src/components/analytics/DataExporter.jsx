import { useState } from 'react';
import { Card, Button,
  Input,
  Checkbox } from '../ui/macos';
import {
  Download,
  FileText,
  FileSpreadsheet,
  FileImage,


  Settings,
  CheckCircle,
  AlertCircle,
  Clock } from



'lucide-react';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';

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
  const [showAdvancedPanel, setShowAdvancedPanel] = useState(showAdvanced);

  const { t } = useTranslation();

  const formatOptions = [
  {
    id: 'json',
    label: 'JSON',
    icon: FileText,
    description: t('misc.de_format_json_desc'),
    color: 'blue'
  },
  {
    id: 'csv',
    label: 'CSV',
    icon: FileSpreadsheet,
    description: t('misc.de_format_csv_desc'),
    color: 'green'
  },
  {
    id: 'xlsx',
    label: 'Excel',
    icon: FileSpreadsheet,
    description: t('misc.de_format_xlsx_desc'),
    color: 'green'
  },
  {
    id: 'pdf',
    label: 'PDF',
    icon: FileImage,
    description: t('misc.de_format_pdf_desc'),
    color: 'red'
  }];


  const dataOptions = [
  { id: 'all', label: t('misc.de_data_all_label'), description: t('misc.de_data_all_desc') },
  { id: 'kpi', label: t('misc.de_data_kpi_label'), description: t('misc.de_data_kpi_desc') },
  { id: 'revenue', label: t('misc.de_data_revenue_label'), description: t('misc.de_data_revenue_desc') },
  { id: 'patients', label: t('misc.de_data_patients_label'), description: t('misc.de_data_patients_desc') },
  { id: 'appointments', label: t('misc.de_data_appointments_label'), description: t('misc.de_data_appointments_desc') },
  { id: 'doctors', label: t('misc.de_data_doctors_label'), description: t('misc.de_data_doctors_desc') }];


  const handleExport = async () => {
    if (!data) {
      setExportStatus({ type: 'error', message: t('misc.de_no_data') });
      return;
    }

    setIsExporting(true);
    setExportStatus({ type: 'info', message: t('misc.de_preparing') });

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
          message: t('misc.de_export_success', { format: selectedFormat.toUpperCase() })
        });
      } else {
        setExportStatus({
          type: 'error',
          message: result.error || t('misc.de_export_error')
        });
      }
    } catch {
      setExportStatus({
        type: 'error',
        message: t('misc.de_export_failed')
      });
    } finally {
      setIsExporting(false);
    }
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
            <h3 className="text-lg font-semibold">{t('misc.de_title')}</h3>
            <p className="text-sm text-gray-600">
              {t('misc.de_subtitle')}
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowAdvancedPanel((prev) => !prev)}>

              <Settings className="w-4 h-4 mr-2" />
              {t('misc.de_settings_button')}
            </Button>
          </div>
        </div>

        {/* Форматы экспорта */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            {t('misc.de_format_label')}
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {formatOptions.
            filter((format) => availableFormats.includes(format.id)).
            map((format) =>
            <button
              key={format.id}
              onClick={() => setSelectedFormat(format.id)}
              className={`p-3 border rounded-lg text-left transition-all ${
              selectedFormat === format.id ?
              'border-blue-500 bg-blue-50 text-blue-700' :
              'border-gray-200 hover:border-gray-300'}`
              }>
              
                  <div className="flex items-center space-x-2 mb-1">
                    <format.icon className="w-4 h-4" />
                    <span className="font-medium">{format.label}</span>
                  </div>
                  <p className="text-xs text-gray-600">{format.description}</p>
                </button>
            )}
          </div>
        </div>

        {/* Тип данных */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-3">
            {t('misc.de_data_label')}
          </label>
          <select
            value={selectedData}
            onChange={(e) => setSelectedData(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
            
            {dataOptions.map((option) =>
            <option key={option.id} value={option.id}>
                {option.label} - {option.description}
              </option>
            )}
          </select>
        </div>

        {/* Дополнительные настройки */}
        {showAdvancedPanel &&
        <div className="space-y-4 p-4 bg-gray-50 rounded-lg">
            <h4 className="font-medium text-gray-900">{t('misc.de_advanced_title')}</h4>
            
            <div className="space-y-3">
              <label className="flex items-center space-x-3">
                <Checkbox aria-label="Include charts in export" checked={includeCharts} onChange={(e) => setIncludeCharts(e.target.checked)}
                className="rounded" />
              
                <div>
                  <span className="text-sm font-medium">{t('misc.de_include_charts')}</span>
                  <p className="text-xs text-gray-600">{t('misc.de_include_charts_desc')}</p>
                </div>
              </label>

              <label className="flex items-center space-x-3">
                <Checkbox aria-label="Include raw data in export" checked={includeRawData} onChange={(e) => setIncludeRawData(e.target.checked)}
                className="rounded" />
              
                <div>
                  <span className="text-sm font-medium">{t('misc.de_include_raw')}</span>
                  <p className="text-xs text-gray-600">{t('misc.de_include_raw_desc')}</p>
                </div>
              </label>

              <label className="flex items-center space-x-3">
                <Checkbox aria-label="Send export by email" checked={emailExport} onChange={(e) => setEmailExport(e.target.checked)}
                className="rounded" />
              
                <div>
                  <span className="text-sm font-medium">{t('misc.de_send_email')}</span>
                  <p className="text-xs text-gray-600">{t('misc.de_send_email_desc')}</p>
                </div>
              </label>

              {emailExport &&
            <div className="ml-6">
                  <Input
                type="email"
                aria-label="Export email address"
                value={emailAddress}
                onChange={(e) => setEmailAddress(e.target.value)}
                placeholder={t('misc.de_email_placeholder')}
                className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              
                </div>
            }
            </div>
          </div>
        }

        {/* Статус экспорта */}
        {exportStatus &&
        <div className={`p-3 rounded-lg border ${getStatusColor()}`}>
            <div className="flex items-center space-x-2">
              {getStatusIcon()}
              <span className="text-sm font-medium">{exportStatus.message}</span>
            </div>
          </div>
        }

        {/* Кнопка экспорта */}
        <div className="flex items-center justify-between pt-4 border-t border-gray-200">
          <div className="text-sm text-gray-600">
            {isExporting ? t('misc.de_exporting') : t('misc.de_ready')}
          </div>
          <Button
            onClick={handleExport}
            disabled={isExporting || !data}
            className="flex items-center space-x-2">
            
            {isExporting ?
            <Clock className="w-4 h-4 animate-spin" /> :

            <Download className="w-4 h-4" />
            }
            <span>
              {isExporting ? t('misc.de_export_button') : t('misc.de_export_to', { format: selectedFormat.toUpperCase() })}
            </span>
          </Button>
        </div>
      </div>
    </Card>);

};


DataExporter.propTypes = {
  ...(DataExporter.propTypes || {}),
  availableFormats: PropTypes.any,
  data: PropTypes.any,
  onExport: PropTypes.any,
  showAdvanced: PropTypes.any,
};

export default DataExporter;
