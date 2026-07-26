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
        error: (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Ошибка получения провайдеров'
      };
    }
  },

  /**
   * Инициализация платежа
   */
  async initPayment(paymentData: Record<string, unknown>) {
    try {
      const response = await api.post('/payments/init', paymentData);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Ошибка инициализации платежа'
      };
    }
  },

  /**
   * Получение статуса платежа
   */
  async getPaymentStatus(paymentId: string | number) {
    try {
      const response = await api.get(`/payments/${paymentId}`);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Ошибка получения статуса платежа'
      };
    }
  },

  /**
   * Генерация квитанции
   */
  async generateReceipt(paymentId: string | number, format = 'pdf') {
    try {
      const response = await api.get(`/payments/${paymentId}/receipt`, {
        params: { format_type: format }
      });

      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Ошибка генерации квитанции'
      };
    }
  },

  /**
   * Скачивание квитанции
   */
    async downloadReceipt(paymentId: string | number) {
    try {
      const response = await api.get(`/payments/${paymentId}/receipt/download`, {
        responseType: 'blob'
      });
      
      // Создаем ссылку для скачивания
      const blob = response.data instanceof Blob
        ? response.data
        : new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `receipt_${paymentId}.pdf`);
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
        error: (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Ошибка скачивания квитанции'
      };
    }
  },

  /**
   * Форматирование суммы
   *
   * PAY-REAUDIT-28 P1-9: убрано деление на 100. Backend хранит amount в
   * основной валюте (som/tenge), не в тийинах/копейках. Раньше все суммы
   * отображались в 100 раз меньше реальной (15000 UZS → "150 сум").
   */
  formatAmount(amount: number | string, currency = 'UZS') {
    const numAmount = parseFloat(String(amount)) || 0;

    if (currency === 'UZS') {
      return `${numAmount.toLocaleString('ru-RU')} сум`;
    } else if (currency === 'KZT') {
      return `${numAmount.toLocaleString('ru-RU')} тенге`;
    } else {
      return `${numAmount} ${currency}`;
    }
  },

  /**
   * Получение названия провайдера
   */
  getProviderName(providerCode: string): string {
    const names: Record<string, string> = {
      click: 'Click',
      payme: 'Payme',
      kaspi: 'Kaspi Pay'
    };
    return names[providerCode] || providerCode;
  },

  /**
   * Получение статуса платежа (локализованный)
   */
  getStatusText(status: string): string {
    // PAY-REAUDIT-28 P1-10: добавлены отсутствовавшие статусы `paid`,
    // `refunded`, `void`, `canceled`. Backend использует `paid` как
    // основной статус успеха (PaymentStatus.PAID.value), но фронтенд
    // показывал сырую английскую строку "paid".
    const texts: Record<string, string> = {
      pending: 'Ожидает',
      processing: 'Обработка',
      paid: 'Оплачено',
      completed: 'Завершён',
      failed: 'Неудачно',
      cancelled: 'Отменён',
      canceled: 'Отменён',
      refunded: 'Возвращён',
      void: 'Аннулирован',
      initialized: 'Инициализирован'
    };
    return texts[status] || status;
  }
};
