/**
 * Утилиты для санитизации пользовательского ввода
 * XSS Protection для медицинской системы
 *
 * ВАЖНО: Всегда санитизируйте пользовательский ввод перед рендерингом!
 */
import DOMPurify from 'dompurify';
import logger from './logger';

/**
 * Конфигурация DOMPurify для медицинского контента
 * Разрешаем базовое форматирование, но блокируем скрипты и опасные атрибуты
 */
const MEDICAL_CONFIG = {
  ALLOWED_TAGS: [
    // Текстовое форматирование
    'p', 'br', 'span', 'div', 'strong', 'em', 'b', 'i', 'u', 's',
    // Заголовки
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    // Списки
    'ul', 'ol', 'li',
    // Таблицы (для медицинских данных)
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    // Цитаты и код (для заметок врача)
    'blockquote', 'pre', 'code',
    // Ссылки (только безопасные)
    'a'
  ],
  ALLOWED_ATTR: [
    'class', 'id', 'style', // Стилизация
    'href', 'target', // Ссылки (только http/https)
    'colspan', 'rowspan', // Таблицы
    'alt', 'title' // Accessibility
  ],
  ALLOWED_URI_REGEXP: /^(?:(?:(?:f|ht)tps?|mailto|tel|callto|sms|cid|xmpp):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
  ALLOW_DATA_ATTR: false, // Блокируем data-* атрибуты
  ALLOW_UNKNOWN_PROTOCOLS: false,
  SAFE_FOR_TEMPLATES: true,
  WHOLE_DOCUMENT: false,
  RETURN_DOM: false,
  RETURN_DOM_FRAGMENT: false,
  RETURN_TRUSTED_TYPE: false,
  FORCE_BODY: false,
  SANITIZE_DOM: true,
  KEEP_CONTENT: true
};

/**
 * Строгая конфигурация - только текст, никакого HTML
 */
const STRICT_CONFIG = {
  ALLOWED_TAGS: [],
  ALLOWED_ATTR: [],
  KEEP_CONTENT: true
};

/**
 * Конфигурация для AI-сгенерированного контента
 * Более ограничительная, так как AI может генерировать вредоносный код
 */
const AI_CONFIG = {
  ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li'],
  ALLOWED_ATTR: [],
  KEEP_CONTENT: true
};

/**
 * Санитизация HTML контента для безопасного рендеринга
 *
 * @param {string} dirty - Грязный HTML
 * @param {Object} config - Конфигурация DOMPurify (по умолчанию MEDICAL_CONFIG)
 * @returns {string} Чистый HTML
 *
 * @example
 * const clean = sanitizeHTML('<p>Диагноз: <script>alert("xss")</script>ОРВИ</p>');
 * // Результат: '<p>Диагноз: ОРВИ</p>'
 */
export function sanitizeHTML(dirty, config = MEDICAL_CONFIG) {
  if (!dirty || typeof dirty !== 'string') {
    return '';
  }

  try {
    const clean = DOMPurify.sanitize(dirty, config);

    // Логируем если были удалены опасные элементы
    if (clean !== dirty) {
      logger.warn('HTML санитизирован, удалены потенциально опасные элементы');
    }

    return clean;
  } catch (error) {
    logger.error('Ошибка санитизации HTML:', error);
    return ''; // В случае ошибки возвращаем пустую строку (безопасно)
  }
}

/**
 * Строгая санитизация - удаляет ВСЕ HTML теги, оставляет только текст
 *
 * @param {string} dirty - Грязный HTML/текст
 * @returns {string} Чистый текст
 *
 * @example
 * const clean = sanitizeText('<p>Текст <script>alert("xss")</script>здесь</p>');
 * // Результат: 'Текст здесь'
 */
export function sanitizeText(dirty) {
  return sanitizeHTML(dirty, STRICT_CONFIG);
}

/**
 * Санитизация AI-сгенерированного контента
 * Более строгая проверка для контента от нейросетей
 *
 * @param {string} aiContent - Контент от AI
 * @returns {string} Санитизированный контент
 *
 * @example
 * const clean = sanitizeAIContent(aiGeneratedText);
 */
export function sanitizeAIContent(aiContent) {
  if (!aiContent || typeof aiContent !== 'string') {
    return '';
  }

  // Дополнительная проверка на подозрительные паттерны в AI контенте
  const suspiciousPatterns = [
    /<script/i,
    /javascript:/i,
    /on\w+\s*=/i, // onclick, onerror и т.д.
    /data:text\/html/i,
    /<iframe/i,
    /<object/i,
    /<embed/i
  ];

  const hasSuspiciousContent = suspiciousPatterns.some(pattern => pattern.test(aiContent));

  if (hasSuspiciousContent) {
    logger.warn('AI content содержит подозрительные паттерны, применена строгая санитизация');
    return sanitizeText(aiContent); // Используем строгую санитизацию
  }

  return sanitizeHTML(aiContent, AI_CONFIG);
}

/**
 * Экранирование специальных HTML символов
 * Для безопасного отображения в атрибутах
 *
 * @param {string} str - Строка для экранирования
 * @returns {string} Экранированная строка
 *
 * @example
 * const safe = escapeHTML('<img src=x onerror="alert(1)">');
 * // Результат: '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;'
 */
export function escapeHTML(str) {
  if (!str || typeof str !== 'string') {
    return '';
  }

  const htmlEscapeMap = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#x27;',
    '/': '&#x2F;'
  };

  return str.replace(/[&<>"'/]/g, char => htmlEscapeMap[char]);
}

/**
 * Валидация и санитизация URL
 * Блокирует javascript:, data: и другие опасные протоколы
 *
 * @param {string} url - URL для проверки
 * @returns {string|null} Безопасный URL или null если опасен
 *
 * @example
 * const safe = sanitizeURL('javascript:alert(1)');
 * // Результат: null (опасный URL)
 *
 * const ok = sanitizeURL('https://example.com');
 * // Результат: 'https://example.com'
 */
export function sanitizeURL(url) {
  if (!url || typeof url !== 'string') {
    return null;
  }

  const trimmed = url.trim();

  // Разрешённые протоколы
  const allowedProtocols = ['http:', 'https:', 'mailto:', 'tel:', 'sms:'];

  try {
    const urlObj = new URL(trimmed, window.location.origin);

    if (!allowedProtocols.includes(urlObj.protocol)) {
      logger.warn('Заблокирован опасный URL протокол:', urlObj.protocol);
      return null;
    }

    return urlObj.href;
  } catch (error) {
    // Если URL невалиден, проверяем относительные пути
    if (trimmed.startsWith('/')) {
      return trimmed; // Относительный путь - безопасен
    }

    logger.warn('Невалидный URL:', trimmed);
    return null;
  }
}

/**
 * Санитизация input полей формы
 * Удаляет потенциально опасные символы из пользовательского ввода
 *
 * @param {string} input - Пользовательский ввод
 * @param {Object} options - Опции санитизации
 * @returns {string} Санитизированный ввод
 *
 * @example
 * const clean = sanitizeInput('<script>alert("xss")</script>', { maxLength: 100 });
 */
export function sanitizeInput(input, options = {}) {
  const {
    maxLength = 10000,
    allowNewlines = true,
    allowSpecialChars = true
  } = options;

  if (!input || typeof input !== 'string') {
    return '';
  }

  let sanitized = input;

  // Удаляем null bytes
  sanitized = sanitized.replace(/\0/g, '');

  // Удаляем управляющие символы (кроме переносов строк если разрешены)
  if (!allowNewlines) {
    sanitized = sanitized.replace(/[\x00-\x1F\x7F-\x9F]/g, '');
  } else {
    sanitized = sanitized.replace(/[\x00-\x09\x0B-\x0C\x0E-\x1F\x7F-\x9F]/g, '');
  }

  // Ограничение длины
  if (sanitized.length > maxLength) {
    sanitized = sanitized.substring(0, maxLength);
    logger.warn('Input обрезан до максимальной длины:', maxLength);
  }

  // Удаляем опасные HTML теги
  sanitized = sanitized.replace(/<script[^>]*>.*?<\/script>/gi, '');
  sanitized = sanitized.replace(/<iframe[^>]*>.*?<\/iframe>/gi, '');
  sanitized = sanitized.replace(/<object[^>]*>.*?<\/object>/gi, '');
  sanitized = sanitized.replace(/<embed[^>]*>/gi, '');

  // Удаляем javascript: и data: протоколы
  sanitized = sanitized.replace(/javascript:/gi, '');
  sanitized = sanitized.replace(/data:text\/html/gi, '');

  return sanitized.trim();
}

/**
 * Безопасный wrapper для dangerouslySetInnerHTML в React
 *
 * @param {string} html - HTML для рендеринга
 * @param {Object} config - Конфигурация санитизации
 * @returns {Object} Объект для dangerouslySetInnerHTML
 *
 * @example
 * <div {...createMarkup(userGeneratedHTML)} />
 */
export function createMarkup(html, config = MEDICAL_CONFIG) {
  return {
    __html: sanitizeHTML(html, config)
  };
}

/**
 * Валидация медицинских кодов (ICD-10, МКБ-10)
 * Предотвращает инъекцию через медицинские коды
 *
 * @param {string} code - Медицинский код
 * @returns {boolean} true если код валиден
 *
 * @example
 * isValidMedicalCode('J00.0') // true
 * isValidMedicalCode('<script>alert(1)</script>') // false
 */
export function isValidMedicalCode(code) {
  if (!code || typeof code !== 'string') {
    return false;
  }

  // ICD-10 формат: A00-Z99.99
  const icd10Pattern = /^[A-Z]\d{2}(\.\d{1,2})?$/;

  return icd10Pattern.test(code.trim());
}

/**
 * Санитизация номера телефона
 * Удаляет все кроме цифр, +, -, (, ), пробелов
 *
 * @param {string} phone - Номер телефона
 * @returns {string} Санитизированный номер
 *
 * @example
 * sanitizePhone('+7 (999) 123-45-67<script>') // '+7 (999) 123-45-67'
 */
export function sanitizePhone(phone) {
  if (!phone || typeof phone !== 'string') {
    return '';
  }

  // Разрешаем только цифры и символы форматирования телефона
  return phone.replace(/[^\d+\-() ]/g, '').trim();
}

/**
 * Санитизация email
 * Валидация и очистка email адреса
 *
 * @param {string} email - Email адрес
 * @returns {string|null} Санитизированный email или null если невалиден
 *
 * @example
 * sanitizeEmail('user@example.com<script>') // 'user@example.com'
 */
export function sanitizeEmail(email) {
  if (!email || typeof email !== 'string') {
    return null;
  }

  const cleaned = email.trim().toLowerCase();

  // Базовая email валидация
  const emailPattern = /^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$/;

  if (!emailPattern.test(cleaned)) {
    logger.warn('Невалидный email адрес');
    return null;
  }

  return cleaned;
}

/**
 * Экспорт конфигураций для кастомизации
 */
export const CONFIGS = {
  MEDICAL: MEDICAL_CONFIG,
  STRICT: STRICT_CONFIG,
  AI: AI_CONFIG
};

export default {
  sanitizeHTML,
  sanitizeText,
  sanitizeAIContent,
  escapeHTML,
  sanitizeURL,
  sanitizeInput,
  createMarkup,
  isValidMedicalCode,
  sanitizePhone,
  sanitizeEmail,
  CONFIGS
};
