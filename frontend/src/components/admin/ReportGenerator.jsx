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
import { 
  Card as MacOSCard, 
  Button as MacOSButton, 
  Badge as MacOSBadge,
  MacOSInput,
  MacOSSelect,
  MacOSCheckbox
} from '../ui/macos';

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
          {reportTypes.map((type) => {
            const Icon = getReportTypeIcon(type);
            const isSelected = selectedReportType === type;
            
            return (
              <MacOSButton
                key={type}
                onClick={() => onReportTypeChange(type)}
                variant={isSelected ? "primary" : "outline"}
                style={{
                  padding: '16px',
                  textAlign: 'left',
                  justifyContent: 'flex-start',
                  height: 'auto',
                  minHeight: '80px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <Icon style={{ width: '24px', height: '24px', color: 'var(--mac-accent-blue)' }} />
                  <div>
                    <h4 style={{ 
                      fontWeight: 'var(--mac-font-weight-medium)', 
                      fontSize: 'var(--mac-font-size-base)',
                      color: 'var(--mac-text-primary)',
                      margin: 0
                    }}>
                      {getReportTypeLabel(type)}
                    </h4>
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      color: 'var(--mac-text-secondary)',
                      margin: '4px 0 0 0'
                    }}>
                      {getReportTypeDescription(type)}
                    </p>
                  </div>
                </div>
              </MacOSButton>
            );
          })}
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
              value={dateRange.start}
              onChange={(e) => onDateRangeChange({ ...dateRange, start: e.target.value })}
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
              }}
            />
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
              value={dateRange.end}
              onChange={(e) => onDateRangeChange({ ...dateRange, end: e.target.value })}
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
              }}
            />
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
              { label: 'Год', days: 365 }
            ].map(({ label, days }) => {
              const today = new Date();
              const startDate = new Date(today.getTime() - days * 24 * 60 * 60 * 1000);
              const endDate = days === 0 ? today : today;
              
              return (
                <MacOSButton
                  key={label}
                  onClick={() => onDateRangeChange({
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
                  }}
                >
                  {label}
                </MacOSButton>
              );
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
                { value: 'surgery', label: 'Хирургия' }
              ]}
              style={{ 
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)', 
                background: 'var(--mac-bg-primary)', 
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
            />
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
                { value: 'cancelled', label: 'Отменено' }
              ]}
              style={{ 
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)', 
                background: 'var(--mac-bg-primary)', 
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
            />
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
                { value: 'mobile', label: 'Мобильный' }
              ]}
              style={{ 
                width: '100%',
                padding: '8px 12px',
                borderRadius: 'var(--mac-radius-md)',
                border: '1px solid var(--mac-border)', 
                background: 'var(--mac-bg-primary)', 
                color: 'var(--mac-text-primary)',
                fontSize: 'var(--mac-font-size-base)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
            />
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
                { value: 'csv', label: 'CSV', icon: FileText }
              ].map(({ value, label, icon: Icon }) => (
                <MacOSButton
                  key={value}
                  onClick={() => setReportFormat(value)}
                  variant={reportFormat === value ? "primary" : "outline"}
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
                  }}
                >
                  <Icon style={{ width: '16px', height: '16px' }} />
                  {label}
                </MacOSButton>
              ))}
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
                }}
              />
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
                }}
              />
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
            onClick={handleGenerate}
            disabled={!selectedReportType || loading}
            variant="primary"
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              background: 'var(--mac-accent-blue)',
              color: 'white'
            }}
          >
            {loading ? (
              <>
                <RefreshCw style={{ width: '16px', height: '16px', animation: 'spin 1s linear infinite' }} />
                <span>Генерация...</span>
              </>
            ) : (
              <>
                <Download style={{ width: '16px', height: '16px' }} />
                <span>Сгенерировать отчет</span>
              </>
            )}
          </MacOSButton>
          
          <MacOSButton
            variant="outline"
            onClick={() => window.print()}
            disabled={loading}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px'
            }}
          >
            <Printer style={{ width: '16px', height: '16px' }} />
            <span>Печать</span>
          </MacOSButton>
        </div>
        
        <div style={{ 
          fontSize: 'var(--mac-font-size-sm)', 
          color: 'var(--mac-text-secondary)' 
        }}>
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

