// Централизованные API endpoints
// Синхронизировано с backend API документацией
//
// Phase 1 — migrated from .js. Object structure preserved (Type Migration ≉ Refactoring).
// Function-valued entries typed; leaves kept as plain strings.

/**
 * Базовые API endpoints
 */
export const API_ENDPOINTS = {
  // Аутентификация
  AUTH: {
    LOGIN: '/authentication/login',
    LOGOUT: '/authentication/logout',
    ME: '/auth/me',
    REFRESH: '/authentication/refresh',
    REGISTER: '/auth/register',
    FORGOT_PASSWORD: '/auth/forgot-password',
    RESET_PASSWORD: '/auth/reset-password',
    VERIFY_EMAIL: '/auth/verify-email'
  },

  // Пользователи
  USERS: {
    LIST: '/users',
    CREATE: '/users',
    GET: (id: string | number) => `/users/${id}`,
    UPDATE: (id: string | number) => `/users/${id}`,
    DELETE: (id: string | number) => `/users/${id}`,
    ROLES: '/users/roles',
    PERMISSIONS: '/users/permissions'
  },

  // Пациенты
  PATIENTS: {
    LIST: '/patients',
    CREATE: '/patients',
    GET: (id: string | number) => `/patients/${id}`,
    UPDATE: (id: string | number) => `/patients/${id}`,
    DELETE: (id: string | number) => `/patients/${id}`,
    SEARCH: '/patients/',
    STATS: '/patients/stats'
  },

  // Врачи
  DOCTORS: {
    LIST: '/doctors',
    CREATE: '/doctors',
    GET: (id: string | number) => `/doctors/${id}`,
    UPDATE: (id: string | number) => `/doctors/${id}`,
    DELETE: (id: string | number) => `/doctors/${id}`,
    SCHEDULE: (id: string | number) => `/doctors/${id}/schedule`,
    AVAILABILITY: (id: string | number) => `/doctors/${id}/availability`,
    SPECIALIZATIONS: '/doctors/specializations',
    DEPARTMENTS: '/doctors/departments'
  },

  // Записи на прием
  APPOINTMENTS: {
    LIST: '/appointments',
    CREATE: '/appointments',
    GET: (id: string | number) => `/appointments/${id}`,
    UPDATE: (id: string | number) => `/appointments/${id}`,
    DELETE: (id: string | number) => `/appointments/${id}`,
    BY_PATIENT: (patientId: string | number) => `/appointments/patient/${patientId}`,
    BY_DOCTOR: (doctorId: string | number) => `/appointments/doctor/${doctorId}`,
    CANCEL: (id: string | number) => `/appointments/${id}/cancel`,
    CONFIRM: (id: string | number) => `/appointments/${id}/confirm`,
    STATS: '/appointments/stats',
    BY_DATE: '/appointments/by-date'
  },

  // Очередь (обновлено)
  QUEUE: {
    LIST: '/queue',
    CREATE: '/queue',
    GET: (id: string | number) => `/queue/${id}`,
    UPDATE: (id: string | number) => `/queue/${id}`,
    DELETE: (id: string | number) => `/queue/${id}`,
    SKIP: (id: string | number) => `/queue/${id}/skip`,
    COMPLETE: (id: string | number) => `/queue/${id}/complete`,
    STATS: '/queue/stats',
    BY_DEPARTMENT: '/queue/by-department',
    CALL_NEXT: '/queue/call-next',
    // Новые endpoints онлайн-очереди
    GENERATE_QR: '/queue/qrcode',
    JOIN: '/queue/join',
    OPEN: '/queue/open',
    TODAY: '/queue/today',
    CALL_PATIENT: '/queue/call',
    STATISTICS: '/queue/statistics'
  },

  // Услуги
  SERVICES: {
    LIST: '/services',
    CREATE: '/services',
    GET: (id: string | number) => `/services/${id}`,
    UPDATE: (id: string | number) => `/services/${id}`,
    DELETE: (id: string | number) => `/services/${id}`,
    BY_DEPARTMENT: '/services/by-department',
    PRICING: '/services/pricing'
  },

  // Отчеты
  REPORTS: {
    LIST: '/reports',
    CREATE: '/reports',
    GET: (id: string | number) => `/reports/${id}`,
    DELETE: (id: string | number) => `/reports/${id}`,
    EXPORT_BY_ID: (id: string | number) => `/reports/${id}/export`,
    GENERATE: '/reports/generate',
    TYPES: '/reports/types'
  },

  // Настройки
  SETTINGS: {
    LIST: '/settings',
    GET: (key: string) => `/settings/${key}`,
    UPDATE: (key: string) => `/settings/${key}`,
    BULK_UPDATE: '/settings/bulk-update',
    CATEGORIES: '/settings/categories'
  },

  // Уведомления
  NOTIFICATIONS: {
    INBOX: '/notifications/inbox',
    HISTORY: '/notifications/history',
    SYNC: '/notifications/sync',
    UNREAD_COUNT: '/notifications/unread-count',
    SETTINGS: (userId: string | number) => `/notifications/settings/${userId}`,
    SETTINGS_POLICY: (userId: string | number) => `/notifications/settings/${userId}/policy`,
    MARK_SEEN: (id: string | number) => `/notifications/${id}/seen`,
    MARK_READ: (id: string | number) => `/notifications/${id}/read`,
    ARCHIVE: (id: string | number) => `/notifications/${id}/archive`,
    MARK_ALL_READ: '/notifications/mark-all-read',
    HISTORY_STATS: '/notifications/history/stats',
    SEND: '/notifications/send'
  },

  // Файлы
  FILES: {
    UPLOAD: '/files/upload',
    LIST: '/files',
    GET: (id: string | number) => `/files/${id}`,
    DELETE: (id: string | number) => `/files/${id}`,
    DOWNLOAD: (id: string | number) => `/files/${id}/download`
  },

  // Платежи (новое)
  PAYMENTS: {
    PROVIDERS: '/payments/providers',
    INIT: '/payments/init',
    STATUS: '/payments',
    RECEIPT: '/payments/receipt',
    DOWNLOAD_RECEIPT: '/payments/receipt/download'
  },

  // Печать (новое)
  PRINT: {
    PRINTERS: '/print/printers',
    TEMPLATES: '/print/templates/templates',
    TICKET: '/print/ticket',
    PRESCRIPTION: '/print/prescription',
    CERTIFICATE: '/print/certificate',
    QUICK: '/print/quick',
    TEST: '/print/test'
  },

  // WebSocket endpoints объединены ниже

  // Аудит
  AUDIT: {
    LOGS: '/audit/logs',
    EXPORT: '/audit/logs/export',
    STATS: '/audit/logs/stats'
  },

  // Аналитика
  ANALYTICS: {
    DASHBOARD: '/analytics/dashboard',
    REVENUE: '/analytics/revenue',
    PATIENTS: '/analytics/patients',
    APPOINTMENTS: '/analytics/appointments',
    DOCTORS: '/analytics/doctors',
    DEPARTMENTS: '/analytics/departments',
    EXPORT: '/analytics/export'
  },

  // Здоровье системы
  HEALTH: {
    CHECK: '/health',
    STATUS: '/status',
    METRICS: '/metrics'
  },

  // WebSocket
  WEBSOCKET: {
    CONNECT: '/ws',
    QUEUE_UPDATES: '/ws/queue',
    NOTIFICATIONS: '/ws/notifications',
    APPOINTMENTS: '/ws/appointments'
  }
};

