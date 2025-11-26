/**
 * Улучшенная система навигации для медицинских интерфейсов
 * Основана на принципах доступности и медицинских стандартах UX
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useAnimation } from './useAnimation';
import { useReducedMotion } from './useEnhancedMediaQuery';

// Хук для управления навигацией
export const useNavigation = (initialRoute = '/') => {
  const [currentRoute, setCurrentRoute] = useState(initialRoute);
  const [history, setHistory] = useState([initialRoute]);
  const [historyIndex, setHistoryIndex] = useState(0);
  const [isNavigating, setIsNavigating] = useState(false);

  // Навигация к маршруту
  const navigate = useCallback((route, options = {}) => {
    const { replace = false, state = null } = options;

    setIsNavigating(true);

    if (replace) {
      setHistory(prev => [...prev.slice(0, historyIndex), route]);
      setCurrentRoute(route);
    } else {
      const newHistory = [...history.slice(0, historyIndex + 1), route];
      setHistory(newHistory);
      setHistoryIndex(newHistory.length - 1);
      setCurrentRoute(route);
    }

    // Имитируем задержку навигации
    setTimeout(() => {
      setIsNavigating(false);
    }, 300);

    // Обновляем URL в браузере
    if (typeof window !== 'undefined') {
      const url = new URL(window.location);
      url.pathname = route;
      window.history.pushState({ route, state }, '', url);
    }
  }, [history, historyIndex]);

  // Навигация назад
  const goBack = useCallback(() => {
    if (historyIndex > 0) {
      const newIndex = historyIndex - 1;
      setHistoryIndex(newIndex);
      setCurrentRoute(history[newIndex]);
      setIsNavigating(true);

      setTimeout(() => {
        setIsNavigating(false);
      }, 300);
    }
  }, [history, historyIndex]);

  // Навигация вперед
  const goForward = useCallback(() => {
    if (historyIndex < history.length - 1) {
      const newIndex = historyIndex + 1;
      setHistoryIndex(newIndex);
      setCurrentRoute(history[newIndex]);
      setIsNavigating(true);

      setTimeout(() => {
        setIsNavigating(false);
      }, 300);
    }
  }, [history, historyIndex]);

  // Проверка возможности навигации назад/вперед
  const canGoBack = historyIndex > 0;
  const canGoForward = historyIndex < history.length - 1;

  // Сброс истории
  const reset = useCallback((route = '/') => {
    setCurrentRoute(route);
    setHistory([route]);
    setHistoryIndex(0);
    setIsNavigating(false);
  }, []);

  // Получение статистики навигации
  const getNavigationStats = useCallback(() => {
    return {
      currentRoute,
      historyLength: history.length,
      historyIndex,
      canGoBack,
      canGoForward,
      isNavigating
    };
  }, [currentRoute, history, historyIndex, canGoBack, canGoForward, isNavigating]);

  return {
    currentRoute,
    history,
    historyIndex,
    isNavigating,
    navigate,
    goBack,
    goForward,
    canGoBack,
    canGoForward,
    reset,
    getNavigationStats
  };
};

// Хук для управления вкладками
export const useTabs = (initialTab = 0) => {
  const [activeTab, setActiveTab] = useState(initialTab);
  const [tabHistory, setTabHistory] = useState([initialTab]);

  // Переключение вкладки
  const switchTab = useCallback((tabIndex) => {
    setActiveTab(tabIndex);
    setTabHistory(prev => [...prev, tabIndex]);
  }, []);

  // Переход к предыдущей вкладке
  const goToPreviousTab = useCallback(() => {
    if (tabHistory.length > 1) {
      const newHistory = tabHistory.slice(0, -1);
      setTabHistory(newHistory);
      setActiveTab(newHistory[newHistory.length - 1]);
    }
  }, [tabHistory]);

  // Проверка возможности перехода назад
  const canGoToPreviousTab = tabHistory.length > 1;

  return {
    activeTab,
    tabHistory,
    switchTab,
    goToPreviousTab,
    canGoToPreviousTab
  };
};

// Компонент вкладки
export const Tab = ({
  children,
  active = false,
  disabled = false,
  onClick,
  className = '',
  ...props
}) => {
  const { prefersReducedMotion } = useReducedMotion();

  return (
    <button
      className={`tab ${active ? 'active' : ''} ${disabled ? 'disabled' : ''} ${className}`}
      disabled={disabled}
      onClick={onClick}
      style={{
        padding: '12px 16px',
        fontSize: '14px',
        fontWeight: active ? '600' : '400',
        color: active ? '#3b82f6' : disabled ? '#9ca3af' : '#374151',
        backgroundColor: active ? '#eff6ff' : 'transparent',
        border: 'none',
        borderBottom: active ? '2px solid #3b82f6' : '2px solid transparent',
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: prefersReducedMotion ? 'none' : 'all 0.2s ease',
        outline: 'none',
        flex: 1
      }}
      onMouseEnter={(e) => {
        if (!active && !disabled && !prefersReducedMotion) {
          e.target.style.backgroundColor = '#f9fafb';
        }
      }}
      onMouseLeave={(e) => {
        if (!active && !disabled && !prefersReducedMotion) {
          e.target.style.backgroundColor = 'transparent';
        }
      }}
      {...props}
    >
      {children}
    </button>
  );
};

// Компонент контейнера вкладок
export const Tabs = ({
  children,
  activeTab = 0,
  onTabChange,
  className = '',
  ...props
}) => {
  return (
    <div className={`tabs ${className}`} {...props}>
      <div
        className="tabs-header"
        style={{
          display: 'flex',
          borderBottom: '1px solid #e5e7eb',
          backgroundColor: '#f9fafb'
        }}
      >
        {React.Children.map(children, (child, index) =>
          React.cloneElement(child, {
            active: index === activeTab,
            onClick: () => onTabChange && onTabChange(index)
          })
        )}
      </div>
    </div>
  );
};

// Компонент панели вкладки
export const TabPanel = ({
  children,
  active = false,
  className = '',
  ...props
}) => {
  const { shouldRender, animationClasses } = useAnimation(active, 'fade', 200);

  if (!shouldRender) return null;

  return (
    <div
      className={`tab-panel ${animationClasses} ${className}`}
      style={{
        padding: '20px',
        backgroundColor: '#ffffff'
      }}
      {...props}
    >
      {children}
    </div>
  );
};

// Компонент навигационного меню
export const NavigationMenu = ({
  items = [],
  activeItem = null,
  onItemClick,
  orientation = 'horizontal',
  className = '',
  ...props
}) => {
  const { prefersReducedMotion } = useReducedMotion();

  const isHorizontal = orientation === 'horizontal';

  return (
    <nav
      className={`navigation-menu ${className}`}
      style={{
        display: 'flex',
        flexDirection: isHorizontal ? 'row' : 'column',
        gap: isHorizontal ? '0' : '8px',
        ...(isHorizontal ? {
          borderBottom: '1px solid #e5e7eb'
        } : {
          borderRight: '1px solid #e5e7eb',
          paddingRight: '16px'
        })
      }}
      {...props}
    >
      {items.map((item, index) => (
        <button
          key={item.id || index}
          onClick={() => onItemClick && onItemClick(item, index)}
          disabled={item.disabled}
          className={`navigation-item ${activeItem === item.id ? 'active' : ''}`}
          style={{
            padding: isHorizontal ? '12px 16px' : '8px 16px',
            fontSize: '14px',
            fontWeight: activeItem === item.id ? '600' : '400',
            color: activeItem === item.id ? '#3b82f6' : item.disabled ? '#9ca3af' : '#374151',
            backgroundColor: activeItem === item.id ? '#eff6ff' : 'transparent',
            border: 'none',
            borderRadius: isHorizontal ? '0' : '6px',
            cursor: item.disabled ? 'not-allowed' : 'pointer',
            textAlign: 'left',
            transition: prefersReducedMotion ? 'none' : 'all 0.2s ease',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            width: '100%',
            ...(isHorizontal && activeItem === item.id ? {
              borderBottom: '2px solid #3b82f6'
            } : {})
          }}
          onMouseEnter={(e) => {
            if (activeItem !== item.id && !item.disabled && !prefersReducedMotion) {
              e.target.style.backgroundColor = '#f9fafb';
            }
          }}
          onMouseLeave={(e) => {
            if (activeItem !== item.id && !item.disabled && !prefersReducedMotion) {
              e.target.style.backgroundColor = 'transparent';
            }
          }}
        >
          {item.icon && <span style={{ fontSize: '16px' }}>{item.icon}</span>}
          <span>{item.label}</span>
          {item.badge && (
            <span
              style={{
                marginLeft: 'auto',
                padding: '2px 6px',
                fontSize: '11px',
                backgroundColor: '#ef4444',
                color: '#ffffff',
                borderRadius: '10px',
                minWidth: '18px',
                textAlign: 'center'
              }}
            >
              {item.badge}
            </span>
          )}
        </button>
      ))}
    </nav>
  );
};

// Компонент хлебных крошек
export const Breadcrumbs = ({
  items = [],
  separator = '/',
  className = '',
  ...props
}) => {
  return (
    <nav
      className={`breadcrumbs ${className}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        fontSize: '14px',
        color: '#6b7280'
      }}
      {...props}
    >
      {items.map((item, index) => (
        <React.Fragment key={item.id || index}>
          {index > 0 && (
            <span style={{ color: '#9ca3af' }}>{separator}</span>
          )}
          {index === items.length - 1 ? (
            <span style={{ color: '#374151', fontWeight: '500' }}>
              {item.label}
            </span>
          ) : (
            <button
              onClick={item.onClick}
              style={{
                background: 'none',
                border: 'none',
                color: '#3b82f6',
                cursor: 'pointer',
                textDecoration: 'none',
                padding: '0',
                fontSize: 'inherit'
              }}
              onMouseEnter={(e) => {
                e.target.style.textDecoration = 'underline';
              }}
              onMouseLeave={(e) => {
                e.target.style.textDecoration = 'none';
              }}
            >
              {item.label}
            </button>
          )}
        </React.Fragment>
      ))}
    </nav>
  );
};

// Компонент пагинации
export const Pagination = ({
  currentPage = 1,
  totalPages = 1,
  onPageChange,
  showPageNumbers = true,
  showPageSize = false,
  pageSize = 10,
  pageSizeOptions = [10, 25, 50, 100],
  onPageSizeChange,
  className = '',
  ...props
}) => {
  const { prefersReducedMotion } = useReducedMotion();

  // Генерация номеров страниц для отображения
  const getVisiblePages = () => {
    const delta = 2;
    const range = [];
    const rangeWithDots = [];

    for (
      let i = Math.max(2, currentPage - delta);
      i <= Math.min(totalPages - 1, currentPage + delta);
      i++
    ) {
      range.push(i);
    }

    if (currentPage - delta > 2) {
      rangeWithDots.push(1, '...');
    } else {
      rangeWithDots.push(1);
    }

    rangeWithDots.push(...range);

    if (currentPage + delta < totalPages - 1) {
      rangeWithDots.push('...', totalPages);
    } else if (totalPages > 1) {
      rangeWithDots.push(totalPages);
    }

    return rangeWithDots;
  };

  const visiblePages = getVisiblePages();

  return (
    <div
      className={`pagination ${className}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '16px 0'
      }}
      {...props}
    >
      {/* Информация о странице */}
      <div style={{ fontSize: '14px', color: '#6b7280' }}>
        Страница {currentPage} из {totalPages}
      </div>

      {/* Контролы пагинации */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {/* Предыдущая страница */}
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          style={{
            padding: '8px 12px',
            fontSize: '14px',
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            backgroundColor: currentPage === 1 ? '#f3f4f6' : '#ffffff',
            color: currentPage === 1 ? '#9ca3af' : '#374151',
            cursor: currentPage === 1 ? 'not-allowed' : 'pointer',
            transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
          }}
          onMouseEnter={(e) => {
            if (currentPage !== 1 && !prefersReducedMotion) {
              e.target.style.backgroundColor = '#f9fafb';
            }
          }}
          onMouseLeave={(e) => {
            if (currentPage !== 1 && !prefersReducedMotion) {
              e.target.style.backgroundColor = '#ffffff';
            }
          }}
        >
          ← Предыдущая
        </button>

        {/* Номера страниц */}
        {showPageNumbers && (
          <div style={{ display: 'flex', gap: '4px' }}>
            {visiblePages.map((page, index) => (
              <button
                key={index}
                onClick={() => typeof page === 'number' && onPageChange(page)}
                disabled={page === '...'}
                style={{
                  padding: '8px 12px',
                  fontSize: '14px',
                  fontWeight: page === currentPage ? '600' : '400',
                  border: '1px solid #d1d5db',
                  borderRadius: '6px',
                  backgroundColor: page === currentPage ? '#3b82f6' : page === '...' ? 'transparent' : '#ffffff',
                  color: page === currentPage ? '#ffffff' : page === '...' ? 'transparent' : '#374151',
                  cursor: page === '...' ? 'default' : 'pointer',
                  minWidth: '40px',
                  transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  if (typeof page === 'number' && page !== currentPage && !prefersReducedMotion) {
                    e.target.style.backgroundColor = page === currentPage ? '#2563eb' : '#f9fafb';
                  }
                }}
                onMouseLeave={(e) => {
                  if (typeof page === 'number' && page !== currentPage && !prefersReducedMotion) {
                    e.target.style.backgroundColor = page === currentPage ? '#3b82f6' : '#ffffff';
                  }
                }}
              >
                {page}
              </button>
            ))}
          </div>
        )}

        {/* Следующая страница */}
        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          style={{
            padding: '8px 12px',
            fontSize: '14px',
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            backgroundColor: currentPage === totalPages ? '#f3f4f6' : '#ffffff',
            color: currentPage === totalPages ? '#9ca3af' : '#374151',
            cursor: currentPage === totalPages ? 'not-allowed' : 'pointer',
            transition: prefersReducedMotion ? 'none' : 'all 0.2s ease'
          }}
          onMouseEnter={(e) => {
            if (currentPage !== totalPages && !prefersReducedMotion) {
              e.target.style.backgroundColor = '#f9fafb';
            }
          }}
          onMouseLeave={(e) => {
            if (currentPage !== totalPages && !prefersReducedMotion) {
              e.target.style.backgroundColor = '#ffffff';
            }
          }}
        >
          Следующая →
        </button>
      </div>

      {/* Выбор размера страницы */}
      {showPageSize && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '14px', color: '#6b7280' }}>Показывать:</span>
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange && onPageSizeChange(Number(e.target.value))}
            style={{
              padding: '4px 8px',
              fontSize: '14px',
              border: '1px solid #d1d5db',
              borderRadius: '4px',
              backgroundColor: '#ffffff',
              color: '#374151'
            }}
          >
            {pageSizeOptions.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
};

export default useNavigation;
