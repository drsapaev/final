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
  User,
  RefreshCw
} from 'lucide-react';
import { toast } from 'react-toastify';
import ModernDialog from '../dialogs/ModernDialog';
import { MacOSInput, MacOSButton, MacOSSelect, MacOSCheckbox } from '../ui/macos';
import { useRoleAccess } from '../common/RoleGuard';
import { normalizeCategoryCode } from '../../utils/serviceCodeUtils';
import { formatDateDisplay } from '../../utils/dateUtils';
import { createQueueEntriesBatch, getDoctorUserId, updateOnlineQueueEntry } from '../../api/queue';
import { api } from '../../api/client';
import logger from '../../utils/logger';
// ⭐ SSOT: Unified service extraction
import { normalizeServicesFromInitialData } from '../../utils/serviceCodeResolver';
import './AppointmentWizardV2.css';

const API_BASE = '/api/v1';

// Категории услуг
const categories = [
  { id: 'specialists', label: 'Специалисты', icon: '👨‍⚕️' },
  { id: 'laboratory', label: 'Лаборатория', icon: '🧪' },
  { id: 'procedures', label: 'Процедуры', icon: '💉' }, // Объединяем косметологию и процедуры
  { id: 'other', label: 'Прочее', icon: '📋' }
];

// CSS Keyframes for animations
const wizardKeyframes = `
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

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
`;

// Inject keyframes into the document
if (typeof document !== 'undefined' && !document.getElementById('wizard-keyframes')) {
  const style = document.createElement('style');
  style.id = 'wizard-keyframes';
  style.textContent = wizardKeyframes;
  document.head.appendChild(style);
}

