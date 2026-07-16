// Централизованные API сервисы
// Использует client.js и endpoints.js для единообразной работы с API
//
// P2 ARCHITECTURE AUDIT (2026-07-14):
// Removed 10 dead service objects that had 0 importers outside this file:
// authService, usersService, patientsService, doctorsService, appointmentsService,
// queueService (the real one is services/queue.js), analyticsService, settingsService,
// filesService, healthService. These were generating 45 frontend-orphan parity
// violations against backend routes that don't exist. The live code uses
// dedicated hooks (useUsers, useDoctors, useAppointments, useFinance, etc.)
// and dedicated API modules (api/queue.js, api/registrar.js, api/payments.js,
// services/queue.js, services/print.js, services/payment.js) instead.
//
// Kept: servicesService (partially live — only getCodeMappings and
// getServiceHistory are used) and notificationsService (fully live). Trimmed
// 2 orphan methods from servicesService: getServicesByDepartment (no backend
// /services/by-department route) and getPricing (no backend /services/pricing
// route).

import { apiRequest } from './client.js';
import { API_ENDPOINTS, buildQueryString } from './endpoints.js';
import logger from '../utils/logger';

const NOTIFICATION_QUERY_CACHE_MS = 15_000;
const notificationQueryResultCache = new Map();
const notificationQueryPromiseCache = new Map();

function buildNotificationQueryKey(endpoint, params = {}) {
  const queryString = buildQueryString(params);
  return queryString ? `${endpoint}?${queryString}` : endpoint;
}

function getNotificationQueryCacheEntry(key) {
  const entry = notificationQueryResultCache.get(key);
  if (!entry) {
    return null;
  }

  if (Date.now() - entry.cachedAt > NOTIFICATION_QUERY_CACHE_MS) {
    notificationQueryResultCache.delete(key);
    return null;
  }

  logger.info('[FIX:NOTIFICATIONS] cache hit for notification query', { key });
  return entry.data;
}

function setNotificationQueryCacheEntry(key, data) {
  notificationQueryResultCache.set(key, {
    cachedAt: Date.now(),
    data
  });
}

export function clearNotificationQueryCache() {
  notificationQueryResultCache.clear();
  notificationQueryPromiseCache.clear();
  logger.info('[FIX:NOTIFICATIONS] notification query cache cleared');
}

async function fetchNotificationQuery(endpoint, params = {}) {
  const cacheKey = buildNotificationQueryKey(endpoint, params);

  const cached = getNotificationQueryCacheEntry(cacheKey);
  if (cached) {
    return cached;
  }

  const inFlight = notificationQueryPromiseCache.get(cacheKey);
  if (inFlight) {
    logger.info('[FIX:NOTIFICATIONS] reusing in-flight notification query', { key: cacheKey });
    return inFlight;
  }

  const requestPromise = apiRequest('GET', cacheKey)
    .then((data) => {
      setNotificationQueryCacheEntry(cacheKey, data);
      return data;
    })
    .finally(() => {
      notificationQueryPromiseCache.delete(cacheKey);
    });

  notificationQueryPromiseCache.set(cacheKey, requestPromise);
  return requestPromise;
}

/**
 * Сервис услуг
 *
 * P2 ARCHITECTURE AUDIT: trimmed 2 orphan methods (getServicesByDepartment,
 * getPricing) whose target backend routes don't exist. Kept the 2 live
 * methods: getCodeMappings (used by serviceCodeResolver.js) and
 * getServiceHistory (used by ServiceAuditHistory.jsx).
 */
export const servicesService = {
  /**
   * ⭐ SSOT: Получение маппингов кодов услуг
   * Используется для синхронизации frontend с backend SSOT
   */
  async getCodeMappings() {
    return apiRequest('GET', '/services/code-mappings');
  },

  /**
   * Получение истории изменений услуги
   */
  async getServiceHistory(serviceId, params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `/services/${serviceId}/history?${queryString}`);
  },

  /**
   * Получение последних изменений всех услуг
   */
  async getRecentServiceChanges(params = {}) {
    const queryString = buildQueryString(params);
    return apiRequest('GET', `/services/admin/audit/recent?${queryString}`);
  }
};

/**
 * Сервис уведомлений
 */
