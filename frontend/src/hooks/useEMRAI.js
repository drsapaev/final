import { useState, useCallback } from 'react';
import { api as apiClient } from '../api/client';

/**
 * Кастомный хук для AI функций в EMR системе
 * Заменяет прямые fetch вызовы в EMRSystem
 */
export const useEMRAI = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [icd10Suggestions, setIcd10Suggestions] = useState([]);

  // Получение AI подсказок для МКБ-10
  const getICD10Suggestions = useCallback(async (symptoms, diagnosis) => {
    if (!symptoms && !diagnosis) {
      setError('Необходимо указать симптомы или диагноз');
      return [];
    }

    setLoading(true);
    setError('');

    try {
      // Используем apiClient вместо прямого fetch
      const response = await apiClient.post('/ai/icd-suggest', {
        symptoms: symptoms ? symptoms.split('.').filter(s => s.trim()) : [],
        diagnosis: diagnosis || ''
      });

      const suggestions = response.data;
      setIcd10Suggestions(suggestions);
      return suggestions;
    } catch (err) {
      console.error('AI error:', err);
      const errorMessage = err.response?.data?.detail || 'Ошибка получения AI подсказок';
      setError(errorMessage);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  // Анализ жалоб пациента
  const analyzeComplaints = useCallback(async (complaintsData) => {
    setLoading(true);
    setError('');

    try {
      const response = await apiClient.post('/ai/analyze-complaints', complaintsData);
      return response.data;
    } catch (err) {
      console.error('AI analysis error:', err);
      const errorMessage = err.response?.data?.detail || 'Ошибка анализа жалоб';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Получение рекомендаций по лечению
  const getTreatmentRecommendations = useCallback(async (patientData) => {
    setLoading(true);
    setError('');

    try {
      const response = await apiClient.post('/ai/treatment-recommendations', patientData);
      return response.data;
    } catch (err) {
      console.error('AI recommendations error:', err);
      const errorMessage = err.response?.data?.detail || 'Ошибка получения рекомендаций';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Предложения по лабораторным исследованиям
  const getLabTestSuggestions = useCallback(async (symptoms, diagnosis) => {
    setLoading(true);
    setError('');

    try {
      const response = await apiClient.post('/ai/lab-suggestions', {
        symptoms,
        diagnosis
      });
      return response.data;
    } catch (err) {
      console.error('AI lab suggestions error:', err);
      const errorMessage = err.response?.data?.detail || 'Ошибка получения предложений по анализам';
      setError(errorMessage);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  // Очистка состояний
  const clearError = useCallback(() => {
    setError('');
  }, []);

  const clearSuggestions = useCallback(() => {
    setIcd10Suggestions([]);
  }, []);

  return {
    // Состояния
    loading,
    error,
    icd10Suggestions,

    // Методы
    getICD10Suggestions,
    analyzeComplaints,
    getTreatmentRecommendations,
    getLabTestSuggestions,
    clearError,
    clearSuggestions,

    // Сеттеры
    setIcd10Suggestions,
    setError
  };
};
