import React, { useState, useEffect, useRef } from 'react';
import { 
  Search, 
  Calendar, 
  Filter, 
  X, 
  ChevronDown,
  Clock,
  User,
  Phone,
  Stethoscope,
  RefreshCw
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import './ModernFilters.css';

const ModernFilters = ({
  searchParams,
  onParamsChange,
  autoRefresh,
  onAutoRefreshChange,
  appointmentsCount = 0,
  className = '',
  ...props
}) => {
  const { theme, getColor } = useTheme();
  const [isExpanded, setIsExpanded] = useState(false);
  const [searchValue, setSearchValue] = useState(searchParams.get('q') || '');
  const [dateValue, setDateValue] = useState(searchParams.get('date') || '');
  const [statusValue, setStatusValue] = useState(searchParams.get('status') || '');
  
  const searchInputRef = useRef(null);
  const searchTimeoutRef = useRef(null);

  // Обновляем локальные значения при изменении searchParams
  useEffect(() => {
    setSearchValue(searchParams.get('q') || '');
    setDateValue(searchParams.get('date') || '');
    setStatusValue(searchParams.get('status') || '');
  }, [searchParams]);

  // Debounced search
  const handleSearchChange = (value) => {
    setSearchValue(value);
    
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    
    searchTimeoutRef.current = setTimeout(() => {
      updateParam('q', value);
    }, 300);
  };

  const updateParam = (key, value) => {
    const params = new URLSearchParams(searchParams);
    if (value && value.trim()) {
      params.set(key, value.trim());
    } else {
      params.delete(key);
    }
    onParamsChange(params);
  };

  const clearAllFilters = () => {
    setSearchValue('');
    setDateValue('');
    setStatusValue('');
    onParamsChange(new URLSearchParams());
  };

  const hasActiveFilters = searchValue || dateValue || statusValue;

  const statusOptions = [
    { value: '', label: 'Все статусы', icon: null },
    { value: 'confirmed', label: 'Подтверждено', icon: '✓' },
    { value: 'queued', label: 'В очереди', icon: '⏳' },
    { value: 'paid_pending', label: 'Ожидает оплаты', icon: '💳' },
    { value: 'paid', label: 'Оплачено', icon: '✅' },
    { value: 'canceled', label: 'Отменено', icon: '❌' },
    { value: 'completed', label: 'Завершено', icon: '🏁' }
  ];

  return (
    <div className={`modern-filters ${className}`} {...props}>
      {/* Основная панель поиска */}
      <div className="filters-main-panel">
        <div className="search-container">
          <Search className="search-icon" size={20} />
          <input
            ref={searchInputRef}
            type="text"
            placeholder="Поиск по ФИО, телефону, услугам..."
            value={searchValue}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="search-input"
            style={{
              backgroundColor: getColor('cardBg'),
              color: getColor('textPrimary'),
              borderColor: getColor('border')
            }}
          />
          {searchValue && (
            <button
              type="button"
              className="search-clear"
              onClick={() => handleSearchChange('')}
              aria-label="Очистить поиск"
            >
              <X size={16} />
            </button>
          )}
        </div>

        <div className="filters-actions">
          {/* Быстрый фильтр по дате */}
          <div className="date-filter">
            <Calendar className="filter-icon" size={18} />
            <input
              type="date"
              value={dateValue}
              onChange={(e) => {
                setDateValue(e.target.value);
                updateParam('date', e.target.value);
              }}
              className="date-input"
              style={{
                backgroundColor: getColor('cardBg'),
                color: getColor('textPrimary'),
                borderColor: getColor('border')
              }}
            />
          </div>

          {/* Кнопка расширенных фильтров */}
          <button
            type="button"
            className={`filters-toggle ${isExpanded ? 'expanded' : ''} ${hasActiveFilters ? 'has-filters' : ''}`}
            onClick={() => setIsExpanded(!isExpanded)}
            style={{
              backgroundColor: hasActiveFilters ? getColor('primary') : getColor('cardBg'),
              color: hasActiveFilters ? 'white' : getColor('textPrimary'),
              borderColor: hasActiveFilters ? getColor('primary') : getColor('border')
            }}
          >
            <Filter size={18} />
            <span>Фильтры</span>
            {hasActiveFilters && <span className="filters-count">•</span>}
            <ChevronDown className={`toggle-icon ${isExpanded ? 'rotated' : ''}`} size={16} />
          </button>
        </div>
      </div>

      {/* Расширенная панель фильтров */}
      {isExpanded && (
        <div className="filters-expanded-panel">
          <div className="filters-grid">
            {/* Статус */}
            <div className="filter-group">
              <label className="filter-label">
                <Clock size={16} />
                Статус записи
              </label>
              <select
                value={statusValue}
                onChange={(e) => {
                  setStatusValue(e.target.value);
                  updateParam('status', e.target.value);
                }}
                className="filter-select"
                style={{
                  backgroundColor: getColor('cardBg'),
                  color: getColor('textPrimary'),
                  borderColor: getColor('border')
                }}
              >
                {statusOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.icon && `${option.icon} `}{option.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Быстрые фильтры по дате */}
            <div className="filter-group">
              <label className="filter-label">
                <Calendar size={16} />
                Быстрый выбор даты
              </label>
              <div className="quick-date-buttons">
                <button
                  type="button"
                  className="quick-date-btn"
                  onClick={() => {
                    const today = new Date().toISOString().split('T')[0];
                    setDateValue(today);
                    updateParam('date', today);
                  }}
                  style={{
                    backgroundColor: dateValue === new Date().toISOString().split('T')[0] 
                      ? getColor('primary') 
                      : getColor('cardBg'),
                    color: dateValue === new Date().toISOString().split('T')[0] 
                      ? 'white' 
                      : getColor('textPrimary'),
                    borderColor: getColor('border')
                  }}
                >
                  Сегодня
                </button>
                <button
                  type="button"
                  className="quick-date-btn"
                  onClick={() => {
                    const tomorrow = new Date();
                    tomorrow.setDate(tomorrow.getDate() + 1);
                    const tomorrowStr = tomorrow.toISOString().split('T')[0];
                    setDateValue(tomorrowStr);
                    updateParam('date', tomorrowStr);
                  }}
                  style={{
                    backgroundColor: getColor('cardBg'),
                    color: getColor('textPrimary'),
                    borderColor: getColor('border')
                  }}
                >
                  Завтра
                </button>
                <button
                  type="button"
                  className="quick-date-btn"
                  onClick={() => {
                    setDateValue('');
                    updateParam('date', '');
                  }}
                  style={{
                    backgroundColor: !dateValue ? getColor('primary') : getColor('cardBg'),
                    color: !dateValue ? 'white' : getColor('textPrimary'),
                    borderColor: getColor('border')
                  }}
                >
                  Все даты
                </button>
              </div>
            </div>
          </div>

          {/* Действия */}
          <div className="filters-actions-panel">
            <div className="filters-info">
              <span className="results-count">
                Найдено записей: <strong>{appointmentsCount}</strong>
              </span>
            </div>
            
            <div className="filters-controls">
              {/* Автообновление */}
              <label className="auto-refresh-toggle">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => onAutoRefreshChange(e.target.checked)}
                />
                <RefreshCw size={16} className={autoRefresh ? 'spinning' : ''} />
                <span>Автообновление</span>
              </label>

              {/* Очистить фильтры */}
              {hasActiveFilters && (
                <button
                  type="button"
                  className="clear-filters-btn"
                  onClick={clearAllFilters}
                  style={{
                    backgroundColor: getColor('danger'),
                    color: 'white'
                  }}
                >
                  <X size={16} />
                  Очистить все
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ModernFilters;

