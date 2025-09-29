import React, { useState, useEffect, useMemo } from 'react';
import { 
  Users, 
  Calendar, 
  Clock, 
  CreditCard, 
  TrendingUp, 
  TrendingDown,
  Activity,
  CheckCircle,
  XCircle,
  AlertCircle,
  Download,
  RefreshCw,
  BarChart3,
  PieChart,
  Eye,
  Filter
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import './ModernStatistics.css';

const ModernStatistics = ({
  appointments = [],
  departmentStats = {},
  language = 'ru',
  onExport,
  onRefresh,
  className = '',
  ...props
}) => {
  const { theme, getColor } = useTheme();
  const [animatedValues, setAnimatedValues] = useState({});
  const [selectedPeriod, setSelectedPeriod] = useState('today');
  const [showDetails, setShowDetails] = useState(false);

  // Переводы
  const t = {
    ru: {
      statistics: 'Статистика',
      totalPatients: 'Всего пациентов',
      todayAppointments: 'Записи сегодня',
      pendingPayments: 'Ожидают оплаты',
      completedToday: 'Завершено сегодня',
      revenue: 'Выручка',
      averageWaitTime: 'Среднее время ожидания',
      departmentLoad: 'Загрузка отделений',
      trends: 'Тенденции',
      today: 'Сегодня',
      week: 'Неделя',
      month: 'Месяц',
      year: 'Год',
      export: 'Экспорт',
      refresh: 'Обновить',
      details: 'Подробнее',
      minutes: 'мин',
      patients: 'пациентов',
      appointments: 'записей',
      sum: 'сум',
      growth: 'рост',
      decline: 'снижение'
    }
  }[language] || {};

  // Вычисление статистики
  const statistics = useMemo(() => {
    const today = new Date().toISOString().split('T')[0];
    const todayAppointments = appointments.filter(apt => {
      const aptDate = apt.date || apt.appointment_date;
      return aptDate === today;
    });

    const completedToday = todayAppointments.filter(apt => 
      apt.status === 'completed' || apt.status === 'done'
    );

    const pendingPayments = appointments.filter(apt => 
      apt.status === 'paid_pending' || apt.payment_status === 'pending'
    );

    const totalRevenue = completedToday.reduce((sum, apt) => 
      sum + (apt.payment_amount || apt.cost || 0), 0
    );

    // Уникальные пациенты
    const uniquePatients = new Set(appointments.map(apt => apt.patient_id)).size;

    // Среднее время ожидания (мок)
    const averageWaitTime = Math.floor(Math.random() * 30) + 10;

    // Тенденции (мок данных)
    const trends = {
      appointments: Math.random() > 0.5 ? 'up' : 'down',
      revenue: Math.random() > 0.5 ? 'up' : 'down',
      patients: Math.random() > 0.5 ? 'up' : 'down',
      waitTime: Math.random() > 0.5 ? 'down' : 'up' // для времени ожидания down - это хорошо
    };

    const trendValues = {
      appointments: Math.floor(Math.random() * 20) + 5,
      revenue: Math.floor(Math.random() * 15) + 3,
      patients: Math.floor(Math.random() * 25) + 8,
      waitTime: Math.floor(Math.random() * 10) + 2
    };

    return {
      totalPatients: uniquePatients,
      todayAppointments: todayAppointments.length,
      completedToday: completedToday.length,
      pendingPayments: pendingPayments.length,
      revenue: totalRevenue,
      averageWaitTime,
      trends,
      trendValues
    };
  }, [appointments]);

  // Анимация счетчиков
  useEffect(() => {
    const animateValue = (key, targetValue) => {
      const duration = 1000;
      const steps = 60;
      const stepValue = targetValue / steps;
      let currentValue = 0;
      let step = 0;

      const timer = setInterval(() => {
        step++;
        currentValue = Math.min(stepValue * step, targetValue);
        
        setAnimatedValues(prev => ({
          ...prev,
          [key]: Math.floor(currentValue)
        }));

        if (step >= steps) {
          clearInterval(timer);
        }
      }, duration / steps);

      return timer;
    };

    const timers = [
      animateValue('totalPatients', statistics.totalPatients),
      animateValue('todayAppointments', statistics.todayAppointments),
      animateValue('completedToday', statistics.completedToday),
      animateValue('pendingPayments', statistics.pendingPayments),
      animateValue('revenue', statistics.revenue)
    ];

    return () => {
      timers.forEach(timer => clearInterval(timer));
    };
  }, [statistics]);

  // Данные для карточек статистики
  const statCards = [
    {
      id: 'totalPatients',
      title: t.totalPatients,
      value: animatedValues.totalPatients || 0,
      icon: Users,
      color: getColor('primary'),
      trend: statistics.trends.patients,
      trendValue: statistics.trendValues.patients,
      suffix: ''
    },
    {
      id: 'todayAppointments',
      title: t.todayAppointments,
      value: animatedValues.todayAppointments || 0,
      icon: Calendar,
      color: getColor('success'),
      trend: statistics.trends.appointments,
      trendValue: statistics.trendValues.appointments,
      suffix: ''
    },
    {
      id: 'completedToday',
      title: t.completedToday,
      value: animatedValues.completedToday || 0,
      icon: CheckCircle,
      color: getColor('info'),
      trend: statistics.trends.appointments,
      trendValue: statistics.trendValues.appointments,
      suffix: ''
    },
    {
      id: 'pendingPayments',
      title: t.pendingPayments,
      value: animatedValues.pendingPayments || 0,
      icon: CreditCard,
      color: getColor('warning'),
      trend: 'down', // для pending payments down - это хорошо
      trendValue: Math.floor(Math.random() * 5) + 1,
      suffix: ''
    },
    {
      id: 'revenue',
      title: t.revenue,
      value: animatedValues.revenue || 0,
      icon: TrendingUp,
      color: getColor('success'),
      trend: statistics.trends.revenue,
      trendValue: statistics.trendValues.revenue,
      suffix: ' ' + t.sum,
      format: 'currency'
    },
    {
      id: 'averageWaitTime',
      title: t.averageWaitTime,
      value: statistics.averageWaitTime,
      icon: Clock,
      color: getColor('info'),
      trend: statistics.trends.waitTime,
      trendValue: statistics.trendValues.waitTime,
      suffix: ' ' + t.minutes
    }
  ];

  // Форматирование значений
  const formatValue = (value, format) => {
    if (format === 'currency') {
      return new Intl.NumberFormat('ru-RU').format(value);
    }
    return value.toLocaleString('ru-RU');
  };

  // Получение иконки тренда
  const getTrendIcon = (trend) => {
    return trend === 'up' ? TrendingUp : TrendingDown;
  };

  // Получение цвета тренда
  const getTrendColor = (trend, isGoodWhenDown = false) => {
    if (isGoodWhenDown) {
      return trend === 'down' ? getColor('success') : getColor('danger');
    }
    return trend === 'up' ? getColor('success') : getColor('danger');
  };

  return (
    <div className={`modern-statistics ${className}`} {...props}>
      {/* Заголовок */}
      <div className="stats-header">
        <div className="stats-title">
          <BarChart3 size={24} style={{ color: getColor('primary') }} />
          <h2 style={{ color: getColor('textPrimary') }}>{t.statistics}</h2>
        </div>
        
        <div className="stats-controls">
          <select
            value={selectedPeriod}
            onChange={(e) => setSelectedPeriod(e.target.value)}
            className="period-select"
            style={{
              backgroundColor: getColor('cardBg'),
              color: getColor('textPrimary'),
              borderColor: getColor('border')
            }}
          >
            <option value="today">{t.today}</option>
            <option value="week">{t.week}</option>
            <option value="month">{t.month}</option>
            <option value="year">{t.year}</option>
          </select>
          
          <button
            type="button"
            className="stats-action-btn"
            onClick={onRefresh}
            title={t.refresh}
            style={{
              backgroundColor: getColor('cardBg'),
              color: getColor('textPrimary'),
              borderColor: getColor('border')
            }}
          >
            <RefreshCw size={16} />
          </button>
          
          <button
            type="button"
            className="stats-action-btn"
            onClick={onExport}
            title={t.export}
            style={{
              backgroundColor: getColor('primary'),
              color: 'white'
            }}
          >
            <Download size={16} />
          </button>
          
          <button
            type="button"
            className="stats-action-btn"
            onClick={() => setShowDetails(!showDetails)}
            title={t.details}
            style={{
              backgroundColor: showDetails ? getColor('primary') : getColor('cardBg'),
              color: showDetails ? 'white' : getColor('textPrimary'),
              borderColor: getColor('border')
            }}
          >
            <Eye size={16} />
          </button>
        </div>
      </div>

      {/* Основные карточки статистики */}
      <div className="stats-grid">
        {statCards.map((card, index) => {
          const TrendIcon = getTrendIcon(card.trend);
          const isGoodWhenDown = card.id === 'pendingPayments' || card.id === 'averageWaitTime';
          
          return (
            <div
              key={card.id}
              className="stat-card"
              style={{
                backgroundColor: getColor('cardBg'),
                borderColor: getColor('border'),
                animationDelay: `${index * 100}ms`
              }}
            >
              <div className="stat-card-header">
                <div 
                  className="stat-icon"
                  style={{ backgroundColor: card.color }}
                >
                  <card.icon size={24} />
                </div>
                
                <div className="stat-trend">
                  <TrendIcon 
                    size={16} 
                    style={{ 
                      color: getTrendColor(card.trend, isGoodWhenDown)
                    }} 
                  />
                  <span 
                    style={{ 
                      color: getTrendColor(card.trend, isGoodWhenDown),
                      fontSize: '12px',
                      fontWeight: '600'
                    }}
                  >
                    {card.trendValue}%
                  </span>
                </div>
              </div>
              
              <div className="stat-content">
                <div 
                  className="stat-value"
                  style={{ color: getColor('textPrimary') }}
                >
                  {formatValue(card.value, card.format)}
                  <span className="stat-suffix">{card.suffix}</span>
                </div>
                
                <div 
                  className="stat-label"
                  style={{ color: getColor('textSecondary') }}
                >
                  {card.title}
                </div>
              </div>
              
              <div className="stat-progress">
                <div 
                  className="stat-progress-bar"
                  style={{
                    backgroundColor: card.color,
                    width: `${Math.min((card.value / (card.value + 10)) * 100, 100)}%`
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Детальная статистика */}
      {showDetails && (
        <div className="stats-details" style={{ backgroundColor: getColor('cardBg') }}>
          <div className="details-header">
            <h3 style={{ color: getColor('textPrimary') }}>
              {t.departmentLoad}
            </h3>
          </div>
          
          <div className="department-stats">
            {Object.entries(departmentStats).map(([dept, stats]) => {
              const departmentNames = {
                cardio: 'Кардиология',
                echokg: 'ЭКГ',
                derma: 'Дерматология',
                dental: 'Стоматология',
                lab: 'Лаборатория',
                procedures: 'Процедуры'
              };
              
              return (
                <div 
                  key={dept}
                  className="department-stat"
                  style={{ borderColor: getColor('border') }}
                >
                  <div className="department-info">
                    <span 
                      className="department-name"
                      style={{ color: getColor('textPrimary') }}
                    >
                      {departmentNames[dept] || dept}
                    </span>
                    
                    <div className="department-indicators">
                      {stats.hasActiveQueue && (
                        <span 
                          className="indicator queue"
                          style={{ backgroundColor: getColor('warning') }}
                          title="Активная очередь"
                        >
                          <Clock size={12} />
                        </span>
                      )}
                      
                      {stats.hasPendingPayments && (
                        <span 
                          className="indicator payment"
                          style={{ backgroundColor: getColor('danger') }}
                          title="Ожидают оплаты"
                        >
                          <AlertCircle size={12} />
                        </span>
                      )}
                    </div>
                  </div>
                  
                  <div className="department-count">
                    <span 
                      className="count-value"
                      style={{ color: getColor('textPrimary') }}
                    >
                      {stats.todayCount || 0}
                    </span>
                    <span 
                      className="count-label"
                      style={{ color: getColor('textSecondary') }}
                    >
                      {t.appointments}
                    </span>
                  </div>
                  
                  <div className="department-progress">
                    <div 
                      className="progress-bar"
                      style={{
                        backgroundColor: getColor('primary'),
                        width: `${Math.min((stats.todayCount / 20) * 100, 100)}%`
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default ModernStatistics;


