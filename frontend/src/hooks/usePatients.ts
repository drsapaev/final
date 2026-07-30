import { useState, useEffect, useCallback } from 'react';

import { api } from '../api/client';  // PR-38 / High-21: centralized axios client
import { buildPatientDocumentFields } from '../utils/patientDocument';
import logger from '../utils/logger';
import type { Patient } from '../types/domain/clinic';
import { getErrorMessage } from '../utils/type-guards';

interface CatchError {
  status?: number;
  response?: { status?: number; data?: unknown };
  message?: string;
}

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
  // TECH-DEBT(g8-usePatients-001): patients state uses ReturnType<typeof transformPatient>
  // inferred shape. Consumers access camelCase fields (firstName, lastName, etc.)
  // which come from transformPatient. Migrating to a typed Patient state requires
  // updating all consumers that access these transformed fields.
  const [patients, setPatients] = useState<ReturnType<typeof transformPatient>[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterGender, setFilterGender] = useState('');
  const [filterAgeRange, setFilterAgeRange] = useState('');
  const [filterBloodType, setFilterBloodType] = useState('');

  // Transform API snake_case → component camelCase.
  // IMPORTANT (audit/phase-1, BS-34): medical fields (allergies, chronic_diseases,
  // blood_type, insurance_number, emergency_contact, emergency_phone, notes)
  // are read from the backend payload, NOT hardcoded to ''. The previous
  // implementation silently wiped these fields on every load/create/update,
  // which caused clinicians to see empty allergy warnings and made filter-by-
  // blood-type impossible. This was a medical-safety defect.
  const transformPatient = (p: Patient) => {
    const raw = p as unknown as Record<string, unknown>;
    return {
      id: p.id,
      firstName: String(raw.first_name ?? ''),
      lastName: String(raw.last_name ?? ''),
      middleName: String(raw.middle_name ?? ''),
      email: String(raw.email ?? ''),
      phone: String(raw.phone ?? ''),
      birthDate: String(raw.birth_date ?? ''),
      gender: raw.sex === 'M' ? 'male' : raw.sex === 'F' ? 'female' : '',
      address: String(raw.address ?? ''),
      passport: String(p.doc_number ?? ''),
      // Medical / identity fields — read with `?? ''` so a missing key
      // collapses to empty string without losing real backend data.
      insuranceNumber: (raw.insurance_number ?? raw.insuranceNumber ?? '') as string,
      emergencyContact: (raw.emergency_contact ?? raw.emergencyContact ?? '') as string,
      emergencyPhone: (raw.emergency_phone ?? raw.emergencyPhone ?? '') as string,
      bloodType: (raw.blood_type ?? raw.bloodType ?? '') as string,
      allergies: (raw.allergies ?? '') as string,
      chronicDiseases: (raw.chronic_diseases ?? raw.chronicDiseases ?? '') as string,
      notes: (raw.notes ?? '') as string,
      createdAt: p.created_at || new Date().toISOString().split('T')[0],
      lastVisit: null,
      visitsCount: 0
    };
  };

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
      const message = getErrorMessage(err) || 'Ошибка загрузки пациентов';
      setError(new Error(message));
      logger.error('Ошибка загрузки пациентов:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Создание пациента
  const createPatient = useCallback(async (patientData: Partial<Patient>) => {
    setLoading(true);
    setError(null);

    try {
      const documentFields = buildPatientDocumentFields(
        patientData.doc_number
      );

      const apiData = {
        last_name: (patientData as unknown as Record<string, unknown>).lastName || patientData.last_name,
        first_name: (patientData as unknown as Record<string, unknown>).firstName || patientData.first_name,
        middle_name: (patientData as unknown as Record<string, unknown>).middleName || patientData.middle_name || null,
        birth_date: (patientData as unknown as Record<string, unknown>).birthDate || patientData.birth_date || null,
        sex: patientData.gender === 'male' ? 'M' : patientData.gender === 'female' ? 'F' : null,
        phone: (patientData as Record<string, unknown>).phone || null,
        email: (patientData as Record<string, unknown>).email || null,
        address: (patientData as Record<string, unknown>).address || null,
        ...documentFields
      };

      // PR-38 / High-21: axios client — no manual fetch/headers/JSON-parse
      const response = await api.post('/patients/', apiData);
      const newPatient = response.data;
      const transformedPatient = transformPatient(newPatient);
      setPatients(prev => [transformedPatient, ...prev]);
      return transformedPatient;
    } catch (err) {
      const message = getErrorMessage(err) || 'Ошибка создания пациента';
      const wrapped = new Error(message);
      (wrapped as CatchError).status = (err as { response?: { status?: number } })?.response?.status;
      (wrapped as CatchError).response = (err as { response?: { status?: number; data?: unknown } })?.response;
      setError(new Error(String(wrapped)));
      throw wrapped;
    } finally {
      setLoading(false);
    }
  }, []);

  // Обновление пациента
  const updatePatient = useCallback(async (id: string | number, patientData: Partial<Patient>) => {
    setLoading(true);
    setError(null);

    try {
      const apiData = {};
      if ((patientData as unknown as Record<string, unknown>).lastName !== undefined) (apiData as Record<string, unknown>).last_name = (patientData as unknown as Record<string, unknown>).lastName;
      if ((patientData as unknown as Record<string, unknown>).firstName !== undefined) (apiData as Record<string, unknown>).first_name = (patientData as unknown as Record<string, unknown>).firstName;
      if ((patientData as unknown as Record<string, unknown>).middleName !== undefined) (apiData as Record<string, unknown>).middle_name = (patientData as unknown as Record<string, unknown>).middleName;
      if (patientData.birthDate !== undefined) (apiData as Record<string, unknown>).birth_date = patientData.birthDate;
      if (patientData.gender !== undefined) (apiData as Record<string, unknown>).sex = patientData.gender === 'male' ? 'M' : patientData.gender === 'female' ? 'F' : null;
      if ((patientData as Record<string, unknown>).phone !== undefined) (apiData as Record<string, unknown>).phone = (patientData as Record<string, unknown>).phone;
      if ((patientData as Record<string, unknown>).email !== undefined) (apiData as Record<string, unknown>).email = (patientData as Record<string, unknown>).email;
      if (patientData.doc_number !== undefined) {
        Object.assign(
          apiData,
          buildPatientDocumentFields(patientData.doc_number)
        );
      }
      if ((patientData as Record<string, unknown>).address !== undefined) (apiData as Record<string, unknown>).address = (patientData as Record<string, unknown>).address;

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
      const message = getErrorMessage(err) || 'Ошибка обновления пациента';
      const wrapped = new Error(message);
      (wrapped as CatchError).status = (err as { response?: { status?: number } })?.response?.status;
      (wrapped as CatchError).response = (err as { response?: { status?: number; data?: unknown } })?.response;
      setError(new Error(String(wrapped)));
      throw wrapped;
    } finally {
      setLoading(false);
    }
  }, []);

  // Удаление пациента
  const deletePatient = useCallback(async (id: string | number) => {
    setLoading(true);
    setError(null);

    try {
      // PR-38 / High-21: axios client
      await api.delete(`/patients/${id}`);
      setPatients(prev => prev.filter(patient => patient.id !== id));
    } catch (err) {
      const message = getErrorMessage(err) || 'Ошибка удаления пациента';
      const wrapped = new Error(message);
      (wrapped as CatchError).status = (err as { response?: { status?: number } })?.response?.status;
      (wrapped as CatchError).response = (err as { response?: { status?: number; data?: unknown } })?.response;
      setError(new Error(String(wrapped)));
      throw wrapped;
    } finally {
      setLoading(false);
    }
  }, []);

  // Вычисление возраста
  const calculateAge = (birthDate: string) => {
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
      String((patient as Record<string, unknown>).firstName).toLowerCase().includes(String(searchTerm).toLowerCase()) ||
      String((patient as Record<string, unknown>).lastName).toLowerCase().includes(String(searchTerm).toLowerCase()) ||
      String((patient as Record<string, unknown>).middleName).toLowerCase().includes(String(searchTerm).toLowerCase()) ||
      String((patient as Record<string, unknown>).phone).includes(String(searchTerm)) ||
      String((patient as Record<string, unknown>).email).toLowerCase().includes(String(searchTerm).toLowerCase()) ||
      String((patient as Record<string, unknown>).passport).toLowerCase().includes(String(searchTerm).toLowerCase());

    const matchesGender = !filterGender || patient.gender === filterGender;

    const patientAge = calculateAge(String(patient.birthDate));
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
  const archivePatient = useCallback(async (id: string | number) => {
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
      const message = getErrorMessage(err) || 'Ошибка архивирования пациента';
      const wrapped = new Error(message);
      (wrapped as CatchError).status = (err as { response?: { status?: number } })?.response?.status;
      (wrapped as CatchError).response = (err as { response?: { status?: number; data?: unknown } })?.response;
      setError(new Error(String(wrapped)));
      throw wrapped;
    } finally {
      setLoading(false);
    }
  }, []);

  // Восстановление пациента
  const restorePatient = useCallback(async (id: string | number) => {
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
      const message = getErrorMessage(err) || 'Ошибка восстановления пациента';
      const wrapped = new Error(message);
      (wrapped as CatchError).status = (err as { response?: { status?: number } })?.response?.status;
      (wrapped as CatchError).response = (err as { response?: { status?: number; data?: unknown } })?.response;
      setError(new Error(String(wrapped)));
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
