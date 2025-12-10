/**
 * React hook для безопасной работы с пользовательским вводом
 * XSS Protection для форм
 */
import { useState, useCallback } from 'react';
import { sanitizeInput, sanitizePhone, sanitizeEmail } from '../utils/sanitizer';
import logger from '../utils/logger';

/**
 * Hook для безопасной работы с input полями
 *
 * @param {*} initialValue - Начальное значение
 * @param {Object} options - Опции валидации
 * @returns {Array} [value, setValue, error]
 *
 * @example
 * const [name, setName, nameError] = useSafeInput('', {
 *   maxLength: 100,
 *   required: true,
 *   type: 'text'
 * });
 */
export function useSafeInput(initialValue = '', options = {}) {
  const {
    maxLength = 10000,
    required = false,
    type = 'text', // 'text', 'phone', 'email'
    allowNewlines = true,
    allowSpecialChars = true,
    customValidator = null
  } = options;

  const [value, setValueInternal] = useState(initialValue);
  const [error, setError] = useState('');

  const setValue = useCallback((newValue) => {
    if (newValue === null || newValue === undefined) {
      setValueInternal('');
      setError('');
      return;
    }

    let sanitized = '';
    let validationError = '';

    // Санитизация в зависимости от типа
    switch (type) {
      case 'phone':
        sanitized = sanitizePhone(newValue);
        break;

      case 'email':
        const emailResult = sanitizeEmail(newValue);
        if (emailResult === null && newValue.trim().length > 0) {
          validationError = 'Невалидный email адрес';
          sanitized = newValue; // Сохраняем для редактирования
        } else {
          sanitized = emailResult || '';
        }
        break;

      case 'text':
      default:
        sanitized = sanitizeInput(newValue, {
          maxLength,
          allowNewlines,
          allowSpecialChars
        });
        break;
    }

    // Проверка required
    if (required && !sanitized.trim()) {
      validationError = 'Поле обязательно для заполнения';
    }

    // Кастомная валидация
    if (customValidator && !validationError) {
      const customError = customValidator(sanitized);
      if (customError) {
        validationError = customError;
      }
    }

    // Логируем если была санитизация
    if (sanitized !== newValue) {
      logger.warn('Input был санитизирован:', {
        original: newValue.substring(0, 50),
        sanitized: sanitized.substring(0, 50)
      });
    }

    setValueInternal(sanitized);
    setError(validationError);
  }, [type, maxLength, required, allowNewlines, allowSpecialChars, customValidator]);

  return [value, setValue, error];
}

/**
 * Hook для безопасной работы с объектом формы
 *
 * @param {Object} initialState - Начальное состояние формы
 * @param {Object} validationRules - Правила валидации для каждого поля
 * @returns {Object} { values, errors, handleChange, handleBlur, isValid, reset }
 *
 * @example
 * const form = useSafeForm({
 *   name: '',
 *   phone: '',
 *   email: ''
 * }, {
 *   name: { required: true, maxLength: 100 },
 *   phone: { type: 'phone', required: true },
 *   email: { type: 'email', required: true }
 * });
 */
export function useSafeForm(initialState = {}, validationRules = {}) {
  const [values, setValues] = useState(initialState);
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});

  const validateField = useCallback((fieldName, value) => {
    const rules = validationRules[fieldName] || {};
    const {
      required = false,
      maxLength = 10000,
      minLength = 0,
      type = 'text',
      pattern = null,
      customValidator = null
    } = rules;

    let sanitized = value;
    let error = '';

    // Санитизация
    switch (type) {
      case 'phone':
        sanitized = sanitizePhone(value);
        break;

      case 'email':
        const emailResult = sanitizeEmail(value);
        if (emailResult === null && value.trim().length > 0) {
          error = 'Невалидный email адрес';
        }
        sanitized = emailResult || value;
        break;

      case 'text':
      default:
        sanitized = sanitizeInput(value, {
          maxLength,
          allowNewlines: rules.allowNewlines !== false,
          allowSpecialChars: rules.allowSpecialChars !== false
        });
        break;
    }

    // Валидация
    if (!error) {
      if (required && !sanitized.trim()) {
        error = rules.errorMessage || 'Поле обязательно для заполнения';
      } else if (sanitized.length < minLength) {
        error = `Минимальная длина: ${minLength} символов`;
      } else if (sanitized.length > maxLength) {
        error = `Максимальная длина: ${maxLength} символов`;
      } else if (pattern && !pattern.test(sanitized)) {
        error = rules.errorMessage || 'Неверный формат';
      } else if (customValidator) {
        error = customValidator(sanitized) || '';
      }
    }

    return { sanitized, error };
  }, [validationRules]);

  const handleChange = useCallback((fieldName) => (event) => {
    const rawValue = event.target?.value ?? event;
    const { sanitized, error } = validateField(fieldName, rawValue);

    setValues(prev => ({ ...prev, [fieldName]: sanitized }));
    setErrors(prev => ({ ...prev, [fieldName]: error }));
  }, [validateField]);

  const handleBlur = useCallback((fieldName) => () => {
    setTouched(prev => ({ ...prev, [fieldName]: true }));

    // Перевалидация при blur
    const currentValue = values[fieldName] || '';
    const { error } = validateField(fieldName, currentValue);
    setErrors(prev => ({ ...prev, [fieldName]: error }));
  }, [values, validateField]);

  const isValid = useCallback(() => {
    // Проверяем все поля
    const allErrors = {};
    let hasErrors = false;

    Object.keys(validationRules).forEach(fieldName => {
      const { error } = validateField(fieldName, values[fieldName] || '');
      if (error) {
        allErrors[fieldName] = error;
        hasErrors = true;
      }
    });

    if (hasErrors) {
      setErrors(allErrors);
      setTouched(Object.keys(validationRules).reduce((acc, key) => {
        acc[key] = true;
        return acc;
      }, {}));
    }

    return !hasErrors;
  }, [values, validationRules, validateField]);

  const reset = useCallback(() => {
    setValues(initialState);
    setErrors({});
    setTouched({});
  }, [initialState]);

  const setValue = useCallback((fieldName, value) => {
    const { sanitized, error } = validateField(fieldName, value);
    setValues(prev => ({ ...prev, [fieldName]: sanitized }));
    setErrors(prev => ({ ...prev, [fieldName]: error }));
  }, [validateField]);

  return {
    values,
    errors,
    touched,
    handleChange,
    handleBlur,
    isValid,
    reset,
    setValue
  };
}

/**
 * Hook для безопасного textarea с предпросмотром санитизации
 *
 * @param {string} initialValue - Начальное значение
 * @param {Object} options - Опции
 * @returns {Object} { value, setValue, sanitizedPreview, error }
 */
export function useSafeTextarea(initialValue = '', options = {}) {
  const [rawValue, setRawValue] = useState(initialValue);
  const [value, setValue, error] = useSafeInput(initialValue, {
    ...options,
    allowNewlines: true
  });

  const sanitizedPreview = sanitizeInput(rawValue, {
    maxLength: options.maxLength || 10000,
    allowNewlines: true,
    allowSpecialChars: options.allowSpecialChars !== false
  });

  const handleChange = useCallback((newValue) => {
    setRawValue(newValue);
    setValue(newValue);
  }, [setValue]);

  return {
    value,
    setValue: handleChange,
    sanitizedPreview,
    error,
    isDifferent: sanitizedPreview !== rawValue
  };
}

export default useSafeInput;
