// src/utils/logger.ts
// Phase 1 — migrated from .js. PHI-sanitizing logger; types added.
//
// HIPAA Compliance: Never log PHI in production. The sanitize() function
// below replaces known PHI field values with [REDACTED] before any console
// output. Sanitization is on by default; can be disabled in dev via
// VITE_ENABLE_PHI_SANITIZATION=false (useful for debugging).

/* eslint-disable no-console */

/**
 * Поля, содержащие PHI (Protected Health Information).
 * Эти данные никогда не должны попадать в логи.
 */
const PHI_FIELDS: readonly string[] = [
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
  'secret', 'api_key', 'apiKey',
];

const isDevelopment: boolean = import.meta.env.MODE === 'development';

const ENABLE_SANITIZATION: boolean = import.meta.env.VITE_ENABLE_PHI_SANITIZATION !== 'false';

/**
 * Санитизация объекта — замена PHI на [REDACTED].
 */
function sanitize(data: unknown, depth: number = 0, seen: WeakSet<object> = new WeakSet()): unknown {
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
  if (seen.has(data as object)) {
    return '[CIRCULAR]';
  }

  // Защита от DOM элементов и React элементов
  // `$$typeof` is the React element symbol; check structurally to avoid
  // importing React internals.
  const maybeReact = data as { $$typeof?: unknown };
  if (data instanceof Element || data instanceof Node || maybeReact.$$typeof) {
    return '[DOM_OR_REACT_ELEMENT]';
  }

  // Защита от больших объектов — пропускаем без обработки
  const ctor = (data as { constructor?: { name?: string } }).constructor;
  if (ctor?.name && (
    ctor.name.includes('Fiber') ||
    ctor.name.includes('Synthetic') ||
    ctor.name.includes('Event')
  )) {
    return `[${ctor.name}]`;
  }

  seen.add(data as object);

  try {
    // Массивы — ограничиваем до 5 элементов для скорости
    if (Array.isArray(data)) {
      if (data.length > 5) {
        return `[Array(${data.length}) - showing first 5]`;
      }
      return data.map((item) => sanitize(item, depth + 1, seen));
    }

    // Объекты — быстрая проверка размера
    const keys = Object.keys(data);
    if (keys.length > 15) {
      return `[Object with ${keys.length} fields]`;
    }

    // Объекты — ограничиваем количество полей
    const sanitized: Record<string, unknown> = {};
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
  } catch {
    return '[SANITIZATION_ERROR]';
  }
}

/**
 * Форматирование аргументов для логирования.
 */
function formatArgs(args: unknown[]): unknown[] {
  // Если санитизация отключена, возвращаем как есть
  if (!ENABLE_SANITIZATION) {
    return args;
  }

  try {
    return args.map((arg) => {
      // Пропускаем примитивы как есть
      if (arg === null || arg === undefined || typeof arg !== 'object') {
        return arg;
      }

      // Error объекты — показываем только message
      if (arg instanceof Error) {
        return {
          name: arg.name,
          message: arg.message,
          stack: arg.stack?.split('\n').slice(0, 3).join('\n'),
        };
      }

      // Для объектов применяем санитизацию
      try {
        return sanitize(arg);
      } catch {
        return '[OBJECT - SANITIZATION FAILED]';
      }
    });
  } catch {
    // Если даже formatArgs упал, возвращаем безопасное значение
    return ['[LOGGING ERROR]'];
  }
}

/**
 * Безопасный логгер
 */
export const logger = {
  /** Обычное информационное сообщение */
  log(...args: unknown[]): void {
    if (isDevelopment) {
      console.log('[LOG]', ...formatArgs(args));
    }
  },

  /** Информационное сообщение */
  info(...args: unknown[]): void {
    if (isDevelopment) {
      console.info('[INFO]', ...formatArgs(args));
    }
  },

  /** Предупреждение */
  warn(...args: unknown[]): void {
    if (isDevelopment) {
      console.warn('[WARN]', ...formatArgs(args));
    }
  },

  /** Ошибка — всегда логируется, даже в production */
  error(...args: unknown[]): void {
    console.error('[ERROR]', ...formatArgs(args));
  },

  /** Отладочная информация — только в development */
  debug(...args: unknown[]): void {
    if (isDevelopment) {
      console.debug('[DEBUG]', ...formatArgs(args));
    }
  },

  /** Группировка логов */
  group(label: string): void {
    if (isDevelopment) {
      console.group(label);
    }
  },

  /** Закрытие группы */
  groupEnd(): void {
    if (isDevelopment) {
      console.groupEnd();
    }
  },

  /** Таблица — только в development */
  table(data: unknown): void {
    if (isDevelopment) {
      console.table(sanitize(data));
    }
  },

  /** Замер времени */
  time(label: string): void {
    if (isDevelopment) {
      console.time(label);
    }
  },

  /** Завершение замера времени */
  timeEnd(label: string): void {
    if (isDevelopment) {
      console.timeEnd(label);
    }
  },
};

/** Utility для санитизации данных вручную. */
export { sanitize };

/**
 * Проверка, является ли поле PHI.
 */
export function isPHIField(fieldName: string): boolean {
  const lowerField = fieldName.toLowerCase();
  return PHI_FIELDS.some((phiField) => lowerField.includes(phiField.toLowerCase()));
}

export default logger;
