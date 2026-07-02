import { useState, useCallback } from 'react';
import { api } from '../api/client.js';

import logger from '../utils/logger';
/**
 * Хук для получения ICD-10 предложений с помощью AI
 * @returns {Object} Объект с данными и методами для работы с ICD предложениями
 */
export const useICDSuggestions = () => {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  // Получение предложений ICD-10 кодов
  const getSuggestions = useCallback(async (symptoms, diagnosis = '', additionalData = {}) => {
    if (!symptoms || (Array.isArray(symptoms) && symptoms.length === 0)) {
      setError('Необходимо указать симптомы для получения предложений');
      return [];
    }

    setLoading(true);
    setError(null);
    
    try {
      // Нормализуем симптомы
      const normalizedSymptoms = Array.isArray(symptoms) 
        ? symptoms.filter(s => s && s.trim())
        : symptoms.split('.').filter(s => s && s.trim());

      const requestData = {
        symptoms: normalizedSymptoms,
        diagnosis: diagnosis || '',
        ...additionalData
      };

      const response = await api.post('/ai/icd-suggest', requestData);
      
      const result = response.data || [];
      setSuggestions(result);
      
      // Добавляем в историю поиска
      setHistory(prev => [{
        id: Date.now(),
        timestamp: new Date().toISOString(),
        query: { symptoms: normalizedSymptoms, diagnosis },
        results: result
      }, ...prev.slice(0, 9)]); // Храним последние 10 поисков
      
      return result;
    } catch (err) {
      logger.error('Ошибка получения ICD предложений:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка получения предложений';
      setError(errorMessage);
      setSuggestions([]);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  // Поиск ICD кодов по тексту
  const searchICD = useCallback(async (searchText, limit = 10) => {
    if (!searchText || searchText.trim().length < 2) {
      return [];
    }

    setLoading(true);
    setError(null);
    
    try {
      const response = await api.get('/ai/icd-search', {
        params: {
          query: searchText.trim(),
          limit: limit
        }
      });
      
      return response.data || [];
    } catch (err) {
      logger.error('Ошибка поиска ICD кодов:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка поиска';
      setError(errorMessage);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  // Получение детальной информации о ICD коде
  const getICDDetails = useCallback(async (icdCode) => {
    if (!icdCode) {
      setError('Необходимо указать ICD код');
      return null;
    }

    setLoading(true);
    setError(null);
    
    try {
      const response = await api.get(`/ai/icd-details/${icdCode}`);
      return response.data;
    } catch (err) {
      logger.error('Ошибка получения деталей ICD кода:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка получения деталей';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Валидация ICD кода
  const validateICD = useCallback(async (icdCode) => {
    if (!icdCode) {
      return { isValid: false, message: 'ICD код не указан' };
    }

    setLoading(true);
    setError(null);
    
    try {
      const response = await api.post('/ai/icd-validate', { code: icdCode });
      return response.data;
    } catch (err) {
      logger.error('Ошибка валидации ICD кода:', err);
      return { 
        isValid: false, 
        message: err.response?.data?.detail || 'Ошибка валидации' 
      };
    } finally {
      setLoading(false);
    }
  }, []);

  // Получение связанных ICD кодов
  const getRelatedCodes = useCallback(async (icdCode, limit = 5) => {
    if (!icdCode) {
      return [];
    }

    setLoading(true);
    setError(null);
    
    try {
      const response = await api.get(`/ai/icd-related/${icdCode}`, {
        params: { limit }
      });
      
      return response.data || [];
    } catch (err) {
      logger.error('Ошибка получения связанных кодов:', err);
      setError(err.response?.data?.detail || err.message || 'Ошибка получения связанных кодов');
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  // Анализ совместимости диагнозов
  const analyzeCompatibility = useCallback(async (primaryDiagnosis, secondaryDiagnoses = []) => {
    if (!primaryDiagnosis) {
      setError('Необходимо указать основной диагноз');
      return null;
    }

    setLoading(true);
    setError(null);
    
    try {
      const response = await api.post('/ai/icd-compatibility', {
        primary: primaryDiagnosis,
        secondary: secondaryDiagnoses
      });
      
      return response.data;
    } catch (err) {
      logger.error('Ошибка анализа совместимости:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка анализа совместимости';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Получение статистики использования ICD кодов
  const getUsageStats = useCallback(async (icdCode, period = '30d') => {
    if (!icdCode) {
      return null;
    }

    try {
      const response = await api.get(`/ai/icd-stats/${icdCode}`, {
        params: { period }
      });
      
      return response.data;
    } catch (err) {
      logger.error('Ошибка получения статистики:', err);
      return null;
    }
  }, []);

  // Форматирование предложения для отображения
  const formatSuggestion = useCallback((suggestion) => {
    if (!suggestion) return '';
    
    const { code, title, description, confidence } = suggestion;
    let formatted = `${code}`;
    
    if (title) {
      formatted += ` - ${title}`;
    }
    
    if (description && description !== title) {
      formatted += ` (${description})`;
    }
    
    if (confidence && confidence < 1) {
      formatted += ` [${Math.round(confidence * 100)}%]`;
    }
    
    return formatted;
  }, []);

  // Группировка предложений по категориям
  const groupSuggestionsByCategory = useCallback((suggestions) => {
    const grouped = {};
    
    suggestions.forEach(suggestion => {
      const category = suggestion.category || 'Другие';
      if (!grouped[category]) {
        grouped[category] = [];
      }
      grouped[category].push(suggestion);
    });
    
    // Сортируем по уверенности в каждой категории
    Object.keys(grouped).forEach(category => {
      grouped[category].sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
    });
    
    return grouped;
  }, []);

  // Фильтрация предложений по уверенности
  const filterByConfidence = useCallback((suggestions, minConfidence = 0.5) => {
    return suggestions.filter(s => (s.confidence || 0) >= minConfidence);
  }, []);

  // Очистка предложений
  const clearSuggestions = useCallback(() => {
    setSuggestions([]);
    setError(null);
  }, []);

  // Очистка истории
  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  return {
    // Данные
    suggestions,
    loading,
    error,
    history,

    // Основные методы
    getSuggestions,
    searchICD,
    getICDDetails,
    validateICD,
    getRelatedCodes,
    analyzeCompatibility,
    getUsageStats,

    // Утилиты
    formatSuggestion,
    groupSuggestionsByCategory,
    filterByConfidence,

    // Управление состоянием
    clearSuggestions,
    clearHistory,
    clearError: () => setError(null)
  };
};

export default useICDSuggestions;
