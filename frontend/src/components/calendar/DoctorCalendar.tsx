import type { CSSProperties } from 'react';

/**
 * DoctorCalendar Component
 * Календарь врача для просмотра расписания и записей на приём
 * Интегрируется с schedule API endpoints
 */
import { api } from '../../api/client';
import { useState, useEffect, useCallback } from 'react';
import {
  Calendar,

  ChevronLeft,
  ChevronRight,




  AlertCircle,
  RefreshCw } from

'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { getApiOrigin } from '../../api/runtime';
import tokenManager from '../../utils/tokenManager';
import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';
import i18n from '../../i18n';
const t18 = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;

const API_BASE = getApiOrigin();

/**
 * Форматирует дату в YYYY-MM-DD
 */
const formatDate = (date) => {
  if (!date) return '';
  const d = new Date(date);
  return d.toISOString().split('T')[0];
};

/**
 * Получает начало недели (понедельник)
 */
const getWeekStart = (date) => {
  const d = new Date(date);
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(d.setDate(diff));
};

/**
 * Генерирует массив дней недели
 */
const getWeekDays = (startDate) => {
  const days = [];
  const start = new Date(startDate);
  for (let i = 0; i < 7; i++) {
    const day = new Date(start);
    day.setDate(start.getDate() + i);
    days.push(day);
  }
  return days;
};

const WEEKDAY_NAMES = [t18('misc.dc_pn'), t18('misc.dc_vt'), t18('misc.dc_sr'), t18('misc.dc_cht'), t18('misc.dc_pt'), t18('misc.dc_sb'), t18('misc.dc_vs')];










/**
 * Главный компонент календаря врача
 */