/**
 * Функции для создания динамических endpoints
 */
export const createEndpoints = {
  // Пользователи
  getUser: (id: string | number) => `/users/${id}`,
  updateUser: (id: string | number) => `/users/${id}`,
  deleteUser: (id: string | number) => `/users/${id}`,

  // Пациенты
  getPatient: (id: string | number) => `/patients/${id}`,
  updatePatient: (id: string | number) => `/patients/${id}`,
  deletePatient: (id: string | number) => `/patients/${id}`,

  // Врачи
  getDoctor: (id: string | number) => `/doctors/${id}`,
  updateDoctor: (id: string | number) => `/doctors/${id}`,
  deleteDoctor: (id: string | number) => `/doctors/${id}`,
  getDoctorSchedule: (id: string | number) => `/doctors/${id}/schedule`,
  getDoctorAvailability: (id: string | number) => `/doctors/${id}/availability`,

  // Записи на прием
  getAppointment: (id: string | number) => `/appointments/${id}`,
  updateAppointment: (id: string | number) => `/appointments/${id}`,
  deleteAppointment: (id: string | number) => `/appointments/${id}`,
  getPatientAppointments: (patientId: string | number) => `/appointments/patient/${patientId}`,
  getDoctorAppointments: (doctorId: string | number) => `/appointments/doctor/${doctorId}`,
  cancelAppointment: (id: string | number) => `/appointments/${id}/cancel`,
  confirmAppointment: (id: string | number) => `/appointments/${id}/confirm`,

  // Очередь
  getQueueItem: (id: string | number) => `/queue/${id}`,
  updateQueueItem: (id: string | number) => `/queue/${id}`,
  deleteQueueItem: (id: string | number) => `/queue/${id}`,
  skipQueueItem: (id: string | number) => `/queue/${id}/skip`,
  completeQueueItem: (id: string | number) => `/queue/${id}/complete`,

  // Услуги
  getService: (id: string | number) => `/services/${id}`,
  updateService: (id: string | number) => `/services/${id}`,
  deleteService: (id: string | number) => `/services/${id}`,

  // Отчеты
  getReport: (id: string | number) => `/reports/${id}`,
  deleteReport: (id: string | number) => `/reports/${id}`,
  exportReport: (id: string | number) => `/reports/${id}/export`,

  // Настройки
  getSetting: (key: string) => `/settings/${key}`,
  updateSetting: (key: string) => `/settings/${key}`,

  // Уведомления
  getNotificationInbox: () => '/notifications/inbox',
  getNotificationHistory: () => '/notifications/history',

  // Файлы
  getFile: (id: string | number) => `/files/${id}`,
  deleteFile: (id: string | number) => `/files/${id}`,
  downloadFile: (id: string | number) => `/files/${id}/download`,

  // Аудит
  getAuditLog: (id: string | number) => `/audit/logs/${id}`
};

