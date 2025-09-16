import { useState, useEffect, useCallback } from 'react';
import { api as apiClient } from '../api/client';

/**
 * Кастомный хук для управления онлайн очередью
 * Заменяет прямые API вызовы в OnlineQueueManager
 */
export const useQueueManager = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [statistics, setStatistics] = useState(null);
  const [specialists, setSpecialists] = useState([]);
  const [queueData, setQueueData] = useState(null);
  const [qrData, setQrData] = useState(null);

  // Загрузка специалистов
  const loadSpecialists = useCallback(async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/users/users');
      const users = response.data.users || response.data;
      const doctors = users.filter(user => user.role === 'Doctor');
      setSpecialists(doctors);
      setError('');
    } catch (err) {
      console.error('Ошибка загрузки специалистов:', err);
      setError('Не удалось загрузить список специалистов');
    } finally {
      setLoading(false);
    }
  }, []);

  // Генерация QR кода
  const generateQRCode = useCallback(async (selectedDate, selectedSpecialist) => {
    if (!selectedDate || !selectedSpecialist) {
      setError('Выберите дату и специалиста');
      return null;
    }
    
    setLoading(true);
    setError('');
    
    try {
      const response = await apiClient.post('/queue/qrcode', null, {
        params: {
          day: selectedDate,
          specialist_id: selectedSpecialist
        }
      });
      
      setQrData(response.data);
      setSuccess('QR код успешно сгенерирован');
      return response.data;
    } catch (err) {
      console.error('Ошибка генерации QR:', err);
      setError(err.response?.data?.detail || 'Ошибка генерации QR кода');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Загрузка очереди на сегодня
  const loadTodayQueue = useCallback(async (selectedSpecialist) => {
    if (!selectedSpecialist) return null;
    
    try {
      const response = await apiClient.get('/queue/today', {
        params: { specialist_id: selectedSpecialist }
      });
      setQueueData(response.data);
      return response.data;
    } catch (err) {
      console.error('Ошибка загрузки очереди:', err);
      if (err.response?.status !== 404) {
        setError('Ошибка загрузки очереди');
      }
      return null;
    }
  }, []);

  // Загрузка статистики
  const loadStatistics = useCallback(async (selectedSpecialist, selectedDate) => {
    if (!selectedSpecialist) return null;
    
    try {
      const response = await apiClient.get(`/queue/statistics/${selectedSpecialist}`, {
        params: { day: selectedDate }
      });
      
      if (response.data.success) {
        setStatistics(response.data.statistics);
        return response.data.statistics;
      }
      return null;
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
      return null;
    }
  }, []);

  // Открытие приема
  const openQueue = useCallback(async (selectedSpecialist) => {
    if (!selectedSpecialist) {
      setError('Выберите специалиста');
      return false;
    }
    
    setLoading(true);
    try {
      await apiClient.post('/queue/open', null, {
        params: {
          day: new Date().toISOString().split('T')[0],
          specialist_id: selectedSpecialist
        }
      });
      setSuccess('Прием открыт. Онлайн-запись закрыта');
      return true;
    } catch (err) {
      console.error('Ошибка открытия приема:', err);
      setError(err.response?.data?.detail || 'Ошибка открытия приема');
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  // Вызов пациента
  const callPatient = useCallback(async (entryId) => {
    setLoading(true);
    try {
      await apiClient.post(`/queue/call/${entryId}`);
      setSuccess('Пациент вызван');
      return true;
    } catch (err) {
      console.error('Ошибка вызова пациента:', err);
      setError(err.response?.data?.detail || 'Ошибка вызова пациента');
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  // Очистка сообщений
  const clearMessages = useCallback(() => {
    setError('');
    setSuccess('');
  }, []);

  // Автоматическая загрузка специалистов при монтировании
  useEffect(() => {
    loadSpecialists();
  }, [loadSpecialists]);

  return {
    // Состояния
    loading,
    error,
    success,
    statistics,
    specialists,
    queueData,
    qrData,
    
    // Методы
    loadSpecialists,
    generateQRCode,
    loadTodayQueue,
    loadStatistics,
    openQueue,
    callPatient,
    clearMessages,
    
    // Сеттеры для внешнего управления
    setError,
    setSuccess,
    setQueueData,
    setQrData
  };
};