const DoctorCalendar = ({
  doctorId,
  department,
  onSelectSlot,
  onViewAppointment,
  compact = false
}) => {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const [, setCurrentDate] = useState(new Date());
  const [weekStart, setWeekStart] = useState(getWeekStart(new Date()));
  const [weekDays, setWeekDays] = useState([]);
  const [schedule, setSchedule] = useState<Record<string, any>>({});
  useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  useState('week'); // 'week' | 'day' | 'month'
  const [, setSelectedDay] = useState(null);

  // Генерируем дни недели при изменении начала недели
  useEffect(() => {
    setWeekDays(getWeekDays(weekStart));
  }, [weekStart]);

  // Загружаем расписание
  const loadSchedule = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const token = tokenManager.getAccessToken();
      const params = new URLSearchParams({
        week_start: formatDate(weekStart)
      });

      if (doctorId) {
        params.append('doctor_id', doctorId);
      }
      if (department) {
        params.append('department', department);
      }

      const response = await fetch(
        `schedule/weekly?${params}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (!response.ok) {
        throw new Error(t18('misc.dc_ne_udalos_zagruzit_raspisani'));
      }

      const data = await response.json();
      setSchedule(data);

    } catch (err) {
      logger.error('Error loading schedule:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [weekStart, doctorId, department]);

  useEffect(() => {
    loadSchedule();
  }, [loadSchedule]);

  // Навигация по неделям
  const goToPrevWeek = () => {
    const newStart = new Date(weekStart);
    newStart.setDate(newStart.getDate() - 7);
    setWeekStart(newStart);
  };

  const goToNextWeek = () => {
    const newStart = new Date(weekStart);
    newStart.setDate(newStart.getDate() + 7);
    setWeekStart(newStart);
  };

  const goToToday = () => {
    setWeekStart(getWeekStart(new Date()));
    setCurrentDate(new Date());
  };
  const handleActivationKeyDown = (event, onActivate) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onActivate();
    }
  };

  // Стили
  const styles = {
    container: {
      backgroundColor: isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-primary)',
      borderRadius: 'var(--mac-radius-lg)',
      boxShadow: isDark ?
      '0 4px 20px color-mix(in srgb, var(--mac-text-primary), transparent 70%)' :
      '0 4px 20px rgba(0, 0, 0, 0.08)',
      overflow: 'hidden'
    },
    header: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      padding: '16px 20px',
      borderBottom: `1px solid ${isDark ? 'color-mix(in srgb, white, transparent 90%)' : 'color-mix(in srgb, black, transparent 92%)'}`,
      backgroundColor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)'
    },
    title: {
      fontSize: 'var(--mac-font-size-xl)',
      fontWeight: 'var(--mac-font-weight-semibold)',
      color: isDark ? 'var(--mac-text-primary)' : 'var(--mac-text-primary)',
      display: 'flex',
      alignItems: 'center',
      gap: '10px'
    },
    navButton: {
      padding: 'var(--mac-spacing-2)',
      borderRadius: 'var(--mac-radius-md)',
      border: 'none',
      backgroundColor: isDark ? 'color-mix(in srgb, white, transparent 92%)' : 'rgba(0,0,0,0.05)',
      color: isDark ? 'var(--mac-text-primary)' : 'var(--mac-text-primary)',
      cursor: 'pointer',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      transition: 'all 0.2s'
    },
    todayButton: {
      padding: 'var(--mac-spacing-2) var(--mac-spacing-4)',
      borderRadius: 'var(--mac-radius-md)',
      border: 'none',
      backgroundColor: 'var(--mac-accent-blue)',
      color: 'var(--mac-bg-primary)',
      fontSize: 'var(--mac-font-size-sm)',
      fontWeight: 'var(--mac-font-weight-medium)',
      cursor: 'pointer',
      transition: 'all 0.2s'
    },
    weekGrid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(7, 1fr)',
      gap: '1px',
      backgroundColor: isDark ? 'color-mix(in srgb, white, transparent 90%)' : 'color-mix(in srgb, black, transparent 92%)'
    },
    dayHeader: {
      padding: '12px 8px',
      textAlign: 'center',
      backgroundColor: isDark ? 'var(--mac-bg-secondary)' : 'var(--mac-bg-secondary)',
      fontSize: 'var(--mac-font-size-xs)',
      fontWeight: 'var(--mac-font-weight-semibold)',
      color: isDark ? 'var(--mac-text-secondary)' : '#6e6e73'
    },
    dayCell: {
      minHeight: compact ? '80px' : '120px',
      padding: 'var(--mac-spacing-2)',
      backgroundColor: isDark ? 'var(--mac-bg-primary)' : 'var(--mac-bg-primary)',
      position: 'relative'
    },
    dayCellToday: {
      backgroundColor: isDark ? 'var(--mac-accent-bg)' : 'rgba(0, 122, 255, 0.05)'
    },
    dayNumber: {
      fontSize: 'var(--mac-font-size-base)',
      fontWeight: 'var(--mac-font-weight-medium)',
      marginBottom: 'var(--mac-spacing-2)',
      color: isDark ? 'var(--mac-text-primary)' : 'var(--mac-text-primary)'
    },
    dayNumberToday: {
      width: '28px',
      height: '28px',
      borderRadius: '50%',
      backgroundColor: 'var(--mac-accent-blue)',
      color: 'var(--mac-bg-primary)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center'
    },
    slot: {
      padding: 'var(--mac-spacing-1) var(--mac-spacing-2)',
      marginBottom: 'var(--mac-spacing-1)',
      borderRadius: 'var(--mac-radius-sm)',
      fontSize: 'var(--mac-font-size-xs)',
      cursor: 'pointer',
      transition: 'all 0.2s'
    },
    slotAvailable: {
      backgroundColor: isDark ? 'var(--mac-success-border, color-mix(in srgb, var(--mac-success), transparent 80%))' : 'rgba(52, 199, 89, 0.1)',
      color: isDark ? '#32d74b' : '#248a3d'
    },
    slotBooked: {
      backgroundColor: isDark ? 'rgba(255, 69, 58, 0.2)' : 'rgba(255, 69, 58, 0.1)',
      color: isDark ? 'var(--mac-error)' : '#d70015'
    },
    loading: {
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      padding: '40px',
      color: isDark ? 'var(--mac-text-secondary)' : '#6e6e73'
    },
    error: {
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      padding: 'var(--mac-spacing-5)',
      color: 'var(--mac-error)',
      backgroundColor: isDark ? 'rgba(255, 59, 48, 0.1)' : 'rgba(255, 59, 48, 0.05)',
      margin: '16px',
      borderRadius: 'var(--mac-radius-md)'
    }
  };

  // Проверяем, является ли день сегодняшним
  const isToday = (date) => {
    const today = new Date();
    return date.toDateString() === today.toDateString();
  };

  // Рендерим слоты дня
  const renderDaySlots = (date) => {
    const dateStr = formatDate(date);
    const daySchedule = schedule[dateStr] || [];

    if (daySchedule.length === 0) {
      return (
        <div style={{ fontSize: 'var(--mac-font-size-xs)', color: isDark ? 'var(--mac-text-tertiary)' : 'var(--mac-text-tertiary)', fontStyle: 'italic' } as CSSProperties}>
                    Нет записей
                </div>);

    }

    return daySchedule.slice(0, compact ? 2 : 4).map((slot, idx) =>
    <div
      key={idx}
      role="button"
      tabIndex={0}
      style={{
        ...styles.slot,
        ...(slot.booked ? styles.slotBooked : styles.slotAvailable)
      } as CSSProperties}
      onClick={() => slot.booked ? onViewAppointment?.(slot) : onSelectSlot?.(slot, date)}
      onKeyDown={(event) => handleActivationKeyDown(event, () => (slot.booked ? onViewAppointment?.(slot) : onSelectSlot?.(slot, date)))}>

                <div style={{ fontWeight: 'var(--mac-font-weight-medium)' } as CSSProperties}>{slot.time || slot.start_time}</div>
                {slot.patient_name &&
      <div style={{ fontSize: 'var(--mac-font-size-xs)', opacity: 0.8 } as CSSProperties}>{slot.patient_name}</div>
      }
            </div>
    );
  };

  // Рендерим день
  const renderDay = (date, index) => {
    const today = isToday(date);

    return (
      <div
        key={index}
        role="button"
        tabIndex={0}
        style={{
          ...styles.dayCell,
          ...(today ? styles.dayCellToday : {})
        } as CSSProperties}
        onClick={() => setSelectedDay(date)}
        onKeyDown={(event) => handleActivationKeyDown(event, () => setSelectedDay(date))}>

                <div
          style={{
            ...styles.dayNumber,
            ...(today ? styles.dayNumberToday : {})
          } as CSSProperties}>

                    {date.getDate()}
                </div>
                {renderDaySlots(date)}
            </div>);

  };

  return (
    <div style={styles.container as unknown as CSSProperties}>
            {/* Header */}
            <div style={styles.header as unknown as CSSProperties}>
                <div style={styles.title as unknown as CSSProperties}>
                    <Calendar size={20 as unknown as "small" | "default" | "large" | "xlarge"} />
                    <span>
                        {weekDays.length > 0 &&
            <>
                                {weekDays[0].toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })}
                            </>
            }
                    </span>
                </div>

                <div style={{ display: 'flex', gap: 'var(--mac-spacing-2)', alignItems: 'center' } as CSSProperties}>
                    <button
            style={styles.navButton as unknown as CSSProperties}
            onClick={goToPrevWeek}
            title={t18('misc.dc_predyduschaya_nedelya')}
            aria-label={t18('misc.dc_predyduschaya_nedelya')}>

                        <ChevronLeft size={18 as unknown as "small" | "default" | "large" | "xlarge"} />
                    </button>

                    <button
            style={styles.todayButton as unknown as CSSProperties}
            onClick={goToToday}>

                        Сегодня
                    </button>

                    <button
            style={styles.navButton as unknown as CSSProperties}
            onClick={goToNextWeek}
            title={t18('misc.dc_sleduyuschaya_nedelya')}
            aria-label={t18('misc.dc_sleduyuschaya_nedelya')}>

                        <ChevronRight size={18 as unknown as "small" | "default" | "large" | "xlarge"} />
                    </button>

                    <button
            style={styles.navButton as unknown as CSSProperties}
            onClick={loadSchedule}
            title={t18('misc.dc_obnovit')}
            aria-label={t18('misc.dc_obnovit')}>

                        <RefreshCw size={16 as unknown as "small" | "default" | "large" | "xlarge"} className={loading ? 'spinning' : ''} />
                    </button>
                </div>
            </div>

            {/* Error */}
            {error &&
      <div style={styles.error as unknown as CSSProperties}>
                    <AlertCircle size={16 as unknown as "small" | "default" | "large" | "xlarge"} style={{ marginRight: 'var(--mac-spacing-2)' }} />
                    {error}
                </div>
      }

            {/* Loading */}
            {loading ?
      <div style={styles.loading as unknown as CSSProperties}>
                    <RefreshCw size={24 as unknown as "small" | "default" | "large" | "xlarge"} className="spinning" style={{ marginRight: 'var(--mac-spacing-2)' }} />
                    Загрузка расписания...
                </div> :

      <>
                    {/* Week Grid */}
                    <div style={styles.weekGrid as unknown as CSSProperties}>
                        {/* Day Headers */}
                        {WEEKDAY_NAMES.map((name, idx) =>
          <div key={idx} style={styles.dayHeader as unknown as CSSProperties}>
                                {name}
                            </div>
          )}

                        {/* Day Cells */}
                        {weekDays.map((day, idx) => renderDay(day, idx))}
                    </div>
                </>
      }

            {/* Spinning animation */}
            <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .spinning {
          animation: spin 1s linear infinite;
        }
      `}</style>
        </div>);

};


DoctorCalendar.propTypes = {
  ...(DoctorCalendar.propTypes || {}),
  compact: PropTypes.any,
  department: PropTypes.any,
  doctorId: PropTypes.any,
  onSelectSlot: PropTypes.any,
  onViewAppointment: PropTypes.any,
};

export default DoctorCalendar;
