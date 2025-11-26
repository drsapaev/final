// Экспорт всех компонентов форм
export { default as ModernInput } from './ModernInput';
export { default as ModernSelect } from './ModernSelect';
export { default as ModernTextarea } from './ModernTextarea';
export { default as ModernForm, FormGroup, FormRow, FormColumn } from './ModernForm';

// Валидаторы
export const validators = {
  required: (message = 'Поле обязательно для заполнения') => (value) => {
    if (!value || (typeof value === 'string' && !value.trim())) {
      return message;
    }
    return true;
  },

  email: (message = 'Введите корректный email') => (value) => {
    if (!value) return true;
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(value) ? true : message;
  },

  phone: (message = 'Введите корректный номер телефона') => (value) => {
    if (!value) return true;
    const phoneRegex = /^\+?[\d\s\-\(\)]{10,}$/;
    return phoneRegex.test(value) ? true : message;
  },

  minLength: (min, message) => (value) => {
    if (!value) return true;
    const actualMessage = message || `Минимум ${min} символов`;
    return value.length >= min ? true : actualMessage;
  },

  maxLength: (max, message) => (value) => {
    if (!value) return true;
    const actualMessage = message || `Максимум ${max} символов`;
    return value.length <= max ? true : actualMessage;
  },

  pattern: (regex, message = 'Неверный формат') => (value) => {
    if (!value) return true;
    return regex.test(value) ? true : message;
  },

  numeric: (message = 'Только цифры') => (value) => {
    if (!value) return true;
    return /^\d+$/.test(value) ? true : message;
  },

  alphanumeric: (message = 'Только буквы и цифры') => (value) => {
    if (!value) return true;
    return /^[a-zA-Zа-яА-Я0-9]+$/.test(value) ? true : message;
  },

  min: (min, message) => (value) => {
    if (!value) return true;
    const num = parseFloat(value);
    const actualMessage = message || `Минимальное значение: ${min}`;
    return num >= min ? true : actualMessage;
  },

  max: (max, message) => (value) => {
    if (!value) return true;
    const num = parseFloat(value);
    const actualMessage = message || `Максимальное значение: ${max}`;
    return num <= max ? true : actualMessage;
  },

  match: (fieldName, message) => (value, allValues) => {
    if (!value) return true;
    const actualMessage = message || 'Поля не совпадают';
    return value === allValues[fieldName] ? true : actualMessage;
  },

  custom: (validator, message = 'Неверное значение') => (value, allValues) => {
    const result = validator(value, allValues);
    return result === true ? true : (typeof result === 'string' ? result : message);
  }
};

// Утилиты для работы с формами
export const formUtils = {
  // Создание начальных значений из схемы
  createInitialValues: (schema, defaultValues = {}) => {
    const initialValues = { ...defaultValues };
    
    Object.keys(schema).forEach(fieldName => {
      if (!(fieldName in initialValues)) {
        initialValues[fieldName] = '';
      }
    });
    
    return initialValues;
  },

  // Очистка значений формы
  clearForm: (schema) => {
    const clearedValues = {};
    
    Object.keys(schema).forEach(fieldName => {
      clearedValues[fieldName] = '';
    });
    
    return clearedValues;
  },

  // Проверка изменений в форме
  hasChanges: (currentValues, initialValues) => {
    return JSON.stringify(currentValues) !== JSON.stringify(initialValues);
  },

  // Получение только измененных полей
  getChangedFields: (currentValues, initialValues) => {
    const changes = {};
    
    Object.keys(currentValues).forEach(key => {
      if (currentValues[key] !== initialValues[key]) {
        changes[key] = currentValues[key];
      }
    });
    
    return changes;
  },

  // Форматирование данных для отправки
  formatForSubmission: (values, formatters = {}) => {
    const formatted = { ...values };
    
    Object.keys(formatters).forEach(fieldName => {
      if (fieldName in formatted) {
        formatted[fieldName] = formatters[fieldName](formatted[fieldName]);
      }
    });
    
    return formatted;
  }
};
