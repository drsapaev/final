import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client.js';

import logger from '../utils/logger';
/**
 * Хук для управления данными эхокардиографии
 * @param {string} visitId - ID визита
 * @param {string} patientId - ID пациента
 * @returns {Object} Объект с данными и методами для работы с ЭхоКГ
 */
export const useEchoData = (visitId, patientId) => {
  const [echoData, setEchoData] = useState({
    // Структуры сердца
    structures: {
      aorticRoot: '',
      leftAtrium: '',
      rightAtrium: '',
      leftVentricle: '',
      rightVentricle: '',
      interventricularSeptum: '',
      posteriorWall: ''
    },
    
    // Функция левого желудочка
    leftVentricleFunction: {
      ejectionFraction: '',
      fractionalShortening: '',
      wallMotion: 'normal',
      diastolicFunction: 'normal'
    },
    
    // Клапаны
    valves: {
      mitral: { stenosis: 'none', regurgitation: 'none' },
      aortic: { stenosis: 'none', regurgitation: 'none' },
      tricuspid: { stenosis: 'none', regurgitation: 'none' },
      pulmonary: { stenosis: 'none', regurgitation: 'none' }
    },
    
    // Перикард
    pericardium: {
      effusion: 'none',
      thickness: 'normal'
    },
    
    // Заключение
    conclusion: '',
    recommendations: ''
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  // Загрузка данных ЭхоКГ
  const loadEchoData = useCallback(async () => {
    if (!visitId) return;
    
    setLoading(true);
    setError(null);
    try {
      const response = await api.get(`/visits/${visitId}/echo/params`);
      if (response.data) {
        setEchoData(prevData => ({
          ...prevData,
          ...response.data
        }));
      }
    } catch (err) {
      // Если бэкенд не реализован (404) — тихо используем значения по умолчанию
      if (err?.response?.status === 404) {
        logger.info('Echo params endpoint not found (404). Using defaults.');
        return;
      }
      logger.error('Ошибка загрузки данных ЭхоКГ:', err);
      setError(err.message || 'Ошибка загрузки данных ЭхоКГ');
    } finally {
      setLoading(false);
    }
  }, [visitId]);

  // Сохранение данных ЭхоКГ
  const saveEchoData = useCallback(async (dataToSave = echoData) => {
    if (!visitId) return;
    
    setSaving(true);
    setError(null);
    try {
      const response = await api.post(`/visits/${visitId}/echo/params`, {
        ...dataToSave,
        visit_id: visitId,
        patient_id: patientId
      });
      
      if (response.data) {
        setEchoData(response.data);
      }
      
      return response.data;
    } catch (err) {
      logger.error('Ошибка сохранения данных ЭхоКГ:', err);
      setError(err.message || 'Ошибка сохранения данных ЭхоКГ');
      throw err;
    } finally {
      setSaving(false);
    }
  }, [visitId, patientId, echoData]);

  // Обновление отдельного поля
  const updateField = useCallback((section, field, value) => {
    setEchoData(prev => {
      if (typeof prev[section] === 'object' && prev[section] !== null) {
        return {
          ...prev,
          [section]: {
            ...prev[section],
            [field]: value
          }
        };
      } else {
        return {
          ...prev,
          [section]: value
        };
      }
    });
  }, []);

  // Обновление данных клапана
  const updateValve = useCallback((valveName, property, value) => {
    setEchoData(prev => ({
      ...prev,
      valves: {
        ...prev.valves,
        [valveName]: {
          ...prev.valves[valveName],
          [property]: value
        }
      }
    }));
  }, []);

  // Сброс данных к значениям по умолчанию
  const resetToDefaults = useCallback(() => {
    setEchoData({
      structures: {
        aorticRoot: '',
        leftAtrium: '',
        rightAtrium: '',
        leftVentricle: '',
        rightVentricle: '',
        interventricularSeptum: '',
        posteriorWall: ''
      },
      leftVentricleFunction: {
        ejectionFraction: '',
        fractionalShortening: '',
        wallMotion: 'normal',
        diastolicFunction: 'normal'
      },
      valves: {
        mitral: { stenosis: 'none', regurgitation: 'none' },
        aortic: { stenosis: 'none', regurgitation: 'none' },
        tricuspid: { stenosis: 'none', regurgitation: 'none' },
        pulmonary: { stenosis: 'none', regurgitation: 'none' }
      },
      pericardium: {
        effusion: 'none',
        thickness: 'normal'
      },
      conclusion: '',
      recommendations: ''
    });
  }, []);

  // Валидация данных
  const validateData = useCallback(() => {
    const errors = [];
    
    // Проверка обязательных полей
    if (!echoData.conclusion?.trim()) {
      errors.push('Заключение обязательно для заполнения');
    }
    
    // Проверка числовых значений
    const numericFields = [
      'structures.ejectionFraction',
      'structures.fractionalShortening'
    ];
    
    numericFields.forEach(fieldPath => {
      const [section, field] = fieldPath.split('.');
      const value = echoData[section]?.[field];
      if (value && (isNaN(value) || value < 0 || value > 100)) {
        errors.push(`${field} должно быть числом от 0 до 100`);
      }
    });
    
    return errors;
  }, [echoData]);

  // Получение сводки по состоянию
  const getSummary = useCallback(() => {
    const summary = {
      hasAbnormalities: false,
      abnormalities: [],
      completeness: 0
    };

    // Проверка клапанов на патологию
    Object.entries(echoData.valves).forEach(([valveName, valve]) => {
      if (valve.stenosis !== 'none' || valve.regurgitation !== 'none') {
        summary.hasAbnormalities = true;
        summary.abnormalities.push(`${valveName} valve abnormality`);
      }
    });

    // Проверка функции ЛЖ
    const ef = parseFloat(echoData.leftVentricleFunction.ejectionFraction);
    if (ef && ef < 50) {
      summary.hasAbnormalities = true;
      summary.abnormalities.push('Reduced ejection fraction');
    }

    // Проверка перикарда
    if (echoData.pericardium.effusion !== 'none') {
      summary.hasAbnormalities = true;
      summary.abnormalities.push('Pericardial effusion');
    }

    // Подсчет заполненности
    const totalFields = 15; // Примерное количество основных полей
    let filledFields = 0;
    
    if (echoData.conclusion?.trim()) filledFields++;
    if (echoData.leftVentricleFunction.ejectionFraction) filledFields++;
    if (echoData.structures.leftAtrium) filledFields++;
    // ... можно добавить больше проверок
    
    summary.completeness = Math.round((filledFields / totalFields) * 100);

    return summary;
  }, [echoData]);

  // Автоматическая загрузка при изменении visitId
  useEffect(() => {
    if (visitId) {
      loadEchoData();
    }
  }, [visitId, loadEchoData]);

  return {
    // Данные
    echoData,
    loading,
    error,
    saving,

    // Методы
    loadEchoData,
    saveEchoData,
    updateField,
    updateValve,
    resetToDefaults,

    // Утилиты
    validateData,
    getSummary,

    // Сброс ошибки
    clearError: () => setError(null)
  };
};

export default useEchoData;
