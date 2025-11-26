import React, { useState, useEffect, useMemo } from 'react';
import { useTheme } from '../../contexts/ThemeContext';
import { Button, Card, Icon } from '../ui/macos';

const ModernStatistics = ({
  appointments = [],
  departmentStats = {},
  language = 'ru',
  selectedDate = null, // YYYY-MM-DD, если не передан — используется сегодня
  onExport,
  onRefresh,
  className = '',
  ...props
}) => {
  const { theme, getColor, getSpacing, getFontSize } = useTheme();
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
    const targetDate = selectedDate || new Date().toISOString().split('T')[0];
    const dayAppointments = appointments.filter(apt => {
      const aptDate = apt.date || apt.appointment_date;
      return aptDate === targetDate;
    });

    // Завершенные визиты за выбранный день
    const completedToday = dayAppointments.filter(apt => 
      apt.status === 'completed' || apt.status === 'done'
    );

    // Ожидают оплаты за выбранный день
    const pendingPayments = dayAppointments.filter(apt => 
      apt.status === 'paid_pending' || apt.payment_status === 'pending'
    );

    // Выручка: суммируем оплаченные записи (по payment_status), а не только завершенные
    const totalRevenue = dayAppointments
      .filter(apt => apt.payment_status === 'paid')
      .reduce((sum, apt) => sum + (apt.payment_amount || apt.cost || 0), 0);

    // Уникальные пациенты
    const uniquePatients = new Set(dayAppointments.map(apt => apt.patient_id)).size;

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
      todayAppointments: dayAppointments.length,
      completedToday: completedToday.length,
      pendingPayments: pendingPayments.length,
      revenue: totalRevenue,
      averageWaitTime,
      trends,
      trendValues
    };
  }, [appointments, selectedDate]);

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

  // Данные для карточек статистики с правильными иконками
  const statCards = [
    {
      id: 'totalPatients',
      title: t.totalPatients,
      value: animatedValues.totalPatients || 0,
      iconName: 'person',
      color: '#007aff',
      trend: statistics.trends.patients,
      trendValue: statistics.trendValues.patients,
      suffix: ''
    },
    {
      id: 'todayAppointments',
      title: t.todayAppointments,
      value: animatedValues.todayAppointments || 0,
      iconName: 'calendar',
      color: '#34c759',
      trend: statistics.trends.appointments,
      trendValue: statistics.trendValues.appointments,
      suffix: ''
    },
    {
      id: 'completedToday',
      title: t.completedToday,
      value: animatedValues.completedToday || 0,
      iconName: 'checkmark.circle',
      color: '#5ac8fa',
      trend: statistics.trends.appointments,
      trendValue: statistics.trendValues.appointments,
      suffix: ''
    },
    {
      id: 'pendingPayments',
      title: t.pendingPayments,
      value: animatedValues.pendingPayments || 0,
      iconName: 'creditcard',
      color: '#ff9500',
      trend: 'down',
      trendValue: Math.floor(Math.random() * 5) + 1,
      suffix: ''
    },
    {
      id: 'revenue',
      title: t.revenue,
      value: animatedValues.revenue || 0,
      iconName: 'creditcard',
      color: '#34c759',
      trend: statistics.trends.revenue,
      trendValue: statistics.trendValues.revenue,
      suffix: ' ' + t.sum,
      format: 'currency'
    },
    {
      id: 'averageWaitTime',
      title: t.averageWaitTime,
      value: statistics.averageWaitTime,
      iconName: 'clock',
      color: '#5ac8fa',
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

  // Получение цвета тренда
  const getTrendColor = (trend, isGoodWhenDown = false) => {
    if (isGoodWhenDown) {
      return trend === 'down' ? '#34c759' : '#ff3b30';
    }
    return trend === 'up' ? '#34c759' : '#ff3b30';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-5)' }} {...props}>
      {/* Заголовок */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 'var(--mac-spacing-4)'
      }}>
        <h2 style={{ 
          color: 'var(--mac-text-primary)', 
          fontSize: 'var(--mac-font-size-xl)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          margin: 0,
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
          <Icon name="chart.bar" size="default" style={{ color: 'var(--mac-accent-blue)' }} />
          {t.statistics}
        </h2>
        
        <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)' }}>
          <Button variant="ghost" size="small" onClick={onRefresh} title={t.refresh}>
            <Icon name="gear" size="small" />
          </Button>
          <Button variant="primary" size="small" onClick={onExport} title={t.export}>
            <Icon name="square.and.arrow.up" size="small" style={{ color: 'white' }} />
          </Button>
        </div>
      </div>

      {/* Основные карточки статистики с улучшенной видимостью */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: 'var(--mac-spacing-4)'
      }}>
        {statCards.map((card) => {
          const isGoodWhenDown = card.id === 'pendingPayments' || card.id === 'averageWaitTime';
          
          return (
            <Card
              key={card.id}
              style={{
                padding: 'var(--mac-spacing-6)',
                backgroundColor: 'var(--mac-bg-toolbar)',
                border: '2px solid var(--mac-separator)',
                borderRadius: 'var(--mac-radius-lg)',
                boxShadow: 'var(--mac-shadow-md)',
                backdropFilter: 'var(--mac-blur-light)',
                WebkitBackdropFilter: 'var(--mac-blur-light)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--mac-spacing-4)'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Icon name={card.iconName} size="xlarge" style={{ color: card.color }} />
                
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  fontSize: '32px', // 32px как у левой иконки
                  fontWeight: 'var(--mac-font-weight-bold)',
                  color: getTrendColor(card.trend, isGoodWhenDown)
                }}>
                  <Icon 
                    name={card.trend === 'up' ? 'checkmark.circle' : 'xmark.circle'} 
                    size="xlarge" // xlarge для ровного размера с левой иконкой
                    style={{ color: getTrendColor(card.trend, isGoodWhenDown) }} 
                  />
                  {card.trendValue}%
                </div>
              </div>
              
              <div>
                <div style={{
                  fontSize: '42px',
                  fontWeight: 'var(--mac-font-weight-bold)',
                  color: 'var(--mac-text-primary)',
                  lineHeight: 1.1,
                  marginBottom: 'var(--mac-spacing-2)'
                }}>
                  {formatValue(card.value, card.format)}
                  <span style={{ fontSize: '28px', fontWeight: 'var(--mac-font-weight-semibold)', marginLeft: '8px' }}>
                    {card.suffix}
                  </span>
                </div>
                
                <div style={{
                  fontSize: 'var(--mac-font-size-base)',
                  color: 'var(--mac-text-secondary)',
                  fontWeight: 'var(--mac-font-weight-semibold)'
                }}>
                  {card.title}
                </div>
              </div>
              
              {/* Прогресс бар */}
              <div style={{
                height: '4px',
                backgroundColor: 'var(--mac-separator)',
                borderRadius: 'var(--mac-radius-full)',
                overflow: 'hidden',
                marginTop: 'var(--mac-spacing-2)'
              }}>
                <div style={{
                  height: '100%',
                  backgroundColor: card.color,
                  width: `${Math.min((card.value / (card.value + 10)) * 100, 100)}%`,
                  borderRadius: 'var(--mac-radius-full)',
                  transition: 'width var(--mac-duration-normal) var(--mac-ease)'
                }} />
              </div>
            </Card>
          );
        })}
      </div>

      {/* Детальная статистика удалена - для упрощения UI */}
    </div>
  );
};

export default ModernStatistics;


