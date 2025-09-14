/**
 * Сервис медицинских данных
 * Централизованная работа с медкартами, EMR, рецептами
 */
import { api } from '../api/client';

export const medicalService = {
  /**
   * Получение медкарты пациента
   */
  async getPatientRecord(patientId) {
    try {
      const response = await api.get(`/patients/${patientId}/emr`);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка получения медкарты'
      };
    }
  },

  /**
   * Создание/обновление EMR записи
   */
  async saveEMR(appointmentId, emrData) {
    try {
      const response = await api.post(`/appointments/${appointmentId}/emr`, emrData);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка сохранения медкарты'
      };
    }
  },

  /**
   * Создание рецепта
   */
  async createPrescription(appointmentId, prescriptionData) {
    try {
      const response = await api.post(`/appointments/${appointmentId}/prescription`, prescriptionData);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка создания рецепта'
      };
    }
  },

  /**
   * Получение шаблонов EMR
   */
  async getEMRTemplates(specialty) {
    try {
      const response = await api.get('/emr/templates', {
        params: { specialty }
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
   * Завершение визита
   */
  async completeVisit(appointmentId, visitData) {
    try {
      const response = await api.post(`/appointments/${appointmentId}/complete`, visitData);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка завершения визита'
      };
    }
  },

  /**
   * Получение истории пациента
   */
  async getPatientHistory(patientId) {
    try {
      const response = await api.get(`/specialized/patient-history/${patientId}`);
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Ошибка получения истории'
      };
    }
  },

  /**
   * Форматирование диагноза
   */
  formatDiagnosis(diagnosis) {
    if (!diagnosis) return 'Диагноз не указан';
    
    // Базовое форматирование
    return diagnosis.trim();
  },

  /**
   * Валидация медицинских данных
   */
  validateEMRData(emrData) {
    const errors = [];
    
    if (!emrData.chief_complaint?.trim()) {
      errors.push('Укажите основную жалобу');
    }
    
    if (!emrData.physical_examination?.trim()) {
      errors.push('Укажите данные осмотра');
    }
    
    if (!emrData.assessment?.trim()) {
      errors.push('Укажите заключение');
    }
    
    return {
      isValid: errors.length === 0,
      errors
    };
  }
};
