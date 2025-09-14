/**
 * Сервис управления очередью
 * Централизованная работа с онлайн-очередью
 */
import { api } from '../api/client';

export const queueService = {
  /**
   * Генерация QR кода для очереди
   */
  async generateQRCode(specialistId, day) {
    try {
      const response = await api.post('/queue/qrcode', null, {
        params: { specialist_id: specialistId, day }
      });
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка генерации QR кода'
      };
    }
  },

  /**
   * Запись в очередь
   */
  async joinQueue(queueData) {
    try {
      const response = await api.post('/queue/join', queueData);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка записи в очередь'
      };
    }
  },

  /**
   * Открытие приема
   */
  async openQueue(specialistId, day) {
    try {
      const response = await api.post('/queue/open', null, {
        params: { specialist_id: specialistId, day }
      });
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка открытия приема'
      };
    }
  },

  /**
   * Получение очереди на сегодня
   */
  async getTodayQueue(specialistId) {
    try {
      const response = await api.get('/queue/today', {
        params: { specialist_id: specialistId }
      });
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка получения очереди'
      };
    }
  },

  /**
   * Вызов пациента
   */
  async callPatient(entryId) {
    try {
      const response = await api.post(`/queue/call/${entryId}`);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка вызова пациента'
      };
    }
  },

  /**
   * Получение статистики очереди
   */
  async getStatistics(specialistId, day) {
    try {
      const response = await api.get(`/queue/statistics/${specialistId}`, {
        params: { day }
      });
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка получения статистики'
      };
    }
  }
};
