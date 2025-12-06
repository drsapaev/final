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
 * Санитизация объекта - замена PHI на [REDACTED]
 * @param {any} data - Данные для санитизации
 * @param {number} depth - Текущая глубина рекурсии (защита от циклических ссылок)
 * @returns {any} Санитизированные данные
 */
function sanitize(data, depth = 0) {
  // Защита от глубокой рекурсии
  if (depth > 10) {
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

  // Массивы
  if (Array.isArray(data)) {
    return data.map(item => sanitize(item, depth + 1));
  }

  // Объекты
  const sanitized = {};
  for (const [key, value] of Object.entries(data)) {
    const lowerKey = key.toLowerCase();

    // Проверяем, содержит ли ключ PHI
    const isPHI = PHI_FIELDS.some(phiField =>
      lowerKey.includes(phiField.toLowerCase())
    );

    if (isPHI) {
      sanitized[key] = '[REDACTED]';
    } else if (typeof value === 'object' && value !== null) {
      sanitized[key] = sanitize(value, depth + 1);
    } else {
      sanitized[key] = value;
    }
  }

  return sanitized;
}

/**
 * Форматирование аргументов для логирования
 * @param {Array} args - Аргументы
 * @returns {Array} Санитизированные аргументы
 */
function formatArgs(args) {
  return args.map(arg => {
    if (typeof arg === 'object' && arg !== null) {
      return sanitize(arg);
    }
    return arg;
  });
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
