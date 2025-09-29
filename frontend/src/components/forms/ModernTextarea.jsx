import React, { useState, useRef, useEffect } from 'react';
import { 
  AlertCircle, 
  CheckCircle,
  Maximize2,
  Minimize2
} from 'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import './ModernTextarea.css';

const ModernTextarea = ({
  label,
  placeholder,
  value,
  onChange,
  onBlur,
  onFocus,
  error,
  success,
  disabled = false,
  required = false,
  rows = 4,
  maxRows = 10,
  minRows = 2,
  maxLength,
  minLength,
  autoResize = true,
  resizable = true,
  expandable = false,
  className = '',
  size = 'medium',
  variant = 'default',
  ...props
}) => {
  const { theme, getColor } = useTheme();
  const [focused, setFocused] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [currentRows, setCurrentRows] = useState(rows);
  const textareaRef = useRef(null);

  // Автоматическое изменение размера
  useEffect(() => {
    if (autoResize && textareaRef.current) {
      const textarea = textareaRef.current;
      
      // Сброс высоты для правильного расчета
      textarea.style.height = 'auto';
      
      // Расчет количества строк
      const lineHeight = parseInt(getComputedStyle(textarea).lineHeight);
      const scrollHeight = textarea.scrollHeight;
      const newRows = Math.max(
        minRows,
        Math.min(maxRows, Math.ceil(scrollHeight / lineHeight))
      );
      
      setCurrentRows(newRows);
      textarea.style.height = `${newRows * lineHeight}px`;
    }
  }, [value, autoResize, minRows, maxRows]);

  // Обработчики событий
  const handleFocus = (e) => {
    setFocused(true);
    onFocus?.(e);
  };

  const handleBlur = (e) => {
    setFocused(false);
    onBlur?.(e);
  };

  const handleChange = (e) => {
    onChange?.(e);
  };

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  const hasError = !!error;
  const hasSuccess = !!success && !hasError;
  const hasValue = value && value.length > 0;
  const characterCount = value ? value.length : 0;

  // Стили
  const textareaStyles = {
    backgroundColor: disabled ? getColor('gray100') : getColor('cardBg'),
    color: disabled ? getColor('textSecondary') : getColor('textPrimary'),
    borderColor: hasError 
      ? getColor('danger') 
      : hasSuccess 
        ? getColor('success')
        : focused 
          ? getColor('primary')
          : getColor('border')
  };

  const labelStyles = {
    color: hasError 
      ? getColor('danger')
      : focused || hasValue
        ? getColor('primary')
        : getColor('textSecondary')
  };

  return (
    <div className={`modern-textarea ${className} ${isExpanded ? 'expanded' : ''}`} {...props}>
      {/* Лейбл */}
      {label && (
        <div className="textarea-header">
          <label 
            className={`textarea-label ${focused || hasValue ? 'focused' : ''} ${size}`}
            style={labelStyles}
            htmlFor={props.id}
          >
            {label}
            {required && <span className="required-mark">*</span>}
          </label>
          
          {/* Кнопка расширения */}
          {expandable && (
            <button
              type="button"
              className="expand-btn"
              onClick={toggleExpanded}
              title={isExpanded ? 'Свернуть' : 'Развернуть'}
              style={{ color: getColor('textSecondary') }}
            >
              {isExpanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            </button>
          )}
        </div>
      )}

      {/* Контейнер текстовой области */}
      <div className={`textarea-container ${variant} ${size} ${focused ? 'focused' : ''} ${hasError ? 'error' : ''} ${hasSuccess ? 'success' : ''} ${disabled ? 'disabled' : ''} ${!resizable ? 'no-resize' : ''}`}>
        <textarea
          ref={textareaRef}
          className="textarea-field"
          placeholder={placeholder}
          value={value || ''}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          disabled={disabled}
          required={required}
          rows={isExpanded ? Math.max(currentRows, 8) : currentRows}
          maxLength={maxLength}
          minLength={minLength}
          style={textareaStyles}
          aria-invalid={hasError ? 'true' : 'false'}
          aria-describedby={hasError ? `${props.id}-error` : undefined}
          {...props}
        />

        {/* Индикаторы состояния */}
        <div className="textarea-indicators">
          {hasError && (
            <div className="textarea-status error">
              <AlertCircle size={16} />
            </div>
          )}
          
          {hasSuccess && (
            <div className="textarea-status success">
              <CheckCircle size={16} />
            </div>
          )}
        </div>
      </div>

      {/* Нижняя панель */}
      <div className="textarea-footer">
        {/* Счетчик символов */}
        {maxLength && (
          <div 
            className={`character-counter ${characterCount > maxLength * 0.9 ? 'warning' : ''} ${characterCount >= maxLength ? 'error' : ''}`}
            style={{ 
              color: characterCount >= maxLength 
                ? getColor('danger')
                : characterCount > maxLength * 0.9
                  ? getColor('warning')
                  : getColor('textSecondary')
            }}
          >
            {characterCount}/{maxLength}
          </div>
        )}

        {/* Информация о строках */}
        {autoResize && (
          <div 
            className="rows-info"
            style={{ color: getColor('textSecondary') }}
          >
            {currentRows} {currentRows === 1 ? 'строка' : currentRows < 5 ? 'строки' : 'строк'}
          </div>
        )}
      </div>

      {/* Сообщение об ошибке */}
      {hasError && (
        <div 
          id={`${props.id}-error`}
          className="textarea-message error"
          style={{ color: getColor('danger') }}
        >
          <AlertCircle size={14} />
          <span>{error}</span>
        </div>
      )}

      {/* Сообщение об успехе */}
      {hasSuccess && (
        <div 
          className="textarea-message success"
          style={{ color: getColor('success') }}
        >
          <CheckCircle size={14} />
          <span>{success}</span>
        </div>
      )}
    </div>
  );
};

export default ModernTextarea;