/**
 * Параметры запросов
 */
export const QUERY_PARAMS = {
  // Пагинация
  PAGE: 'page',
  PER_PAGE: 'per_page',
  LIMIT: 'limit',
  OFFSET: 'offset',
  
  // Сортировка
  SORT_BY: 'sort_by',
  SORT_ORDER: 'sort_order',
  ORDER_BY: 'order_by',
  
  // Фильтрация
  SEARCH: 'search',
  FILTER: 'filter',
  STATUS: 'status',
  ROLE: 'role',
  DEPARTMENT: 'department',
  DATE_FROM: 'date_from',
  DATE_TO: 'date_to',
  
  // Специфичные
  PATIENT_ID: 'patient_id',
  DOCTOR_ID: 'doctor_id',
  APPOINTMENT_ID: 'appointment_id',
  QUEUE_ID: 'queue_id'
};

/**
 * HTTP методы
 */
export const HTTP_METHODS = {
  GET: 'GET',
  POST: 'POST',
  PUT: 'PUT',
  PATCH: 'PATCH',
  DELETE: 'DELETE',
  HEAD: 'HEAD',
  OPTIONS: 'OPTIONS'
};

/**
 * Content-Type заголовки
 */
export const CONTENT_TYPES = {
  JSON: 'application/json',
  FORM_URLENCODED: 'application/x-www-form-urlencoded',
  MULTIPART: 'multipart/form-data',
  TEXT: 'text/plain',
  HTML: 'text/html'
};

/**
 * Создание URL с параметрами
 */
export function buildUrl(endpoint: string, params: Record<string, unknown> = {}): string {
  const url = new URL(endpoint, window.location.origin);
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      url.searchParams.append(key, String(value));
    }
  });
  
  return url.pathname + url.search;
}

/**
 * Создание query string
 */
export function buildQueryString(params: Record<string, unknown> = {}): string {
  const searchParams = new URLSearchParams();
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      searchParams.append(key, String(value));
    }
  });
  
  return searchParams.toString();
}

/**
 * Валидация endpoint
 */
export function validateEndpoint(endpoint: unknown): endpoint is string {
  if (typeof endpoint !== 'string') {
    throw new Error('Endpoint must be a string');
  }
  
  if (!endpoint.startsWith('/')) {
    throw new Error('Endpoint must start with /');
  }
  
  return true;
}

/**
 * Получение endpoint по ключу
 */
export function getEndpoint(category: string, key: string): string | ((...args: unknown[]) => string) {
  const categoryEndpoints = (API_ENDPOINTS as Record<string, Record<string, unknown>>)[category];
  if (!categoryEndpoints) {
    throw new Error(`Unknown API category: ${category}`);
  }
  
  const endpoint = categoryEndpoints[key];
  if (!endpoint) {
    throw new Error(`Unknown endpoint: ${category}.${key}`);
  }
  
  return endpoint as string | ((...args: unknown[]) => string);
}
