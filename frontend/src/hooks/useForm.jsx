/**
 * Улучшенная система форм для медицинских интерфейсов
 * Основана на принципах доступности и медицинских стандартах UX
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useAnimation } from './useAnimation';
import { useReducedMotion } from './useEnhancedMediaQuery';

// Валидаторы для медицинских форм
export const validators = {
  required: (value) => {
    if (typeof value === 'string') {
      return value.trim() !== '';
    }
    return value != null && value !== '';
  },

  email: (value) => {
    if (!value) return true;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(value);
  },

  phone: (value) => {
    if (!value) return true;
    const phoneRegex = /^\+?[\d\s\-\(\)]{10,}$/;
    return phoneRegex.test(value.replace(/\s/g, ''));
  },

  minLength: (min) => (value) => {
    if (!value) return true;
    return String(value).length >= min;
  },

  maxLength: (max) => (value) => {
    if (!value) return true;
    return String(value).length <= max;
  },

  pattern: (regex) => (value) => {
    if (!value) return true;
    return regex.test(String(value));
  },

  numeric: (value) => {
    if (!value) return true;
    return !isNaN(Number(value));
  },

  min: (min) => (value) => {
    if (!value) return true;
    const num = Number(value);
    return !isNaN(num) && num >= min;
  },

  max: (max) => (value) => {
    if (!value) return true;
    const num = Number(value);
    return !isNaN(num) && num <= max;
  },

  date: (value) => {
    if (!value) return true;
    const date = new Date(value);
    return !isNaN(date.getTime());
  },

  future: (value) => {
    if (!value) return true;
    const date = new Date(value);
    return !isNaN(date.getTime()) && date > new Date();
  },

  past: (value) => {
    if (!value) return true;
    const date = new Date(value);
    return !isNaN(date.getTime()) && date < new Date();
  }
};

// Хук для управления формой
export const useForm = (initialValues = {}, options = {}) => {
  const {
    validateOnChange = true,
    validateOnBlur = true,
    validateOnSubmit = true,
    resetOnSubmit = false
  } = options;

  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isValid, setIsValid] = useState(true);

  // Валидация поля
  const validateField = useCallback((name, value, rules = {}) => {
    const fieldErrors = [];

    Object.entries(rules).forEach(([ruleName, ruleValue]) => {
      const validator = validators[ruleName];
      if (validator) {
        const result = validator(ruleValue)(value);
        if (!result) {
          fieldErrors.push(ruleValue.message || `Ошибка валидации: ${ruleName}`);
        }
      }
    });

    return fieldErrors;
  }, []);

  // Валидация всей формы
  const validateForm = useCallback(() => {
    const allErrors = {};
    let formIsValid = true;

    Object.entries(values).forEach(([name, value]) => {
      const fieldRules = options.validation?.[name] || {};
      const fieldErrors = validateField(name, value, fieldRules);

      if (fieldErrors.length > 0) {
        allErrors[name] = fieldErrors;
        formIsValid = false;
      }
    });

    setErrors(allErrors);
    setIsValid(formIsValid);
    return formIsValid;
  }, [values, options.validation, validateField]);

  // Обработка изменения поля
  const handleChange = useCallback((name, value) => {
    setValues(prev => ({
      ...prev,
      [name]: value
    }));

    if (validateOnChange && options.validation?.[name]) {
      const fieldErrors = validateField(name, value, options.validation[name]);
      setErrors(prev => ({
        ...prev,
        [name]: fieldErrors
      }));
    }

    // Очистка ошибок при изменении
    if (errors[name]) {
      setErrors(prev => ({
        ...prev,
        [name]: []
      }));
    }
  }, [validateOnChange, options.validation, validateField, errors]);

  // Обработка потери фокуса
  const handleBlur = useCallback((name) => {
    setTouched(prev => ({
      ...prev,
      [name]: true
    }));

    if (validateOnBlur && options.validation?.[name]) {
      const value = values[name];
      const fieldErrors = validateField(name, value, options.validation[name]);
      setErrors(prev => ({
        ...prev,
        [name]: fieldErrors
      }));
    }
  }, [validateOnBlur, options.validation, validateField, values]);

  // Обработка фокуса
  const handleFocus = useCallback((name) => {
    // Можно добавить логику для фокуса
  }, []);

  // Сброс формы
  const reset = useCallback(() => {
    setValues(initialValues);
    setErrors({});
    setTouched({});
    setIsSubmitting(false);
    setIsValid(true);
  }, [initialValues]);

  // Отправка формы
  const handleSubmit = useCallback(async (e) => {
    e?.preventDefault();

    setTouched(Object.keys(values).reduce((acc, key) => ({ ...acc, [key]: true }), {}));

    if (validateOnSubmit) {
      const formIsValid = validateForm();
      if (!formIsValid) return;
    }

    setIsSubmitting(true);

    try {
      if (options.onSubmit) {
        await options.onSubmit(values);
      }

      if (resetOnSubmit) {
        reset();
      }
    } catch (error) {
      console.error('Form submission error:', error);
    } finally {
      setIsSubmitting(false);
    }
  }, [values, validateOnSubmit, validateForm, options.onSubmit, resetOnSubmit, reset]);

  // Получение значения поля
  const getFieldProps = useCallback((name) => {
    return {
      name,
      value: values[name] || '',
      onChange: (value) => handleChange(name, value),
      onBlur: () => handleBlur(name),
      onFocus: () => handleFocus(name),
      error: errors[name]?.[0],
      touched: touched[name],
      isValid: !errors[name] || errors[name].length === 0
    };
  }, [values, errors, touched, handleChange, handleBlur, handleFocus]);

  // Получение статистики формы
  const getFormStats = useCallback(() => {
    return {
      totalFields: Object.keys(values).length,
      touchedFields: Object.keys(touched).length,
      errorFields: Object.keys(errors).length,
      isValid,
      isSubmitting,
      hasChanges: JSON.stringify(values) !== JSON.stringify(initialValues)
    };
  }, [values, touched, errors, isValid, isSubmitting, initialValues]);

  return {
    // Данные формы
    values,
    errors,
    touched,
    isValid,
    isSubmitting,

    // Действия
    handleChange,
    handleBlur,
    handleFocus,
    handleSubmit,
    reset,
    validateForm,

    // Утилиты
    getFieldProps,
    getFormStats,

    // Прямой доступ к сеттерам
    setValues,
    setErrors,
    setTouched
  };
};

// Поле формы
export const FormField = ({
  name,
  label,
  type = 'text',
  placeholder,
  required = false,
  disabled = false,
  error,
  touched,
  value,
  onChange,
  onBlur,
  className = '',
  ...props
}) => {
  const { prefersReducedMotion } = useReducedMotion();
  const { shouldRender, animationClasses } = useAnimation(!!error, 'slideDown', 200);

  const handleChange = (e) => {
    const newValue = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    if (onChange) {
      onChange(newValue);
    }
  };

  return (
    <div className={`form-field ${className}`} style={{ marginBottom: '16px' }}>
      {label && (
        <label
          htmlFor={name}
          style={{
            display: 'block',
            marginBottom: '4px',
            fontSize: '14px',
            fontWeight: '500',
            color: error ? '#ef4444' : '#374151'
          }}
        >
          {label}
          {required && <span style={{ color: '#ef4444' }}> *</span>}
        </label>
      )}

      <input
        id={name}
        name={name}
        type={type}
        value={value || ''}
        onChange={handleChange}
        placeholder={placeholder}
        disabled={disabled}
        required={required}
        style={{
          width: '100%',
          padding: '8px 12px',
          fontSize: '14px',
          border: `1px solid ${error ? '#ef4444' : '#d1d5db'}`,
          borderRadius: '6px',
          backgroundColor: disabled ? '#f9fafb' : '#ffffff',
          color: '#374151',
          outline: 'none',
          transition: prefersReducedMotion ? 'none' : 'border-color 0.2s ease, box-shadow 0.2s ease'
        }}
        onFocus={(e) => {
          if (!prefersReducedMotion) {
            e.target.style.borderColor = error ? '#ef4444' : '#3b82f6';
            e.target.style.boxShadow = `0 0 0 3px ${error ? '#fef2f2' : '#dbeafe'}`;
          }
        }}
        onBlur={(e) => {
          if (!prefersReducedMotion) {
            e.target.style.borderColor = error ? '#ef4444' : '#d1d5db';
            e.target.style.boxShadow = 'none';
          }
          if (onBlur) onBlur(e);
        }}
        {...props}
      />

      {shouldRender && error && (
        <div
          className={`form-field-error ${animationClasses}`}
          style={{
            marginTop: '4px',
            fontSize: '12px',
            color: '#ef4444'
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
};

// Текстовое поле формы
export const FormTextarea = ({
  name,
  label,
  placeholder,
  required = false,
  disabled = false,
  error,
  touched,
  value,
  onChange,
  onBlur,
  rows = 3,
  className = '',
  ...props
}) => {
  const { prefersReducedMotion } = useReducedMotion();

  const handleChange = (e) => {
    if (onChange) {
      onChange(e.target.value);
    }
  };

  return (
    <div className={`form-textarea ${className}`} style={{ marginBottom: '16px' }}>
      {label && (
        <label
          htmlFor={name}
          style={{
            display: 'block',
            marginBottom: '4px',
            fontSize: '14px',
            fontWeight: '500',
            color: error ? '#ef4444' : '#374151'
          }}
        >
          {label}
          {required && <span style={{ color: '#ef4444' }}> *</span>}
        </label>
      )}

      <textarea
        id={name}
        name={name}
        value={value || ''}
        onChange={handleChange}
        placeholder={placeholder}
        disabled={disabled}
        required={required}
        rows={rows}
        style={{
          width: '100%',
          padding: '8px 12px',
          fontSize: '14px',
          fontFamily: 'inherit',
          border: `1px solid ${error ? '#ef4444' : '#d1d5db'}`,
          borderRadius: '6px',
          backgroundColor: disabled ? '#f9fafb' : '#ffffff',
          color: '#374151',
          outline: 'none',
          resize: 'vertical',
          transition: prefersReducedMotion ? 'none' : 'border-color 0.2s ease, box-shadow 0.2s ease'
        }}
        onFocus={(e) => {
          if (!prefersReducedMotion) {
            e.target.style.borderColor = error ? '#ef4444' : '#3b82f6';
            e.target.style.boxShadow = `0 0 0 3px ${error ? '#fef2f2' : '#dbeafe'}`;
          }
        }}
        onBlur={(e) => {
          if (!prefersReducedMotion) {
            e.target.style.borderColor = error ? '#ef4444' : '#d1d5db';
            e.target.style.boxShadow = 'none';
          }
          if (onBlur) onBlur(e);
        }}
        {...props}
      />

      {error && (
        <div
          style={{
            marginTop: '4px',
            fontSize: '12px',
            color: '#ef4444'
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
};

// Выпадающий список формы
export const FormSelect = ({
  name,
  label,
  placeholder = 'Выберите...',
  required = false,
  disabled = false,
  error,
  touched,
  value,
  onChange,
  onBlur,
  options = [],
  className = '',
  ...props
}) => {
  const { prefersReducedMotion } = useReducedMotion();

  const handleChange = (e) => {
    if (onChange) {
      onChange(e.target.value);
    }
  };

  return (
    <div className={`form-select ${className}`} style={{ marginBottom: '16px' }}>
      {label && (
        <label
          htmlFor={name}
          style={{
            display: 'block',
            marginBottom: '4px',
            fontSize: '14px',
            fontWeight: '500',
            color: error ? '#ef4444' : '#374151'
          }}
        >
          {label}
          {required && <span style={{ color: '#ef4444' }}> *</span>}
        </label>
      )}

      <select
        id={name}
        name={name}
        value={value || ''}
        onChange={handleChange}
        disabled={disabled}
        required={required}
        style={{
          width: '100%',
          padding: '8px 12px',
          fontSize: '14px',
          border: `1px solid ${error ? '#ef4444' : '#d1d5db'}`,
          borderRadius: '6px',
          backgroundColor: disabled ? '#f9fafb' : '#ffffff',
          color: '#374151',
          outline: 'none',
          cursor: disabled ? 'not-allowed' : 'pointer',
          transition: prefersReducedMotion ? 'none' : 'border-color 0.2s ease, box-shadow 0.2s ease'
        }}
        onFocus={(e) => {
          if (!prefersReducedMotion) {
            e.target.style.borderColor = error ? '#ef4444' : '#3b82f6';
            e.target.style.boxShadow = `0 0 0 3px ${error ? '#fef2f2' : '#dbeafe'}`;
          }
        }}
        onBlur={(e) => {
          if (!prefersReducedMotion) {
            e.target.style.borderColor = error ? '#ef4444' : '#d1d5db';
            e.target.style.boxShadow = 'none';
          }
          if (onBlur) onBlur(e);
        }}
        {...props}
      >
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      {error && (
        <div
          style={{
            marginTop: '4px',
            fontSize: '12px',
            color: '#ef4444'
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
};

// Компонент формы
export const Form = ({
  children,
  onSubmit,
  className = '',
  style = {},
  ...props
}) => {
  const handleSubmit = (e) => {
    e.preventDefault();
    if (onSubmit) {
      onSubmit(e);
    }
  };

  return (
    <form
      className={`form ${className}`}
      onSubmit={handleSubmit}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        ...style
      }}
      {...props}
    >
      {children}
    </form>
  );
};

export default useForm;
