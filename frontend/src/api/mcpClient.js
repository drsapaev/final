/**
 * MCP (Model Context Protocol) API Client
 */
import axios from 'axios';
import { getAuthToken } from '../services/auth';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api/v1';

// Создаем axios instance для MCP
const mcpClient = axios.create({
  baseURL: `${API_BASE_URL}/mcp`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Добавляем interceptor для авторизации
mcpClient.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Добавляем interceptor для обработки ошибок
mcpClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail || error.response?.data?.message;
    
    // Логирование ошибок
    console.error(`[MCP Client] ${error.config?.method?.toUpperCase()} ${error.config?.url}`, {
      status,
      detail,
      data: error.response?.data
    });
    
    // Обработка различных статусов
    if (status === 401) {
      console.warn('[MCP Client] 401 Unauthorized - редирект на /login');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    } else if (status === 403) {
      const message = detail || 'Недостаточно прав для выполнения операции';
      console.warn(`[MCP Client] 403 Forbidden: ${message}`);
      // Не блокируем Promise, позволяем компонентам обработать ошибку
    } else if (status === 404) {
      const message = detail || 'Ресурс не найден';
      console.warn(`[MCP Client] 404 Not Found: ${message}`);
    } else if (status >= 500) {
      console.error(`[MCP Client] Server Error ${status}: ${detail || 'Внутренняя ошибка сервера'}`);
    } else if (!error.response) {
      console.error('[MCP Client] Network Error - нет ответа от сервера');
    }
    
    return Promise.reject(error);
  }
);

/**
 * MCP API методы
 */
export const mcpAPI = {
  // === Управление MCP ===
  
  /**
   * Получить статус MCP системы
   */
  async getStatus() {
    const response = await mcpClient.get('/status');
    return response.data;
  },

  /**
   * Проверка здоровья MCP серверов
   */
  async healthCheck() {
    const response = await mcpClient.get('/health');
    return response.data;
  },

  /**
   * Получить метрики MCP
   */
  async getMetrics(server = null) {
    const params = server ? { server } : {};
    const response = await mcpClient.get('/metrics', { params });
    return response.data;
  },

  /**
   * Получить возможности MCP серверов
   */
  async getCapabilities(server = null) {
    const params = server ? { server } : {};
    const response = await mcpClient.get('/capabilities', { params });
    return response.data;
  },

  // === Анализ жалоб ===
  
  /**
   * Анализ жалоб пациента
   */
  async analyzeComplaint(data) {
    const response = await mcpClient.post('/complaint/analyze', {
      complaint: data.complaint,
      patient_age: data.patientAge,
      patient_gender: data.patientGender,
      urgency_assessment: data.urgencyAssessment !== false,
      provider: data.provider
    });
    return response.data;
  },

  /**
   * Валидация жалоб
   */
  async validateComplaint(complaint) {
    const response = await mcpClient.post('/complaint/validate', null, {
      params: { complaint }
    });
    return response.data;
  },

  /**
   * Получить шаблоны жалоб
   */
  async getComplaintTemplates(specialty = null) {
    const params = specialty ? { specialty } : {};
    const response = await mcpClient.get('/complaint/templates', { params });
    return response.data;
  },

  // === МКБ-10 ===
  
  /**
   * Подсказки кодов МКБ-10
   */
  async suggestICD10(data) {
    const response = await mcpClient.post('/icd10/suggest', {
      symptoms: data.symptoms,
      diagnosis: data.diagnosis,
      specialty: data.specialty,
      provider: data.provider,
      max_suggestions: data.maxSuggestions || 5
    });
    return response.data;
  },

  /**
   * Валидация кода МКБ-10
   */
  async validateICD10(code, symptoms = null, diagnosis = null) {
    const response = await mcpClient.post('/icd10/validate', null, {
      params: { code, symptoms, diagnosis }
    });
    return response.data;
  },

  /**
   * Поиск кодов МКБ-10
   */
  async searchICD10(query, category = null, limit = 10) {
    const response = await mcpClient.get('/icd10/search', {
      params: { query, category, limit }
    });
    return response.data;
  },

  // === Лабораторные анализы ===
  
  /**
   * Интерпретация лабораторных результатов
   */
  async interpretLabResults(data) {
    const response = await mcpClient.post('/lab/interpret', {
      results: data.results,
      patient_age: data.patientAge,
      patient_gender: data.patientGender,
      provider: data.provider,
      include_recommendations: data.includeRecommendations !== false
    });
    return response.data;
  },

  /**
   * Проверка критических значений
   */
  async checkCriticalValues(results) {
    const response = await mcpClient.post('/lab/check-critical', results);
    return response.data;
  },

  /**
   * Получить нормальные диапазоны
   */
  async getNormalRanges(testName = null, patientGender = null) {
    const params = {};
    if (testName) params.test_name = testName;
    if (patientGender) params.patient_gender = patientGender;
    
    const response = await mcpClient.get('/lab/normal-ranges', { params });
    return response.data;
  },

  // === Медицинские изображения ===
  
  /**
   * Анализ медицинского изображения
   */
  async analyzeImage(imageFile, imageType, options = {}) {
    const formData = new FormData();
    formData.append('image', imageFile);
    formData.append('image_type', imageType);
    
    if (options.modality) formData.append('modality', options.modality);
    if (options.clinicalContext) formData.append('clinical_context', options.clinicalContext);
    if (options.provider) formData.append('provider', options.provider);
    
    const response = await mcpClient.post('/imaging/analyze', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },

  /**
   * Анализ кожных образований
   */
  async analyzeSkinLesion(imageFile, lesionInfo = null, patientHistory = null, provider = null) {
    const formData = new FormData();
    formData.append('image', imageFile);
    
    if (lesionInfo) formData.append('lesion_info', JSON.stringify(lesionInfo));
    if (patientHistory) formData.append('patient_history', JSON.stringify(patientHistory));
    if (provider) formData.append('provider', provider);
    
    const response = await mcpClient.post('/imaging/skin-lesion', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },

  /**
   * Получить типы медицинских изображений
   */
  async getImagingTypes(category = null) {
    const params = category ? { category } : {};
    const response = await mcpClient.get('/imaging/types', { params });
    return response.data;
  },

  // === Пакетная обработка ===
  
  /**
   * Пакетная обработка запросов
   */
  async batchProcess(requests, parallel = true) {
    const response = await mcpClient.post('/batch', {
      requests,
      parallel
    });
    return response.data;
  }
};

// Хук для использования MCP в React компонентах
export const useMCP = () => {
  return mcpAPI;
};

export default mcpClient;
