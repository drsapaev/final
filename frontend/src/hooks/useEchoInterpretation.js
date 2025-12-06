import { useState, useCallback } from 'react';
import { api } from '../api/client.js';

import logger from '../utils/logger';
/**
 * Хук для AI интерпретации эхокардиографии
 * @param {string} visitId - ID визита
 * @param {string} patientId - ID пациента
 * @returns {Object} Объект с данными и методами для AI анализа ЭхоКГ
 */
export const useEchoInterpretation = (visitId, patientId) => {
  const [aiResult, setAiResult] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  // AI анализ данных ЭхоКГ
  const analyzeEcho = useCallback(async (echoParameters) => {
    if (!visitId || !echoParameters) {
      setError('Недостаточно данных для анализа');
      return null;
    }

    setAnalyzing(true);
    setError(null);
    
    try {
      const response = await api.post('/ai/echo-interpret', {
        visit_id: visitId,
        patient_id: patientId,
        parameters: echoParameters,
        timestamp: new Date().toISOString()
      });
      
      const result = response.data;
      setAiResult(result);
      
      // Добавляем в историю
      setHistory(prev => [{
        id: Date.now(),
        timestamp: new Date().toISOString(),
        parameters: echoParameters,
        result: result
      }, ...prev.slice(0, 9)]); // Храним последние 10 анализов
      
      return result;
    } catch (err) {
      logger.error('Ошибка AI анализа ЭхоКГ:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка AI анализа';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setAnalyzing(false);
    }
  }, [visitId, patientId]);

  // Получение рекомендаций на основе параметров
  const getRecommendations = useCallback(async (echoParameters, symptoms = []) => {
    setAnalyzing(true);
    setError(null);
    
    try {
      const response = await api.post('/ai/echo-recommendations', {
        visit_id: visitId,
        patient_id: patientId,
        parameters: echoParameters,
        symptoms: symptoms
      });
      
      return response.data;
    } catch (err) {
      logger.error('Ошибка получения рекомендаций:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка получения рекомендаций';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setAnalyzing(false);
    }
  }, [visitId, patientId]);

  // Анализ риска на основе ЭхоКГ данных
  const assessRisk = useCallback(async (echoParameters, patientData = {}) => {
    setAnalyzing(true);
    setError(null);
    
    try {
      const response = await api.post('/ai/echo-risk-assessment', {
        visit_id: visitId,
        patient_id: patientId,
        parameters: echoParameters,
        patient_data: patientData
      });
      
      return response.data;
    } catch (err) {
      logger.error('Ошибка оценки риска:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка оценки риска';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setAnalyzing(false);
    }
  }, [visitId, patientId]);

  // Сравнение с предыдущими исследованиями
  const compareWithPrevious = useCallback(async (currentParameters) => {
    setAnalyzing(true);
    setError(null);
    
    try {
      const response = await api.post('/ai/echo-compare', {
        visit_id: visitId,
        patient_id: patientId,
        current_parameters: currentParameters
      });
      
      return response.data;
    } catch (err) {
      logger.error('Ошибка сравнения с предыдущими исследованиями:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка сравнения';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setAnalyzing(false);
    }
  }, [visitId, patientId]);

  // Генерация структурированного отчета
  const generateReport = useCallback(async (echoParameters, aiResult = null) => {
    setAnalyzing(true);
    setError(null);
    
    try {
      const response = await api.post('/ai/echo-report', {
        visit_id: visitId,
        patient_id: patientId,
        parameters: echoParameters,
        ai_analysis: aiResult || aiResult
      });
      
      return response.data;
    } catch (err) {
      logger.error('Ошибка генерации отчета:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка генерации отчета';
      setError(errorMessage);
      throw new Error(errorMessage);
    } finally {
      setAnalyzing(false);
    }
  }, [visitId, patientId, aiResult]);

  // Валидация параметров перед анализом
  const validateParameters = useCallback((parameters) => {
    const errors = [];
    const warnings = [];

    // Проверка обязательных параметров
    if (!parameters.leftVentricleFunction?.ejectionFraction) {
      errors.push('Фракция выброса левого желудочка обязательна для AI анализа');
    }

    // Проверка диапазонов значений
    const ef = parseFloat(parameters.leftVentricleFunction?.ejectionFraction);
    if (ef && (ef < 10 || ef > 90)) {
      warnings.push('Фракция выброса вне обычного диапазона (10-90%)');
    }

    // Проверка консистентности данных
    if (parameters.leftVentricleFunction?.wallMotion === 'severely_impaired' && ef > 50) {
      warnings.push('Несоответствие между нарушением сократимости и фракцией выброса');
    }

    return { errors, warnings, isValid: errors.length === 0 };
  }, []);

  // Получение интерпретации отдельного параметра
  const interpretParameter = useCallback((parameterName, value, context = {}) => {
    const interpretations = {
      ejectionFraction: (val) => {
        if (val >= 55) return { status: 'normal', message: 'Нормальная систолическая функция ЛЖ' };
        if (val >= 45) return { status: 'mild', message: 'Легкое снижение систолической функции ЛЖ' };
        if (val >= 35) return { status: 'moderate', message: 'Умеренное снижение систолической функции ЛЖ' };
        return { status: 'severe', message: 'Выраженное снижение систолической функции ЛЖ' };
      },
      leftAtrium: (val) => {
        const numVal = parseFloat(val);
        if (numVal <= 40) return { status: 'normal', message: 'Нормальный размер левого предсердия' };
        if (numVal <= 47) return { status: 'mild', message: 'Легкое увеличение левого предсердия' };
        if (numVal <= 52) return { status: 'moderate', message: 'Умеренное увеличение левого предсердия' };
        return { status: 'severe', message: 'Выраженное увеличение левого предсердия' };
      }
    };

    const interpreter = interpretations[parameterName];
    if (interpreter && value) {
      return interpreter(value);
    }

    return { status: 'unknown', message: 'Интерпретация недоступна' };
  }, []);

  // Очистка результатов
  const clearResults = useCallback(() => {
    setAiResult(null);
    setError(null);
  }, []);

  // Очистка истории
  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  return {
    // Данные
    aiResult,
    analyzing,
    error,
    history,

    // Основные методы
    analyzeEcho,
    getRecommendations,
    assessRisk,
    compareWithPrevious,
    generateReport,

    // Утилиты
    validateParameters,
    interpretParameter,

    // Управление состоянием
    clearResults,
    clearHistory,
    clearError: () => setError(null)
  };
};

export default useEchoInterpretation;