function appendQuery(endpoint, params = {}) {
  const queryString = buildQueryString(params);
  return queryString ? `${endpoint}?${queryString}` : endpoint;
}

export const notificationsService = {
  /**
   * Persistent inbox
   */
  async getInbox(params = {}) {
    return fetchNotificationQuery(API_ENDPOINTS.NOTIFICATIONS.INBOX, params);
  },

  /**
   * Cursor-based inbox sync
   */
  async getSync(params = {}) {
    return fetchNotificationQuery(API_ENDPOINTS.NOTIFICATIONS.SYNC, params);
  },

  /**
   * Legacy compatibility alias
   */
  async getHistory(params = {}) {
    return fetchNotificationQuery(API_ENDPOINTS.NOTIFICATIONS.INBOX, params);
  },

  /**
   * Backward compatibility for older callers
   */
  async getNotifications(params = {}) {
    return fetchNotificationQuery(API_ENDPOINTS.NOTIFICATIONS.INBOX, params);
  },

  /**
   * Server-authoritative unread counts
   */
  async getUnreadCount(params = {}) {
    return fetchNotificationQuery(API_ENDPOINTS.NOTIFICATIONS.UNREAD_COUNT, params);
  },

  /**
   * Notification channel settings for a user
   */
  async getSettings(userId) {
    return apiRequest('GET', API_ENDPOINTS.NOTIFICATIONS.SETTINGS(userId));
  },

  /**
   * Update notification channel settings for a user
   */
  async updateSettings(userId, settingsPayload) {
    const response = await apiRequest(
      'PUT',
      API_ENDPOINTS.NOTIFICATIONS.SETTINGS(userId),
      { data: settingsPayload }
    );
    clearNotificationQueryCache();
    return response;
  },

  /**
   * Runtime anti-noise policy for a user
   */
  async getPolicy(userId) {
    return apiRequest('GET', API_ENDPOINTS.NOTIFICATIONS.SETTINGS_POLICY(userId));
  },

  /**
   * Update runtime anti-noise policy for a user
   */
  async updatePolicy(userId, policyPayload) {
    const response = await apiRequest(
      'PUT',
      API_ENDPOINTS.NOTIFICATIONS.SETTINGS_POLICY(userId),
      { data: policyPayload }
    );
    clearNotificationQueryCache();
    return response;
  },

  /**
   * Mark a notification as seen
   */
  async markSeen(id) {
  const response = await apiRequest('POST', API_ENDPOINTS.NOTIFICATIONS.MARK_SEEN(id));
  clearNotificationQueryCache();
  return response;
  },

  /**
   * Mark a notification as read
   */
  async markAsRead(id) {
  const response = await apiRequest('POST', API_ENDPOINTS.NOTIFICATIONS.MARK_READ(id));
  clearNotificationQueryCache();
  return response;
  },

  /**
   * Archive a notification
   */
  async archiveNotification(id) {
  const response = await apiRequest('POST', API_ENDPOINTS.NOTIFICATIONS.ARCHIVE(id));
  clearNotificationQueryCache();
  return response;
  },

  /**
   * Mark all notifications as read
   */
  async markAllAsRead(params = {}) {
  const response = await apiRequest('POST', appendQuery(API_ENDPOINTS.NOTIFICATIONS.MARK_ALL_READ, params));
  clearNotificationQueryCache();
  return response;
  },

  /**
   * Notification stats for admin dashboards
   */
  async getStats(days = 7) {
    return apiRequest(
      'GET',
      appendQuery(API_ENDPOINTS.NOTIFICATIONS.HISTORY_STATS, { days })
    );
  },

  /**
   * Отправка уведомления
   */
  async sendNotification(notificationData) {
  const response = await apiRequest('POST', API_ENDPOINTS.NOTIFICATIONS.SEND, {
      data: notificationData
    });
    clearNotificationQueryCache();
    return response;
  },

  /**
   * Method intentionally unsupported by the canonical contract
   */
  async getNotification() {
    throw new Error('[FIX:NOTIFICATIONS] get by id is not supported by /notifications contract');
  },

  /**
   * Method intentionally unsupported by the canonical contract
   */
  async getNotificationTypes() {
    throw new Error('[FIX:NOTIFICATIONS] notification types are not supported by /notifications contract');
  }
};
