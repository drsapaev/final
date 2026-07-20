/**
 * API для работы с сообщениями между пользователями
 */

import { api } from './client';

const MESSAGE_QUERY_CACHE_MS = 15_000;
const conversationCache = new Map();
const unreadCountCache = new Map();
const conversationPromiseCache = new Map();
const unreadCountPromiseCache = new Map();

function isFreshCacheEntry(entry, ttlMs = MESSAGE_QUERY_CACHE_MS) {
  return Boolean(entry) && Date.now() - entry.cachedAt < ttlMs;
}

function getCachedConversationResult(key) {
  const entry = conversationCache.get(key);
  if (isFreshCacheEntry(entry)) {
    return entry.data;
  }

  if (entry) {
    conversationCache.delete(key);
  }

  return null;
}

function getCachedUnreadCountResult(key) {
  const entry = unreadCountCache.get(key);
  if (isFreshCacheEntry(entry)) {
    return entry.data;
  }

  if (entry) {
    unreadCountCache.delete(key);
  }

  return null;
}

export function clearMessageQueryCache(): void {
  conversationCache.clear();
  unreadCountCache.clear();
  conversationPromiseCache.clear();
  unreadCountPromiseCache.clear();
}

/**
 * Отправить сообщение пользователю
 * @param {number} recipientId - ID получателя
 * @param {string} content - Текст сообщения
 * @returns {Promise<Object>} Созданное сообщение
 */
export const sendMessage = async (recipientId, content) => {
    const response = await api.post('/messages/send', {
        recipient_id: recipientId,
        content: content
    });
    clearMessageQueryCache();
    return response.data;
};

/**
 * Получить список всех бесед
 * @returns {Promise<Object>} Список бесед и общее количество непрочитанных
 */
export const getConversations = async () => {
    const cacheKey = '/messages/conversations';
    const cached = getCachedConversationResult(cacheKey);
    if (cached) {
        return cached;
    }

    const inFlight = conversationPromiseCache.get(cacheKey);
    if (inFlight) {
        return inFlight;
    }

    const requestPromise = api.get(cacheKey).then((response) => {
        conversationCache.set(cacheKey, {
            cachedAt: Date.now(),
            data: response.data
        });
        return response.data;
    }).finally(() => {
        conversationPromiseCache.delete(cacheKey);
    });

    conversationPromiseCache.set(cacheKey, requestPromise);
    return requestPromise;
};

/**
 * Получить переписку с конкретным пользователем
 * @param {number} userId - ID собеседника
 * @param {number} skip - Пропустить N сообщений (пагинация)
 * @param {number} limit - Лимит сообщений
 * @returns {Promise<Object>} Список сообщений
 */
export const getConversation = async (userId, skip = 0, limit = 50) => {
    const response = await api.get(`/messages/conversation/${userId}`, {
        params: { skip, limit }
    });
    return response.data;
};

/**
 * Получить количество непрочитанных сообщений
 * @returns {Promise<number>} Количество непрочитанных
 */
export const getUnreadCount = async () => {
    const cacheKey = '/messages/unread';
    const cached = getCachedUnreadCountResult(cacheKey);
    if (cached !== null) {
        return cached;
    }

    const inFlight = unreadCountPromiseCache.get(cacheKey);
    if (inFlight) {
        return inFlight;
    }

    const requestPromise = api.get(cacheKey).then((response) => {
        const unreadCount = response.data.unread_count;
        unreadCountCache.set(cacheKey, {
            cachedAt: Date.now(),
            data: unreadCount
        });
        return unreadCount;
    }).finally(() => {
        unreadCountPromiseCache.delete(cacheKey);
    });

    unreadCountPromiseCache.set(cacheKey, requestPromise);
    return requestPromise;
};

/**
 * Пометить сообщение как прочитанное
 * @param {number} messageId - ID сообщения
 * @returns {Promise<Object>} Обновленное сообщение
 */
export const markAsRead = async (messageId) => {
    const response = await api.patch(`/messages/${messageId}/read`);
    clearMessageQueryCache();
    return response.data;
};

/**
 * Удалить сообщение (мягкое удаление)
 * @param {number} messageId - ID сообщения
 * @returns {Promise<Object>} Результат
 */
export const deleteMessage = async (messageId) => {
    const response = await api.delete(`/messages/${messageId}`);
    clearMessageQueryCache();
    return response.data;
};

/**
 * Получить список доступных пользователей для переписки
 * @param {string} search - Поисковый запрос
 * @returns {Promise<Array>} Список пользователей
 */
export const getAvailableUsers = async (search = '') => {
    const response = await api.get('/messages/users/available', {
        params: { search }
    });
    return response.data;
};

/**
 * Добавить/удалить реакцию на сообщение
 * @param {number} messageId - ID сообщения
 * @param {string} reaction - Emoji реакции
 * @returns {Promise<Object>} Обновленное сообщение
 */
export const toggleReaction = async (messageId, reaction) => {
    const response = await api.post(`/messages/${messageId}/reactions`, {
        reaction
    });
    clearMessageQueryCache();
    return response.data;
};

/**
 * Загрузить файл для сообщения
 * @param {number} recipientId - ID получателя
 * @param {File} file - Файл
 * @returns {Promise<Object>} Созданное сообщение
 */
export const uploadFile = async (recipientId, file) => {
    const formData = new FormData();
    formData.append('recipient_id', recipientId);
    formData.append('file', file);

    const response = await api.post('/messages/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    });
    clearMessageQueryCache();
    return response.data;
};

export default {
    sendMessage,
    getConversations,
    getConversation,
    getUnreadCount,
    markAsRead,
    deleteMessage,
    getAvailableUsers,
    toggleReaction,
    uploadFile
};
