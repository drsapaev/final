/* eslint-disable no-console */
/**
 * Безопасный логгер с автоматической санитизацией PHI
 * Предотвращает случайное логирование Protected Health Information
 *
 * HIPAA Compliance: Never log PHI in production
 */

/**
 * Поля, содержащие PHI (Protected Health Information)
 * Эти данные никогда не должны попадать в логи
 */
const PHI_FIELDS = [
  // Идентификаторы пациента
  'patient_id', 'patientId', 'patient_name', 'patientName',
  'full_name', 'fullName', 'firstName', 'lastName', 'middleName',
  'first_name', 'last_name', 'middle_name',
  'name', 'surname', 'patronymic',

  // Контактная информация
  'phone', 'phone_number', 'phoneNumber', 'mobile', 'email',
  'address', 'street', 'city', 'postal_code', 'postalCode',

  // Медицинские данные
  'diagnosis', 'symptoms', 'complaint', 'complaints',
  'medical_history', 'medicalHistory', 'treatment', 'prescription',
  'lab_results', 'labResults', 'test_results', 'testResults',
  'blood_type', 'bloodType', 'allergies', 'medications',

  // Биометрические данные
  'date_of_birth', 'dateOfBirth', 'birth_date', 'birthDate', 'dob',
  'ssn', 'passport', 'insurance_number', 'insuranceNumber',

  // Финансовые данные
  'card_number', 'cardNumber', 'cvv', 'payment_method', 'paymentMethod',

  // Аутентификация
  'password', 'token', 'access_token', 'refresh_token',
  'secret', 'api_key', 'apiKey'
];

/**
 * Проверка, является ли окружение development
 */
const isDevelopment = import.meta.env.MODE === 'development';

/**
 * Быстрая проверка - нужна ли санитизация
 * В development режиме можно отключить для производительности
 */
const ENABLE_SANITIZATION = import.meta.env.VITE_ENABLE_PHI_SANITIZATION !== 'false';

/**
 * Санитизация объекта - замена PHI на [REDACTED]
 * @param {any} data - Данные для санитизации
 * @param {number} depth - Текущая глубина рекурсии (защита от циклических ссылок)
 * @param {WeakSet} seen - Set для отслеживания циклических ссылок
 * @returns {any} Санитизированные данные
 */
function sanitize(data, depth = 0, seen = new WeakSet()) {
  // Защита от глубокой рекурсии
  if (depth > 3) {
    return '[MAX_DEPTH]';
  }

  // Null и undefined
  if (data === null || data === undefined) {
    return data;
  }

  // Примитивы (number, string, boolean)
  if (typeof data !== 'object') {
    return data;
  }

  // Защита от циклических ссылок
  if (seen.has(data)) {
    return '[CIRCULAR]';
  }

  // Защита от DOM элементов и React элементов
  if (data instanceof Element || data instanceof Node || data.$$typeof) {
    return '[DOM_OR_REACT_ELEMENT]';
  }

  // Защита от больших объектов - пропускаем без обработки
  if (data.constructor && data.constructor.name &&
      (data.constructor.name.includes('Fiber') ||
       data.constructor.name.includes('Synthetic') ||
       data.constructor.name.includes('Event'))) {
    return `[${data.constructor.name}]`;
  }

  // Добавляем объект в seen
  seen.add(data);

  try {
    // Массивы - ограничиваем до 5 элементов для скорости
    if (Array.isArray(data)) {
      if (data.length > 5) {
        return `[Array(${data.length}) - showing first 5]`;
      }
      return data.map(item => sanitize(item, depth + 1, seen));
    }

    // Объекты - быстрая проверка размера
    const keys = Object.keys(data);
    if (keys.length > 15) {
      return `[Object with ${keys.length} fields]`;
    }

    // Объекты - ограничиваем количество полей
    const sanitized = {};
    let count = 0;
    const maxFields = 15;

    for (const [key, value] of Object.entries(data)) {
      if (count >= maxFields) {
        sanitized['...'] = `[${keys.length - maxFields} more]`;
        break;
      }

      const lowerKey = key.toLowerCase();

      // Быстрая проверка PHI (без toLowerCase в цикле)
      let isPHI = false;
      for (let i = 0; i < PHI_FIELDS.length; i++) {
        if (lowerKey.includes(PHI_FIELDS[i].toLowerCase())) {
          isPHI = true;
          break;
        }
      }

      if (isPHI) {
        sanitized[key] = '[REDACTED]';
      } else if (typeof value === 'object' && value !== null) {
        sanitized[key] = sanitize(value, depth + 1, seen);
      } else {
        sanitized[key] = value;
      }

      count++;
    }

    return sanitized;
  } catch (error) {
    return '[SANITIZATION_ERROR]';
  }
}

