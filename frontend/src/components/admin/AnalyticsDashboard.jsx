import React, { useState } from 'react';
import {


  TrendingUp,
  TrendingDown,
  Users,
  Calendar,
  DollarSign,



  Award } from

'lucide-react';
import { Card as MacOSCard } from '../ui/macos';
import PropTypes from 'prop-types';








const AnalyticsDashboard = ({
  data = {},
  loading = false
}) => {void
  useState('revenue');void
  useState('month');

  // Empty shape only; operational analytics must come from backend data.
  const emptyData = {
    overview: {
      totalRevenue: 0,
      totalPatients: 0,
      totalAppointments: 0,
      averageRating: 0,
      revenueGrowth: 0,
      patientGrowth: 0,
      appointmentGrowth: 0,
      ratingGrowth: 0
    },
    revenue: {
      daily: [],

      byCategory: [],

      byDoctor: []

    },
    appointments: {
      byStatus: [],

      byDay: [],

      byTime: []

    },
    patients: {
      byAge: [],

      byGender: [],

      newVsReturning: []

    },
    performance: {
      doctors: [],

      departments: []

    }
  };

  const currentData = data.overview || emptyData.overview;
  const revenueData = data.revenue || emptyData.revenue;
  const appointmentsData = data.appointments || emptyData.appointments;
  const patientsData = data.patients || emptyData.patients;void (
  data.performance || emptyData.performance);

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
      <div
        role="status"
        aria-label="Загрузка аналитики"
        style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
          gap: '16px'
        }}>
          {[...Array(4)].map((_, i) =>
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
          )}
        </div>
      </div>);

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
                  'aria-hidden': true,
                  focusable: 'false',
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
                  }}>

                  {formatPercentage(currentData.revenueGrowth)}
                </span>
              </div>
            </div>
            <DollarSign aria-hidden="true" focusable="false" style={{ width: '32px', height: '32px', color: 'var(--mac-success)' }} />
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
                  'aria-hidden': true,
                  focusable: 'false',
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
                  }}>

                  {formatPercentage(currentData.patientGrowth)}
                </span>
              </div>
            </div>
            <Users aria-hidden="true" focusable="false" style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
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
                  'aria-hidden': true,
                  focusable: 'false',
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
                  }}>

                  {formatPercentage(currentData.appointmentGrowth)}
                </span>
              </div>
            </div>
            <Calendar aria-hidden="true" focusable="false" style={{ width: '32px', height: '32px', color: 'var(--mac-accent-blue)' }} />
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
                  'aria-hidden': true,
                  focusable: 'false',
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
                  }}>

                  {formatPercentage(currentData.ratingGrowth)}
                </span>
              </div>
            </div>
            <Award aria-hidden="true" focusable="false" style={{ width: '32px', height: '32px', color: 'var(--mac-warning)' }} />
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
            {revenueData.byCategory.map((item, index) =>
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
                  <div
                  role="progressbar"
                  aria-label={`Доля дохода категории ${item.category}`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={item.percentage}
                  style={{
                  width: '100%',
                  backgroundColor: 'var(--mac-bg-tertiary)',
                  borderRadius: 'var(--mac-radius-full)',
                  height: '8px'
                }}>
                    <div
                    aria-hidden="true"
                    style={{
                      height: '8px',
                      borderRadius: 'var(--mac-radius-full)',
                      width: `${item.percentage}%`,
                      background: 'var(--mac-accent-blue)',
                      transition: 'width var(--mac-duration-normal) var(--mac-ease)'
                    }}>
                  </div>
                  </div>
                  <span style={{
                  fontSize: 'var(--mac-font-size-xs)',
                  color: 'var(--mac-text-secondary)'
                }}>
                    {item.percentage}%
                  </span>
                </div>
              </div>
            )}
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
            {appointmentsData.byStatus.map((item, index) =>
            <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div
                  aria-hidden="true"
                  style={{
                    width: '12px',
                    height: '12px',
                    borderRadius: 'var(--mac-radius-full)',
                    background: index === 0 ? 'var(--mac-success)' :
                    index === 1 ? 'var(--mac-warning)' : 'var(--mac-danger)'
                  }}>
                </div>
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
            )}
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
            {revenueData.byDoctor.map((doctor, index) =>
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
            )}
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
            {appointmentsData.byDay.map((day, index) =>
            <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)'
              }}>
                  {day.day}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div
                  role="progressbar"
                  aria-label={`Количество записей в день ${day.day}`}
                  aria-valuemin={0}
                  aria-valuemax={Math.max(...appointmentsData.byDay.map((d) => d.count))}
                  aria-valuenow={day.count}
                  style={{
                  width: '96px',
                  backgroundColor: 'var(--mac-bg-tertiary)',
                  borderRadius: 'var(--mac-radius-full)',
                  height: '8px'
                }}>
                    <div
                    aria-hidden="true"
                    style={{
                      height: '8px',
                      borderRadius: 'var(--mac-radius-full)',
                      width: `${day.count / Math.max(...appointmentsData.byDay.map((d) => d.count)) * 100}%`,
                      background: 'var(--mac-accent-blue)',
                      transition: 'width var(--mac-duration-normal) var(--mac-ease)'
                    }}>
                  </div>
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
            )}
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
            {patientsData.byAge.map((group, index) =>
            <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)'
              }}>
                  {group.range} лет
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div
                  role="progressbar"
                  aria-label={`Доля пациентов в возрастной группе ${group.range}`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={group.percentage}
                  style={{
                  width: '80px',
                  backgroundColor: 'var(--mac-bg-tertiary)',
                  borderRadius: 'var(--mac-radius-full)',
                  height: '8px'
                }}>
                    <div
                    aria-hidden="true"
                    style={{
                      height: '8px',
                      borderRadius: 'var(--mac-radius-full)',
                      width: `${group.percentage}%`,
                      background: 'var(--mac-accent-blue)',
                      transition: 'width var(--mac-duration-normal) var(--mac-ease)'
                    }}>
                  </div>
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
            )}
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
            {patientsData.byGender.map((gender, index) =>
            <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)'
              }}>
                  {gender.gender}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div
                  role="progressbar"
                  aria-label={`Доля пациентов: ${gender.gender}`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={gender.percentage}
                  style={{
                  width: '80px',
                  backgroundColor: 'var(--mac-bg-tertiary)',
                  borderRadius: 'var(--mac-radius-full)',
                  height: '8px'
                }}>
                    <div
                    aria-hidden="true"
                    style={{
                      height: '8px',
                      borderRadius: 'var(--mac-radius-full)',
                      width: `${gender.percentage}%`,
                      background: index === 0 ? 'var(--mac-accent-blue)' : 'var(--mac-accent-blue)',
                      transition: 'width var(--mac-duration-normal) var(--mac-ease)'
                    }}>
                  </div>
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
            )}
          </div>
        </MacOSCard>
      </div>
    </div>);

};


AnalyticsDashboard.propTypes = {
  ...(AnalyticsDashboard.propTypes || {}),
  data: PropTypes.any,
  loading: PropTypes.any,
};

export default AnalyticsDashboard;
