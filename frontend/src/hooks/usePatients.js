import { useState, useEffect, useCallback } from 'react';

import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';
const API_BASE = (import.meta?.env?.VITE_API_BASE_URL) || 'http://localhost:8000';

const usePatients = () => {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterGender, setFilterGender] = useState('');
  const [filterAgeRange, setFilterAgeRange] = useState('');
  const [filterBloodType, setFilterBloodType] = useState('');


  // Загрузка пациентов - использует реальный API (Single Source of Truth)
  const loadPatients = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const token = tokenManager.getAccessToken();
      if (!token) {
        throw new Error('Токен авторизации не найден');
      }

      const response = await fetch(`${API_BASE}/api/v1/patients/?limit=1000`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Ошибка загрузки пациентов' }));
        throw new Error(errorData.detail || `Ошибка ${response.status}`);
      }

      const data = await response.json();
      // Преобразуем данные из формата API в формат компонента
      const transformedPatients = data.map(patient => ({
        id: patient.id,
        firstName: patient.first_name,
        lastName: patient.last_name,
        middleName: patient.middle_name,
        email: patient.email || '',
        phone: patient.phone || '',
        birthDate: patient.birth_date || '',
        gender: patient.sex === 'M' ? 'male' : patient.sex === 'F' ? 'female' : '',
        address: patient.address || '',
        passport: patient.doc_number || '',
        insuranceNumber: '', // Поле отсутствует в API
        emergencyContact: '', // Поле отсутствует в API
        emergencyPhone: '', // Поле отсутствует в API
        bloodType: '', // Поле отсутствует в API
        allergies: '', // Поле отсутствует в API
        chronicDiseases: '', // Поле отсутствует в API
        notes: '', // Поле отсутствует в API
        createdAt: patient.created_at || new Date().toISOString().split('T')[0],
        lastVisit: null, // Нужно получать отдельно
        visitsCount: 0 // Нужно получать отдельно
      }));

      setPatients(transformedPatients);
    } catch (err) {
      setError(err);
      logger.error('Ошибка загрузки пациентов:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Создание пациента - использует реальный API (Single Source of Truth)
  const createPatient = useCallback(async (patientData) => {
    setLoading(true);
    setError(null);

    try {
      const token = tokenManager.getAccessToken();
      if (!token) {
        throw new Error('Токен авторизации не найден');
      }

      // Преобразуем данные из формата компонента в формат API
      // Backend принимает полное ФИО или отдельные поля - используем отдельные поля
      const apiData = {
        last_name: patientData.lastName || patientData.last_name,
        first_name: patientData.firstName || patientData.first_name,
        middle_name: patientData.middleName || patientData.middle_name || null,
        birth_date: patientData.birthDate || patientData.birth_date || null,
        sex: patientData.gender === 'male' ? 'M' : patientData.gender === 'female' ? 'F' : null,
        phone: patientData.phone || null,
        email: patientData.email || null,
        doc_number: patientData.passport || patientData.doc_number || null,
        address: patientData.address || null
      };

      const response = await fetch(`${API_BASE}/api/v1/patients/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(apiData)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Ошибка создания пациента' }));
        throw new Error(errorData.detail || `Ошибка ${response.status}`);
      }

      const newPatient = await response.json();

      // Преобразуем обратно в формат компонента
      const transformedPatient = {
        id: newPatient.id,
        firstName: newPatient.first_name,
        lastName: newPatient.last_name,
        middleName: newPatient.middle_name,
        email: newPatient.email || '',
        phone: newPatient.phone || '',
        birthDate: newPatient.birth_date || '',
        gender: newPatient.sex === 'M' ? 'male' : newPatient.sex === 'F' ? 'female' : '',
        address: newPatient.address || '',
        passport: newPatient.doc_number || '',
        createdAt: newPatient.created_at || new Date().toISOString().split('T')[0],
        lastVisit: null,
        visitsCount: 0
      };

      setPatients(prev => [transformedPatient, ...prev]);
      return transformedPatient;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Обновление пациента - использует реальный API (Single Source of Truth)
  const updatePatient = useCallback(async (id, patientData) => {
    setLoading(true);
    setError(null);

    try {
      const token = tokenManager.getAccessToken();
      if (!token) {
        throw new Error('Токен авторизации не найден');
      }

      // Преобразуем данные из формата компонента в формат API
      const apiData = {};
      if (patientData.lastName !== undefined) apiData.last_name = patientData.lastName;
      if (patientData.firstName !== undefined) apiData.first_name = patientData.firstName;
      if (patientData.middleName !== undefined) apiData.middle_name = patientData.middleName;
      if (patientData.birthDate !== undefined) apiData.birth_date = patientData.birthDate;
      if (patientData.gender !== undefined) apiData.sex = patientData.gender === 'male' ? 'M' : patientData.gender === 'female' ? 'F' : null;
      if (patientData.phone !== undefined) apiData.phone = patientData.phone;
      if (patientData.email !== undefined) apiData.email = patientData.email;
      if (patientData.passport !== undefined) apiData.doc_number = patientData.passport;
      if (patientData.address !== undefined) apiData.address = patientData.address;

      const response = await fetch(`${API_BASE}/api/v1/patients/${id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(apiData)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Ошибка обновления пациента' }));
        throw new Error(errorData.detail || `Ошибка ${response.status}`);
      }

      const updatedPatient = await response.json();

      // Преобразуем обратно в формат компонента
      const transformedPatient = {
        id: updatedPatient.id,
        firstName: updatedPatient.first_name,
        lastName: updatedPatient.last_name,
        middleName: updatedPatient.middle_name,
        email: updatedPatient.email || '',
        phone: updatedPatient.phone || '',
        birthDate: updatedPatient.birth_date || '',
        gender: updatedPatient.sex === 'M' ? 'male' : updatedPatient.sex === 'F' ? 'female' : '',
        address: updatedPatient.address || '',
        passport: updatedPatient.doc_number || ''
      };

      setPatients(prev => prev.map(patient =>
        patient.id === id
          ? { ...patient, ...transformedPatient }
          : patient
      ));

      return transformedPatient;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Удаление пациента - использует реальный API (Single Source of Truth)
  const deletePatient = useCallback(async (id) => {
    setLoading(true);
    setError(null);

    try {
      const token = tokenManager.getAccessToken();
      if (!token) {
        throw new Error('Токен авторизации не найден');
      }

      const response = await fetch(`${API_BASE}/api/v1/patients/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Ошибка удаления пациента' }));
        throw new Error(errorData.detail || `Ошибка ${response.status}`);
      }

      setPatients(prev => prev.filter(patient => patient.id !== id));
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Вычисление возраста
  const calculateAge = (birthDate) => {
    const today = new Date();
    const birth = new Date(birthDate);
    let age = today.getFullYear() - birth.getFullYear();
    const monthDiff = today.getMonth() - birth.getMonth();

    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
      age--;
    }

    return age;
  };

  // Фильтрация пациентов
  const filteredPatients = patients.filter(patient => {
    const matchesSearch = !searchTerm ||
      patient.firstName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      patient.lastName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      patient.middleName?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      patient.phone.includes(searchTerm) ||
      patient.email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      patient.passport.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesGender = !filterGender || patient.gender === filterGender;

    const patientAge = calculateAge(patient.birthDate);
    const matchesAgeRange = !filterAgeRange || (() => {
      switch (filterAgeRange) {
        case '0-18': return patientAge >= 0 && patientAge <= 18;
        case '19-35': return patientAge >= 19 && patientAge <= 35;
        case '36-50': return patientAge >= 36 && patientAge <= 50;
        case '51-65': return patientAge >= 51 && patientAge <= 65;
        case '65+': return patientAge > 65;
        default: return true;
      }
    })();

    const matchesBloodType = !filterBloodType || patient.bloodType === filterBloodType;

    return matchesSearch && matchesGender && matchesAgeRange && matchesBloodType;
  });

  // Архивирование пациента (soft-delete) - использует реальный API
  const archivePatient = useCallback(async (id) => {
    setLoading(true);
    setError(null);

    try {
      const token = tokenManager.getAccessToken();
      if (!token) {
        throw new Error('Токен авторизации не найден');
      }

      const response = await fetch(`${API_BASE}/api/v1/patients/${id}/soft`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Ошибка архивирования пациента' }));
        throw new Error(errorData.detail || `Ошибка ${response.status}`);
      }

      // Обновляем пациента в списке как удаленного
      setPatients(prev => prev.map(patient =>
        patient.id === id
          ? { ...patient, is_deleted: true }
          : patient
      ));
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Восстановление пациента - использует реальный API
  const restorePatient = useCallback(async (id) => {
    setLoading(true);
    setError(null);

    try {
      const token = tokenManager.getAccessToken();
      if (!token) {
        throw new Error('Токен авторизации не найден');
      }

      const response = await fetch(`${API_BASE}/api/v1/patients/${id}/restore`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Ошибка восстановления пациента' }));
        throw new Error(errorData.detail || `Ошибка ${response.status}`);
      }

      // Обновляем пациента в списке как активного
      setPatients(prev => prev.map(patient =>
        patient.id === id
          ? { ...patient, is_deleted: false }
          : patient
      ));
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Загрузка при монтировании
  useEffect(() => {
    loadPatients();
  }, [loadPatients]);

  return {
    patients: filteredPatients,
    allPatients: patients,
    loading,
    error,
    searchTerm,
    setSearchTerm,
    filterGender,
    setFilterGender,
    filterAgeRange,
    setFilterAgeRange,
    filterBloodType,
    setFilterBloodType,
    createPatient,
    updatePatient,
    deletePatient,
    archivePatient,  // Soft-delete
    restorePatient,  // Restore
    refresh: loadPatients,
    calculateAge
  };
};

export default usePatients;
