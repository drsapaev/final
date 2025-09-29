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
  TrendingUp
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import './ModernTabs.css';

const ModernTabs = ({ 
  activeTab, 
  onTabChange, 
  departmentStats = {}, 
  theme = 'light',
  language = 'ru' 
}) => {
  const [indicatorStyle, setIndicatorStyle] = useState({});
  const tabsRef = useRef(null);
  const isDark = theme === 'dark';

  // Переводы
  const t = {
    ru: {
      cardio: 'Кардиолог',
      echokg: 'ЭКГ', 
      derma: 'Дерматолог',
      dental: 'Стоматолог',
      lab: 'Лаборатория',
      procedures: 'Процедуры',
      today: 'Сегодня',
      queue: 'В очереди',
      pending: 'Ожидают',
      all: 'Все отделения'
    }
  }[language] || {};

  // Конфигурация вкладок
  const tabs = [
    {
      key: 'cardio',
      label: t.cardio,
      icon: Heart,
      color: '#ef4444',
      gradient: 'linear-gradient(135deg, #ef4444, #dc2626)'
    },
    {
      key: 'echokg', 
      label: t.echokg,
      icon: Activity,
      color: '#ec4899',
      gradient: 'linear-gradient(135deg, #ec4899, #db2777)'
    },
    {
      key: 'derma',
      label: t.derma, 
      icon: UserCheck,
      color: '#f59e0b',
      gradient: 'linear-gradient(135deg, #f59e0b, #d97706)'
    },
    {
      key: 'dental',
      label: t.dental,
      icon: Smile,
      color: '#3b82f6',
      gradient: 'linear-gradient(135deg, #3b82f6, #2563eb)'
    },
    {
      key: 'lab',
      label: t.lab,
      icon: FlaskConical,
      color: '#10b981',
      gradient: 'linear-gradient(135deg, #10b981, #059669)'
    },
    {
      key: 'procedures',
      label: t.procedures,
      icon: Syringe,
      color: '#8b5cf6',
      gradient: 'linear-gradient(135deg, #8b5cf6, #7c3aed)'
    }
  ];

  // Используем ту же систему цветов, что и таблица
  const { getColor } = useTheme();
  
  const colors = {
    bg: isDark ? getColor('secondary', 900) : '#ffffff',
    bgSecondary: isDark ? getColor('secondary', 800) : getColor('secondary', 50),
    border: isDark ? getColor('secondary', 700) : getColor('secondary', 200),
    text: isDark ? getColor('secondary', 50) : getColor('secondary', 900),
    textSecondary: isDark ? getColor('secondary', 300) : getColor('secondary', 600),
    hover: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)',
    active: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'
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

  return (
    <div className={`modern-tabs ${isDark ? 'dark' : 'light'}`}>
      <div 
        className="tabs-container"
        style={{
          background: isDark ? 'rgba(15, 23, 42, 0.8)' : 'rgba(255, 255, 255, 0.8)',
          backdropFilter: 'blur(20px)',
          borderTop: `1px solid ${isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(255, 255, 255, 0.2)'}`,
          borderLeft: `1px solid ${isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(255, 255, 255, 0.2)'}`,
          borderRight: `1px solid ${isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(255, 255, 255, 0.2)'}`,
          borderBottom: 'none',
          borderRadius: '12px 12px 0 0',
          padding: '8px 16px'
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
                  color: isActive ? '#ffffff' : colors.text,
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

