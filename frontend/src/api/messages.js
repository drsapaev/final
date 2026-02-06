/**
 * API для работы с сообщениями между пользователями
 */

import { api } from './client';

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
    return response.data;
};

/**
 * Получить список всех бесед
 * @returns {Promise<Object>} Список бесед и общее количество непрочитанных
 */
export const getConversations = async () => {
    const response = await api.get('/messages/conversations');
    return response.data;
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
    const response = await api.get('/messages/unread');
    return response.data.unread_count;
};

/**
 * Пометить сообщение как прочитанное
 * @param {number} messageId - ID сообщения
 * @returns {Promise<Object>} Обновленное сообщение
 */
export const markAsRead = async (messageId) => {
    const response = await api.patch(`/messages/${messageId}/read`);
    return response.data;
};

/**
 * Удалить сообщение (мягкое удаление)
 * @param {number} messageId - ID сообщения
 * @returns {Promise<Object>} Результат
 */
export const deleteMessage = async (messageId) => {
    const response = await api.delete(`/messages/${messageId}`);
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
