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
      if (editMode && initialData) {
        // 📝 РЕЖИМ РЕДАКТИРОВАНИЯ: Загружаем данные из initialData
        console.log('📝 AppointmentWizardV2: Initializing EDIT MODE', initialData);

        // Парсим услуги из initialData (предполагаем, что они приходят в определенном формате)
        // В реальном приложении может потребоваться маппинг

        // ✅ ИСПРАВЛЕНО: Правильная инициализация даты рождения
        const birthDate = initialData.patient_birth_date ||
                          (initialData.patient_birth_year ? `${initialData.patient_birth_year}-01-01` : '');

        setWizardData({
          patient: {
            id: initialData.patient_id || null, // 🚨 FIX: Никогда не используем initialData.id (это ID записи!), только patient_id
            fio: initialData.patient_fio || initialData.patient_name || '',
            birth_date: birthDate, // ✅ ИСПРАВЛЕНО: Приоритет полной даты
            phone: initialData.phone || initialData.patient_phone || '',
            address: initialData.address || '',
            gender: initialData.patient_gender || initialData.gender || ''
          },
          cart: {
            items: (() => {
              // 🛒 ВОССТАНОВЛЕНИЕ КОРЗИНЫ УСЛУГ
              // Пытаемся восстановить услуги из initialData
              // Поддерживаем разные форматы: services (массив строк), queue_numbers (массив объектов)

              const items = [];

              // ✅ ИСПРАВЛЕНО: Приоритет восстановления услуг
              // 1. Сначала пробуем из services (массив строк или кодов)
              if (Array.isArray(initialData.services) && initialData.services.length > 0) {
                console.log('📦 Восстановление услуг из services:', initialData.services);
                initialData.services.forEach(serviceName => {
                  if (serviceName) { // Проверка существования
                    items.push({
                      id: Date.now() + Math.random(),
                      service_id: null,
                      service_name: serviceName,
                      service_price: 0,
                      quantity: 1,
                      doctor_id: null,
                      visit_date: initialData.date || new Date().toISOString().split('T')[0],
                      visit_time: null,
                      _temp_name: serviceName
                    });
                  }
                });
              }
              // 2. Если services нет, пробуем из service_codes
              else if (Array.isArray(initialData.service_codes) && initialData.service_codes.length > 0) {
                console.log('📦 Восстановление услуг из service_codes:', initialData.service_codes);
                initialData.service_codes.forEach(serviceCode => {
                  if (serviceCode) {
                    items.push({
                      id: Date.now() + Math.random(),
                      service_id: null,
                      service_name: serviceCode, // Будет резолвиться позже
                      service_price: 0,
                      quantity: 1,
                      doctor_id: null,
                      visit_date: initialData.date || new Date().toISOString().split('T')[0],
                      visit_time: null,
                      _temp_name: serviceCode
                    });
                  }
                });
              }
              // 3. Последний вариант - из queue_numbers (только если есть service_name)
              else if (Array.isArray(initialData.queue_numbers)) {
                console.log('📦 Восстановление услуг из queue_numbers:', initialData.queue_numbers);
                initialData.queue_numbers.forEach(q => {
                  // Пропускаем записи без конкретной услуги (просто очередь)
                  if (!q || !q.service_name) {
                    console.warn('⚠️ Queue entry has no service_name, skipping:', q);
                    return;
                  }

                  items.push({
                    id: Date.now() + Math.random(),
                    service_id: q.service_id || null,
                    service_name: q.service_name,
                    service_price: q.service_price || 0,
                    quantity: q.quantity || 1,
                    doctor_id: q.doctor_id || null,
                    visit_date: q.date || initialData.date || new Date().toISOString().split('T')[0],
                    visit_time: q.visit_time || null,
                    _temp_name: q.service_name
                  });
                });
              }

              console.log('📦 Initialized cart with items:', items);
              console.log('📦 InitialData full structure:', initialData);
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
        // 🆕 НОВАЯ ЗАПИСЬ: Проверяем черновик
        const savedDraft = localStorage.getItem(DRAFT_KEY);
        if (savedDraft) {
          try {
            const draft = JSON.parse(savedDraft);
            const now = Date.now();

            if (draft.timestamp && (now - draft.timestamp) < DRAFT_TTL) {
              // Черновик актуален
              console.log('📂 AppointmentWizardV2: Loaded DRAFT');
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
            console.warn('Ошибка загрузки черновика:', e);
            localStorage.removeItem(DRAFT_KEY);
          }
        }
      }
    }
  }, [isOpen, editMode, initialData]);

  // Safeguard: Ensure wizardData structure is valid
  useEffect(() => {
    if (!wizardData.patient) {
      console.warn('⚠️ Wizard data corrupted (missing patient), resetting...');
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
      console.error('Ошибка проверки телефона:', error);
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
      console.error('Ошибка поиска пациентов:', error);
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
        gender: patient.gender || '', // ✅ Заполняем пол
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
      console.error('Ошибка загрузки услуг:', error);
    }
  };

  // ===================== РЕЗОЛВИНГ УСЛУГ (EDIT MODE) =====================

  // Эффект для обогащения данных корзины реальными ID и ценами после загрузки servicesData
  useEffect(() => {
    if (editMode && servicesData.length > 0 && wizardData.cart.items.length > 0) {
      console.log('🔍 Attempting to resolve services in edit mode...', {
        servicesDataCount: servicesData.length,
        cartItemsCount: wizardData.cart.items.length,
        unresolvedItems: wizardData.cart.items.filter(i => !i.service_id).length
      });

      const updatedItems = wizardData.cart.items.map(item => {
        // Если услуга уже полностью определена (есть ID), пропускаем
        if (item.service_id) return item;

        // Ищем услугу по имени или коду (которое мы сохранили в service_name или _temp_name)
        const searchName = item._temp_name || item.service_name;
        if (!searchName) {
          console.warn('⚠️ Item has no searchable name:', item);
          return item;
        }

        // ✅ ИСПРАВЛЕНО: Поиск по service_code (приоритет) и по name
        const foundService = servicesData.find(s =>
          s.service_code === searchName || // Сначала ищем по коду (K01, L01, etc)
          s.name === searchName            // Потом по названию
        );

        if (foundService) {
          console.log(`✅ Service resolved: "${searchName}" -> ID ${foundService.id} (${foundService.name})`);
          return {
            ...item,
            service_id: foundService.id,
            service_name: foundService.name,
            service_price: foundService.price,
          };
        } else {
          console.warn(`⚠️ Service not found in servicesData: "${searchName}"`);
        }

        return item;
      });

      // Проверяем, изменилось ли что-то
      const hasChanges = updatedItems.some((item, index) => {
        const prevItem = wizardData.cart.items[index];
        return item.service_id !== prevItem.service_id || item.service_price !== prevItem.service_price;
      });

      if (hasChanges) {
        console.log('✅ Updating cart with resolved services:', updatedItems.length);
        setWizardData(prev => ({
          ...prev,
          cart: {
            ...prev.cart,
            items: updatedItems
          }
        }));
      }
    }
  }, [editMode, servicesData.length, wizardData.cart.items.length]); // Триггерим когда загружаются услуги или меняется количество элементов корзины

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

      // === ШАГ 1: ОПРЕДЕЛЯЕМ ИЛИ НАХОДИМ patient_id ===

      // В режиме EDIT MODE с QR-пациентом (patient_id = null)
      if (editMode && !wizardData.patient.id && wizardData.patient.phone) {
        console.log('🔍 Edit mode: patient_id is null, searching for existing patient by phone...');
        console.log('📞 Patient data:', {
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
          console.log('📋 Found patients (by phone):', patients.length);
        }

        let foundPatient = patients.find(p => (p.phone || '').replace(/\D/g, '') === cleanPhone);

        // Попытка 2: Если не нашли, пробуем по очищенному номеру
        if (!foundPatient && cleanPhone.length >= 9) {
          console.log('🔄 Trying search with cleaned phone:', cleanPhone);
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
          cartData.patient_id = foundPatient.id;
          console.log('✅ Found existing patient:', foundPatient.id);

          // Обновляем данные пациента если нужно
          const needsUpdate =
            (wizardData.patient.birth_date && wizardData.patient.birth_date !== foundPatient.birth_date) ||
            (wizardData.patient.address && wizardData.patient.address !== foundPatient.address) ||
            (wizardData.patient.gender && wizardData.patient.gender !== foundPatient.sex);

          if (needsUpdate) {
            console.log('🔄 Updating patient data...');
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
              console.log('✅ Patient data updated');
            } catch (e) {
              console.warn('⚠️ Failed to update patient:', e);
            }
          }
        } else {
          throw new Error(`Пациент с телефоном ${wizardData.patient.phone} не найден. Невозможно обновить запись.`);
        }
      }
      // В обычном режиме (не edit) создаем пациента если нужно
      else if (!editMode && !wizardData.patient.id) {
        // ✅ УПРОЩЕНО: Отправляем полное ФИО в API, backend нормализует его (Single Source of Truth)
        // Валидация обязательных полей
        if (!wizardData.patient.fio || !wizardData.patient.fio.trim()) {
          throw new Error('ФИО пациента обязательно для заполнения');
        }

        const token = localStorage.getItem('auth_token');
        console.log('🔑 Токен для создания пациента:', token ? `${token.substring(0, 20)}...` : 'НЕТ ТОКЕНА');
        console.log('📊 Длина токена:', token ? token.length : 0);

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
            const cleanPhone = wizardData.patient.phone.replace(/\D/g, '');
            console.log(`⚠️ Ищем существующего пациента по номеру телефона: ${wizardData.patient.phone} (clean: ${cleanPhone})`);

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
                cartData.patient_id = foundPatient.id;
                console.log('✅ Найден существующий пациент (по телефону):', foundPatient.id);
              } else {
                // 🚨 НЕ используем fallback - требуем точное совпадение
                console.error('❌ Exact phone match not found. API returned', patients.length, 'patients');
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
          console.error('❌ Ошибка создания пациента:', patientResponse.status, errorText);
          throw new Error(`Ошибка создания пациента: ${patientResponse.status} ${errorText}`);
        }
      }

      // === ШАГ 2: СОЗДАЁМ КОРЗИНУ ВИЗИТОВ ===
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
        // Всегда завершаем после создания корзины (без онлайн оплаты в UI)
        // Очищаем черновик только если это не редактирование (хотя clearDraft безопасен)
        if (!editMode) {
          localStorage.removeItem(DRAFT_KEY);
        }

        toast.success(editMode ? 'Запись обновлена!' : 'Запись создана успешно!');
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
          console.error('❌ Не удалось прочитать ошибку как JSON');

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
      console.log('✅ ЭКГ обнаружено! Возвращаем department=\'echokg\'');
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

    // ✅ Нормализация category_code перед использованием
    const normalizedCategoryCode = service.category_code ? normalizeCategoryCode(service.category_code) : '';
    const result = mapping[normalizedCategoryCode] || 'general';
    console.log(`🎯 getDepartmentByService результат: serviceId=${serviceId}, category_code=${normalizedCategoryCode}, department=${result}`);
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
      console.error('Ошибка обновления услуг:', error);
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
  isReloading
}) => {
  // Local state removed - lifted to AppointmentWizardV2

  // Categories are now defined globally at the top of the file


  // Фильтрация и группировка услуг
  const getDisplayedServices = () => {
    if (!Array.isArray(servicesData)) return [];

    let filtered = servicesData;

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
      const normalizedCategoryCode = service.category_code ? normalizeCategoryCode(service.category_code) : '';
      const isConsultation = service.name.toLowerCase().includes('консультация');

      switch (activeCategory) {
        case 'specialists':
          return isConsultation;
        case 'laboratory':
          return normalizedCategoryCode === 'L';
        case 'procedures':
          // Косметология (C), Процедуры (P, D_PROC), ЭКГ и т.д.
          return ['C', 'P', 'D_PROC', 'O'].includes(normalizedCategoryCode) && !isConsultation;
        case 'other':
          // Всё остальное
          return !isConsultation && !['L', 'C', 'P', 'D_PROC', 'O'].includes(normalizedCategoryCode);
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
            const isInCart = cart?.items?.some(item => item.service_id === service.id);
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
            {cart.items.map(item => (
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
                <span style={{ maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {item.service_name}
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
            ))}
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

