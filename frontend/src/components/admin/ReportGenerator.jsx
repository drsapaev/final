import { useEffect, useState } from 'react';
import {
  Download,
  Calendar,
  BarChart3,
  PieChart,
  TrendingUp,
  Users,
  DollarSign,
  FileText,
  Clock,

  RefreshCw,

  Printer } from
'lucide-react';
import {
  Card as MacOSCard,
  Button as Button,
  Input,
  Select,
  Checkbox,
} from '../ui/macos';
import { api } from '../../api/client';
import PropTypes from 'prop-types';
import { toast } from 'react-toastify';
import logger from '../../utils/logger';

const REPORT_ENDPOINTS = {
  patient_report: 'patient',
  appointments_report: 'appointments',
  financial_report: 'financial',
  queue_report: 'queue',
  doctor_performance_report: 'doctor-performance',
  patients: 'patient',
  appointments: 'appointments',
  financial: 'financial',
  queue: 'queue',
  doctors: 'doctor-performance',
  performance: 'doctor-performance',
  revenue: 'financial',
  analytics: 'financial'
};

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

  const [availableReportTypes, setAvailableReportTypes] = useState([]);
  const [internalSelectedReportType, setInternalSelectedReportType] = useState(
    selectedReportType || ''
  );
  const [internalDateRange, setInternalDateRange] = useState(dateRange);
  const [internalLoading, setInternalLoading] = useState(false);
  const [reportFormat, setReportFormat] = useState('pdf');
  const [includeCharts, setIncludeCharts] = useState(true);
  const [includeDetails, setIncludeDetails] = useState(true);

  const effectiveLoading = loading || internalLoading;
  const effectiveDateRange = onDateRangeChange ? dateRange : internalDateRange;
  const effectiveSelectedReportType =
    selectedReportType || internalSelectedReportType;

  const normalizeReportType = (type) => {
    if (!type) {
      return null;
    }

    if (typeof type === 'string') {
      return {
        type,
        label: getReportTypeLabel(type),
        description: getReportTypeDescription(type)
      };
    }

    const value = type.type || type.id || type.value || '';

    return {
      type: value,
      label: type.name || type.label || getReportTypeLabel(value),
      description:
        type.description || getReportTypeDescription(value)
    };
  };

  useEffect(() => {
    let isMounted = true;

    const loadReportTypes = async () => {
      if (reportTypes.length > 0) {
        const normalized = reportTypes
          .map(normalizeReportType)
          .filter(Boolean);
        if (isMounted) {
          setAvailableReportTypes(normalized);
          if (!selectedReportType && normalized.length > 0) {
            setInternalSelectedReportType(normalized[0].type);
          }
        }
        return;
      }

      try {
        const response = await api.get('/reports/available-reports');
        const normalized = (response.data?.reports || [])
          .map(normalizeReportType)
          .filter(Boolean);

        if (!isMounted) {
          return;
        }

        setAvailableReportTypes(normalized);
        if (!normalized.some((type) => type.type === internalSelectedReportType)) {
          setInternalSelectedReportType('');
        }
      } catch (error) {
        logger.warn('Не удалось загрузить доступные отчеты для генератора:', error);

        if (!isMounted) {
          return;
        }

        setAvailableReportTypes([]);
        if (!selectedReportType) {
          setInternalSelectedReportType('');
        }
      }
    };

    loadReportTypes();

    return () => {
      isMounted = false;
    };
  }, [reportTypes, selectedReportType, internalSelectedReportType]);

  const handleFilterChange = (filterName, value) => {
    setFilters((prev) => ({
      ...prev,
      [filterName]: value
    }));
  };

  const handleGenerate = async (formatOverride = reportFormat) => {
    const reportConfig = {
      type: effectiveSelectedReportType,
      dateRange: effectiveDateRange,
      filters,
      format: formatOverride,
      includeCharts,
      includeDetails
    };

    if (onGenerateReport) {
      return onGenerateReport(reportConfig);
    }

    if (!effectiveSelectedReportType) {
      toast.error('Выберите тип отчета');
      return null;
    }

    const endpoint = REPORT_ENDPOINTS[effectiveSelectedReportType];
    if (!endpoint) {
      toast.error('Для выбранного отчета нет backend-эндпоинта');
      return null;
    }

    setInternalLoading(true);
    try {
      const response = await api.post(`/reports/${endpoint}`, {
        start_date: effectiveDateRange.start || null,
        end_date: effectiveDateRange.end || null,
        format: formatOverride,
        filters,
        department: filters.department || null,
        doctor_id: filters.doctor ? Number(filters.doctor) : null
      });

      const data = response.data;
      if (data?.success === false) {
        toast.error(data.error || 'Ошибка генерации отчета');
        return data;
      }

      toast.success('Отчет успешно сгенерирован');

      if (formatOverride === 'pdf' && data?.filename) {
        toast.info(`PDF сформирован: ${data.filename}`);
      }

      return data;
    } catch (error) {
      logger.error('Ошибка генерации отчета:', error);
      toast.error(error.response?.data?.detail || 'Ошибка генерации отчета');
      return null;
    } finally {
      setInternalLoading(false);
    }
  };

  const getReportTypeIcon = (type) => {
    const iconMap = {
      financial: DollarSign,
      financial_report: DollarSign,
      appointments: Calendar,
      appointments_report: Calendar,
      patient_report: Users,
      patients: Users,
      queue_report: Clock,
      doctors: Users,
      doctor_performance_report: PieChart,
      performance: PieChart,
      analytics: BarChart3,
      revenue: TrendingUp
    };
    return iconMap[type] || FileText;
  };

  const getReportTypeLabel = (type) => {
    const labelMap = {
      financial: 'Финансовый отчет',
      financial_report: 'Финансовый отчет',
      appointments: 'Отчет по записям',
      appointments_report: 'Отчет по записям',
      patients: 'Отчет по пациентам',
      patient_report: 'Отчет по пациентам',
      queue_report: 'Отчет по очереди',
      doctors: 'Отчет по врачам',
      doctor_performance_report: 'Отчет по эффективности врачей',
      analytics: 'Аналитический отчет',
      revenue: 'Отчет по доходам',
      performance: 'Отчет по эффективности'
    };
    return labelMap[type] || type;
  };

  const getReportTypeDescription = (type) => {
    const descMap = {
      financial: 'Детальный анализ доходов и расходов клиники',
      financial_report: 'Детальный анализ доходов и расходов клиники',
      appointments: 'Статистика записей, загруженности и эффективности',
      appointments_report: 'Статистика записей, загруженности и эффективности',
      patients: 'Анализ пациентской базы и демографии',
      patient_report: 'Анализ пациентской базы и демографии',
      queue_report: 'Анализ очередей и времени ожидания',
      doctors: 'Производительность и загруженность врачей',
      doctor_performance_report: 'Производительность и загруженность врачей',
      analytics: 'Общая аналитика и ключевые показатели',
      revenue: 'Анализ доходов по источникам и периодам',
      performance: 'KPI и метрики эффективности работы'
    };
    return descMap[type] || 'Отчет по выбранным параметрам';
  };

  const updateSelectedReportType = (type) => {
    if (onReportTypeChange) {
      onReportTypeChange(type);
      return;
    }

    setInternalSelectedReportType(type);
  };

  const updateDateRange = (nextRange) => {
    if (onDateRangeChange) {
      onDateRangeChange(nextRange);
      return;
    }

    setInternalDateRange(nextRange);
  };

  const currentReportTypes =
    reportTypes.length > 0 ? reportTypes.map(normalizeReportType).filter(Boolean) : availableReportTypes;

  return (
    <div className="admin-flex-col-24">
      {/* Выбор типа отчета */}
      <MacOSCard padding="large">
        <h3 className="admin-fs-lg-fw-semi-mb-16-primary-m-0-3">
          Тип отчета
        </h3>
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
          {currentReportTypes.length > 0 ? currentReportTypes.map((type) => {
            const typeValue = type.type || type.value || type.id;
            if (!typeValue) {
              return null;
            }

            const Icon = getReportTypeIcon(typeValue);
            const isSelected = effectiveSelectedReportType === typeValue;

            return (
              <Button
                key={typeValue}
                onClick={() => updateSelectedReportType(typeValue)}
                variant={isSelected ? 'primary' : 'outline'}
                className="admin-p-16-ta-left-jc-start-h-auto-minh-80">
                
                <div className="admin-flex-center-12">
                  <Icon className="admin-w-24-h-24-blue" />
                  <div>
                    <h4 className="admin-fw-med-fs-base-primary-m-0">
                      {type.label || getReportTypeLabel(typeValue)}
                    </h4>
                    <p className="admin-fs-sm-secondary-m-4px-0-0-0">
                      {type.description || getReportTypeDescription(typeValue)}
                    </p>
                  </div>
                </div>
              </Button>);

          }) : (
            <div className="admin-secondary-fs-sm">
              Загрузка доступных отчетов...
            </div>
          )}
        </div>
      </MacOSCard>

      {/* Период отчета */}
      <MacOSCard padding="large">
        <h3 className="admin-fs-lg-fw-semi-mb-16-primary-m-0-2">
          Период отчета
        </h3>
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
          <div>
            <label className="admin-d-block-fs-sm-fw-med-mb-8-primary-5">
              Дата начала
            </label>
            <Input
              type="date"
              value={effectiveDateRange.start}
              onChange={(e) => updateDateRange({ ...effectiveDateRange, start: e.target.value })}
              icon={Calendar}
              iconPosition="left"
              className="admin-w-100pct-pl-40-pr-12-pt-8-pb-8-radius-var-mac-radius-md-bd-1px-solid-var-mac-bo-bg-bg-primary-primary-fs-base-tr-all-var-mac-duration-1" />
            
          </div>
          <div>
            <label className="admin-d-block-fs-sm-fw-med-mb-8-primary-4">
              Дата окончания
            </label>
            <Input
              type="date"
              value={effectiveDateRange.end}
              onChange={(e) => updateDateRange({ ...effectiveDateRange, end: e.target.value })}
              icon={Calendar}
              iconPosition="left"
              className="admin-w-100pct-pl-40-pr-12-pt-8-pb-8-radius-var-mac-radius-md-bd-1px-solid-var-mac-bo-bg-bg-primary-primary-fs-base-tr-all-var-mac-duration" />
            
          </div>
        </div>
        
        {/* Быстрый выбор периода */}
        <div className="admin-mt-16">
          <p className="admin-fs-sm-fw-med-mb-8-primary">
            Быстрый выбор:
          </p>
          <div className="admin-d-flex-fw-wrap-gap-8">
            {[
            { label: 'Сегодня', days: 0 },
            { label: 'Неделя', days: 7 },
            { label: 'Месяц', days: 30 },
            { label: 'Квартал', days: 90 },
            { label: 'Год', days: 365 }].
            map(({ label, days }) => {
              const today = new Date();
              const startDate = new Date(today.getTime() - days * 24 * 60 * 60 * 1000);
              const endDate = days === 0 ? today : today;

              return (
                <Button
                  key={label}
                  onClick={() => updateDateRange({
                    start: startDate.toISOString().split('T')[0],
                    end: endDate.toISOString().split('T')[0]
                  })}
                  variant="outline"
                  size="sm"
                  className="admin-p-4px-12px-fs-sm-secondary-bg-bg-primary-bd-1px-solid-var-mac-bo-radius-var-mac-radius-md-tr-all-var-mac-duration">
                  
                  {label}
                </Button>);

            })}
          </div>
        </div>
      </MacOSCard>

      {/* Фильтры */}
      <MacOSCard padding="large">
        <h3 className="admin-fs-lg-fw-semi-mb-16-primary-m-0-1">
          Дополнительные фильтры
        </h3>
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-16">
          <div>
            <label className="admin-d-block-fs-sm-fw-med-mb-8-primary-3">
              Отделение
            </label>
            <Select
              value={filters.department}
              onChange={(value) => handleFilterChange('department', value)}
              options={[
              { value: '', label: 'Все отделения' },
              { value: 'cardiology', label: 'Кардиология' },
              { value: 'dermatology', label: 'Дерматология' },
              { value: 'neurology', label: 'Неврология' },
              { value: 'pediatrics', label: 'Педиатрия' },
              { value: 'surgery', label: 'Хирургия' }]
              }
              size="large"
              className="admin-w-full" />
            
          </div>
          
          <div>
            <label className="admin-d-block-fs-sm-fw-med-mb-8-primary-2">
              Статус
            </label>
            <Select
              value={filters.status}
              onChange={(value) => handleFilterChange('status', value)}
              options={[
              { value: '', label: 'Все статусы' },
              { value: 'completed', label: 'Завершено' },
              { value: 'pending', label: 'Ожидает' },
              { value: 'cancelled', label: 'Отменено' }]
              }
              size="large"
              className="admin-w-full" />
            
          </div>
          
          <div>
            <label className="admin-d-block-fs-sm-fw-med-mb-8-primary-1">
              Способ оплаты
            </label>
            <Select
              value={filters.paymentMethod}
              onChange={(value) => handleFilterChange('paymentMethod', value)}
              options={[
              { value: '', label: 'Все способы' },
              { value: 'cash', label: 'Наличные' },
              { value: 'card', label: 'Карта' },
              { value: 'transfer', label: 'Перевод' },
              { value: 'mobile', label: 'Мобильный' }]
              }
              size="large"
              className="admin-w-full" />
            
          </div>
        </div>
      </MacOSCard>

      {/* Настройки отчета */}
      <MacOSCard padding="large">
        <h3 className="admin-fs-lg-fw-semi-mb-16-primary-m-0">
          Настройки отчета
        </h3>
        <div className="admin-d-grid-gtc-repeat-auto-fit-minm-gap-24">
          <div>
            <label className="admin-d-block-fs-sm-fw-med-mb-8-primary">
              Формат файла
            </label>
            <div className="admin-d-flex-gap-16">
              {[
              { value: 'pdf', label: 'PDF', icon: FileText },
              { value: 'excel', label: 'Excel', icon: BarChart3 },
              { value: 'csv', label: 'CSV', icon: FileText }].
              map(({ value, label, icon: Icon }) =>
              <Button
                key={value}
                onClick={() => setReportFormat(value)}
                variant={reportFormat === value ? 'primary' : 'outline'}
                className="admin-d-flex-ai-center-gap-8-p-8px-16px-radius-var-mac-radius-md-tr-all-var-mac-duration-bd-dyn-bg-dyn-col-dyn" style={{ '--admin-bd0': reportFormat === value ? '1px solid var(--mac-accent-blue)' : '1px solid var(--mac-border)', '--admin-bg1': reportFormat === value ? 'var(--mac-accent-blue)' : 'var(--mac-bg-primary)', '--admin-col2': reportFormat === value ? 'white' : 'var(--mac-text-primary)' }}>
                
                  <Icon className="admin-icon-16" />
                  {label}
                </Button>
              )}
            </div>
          </div>
          
          <div className="admin-flex-col-16">
            <div className="admin-flex-center-12">
              <Checkbox
                id="includeCharts"
                checked={includeCharts}
                onChange={(e) => setIncludeCharts(e.target.checked)}
                className="admin-w-16-h-16-accentco-blue-1" />
              
              <label htmlFor="includeCharts" className="admin-fs-sm-primary">
                Включить графики и диаграммы
              </label>
            </div>
            
            <div className="admin-flex-center-12">
              <Checkbox
                id="includeDetails"
                checked={includeDetails}
                onChange={(e) => setIncludeDetails(e.target.checked)}
                className="admin-w-16-h-16-accentco-blue" />
              
              <label htmlFor="includeDetails" className="admin-fs-sm-primary">
                Включить детальную информацию
              </label>
            </div>
          </div>
        </div>
      </MacOSCard>

      {/* Кнопки действий */}
      <div className="admin-flex-between">
        <div className="admin-d-flex-ai-center-gap-16">
          <Button
            onClick={() => handleGenerate(reportFormat)}
            disabled={!effectiveSelectedReportType || effectiveLoading}
            variant="primary"
            aria-label={`Generate selected report as ${String(reportFormat).toUpperCase()}`}
            className="admin-d-flex-ai-center-gap-8-bg-blue-white">
            
            {effectiveLoading ?
            <>
                <RefreshCw className="admin-w-16-h-16-anim-spin-1s-linear-infin" />
                <span>Генерация...</span>
              </> :

            <>
                <Download className="admin-icon-16" />
                <span>Сгенерировать отчет</span>
              </>
            }
          </Button>
          
          <Button
            variant="outline"
            onClick={() => handleGenerate('pdf')}
            disabled={!effectiveSelectedReportType || effectiveLoading}
            className="admin-flex-center-8">
            
            <Printer className="admin-icon-16" />
            <span>Печать</span>
          </Button>
        </div>
        
        <div className="admin-text-sm admin-text-secondary">
          {effectiveSelectedReportType &&
          <span>
              Будет сгенерирован: <strong>{getReportTypeLabel(effectiveSelectedReportType)}</strong>
            </span>
          }
        </div>
      </div>
    </div>);

};


ReportGenerator.propTypes = {
  ...(ReportGenerator.propTypes || {}),
  dateRange: PropTypes.any,
  loading: PropTypes.any,
  onDateRangeChange: PropTypes.any,
  onGenerateReport: PropTypes.any,
  onReportTypeChange: PropTypes.any,
  reportTypes: PropTypes.any,
  selectedReportType: PropTypes.any,
};

export default ReportGenerator;
