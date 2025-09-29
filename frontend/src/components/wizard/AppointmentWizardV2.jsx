import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { 
  Search, 
  Phone, 
  Plus, 
  Minus, 
  X, 
  Stethoscope, 
  Check, 
  ArrowLeft, 
  ArrowRight, 
  Trash2, 
  AlertCircle,
  ShoppingCart,
  Grid,
  List,
  ChevronDown
} from 'lucide-react';
import { toast } from 'react-toastify';
import ModernDialog from '../dialogs/ModernDialog';
// Импорты PaymentClick и PaymentPayMe убраны
import './AppointmentWizardV2.css';
import './AppointmentWizardV2-step2.css';
import './AppointmentWizardV2-compact.css';

const API_BASE = '/api/v1';

const AppointmentWizardV2 = ({ 
  isOpen, 
  onClose, 
  onComplete,
  isProcessing = false,
  setIsProcessing = () => {} // Дефолтная функция-заглушка
}) => {
  // Состояние мастера
  const [currentStep, setCurrentStep] = useState(1);
  
  // Данные мастера
  const [wizardData, setWizardData] = useState({
    patient: {
      id: null,
      fio: '',
      birth_date: '',
      phone: '',
      address: ''
    },
    cart: {
      items: [],
      discount_mode: 'none', // none|repeat|benefit
      all_free: false,
      notes: ''
    },
    payment: {
      method: 'cash', // Всегда наличные по умолчанию
      total_amount: 0
    }
  });
  
  // Состояние UI
  const [errors, setErrors] = useState({});
  const [patientSuggestions, setPatientSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [searchTimeout, setSearchTimeout] = useState(null);
  const [servicesData, setServicesData] = useState([]);
  const [doctorsData, setDoctorsData] = useState([]);
  const [filteredServices, setFilteredServices] = useState([]);
  const [showAllServices, setShowAllServices] = useState(false);
  const [formattedBirthDate, setFormattedBirthDate] = useState('');
  
  // Состояние онлайн оплаты убрано
  
  // Refs
  const fioRef = useRef(null);
  const phoneRef = useRef(null);
  
  // Общее количество шагов
  const totalSteps = 2;
  
  // ===================== АВТОСОХРАНЕНИЕ =====================
  
  const DRAFT_KEY = 'appointment_wizard_draft';
  const DRAFT_TTL = 48 * 60 * 60 * 1000; // 48 часов
  
  // Загрузка черновика
  useEffect(() => {
    if (isOpen) {
      const savedDraft = localStorage.getItem(DRAFT_KEY);
      if (savedDraft) {
        try {
          const draft = JSON.parse(savedDraft);
          const now = Date.now();
          
          if (draft.timestamp && (now - draft.timestamp) < DRAFT_TTL) {
            // Черновик актуален
            setWizardData(prev => ({
              ...prev,
              ...draft.data
            }));
            toast.success('Загружен сохранённый черновик');
          } else {
            // Черновик устарел
            localStorage.removeItem(DRAFT_KEY);
          }
        } catch (e) {
          console.warn('Ошибка загрузки черновика:', e);
          localStorage.removeItem(DRAFT_KEY);
        }
      }
    }
  }, [isOpen]);
  
  // Автосохранение черновика
  useEffect(() => {
    if (isOpen && (wizardData.patient.fio || wizardData.cart.items.length > 0)) {
      const draft = {
        timestamp: Date.now(),
        data: wizardData
      };
      localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    }
  }, [wizardData, isOpen]);
  
  // Очистка черновика
  const clearDraft = () => {
    localStorage.removeItem(DRAFT_KEY);
    setWizardData({
      patient: { id: null, fio: '', birth_date: '', phone: '', address: '' },
      cart: { items: [], discount_mode: 'none', all_free: false, notes: '' },
      payment: { method: 'cash', total_amount: 0 }
    });
    setCurrentStep(1);
    toast.success('Черновик очищен');
  };
  
  // ===================== МАСКИ ВВОДА =====================
  
  const formatPhoneNumber = (value) => {
    // Убираем все символы кроме цифр
    const digits = value.replace(/\D/g, '');
    
    // Ограничиваем до 12 цифр (998 + 9 цифр номера)
    const limitedDigits = digits.slice(0, 12);
    
    // Форматируем как +998 XX XXX XX XX
    if (limitedDigits.length === 0) return '';
    if (limitedDigits.length <= 3) return `+${limitedDigits}`;
    if (limitedDigits.length <= 5) return `+${limitedDigits.slice(0, 3)} ${limitedDigits.slice(3)}`;
    if (limitedDigits.length <= 8) return `+${limitedDigits.slice(0, 3)} ${limitedDigits.slice(3, 5)} ${limitedDigits.slice(5)}`;
    if (limitedDigits.length <= 10) return `+${limitedDigits.slice(0, 3)} ${limitedDigits.slice(3, 5)} ${limitedDigits.slice(5, 8)} ${limitedDigits.slice(8)}`;
    return `+${limitedDigits.slice(0, 3)} ${limitedDigits.slice(3, 5)} ${limitedDigits.slice(5, 8)} ${limitedDigits.slice(8, 10)} ${limitedDigits.slice(10)}`;
  };
  
  const formatBirthDate = (value) => {
    // Убираем все символы кроме цифр
    const digits = value.replace(/\D/g, '');
    
    // Ограничиваем до 8 цифр (ДДММГГГГ)
    const limitedDigits = digits.slice(0, 8);
    
    // Форматируем как ДД.ММ.ГГГГ
    if (limitedDigits.length === 0) return '';
    if (limitedDigits.length <= 2) return limitedDigits;
    if (limitedDigits.length <= 4) return `${limitedDigits.slice(0, 2)}.${limitedDigits.slice(2)}`;
    return `${limitedDigits.slice(0, 2)}.${limitedDigits.slice(2, 4)}.${limitedDigits.slice(4)}`;
  };
  
  const convertDateToISO = (dateStr) => {
    // Конвертируем ДД.ММ.ГГГГ в ГГГГ-ММ-ДД
    if (!dateStr || dateStr.length !== 10) return '';
    const [day, month, year] = dateStr.split('.');
    if (!day || !month || !year || year.length !== 4) return '';
    return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
  };
  
  const convertDateFromISO = (isoStr) => {
    // Конвертируем ГГГГ-ММ-ДД в ДД.ММ.ГГГГ
    if (!isoStr) return '';
    const [year, month, day] = isoStr.split('-');
    if (!year || !month || !day) return '';
    return `${day}.${month}.${year}`;
  };

  // ===================== ПОИСК ПАЦИЕНТОВ =====================
  
  const searchPatients = useCallback(async (query) => {
    if (!query || query.length < 2) {
      setPatientSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    
    try {
      const response = await fetch(`${API_BASE}/patients/?q=${encodeURIComponent(query)}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        const data = await response.json();
        
        // Сортировка по приоритету: телефон > точное ФИО > частичное ФИО
        const sorted = data.sort((a, b) => {
          const queryLower = query.toLowerCase();
          
          // Приоритет 1: точное совпадение телефона
          if (a.phone === query) return -1;
          if (b.phone === query) return 1;
          
          // Приоритет 2: точное совпадение ФИО
          if (a.fio.toLowerCase() === queryLower) return -1;
          if (b.fio.toLowerCase() === queryLower) return 1;
          
          // Приоритет 3: частичное совпадение ФИО
          const aMatch = a.fio.toLowerCase().includes(queryLower);
          const bMatch = b.fio.toLowerCase().includes(queryLower);
          
          if (aMatch && !bMatch) return -1;
          if (!aMatch && bMatch) return 1;
          
          return 0;
        });
        
        setPatientSuggestions(sorted.slice(0, 10)); // Максимум 10 результатов
        setShowSuggestions(true);
      }
    } catch (error) {
      console.error('Ошибка поиска пациентов:', error);
    }
  }, []);
  
  const handlePatientSearch = (value) => {
    setWizardData(prev => ({
      ...prev,
      patient: { ...prev.patient, fio: value }
    }));
    
    // Дебаунс поиска
    if (searchTimeout) clearTimeout(searchTimeout);
    const timeout = setTimeout(() => searchPatients(value), 300);
    setSearchTimeout(timeout);
  };
  
  const selectPatient = (patient) => {
    // Парсинг ФИО
    const nameParts = patient.fio.trim().split(' ');
    const lastName = nameParts[0] || '';
    const firstName = nameParts[1] || '';
    const middleName = nameParts.slice(2).join(' ') || '';
    
    setWizardData(prev => ({
      ...prev,
      patient: {
        id: patient.id,
        fio: patient.fio,
        birth_date: patient.birth_date || '',
        phone: patient.phone || '',
        address: patient.address || '',
        // Сохраняем разобранное ФИО для создания нового пациента
        lastName,
        firstName,
        middleName
      }
    }));
    
    // Обновляем отформатированную дату
    setFormattedBirthDate(convertDateFromISO(patient.birth_date));
    setShowSuggestions(false);
    setErrors(prev => ({ ...prev, fio: null }));
  };
  
  const handlePhoneChange = (value) => {
    const formatted = formatPhoneNumber(value);
    setWizardData(prev => ({
      ...prev,
      patient: { ...prev.patient, phone: formatted }
    }));
  };
  
  const handleBirthDateChange = (value) => {
    const formatted = formatBirthDate(value);
    setFormattedBirthDate(formatted);
    
    // Конвертируем в ISO формат для сохранения
    const isoDate = convertDateToISO(formatted);
    setWizardData(prev => ({
      ...prev,
      patient: { ...prev.patient, birth_date: isoDate }
    }));
  };
  
  // ===================== ЗАГРУЗКА ДАННЫХ =====================
  
  useEffect(() => {
    if (isOpen) {
      loadServices();
      loadDoctors();
    }
  }, [isOpen]);
  
  const loadServices = async () => {
    try {
      const response = await fetch(`${API_BASE}/registrar/services`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        const data = await response.json();
        
        // Извлекаем все услуги из групп
        let allServices = [];
        if (data.services_by_group) {
          Object.values(data.services_by_group).forEach(groupServices => {
            if (Array.isArray(groupServices)) {
              allServices = allServices.concat(groupServices);
            }
          });
        }
        
        setServicesData(allServices);
        filterServices(allServices, wizardData.cart.items);
      }
    } catch (error) {
      console.error('Ошибка загрузки услуг:', error);
    }
  };
  
  const loadDoctors = async () => {
    try {
      const response = await fetch(`${API_BASE}/registrar/doctors`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        }
      });
      if (response.ok) {
        const data = await response.json();
        setDoctorsData(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки врачей:', error);
    }
  };
  
  // Фильтрация услуг по выбранным врачам
  const filterServices = (allServices, cartItems) => {
    if (!showAllServices) {
      // Если корзина пуста - показываем только основные консультации
      if (cartItems.length === 0) {
        const basicServices = allServices.filter(service => 
          service.name.toLowerCase().includes('консультация') ||
          service.service_code === 'K01' || // Консультация кардиолога
          service.service_code === 'D01' || // Консультация дерматолога  
          service.service_code === 'S01'    // Консультация стоматолога
        );
        setFilteredServices(basicServices);
        return;
      }
      
      // Если в корзине есть услуги - показываем только основные услуги выбранных врачей
      const selectedDoctorIds = [...new Set(cartItems.map(item => item.doctor_id).filter(Boolean))];
      
      if (selectedDoctorIds.length > 0) {
        const filtered = [];
        
        selectedDoctorIds.forEach(doctorId => {
          const doctor = doctorsData.find(d => d.id === doctorId);
          if (doctor) {
            const categoryCode = getDoctorCategoryCode(doctor.specialty);
            
            // Показываем только основные услуги каждого врача (максимум 5-6 услуг)
            const doctorServices = allServices.filter(service => 
              service.category_code === categoryCode && service.requires_doctor
            ).slice(0, 6); // Ограничиваем до 6 услуг на врача
            
            filtered.push(...doctorServices);
          }
        });
        
        // Добавляем основные лабораторные (без врача) - только самые популярные
        const basicLab = allServices.filter(service => 
          !service.requires_doctor && service.category_code === 'L' && (
            service.service_code === 'L01' || // Общий анализ крови
            service.service_code === 'L11' || // Глюкоза
            service.service_code === 'L25' || // Общий анализ мочи
            service.service_code === 'L30' || // HBsAg
            service.service_code === 'L31' || // HCV
            service.service_code === 'L32'    // HIV
          )
        );
        
        filtered.push(...basicLab);
        setFilteredServices(filtered);
        return;
      }
    }
    
    setFilteredServices(allServices);
  };
  
  const getDoctorCategoryCode = (specialty) => {
    const mapping = {
      'Кардиолог': 'K',
      'Стоматолог': 'D', 
      'Дерматолог': 'C',
      'Дерматолог-косметолог': 'C'
    };
    return mapping[specialty] || 'O';
  };
  
  // ===================== КОРЗИНА =====================
  
  const addToCart = (service) => {
    const newItem = {
      id: Date.now(), // Временный ID для React keys
      service_id: service.id,
      service_name: service.name,
      service_price: service.price,
      quantity: 1,
      doctor_id: service.requires_doctor ? null : undefined,
      visit_date: new Date().toISOString().split('T')[0], // Сегодня по умолчанию
      visit_time: null
    };
    
    setWizardData(prev => ({
      ...prev,
      cart: {
        ...prev.cart,
        items: [...prev.cart.items, newItem]
      }
    }));
    
    // Обновляем фильтрацию
    filterServices(servicesData, [...wizardData.cart.items, newItem]);
  };
  
  const removeFromCart = (itemId) => {
    const newItems = wizardData.cart.items.filter(item => item.id !== itemId);
    setWizardData(prev => ({
      ...prev,
      cart: {
        ...prev.cart,
        items: newItems
      }
    }));
    
    filterServices(servicesData, newItems);
  };
  
  const updateCartItem = (itemId, field, value) => {
    const newItems = wizardData.cart.items.map(item => 
      item.id === itemId ? { ...item, [field]: value } : item
    );
    
    setWizardData(prev => ({
      ...prev,
      cart: {
        ...prev.cart,
        items: newItems
      }
    }));
  };
  
  // ===================== РАСЧЁТ СУММЫ =====================
  
  const calculateTotal = () => {
    let total = 0;
    
    wizardData.cart.items.forEach(item => {
      let itemPrice = item.service_price * item.quantity;
      
      // Применяем скидки
      const service = servicesData.find(s => s.id === item.service_id);
      if (service) {
        if (wizardData.cart.discount_mode === 'repeat' && service.is_consultation) {
          itemPrice = 0; // Повторная консультация бесплатна
        } else if (wizardData.cart.discount_mode === 'benefit' && service.is_consultation) {
          itemPrice = 0; // Льготная консультация бесплатна
        } else if (wizardData.cart.all_free) {
          itemPrice = 0; // Всё бесплатно
        }
      }
      
      total += itemPrice;
    });
    
    return Math.round(total); // Округляем до целых
  };
  
  // ===================== НАВИГАЦИЯ =====================
  
  const validateStep = (step) => {
    const newErrors = {};
    
    if (step === 1) {
      if (!wizardData.patient.fio.trim()) {
        newErrors.fio = 'Введите ФИО пациента';
      }
      if (!wizardData.patient.phone.trim()) {
        newErrors.phone = 'Введите телефон пациента';
      }
      // Валидация даты рождения
      if (formattedBirthDate && formattedBirthDate !== '00.00.0000') {
        const [day, month, year] = formattedBirthDate.split('.');
        const dayNum = parseInt(day);
        const monthNum = parseInt(month);
        const yearNum = parseInt(year);
        
        if (!day || !month || !year || 
            dayNum < 1 || dayNum > 31 || 
            monthNum < 1 || monthNum > 12 || 
            yearNum < 1900 || yearNum > new Date().getFullYear()) {
          newErrors.birth_date = 'Введите корректную дату рождения (ДД.ММ.ГГГГ)';
        }
      }
    } else if (step === 2) {
      if (wizardData.cart.items.length === 0) {
        newErrors.cart = 'Добавьте хотя бы одну услугу';
      }
      // Проверяем, что для услуг, требующих врача, врач выбран
      const missingDoctors = wizardData.cart.items.filter(item => {
        const service = servicesData.find(s => s.id === item.service_id);
        return service?.requires_doctor && !item.doctor_id;
      });
      if (missingDoctors.length > 0) {
        newErrors.doctors = 'Выберите врачей для всех услуг, которые их требуют';
      }
    }
    // Убрана валидация для шагов 3 и 4
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };
  
  const nextStep = () => {
    if (validateStep(currentStep)) {
      setCurrentStep(prev => Math.min(prev + 1, totalSteps));
    }
  };
  
  const prevStep = () => {
    setCurrentStep(prev => Math.max(prev - 1, 1));
  };
  
  const goToStep = (step) => {
    if (step <= currentStep || validateStep(currentStep)) {
      setCurrentStep(step);
    }
  };
  
  // ===================== ГОРЯЧИЕ КЛАВИШИ =====================
  
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!isOpen) return;
      
      // Enter - следующий шаг (кроме textarea)
      if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        if (currentStep < totalSteps) {
          nextStep();
        } else {
          handleComplete();
        }
      }
      
      // Ctrl+Enter - завершить
      if (e.key === 'Enter' && e.ctrlKey) {
        e.preventDefault();
        handleComplete();
      }
      
      // Shift+Enter в textarea - перенос строки (по умолчанию)
    };
    
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, currentStep]);
  
  // ===================== ЗАВЕРШЕНИЕ =====================
  
  const handleComplete = async () => {
    if (!validateStep(currentStep)) return;
    
    // Проверяем токен авторизации
    const token = localStorage.getItem('auth_token');
    if (!token) {
      toast.error('Требуется авторизация. Пожалуйста, войдите в систему заново.');
      return;
    }
    
    // Проверяем валидность токена
    try {
      const testResponse = await fetch(`${API_BASE}/patients/`, {
        method: 'GET',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json' 
        }
      });
      
      if (testResponse.status === 401) {
        toast.error('Сессия истекла. Пожалуйста, войдите в систему заново.');
        return;
      }
    } catch (error) {
      console.error('❌ Ошибка проверки токена:', error);
      toast.error('Ошибка проверки авторизации. Пожалуйста, войдите в систему заново.');
      return;
    }
    
    setIsProcessing(true);
    
    try {
      // Подготавливаем данные для отправки
      const cartData = {
        patient_id: wizardData.patient.id,
        visits: groupCartItemsByVisit(),
        discount_mode: wizardData.cart.discount_mode,
        payment_method: wizardData.payment.method,
        all_free: wizardData.cart.all_free,
        notes: wizardData.cart.notes
      };
      
      // Если пациент новый, сначала создаём его
      if (!wizardData.patient.id) {
        // Разбиваем ФИО на отдельные поля
        const fioParts = wizardData.patient.fio.trim().split(' ');
        const lastName = fioParts[0] || '';
        const firstName = fioParts[1] || '';
        const middleName = fioParts.slice(2).join(' ') || null;
        
        const token = localStorage.getItem('auth_token');
        console.log('🔑 Токен для создания пациента:', token ? `${token.substring(0, 20)}...` : 'НЕТ ТОКЕНА');
        console.log('🔍 Полный токен:', token);
        console.log('📊 Длина токена:', token ? token.length : 0);
        
        const patientResponse = await fetch(`${API_BASE}/patients/`, {
          method: 'POST',
          headers: { 
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json' 
          },
          body: JSON.stringify({
            last_name: lastName,
            first_name: firstName,
            middle_name: middleName,
            birth_date: wizardData.patient.birth_date,
            phone: wizardData.patient.phone,
            address: wizardData.patient.address
          })
        });
        
        if (patientResponse.ok) {
          const patient = await patientResponse.json();
          cartData.patient_id = patient.id;
        } else if (patientResponse.status === 400) {
          // Пациент уже существует, попробуем найти его по номеру телефона
          console.log('⚠️ Пациент уже существует, ищем по номеру телефона...');
          const searchResponse = await fetch(`${API_BASE}/patients/?phone=${encodeURIComponent(wizardData.patient.phone)}`, {
            headers: { 
              'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
              'Content-Type': 'application/json' 
            }
          });
          
          if (searchResponse.ok) {
            const patients = await searchResponse.json();
            if (patients.length > 0) {
              cartData.patient_id = patients[0].id;
              console.log('✅ Найден существующий пациент:', patients[0].id);
            } else {
              throw new Error('Пациент не найден по номеру телефона');
            }
          } else {
            throw new Error('Ошибка поиска пациента');
          }
        } else {
          const errorText = await patientResponse.text();
          console.error('❌ Ошибка создания пациента:', patientResponse.status, errorText);
          throw new Error(`Ошибка создания пациента: ${patientResponse.status} ${errorText}`);
        }
      }
      
      // Создаём корзину визитов
      console.log('📤 Отправляем данные корзины:', cartData);
      const cartResponse = await fetch(`${API_BASE}/registrar/cart`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json' 
        },
        body: JSON.stringify(cartData)
      });
      
      if (cartResponse.ok) {
        const result = await cartResponse.json();
        
        // Всегда завершаем после создания корзины (без онлайн оплаты в UI)
        localStorage.removeItem(DRAFT_KEY);
        toast.success('Запись создана успешно!');
        onComplete?.(result);
        onClose();
      } else {
        const errorText = await cartResponse.text();
        console.error('❌ Ошибка создания корзины:', cartResponse.status, errorText);
        throw new Error(`Ошибка создания корзины: ${cartResponse.status} ${errorText}`);
      }
    } catch (error) {
      console.error('Ошибка завершения мастера:', error);
      toast.error(error.message || 'Произошла ошибка');
    } finally {
      setIsProcessing(false);
    }
  };
  
  // Группировка элементов корзины по визитам
  const groupCartItemsByVisit = () => {
    const visits = {};
    
    wizardData.cart.items.forEach(item => {
      const key = `${item.doctor_id || 'no_doctor'}_${item.visit_date}_${item.visit_time || 'no_time'}`;
      
      if (!visits[key]) {
        visits[key] = {
          doctor_id: item.doctor_id || null,
          services: [],
          visit_date: item.visit_date,
          visit_time: item.visit_time || null,
          department: getDepartmentByService(item.service_id),
          notes: null
        };
      }
      
      visits[key].services.push({
        service_id: item.service_id,
        quantity: item.quantity
      });
    });
    
    return Object.values(visits);
  };
  
  const getDepartmentByService = (serviceId) => {
    const service = servicesData.find(s => s.id === serviceId);
    
    if (!service) {
      return 'general';
    }
    
    // ✅ ИСПРАВЛЕННЫЙ МАППИНГ - соответствует вкладкам RegistrarPanel
    const mapping = {
      'K': 'cardiology',    // Кардиология → вкладка cardio
      'D': 'dermatology',   // Дерматология → вкладка derma  
      'S': 'dentistry',     // Стоматология → вкладка dental
      'L': 'laboratory',    // Лаборатория → вкладка lab
      'C': 'procedures',    // Косметология → вкладка procedures (нет отдельной вкладки)
      'O': 'procedures'     // Прочие процедуры → вкладка procedures
    };
    
    return mapping[service.category_code] || 'general';
  };
  
  // ===================== ДЕЙСТВИЯ ДИАЛОГА =====================
  
  const actions = [
    {
      label: 'Очистить черновик',
      onClick: clearDraft,
      variant: 'secondary',
      icon: <Trash2 size={16} />,
      disabled: isProcessing
    },
    currentStep > 1 && {
      label: 'Назад',
      onClick: prevStep,
      variant: 'secondary',
      icon: <ArrowLeft size={16} />,
      disabled: isProcessing
    },
    {
      label: currentStep === totalSteps ? 'Завершить' : 'Далее',
      onClick: currentStep === totalSteps ? handleComplete : nextStep,
      variant: 'primary',
      icon: currentStep === totalSteps ? <Check size={16} /> : <ArrowRight size={16} />,
      disabled: isProcessing,
      loading: isProcessing
    }
  ].filter(Boolean);
  
  // ===================== ОБРАБОТЧИКИ ОНЛАЙН ОПЛАТЫ УБРАНЫ =====================

  return (
    <>
      <ModernDialog
        isOpen={isOpen}
        onClose={onClose}
        title="Мастер регистрации пациента"
        actions={actions}
        maxWidth="70rem"
        closeOnBackdrop={false}
        closeOnEscape={false}
        className="appointment-wizard-v2"
      >
        <div className="wizard-container-v2">
          {/* Контент шагов */}
          <div className="wizard-content-v2">
            {currentStep === 1 && (
              <PatientStepV2
                data={wizardData.patient}
                errors={errors}
                suggestions={patientSuggestions}
                showSuggestions={showSuggestions}
                onSearch={handlePatientSearch}
                onSelectPatient={selectPatient}
                onUpdate={(field, value) => 
                  setWizardData(prev => ({
                    ...prev,
                    patient: { ...prev.patient, [field]: value }
                  }))
                }
                onPhoneChange={handlePhoneChange}
                onBirthDateChange={handleBirthDateChange}
                formattedBirthDate={formattedBirthDate}
                fioRef={fioRef}
                phoneRef={phoneRef}
                cart={wizardData.cart}
                onUpdateCart={(field, value) =>
                  setWizardData(prev => ({
                    ...prev,
                    cart: { ...prev.cart, [field]: value }
                  }))
                }
              />
            )}

            {currentStep === 2 && (
              <CartStepV2
                cart={wizardData.cart}
                services={filteredServices}
                doctors={doctorsData}
                showAllServices={showAllServices}
                onToggleAllServices={() => setShowAllServices(!showAllServices)}
                onAddToCart={addToCart}
                onRemoveFromCart={removeFromCart}
                onUpdateItem={updateCartItem}
                onUpdateCart={(field, value) =>
                  setWizardData(prev => ({
                    ...prev,
                    cart: { ...prev.cart, [field]: value }
                  }))
                }
                calculateTotal={calculateTotal}
                servicesData={servicesData}
                errors={errors}
              />
            )}

          </div>
        </div>
      </ModernDialog>
      
      {/* Диалоги онлайн оплаты удалены из UI */}
    </>
  );
};

// ===================== КОМПОНЕНТЫ ШАГОВ =====================

// Шаг 1: Пациент
const PatientStepV2 = ({ 
  data, 
  errors, 
  suggestions, 
  showSuggestions, 
  onSearch, 
  onSelectPatient, 
  onUpdate,
  onPhoneChange,
  onBirthDateChange,
  formattedBirthDate,
  fioRef,
  phoneRef,
  cart,
  onUpdateCart
}) => (
  <div className="step-content">
    <div className="form-grid">
      {/* ФИО с поиском */}
      <div className="form-field full-width">
        <label>ФИО пациента *</label>
        <div className="search-field">
          <input
            ref={fioRef}
            type="text"
            value={data.fio}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Введите ФИО или телефон для поиска..."
            className={errors.fio ? 'error' : ''}
          />
          <Search size={16} className="search-icon" />
          
          {showSuggestions && suggestions.length > 0 && (
            <div className="suggestions-dropdown">
              {suggestions.map((patient) => (
                <div
                  key={patient.id}
                  className="suggestion-item"
                  onClick={() => onSelectPatient(patient)}
                >
                  <div className="suggestion-name">{patient.fio}</div>
                  <div className="suggestion-details">
                    <Phone size={12} /> {patient.phone} • 
                    <Calendar size={12} /> {patient.birth_date}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        {errors.fio && <span className="error-text">{errors.fio}</span>}
      </div>

      {/* Телефон */}
      <div className="form-field">
        <label>Телефон *</label>
        <input
          ref={phoneRef}
          type="tel"
          value={data.phone}
          onChange={(e) => onPhoneChange(e.target.value)}
          placeholder="+998 XX XXX XX XX"
          className={errors.phone ? 'error' : ''}
        />
        {errors.phone && <span className="error-text">{errors.phone}</span>}
      </div>

      {/* Дата рождения */}
      <div className="form-field">
        <label>Дата рождения</label>
        <input
          type="text"
          value={formattedBirthDate}
          onChange={(e) => onBirthDateChange(e.target.value)}
          placeholder="ДД.ММ.ГГГГ"
          maxLength="10"
          className={errors.birth_date ? 'error' : ''}
        />
        {errors.birth_date && <span className="error-text">{errors.birth_date}</span>}
      </div>

      {/* Адрес */}
      <div className="form-field full-width">
        <label>Адрес</label>
        <input
          type="text"
          value={data.address}
          onChange={(e) => onUpdate('address', e.target.value)}
          placeholder="Адрес проживания"
        />
      </div>

      {/* Тип визита - перенесено из PaymentStepV2 */}
      <div className="form-field full-width">
        <label>Тип визита</label>
        <div className="visit-type-options">
          <label className="radio-option">
            <input
              type="radio"
              name="discount_mode"
              value="none"
              checked={cart?.discount_mode === 'none'}
              onChange={(e) => onUpdateCart('discount_mode', e.target.value)}
            />
            <span>Платный</span>
          </label>
          
          <label className="radio-option">
            <input
              type="radio"
              name="discount_mode"
              value="repeat"
              checked={cart?.discount_mode === 'repeat'}
              onChange={(e) => onUpdateCart('discount_mode', e.target.value)}
            />
            <span>Повторный (бесплатная консультация)</span>
          </label>
          
          <label className="radio-option">
            <input
              type="radio"
              name="discount_mode"
              value="benefit"
              checked={cart?.discount_mode === 'benefit'}
              onChange={(e) => onUpdateCart('discount_mode', e.target.value)}
            />
            <span>Льготный (бесплатная консультация)</span>
          </label>
        </div>
        
        <div className="all-free-option">
          <label className="checkbox-option">
            <input
              type="checkbox"
              checked={cart?.all_free}
              onChange={(e) => onUpdateCart('all_free', e.target.checked)}
            />
            <span>All Free (требует одобрения администратора)</span>
          </label>
          {cart?.all_free && (
            <div className="warning-message">
              <AlertCircle size={16} />
              Заявка будет отправлена на одобрение администратору
            </div>
          )}
        </div>
      </div>
    </div>
  </div>
);

// Шаг 2: Корзина - Компактный дизайн с dropdown и чекбоксами
const CartStepV2 = ({ 
  cart, 
  services, 
  doctors, 
  showAllServices, 
  onToggleAllServices,
  onAddToCart, 
  onRemoveFromCart, 
  onUpdateItem,
  onUpdateCart,
  calculateTotal,
  servicesData,
  errors 
}) => {
  const [expandedCategories, setExpandedCategories] = useState({
    specialists: false,
    laboratory: false,
    cosmetology: false,
    other: false
  });
  
  const [selectedServices, setSelectedServices] = useState(new Set());
  
  // Группировка услуг по категориям
  const groupedServices = {
    specialists: [],
    laboratory: [],
    cosmetology: [],
    other: []
  };
  
  if (Array.isArray(services)) {
    services.forEach(service => {
      // Консультации специалистов
      if (service.name.toLowerCase().includes('консультация')) {
        groupedServices.specialists.push(service);
      }
      // Лабораторные анализы
      else if (service.category_code === 'L') {
        groupedServices.laboratory.push(service);
      }
      // Косметология
      else if (service.category_code === 'C') {
        groupedServices.cosmetology.push(service);
      }
      // Прочие услуги
      else {
        groupedServices.other.push(service);
      }
    });
  }
  
  // Обработка выбора услуги
  const handleServiceToggle = (service) => {
    const isInCart = cart?.items?.some(item => item.service_id === service.id);
    
    if (isInCart) {
      const cartItem = cart.items.find(item => item.service_id === service.id);
      onRemoveFromCart(cartItem.id);
    } else {
      onAddToCart(service);
    }
  };
  
  // Переключение категории
  const toggleCategory = (category) => {
    setExpandedCategories(prev => ({
      ...prev,
      [category]: !prev[category]
    }));
  };
  
  // Общая сумма корзины с учетом скидок
  const cartTotal = useMemo(() => {
    if (!Array.isArray(cart?.items)) return 0;
    
    let total = 0;
    cart.items.forEach(item => {
      let itemPrice = (item.service_price || 0) * (item.quantity || 1);
      
      // Применяем скидки для консультаций
      const service = servicesData?.find(s => s.id === item.service_id);
      if (service && service.is_consultation) {
        if (cart.discount_mode === 'repeat' || cart.discount_mode === 'benefit') {
          itemPrice = 0; // Консультации бесплатны для повторных и льготных визитов
        }
      }
      
      // All Free делает всё бесплатным
      if (cart.all_free) {
        itemPrice = 0;
      }
      
      total += itemPrice;
    });
    
    return Math.round(total);
  }, [cart?.items, cart?.discount_mode, cart?.all_free, servicesData]);
  
  return (
    <div className="step-content cart-step-compact">
      {/* Заголовок */}
      <div className="step-header">
        <h3>Выберите услуги для пациента</h3>
        <div className="cart-summary-inline">
          <ShoppingCart size={18} />
          <span>Выбрано: {cart?.items?.length || 0} услуг</span>
          <span className="divider">|</span>
          <span className="total-sum">Сумма: {cartTotal.toLocaleString()} сум</span>
        </div>
      </div>
      
      {/* Основная сетка с тремя колонками */}
      <div className="services-grid-compact">
        {/* Колонка 1: Специалисты */}
        <div className="service-column">
          <div className="column-header">
            <h4>👨‍⚕️ Консультации специалистов</h4>
          </div>
          
          {/* Специалисты - чекбоксы */}
          <div className="specialists-list">
            {groupedServices.specialists.map(service => {
              const isInCart = cart?.items?.some(item => item.service_id === service.id);
              return (
                <label key={service.id} className="service-checkbox">
                  <input
                    type="checkbox"
                    checked={isInCart}
                    onChange={() => handleServiceToggle(service)}
                  />
                  <span className="service-label">
                    <span className="service-name">{service.name}</span>
                    <span className="service-price">{service.price?.toLocaleString()} сум</span>
                  </span>
                </label>
              );
            })}
          </div>
          
          {/* Лабораторные анализы - dropdown */}
          <div className="dropdown-section">
            <button 
              className={`dropdown-header ${expandedCategories.laboratory ? 'expanded' : ''}`}
              onClick={() => toggleCategory('laboratory')}
            >
              <span>🧪 Лабораторные анализы ({groupedServices.laboratory.length})</span>
              <ChevronDown size={18} className="dropdown-icon" />
            </button>
            
            {expandedCategories.laboratory && (
              <div className="dropdown-content">
                {groupedServices.laboratory.map(service => {
                  const isInCart = cart?.items?.some(item => item.service_id === service.id);
                  return (
                    <label key={service.id} className="service-checkbox">
                      <input
                        type="checkbox"
                        checked={isInCart}
                        onChange={() => handleServiceToggle(service)}
                      />
                      <span className="service-label">
                        <span className="service-name">{service.name}</span>
                        <span className="service-price">{service.price?.toLocaleString()} сум</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        </div>
        
        {/* Колонка 2: Косметология */}
        <div className="service-column">
          <div className="column-header">
            <h4>✨ Косметологические процедуры</h4>
          </div>
          
          <div className="dropdown-section">
            <button 
              className={`dropdown-header ${expandedCategories.cosmetology ? 'expanded' : ''}`}
              onClick={() => toggleCategory('cosmetology')}
            >
              <span>Процедуры ({groupedServices.cosmetology.length})</span>
              <ChevronDown size={18} className="dropdown-icon" />
            </button>
            
            {expandedCategories.cosmetology && (
              <div className="dropdown-content">
                {groupedServices.cosmetology.map(service => {
                  const isInCart = cart?.items?.some(item => item.service_id === service.id);
                  return (
                    <label key={service.id} className="service-checkbox">
                      <input
                        type="checkbox"
                        checked={isInCart}
                        onChange={() => handleServiceToggle(service)}
                      />
                      <span className="service-label">
                        <span className="service-name">{service.name}</span>
                        <span className="service-price">{service.price?.toLocaleString()} сум</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        </div>
        
        {/* Колонка 3: Прочие услуги и корзина */}
        <div className="service-column">
          <div className="column-header">
            <h4>📋 Дополнительные услуги</h4>
          </div>
          
          <div className="dropdown-section">
            <button 
              className={`dropdown-header ${expandedCategories.other ? 'expanded' : ''}`}
              onClick={() => toggleCategory('other')}
            >
              <span>Прочие услуги ({groupedServices.other.length})</span>
              <ChevronDown size={18} className="dropdown-icon" />
            </button>
            
            {expandedCategories.other && (
              <div className="dropdown-content">
                {groupedServices.other.map(service => {
                  const isInCart = cart?.items?.some(item => item.service_id === service.id);
                  return (
                    <label key={service.id} className="service-checkbox">
                      <input
                        type="checkbox"
                        checked={isInCart}
                        onChange={() => handleServiceToggle(service)}
                      />
                      <span className="service-label">
                        <span className="service-name">{service.name}</span>
                        <span className="service-price">{service.price?.toLocaleString()} сум</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
          
          {/* Мини-корзина */}
          <div className="mini-cart">
            <h5>🛒 Выбранные услуги</h5>
            {!cart?.items?.length ? (
              <p className="empty-text">Услуги не выбраны</p>
            ) : (
              <div className="selected-services">
                {cart.items.map(item => (
                  <div key={item.id} className="selected-item">
                    <span className="item-name">{item.service_name}</span>
                    <button 
                      className="remove-btn"
                      onClick={() => onRemoveFromCart(item.id)}
                      title="Удалить"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Ошибки валидации */}
      {(errors.cart || errors.doctors) && (
        <div className="validation-errors">
          {errors.cart && (
            <div className="error-message">
              <AlertCircle size={16} />
              {errors.cart}
            </div>
          )}
          {errors.doctors && (
            <div className="error-message">
              <AlertCircle size={16} />
              {errors.doctors}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// Функция для получения кода категории врача
const getDoctorCategoryCode = (specialty) => {
  const mapping = {
    'Кардиолог': 'K',
    'Стоматолог': 'S', 
    'Дерматолог': 'D',
    'Дерматолог-косметолог': 'C'
  };
  return mapping[specialty] || 'O';
};



export default AppointmentWizardV2;

