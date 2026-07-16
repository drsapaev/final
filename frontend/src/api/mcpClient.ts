// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

/**
 * MCP (Model Context Protocol) API Client
 *
 * UX Audit Stage 1 refactor (cross-cutting issue 10.1):
 * Раньше mcpClient создавал собственный axios-instance со своими
 * interceptors для auth/401/logging. Это приводило к:
 *   - дублированию логики token-refresh / CSRF / rate-limit
 *   - рассинхрону с api/client.js (например, mcpClient не делал refresh-token)
 *   - двум разным путям редиректа на /login при 401
 *
 * Теперь mcpClient — тонкая обёртка над `api` из api/client.js:
 *   - наследует все interceptors (auth, refresh, CSRF, rate-limit)
 *   - использует тот же baseURL + суффикс `/mcp`
 *   - логирование через общий logger
 *
 * Backward compatibility: API-методы mcpAPI.* сохраняют сигнатуры.
 */

import { api } from './client';
import { hardRedirectToLogin } from '../utils/navigation';
import logger from '../utils/logger';

// Префикс для всех MCP-эндпоинтов. Подставляется к baseURL из api/client.js.
const MCP_PREFIX = '/mcp';

/**
 * Низкоуровневый helper: выполняет запрос через api (axios) с подставленным
 * MCP-префиксом, возвращает response.data.
 *
 * @param {string} method - HTTP method (get/post/put/patch/delete)
 * @param {string} path - путь без /mcp префикса
 * @param {object} [config]
 * @returns {Promise<any>}
 */
async function mcpRequest(method, path, config = {}) {
  try {
    const url = `${MCP_PREFIX}${path}`;
    // UX Audit Stage 3: используем api.get()/post()/put() вместо api.request()
    // для совместимости с существующими тестами, которые мокают get/post методы.
    const { data, ...restConfig } = config;
    let response;

    switch (method.toLowerCase()) {
      case 'get':
        response = await api.get(url, restConfig);
        break;
      case 'post':
        response = await api.post(url, data, restConfig);
        break;
      case 'put':
        response = await api.put(url, data, restConfig);
        break;
      case 'patch':
        response = await api.patch(url, data, restConfig);
        break;
      case 'delete':
        response = await api.delete(url, restConfig);
        break;
      default:
        throw new Error(`Unsupported HTTP method: ${method}`);
    }

    return response.data;
  } catch (error) {
    const status = error?.response?.status;
    const detail = error?.response?.data?.detail || error?.response?.data?.message;

    logger.error(`[MCP] ${method.toUpperCase()} ${MCP_PREFIX}${path}`, {
      status,
      detail,
      data: error?.response?.data,
    });

    // 401 уже обрабатывается в api/client.js response interceptor
    // (он логирует, но не редиректит). Здесь мы делаем редирект —
    // MCP-запросы почти всегда требуют активной сессии.
    if (status === 401) {
      hardRedirectToLogin({
        reason: 'mcp-unauthorized',
        redirectAfter: typeof window !== 'undefined' ? window.location.pathname : undefined,
      });
    }

    throw error;
  }
}

/**
 * MCP API методы — публичный интерфейс.
 * Сигнатуры идентичны предыдущей версии для обратной совместимости.
 */
export const mcpAPI = {
  // === Управление MCP ===

  /**
   * Получить статус MCP системы
   */
  async getStatus() {
    return mcpRequest('get', '/status');
  },

  /**
   * Проверка здоровья MCP серверов
   */
  async healthCheck() {
    return mcpRequest('get', '/health');
  },

  /**
   * Получить метрики MCP
   */
  async getMetrics(server = null) {
    const params = server ? { server } : {};
    return mcpRequest('get', '/metrics', { params });
  },

  /**
   * Получить возможности MCP серверов
   */
  async getCapabilities(server = null) {
    const params = server ? { server } : {};
    return mcpRequest('get', '/capabilities', { params });
  },

  // === Анализ жалоб ===

  /**
   * Анализ жалоб пациента
   */
  async analyzeComplaint(data, options = {}) {
    return mcpRequest('post', '/complaint/analyze', {
      data: {
        complaint: data.complaint,
        patient_age: data.patientAge,
        patient_gender: data.patientGender,
        urgency_assessment: data.urgencyAssessment !== false,
        provider: data.provider,
      },
      signal: options.signal,
    });
  },

  /**
   * Валидация жалоб
   */
  async validateComplaint(complaint) {
    return mcpRequest('post', '/complaint/validate', {
      params: { complaint },
    });
  },

  /**
   * Получить шаблоны жалоб
   */
  async getComplaintTemplates(specialty = null) {
    const params = specialty ? { specialty } : {};
    return mcpRequest('get', '/complaint/templates', { params });
  },

  // === МКБ-10 ===

  /**
   * Подсказки кодов МКБ-10
   */
  async suggestICD10(data, options = {}) {
    return mcpRequest('post', '/icd10/suggest', {
      data: {
        symptoms: data.symptoms,
        diagnosis: data.diagnosis,
        specialty: data.specialty,
        provider: data.provider,
        max_suggestions: data.maxSuggestions || 5,
      },
      signal: options.signal,
    });
  },

  /**
   * Валидация кода МКБ-10
   */
  async validateICD10(code, symptoms = null, diagnosis = null) {
    return mcpRequest('post', '/icd10/validate', {
      params: { code, symptoms, diagnosis },
    });
  },

  /**
   * Поиск кодов МКБ-10
   */
  async searchICD10(query, category = null, limit = 10) {
    return mcpRequest('get', '/icd10/search', {
      params: { query, category, limit },
    });
  },

  // === Лабораторные анализы ===

  /**
   * Интерпретация лабораторных результатов
   */
  async interpretLabResults(data) {
    return mcpRequest('post', '/lab/interpret', {
      data: {
        results: data.results,
        patient_age: data.patientAge,
        patient_gender: data.patientGender,
        provider: data.provider,
        include_recommendations: data.includeRecommendations !== false,
      },
    });
  },

  /**
   * Проверка критических значений
   */
  async checkCriticalValues(results) {
    return mcpRequest('post', '/lab/check-critical', { data: results });
  },

  /**
   * Получить нормальные диапазоны
   */
  async getNormalRanges(testName = null, patientGender = null) {
    const params = {};
    if (testName) params.test_name = testName;
    if (patientGender) params.patient_gender = patientGender;
    return mcpRequest('get', '/lab/normal-ranges', { params });
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

    return mcpRequest('post', '/imaging/analyze', {
      data: formData,
      headers: { 'Content-Type': 'multipart/form-data' },
    });
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

    return mcpRequest('post', '/imaging/skin-lesion', {
      data: formData,
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  /**
   * Получить типы медицинских изображений
   */
  async getImagingTypes(category = null) {
    const params = category ? { category } : {};
    return mcpRequest('get', '/imaging/types', { params });
  },

  // === Пакетная обработка ===

  /**
   * Пакетная обработка запросов
   */
  async batchProcess(requests, parallel = true) {
    return mcpRequest('post', '/batch', {
      data: { requests, parallel },
    });
  },
};

/**
 * Хук для использования MCP в React компонентах.
 * Backward-compatible с предыдущей версией.
 */
export const useMCP = () => mcpAPI;

// Default export — для кода, который импортировал mcpClient напрямую.
// Раньше это был axios-instance; теперь это сам объект mcpAPI,
// что покрывает большинство сценариев использования.
export default mcpAPI;