/**
 * Форматирование аргументов для логирования
 * @param {Array} args - Аргументы
 * @returns {Array} Санитизированные аргументы
 */
function formatArgs(args) {
  // Если санитизация отключена, возвращаем как есть
  if (!ENABLE_SANITIZATION) {
    return args;
  }

  try {
    return args.map(arg => {
      // Пропускаем примитивы как есть
      if (arg === null || arg === undefined || typeof arg !== 'object') {
        return arg;
      }

      // Error объекты - показываем только message
      if (arg instanceof Error) {
        return {
          name: arg.name,
          message: arg.message,
          stack: arg.stack?.split('\n').slice(0, 3).join('\n')
        };
      }

      // Для объектов применяем санитизацию
      try {
        return sanitize(arg);
      } catch (error) {
        return '[OBJECT - SANITIZATION FAILED]';
      }
    });
  } catch (error) {
    // Если даже formatArgs упал, возвращаем безопасное значение
    return ['[LOGGING ERROR]'];
  }
}

/**
 * Безопасный логгер
 */
export const logger = {
  /**
   * Обычное информационное сообщение
   */
  log(...args) {
    if (isDevelopment) {
      console.log('[LOG]', ...formatArgs(args));
    }
  },

  /**
   * Информационное сообщение
   */
  info(...args) {
    if (isDevelopment) {
      console.info('[INFO]', ...formatArgs(args));
    }
  },

  /**
   * Предупреждение
   */
  warn(...args) {
    if (isDevelopment) {
      console.warn('[WARN]', ...formatArgs(args));
    }
  },

  /**
   * Ошибка - всегда логируется, даже в production
   */
  error(...args) {
    // Ошибки логируем всегда, но санитизируем
    console.error('[ERROR]', ...formatArgs(args));
  },

  /**
   * Отладочная информация - только в development
   */
  debug(...args) {
    if (isDevelopment) {
      console.debug('[DEBUG]', ...formatArgs(args));
    }
  },

  /**
   * Группировка логов
   */
  group(label) {
    if (isDevelopment) {
      console.group(label);
    }
  },

  /**
   * Закрытие группы
   */
  groupEnd() {
    if (isDevelopment) {
      console.groupEnd();
    }
  },

  /**
   * Таблица - только в development
   */
  table(data) {
    if (isDevelopment) {
      console.table(sanitize(data));
    }
  },

  /**
   * Замер времени
   */
  time(label) {
    if (isDevelopment) {
      console.time(label);
    }
  },

  /**
   * Завершение замера времени
   */
  timeEnd(label) {
    if (isDevelopment) {
      console.timeEnd(label);
    }
  }
};

/**
 * Utility для санитизации данных вручную
 * Полезно для подготовки данных перед отправкой в внешние системы
 */
export { sanitize };

/**
 * Проверка, является ли поле PHI
 * @param {string} fieldName - Имя поля
 * @returns {boolean}
 */
export function isPHIField(fieldName) {
  const lowerField = fieldName.toLowerCase();
  return PHI_FIELDS.some(phiField =>
    lowerField.includes(phiField.toLowerCase())
  );
}

export default logger;
