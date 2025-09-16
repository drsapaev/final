import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client.js';

/**
 * Хук для управления лабораторными результатами
 * @param {string} visitId - ID визита
 * @returns {Object} Объект с данными и методами для работы с лабораторными результатами
 */
export const useLabResults = (visitId) => {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);

  // Загрузка результатов
  const loadResults = useCallback(async () => {
    if (!visitId) return;
    
    setLoading(true);
    setError(null);
    try {
      const response = await api.get(`/visits/${visitId}/lab-results`);
      setResults(response.data || []);
    } catch (err) {
      console.error('Ошибка загрузки результатов:', err);
      setError(err.message || 'Ошибка загрузки результатов');
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [visitId]);

  // Сохранение результата
  const saveResult = useCallback(async (resultData) => {
    setLoading(true);
    setError(null);
    try {
      let response;
      if (resultData.id) {
        // Обновление существующего результата
        response = await api.put(`/lab-results/${resultData.id}`, resultData);
      } else {
        // Создание нового результата
        response = await api.post('/lab-results', {
          ...resultData,
          visit_id: visitId
        });
      }
      
      // Обновляем локальный список
      await loadResults();
      return response.data;
    } catch (err) {
      console.error('Ошибка сохранения результата:', err);
      setError(err.message || 'Ошибка сохранения результата');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [visitId, loadResults]);

  // Удаление результата
  const deleteResult = useCallback(async (resultId) => {
    setLoading(true);
    setError(null);
    try {
      await api.delete(`/lab-results/${resultId}`);
      // Обновляем локальный список
      await loadResults();
    } catch (err) {
      console.error('Ошибка удаления результата:', err);
      setError(err.message || 'Ошибка удаления результата');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [loadResults]);

  // Загрузка файла результата
  const uploadFile = useCallback(async (file, resultData) => {
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('visit_id', visitId);
      if (resultData) {
        Object.keys(resultData).forEach(key => {
          formData.append(key, resultData[key]);
        });
      }

      const response = await api.post('/lab-results/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      // Обновляем локальный список
      await loadResults();
      return response.data;
    } catch (err) {
      console.error('Ошибка загрузки файла:', err);
      setError(err.message || 'Ошибка загрузки файла');
      throw err;
    } finally {
      setUploading(false);
    }
  }, [visitId, loadResults]);

  // Генерация PDF отчета
  const generatePDF = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.get(`/visits/${visitId}/lab-results/pdf`, {
        responseType: 'blob',
      });

      // Создаем ссылку для скачивания
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `lab-results-${visitId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Ошибка генерации PDF:', err);
      setError(err.message || 'Ошибка генерации PDF');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [visitId]);

  // Отправка результатов пациенту
  const sendToPatient = useCallback(async (patientId, resultIds = []) => {
    setLoading(true);
    setError(null);
    try {
      await api.post(`/patients/${patientId}/send-lab-results`, {
        visit_id: visitId,
        result_ids: resultIds.length > 0 ? resultIds : results.map(r => r.id)
      });
    } catch (err) {
      console.error('Ошибка отправки результатов:', err);
      setError(err.message || 'Ошибка отправки результатов');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [visitId, results]);

  // Фильтрация результатов по категории
  const getResultsByCategory = useCallback((category) => {
    if (category === 'all') return results;
    return results.filter(r => r.category === category);
  }, [results]);

  // Подсчет результатов по категориям
  const getCategoryCount = useCallback((category) => {
    return getResultsByCategory(category).length;
  }, [getResultsByCategory]);

  // Получение статистики
  const getStats = useCallback(() => {
    const total = results.length;
    const completed = results.filter(r => r.status === 'completed').length;
    const pending = results.filter(r => r.status === 'pending').length;
    const abnormal = results.filter(r => r.is_abnormal).length;

    return {
      total,
      completed,
      pending,
      abnormal,
      completionRate: total > 0 ? Math.round((completed / total) * 100) : 0
    };
  }, [results]);

  // Автоматическая загрузка при изменении visitId
  useEffect(() => {
    if (visitId) {
      loadResults();
    }
  }, [visitId, loadResults]);

  return {
    // Данные
    results,
    loading,
    error,
    uploading,

    // Методы
    loadResults,
    saveResult,
    deleteResult,
    uploadFile,
    generatePDF,
    sendToPatient,

    // Утилиты
    getResultsByCategory,
    getCategoryCount,
    getStats,

    // Сброс ошибки
    clearError: () => setError(null)
  };
};

export default useLabResults;
