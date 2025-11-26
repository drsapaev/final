import React, { useState, useRef, useEffect } from 'react';
import {
  Heart,
  Activity,
  UserCheck,
  Smile,
  FlaskConical,
  Syringe,
  Calendar,
  Clock,
  AlertCircle,
  TrendingUp,
  Package,
  Stethoscope,
  TestTube,
  Scissors,
  FolderTree
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import { api } from '../../api/client';
import './ModernTabs.css';

// Маппинг иконок из lucide-react
const iconMap = {
  Heart,
  Activity,
  UserCheck,
  Smile,
  FlaskConical,
  Syringe,
  Calendar,
  Package,
  Stethoscope,
  TestTube,
  Scissors,
  FolderTree
};

const ModernTabs = ({
  activeTab,
  onTabChange,
  departmentStats = {},
  theme = 'light',
  language = 'ru'
}) => {
  const [indicatorStyle, setIndicatorStyle] = useState({});
  const [tabs, setTabs] = useState([]);
  const [loading, setLoading] = useState(true);
  const tabsRef = useRef(null);

  // Переводы
  const t = {
    ru: {
      today: 'Сегодня',
      queue: 'В очереди',
      pending: 'Ожидают',
      all: 'Все отделения'
    }
  }[language] || {};

  // Загрузка отделений из БД
  useEffect(() => {
    const loadDepartments = async () => {
      try {
        setLoading(true);
        const response = await api.get('/departments?active_only=true');

        // Backend returns {success: true, data: [...], count: N}
        // axios response.data contains the backend response body
        const departments = response.data.data || [];

        // Преобразуем данные из БД в формат для вкладок
        const departmentsData = departments.map(dept => ({
          key: dept.key,
          label: language === 'uz' ? (dept.name_uz || dept.name_ru) : dept.name_ru,
          icon: iconMap[dept.icon] || Package, // Fallback на Package если иконка не найдена
          color: dept.color,
          gradient: dept.gradient || `linear-gradient(135deg, ${dept.color}, ${dept.color})`
        }));

        setTabs(departmentsData);
      } catch (error) {
        console.error('Ошибка загрузки отделений:', error);
        // Fallback на hardcoded вкладки если API не работает
        setTabs([
          {
            key: 'cardio',
            label: language === 'uz' ? 'Kardiolog' : 'Кардиолог',
            icon: Heart,
            color: '#ef4444',
            gradient: 'linear-gradient(135deg, #ef4444, #dc2626)'
          },
          {
            key: 'echokg',
            label: language === 'uz' ? 'EKG' : 'ЭКГ',
            icon: Activity,
            color: '#ec4899',
            gradient: 'linear-gradient(135deg, #ec4899, #db2777)'
          },
          {
            key: 'derma',
            label: language === 'uz' ? 'Dermatolog' : 'Дерматолог',
            icon: UserCheck,
            color: '#f59e0b',
            gradient: 'linear-gradient(135deg, #f59e0b, #d97706)'
          },
          {
            key: 'dental',
            label: language === 'uz' ? 'Stomatolog' : 'Стоматолог',
            icon: Smile,
            color: '#3b82f6',
            gradient: 'linear-gradient(135deg, #3b82f6, #2563eb)'
          },
          {
            key: 'lab',
            label: language === 'uz' ? 'Laboratoriya' : 'Лаборатория',
            icon: FlaskConical,
            color: '#10b981',
            gradient: 'linear-gradient(135deg, #10b981, #059669)'
          },
          {
            key: 'procedures',
            label: language === 'uz' ? 'Muolajalar' : 'Процедуры',
            icon: Syringe,
            color: '#8b5cf6',
            gradient: 'linear-gradient(135deg, #8b5cf6, #7c3aed)'
          }
        ]);
      } finally {
        setLoading(false);
      }
    };

    loadDepartments();
  }, [language]);

  // Используем ту же систему цветов, что и таблица
  const { isDark } = useTheme();

  const colors = {
    bg: isDark ? 'rgba(15, 23, 42, 0.9)' : 'rgba(255, 255, 255, 0.98)',
    bgSecondary: isDark ? 'rgba(30, 41, 59, 0.8)' : 'rgba(255, 255, 255, 0.98)',
    border: isDark ? 'rgba(255, 255, 255, 0.2)' : 'rgba(0, 0, 0, 0.3)',
    text: isDark ? '#f8fafc' : '#0f172a',
    textSecondary: isDark ? '#cbd5e1' : '#64748b',
    hover: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.1)',
    active: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.15)'
  };

  // Обновление позиции индикатора
  useEffect(() => {
    if (activeTab && tabsRef.current) {
      const activeButton = tabsRef.current.querySelector(`[data-tab="${activeTab}"]`);
      if (activeButton) {
        const rect = activeButton.getBoundingClientRect();
        const containerRect = tabsRef.current.getBoundingClientRect();

        setIndicatorStyle({
          left: rect.left - containerRect.left,
          width: rect.width,
          opacity: 1
        });
      }
    } else {
      setIndicatorStyle({ opacity: 0 });
    }
  }, [activeTab]);

  // Получение статистики для отдела
  const getStats = (tabKey) => {
    const stats = departmentStats[tabKey] || {};
    return {
      todayCount: stats.todayCount || 0,
      hasActiveQueue: stats.hasActiveQueue || false,
      hasPendingPayments: stats.hasPendingPayments || false
    };
  };

  // Рендер индикаторов статуса
  const renderStatusIndicators = (tabKey) => {
    const stats = getStats(tabKey);
    const indicators = [];

    if (stats.hasActiveQueue) {
      indicators.push(
        <div
          key="queue"
          className="status-indicator queue"
          title={`${t.queue}: ${stats.todayCount}`}
        >
          <Clock size={10} />
        </div>
      );
    }

    if (stats.hasPendingPayments) {
      indicators.push(
        <div
          key="pending"
          className="status-indicator pending"
          title={t.pending}
        >
          <AlertCircle size={10} />
        </div>
      );
    }

    if (stats.todayCount > 0) {
      indicators.push(
        <div
          key="count"
          className="status-indicator count"
          title={`${t.today}: ${stats.todayCount}`}
        >
          {stats.todayCount}
        </div>
      );
    }

    return indicators;
  };

  // Показываем заглушку пока загружаются вкладки
  if (loading) {
    return (
      <div className={`modern-tabs ${isDark ? 'dark' : 'light'}`}>
        <div
          className="tabs-container"
          style={{
            background: colors.bg,
            backdropFilter: 'blur(20px)',
            borderTop: `1px solid ${colors.border}`,
            borderLeft: `1px solid ${colors.border}`,
            borderRight: `1px solid ${colors.border}`,
            borderBottom: `1px solid ${colors.border}`,
            borderRadius: '12px 12px 0 0',
            padding: '8px 16px',
            boxShadow: 'none'
          }}
        >
          <div style={{ padding: '12px', textAlign: 'center', color: colors.textSecondary }}>
            Загрузка отделений...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`modern-tabs ${isDark ? 'dark' : 'light'}`}>
      <div
        className="tabs-container"
        style={{
          background: colors.bg,
          backdropFilter: 'blur(20px)',
          borderTop: `1px solid ${colors.border}`,
          borderLeft: `1px solid ${colors.border}`,
          borderRight: `1px solid ${colors.border}`,
          borderBottom: `1px solid ${colors.border}`,
          borderRadius: '12px 12px 0 0',
          padding: '8px 16px',
          boxShadow: 'none'
        }}
      >
        {/* Кнопка "Все отделения" */}
        <button
          className={`tab-button all-departments ${!activeTab ? 'active' : ''}`}
          onClick={() => onTabChange(null)}
          style={{
            color: !activeTab ? '#3b82f6' : colors.text
          }}
        >
          <div className="tab-icon">
            <TrendingUp size={16} />
          </div>
          <span className="tab-label">{t.all}</span>
        </button>

        {/* Разделитель */}
        <div
          className="tabs-divider"
          style={{ backgroundColor: colors.border }}
        />

        {/* Контейнер для вкладок отделений */}
        <div className="department-tabs" ref={tabsRef}>
          {/* Анимированный индикатор */}
          <div
            className="tab-indicator"
            style={{
              ...indicatorStyle,
              background: activeTab ? tabs.find(t => t.key === activeTab)?.gradient : 'transparent'
            }}
          />

          {/* Вкладки отделений */}
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.key;
            const stats = getStats(tab.key);

            return (
              <button
                key={tab.key}
                data-tab={tab.key}
                className={`tab-button department ${isActive ? 'active' : ''}`}
                onClick={() => onTabChange(isActive ? null : tab.key)}
                style={{
                  color: isActive ? (isDark ? '#ffffff' : '#0f172a') : colors.text,
                  backgroundColor: isActive ? (isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)') : 'transparent',
                  '--tab-color': tab.color,
                  '--tab-gradient': tab.gradient
                }}
              >
                <div className="tab-content">
                  <div className="tab-icon">
                    <Icon size={16} />
                  </div>
                  <span className="tab-label">{tab.label}</span>

                  {/* Индикаторы статуса */}
                  <div className="status-indicators">
                    {renderStatusIndicators(tab.key)}
                  </div>
                </div>

                {/* Эффект ripple */}
                <div className="ripple-effect" />
              </button>
            );
          })}
        </div>
      </div>

      {/* Информационная панель убрана для стиля Edge */}
    </div>
  );
};

export default ModernTabs;

