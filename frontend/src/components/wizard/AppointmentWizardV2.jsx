import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import PropTypes from 'prop-types';
import {
  Search,
  Phone,


  X,

  Check,
  ArrowLeft,
  ArrowRight,
  Trash2,
  AlertCircle,
  Stethoscope,
  FlaskConical,
  Syringe,
  ClipboardList,




  Calendar,

  RefreshCw } from
'lucide-react';
import { toast } from 'react-toastify';
import ModernDialog from '../dialogs/ModernDialog';
import {
  Input, Button, Tooltip,
} from '../ui/macos';
import { useRoleAccess } from '../common/RoleGuard';
import { normalizeCategoryCode } from '../../utils/serviceCodeUtils';
import { formatDateDisplay } from '../../utils/dateUtils';
import {
  formatUzbekPhoneDisplay,
  isValidUzbekPhone,
  normalizeUzbekPhoneForApi
} from '../../utils/phoneUtils';
import { applyRegistrarEditDelta, createQueueEntriesBatch, updateOnlineQueueEntry } from '../../api/queue';
import { api } from '../../api/client';
// UX Audit Stage 3 (Wizard issue 5.1):
// Все 13 raw fetch() к /patients/* и /registrar/cart заменены на
// централизованный patients API client. Это убирает дублирование
// headers/JSON-parsing/error-handling и использует axios-interceptor
// из api/client.js для auth/CSRF/refresh-token.
import {
  getPatient,
  createPatient,
  updatePatient,
  searchPatientsByPhone,
  searchPatients as searchPatientsApi,
  checkAuthProbe,
  createRegistrarCart,
  findPatientByPhoneVariants,
} from '../../api/patients';
import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
// UX Audit Registrar #2: useConfirm hook для замены window.confirm().
import { useConfirm } from '../common/ConfirmDialog';
// ⭐ SSOT: Unified service extraction
import { normalizeServicesFromInitialData } from '../../utils/serviceCodeResolver';
import './AppointmentWizardV2.css';
// UX Audit Stage 3 (Wizard issue 5.2):
// PatientStepV2 и CartStepV2 вынесены в отдельные файлы для уменьшения размера.
import PatientStepV2 from './PatientStepV2';
import CartStepV2 from './CartStepV2';


// UX Audit Stage 3 (Wizard issue 5.1):
// API_BASE удалён — все вызовы идут через api-клиент, который сам
// добавляет baseURL. Раньше API_BASE использовался в 13 raw fetch().
// Константа оставлена закомментированной для исторического контекста.
// const API_BASE = '/api/v1';

// UX Audit Stage 3 (Wizard issue 5.2):
// Все utility-функции и константы вынесены в wizardUtils.js для уменьшения
// размера основного файла (с 4175 до ~3870 строк) и возможности переиспользования.
import {
  PATIENT_NAME_PATTERN,
  MIXED_REPEAT_WARNING,
  STEP_PATIENT,
  STEP_CART,
  TOTAL_STEPS,
  getLocalISODate,
  normalizeWizardContractValue,
  getWizardRecordKind,
  getWizardSourceKind,
  hasQueueIdentityValue,
  resolveExplicitQueueEntryId,
  getFirstQueueNumberId,
  resolveOnlineQueueEntryId,
  getRemovedQueueEntryIds,
  cancelRemovedQueueEntries,
  normalizeServiceSelectionValue,
  normalizeServiceSelectionName,
  normalizeGenderForForm,
  firstNonEmpty,
  resolvePatientGenderValue,
  genderToPatientSexForApi,
  resolveInitialPatientId,
  WIZARD_DEPARTMENT_FILTER_KEYS,
  getWizardDepartmentFilterKeys,
  serviceCodeToWizardCategory,
  activeTabToWizardCategory,
  resolveInitialServiceCategory,
  categories,
} from './wizardUtils';

