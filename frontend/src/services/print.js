/**
 * Сервис печати документов
 * Централизованная работа с принтерами и документами
 */
import { api } from '../api/client';

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
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка получения принтеров'
      };
    }
  },

  /**
   * Печать талона очереди
   */
  async printTicket(ticketData) {
    try {
      const response = await api.post('/print/ticket', ticketData);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка печати талона'
      };
    }
  },

  /**
   * Печать рецепта (PDF)
   */
  async printPrescription(prescriptionData) {
    try {
      const response = await api.post('/print/prescription', prescriptionData);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка печати рецепта'
      };
    }
  },

  /**
   * Печать справки
   */
  async printCertificate(certificateData) {
    try {
      const response = await api.post('/print/certificate', certificateData);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка печати справки'
      };
    }
  },

  /**
   * Быстрая печать текста
   */
  async quickPrint(text, printerName = 'default') {
    try {
      const response = await api.post('/print/quick', {
        text,
        printer_name: printerName
      });
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка быстрой печати'
      };
    }
  },

  /**
   * Получение шаблонов печати
   */
  async getTemplates(templateType, language = 'ru') {
    try {
      const response = await api.get('/print/templates', {
        params: { template_type: templateType, language }
      });
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка получения шаблонов'
      };
    }
  },

  /**
   * Проверка статуса принтера
   */
  async checkPrinterStatus(printerName) {
    try {
      const response = await api.get(`/print/printers/${printerName}/status`);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка проверки принтера'
      };
    }
  },

  /**
   * Тестовая печать
   */
  async testPrint(printerName) {
    try {
      const response = await api.post('/print/test', {
        printer_name: printerName
      });
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка тестовой печати'
      };
    }
  }
};
