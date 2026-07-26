/**
 * Сервис печати документов
 * Централизованная работа с принтерами и документами
 */
import { api } from '../api/client';

const normalizePrintResponse = (responseData: Record<string, unknown>, fallbackErrorMessage: string) => {
  if (responseData?.success === false) {
    return {
      success: false,
      error: responseData.error || responseData.message || fallbackErrorMessage,
      data: responseData
    };
  }

  return {
    success: true,
    data: responseData
  };
};

const normalizePrintError = (error: unknown, fallbackMessage: string) => ({
  success: false,
  error: (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || fallbackMessage
});

export const printService = {
  /**
   * Получение списка принтеров
   */
  async getPrinters() {
    try {
      const response = await api.get('/print/printers');
      
      return {
        success: true,
        data: response.data.printers || []
      };
    } catch (error) {
      return normalizePrintError(error, 'Ошибка получения принтеров');
    }
  },

  /**
   * Печать талона очереди
   */
  async printTicket(ticketData: Record<string, unknown>) {
    try {
      const response = await api.post('/print/ticket', ticketData);

      return normalizePrintResponse(response.data, 'Ошибка печати талона');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка печати талона');
    }
  },

  /**
   * Печать рецепта (PDF)
   */
  async printPrescription(prescriptionData: Record<string, unknown>) {
    try {
      const response = await api.post('/print/prescription', prescriptionData);

      return normalizePrintResponse(response.data, 'Ошибка печати рецепта');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка печати рецепта');
    }
  },

  /**
   * Печать справки
   */
  async printCertificate(certificateData: Record<string, unknown>) {
    try {
      const response = await api.post('/print/certificate', certificateData);

      return normalizePrintResponse(response.data, 'Ошибка печати справки');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка печати справки');
    }
  },

  /**
   * Печать лабораторных результатов
   */
  async printLabResults(labResultsData: Record<string, unknown>) {
    try {
      const response = await api.post('/print/lab-results', labResultsData);

      return normalizePrintResponse(response.data, 'Ошибка печати лабораторных результатов');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка печати лабораторных результатов');
    }
  },

  /**
   * Печать чека
   */
  async printReceipt(receiptData: Record<string, unknown>) {
    try {
      const response = await api.post('/print/receipt', receiptData);

      return normalizePrintResponse(response.data, 'Ошибка печати чека');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка печати чека');
    }
  },

  /**
   * Быстрая печать
   */
  async quickPrint(text: string, printerName = 'default') {
    return {
      success: false,
      error:
        'Generic quickPrint is deprecated. Use printTicket, printReceipt, quickQueueTicket, or quickPaymentReceipt.'
    };
  },

  /**
   * Быстрая печать талона очереди
   */
  async quickQueueTicket(ticketData: Record<string, unknown>) {
    try {
      const response = await api.post('/print/quick/queue-ticket', ticketData);

      return normalizePrintResponse(response.data, 'Ошибка быстрой печати талона');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка быстрой печати талона');
    }
  },

  /**
   * Быстрая печать чека
   */
  async quickPaymentReceipt(receiptData: Record<string, unknown>) {
    try {
      const response = await api.post('/print/quick/payment-receipt', receiptData);

      return normalizePrintResponse(response.data, 'Ошибка быстрой печати чека');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка быстрой печати чека');
    }
  },

  /**
   * Получение шаблонов печати
   */
  async getTemplates(templateType: string, language = 'ru') {
    try {
      const response = await api.get('/print/templates/templates', {
        params: { template_type: templateType, language }
      });
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return normalizePrintError(error, 'Ошибка получения шаблонов');
    }
  },

  /**
   * Проверка статуса принтера
   */
  async checkPrinterStatus(printerName: string) {
    try {
      const response = await api.get(`/print/printers/${printerName}/status`);

      return normalizePrintResponse(response.data, 'Ошибка проверки принтера');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка проверки принтера');
    }
  },

  /**
   * Тестовая печать
   */
  async testPrint(printerName: string) {
    try {
      const response = await api.post(
        `/print/printers/${encodeURIComponent(printerName)}/test`
      );

      return normalizePrintResponse(response.data, 'Ошибка тестовой печати');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка тестовой печати');
    }
  }
};
