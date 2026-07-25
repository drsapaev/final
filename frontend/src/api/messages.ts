/**
 * API для работы с сообщениями между пользователями
 *
 * Wave 4: all functions return domain Chat* types from types/domain/chat.ts.
 * The raw backend JSON is mapped at the boundary by mappers/chat.ts so
 * ChatContext and other consumers never see `Record<string, unknown>`.
 */

import { api } from './client';
import type {
  ChatMessage,
  ChatConversation,
  ChatAvailableUser,
  ChatConversationsResponse,
  ChatConversationResponse,
  ChatUnreadCountResponse,
  ChatAvailableUsersResponse,
} from '../types/domain/chat';
import {
  mapChatMessageDto,
  mapChatConversationDto,
  mapConversationsResponseDto,
  mapConversationResponseDto,
  mapUnreadCountResponseDto,
  mapAvailableUsersResponseDto,
  mapChatAvailableUserDtos,
} from './mappers';

const MESSAGE_QUERY_CACHE_MS = 15_000;
const conversationCache = new Map<string, { cachedAt: number; data: ChatConversationsResponse }>();
const unreadCountCache = new Map<string, { cachedAt: number; data: number }>();
const conversationPromiseCache = new Map<string, Promise<ChatConversationsResponse>>();
const unreadCountPromiseCache = new Map<string, Promise<number>>();

function isFreshCacheEntry(entry: { cachedAt: number } | undefined, ttlMs = MESSAGE_QUERY_CACHE_MS): boolean {
  return Boolean(entry) && Date.now() - entry!.cachedAt < ttlMs;
}

function getCachedConversationResult(key: string): ChatConversationsResponse | null {
  const entry = conversationCache.get(key);
  if (isFreshCacheEntry(entry)) {
    return entry!.data;
  }

  if (entry) {
    conversationCache.delete(key);
  }

  return null;
}

function getCachedUnreadCountResult(key: string): number | null {
  const entry = unreadCountCache.get(key);
  if (isFreshCacheEntry(entry)) {
    return entry!.data;
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
 * @returns {Promise<ChatMessage>} Созданное сообщение (домен)
 */
export const sendMessage = async (recipientId: number, content: string): Promise<ChatMessage> => {
    const response = await api.post('/messages/send', {
        recipient_id: recipientId,
        content: content
    });
    clearMessageQueryCache();
    return mapChatMessageDto(response.data as Record<string, unknown>);
};

/**
 * Получить список всех бесед
 * @returns {Promise<ChatConversationsResponse>} Список бесед и общее количество непрочитанных
 */
export const getConversations = async (): Promise<ChatConversationsResponse> => {
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
        const mapped = mapConversationsResponseDto(response.data as Record<string, unknown>);
        conversationCache.set(cacheKey, {
            cachedAt: Date.now(),
            data: mapped
        });
        return mapped;
    }).finally(() => {
        conversationPromiseCache.delete(cacheKey);
    });

    conversationPromiseCache.set(cacheKey, requestPromise);
    return requestPromise;
};

/**
 * Получить переписку с конкретным пользователем
 * @param userId - ID собеседника
 * @param skip - Пропустить N сообщений (пагинация)
 * @param limit - Лимит сообщений
 * @returns {Promise<ChatConversationResponse>} Список сообщений (домен)
 */
export const getConversation = async (userId: number, skip = 0, limit = 50): Promise<ChatConversationResponse> => {
    const response = await api.get(`/messages/conversation/${userId}`, {
        params: { skip, limit }
    });
    return mapConversationResponseDto(response.data as Record<string, unknown>);
};

/**
 * Получить количество непрочитанных сообщений
 * @returns {Promise<number>} Количество непрочитанных
 */
export const getUnreadCount = async (): Promise<number> => {
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
        const unreadCount = Number((response.data as { unread_count?: unknown }).unread_count) || 0;
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
 * @returns {Promise<ChatMessage>} Обновленное сообщение (домен)
 */
export const markAsRead = async (messageId: number): Promise<ChatMessage> => {
    const response = await api.patch(`/messages/${messageId}/read`);
    clearMessageQueryCache();
    return mapChatMessageDto(response.data as Record<string, unknown>);
};

/**
 * Удалить сообщение (мягкое удаление)
 *
 * @api-transport backend returns a free-form status dict ({ success, deleted_at });
 *               no dedicated domain type yet.
 *
 * @returns {Promise<Record<string, unknown>>} Результат
 */
export const deleteMessage = async (messageId: number): Promise<Record<string, unknown>> => {
    const response = await api.delete(`/messages/${messageId}`);
    clearMessageQueryCache();
    return response.data as Record<string, unknown>;
};

/**
 * Получить список доступных пользователей для переписки
 * @returns {Promise<ChatAvailableUser[]>} Список пользователей (домен)
 */
export const getAvailableUsers = async (search = ''): Promise<ChatAvailableUser[] | ChatAvailableUsersResponse> => {
    const response = await api.get('/messages/users/available', {
        params: { search }
    });
    // Backend may return either an array directly or { users: [...] }
    const data = response.data;
    if (Array.isArray(data)) {
        return mapChatAvailableUserDtos(data);
    }
    return mapAvailableUsersResponseDto(data as Record<string, unknown>);
};

/**
 * Добавить/удалить реакцию на сообщение
 * @returns {Promise<ChatMessage>} Обновленное сообщение (домен)
 */
export const toggleReaction = async (messageId: number, reaction: string): Promise<ChatMessage> => {
    const response = await api.post(`/messages/${messageId}/reactions`, {
        reaction
    });
    clearMessageQueryCache();
    return mapChatMessageDto(response.data as Record<string, unknown>);
};

/**
 * Загрузить файл для сообщения
 * @returns {Promise<ChatMessage>} Созданное сообщение (домен)
 */
export const uploadFile = async (recipientId: number, file: File): Promise<ChatMessage> => {
    const formData = new FormData();
    formData.append('recipient_id', String(recipientId));
    formData.append('file', file);

    const response = await api.post('/messages/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    });
    clearMessageQueryCache();
    return mapChatMessageDto(response.data as Record<string, unknown>);
};

// Re-export domain types for backwards compatibility with callers that
// imported them from '@/api/messages' in earlier phases.
export type {
  ChatMessage,
  ChatConversation,
  ChatAvailableUser,
  ChatConversationsResponse,
  ChatConversationResponse,
  ChatUnreadCountResponse,
  ChatAvailableUsersResponse,
};

// Legacy default export keeps the same shape: an object with all functions.
const messagesApi = {
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

export default messagesApi;
