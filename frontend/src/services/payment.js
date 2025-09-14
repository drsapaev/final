/**
 * Сервис платежей
 * Централизованная работа с платежной системой
 */
import { api } from '../api/client';

export const paymentService = {
  /**
   * Получение доступных провайдеров
   */
  async getProviders() {
    try {
      const response = await api.get('/payments/providers');
      
      return {
        success: true,
        data: response.data.providers || []
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка получения провайдеров'
      };
    }
  },

  /**
   * Инициализация платежа
   */
  async initPayment(paymentData) {
    try {
      const response = await api.post('/payments/init', paymentData);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка инициализации платежа'
      };
    }
  },

  /**
   * Получение статуса платежа
   */
  async getPaymentStatus(paymentId) {
    try {
      const response = await api.get(`/payments/${paymentId}`);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка получения статуса платежа'
      };
    }
  },

  /**
   * Генерация квитанции
   */
  async generateReceipt(paymentId, format = 'pdf') {
    try {
      const response = await api.post(`/payments/${paymentId}/receipt`, {
        format
      });
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка генерации квитанции'
      };
    }
  },

  /**
   * Скачивание квитанции
   */
  async downloadReceipt(paymentId) {
    try {
      const response = await api.get(`/payments/${paymentId}/receipt/download`, {
        responseType: 'blob'
      });
      
      // Создаем ссылку для скачивания
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `receipt_${paymentId}.txt`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      return {
        success: true
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка скачивания квитанции'
      };
    }
  },

  /**
   * Форматирование суммы
   */
  formatAmount(amount, currency = 'UZS') {
    const numAmount = parseFloat(amount);
    
    if (currency === 'UZS') {
      return `${(numAmount / 100).toLocaleString('ru-RU')} сум`;
    } else if (currency === 'KZT') {
      return `${(numAmount / 100).toLocaleString('ru-RU')} тенге`;
    } else {
      return `${numAmount} ${currency}`;
    }
  },

  /**
   * Получение названия провайдера
   */
  getProviderName(providerCode) {
    const names = {
      click: 'Click',
      payme: 'Payme',
      kaspi: 'Kaspi Pay'
    };
    return names[providerCode] || providerCode;
  },

  /**
   * Получение статуса платежа (локализованный)
   */
  getStatusText(status) {
    const texts = {
      pending: 'Ожидает',
      processing: 'Обработка',
      completed: 'Завершен',
      failed: 'Неудачно',
      cancelled: 'Отменен',
      initialized: 'Инициализирован'
    };
    return texts[status] || status;
  }
};
