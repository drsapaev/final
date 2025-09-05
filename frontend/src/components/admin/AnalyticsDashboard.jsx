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
import { Card, Badge } from '../../design-system/components';

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
    return value > 0 ? 'var(--success-color)' : 'var(--danger-color)';
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="p-4">
              <div className="animate-pulse">
                <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
                <div className="h-8 bg-gray-200 rounded w-1/2"></div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Обзорные метрики */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                Общий доход
              </p>
              <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {formatCurrency(currentData.totalRevenue)}
              </p>
              <div className="flex items-center mt-1">
                {React.createElement(getGrowthIcon(currentData.revenueGrowth), {
                  className: "w-4 h-4 mr-1",
                  style: { color: getGrowthColor(currentData.revenueGrowth) }
                })}
                <span 
                  className="text-sm font-medium"
                  style={{ color: getGrowthColor(currentData.revenueGrowth) }}
                >
                  {formatPercentage(currentData.revenueGrowth)}
                </span>
              </div>
            </div>
            <DollarSign className="w-8 h-8" style={{ color: 'var(--success-color)' }} />
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                Пациенты
              </p>
              <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {currentData.totalPatients.toLocaleString()}
              </p>
              <div className="flex items-center mt-1">
                {React.createElement(getGrowthIcon(currentData.patientGrowth), {
                  className: "w-4 h-4 mr-1",
                  style: { color: getGrowthColor(currentData.patientGrowth) }
                })}
                <span 
                  className="text-sm font-medium"
                  style={{ color: getGrowthColor(currentData.patientGrowth) }}
                >
                  {formatPercentage(currentData.patientGrowth)}
                </span>
              </div>
            </div>
            <Users className="w-8 h-8" style={{ color: 'var(--info-color)' }} />
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                Записи
              </p>
              <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {currentData.totalAppointments.toLocaleString()}
              </p>
              <div className="flex items-center mt-1">
                {React.createElement(getGrowthIcon(currentData.appointmentGrowth), {
                  className: "w-4 h-4 mr-1",
                  style: { color: getGrowthColor(currentData.appointmentGrowth) }
                })}
                <span 
                  className="text-sm font-medium"
                  style={{ color: getGrowthColor(currentData.appointmentGrowth) }}
                >
                  {formatPercentage(currentData.appointmentGrowth)}
                </span>
              </div>
            </div>
            <Calendar className="w-8 h-8" style={{ color: 'var(--accent-color)' }} />
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                Рейтинг
              </p>
              <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {currentData.averageRating}
              </p>
              <div className="flex items-center mt-1">
                {React.createElement(getGrowthIcon(currentData.ratingGrowth), {
                  className: "w-4 h-4 mr-1",
                  style: { color: getGrowthColor(currentData.ratingGrowth) }
                })}
                <span 
                  className="text-sm font-medium"
                  style={{ color: getGrowthColor(currentData.ratingGrowth) }}
                >
                  {formatPercentage(currentData.ratingGrowth)}
                </span>
              </div>
            </div>
            <Award className="w-8 h-8" style={{ color: 'var(--warning-color)' }} />
          </div>
        </Card>
      </div>

      {/* Детальная аналитика */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Доходы по категориям */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
            Доходы по категориям
          </h3>
          <div className="space-y-3">
            {revenueData.byCategory.map((item, index) => (
              <div key={index} className="flex items-center justify-between">
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                      {item.category}
                    </span>
                    <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                      {formatCurrency(item.amount)}
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className="h-2 rounded-full" 
                      style={{ 
                        width: `${item.percentage}%`,
                        background: 'var(--accent-color)'
                      }}
                    ></div>
                  </div>
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    {item.percentage}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Статус записей */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
            Статус записей
          </h3>
          <div className="space-y-3">
            {appointmentsData.byStatus.map((item, index) => (
              <div key={index} className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div 
                    className="w-3 h-3 rounded-full"
                    style={{ 
                      background: index === 0 ? 'var(--success-color)' : 
                                 index === 1 ? 'var(--warning-color)' : 'var(--danger-color)'
                    }}
                  ></div>
                  <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                    {item.status}
                  </span>
                </div>
                <div className="text-right">
                  <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                    {item.count}
                  </span>
                  <span className="text-xs ml-2" style={{ color: 'var(--text-secondary)' }}>
                    ({item.percentage}%)
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Топ врачей по доходам */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
            Топ врачей по доходам
          </h3>
          <div className="space-y-3">
            {revenueData.byDoctor.map((doctor, index) => (
              <div key={index} className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-sm font-medium"
                       style={{ background: 'var(--accent-color)' }}>
                    {index + 1}
                  </div>
                  <div>
                    <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                      {doctor.doctor}
                    </p>
                    <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                      {doctor.appointments} записей
                    </p>
                  </div>
                </div>
                <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                  {formatCurrency(doctor.amount)}
                </span>
              </div>
            ))}
          </div>
        </Card>

        {/* Распределение по дням недели */}
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
            Записи по дням недели
          </h3>
          <div className="space-y-3">
            {appointmentsData.byDay.map((day, index) => (
              <div key={index} className="flex items-center justify-between">
                <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                  {day.day}
                </span>
                <div className="flex items-center space-x-3">
                  <div className="w-24 bg-gray-200 rounded-full h-2">
                    <div 
                      className="h-2 rounded-full" 
                      style={{ 
                        width: `${(day.count / Math.max(...appointmentsData.byDay.map(d => d.count))) * 100}%`,
                        background: 'var(--accent-color)'
                      }}
                    ></div>
                  </div>
                  <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                    {day.count}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* Демография пациентов */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
            Возрастные группы
          </h3>
          <div className="space-y-3">
            {patientsData.byAge.map((group, index) => (
              <div key={index} className="flex items-center justify-between">
                <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                  {group.range} лет
                </span>
                <div className="flex items-center space-x-3">
                  <div className="w-20 bg-gray-200 rounded-full h-2">
                    <div 
                      className="h-2 rounded-full" 
                      style={{ 
                        width: `${group.percentage}%`,
                        background: 'var(--info-color)'
                      }}
                    ></div>
                  </div>
                  <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                    {group.count}
                  </span>
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    ({group.percentage}%)
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-6">
          <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
            Пол пациентов
          </h3>
          <div className="space-y-3">
            {patientsData.byGender.map((gender, index) => (
              <div key={index} className="flex items-center justify-between">
                <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                  {gender.gender}
                </span>
                <div className="flex items-center space-x-3">
                  <div className="w-20 bg-gray-200 rounded-full h-2">
                    <div 
                      className="h-2 rounded-full" 
                      style={{ 
                        width: `${gender.percentage}%`,
                        background: index === 0 ? 'var(--info-color)' : 'var(--accent-color)'
                      }}
                    ></div>
                  </div>
                  <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                    {gender.count}
                  </span>
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    ({gender.percentage}%)
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
};

export default AnalyticsDashboard;
