import { useState, useEffect, useCallback } from 'react';

const useAppointments = () => {
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterDate, setFilterDate] = useState('');
  const [filterDoctor, setFilterDoctor] = useState('');

  // Моковые данные для демонстрации
  const mockAppointments = [
    {
      id: 1,
      patientId: 1,
      doctorId: 1,
      patientName: 'Иванова Анна Сергеевна',
      doctorName: 'Иванов Иван Иванович',
      doctorSpecialization: 'Кардиолог',
      appointmentDate: '2024-02-01',
      appointmentTime: '10:00',
      duration: 30,
      status: 'confirmed',
      reason: 'Боли в области сердца, одышка при физической нагрузке',
      notes: 'Пациентка жалуется на периодические боли в груди',
      phone: '+998 90 123 45 67',
      email: 'anna.ivanova@email.com',
      createdAt: '2024-01-25',
      updatedAt: '2024-01-25'
    },
    {
      id: 2,
      patientId: 2,
      doctorId: 2,
      patientName: 'Петров Дмитрий Александрович',
      doctorName: 'Петрова Мария Сергеевна',
      doctorSpecialization: 'Дерматолог',
      appointmentDate: '2024-02-01',
      appointmentTime: '14:30',
      duration: 45,
      status: 'paid',
      reason: 'Кожная сыпь на руках и ногах',
      notes: 'Сыпь появилась неделю назад, сопровождается зудом',
      phone: '+998 91 234 56 78',
      email: 'dmitry.petrov@email.com',
      createdAt: '2024-01-26',
      updatedAt: '2024-01-27'
    },
    {
      id: 3,
      patientId: 3,
      doctorId: 3,
      patientName: 'Сидорова Мария Ивановна',
      doctorName: 'Сидоров Сергей Петрович',
      doctorSpecialization: 'Стоматолог',
      appointmentDate: '2024-02-02',
      appointmentTime: '09:00',
      duration: 60,
      status: 'in_visit',
      reason: 'Плановый осмотр и чистка зубов',
      notes: 'Регулярный профилактический визит',
      phone: '+998 92 345 67 89',
      email: 'maria.sidorova@email.com',
      createdAt: '2024-01-28',
      updatedAt: '2024-02-02'
    },
    {
      id: 4,
      patientId: 4,
      doctorId: 1,
      patientName: 'Козлов Алексей Владимирович',
      doctorName: 'Иванов Иван Иванович',
      doctorSpecialization: 'Кардиолог',
      appointmentDate: '2024-02-02',
      appointmentTime: '11:15',
      duration: 30,
      status: 'completed',
      reason: 'Контрольный осмотр после операции',
      notes: 'Состояние стабильное, рекомендовано продолжать лечение',
      phone: '+998 93 456 78 90',
      email: 'alexey.kozlov@email.com',
      createdAt: '2024-01-29',
      updatedAt: '2024-02-02'
    },
    {
      id: 5,
      patientId: 5,
      doctorId: 4,
      patientName: 'Новикова Елена Дмитриевна',
      doctorName: 'Козлова Анна Владимировна',
      doctorSpecialization: 'Терапевт',
      appointmentDate: '2024-02-03',
      appointmentTime: '15:00',
      duration: 45,
      status: 'pending',
      reason: 'Беременность 24 недели - плановый осмотр',
      notes: 'Требуется особое внимание к состоянию плода',
      phone: '+998 94 567 89 01',
      email: 'elena.novikova@email.com',
      createdAt: '2024-01-30',
      updatedAt: '2024-01-30'
    },
    {
      id: 6,
      patientId: 2,
      doctorId: 5,
      patientName: 'Петров Дмитрий Александрович',
      doctorName: 'Новиков Дмитрий Александрович',
      doctorSpecialization: 'Хирург',
      appointmentDate: '2024-01-30',
      appointmentTime: '16:00',
      duration: 90,
      status: 'cancelled',
      reason: 'Консультация по поводу операции',
      notes: 'Пациент отменил запись по личным обстоятельствам',
      phone: '+998 91 234 56 78',
      email: 'dmitry.petrov@email.com',
      createdAt: '2024-01-28',
      updatedAt: '2024-01-30'
    }
  ];

  // Загрузка записей
  const loadAppointments = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      setAppointments(mockAppointments);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Создание записи
  const createAppointment = useCallback(async (appointmentData) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      const newAppointment = {
        id: Date.now(),
        ...appointmentData,
        createdAt: new Date().toISOString().split('T')[0],
        updatedAt: new Date().toISOString().split('T')[0]
      };
      
      setAppointments(prev => [newAppointment, ...prev]);
      return newAppointment;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Обновление записи
  const updateAppointment = useCallback(async (id, appointmentData) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      setAppointments(prev => prev.map(appointment => 
        appointment.id === id 
          ? { ...appointment, ...appointmentData, updatedAt: new Date().toISOString().split('T')[0] }
          : appointment
      ));
      
      return { id, ...appointmentData };
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Удаление записи
  const deleteAppointment = useCallback(async (id) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      
      setAppointments(prev => prev.filter(appointment => appointment.id !== id));
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Фильтрация записей
  const filteredAppointments = appointments.filter(appointment => {
    const matchesSearch = !searchTerm || 
      appointment.patientName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      appointment.doctorName.toLowerCase().includes(searchTerm.toLowerCase()) ||
      appointment.reason.toLowerCase().includes(searchTerm.toLowerCase()) ||
      appointment.phone?.includes(searchTerm) ||
      appointment.email?.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = !filterStatus || appointment.status === filterStatus;
    const matchesDate = !filterDate || appointment.appointmentDate === filterDate;
    const matchesDoctor = !filterDoctor || appointment.doctorId === parseInt(filterDoctor);
    
    return matchesSearch && matchesStatus && matchesDate && matchesDoctor;
  });

  // Получение статистики по статусам
  const getStatusStats = () => {
    const stats = {
      pending: 0,
      confirmed: 0,
      paid: 0,
      in_visit: 0,
      completed: 0,
      cancelled: 0,
      no_show: 0
    };
    
    appointments.forEach(appointment => {
      stats[appointment.status] = (stats[appointment.status] || 0) + 1;
    });
    
    return stats;
  };

  // Получение записей на сегодня
  const getTodayAppointments = () => {
    const today = new Date().toISOString().split('T')[0];
    return appointments.filter(appointment => appointment.appointmentDate === today);
  };

  // Получение записей на завтра
  const getTomorrowAppointments = () => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split('T')[0];
    return appointments.filter(appointment => appointment.appointmentDate === tomorrowStr);
  };

  // Загрузка при монтировании
  useEffect(() => {
    loadAppointments();
  }, [loadAppointments]);

  return {
    appointments: filteredAppointments,
    allAppointments: appointments,
    loading,
    error,
    searchTerm,
    setSearchTerm,
    filterStatus,
    setFilterStatus,
    filterDate,
    setFilterDate,
    filterDoctor,
    setFilterDoctor,
    createAppointment,
    updateAppointment,
    deleteAppointment,
    refresh: loadAppointments,
    getStatusStats,
    getTodayAppointments,
    getTomorrowAppointments
  };
};

export default useAppointments;