const AppointmentWizardV2 = ({
  isOpen,
  onClose,
  onComplete,
  isProcessing = false,
  setIsProcessing = () => { }, // Дефолтная функция-заглушка
  activeTab = null, // ✅ ДОБАВЛЯЕМ activeTab для фильтрации услуг по отделению
  editMode = false, // ✨ НОВОЕ: Режим редактирования
  initialData = null // ✨ НОВОЕ: Данные для редактирования
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
      address: '',
      gender: '' // ✅ Добавлено поле пола
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
  const [phoneCheckTimeout, setPhoneCheckTimeout] = useState(null); // ✅ Timeout для проверки телефона
  const [phoneError, setPhoneError] = useState(null); // ✅ Ошибка уникальности телефона
  const [servicesData, setServicesData] = useState([]);
  const [doctorsData, setDoctorsData] = useState([]);
  const [filteredServices, setFilteredServices] = useState([]);
  const [showAllServices, setShowAllServices] = useState(false);
  const [formattedBirthDate, setFormattedBirthDate] = useState('');

  // ===================== ИНИЦИАЛИЗАЦИЯ (EDIT MODE vs DRAFT) =====================

  const DRAFT_KEY = 'appointment_wizard_draft';
  const DRAFT_TTL = 48 * 60 * 60 * 1000; // 48 часов

  // Эффект для инициализации данных при открытии
  useEffect(() => {
    if (isOpen) {
      // ✅ ИСПРАВЛЕНО: Строгая проверка editMode перед загрузкой данных
      if (editMode === true && initialData !== null && initialData !== undefined) {
        // 📝 РЕЖИМ РЕДАКТИРОВАНИЯ: Загружаем данные из initialData
        logger.log('📝 AppointmentWizardV2: Initializing EDIT MODE', initialData);

        // Парсим услуги из initialData (предполагаем, что они приходят в определенном формате)
        // В реальном приложении может потребоваться маппинг

        // ✅ ИСПРАВЛЕНО: Правильная инициализация даты рождения
        const birthDate = initialData.patient_birth_date ||
          (initialData.patient_birth_year ? `${initialData.patient_birth_year}-01-01` : '');

        setWizardData({
          patient: {
            id: initialData.patient_id || initialData.patient?.id || null, // ✅ ИСПРАВЛЕНО: Добавлена проверка patient?.id
            fio: initialData.patient_fio || initialData.patient_name || initialData.patient?.fio || '',
            birth_date: birthDate, // ✅ ИСПРАВЛЕНО: Приоритет полной даты
            phone: initialData.phone || initialData.patient_phone || initialData.patient?.phone || '',
            address: initialData.address || initialData.patient?.address || '',
            gender: (() => {
              // ✅ ИСПРАВЛЕНО: Преобразование пола из формата БД (M/F/sex) в формат формы (male/female)
              const genderValue = initialData.patient_gender ||
                initialData.gender ||
                initialData.patient?.gender ||
                initialData.patient?.sex ||
                initialData.sex ||
                '';
              if (genderValue === 'M' || genderValue === 'm' || genderValue === 'male') return 'male';
              if (genderValue === 'F' || genderValue === 'f' || genderValue === 'female') return 'female';
              return genderValue; // Если уже в формате male/female, оставляем как есть
            })()
          },
          cart: {
            // ⭐ SSOT: Используем унифицированную функцию вместо 5 разных источников
            items: (() => {
              logger.log('📦 AppointmentWizardV2: Using SSOT normalizeServicesFromInitialData');
              const items = normalizeServicesFromInitialData(initialData, []);
              logger.log('📦 Initialized cart with items:', items);
              logger.log('📦 InitialData full structure:', initialData);

              // ✅ SSOT: Логируем источник
              if (items.length > 0) {
                logger.log(`✅ SSOT: Услуги извлечены из источника: ${items[0]._source}`);
              }
              return items;
            })(),
            discount_mode: initialData.discount_mode || 'none', // ✅ ИСПРАВЛЕНО: Восстанавливаем скидки
            all_free: initialData.all_free || false,
            notes: initialData.notes || ''
          },
          payment: {
            method: initialData.payment_method || initialData.payment_type || 'cash',
            total_amount: initialData.total_amount || initialData.cost || 0
          }
        });

        // ✅ ИСПРАВЛЕНО: Синхронизация formattedBirthDate
        if (birthDate) {
          setFormattedBirthDate(convertDateFromISO(birthDate));
        }

      } else {
        // 🆕 НОВАЯ ЗАПИСЬ: Режим создания - игнорируем initialData даже если он есть
        // Проверяем только draft
        const savedDraft = localStorage.getItem(DRAFT_KEY);
        if (savedDraft) {
          try {
            const draft = JSON.parse(savedDraft);
            const now = Date.now();

            if (draft.timestamp && (now - draft.timestamp) < DRAFT_TTL) {
              // Черновик актуален
              logger.log('📂 AppointmentWizardV2: Loaded DRAFT');
              setWizardData(prev => ({
                ...prev,
                ...draft.data
              }));
              // Восстанавливаем отформатированную дату
              if (draft.data.patient.birth_date) {
                setFormattedBirthDate(convertDateFromISO(draft.data.patient.birth_date));
              }
              toast.success('Загружен сохранённый черновик');
            } else {
              // Черновик устарел
              localStorage.removeItem(DRAFT_KEY);
            }
          } catch (e) {
            logger.warn('Ошибка загрузки черновика:', e);
            localStorage.removeItem(DRAFT_KEY);
          }
        }
      }
    }
  }, [isOpen, editMode, initialData]);

  // ✅ ИСПРАВЛЕНО: Сброс состояния мастера при закрытии
  useEffect(() => {
    if (!isOpen) {
      // Сбрасываем состояние при закрытии
      setWizardData({
        patient: { id: null, fio: '', birth_date: '', phone: '', address: '', gender: '' },
        cart: { items: [], discount_mode: 'none', all_free: false, notes: '' },
        payment: { method: 'cash', total_amount: 0 }
      });
      setCurrentStep(1);
      setFormattedBirthDate('');
    }
  }, [isOpen]);

  // Safeguard: Ensure wizardData structure is valid
  useEffect(() => {
    if (!wizardData.patient) {
      logger.warn('⚠️ Wizard data corrupted (missing patient), resetting...');
      setWizardData(prev => ({
        ...prev,
        patient: { id: null, fio: '', birth_date: '', phone: '', address: '', gender: '' }
      }));
    }
    if (!wizardData.cart) {
      setWizardData(prev => ({
        ...prev,
        cart: { items: [], discount_mode: 'none', all_free: false, notes: '' }
      }));
    }
  }, [wizardData]);

  // Состояние онлайн оплаты убрано

  // State for Service Selection (Step 2) - Lifted up for Header
  const [isReloadingServices, setIsReloadingServices] = useState(false);
  const [activeServiceCategory, setActiveServiceCategory] = useState('specialists');
  const [serviceSearchQuery, setServiceSearchQuery] = useState('');

  // Refs
  const fioRef = useRef(null);
  const phoneRef = useRef(null);

  // Общее количество шагов
  const totalSteps = 2;

  // ===================== ПРОВЕРКА ТЕЛЕФОНА =====================

  const checkPhoneUniqueness = async (phone) => {
    // Очищаем номер для проверки (только цифры)
    const cleanPhone = phone.replace(/\D/g, '');
    // Проверяем только если номер достаточно длинный (998 + 9 цифр = 12)
    if (cleanPhone.length < 12) {
      setPhoneError(null);
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/patients/?phone=${encodeURIComponent(phone)}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        // Если найден пациент и это не тот же самый пациент (если мы редактируем, но тут мы создаем/ищем)
        // В мастере мы всегда предполагаем, что если ID не выбран, то это новый.
        // Если ID выбран, то мы не проверяем (или проверяем, не занят ли другим).

        const existingPatient = data.find(p => {
          // Сравниваем телефоны (очищенные)
          const pPhone = (p.phone || '').replace(/\D/g, '');
          return pPhone === cleanPhone;
        });

        if (existingPatient && existingPatient.id !== wizardData.patient.id) {
          setPhoneError({
            message: 'Пациент с таким номером уже существует',
            patient: existingPatient
          });
        } else {
          setPhoneError(null);
        }
      }
    } catch (error) {
      logger.error('Ошибка проверки телефона:', error);
    }
  };

  const handlePhoneChange = (value) => {
    const formatted = formatPhoneNumber(value);
    setWizardData(prev => ({
      ...prev,
      patient: { ...prev.patient, phone: formatted }
    }));

    // Сбрасываем ошибку при изменении
    setPhoneError(null);

    // Дебаунс проверки
    if (phoneCheckTimeout) clearTimeout(phoneCheckTimeout);
    const timeout = setTimeout(() => checkPhoneUniqueness(formatted), 500);
    setPhoneCheckTimeout(timeout);
  };

  // ===================== АВТОСОХРАНЕНИЕ =====================



  // Загрузка черновика перемещена в основной эффект инициализации


  // Автосохранение черновика (ТОЛЬКО ЕСЛИ НЕ РЕДАКТИРОВАНИЕ)
  useEffect(() => {
    if (editMode) return; // 🚫 Не сохраняем черновик в режиме редактирования

    if (isOpen && (wizardData.patient.fio || wizardData.cart.items.length > 0)) {
      const draft = {
        timestamp: Date.now(),
        data: wizardData
      };
      localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    }
  }, [wizardData, isOpen, editMode]);

  // Очистка черновика
  const clearDraft = () => {
    localStorage.removeItem(DRAFT_KEY);
    setWizardData({
      patient: { id: null, fio: '', birth_date: '', phone: '', address: '', gender: '' },
      cart: { items: [], discount_mode: 'none', all_free: false, notes: '' },
      payment: { method: 'cash', total_amount: 0 }
    });
    setFormattedBirthDate('');
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
      logger.error('Ошибка поиска пациентов:', error);
    }
  }, []);

  const handlePatientSearch = (value) => {
    // 🚨 FIX: Сбрасываем ID при изменении текста, чтобы не было "призраков"
    // Если пользователь меняет имя, это уже не тот пациент, которого выбрали ранее
    setWizardData(prev => ({
      ...prev,
      patient: {
        ...prev.patient,
        fio: value,
        id: null // ✅ Сброс ID
      }
    }));

    // Дебаунс поиска
    if (searchTimeout) clearTimeout(searchTimeout);
    const timeout = setTimeout(() => searchPatients(value), 300);
    setSearchTimeout(timeout);
  };

  const selectPatient = (patient) => {
    // ✅ УПРОЩЕНО: Формируем fio из отдельных полей для отображения (Single Source of Truth)
    // Backend уже нормализует ФИО, здесь только форматируем для UI
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

    // Сохраняем данные пациента (без парсинга ФИО - backend сделает это при создании)
    setWizardData(prev => ({
      ...prev,
      patient: {
        id: patient.id,
        fio: patientFio,
        birth_date: patient.birth_date || '',
        phone: patient.phone || '',
        address: patient.address || '',
        gender: (() => {
          // ✅ ИСПРАВЛЕНО: Преобразование пола из формата БД (M/F/sex) в формат формы (male/female)
          const genderValue = patient.gender || patient.sex || '';
          if (genderValue === 'M' || genderValue === 'm' || genderValue === 'male') return 'male';
          if (genderValue === 'F' || genderValue === 'f' || genderValue === 'female') return 'female';
          return genderValue;
        })(), // ✅ Заполняем пол с преобразованием
        // Отдельные поля для обратной совместимости (если нужны)
        lastName: patient.last_name || '',
        firstName: patient.first_name || '',
        middleName: patient.middle_name || ''
      }
    }));

    // Обновляем отформатированную дату
    setFormattedBirthDate(convertDateFromISO(patient.birth_date));
    setShowSuggestions(false);
    setErrors(prev => ({ ...prev, fio: null }));
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
  }, [isOpen, activeTab]); // ✅ Обновляем услуги при смене вкладки

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

        // ✅ ФИЛЬТРАЦИЯ ПО ОТДЕЛЕНИЮ: Если activeTab указан, показываем услуги этого отделения
        // Также показываем услуги без department_key (общие услуги)


        if (activeTab && activeTab !== 'all') {
          const beforeFilter = allServices.length;
          allServices = allServices.filter(service =>
            service.department_key === activeTab || !service.department_key
          );
        }

        setServicesData(allServices);
        filterServices(allServices, wizardData.cart.items);
      }
    } catch (error) {
      logger.error('Ошибка загрузки услуг:', error);
    }
  };

  // ===================== РЕЗОЛВИНГ УСЛУГ (SSOT) =====================

  // ✅ SSOT: Функция для получения названия услуги из servicesData
  const getServiceName = useCallback((item) => {
    if (!item) return 'Неизвестная услуга';

    // Приоритет 1: Если есть service_id, ищем в servicesData
    if (item.service_id) {
      const service = servicesData.find(s => s.id === item.service_id);
      if (service?.name) return service.name;
    }

    // Приоритет 2: Если service_name уже является полным названием (не код), используем его
    let serviceName = item.service_name;

    // ⭐ DEFENSIVE FIX: Если service_name это объект (например, из-за ошибки в данных), пытаемся достать строку
    if (typeof serviceName === 'object' && serviceName !== null) {
      logger.warn('⚠️ getServiceName encountered an object for service_name:', serviceName);
      serviceName = serviceName.name || serviceName.display_name || serviceName.displayName || String(serviceName);
    }

    if (serviceName && typeof serviceName === 'string' && serviceName.length > 3 && !/^[A-Z]\d+$/i.test(serviceName)) {
      // Если это не код (не формат "K01", "p09" и т.д.), а реальное название
      const foundByName = servicesData.find(s => s.name === serviceName);
      if (foundByName) return foundByName.name;
    }

    // Приоритет 3: Пытаемся найти по коду
    let searchName = item._temp_name || item.service_name || item.code;

    // ⭐ DEFENSIVE FIX: Если searchName это объект
    if (typeof searchName === 'object' && searchName !== null) {
      searchName = searchName.code || searchName.service_code || searchName.name || String(searchName);
    }

    if (searchName && typeof searchName === 'string' && servicesData.length > 0) {
      const searchNameUpper = String(searchName).toUpperCase().trim();
      const searchNameNoZero = searchNameUpper.replace(/^([A-Z])0+(\d+)$/, '$1$2');

      const foundService = servicesData.find(s => {
        if (!s.service_code) return false;
        const serviceCodeUpper = String(s.service_code).toUpperCase().trim();
        const serviceCodeNoZero = serviceCodeUpper.replace(/^([A-Z])0+(\d+)$/, '$1$2');

        if (serviceCodeUpper === searchNameUpper) return true;
        if (serviceCodeNoZero === searchNameNoZero) return true;
        if (s.name === searchName || s.name === searchNameUpper) return true;
        return false;
      });

      if (foundService?.name) return foundService.name;

      // ✅ УЛУЧШЕНО: Поиск по частичному совпадению названия
      const foundByNamePartial = servicesData.find(s => {
        if (!s.name) return false;
        const serviceNameLower = s.name.toLowerCase();
        const searchNameLower = String(searchName).toLowerCase();
        return serviceNameLower.includes(searchNameLower) || searchNameLower.includes(serviceNameLower);
      });

      if (foundByNamePartial?.name) return foundByNamePartial.name;
    }

    // Fallback: возвращаем service_name (если это название) или код
    // ⭐ FINAL DEFENSIVE: Убеждаемся, что возвращаем строку
    const fallback = serviceName || searchName || 'Неизвестная услуга';
    return (typeof fallback === 'string') ? fallback : JSON.stringify(fallback);
  }, [servicesData]);

  // Эффект для обогащения данных корзины реальными ID и ценами после загрузки servicesData
  useEffect(() => {
    // ✅ ИСПРАВЛЕНО: Разрешаем услуги не только в editMode, но и когда servicesData загружены
    if (servicesData.length > 0 && wizardData.cart.items.length > 0) {
      const unresolvedCount = wizardData.cart.items.filter(i => !i.service_id).length;

      // ✅ НОВОЕ: Проверяем также элементы с service_id, у которых имя не совпадает с SSOT
      const hasNameMismatches = wizardData.cart.items.some(item => {
        if (!item.service_id) return false;
        const service = servicesData.find(s => s.id === item.service_id);
        return service && service.name && service.name !== item.service_name;
      });

      // Если нет ни нерешённых услуг, ни несоответствий имён — выходим
      if (unresolvedCount === 0 && !hasNameMismatches) return;

      logger.log('🔍 Attempting to resolve services...', {
        servicesDataCount: servicesData.length,
        cartItemsCount: wizardData.cart.items.length,
        unresolvedItems: unresolvedCount
      });

      const updatedItems = wizardData.cart.items.map(item => {
        // ✅ Сначала синхронизируем элементы, у которых уже есть service_id, с SSOT (servicesData)
        if (item.service_id) {
          const service = servicesData.find(s => s.id === item.service_id);

          if (service) {
            const nextName = service.name || item.service_name;
            const nextPrice = service.price != null ? service.price : (item.service_price || 0);

            // Если название или цена отличаются от SSOT — обновляем элемент
            if (nextName !== item.service_name || nextPrice !== item.service_price) {
              return {
                ...item,
                service_name: nextName,
                service_price: nextPrice,
                // ✅ ВАЖНО: Сохраняем doctor_id при обновлении
                doctor_id: item.doctor_id || null
              };
            }
          }

          // Если service_id есть и изменений нет — возвращаем элемент без изменений
          // ✅ ВАЖНО: Убеждаемся, что doctor_id сохранен
          return {
            ...item,
            doctor_id: item.doctor_id || null
          };
        }

        // Ищем услугу по имени или коду (которое мы сохранили в service_name или _temp_name)
        const searchName = item._temp_name || item.service_name;
        if (!searchName) {
          logger.warn('⚠️ Item has no searchable name:', item);
          return item;
        }

        // ✅ ИСПРАВЛЕНО: Поиск по service_code (приоритет) и по name
        // Приводим к верхнему регистру для сравнения кодов
        const searchNameUpper = String(searchName).toUpperCase().trim();
        // Убираем ведущие нули для сравнения (p09 = p9)
        const searchNameNoZero = searchNameUpper.replace(/^([A-Z])0+(\d+)$/, '$1$2');

        const foundService = servicesData.find(s => {
          if (!s.service_code) return false;
          const serviceCodeUpper = String(s.service_code).toUpperCase().trim();
          const serviceCodeNoZero = serviceCodeUpper.replace(/^([A-Z])0+(\d+)$/, '$1$2');

          // Прямое сравнение
          if (serviceCodeUpper === searchNameUpper) return true;
          // Сравнение без ведущих нулей (p09 = p9)
          if (serviceCodeNoZero === searchNameNoZero) return true;
          // Поиск по названию
          if (s.name === searchName || s.name === searchNameUpper) return true;
          return false;
        });

        if (foundService) {
          logger.log(`✅ Service resolved: "${searchName}" -> ID ${foundService.id} (${foundService.name})`);
          return {
            ...item,
            service_id: foundService.id,
            service_name: foundService.name, // ✅ SSOT: Сохраняем полное название из servicesData
            service_price: foundService.price || 0,
            _temp_name: searchName, // Сохраняем исходный код для отладки
            // ✅ ВАЖНО: Сохраняем doctor_id при резолвинге
            doctor_id: item.doctor_id || null
          };
        } else {
          // ✅ УЛУЧШЕНО: Пробуем найти по частичному совпадению названия
          const foundByName = servicesData.find(s => {
            if (!s.name) return false;
            const serviceNameLower = s.name.toLowerCase();
            const searchNameLower = String(searchName).toLowerCase();
            return serviceNameLower.includes(searchNameLower) || searchNameLower.includes(serviceNameLower);
          });

          if (foundByName) {
            logger.log(`✅ Service found by name match: "${searchName}" -> ID ${foundByName.id} (${foundByName.name})`);
            return {
              ...item,
              service_id: foundByName.id,
              service_name: foundByName.name,
              service_price: foundByName.price || 0,
              _temp_name: searchName,
              // ✅ ВАЖНО: Сохраняем doctor_id при резолвинге
              doctor_id: item.doctor_id || null
            };
          }

          logger.warn(`⚠️ Service not found in servicesData: "${searchName}". Available codes:`,
            servicesData.slice(0, 20).map(s => `${s.service_code || 'N/A'}: ${s.name || 'N/A'}`).filter(s => s !== 'N/A: N/A'));
        }

        return item;
      });

      // ✅ ИСПРАВЛЕНО: Проверяем изменения, включая service_name
      const hasChanges = updatedItems.some((item, index) => {
        const prevItem = wizardData.cart.items[index];
        return item.service_id !== prevItem.service_id ||
          item.service_price !== prevItem.service_price ||
          item.service_name !== prevItem.service_name; // ✅ Проверяем также изменение названия
      });

      if (hasChanges) {
        logger.log('✅ Updating cart with resolved services:', updatedItems.length);
        // ✅ УЛУЧШЕНО: Логируем какие услуги были разрешены
        const resolved = updatedItems.filter((item, index) => {
          const prevItem = wizardData.cart.items[index];
          return item.service_id !== prevItem.service_id;
        });
        if (resolved.length > 0) {
          logger.log('📋 Resolved services:', resolved.map(item => `${item._temp_name || item.service_name} -> ${item.service_name} (ID: ${item.service_id})`));
        }

        setWizardData(prev => ({
          ...prev,
          cart: {
            ...prev.cart,
            items: updatedItems
          }
        }));
      }
    }
  }, [servicesData, wizardData.cart.items]); // ✅ ИСПРАВЛЕНО: Триггерим при изменении servicesData или корзины

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
      logger.error('Ошибка загрузки врачей:', error);
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
    // ✅ SSOT: Всегда используем данные из servicesData
    const serviceFromData = servicesData.find(s => s.id === service.id) || service;

    const newItem = {
      id: Date.now(), // Временный ID для React keys
      service_id: serviceFromData.id,
      service_name: serviceFromData.name, // ✅ SSOT: Полное название из servicesData
      service_price: serviceFromData.price,
      quantity: 1,
      doctor_id: serviceFromData.requires_doctor ? null : undefined,
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
      if (!wizardData.patient.gender) { // ✅ Валидация пола
        newErrors.gender = 'Выберите пол';
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
      logger.error('❌ Ошибка проверки токена:', error);
      toast.error('Ошибка проверки авторизации. Пожалуйста, войдите в систему заново.');
      return;
    }

    setIsProcessing(true);

    try {
      // ✅ ИСПРАВЛЕНО: Валидация корзины перед подготовкой данных
      if (!wizardData.cart.items || wizardData.cart.items.length === 0) {
        toast.error('Корзина пуста. Пожалуйста, добавьте услуги.');
        return;
      }

      // Проверяем, что все элементы корзины имеют service_id
      const itemsWithoutServiceId = wizardData.cart.items.filter(item => !item.service_id);
      if (itemsWithoutServiceId.length > 0) {
        logger.error('❌ Найдены элементы корзины без service_id:', itemsWithoutServiceId);
        toast.error('Некоторые услуги не могут быть обработаны. Пожалуйста, удалите их из корзины и добавьте заново.');
        return;
      }

      // ✅ ИСПРАВЛЕНО: Сначала группируем услуги по визитам
      let visits = groupCartItemsByVisit();
      if (!visits || visits.length === 0) {
        toast.error('Корзина пуста или содержит невалидные услуги. Пожалуйста, проверьте выбранные услуги.');
        return;
      }

      // Проверяем, что все визиты имеют хотя бы одну услугу с service_id
      const invalidVisits = visits.filter(visit =>
        !visit.services ||
        visit.services.length === 0 ||
        visit.services.some(s => !s.service_id)
      );

      if (invalidVisits.length > 0) {
        logger.error('❌ Найдены визиты с невалидными услугами:', invalidVisits);
        toast.error('Некоторые услуги не могут быть обработаны. Пожалуйста, перезагрузите страницу и попробуйте снова.');
        return;
      }

      // ✅ НОВОЕ: Локальная переменная для patient_id, которую будем заполнять по мере создания/поиска пациента
      let patientId = wizardData.patient.id;

      // === ШАГ 1: ОПРЕДЕЛЯЕМ ИЛИ НАХОДИМ patient_id ===

      // В режиме EDIT MODE с QR-пациентом (patient_id = null)
      if (editMode && !patientId && wizardData.patient.phone) {
        logger.log('🔍 Edit mode: patient_id is null, searching for existing patient by phone...');
        logger.log('📞 Patient data:', {
          fio: wizardData.patient.fio,
          phone: wizardData.patient.phone,
          birth_date: wizardData.patient.birth_date
        });

        // Ищем пациента по телефону
        const cleanPhone = wizardData.patient.phone.replace(/\D/g, '');

        // Попытка 1: Поиск по форматированному номеру
        let searchResponse = await fetch(`${API_BASE}/patients/?phone=${encodeURIComponent(wizardData.patient.phone)}`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
            'Content-Type': 'application/json'
          }
        });

        let patients = [];
        if (searchResponse.ok) {
          patients = await searchResponse.json();
          logger.log('📋 Found patients (by phone):', patients.length);
        }

        let foundPatient = patients.find(p => (p.phone || '').replace(/\D/g, '') === cleanPhone);

        // Попытка 2: Если не нашли, пробуем по очищенному номеру
        if (!foundPatient && cleanPhone.length >= 9) {
          logger.log('🔄 Trying search with cleaned phone:', cleanPhone);
          searchResponse = await fetch(`${API_BASE}/patients/?phone=${encodeURIComponent(cleanPhone)}`, {
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
              'Content-Type': 'application/json'
            }
          });

          if (searchResponse.ok) {
            patients = await searchResponse.json();
            foundPatient = patients.find(p => (p.phone || '').replace(/\D/g, '') === cleanPhone);
          }
        }

        if (foundPatient) {
          // Обновляем локальный patientId и wizardData
          patientId = foundPatient.id;
          setWizardData(prev => ({
            ...prev,
            patient: { ...prev.patient, id: foundPatient.id }
          }));
          logger.log('✅ Found existing patient:', foundPatient.id);

          // Обновляем данные пациента если нужно
          const needsUpdate =
            (wizardData.patient.birth_date && wizardData.patient.birth_date !== foundPatient.birth_date) ||
            (wizardData.patient.address && wizardData.patient.address !== foundPatient.address) ||
            (wizardData.patient.gender && wizardData.patient.gender !== foundPatient.sex);

          if (needsUpdate) {
            logger.log('🔄 Updating patient data...');
            const updateData = {};

            if (wizardData.patient.birth_date) updateData.birth_date = wizardData.patient.birth_date;
            if (wizardData.patient.address) updateData.address = wizardData.patient.address;
            if (wizardData.patient.gender) updateData.sex = wizardData.patient.gender;

            try {
              await fetch(`${API_BASE}/patients/${foundPatient.id}`, {
                method: 'PUT',
                headers: {
                  'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
                  'Content-Type': 'application/json'
                },
                body: JSON.stringify(updateData)
              });
              logger.log('✅ Patient data updated');
            } catch (e) {
              logger.warn('⚠️ Failed to update patient:', e);
            }
          }
        } else {
          // ✅ НОВОЕ: Если в режиме редактирования по QR пациент по телефону не найден,
          // создаем НОВОГО пациента с данными из формы, чтобы не блокировать завершение мастера.
          logger.warn(`⚠️ Пациент с телефоном ${wizardData.patient.phone} не найден. Создаем нового пациента (editMode + QR).`);

          const token = localStorage.getItem('auth_token');

          const patientData = {
            full_name: wizardData.patient.fio.trim(),
            gender: wizardData.patient.gender || null,
            last_name: wizardData.patient.lastName || '',
            first_name: wizardData.patient.firstName || '',
            middle_name: wizardData.patient.middleName || null,
            phone: wizardData.patient.phone || null,
            address: wizardData.patient.address || null
          };

          if (wizardData.patient.birth_date) {
            patientData.birth_date = wizardData.patient.birth_date;
          }

          logger.log('📋 Данные для СОЗДАНИЯ пациента в editMode (QR fallback):', patientData);

          const createResponse = await fetch(`${API_BASE}/patients/`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(patientData)
          });

          if (createResponse.ok) {
            const newPatient = await createResponse.json();
            patientId = newPatient.id;
            setWizardData(prev => ({
              ...prev,
              patient: { ...prev.patient, id: newPatient.id }
            }));
            logger.log('✅ Новый пациент создан в editMode (QR fallback):', newPatient.id);
          } else {
            const errorText = await createResponse.text();
            logger.error('❌ Ошибка создания пациента в editMode (QR fallback):', createResponse.status, errorText);
            throw new Error(`Пациент с телефоном ${wizardData.patient.phone} не найден и не удалось создать нового: ${createResponse.status} ${errorText}`);
          }
        }
      }
      // В обычном режиме (не edit) создаем пациента если нужно
      else if (!editMode && !patientId) {
        // ✅ УПРОЩЕНО: Отправляем полное ФИО в API, backend нормализует его (Single Source of Truth)
        // Валидация обязательных полей
        if (!wizardData.patient.fio || !wizardData.patient.fio.trim()) {
          throw new Error('ФИО пациента обязательно для заполнения');
        }

        const token = localStorage.getItem('auth_token');
        logger.log('🔑 Токен для создания пациента:', token ? `${token.substring(0, 20)}...` : 'НЕТ ТОКЕНА');
        logger.log('📊 Длина токена:', token ? token.length : 0);

        // Подготовка данных пациента - отправляем полное ФИО, backend нормализует
        const patientData = {
          full_name: wizardData.patient.fio.trim(),
          gender: wizardData.patient.gender, // ✅ Отправляем пол
          // Для обратной совместимости также отправляем отдельные поля (если есть)
          last_name: wizardData.patient.lastName || '',
          first_name: wizardData.patient.firstName || '',
          middle_name: wizardData.patient.middleName || null,
          phone: wizardData.patient.phone || null,
          address: wizardData.patient.address || null
        };

        // Добавляем дату рождения только если она есть
        if (wizardData.patient.birth_date) {
          patientData.birth_date = wizardData.patient.birth_date;
        }

        logger.log('📋 Данные для создания пациента:', patientData);

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
          // Обновляем локальный patientId и wizardData с созданным patient_id
          patientId = patient.id;
          setWizardData(prev => ({
            ...prev,
            patient: { ...prev.patient, id: patient.id }
          }));
          logger.log('✅ Пациент создан успешно:', patient.id);
        } else if (patientResponse.status === 400) {
          // Получаем детальную информацию об ошибке
          let errorDetail = 'Пациент с таким номером телефона уже существует';
          try {
            const errorData = await patientResponse.json();
            errorDetail = errorData.detail || errorDetail;
            logger.log('⚠️ Ошибка 400 при создании пациента:', errorDetail);
          } catch (e) {
            const errorText = await patientResponse.text();
            logger.log('⚠️ Текст ошибки создания пациента:', errorText);
            errorDetail = errorText || errorDetail;
          }

          // Пациент уже существует или другая ошибка валидации - ищем по номеру телефона
          if (wizardData.patient.phone) {
            const cleanPhone = wizardData.patient.phone.replace(/\D/g, '');
            logger.log(`⚠️ Ищем существующего пациента по номеру телефона: ${wizardData.patient.phone} (clean: ${cleanPhone})`);

            // Пробуем искать и по форматированному, и по чистому номеру (если API поддерживает)
            // Обычно API ищет по частичному совпадению или точному
            const searchResponse = await fetch(`${API_BASE}/patients/?phone=${encodeURIComponent(wizardData.patient.phone)}`, {
              headers: {
                'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
                'Content-Type': 'application/json'
              }
            });

            if (searchResponse.ok) {
              const patients = await searchResponse.json();
              // Ищем точное совпадение по очищенному номеру
              const foundPatient = patients.find(p => (p.phone || '').replace(/\D/g, '') === cleanPhone);

              if (foundPatient) {
                // Обновляем локальный patientId и wizardData с найденным patient_id
                patientId = foundPatient.id;
                setWizardData(prev => ({
                  ...prev,
                  patient: { ...prev.patient, id: foundPatient.id }
                }));
                logger.log('✅ Найден существующий пациент (по телефону):', foundPatient.id);
              } else {
                // 🚨 НЕ используем fallback - требуем точное совпадение
                logger.error('❌ Exact phone match not found. API returned', patients.length, 'patients');
                throw new Error(`Пациент с телефоном ${wizardData.patient.phone} уже существует, но не найден в базе данных.`);
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
          logger.error('❌ Ошибка создания пациента:', patientResponse.status, errorText);
          throw new Error(`Ошибка создания пациента: ${patientResponse.status} ${errorText}`);
        }
      }

      // На этом этапе patientId должен быть определён
      if (!patientId) {
        logger.error('❌ Не удалось определить patient_id перед созданием корзины', {
          wizardPatient: wizardData.patient
        });
        toast.error('Не удалось определить пациента. Пожалуйста, перезагрузите страницу и попробуйте ещё раз.');
        return;
      }

      // ✅ НОВОЕ: Проверяем, редактируется ли запись в очереди (QR или desk) и есть ли новые услуги
      // Расширено для поддержки всех типов записей: online, desk, visit, appointment
      // ✅ ИСПРАВЛЕНО Bug 1: Добавлены явные скобки для правильного приоритета операторов
      const hasQueueEntries = editMode && initialData && (
        (Array.isArray(initialData.queue_numbers) && initialData.queue_numbers.length > 0) ||
        initialData.source === 'online' ||
        initialData.source === 'desk' ||
        initialData.record_type === 'online_queue' ||
        initialData.record_type === 'visit' ||
        initialData.record_type === 'appointment'
      );

      const originalServiceIds = new Set();
      const originalQueueIds = new Set(); // ✅ Moved here for availability in handleComplete

      if (hasQueueEntries) {
        // ✅ Устанавливаем source по умолчанию для записей типа visit
        const effectiveSource = initialData.source ||
          (initialData.record_type === 'visit' || initialData.record_type === 'appointment' ? 'desk' : 'online');

        // ✅ Сценарий 3: Редактирование записи в очереди (QR или desk) с добавлением новых услуг
        const recordType = effectiveSource === 'online' ? 'QR-запись' : 'ручная запись';
        logger.log(`📝 Редактирование ${recordType}, проверяем новые услуги...`, {
          source: initialData.source,
          effectiveSource,
          record_type: initialData.record_type,
          queue_numbers: Array.isArray(initialData.queue_numbers) ? initialData.queue_numbers.length :
            (initialData.queue_numbers ? 1 : 0),
          service_codes: Array.isArray(initialData.service_codes) ? initialData.service_codes.length : 0,
          services: Array.isArray(initialData.services) ? initialData.services.length : 0
        });

        // ⭐ SSOT: Для чистых QR-записей (online_queue) обновляем существующую запись вместо создания новой
        const isOnlineQueueEntry = initialData.record_type === 'online_queue' && effectiveSource === 'online';
        // ✅ SSOT FIX: queue_entry_id приходит из backend для QR-визитов, иначе из queue_numbers
        const queueEntryId = initialData.queue_entry_id || initialData.queue_numbers?.[0]?.id || initialData.id;

        if (isOnlineQueueEntry && queueEntryId) {
          logger.log(`⭐ SSOT: QR-запись ID=${queueEntryId}, обновляем через full-update endpoint...`);

          try {
            // Подготавливаем данные пациента
            const patientData = {
              patient_name: wizardData.patient.fio || wizardData.patient.name,
              phone: wizardData.patient.phone,
              birth_year: wizardData.patient.birth_date
                ? parseInt(wizardData.patient.birth_date.split('-')[0])
                : null,
              address: wizardData.patient.address || null
            };

            // Подготавливаем услуги из корзины
            const cartServices = wizardData.cart.items.map(item => ({
              service_id: item.service_id,
              quantity: item.quantity || 1
            })).filter(s => s.service_id);

            // Определяем visit_type и discount_mode
            const visitType = wizardData.cart.discount_mode === 'repeat' ? 'repeat' :
              wizardData.cart.discount_mode === 'benefit' ? 'benefit' : 'paid';
            const discountMode = wizardData.cart.discount_mode || 'none';
            const allFree = discountMode === 'all_free';

            // logger.log('📤 Вызов updateOnlineQueueEntry:', { ... }); // Removed to reduce noise

            // ⭐ FIX: Собираем все ID из объединённой строки для проверки дубликатов
            const aggregatedIds = initialData.aggregated_ids ||
              (initialData.queue_numbers || []).map(qn => qn.id).filter(Boolean);

            const updateResult = await updateOnlineQueueEntry({
              entryId: queueEntryId,
              patientData,
              visitType,
              discountMode,
              services: cartServices,
              allFree,
              aggregatedIds  // ⭐ FIX: Передаём все ID для проверки дубликатов
            });

            logger.log('✅ QR-запись успешно обновлена:', updateResult);
            toast.success('Запись успешно обновлена');

            // Завершаем без создания новых записей
            if (!editMode) {
              localStorage.removeItem(DRAFT_KEY);
            }
            onComplete?.(updateResult);
            onClose();
            return; // ⭐ ВАЖНО: Завершаем handleComplete, не продолжаем с cart endpoint
          } catch (updateError) {
            // ⭐ FIX: Не продолжаем с fallback - это создавало дубликаты!
            logger.error('❌ Ошибка обновления QR-записи:', updateError);
            const errorMessage = updateError?.response?.data?.detail || updateError?.message || 'Неизвестная ошибка';
            toast.error(`Ошибка обновления записи: ${errorMessage}`);
            setIsProcessing?.(false);
            return; // ⭐ CRITICAL: Не создаём дубликаты через cart endpoint
          }
        }

        // Определяем исходные услуги из initialData
        const originalServiceCodes = new Set();
        const originalServiceNames = new Set();
        // originalQueueIds moved to higher scope

        // ✅ ПРИОРИТЕТ 1: service_codes - наиболее надежный источник для записей типа visit
        if (Array.isArray(initialData.service_codes) && initialData.service_codes.length > 0) {
          logger.log('📋 Извлечение услуг из service_codes:', initialData.service_codes);
          initialData.service_codes.forEach(code => {
            if (code) {
              const normalizedCode = code.toUpperCase().trim();
              originalServiceCodes.add(normalizedCode);
              // Находим service_id по service_code
              const service = servicesData.find(s => {
                if (!s.service_code) return false;
                const serviceCodeUpper = String(s.service_code).toUpperCase().trim();
                const serviceCodeNoZero = serviceCodeUpper.replace(/^([A-Z])0+(\d+)$/, '$1$2');
                const codeNoZero = normalizedCode.replace(/^([A-Z])0+(\d+)$/, '$1$2');
                return serviceCodeUpper === normalizedCode || serviceCodeNoZero === codeNoZero;
              });
              if (service) {
                originalServiceIds.add(service.id);
                originalServiceNames.add(service.name.toLowerCase().trim());
                logger.log(`  ✅ Найден service_id=${service.id} для кода "${code}"`);
              } else {
                logger.warn(`  ⚠️ Услуга с кодом "${code}" не найдена в servicesData`);
              }
            }
          });
        }

        // ✅ ПРИОРИТЕТ 1.5: services (если service_codes пуст) - может быть кодами
        // ⚠️ ВАЖНО: services может содержать коды (k01, d05) или имена
        if (originalServiceIds.size === 0 && Array.isArray(initialData.services) && initialData.services.length > 0) {
          logger.log('📋 service_codes пуст, используем services как коды:', initialData.services);
          initialData.services.forEach(serviceValue => {
            if (serviceValue) {
              const normalizedValue = serviceValue.toUpperCase().trim();

              // ✅ Сначала пробуем найти по service_code (коды типа 'k01', 'd05')
              // ⚠️ ВАЖНО: Коды могут быть в формате 'K01', 'k01', 'K01: Название' и т.д.
              let service = servicesData.find(s => {
                if (!s.service_code) return false;
                const serviceCodeUpper = String(s.service_code).toUpperCase().trim();
                // Убираем ведущие нули для сравнения (k01 = k1)
                const serviceCodeNoZero = serviceCodeUpper.replace(/^([A-Z])0+(\d+)$/, '$1$2');
                const valueNoZero = normalizedValue.replace(/^([A-Z])0+(\d+)$/, '$1$2');

                // Прямое сравнение
                if (serviceCodeUpper === normalizedValue) return true;
                // Сравнение без ведущих нулей
                if (serviceCodeNoZero === valueNoZero) return true;
                // Сравнение с учетом возможного формата 'K01: Название'
                const serviceCodeBase = serviceCodeUpper.split(':')[0].trim();
                const valueBase = normalizedValue.split(':')[0].trim();
                if (serviceCodeBase === valueBase) return true;

                return false;
              });

              // Если не нашли по коду, пробуем по имени (fallback)
              if (!service) {
                const normalizedName = serviceValue.toLowerCase().trim();
                service = servicesData.find(s =>
                  s.name && s.name.toLowerCase().trim() === normalizedName
                );
              }

              if (service) {
                originalServiceIds.add(service.id);
                if (service.service_code) {
                  originalServiceCodes.add(service.service_code.toUpperCase().trim());
                }
                originalServiceNames.add(service.name.toLowerCase().trim());
                logger.log(`  ✅ Найден service_id=${service.id} для "${serviceValue}" (код: ${service.service_code || 'нет'}, имя: ${service.name})`);
              } else {
                // ✅ УЛУЧШЕНО: Показываем примеры кодов из servicesData для отладки
                const exampleCodes = servicesData
                  .filter(s => s.service_code)
                  .slice(0, 10)
                  .map(s => `${s.service_code}: ${s.name}`)
                  .join(', ');
                logger.warn(`  ⚠️ Услуга "${serviceValue}" не найдена в servicesData. Примеры кодов: ${exampleCodes}`);
              }
            }
          });
        }

        // ✅ ПРИОРИТЕТ 2: queue_numbers - основной источник для всех типов записей
        if (Array.isArray(initialData.queue_numbers) && initialData.queue_numbers.length > 0) {
          logger.log('📋 Извлечение услуг из queue_numbers:', initialData.queue_numbers);
          initialData.queue_numbers.forEach(q => {
            if (q && q.service_id) {
              originalServiceIds.add(q.service_id);
              if (q.id) originalQueueIds.add(q.id); // ✅ Сохраняем ID записи очереди
              // Находим service_code и name по service_id
              const service = servicesData.find(s => s.id === q.service_id);
              if (service) {
                if (service.service_code) {
                  originalServiceCodes.add(service.service_code.toUpperCase().trim());
                }
                originalServiceNames.add(service.name.toLowerCase().trim());
              }
            }
            if (q && q.service_code) {
              const normalizedCode = q.service_code.toUpperCase().trim();
              originalServiceCodes.add(normalizedCode);
              const service = servicesData.find(s =>
                s.service_code && s.service_code.toUpperCase().trim() === normalizedCode
              );
              if (service) {
                originalServiceIds.add(service.id);
                originalServiceNames.add(service.name.toLowerCase().trim());
              }
            }
            if (q && q.service_name) {
              const normalizedName = q.service_name.toLowerCase().trim();
              originalServiceNames.add(normalizedName);
              const service = servicesData.find(s =>
                s.name && s.name.toLowerCase().trim() === normalizedName
              );
              if (service) {
                originalServiceIds.add(service.id);
                if (service.service_code) {
                  originalServiceCodes.add(service.service_code.toUpperCase().trim());
                }
              }
            }
          });
        }

        // ✅ ПРИОРИТЕТ 3: services (массив строк) - может быть кодами или именами
        if (Array.isArray(initialData.services) && initialData.services.length > 0) {
          logger.log('📋 Извлечение услуг из services:', initialData.services);
          initialData.services.forEach(serviceValue => {
            if (serviceValue) {
              const normalizedValue = serviceValue.toUpperCase().trim();
              const normalizedName = serviceValue.toLowerCase().trim();

              // ✅ Сначала пробуем найти по service_code (коды типа 'k01', 'd05')
              let service = servicesData.find(s => {
                if (!s.service_code) return false;
                const serviceCodeUpper = String(s.service_code).toUpperCase().trim();
                // Убираем ведущие нули для сравнения (k01 = k1)
                const serviceCodeNoZero = serviceCodeUpper.replace(/^([A-Z])0+(\d+)$/, '$1$2');
                const valueNoZero = normalizedValue.replace(/^([A-Z])0+(\d+)$/, '$1$2');
                return serviceCodeUpper === normalizedValue || serviceCodeNoZero === valueNoZero;
              });

              // Если не нашли по коду, пробуем по имени
              if (!service) {
                service = servicesData.find(s =>
                  s.name && s.name.toLowerCase().trim() === normalizedName
                );
              }

              if (service) {
                originalServiceIds.add(service.id);
                if (service.service_code) {
                  originalServiceCodes.add(service.service_code.toUpperCase().trim());
                }
                originalServiceNames.add(service.name.toLowerCase().trim());
                logger.log(`  ✅ Найден service_id=${service.id} для "${serviceValue}" (код: ${service.service_code || 'нет'}, имя: ${service.name})`);
              } else {
                logger.warn(`  ⚠️ Услуга "${serviceValue}" не найдена в servicesData (ни по коду, ни по имени)`);
              }
            }
          });
        }

        logger.log('📋 Исходные услуги определены:', {
          serviceIds: Array.from(originalServiceIds),
          serviceCodes: Array.from(originalServiceCodes),
          serviceNames: Array.from(originalServiceNames)
        });

        // Определяем новые услуги (которых не было в исходной записи)
        // Сначала собираем все новые услуги с doctor_id для последующей конвертации
        const newServicesWithDoctorId = [];
        const newServicesWithoutDoctor = [];
        const existingServices = [];

        for (const visit of visits) {
          logger.log(`🔍 Проверка визита: doctor_id=${visit.doctor_id}, services count=${visit.services.length}`);
          for (const serviceItem of visit.services) {
            const service = servicesData.find(s => s.id === serviceItem.service_id);
            if (!service) {
              logger.warn('⚠️ Услуга не найдена в servicesData:', serviceItem.service_id);
              continue;
            }

            // Проверяем, является ли услуга новой
            const isNewService = !originalServiceIds.has(serviceItem.service_id) &&
              !originalServiceCodes.has((service.service_code || '').toUpperCase().trim()) &&
              !originalServiceNames.has((service.name || '').toLowerCase().trim());

            logger.log(`  🔍 Услуга "${service.name}" (ID: ${serviceItem.service_id}, код: ${service.service_code}):`, {
              isNewService,
              inServiceIds: originalServiceIds.has(serviceItem.service_id),
              inServiceCodes: originalServiceCodes.has((service.service_code || '').toUpperCase().trim()),
              inServiceNames: originalServiceNames.has((service.name || '').toLowerCase().trim()),
              hasDoctorId: !!visit.doctor_id
            });

            if (isNewService) {
              // Новая услуга - нужно добавить через batch endpoint
              // ⚠️ ВАЖНО: batch endpoint требует specialist_id (user_id), а не doctor_id
              // Для услуг с врачом используем visit.doctor_id и конвертируем в user_id
              // Для услуг без врача (лаборатория) пропускаем batch endpoint
              if (visit.doctor_id) {
                // Сохраняем для последующей конвертации
                logger.log(`  ✅ Новая услуга с врачом: "${service.name}", doctor_id=${visit.doctor_id}`);
                newServicesWithDoctorId.push({
                  doctor_id: visit.doctor_id,
                  service_id: serviceItem.service_id,
                  service_name: service.name,
                  quantity: serviceItem.quantity || 1
                });
              } else {
                // Услуга без врача - обработаем через обычный cart endpoint
                logger.log(`  ℹ️ Новая услуга без врача: "${service.name}", будет обработана через cart endpoint`);
                newServicesWithoutDoctor.push({
                  service_id: serviceItem.service_id,
                  quantity: serviceItem.quantity || 1
                });
              }
            } else {
              logger.log(`  ℹ️ Существующая услуга: "${service.name}"`);
              existingServices.push(serviceItem);
            }
          }
        }

        // ✅ Конвертируем все doctor_id в user_id параллельно
        const newServices = [];
        if (newServicesWithDoctorId.length > 0) {
          logger.log(`🔄 Конвертация ${newServicesWithDoctorId.length} doctor_id в user_id...`);
          const conversionPromises = newServicesWithDoctorId.map(async (item) => {
            try {
              const user_id = await getDoctorUserId(item.doctor_id);
              logger.log(`✅ Конвертация успешна: doctor_id=${item.doctor_id} -> user_id=${user_id} для услуги "${item.service_name}"`);
              return {
                success: true,
                service: {
                  specialist_id: user_id,
                  service_id: item.service_id,
                  quantity: item.quantity
                },
                failedItem: null
              };
            } catch (error) {
              logger.error(`❌ Ошибка конвертации doctor_id=${item.doctor_id} в user_id:`, error);
              logger.warn(`⚠️ Услуга "${item.service_name}" будет обработана через cart endpoint из-за ошибки конвертации`);
              // ✅ ИСПРАВЛЕНО Bug 1: Возвращаем информацию об ошибке для fallback в cart endpoint
              return {
                success: false,
                service: null,
                failedItem: {
                  service_id: item.service_id,
                  quantity: item.quantity
                }
              };
            }
          });

          const conversionResults = await Promise.all(conversionPromises);

          // Добавляем успешно конвертированные услуги
          conversionResults.forEach(result => {
            if (result.success && result.service) {
              newServices.push(result.service);
            }
          });

          // ✅ ИСПРАВЛЕНО Bug 1: Добавляем услуги с ошибкой конвертации в newServicesWithoutDoctor для fallback
          conversionResults.forEach(result => {
            if (!result.success && result.failedItem) {
              newServicesWithoutDoctor.push(result.failedItem);
              logger.log(`📋 Услуга service_id=${result.failedItem.service_id} добавлена в fallback для cart endpoint`);
            }
          });
        }

        // ✅ ИСПРАВЛЕНИЕ: Проверяем наличие новых услуг (как с врачами, так и без)
        const hasNewServices = newServices.length > 0 || newServicesWithoutDoctor.length > 0;

        if (hasNewServices) {
          logger.log(`✅ Найдены новые услуги для ${recordType}:`, {
            withDoctor: newServices.length,
            withoutDoctor: newServicesWithoutDoctor.length
          });

          // Фильтруем услуги, которые требуют специалиста (имеют specialist_id)
          const servicesWithSpecialist = newServices.filter(s => s.specialist_id);

          if (servicesWithSpecialist.length > 0) {
            // Используем batch endpoint для добавления новых услуг с специалистами
            try {
              // ✅ Сохраняем оригинальный source (online для QR, desk для ручных записей)
              const originalSource = effectiveSource; // Используем effectiveSource, установленный выше
              logger.log(`📤 Вызов batch endpoint для ${servicesWithSpecialist.length} новых услуг с source="${originalSource}"...`);

              const batchResult = await createQueueEntriesBatch({
                patientId: patientId,
                source: originalSource, // ⭐ Сохраняем оригинальный source
                services: servicesWithSpecialist
              });

              logger.log('✅ Batch endpoint успешно создал записи:', batchResult);
              toast.success(`Добавлено ${servicesWithSpecialist.length} новых услуг в очередь`);

              // Если есть услуги без специалиста, обрабатываем их через обычный cart endpoint
              if (newServicesWithoutDoctor.length > 0) {
                logger.log('ℹ️ Найдены услуги без специалиста, обрабатываем через cart endpoint');
                // Продолжаем с обычным cart endpoint для услуг без специалиста
              } else {
                // Все услуги обработаны через batch endpoint
                // Обновляем данные пациента через cart endpoint (если нужно обновить личные данные)
                // Но не создаем новые визиты, так как новые услуги уже добавлены в очередь
                logger.log('✅ Все новые услуги обработаны через batch endpoint');

                // Если нужно обновить личные данные пациента, вызываем cart endpoint с существующими услугами
                // Иначе просто завершаем
                if (existingServices.length > 0 || Object.keys(wizardData.patient).some(key => {
                  const initialValue = initialData[`patient_${key}`] || initialData[key];
                  const currentValue = wizardData.patient[key];
                  return initialValue !== currentValue;
                })) {
                  logger.log('ℹ️ Обновляем личные данные пациента через cart endpoint...');
                  // ✅ ИСПРАВЛЕНО Bug 1: В режиме редактирования, когда все новые услуги обработаны через batch,
                  // не отправляем существующие визиты в cart endpoint, чтобы избежать дубликатов
                  // Cart endpoint используется только для обновления данных пациента, не для создания визитов
                  if (editMode) {
                    visits = []; // Пустой массив - не создаем новые визиты, только обновляем данные пациента
                    logger.log('📝 Режим редактирования: visits установлен в [] для обновления только данных пациента');
                  }
                  // Продолжаем с cart endpoint для обновления данных
                } else {
                  // Нет изменений в данных, просто завершаем
                  // ✅ НОВОЕ: Обработка удаленных записей очереди
                  // Находим записи, которых больше нет в корзине
                  const currentQueueIds = new Set(
                    wizardData.cart.items
                      .map(item => item.original_queue_id)
                      .filter(id => id)
                  );

                  const removedQueueIds = Array.from(originalQueueIds).filter(id => !currentQueueIds.has(id));

                  if (removedQueueIds.length > 0) {
                    logger.log(`🗑️ Найдены удаленные записи очереди: ${removedQueueIds.join(', ')}. Отменяем их...`);
                    try {
                      // Параллельная отмена всех удаленных записей
                      await Promise.all(removedQueueIds.map(id =>
                        api.post(`/online-queue/entries/${id}/cancel`)
                          .catch(err => {
                            logger.error(`❌ Ошибка отмены записи очереди ${id}:`, err);
                            // Не прерываем процесс, если одна отмена не удалась
                          })
                      ));
                      logger.log('✅ Все удаленные записи очереди успешно отменены');
                    } catch (error) {
                      logger.error('❌ Ошибка при отмене записей очереди:', error);
                    }
                  } else {
                    logger.log('ℹ️ Нет удаленных записей очереди для отмены');
                  }

                  if (!editMode) {
                    localStorage.removeItem(DRAFT_KEY);
                  }
                  onComplete?.(batchResult);
                  onClose();
                  return;
                }
              }
            } catch (batchError) {
              logger.error('❌ Ошибка batch endpoint:', batchError);
              toast.error(`Ошибка добавления услуг: ${batchError.message || 'Неизвестная ошибка'}`);
              // Продолжаем с обычным cart endpoint как fallback
              logger.log('ℹ️ Продолжаем с cart endpoint как fallback...');
            }
          }

          // ✅ Обработка услуг без специалиста (лаборатория и т.д.)
          if (newServicesWithoutDoctor.length > 0) {
            logger.log('ℹ️ Новые услуги не требуют специалиста, используем обычный cart endpoint');

            // ✅ ИСПРАВЛЕНИЕ: В режиме редактирования создаем визиты только из НОВЫХ услуг
            if (editMode) {
              logger.log('📝 Режим редактирования: создаем визиты только из новых услуг');

              // Группируем только новые услуги по визитам
              const newServiceVisits = {};
              newServicesWithoutDoctor.forEach(item => {
                const department = getDepartmentByService(item.service_id);
                const key = `${department}_no_doctor_${new Date().toISOString().split('T')[0]}_no_time`;

                if (!newServiceVisits[key]) {
                  newServiceVisits[key] = {
                    doctor_id: null,
                    services: [],
                    visit_date: new Date().toISOString().split('T')[0],
                    visit_time: null,
                    department: department,
                    notes: null
                  };
                }

                newServiceVisits[key].services.push({
                  service_id: item.service_id,
                  quantity: item.quantity
                });
              });

              // ✅ ИСПРАВЛЕНО: Сохраняем существующие визиты и добавляем только новые
              // По сценарию 5: новые услуги создают новые визиты, существующие не изменяются
              // Но для cart endpoint нужно отправить только новые визиты (существующие уже в БД)
              const newVisitsOnly = Object.values(newServiceVisits);
              visits = newVisitsOnly;
              logger.log('📋 Созданы визиты только из новых услуг:', visits.length);
              logger.log('ℹ️ Существующие визиты не изменяются (остаются в БД)');
            }
            // Все новые услуги без специалиста - обрабатываем через cart endpoint
          }
        } else {
          logger.log('ℹ️ Новых услуг не найдено, используем обычный cart endpoint для обновления данных');
          // Нет новых услуг, но возможно нужно обновить данные пациента
          // Продолжаем с обычным cart endpoint
        }
      }

      // === ШАГ 2: СОЗДАЁМ КОРЗИНУ ВИЗИТОВ ИЛИ ОБНОВЛЯЕМ ДАННЫЕ ПАЦИЕНТА ===

      // ✅ ИСПРАВЛЕНО Bug 2: Если visits пустой (все услуги обработаны через batch),
      // используем отдельный endpoint для обновления данных пациента, чтобы не создавать invoice с нулевой суммой
      if (visits.length === 0 && editMode) {
        logger.log('📝 Режим редактирования: visits пустой, обновляем только данные пациента через patients API');

        // Обновляем данные пациента через отдельный endpoint
        const patientUpdateData = {
          full_name: wizardData.patient.fio || wizardData.patient.name,
          phone: wizardData.patient.phone,
          birth_date: wizardData.patient.birth_date || wizardData.patient.birthDate,
          sex: wizardData.patient.gender === 'male' ? 'M' : wizardData.patient.gender === 'female' ? 'F' : null,
          address: wizardData.patient.address
        };

        // Удаляем undefined значения
        Object.keys(patientUpdateData).forEach(key =>
          patientUpdateData[key] === undefined && delete patientUpdateData[key]
        );

        try {
          // ✅ ИСПРАВЛЕНО Bug 1: API_BASE уже содержит '/api/v1', не дублируем префикс
          const patientResponse = await fetch(`${API_BASE}/patients/${patientId}`, {
            method: 'PUT',
            headers: {
              'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(patientUpdateData)
          });

          if (patientResponse.ok) {
            logger.log('✅ Данные пациента успешно обновлены');
            // ✅ ИСПРАВЛЕНО: Очищаем draft после успешного обновления
            localStorage.removeItem(DRAFT_KEY);
            toast.success('Данные пациента обновлены');

            // ✅ НОВОЕ: Обработка удаленных записей очереди (для patient update path)
            const currentQueueIds = new Set(
              wizardData.cart.items
                .map(item => item.original_queue_id)
                .filter(id => id)
            );

            const removedQueueIds = Array.from(originalQueueIds).filter(id => !currentQueueIds.has(id));

            if (removedQueueIds.length > 0) {
              logger.log(`🗑️ Найдены удаленные записи очереди (Update Path): ${removedQueueIds.join(', ')}`);
              // Non-blocking cleanup
              Promise.all(removedQueueIds.map(id => api.post(`/online-queue/entries/${id}/cancel`)))
                .catch(e => logger.error('❌ Ошибка отмены записей:', e));
            }

            onComplete?.({ success: true, message: 'Данные пациента обновлены' });
            onClose();
            return;
          } else {
            const errorData = await patientResponse.json().catch(() => ({ detail: 'Ошибка обновления пациента' }));
            throw new Error(errorData.detail || `Ошибка ${patientResponse.status}`);
          }
        } catch (patientError) {
          logger.error('❌ Ошибка обновления данных пациента:', patientError);
          toast.error(`Ошибка обновления данных пациента: ${patientError.message || 'Неизвестная ошибка'}`);
          // Продолжаем с обычным flow (хотя visits пустой, это не должно произойти)
        }
      }

      // ✅ ИСПРАВЛЕНО Bug 2: Предотвращаем отправку пустой корзины, если визитов нет
      // Это может произойти в режиме редактирования, если мы пытались обновить пациента и произошла ошибка,
      // или если все новые услуги были обработаны через batch endpoint.
      if (visits.length === 0) {
        logger.warn('⚠️ Нет визитов для создания в корзине (visits is empty). Пропускаем вызов /registrar/cart.');
        if (editMode) {
          // Ошибка (если была) уже обработана в блоках выше, просто выходим
          return;
        }
        // В режиме создания, если визитов нет, показываем предупреждение
        toast.warning('Корзина пуста. Добавьте услуги для создания записи.');
        return;
      }

      const cartData = {
        patient_id: patientId,
        visits: visits,
        discount_mode: wizardData.cart.discount_mode,
        payment_method: wizardData.payment.method,
        all_free: wizardData.cart.all_free,
        notes: wizardData.cart.notes
      };

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

        logger.log('✅ Запись создана успешно на backend:', result);

        // Всегда завершаем после создания корзины (без онлайн оплаты в UI)
        // Всегда завершаем после создания корзины (без онлайн оплаты в UI)
        // Очищаем черновик только если это не редактирование (хотя clearDraft безопасен)
        if (!editMode) {
          localStorage.removeItem(DRAFT_KEY);
        }

        toast.success(editMode ? 'Запись обновлена!' : 'Запись создана успешно!');

        // ✅ НОВОЕ: Обработка удаленных записей очереди (для cart creation path)
        const currentQueueIds = new Set(
          wizardData.cart.items
            .map(item => item.original_queue_id)
            .filter(id => id)
        );

        const removedQueueIds = Array.from(originalQueueIds).filter(id => !currentQueueIds.has(id));

        if (removedQueueIds.length > 0) {
          logger.log(`🗑️ Найдены удаленные записи очереди (Cart Path): ${removedQueueIds.join(', ')}`);
          // Non-blocking cleanup
          Promise.all(removedQueueIds.map(id => api.post(`/online-queue/entries/${id}/cancel`)))
            .catch(e => logger.error('❌ Ошибка отмены записей:', e));
        }

        onComplete?.(result);
        onClose();
      } else {
        // Получаем детальную информацию об ошибке
        let errorMessage = `Ошибка создания записи (${cartResponse.status})`;
        let isPermissionError = false;

        try {
          const errorData = await cartResponse.json();
          logger.error('❌ Детали ошибки создания корзины:', errorData);
          errorMessage = errorData.detail || errorMessage;

          // Проверяем, является ли это ошибкой прав доступа
          if (cartResponse.status === 403) {
            isPermissionError = true;
            if (errorMessage.includes('Not enough permissions')) {
              errorMessage = 'У вас нет прав для создания записей. Необходима роль Регистратора или Администратора.';
            }
          }
        } catch (parseError) {
          logger.error('❌ Не удалось прочитать ошибку как JSON');

          if (cartResponse.status === 403) {
            isPermissionError = true;
            errorMessage = 'У вас нет прав для создания записей. Необходима роль Регистратора или Администратора.';
          }
        }

        logger.error('❌ Ошибка создания корзины:', cartResponse.status, errorMessage);

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
      logger.error('Ошибка завершения мастера:', error);
      toast.error(error.message || 'Произошла ошибка');
    } finally {
      setIsProcessing(false);
    }
  };

  // Группировка элементов корзины по визитам
  const groupCartItemsByVisit = () => {
    const visits = {};

    // ✅ ИСПРАВЛЕНО: Фильтруем элементы корзины без service_id
    const validItems = wizardData.cart.items.filter(item => {
      if (!item.service_id) {
        logger.warn('⚠️ Пропущен элемент корзины без service_id:', item);
        return false;
      }
      return true;
    });

    if (validItems.length === 0) {
      logger.warn('⚠️ Нет валидных элементов в корзине');
      return {};
    }

    validItems.forEach(item => {
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
    // ✅ ИСПРАВЛЕНО: Проверка на null/undefined перед поиском
    if (!serviceId || serviceId === null || serviceId === undefined) {
      logger.warn('⚠️ getDepartmentByService: serviceId is null/undefined');
      return 'general';
    }

    const service = servicesData.find(s => s.id === serviceId);

    if (!service) {
      logger.warn(`⚠️ Услуга ${serviceId} не найдена в servicesData`);
      return 'general';
    }

    logger.log(`🔍 getDepartmentByService: serviceId=${serviceId}, queue_tag=${service.queue_tag}, category_code=${service.category_code}`);

    // 🎯 СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ ЭКГ: отдельный кабинет!
    if (service.queue_tag === 'ecg') {
      logger.log('✅ ЭКГ обнаружено! Возвращаем department=\'echokg\'');
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

    // ✅ ИСПРАВЛЕНО Bug 2: Сначала проверяем оригинальный category_code для точного маппинга
    // Это предотвращает неправильный маппинг дерматологии и стоматологии в кардиологию
    if (service.category_code && mapping[service.category_code]) {
      const result = mapping[service.category_code];
      logger.log(`🎯 getDepartmentByService результат: serviceId=${serviceId}, category_code=${service.category_code}, department=${result} (прямой маппинг)`);
      return result;
    }

    // ✅ Нормализация category_code как fallback
    const normalizedCategoryCode = service.category_code ? normalizeCategoryCode(service.category_code) : '';

    // ✅ ИСПРАВЛЕНИЕ: Маппинг для нормализованных кодов (только для случаев, когда нет прямого маппинга)
    const normalizedMapping = {
      'specialists': 'cardiology',    // Консультации специалистов (только если не 'D' или 'S') -> cardiology
      'laboratory': 'lab',            // ✅ ИСПРАВЛЕНИЕ: Лаборатория -> lab (для соответствия вкладке)
      'procedures': 'procedures',     // Процедуры -> procedures
      'other': 'general'              // Прочее -> general
    };

    const result = normalizedMapping[normalizedCategoryCode] || mapping[service.category_code] || 'general';
    logger.log(`🎯 getDepartmentByService результат: serviceId=${serviceId}, category_code=${normalizedCategoryCode}, department=${result}`);
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

  // Обработчик обновления услуг (для хедера)
  const handleReloadServices = async () => {
    setIsReloadingServices(true);
    try {
      await loadServices();
      toast.success('Список услуг обновлён');
    } catch (error) {
      logger.error('Ошибка обновления услуг:', error);
      toast.error('Не удалось обновить список услуг');
    } finally {
      setIsReloadingServices(false);
    }
  };

  // Кастомный заголовок для Шага 1
  const Step1Header = (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      width: '100%',
      padding: '4px 32px 12px 32px',
      borderBottom: '1px solid var(--mac-border)'
    }}>
      {/* Заголовок */}
      <h3 style={{
        fontSize: '17px',
        fontWeight: '600',
        color: 'var(--mac-text-primary)',
        margin: 0,
        letterSpacing: '-0.02em'
      }}>
        Регистрация пациента
      </h3>

      {/* Кнопка закрытия */}
      <button
        onClick={onClose}
        title="Закрыть"
        style={{
          width: '32px',
          height: '32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: 'none',
          background: 'transparent',
          color: 'var(--mac-text-secondary)',
          borderRadius: '6px',
          cursor: 'pointer',
          transition: 'all 0.2s'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = 'var(--mac-danger)';
          e.currentTarget.style.color = 'white';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'transparent';
          e.currentTarget.style.color = 'var(--mac-text-secondary)';
        }}
      >
        <X size={18} />
      </button>
    </div>
  );

  // Улучшенный заголовок для Шага 2
  const Step2Header = (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      width: '100%',
      gap: '20px',
      padding: '8px 32px 12px 32px',
      borderBottom: '1px solid var(--mac-border)'
    }}>
      {/* 1. Поиск (Слева) */}
      <div style={{ flex: '0 0 280px' }}>
        <MacOSInput
          placeholder="Поиск услуги (название или код)..."
          value={serviceSearchQuery}
          onChange={(e) => setServiceSearchQuery(e.target.value)}
          icon={Search}
          clearable
          onClear={() => setServiceSearchQuery('')}
          autoFocus
          size="sm"
          style={{ height: '36px', fontSize: '13px' }}
        />
      </div>

      {/* 2. Категории (Центр) */}
      <div style={{
        flex: 1,
        display: 'flex',
        justifyContent: 'center',
        gap: '12px',
        padding: '0 12px'
      }}>
        {categories.map(cat => (
          <button
            key={cat.id}
            onClick={() => setActiveServiceCategory(cat.id)}
            style={{
              padding: '7px 16px',
              borderRadius: 'var(--mac-radius-full)',
              border: activeServiceCategory === cat.id
                ? '1px solid var(--mac-primary)'
                : '1px solid transparent',
              background: activeServiceCategory === cat.id
                ? 'linear-gradient(135deg, var(--mac-primary) 0%, #005bb5 100%)'
                : 'var(--mac-bg-secondary)',
              color: activeServiceCategory === cat.id
                ? 'white'
                : 'var(--mac-text-primary)',
              cursor: 'pointer',
              fontSize: '13px',
              fontWeight: activeServiceCategory === cat.id ? '600' : '500',
              whiteSpace: 'nowrap',
              transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              boxShadow: activeServiceCategory === cat.id
                ? '0 4px 12px rgba(0, 122, 255, 0.3), 0 2px 4px rgba(0, 122, 255, 0.2)'
                : '0 1px 2px rgba(0, 0, 0, 0.05)',
              transform: activeServiceCategory === cat.id ? 'translateY(-1px)' : 'translateY(0)'
            }}
            onMouseEnter={(e) => {
              if (activeServiceCategory !== cat.id) {
                e.currentTarget.style.background = 'var(--mac-bg-tertiary)';
                e.currentTarget.style.transform = 'translateY(-1px)';
                e.currentTarget.style.boxShadow = '0 2px 6px rgba(0, 0, 0, 0.1)';
              }
            }}
            onMouseLeave={(e) => {
              if (activeServiceCategory !== cat.id) {
                e.currentTarget.style.background = 'var(--mac-bg-secondary)';
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 1px 2px rgba(0, 0, 0, 0.05)';
              }
            }}
          >
            <span style={{ fontSize: '15px' }}>{cat.icon}</span>
            {cat.label}
          </button>
        ))}
      </div>

      {/* 3. Действия (Справа) */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        flex: '0 0 auto'
      }}>
        {/* Кнопка обновления */}
        <button
          onClick={handleReloadServices}
          disabled={isReloadingServices}
          title="Обновить список услуг"
          style={{
            width: '36px',
            height: '36px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: '1px solid var(--mac-border)',
            background: 'var(--mac-bg-primary)',
            color: 'var(--mac-text-secondary)',
            borderRadius: '8px',
            cursor: isReloadingServices ? 'wait' : 'pointer',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => {
            if (!isReloadingServices) {
              e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
              e.currentTarget.style.borderColor = 'var(--mac-primary)';
              e.currentTarget.style.color = 'var(--mac-primary)';
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--mac-bg-primary)';
            e.currentTarget.style.borderColor = 'var(--mac-border)';
            e.currentTarget.style.color = 'var(--mac-text-secondary)';
          }}
        >
          <RefreshCw size={16} className={isReloadingServices ? 'spin' : ''} />
        </button>

        {/* Кнопка закрытия */}
        <button
          onClick={onClose}
          title="Закрыть"
          style={{
            width: '36px',
            height: '36px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: '1px solid var(--mac-border)',
            background: 'var(--mac-bg-primary)',
            color: 'var(--mac-text-secondary)',
            borderRadius: '8px',
            cursor: 'pointer',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--mac-danger)';
            e.currentTarget.style.borderColor = 'var(--mac-danger)';
            e.currentTarget.style.color = 'white';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--mac-bg-primary)';
            e.currentTarget.style.borderColor = 'var(--mac-border)';
            e.currentTarget.style.color = 'var(--mac-text-secondary)';
          }}
        >
          <X size={18} />
        </button>
      </div>
    </div>
  );

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
        customHeader={currentStep === 1 ? Step1Header : Step2Header}
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
                phoneError={errors.phone}
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
                onReloadServices={loadServices}
                getServiceName={getServiceName} // ✅ SSOT: Передаем функцию для получения названий услуг
                activeCategory={activeServiceCategory}
                setActiveCategory={setActiveServiceCategory}
                searchQuery={serviceSearchQuery}
                setSearchQuery={setServiceSearchQuery}
                isReloading={isReloadingServices}
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
  data = {}, // ✅ Default empty object to prevent crash
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
  onUpdateCart,
  phoneError
}) => {
  const safeData = data || {};

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--mac-spacing-6)',
      animation: 'slideIn 0.3s ease-out',
      height: '100%',
      overflowY: 'auto',
      paddingRight: '4px',
      padding: '12px 0' // 12px vertical padding
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
          position: 'relative'
        }}>
          <label style={{
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)'
          }}>
            ФИО пациента *
          </label>
          <div style={{ position: 'relative' }}>
            <MacOSInput
              ref={fioRef}
              type="text"
              value={safeData.fio || ''}
              onChange={(e) => onSearch(e.target.value)}
              placeholder="Введите ФИО для поиска или создания"
              error={!!errors.fio}
              icon={Search}
              iconPosition="left"
              size="md"
              autoFocus
            />

            {/* Индикатор Новый/Существующий */}
            <div style={{
              position: 'absolute',
              right: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: 'var(--mac-font-size-xs)',
              pointerEvents: 'none'
            }}>
              {safeData.id ? (
                <>
                  <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--mac-primary)' }} />
                  <span style={{ color: 'var(--mac-primary)', fontWeight: '500' }}>Существующий</span>
                </>
              ) : (
                (safeData.fio || '').length > 0 && (
                  <>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--mac-success)' }} />
                    <span style={{ color: 'var(--mac-success)', fontWeight: '500' }}>Новый</span>
                  </>
                )
              )}
            </div>
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

          {/* Саджесты */}
          {showSuggestions && suggestions.length > 0 && (
            <div style={{
              position: 'absolute',
              top: '100%',
              left: 0,
              right: 0,
              zIndex: 100,
              marginTop: '4px',
              background: 'var(--mac-bg-primary)',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-md)',
              boxShadow: 'var(--mac-shadow-lg)',
              maxHeight: '200px',
              overflowY: 'auto'
            }}>
              {suggestions.map(patient => (
                <div
                  key={patient.id}
                  onClick={() => onSelectPatient(patient)}
                  style={{
                    padding: 'var(--mac-spacing-3)',
                    cursor: 'pointer',
                    borderBottom: '1px solid var(--mac-border)',
                    transition: 'background-color 0.2s'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  <div style={{ fontWeight: 'var(--mac-font-weight-medium)', color: 'var(--mac-text-primary)' }}>
                    {patient.fio || `${patient.last_name} ${patient.first_name}`}
                  </div>
                  <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-secondary)', display: 'flex', gap: '8px' }}>
                    <span>📱 {patient.phone}</span>
                    <span>🎂 {formatDateDisplay(patient.birth_date)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Пол (рядом с ФИО) */}
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
            Пол *
          </label>
          <div style={{
            display: 'flex',
            background: 'var(--mac-bg-secondary)',
            padding: '4px',
            borderRadius: 'var(--mac-radius-md)',
            border: '1px solid var(--mac-border)',
            height: '36px'
          }}>
            {['male', 'female'].map((gender) => (
              <button
                key={gender}
                onClick={() => onUpdate('gender', gender)}
                style={{
                  flex: 1,
                  padding: '8px',
                  border: 'none',
                  borderRadius: 'var(--mac-radius-sm)',
                  background: safeData.gender === gender ? 'var(--mac-bg-primary)' : 'transparent',
                  color: safeData.gender === gender ? 'var(--mac-text-primary)' : 'var(--mac-text-secondary)',
                  boxShadow: safeData.gender === gender ? 'var(--mac-shadow-sm)' : 'none',
                  cursor: 'pointer',
                  fontSize: 'var(--mac-font-size-sm)',
                  fontWeight: safeData.gender === gender ? '600' : '400',
                  transition: 'all 0.2s ease'
                }}
              >
                {gender === 'male' ? 'Мужской' : 'Женский'}
              </button>
            ))}
          </div>
          {errors.gender && (
            <span style={{
              fontSize: 'var(--mac-font-size-xs)',
              color: 'var(--mac-danger)',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              <AlertCircle size={14} />
              {errors.gender}
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
            error={!!errors.phone || !!phoneError}
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
          {phoneError && (
            <div style={{
              marginTop: '4px',
              padding: '8px',
              background: '#fee2e2',
              border: '1px solid #fecaca',
              borderRadius: 'var(--mac-radius-sm)',
              display: 'flex',
              flexDirection: 'column',
              gap: '4px'
            }}>
              <span style={{
                fontSize: 'var(--mac-font-size-xs)',
                color: '#991b1b',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontWeight: '500'
              }}>
                <AlertCircle size={14} />
                {phoneError.message}
              </span>
              <button
                onClick={() => onSelectPatient(phoneError.patient)}
                style={{
                  background: '#991b1b',
                  color: 'white',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '4px 8px',
                  fontSize: '11px',
                  cursor: 'pointer',
                  alignSelf: 'flex-start'
                }}
              >
                Выбрать {phoneError?.patient?.fio || 'этого пациента'}
              </button>
            </div>
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
  );
};

// Шаг 2: Корзина - Split View (Категории + Список)
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
  errors,
  onReloadServices,
  // New props from parent
  activeCategory,
  setActiveCategory,
  searchQuery,
  setSearchQuery,
  isReloading,
  getServiceName // ✅ SSOT: Функция для получения названий услуг
}) => {
  // Local state removed - lifted to AppointmentWizardV2

  // Categories are now defined globally at the top of the file


  // Фильтрация и группировка услуг
  const getDisplayedServices = () => {
    if (!Array.isArray(servicesData)) return [];

    const filtered = servicesData;

    // 1. Фильтрация по поиску (Глобальный поиск)
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      return filtered.filter(service =>
        service.name.toLowerCase().includes(query) ||
        (service.code && service.code.toLowerCase().includes(query))
      );
    }

    // 2. Фильтрация по категории (если нет поиска)
    return filtered.filter(service => {
      const normalizedCategory = service.category_code ? normalizeCategoryCode(service.category_code) : 'other';
      const isConsultation = service.name.toLowerCase().includes('консультация');

      // ✅ Проверка на ЭКГ, ЭхоКГ и рентгенографию по service_code и названию
      const serviceCode = service.service_code ? String(service.service_code).toUpperCase() : '';
      const serviceName = service.name ? service.name.toLowerCase() : '';

      const isECG = serviceCode === 'K10' ||
        serviceCode.includes('ECG') ||
        serviceName.includes('экг');

      const isEchoCG = serviceCode === 'K11' ||
        serviceCode.includes('ECHO') ||
        serviceName.includes('эхокг') ||
        serviceName.includes('эхо-кг');

      // ✅ Рентгенография зубов: S-коды (стоматология) + название содержит "рентген"
      const isDentalXRay = (serviceCode.startsWith('S') && serviceCode.match(/^S\d+$/)) &&
        (serviceName.includes('рентген') || serviceName.includes('рентгено') || serviceName.includes('x-ray') || serviceName.includes('xray') || serviceName.includes('рентгенография'));

      switch (activeCategory) {
        case 'specialists':
          // ✅ Консультации + ЭКГ + ЭхоКГ + рентгенография зубов
          return isConsultation || isECG || isEchoCG || isDentalXRay;
        case 'laboratory':
          return normalizedCategory === 'laboratory';
        case 'procedures':
          // Процедуры (нормализованные значения: 'procedures')
          // ✅ Исключаем ЭКГ, ЭхоКГ и рентгенографию из процедур
          return normalizedCategory === 'procedures' && !isConsultation && !isECG && !isEchoCG && !isDentalXRay;
        case 'other':
          // Всё остальное (не консультации и не лаборатория и не процедуры и не ЭКГ/ЭхоКГ/рентген)
          return !isConsultation && normalizedCategory === 'other' && !isECG && !isEchoCG && !isDentalXRay;
        default:
          return true;
      }
    });
  };

  const displayedServices = getDisplayedServices();

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

  // Общая сумма корзины
  const cartTotal = useMemo(() => {
    if (!Array.isArray(cart?.items)) return 0;
    let total = 0;
    cart.items.forEach(item => {
      let itemPrice = (item.service_price || 0) * (item.quantity || 1);
      const service = servicesData?.find(s => s.id === item.service_id);
      if (service && service.is_consultation) {
        if (cart.discount_mode === 'repeat' || cart.discount_mode === 'benefit') {
          itemPrice = 0;
        }
      }
      if (cart.all_free) itemPrice = 0;
      total += itemPrice;
    });
    return Math.round(total);
  }, [cart?.items, cart?.discount_mode, cart?.all_free, servicesData]);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: 'var(--mac-spacing-4)',
      height: '100%', // Fill available space
      padding: '12px 0', // 12px vertical padding
      overflow: 'hidden',
      width: '100%'
    }}>
      {/* Верхняя панель: Поиск и Категории */}
      {/* Верхняя панель: Поиск и Категории */}


      {/* Основная область: Сетка услуг (Скролл внутри) */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        paddingRight: 'var(--mac-spacing-2)',
        minHeight: 0, // Crucial for nested flex scrolling
        border: '1px solid var(--mac-border)',
        borderRadius: 'var(--mac-radius-md)',
        padding: 'var(--mac-spacing-4)', // 16px internal padding
        background: 'var(--mac-bg-primary)'
      }}>
        {searchQuery && (
          <div style={{
            marginBottom: 'var(--mac-spacing-3)',
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)'
          }}>
            Результаты поиска: {displayedServices.length}
          </div>
        )}

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)', // 3 колонки
          gap: 'var(--mac-spacing-2)', // Compact gap
          alignContent: 'start'
        }}>
          {displayedServices.map(service => {
            // ✅ ИСПРАВЛЕНО: Проверяем также по service_code для edit режима (когда service_id еще null)
            const isInCart = cart?.items?.some(item => {
              if (item.service_id === service.id) return true;
              // Если service_id еще не разрешен, проверяем по коду (включая варианты с нулями: p09, P09, P9)
              if (!item.service_id && service.service_code) {
                const itemCode = String(item.service_name || item._temp_name || '').toUpperCase().trim();
                const serviceCode = String(service.service_code).toUpperCase().trim();
                // Прямое сравнение
                if (itemCode === serviceCode) return true;
                // Сравнение без ведущих нулей (p09 = p9)
                const itemCodeNoZero = itemCode.replace(/^([A-Z])0+(\d+)$/, '$1$2');
                const serviceCodeNoZero = serviceCode.replace(/^([A-Z])0+(\d+)$/, '$1$2');
                if (itemCodeNoZero === serviceCodeNoZero) return true;
              }
              return false;
            });
            return (
              <label
                key={service.id}
                className={`compact-service-card ${isInCart ? 'selected' : ''}`}
              >
                <input
                  type="checkbox"
                  checked={isInCart}
                  onChange={() => handleServiceToggle(service)}
                  style={{ width: '14px', height: '14px', cursor: 'pointer', flexShrink: 0, margin: 0 }}
                />
                <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column', gap: '0px' }}>
                  <div className="service-name-text" title={service.name}>
                    {service.name}
                  </div>
                  <div className="service-price-text">
                    {service.price?.toLocaleString()} сум
                  </div>
                </div>
              </label>
            );
          })}

          {displayedServices.length === 0 && (
            <div style={{
              gridColumn: '1 / -1',
              textAlign: 'center',
              padding: 'var(--mac-spacing-8)',
              color: 'var(--mac-text-tertiary)'
            }}>
              Услуги не найдены
            </div>
          )}
        </div>
      </div>

      {/* Нижняя панель: Корзина */}
      <div style={{
        flexShrink: 0,
        paddingTop: 'var(--mac-spacing-3)',
        borderTop: '1px solid var(--mac-border)',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--mac-spacing-2)'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: 'var(--mac-font-size-sm)',
          color: 'var(--mac-text-secondary)'
        }}>
          <span>Выбрано: {cart?.items?.length || 0} шт.</span>
          <span style={{ color: 'var(--mac-success)', fontWeight: '600' }}>
            Итого: {cartTotal.toLocaleString()} сум
          </span>
        </div>

        {/* Горизонтальный скролл корзины */}
        {cart?.items?.length > 0 ? (
          <div style={{
            display: 'flex',
            gap: 'var(--mac-spacing-2)',
            overflowX: 'auto',
            paddingBottom: '4px'
          }}>
            {cart.items.map(item => {
              // ✅ SSOT: Используем единую функцию для получения названия услуги
              const displayName = getServiceName ? getServiceName(item) : (item.service_name || 'Неизвестная услуга');

              return (
                <div key={item.id} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '4px 8px',
                  background: 'var(--mac-bg-secondary)',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-sm)',
                  fontSize: 'var(--mac-font-size-xs)',
                  whiteSpace: 'nowrap'
                }}>
                  <span style={{ maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis' }} title={displayName}>
                    {displayName}
                  </span>
                  <button
                    onClick={() => onRemoveFromCart(item.id)}
                    style={{
                      border: 'none',
                      background: 'transparent',
                      color: 'var(--mac-danger)',
                      cursor: 'pointer',
                      padding: 0,
                      display: 'flex'
                    }}
                  >
                    <X size={14} />
                  </button>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{ fontSize: 'var(--mac-font-size-xs)', color: 'var(--mac-text-tertiary)' }}>
            Корзина пуста
          </div>
        )}

        {/* Ошибки валидации */}
        {(errors.cart || errors.doctors) && (
          <div style={{
            padding: '8px',
            background: '#fee2e2',
            border: '1px solid #fecaca',
            borderRadius: 'var(--mac-radius-sm)',
            color: '#991b1b',
            fontSize: 'var(--mac-font-size-xs)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)'
          }}>
            <AlertCircle size={14} />
            {errors.cart || errors.doctors}
          </div>
        )}
      </div>
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

