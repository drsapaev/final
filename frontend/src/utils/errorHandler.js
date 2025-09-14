/**
 * Единая система обработки ошибок
 * Централизованное логирование и отображение ошибок
 */

/**
 * Типы ошибок
 */
export const ErrorTypes = {
  NETWORK: 'network',
  AUTH: 'auth',
  VALIDATION: 'validation',
  SERVER: 'server',
  PERMISSION: 'permission',
  NOT_FOUND: 'not_found',
  UNKNOWN: 'unknown'
};

/**
 * Определение типа ошибки
 */
function getErrorType(error) {
  if (!error.response) {
    return ErrorTypes.NETWORK;
  }

  const status = error.response.status;
  
  if (status === 401) return ErrorTypes.AUTH;
  if (status === 403) return ErrorTypes.PERMISSION;
  if (status === 404) return ErrorTypes.NOT_FOUND;
  if (status === 422) return ErrorTypes.VALIDATION;
  if (status >= 500) return ErrorTypes.SERVER;
  
  return ErrorTypes.UNKNOWN;
}

/**
 * Получение пользовательского сообщения об ошибке
 */
function getUserMessage(error, errorType) {
  // Если есть детальное сообщение от сервера, используем его
  const serverMessage = error.response?.data?.detail || error.response?.data?.message;
  
  if (serverMessage && typeof serverMessage === 'string') {
    return serverMessage;
  }

  // Стандартные сообщения по типам ошибок
  const defaultMessages = {
    [ErrorTypes.NETWORK]: 'Проблемы с подключением к серверу. Проверьте интернет-соединение.',
    [ErrorTypes.AUTH]: 'Требуется авторизация. Пожалуйста, войдите в систему.',
    [ErrorTypes.PERMISSION]: 'Недостаточно прав для выполнения операции.',
    [ErrorTypes.NOT_FOUND]: 'Запрашиваемый ресурс не найден.',
    [ErrorTypes.VALIDATION]: 'Проверьте правильность введенных данных.',
    [ErrorTypes.SERVER]: 'Серверная ошибка. Попробуйте позже или обратитесь к администратору.',
    [ErrorTypes.UNKNOWN]: 'Произошла неизвестная ошибка. Попробуйте еще раз.'
  };

  return defaultMessages[errorType] || defaultMessages[ErrorTypes.UNKNOWN];
}

/**
 * Логирование ошибки
 */
function logError(error, context = '') {
  const errorInfo = {
    timestamp: new Date().toISOString(),
    context,
    url: error.config?.url,
    method: error.config?.method,
    status: error.response?.status,
    statusText: error.response?.statusText,
    data: error.response?.data,
    message: error.message
  };

  // В development выводим подробную информацию
  if (process.env.NODE_ENV === 'development') {
    console.group(`❌ Error Handler: ${context || 'Unknown context'}`);
    console.error('Error details:', errorInfo);
    console.error('Original error:', error);
    console.groupEnd();
  }

  // В production отправляем ошибки в систему мониторинга
  if (process.env.NODE_ENV === 'production') {
    // TODO: Интеграция с системой мониторинга (Sentry, LogRocket, etc.)
    console.error('Production error:', errorInfo);
  }
}

/**
 * Основная функция обработки ошибок
 */
export function handleError(error, context = '', options = {}) {
  const {
    showToast = true,
    logError: shouldLog = true,
    customMessage = null
  } = options;

  // Логируем ошибку
  if (shouldLog) {
    logError(error, context);
  }

  // Определяем тип ошибки
  const errorType = getErrorType(error);
  
  // Получаем сообщение для пользователя
  const userMessage = customMessage || getUserMessage(error, errorType);

  // Показываем уведомление пользователю
  if (showToast && window.showToast) {
    const toastType = errorType === ErrorTypes.VALIDATION ? 'warning' : 'error';
    window.showToast(userMessage, toastType);
  }

  // Возвращаем структурированную информацию об ошибке
  return {
    type: errorType,
    message: userMessage,
    originalError: error,
    status: error.response?.status,
    data: error.response?.data
  };
}

/**
 * Обработчик для async/await функций
 */
export function withErrorHandler(asyncFunction, context = '') {
  return async (...args) => {
    try {
      return await asyncFunction(...args);
    } catch (error) {
      const errorInfo = handleError(error, context);
      
      // Возвращаем результат с ошибкой вместо выброса исключения
      return {
        success: false,
        error: errorInfo.message,
        errorType: errorInfo.type,
        errorDetails: errorInfo
      };
    }
  };
}

/**
 * React Hook для обработки ошибок в компонентах
 */
export function useErrorHandler() {
  return (error, context = '') => {
    return handleError(error, context);
  };
}

/**
 * Валидация данных форм
 */
export function validateFormData(data, rules) {
  const errors = {};
  
  for (const field in rules) {
    const rule = rules[field];
    const value = data[field];
    
    // Проверка обязательности
    if (rule.required && (!value || (typeof value === 'string' && !value.trim()))) {
      errors[field] = rule.message || `Поле "${field}" обязательно для заполнения`;
      continue;
    }
    
    // Проверка минимальной длины
    if (rule.minLength && value && value.length < rule.minLength) {
      errors[field] = rule.message || `Минимальная длина: ${rule.minLength} символов`;
      continue;
    }
    
    // Проверка максимальной длины
    if (rule.maxLength && value && value.length > rule.maxLength) {
      errors[field] = rule.message || `Максимальная длина: ${rule.maxLength} символов`;
      continue;
    }
    
    // Проверка паттерна (email, телефон и т.д.)
    if (rule.pattern && value && !rule.pattern.test(value)) {
      errors[field] = rule.message || `Неверный формат поля "${field}"`;
      continue;
    }
    
    // Кастомная валидация
    if (rule.validator && value) {
      const customError = rule.validator(value, data);
      if (customError) {
        errors[field] = customError;
      }
    }
  }
  
  return {
    isValid: Object.keys(errors).length === 0,
    errors
  };
}

/**
 * Предустановленные правила валидации
 */
export const ValidationRules = {
  email: {
    pattern: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
    message: 'Введите корректный email адрес'
  },
  
  phone: {
    pattern: /^\+?[1-9]\d{1,14}$/,
    message: 'Введите корректный номер телефона'
  },
  
  password: {
    minLength: 6,
    message: 'Пароль должен содержать минимум 6 символов'
  },
  
  required: {
    required: true,
    message: 'Это поле обязательно для заполнения'
  }
};
