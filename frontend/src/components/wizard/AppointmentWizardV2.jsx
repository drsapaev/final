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
  ChevronDown,
  Calendar,
  User
} from 'lucide-react';
import { toast } from 'react-toastify';
import ModernDialog from '../dialogs/ModernDialog';
import { MacOSInput, MacOSButton, MacOSSelect, MacOSCheckbox } from '../ui/macos';
import { useRoleAccess } from '../common/RoleGuard';

const API_BASE = '/api/v1';

// CSS Keyframes for animations
const slideInKeyframes = `
@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateX(20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}
`;

// Inject keyframes into the document
if (typeof document !== 'undefined' && !document.getElementById('wizard-keyframes')) {
  const style = document.createElement('style');
  style.id = 'wizard-keyframes';
  style.textContent = slideInKeyframes;
  document.head.appendChild(style);
}

const AppointmentWizardV2 = ({ 
  isOpen, 
  onClose, 
  onComplete,
  isProcessing = false,
  setIsProcessing = () => {} // Дефолтная функция-заглушка
}) => {
  // Проверка прав доступа
  const { hasRole } = useRoleAccess();
  const hasRegistrarAccess = hasRole(['Admin', 'Registrar']);
  
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
        
        // ✅ Формируем fio из отдельных полей, если его нет
        const patientsWithFio = data.map(patient => {
          if (!patient.fio && (patient.last_name || patient.first_name)) {
            const parts = [
              patient.last_name || '',
              patient.first_name || '',
              patient.middle_name || ''
            ].filter(p => p);
            patient.fio = parts.join(' ').trim() || 'Без имени';
          } else if (!patient.fio) {
            patient.fio = 'Без имени';
          }
          return patient;
        });
        
        // Сортировка по приоритету: телефон > точное ФИО > частичное ФИО
        const sorted = patientsWithFio.sort((a, b) => {
          const queryLower = (query || '').toLowerCase();
          const aPhone = a?.phone || '';
          const bPhone = b?.phone || '';
          const aFio = (a?.fio || '').toLowerCase();
          const bFio = (b?.fio || '').toLowerCase();
          
          // Приоритет 1: точное совпадение телефона
          if (aPhone === query) return -1;
          if (bPhone === query) return 1;
          
          // Приоритет 2: точное совпадение ФИО
          if (aFio === queryLower) return -1;
          if (bFio === queryLower) return 1;
          
          // Приоритет 3: частичное совпадение ФИО
          const aMatch = aFio.includes(queryLower);
          const bMatch = bFio.includes(queryLower);
          
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
    // ✅ БЕЗОПАСНО: Формируем fio из отдельных полей, если его нет
    let patientFio = patient.fio;
    if (!patientFio && (patient.last_name || patient.first_name)) {
      const parts = [
        patient.last_name || '',
        patient.first_name || '',
        patient.middle_name || ''
      ].filter(p => p);
      patientFio = parts.join(' ').trim() || 'Без имени';
    } else if (!patientFio) {
      patientFio = 'Без имени';
    }
    
    // Парсинг ФИО (безопасно)
    const nameParts = (patientFio || '').trim().split(/\s+/).filter(p => p.length > 0);
    const lastName = nameParts[0] || patient.last_name || '';
    const firstName = nameParts[1] || patient.first_name || '';
    const middleName = nameParts.slice(2).join(' ') || patient.middle_name || '';
    
    setWizardData(prev => ({
      ...prev,
      patient: {
        id: patient.id,
        fio: patientFio,
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
  
  // 🔧 УПРОЩЕННАЯ ФИЛЬТРАЦИЯ: Показываем все услуги без привязки к врачам
  const filterServices = (allServices, cartItems) => {
    
    // Если нет услуг, показываем пустой массив
    if (!Array.isArray(allServices) || allServices.length === 0) {
      setFilteredServices([]);
      return;
    }
    
    // 🎯 НОВАЯ ЛОГИКА: Всегда показываем ВСЕ услуги
    // Пользователь может выбирать любые услуги независимо от врачей
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
      visit_date: (() => {
        // ✅ Используем локальную дату, а не UTC
        const now = new Date();
        const year = now.getFullYear();
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const day = String(now.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
      })(),
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
        const fioParts = wizardData.patient.fio.trim().split(/\s+/).filter(part => part.length > 0);
        
        // ✅ УЛУЧШЕНО: Правильное разделение ФИО
        // Если только одно слово - это фамилия, имя будет пустым (но мы используем фамилию как имя)
        // Если два слова - фамилия и имя
        // Если три и более - фамилия, имя, отчество
        let lastName = '';
        let firstName = '';
        let middleName = null;
        
        if (fioParts.length === 1) {
          // Только фамилия или одно слово - используем как фамилию и имя
          lastName = fioParts[0];
          firstName = fioParts[0]; // Дублируем для обязательного поля
        } else if (fioParts.length >= 2) {
          lastName = fioParts[0];
          firstName = fioParts[1];
          if (fioParts.length > 2) {
            middleName = fioParts.slice(2).join(' ');
          }
        } else {
          // Пустое ФИО - это ошибка валидации
          throw new Error('ФИО пациента обязательно для заполнения');
        }
        
        // Валидация обязательных полей
        if (!lastName || !firstName) {
          throw new Error('ФИО пациента должно содержать минимум фамилию и имя');
        }
        
        const token = localStorage.getItem('auth_token');
        console.log('🔑 Токен для создания пациента:', token ? `${token.substring(0, 20)}...` : 'НЕТ ТОКЕНА');
        console.log('📊 Длина токена:', token ? token.length : 0);
        
        // Подготовка данных пациента
        const patientData = {
          last_name: lastName,
          first_name: firstName,
          middle_name: middleName,
          phone: wizardData.patient.phone || null,
          address: wizardData.patient.address || null
        };
        
        // Добавляем дату рождения только если она есть
        if (wizardData.patient.birth_date) {
          patientData.birth_date = wizardData.patient.birth_date;
        }
        
        console.log('📋 Данные для создания пациента:', patientData);
        
        const patientResponse = await fetch(`${API_BASE}/patients/`, {
          method: 'POST',
          headers: { 
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json' 
          },
          body: JSON.stringify(patientData)
        });
        
        if (patientResponse.ok) {
          const patient = await patientResponse.json();
          cartData.patient_id = patient.id;
          console.log('✅ Пациент создан успешно:', patient.id);
        } else if (patientResponse.status === 400) {
          // Получаем детальную информацию об ошибке
          let errorDetail = 'Пациент с таким номером телефона уже существует';
          try {
            const errorData = await patientResponse.json();
            errorDetail = errorData.detail || errorDetail;
            console.log('⚠️ Ошибка 400 при создании пациента:', errorDetail);
          } catch (e) {
            const errorText = await patientResponse.text();
            console.log('⚠️ Текст ошибки создания пациента:', errorText);
            errorDetail = errorText || errorDetail;
          }
          
          // Пациент уже существует или другая ошибка валидации - ищем по номеру телефона
          if (wizardData.patient.phone) {
            console.log('⚠️ Ищем существующего пациента по номеру телефона...');
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
                // Пациент не найден - возможно, ошибка валидации данных
                throw new Error(`Ошибка создания пациента: ${errorDetail}`);
              }
            } else {
              throw new Error('Ошибка поиска пациента');
            }
          } else {
            // Нет телефона и ошибка создания - это проблема валидации
            throw new Error(`Ошибка валидации данных пациента: ${errorDetail}`);
          }
        } else {
          const errorText = await patientResponse.text();
          console.error('❌ Ошибка создания пациента:', patientResponse.status, errorText);
          throw new Error(`Ошибка создания пациента: ${patientResponse.status} ${errorText}`);
        }
      }
      
      // Создаём корзину визитов
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

        console.log('✅ Запись создана успешно на backend:', result);

        // Всегда завершаем после создания корзины (без онлайн оплаты в UI)
        localStorage.removeItem(DRAFT_KEY);
        toast.success('Запись создана успешно!');
        onComplete?.(result);
        onClose();
      } else {
        // Получаем детальную информацию об ошибке
        let errorMessage = `Ошибка создания записи (${cartResponse.status})`;
        let isPermissionError = false;

        try {
          const errorData = await cartResponse.json();
          console.error('❌ Детали ошибки создания корзины:', errorData);
          errorMessage = errorData.detail || errorMessage;
          
          // Проверяем, является ли это ошибкой прав доступа
          if (cartResponse.status === 403) {
            isPermissionError = true;
            if (errorMessage.includes('Not enough permissions')) {
              errorMessage = 'У вас нет прав для создания записей. Необходима роль Регистратора или Администратора.';
            }
          }
        } catch (parseError) {
          const errorText = await cartResponse.text();
          console.error('❌ Текст ошибки создания корзины:', errorText);
          errorMessage = errorText || errorMessage;
          
          if (cartResponse.status === 403) {
            isPermissionError = true;
            errorMessage = 'У вас нет прав для создания записей. Необходима роль Регистратора или Администратора.';
          }
        }

        console.error('❌ Ошибка создания корзины:', cartResponse.status, errorMessage);
        
        if (isPermissionError) {
          toast.error(errorMessage, { 
            duration: 5000,
            style: { backgroundColor: '#fee', border: '1px solid #fcc' }
          });
          // Закрываем мастер при ошибке прав доступа
          onClose();
        } else {
          toast.error(`Ошибка создания записи: ${errorMessage}`);
        }
        return; // ❌ НЕ закрываем мастер при других ошибках
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
      // Определяем отделение для услуги
      const department = getDepartmentByService(item.service_id);
      
      // ✅ ИСПРАВЛЕНО: Объединяем все процедуры в один визит
      // Все процедуры (P, C, D_PROC) должны быть в одном визите с department = 'procedures'
      let finalDepartment = department;
      if (department === 'procedures') {
        finalDepartment = 'procedures'; // Все процедуры в одном отделе
      }
      
      // Группируем по finalDepartment + doctor_id + visit_date + visit_time
      const key = `${finalDepartment}_${item.doctor_id || 'no_doctor'}_${item.visit_date}_${item.visit_time || 'no_time'}`;
      
      if (!visits[key]) {
        visits[key] = {
          doctor_id: item.doctor_id || null,
          services: [],
          visit_date: item.visit_date,
          visit_time: item.visit_time || null,
          department: finalDepartment,
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
      console.warn(`⚠️ Услуга ${serviceId} не найдена в servicesData`);
      return 'general';
    }
    
    console.log(`🔍 getDepartmentByService: serviceId=${serviceId}, queue_tag=${service.queue_tag}, category_code=${service.category_code}`);
    
    // 🎯 СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ ЭКГ: отдельный кабинет!
    if (service.queue_tag === 'ecg') {
      console.log(`✅ ЭКГ обнаружено! Возвращаем department='echokg'`);
      return 'echokg';  // ЭКГ в отдельном кабинете (соответствует вкладке 'echokg')
    }
    
    // ✅ ИСПРАВЛЕННЫЙ МАППИНГ - соответствует вкладкам RegistrarPanel
    const mapping = {
      'K': 'cardiology',    // Кардиология → вкладка cardio (БЕЗ ЭКГ!)
      'D': 'dermatology',   // Дерматология → вкладка derma (только консультации)
      'S': 'dentistry',     // Стоматология → вкладка dental
      'L': 'laboratory',    // Лаборатория → вкладка lab
      'P': 'procedures',    // Физиотерапия → вкладка procedures
      'C': 'procedures',    // Косметология → вкладка procedures
      'D_PROC': 'procedures', // Дерматологические процедуры → вкладка procedures
      'O': 'procedures'     // Прочие процедуры → вкладка procedures
    };
    
    const result = mapping[service.category_code] || 'general';
    console.log(`🎯 getDepartmentByService результат: serviceId=${serviceId}, category_code=${service.category_code}, department=${result}`);
    return result;
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

  // Проверка прав доступа перед рендерингом
  if (!hasRegistrarAccess) {
    return (
      <ModernDialog
        isOpen={isOpen}
        onClose={onClose}
        title="Доступ запрещен"
        maxWidth="40rem"
      >
        <div style={{
          padding: 'var(--mac-spacing-6)',
          textAlign: 'center'
        }}>
          <AlertCircle 
            size={48} 
            style={{ 
              color: 'var(--mac-danger)', 
              marginBottom: 'var(--mac-spacing-4)' 
            }} 
          />
          <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            marginBottom: 'var(--mac-spacing-3)',
            color: 'var(--mac-text-primary)'
          }}>
            Недостаточно прав доступа
          </h3>
          <p style={{
            fontSize: 'var(--mac-font-size-md)',
            color: 'var(--mac-text-secondary)',
            marginBottom: 'var(--mac-spacing-4)',
            lineHeight: 1.6
          }}>
            Для создания записей пациентов необходима роль Регистратора или Администратора.
          </p>
          <MacOSButton
            onClick={onClose}
            variant="primary"
            style={{ marginTop: 'var(--mac-spacing-4)' }}
          >
            Закрыть
          </MacOSButton>
        </div>
      </ModernDialog>
    );
  }

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
  <div style={{
    display: 'flex',
    flexDirection: 'column',
    gap: 'var(--mac-spacing-6)',
    animation: 'slideIn 0.3s ease-out'
  }}>
    <div style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr',
      gap: 'var(--mac-spacing-5)',
      alignItems: 'start'
    }}>
      {/* ФИО с поиском */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--mac-spacing-2)',
        gridColumn: '1 / -1'
      }}>
        <label style={{
          fontSize: 'var(--mac-font-size-sm)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)'
        }}>
          ФИО пациента *
        </label>
        <div style={{ position: 'relative', width: '100%' }}>
          <MacOSInput
            ref={fioRef}
            type="text"
            value={data.fio}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Введите ФИО или телефон для поиска..."
            error={!!errors.fio}
            icon={Search}
            iconPosition="right"
            size="md"
          />
          
          {showSuggestions && suggestions.length > 0 && (
            <div style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              zIndex: 1000,
              background: 'var(--mac-bg-primary)',
              border: '1px solid var(--mac-border)',
              borderTop: 'none',
              borderRadius: '0 0 var(--mac-radius-md) var(--mac-radius-md)',
              boxShadow: 'var(--mac-shadow-md)',
              maxHeight: '200px',
              overflowY: 'auto'
            }}>
              {suggestions.map((patient) => (
                <div
                  key={patient.id}
                  style={{
                    padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                    cursor: 'pointer',
                    transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
                    borderBottom: '1px solid var(--mac-separator)'
                  }}
                  onClick={() => onSelectPatient(patient)}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  <div style={{
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '4px'
                  }}>
                    {patient.fio}
                  </div>
                  <div style={{
                    fontSize: 'var(--mac-font-size-xs)',
                    color: 'var(--mac-text-tertiary)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--mac-spacing-2)'
                  }}>
                    <Phone size={12} />
                    {patient.phone} •
                    <Calendar size={12} />
                    {patient.birth_date}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        {errors.fio && (
          <span style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-danger)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}>
            <AlertCircle size={14} />
            {errors.fio}
          </span>
        )}
      </div>

      {/* Телефон */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--mac-spacing-2)'
      }}>
        <label style={{
          fontSize: 'var(--mac-font-size-sm)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)'
        }}>
          Телефон *
        </label>
        <MacOSInput
          ref={phoneRef}
          type="tel"
          value={data.phone}
          onChange={(e) => onPhoneChange(e.target.value)}
          placeholder="+998 XX XXX XX XX"
          error={!!errors.phone}
          icon={Phone}
          iconPosition="left"
          size="md"
        />
        {errors.phone && (
          <span style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-danger)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}>
            <AlertCircle size={14} />
            {errors.phone}
          </span>
        )}
      </div>

      {/* Дата рождения */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--mac-spacing-2)'
      }}>
        <label style={{
          fontSize: 'var(--mac-font-size-sm)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)'
        }}>
          Дата рождения
        </label>
        <MacOSInput
          type="text"
          value={formattedBirthDate}
          onChange={(e) => onBirthDateChange(e.target.value)}
          placeholder="ДД.ММ.ГГГГ"
          maxLength={10}
          error={!!errors.birth_date}
          icon={Calendar}
          iconPosition="left"
          size="md"
        />
        {errors.birth_date && (
          <span style={{
            fontSize: 'var(--mac-font-size-xs)',
            color: 'var(--mac-danger)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}>
            <AlertCircle size={14} />
            {errors.birth_date}
          </span>
        )}
      </div>

      {/* Адрес */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--mac-spacing-2)',
        gridColumn: '1 / -1'
      }}>
        <label style={{
          fontSize: 'var(--mac-font-size-sm)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)'
        }}>
          Адрес
        </label>
        <MacOSInput
          type="text"
          value={data.address}
          onChange={(e) => onUpdate('address', e.target.value)}
          placeholder="Адрес проживания"
          size="md"
        />
      </div>

      {/* Тип визита - перенесено из PaymentStepV2 */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--mac-spacing-2)',
        gridColumn: '1 / -1'
      }}>
        <label style={{
          fontSize: 'var(--mac-font-size-sm)',
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)'
        }}>
          Тип визита
        </label>
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--mac-spacing-2)'
        }}>
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            padding: 'var(--mac-spacing-3)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            background: 'var(--mac-bg-primary)'
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-primary)'}
          >
            <input
              type="radio"
              name="discount_mode"
              value="none"
              checked={cart?.discount_mode === 'none'}
              onChange={(e) => onUpdateCart('discount_mode', e.target.value)}
              style={{ margin: 0 }}
            />
            <span style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              Платный
            </span>
          </label>
          
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            padding: 'var(--mac-spacing-3)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            background: 'var(--mac-bg-primary)'
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-primary)'}
          >
            <input
              type="radio"
              name="discount_mode"
              value="repeat"
              checked={cart?.discount_mode === 'repeat'}
              onChange={(e) => onUpdateCart('discount_mode', e.target.value)}
              style={{ margin: 0 }}
            />
            <span style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              Повторный (бесплатная консультация)
            </span>
          </label>
          
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            padding: 'var(--mac-spacing-3)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            background: 'var(--mac-bg-primary)'
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-primary)'}
          >
            <input
              type="radio"
              name="discount_mode"
              value="benefit"
              checked={cart?.discount_mode === 'benefit'}
              onChange={(e) => onUpdateCart('discount_mode', e.target.value)}
              style={{ margin: 0 }}
            />
            <span style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              Льготный (бесплатная консультация)
            </span>
          </label>
        </div>
        
        <div style={{ marginTop: 'var(--mac-spacing-2)' }}>
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            padding: 'var(--mac-spacing-3)',
            border: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md)',
            cursor: 'pointer',
            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
            background: 'var(--mac-bg-primary)'
          }}
          onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
          onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-primary)'}
          >
            <input
              type="checkbox"
              checked={cart?.all_free}
              onChange={(e) => onUpdateCart('all_free', e.target.checked)}
              style={{ margin: 0 }}
            />
            <span style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              All Free (требует одобрения администратора)
            </span>
          </label>
          {cart?.all_free && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-2)',
              padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
              background: 'var(--mac-warning)',
              border: '1px solid var(--mac-warning-hover)',
              borderRadius: 'var(--mac-radius-sm)',
              color: 'var(--mac-text-primary)',
              fontSize: 'var(--mac-font-size-xs)',
              marginTop: 'var(--mac-spacing-2)'
            }}>
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
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--mac-spacing-5)',
      height: '100%',
      padding: 'var(--mac-spacing-5)'
    }}>
      {/* Заголовок */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingBottom: 'var(--mac-spacing-4)',
        borderBottom: '2px solid var(--mac-border)'
      }}>
        <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          color: 'var(--mac-text-primary)',
          margin: 0
        }}>
          Выберите услуги для пациента
        </h3>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-3)',
          fontSize: 'var(--mac-font-size-sm)',
          color: 'var(--mac-text-secondary)'
        }}>
          <ShoppingCart size={18} />
          <span>Выбрано: {cart?.items?.length || 0} услуг</span>
          <span style={{ color: 'var(--mac-border)' }}>|</span>
          <span style={{
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-success)'
          }}>
            Сумма: {cartTotal.toLocaleString()} сум
          </span>
        </div>
      </div>
      
      {/* Основная сетка с тремя колонками */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 'var(--mac-spacing-5)',
        flex: 1
      }}>
        {/* Колонка 1: Специалисты */}
        <div style={{
          background: 'var(--mac-bg-primary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-md)',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <div style={{
            padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
            background: 'var(--mac-bg-secondary)',
            borderBottom: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md) var(--mac-radius-md) 0 0'
          }}>
            <h4 style={{
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-2)'
            }}>
              👨‍⚕️ Консультации специалистов
            </h4>
          </div>
          
          {/* Специалисты - чекбоксы */}
          <div style={{
            padding: 'var(--mac-spacing-3)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--mac-spacing-2)',
            borderBottom: '1px solid var(--mac-border)'
          }}>
            {groupedServices.specialists.map(service => {
              const isInCart = cart?.items?.some(item => item.service_id === service.id);
              return (
                <label key={service.id} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--mac-spacing-2)',
                  padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                  background: 'var(--mac-bg-primary)',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-sm)',
                  cursor: 'pointer',
                  transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-primary)'}
                >
                  <input
                    type="checkbox"
                    checked={isInCart}
                    onChange={() => handleServiceToggle(service)}
                    style={{ margin: 0, width: '18px', height: '18px', cursor: 'pointer' }}
                  />
                  <span style={{
                    flex: 1,
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 'var(--mac-spacing-2)'
                  }}>
                    <span style={{
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-primary)',
                      lineHeight: 1.3
                    }}>
                      {service.name}
                    </span>
                    <span style={{
                      fontSize: 'var(--mac-font-size-xs)',
                      fontWeight: 'var(--mac-font-weight-semibold)',
                      color: 'var(--mac-success)',
                      whiteSpace: 'nowrap'
                    }}>
                      {service.price?.toLocaleString()} сум
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
          
          {/* Лабораторные анализы - dropdown */}
          <div style={{
            borderBottom: '1px solid var(--mac-separator)'
          }}>
            <button 
              style={{
                width: '100%',
                padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                background: expandedCategories.laboratory ? 'var(--mac-bg-tertiary)' : 'var(--mac-bg-primary)',
                border: 'none',
                borderBottom: '1px solid var(--mac-border)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                cursor: 'pointer',
                transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)'
              }}
              onClick={() => toggleCategory('laboratory')}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = expandedCategories.laboratory ? 'var(--mac-bg-tertiary)' : 'var(--mac-bg-primary)'}
            >
              <span>🧪 Лабораторные анализы ({groupedServices.laboratory.length})</span>
              <ChevronDown size={18} style={{
                transition: 'transform var(--mac-duration-normal) var(--mac-ease)',
                transform: expandedCategories.laboratory ? 'rotate(180deg)' : 'rotate(0deg)',
                color: 'var(--mac-text-tertiary)'
              }} />
            </button>
            
            {expandedCategories.laboratory && (
              <div style={{
                maxHeight: '300px',
                overflowY: 'auto',
                padding: 'var(--mac-spacing-3)',
                background: 'var(--mac-bg-primary)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--mac-spacing-2)'
              }}>
                {groupedServices.laboratory.map(service => {
                  const isInCart = cart?.items?.some(item => item.service_id === service.id);
                  return (
                    <label key={service.id} style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--mac-spacing-2)',
                      padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                      background: 'var(--mac-bg-primary)',
                      border: '1px solid var(--mac-border)',
                      borderRadius: 'var(--mac-radius-sm)',
                      cursor: 'pointer',
                      transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-primary)'}
                    >
                      <input
                        type="checkbox"
                        checked={isInCart}
                        onChange={() => handleServiceToggle(service)}
                        style={{ margin: 0, width: '18px', height: '18px', cursor: 'pointer' }}
                      />
                      <span style={{
                        flex: 1,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 'var(--mac-spacing-2)'
                      }}>
                        <span style={{
                          fontSize: 'var(--mac-font-size-sm)',
                          color: 'var(--mac-text-primary)',
                          lineHeight: 1.3
                        }}>
                          {service.name}
                        </span>
                        <span style={{
                          fontSize: 'var(--mac-font-size-xs)',
                          fontWeight: 'var(--mac-font-weight-semibold)',
                          color: 'var(--mac-success)',
                          whiteSpace: 'nowrap'
                        }}>
                          {service.price?.toLocaleString()} сум
                        </span>
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        </div>
        
        {/* Колонка 2: Косметология */}
        <div style={{
          background: 'var(--mac-bg-primary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-md)',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <div style={{
            padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
            background: 'var(--mac-bg-secondary)',
            borderBottom: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md) var(--mac-radius-md) 0 0'
          }}>
            <h4 style={{
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-2)'
            }}>
              ✨ Косметологические процедуры
            </h4>
          </div>
          
          <div style={{
            borderBottom: '1px solid var(--mac-separator)'
          }}>
            <button 
              style={{
                width: '100%',
                padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                background: expandedCategories.cosmetology ? 'var(--mac-bg-tertiary)' : 'var(--mac-bg-primary)',
                border: 'none',
                borderBottom: '1px solid var(--mac-border)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                cursor: 'pointer',
                transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)'
              }}
              onClick={() => toggleCategory('cosmetology')}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = expandedCategories.cosmetology ? 'var(--mac-bg-tertiary)' : 'var(--mac-bg-primary)'}
            >
              <span>Процедуры ({groupedServices.cosmetology.length})</span>
              <ChevronDown size={18} style={{
                transition: 'transform var(--mac-duration-normal) var(--mac-ease)',
                transform: expandedCategories.cosmetology ? 'rotate(180deg)' : 'rotate(0deg)',
                color: 'var(--mac-text-tertiary)'
              }} />
            </button>
            
            {expandedCategories.cosmetology && (
              <div style={{
                maxHeight: '300px',
                overflowY: 'auto',
                padding: 'var(--mac-spacing-3)',
                background: 'var(--mac-bg-primary)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--mac-spacing-2)'
              }}>
                {groupedServices.cosmetology.map(service => {
                  const isInCart = cart?.items?.some(item => item.service_id === service.id);
                  return (
                    <label key={service.id} style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--mac-spacing-2)',
                      padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                      background: 'var(--mac-bg-primary)',
                      border: '1px solid var(--mac-border)',
                      borderRadius: 'var(--mac-radius-sm)',
                      cursor: 'pointer',
                      transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-primary)'}
                    >
                      <input
                        type="checkbox"
                        checked={isInCart}
                        onChange={() => handleServiceToggle(service)}
                        style={{ margin: 0, width: '18px', height: '18px', cursor: 'pointer' }}
                      />
                      <span style={{
                        flex: 1,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 'var(--mac-spacing-2)'
                      }}>
                        <span style={{
                          fontSize: 'var(--mac-font-size-sm)',
                          color: 'var(--mac-text-primary)',
                          lineHeight: 1.3
                        }}>
                          {service.name}
                        </span>
                        <span style={{
                          fontSize: 'var(--mac-font-size-xs)',
                          fontWeight: 'var(--mac-font-weight-semibold)',
                          color: 'var(--mac-success)',
                          whiteSpace: 'nowrap'
                        }}>
                          {service.price?.toLocaleString()} сум
                        </span>
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
        </div>
        
        {/* Колонка 3: Прочие услуги и корзина */}
        <div style={{
          background: 'var(--mac-bg-primary)',
          border: '1px solid var(--mac-border)',
          borderRadius: 'var(--mac-radius-md)',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <div style={{
            padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
            background: 'var(--mac-bg-secondary)',
            borderBottom: '1px solid var(--mac-border)',
            borderRadius: 'var(--mac-radius-md) var(--mac-radius-md) 0 0'
          }}>
            <h4 style={{
              fontSize: 'var(--mac-font-size-base)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-2)'
            }}>
              📋 Дополнительные услуги
            </h4>
          </div>
          
          <div style={{
            borderBottom: '1px solid var(--mac-separator)'
          }}>
            <button 
              style={{
                width: '100%',
                padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
                background: expandedCategories.other ? 'var(--mac-bg-tertiary)' : 'var(--mac-bg-primary)',
                border: 'none',
                borderBottom: '1px solid var(--mac-border)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                cursor: 'pointer',
                transition: 'background-color var(--mac-duration-normal) var(--mac-ease)',
                fontSize: 'var(--mac-font-size-sm)',
                fontWeight: 'var(--mac-font-weight-medium)',
                color: 'var(--mac-text-primary)'
              }}
              onClick={() => toggleCategory('other')}
              onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
              onMouseLeave={(e) => e.currentTarget.style.backgroundColor = expandedCategories.other ? 'var(--mac-bg-tertiary)' : 'var(--mac-bg-primary)'}
            >
              <span>Прочие услуги ({groupedServices.other.length})</span>
              <ChevronDown size={18} style={{
                transition: 'transform var(--mac-duration-normal) var(--mac-ease)',
                transform: expandedCategories.other ? 'rotate(180deg)' : 'rotate(0deg)',
                color: 'var(--mac-text-tertiary)'
              }} />
            </button>
            
            {expandedCategories.other && (
              <div style={{
                maxHeight: '300px',
                overflowY: 'auto',
                padding: 'var(--mac-spacing-3)',
                background: 'var(--mac-bg-primary)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--mac-spacing-2)'
              }}>
                {groupedServices.other.map(service => {
                  const isInCart = cart?.items?.some(item => item.service_id === service.id);
                  return (
                    <label key={service.id} style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--mac-spacing-2)',
                      padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                      background: 'var(--mac-bg-primary)',
                      border: '1px solid var(--mac-border)',
                      borderRadius: 'var(--mac-radius-sm)',
                      cursor: 'pointer',
                      transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-primary)'}
                    >
                      <input
                        type="checkbox"
                        checked={isInCart}
                        onChange={() => handleServiceToggle(service)}
                        style={{ margin: 0, width: '18px', height: '18px', cursor: 'pointer' }}
                      />
                      <span style={{
                        flex: 1,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: 'var(--mac-spacing-2)'
                      }}>
                        <span style={{
                          fontSize: 'var(--mac-font-size-sm)',
                          color: 'var(--mac-text-primary)',
                          lineHeight: 1.3
                        }}>
                          {service.name}
                        </span>
                        <span style={{
                          fontSize: 'var(--mac-font-size-xs)',
                          fontWeight: 'var(--mac-font-weight-semibold)',
                          color: 'var(--mac-success)',
                          whiteSpace: 'nowrap'
                        }}>
                          {service.price?.toLocaleString()} сум
                        </span>
                      </span>
                    </label>
                  );
                })}
              </div>
            )}
          </div>
          
          {/* Мини-корзина */}
          <div style={{
            marginTop: 'auto',
            padding: 'var(--mac-spacing-4)',
            background: 'var(--mac-bg-secondary)',
            borderTop: '1px solid var(--mac-border)',
            borderRadius: '0 0 var(--mac-radius-md) var(--mac-radius-md)'
          }}>
            <h5 style={{
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              margin: '0 0 var(--mac-spacing-3)',
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-2)'
            }}>
              🛒 Выбранные услуги
            </h5>
            {!cart?.items?.length ? (
              <p style={{
                fontSize: 'var(--mac-font-size-xs)',
                color: 'var(--mac-text-tertiary)',
                textAlign: 'center',
                padding: 'var(--mac-spacing-5) 0',
                margin: 0
              }}>
                Услуги не выбраны
              </p>
            ) : (
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--mac-spacing-2)',
                maxHeight: '200px',
                overflowY: 'auto'
              }}>
                {cart.items.map(item => (
                  <div key={item.id} style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                    background: 'var(--mac-bg-primary)',
                    border: '1px solid var(--mac-border)',
                    borderRadius: 'var(--mac-radius-sm)',
                    fontSize: 'var(--mac-font-size-xs)'
                  }}>
                    <span style={{
                      color: 'var(--mac-text-primary)',
                      flex: 1,
                      marginRight: 'var(--mac-spacing-2)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}>
                      {item.service_name}
                    </span>
                    <button 
                      style={{
                        width: '20px',
                        height: '20px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: 'var(--mac-danger)',
                        color: 'white',
                        border: 'none',
                        borderRadius: 'var(--mac-radius-sm)',
                        cursor: 'pointer',
                        transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                        flexShrink: 0
                      }}
                      onClick={() => onRemoveFromCart(item.id)}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-danger-hover)'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-danger)'}
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
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--mac-spacing-2)'
        }}>
          {errors.cart && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-2)',
              padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
              background: '#fee2e2',
              border: '1px solid #fecaca',
              borderRadius: 'var(--mac-radius-md)',
              color: '#991b1b',
              fontSize: 'var(--mac-font-size-sm)'
            }}>
              <AlertCircle size={16} />
              {errors.cart}
            </div>
          )}
          {errors.doctors && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--mac-spacing-2)',
              padding: 'var(--mac-spacing-3) var(--mac-spacing-4)',
              background: '#fee2e2',
              border: '1px solid #fecaca',
              borderRadius: 'var(--mac-radius-md)',
              color: '#991b1b',
              fontSize: 'var(--mac-font-size-sm)'
            }}>
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

