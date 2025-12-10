import { useState, useEffect, useCallback } from 'react';
import { doctorsService } from '../api/services';
import { api } from '../api/client';

import logger from '../utils/logger';
const useDoctors = () => {
  const [doctors, setDoctors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterSpecialization, setFilterSpecialization] = useState('');
  const [filterDepartment, setFilterDepartment] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  // Загрузка врачей
  const loadDoctors = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await api.get('/admin/doctors');
      if (response.data) {
        setDoctors(Array.isArray(response.data) ? response.data : []);
      }
    } catch (err) {
      logger.error('Ошибка загрузки врачей:', err);
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Создание врача
  const createDoctor = useCallback(async (doctorData) => {
    setLoading(true);
    setError(null);
    
    try {
      // Преобразуем данные формы в формат, ожидаемый бэкендом
      // Сначала нужно создать пользователя, если его нет
      let userId = null;
      
      if (doctorData.email || doctorData.name) {
        try {
          // Создаем пользователя с ролью Doctor
          // Роутер подключен с префиксом /users, а внутри есть эндпоинт /users
          // Полный путь: /api/v1/users/users
          const userCreateUrl = '/users/users';
          logger.log('🔵 Создание пользователя:', userCreateUrl, {
            username: doctorData.email?.split('@')[0] || `doctor_${Date.now()}`,
            email: doctorData.email,
            full_name: doctorData.name,
            role: 'Doctor'
          });
          const userResponse = await api.post(userCreateUrl, {
            username: doctorData.email?.split('@')[0] || `doctor_${Date.now()}`,
            email: doctorData.email,
            full_name: doctorData.name,
            phone: doctorData.phone,
            role: 'Doctor',
            is_active: doctorData.status === 'active',
            password: 'TempPassword123!' // Временный пароль, нужно будет изменить при первом входе
          });
          
          if (userResponse.data?.id || userResponse.data?.user?.id) {
            userId = userResponse.data.id || userResponse.data.user.id;
          }
        } catch (userError) {
          logger.error('Ошибка создания пользователя:', userError);
          // Если пользователь уже существует, пытаемся найти его
          if (userError.response?.status === 400) {
            const errorDetail = userError.response?.data?.detail || '';
            if (errorDetail.includes('уже существует') || errorDetail.includes('already exists')) {
              throw new Error('Пользователь с таким email или username уже существует');
            }
            throw new Error(errorDetail || 'Ошибка создания пользователя');
          }
          throw userError;
        }
      }
      
      // Преобразуем department в specialty (если нужно)
      const specialty = doctorData.department || doctorData.specialization || 'general';
      
      // Создаем врача
      const doctorPayload = {
        user_id: userId,
        specialty: specialty,
        cabinet: null,
        price_default: null,
        start_number_online: 1,
        max_online_per_day: 15,
        active: doctorData.status === 'active' || doctorData.status !== 'inactive'
      };
      
      const response = await api.post('/admin/doctors', doctorPayload);
      
      if (response.data) {
        // Обновляем список врачей
        await loadDoctors();
        return response.data;
      }
      
      throw new Error('Не удалось создать врача');
    } catch (err) {
      logger.error('Ошибка создания врача:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка создания врача';
      setError(err);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [loadDoctors]);

  // Обновление врача
  const updateDoctor = useCallback(async (id, doctorData) => {
    setLoading(true);
    setError(null);
    
    try {
      // Преобразуем данные формы в формат, ожидаемый бэкендом
      const specialty = doctorData.department || doctorData.specialization || 'general';
      
      const doctorPayload = {
        specialty: specialty,
        active: doctorData.status === 'active' || doctorData.status !== 'inactive'
      };
      
      const response = await api.put(`/admin/doctors/${id}`, doctorPayload);
      
      if (response.data) {
        // Обновляем список врачей
        await loadDoctors();
        return response.data;
      }
      
      throw new Error('Не удалось обновить врача');
    } catch (err) {
      logger.error('Ошибка обновления врача:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка обновления врача';
      setError(err);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [loadDoctors]);

  // Удаление врача
  const deleteDoctor = useCallback(async (id) => {
    setLoading(true);
    setError(null);
    
    try {
      await api.delete(`/admin/doctors/${id}`);
      // Обновляем список врачей
      await loadDoctors();
    } catch (err) {
      logger.error('Ошибка удаления врача:', err);
      const errorMessage = err.response?.data?.detail || err.message || 'Ошибка удаления врача';
      setError(err);
      throw new Error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [loadDoctors]);

  // Фильтрация врачей
  const filteredDoctors = doctors.filter(doctor => {
    const doctorName = doctor.user?.full_name || doctor.name || '';
    const doctorEmail = doctor.user?.email || doctor.email || '';
    const doctorSpecialty = doctor.specialty || doctor.specialization || '';
    
    const matchesSearch = !searchTerm || 
      doctorName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      doctorSpecialty.toLowerCase().includes(searchTerm.toLowerCase()) ||
      doctorEmail.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesSpecialization = !filterSpecialization || 
      doctorSpecialty.toLowerCase().includes(filterSpecialization.toLowerCase());
    
    const matchesDepartment = !filterDepartment || doctorSpecialty === filterDepartment;
    const matchesStatus = !filterStatus || (doctor.active ? 'active' : 'inactive') === filterStatus;
    
    return matchesSearch && matchesSpecialization && matchesDepartment && matchesStatus;
  });

  // Загрузка при монтировании
  useEffect(() => {
    loadDoctors();
  }, [loadDoctors]);

  return {
    doctors: filteredDoctors,
    allDoctors: doctors,
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
    refresh: loadDoctors
  };
};

export default useDoctors;
