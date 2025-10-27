import React, { useState, useEffect } from 'react';
import { 
  BarChart3, 
  PieChart, 
  TrendingUp, 
  TrendingDown,
  Users, 
  Calendar, 
  DollarSign, 
  Activity,
  Clock,
  Target,
  Award,
  AlertCircle
} from 'lucide-react';
import { Card as MacOSCard, Badge as MacOSBadge } from '../ui/macos';
import { 
  MacOSStatCard, 
  MacOSMetricCard,
  MacOSTable,
  MacOSEmptyState,
  MacOSLoadingSkeleton
} from '../ui/macos';

const AnalyticsDashboard = ({ 
  data = {},
  loading = false,
  dateRange = { start: '', end: '' }
}) => {
  const [selectedMetric, setSelectedMetric] = useState('revenue');
  const [timeframe, setTimeframe] = useState('month');

  // Моковые данные для демонстрации
  const mockData = {
    overview: {
      totalRevenue: 12500000,
      totalPatients: 1247,
      totalAppointments: 3421,
      averageRating: 4.7,
      revenueGrowth: 12.5,
      patientGrowth: 8.3,
      appointmentGrowth: 15.2,
      ratingGrowth: 0.3
    },
    revenue: {
      daily: [
        { date: '2024-01-01', amount: 450000 },
        { date: '2024-01-02', amount: 520000 },
        { date: '2024-01-03', amount: 380000 },
        { date: '2024-01-04', amount: 610000 },
        { date: '2024-01-05', amount: 490000 },
        { date: '2024-01-06', amount: 420000 },
        { date: '2024-01-07', amount: 580000 }
      ],
      byCategory: [
        { category: 'Консультации', amount: 4500000, percentage: 36 },
        { category: 'Диагностика', amount: 3200000, percentage: 25.6 },
        { category: 'Лечение', amount: 2800000, percentage: 22.4 },
        { category: 'Процедуры', amount: 1200000, percentage: 9.6 },
        { category: 'Анализы', amount: 800000, percentage: 6.4 }
      ],
      byDoctor: [
        { doctor: 'Иванов И.И.', amount: 2100000, appointments: 45 },
        { doctor: 'Петрова М.С.', amount: 1800000, appointments: 38 },
        { doctor: 'Козлова А.В.', amount: 1600000, appointments: 42 },
        { doctor: 'Сидоров Д.А.', amount: 1400000, appointments: 35 }
      ]
    },
    appointments: {
      byStatus: [
        { status: 'Завершено', count: 2856, percentage: 83.5 },
        { status: 'Ожидает', count: 342, percentage: 10 },
        { status: 'Отменено', count: 223, percentage: 6.5 }
      ],
      byDay: [
        { day: 'Пн', count: 89 },
        { day: 'Вт', count: 95 },
        { day: 'Ср', count: 78 },
        { day: 'Чт', count: 102 },
        { day: 'Пт', count: 88 },
        { day: 'Сб', count: 45 },
        { day: 'Вс', count: 12 }
      ],
      byTime: [
        { time: '09:00-12:00', count: 245, percentage: 35 },
        { time: '12:00-15:00', count: 198, percentage: 28 },
        { time: '15:00-18:00', count: 156, percentage: 22 },
        { time: '18:00-21:00', count: 102, percentage: 15 }
      ]
    },
    patients: {
      byAge: [
        { range: '0-18', count: 234, percentage: 18.8 },
        { range: '19-35', count: 456, percentage: 36.6 },
        { range: '36-50', count: 312, percentage: 25.0 },
        { range: '51-65', count: 178, percentage: 14.3 },
        { range: '65+', count: 67, percentage: 5.4 }
      ],
      byGender: [
        { gender: 'Женщины', count: 748, percentage: 60 },
        { gender: 'Мужчины', count: 499, percentage: 40 }
      ],
      newVsReturning: [
        { type: 'Новые', count: 456, percentage: 36.6 },
        { type: 'Повторные', count: 791, percentage: 63.4 }
      ]
    },
    performance: {
      doctors: [
        { 
          doctor: 'Иванов И.И.', 
          appointments: 45, 
          revenue: 2100000, 
          rating: 4.8, 
          efficiency: 92 
        },
        { 
          doctor: 'Петрова М.С.', 
          appointments: 38, 
          revenue: 1800000, 
          rating: 4.6, 
          efficiency: 88 
        },
        { 
          doctor: 'Козлова А.В.', 
          appointments: 42, 
          revenue: 1600000, 
          rating: 4.7, 
          efficiency: 90 
        }
      ],
      departments: [
        { department: 'Кардиология', appointments: 856, revenue: 4200000 },
        { department: 'Дерматология', appointments: 642, revenue: 3200000 },
        { department: 'Неврология', appointments: 534, revenue: 2800000 },
        { department: 'Педиатрия', appointments: 789, revenue: 2300000 }
      ]
    }
  };

  const currentData = data.overview || mockData.overview;
  const revenueData = data.revenue || mockData.revenue;
  const appointmentsData = data.appointments || mockData.appointments;
  const patientsData = data.patients || mockData.patients;
  const performanceData = data.performance || mockData.performance;

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'UZS',
      minimumFractionDigits: 0
    }).format(amount);
  };

  const formatPercentage = (value) => {
    return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
  };

  const getGrowthIcon = (value) => {
    return value > 0 ? TrendingUp : TrendingDown;
  };

  const getGrowthColor = (value) => {
    return value > 0 ? 'var(--mac-success)' : 'var(--mac-danger)';
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', 
          gap: '16px' 
        }}>
          {[...Array(4)].map((_, i) => (
            <MacOSCard key={i} padding="default">
              <div style={{ 
                animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                '@keyframes pulse': {
                  '0%, 100%': { opacity: 1 },
                  '50%': { opacity: 0.5 }
                }
              }}>
                <div style={{ 
                  height: '16px', 
                  backgroundColor: 'var(--mac-bg-tertiary)', 
                  borderRadius: 'var(--mac-radius-sm)', 
                  width: '75%', 
                  marginBottom: '8px' 
                }}></div>
                <div style={{ 
                  height: '32px', 
                  backgroundColor: 'var(--mac-bg-tertiary)', 
                  borderRadius: 'var(--mac-radius-sm)', 
                  width: '50%' 
                }}></div>
              </div>
            </MacOSCard>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Обзорные метрики */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', 
        gap: '16px' 
      }}>
        <MacOSCard padding="default">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-secondary)',
                margin: 0
              }}>
                Общий доход
              </p>
              <p style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)', 
                color: 'var(--mac-text-primary)',
                margin: '4px 0 0 0'
              }}>
                {formatCurrency(currentData.totalRevenue)}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', marginTop: '4px' }}>
                {React.createElement(getGrowthIcon(currentData.revenueGrowth), {
                  style: { 
                    width: '16px', 
                    height: '16px', 
                    marginRight: '4px',
                    color: getGrowthColor(currentData.revenueGrowth) 
                  }
                })}
                <span 
                  style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: getGrowthColor(currentData.revenueGrowth) 
                  }}
                >
                  {formatPercentage(currentData.revenueGrowth)}
                </span>
              </div>
            </div>
            <DollarSign style={{ width: '32px', height: '32px', color: 'var(--mac-success)' }} />
          </div>
        </MacOSCard>

        <MacOSCard padding="default">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-secondary)',
                margin: 0
              }}>
                Пациенты
              </p>
              <p style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)', 
                color: 'var(--mac-text-primary)',
                margin: '4px 0 0 0'
              }}>
                {currentData.totalPatients.toLocaleString()}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', marginTop: '4px' }}>
                {React.createElement(getGrowthIcon(currentData.patientGrowth), {
                  style: { 
                    width: '16px', 
                    height: '16px', 
                    marginRight: '4px',
                    color: getGrowthColor(currentData.patientGrowth) 
                  }
                })}
                <span 
                  style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: getGrowthColor(currentData.patientGrowth) 
                  }}
                >
                  {formatPercentage(currentData.patientGrowth)}
                </span>
              </div>
            </div>
            <Users style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
          </div>
        </MacOSCard>

        <MacOSCard padding="default">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-secondary)',
                margin: 0
              }}>
                Записи
              </p>
              <p style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)', 
                color: 'var(--mac-text-primary)',
                margin: '4px 0 0 0'
              }}>
                {currentData.totalAppointments.toLocaleString()}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', marginTop: '4px' }}>
                {React.createElement(getGrowthIcon(currentData.appointmentGrowth), {
                  style: { 
                    width: '16px', 
                    height: '16px', 
                    marginRight: '4px',
                    color: getGrowthColor(currentData.appointmentGrowth) 
                  }
                })}
                <span 
                  style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: getGrowthColor(currentData.appointmentGrowth) 
                  }}
                >
                  {formatPercentage(currentData.appointmentGrowth)}
                </span>
              </div>
            </div>
            <Calendar style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
          </div>
        </MacOSCard>

        <MacOSCard padding="default">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-secondary)',
                margin: 0
              }}>
                Рейтинг
              </p>
              <p style={{ 
                fontSize: 'var(--mac-font-size-2xl)', 
                fontWeight: 'var(--mac-font-weight-bold)', 
                color: 'var(--mac-text-primary)',
                margin: '4px 0 0 0'
              }}>
                {currentData.averageRating}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', marginTop: '4px' }}>
                {React.createElement(getGrowthIcon(currentData.ratingGrowth), {
                  style: { 
                    width: '16px', 
                    height: '16px', 
                    marginRight: '4px',
                    color: getGrowthColor(currentData.ratingGrowth) 
                  }
                })}
                <span 
                  style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: getGrowthColor(currentData.ratingGrowth) 
                  }}
                >
                  {formatPercentage(currentData.ratingGrowth)}
                </span>
              </div>
            </div>
            <Award style={{ width: '32px', height: '32px', color: 'var(--mac-warning)' }} />
          </div>
        </MacOSCard>
      </div>

      {/* Детальная аналитика */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
        gap: '24px' 
      }}>
        {/* Доходы по категориям */}
        <MacOSCard padding="large">
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            marginBottom: '16px',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
            Доходы по категориям
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {revenueData.byCategory.map((item, index) => (
              <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      fontWeight: 'var(--mac-font-weight-medium)', 
                      color: 'var(--mac-text-primary)' 
                    }}>
                      {item.category}
                    </span>
                    <span style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      fontWeight: 'var(--mac-font-weight-medium)', 
                      color: 'var(--mac-text-primary)' 
                    }}>
                      {formatCurrency(item.amount)}
                    </span>
                  </div>
                  <div style={{ 
                    width: '100%', 
                    backgroundColor: 'var(--mac-bg-tertiary)', 
                    borderRadius: 'var(--mac-radius-full)', 
                    height: '8px' 
                  }}>
                    <div 
                      style={{ 
                        height: '8px', 
                        borderRadius: 'var(--mac-radius-full)',
                        width: `${item.percentage}%`,
                        background: 'var(--mac-accent-blue)',
                        transition: 'width var(--mac-duration-normal) var(--mac-ease)'
                      }}
                    ></div>
                  </div>
                  <span style={{ 
                    fontSize: 'var(--mac-font-size-xs)', 
                    color: 'var(--mac-text-secondary)' 
                  }}>
                    {item.percentage}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </MacOSCard>

        {/* Статус записей */}
        <MacOSCard padding="large">
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            marginBottom: '16px',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
            Статус записей
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {appointmentsData.byStatus.map((item, index) => (
              <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div 
                    style={{ 
                      width: '12px', 
                      height: '12px', 
                      borderRadius: 'var(--mac-radius-full)',
                      background: index === 0 ? 'var(--mac-success)' : 
                                 index === 1 ? 'var(--mac-warning)' : 'var(--mac-danger)'
                    }}
                  ></div>
                  <span style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)' 
                  }}>
                    {item.status}
                  </span>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)' 
                  }}>
                    {item.count}
                  </span>
                  <span style={{ 
                    fontSize: 'var(--mac-font-size-xs)', 
                    marginLeft: '8px', 
                    color: 'var(--mac-text-secondary)' 
                  }}>
                    ({item.percentage}%)
                  </span>
                </div>
              </div>
            ))}
          </div>
        </MacOSCard>

        {/* Топ врачей по доходам */}
        <MacOSCard padding="large">
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            marginBottom: '16px',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
            Топ врачей по доходам
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {revenueData.byDoctor.map((doctor, index) => (
              <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ 
                    width: '32px', 
                    height: '32px', 
                    borderRadius: 'var(--mac-radius-full)', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center', 
                    color: 'white', 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    background: 'var(--mac-accent-blue)' 
                  }}>
                    {index + 1}
                  </div>
                  <div>
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-sm)', 
                      fontWeight: 'var(--mac-font-weight-medium)', 
                      color: 'var(--mac-text-primary)',
                      margin: 0
                    }}>
                      {doctor.doctor}
                    </p>
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-xs)', 
                      color: 'var(--mac-text-secondary)',
                      margin: 0
                    }}>
                      {doctor.appointments} записей
                    </p>
                  </div>
                </div>
                <span style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)' 
                }}>
                  {formatCurrency(doctor.amount)}
                </span>
              </div>
            ))}
          </div>
        </MacOSCard>

        {/* Распределение по дням недели */}
        <MacOSCard padding="large">
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            marginBottom: '16px',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
            Записи по дням недели
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {appointmentsData.byDay.map((day, index) => (
              <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)' 
                }}>
                  {day.day}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ 
                    width: '96px', 
                    backgroundColor: 'var(--mac-bg-tertiary)', 
                    borderRadius: 'var(--mac-radius-full)', 
                    height: '8px' 
                  }}>
                    <div 
                      style={{ 
                        height: '8px', 
                        borderRadius: 'var(--mac-radius-full)',
                        width: `${(day.count / Math.max(...appointmentsData.byDay.map(d => d.count))) * 100}%`,
                        background: 'var(--mac-accent-blue)',
                        transition: 'width var(--mac-duration-normal) var(--mac-ease)'
                      }}
                    ></div>
                  </div>
                  <span style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)' 
                  }}>
                    {day.count}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </MacOSCard>
      </div>

      {/* Демография пациентов */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
        gap: '24px' 
      }}>
        <MacOSCard padding="large">
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            marginBottom: '16px',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
            Возрастные группы
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {patientsData.byAge.map((group, index) => (
              <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)' 
                }}>
                  {group.range} лет
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ 
                    width: '80px', 
                    backgroundColor: 'var(--mac-bg-tertiary)', 
                    borderRadius: 'var(--mac-radius-full)', 
                    height: '8px' 
                  }}>
                    <div 
                      style={{ 
                        height: '8px', 
                        borderRadius: 'var(--mac-radius-full)',
                        width: `${group.percentage}%`,
                        background: 'var(--mac-accent-blue)',
                        transition: 'width var(--mac-duration-normal) var(--mac-ease)'
                      }}
                    ></div>
                  </div>
                  <span style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)' 
                  }}>
                    {group.count}
                  </span>
                  <span style={{ 
                    fontSize: 'var(--mac-font-size-xs)', 
                    color: 'var(--mac-text-secondary)' 
                  }}>
                    ({group.percentage}%)
                  </span>
                </div>
              </div>
            ))}
          </div>
        </MacOSCard>

        <MacOSCard padding="large">
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            marginBottom: '16px',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
            Пол пациентов
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {patientsData.byGender.map((gender, index) => (
              <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)' 
                }}>
                  {gender.gender}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ 
                    width: '80px', 
                    backgroundColor: 'var(--mac-bg-tertiary)', 
                    borderRadius: 'var(--mac-radius-full)', 
                    height: '8px' 
                  }}>
                    <div 
                      style={{ 
                        height: '8px', 
                        borderRadius: 'var(--mac-radius-full)',
                        width: `${gender.percentage}%`,
                        background: index === 0 ? 'var(--mac-accent-blue)' : 'var(--mac-accent-blue)',
                        transition: 'width var(--mac-duration-normal) var(--mac-ease)'
                      }}
                    ></div>
                  </div>
                  <span style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-text-primary)' 
                  }}>
                    {gender.count}
                  </span>
                  <span style={{ 
                    fontSize: 'var(--mac-font-size-xs)', 
                    color: 'var(--mac-text-secondary)' 
                  }}>
                    ({gender.percentage}%)
                  </span>
                </div>
              </div>
            ))}
          </div>
        </MacOSCard>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;

