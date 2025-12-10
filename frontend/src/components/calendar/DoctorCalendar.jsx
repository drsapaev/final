/**
 * DoctorCalendar Component
 * Календарь врача для просмотра расписания и записей на приём
 * Интегрируется с schedule API endpoints
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
    Calendar,
    Clock,
    ChevronLeft,
    ChevronRight,
    User,
    Users,
    Check,
    X,
    AlertCircle,
    RefreshCw,
    Filter,
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

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

const WEEKDAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const WEEKDAY_NAMES_FULL = [
    'Понедельник',
    'Вторник',
    'Среда',
    'Четверг',
    'Пятница',
    'Суббота',
    'Воскресенье',
];

/**
 * Главный компонент календаря врача
 */
const DoctorCalendar = ({
    doctorId,
    department,
    onSelectSlot,
    onViewAppointment,
    compact = false,
}) => {
    const { theme } = useTheme();
    const isDark = theme === 'dark';

    const [currentDate, setCurrentDate] = useState(new Date());
    const [weekStart, setWeekStart] = useState(getWeekStart(new Date()));
    const [weekDays, setWeekDays] = useState([]);
    const [schedule, setSchedule] = useState({});
    const [appointments, setAppointments] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [viewMode, setViewMode] = useState('week'); // 'week' | 'day' | 'month'
    const [selectedDay, setSelectedDay] = useState(null);

    // Генерируем дни недели при изменении начала недели
    useEffect(() => {
        setWeekDays(getWeekDays(weekStart));
    }, [weekStart]);

    // Загружаем расписание
    const loadSchedule = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const token = localStorage.getItem('token');
            const params = new URLSearchParams({
                week_start: formatDate(weekStart),
            });

            if (doctorId) {
                params.append('doctor_id', doctorId);
            }
            if (department) {
                params.append('department', department);
            }

            const response = await fetch(
                `${API_BASE}/api/v1/schedule/weekly?${params}`,
                {
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                }
            );

            if (!response.ok) {
                throw new Error('Не удалось загрузить расписание');
            }

            const data = await response.json();
            setSchedule(data);

        } catch (err) {
            console.error('Error loading schedule:', err);
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

    // Стили
    const styles = {
        container: {
            backgroundColor: isDark ? 'var(--mac-bg-secondary)' : '#ffffff',
            borderRadius: '12px',
            boxShadow: isDark
                ? '0 4px 20px rgba(0, 0, 0, 0.3)'
                : '0 4px 20px rgba(0, 0, 0, 0.08)',
            overflow: 'hidden',
        },
        header: {
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '16px 20px',
            borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)'}`,
            backgroundColor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)',
        },
        title: {
            fontSize: '18px',
            fontWeight: '600',
            color: isDark ? 'var(--mac-text-primary)' : '#1d1d1f',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
        },
        navButton: {
            padding: '8px',
            borderRadius: '8px',
            border: 'none',
            backgroundColor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)',
            color: isDark ? 'var(--mac-text-primary)' : '#1d1d1f',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.2s',
        },
        todayButton: {
            padding: '8px 16px',
            borderRadius: '8px',
            border: 'none',
            backgroundColor: '#007aff',
            color: '#ffffff',
            fontSize: '13px',
            fontWeight: '500',
            cursor: 'pointer',
            transition: 'all 0.2s',
        },
        weekGrid: {
            display: 'grid',
            gridTemplateColumns: 'repeat(7, 1fr)',
            gap: '1px',
            backgroundColor: isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.08)',
        },
        dayHeader: {
            padding: '12px 8px',
            textAlign: 'center',
            backgroundColor: isDark ? 'var(--mac-bg-secondary)' : '#f5f5f7',
            fontSize: '12px',
            fontWeight: '600',
            color: isDark ? 'var(--mac-text-secondary)' : '#6e6e73',
        },
        dayCell: {
            minHeight: compact ? '80px' : '120px',
            padding: '8px',
            backgroundColor: isDark ? 'var(--mac-bg-primary)' : '#ffffff',
            position: 'relative',
        },
        dayCellToday: {
            backgroundColor: isDark ? 'rgba(0, 122, 255, 0.1)' : 'rgba(0, 122, 255, 0.05)',
        },
        dayNumber: {
            fontSize: '14px',
            fontWeight: '500',
            marginBottom: '8px',
            color: isDark ? 'var(--mac-text-primary)' : '#1d1d1f',
        },
        dayNumberToday: {
            width: '28px',
            height: '28px',
            borderRadius: '50%',
            backgroundColor: '#007aff',
            color: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
        },
        slot: {
            padding: '4px 8px',
            marginBottom: '4px',
            borderRadius: '6px',
            fontSize: '11px',
            cursor: 'pointer',
            transition: 'all 0.2s',
        },
        slotAvailable: {
            backgroundColor: isDark ? 'rgba(52, 199, 89, 0.2)' : 'rgba(52, 199, 89, 0.1)',
            color: isDark ? '#32d74b' : '#248a3d',
        },
        slotBooked: {
            backgroundColor: isDark ? 'rgba(255, 69, 58, 0.2)' : 'rgba(255, 69, 58, 0.1)',
            color: isDark ? '#ff453a' : '#d70015',
        },
        loading: {
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            padding: '40px',
            color: isDark ? 'var(--mac-text-secondary)' : '#6e6e73',
        },
        error: {
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            padding: '20px',
            color: '#ff3b30',
            backgroundColor: isDark ? 'rgba(255, 59, 48, 0.1)' : 'rgba(255, 59, 48, 0.05)',
            margin: '16px',
            borderRadius: '8px',
        },
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
                <div style={{ fontSize: '11px', color: isDark ? '#999' : '#999', fontStyle: 'italic' }}>
                    Нет записей
                </div>
            );
        }

        return daySchedule.slice(0, compact ? 2 : 4).map((slot, idx) => (
            <div
                key={idx}
                style={{
                    ...styles.slot,
                    ...(slot.booked ? styles.slotBooked : styles.slotAvailable),
                }}
                onClick={() => slot.booked ? onViewAppointment?.(slot) : onSelectSlot?.(slot, date)}
            >
                <div style={{ fontWeight: '500' }}>{slot.time || slot.start_time}</div>
                {slot.patient_name && (
                    <div style={{ fontSize: '10px', opacity: 0.8 }}>{slot.patient_name}</div>
                )}
            </div>
        ));
    };

    // Рендерим день
    const renderDay = (date, index) => {
        const today = isToday(date);

        return (
            <div
                key={index}
                style={{
                    ...styles.dayCell,
                    ...(today ? styles.dayCellToday : {}),
                }}
                onClick={() => setSelectedDay(date)}
            >
                <div
                    style={{
                        ...styles.dayNumber,
                        ...(today ? styles.dayNumberToday : {}),
                    }}
                >
                    {date.getDate()}
                </div>
                {renderDaySlots(date)}
            </div>
        );
    };

    return (
        <div style={styles.container}>
            {/* Header */}
            <div style={styles.header}>
                <div style={styles.title}>
                    <Calendar size={20} />
                    <span>
                        {weekDays.length > 0 && (
                            <>
                                {weekDays[0].toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })}
                            </>
                        )}
                    </span>
                </div>

                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <button
                        style={styles.navButton}
                        onClick={goToPrevWeek}
                        title="Предыдущая неделя"
                    >
                        <ChevronLeft size={18} />
                    </button>

                    <button
                        style={styles.todayButton}
                        onClick={goToToday}
                    >
                        Сегодня
                    </button>

                    <button
                        style={styles.navButton}
                        onClick={goToNextWeek}
                        title="Следующая неделя"
                    >
                        <ChevronRight size={18} />
                    </button>

                    <button
                        style={styles.navButton}
                        onClick={loadSchedule}
                        title="Обновить"
                    >
                        <RefreshCw size={16} className={loading ? 'spinning' : ''} />
                    </button>
                </div>
            </div>

            {/* Error */}
            {error && (
                <div style={styles.error}>
                    <AlertCircle size={16} style={{ marginRight: '8px' }} />
                    {error}
                </div>
            )}

            {/* Loading */}
            {loading ? (
                <div style={styles.loading}>
                    <RefreshCw size={24} className="spinning" style={{ marginRight: '8px' }} />
                    Загрузка расписания...
                </div>
            ) : (
                <>
                    {/* Week Grid */}
                    <div style={styles.weekGrid}>
                        {/* Day Headers */}
                        {WEEKDAY_NAMES.map((name, idx) => (
                            <div key={idx} style={styles.dayHeader}>
                                {name}
                            </div>
                        ))}

                        {/* Day Cells */}
                        {weekDays.map((day, idx) => renderDay(day, idx))}
                    </div>
                </>
            )}

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
        </div>
    );
};

export default DoctorCalendar;
