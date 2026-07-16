import { useState, useEffect, useCallback } from 'react';

import { api } from '../api/client';
import logger from '../utils/logger';

const normalizeDoctorPayload = (doctorData) => ({
  user_id: doctorData.userId ? Number(doctorData.userId) : null,
  specialty: doctorData.specialty?.trim() || 'general',
  cabinet: doctorData.cabinet?.trim() || null,
  price_default:
    doctorData.priceDefault === '' || doctorData.priceDefault === null || doctorData.priceDefault === undefined
      ? null
      : Number(doctorData.priceDefault),
  start_number_online:
    doctorData.startNumberOnline === '' || doctorData.startNumberOnline === null || doctorData.startNumberOnline === undefined
      ? 1
      : Number(doctorData.startNumberOnline),
  max_online_per_day:
    doctorData.maxOnlinePerDay === '' || doctorData.maxOnlinePerDay === null || doctorData.maxOnlinePerDay === undefined
      ? 15
      : Number(doctorData.maxOnlinePerDay),
  active: doctorData.active !== false && doctorData.status !== 'inactive',
});

const useDoctors = () => {
  const [doctors, setDoctors] = useState([]);
  const [availableUsers, setAvailableUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterSpecialization, setFilterSpecialization] = useState('');
  const [filterDepartment, setFilterDepartment] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  const loadDoctors = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await api.get('/admin/doctors');
      setDoctors(Array.isArray(response.data) ? response.data : []);
    } catch (err) {
      logger.error('Ошибка загрузки врачей:', err);
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadAvailableUsers = useCallback(async (doctorId: unknown = null) => {
    try {
      const response = await api.get('/admin/doctors/available-users', {
        params: doctorId ? { doctor_id: doctorId } : undefined,
      });
      const items = Array.isArray(response.data) ? response.data : [];
      setAvailableUsers(items);
      return items;
    } catch (err) {
      logger.error('Ошибка загрузки доступных пользователей для врачей:', err);
      setAvailableUsers([]);
      throw err;
    }
  }, []);

  const createDoctor = useCallback(
    async (doctorData) => {
      setLoading(true);
      setError(null);

      try {
        const response = await api.post('/admin/doctors', normalizeDoctorPayload(doctorData));
        await Promise.all([loadDoctors(), loadAvailableUsers()]);
        return response.data;
      } catch (err) {
        logger.error('Ошибка создания врача:', err);
        const errorMessage =
          err.response?.data?.detail || err.message || 'Ошибка создания врача';
        setError(err);
        throw new Error(errorMessage);
      } finally {
        setLoading(false);
      }
    },
    [loadDoctors, loadAvailableUsers]
  );

  const updateDoctor = useCallback(
    async (id, doctorData) => {
      setLoading(true);
      setError(null);

      try {
        const response = await api.put(`/admin/doctors/${id}`, normalizeDoctorPayload(doctorData));
        await Promise.all([loadDoctors(), loadAvailableUsers(id)]);
        return response.data;
      } catch (err) {
        logger.error('Ошибка обновления врача:', err);
        const errorMessage =
          err.response?.data?.detail || err.message || 'Ошибка обновления врача';
        setError(err);
        throw new Error(errorMessage);
      } finally {
        setLoading(false);
      }
    },
    [loadDoctors, loadAvailableUsers]
  );

  const deleteDoctor = useCallback(
    async (id) => {
      setLoading(true);
      setError(null);

      try {
        await api.delete(`/admin/doctors/${id}`);
        await Promise.all([loadDoctors(), loadAvailableUsers()]);
      } catch (err) {
        logger.error('Ошибка удаления врача:', err);
        const errorMessage =
          err.response?.data?.detail || err.message || 'Ошибка удаления врача';
        setError(err);
        throw new Error(errorMessage);
      } finally {
        setLoading(false);
      }
    },
    [loadDoctors, loadAvailableUsers]
  );

  const filteredDoctors = doctors.filter((doctor) => {
    const doctorName = doctor.user?.full_name || doctor.user?.username || '';
    const doctorEmail = doctor.user?.email || '';
    const doctorPhone = doctor.user?.phone || '';
    const doctorSpecialty = doctor.specialty || '';
    const doctorCabinet = doctor.cabinet || '';

    const matchesSearch =
      !searchTerm ||
      doctorName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      doctorSpecialty.toLowerCase().includes(searchTerm.toLowerCase()) ||
      doctorEmail.toLowerCase().includes(searchTerm.toLowerCase()) ||
      doctorPhone.toLowerCase().includes(searchTerm.toLowerCase()) ||
      doctorCabinet.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesSpecialization =
      !filterSpecialization ||
      doctorSpecialty.toLowerCase().includes(filterSpecialization.toLowerCase());

    const matchesDepartment =
      !filterDepartment || doctorSpecialty.toLowerCase() === filterDepartment.toLowerCase();

    const matchesStatus =
      !filterStatus || (doctor.active ? 'active' : 'inactive') === filterStatus;

    return (
      matchesSearch &&
      matchesSpecialization &&
      matchesDepartment &&
      matchesStatus
    );
  });

  useEffect(() => {
    void loadDoctors();
    void loadAvailableUsers();
  }, [loadDoctors, loadAvailableUsers]);

  return {
    doctors: filteredDoctors,
    allDoctors: doctors,
    availableUsers,
    loading,
    error,
    searchTerm,
    setSearchTerm,
    filterSpecialization,
    setFilterSpecialization,
    filterDepartment,
    setFilterDepartment,
    filterStatus,
    setFilterStatus,
    createDoctor,
    updateDoctor,
    deleteDoctor,
    refresh: loadDoctors,
    refreshAvailableUsers: loadAvailableUsers,
  };
};

export default useDoctors;