const AppointmentWizardV2 = ({
  isOpen,
  onClose,
  onComplete,
  isProcessing = false,
  setIsProcessing = () => {}, // Дефолтная функция-заглушка
  activeTab = null, // ✅ ДОБАВЛЯЕМ activeTab для фильтрации услуг по отделению
  editMode = false, // ✨ НОВОЕ: Режим редактирования
  initialData = null // ✨ НОВОЕ: Данные для редактирования
}) => {
  // Проверка прав доступа
  const { hasRole } = useRoleAccess();
  const hasRegistrarAccess = hasRole(['Admin', 'Registrar', 'Receptionist']);

  // UX Audit Registrar #2: useConfirm hook для замены window.confirm().
  // Возвращает [confirm, dialog]; dialog должен быть отрендерен в JSX.
  const [confirm, confirmDialog] = useConfirm();

  // Состояние мастера
  const [currentStep, setCurrentStep] = useState(STEP_PATIENT);

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
  const [isSearchingPatients, setIsSearchingPatients] = useState(false); // UX Audit Registrar #11
  const [phoneCheckTimeout, setPhoneCheckTimeout] = useState(null); // ✅ Timeout для проверки телефона
  const [phoneError, setPhoneError] = useState(null); // ✅ Ошибка уникальности телефона
  const [servicesData, setServicesData] = useState([]);
  const [doctorsData, setDoctorsData] = useState([]);
  const [filteredServices, setFilteredServices] = useState([]);
  const [showAllServices, setShowAllServices] = useState(false);
  // PR-25: queue profiles for dynamic department filtering
  const [queueProfiles, setQueueProfiles] = useState([]);
  const [formattedBirthDate, setFormattedBirthDate] = useState('');
  const [repeatEligibilityByItemId, setRepeatEligibilityByItemId] = useState({});
  const [isRepeatEligibilityLoading, setIsRepeatEligibilityLoading] = useState(false);

  // ===================== ИНИЦИАЛИЗАЦИЯ (EDIT MODE vs DRAFT) =====================

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
        const birthDate = initialData.patient_birth_date || (
        initialData.patient_birth_year ? `${initialData.patient_birth_year}-01-01` : '');
        const initialCartItems = (() => {
          logger.log('📦 AppointmentWizardV2: Using SSOT normalizeServicesFromInitialData');
          const items = normalizeServicesFromInitialData(initialData, []);
          logger.log('📦 Initialized cart with items:', items);
          logger.log('📦 InitialData full structure:', initialData);

          if (items.length > 0) {
            logger.log(`✅ SSOT: Услуги извлечены из источника: ${items[0]._source}`);
          }
          return items;
        })();
        setActiveServiceCategory(resolveInitialServiceCategory(initialCartItems, activeTab));
        setServiceSearchQuery('');
        setShowAllServices(false);

        setWizardData({
          patient: {
            id: resolveInitialPatientId(initialData),
            fio: initialData.patient_fio || initialData.patient_name || initialData.patient?.fio || '',
            birth_date: birthDate, // ✅ ИСПРАВЛЕНО: Приоритет полной даты
            phone: formatUzbekPhoneDisplay(
              initialData.phone || initialData.patient_phone || initialData.patient?.phone || ''
            ),
            address: initialData.address || initialData.patient?.address || '',
            gender: (() => {
              // ✅ ИСПРАВЛЕНО: Преобразование пола из формата БД (M/F/sex) в формат формы (male/female)
              const genderValue = resolvePatientGenderValue(initialData);
              return normalizeGenderForForm(genderValue);
            })()
          },
          cart: {
            // ⭐ SSOT: Используем унифицированную функцию вместо 5 разных источников
            items: initialCartItems,
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
        setActiveServiceCategory(activeTabToWizardCategory(activeTab));
        setServiceSearchQuery('');
        setShowAllServices(false);
        // New appointment mode intentionally avoids persistent draft storage for patient PHI.
      }
    }
  }, [isOpen, editMode, initialData, activeTab]);

  useEffect(() => {
    if (!isOpen || !editMode || wizardData.patient.gender) return;

    const patientId = wizardData.patient.id || resolveInitialPatientId(initialData);
    if (!patientId) return;

    let cancelled = false;

    const hydrateMissingEditGender = async () => {
      const token = tokenManager.getAccessToken();
      if (!token) return;

      try {
        // UX Audit Stage 3 (Wizard issue 5.1):
        // Заменён raw fetch() с багом двойного префикса `/api/v1/api/v1/patients/{id}`
        // на централизованный api.get() через getPatient().
        // Раньше было: fetch(`${API_BASE}/api/v1/patients/${patientId}`) — двойной префикс!
        const patient = await getPatient(patientId);
        const normalizedGender = normalizeGenderForForm(resolvePatientGenderValue(patient));
        if (!normalizedGender || cancelled) return;

        setWizardData((prev) => {
          if (prev.patient.gender) return prev;
          return {
            ...prev,
            patient: {
              ...prev.patient,
              id: prev.patient.id || patientId,
              gender: normalizedGender
            }
          };
        });
      } catch (error) {
        logger.warn('[AppointmentWizardV2] Failed to hydrate edit-mode patient gender', {
          patientId,
          error: error?.message || error
        });
      }
    };

    hydrateMissingEditGender();

    return () => {
      cancelled = true;
    };
  }, [isOpen, editMode, wizardData.patient.id, wizardData.patient.gender, initialData]);

  // ✅ ИСПРАВЛЕНО: Сброс состояния мастера при закрытии
  useEffect(() => {
    if (!isOpen) {
      // Сбрасываем состояние при закрытии
      setWizardData({
        patient: { id: null, fio: '', birth_date: '', phone: '', address: '', gender: '' },
        cart: { items: [], discount_mode: 'none', all_free: false, notes: '' },
        payment: { method: 'cash', total_amount: 0 }
      });
      setCurrentStep(STEP_PATIENT);
      setFormattedBirthDate('');
      setRepeatEligibilityByItemId({});
      setIsRepeatEligibilityLoading(false);
      setActiveServiceCategory('specialists');
      setServiceSearchQuery('');
      setShowAllServices(false);
    }
  }, [isOpen]);

  // Safeguard: Ensure wizardData structure is valid
  useEffect(() => {
    if (!wizardData.patient) {
      logger.warn('⚠️ Wizard data corrupted (missing patient), resetting...');
      setWizardData((prev) => ({
        ...prev,
        patient: { id: null, fio: '', birth_date: '', phone: '', address: '', gender: '' }
      }));
    }
    if (!wizardData.cart) {
      setWizardData((prev) => ({
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
  const nextStepRef = useRef(() => {});
  const handleCompleteRef = useRef(async () => {});

  // Общее количество шагов
  const totalSteps = TOTAL_STEPS;

  // ===================== ПРОВЕРКА ТЕЛЕФОНА =====================

  const checkPhoneUniqueness = async (phone) => {
    const normalizedPhone = normalizeUzbekPhoneForApi(phone);
    const cleanPhone = normalizedPhone.replace(/\D/g, '');

    // Проверяем только если номер уже канонический
    if (cleanPhone.length !== 12) {
      setPhoneError(null);
      return;
    }

    try {
      // UX Audit Stage 3 (Wizard issue 5.1):
      // Заменён raw fetch() на searchPatientsByPhone() из api/patients.
      const data = await searchPatientsByPhone(normalizedPhone);
      // Если найден пациент и это не тот же самый пациент (если мы редактируем, но тут мы создаем/ищем)
      // В мастере мы всегда предполагаем, что если ID не выбран, то это новый.
      // Если ID выбран, то мы не проверяем (или проверяем, не занят ли другим).

      const existingPatient = data.find((p) => {
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
    } catch (error) {
      logger.error('Ошибка проверки телефона:', error);
    }
  };

  const handlePhoneChange = (value) => {
    const formatted = formatUzbekPhoneDisplay(value);
    setWizardData((prev) => ({
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



  // Persistent draft loading is disabled to keep patient PHI out of browser storage.


  // Reset wizard to initial state. QW-08 fix: previously called clearDraft and showed
  // a misleading "Черновик очищен" toast even though no persistent draft existed.
  // Renamed intent is purely in-memory form reset.
  const clearDraft = () => {
    setWizardData({
      patient: { id: null, fio: '', birth_date: '', phone: '', address: '', gender: '' },
      cart: { items: [], discount_mode: 'none', all_free: false, notes: '' },
      payment: { method: 'cash', total_amount: 0 }
    });
    setFormattedBirthDate('');
    setCurrentStep(STEP_PATIENT);
    toast.success('Форма очищена');
  };

  // ===================== МАСКИ ВВОДА =====================

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

    // UX Audit Registrar #11: loading indicator во время поиска.
    setIsSearchingPatients(true);

    try {
      // UX Audit Stage 3 (Wizard issue 5.1):
      // Заменён raw fetch() на searchPatientsApi() из api/patients.
      const data = await searchPatientsApi(query);

      // ✅ Формируем fio из отдельных полей, если его нет
      const patientsWithFio = data.map((patient) => {
          if (!patient.fio && (patient.last_name || patient.first_name)) {
            const parts = [
            patient.last_name || '',
            patient.first_name || '',
            patient.middle_name || ''].
            filter((p) => p);
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
    } catch (error) {
      logger.error('Ошибка поиска пациентов:', error);
    } finally {
      setIsSearchingPatients(false);
    }
  }, []);

  const handlePatientSearch = (value) => {
    // 🚨 FIX: Сбрасываем ID при изменении текста, чтобы не было "призраков"
    // Если пользователь меняет имя, это уже не тот пациент, которого выбрали ранее
    setWizardData((prev) => ({
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
      patient.middle_name || ''].
      filter((p) => p);
      patientFio = parts.join(' ').trim() || 'Без имени';
    } else if (!patientFio) {
      patientFio = 'Без имени';
    }

    // Сохраняем данные пациента (без парсинга ФИО - backend сделает это при создании)
    setWizardData((prev) => ({
      ...prev,
      patient: {
        id: patient.id,
        fio: patientFio,
        birth_date: patient.birth_date || '',
        phone: patient.phone || '',
        address: patient.address || '',
        gender: (() => {
          // ✅ ИСПРАВЛЕНО: Преобразование пола из формата БД (M/F/sex) в формат формы (male/female)
          const genderValue = resolvePatientGenderValue(patient);
          return normalizeGenderForForm(genderValue);
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
    setErrors((prev) => ({ ...prev, fio: null }));
  };



  const handleBirthDateChange = (value) => {
    const formatted = formatBirthDate(value);
    setFormattedBirthDate(formatted);

    // Конвертируем в ISO формат для сохранения
    const isoDate = convertDateToISO(formatted);
    setWizardData((prev) => ({
      ...prev,
      patient: { ...prev.patient, birth_date: isoDate }
    }));
  };

  // ===================== ЗАГРУЗКА ДАННЫХ =====================

  const loadServices = useCallback(async () => {
    try {
      const { data } = await api.get('/registrar/services');

        // PR-25: load queue profiles for dynamic department filtering
        let profiles = queueProfiles;
        if (profiles.length === 0) {
          try {
            const profilesRes = await api.get('/queues/profiles?active_only=true');
            profiles = profilesRes.data?.profiles || [];
            setQueueProfiles(profiles);
          } catch (e) {
            logger.error('Failed to load queue profiles for filter:', e);
          }
        }

        // Извлекаем все услуги из групп
        let allServices = [];
        if (data.services_by_group) {
          Object.values(data.services_by_group).forEach((groupServices) => {
            if (Array.isArray(groupServices)) {
              allServices = allServices.concat(groupServices);
            }
          });
        }

        // ✅ ФИЛЬТРАЦИЯ ПО ОТДЕЛЕНИЮ: Если activeTab указан, показываем услуги этого отделения
        // PR-25: use dynamic queueProfiles instead of hardcoded map
        const departmentFilterKeys = editMode ? [] : getWizardDepartmentFilterKeys(activeTab, profiles);
        if (departmentFilterKeys.length > 0) {
          const departmentFilterSet = new Set(departmentFilterKeys);
          allServices = allServices.filter((service) => {
            const departmentKey = String(service.department_key || service.departmentKey || '').trim().toLowerCase();
            return !departmentKey || departmentFilterSet.has(departmentKey);
          });
        }

        setServicesData(allServices);
        setFilteredServices(allServices);
    } catch (error) {
      logger.error('Ошибка загрузки услуг:', error);
    }
  }, [activeTab, editMode]);

  // ===================== РЕЗОЛВИНГ УСЛУГ (SSOT) =====================

  // ✅ SSOT: Функция для получения названия услуги из servicesData
  const getServiceName = useCallback((item) => {
    if (!item) return 'Неизвестная услуга';

    // Приоритет 1: Если есть service_id, ищем в servicesData
    if (item.service_id) {
      const service = servicesData.find((s) => s.id === item.service_id);
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
      const foundByName = servicesData.find((s) => s.name === serviceName);
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

      const foundService = servicesData.find((s) => {
        if (!s.service_code) return false;
        const serviceCodeUpper = String(s.service_code).toUpperCase().trim();
        const serviceCodeNoZero = serviceCodeUpper.replace(/^([A-Z])0+(\d+)$/, '$1$2');

        if (serviceCodeUpper === searchNameUpper) return true;
        if (serviceCodeNoZero === searchNameNoZero) return true;
        if (s.name === searchName || s.name === searchNameUpper) return true;
        return false;
      });

      if (foundService?.name) return foundService.name;
    }

    // Fallback: возвращаем service_name (если это название) или код
    // ⭐ FINAL DEFENSIVE: Убеждаемся, что возвращаем строку
    const fallback = serviceName || searchName || 'Неизвестная услуга';
    return typeof fallback === 'string' ? fallback : JSON.stringify(fallback);
  }, [servicesData]);

  // Эффект для обогащения данных корзины реальными ID и ценами после загрузки servicesData
  useEffect(() => {
    // ✅ ИСПРАВЛЕНО: Разрешаем услуги не только в editMode, но и когда servicesData загружены
    if (servicesData.length > 0 && wizardData.cart.items.length > 0) {
      const unresolvedCount = wizardData.cart.items.filter((i) => !i.service_id).length;

      // ✅ НОВОЕ: Проверяем также элементы с service_id, у которых имя не совпадает с SSOT
      const hasNameMismatches = wizardData.cart.items.some((item) => {
        if (!item.service_id) return false;
        const service = servicesData.find((s) => s.id === item.service_id);
        return service && service.name && service.name !== item.service_name;
      });

      // Если нет ни нерешённых услуг, ни несоответствий имён — выходим
      if (unresolvedCount === 0 && !hasNameMismatches) return;

      logger.log('🔍 Attempting to resolve services...', {
        servicesDataCount: servicesData.length,
        cartItemsCount: wizardData.cart.items.length,
        unresolvedItems: unresolvedCount
      });

      const updatedItems = wizardData.cart.items.map((item) => {
        // ✅ Сначала синхронизируем элементы, у которых уже есть service_id, с SSOT (servicesData)
        if (item.service_id) {
          const service = servicesData.find((s) => s.id === item.service_id);

          if (service) {
            const nextName = service.name || item.service_name;
            const nextPrice = service.price != null ? service.price : item.service_price || 0;

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

        const foundService = servicesData.find((s) => {
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
        }

        logger.warn(`⚠️ Service not found in servicesData: "${searchName}". Available codes:`,
        servicesData.slice(0, 20).map((s) => `${s.service_code || 'N/A'}: ${s.name || 'N/A'}`).filter((s) => s !== 'N/A: N/A'));

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
          logger.log('📋 Resolved services:', resolved.map((item) => `${item._temp_name || item.service_name} -> ${item.service_name} (ID: ${item.service_id})`));
        }

        setWizardData((prev) => ({
          ...prev,
          cart: {
            ...prev.cart,
            items: updatedItems
          }
        }));
      }
    }
  }, [servicesData, wizardData.cart.items]); // ✅ ИСПРАВЛЕНО: Триггерим при изменении servicesData или корзины

  const loadDoctors = useCallback(async () => {
    try {
      const { data } = await api.get('/registrar/doctors');
      setDoctorsData(data);
    } catch (error) {
      logger.error('Ошибка загрузки врачей:', error);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadServices();
      loadDoctors();
    }
  }, [isOpen, loadServices, loadDoctors]); // ✅ Обновляем услуги при смене вкладки

  const getServiceById = useCallback((serviceId) => {
    if (!serviceId) return null;
    return servicesData.find((service) => service.id === serviceId) || null;
  }, [servicesData]);

  const consultationCartItems = useMemo(() =>
  (wizardData.cart.items || []).
  map((item) => ({ item, service: getServiceById(item.service_id) })).
  filter(({ service }) => Boolean(service?.is_consultation)),
  [wizardData.cart.items, getServiceById]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    if (!consultationCartItems.length) {
      setRepeatEligibilityByItemId({});
      setIsRepeatEligibilityLoading(false);
      return;
    }

    const patientId = wizardData.patient.id;
    const todayLocal = (() => {
      const now = new Date();
      const year = now.getFullYear();
      const month = String(now.getMonth() + 1).padStart(2, '0');
      const day = String(now.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}`;
    })();

    const initialMap = {};
    const previewCandidates = [];

    consultationCartItems.forEach(({ item, service }) => {
      if (!service) return;
      if (!patientId) {
        initialMap[item.id] = {
          eligible: false,
          reason: 'Проверка доступна после выбора существующего пациента',
          repeat_discount_percent: 0,
          repeat_window_days: 0
        };
        return;
      }

      if (!item.doctor_id) {
        initialMap[item.id] = {
          eligible: false,
          reason: 'Выберите врача для проверки повторной скидки',
          repeat_discount_percent: 0,
          repeat_window_days: 0
        };
        return;
      }

      previewCandidates.push({
        candidate_key: String(item.id),
        doctor_id: item.doctor_id,
        service_id: item.service_id,
        visit_date: item.visit_date || todayLocal
      });
    });

    let isCancelled = false;

    const runPreview = async () => {
      if (!patientId || previewCandidates.length === 0) {
        if (!isCancelled) {
          setRepeatEligibilityByItemId(initialMap);
          setIsRepeatEligibilityLoading(false);
        }
        return;
      }

      if (!isCancelled) {
        setIsRepeatEligibilityLoading(true);
      }

      try {
        const response = await api.post('/registrar/repeat-eligibility-preview', {
          patient_id: patientId,
          candidates: previewCandidates
        });

        const mergedMap = { ...initialMap };
        (response?.data?.items || []).forEach((resultItem) => {
          const key = Number(resultItem?.candidate_key);
          if (!Number.isNaN(key)) {
            mergedMap[key] = {
              eligible: Boolean(resultItem?.eligible),
              reason: resultItem?.reason || '',
              repeat_discount_percent: Number(resultItem?.repeat_discount_percent || 0),
              repeat_window_days: Number(resultItem?.repeat_window_days || 0)
            };
          }
        });

        if (!isCancelled) {
          setRepeatEligibilityByItemId(mergedMap);
        }
      } catch (error) {
        logger.error('❌ Ошибка preview повторной скидки:', error);
        const fallbackMap = { ...initialMap };
        previewCandidates.forEach((candidate) => {
          const key = Number(candidate.candidate_key);
          if (!Number.isNaN(key)) {
            fallbackMap[key] = {
              eligible: false,
              reason: 'Не удалось проверить повторную скидку',
              repeat_discount_percent: 0,
              repeat_window_days: 0
            };
          }
        });
        if (!isCancelled) {
          setRepeatEligibilityByItemId(fallbackMap);
        }
      } finally {
        if (!isCancelled) {
          setIsRepeatEligibilityLoading(false);
        }
      }
    };

    runPreview();

    return () => {
      isCancelled = true;
    };
  }, [isOpen, wizardData.patient.id, consultationCartItems]);

  const repeatSuggestionSummary = useMemo(() => {
    if (!consultationCartItems.length) {
      return {
        hasConsultations: false,
        fullyEligible: false,
        hasMixed: false,
        maxDiscountPercent: 0,
        hasUnknown: false
      };
    }

    let eligibleCount = 0;
    let ineligibleCount = 0;
    let unknownCount = 0;
    let maxDiscountPercent = 0;

    consultationCartItems.forEach(({ item }) => {
      const eligibility = repeatEligibilityByItemId[item.id];
      if (!eligibility) {
        unknownCount += 1;
        return;
      }
      if (eligibility.eligible) {
        eligibleCount += 1;
        maxDiscountPercent = Math.max(
          maxDiscountPercent,
          Number(eligibility.repeat_discount_percent || 0)
        );
      } else {
        ineligibleCount += 1;
      }
    });

    const fullyEligible = eligibleCount === consultationCartItems.length && consultationCartItems.length > 0;
    const hasMixed = eligibleCount > 0 && ineligibleCount > 0;

    return {
      hasConsultations: true,
      fullyEligible,
      hasMixed,
      maxDiscountPercent,
      hasUnknown: unknownCount > 0
    };
  }, [consultationCartItems, repeatEligibilityByItemId]);

  const applyRepeatSuggestion = useCallback(() => {
    if (!repeatSuggestionSummary.hasConsultations) {
      toast.info('Добавьте консультацию, чтобы применить повторную скидку');
      return;
    }

    if (repeatSuggestionSummary.hasUnknown || isRepeatEligibilityLoading) {
      toast.info('Дождитесь завершения проверки повторной скидки');
      return;
    }

    if (repeatSuggestionSummary.fullyEligible) {
      setWizardData((prev) => ({
        ...prev,
        cart: {
          ...prev.cart,
          discount_mode: 'repeat'
        }
      }));
      const discountPercent = repeatSuggestionSummary.maxDiscountPercent;
      toast.success(
        discountPercent > 0 ?
        `Применена повторная скидка ${discountPercent}%` :
        'Применен режим повторного визита'
      );
      return;
    }

    toast.warning(MIXED_REPEAT_WARNING);
  }, [repeatSuggestionSummary, isRepeatEligibilityLoading]);

  // 🔧 УПРОЩЕННАЯ ФИЛЬТРАЦИЯ: Показываем все услуги без привязки к врачам
  const filterServices = (allServices) => {

    // Если нет услуг, показываем пустой массив
    if (!Array.isArray(allServices) || allServices.length === 0) {
      setFilteredServices([]);
      return;
    }

    // 🎯 НОВАЯ ЛОГИКА: Всегда показываем ВСЕ услуги
    // Пользователь может выбирать любые услуги независимо от врачей
    setFilteredServices(allServices);
  };











  // ===================== КОРЗИНА =====================

  const addToCart = (service) => {
    // ✅ SSOT: Всегда используем данные из servicesData
    const serviceFromData = servicesData.find((s) => s.id === service.id) || service;

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

    setWizardData((prev) => ({
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
    const newItems = wizardData.cart.items.filter((item) => item.id !== itemId);
    setWizardData((prev) => ({
      ...prev,
      cart: {
        ...prev.cart,
        items: newItems
      }
    }));

    filterServices(servicesData, newItems);
  };

  const updateCartItem = (itemId, field, value) => {
    const newItems = wizardData.cart.items.map((item) =>
    item.id === itemId ? { ...item, [field]: value } : item
    );

    setWizardData((prev) => ({
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

    wizardData.cart.items.forEach((item) => {
      let itemPrice = item.service_price * item.quantity;

      // Применяем скидки
      const service = servicesData.find((s) => s.id === item.service_id);
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

  const validatePatientFio = (rawFio) => {
    const normalizedFio = rawFio.trim();

    if (!normalizedFio) {
      return 'Введите ФИО пациента';
    }

    if (!PATIENT_NAME_PATTERN.test(normalizedFio)) {
      return 'ФИО может содержать только буквы, пробелы, дефисы и апостроф';
    }

    if (/\s{3,}/.test(normalizedFio)) {
      return 'ФИО содержит слишком много пробелов подряд';
    }

    const nameParts = normalizedFio.split(/\s+/).filter(Boolean);
    const lastName = nameParts[0] || '';
    const firstName = nameParts[1] || (nameParts[0] || '');
    const middleName = nameParts.length > 2 ? nameParts.slice(2).join(' ') : '';

    if (lastName.length < 2) {
      return 'Фамилия должна содержать минимум 2 буквы';
    }

    if (firstName.length < 2) {
      return 'Имя должно содержать минимум 2 буквы';
    }

    if (middleName && middleName.length < 2) {
      return 'Отчество должно содержать минимум 2 буквы';
    }

    return null;
  };

  // ===================== НАВИГАЦИЯ =====================

  const validateStep = (step) => {
    const newErrors = {};

    if (step === 1) {
      const fioError = validatePatientFio(wizardData.patient.fio);
      if (fioError) {
        newErrors.fio = fioError;
      }
      // ✅ Телефон теперь необязателен (дети, пожилые без телефона)
      // Проверяем формат только если телефон указан
      if (wizardData.patient.phone.trim() && !isValidUzbekPhone(wizardData.patient.phone)) {
        newErrors.phone = 'Номер телефона должен быть в формате +998XXXXXXXXX';
      }
      if (!wizardData.patient.gender) {// ✅ Валидация пола
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
      const missingDoctors = wizardData.cart.items.filter((item) => {
        const service = servicesData.find((s) => s.id === item.service_id);
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
      setCurrentStep((prev) => Math.min(prev + 1, totalSteps));
    }
  };
  nextStepRef.current = nextStep;

  const prevStep = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 1));
  };







  // ===================== ГОРЯЧИЕ КЛАВИШИ =====================

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (!isOpen) return;

      // Enter - следующий шаг (кроме textarea)
      if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && e.target.tagName !== 'TEXTAREA') {
        e.preventDefault();
        if (currentStep < totalSteps) {
          nextStepRef.current();
        } else {
          handleCompleteRef.current();
        }
      }

      // Ctrl+Enter - завершить
      if (e.key === 'Enter' && e.ctrlKey) {
        e.preventDefault();
        handleCompleteRef.current();
      }

      // Shift+Enter в textarea - перенос строки (по умолчанию)
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, currentStep, totalSteps]);

  // ===================== ЗАВЕРШЕНИЕ =====================

  const handleComplete = async () => {
    if (!validateStep(currentStep)) return;

    // P-022 fix: previously used toast.warning/toast.info as blocking validation
    // (early return after toast). Toasts are non-modal and easy to miss — the
    // user clicks "Завершить" and nothing visible happens besides a transient
    // notification. Now we surface these as inline errors in the cart via
    // errors.repeat, which is rendered next to the cart content (see cart
    // error block at the bottom of Step 2). Toasts are kept only for the
    // auth-token check below, which is not cart-validation.
    const isRepeatMode = wizardData.cart.discount_mode === 'repeat' && !wizardData.cart.all_free;
    if (isRepeatMode) {
      if (!repeatSuggestionSummary.hasConsultations) {
        setErrors((prev) => ({ ...prev, repeat: 'Повторная скидка применяется только к консультациям. Добавьте консультацию в корзину или выберите другой тип скидки.' }));
        setCurrentStep(STEP_CART); // Ensure user is on the cart step to see the error
        return;
      }
      if (repeatSuggestionSummary.hasUnknown || isRepeatEligibilityLoading) {
        setErrors((prev) => ({ ...prev, repeat: 'Дождитесь завершения проверки повторной скидки перед завершением.' }));
        setCurrentStep(STEP_CART);
        return;
      }
      if (!repeatSuggestionSummary.fullyEligible) {
        setErrors((prev) => ({ ...prev, repeat: MIXED_REPEAT_WARNING }));
        setCurrentStep(STEP_CART);
        return;
      }
      // Clear any prior repeat error if validation now passes
      setErrors((prev) => {
        if (!prev.repeat) return prev;
        const next = { ...prev };
        delete next.repeat;
        return next;
      });
    } else {
      // Clear stale repeat error when not in repeat mode
      setErrors((prev) => {
        if (!prev.repeat) return prev;
        const next = { ...prev };
        delete next.repeat;
        return next;
      });
    }

    // Проверяем токен авторизации
    const token = tokenManager.getAccessToken();
    if (!token) {
      toast.error('Требуется авторизация. Пожалуйста, войдите в систему заново.');
      return;
    }

    // UX Audit Registrar #9: Summary confirmation перед завершением.
    // Показываем что именно будет создано — услуги, количество визитов, сумма.
    // Раньше кнопка «Завершить» сразу создавала запись без preview.
    const cartItems = wizardData.cart.items || [];
    const totalAmount = cartItems.reduce((sum, item) => sum + (Number(item.price) || 0), 0);
    const serviceCount = cartItems.length;
    const doctorCount = new Set(cartItems.map((item) => item.doctor_id).filter(Boolean)).size;

    // PR-25: itemized breakdown — show each service + doctor + price
    const itemizedLines = cartItems.map((item) => {
      const svcName = item.service_name || item.name || `Услуга #${item.service_id}`;
      const qty = item.quantity || 1;
      const price = Number(item.price) || 0;
      const docName = item.doctor_name || (item.doctor_id ? `Врач #${item.doctor_id}` : '');
      const priceStr = price > 0 ? `${new Intl.NumberFormat('ru-RU').format(price * qty)} сум` : 'бесплатно';
      return `• ${svcName}${qty > 1 ? ` ×${qty}` : ''}${docName ? ` — ${docName}` : ''} — ${priceStr}`;
    });

    const summaryLines = [
      `Пациент: ${wizardData.patient.fio || '—'}`,
      '',
      ...itemizedLines,
      '',
      doctorCount > 1 ? `Врачей: ${doctorCount}` : null,
      totalAmount > 0 ? `Итого: ${new Intl.NumberFormat('ru-RU').format(totalAmount)} сум` : 'Бесплатно',
    ].filter(Boolean);

    // UX Audit Registrar #2: window.confirm() → useConfirm hook.
    // PR-24: parameterize title/CTA by editMode so user sees "Обновить" not "Создать"
    const confirmed = await confirm({
      title: editMode ? 'Обновить запись' : 'Создать запись',
      message: editMode ? 'Обновить запись с указанными данными?' : 'Создать запись с указанными данными?',
      description: summaryLines.join('\n'),
      confirmLabel: editMode ? 'Обновить' : 'Создать',
      cancelLabel: 'Отмена',
      intent: 'primary',
    });
    if (!confirmed) {
      return;
    }

    // UX Audit Stage 3 (Wizard issue 5.1):
    // Проверяем валидность токена через централизованный helper.
    // Раньше это был raw fetch() с проверкой status === 401.
    try {
      const isAuthorized = await checkAuthProbe();
      if (!isAuthorized) {
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
      const itemsWithoutServiceId = wizardData.cart.items.filter((item) => !item.service_id);
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
      const invalidVisits = visits.filter((visit) =>
      !visit.services ||
      visit.services.length === 0 ||
      visit.services.some((s) => !s.service_id)
      );

      if (invalidVisits.length > 0) {
        logger.error('❌ Найдены визиты с невалидными услугами:', invalidVisits);
        toast.error('Некоторые услуги не могут быть обработаны. Пожалуйста, перезагрузите страницу и попробуйте снова.');
        return;
      }

      // ✅ НОВОЕ: Локальная переменная для patient_id, которую будем заполнять по мере создания/поиска пациента
      let patientId = wizardData.patient.id;
      const initialPatientId = resolveInitialPatientId(initialData);
      if (editMode && initialPatientId && !patientId) {
        patientId = initialPatientId;
        logger.warn('[AppointmentWizardV2] Restored edit-mode patient_id from initialData before submit', {
          patientId: initialPatientId
        });
      }
      const normalizedPhone = wizardData.patient.phone
        ? normalizeUzbekPhoneForApi(wizardData.patient.phone)
        : null;
      const normalizedPhoneDigits = normalizedPhone ? normalizedPhone.replace(/\D/g, '') : '';
      const selectedPatientSex = genderToPatientSexForApi(wizardData.patient.gender);

      // === ШАГ 1: ОПРЕДЕЛЯЕМ ИЛИ НАХОДИМ patient_id ===

      // В режиме EDIT MODE с QR-пациентом (patient_id = null)
      if (editMode && !patientId && wizardData.patient.phone) {
        logger.log('🔍 Edit mode: patient_id is null, searching for existing patient by phone...');
        logger.log('📞 Patient data:', {
          fio: wizardData.patient.fio,
          phone: normalizedPhone,
          birth_date: wizardData.patient.birth_date
        });

        // Ищем пациента по телефону
        const cleanPhone = normalizedPhoneDigits;

        // UX Audit Stage 3 (Wizard issue 5.1 + 5.3):
        // Заменён двойной raw fetch() (по форматированному + очищенному телефону)
        // на единый helper findPatientByPhoneVariants из api/patients.
        const foundPatient = await findPatientByPhoneVariants(normalizedPhone);
        if (foundPatient) {
          logger.log('📋 Found existing patient by phone:', foundPatient.id);
        }

        if (foundPatient) {
          // Обновляем локальный patientId и wizardData
          patientId = foundPatient.id;
          setWizardData((prev) => ({
            ...prev,
            patient: { ...prev.patient, id: foundPatient.id }
          }));
          logger.log('✅ Found existing patient:', foundPatient.id);

          // Обновляем данные пациента если нужно
          const foundPatientSex = genderToPatientSexForApi(resolvePatientGenderValue(foundPatient));
          const needsUpdate =
          wizardData.patient.birth_date && wizardData.patient.birth_date !== foundPatient.birth_date ||
          wizardData.patient.address && wizardData.patient.address !== foundPatient.address ||
          selectedPatientSex && selectedPatientSex !== foundPatientSex;

          if (needsUpdate) {
            logger.log('🔄 Updating patient data...');
            const updateData = {};

            if (wizardData.patient.birth_date) updateData.birth_date = wizardData.patient.birth_date;
            if (wizardData.patient.address) updateData.address = wizardData.patient.address;
            if (selectedPatientSex) updateData.sex = selectedPatientSex;

            try {
              // UX Audit Stage 3: заменён raw fetch() PUT на updatePatient().
              await updatePatient(foundPatient.id, updateData);
              logger.log('✅ Patient data updated');
            } catch (e) {
              logger.warn('⚠️ Failed to update patient:', e);
            }
          }
        } else {
          // ✅ НОВОЕ: Если в режиме редактирования по QR пациент по телефону не найден,
          // создаем НОВОГО пациента с данными из формы, чтобы не блокировать завершение мастера.
          logger.warn(`⚠️ Пациент с телефоном ${wizardData.patient.phone} не найден. Создаем нового пациента (editMode + QR).`);

          const patientData = {
            full_name: wizardData.patient.fio.trim(),
            sex: selectedPatientSex,
            last_name: wizardData.patient.lastName || '',
            first_name: wizardData.patient.firstName || '',
            middle_name: wizardData.patient.middleName || null,
            phone: normalizedPhone,
            address: wizardData.patient.address || null
          };

          if (wizardData.patient.birth_date) {
            patientData.birth_date = wizardData.patient.birth_date;
          }

          logger.log('📋 Данные для СОЗДАНИЯ пациента в editMode (QR fallback):', patientData);

          // UX Audit Stage 3: заменён raw fetch() POST на createPatient().
          // createPatient() бросает Error с детальным сообщением при неудаче
          // (например, «пациент уже существует»), нам не нужен else-блок.
          const newPatient = await createPatient(patientData);
          patientId = newPatient.id;
          setWizardData((prev) => ({
            ...prev,
            patient: { ...prev.patient, id: newPatient.id }
          }));
          logger.log('✅ Новый пациент создан в editMode (QR fallback):', newPatient.id);
        }
      }
      // В обычном режиме (не edit) создаем пациента если нужно
      else if (!editMode && !patientId) {
        // ✅ УПРОЩЕНО: Отправляем полное ФИО в API, backend нормализует его (Single Source of Truth)
        // Валидация обязательных полей
        if (!wizardData.patient.fio || !wizardData.patient.fio.trim()) {
          throw new Error('ФИО пациента обязательно для заполнения');
        }

        const token = tokenManager.getAccessToken();
        logger.log('🔑 Токен для создания пациента:', token ? `${token.substring(0, 20)}...` : 'НЕТ ТОКЕНА');
        logger.log('📊 Длина токена:', token ? token.length : 0);

        // Подготовка данных пациента - отправляем полное ФИО, backend нормализует
        const patientData = {
          full_name: wizardData.patient.fio.trim(),
          sex: selectedPatientSex,
          // Для обратной совместимости также отправляем отдельные поля (если есть)
          last_name: wizardData.patient.lastName || '',
          first_name: wizardData.patient.firstName || '',
          middle_name: wizardData.patient.middleName || null,
          phone: normalizedPhone,
          address: wizardData.patient.address || null
        };

        // Добавляем дату рождения только если она есть
        if (wizardData.patient.birth_date) {
          patientData.birth_date = wizardData.patient.birth_date;
        }

        logger.log('📋 Данные для создания пациента:', patientData);

        // UX Audit Stage 3 (Wizard issue 5.1):
        // Заменён большой raw fetch() блок (с if/else if/else для 200/400/other)
        // на createPatient() из api/patients, который инкапсулирует 400-логику.
        try {
          const patient = await createPatient(patientData);
          patientId = patient.id;
          setWizardData((prev) => ({
            ...prev,
            patient: { ...prev.patient, id: patient.id }
          }));
          logger.log('✅ Пациент создан успешно:', patient.id);
        } catch (createError) {
          // createPatient бросает Error с .status === 400 если «пациент уже существует»
          if (createError.status === 400 && wizardData.patient.phone) {
            // Пациент уже существует — ищем по телефону
            const cleanPhone = normalizedPhoneDigits;
            logger.log(`⚠️ Ищем существующего пациента по номеру телефона: ${wizardData.patient.phone} (clean: ${cleanPhone})`);

            // UX Audit Stage 3 (issue 5.3): используем findPatientByPhoneVariants
            const foundPatient = await findPatientByPhoneVariants(normalizedPhone);

            if (foundPatient) {
              patientId = foundPatient.id;
              setWizardData((prev) => ({
                ...prev,
                patient: { ...prev.patient, id: foundPatient.id }
              }));
              logger.log('✅ Найден существующий пациент (по телефону):', foundPatient.id);
            } else {
              // 🚨 НЕ используем fallback - требуем точное совпадение
              logger.error('❌ Exact phone match not found after 400');
              throw new Error(`Пациент с телефоном ${wizardData.patient.phone} уже существует, но не найден в базе данных.`);
            }
          } else if (createError.status === 400) {
            // Нет телефона и ошибка создания - это проблема валидации
            throw new Error(`Ошибка валидации данных пациента: ${createError.message}`);
          } else {
            // Другие ошибки (5xx, network)
            logger.error('❌ Ошибка создания пациента:', createError.status, createError.message);
            throw new Error(`Ошибка создания пациента: ${createError.status || ''} ${createError.message}`);
          }
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

      const initialPatientSex = genderToPatientSexForApi(resolvePatientGenderValue(initialData));
      if (editMode && patientId && selectedPatientSex && selectedPatientSex !== initialPatientSex) {
        // UX Audit Stage 3 (Wizard issue 5.1):
        // Заменён raw fetch() PUT на updatePatient() из api/patients.
        try {
          await updatePatient(patientId, { sex: selectedPatientSex });
          logger.log('[AppointmentWizardV2] Persisted edit-mode patient gender before submit', {
            patientId,
            sex: selectedPatientSex
          });
        } catch (updateError) {
          logger.error('[AppointmentWizardV2] Failed to persist patient gender before edit submit', {
            patientId,
            status: updateError.status,
            errorText: updateError.message
          });
          toast.error('Не удалось сохранить пол пациента. Проверьте доступ и попробуйте ещё раз.');
          return;
        }
      }

      // ✅ НОВОЕ: Проверяем, редактируется ли запись в очереди (QR или desk) и есть ли новые услуги
      // Расширено для поддержки всех типов записей: online, desk, visit, appointment
      // ✅ ИСПРАВЛЕНО Bug 1: Добавлены явные скобки для правильного приоритета операторов
      const initialRecordKind = getWizardRecordKind(initialData);
      const initialSourceKind = getWizardSourceKind(initialData);
      const hasQueueEntries = editMode && initialData && (
      Array.isArray(initialData.queue_numbers) && initialData.queue_numbers.length > 0 ||
      initialSourceKind === 'online' ||
      initialSourceKind === 'desk' ||
      initialRecordKind === 'online_queue' ||
      initialRecordKind === 'visit' ||
      initialRecordKind === 'appointment');


      const originalServiceIds = new Set();
      const originalQueueIds = new Set(); // ✅ Moved here for availability in handleComplete
      // PR-14: collect updated_at per queue entry for optimistic locking.
      // Map<entryId, isoString> — passed to applyRegistrarEditDelta as
      // expectedEntryUpdatedAt so backend can detect concurrent edits.
      const entryUpdatedAtMap = {};

      if (hasQueueEntries) {
        // ✅ Устанавливаем source по умолчанию для записей типа visit
        const effectiveSource = initialSourceKind || (
        initialRecordKind === 'visit' || initialRecordKind === 'appointment' ? 'desk' : 'online');

        // ✅ Сценарий 3: Редактирование записи в очереди (QR или desk) с добавлением новых услуг
        const recordType = effectiveSource === 'online' ? 'QR-запись' : 'ручная запись';
        logger.log(`📝 Редактирование ${recordType}, проверяем новые услуги...`, {
          source: initialData.source,
          source_kind: initialData.source_kind,
          effectiveSource,
          record_type: initialData.record_type,
          record_kind: initialData.record_kind,
          queue_numbers: Array.isArray(initialData.queue_numbers) ? initialData.queue_numbers.length :
          initialData.queue_numbers ? 1 : 0,
          service_codes: Array.isArray(initialData.service_codes) ? initialData.service_codes.length : 0,
          services: Array.isArray(initialData.services) ? initialData.services.length : 0
        });

        // ⭐ SSOT: Для чистых QR-записей (online_queue) обновляем существующую запись вместо создания новой
        const isOnlineQueueEntry = initialRecordKind === 'online_queue' && effectiveSource === 'online';
        // ✅ SSOT FIX: queue_entry_id приходит из backend для QR-визитов, иначе из queue_numbers
        const queueEntryId = resolveOnlineQueueEntryId(initialData, initialRecordKind, effectiveSource);

        if (isOnlineQueueEntry && queueEntryId) {
          logger.log(`⭐ SSOT: QR-запись ID=${queueEntryId}, обновляем через full-update endpoint...`);

          try {
            // Подготавливаем данные пациента
            const patientData = {
              patient_name: wizardData.patient.fio || wizardData.patient.name,
              phone: normalizedPhone,
              birth_year: wizardData.patient.birth_date ?
              parseInt(wizardData.patient.birth_date.split('-')[0]) :
              null,
              address: wizardData.patient.address || null
            };

            // Подготавливаем услуги из корзины
            const cartServices = wizardData.cart.items.map((item) => ({
              service_id: item.service_id,
              quantity: item.quantity || 1
            })).filter((s) => s.service_id);

            // Определяем visit_type и discount_mode
            const visitType = wizardData.cart.discount_mode === 'repeat' ? 'repeat' :
            wizardData.cart.discount_mode === 'benefit' ? 'benefit' : 'paid';
            const discountMode = wizardData.cart.discount_mode || 'none';
            const allFree = Boolean(wizardData.cart.all_free);

            // logger.log('📤 Вызов updateOnlineQueueEntry:', { ... }); // Removed to reduce noise

            // ⭐ FIX: Собираем все ID из объединённой строки для проверки дубликатов
            const aggregatedIds = initialData.aggregated_ids ||
            (initialData.queue_numbers || []).map((qn) => qn.id).filter(Boolean);

            const updateResult = await updateOnlineQueueEntry({
              entryId: queueEntryId,
              patientData,
              visitType,
              discountMode,
              services: cartServices,
              allFree,
              aggregatedIds // ⭐ FIX: Передаём все ID для проверки дубликатов
            });

            logger.log('✅ QR-запись успешно обновлена:', updateResult);
            toast.success('Запись успешно обновлена');

            // Завершаем без создания новых записей
            // (QW-08: removed dead if(!editMode){localStorage.removeItem(...)} block)
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

        if (Array.isArray(initialData.service_details) && initialData.service_details.length > 0) {
          logger.log('📋 Извлечение исходных услуг из service_details:', initialData.service_details);
          initialData.service_details.forEach((serviceDetail) => {
            if (!serviceDetail) return;

            const serviceId = serviceDetail.service_id || serviceDetail.id || null;
            const serviceCode = serviceDetail.service_code || serviceDetail.code || null;
            const serviceName = serviceDetail.service_name || serviceDetail.name || null;
            const queueId = resolveExplicitQueueEntryId(serviceDetail, { allowLegacyId: false });

            if (serviceId) originalServiceIds.add(serviceId);
            if (queueId) originalQueueIds.add(queueId);
            // PR-14: collect updated_at for optimistic locking
            if (queueId) {
              const ts = serviceDetail.updated_at || serviceDetail.last_changed_at || initialData.updated_at || initialData.last_changed_at;
              if (ts) entryUpdatedAtMap[queueId] = ts;
            }
            if (serviceCode) originalServiceCodes.add(String(serviceCode).toUpperCase().trim());
            if (serviceName) originalServiceNames.add(String(serviceName).toLowerCase().trim());
          });
        }

        // ✅ ПРИОРИТЕТ 1: service_codes - наиболее надежный источник для записей типа visit
        if (Array.isArray(initialData.service_codes) && initialData.service_codes.length > 0) {
          logger.log('📋 Извлечение услуг из service_codes:', initialData.service_codes);
          initialData.service_codes.forEach((code) => {
            if (code) {
              const normalizedCode = code.toUpperCase().trim();
              originalServiceCodes.add(normalizedCode);
              // Находим service_id по service_code
              const service = servicesData.find((s) => {
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
          initialData.services.forEach((serviceValue) => {
            const normalizedRawValue = normalizeServiceSelectionValue(serviceValue);
            const normalizedRawName = normalizeServiceSelectionName(serviceValue);

            if (normalizedRawValue || normalizedRawName) {
              const normalizedValue = normalizedRawValue.toUpperCase().trim();

              // ✅ Сначала пробуем найти по service_code (коды типа 'k01', 'd05')
              // ⚠️ ВАЖНО: Коды могут быть в формате 'K01', 'k01', 'K01: Название' и т.д.
              let service = servicesData.find((s) => {
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
                const normalizedName = normalizedRawName.toLowerCase().trim();
                service = servicesData.find((s) =>
                s.name && s.name.toLowerCase().trim() === normalizedName
                );
              }

              if (service) {
                originalServiceIds.add(service.id);
                if (service.service_code) {
                  originalServiceCodes.add(service.service_code.toUpperCase().trim());
                }
                originalServiceNames.add(service.name.toLowerCase().trim());
                logger.log(`  ✅ Найден service_id=${service.id} для "${normalizedRawValue || normalizedRawName}" (код: ${service.service_code || 'нет'}, имя: ${service.name})`);
              } else {
                // ✅ УЛУЧШЕНО: Показываем примеры кодов из servicesData для отладки
                const exampleCodes = servicesData.
                filter((s) => s.service_code).
                slice(0, 10).
                map((s) => `${s.service_code}: ${s.name}`).
                join(', ');
                logger.warn(`  ⚠️ Услуга "${normalizedRawValue || normalizedRawName || '[empty]'}" не найдена в servicesData. Примеры кодов: ${exampleCodes}`);
              }
            }
          });
        }

        // ✅ ПРИОРИТЕТ 2: queue_numbers - основной источник для всех типов записей
        if (Array.isArray(initialData.queue_numbers) && initialData.queue_numbers.length > 0) {
          logger.log('📋 Извлечение услуг из queue_numbers:', initialData.queue_numbers);
          initialData.queue_numbers.forEach((q) => {
            if (q && q.service_id) {
              originalServiceIds.add(q.service_id);
              const queueId = resolveExplicitQueueEntryId(q);
              if (queueId) originalQueueIds.add(queueId); // ✅ Сохраняем ID записи очереди
              // PR-14: collect updated_at for optimistic locking
              if (queueId) {
                const ts = q.updated_at || q.last_changed_at || initialData.updated_at || initialData.last_changed_at;
                if (ts) entryUpdatedAtMap[queueId] = ts;
              }
              // Находим service_code и name по service_id
              const service = servicesData.find((s) => s.id === q.service_id);
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
              const service = servicesData.find((s) =>
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
              const service = servicesData.find((s) =>
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
          initialData.services.forEach((serviceValue) => {
            const normalizedRawValue = normalizeServiceSelectionValue(serviceValue);
            const normalizedRawName = normalizeServiceSelectionName(serviceValue);

            if (normalizedRawValue || normalizedRawName) {
              const normalizedValue = normalizedRawValue.toUpperCase().trim();
              const normalizedName = normalizedRawName.toLowerCase().trim();

              // ✅ Сначала пробуем найти по service_code (коды типа 'k01', 'd05')
              let service = servicesData.find((s) => {
                if (!s.service_code) return false;
                const serviceCodeUpper = String(s.service_code).toUpperCase().trim();
                // Убираем ведущие нули для сравнения (k01 = k1)
                const serviceCodeNoZero = serviceCodeUpper.replace(/^([A-Z])0+(\d+)$/, '$1$2');
                const valueNoZero = normalizedValue.replace(/^([A-Z])0+(\d+)$/, '$1$2');
                return serviceCodeUpper === normalizedValue || serviceCodeNoZero === valueNoZero;
              });

              // Если не нашли по коду, пробуем по имени
              if (!service) {
                service = servicesData.find((s) =>
                s.name && s.name.toLowerCase().trim() === normalizedName
                );
              }

              if (service) {
                originalServiceIds.add(service.id);
                if (service.service_code) {
                  originalServiceCodes.add(service.service_code.toUpperCase().trim());
                }
                originalServiceNames.add(service.name.toLowerCase().trim());
                logger.log(`  ✅ Найден service_id=${service.id} для "${normalizedRawValue || normalizedRawName}" (код: ${service.service_code || 'нет'}, имя: ${service.name})`);
              } else {
                logger.warn(`  ⚠️ Услуга "${normalizedRawValue || normalizedRawName || '[empty]'}" не найдена в servicesData (ни по коду, ни по имени)`);
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
            const service = servicesData.find((s) => s.id === serviceItem.service_id);
            if (!service) {
              logger.warn('⚠️ Услуга не найдена в servicesData:', serviceItem.service_id);
              continue;
            }

            // Проверяем, является ли услуга новой
            const hasExistingQueueIdentity = Boolean(serviceItem.original_queue_id);
            const isNewService = !hasExistingQueueIdentity &&
            !originalServiceIds.has(serviceItem.service_id) &&
            !originalServiceCodes.has((service.service_code || '').toUpperCase().trim()) &&
            !originalServiceNames.has((service.name || '').toLowerCase().trim());

            logger.log(`  🔍 Услуга "${service.name}" (ID: ${serviceItem.service_id}, код: ${service.service_code}):`, {
              isNewService,
              inServiceIds: originalServiceIds.has(serviceItem.service_id),
              inServiceCodes: originalServiceCodes.has((service.service_code || '').toUpperCase().trim()),
              inServiceNames: originalServiceNames.has((service.name || '').toLowerCase().trim()),
              hasExistingQueueIdentity,
              hasDoctorId: !!visit.doctor_id
            });

            if (isNewService) {
              // Новая услуга - нужно добавить через batch endpoint
              // specialist_id в batch endpoint канонически использует Doctor.id
              // Для услуг без врача (лаборатория) пропускаем batch endpoint
              if (visit.doctor_id) {
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

        // ✅ Готовим batch payload в каноническом формате Doctor.id
        const newServices = [];
        if (newServicesWithDoctorId.length > 0) {
          logger.log(`🔄 Подготовка ${newServicesWithDoctorId.length} новых услуг для batch endpoint через Doctor.id...`);
          newServicesWithDoctorId.forEach((item) => {
            newServices.push({
              specialist_id: item.doctor_id,
              service_id: item.service_id,
              quantity: item.quantity
            });
          });
        }

        // ✅ ИСПРАВЛЕНИЕ: Проверяем наличие новых услуг (как с врачами, так и без)
        const hasNewServices = newServices.length > 0 || newServicesWithoutDoctor.length > 0;

        if (editMode && hasNewServices) {
          const editDeltaServices = [
            ...newServices,
            ...newServicesWithoutDoctor.map((item) => ({
              service_id: item.service_id,
              quantity: item.quantity,
              specialist_id: null
            }))
          ];
          const patientDataForEditDelta = {
            full_name: wizardData.patient.fio || wizardData.patient.name,
            phone: normalizedPhone,
            birth_date: wizardData.patient.birth_date || wizardData.patient.birthDate || null,
            sex: selectedPatientSex,
            address: wizardData.patient.address || null
          };
          Object.keys(patientDataForEditDelta).forEach((key) => {
            if (patientDataForEditDelta[key] === undefined) {
              delete patientDataForEditDelta[key];
            }
          });

          try {
            logger.log('[AppointmentWizardV2] edit mode with new services; applying edit delta', {
              serviceCount: editDeltaServices.length,
              existingQueueEntryIds: Array.from(originalQueueIds)
            });
            const editDeltaResult = await applyRegistrarEditDelta({
              patientId,
              targetDate: getLocalISODate(),
              patientData: patientDataForEditDelta,
              paymentMethod: wizardData.payment.method,
              discountMode: wizardData.cart.discount_mode,
              allFree: wizardData.cart.all_free,
              services: editDeltaServices,
              existingQueueEntryIds: Array.from(originalQueueIds),
              // PR-14: pass optimistic-locking map so backend can detect
              // concurrent edits (last-write-wins → 409 Conflict).
              expectedEntryUpdatedAt: Object.keys(entryUpdatedAtMap).length > 0 ? entryUpdatedAtMap : null,
            });

            if (!editDeltaResult?.success) {
              throw new Error(editDeltaResult?.message || 'Edit delta failed');
            }

            await cancelRemovedQueueEntries(originalQueueIds, wizardData.cart.items, 'edit-delta');
            toast.success('Запись обновлена');
            onComplete?.(editDeltaResult);
            onClose();
            return;
          } catch (editDeltaError) {
            logger.error('[AppointmentWizardV2] edit delta failed', editDeltaError);
            toast.error(editDeltaError?.response?.data?.detail || editDeltaError?.message || 'Не удалось обновить запись');
            return;
          }
        }

        if (editMode && !hasNewServices) {
          logger.log('[AppointmentWizardV2] edit mode without new services; bypassing registrar/cart to avoid duplicate visits');
          visits = [];
        }

        if (hasNewServices) {
          logger.log(`✅ Найдены новые услуги для ${recordType}:`, {
            withDoctor: newServices.length,
            withoutDoctor: newServicesWithoutDoctor.length
          });

          // Фильтруем услуги, которые требуют специалиста (имеют specialist_id)
          const servicesWithSpecialist = newServices.filter((s) => s.specialist_id);

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
                if (existingServices.length > 0 || Object.keys(wizardData.patient).some((key) => {
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
                    wizardData.cart.items.
                    map((item) => item.original_queue_id).
                    filter((id) => id)
                  );

                  const removedQueueIds = Array.from(originalQueueIds).filter((id) => !currentQueueIds.has(id));

                  if (removedQueueIds.length > 0) {
                    logger.log(`🗑️ Найдены удаленные записи очереди: ${removedQueueIds.join(', ')}. Отменяем их...`);
                    try {
                      // Параллельная отмена всех удаленных записей
                      await Promise.all(removedQueueIds.map((id) =>
                      api.post(`/online-queue/entries/${id}/cancel`).
                      catch((err) => {
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

                  // (QW-08: removed dead if(!editMode){localStorage.removeItem(...)} block)
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
              newServicesWithoutDoctor.forEach((item) => {
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
          phone: normalizedPhone,
          birth_date: wizardData.patient.birth_date || wizardData.patient.birthDate,
          sex: selectedPatientSex,
          address: wizardData.patient.address
        };

        // Удаляем undefined значения
        Object.keys(patientUpdateData).forEach((key) =>
        patientUpdateData[key] === undefined && delete patientUpdateData[key]
        );

        try {
          // UX Audit Stage 3 (Wizard issue 5.1):
          // Заменён raw fetch() PUT на updatePatient() из api/patients.
          // updatePatient() бросает Error с .message и .status при неудаче.
          await updatePatient(patientId, patientUpdateData);
          logger.log('✅ Данные пациента успешно обновлены');
          toast.success('Данные пациента обновлены');

          // ✅ НОВОЕ: Обработка удаленных записей очереди (для patient update path)
          const currentQueueIds = new Set(
            wizardData.cart.items.
              map((item) => item.original_queue_id).
              filter((id) => id)
          );

          const removedQueueIds = Array.from(originalQueueIds).filter((id) => !currentQueueIds.has(id));

          if (removedQueueIds.length > 0) {
            logger.log(`🗑️ Найдены удаленные записи очереди (Update Path): ${removedQueueIds.join(', ')}`);
            await cancelRemovedQueueEntries(originalQueueIds, wizardData.cart.items, 'patient-update');
          }

          onComplete?.({ success: true, message: 'Данные пациента обновлены' });
          onClose();
          return;
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
      // UX Audit Stage 3 (Wizard issue 5.1):
      // Заменён raw fetch() POST на createRegistrarCart() из api/patients.
      // createRegistrarCart бросает Error с .status, .message, .response при неудаче.
      let result;
      try {
        result = await createRegistrarCart(cartData);
      } catch (cartError) {
        // Обработка ошибок создания корзины
        let errorMessage = cartError.message || `Ошибка создания записи (${cartError.status || 'network'})`;
        const isPermissionError = cartError.status === 403;

        logger.error('❌ Ошибка создания корзины:', cartError.status, errorMessage);

        if (isPermissionError) {
          if (errorMessage.includes('Not enough permissions')) {
            errorMessage = 'У вас нет прав для создания записей. Необходима роль Регистратора или Администратора.';
          }
          toast.error(errorMessage, {
            duration: 5000,
            style: {
              backgroundColor: 'color-mix(in srgb, var(--mac-error), transparent 84%)',
              border: '1px solid color-mix(in srgb, var(--mac-error), transparent 72%)',
              color: 'var(--mac-text-primary)'
            }
          });
          // Закрываем мастер при ошибке прав доступа
          onClose();
        } else {
          toast.error(`Ошибка создания записи: ${errorMessage}`);
        }
        return; // ❌ НЕ закрываем мастер при других ошибках
      }

      logger.log('✅ Запись создана успешно на backend:', result);

      // Всегда завершаем после создания корзины (без онлайн оплаты в UI)
      // (QW-08: removed dead if(!editMode){localStorage.removeItem(...)} block)

      toast.success(editMode ? 'Запись обновлена!' : 'Запись создана успешно!');

      // ✅ НОВОЕ: Обработка удаленных записей очереди (для cart creation path)
      const currentQueueIds = new Set(
        wizardData.cart.items.
          map((item) => item.original_queue_id).
          filter((id) => id)
      );

      const removedQueueIds = Array.from(originalQueueIds).filter((id) => !currentQueueIds.has(id));

      if (removedQueueIds.length > 0) {
        logger.log(`🗑️ Найдены удаленные записи очереди (Cart Path): ${removedQueueIds.join(', ')}`);
        await cancelRemovedQueueEntries(originalQueueIds, wizardData.cart.items, 'cart-update');
      }

      onComplete?.(result);
      onClose();
    } catch (error) {
      logger.error('Ошибка завершения мастера:', error);
      toast.error(error.message || 'Произошла ошибка');
    } finally {
      setIsProcessing(false);
    }
  };
  handleCompleteRef.current = handleComplete;

  // Группировка элементов корзины по визитам
  const groupCartItemsByVisit = () => {
    const visits = {};

    // ✅ ИСПРАВЛЕНО: Фильтруем элементы корзины без service_id
    const validItems = wizardData.cart.items.filter((item) => {
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

    validItems.forEach((item) => {
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
        quantity: item.quantity,
        original_queue_id: item.original_queue_id || null,
        service_code: item.service_code || null,
        service_name: item.service_name || item.name || null,
        _source: item._source || null
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

    const service = servicesData.find((s) => s.id === serviceId);

    if (!service) {
      logger.warn(`⚠️ Услуга ${serviceId} не найдена в servicesData`);
      return 'general';
    }

    logger.log(`🔍 getDepartmentByService: serviceId=${serviceId}, queue_tag=${service.queue_tag}, category_code=${service.category_code}`);

    // 🎯 СПЕЦИАЛЬНАЯ ОБРАБОТКА ДЛЯ ЭКГ: отдельный кабинет!
    if (service.queue_tag === 'ecg') {
      logger.log('✅ ЭКГ обнаружено! Возвращаем department=\'echokg\'');
      return 'echokg'; // ЭКГ в отдельном кабинете (соответствует вкладке 'echokg')
    }

    // ✅ ИСПРАВЛЕННЫЙ МАППИНГ - соответствует вкладкам RegistrarPanel
    const mapping = {
      'K': 'cardiology', // Кардиология → вкладка cardio (БЕЗ ЭКГ!)
      'D': 'dermatology', // Дерматология → вкладка derma (только консультации)
      'S': 'dentistry', // Стоматология → вкладка dental
      'L': 'laboratory', // Лаборатория → вкладка lab
      'P': 'procedures', // Физиотерапия → вкладка procedures
      'C': 'procedures', // Косметология → вкладка procedures
      'D_PROC': 'procedures', // Дерматологические процедуры → вкладка procedures
      'O': 'procedures' // Прочие процедуры → вкладка procedures
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
      'specialists': 'cardiology', // Консультации специалистов (только если не 'D' или 'S') -> cardiology
      'laboratory': 'lab', // ✅ ИСПРАВЛЕНИЕ: Лаборатория -> lab (для соответствия вкладке)
      'procedures': 'procedures', // Процедуры -> procedures
      'other': 'general' // Прочее -> general
    };

    const result = normalizedMapping[normalizedCategoryCode] || mapping[service.category_code] || 'general';
    logger.log(`🎯 getDepartmentByService результат: serviceId=${serviceId}, category_code=${normalizedCategoryCode}, department=${result}`);
    return result;
  };

  // ===================== ДЕЙСТВИЯ ДИАЛОГА =====================

  const actions = [
  {
    label: 'Очистить форму',
    onClick: clearDraft,
    variant: 'secondary',
    icon: <Trash2 size={16} />,
    disabled: isProcessing
  },
  currentStep > STEP_PATIENT && {
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
  }].
  filter(Boolean);

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

  const wizardHeaderShellStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: '100%',
    gap: 'var(--mac-spacing-4)',
    padding: '10px 20px 12px',
    borderBottom: '1px solid var(--mac-border)',
    background: 'var(--mac-bg-primary)'
  };

  const wizardHeaderTitleStyle = {
    fontSize: 'var(--mac-font-size-xl)',
    fontWeight: 'var(--mac-font-weight-semibold)',
    color: 'var(--mac-text-primary)',
    margin: 0,
    letterSpacing: '-0.02em',
    lineHeight: 1.2
  };

  const wizardHeaderSubtitleStyle = {
    margin: '4px 0 0',
    fontSize: 'var(--mac-font-size-sm)',
    color: 'var(--mac-text-secondary)',
    lineHeight: 1.4
  };

  const wizardHeaderIconStyle = {
    width: '36px',
    height: '36px',
    borderRadius: 'var(--mac-radius-lg)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    background: 'var(--mac-bg-secondary)',
    color: 'var(--mac-primary)',
    border: '1px solid var(--mac-border)',
    boxShadow: 'var(--mac-shadow-sm)'
  };

  const wizardHeaderCloseStyle = {
    width: '32px',
    height: '32px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid var(--mac-border)',
    background: 'var(--mac-bg-secondary)',
    color: 'var(--mac-text-secondary)',
    borderRadius: '999px',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    boxShadow: 'var(--mac-shadow-sm)',
    flexShrink: 0
  };

  const wizardSegmentButtonBase = {
    minHeight: '34px',
    padding: '7px 14px',
    borderRadius: '999px',
    border: '1px solid var(--mac-border)',
    background: 'var(--mac-bg-secondary)',
    color: 'var(--mac-text-primary)',
    cursor: 'pointer',
    fontSize: 'var(--mac-font-size-sm)',
    fontWeight: 'var(--mac-font-weight-medium)',
    whiteSpace: 'nowrap',
    transition: 'all 0.2s ease',
    display: 'flex',
    alignItems: 'center',
    gap: 'var(--mac-spacing-2)',
    boxShadow: 'var(--mac-shadow-sm)'
  };

  // Кастомный заголовок для Шага 1
  // PR-24: show edit-mode banner when editing
  const editModeBanner = editMode ? (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '6px',
      padding: '4px 10px',
      borderRadius: 'var(--mac-radius-sm)',
      background: 'rgba(59, 130, 246, 0.12)',
      color: '#2563eb',
      fontSize: '12px',
      fontWeight: 600,
      marginBottom: '4px'
    }}>
      ✏️ Редактирование записи
      {initialData?.source_kind === 'online' || initialData?.source === 'online' ? (
        <span style={{
          padding: '1px 6px', borderRadius: '4px', fontSize: '10px',
          background: 'rgba(139, 92, 246, 0.15)', color: '#7c3aed'
        }}>QR</span>
      ) : (
        <span style={{
          padding: '1px 6px', borderRadius: '4px', fontSize: '10px',
          background: 'rgba(100, 116, 139, 0.15)', color: '#64748b'
        }}>Desk</span>
      )}
    </div>
  ) : null;

  const Step1Header =
  <div style={wizardHeaderShellStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-3)', minWidth: 0 }}>
        <div style={wizardHeaderIconStyle}>
          <Check size={18} />
        </div>
        <div style={{ minWidth: 0 }}>
          {editModeBanner}
          <h3 style={wizardHeaderTitleStyle}>
            {editMode ? 'Редактирование записи' : 'Регистрация пациента'}
          </h3>
          <p style={wizardHeaderSubtitleStyle}>
            Шаг 1 из 2 · данные пациента и карточка записи
          </p>
        </div>
      </div>

      <button
      type="button"
      onClick={onClose}
      title="Закрыть"
      aria-label="Закрыть"
      style={wizardHeaderCloseStyle}
      onMouseEnter={(e) => {
        e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)';
        e.currentTarget.style.borderColor = 'var(--mac-border-secondary)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
        e.currentTarget.style.borderColor = 'var(--mac-border)';
      }}>
        <X size={18} />
      </button>
    </div>;


  // Улучшенный заголовок для Шага 2
  const Step2Header =
  <div style={wizardHeaderShellStyle}>
      {/* 1. Поиск (Слева) */}
      <div style={{ flex: '0 0 300px', minWidth: 0 }}>
        <Input
        placeholder="Поиск услуги (название или код)..."
        value={serviceSearchQuery}
        onChange={(e) => setServiceSearchQuery(e.target.value)}
        icon={Search}
        clearable
        onClear={() => setServiceSearchQuery('')}
        autoFocus
        size="sm"
        style={{ height: '38px', fontSize: 'var(--mac-font-size-sm)' }} />

      </div>

      {/* 2. Категории (Центр) */}
      <div style={{
      flex: 1,
      display: 'flex',
      justifyContent: 'center',
      gap: 'var(--mac-spacing-2)',
      padding: '0 8px',
      flexWrap: 'wrap'
    }}>
        {categories.map((cat) =>
      <button
        key={cat.id}
        type="button"
        onClick={() => setActiveServiceCategory(cat.id)}
        style={{
          ...wizardSegmentButtonBase,
          borderColor: activeServiceCategory === cat.id ? 'var(--mac-accent)' : 'var(--mac-border)',
          background: activeServiceCategory === cat.id ?
          'color-mix(in srgb, var(--mac-accent), transparent 90%)' :
          'var(--mac-bg-secondary)',
          color: activeServiceCategory === cat.id ? 'var(--mac-primary)' : 'var(--mac-text-primary)',
          fontWeight: activeServiceCategory === cat.id ? '600' : '500',
          transform: activeServiceCategory === cat.id ? 'translateY(-1px)' : 'translateY(0)',
          boxShadow: activeServiceCategory === cat.id ? '0 6px 14px rgba(59, 130, 246, 0.08)' : 'var(--mac-shadow-sm)'
        }}
        onMouseEnter={(e) => {
          if (activeServiceCategory !== cat.id) {
            e.currentTarget.style.background = 'var(--mac-bg-tertiary)';
            e.currentTarget.style.transform = 'translateY(-1px)';
            e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
          }
        }}
        onMouseLeave={(e) => {
          if (activeServiceCategory !== cat.id) {
            e.currentTarget.style.background = 'var(--mac-bg-secondary)';
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
          }
        }}>

            <span style={{ fontSize: 'var(--mac-font-size-lg)', display: 'inline-flex', alignItems: 'center' }}>
            {cat.icon === 'stethoscope' ? <Stethoscope size={16} /> :
             cat.icon === 'flask' ? <FlaskConical size={16} /> :
             cat.icon === 'syringe' ? <Syringe size={16} /> :
             cat.icon === 'clipboard' ? <ClipboardList size={16} /> : null}
          </span>
            {cat.label}
          </button>
      )}
      </div>

      {/* 3. Действия (Справа) */}
      <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 'var(--mac-spacing-2)',
      flex: '0 0 auto'
    }}>
        {/* Кнопка обновления */}
        <button
        type="button"
        onClick={handleReloadServices}
        disabled={isReloadingServices}
        title="Обновить список услуг"
        aria-label={isReloadingServices ? 'Refreshing service list' : 'Refresh service list'}
        style={{
          width: '34px',
          height: '34px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: '1px solid var(--mac-border)',
          background: 'var(--mac-bg-secondary)',
          color: 'var(--mac-text-secondary)',
          borderRadius: '999px',
          cursor: isReloadingServices ? 'wait' : 'pointer',
          transition: 'all 0.2s',
          boxShadow: 'var(--mac-shadow-sm)'
        }}
        onMouseEnter={(e) => {
          if (!isReloadingServices) {
            e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
            e.currentTarget.style.borderColor = 'var(--mac-primary)';
            e.currentTarget.style.color = 'var(--mac-primary)';
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
          e.currentTarget.style.borderColor = 'var(--mac-border)';
          e.currentTarget.style.color = 'var(--mac-text-secondary)';
        }}>

          <RefreshCw size={16} className={isReloadingServices ? 'spin' : ''} />
        </button>

        {/* Кнопка закрытия */}
        <button
        type="button"
        onClick={onClose}
        title="Закрыть"
        aria-label="Close appointment wizard"
        style={{
          width: '34px',
          height: '34px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: '1px solid var(--mac-border)',
          background: 'var(--mac-bg-secondary)',
          color: 'var(--mac-text-secondary)',
          borderRadius: '999px',
          cursor: 'pointer',
          transition: 'all 0.2s',
          boxShadow: 'var(--mac-shadow-sm)'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = 'var(--mac-bg-tertiary)';
          e.currentTarget.style.borderColor = 'var(--mac-border-secondary)';
          e.currentTarget.style.color = 'var(--mac-text-primary)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'var(--mac-bg-secondary)';
          e.currentTarget.style.borderColor = 'var(--mac-border)';
          e.currentTarget.style.color = 'var(--mac-text-secondary)';
        }}>

          <X size={18} />
        </button>
      </div>
    </div>;


  // Проверка прав доступа перед рендерингом
  if (!hasRegistrarAccess) {
    return (
      <ModernDialog
        isOpen={isOpen}
        onClose={onClose}
        title="Доступ запрещен"
        maxWidth="40rem">

        <div style={{
          padding: 'var(--mac-spacing-6)',
          textAlign: 'center'
        }}>
          <AlertCircle
            size={48}
            style={{
              color: 'var(--mac-danger)',
              marginBottom: 'var(--mac-spacing-4)'
            }} />

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
            Для создания записей пациентов необходима роль Регистратора
            (включая Receptionist) или Администратора.
          </p>
          <Button
            onClick={onClose}
            variant="primary"
            style={{ marginTop: 'var(--mac-spacing-4)' }}>

            Закрыть
          </Button>
        </div>
      </ModernDialog>);

  }

  return (
    <>
      <ModernDialog
        isOpen={isOpen}
        onClose={onClose}
        customHeader={currentStep === STEP_PATIENT ? Step1Header : Step2Header}
        actions={actions}
        maxWidth="70rem"
        closeOnBackdrop={false}
        closeOnEscape={false}
        className="appointment-wizard-v2"
        dialogStyle={{
          backgroundColor: 'var(--mac-bg-primary)'
        }}>

        <div className="wizard-container-v2">
          {/* UX Audit Registrar #22: Progress indicator — визуальный progress bar.
              Текст «Шаг 1 из 2» уже есть в header, но визуальный bar даёт
              мгновенное понимание прогресса без чтения. */}
          <div style={{
            display: 'flex',
            gap: 'var(--mac-spacing-2)',
            marginBottom: 'var(--mac-spacing-3)',
            padding: '0 4px',
          }}>
            {Array.from({ length: totalSteps }, (_, i) => i + 1).map((step) => (
              <div
                key={step}
                style={{
                  flex: 1,
                  height: '4px',
                  borderRadius: 'var(--mac-radius-sm)',
                  backgroundColor: currentStep >= step
                    ? 'var(--mac-accent-blue, #007aff)'
                    : 'color-mix(in srgb, var(--mac-text-secondary, #8e8e93), transparent 70%)',
                  transition: 'background-color 200ms ease',
                }}
              />
            ))}
          </div>

          {/* Контент шагов */}
          <div className="wizard-content-v2">
            {currentStep === STEP_PATIENT &&
            <PatientStepV2
              data={wizardData.patient}
              errors={errors}
              suggestions={patientSuggestions}
              showSuggestions={showSuggestions}
              isSearching={isSearchingPatients}
              onSearch={handlePatientSearch}
              onSelectPatient={selectPatient}
              onUpdate={(field, value) =>
              setWizardData((prev) => ({
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
              setWizardData((prev) => ({
                ...prev,
                cart: { ...prev.cart, [field]: value }
              }))
              }
              phoneError={phoneError} />
            }

            {currentStep === STEP_CART &&
            <CartStepV2
              cart={wizardData.cart}
              services={filteredServices}
              doctorsData={doctorsData}
              showAllServices={showAllServices}
              onToggleAllServices={() => setShowAllServices(!showAllServices)}
              onAddToCart={addToCart}
              onRemoveFromCart={removeFromCart}
              onUpdateItem={updateCartItem}
              onUpdateCart={(field, value) =>
              setWizardData((prev) => ({
                ...prev,
                cart: { ...prev.cart, [field]: value }
              }))
              }
              calculateTotal={calculateTotal}
              servicesData={servicesData}
              errors={errors}
              onReloadServices={loadServices}
              getServiceName={getServiceName} // ✅ SSOT: Передаем функцию для получения названий услуг
              editMode={editMode}
              activeCategory={activeServiceCategory}
              setActiveCategory={setActiveServiceCategory}
              searchQuery={serviceSearchQuery}
              setSearchQuery={setServiceSearchQuery}
              isReloading={isReloadingServices}
              repeatEligibilityByItemId={repeatEligibilityByItemId}
              isRepeatEligibilityLoading={isRepeatEligibilityLoading}
              onApplyRepeatSuggestion={applyRepeatSuggestion}
              repeatSuggestionSummary={repeatSuggestionSummary} />

            }

          </div>
        </div>
      </ModernDialog>

      {/* UX Audit Registrar #2: ConfirmDialog (useConfirm hook). */}
      {confirmDialog}

      {/* Диалоги онлайн оплаты удалены из UI */}
    </>);

};

export default AppointmentWizardV2;

AppointmentWizardV2.propTypes = {
  isOpen: PropTypes.bool,
  onClose: PropTypes.func,
  onComplete: PropTypes.func,
  isProcessing: PropTypes.bool,
  setIsProcessing: PropTypes.func,
  activeTab: PropTypes.any,
  editMode: PropTypes.bool,
  initialData: PropTypes.any
};

// UX Audit Stage 3 (Wizard issue 5.2):
// PatientStepV2 и CartStepV2 вынесены в отдельные файлы.
export { PatientStepV2, CartStepV2 };
