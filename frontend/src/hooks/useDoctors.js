import { useState, useEffect, useCallback } from 'react';

const useDoctors = () => {
  const [doctors, setDoctors] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterSpecialization, setFilterSpecialization] = useState('');
  const [filterDepartment, setFilterDepartment] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  // Моковые данные для демонстрации
  const mockDoctors = [
    {
      id: 1,
      name: 'Иванов Иван Иванович',
      email: 'ivanov@clinic.uz',
      phone: '+998 90 123 45 67',
      specialization: 'Кардиолог',
      department: 'cardiology',
      experience: 15,
      schedule: 'Пн-Пт 9:00-18:00',
      status: 'active',
      bio: 'Опытный кардиолог с 15-летним стажем. Специализируется на лечении ишемической болезни сердца.',
      createdAt: '2024-01-15',
      patientsCount: 156
    },
    {
      id: 2,
      name: 'Петрова Мария Сергеевна',
      email: 'petrova@clinic.uz',
      phone: '+998 91 234 56 78',
      specialization: 'Дерматолог',
      department: 'dermatology',
      experience: 8,
      schedule: 'Вт-Сб 10:00-19:00',
      status: 'active',
      bio: 'Специалист по кожным заболеваниям и косметологии.',
      createdAt: '2024-01-20',
      patientsCount: 89
    },
    {
      id: 3,
      name: 'Сидоров Сергей Петрович',
      email: 'sidorov@clinic.uz',
      phone: '+998 92 345 67 89',
      specialization: 'Стоматолог',
      department: 'dentistry',
      experience: 12,
      schedule: 'Пн-Сб 8:00-17:00',
      status: 'active',
      bio: 'Стоматолог-хирург, специализируется на имплантации зубов.',
      createdAt: '2024-01-25',
      patientsCount: 203
    },
    {
      id: 4,
      name: 'Козлова Анна Владимировна',
      email: 'kozlova@clinic.uz',
      phone: '+998 93 456 78 90',
      specialization: 'Терапевт',
      department: 'general',
      experience: 20,
      schedule: 'Пн-Пт 8:00-16:00',
      status: 'on_leave',
      bio: 'Врач общей практики с большим опытом работы.',
      createdAt: '2024-02-01',
      patientsCount: 312
    },
    {
      id: 5,
      name: 'Новиков Дмитрий Александрович',
      email: 'novikov@clinic.uz',
      phone: '+998 94 567 89 01',
      specialization: 'Хирург',
      department: 'surgery',
      experience: 18,
      schedule: 'Пн-Пт 7:00-15:00',
      status: 'active',
      bio: 'Опытный хирург, специализируется на лапароскопических операциях.',
      createdAt: '2024-02-05',
      patientsCount: 78
    }
  ];

  // Загрузка врачей
  const loadDoctors = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      setDoctors(mockDoctors);
    } catch (err) {
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
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      const newDoctor = {
        id: Date.now(),
        ...doctorData,
        createdAt: new Date().toISOString().split('T')[0],
        patientsCount: 0
      };
      
      setDoctors(prev => [newDoctor, ...prev]);
      return newDoctor;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Обновление врача
  const updateDoctor = useCallback(async (id, doctorData) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      setDoctors(prev => prev.map(doctor => 
        doctor.id === id 
          ? { ...doctor, ...doctorData }
          : doctor
      ));
      
      return { id, ...doctorData };
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Удаление врача
  const deleteDoctor = useCallback(async (id) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      
      setDoctors(prev => prev.filter(doctor => doctor.id !== id));
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Фильтрация врачей
  const filteredDoctors = doctors.filter(doctor => {
    const matchesSearch = !searchTerm || 
      doctor.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      doctor.specialization.toLowerCase().includes(searchTerm.toLowerCase()) ||
      doctor.email.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesSpecialization = !filterSpecialization || 
      doctor.specialization.toLowerCase().includes(filterSpecialization.toLowerCase());
    
    const matchesDepartment = !filterDepartment || doctor.department === filterDepartment;
    const matchesStatus = !filterStatus || doctor.status === filterStatus;
    
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
