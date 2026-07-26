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
