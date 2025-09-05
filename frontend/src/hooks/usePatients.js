import { useState, useEffect, useCallback } from 'react';

const usePatients = () => {
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterGender, setFilterGender] = useState('');
  const [filterAgeRange, setFilterAgeRange] = useState('');
  const [filterBloodType, setFilterBloodType] = useState('');

  // Моковые данные для демонстрации
  const mockPatients = [
    {
      id: 1,
      firstName: 'Анна',
      lastName: 'Иванова',
      middleName: 'Сергеевна',
      email: 'anna.ivanova@email.com',
      phone: '+998 90 123 45 67',
      birthDate: '1985-03-15',
      gender: 'female',
      address: 'г. Ташкент, ул. Навои, д. 15',
      passport: 'AA1234567',
      insuranceNumber: '12345678901234',
      emergencyContact: 'Иванов Сергей Петрович',
      emergencyPhone: '+998 91 234 56 78',
      bloodType: 'A+',
      allergies: 'Пенициллин',
      chronicDiseases: 'Гипертония',
      notes: 'Пациентка регулярно принимает лекарства от давления',
      createdAt: '2024-01-10',
      lastVisit: '2024-01-20',
      visitsCount: 5
    },
    {
      id: 2,
      firstName: 'Дмитрий',
      lastName: 'Петров',
      middleName: 'Александрович',
      email: 'dmitry.petrov@email.com',
      phone: '+998 91 234 56 78',
      birthDate: '1978-07-22',
      gender: 'male',
      address: 'г. Ташкент, ул. Амира Темура, д. 42',
      passport: 'AB9876543',
      insuranceNumber: '98765432109876',
      emergencyContact: 'Петрова Елена Владимировна',
      emergencyPhone: '+998 92 345 67 89',
      bloodType: 'O+',
      allergies: null,
      chronicDiseases: null,
      notes: 'Спортсмен, регулярно проходит медосмотры',
      createdAt: '2024-01-12',
      lastVisit: '2024-01-18',
      visitsCount: 3
    },
    {
      id: 3,
      firstName: 'Мария',
      lastName: 'Сидорова',
      middleName: 'Ивановна',
      email: 'maria.sidorova@email.com',
      phone: '+998 92 345 67 89',
      birthDate: '1992-11-08',
      gender: 'female',
      address: 'г. Ташкент, ул. Чилонзар, д. 8',
      passport: 'AC4567890',
      insuranceNumber: '45678901234567',
      emergencyContact: 'Сидоров Иван Петрович',
      emergencyPhone: '+998 93 456 78 90',
      bloodType: 'B+',
      allergies: 'Пыльца, шерсть животных',
      chronicDiseases: 'Астма',
      notes: 'Требует особого внимания к дыхательной системе',
      createdAt: '2024-01-15',
      lastVisit: '2024-01-22',
      visitsCount: 8
    },
    {
      id: 4,
      firstName: 'Алексей',
      lastName: 'Козлов',
      middleName: 'Владимирович',
      email: 'alexey.kozlov@email.com',
      phone: '+998 93 456 78 90',
      birthDate: '1965-05-30',
      gender: 'male',
      address: 'г. Ташкент, ул. Мирзо Улугбека, д. 25',
      passport: 'AD7890123',
      insuranceNumber: '78901234567890',
      emergencyContact: 'Козлова Наталья Сергеевна',
      emergencyPhone: '+998 94 567 89 01',
      bloodType: 'AB+',
      allergies: 'Морепродукты',
      chronicDiseases: 'Диабет 2 типа',
      notes: 'Инсулинозависимый диабет, регулярный контроль сахара',
      createdAt: '2024-01-18',
      lastVisit: '2024-01-25',
      visitsCount: 12
    },
    {
      id: 5,
      firstName: 'Елена',
      lastName: 'Новикова',
      middleName: 'Дмитриевна',
      email: 'elena.novikova@email.com',
      phone: '+998 94 567 89 01',
      birthDate: '1988-09-12',
      gender: 'female',
      address: 'г. Ташкент, ул. Шота Руставели, д. 33',
      passport: 'AE0123456',
      insuranceNumber: '01234567890123',
      emergencyContact: 'Новиков Андрей Сергеевич',
      emergencyPhone: '+998 95 678 90 12',
      bloodType: 'O-',
      allergies: null,
      chronicDiseases: null,
      notes: 'Беременность 24 недели, требует особого наблюдения',
      createdAt: '2024-01-20',
      lastVisit: '2024-01-28',
      visitsCount: 6
    }
  ];

  // Загрузка пациентов
  const loadPatients = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      setPatients(mockPatients);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Создание пациента
  const createPatient = useCallback(async (patientData) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      const newPatient = {
        id: Date.now(),
        ...patientData,
        createdAt: new Date().toISOString().split('T')[0],
        lastVisit: null,
        visitsCount: 0
      };
      
      setPatients(prev => [newPatient, ...prev]);
      return newPatient;
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Обновление пациента
  const updatePatient = useCallback(async (id, patientData) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      setPatients(prev => prev.map(patient => 
        patient.id === id 
          ? { ...patient, ...patientData }
          : patient
      ));
      
      return { id, ...patientData };
    } catch (err) {
      setError(err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  // Удаление пациента
  const deletePatient = useCallback(async (id) => {
    setLoading(true);
    setError(null);
    
    try {
      // Имитация API запроса
      await new Promise(resolve => setTimeout(resolve, 500));
      
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
    refresh: loadPatients,
    calculateAge
  };
};

export default usePatients;
