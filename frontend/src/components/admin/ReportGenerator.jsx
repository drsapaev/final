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
  Button as MacOSButton,

  MacOSInput,
  MacOSSelect,
  MacOSCheckbox } from
'../ui/macos';
import { api } from '../../api/client';
import PropTypes from 'prop-types';
import { toast } from 'react-toastify';
import logger from '../../utils/logger';

const DEFAULT_REPORT_TYPES = [
  'patient_report',
  'appointments_report',
  'financial_report',
  'queue_report',
  'doctor_performance_report'
];

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

        if (normalized.length > 0) {
          setAvailableReportTypes(normalized);
          if (!selectedReportType && !internalSelectedReportType) {
            setInternalSelectedReportType(normalized[0].type);
          }
        } else {
          const fallback = DEFAULT_REPORT_TYPES
            .map(normalizeReportType)
            .filter(Boolean);
          setAvailableReportTypes(fallback);
          if (!selectedReportType && !internalSelectedReportType && fallback[0]) {
            setInternalSelectedReportType(fallback[0].type);
          }
        }
      } catch (error) {
        logger.warn('Не удалось загрузить доступные отчеты для генератора:', error);

        if (!isMounted) {
          return;
        }

        const fallback = DEFAULT_REPORT_TYPES
          .map(normalizeReportType)
          .filter(Boolean);
        setAvailableReportTypes(fallback);
        if (!selectedReportType && !internalSelectedReportType && fallback[0]) {
          setInternalSelectedReportType(fallback[0].type);
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Выбор типа отчета */}
      <MacOSCard padding="large">
        <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          marginBottom: '16px',
          color: 'var(--mac-text-primary)',
          margin: 0
        }}>
          Тип отчета
        </h3>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px'
        }}>
          {currentReportTypes.length > 0 ? currentReportTypes.map((type) => {
            const typeValue = type.type || type.value || type.id;
            if (!typeValue) {
              return null;
            }

            const Icon = getReportTypeIcon(typeValue);
            const isSelected = effectiveSelectedReportType === typeValue;

            return (
              <MacOSButton
                key={typeValue}
                onClick={() => updateSelectedReportType(typeValue)}
                variant={isSelected ? 'primary' : 'outline'}
                style={{
                  padding: '16px',
                  textAlign: 'left',
                  justifyContent: 'flex-start',
                  height: 'auto',
                  minHeight: '80px'
                }}>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <Icon style={{ width: '24px', height: '24px', color: 'var(--mac-accent-blue)' }} />
                  <div>
                    <h4 style={{
                      fontWeight: 'var(--mac-font-weight-medium)',
                      fontSize: 'var(--mac-font-size-base)',
                      color: 'var(--mac-text-primary)',
                      margin: 0
                    }}>
                      {type.label || getReportTypeLabel(typeValue)}
                    </h4>
                    <p style={{
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-secondary)',
                      margin: '4px 0 0 0'
                    }}>
                      {type.description || getReportTypeDescription(typeValue)}
                    </p>
                  </div>
                </div>
              </MacOSButton>);

          }) : (
            <div style={{ color: 'var(--mac-text-secondary)', fontSize: 'var(--mac-font-size-sm)' }}>
              Загрузка доступных отчетов...
            </div>
          )}
        </div>
      </MacOSCard>

      {/* Период отчета */}
      <MacOSCard padding="large">
        <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          marginBottom: '16px',
          color: 'var(--mac-text-primary)',
          margin: 0
        }}>
          Период отчета
        </h3>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px'
        }}>
          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              marginBottom: '8px',
              color: 'var(--mac-text-primary)'
            }}>
              Дата начала
            </label>
            <MacOSInput
              type="date"
              value={effectiveDateRange.start}
              onChange={(e) => updateDateRange({ ...effectiveDateRange, start: e.target.value })}
              icon={Calendar}
              iconPosition="left"
              style={{
                width: '100%',
                paddingLeft: '40px',
                paddingRight: '12px',
                paddingTop: '8px',
                paddingBottom: '8px',
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }} />
            
          </div>
          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              marginBottom: '8px',
              color: 'var(--mac-text-primary)'
            }}>
              Дата окончания
            </label>
            <MacOSInput
              type="date"
              value={effectiveDateRange.end}
              onChange={(e) => updateDateRange({ ...effectiveDateRange, end: e.target.value })}
              icon={Calendar}
              iconPosition="left"
              style={{
                width: '100%',
                paddingLeft: '40px',
                paddingRight: '12px',
                paddingTop: '8px',
                paddingBottom: '8px',
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }} />
            
          </div>
        </div>
        
        {/* Быстрый выбор периода */}
        <div style={{ marginTop: '16px' }}>
          <p style={{
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            marginBottom: '8px',
            color: 'var(--mac-text-primary)'
          }}>
            Быстрый выбор:
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
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
                <MacOSButton
                  key={label}
                  onClick={() => updateDateRange({
                    start: startDate.toISOString().split('T')[0],
                    end: endDate.toISOString().split('T')[0]
                  })}
                  variant="outline"
                  size="sm"
                  style={{
                    padding: '4px 12px',
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)',
                    background: 'var(--mac-bg-primary)',
                    border: '1px solid var(--mac-border)',
                    borderRadius: 'var(--mac-radius-md)',
                    transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                  }}>
                  
                  {label}
                </MacOSButton>);

            })}
          </div>
        </div>
      </MacOSCard>

      {/* Фильтры */}
      <MacOSCard padding="large">
        <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          marginBottom: '16px',
          color: 'var(--mac-text-primary)',
          margin: 0
        }}>
          Дополнительные фильтры
        </h3>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px'
        }}>
          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              marginBottom: '8px',
              color: 'var(--mac-text-primary)'
            }}>
              Отделение
            </label>
            <MacOSSelect
              value={filters.department}
              onChange={(e) => handleFilterChange('department', e.target.value)}
              options={[
              { value: '', label: 'Все отделения' },
              { value: 'cardiology', label: 'Кардиология' },
              { value: 'dermatology', label: 'Дерматология' },
              { value: 'neurology', label: 'Неврология' },
              { value: 'pediatrics', label: 'Педиатрия' },
              { value: 'surgery', label: 'Хирургия' }]
              }
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }} />
            
          </div>
          
          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              marginBottom: '8px',
              color: 'var(--mac-text-primary)'
            }}>
              Статус
            </label>
            <MacOSSelect
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              options={[
              { value: '', label: 'Все статусы' },
              { value: 'completed', label: 'Завершено' },
              { value: 'pending', label: 'Ожидает' },
              { value: 'cancelled', label: 'Отменено' }]
              }
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }} />
            
          </div>
          
          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              marginBottom: '8px',
              color: 'var(--mac-text-primary)'
            }}>
              Способ оплаты
            </label>
            <MacOSSelect
              value={filters.paymentMethod}
              onChange={(e) => handleFilterChange('paymentMethod', e.target.value)}
              options={[
              { value: '', label: 'Все способы' },
              { value: 'cash', label: 'Наличные' },
              { value: 'card', label: 'Карта' },
              { value: 'transfer', label: 'Перевод' },
              { value: 'mobile', label: 'Мобильный' }]
              }
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)',
                background: 'var(--mac-bg-primary)',
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }} />
            
          </div>
        </div>
      </MacOSCard>

      {/* Настройки отчета */}
      <MacOSCard padding="large">
        <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          marginBottom: '16px',
          color: 'var(--mac-text-primary)',
          margin: 0
        }}>
          Настройки отчета
        </h3>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '24px'
        }}>
          <div>
            <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              marginBottom: '8px',
              color: 'var(--mac-text-primary)'
            }}>
              Формат файла
            </label>
            <div style={{ display: 'flex', gap: '16px' }}>
              {[
              { value: 'pdf', label: 'PDF', icon: FileText },
              { value: 'excel', label: 'Excel', icon: BarChart3 },
              { value: 'csv', label: 'CSV', icon: FileText }].
              map(({ value, label, icon: Icon }) =>
              <MacOSButton
                key={value}
                onClick={() => setReportFormat(value)}
                variant={reportFormat === value ? 'primary' : 'outline'}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 16px',
                  borderRadius: 'var(--mac-radius-md)',
                  border: reportFormat === value ? '1px solid var(--mac-accent-blue)' : '1px solid var(--mac-border)',
                  background: reportFormat === value ? 'var(--mac-accent-blue)' : 'var(--mac-bg-primary)',
                  color: reportFormat === value ? 'white' : 'var(--mac-text-primary)',
                  transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                }}>
                
                  <Icon style={{ width: '16px', height: '16px' }} />
                  {label}
                </MacOSButton>
              )}
            </div>
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <MacOSCheckbox
                id="includeCharts"
                checked={includeCharts}
                onChange={(e) => setIncludeCharts(e.target.checked)}
                style={{
                  width: '16px',
                  height: '16px',
                  accentColor: 'var(--mac-accent-blue)'
                }} />
              
              <label htmlFor="includeCharts" style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-primary)'
              }}>
                Включить графики и диаграммы
              </label>
            </div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <MacOSCheckbox
                id="includeDetails"
                checked={includeDetails}
                onChange={(e) => setIncludeDetails(e.target.checked)}
                style={{
                  width: '16px',
                  height: '16px',
                  accentColor: 'var(--mac-accent-blue)'
                }} />
              
              <label htmlFor="includeDetails" style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-primary)'
              }}>
                Включить детальную информацию
              </label>
            </div>
          </div>
        </div>
      </MacOSCard>

      {/* Кнопки действий */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <MacOSButton
            onClick={() => handleGenerate(reportFormat)}
            disabled={!effectiveSelectedReportType || effectiveLoading}
            variant="primary"
            aria-label={`Generate selected report as ${String(reportFormat).toUpperCase()}`}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              background: 'var(--mac-accent-blue)',
              color: 'white'
            }}>
            
            {effectiveLoading ?
            <>
                <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} />
                <span>Генерация...</span>
              </> :

            <>
                <Download style={{ width: '16px', height: '16px' }} />
                <span>Сгенерировать отчет</span>
              </>
            }
          </MacOSButton>
          
          <MacOSButton
            variant="outline"
            onClick={() => handleGenerate('pdf')}
            disabled={!effectiveSelectedReportType || effectiveLoading}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
            
            <Printer style={{ width: '16px', height: '16px' }} />
            <span>Печать</span>
          </MacOSButton>
        </div>
        
        <div style={{
          fontSize: 'var(--mac-font-size-sm)',
          color: 'var(--mac-text-secondary)'
        }}>
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
