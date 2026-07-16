// @ts-nocheck — Phase 2: file converted .js → .ts but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useState, useEffect, useCallback } from 'react';

import { api } from '../api/client';  // PR-38 / High-21: centralized axios client
import { buildPatientDocumentFields } from '../utils/patientDocument';
import logger from '../utils/logger';

/**
 * usePatients hook — patient CRUD operations.
 *
 * PR-38 / High-21: Migrated from raw fetch() to the centralized axios client.
 * Previously: 6 raw fetch() calls with duplicated URL/header/JSON-parse/error
 * handling. Now: all HTTP goes through `api` from api/client.js, which
 * handles auth/CSRF/refresh-token interceptors centrally.
 *
 * The api/patients.js module provides higher-level wrappers (getPatient,
 * createPatient, updatePatient, etc.) but this hook needs finer control
 * over the response transformation (snake_case → camelCase), so it calls
 * the axios client directly with the same `/patients/*` paths.
 */

const usePatients = () => {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterGender, setFilterGender] = useState('');
  const [filterAgeRange, setFilterAgeRange] = useState('');
  const [filterBloodType, setFilterBloodType] = useState('');

  // Transform API snake_case → component camelCase
  const transformPatient = (p) => ({
    id: p.id,
    firstName: p.first_name,
    lastName: p.last_name,
    middleName: p.middle_name,
    email: p.email || '',
    phone: p.phone || '',
    birthDate: p.birth_date || '',
    gender: p.sex === 'M' ? 'male' : p.sex === 'F' ? 'female' : '',
    address: p.address || '',
    passport: p.doc_number || '',
    insuranceNumber: '',
    emergencyContact: '',
    emergencyPhone: '',
    bloodType: '',
    allergies: '',
    chronicDiseases: '',
    notes: '',
    createdAt: p.created_at || new Date().toISOString().split('T')[0],
    lastVisit: null,
    visitsCount: 0
  });

  // Загрузка пациентов
  const loadPatients = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // PR-38 / High-21: axios client handles auth/CSRF/refresh centrally.
      const response = await api.get('/patients/?limit=1000');
      const data = response.data;
      const transformedPatients = data.map(transformPatient);
      setPatients(transformedPatients);
    } catch (err) {
      const message = err?.response?.data?.detail || err?.message || 'Ошибка загрузки пациентов';
      setError(new Error(message));
      logger.error('Ошибка загрузки пациентов:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Создание пациента
  const createPatient = useCallback(async (patientData) => {
    setLoading(true);
    setError(null);

    try {
      const documentFields = buildPatientDocumentFields(
        patientData.passport ?? patientData.doc_number
      );

      const apiData = {
        last_name: patientData.lastName || patientData.last_name,
        first_name: patientData.firstName || patientData.first_name,
        middle_name: patientData.middleName || patientData.middle_name || null,
        birth_date: patientData.birthDate || patientData.birth_date || null,
        sex: patientData.gender === 'male' ? 'M' : patientData.gender === 'female' ? 'F' : null,
        phone: patientData.phone || null,
        email: patientData.email || null,
        address: patientData.address || null,
        ...documentFields
      };

      // PR-38 / High-21: axios client — no manual fetch/headers/JSON-parse
      const response = await api.post('/patients/', apiData);
      const newPatient = response.data;
      const transformedPatient = transformPatient(newPatient);
      setPatients(prev => [transformedPatient, ...prev]);
      return transformedPatient;
    } catch (err) {
      const message = err?.response?.data?.detail || err?.message || 'Ошибка создания пациента';
      const wrapped = new Error(message);
      wrapped.status = err?.response?.status;
      wrapped.response = err?.response;
      setError(wrapped);
      throw wrapped;
    } finally {
      setLoading(false);
    }
  }, []);

  // Обновление пациента
  const updatePatient = useCallback(async (id, patientData) => {
    setLoading(true);
    setError(null);

    try {
      const apiData = {};
      if (patientData.lastName !== undefined) apiData.last_name = patientData.lastName;
      if (patientData.firstName !== undefined) apiData.first_name = patientData.firstName;
      if (patientData.middleName !== undefined) apiData.middle_name = patientData.middleName;
      if (patientData.birthDate !== undefined) apiData.birth_date = patientData.birthDate;
      if (patientData.gender !== undefined) apiData.sex = patientData.gender === 'male' ? 'M' : patientData.gender === 'female' ? 'F' : null;
      if (patientData.phone !== undefined) apiData.phone = patientData.phone;
      if (patientData.email !== undefined) apiData.email = patientData.email;
      if (patientData.passport !== undefined || patientData.doc_number !== undefined) {
        Object.assign(
          apiData,
          buildPatientDocumentFields(patientData.passport ?? patientData.doc_number)
        );
      }
      if (patientData.address !== undefined) apiData.address = patientData.address;

      // PR-38 / High-21: axios client
      const response = await api.put(`/patients/${id}`, apiData);
      const updatedPatient = response.data;
      const transformedPatient = transformPatient(updatedPatient);
      // Transform returns the basic fields; preserve any extra fields from the
      // existing patient (e.g., is_deleted flag) via spread.
      setPatients(prev => prev.map(patient =>
        patient.id === id
          ? { ...patient, ...transformedPatient }
          : patient
      ));
      return transformedPatient;
    } catch (err) {
      const message = err?.response?.data?.detail || err?.message || 'Ошибка обновления пациента';
      const wrapped = new Error(message);
      wrapped.status = err?.response?.status;
      wrapped.response = err?.response;
      setError(wrapped);
      throw wrapped;
    } finally {
      setLoading(false);
    }
  }, []);

  // Удаление пациента
  const deletePatient = useCallback(async (id) => {
    setLoading(true);
    setError(null);

    try {
      // PR-38 / High-21: axios client
      await api.delete(`/patients/${id}`);
      setPatients(prev => prev.filter(patient => patient.id !== id));
    } catch (err) {
      const message = err?.response?.data?.detail || err?.message || 'Ошибка удаления пациента';
      const wrapped = new Error(message);
      wrapped.status = err?.response?.status;
      wrapped.response = err?.response;
      setError(wrapped);
      throw wrapped;
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

  // Архивирование пациента (soft-delete)
  const archivePatient = useCallback(async (id) => {
    setLoading(true);
    setError(null);

    try {
      // PR-38 / High-21: axios client
      await api.delete(`/patients/${id}/soft`);
      setPatients(prev => prev.map(patient =>
        patient.id === id
          ? { ...patient, is_deleted: true }
          : patient
      ));
    } catch (err) {
      const message = err?.response?.data?.detail || err?.message || 'Ошибка архивирования пациента';
      const wrapped = new Error(message);
      wrapped.status = err?.response?.status;
      wrapped.response = err?.response;
      setError(wrapped);
      throw wrapped;
    } finally {
      setLoading(false);
    }
  }, []);

  // Восстановление пациента
  const restorePatient = useCallback(async (id) => {
    setLoading(true);
    setError(null);

    try {
      // PR-38 / High-21: axios client
      await api.post(`/patients/${id}/restore`);
      setPatients(prev => prev.map(patient =>
        patient.id === id
          ? { ...patient, is_deleted: false }
          : patient
      ));
    } catch (err) {
      const message = err?.response?.data?.detail || err?.message || 'Ошибка восстановления пациента';
      const wrapped = new Error(message);
      wrapped.status = err?.response?.status;
      wrapped.response = err?.response;
      setError(wrapped);
      throw wrapped;
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
    archivePatient,
    restorePatient,
    refresh: loadPatients,
    calculateAge
  };
};

export default usePatients;
