import React, { useState, useRef, useEffect } from 'react';
import { 
  ChevronDown, 
  ChevronUp, 
  Check, 
  Search, 
  X,
  AlertCircle,
  CheckCircle
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import './ModernSelect.css';

const ModernSelect = ({
  label,
  placeholder = 'Выберите опцию',
  value,
  onChange,
  options = [],
  error,
  success,
  disabled = false,
  required = false,
  searchable = false,
  multiple = false,
  clearable = false,
  loading = false,
  size = 'medium',
  variant = 'default',
  renderOption,
  renderValue,
  groupBy,
  className = '',
  ...props
}) => {
  const { theme, getColor } = useTheme();
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [focused, setFocused] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  
  const selectRef = useRef(null);
  const dropdownRef = useRef(null);
  const searchInputRef = useRef(null);

  // Закрытие при клике вне компонента
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (selectRef.current && !selectRef.current.contains(event.target)) {
        setIsOpen(false);
        setSearchQuery('');
        setHighlightedIndex(-1);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Фокус на поиске при открытии
  useEffect(() => {
    if (isOpen && searchable && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [isOpen, searchable]);

  // Обработка клавиш
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (!isOpen) return;

      const filteredOptions = getFilteredOptions();
      
      switch (event.key) {
        case 'ArrowDown':
          event.preventDefault();
          setHighlightedIndex(prev => 
            prev < filteredOptions.length - 1 ? prev + 1 : 0
          );
          break;
        case 'ArrowUp':
          event.preventDefault();
          setHighlightedIndex(prev => 
            prev > 0 ? prev - 1 : filteredOptions.length - 1
          );
          break;
        case 'Enter':
          event.preventDefault();
          if (highlightedIndex >= 0) {
            handleOptionClick(filteredOptions[highlightedIndex]);
          }
          break;
        case 'Escape':
          setIsOpen(false);
          setSearchQuery('');
          setHighlightedIndex(-1);
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, highlightedIndex]);

  // Фильтрация опций
  const getFilteredOptions = () => {
    if (!searchQuery) return options;
    
    return options.filter(option => {
      const label = typeof option === 'object' ? option.label : option;
      return label.toLowerCase().includes(searchQuery.toLowerCase());
    });
  };

  // Группировка опций
  const getGroupedOptions = () => {
    const filteredOptions = getFilteredOptions();
    
    if (!groupBy) return { '': filteredOptions };
    
    return filteredOptions.reduce((groups, option) => {
      const group = typeof groupBy === 'function' ? groupBy(option) : option[groupBy];
      if (!groups[group]) groups[group] = [];
      groups[group].push(option);
      return groups;
    }, {});
  };

  // Получение выбранных значений
  const getSelectedValues = () => {
    if (!value) return [];
    return Array.isArray(value) ? value : [value];
  };

  // Проверка выбранности опции
  const isOptionSelected = (option) => {
    const selectedValues = getSelectedValues();
    const optionValue = typeof option === 'object' ? option.value : option;
    return selectedValues.some(val => 
      (typeof val === 'object' ? val.value : val) === optionValue
    );
  };

  // Обработка клика по опции
  const handleOptionClick = (option) => {
    if (multiple) {
      const selectedValues = getSelectedValues();
      const optionValue = typeof option === 'object' ? option.value : option;
      
      const isSelected = selectedValues.some(val => 
        (typeof val === 'object' ? val.value : val) === optionValue
      );
      
      let newValue;
      if (isSelected) {
        newValue = selectedValues.filter(val => 
          (typeof val === 'object' ? val.value : val) !== optionValue
        );
      } else {
        newValue = [...selectedValues, option];
      }
      
      onChange?.(newValue);
    } else {
      onChange?.(option);
      setIsOpen(false);
      setSearchQuery('');
      setHighlightedIndex(-1);
    }
  };

  // Очистка выбора
  const handleClear = (e) => {
    e.stopPropagation();
    onChange?.(multiple ? [] : null);
  };

  // Удаление выбранной опции (для multiple)
  const handleRemoveOption = (e, optionToRemove) => {
    e.stopPropagation();
    const selectedValues = getSelectedValues();
    const optionValue = typeof optionToRemove === 'object' ? optionToRemove.value : optionToRemove;
    
    const newValue = selectedValues.filter(val => 
      (typeof val === 'object' ? val.value : val) !== optionValue
    );
    
    onChange?.(newValue);
  };

  // Рендер значения
  const renderDisplayValue = () => {
    const selectedValues = getSelectedValues();
    
    if (selectedValues.length === 0) {
      return <span className="select-placeholder">{placeholder}</span>;
    }
    
    if (renderValue) {
      return renderValue(selectedValues);
    }
    
    if (multiple) {
      return (
        <div className="select-tags">
          {selectedValues.map((val, index) => {
            const label = typeof val === 'object' ? val.label : val;
            return (
              <span key={index} className="select-tag">
                {label}
                <button
                  type="button"
                  className="tag-remove"
                  onClick={(e) => handleRemoveOption(e, val)}
                  tabIndex={-1}
                >
                  <X size={12} />
                </button>
              </span>
            );
          })}
        </div>
      );
    }
    
    const selectedValue = selectedValues[0];
    return typeof selectedValue === 'object' ? selectedValue.label : selectedValue;
  };

  // Рендер опции
  const renderOptionContent = (option, index) => {
    if (renderOption) {
      return renderOption(option, isOptionSelected(option));
    }
    
    const label = typeof option === 'object' ? option.label : option;
    const isSelected = isOptionSelected(option);
    
    return (
      <>
        <span className="option-label">{label}</span>
        {isSelected && <Check size={16} className="option-check" />}
      </>
    );
  };

  const hasError = !!error;
  const hasSuccess = !!success && !hasError;
  const selectedValues = getSelectedValues();
  const hasValue = selectedValues.length > 0;

  // Стили
  const selectStyles = {
    backgroundColor: disabled ? getColor('gray100') : getColor('cardBg'),
    color: disabled ? getColor('textSecondary') : getColor('textPrimary'),
    borderColor: hasError 
      ? getColor('danger') 
      : hasSuccess 
        ? getColor('success')
        : focused || isOpen
          ? getColor('primary')
          : getColor('border')
  };

  const labelStyles = {
    color: hasError 
      ? getColor('danger')
      : focused || hasValue || isOpen
        ? getColor('primary')
        : getColor('textSecondary')
  };

  return (
    <div className={`modern-select ${className}`} ref={selectRef} {...props}>
      {/* Лейбл */}
      {label && (
        <label 
          className={`select-label ${focused || hasValue || isOpen ? 'focused' : ''} ${size}`}
          style={labelStyles}
        >
          {label}
          {required && <span className="required-mark">*</span>}
        </label>
      )}

      {/* Контейнер выбора */}
      <div 
        className={`select-container ${variant} ${size} ${focused || isOpen ? 'focused' : ''} ${hasError ? 'error' : ''} ${hasSuccess ? 'success' : ''} ${disabled ? 'disabled' : ''}`}
        style={selectStyles}
        onClick={() => !disabled && setIsOpen(!isOpen)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        tabIndex={disabled ? -1 : 0}
        role="combobox"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-invalid={hasError}
      >
        {/* Отображаемое значение */}
        <div className="select-value">
          {renderDisplayValue()}
        </div>

        {/* Действия */}
        <div className="select-actions">
          {/* Кнопка очистки */}
          {clearable && hasValue && !disabled && (
            <button
              type="button"
              className="select-action-btn"
              onClick={handleClear}
              tabIndex={-1}
              aria-label="Очистить выбор"
            >
              <X size={16} />
            </button>
          )}

          {/* Индикатор состояния */}
          {hasError && (
            <div className="select-status error">
              <AlertCircle size={16} />
            </div>
          )}
          
          {hasSuccess && (
            <div className="select-status success">
              <CheckCircle size={16} />
            </div>
          )}

          {/* Стрелка */}
          <div className={`select-arrow ${isOpen ? 'open' : ''}`}>
            {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>
        </div>
      </div>

      {/* Выпадающий список */}
      {isOpen && (
        <div 
          ref={dropdownRef}
          className="select-dropdown"
          style={{
            backgroundColor: getColor('cardBg'),
            borderColor: getColor('border')
          }}
        >
          {/* Поиск */}
          {searchable && (
            <div className="select-search">
              <Search size={16} className="search-icon" />
              <input
                ref={searchInputRef}
                type="text"
                className="search-input"
                placeholder="Поиск..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  backgroundColor: 'transparent',
                  color: getColor('textPrimary')
                }}
              />
            </div>
          )}

          {/* Опции */}
          <div className="select-options" role="listbox">
            {loading ? (
              <div className="select-loading">
                <div className="loading-spinner" />
                <span>Загрузка...</span>
              </div>
            ) : (
              (() => {
                const groupedOptions = getGroupedOptions();
                const groups = Object.keys(groupedOptions);
                
                if (groups.length === 0 || (groups.length === 1 && groups[0] === '' && groupedOptions[''].length === 0)) {
                  return (
                    <div className="select-empty" style={{ color: getColor('textSecondary') }}>
                      Нет доступных опций
                    </div>
                  );
                }
                
                let optionIndex = 0;
                
                return groups.map(groupName => (
                  <div key={groupName} className="option-group">
                    {groupName && (
                      <div 
                        className="group-header"
                        style={{ color: getColor('textSecondary') }}
                      >
                        {groupName}
                      </div>
                    )}
                    {groupedOptions[groupName].map((option) => {
                      const currentIndex = optionIndex++;
                      return (
                        <div
                          key={typeof option === 'object' ? option.value : option}
                          className={`select-option ${isOptionSelected(option) ? 'selected' : ''} ${highlightedIndex === currentIndex ? 'highlighted' : ''}`}
                          onClick={() => handleOptionClick(option)}
                          role="option"
                          aria-selected={isOptionSelected(option)}
                          style={{
                            backgroundColor: highlightedIndex === currentIndex 
                              ? getColor('primary') + '10' 
                              : 'transparent',
                            color: getColor('textPrimary')
                          }}
                        >
                          {renderOptionContent(option, currentIndex)}
                        </div>
                      );
                    })}
                  </div>
                ));
              })()
            )}
          </div>
        </div>
      )}

      {/* Сообщение об ошибке */}
      {hasError && (
        <div 
          className="select-message error"
          style={{ color: getColor('danger') }}
        >
          <AlertCircle size={14} />
          <span>{error}</span>
        </div>
      )}

      {/* Сообщение об успехе */}
      {hasSuccess && (
        <div 
          className="select-message success"
          style={{ color: getColor('success') }}
        >
          <CheckCircle size={14} />
          <span>{success}</span>
        </div>
      )}
    </div>
  );
};

export default ModernSelect;

