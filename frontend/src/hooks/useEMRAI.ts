import { useState, useCallback } from 'react';
import { api as apiClient } from '../api/client';
import { mcpAPI } from '../api/mcpClient';
import {
  validateICD10Suggestions,
  validateClinicalRecommendations,
  validateAIResponse,
  detectPromptInjection
} from '../utils/aiValidator';

import logger from '../utils/logger';
/**
 * Кастомный хук для AI функций в EMR системе через MCP
 * Поддерживает все медицинские AI функции
 */
export const useEMRAI = (useMCP = true, provider = 'deepseek') => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [icd10Suggestions, setIcd10Suggestions] = useState([]);
  const [clinicalRecommendations, setClinicalRecommendations] = useState(null);

  // Получение AI подсказок для МКБ-10 через MCP
  const getICD10Suggestions = useCallback(async (symptoms, diagnosis, specialty = null) => {
    // Prompt injection check
    const inputText = (symptoms?.join(' ') || '') + ' ' + (diagnosis || '');
    if (detectPromptInjection(inputText)) {
      setError('Обнаружена попытка prompt injection.');
      logger.warn('EMR AI: prompt injection detected in ICD10 suggestions');
      return;
    }
    if (!symptoms && !diagnosis) {
      setError('Необходимо указать симптомы или диагноз');
      return [];
    }

    setLoading(true);
    setError('');
    setClinicalRecommendations(null);

    try {
      if (useMCP) {
        const mcpResult = await mcpAPI.suggestICD10({
          symptoms: symptoms ? symptoms.split('.').map(s => s.trim()).filter(Boolean) : [],
          diagnosis: diagnosis || '',
          specialty: specialty,
          provider: provider,
          maxSuggestions: 5
        });

        if ((mcpResult as Record<string, unknown>).status === 'success') {
          const data = (mcpResult as Record<string, unknown>).data;

          // Validate and sanitize clinical recommendations
          if ((data as Record<string, unknown>).clinical_recommendations) {
            const validatedRecommendations = validateClinicalRecommendations((data as Record<string, unknown>).clinical_recommendations);
            setClinicalRecommendations(validatedRecommendations);
          }

          // Validate and sanitize ICD10 suggestions
          const rawSuggestions = (data as Record<string, unknown>).suggestions || [];
          const validatedSuggestions = validateICD10Suggestions(rawSuggestions);

          if ((validatedSuggestions as unknown[]).length === 0 && (rawSuggestions as unknown[]).length > 0) {
            logger.warn('[AI Security] All ICD10 suggestions failed validation');
          }

          setIcd10Suggestions(validatedSuggestions);
          return validatedSuggestions;
        } else {
          throw new Error(String((mcpResult as Record<string, unknown>).error) || 'MCP ICD10 suggestion failed');
        }
      } else {
        // Старый метод через прямой API
        const response = await apiClient.post('/ai/icd-suggest', {
          symptoms: symptoms ? symptoms.split('.').filter(s => s.trim()) : [],
          diagnosis: diagnosis || '',
          provider: provider
        });

        const suggestions = response.data;
        setIcd10Suggestions(suggestions);
        return suggestions;
      }
    } catch (err) {
      logger.error('AI error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка получения AI подсказок';
      setError(errorMessage);
      return [];
    } finally {
      setLoading(false);
    }
  }, [useMCP, provider]);

  // Анализ жалоб пациента через MCP
  const analyzeComplaints = useCallback(async (complaintsData) => {
    // Prompt injection check
    const complaintText = complaintsData?.complaint || complaintsData?.complaints || '';
    if (detectPromptInjection(complaintText)) {
      setError('Обнаружена попытка prompt injection.');
      logger.warn('EMR AI: prompt injection detected in complaint analysis');
      return null;
    }
    setLoading(true);
    setError('');

    try {
      if (useMCP) {
        const mcpResult = await mcpAPI.analyzeComplaint({
          complaint: complaintsData.complaint || complaintsData.complaints,
          patientAge: complaintsData.patient_age || complaintsData.age,
          patientGender: complaintsData.patient_gender || complaintsData.gender,
          provider: provider,
          urgencyAssessment: true
        });

        if ((mcpResult as Record<string, unknown>).status === 'success') {
          // Validate AI response
          const validatedData = validateAIResponse((mcpResult as Record<string, unknown>).data, {
            expectedType: 'object',
            sanitize: true,
            strictMode: false
          });
          return validatedData;
        } else {
          throw new Error(String((mcpResult as Record<string, unknown>).error) || 'MCP complaint analysis failed');
        }
      } else {
        const response = await apiClient.post('/ai/analyze-complaints', {
          ...complaintsData,
          provider: provider
        });
        return response.data;
      }
    } catch (err) {
      logger.error('AI analysis error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка анализа жалоб';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, [useMCP, provider]);

  // Получение рекомендаций по лечению
  const getTreatmentRecommendations = useCallback(async (patientData) => {
    setLoading(true);
    setError('');

    try {
      const response = await apiClient.post('/ai/treatment-recommendations', patientData);
      return response.data;
    } catch (err) {
      logger.error('AI recommendations error:', err);
      const errorMessage = err.response?.data?.detail || 'Ошибка получения рекомендаций';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Интерпретация лабораторных результатов через MCP
  const interpretLabResults = useCallback(async (results, patientAge, patientGender) => {
    setLoading(true);
    setError('');

    try {
      if (useMCP) {
        const mcpResult = await mcpAPI.interpretLabResults({
          results: results,
          patientAge: patientAge,
          patientGender: patientGender,
          provider: provider,
          includeRecommendations: true
        });

        if ((mcpResult as Record<string, unknown>).status === 'success') {
          // Validate AI response
          const validatedData = validateAIResponse((mcpResult as Record<string, unknown>).data, {
            expectedType: 'object',
            sanitize: true,
            strictMode: false
          });
          return validatedData;
        } else {
          throw new Error(String((mcpResult as Record<string, unknown>).error) || 'MCP lab interpretation failed');
        }
      } else {
        const response = await apiClient.post('/ai/lab-interpret', {
          results: results,
          patient_age: patientAge,
          patient_gender: patientGender,
          provider: provider
        });
        return response.data;
      }
    } catch (err) {
      logger.error('AI lab interpretation error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка интерпретации анализов';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, [useMCP, provider]);

  // Предложения по лабораторным исследованиям (оставлено для обратной совместимости)
  const getLabTestSuggestions = useCallback(async (symptoms, diagnosis) => {
    setLoading(true);
    setError('');

    try {
      const response = await apiClient.post('/ai/lab-suggestions', {
        symptoms,
        diagnosis,
        provider: provider
      });
      return response.data;
    } catch (err) {
      logger.error('AI lab suggestions error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка получения предложений по анализам';
      setError(errorMessage);
      return [];
    } finally {
      setLoading(false);
    }
  }, [provider]);

  // Очистка состояний
  const clearError = useCallback(() => {
    setError('');
  }, []);

  const clearSuggestions = useCallback(() => {
    setIcd10Suggestions([]);
  }, []);

  // Анализ медицинских изображений через MCP
  const analyzeImage = useCallback(async (imageFile, imageType, options = {}) => {
    setLoading(true);
    setError('');

    try {
      if (useMCP) {
        const mcpResult = await mcpAPI.analyzeImage(imageFile, imageType, {
          ...options,
          provider: provider
        });

        if ((mcpResult as Record<string, unknown>).status === 'success') {
          // Validate AI response
          const validatedData = validateAIResponse((mcpResult as Record<string, unknown>).data, {
            expectedType: 'object',
            sanitize: true,
            strictMode: false
          });
          return validatedData;
        } else {
          throw new Error(String((mcpResult as Record<string, unknown>).error) || 'MCP image analysis failed');
        }
      } else {
        throw new Error('Image analysis requires MCP mode');
      }
    } catch (err) {
      logger.error('AI image analysis error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка анализа изображения';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, [useMCP, provider]);

  // Анализ кожных образований через MCP
  const analyzeSkinLesion = useCallback(async (imageFile, lesionInfo = null, patientHistory = null) => {
    setLoading(true);
    setError('');

    try {
      if (useMCP) {
        const mcpResult = await mcpAPI.analyzeSkinLesion(imageFile, lesionInfo, patientHistory, provider);

        if ((mcpResult as Record<string, unknown>).status === 'success') {
          // Validate AI response
          const validatedData = validateAIResponse((mcpResult as Record<string, unknown>).data, {
            expectedType: 'object',
            sanitize: true,
            strictMode: false
          });
          return validatedData;
        } else {
          throw new Error(String((mcpResult as Record<string, unknown>).error) || 'MCP skin lesion analysis failed');
        }
      } else {
        throw new Error('Skin lesion analysis requires MCP mode');
      }
    } catch (err) {
      logger.error('AI skin lesion analysis error:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка анализа кожного образования';
      setError(errorMessage);
      return null;
    } finally {
      setLoading(false);
    }
  }, [useMCP, provider]);

  return {
    // Состояния
    loading,
    error,
    icd10Suggestions,
    clinicalRecommendations,

    // Методы
    getICD10Suggestions,
    analyzeComplaints,
    getTreatmentRecommendations,
    interpretLabResults,
    getLabTestSuggestions,
    analyzeImage,
    analyzeSkinLesion,
    clearError,
    clearSuggestions,

    // Сеттеры
    setIcd10Suggestions,
    setClinicalRecommendations,
    setError
  };
};
