// Централизованные API endpoints
// Синхронизировано с backend API документацией

/**
 * Базовые API endpoints
 */
export const API_ENDPOINTS = {
  // Аутентификация
  AUTH: {
    LOGIN: '/auth/login',
    LOGOUT: '/auth/logout',
    ME: '/auth/me',
    REFRESH: '/auth/refresh',
    REGISTER: '/auth/register',
    FORGOT_PASSWORD: '/auth/forgot-password',
    RESET_PASSWORD: '/auth/reset-password',
    VERIFY_EMAIL: '/auth/verify-email'
  },

  // Пользователи
  USERS: {
    LIST: '/users',
    CREATE: '/users',
    ROLES: '/users/roles',
    PERMISSIONS: '/users/permissions'
  },

  // Пациенты
  PATIENTS: {
    LIST: '/patients',
    CREATE: '/patients',
    SEARCH: '/patients/',
    STATS: '/patients/stats'
  },

  // Врачи
  DOCTORS: {
    LIST: '/doctors',
    CREATE: '/doctors',
    SPECIALIZATIONS: '/doctors/specializations',
    DEPARTMENTS: '/doctors/departments'
  },

  // Записи на прием
  APPOINTMENTS: {
    LIST: '/appointments',
    CREATE: '/appointments',
    STATS: '/appointments/stats',
    BY_DATE: '/appointments/by-date'
  },

  // Очередь (обновлено)
  QUEUE: {
    LIST: '/queue',
    CREATE: '/queue',
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
    BY_DEPARTMENT: '/services/by-department',
    PRICING: '/services/pricing'
  },

  // Отчеты
  REPORTS: {
    LIST: '/reports',
    CREATE: '/reports',
    GENERATE: '/reports/generate',
    TYPES: '/reports/types'
  },

  // Настройки
  SETTINGS: {
    LIST: '/settings',
    BULK_UPDATE: '/settings/bulk-update',
    CATEGORIES: '/settings/categories'
  },

  // Уведомления
  NOTIFICATIONS: {
    LIST: '/notifications',
    MARK_ALL_READ: '/notifications/mark-all-read',
    SEND: '/notifications/send',
    TYPES: '/notifications/types'
  },

  // Файлы
  FILES: {
    UPLOAD: '/files/upload',
    LIST: '/files'
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
    TEMPLATES: '/print/templates',
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
  getUser: (id) => `/users/${id}`,
  updateUser: (id) => `/users/${id}`,
  deleteUser: (id) => `/users/${id}`,

  // Пациенты
  getPatient: (id) => `/patients/${id}`,
  updatePatient: (id) => `/patients/${id}`,
  deletePatient: (id) => `/patients/${id}`,

  // Врачи
  getDoctor: (id) => `/doctors/${id}`,
  updateDoctor: (id) => `/doctors/${id}`,
  deleteDoctor: (id) => `/doctors/${id}`,
  getDoctorSchedule: (id) => `/doctors/${id}/schedule`,
  getDoctorAvailability: (id) => `/doctors/${id}/availability`,

  // Записи на прием
  getAppointment: (id) => `/appointments/${id}`,
  updateAppointment: (id) => `/appointments/${id}`,
  deleteAppointment: (id) => `/appointments/${id}`,
  getPatientAppointments: (patientId) => `/appointments/patient/${patientId}`,
  getDoctorAppointments: (doctorId) => `/appointments/doctor/${doctorId}`,
  cancelAppointment: (id) => `/appointments/${id}/cancel`,
  confirmAppointment: (id) => `/appointments/${id}/confirm`,

  // Очередь
  getQueueItem: (id) => `/queue/${id}`,
  updateQueueItem: (id) => `/queue/${id}`,
  deleteQueueItem: (id) => `/queue/${id}`,
  skipQueueItem: (id) => `/queue/${id}/skip`,
  completeQueueItem: (id) => `/queue/${id}/complete`,

  // Услуги
  getService: (id) => `/services/${id}`,
  updateService: (id) => `/services/${id}`,
  deleteService: (id) => `/services/${id}`,

  // Отчеты
  getReport: (id) => `/reports/${id}`,
  deleteReport: (id) => `/reports/${id}`,
  exportReport: (id) => `/reports/${id}/export`,

  // Настройки
  getSetting: (key) => `/settings/${key}`,
  updateSetting: (key) => `/settings/${key}`,

  // Уведомления
  getNotification: (id) => `/notifications/${id}`,
  markNotificationRead: (id) => `/notifications/${id}/read`,

  // Файлы
  getFile: (id) => `/files/${id}`,
  deleteFile: (id) => `/files/${id}`,
  downloadFile: (id) => `/files/${id}/download`,

  // Аудит
  getAuditLog: (id) => `/audit/logs/${id}`
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
export function buildUrl(endpoint, params = {}) {
  const url = new URL(endpoint, window.location.origin);
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      url.searchParams.append(key, value);
    }
  });
  
  return url.pathname + url.search;
}

/**
 * Создание query string
 */
export function buildQueryString(params = {}) {
  const searchParams = new URLSearchParams();
  
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      searchParams.append(key, value);
    }
  });
  
  return searchParams.toString();
}

/**
 * Валидация endpoint
 */
export function validateEndpoint(endpoint) {
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
export function getEndpoint(category, key, ...args) {
  const categoryEndpoints = API_ENDPOINTS[category];
  if (!categoryEndpoints) {
    throw new Error(`Unknown API category: ${category}`);
  }
  
  const endpoint = categoryEndpoints[key];
  if (!endpoint) {
    throw new Error(`Unknown endpoint: ${category}.${key}`);
  }
  
  return endpoint;
}
