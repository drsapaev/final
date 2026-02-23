import { useState, useRef, useEffect } from 'react';
import PropTypes from 'prop-types';
import {
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle,
  Search,
  Calendar,
  Phone,
  Mail,
  User,
  Lock,
  X } from
'lucide-react';
import { useTheme } from '../../contexts/ThemeContext';
import './ModernInput.css';

const ModernInput = ({
  type = 'text',
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
  icon,
  clearable = false,
  autoComplete,
  maxLength,
  minLength,
  pattern,
  validation,
  suggestions = [],
  showSuggestions = false,
  onSuggestionSelect,
  className = '',
  size = 'medium',
  variant = 'default',
  ...props
}) => {
  const { getColor } = useTheme();
  const [focused, setFocused] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [localError, setLocalError] = useState('');
  const inputRef = useRef(null);
  const suggestionsRef = useRef(null);

  // Валидация
  useEffect(() => {
    if (validation && value) {
      const result = validation(value);
      setLocalError(result === true ? '' : result);
    } else {
      setLocalError('');
    }
  }, [value, validation]);

  // Получение иконки по типу
  const getTypeIcon = () => {
    if (icon) return icon;

    switch (type) {
      case 'email':return Mail;
      case 'password':return Lock;
      case 'search':return Search;
      case 'tel':return Phone;
      case 'date':return Calendar;
      default:return User;
    }
  };

  const IconComponent = getTypeIcon();
  const hasError = error || localError;
  const hasSuccess = success && !hasError;

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

  const handleClear = () => {
    const event = { target: { value: '' } };
    onChange?.(event);
    inputRef.current?.focus();
  };

  const handleSuggestionClick = (suggestion) => {
    onSuggestionSelect?.(suggestion);
    inputRef.current?.focus();
  };

  // Стили
  const inputStyles = {
    backgroundColor: disabled ? getColor('gray100') : getColor('cardBg'),
    color: disabled ? getColor('textSecondary') : getColor('textPrimary'),
    borderColor: hasError ?
    getColor('danger') :
    hasSuccess ?
    getColor('success') :
    focused ?
    getColor('primary') :
    getColor('border')
  };

  const labelStyles = {
    color: hasError ?
    getColor('danger') :
    focused || value ?
    getColor('primary') :
    getColor('textSecondary')
  };

  return (
    <div className={`modern-input ${className}`} {...props}>
      {/* Лейбл */}
      {label &&
      <label
        className={`input-label ${focused || value ? 'focused' : ''} ${size}`}
        style={labelStyles}
        htmlFor={props.id}>
        
          {label}
          {required && <span className="required-mark">*</span>}
        </label>
      }

      {/* Контейнер ввода */}
      <div className={`input-container ${variant} ${size} ${focused ? 'focused' : ''} ${hasError ? 'error' : ''} ${hasSuccess ? 'success' : ''} ${disabled ? 'disabled' : ''}`}>
        {/* Иконка слева */}
        {IconComponent &&
        <div className="input-icon left">
            <IconComponent size={size === 'small' ? 16 : size === 'large' ? 20 : 18} />
          </div>
        }

        {/* Поле ввода */}
        <input
          ref={inputRef}
          type={type === 'password' ? showPassword ? 'text' : 'password' : type}
          className={`input-field ${IconComponent ? 'has-left-icon' : ''} ${clearable && value || type === 'password' ? 'has-right-icon' : ''}`}
          placeholder={placeholder}
          value={value || ''}
          onChange={handleChange}
          onFocus={handleFocus}
          onBlur={handleBlur}
          disabled={disabled}
          required={required}
          autoComplete={autoComplete}
          maxLength={maxLength}
          minLength={minLength}
          pattern={pattern}
          style={inputStyles}
          aria-invalid={hasError ? 'true' : 'false'}
          aria-describedby={hasError ? `${props.id}-error` : undefined}
          {...props} />
        

        {/* Иконки справа */}
        <div className="input-actions">
          {/* Кнопка показа пароля */}
          {type === 'password' &&
          <button
            type="button"
            className="input-action-btn"
            onClick={() => setShowPassword(!showPassword)}
            tabIndex={-1}
            aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}>
            
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          }

          {/* Кнопка очистки */}
          {clearable && value && !disabled &&
          <button
            type="button"
            className="input-action-btn"
            onClick={handleClear}
            tabIndex={-1}
            aria-label="Очистить поле">
            
              <X size={16} />
            </button>
          }

          {/* Индикатор состояния */}
          {hasError &&
          <div className="input-status error">
              <AlertCircle size={16} />
            </div>
          }
          
          {hasSuccess &&
          <div className="input-status success">
              <CheckCircle size={16} />
            </div>
          }
        </div>
      </div>

      {/* Подсказки */}
      {showSuggestions && suggestions.length > 0 &&
      <div
        ref={suggestionsRef}
        className="input-suggestions"
        style={{
          backgroundColor: getColor('cardBg'),
          borderColor: getColor('border')
        }}>
        
          {suggestions.map((suggestion, index) =>
        <div
          key={index}
          className="suggestion-item"
          onClick={() => handleSuggestionClick(suggestion)}
          role="button"
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              handleSuggestionClick(suggestion);
            }
          }}
          style={{ color: getColor('textPrimary') }}>
          
              {typeof suggestion === 'object' ? suggestion.label : suggestion}
            </div>
        )}
        </div>
      }

      {/* Сообщение об ошибке */}
      {hasError &&
      <div
        id={`${props.id}-error`}
        className="input-message error"
        style={{ color: getColor('danger') }}>
        
          <AlertCircle size={14} />
          <span>{error || localError}</span>
        </div>
      }

      {/* Сообщение об успехе */}
      {hasSuccess &&
      <div
        className="input-message success"
        style={{ color: getColor('success') }}>
        
          <CheckCircle size={14} />
          <span>{success}</span>
        </div>
      }

      {/* Счетчик символов */}
      {maxLength &&
      <div
        className="input-counter"
        style={{ color: getColor('textSecondary') }}>
        
          {(value || '').length}/{maxLength}
        </div>
      }
    </div>);

};

ModernInput.propTypes = {
  type: PropTypes.string,
  label: PropTypes.node,
  placeholder: PropTypes.string,
  value: PropTypes.any,
  onChange: PropTypes.func,
  onBlur: PropTypes.func,
  onFocus: PropTypes.func,
  error: PropTypes.node,
  success: PropTypes.node,
  disabled: PropTypes.bool,
  required: PropTypes.bool,
  icon: PropTypes.oneOfType([PropTypes.node, PropTypes.func]),
  clearable: PropTypes.bool,
  autoComplete: PropTypes.string,
  maxLength: PropTypes.number,
  minLength: PropTypes.number,
  pattern: PropTypes.string,
  validation: PropTypes.func,
  suggestions: PropTypes.array,
  showSuggestions: PropTypes.bool,
  onSuggestionSelect: PropTypes.func,
  className: PropTypes.string,
  size: PropTypes.string,
  variant: PropTypes.string,
  id: PropTypes.string
};

export default ModernInput;
