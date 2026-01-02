import { useState, useEffect, useCallback, useRef, useMemo, memo, startTransition } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ToastContainer, toast } from 'react-toastify';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import AppointmentContextMenu from '../components/tables/AppointmentContextMenu';
import ModernTabs from '../components/navigation/ModernTabs';
import { Button, Card, CardHeader, CardContent, Badge, Icon, Input } from '../components/ui/macos';
import { AnimatedTransition, AnimatedLoader } from '../components/ui';
import { useBreakpoint } from '../hooks/useEnhancedMediaQuery';
import { useTheme } from '../contexts/ThemeContext';
import '../components/ui/animations.css';
import '../styles/responsive.css';
import '../styles/animations.css';
import '../styles/dark-theme-visibility-fix.css';
import logger from '../utils/logger';

const API_BASE = import.meta?.env?.VITE_API_BASE_URL || 'http://localhost:8000';

// Современные диалоги
import PaymentDialog from '../components/dialogs/PaymentDialog';
import CancelDialog from '../components/dialogs/CancelDialog';
import PrintDialog from '../components/dialogs/PrintDialog';

// Современный мастер
// ✅ Используется только новый мастер (V2)
import AppointmentWizardV2 from '../components/wizard/AppointmentWizardV2';
import PaymentManager from '../components/payment/PaymentManager';

// Современная очередь
import ModernQueueManager from '../components/queue/ModernQueueManager';

// Современная статистика
import ModernStatistics from '../components/statistics/ModernStatistics';

// Модальное окно редактирования пациента
// ✨ ЗАКОММЕНТИРОВАНО: Теперь используется AppointmentWizardV2 для редактирования
// import EditPatientModal from '../components/common/EditPatientModal';

// Утилиты для работы с датами
import { getLocalDateString, getYesterdayDateString } from '../utils/dateUtils';

// ⭐ SSOT: Centralized service code resolver
import { SPECIALTY_TO_CODE, toServiceCode as ssotToServiceCode } from '../utils/serviceCodeResolver';

// API client
import { api } from '../api/client';
// ⭐ BATCH API: Для атомарных операций с записями пациента (см. BATCH_UPDATE_ARCHITECTURE.md)
import { cancelAllPatientEntries, formatDateForAPI } from '../api/registrarBatch';

// ✅ Форс-мажор модальное окно
import ForceMajeureModal from '../components/registrar/ForceMajeureModal';

const RegistrarPanel = () => {
  // Рендер компонента (debug отключен)
  // Адаптивные хуки
  const { isMobile, isTablet } = useBreakpoint();

  // Основные состояния
  const [activeTab, setActiveTab] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const searchQuery = useMemo(() => (searchParams.get('q') || '').toLowerCase(), [searchParams]);
  const statusFilter = useMemo(() => searchParams.get('status'), [searchParams]);
  const todayStr = getLocalDateString();

  // ✅ ДИНАМИЧЕСКИЕ ОТДЕЛЕНИЯ: состояние для хранения отделений из БД
  const [dynamicDepartments, setDynamicDepartments] = useState([]);

  // ⭐ SSOT: Queue profiles loaded from API (via ModernTabs)
  // Used for filtering entries by queue_tags instead of hardcoded mapping
  const [queueProfiles, setQueueProfiles] = useState([]);

  // Состояния для печати
  const [printDialog, setPrintDialog] = useState({ open: false, type: '', data: null });
  const [printData, setPrintData] = useState(null);
  const [cancelDialog, setCancelDialog] = useState({ open: false, row: null, reason: '' });
  const [paymentDialog, setPaymentDialog] = useState({ open: false, row: null, paid: false, source: null });
  // ✅ State for rescheduling
  const [rescheduleData, setRescheduleData] = useState(null);

  // ✅ State for Force Majeure modal
  const [forceMajeureModal, setForceMajeureModal] = useState({ open: false, specialistId: null, specialistName: '' });

  const [contextMenu, setContextMenu] = useState({ open: false, row: null, position: { x: 0, y: 0 } });

  // Состояния для пагинации
  const [paginationInfo, setPaginationInfo] = useState({ total: 0, hasMore: false, loadingMore: false });
  // Демо-данные вынесены в константу
  const demoAppointments = useMemo(() => ([
    {
      id: 1,
      patient_fio: 'Иванов Иван Иванович',
      patient_birth_year: 1985,
      patient_phone: '+998 (90) 123-45-67',
      address: 'ул. Навои, д. 15, кв. 23',
      services: ['Консультация кардиолога', 'ЭКГ'],
      visit_type: 'paid',
      payment_type: 'card',
      payment_status: 'paid',
      cost: 50000,
      status: 'confirmed',
      isEmpty: false,
      department: 'cardiology',
      doctor_specialty: 'cardiology',
      date: todayStr,
      appointment_date: todayStr,
      record_type: 'appointment', // Добавляем тип записи для демо-данных
      // Добавляем номера очередей для демонстрации
      queue_numbers: [
        {
          queue_tag: 'cardiology_common',
          queue_name: 'Кардиолог',
          number: 1,
          status: 'waiting',
          source: 'online',
          created_at: new Date().toISOString()
        }
      ],
      confirmation_status: 'confirmed',
      confirmed_at: new Date().toISOString(),
      confirmed_by: 'telegram_123456'
    },
    // Добавляем записи для того же пациента в разных отделениях (для тестирования агрегации)
    {
      id: 2,
      patient_fio: 'Иванов Иван Иванович', // Тот же пациент
      patient_birth_year: 1985,
      patient_phone: '+998 (90) 123-45-67',
      address: 'ул. Навои, д. 15, кв. 23',
      services: ['Консультация дерматолога', 'Дерматоскопия'], // Другие услуги
      visit_type: 'paid',
      payment_type: 'card',
      payment_status: 'paid',
      cost: 45000,
      status: 'confirmed',
      isEmpty: false,
      department: 'dermatology', // Другое отделение
      doctor_specialty: 'dermatology',
      date: todayStr,
      record_type: 'appointment', // Добавляем тип записи для демо-данных
      appointment_date: todayStr,
      queue_numbers: [
        {
          queue_tag: 'dermatology',
          queue_name: 'Дерматолог',
          number: 1,
          status: 'waiting',
          source: 'online',
          created_at: new Date().toISOString()
        }
      ],
      confirmation_status: 'confirmed',
      confirmed_at: new Date().toISOString(),
      confirmed_by: 'telegram_123456'
    },
    {
      id: 3,
      patient_fio: 'Иванов Иван Иванович', // Тот же пациент
      patient_birth_year: 1985,
      patient_phone: '+998 (90) 123-45-67',
      address: 'ул. Навои, д. 15, кв. 23',
      services: ['Консультация стоматолога'], // Третья услуга
      visit_type: 'paid',
      payment_type: 'cash',
      payment_status: 'paid',
      cost: 30000,
      status: 'confirmed',
      isEmpty: false,
      department: 'stomatology', // Третье отделение
      doctor_specialty: 'stomatology',
      date: todayStr,
      record_type: 'appointment', // Добавляем тип записи для демо-данных
      appointment_date: todayStr,
      queue_numbers: [
        {
          queue_tag: 'stomatology',
          queue_name: 'Стоматолог',
          number: 1,
          status: 'waiting',
          source: 'online',
          created_at: new Date().toISOString()
        }
      ],
      confirmation_status: 'confirmed',
      confirmed_at: new Date().toISOString(),
      confirmed_by: 'telegram_123456'
    },
    {
      id: 2,
      patient_fio: 'Петрова Анна Сергеевна',
      patient_birth_year: 1990,
      patient_phone: '+998 (91) 234-56-78',
      address: 'пр. Амира Темура, д. 42',
      services: ['ЭКГ', 'Холтер'],
      visit_type: 'repeat',
      payment_type: 'cash',
      payment_status: 'pending',
      cost: 30000,
      status: 'queued',
      isEmpty: false,
      department: 'cardiology',
      doctor_specialty: 'cardiology',
      date: todayStr,
      record_type: 'appointment', // Добавляем тип записи для демо-данных
      appointment_date: todayStr,
      // Добавляем номера очередей
      queue_numbers: [
        {
          queue_tag: 'cardiology_common',
          queue_name: 'Кардиолог',
          number: 2,
          status: 'waiting',
          source: 'confirmation',
          created_at: new Date().toISOString()
        }
      ],
      confirmation_status: 'confirmed',
      confirmed_at: new Date().toISOString(),
      confirmed_by: 'registrar_1'
    },
    {
      id: 3,
      patient_fio: 'Сидоров Петр Александрович',
      patient_birth_year: 1975,
      patient_phone: '+998 (93) 345-67-89',
      address: 'ул. Шота Руставели, д. 8, кв. 45',
      services: ['Консультация дерматолога'],
      visit_type: 'paid',
      payment_type: 'card',
      payment_status: 'paid',
      cost: 45000,
      status: 'confirmed',
      isEmpty: false,
      department: 'dermatology',
      doctor_specialty: 'dermatology',
      date: todayStr,
      record_type: 'appointment', // Добавляем тип записи для демо-данных
      appointment_date: todayStr,
      queue_numbers: [
        {
          queue_tag: 'dermatology',
          queue_name: 'Дерматолог',
          number: 1,
          status: 'waiting',
          source: 'online',
          created_at: new Date().toISOString()
        }
      ],
      confirmation_status: 'confirmed',
      confirmed_at: new Date().toISOString(),
      confirmed_by: 'telegram_789012'
    },
    {
      id: 4,
      patient_fio: 'Козлова Мария Владимировна',
      patient_birth_year: 1988,
      patient_phone: '+998 (94) 456-78-90',
      address: 'ул. Бабура, д. 25',
      services: ['Лечение кариеса'],
      visit_type: 'paid',
      payment_type: 'cash',
      payment_status: 'pending',
      cost: 60000,
      status: 'queued',
      isEmpty: false,
      department: 'stomatology',
      doctor_specialty: 'stomatology',
      date: todayStr,
      record_type: 'appointment', // Добавляем тип записи для демо-данных
      appointment_date: todayStr,
      queue_numbers: [
        {
          queue_tag: 'stomatology',
          queue_name: 'Стоматолог',
          number: 1,
          status: 'waiting',
          source: 'desk',
          created_at: new Date().toISOString()
        }
      ],
      confirmation_status: 'none',
      confirmed_at: null,
      confirmed_by: null
    },
    {
      id: 5,
      patient_fio: 'Морозов Алексей Игоревич',
      patient_birth_year: 1992,
      patient_phone: '+998 (95) 567-89-01',
      address: 'ул. Мирзо Улугбека, д. 67, кв. 12',
      services: ['Общий анализ крови', 'Биохимия'],
      visit_type: 'paid',
      payment_type: 'card',
      payment_status: 'paid',
      cost: 25000,
      status: 'confirmed',
      isEmpty: false,
      department: 'laboratory',
      doctor_specialty: 'laboratory',
      date: todayStr,
      record_type: 'appointment', // Добавляем тип записи для демо-данных
      appointment_date: todayStr,
      queue_numbers: [
        {
          queue_tag: 'lab',
          queue_name: 'Лаборатория',
          number: 1,
          status: 'waiting',
          source: 'online',
          created_at: new Date().toISOString()
        }
      ],
      confirmation_status: 'confirmed',
      confirmed_at: new Date().toISOString(),
      confirmed_by: 'telegram_345678'
    },
    {
      id: 6,
      patient_fio: 'Волкова Елена Сергеевна',
      patient_birth_year: 1983,
      patient_phone: '+998 (97) 678-90-12',
      address: 'ул. Алишера Навои, д. 134',
      services: ['Капельница', 'Инъекция'],
      visit_type: 'free',
      payment_type: 'cash',
      payment_status: 'paid',
      cost: 35000,
      status: 'queued',
      isEmpty: false,
      department: 'procedures',
      doctor_specialty: 'procedures',
      date: todayStr,
      record_type: 'appointment', // Добавляем тип записи для демо-данных
      appointment_date: todayStr,
      queue_numbers: [
        {
          queue_tag: 'procedures',
          queue_name: 'Процедуры',
          number: 1,
          status: 'waiting',
          source: 'desk',
          created_at: new Date().toISOString()
        }
      ],
      confirmation_status: 'none',
      confirmed_at: null,
      confirmed_by: null
    }
  ]), [todayStr]);

  // Состояния для управления данными
  const [appointments, setAppointments] = useState([]);
  // ⭐ SSOT FIX: Сырые данные (flat list) до агрегации — для Tooltip
  const [rawEntries, setRawEntries] = useState([]);
  const [dataSource, setDataSource] = useState('loading'); // 'loading' | 'api' | 'demo' | 'error'
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [appointmentsSelected, setAppointmentsSelected] = useState(new Set());
  const appointmentsCount = appointments.length;
  // ✅ Используется только новый мастер (V2)
  const [showWizard, setShowWizard] = useState(false);
  const [wizardEditMode, setWizardEditMode] = useState(false);      // ✨ НОВОЕ: Режим редактирования
  const [wizardInitialData, setWizardInitialData] = useState(null); // ✨ НОВОЕ: Данные для редактирования
  const [showPaymentManager, setShowPaymentManager] = useState(false); // Для модуля оплаты
  const [isProcessing, setIsProcessing] = useState(false); // Состояние обработки


  // Отладка состояния мастера удалена - используется AppointmentWizard

  // Отладка состояния загрузки
  useEffect(() => {
    // logger.info('⏳ appointmentsLoading changed:', appointmentsLoading);
  }, [appointmentsLoading]);

  // Отладка изменений appointments
  useEffect(() => {
    // logger.info('📋 appointments changed, count:', appointments.length);
    // if (appointments.length > 0) {
    //   logger.info('📋 Первая запись в состоянии:', appointments[0]);
    // }

    // Тестируем агрегацию пациентов при изменении данных (debug отключен)
    /*if (appointments.length > 0) {
      setTimeout(() => {
        logger.info('🧪 Тестирование агрегации пациентов:');
        logger.info('Исходные записи:', appointments.length);

        // Простая функция агрегации для тестирования
        const patientGroups = {};
        appointments.forEach(appointment => {
          const patientKey = appointment.patient_fio;
          if (!patientGroups[patientKey]) {
            patientGroups[patientKey] = {
              patient_fio: appointment.patient_fio,
              services: [],
              departments: new Set(),
              cost: 0 // Общая стоимость
            };
          }

          // Суммируем стоимость
          if (appointment.cost) {
            patientGroups[patientKey].cost += appointment.cost;
          }

          if (appointment.services && Array.isArray(appointment.services)) {
            appointment.services.forEach(service => {
              if (!patientGroups[patientKey].services.includes(service)) {
                patientGroups[patientKey].services.push(service);
              }
            });
          }
          if (appointment.department) {
            patientGroups[patientKey].departments.add(appointment.department);
          }
        });

        const aggregated = Object.values(patientGroups);
        logger.info('После агрегации:', aggregated.length);

        // Находим первого пациента для тестирования
        const firstPatient = aggregated[0];
        if (firstPatient) {
          logger.info('Первый пациент после агрегации:', firstPatient.patient_fio);
          logger.info('Количество услуг:', firstPatient.services.length);
          logger.info('Услуги:', firstPatient.services);
          logger.info('Отделения:', Array.from(firstPatient.departments));
          logger.info('Общая стоимость:', firstPatient.cost);
        }
      }, 100);
    }*/
  }, [appointments]);

  // Убираем дублирование - filteredAppointments уже определена ниже в коде
  const [showSlotsModal, setShowSlotsModal] = useState(false);
  const [showQRModal, setShowQRModal] = useState(false);
  const autoRefresh = true;

  // Новые состояния для интеграции с админ панелью
  const [doctors, setDoctors] = useState([]);
  const [services, setServices] = useState({});
  const [selectedDoctor, setSelectedDoctor] = useState(null);
  const [showCalendar, setShowCalendar] = useState(false);
  const [historyDate, setHistoryDate] = useState(getLocalDateString());
  const [tempDateInput, setTempDateInput] = useState(getLocalDateString());

  const language = useMemo(() => localStorage.getItem('ui_lang') || 'ru', []);

  // Инициализация selectedDoctor первым доступным врачом
  useEffect(() => {
    if (!selectedDoctor && doctors.length > 0) {
      setSelectedDoctor(doctors[0]);
    }
  }, [doctors, selectedDoctor]);

  // Переводы
  const translations = {
    ru: {
      // Основные
      welcome: 'Добро пожаловать',
      start_work: 'Начать работу',
      quick_start: 'Быстрый старт',
      loading: 'Загрузка',
      error: 'Ошибка',
      success: 'Успешно',
      warning: 'Предупреждение',

      // Вкладки
      tabs_welcome: 'Главная',
      tabs_appointments: 'Все записи',
      tabs_cardio: 'Кардиолог',
      tabs_echokg: 'ЭКГ',
      tabs_derma: 'Дерматолог',
      tabs_dental: 'Стоматолог',
      tabs_lab: 'Лаборатория',
      tabs_procedures: 'Процедуры',
      tabs_queue: 'Онлайн-очередь',

      // Действия
      new_appointment: 'Новая запись',
      export_csv: 'Экспорт CSV',
      today: 'Сегодня',
      reset: 'Сбросить',
      confirm: 'Подтвердить',
      cancel: 'Отменить',
      no_show: 'Неявка',
      reason: 'Причина',
      bulk_actions: 'Массовые действия',
      search: 'Поиск',
      filter: 'Фильтр',
      clear_filter: 'Очистить фильтр',

      // Мастер
      patient: 'Пациент',
      details: 'Детали',
      payment: 'Оплата',
      next: 'Далее',
      back: 'Назад',
      save: 'Сохранить',
      close: 'Закрыть',
      add_to_queue: 'Добавить в очередь',
      priority: 'Приоритет',
      available_slots: 'Доступные слоты',
      tomorrow: 'Завтра',
      select_date: 'Выбрать дату',
      online_payment: 'Онлайн оплата',

      // Поля формы
      full_name: 'ФИО',
      birth_date: 'Дата рождения',
      phone: 'Телефон',
      address: 'Адрес',
      services: 'Услуги',
      doctor: 'Врач',
      appointment_type: 'Тип обращения',
      payment_method: 'Способ оплаты',
      amount: 'Сумма',

      // Статусы
      status_scheduled: 'Запланирован',
      status_confirmed: 'Подтвержден',
      status_queued: 'В очереди',
      status_in_cabinet: 'В кабинете',
      status_done: 'Завершен',
      status_cancelled: 'Отменен',
      status_no_show: 'Неявка',
      status_paid_pending: 'Ожидает оплаты',
      status_paid: 'Оплачен',

      // Статистика
      total_patients: 'Всего пациентов',
      today_appointments: 'Записей сегодня',
      pending_payments: 'Ожидают оплаты',
      active_queues: 'Активные очереди',
      empty_table: 'Нет данных для отображения',

      // Сообщения
      appointment_created: 'Запись создана успешно',
      appointment_cancelled: 'Запись отменена',
      payment_successful: 'Оплата прошла успешно',
      print_ticket: 'Печать талона',
      auto_refresh: 'Автообновление',
      data_source_demo: 'Показаны демо-данные',
      data_source_api: 'Данные загружены с сервера'
    },
    uz: {
      // Основные
      welcome: 'Xush kelibsiz',
      start_work: 'Ishni boshlash',
      quick_start: 'Tezkor start',
      loading: 'Yuklanmoqda',
      error: 'Xatolik',
      success: 'Muvaffaqiyatli',
      warning: 'Ogohlantirish',

      // Вкладки
      tabs_welcome: 'Asosiy',
      tabs_appointments: 'yozilganlar',
      tabs_cardio: 'Kardiolog',
      tabs_echokg: 'EKG',
      tabs_derma: 'Dermatolog',
      tabs_dental: 'Stomatolog',
      tabs_lab: 'Laboratoriya',
      tabs_procedures: 'muolaja',
      tabs_queue: 'navbat',

      // Действия
      new_appointment: 'Yangi yozuv',
      export_csv: 'CSV eksport',
      today: 'Bugun',
      reset: 'Tozalash',
      confirm: 'Tasdiqlash',
      cancel: 'Bekor qilish',
      no_show: 'Kelmaslik',
      reason: 'Sabab',
      bulk_actions: 'Ommaviy amallar',
      search: 'Qidirish',
      filter: 'Filter',
      clear_filter: 'Filterni tozalash',

      // Мастер
      patient: 'Bemor',
      details: 'Tafsilotlar',
      payment: 'To\'lov',
      next: 'Keyingi',
      back: 'Orqaga',
      save: 'Saqlash',
      close: 'Yopish',
      add_to_queue: 'Navbatga qo\'shish',
      priority: 'Ustuvorlik',
      available_slots: 'Mavjud vaqtlar',
      tomorrow: 'Ertaga',
      select_date: 'Sanani tanlash',
      online_payment: 'Onlayn to\'lov',

      // Поля формы
      full_name: 'F.I.Sh',
      birth_date: 'Tug\'ilgan sana',
      phone: 'Telefon',
      address: 'Manzil',
      services: 'Xizmatlar',
      doctor: 'Shifokor',
      appointment_type: 'Murojaat turi',
      payment_method: 'To\'lov usuli',
      amount: 'Summa',

      // Статусы
      status_scheduled: 'Rejalashtirilgan',
      status_confirmed: 'Tasdiqlangan',
      status_queued: 'Navbatda',
      status_in_cabinet: 'Kabinetda',
      status_done: 'Tugallangan',
      status_cancelled: 'Bekor qilingan',
      status_no_show: 'Kelmagan',
      status_paid_pending: 'To\'lovni kutmoqda',
      status_paid: 'To\'langan',

      // Статистика
      total_patients: 'Jami bemorlar',
      today_appointments: 'Bugungi yozuvlar',
      pending_payments: 'To\'lovni kutmoqda',
      active_queues: 'Faol navbatlar',
      empty_table: 'Ma\'lumot yo\'q',

      // Сообщения
      appointment_created: 'Yozuv muvaffaqiyatli yaratildi',
      appointment_cancelled: 'Yozuv bekor qilindi',
      payment_successful: 'To\'lov muvaffaqiyatli o\'tdi',
      print_ticket: 'Talon chop etish',
      auto_refresh: 'Avtomatik yangilash',
      data_source_demo: 'Demo ma\'lumotlar ko\'rsatilgan',
      data_source_api: 'Ma\'lumotlar serverdan yuklandi'
    }
  };
  const t = (key) => (translations[language] && translations[language][key]) || translations.ru[key] || key;

  // Используем централизованную тему
  const {
    theme,
    isDark,
    getSpacing,
    getFontSize,
    getColor
  } = useTheme();

  // Адаптивные цвета из централизованной системы темизации
  const cardBg = isDark ? 'var(--color-background-primary)' : 'var(--color-background-secondary)';
  const textColor = isDark ? 'var(--color-text-primary)' : 'var(--color-text-primary)';
  const borderColor = isDark ? 'var(--color-border-medium)' : 'var(--color-border-light)';
  const accentColor = 'var(--color-primary-500)';

  // Используем централизованную типографику и отступы
  // Используем CSS переменные вместо getSpacing и getColor

  const pageStyle = {
    padding: '0',
    maxWidth: 'none',
    margin: '0',
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
    fontSize: isMobile ? 'var(--mac-font-size-sm)' : isTablet ? 'var(--mac-font-size-base)' : 'var(--mac-font-size-lg)',
    fontWeight: 400,
    lineHeight: 1.5,
    background: 'var(--mac-gradient-window)',
    color: 'var(--mac-text-primary)',
    minHeight: '100vh',
    position: 'relative',
    transition: 'background var(--mac-duration-normal) var(--mac-ease)'
  };

  // Контейнер таблицы, визуально "сливается" с вкладками
  const tableContainerStyle = {
    background: theme === 'light'
      ? 'rgba(255, 255, 255, 0.98)'
      : 'rgba(15, 23, 42, 0.8)',
    backdropFilter: 'blur(20px)',
    color: textColor,
    borderLeft: `1px solid ${theme === 'light' ? 'rgba(0, 0, 0, 0.15)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderRight: `1px solid ${theme === 'light' ? 'rgba(0, 0, 0, 0.15)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderBottom: `1px solid ${theme === 'light' ? 'rgba(0, 0, 0, 0.15)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderTop: `1px solid ${theme === 'light' ? 'rgba(0, 0, 0, 0.08)' : 'rgba(255, 255, 255, 0.05)'}`,
    borderRadius: '0 0 20px 20px',
    margin: '0 20px 20px 20px',
    boxShadow: theme === 'light'
      ? '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
      : '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
    overflow: 'hidden'
  };

  // Содержимое контейнера таблицы без верхнего внутреннего отступа
  const tableContentStyle = {
    padding: '0',
    color: textColor
  };

  const buttonStyle = {
    padding: '0.5rem 1.5rem',
    background: 'linear-gradient(135deg, var(--color-primary-500) 0%, var(--color-primary-600) 100%)',
    color: 'white',
    border: 'none',
    borderRadius: '12px',
    cursor: 'pointer',
    marginRight: '0.5rem',
    fontSize: '14px',
    fontWeight: '600',
    lineHeight: '1.25',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)',
    position: 'relative',
    overflow: 'hidden',
    textShadow: '0 1px 2px rgba(0, 0, 0, 0.5)'
  };

  const buttonSecondaryStyle = {
    padding: `${'0.5rem'} ${'1.5rem'}`,
    background: theme === 'light' ? 'white' : 'var(--color-background-secondary)',
    color: textColor,
    border: `1px solid ${borderColor}`,
    borderRadius: '12px',
    cursor: 'pointer',
    marginRight: '0.5rem',
    fontSize: '14px',
    fontWeight: '600',
    lineHeight: '1.25',
    transition: 'all 0.2s ease',
    boxShadow: 'none',
  };


  // Загрузка данных из админ панели
  const loadIntegratedData = useCallback(async () => {
    logger.info('🔧 loadIntegratedData called at:', new Date().toISOString());
    try {
      // УБИРАЕМ setAppointmentsLoading(true) - это не должно влиять на загрузку записей
      // setAppointmentsLoading(true);

      // Сначала устанавливаем fallback данные для врачей и услуг
      // logger.info('Setting fallback doctors and services data');
      setDoctors([
        { id: 1, specialty: 'cardiology', user: { full_name: 'Доктор Кардиолог' }, cabinet: '101', price_default: 50000 },
        { id: 2, specialty: 'dermatology', user: { full_name: 'Доктор Дерматолог' }, cabinet: '102', price_default: 45000 },
        { id: 3, specialty: 'stomatology', user: { full_name: 'Доктор Стоматолог' }, cabinet: '103', price_default: 60000 }
      ]);

      setServices({
        laboratory: [
          { id: 1, name: 'Общий анализ крови', price: 15000, specialty: 'laboratory', group: 'laboratory' },
          { id: 2, name: 'Биохимический анализ крови', price: 25000, specialty: 'laboratory', group: 'laboratory' },
          { id: 3, name: 'Анализ мочи', price: 10000, specialty: 'laboratory', group: 'laboratory' },
          { id: 4, name: 'Анализ кала', price: 12000, specialty: 'laboratory', group: 'laboratory' }
        ],
        cardiology: [
          { id: 13, name: 'Консультация кардиолога', price: 50000, specialty: 'cardiology', group: 'cardiology' },
          { id: 14, name: 'ЭКГ', price: 20000, specialty: 'cardiology', group: 'cardiology' },
          { id: 15, name: 'ЭхоКГ', price: 35000, specialty: 'cardiology', group: 'cardiology' },
          { id: 16, name: 'ЭКГ с консультацией кардиолога', price: 70000, specialty: 'cardiology', group: 'cardiology' },
          { id: 17, name: 'ЭхоКГ с консультацией кардиолога', price: 85000, specialty: 'cardiology', group: 'cardiology' }
        ],
        dermatology: [
          { id: 5, name: 'Консультация дерматолога-косметолога', price: 40000, specialty: 'dermatology', group: 'dermatology' },
          { id: 6, name: 'Дерматоскопия', price: 30000, specialty: 'dermatology', group: 'dermatology' },
          { id: 7, name: 'УЗИ кожи', price: 20000, specialty: 'dermatology', group: 'dermatology' },
          { id: 8, name: 'Лечение акне', price: 60000, specialty: 'dermatology', group: 'dermatology' }
        ],
        stomatology: [
          { id: 18, name: 'Консультация стоматолога', price: 30000, specialty: 'stomatology', group: 'stomatology' },
          { id: 19, name: 'Лечение кариеса', price: 80000, specialty: 'stomatology', group: 'stomatology' },
          { id: 20, name: 'Удаление зуба', price: 50000, specialty: 'stomatology', group: 'stomatology' },
          { id: 21, name: 'Чистка зубов', price: 40000, specialty: 'stomatology', group: 'stomatology' }
        ],
        cosmetology: [
          { id: 9, name: 'Чистка лица', price: 35000, specialty: 'cosmetology', group: 'cosmetology' },
          { id: 10, name: 'Пилинг лица', price: 40000, specialty: 'cosmetology', group: 'cosmetology' },
          { id: 11, name: 'Массаж лица', price: 25000, specialty: 'cosmetology', group: 'cosmetology' },
          { id: 12, name: 'Мезотерапия', price: 120000, specialty: 'cosmetology', group: 'cosmetology' }
        ],
        procedures: [
          { id: 22, name: 'Физиотерапия', price: 25000, specialty: 'procedures', group: 'procedures' },
          { id: 23, name: 'Массаж', price: 30000, specialty: 'procedures', group: 'procedures' },
          { id: 24, name: 'Ингаляция', price: 15000, specialty: 'procedures', group: 'procedures' }
        ]
      });

      // Загружаем врачей, услуги и настройки очередей из админ панели
      try {
        const token = localStorage.getItem('auth_token');
        logger.info('🔍 RegistrarPanel: token from localStorage:', token ? `${token.substring(0, 30)}...` : 'null');

        // Загружаем данные последовательно, чтобы избежать проблем с Promise.all
        let doctorsRes, servicesRes, queueRes;

        try {
          logger.info('🔍 Загружаем врачей с токеном:', token ? `${token.substring(0, 30)}...` : 'null');
          doctorsRes = await api.get('/registrar/doctors');
          logger.info('📊 Ответ врачей: OK');
        } catch (error) {
          logger.error('❌ Ошибка загрузки врачей:', error.message);
          doctorsRes = { ok: false };
        }

        try {
          logger.info('🔍 Загружаем услуги...');
          servicesRes = await api.get('/registrar/services');
          logger.info('📊 Ответ услуг: OK');
        } catch (error) {
          logger.error('❌ Ошибка загрузки услуг:', error.message);
          servicesRes = { ok: false };
        }

        try {
          logger.info('🔍 Загружаем настройки очереди...');
          queueRes = await api.get('/registrar/queue-settings');
          logger.info('📊 Ответ настроек очереди: OK');
        } catch (error) {
          logger.error('❌ Ошибка загрузки настроек очереди:', error.message);
          queueRes = { ok: false };
        }

        // Загружаем отделения
        let departmentsRes;
        try {
          logger.info('🔍 Загружаем отделения...');
          departmentsRes = await api.get('/registrar/departments?active_only=true');
          logger.info('📊 Ответ отделений: OK', departmentsRes.data);
        } catch (error) {
          logger.error('❌ Ошибка загрузки отделений:', error);
          departmentsRes = { success: false };
        }

        logger.info('🔄 Обрабатываем ответы API...');

        // Проверяем, что все ответы успешны
        const allSuccess = doctorsRes && doctorsRes.data && servicesRes && servicesRes.data && queueRes && queueRes.data;
        logger.info('📊 Статус ответов:', {
          doctors: (doctorsRes && doctorsRes.data) ? 'OK' : 'ERROR',
          services: (servicesRes && servicesRes.data) ? 'OK' : 'ERROR',
          queueSettings: (queueRes && queueRes.data) ? 'OK' : 'ERROR',
          allSuccess
        });

        if (!allSuccess) {
          logger.warn('⚠️ Некоторые API недоступны, но продолжаем работу');
        }

        if (doctorsRes && doctorsRes.data) {
          try {
            const doctorsData = doctorsRes.data;
            const apiDoctors = doctorsData.doctors || [];
            logger.info('✅ Данные врачей получены:', apiDoctors.length, 'врачей');
            // Если API вернул данные — используем их
            if (apiDoctors.length > 0) {
              setDoctors(apiDoctors);
              logger.info('✅ Врачи обновлены из API');
            }
          } catch (error) {
            logger.warn('Ошибка обработки данных врачей:', error.message);
          }
        } else {
          logger.warn('❌ API врачей недоступен, используем демо-данные');
        }

        // Обработка отделений
        if (departmentsRes && departmentsRes.data) {
          const depts = departmentsRes.data.data || [];
          if (Array.isArray(depts) && depts.length > 0) {
            setDynamicDepartments(depts);
            logger.info('✅ Отделения обновлены из API:', depts.length);
          }
        }

        if (servicesRes && servicesRes.data) {
          try {
            const servicesData = servicesRes.data;
            const apiServices = servicesData.services_by_group || {};
            logger.info('✅ Данные услуг получены:', Object.keys(apiServices));
            // Если API вернул данные — используем их
            if (Object.keys(apiServices).length > 0) {
              setServices(apiServices);
              logger.info('✅ Услуги обновлены из API');
            }
          } catch (error) {
            logger.warn('Ошибка обработки данных услуг:', error.message);
          }
        } else {
          logger.warn('❌ API услуг недоступен, используем демо-данные');
        }

        if (queueRes && queueRes.data) {
          try {
            logger.info('✅ Настройки очереди обновлены из API');
          } catch (error) {
            logger.warn('Ошибка обработки данных настроек очереди:', error.message);
          }
        } else {
          logger.warn('❌ API настроек очереди недоступен, используем демо-данные');
        }

        logger.info('🎯 Загрузка интегрированных данных завершена');
      } catch (fetchError) {
        // Backend недоступен - используем демо-данные (уже установлены выше)
        logger.warn('Backend недоступен для загрузки интегрированных данных, используем демо-режим:', fetchError.message);
      }

    } catch (error) {
      logger.error('Ошибка загрузки интегрированных данных:', error);
      toast.error('Ошибка загрузки данных из админ панели');
    } finally {
      // УБИРАЕМ setAppointmentsLoading(false) - это не должно влиять на загрузку записей
      // setAppointmentsLoading(false);
    }
  }, []);

  // Функция для получения данных пациента по ID
  const fetchPatientData = useCallback(async (patientId) => {
    // Проверяем, является ли это демо-пациентом (ID >= 1000)
    if (patientId >= 1000) {
      // Возвращаем null для демо-пациентов, так как их данные уже есть в записи
      return null;
    }

    const token = localStorage.getItem('auth_token');
    if (!token) return null;

    try {
      const response = await fetch(`${API_BASE}/api/v1/patients/${patientId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      // Подавляем ошибки для демо-режима
      if (error.message !== 'Failed to fetch') {
        logger.error(`Error fetching patient ${patientId}:`, error);
      }
    }
    return null;
  }, []);

  // Функция для обогащения записей данными пациентов и недостающими полями
  const enrichAppointmentsWithPatientData = useCallback(async (appointments) => {
    const enrichedAppointments = await Promise.all(appointments.map(async (apt) => {
      let enrichedApt = { ...apt };

      // Обогащаем данными пациента
      if (apt.patient_id) {
        const patient = await fetchPatientData(apt.patient_id);
        if (patient) {
          // ✅ ИСПРАВЛЕНО: Формируем patient_fio безопасно, используя все доступные поля
          // Если поля пустые, используем fallback
          let patient_fio = '';
          if (patient.last_name && patient.first_name) {
            patient_fio = `${patient.last_name} ${patient.first_name}`;
            if (patient.middle_name) {
              patient_fio += ` ${patient.middle_name}`;
            }
          } else if (patient.last_name) {
            patient_fio = patient.last_name;
          } else if (patient.first_name) {
            patient_fio = patient.first_name;
          } else {
            // Fallback, если все поля пустые (не должно произойти благодаря валидации)
            patient_fio = `Пациент ID=${patient.id}`;
          }

          enrichedApt = {
            ...enrichedApt,
            patient_fio: patient_fio.trim() || `Пациент ID=${patient.id}`,
            patient_phone: patient.phone,
            patient_birth_year: patient.birth_date ? new Date(patient.birth_date).getFullYear() : null,
            address: patient.address || 'Не указан', // Добавляем адрес из данных пациента
          };
        }
      }

      // Применяем локальные оверрайды (например, после оплаты), чтобы не было отката
      try {
        const overridesRaw = localStorage.getItem('appointments_local_overrides');
        if (overridesRaw) {
          const overrides = JSON.parse(overridesRaw);
          const ov = overrides[String(enrichedApt.id)];
          if (ov && (!ov.expiresAt || ov.expiresAt > Date.now())) {
            // ✅ ИСПРАВЛЕНО: Применяем только определенные поля из оверрайда, сохраняя queue_numbers
            enrichedApt = {
              ...enrichedApt,
              status: ov.status !== undefined ? ov.status : enrichedApt.status,
              payment_status: ov.payment_status !== undefined ? ov.payment_status : enrichedApt.payment_status
              // queue_numbers остается из enrichedApt (из API)
            };
          }
        }
      } catch {
        // Игнорируем ошибки парсинга JSON
      }

      // Добавляем недостающие поля для таблицы с значениями по умолчанию
      // ✅ ИСПРАВЛЕНО: Правильно обрабатываем all_free заявки (только одобренные)
      const isAllFree = enrichedApt.discount_mode === 'all_free' && enrichedApt.approval_status === 'approved';

      enrichedApt = {
        ...enrichedApt,
        // Если поля уже есть в API, используем их, иначе значения по умолчанию
        // ✅ ИСПРАВЛЕНО: Для all_free устанавливаем visit_type как 'free'
        visit_type: isAllFree ? 'free' : (enrichedApt.visit_type || 'paid'), // Платный по умолчанию
        // ✅ Для all_free устанавливаем payment_type как 'free', иначе определяем по провайдеру
        payment_type: isAllFree ? 'free' : (enrichedApt.payment_type || (enrichedApt.payment_provider === 'online' ? 'online' : 'cash')),
        // ✅ Если пришел payment_status от API — уважаем его; иначе — выводим из discount_mode или payment_processed_at
        payment_status: isAllFree ? 'paid' : (enrichedApt.payment_status || (enrichedApt.discount_mode === 'paid' ? 'paid' : (enrichedApt.payment_processed_at ? 'paid' : (enrichedApt.payment_amount > 0 ? 'pending' : 'pending')))),
        services: enrichedApt.services || [], // ✅ ИСПРАВЛЕНО: оставляем пустым если нет услуг
        // ✅ Для all_free устанавливаем cost = 0, иначе используем payment_amount или cost
        cost: isAllFree ? 0 : (enrichedApt.cost || enrichedApt.payment_amount || 0),
      };

      return enrichedApt;
    }));
    return enrichedAppointments;
  }, [fetchPatientData]);

  // Улучшенная загрузка записей с поддержкой тихого режима
  const loadAppointments = useCallback(async (options = {}) => {
    // console.log('📥 loadAppointments called at:', new Date().toISOString(), options);
    const { silent = false, source: callSource = 'unknown' } = options || {};
    try {
      if (!silent) {
        setAppointmentsLoading(true);
        setDataSource('loading');
      }

      // Проверяем наличие токена
      const token = localStorage.getItem('auth_token');
      // console.log('🔍 loadAppointments: token exists:', !!token);
      if (!token) {
        console.warn('Токен аутентификации отсутствует, показываем пустое состояние');
        startTransition(() => {
          if (!silent) setDataSource('api');
          setAppointments([]);
        });
        return;
      }


      // console.log('🔍 loadAppointments: making request');


      // Используем новый эндпоинт для получения очередей на указанную дату
      // Если календарь открыт, используем historyDate, иначе сегодня
      const dateParam = showCalendar && historyDate ? historyDate : getLocalDateString();
      /* console.log('📅 Параметры для loadAppointments:', {
        source: callSource,
        showCalendar,
        historyDate,
        dateParam,
        activeTab
      }); */

      const params = new URLSearchParams();
      params.append('target_date', dateParam);



      // console.log('🔍 loadAppointments: requesting with params:', { target_date: dateParam });


      const response = await api.get('/registrar/queues/today', { params: { target_date: dateParam } });

      // Axios successful response
      const data = response.data;

      // Новый формат: данные сгруппированы по специальностям
      let appointmentsData = [];

      if (data && typeof data === 'object') {
        // Временно отключено логирование больших объектов для диагностики
        // logger.info('📊 Получены данные от сервера:', data);
        // console.log('📊 Получены данные от сервера (count):', data.queues?.length || 0);


        // Обрабатываем формат от эндпоинта registrar_integration.py
        if (data.queues && Array.isArray(data.queues)) {
          // console.log('📊 Обрабатываем формат очередей:', data.queues.length, 'очередей');
          // ✅ ОТЛАДКА: Логируем структуру данных от сервера
          /*data.queues.forEach((q, idx) => {
            logger.info(`  Очередь ${idx + 1}: specialty=${q.specialty}, entries=${q.entries?.length || 0}`);
            if (q.entries && q.entries.length > 0) {
              q.entries.slice(0, 2).forEach((e, eIdx) => {
                const entryData = e.data || e;
                logger.info(`    Запись ${eIdx + 1}: type=${e.type}, id=${entryData?.id}, patient_id=${entryData?.patient_id}, patient_name=${entryData?.patient_name}`);
              });
            }
          });*/


          // ⭐ SSOT: Simple flatMap - no deduplication, no aggregation
          // Each backend entry = one frontend row
          // Removed: appointmentsMap, mergedByPatientKey, getAppointmentKey, calcPriority, mergeAppointments

          // Minimal field adaptation layer
          const adaptEntry = (entry, queue) => {
            const fullEntry = entry.data || entry;
            const entryId = fullEntry?.id;
            if (!entryId) return null; // Skip entries without ID

            const queueNum = fullEntry.number !== undefined && fullEntry.number !== null
              ? fullEntry.number
              : 0;
            const queueTime = entry.queue_time || fullEntry.queue_time || fullEntry.created_at || new Date().toISOString();

            return {
              // SSOT passthrough
              id: entryId,
              patient_id: fullEntry.patient_id || entry.patient_id,
              patient_fio: fullEntry.patient_name || entry.patient_name || 'Неизвестный пациент',
              patient_birth_year: fullEntry.patient_birth_year || fullEntry.birth_year || null,
              patient_phone: fullEntry.phone || fullEntry.patient_phone || '',
              address: fullEntry.address || '',
              services: Array.isArray(fullEntry.services) ? fullEntry.services : [],
              service_codes: Array.isArray(fullEntry.service_codes) ? fullEntry.service_codes : [],
              cost: fullEntry.cost || 0,
              payment_status: fullEntry.payment_status || 'pending',
              source: fullEntry.source || entry.source || 'desk',
              status: fullEntry.status || 'waiting',
              record_type: entry.type || fullEntry.type || entry.record_type || 'unknown',
              created_at: fullEntry.created_at || new Date().toISOString(),
              queue_time: queueTime,
              discount_mode: fullEntry.discount_mode || 'none',
              approval_status: fullEntry.approval_status || null,

              // Queue info
              queue_number: queueNum,
              queue_numbers: [{
                number: queueNum,
                // ⚠️ TEMPORARY ADAPTER: queue_tag derived from queue.specialty
                // until backend provides explicit queue_tag per entry
                queue_tag: queue.specialty || null,
                specialty: queue.specialty || null,
                status: fullEntry.status || 'waiting',
                queue_time: queueTime
              }],
              specialty: queue.specialty || null,
              // ⚠️ TEMPORARY ADAPTER: Fallback to specialty
              queue_tag: queue.specialty || null,
              department: queue.specialty || null,
              department_key: fullEntry.department_key || null,

              // Derived fields (minimal)
              visit_type: fullEntry.discount_mode === 'all_free' ? 'free' :
                fullEntry.discount_mode === 'benefit' ? 'benefit' : 'paid',
              payment_type: 'cash', // Backend doesn't return this yet
              date: dateParam,
              appointment_date: dateParam,

              // ⭐ SSOT: session_id for visual grouping (presentation only)
              // DO NOT parse this value - it's an opaque string from backend
              session_id: fullEntry.session_id || null
            };
          };

          // ⭐ SSOT: flatMap all entries without any deduplication or aggregation
          appointmentsData = data.queues.flatMap(queue =>
            (queue.entries || [])
              .map(entry => adaptEntry(entry, queue))
              .filter(entry => entry !== null) // Remove entries without ID
          );

          logger.info(`📊 SSOT: Loaded ${appointmentsData.length} entries (no dedup, no aggregation)`);
        } else {
          // Обрабатываем старый формат для совместимости
          if (activeTab && data[activeTab]) {
            appointmentsData = Array.isArray(data[activeTab]) ? data[activeTab] : [];
          } else {
            // Берем все специальности и объединяем
            for (const dept in data) {
              const deptData = data[dept];
              if (Array.isArray(deptData)) {
                appointmentsData.push(...deptData);
              }
            }
          }
        }

        setPaginationInfo({
          total: appointmentsData.length,
          hasMore: false,
          loadingMore: false
        });

        logger.info(`📊 Загружено ${appointmentsData.length} записей для специальности: ${activeTab || 'все'}`);

        // Отладка: показываем ID всех загруженных записей
        if (appointmentsData.length > 0) {
          logger.info('📋 ID всех загруженных записей:', appointmentsData.map(a => a.id));
        }

        // ✅ ИСПРАВЛЕНО: Пустая очередь - это нормально, не переключаемся в демо-режим
        if (appointmentsData.length === 0) {
          logger.info('📋 Нет записей на сегодня - это нормальная ситуация в начале дня');
          // Устанавливаем пустой массив, не выбрасываем ошибку
          setAppointments([]);
          setDataSource('api'); // ✅ Указываем, что данные получены от API
          setAppointmentsLoading(false);
          return; // ✅ Выходим из функции, не загружаем демо-данные
        }
      } else {
        logger.warn('⚠️ Получены некорректные данные от сервера:', data);
        throw new Error('Некорректные данные от сервера');
      }

      if (appointmentsData.length > 0) {
        // Обогащаем данные записей информацией о пациентах
        const enriched = await enrichAppointmentsWithPatientData(appointmentsData);

        // ⭐ SSOT: Просто устанавливаем данные без local overrides
        // Removed: _locallyModified, localStorage overrides
        startTransition(() => {
          setAppointments(enriched);
          setDataSource('api');
        });
        logger.info('✅ SSOT: Загружено', enriched.length, 'записей (без local overrides)');
      } else {
        // ⭐ SSOT: Demo fallback без local overrides
        startTransition(() => {
          setAppointments(demoAppointments);
          setDataSource('demo');
        });
      }
    } catch (error) {
      // Handle axios errors
      if (error.response?.status === 401) {
        // Токен недействителен
        logger.warn('Токен недействителен (401), очищаем и используем демо-данные');
        localStorage.removeItem('auth_token');
        // ⭐ SSOT: Demo fallback без local overrides
        startTransition(() => {
          if (!silent) setDataSource('demo');
          setAppointments(demoAppointments);
        });
      } else {
        // Other errors (network, 404, 500, etc.)
        logger.error('❌ Backend недоступен для загрузки записей, используем демо-режим:', error.message);
        logger.error('❌ Детали ошибки:', error);
        startTransition(() => {
          if (!silent) setDataSource(prev => (prev === 'demo' ? prev : 'demo'));
          setAppointments(prev => {
            try {
              const prevStr = JSON.stringify(prev);
              const nextStr = JSON.stringify(demoAppointments);
              if (prevStr === nextStr) return prev;
            } catch {
              // Игнорируем ошибки сравнения JSON
            }
            return demoAppointments;
          });
        });

        // Показываем уведомление пользователю только при первой загрузке
        if (appointmentsCount === 0) {
          toast('Backend недоступен. Работаем в демо-режиме.', { icon: 'ℹ️' });
        }
      }
    } finally {
      if (!silent) setAppointmentsLoading(false);
    }
  }, [enrichAppointmentsWithPatientData, showCalendar, historyDate, activeTab, demoAppointments, appointmentsCount]);

  // ✅ ДИНАМИЧЕСКИЕ ОТДЕЛЕНИЯ: загрузка отделений из БД
  const loadDynamicDepartments = useCallback(async () => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return;

      const response = await fetch(`${API_BASE}/api/v1/departments/active`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const departments = await response.json();
        // Backend returns {success: true, data: [...], count: N}
        const departmentsArray = departments.data || [];
        setDynamicDepartments(departmentsArray);
        logger.info('✅ Загружены динамические отделения:', departmentsArray.map(d => d.key));
      }
    } catch (error) {
      logger.error('Ошибка загрузки отделений:', error);
    }
  }, []);

  // Слушаем обновления отделений от админ-панели
  useEffect(() => {
    const handleDepartmentsUpdate = (event) => {
      logger.info('RegistrarPanel: Получено обновление отделений, перезагружаю...', event.detail);
      loadDynamicDepartments();
    };

    window.addEventListener('departments:updated', handleDepartmentsUpdate);
    return () => window.removeEventListener('departments:updated', handleDepartmentsUpdate);
  }, [loadDynamicDepartments]);

  // Первичная загрузка данных (однократно) с защитой от двойного вызова в React 18
  const initialLoadRef = useRef(false);
  useEffect(() => {
    if (initialLoadRef.current) return;
    initialLoadRef.current = true;
    logger.info('🚀 Starting initial data load (guarded)...');
    loadDynamicDepartments(); // ✅ Загружаем отделения
    loadAppointments({ source: 'initial_load' });
    loadIntegratedData();
  }, [loadAppointments, loadIntegratedData, loadDynamicDepartments]);

  // Слушаем глобальные события обновления очереди для синхронизации статусов
  useEffect(() => {
    const handleQueueUpdate = (event) => {
      const { action, specialty } = event.detail || {};
      logger.info('[RegistrarPanel] Получено событие обновления очереди:', { action, specialty, detail: event.detail });

      // Для критических действий обновляем немедленно без silent режима
      const criticalActions = ['patientCalled', 'visitStarted', 'visitCompleted', 'nextPatientCalled', 'refreshAll', 'entryAdded'];
      const shouldUpdateImmediately = criticalActions.includes(action);

      if (shouldUpdateImmediately) {
        logger.info('[RegistrarPanel] Немедленное обновление после действия:', action);
        logger.info('[RegistrarPanel] Детали события:', event.detail);
        // Увеличиваем задержку для гарантии сохранения данных в БД (особенно для новых записей)
        const delay = action === 'entryAdded' || action === 'refreshAll' ? 500 : 300;
        setTimeout(() => {
          logger.info('[RegistrarPanel] Выполняем обновление после задержки:', delay, 'ms');
          loadAppointments({ source: `queue_update_${action}`, silent: false });
        }, delay);
      } else {
        // Для других событий тихое обновление
        loadAppointments({ source: 'queue_update_event', silent: true });
      }
    };
    window.addEventListener('queueUpdated', handleQueueUpdate);

    return () => {
      window.removeEventListener('queueUpdated', handleQueueUpdate);
    };
  }, [loadAppointments]);

  // Перезагружаем данные при изменении фильтров
  useEffect(() => {
    if (initialLoadRef.current) {
      logger.info('🔄 Фильтры изменились (поиск/статус), но НЕ перезагружаем данные (дата контролируется календарём)');
      // Не перезагружаем данные - фильтрация происходит на клиенте через useMemo filteredAppointments
    }
  }, [searchQuery, statusFilter]);

  // Синхронизация tempDateInput с historyDate при открытии календаря
  useEffect(() => {
    if (showCalendar) {
      setTempDateInput(historyDate);
    }
  }, [showCalendar, historyDate]);

  // Debounce для ввода даты с клавиатуры
  useEffect(() => {
    if (!showCalendar) return;

    const timer = setTimeout(() => {
      // Проверяем, что введённая дата валидна и отличается от текущей
      if (tempDateInput && tempDateInput !== historyDate) {
        logger.info('📅 Debounced date input:', tempDateInput);
        setHistoryDate(tempDateInput);
      }
    }, 1000); // Задержка 1 секунда

    return () => clearTimeout(timer);
  }, [tempDateInput, showCalendar, historyDate]);

  // Перезагружаем данные при изменении даты в календаре
  useEffect(() => {
    if (showCalendar && historyDate && initialLoadRef.current) {
      logger.info('📅 Дата календаря изменилась на:', historyDate);
      logger.info('📅 Вызываем loadAppointments с параметрами:', { showCalendar, historyDate });
      loadAppointments({ silent: false, source: 'calendar_date_change' });
    }
  }, [historyDate, showCalendar, loadAppointments]);

  // Отслеживаем изменения в appointments для отладки
  useEffect(() => {
    logger.info('🔔 appointments state изменился:', {
      count: appointments.length,
      showCalendar,
      historyDate,
      first3: appointments.slice(0, 3).map(a => ({ id: a.id, fio: a.patient_fio, date: a.appointment_date }))
    });
  }, [appointments, showCalendar, historyDate]);

  // Функция для загрузки дополнительных записей
  const loadMoreAppointments = useCallback(async () => {
    if (paginationInfo.loadingMore || !paginationInfo.hasMore) return;

    setPaginationInfo(prev => ({ ...prev, loadingMore: true }));

    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return;

      // Используем новый эндпоинт для получения очередей на сегодня
      const response = await fetch(`${API_BASE}/api/v1/registrar/queues/today${activeTab ? `?department=${activeTab}` : ''}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      // ✅ ИСПРАВЛЕНО: Обработка ошибки 403 (Forbidden) - недостаточно прав
      if (response.status === 403) {
        logger.warn('⚠️ Доступ запрещен: недостаточно прав для просмотра очередей');
        setPaginationInfo(prev => ({ ...prev, loadingMore: false }));
        return;
      }

      if (response.ok) {
        const data = await response.json();

        // Новый формат: данные сгруппированы по специальностям
        let newAppointments = [];

        if (data && typeof data === 'object') {
          logger.info('📊 Получены данные от сервера (дополнительно):', data);

          // Обрабатываем формат от эндпоинта registrar_integration.py
          if (data.queues && Array.isArray(data.queues)) {
            // Если задана конкретная специальность, фильтруем очереди
            if (activeTab) {
              // Находим очередь для указанной специальности
              const targetQueue = data.queues.find(queue =>
                queue.specialty === activeTab ||
                (activeTab === 'cardio' && queue.specialty === 'cardiology') ||
                (activeTab === 'derma' && queue.specialty === 'dermatology') ||
                (activeTab === 'dental' && queue.specialty === 'stomatology') ||
                (activeTab === 'lab' && queue.specialty === 'laboratory') ||
                (activeTab === 'procedures' && queue.specialty === 'procedures') ||
                (activeTab === 'echokg' && (queue.specialty === 'echokg' || queue.specialty === 'ecg' || queue.specialty === 'ЭКГ'))
              );

              if (targetQueue && targetQueue.entries) {
                newAppointments = targetQueue.entries.map(entry => ({
                  id: entry.id,
                  patient_id: entry.patient_id || null,
                  patient_fio: entry.patient_name,
                  patient_phone: entry.phone,
                  patient_birth_year: entry.patient_birth_year || null,
                  address: entry.address || '',
                  doctor_id: null,
                  department: targetQueue.specialty,
                  appointment_date: data.date,
                  appointment_time: null,
                  status: entry.status,
                  services: entry.services || [],  // ✅ ИСПРАВЛЕНО: Берем services из entry
                  service_codes: entry.service_codes || [],  // ✅ ИСПРАВЛЕНО: Берем service_codes из entry
                  cost: entry.cost || 0,  // ✅ ДОБАВЛЕНО: Стоимость
                  payment_status: entry.payment_status || 'pending',  // ✅ ДОБАВЛЕНО: Статус оплаты
                  discount_mode: entry.discount_mode || 'none',  // ✅ ДОБАВЛЕНО: Режим скидки
                  source: entry.source,
                  created_at: entry.created_at,  // ✅ ИСПРАВЛЕНО: Добавляем created_at
                  visit_time: entry.visit_time || null,  // ✅ ДОБАВЛЕНО: Время визита
                  record_type: entry.record_type || 'visit',  // ✅ ДОБАВЛЕНО: Тип записи
                  service_details: entry.service_details || [],  // ✅ НОВОЕ: Полные данные услуг
                  queue_numbers: [{
                    id: entry.id, // ✅ ВАЖНО для AppointmentWizardV2: originalQueueIds использует это поле
                    queue_tag: targetQueue.specialty,
                    queue_name: targetQueue.specialist_name || targetQueue.specialty || 'Очередь',
                    number: entry.number,
                    status: entry.status,
                    specialty: targetQueue.specialty,
                    source: entry.source,
                    created_at: entry.created_at,
                    service_details: entry.service_details || []  // ✅ НОВОЕ: Полные данные услуг
                  }],
                  confirmation_status: 'none',
                  confirmed_at: null,
                  confirmed_by: null
                }));
              } else {
                newAppointments = [];
              }
            } else {
              // Берем все очереди и объединяем записи
              for (const queue of data.queues) {
                if (queue.entries && Array.isArray(queue.entries)) {
                  const queueAppointments = queue.entries.map(entry => ({
                    id: entry.id,
                    patient_id: entry.patient_id || null,
                    patient_fio: entry.patient_name,
                    patient_phone: entry.phone,
                    patient_birth_year: entry.patient_birth_year || null,
                    address: entry.address || '',
                    doctor_id: queue.specialist_id,
                    department: queue.specialty,
                    appointment_date: data.date,
                    appointment_time: null,
                    status: entry.status,
                    services: entry.services || [],  // ✅ ИСПРАВЛЕНО: Берем services из entry
                    service_codes: entry.service_codes || [],  // ✅ ИСПРАВЛЕНО: Берем service_codes из entry
                    cost: entry.cost || 0,  // ✅ ДОБАВЛЕНО: Стоимость
                    payment_status: entry.payment_status || 'pending',  // ✅ ДОБАВЛЕНО: Статус оплаты
                    discount_mode: entry.discount_mode || 'none',  // ✅ ДОБАВЛЕНО: Режим скидки
                    source: entry.source,
                    created_at: entry.created_at,  // ✅ ИСПРАВЛЕНО: Добавляем created_at
                    visit_time: entry.visit_time || null,  // ✅ ДОБАВЛЕНО: Время визита
                    record_type: entry.record_type || 'visit',  // ✅ ДОБАВЛЕНО: Тип записи
                    service_details: entry.service_details || [],  // ✅ НОВОЕ: Полные данные услуг
                    queue_numbers: [{
                      id: entry.id, // ✅ ВАЖНО для AppointmentWizardV2: originalQueueIds использует это поле
                      queue_tag: queue.specialty,
                      queue_name: queue.specialist_name || queue.specialty || 'Очередь',
                      number: entry.number,
                      status: entry.status,
                      specialty: queue.specialty,
                      source: entry.source,
                      created_at: entry.created_at,
                      service_details: entry.service_details || []  // ✅ НОВОЕ: Полные данные услуг
                    }],
                    confirmation_status: 'none',
                    confirmed_at: null,
                    confirmed_by: null
                  }));
                  newAppointments.push(...queueAppointments);
                }
              }
            }
          } else {
            // Обрабатываем старый формат для совместимости
            if (activeTab && data[activeTab]) {
              newAppointments = Array.isArray(data[activeTab]) ? data[activeTab] : [];
            } else {
              // Берем все специальности и объединяем
              for (const dept in data) {
                const deptData = data[dept];
                if (Array.isArray(deptData)) {
                  newAppointments.push(...deptData);
                }
              }
            }
          }
        }

        if (newAppointments.length > 0) {
          const enriched = await enrichAppointmentsWithPatientData(newAppointments);
          setAppointments(prev => [...prev, ...enriched]);
          setPaginationInfo({
            total: appointments.length + newAppointments.length,
            hasMore: false, // Пока не поддерживаем пагинацию в новом формате
            loadingMore: false
          });
        } else {
          logger.warn('⚠️ Нет дополнительных данных от сервера');
          setPaginationInfo(prev => ({ ...prev, loadingMore: false }));
        }
      }
    } catch (error) {
      logger.error('Ошибка загрузки дополнительных записей:', error);
      setPaginationInfo(prev => ({ ...prev, loadingMore: false }));
    }
  }, [paginationInfo, appointments.length, activeTab, enrichAppointmentsWithPatientData]);

  // Обработчик события из хедера для открытия мастера записи
  useEffect(() => {
    const handleOpenWizard = () => {
      setShowWizard(true);
    };

    window.addEventListener('openAppointmentWizard', handleOpenWizard);
    return () => {
      window.removeEventListener('openAppointmentWizard', handleOpenWizard);
    };
  }, []);

  // ✅ Проверка localStorage для обновления после присоединения к очереди (fallback механизм)
  useEffect(() => {
    const checkLastQueueJoin = () => {
      try {
        const lastJoinStr = localStorage.getItem('lastQueueJoin');
        if (!lastJoinStr) return;

        const lastJoin = JSON.parse(lastJoinStr);
        const joinTime = new Date(lastJoin.timestamp);
        const now = new Date();
        const diffMs = now - joinTime;

        // Проверяем только если прошло меньше 10 секунд с момента присоединения
        if (diffMs < 10000 && diffMs > 0) {
          logger.info('[RegistrarPanel] Обнаружено недавнее присоединение к очереди, обновляем данные');
          logger.info('[RegistrarPanel] Данные присоединения:', lastJoin);
          // Удаляем флаг после использования
          localStorage.removeItem('lastQueueJoin');
          // Обновляем данные
          setTimeout(() => {
            loadAppointments({ source: 'queueJoin_fallback', silent: false });
          }, 500);
        }
      } catch (err) {
        logger.error('[RegistrarPanel] Ошибка проверки lastQueueJoin:', err);
      }
    };

    // Проверяем при монтировании и каждые 2 секунды
    checkLastQueueJoin();
    const interval = setInterval(checkLastQueueJoin, 2000);

    return () => clearInterval(interval);
  }, [loadAppointments]);

  // Автообновление очереди с возможностью паузы (в тихом режиме)
  useEffect(() => {
    // Во время мастера записи или модальных окон автообновление отключаем, чтобы не было мерцаний
    if (showWizard || paymentDialog.open || printDialog.open || cancelDialog.open) return;
    if (!autoRefresh) return;

    const id = setInterval(() => {
      // Загружаем только записи тихо, без смены индикаторов
      logger.info('⏰ Автообновление: вызов loadAppointments');
      loadAppointments({ silent: true, source: 'auto_refresh' });
    }, 15000);

    return () => clearInterval(id);
  }, [autoRefresh, showWizard, paymentDialog.open, printDialog.open, cancelDialog.open, loadAppointments]);

  // Функции для жесткого потока
  const handleStartVisit = useCallback(async (appointment) => {
    try {
      logger.info('🔍 handleStartVisit вызван с данными:', appointment);
      logger.info('🔍 appointment.id:', appointment.id, 'тип:', typeof appointment.id);

      // ✅ ИСПРАВЛЕНО: Используем правильный эндпоинт для queue entries
      const url = `${API_BASE}/api/v1/registrar/queue/${appointment.id}/start-visit`;
      logger.info('🔍 Отправляем запрос на:', url);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (response.ok) {
        const result = await response.json();
        logger.info('Обновленная запись:', result);

        // Обновляем список записей с новым статусом
        setAppointments(prev => prev.map(apt =>
          apt.id === appointment.id ? {
            ...apt,
            status: result.entry?.status || 'in_progress',
            _locallyModified: false
          } : apt
        ));
        toast.success('Пациент вызван успешно!');

        // Перезагружаем данные для синхронизации с сервером
        await loadAppointments({ source: 'start_visit_success' });
      } else {
        const errorText = await response.text().catch(() => '');
        logger.error('Ошибка API start-visit:', response.status, errorText);
        throw new Error(`API ${response.status}: ${errorText}`);
      }
    } catch (error) {
      logger.error('RegistrarPanel: Start visit API error:', error);
      toast.error('Не удалось вызвать пациента: ' + error.message);
    }
  }, [loadAppointments]);

  const handlePayment = async (appointment) => {
    try {
      logger.info('🔍 handlePayment вызван с данными:', appointment);
      logger.info('🔍 appointment.id:', appointment.id, 'тип:', typeof appointment.id);
      logger.info('🔍 appointment.record_type:', appointment.record_type);
      logger.info('🔍 Все ключи appointment:', Object.keys(appointment));
      logger.info('🔍 Полный объект appointment:', JSON.stringify(appointment, null, 2));

      // Определяем, является ли это агрегированной записью
      const isAggregated = appointment.departments && appointment.departments instanceof Set;
      logger.info('🔍 Это агрегированная запись:', isAggregated);

      // Если это агрегированная запись, находим все оригинальные записи пациента
      let recordsToUpdate = [appointment]; // По умолчанию только текущая запись
      if (isAggregated) {
        logger.info('🔍 Ищем все записи пациента:', appointment.patient_fio);
        // Находим все записи этого пациента в оригинальном массиве
        const allPatientRecords = appointments.filter(apt => apt.patient_fio === appointment.patient_fio);
        logger.info('🔍 Найдено записей пациента:', allPatientRecords.length);
        recordsToUpdate = allPatientRecords;
      }

      logger.info('Попытка оплатить записи:', recordsToUpdate.map(r => r.id));

      // ✅ ИСПРАВЛЕНИЕ: Оплачиваем ВСЕ записи пациента, а не только первую
      logger.info('🔍 Оплачиваем ВСЕ записи пациента:', recordsToUpdate.length);

      const paymentResults = [];
      for (const record of recordsToUpdate) {
        const recordType = record.record_type || (record.id >= 20000 ? 'visit' : 'appointment');
        const recordId = record.id;

        // ✅ ИСПРАВЛЕНИЕ: Проверяем статус КАЖДОЙ записи перед попыткой оплаты
        const paymentStatus = (record.payment_status || '').toLowerCase();
        const status = (record.status || '').toLowerCase();
        const discountMode = (record.discount_mode || '').toLowerCase();

        logger.info(`🔍 Запись ${recordId}: статус оплаты=${paymentStatus}, статус=${status}, discount_mode=${discountMode}`);

        // Пропускаем записи, которые уже оплачены
        if (paymentStatus === 'paid' ||
          status === 'paid' ||
          status === 'queued' ||
          discountMode === 'paid') {
          logger.info(`⏭️ Запись ${recordId} уже оплачена, пропускаем`);
          paymentResults.push({ success: true, recordId, skipped: true, reason: 'already_paid' });
          continue;
        }

        let url;
        if (recordType === 'visit') {
          url = `${API_BASE}/api/v1/registrar/visits/${recordId}/mark-paid`;
        } else if (recordType === 'online_queue') {
          // ✅ ИСПРАВЛЕНО: Для online_queue используем специальный endpoint
          url = `${API_BASE}/api/v1/registrar/queue/entry/${recordId}/mark-paid`;
        } else {
          url = `${API_BASE}/api/v1/appointments/${recordId}/mark-paid`;
        }

        logger.info(`🔍 Оплата записи ${recordId} (${recordType}):`, url);

        try {
          const response = await fetch(url, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
            }
          });

          if (response.ok) {
            const result = await response.json();
            paymentResults.push({ success: true, recordId, result });
            logger.info(`✅ Запись ${recordId} успешно оплачена`);
          } else {
            const errorText = await response.text();
            logger.warn(`⚠️ Ошибка оплаты записи ${recordId}:`, errorText);
            paymentResults.push({ success: false, recordId, error: errorText });
          }
        } catch (error) {
          logger.error(`❌ Ошибка при оплате записи ${recordId}:`, error);
          paymentResults.push({ success: false, recordId, error: error.message });
        }
      }

      const successCount = paymentResults.filter(r => r.success && !r.skipped).length;
      const skippedCount = paymentResults.filter(r => r.success && r.skipped).length;
      const failedCount = paymentResults.filter(r => !r.success).length;

      logger.info(`✅ Успешно оплачено ${successCount} из ${recordsToUpdate.length} записей`);
      if (skippedCount > 0) {
        logger.info(`⏭️ Пропущено уже оплаченных записей: ${skippedCount}`);
      }
      if (failedCount > 0) {
        logger.info(`❌ Ошибок при оплате: ${failedCount}`);
      }

      if (successCount > 0 || skippedCount > 0) {
        // Обновляем статус только для записей, которые были реально оплачены (не пропущены)
        const paidRecordIds = paymentResults
          .filter(r => r.success && !r.skipped)
          .map(r => r.recordId);

        logger.info('✅ Оплата успешна, обновляем локальное состояние для оплаченных записей:', paidRecordIds);

        // Обновляем статус только для реально оплаченных записей
        recordsToUpdate
          .filter(record => paidRecordIds.includes(record.id))
          .forEach(record => {
            const recordWithQueuedStatus = {
              ...record,
              status: 'queued', // Принудительно устанавливаем статус "В очереди" после оплаты
              payment_status: 'paid',
              _locallyModified: true // Помечаем как локально измененную, чтобы избежать перезаписи при обновлении
            };

            // Сохраняем локальный оверрайд для каждой записи
            try {
              const overridesRaw = localStorage.getItem('appointments_local_overrides');
              const overrides = overridesRaw ? JSON.parse(overridesRaw) : {};
              overrides[String(record.id)] = {
                status: recordWithQueuedStatus.status,
                payment_status: recordWithQueuedStatus.payment_status,
                // TTL 10 минут
                expiresAt: Date.now() + 10 * 60 * 1000
              };
              localStorage.setItem('appointments_local_overrides', JSON.stringify(overrides));
            } catch {
              // Игнорируем ошибки парсинга JSON
            }

            // Обновляем состояние для каждой записи
            setAppointments(prev => prev.map(apt => (
              apt.id === record.id ? recordWithQueuedStatus : apt
            )));
          });

        // Формируем информативное сообщение
        let message = '';
        if (successCount > 0 && skippedCount > 0) {
          message = `Оплачено ${successCount} записей, ${skippedCount} уже были оплачены ранее`;
        } else if (successCount > 0) {
          message = `Оплачено ${successCount} записей пациента и добавлены в очередь!`;
        } else if (skippedCount > 0) {
          message = 'Все записи уже оплачены';
        }

        if (failedCount > 0) {
          message += `. Ошибок: ${failedCount}`;
        }

        toast.success(message);
        // Мягко подтянем данные из API, чтобы зафиксировать статус с бэкенда
        setTimeout(() => loadAppointments({ silent: true, source: 'payment_success' }), 800);
        return paymentResults;
      } else {
        toast.error('Не удалось оплатить записи');
        return paymentResults;
      }
    } catch (error) {
      logger.error('RegistrarPanel: Payment error:', error);
      toast.error('Ошибка при оплате');
    }
  };

  // Обработчики событий
  const updateAppointmentStatus = useCallback(async (appointmentId, status, reason = '') => {
    try {
      if (!appointmentId || Number(appointmentId) <= 0) {
        toast.error('Некорректный идентификатор записи');
        return;
      }
      const token = localStorage.getItem('auth_token');
      if (!token) {
        toast.error('Требуется вход в систему');
        return;
      }
      let url = '';
      const method = 'POST';
      let body;

      // Определяем источник записи и правильный ID
      const isFromVisits = appointmentId >= 20000;
      const realId = isFromVisits ? appointmentId - 20000 : appointmentId;

      if (status === 'complete' || status === 'done') {
        if (isFromVisits) {
          url = `${API_BASE}/api/v1/registrar/visits/${realId}/complete`;
        } else {
          url = `${API_BASE}/api/v1/appointments/${realId}/complete`;
        }
        body = JSON.stringify({ reason });
      } else if (status === 'paid' || status === 'mark-paid') {
        if (isFromVisits) {
          url = `${API_BASE}/api/v1/registrar/visits/${realId}/mark-paid`;
        } else {
          url = `${API_BASE}/api/v1/appointments/${realId}/mark-paid`;
        }
      } else if (status === 'cancelled' || status === 'canceled') {
        // Пока нет API для отмены, обновляем локально
        logger.info('Отмена записи (локально):', appointmentId);
        setAppointments(prev => prev.map(apt =>
          apt.id === appointmentId ? {
            ...apt,
            status: 'cancelled',
            _locallyModified: true,
            _cancelReason: reason
          } : apt
        ));
        toast.success('Запись отменена (локально)');
        return { id: appointmentId, status: 'cancelled' };
      } else if (status === 'confirmed') {
        // Пока нет API для подтверждения, обновляем локально
        logger.info('Подтверждение записи (локально):', appointmentId);
        setAppointments(prev => prev.map(apt =>
          apt.id === appointmentId ? {
            ...apt,
            status: 'confirmed',
            _locallyModified: true
          } : apt
        ));
        toast.success('Запись подтверждена (локально)');
        return { id: appointmentId, status: 'confirmed' };
      } else if (status === 'no_show') {
        // Пока нет API для неявки, обновляем локально
        logger.info('Неявка записи (локально):', appointmentId, 'Причина:', reason);
        setAppointments(prev => prev.map(apt =>
          apt.id === appointmentId ? {
            ...apt,
            status: 'no_show',
            _locallyModified: true,
            _noShowReason: reason
          } : apt
        ));
        toast.success('Отмечено как неявка (локально)');
        return { id: appointmentId, status: 'no_show' };
      } else if (status === 'in_cabinet') {
        if (isFromVisits) {
          url = `${API_BASE}/api/v1/registrar/visits/${realId}/start-visit`;
        } else {
          // Используем эндпоинт для очереди регистратора
          url = `${API_BASE}/api/v1/registrar/queue/${realId}/start-visit`;
        }
      } else {
        logger.info('Неподдерживаемый статус:', status);
        toast.error('Изменение данного статуса не поддерживается');
        return;
      }

      logger.info('Обновляем статус записи:', appointmentId, 'на', status, 'URL:', url);

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body
      });

      logger.info('Ответ API обновления статуса:', response.status, response.statusText);

      if (!response.ok) {
        const errText = await response.text().catch(() => '');
        logger.error('Ошибка API обновления статуса:', response.status, errText);
        throw new Error(errText || `API ${response.status}`);
      }

      const updatedAppointment = await response.json();
      logger.info('Обновленная запись:', updatedAppointment);

      // Обновляем локальное состояние
      setAppointments(prev => prev.map(apt =>
        apt.id === appointmentId ? { ...apt, status: updatedAppointment.status || status } : apt
      ));

      await loadAppointments({ source: 'status_update' });
      toast.success('Статус обновлен');
      return updatedAppointment;
    } catch (error) {
      logger.error('RegistrarPanel: Update status error:', error);
      toast.error('Не удалось обновить статус: ' + error.message);
      return null;
    }
  }, [loadAppointments]);

  const handleBulkAction = useCallback(async (action, reason = '') => {
    if (appointmentsSelected.size === 0) return;

    if (['cancelled', 'no_show'].includes(action)) {
      const ok = window.confirm(`Применить действие «${action}» для ${appointmentsSelected.size} записей?`);
      if (!ok) return;
    }

    const results = await Promise.allSettled(
      Array.from(appointmentsSelected).map(id => updateAppointmentStatus(id, action, reason))
    );

    const successCount = results.filter(r => r.status === 'fulfilled').length;
    const failCount = results.length - successCount;

    if (successCount > 0) toast.success(`Обновлено: ${successCount}`);
    if (failCount > 0) toast.error(`Ошибок: ${failCount}`);
    setAppointmentsSelected(new Set());
  }, [appointmentsSelected, updateAppointmentStatus]);

  // ✅ ИСПОЛЬЗУЕМ useRef для хранения filteredAppointments, чтобы избежать ошибки "Cannot access before initialization"
  const filteredAppointmentsRef = useRef([]);

  // Горячие клавиши
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Отладка всех нажатий клавиш
      logger.info('Key pressed:', e.key, 'Ctrl:', e.ctrlKey, 'Alt:', e.altKey, 'Target:', e.target.tagName);

      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        logger.info('Ignoring key press in input/textarea');
        return;
      }

      if (e.key === 'Enter') {
        // Enter в мастере обрабатывается отдельно в полях ввода
        // Здесь не обрабатываем, чтобы избежать конфликтов
      } else if (e.ctrlKey) {
        if (e.key === 'p') {
          e.preventDefault();
        } else if (e.key === 'k') {
          e.preventDefault();
          setShowWizard(true);
        } else if (e.key === '1') setActiveTab('welcome');
        else if (e.key === '2') setActiveTab('appointments');
        else if (e.key === '3') setActiveTab('cardio');
        else if (e.key === '4') setActiveTab('derma');
        else if (e.key === '5') setActiveTab('queue');
        else if (e.key === 'a') {
          e.preventDefault();
          logger.info('Ctrl+A: Выбрать все записи');
          // ✅ ИСПРАВЛЕНО: Используем filteredAppointments из ref
          const allIds = filteredAppointmentsRef.current.map(a => a.id);
          setAppointmentsSelected(new Set(allIds));
          logger.info('Выбрано записей:', allIds.length);
        } else if (e.key === 'd') {
          e.preventDefault();
          logger.info('Ctrl+D: Снять выделение');
          setAppointmentsSelected(new Set());
        }
      } else if (e.altKey) {
        logger.info('Alt key pressed with:', e.key, 'Selected rows:', appointmentsSelected.size);
        if (e.key === '1') {
          e.preventDefault();
          logger.info('Alt+1: Подтвердить');
          if (appointmentsSelected.size > 0) {
            handleBulkAction('confirmed');
          } else {
            logger.info('Нет выбранных записей для подтверждения');
          }
        } else if (e.key === '2') {
          e.preventDefault();
          logger.info('Alt+2: Отменить');
          if (appointmentsSelected.size > 0) {
            const reason = window.prompt('Причина отмены');
            if (reason) handleBulkAction('cancelled', reason);
          } else {
            logger.info('Нет выбранных записей для отмены');
          }
        } else if (e.key === '3') {
          e.preventDefault();
          logger.info('Alt+3: Неявка');
          if (appointmentsSelected.size > 0) {
            handleBulkAction('no_show');
          } else {
            logger.info('Нет выбранных записей для неявки');
          }
        }
      } else if (e.key === 'Escape') {
        if (showWizard) setShowWizard(false);
        if (showSlotsModal) setShowSlotsModal(false);
        if (showQRModal) setShowQRModal(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [showWizard, showSlotsModal, showQRModal, appointments, handleBulkAction, appointmentsSelected]);

  // ⭐ SSOT: Simple department check - backend already assigned queue_tag
  // Canonical field: queue_tag (from backend specialty via adaptEntry)
  // Removed: ~465 lines of legacy heuristics, mappings, queue_numbers.some(), service inference
  const isInDepartment = useCallback((appointment, departmentKey) => {
    // "all" tab shows everything
    if (departmentKey === 'все' || departmentKey === 'all' || !departmentKey) return true;

    // SSOT: Backend already assigned the canonical department field
    // ⚠️ TEMPORARY ADAPTER: Remove specialty/queue_tag fallback
    // when backend guarantees department_key consistency
    // Target: return appointment.department_key === departmentKey;
    return appointment.queue_tag === departmentKey ||
      appointment.specialty === departmentKey ||
      appointment.department_key === departmentKey;
  }, []);


  // Мемоизированные счетчики и индикаторы по отделам
  const departmentStats = useMemo(() => {
    const stats = {};

    // ⭐ SSOT: Use queue profile keys from API, not hardcoded department keys
    // queueProfiles is loaded from GET /queues/profiles via ModernTabs
    const profileKeys = queueProfiles.length > 0
      ? queueProfiles.map(p => p.key)
      : ['cardiology', 'ecg', 'dermatology', 'stomatology', 'lab', 'procedures']; // Fallback

    // Get queue_tags for each profile for accurate matching
    const profileTagsMap = {};
    queueProfiles.forEach(p => {
      profileTagsMap[p.key] = p.queue_tags || [p.key];
    });

    profileKeys.forEach(profileKey => {
      // ⭐ SSOT: Match entries by queue_tags from profile
      const possibleTags = profileTagsMap[profileKey] || [profileKey];

      const profileAppointments = appointments.filter(a => {
        const entryTag = (a.queue_tag || a.specialty || '').toLowerCase().trim();
        return possibleTags.some(tag => tag.toLowerCase() === entryTag);
      });

      const todayAppointments = profileAppointments.filter(a => {
        const appointmentDate = a.date || a.appointment_date;
        return appointmentDate === todayStr;
      });

      stats[profileKey] = {
        todayCount: todayAppointments.length,
        hasActiveQueue: profileAppointments.some(a =>
          a.queue_numbers && a.queue_numbers.length > 0 &&
          ['waiting', 'called', 'in_service'].includes(a.status)
        ),
        hasPendingPayments: profileAppointments.some(a =>
          a.status === 'paid_pending' || a.payment_status === 'pending'
        )
      };
    });

    return stats;
  }, [appointments, todayStr, queueProfiles]);


  // 🎨 PRESENTATION-ONLY: Aggregation for "All departments" tab
  // Groups entries by patient for visual display (1 patient = 1 row)
  // ✅ ALLOWED by SSOT: This is view-model grouping, NOT business logic
  // ⚠️ Do NOT use for: filtering, routing, department decisions
  const aggregatePatientsForAllDepartments = useCallback((appointments) => {
    const patientGroups = {};

    appointments.forEach(appointment => {
      // Используем patient_fio как уникальный идентификатор пациента
      const patientKey = appointment.patient_fio;

      if (!patientGroups[patientKey]) {
        // ✅ ИСПРАВЛЕНО: Проверяем All Free статус для корректного отображения
        const isAllFree = appointment.discount_mode === 'all_free' && appointment.approval_status === 'approved';

        patientGroups[patientKey] = {
          id: appointment.id,
          patient_id: appointment.patient_id,
          patient_fio: appointment.patient_fio,
          patient_birth_year: appointment.patient_birth_year,
          patient_phone: appointment.patient_phone,
          address: appointment.address,
          // ✅ ИСПРАВЛЕНО: Для all_free устанавливаем visit_type как 'free'
          visit_type: isAllFree ? 'free' : appointment.visit_type,
          // ✅ ИСПРАВЛЕНО: Для all_free устанавливаем payment_type как 'free'
          payment_type: isAllFree ? 'free' : appointment.payment_type,
          payment_status: appointment.payment_status,
          cost: 0, // Будет суммироваться из всех записей
          status: appointment.status,
          date: appointment.date,
          appointment_date: appointment.appointment_date,
          created_at: appointment.created_at,
          // Агрегируем услуги из разных отделений
          services: [],
          departments: new Set(),
          doctors: new Set(),
          // Используем первую попавшуюся запись для остальных полей
          department: appointment.department,
          doctor_specialty: appointment.doctor_specialty,
          queue_numbers: appointment.queue_numbers || [],
          confirmation_status: appointment.confirmation_status,
          confirmed_at: appointment.confirmed_at,
          confirmed_by: appointment.confirmed_by,
          record_type: appointment.record_type, // ✅ ДОБАВЛЕНО: Сохраняем тип записи при агрегации
          source: appointment.source, // ✅ FIX: Сохраняем источник (online/desk) для Wizard'а
          // ✅ ДОБАВЛЕНО: Сохраняем discount_mode и approval_status для корректного отображения
          discount_mode: appointment.discount_mode,
          approval_status: appointment.approval_status,
          // ✅ FIX: Собираем ВСЕ ID записей для групповой отмены
          // Если запись уже агрегирована в loadAppointments, берем её aggregated_ids
          aggregated_ids: appointment.aggregated_ids ? [...appointment.aggregated_ids] : [appointment.id]
        };
      } else {
        // Добавляем ID в массив агрегированных
        const newIds = appointment.aggregated_ids || [appointment.id];
        patientGroups[patientKey].aggregated_ids.push(...newIds);
        // Убираем возможные дубликаты
        patientGroups[patientKey].aggregated_ids = [...new Set(patientGroups[patientKey].aggregated_ids)];

        // ✅ ИСПРАВЛЕНО: Если уже есть запись, но новая имеет All Free — обновляем
        const isAllFree = appointment.discount_mode === 'all_free' && appointment.approval_status === 'approved';
        const existingIsAllFree = patientGroups[patientKey].discount_mode === 'all_free' &&
          patientGroups[patientKey].approval_status === 'approved';

        if (isAllFree && !existingIsAllFree) {
          // Новая запись All Free, а существующая нет — обновляем
          patientGroups[patientKey].visit_type = 'free';
          patientGroups[patientKey].payment_type = 'free';
          patientGroups[patientKey].discount_mode = appointment.discount_mode;
          patientGroups[patientKey].approval_status = appointment.approval_status;
        }

        // ✅ FIX: Агрегируем queue_numbers (добавляем новые очереди к существующему пациенту в таблице "Все")
        // ⭐ ИСПРАВЛЕНО: Дедупликация по ID записи, а не по specialty
        // Это позволяет сохранить несколько записей с одинаковой specialty (например, 2 консультации кардиолога)
        if (appointment.queue_numbers && Array.isArray(appointment.queue_numbers)) {
          const existingQueueIds = new Set((patientGroups[patientKey].queue_numbers || []).map(qn =>
            qn.id?.toString() || `${qn.queue_tag}_${qn.service_id}`
          ));

          appointment.queue_numbers.forEach(qn => {
            const queueId = qn.id?.toString() || `${qn.queue_tag}_${qn.service_id}`;
            if (!existingQueueIds.has(queueId)) {
              patientGroups[patientKey].queue_numbers.push(qn);
              existingQueueIds.add(queueId);
            }
          });
        }

        // ✅ SSOT: Только source='online' считается QR-записью
        // confirmation больше не используется — backend теперь всегда возвращает 'online' или 'desk'
        const isQRSource = (src) => src === 'online';
        const currentIsQR = isQRSource(appointment.source);
        const aggregatedIsQR = isQRSource(patientGroups[patientKey].source);

        if (currentIsQR && !aggregatedIsQR) {
          patientGroups[patientKey].source = appointment.source;
          patientGroups[patientKey].record_type = appointment.record_type || patientGroups[patientKey].record_type;
        }
      }

      // Суммируем стоимость для ВСЕХ записей пациента (включая первую)
      // ✅ ИСПРАВЛЕНО: Для All Free не суммируем стоимость, оставляем 0
      const isAllFree = appointment.discount_mode === 'all_free' && appointment.approval_status === 'approved';
      if (!isAllFree && appointment.cost) {
        patientGroups[patientKey].cost += appointment.cost;
      }

      // Добавляем услуги если их еще нет
      // ⭐ DEBUG: Логируем что приходит в агрегацию
      // console.log(`🔄 Aggregating ${appointment.patient_fio}: appointment.services=${JSON.stringify(appointment.services)}, current patientGroups[${patientKey}].services=${JSON.stringify(patientGroups[patientKey].services)}`);

      if (appointment.services && Array.isArray(appointment.services)) {
        appointment.services.forEach(service => {
          if (!patientGroups[patientKey].services.includes(service)) {
            patientGroups[patientKey].services.push(service);
          }
        });
      }

      // ✅ FIX: Агрегируем service_codes для корректной работы Wizard
      if (appointment.service_codes && Array.isArray(appointment.service_codes)) {
        if (!patientGroups[patientKey].service_codes) patientGroups[patientKey].service_codes = [];
        appointment.service_codes.forEach(code => {
          if (!patientGroups[patientKey].service_codes.includes(code)) {
            patientGroups[patientKey].service_codes.push(code);
          }
        });
      }

      // Добавляем информацию об отделении
      if (appointment.department) {
        patientGroups[patientKey].departments.add(appointment.department);
      }

      // Добавляем информацию о враче
      if (appointment.doctor_specialty) {
        patientGroups[patientKey].doctors.add(appointment.doctor_specialty);
      }
    });

    // Преобразуем обратно в массив
    return Object.values(patientGroups);
  }, []);

  // Мемоизированная фильтрация записей по выбранной вкладке (повторный клик снимает фильтр → activeTab === null)
  // Фильтрация по вкладке + по дате (?date=YYYY-MM-DD) + по поиску (?q=...)

  // ✅ Функция фильтрации услуг по вкладке
  // ⭐ ИСПРАВЛЕНО: Для QR-записей с несколькими специалистами используем queue_numbers
  const filterServicesByDepartment = useCallback((appointment, departmentKey) => {
    // ⭐ SSOT: Используем централизованную функцию toServiceCode
    // Расширяем её для обратной совместимости с fuzzy matching
    const toServiceCode = (value) => {
      if (!value) return null;

      // Сначала пробуем SSOT резолвер
      const ssotResult = ssotToServiceCode(value);
      if (ssotResult) return ssotResult;

      // Fallback для fuzzy matching (legacy support)
      const normalized = String(value).toLowerCase().trim();
      for (const [key, code] of Object.entries(SPECIALTY_TO_CODE)) {
        if (normalized.includes(key) || key.includes(normalized)) {
          return code;
        }
      }

      // Ultimate fallback: первая буква + 01
      // ⚠️ ТОЛЬКО для известных категорий, не для произвольных кириллических букв
      const firstLetter = normalized.charAt(0).toUpperCase();
      if (/[A-Z]/i.test(firstLetter)) {
        // Только латинские буквы для кодов (K, D, S, L, P, C)
        return `${firstLetter}01`;
      }
      // Кириллические буквы: конвертируем известные, игнорируем остальные
      const ruToEn = { 'К': 'K', 'Д': 'D', 'С': 'S', 'Л': 'L', 'П': 'P' };
      const mappedLetter = ruToEn[firstLetter];
      if (mappedLetter) {
        return `${mappedLetter}01`;
      }
      // ⛔ Не генерируем коды из неизвестных кириллических букв (О, Е, А и т.д.)
      // Это предотвращает генерацию невалидных кодов вроде "О01"

      return null;
    };

    // ⭐ Для QR-записей с queue_numbers - собираем услуги из всех queue_numbers
    if (appointment.queue_numbers && Array.isArray(appointment.queue_numbers) && appointment.queue_numbers.length > 0) {

      // ⭐ Если НЕТ departmentKey (вкладка "Все отделения") - используем уже имеющиеся services
      if (!departmentKey) {
        // ✅ ИСПРАВЛЕНО: Используем appointment.services напрямую, т.к. они уже содержат правильные коды (K11, L02 и т.д.)
        // Раньше мы генерировали коды из specialty/service_name, что приводило к fallback на K01/L01
        if (appointment.services && Array.isArray(appointment.services) && appointment.services.length > 0) {
          return appointment.services;
        }

        // Fallback: только если services пустой, генерируем из queue_numbers
        const allCodes = [];
        const seenCodes = new Set();

        appointment.queue_numbers.forEach(qn => {
          // Приоритет 1: service_name
          const serviceNameCode = toServiceCode(qn.service_name);
          if (serviceNameCode && !seenCodes.has(serviceNameCode)) {
            allCodes.push(serviceNameCode);
            seenCodes.add(serviceNameCode);
            return;
          }

          // Приоритет 2: specialty
          const specialtyCode = toServiceCode(qn.specialty || qn.queue_tag);
          if (specialtyCode && !seenCodes.has(specialtyCode)) {
            allCodes.push(specialtyCode);
            seenCodes.add(specialtyCode);
          }
        });

        return allCodes.length > 0 ? allCodes : [];
      }

      // ⭐ Для конкретной вкладки - фильтруем из существующих services по категории
      // ✅ ИСПРАВЛЕНО: Используем appointment.services напрямую, фильтруя по категории отделения
      const departmentCodePrefixes = {
        'cardio': ['K'],  // K01, K11 и т.д. - все кардиоуслуги кроме ECG
        'echokg': ['K10', 'ECG'],  // Только ЭКГ (K10)
        'derma': ['D'],  // D01 и т.д. (только консультации, не D_PROC)
        'dental': ['S'],  // S01, S10 и т.д.
        'lab': ['L'],  // L01, L02, L11 и т.д.
        'procedures': ['P', 'C', 'D_PROC']  // P01, P02, C01, C05, D_PROC02 и т.д.
      };

      const allowedPrefixes = departmentCodePrefixes[departmentKey] || [];

      // ✅ Фильтруем существующие services по категории
      if (appointment.services && Array.isArray(appointment.services) && appointment.services.length > 0) {
        const filteredByDepartment = appointment.services.filter(serviceItem => {
          // ✅ ИСПРАВЛЕНО: Извлекаем код из объекта если это объект, иначе используем как строку
          // Backend может возвращать services как [{code: "L10", name: "Общий белок", ...}] или как ["L10"]
          const code = (typeof serviceItem === 'object' && serviceItem?.code)
            ? String(serviceItem.code).toUpperCase()
            : String(serviceItem).toUpperCase();

          // Специальная логика для echokg: только K10 и ECG коды
          if (departmentKey === 'echokg') {
            return code === 'K10' || code.startsWith('ECG');
          }

          // Специальная логика для cardio: все K-коды КРОМЕ K10 (ЭКГ)
          if (departmentKey === 'cardio') {
            return code.startsWith('K') && code !== 'K10';
          }

          // Для остальных отделений - проверяем по префиксу
          return allowedPrefixes.some(prefix => code.startsWith(prefix));
        });

        if (filteredByDepartment.length > 0) {
          return filteredByDepartment;
        }
      }

      // Fallback: если в services нет подходящих кодов, генерируем из queue_numbers (для старых записей)
      const tabToSpecialtyMap = {
        'cardio': ['cardiology', 'cardio', 'cardiolog'],
        'echokg': ['echokg', 'ecg', 'echo'],
        'derma': ['dermatology', 'derma', 'dermatolog'],
        'dental': ['stomatology', 'dentist', 'dental', 'stom'],
        'lab': ['laboratory', 'lab'],
        'procedures': ['procedures', 'procedure', 'cosmetology', 'physio']
      };

      const possibleSpecialties = tabToSpecialtyMap[departmentKey] || [departmentKey];

      const matchingQueue = appointment.queue_numbers.find(qn => {
        const qnSpecialty = (qn.specialty || qn.queue_tag || '').toLowerCase().trim();
        return possibleSpecialties.some(spec => qnSpecialty.includes(spec) || spec.includes(qnSpecialty));
      });

      if (matchingQueue) {
        const serviceNameCode = toServiceCode(matchingQueue.service_name);
        if (serviceNameCode) {
          return [serviceNameCode];
        }

        const specialtyCode = toServiceCode(matchingQueue.specialty || matchingQueue.queue_tag);
        if (specialtyCode) {
          return [specialtyCode];
        }
      }
    }

    // ⭐ Для обычных записей без queue_numbers
    if (!departmentKey) {
      return appointment.services;
    }

    // ⭐ Стандартная фильтрация по service_codes
    if (!appointment.services || !Array.isArray(appointment.services) || appointment.services.length === 0) {
      return appointment.services;
    }

    const appointmentServiceCodes = appointment.service_codes || [];
    const appointmentServices = appointment.services || [];

    // Создаем маппинг service -> service_code
    const serviceToCodeMap = new Map();

    appointmentServices.forEach((service, index) => {
      if (appointmentServiceCodes[index]) {
        serviceToCodeMap.set(service, String(appointmentServiceCodes[index]).toUpperCase());
        return;
      }

      if (services && typeof services === 'object') {
        for (const groupName in services) {
          const groupServices = services[groupName];
          if (Array.isArray(groupServices)) {
            if (typeof service === 'number' || (typeof service === 'string' && !isNaN(service))) {
              const serviceId = parseInt(service);
              const serviceByID = groupServices.find(s => s.id === serviceId);
              if (serviceByID && serviceByID.service_code) {
                serviceToCodeMap.set(service, String(serviceByID.service_code).toUpperCase());
                return;
              }
            }
            const serviceByName = groupServices.find(s => s.name === service);
            if (serviceByName && serviceByName.service_code) {
              serviceToCodeMap.set(service, String(serviceByName.service_code).toUpperCase());
              return;
            }
          }
        }
      }
    });

    // Маппинг категорий по вкладкам
    const departmentCategoryMapping = {
      'cardio': ['K', 'ECHO'],
      'echokg': ['ECG'],
      'derma': ['D', 'DERM', 'DERM_PROC'],
      'dental': ['S', 'DENT', 'STOM'],
      'lab': ['L'],
      'procedures': ['P', 'C', 'D_PROC']
    };

    const getServiceCategoryByCode = (serviceCode) => {
      if (!serviceCode) return null;
      const normalizedCode = String(serviceCode).toUpperCase();

      if (normalizedCode === 'K10' || normalizedCode === 'CARD_ECG' || normalizedCode.includes('ECG') || normalizedCode.includes('ЭКГ')) return 'ECG';
      if (normalizedCode === 'CARD_ECHO' || normalizedCode.includes('ECHO') || normalizedCode.includes('ЭХОКГ')) return 'ECHO';
      if (normalizedCode.match(/^P\d+$/)) return 'P';
      if (normalizedCode.match(/^D_PROC\d+$/)) return 'D_PROC';
      if (normalizedCode.match(/^C\d+$/)) return 'C';
      if (normalizedCode.match(/^K\d+$/) && normalizedCode !== 'K10') return 'K';
      if (normalizedCode.match(/^S\d+$/)) return 'S';
      if (normalizedCode.match(/^L\d+$/)) return 'L';
      if (normalizedCode === 'D01') return 'D';
      if (normalizedCode.startsWith('CONS_CARD')) return 'K';
      if (normalizedCode.startsWith('CONS_DERM') || normalizedCode.startsWith('DERMA_')) return 'DERM';
      if (normalizedCode.startsWith('CONS_DENT') || normalizedCode.startsWith('DENT_') || normalizedCode.startsWith('STOM_')) return 'DENT';
      if (normalizedCode.startsWith('LAB_')) return 'L';
      if (normalizedCode.startsWith('COSM_')) return 'C';
      if (normalizedCode.startsWith('PHYSIO_') || normalizedCode.startsWith('PHYS_')) return 'P';
      if (normalizedCode.startsWith('DERM_PROC_') || normalizedCode.startsWith('DERM_')) return 'D_PROC';
      if (normalizedCode.startsWith('CARD_') && !normalizedCode.includes('ECG')) return 'K';
      return null;
    };

    const targetCategoryCodes = departmentCategoryMapping[departmentKey] || [];

    const filteredServices = appointmentServices
      .filter((service) => {
        const serviceCode = serviceToCodeMap.get(service);
        if (!serviceCode) return false;
        const category = getServiceCategoryByCode(serviceCode);
        return targetCategoryCodes.includes(category);
      });

    return filteredServices;
  }, [services]);

  // ✅ filteredAppointments вычисляется здесь и сохраняется в ref
  const filteredAppointments = useMemo(() => {
    // ⭐ SSOT: Get queue_tags from loaded profiles instead of hardcoded mapping
    // queueProfiles is populated by ModernTabs via onProfilesLoaded callback
    const getQueueTagsForTab = (tabKey) => {
      if (!tabKey) return [];

      // Find profile by key
      const profile = queueProfiles.find(p => p.key === tabKey);
      if (profile && profile.queue_tags && profile.queue_tags.length > 0) {
        return profile.queue_tags;
      }

      // Fallback: use tabKey itself as the only tag
      // ⚠️ TEMPORARY ADAPTER: for backwards compatibility during transition
      return [tabKey];
    };

    // Если выбрана конкретная вкладка (не "Все отделения"), используем rawEntries с фильтрацией по queue_tag
    if (activeTab) {
      // ⭐ SSOT: queue_tags from API profiles, not hardcoded
      const possibleTags = getQueueTagsForTab(activeTab);

      // Фильтруем rawEntries по queue_tag вкладки
      const entriesForTab = (rawEntries && rawEntries.length > 0 ? rawEntries : appointments).filter(entry => {
        // Определяем queue_tag записи
        const entryQueueTag = (
          entry.queue_tag ||
          entry.specialty ||
          (entry.queue_numbers && entry.queue_numbers[0]?.queue_tag) ||
          ''
        ).toString().toLowerCase().trim();

        // Проверяем соответствие вкладке
        const matchesTab = possibleTags.some(tag => tag.toLowerCase() === entryQueueTag);
        if (!matchesTab) return false;

        // Фильтр по статусу
        if (statusFilter && entry.status !== statusFilter) return false;

        // Фильтр по поиску
        if (searchQuery) {
          const inFio = (entry.patient_fio || entry.patient_name || '').toLowerCase().includes(searchQuery);
          const inId = String(entry.id).includes(searchQuery);
          const phoneDigits = (entry.patient_phone || entry.phone || '').replace(/\D/g, '');
          const searchDigits = searchQuery.replace(/\D/g, '');
          const inPhone = phoneDigits.includes(searchDigits);
          if (!inFio && !inId && !inPhone) return false;
        }

        return true;
      });

      // Сортируем по queue_time ASC
      const sorted = entriesForTab.sort((a, b) => {
        const aTime = (a.queue_time ? new Date(a.queue_time) : new Date(a.created_at || 0)).getTime();
        const bTime = (b.queue_time ? new Date(b.queue_time) : new Date(b.created_at || 0)).getTime();
        return aTime - bTime;
      });

      logger.info('⭐ FIX 16: Вкладка', activeTab, '- найдено', sorted.length, 'записей из',
        rawEntries?.length || 0, 'rawEntries');

      // ⭐ FIX 16: Подробный лог queue_time для каждой entry
      sorted.forEach((entry, idx) => {
        logger.info(`  📌 Entry[${idx}]: id=${entry.id}, queue_tag=${entry.queue_tag}, queue_time=${entry.queue_time}, patient=${entry.patient_fio}`);
      });

      // Каждая entry уже содержит свой queue_time — никакого переопределения не нужно
      return sorted.map(entry => ({
        ...entry,
        // Нормализуем поля для совместимости с EnhancedAppointmentsTable
        patient_fio: entry.patient_fio || entry.patient_name || 'Неизвестный пациент',
        queue_number: entry.number || entry.queue_number,
        queue_numbers: entry.queue_numbers || [{
          number: entry.number,
          queue_tag: entry.queue_tag || entry.specialty,
          status: entry.status,
          queue_time: entry.queue_time
        }]
      }));
    }

    // Для вкладки "Все отделения" (activeTab === null или undefined) - агрегируем пациентов
    if (!activeTab) {
      // Сначала фильтруем по статусу, если задан
      const filtered = appointments.filter(appointment => {
        // Фильтр по статусу (если задан)
        if (statusFilter && appointment.status !== statusFilter) return false;
        return true;
      });

      // ⭐ ВАЖНО: Сортируем по queue_time ASC (согласно cursor.yaml), иначе по created_at
      filtered.sort((a, b) => {
        // Приоритет: queue_time > created_at
        const aTime = (a.queue_time ? new Date(a.queue_time) : (a.created_at ? new Date(a.created_at) : null))?.getTime() || 0;
        const bTime = (b.queue_time ? new Date(b.queue_time) : (b.created_at ? new Date(b.created_at) : null))?.getTime() || 0;
        if (aTime === bTime) {
          return (a.id || 0) - (b.id || 0);
        }
        return aTime - bTime; // От раннего к позднему (ASC)
      });

      // Затем агрегируем пациентов
      logger.info(`📊 Для вкладки "Все отделения": ${filtered.length} записей до агрегации`);
      const qrInFiltered = filtered.filter(a => a.source === 'online');
      logger.info(`🔍 QR-записей в фильтре: ${qrInFiltered.length}`);
      qrInFiltered.forEach(a => {
        logger.info(`  - ${a.patient_fio}: ${a.queue_numbers?.length || 0} queue_numbers`, a.queue_numbers);
      });

      const aggregatedPatients = aggregatePatientsForAllDepartments(filtered);
      logger.info(`📊 После агрегации: ${aggregatedPatients.length} пациентов`);

      // Применяем поиск к агрегированным данным
      if (searchQuery) {
        const searched = aggregatedPatients.filter(patient => {
          const inFio = (patient.patient_fio || '').toLowerCase().includes(searchQuery);

          // Поиск по ID записи
          const inId = String(patient.id).includes(searchQuery);

          // Улучшенный поиск по телефону
          const originalPhone = (patient.patient_phone || '').toLowerCase();
          const phoneDigits = originalPhone.replace(/\D/g, '');
          const searchDigits = searchQuery.replace(/\D/g, '');

          const inPhone = originalPhone.includes(searchQuery) ||
            phoneDigits.includes(searchDigits) ||
            (searchDigits.length >= 3 && phoneDigits.includes(searchDigits));

          // Поиск по услугам (теперь ищем в агрегированном списке)
          const inServices = Array.isArray(patient.services) && patient.services.some(s => String(s).toLowerCase().includes(searchQuery));

          return inFio || inPhone || inServices || inId;
        });
        // ✅ ИСПРАВЛЕНИЕ: Сортируем результат поиска по времени регистрации
        return searched.sort((a, b) => {
          const aTime = a.created_at ? new Date(a.created_at).getTime() : 0;
          const bTime = b.created_at ? new Date(b.created_at).getTime() : 0;
          if (aTime === bTime) {
            return (a.id || 0) - (b.id || 0);
          }
          return aTime - bTime;
        });
      }

      // ⭐ ВАЖНО: Сортируем агрегированных пациентов по queue_time ASC (согласно cursor.yaml)
      const sortedAggregated = aggregatedPatients.sort((a, b) => {
        // Приоритет: queue_time > created_at
        const aTime = (a.queue_time ? new Date(a.queue_time) : (a.created_at ? new Date(a.created_at) : null))?.getTime() || 0;
        const bTime = (b.queue_time ? new Date(b.queue_time) : (b.created_at ? new Date(b.created_at) : null))?.getTime() || 0;
        if (aTime === bTime) {
          return (a.id || 0) - (b.id || 0);
        }
        return aTime - bTime; // От раннего к позднему (ASC)
      });

      // ✅ ИСПРАВЛЕНО: Применяем правильное форматирование услуг для вкладки "Все отделения"
      // Это гарантирует, что для QR-записей будут показаны все коды услуг (K01, S01 и т.д.)
      return sortedAggregated.map(patient => ({
        ...patient,
        services: filterServicesByDepartment(patient, null)
      }));
    }

    // ⭐ ВАЖНО: Сортируем все записи по queue_time ASC (согласно cursor.yaml), иначе по created_at
    return appointments.sort((a, b) => {
      // Приоритет: queue_time > created_at
      const aTime = (a.queue_time ? new Date(a.queue_time) : (a.created_at ? new Date(a.created_at) : null))?.getTime() || 0;
      const bTime = (b.queue_time ? new Date(b.queue_time) : (b.created_at ? new Date(b.created_at) : null))?.getTime() || 0;
      if (aTime === bTime) {
        return (a.id || 0) - (b.id || 0);
      }
      return aTime - bTime; // От раннего к позднему (ASC)
    });
  }, [appointments, rawEntries, activeTab, statusFilter, searchQuery, isInDepartment, aggregatePatientsForAllDepartments, filterServicesByDepartment, queueProfiles]);

  // ✅ Сохраняем filteredAppointments в ref для использования в handleKeyDown
  filteredAppointmentsRef.current = filteredAppointments;

  // Мемоизированный компонент индикатора источника данных (для всех вкладок)
  const DataSourceIndicator = memo(({ count }) => {
    if (dataSource === 'demo') {
      return (
        <div style={{
          background: 'linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%)',
          color: 'white',
          padding: '8px 12px',
          borderRadius: '6px',
          marginBottom: '12px',
          fontSize: '14px',
          fontWeight: '500',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          textShadow: '0 1px 2px rgba(0, 0, 0, 0.5)'
        }}>
          <span>⚠️</span>
          <span>Показаны демо-данные. Проверьте подключение к серверу.</span>
          <button
            onClick={() => loadAppointments({ source: 'demo_refresh_button' })}
            style={{
              background: 'rgba(255, 255, 255, 0.2)',
              border: 'none',
              color: 'white',
              padding: '4px 8px',
              borderRadius: '4px',
              fontSize: '12px',
              cursor: 'pointer',
              marginLeft: 'auto'
            }}
          >
            🔄 Повторить
          </button>
        </div>
      );
    }

    if (dataSource === 'api') {
      return (
        <div style={{
          background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
          color: 'white',
          padding: '8px 12px',
          borderRadius: '6px',
          marginBottom: '12px',
          fontSize: '14px',
          fontWeight: '500',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          textShadow: '0 1px 2px rgba(0, 0, 0, 0.5)'
        }}>
          <span>✅</span>
          <span>Данные загружены с сервера</span>
          <span style={{ marginLeft: 'auto', fontSize: '12px', opacity: 0.9 }}>
            {count} из {paginationInfo.total} записей
          </span>
        </div>
      );
    }

    if (dataSource === 'loading') {
      return (
        <div style={{
          background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
          color: 'white',
          padding: '8px 12px',
          borderRadius: '6px',
          marginBottom: '12px',
          fontSize: '14px',
          fontWeight: '500',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          textShadow: '0 1px 2px rgba(0, 0, 0, 0.5)'
        }}>
          <span>🔄</span>
          <span>Загрузка данных...</span>
        </div>
      );
    }

    return null;
  });

  DataSourceIndicator.displayName = 'DataSourceIndicator';

  // Функция генерации CSV
  const generateCSV = (data) => {
    const headers = ['№', 'ФИО', 'Год рождения', 'Телефон', 'Услуги', 'Тип обращения', 'Вид оплаты', 'Стоимость', 'Статус'];
    const rows = data.map((row, index) => [
      index + 1,
      row.patient_fio || '',
      row.patient_birth_year || '',
      row.patient_phone || '',
      Array.isArray(row.services) ? row.services.join('; ') : row.services || '',
      row.visit_type || '',
      row.payment_type || '',
      row.cost || '',
      row.status || ''
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    return csvContent;
  };

  // Функция скачивания CSV
  const downloadCSV = (content, filename) => {
    const blob = new Blob(['\ufeff' + content], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };


  // Обработчик действий контекстного меню
  const handleContextMenuAction = useCallback(async (action, row) => {
    switch (action) {
      case 'view':
        setWizardEditMode(true);
        setWizardInitialData(row);
        setShowWizard(true);
        break;
      case 'edit':
        logger.info('Редактирование записи:', row);
        break;
      case 'in_cabinet':
        await updateAppointmentStatus(row.id, 'in_cabinet');
        toast.success('Пациент отправлен в кабинет');
        break;
      case 'call':
        await handleStartVisit(row);
        break;
      case 'complete':
        await updateAppointmentStatus(row.id, 'done');
        toast.success('Приём завершён');
        break;
      case 'payment':
        setPaymentDialog({ open: true, row, paid: false, source: 'context' });
        break;
      case 'print':
        setPrintDialog({ open: true, type: 'ticket', data: row });
        break;
      case 'reschedule':
        setRescheduleData(row);
        setShowSlotsModal(true);
        break;
      case 'cancel':
        setCancelDialog({ open: true, row, reason: '' });
        break;
      case 'call_patient':
        if (row.patient_phone) {
          window.open(`tel:${row.patient_phone}`);
        }
        break;
      case 'force_majeure':
        // Открываем модальное окно форс-мажора для специалиста
        setForceMajeureModal({
          open: true,
          specialistId: row.doctor_id || row.specialist_id || null,
          specialistName: row.doctor_name || row.specialist_name || 'Все специалисты'
        });
        break;
      default:
        logger.info('Неизвестное действие:', action);
        break;
    }
  }, [updateAppointmentStatus, handleStartVisit]);

  return (
    <div style={{ ...pageStyle, overflow: 'hidden' }} role="main" aria-label="Панель регистратора">
      <ToastContainer position="bottom-right" />


      {/* Skip to content link for screen readers */}
      <a
        href="#main-content"
        style={{
          position: 'absolute',
          left: '-9999px',
          top: '0',
          zIndex: 9999,
          padding: '8px 16px',
          background: 'var(--color-primary-600)',
          color: 'white',
          textDecoration: 'none',
          borderRadius: '0 0 4px 4px'
        }}
        onFocus={(e) => {
          e.target.style.left = '0';
        }}
        onBlur={(e) => {
          e.target.style.left = '-9999px';
        }}
      >
        Перейти к основному содержимому
      </a>

      {/* Современные вкладки */}
      {(!searchParams.get('view') || (searchParams.get('view') !== 'welcome' && searchParams.get('view') !== 'queue')) && (
        <div style={{
          margin: `0 ${'1rem'}`,
          maxWidth: 'none',
          width: 'calc(100vw - 32px)'
        }}>
          <ModernTabs
            activeTab={activeTab}
            onTabChange={setActiveTab}
            onProfilesLoaded={setQueueProfiles}  // ⭐ SSOT: Store profiles for filtering
            departmentStats={departmentStats}
            theme={theme}
            language={language}
            dynamicDepartments={dynamicDepartments}
          />
        </div>
      )}

      {/* Старые вкладки удалены - используется ModernTabs компонент */}

      {/* Основной контент без отступа сверху */}
      <div style={{ overflow: 'hidden' }}>
        {/* Экран приветствия по параметру view=welcome (с историей: календарь + поиск) */}
        {searchParams.get('view') === 'welcome' && (
          <AnimatedTransition type="fade" delay={100}>
            <Card variant="default" style={{
              margin: `0 ${'1rem'} ${'2rem'} ${'1rem'}`,
              maxWidth: 'none',
              width: 'calc(100vw - 32px)',
              backgroundColor: 'var(--mac-bg-toolbar)',
              border: '1px solid var(--mac-separator)',
              borderRadius: 'var(--mac-radius-lg)',
              backdropFilter: 'var(--mac-blur-medium)',
              WebkitBackdropFilter: 'var(--mac-blur-medium)'
            }}>
              <CardHeader style={{
                padding: 'var(--mac-spacing-8)',
                background: 'var(--mac-gradient-subtle)',
                borderBottom: '1px solid var(--mac-separator)'
              }}>
                <AnimatedTransition type="slide" direction="up" delay={200}>
                  <h1 style={{
                    margin: 0,
                    fontSize: '40px',
                    fontWeight: '700',
                    lineHeight: '1.2',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--mac-spacing-3)',
                    color: 'var(--mac-text-primary)',
                    fontFamily: '"SF Pro Display", -apple-system, BlinkMacSystemFont, "Helvetica Neue", system-ui, sans-serif',
                    letterSpacing: '-0.01em',
                    textRendering: 'optimizeLegibility'
                  }}>
                    {t('welcome')} в панель регистратора!
                    <Icon name="person" size="default" style={{ color: 'var(--mac-accent-blue)' }} />
                  </h1>
                </AnimatedTransition>
                <AnimatedTransition type="fade" delay={400}>
                  <div style={{
                    fontSize: '20px',
                    fontWeight: '600',
                    color: 'var(--mac-text-secondary)',
                    lineHeight: '1.4',
                    marginTop: 'var(--mac-spacing-3)',
                    fontFamily: '"SF Pro Text", -apple-system, BlinkMacSystemFont, "Helvetica Neue", system-ui, sans-serif',
                    letterSpacing: '0.01em',
                    opacity: 0.9
                  }}>
                    {new Date().toLocaleDateString(language === 'ru' ? 'ru-RU' : 'uz-UZ', {
                      weekday: 'long',
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })}
                  </div>
                </AnimatedTransition>
              </CardHeader>

              <CardContent>
                {/* Современная статистика */}
                <ModernStatistics
                  appointments={appointments}
                  departmentStats={departmentStats}
                  language={language}
                  selectedDate={showCalendar && historyDate ? historyDate : getLocalDateString()}
                  onExport={() => {
                    logger.info('Экспорт статистики');
                  }}
                  onRefresh={() => {
                    loadAppointments({ source: 'statistics_refresh' });
                  }}
                />

                {/* Панель управления и фильтров */}
                <AnimatedTransition type="fade" delay={800}>
                  <div style={{ marginBottom: 'var(--mac-spacing-8)' }}>
                    <AnimatedTransition type="slide" direction="up" delay={900}>
                      <h2 style={{
                        fontSize: 'var(--mac-font-size-xl)',
                        marginBottom: 'var(--mac-spacing-4)',
                        color: 'var(--mac-text-primary)',
                        fontWeight: 'var(--mac-font-weight-semibold)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--mac-spacing-2)'
                      }}>
                        <Icon name="gear" size="default" style={{ color: 'var(--mac-accent-blue)' }} />
                        Панель управления
                      </h2>
                    </AnimatedTransition>

                    {/* Быстрые действия */}
                    <AnimatedTransition type="fade" delay={1000}>
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                        gap: 'var(--mac-spacing-3)',
                        alignItems: 'stretch',
                        marginBottom: 'var(--mac-spacing-6)'
                      }}>
                        <AnimatedTransition type="scale" delay={1100}>
                          <Button
                            variant="primary"
                            size="default"
                            onClick={() => {
                              logger.info('Кнопка "Новая запись" нажата');
                              setWizardEditMode(false);  // ✅ Сброс режима
                              setWizardInitialData(null); // ✅ Сброс данных
                              setShowWizard(true);
                            }}
                            aria-label="Create new appointment"
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 'var(--mac-spacing-2)',
                              fontWeight: 'var(--mac-font-weight-semibold)'
                            }}
                          >
                            <Icon name="plus" size="small" style={{ color: 'white' }} />
                            {t('new_appointment')}
                          </Button>
                        </AnimatedTransition>

                        {/* Кнопка модуля оплаты */}
                        <AnimatedTransition type="scale" delay={1350}>
                          <Button
                            variant="secondary"
                            size="default"
                            onClick={() => setShowPaymentManager(true)}
                            aria-label="Open payment module"
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 'var(--mac-spacing-2)'
                            }}
                          >
                            <Icon name="creditcard" size="small" />
                            Модуль оплаты
                          </Button>
                        </AnimatedTransition>

                        <AnimatedTransition type="scale" delay={1400}>
                          <Button
                            variant="outline"
                            size="default"
                            onClick={() => {
                              logger.info('Кнопка "Экспорт CSV" нажата');
                              const csvContent = generateCSV(appointments);
                              const filename = `appointments_${getLocalDateString()}.csv`;
                              downloadCSV(csvContent, filename);
                              toast.success(`Экспортировано ${appointments.length} записей`);
                            }}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 'var(--mac-spacing-2)'
                            }}
                          >
                            <Icon name="square.and.arrow.up" size="small" />
                            {t('export_csv')}
                          </Button>
                        </AnimatedTransition>
                      </div>
                    </AnimatedTransition>

                    {/* Фильтры и навигация */}
                    <AnimatedTransition type="fade" delay={1500}>
                      <div style={{
                        background: 'var(--mac-bg-toolbar)',
                        borderRadius: 'var(--mac-radius-lg)',
                        padding: 'var(--mac-spacing-5)',
                        border: '1px solid var(--mac-separator)',
                        backdropFilter: 'var(--mac-blur-light)',
                        WebkitBackdropFilter: 'var(--mac-blur-light)'
                      }}>
                        <h3 style={{
                          fontSize: 'var(--mac-font-size-lg)',
                          marginBottom: 'var(--mac-spacing-4)',
                          color: 'var(--mac-text-primary)',
                          fontWeight: 'var(--mac-font-weight-semibold)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 'var(--mac-spacing-2)'
                        }}>
                          <Icon name="magnifyingglass" size="default" style={{ color: 'var(--mac-accent-blue)' }} />
                          Фильтры и навигация
                        </h3>

                        <div style={{
                          display: 'grid',
                          gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                          gap: 'var(--mac-spacing-3)',
                          alignItems: 'stretch'
                        }}>
                          <Button
                            variant={showCalendar ? 'warning' : 'outline'}
                            size="default"
                            onClick={() => {
                              logger.info('Кнопка "Календарь" нажата');
                              setShowCalendar(!showCalendar);
                            }}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 'var(--mac-spacing-2)'
                            }}
                          >
                            <Icon name="magnifyingglass" size="small" style={{ color: showCalendar ? 'white' : 'var(--mac-text-primary)' }} />
                            Календарь
                          </Button>

                          <Button
                            variant="success"
                            size="default"
                            onClick={() => window.location.href = '/registrar-panel?status=queued'}
                            style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}
                          >
                            <Icon name="checkmark.circle" size="small" style={{ color: 'white' }} />
                            Активная очередь
                          </Button>

                          <Button
                            variant="primary"
                            size="default"
                            onClick={() => window.location.href = '/registrar-panel?status=paid_pending'}
                            style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}
                          >
                            <Icon name="creditcard" size="small" style={{ color: 'white' }} />
                            Ожидают оплаты
                          </Button>

                          <Button
                            variant="outline"
                            size="default"
                            onClick={() => window.location.href = '/registrar-panel'}
                            style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}
                          >
                            <Icon name="eye" size="small" />
                            Все записи
                          </Button>

                          <Button
                            variant="outline"
                            size="default"
                            onClick={() => window.location.href = '/registrar-panel?view=queue'}
                            style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}
                          >
                            <Icon name="bell" size="small" />
                            Онлайн-очередь
                          </Button>

                          <Button
                            variant="outline"
                            size="default"
                            onClick={() => { loadAppointments({ source: 'manual_refresh_button' }); toast.success('Данные обновлены'); }}
                            style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}
                          >
                            <Icon name="gear" size="small" />
                            Обновить данные
                          </Button>
                        </div>

                        {/* Календарный виджет */}
                        {showCalendar && (
                          <div style={{
                            marginTop: 'var(--mac-spacing-4)',
                            padding: 'var(--mac-spacing-5)',
                            background: 'var(--mac-bg-primary)',
                            borderRadius: 'var(--mac-radius-lg)',
                            border: '1px solid var(--mac-separator)',
                            boxShadow: 'var(--mac-shadow-sm)'
                          }}>
                            <div style={{
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 'var(--mac-spacing-3)'
                            }}>
                              <label style={{
                                fontSize: 'var(--mac-font-size-sm)',
                                fontWeight: 'var(--mac-font-weight-semibold)',
                                color: 'var(--mac-text-primary)',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 'var(--mac-spacing-2)'
                              }}>
                                <Icon name="magnifyingglass" size="small" style={{ color: 'var(--mac-text-secondary)' }} />
                                Выберите дату для просмотра истории:
                              </label>
                              <Input
                                type="date"
                                label=""
                                value={tempDateInput}
                                onChange={(e) => {
                                  setTempDateInput(e.target.value);
                                  logger.info('Введена дата (debounced):', e.target.value);
                                }}
                                onBlur={(e) => {
                                  if (e.target.value && e.target.value !== historyDate) {
                                    logger.info('📅 Date input blur - applying immediately:', e.target.value);
                                    setHistoryDate(e.target.value);
                                  }
                                }}
                              />
                              <div style={{
                                display: 'flex',
                                gap: '8px',
                                flexWrap: 'wrap'
                              }}>
                                <button
                                  type="button"
                                  onClick={() => {
                                    const today = getLocalDateString();
                                    setTempDateInput(today);
                                    setHistoryDate(today);
                                  }}
                                  style={{
                                    padding: '8px 12px',
                                    borderRadius: '6px',
                                    fontSize: '13px',
                                    background: theme === 'light' ? '#f3f4f6' : '#4b5563',
                                    color: textColor,
                                    border: 'none',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s'
                                  }}
                                >
                                  Сегодня
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    const yesterdayStr = getYesterdayDateString();
                                    setTempDateInput(yesterdayStr);
                                    setHistoryDate(yesterdayStr);
                                  }}
                                  style={{
                                    padding: '8px 12px',
                                    borderRadius: '6px',
                                    fontSize: '13px',
                                    background: theme === 'light' ? '#f3f4f6' : '#4b5563',
                                    color: textColor,
                                    border: 'none',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s'
                                  }}
                                >
                                  Вчера
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    const weekAgo = new Date();
                                    weekAgo.setDate(weekAgo.getDate() - 7);
                                    const weekAgoStr = getLocalDateString(weekAgo);
                                    setTempDateInput(weekAgoStr);
                                    setHistoryDate(weekAgoStr);
                                  }}
                                  style={{
                                    padding: '8px 12px',
                                    borderRadius: '6px',
                                    fontSize: '13px',
                                    background: theme === 'light' ? '#f3f4f6' : '#4b5563',
                                    color: textColor,
                                    border: 'none',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s'
                                  }}
                                >
                                  Неделю назад
                                </button>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </AnimatedTransition>
                  </div>
                </AnimatedTransition>

                {/* История записей */}
                <div>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: 'var(--mac-spacing-4)',
                    flexWrap: 'wrap',
                    gap: 'var(--mac-spacing-3)'
                  }}>
                    <h3 style={{
                      fontSize: 'var(--mac-font-size-xl)',
                      margin: 0,
                      color: 'var(--mac-text-primary)',
                      fontWeight: 'var(--mac-font-weight-semibold)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 'var(--mac-spacing-2)'
                    }}>
                      <Icon name="eye" size="default" style={{ color: 'var(--mac-accent-blue)' }} />
                      История записей
                    </h3>
                    {showCalendar && (
                      <Badge variant="secondary" style={{
                        fontSize: 'var(--mac-font-size-sm)',
                        fontWeight: 'var(--mac-font-weight-medium)',
                        padding: 'var(--mac-spacing-2) var(--mac-spacing-3)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 'var(--mac-spacing-2)'
                      }}>
                        <Icon name="magnifyingglass" size="small" />
                        {new Date(historyDate).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })}
                      </Badge>
                    )}
                  </div>
                  <div style={{
                    background: 'var(--mac-bg-toolbar)',
                    border: '1px solid var(--mac-separator)',
                    borderRadius: 'var(--mac-radius-lg)',
                    padding: 'var(--mac-spacing-5)',
                    backdropFilter: 'var(--mac-blur-light)',
                    WebkitBackdropFilter: 'var(--mac-blur-light)'
                  }}>
                    {/* Индикатор источника данных */}
                    {appointments.length > 0 && <DataSourceIndicator count={appointments.length} />}

                    {/* ✅ ДОБАВЛЕНО: Сообщение при пустой очереди */}
                    {(() => {
                      const token = localStorage.getItem('auth_token');
                      const isNoToken = !token;
                      const isEmptyQueue = !appointmentsLoading && dataSource === 'api' && filteredAppointments.length === 0;

                      logger.info('🎯 Empty state render check:', {
                        appointmentsLoading,
                        dataSource,
                        filteredLength: filteredAppointments.length,
                        appointmentsLength: appointments.length,
                        hasToken: !!token,
                        isNoToken,
                        isEmptyQueue,
                        shouldShow: isEmptyQueue
                      });

                      return isEmptyQueue;
                    })() && (
                        <div style={{
                          padding: '60px 20px',
                          textAlign: 'center',
                          background: cardBg,
                          borderRadius: '12px',
                          border: `1px solid ${borderColor}`
                        }}>
                          <div style={{
                            fontSize: '48px',
                            marginBottom: '16px',
                            opacity: 0.3
                          }}>
                            {!localStorage.getItem('auth_token') ? '🔐' : '📋'}
                          </div>
                          <h3 style={{
                            fontSize: '20px',
                            fontWeight: '600',
                            color: textColor,
                            marginBottom: '8px'
                          }}>
                            {!localStorage.getItem('auth_token') ? 'Сессия истекла' : 'Очередь пуста'}
                          </h3>
                          <p style={{
                            fontSize: '16px',
                            color: textColor,
                            opacity: 0.7,
                            marginBottom: '24px',
                            lineHeight: '1.5'
                          }}>
                            {!localStorage.getItem('auth_token')
                              ? 'Нажмите "Войти снова", чтобы обновить данные.'
                              : 'На сегодня нет записей в очереди.'}
                          </p>

                          {/* Кнопки действий */}
                          {!localStorage.getItem('auth_token') && (
                            <div style={{
                              display: 'flex',
                              gap: '12px',
                              justifyContent: 'center',
                              flexWrap: 'wrap'
                            }}>
                              <button
                                onClick={() => {
                                  // Перенаправляем на страницу входа
                                  window.location.href = '/login';
                                }}
                                style={{
                                  padding: '12px 24px',
                                  background: '#3b82f6',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '8px',
                                  fontSize: '14px',
                                  fontWeight: '500',
                                  cursor: 'pointer',
                                  transition: 'all 0.2s'
                                }}
                                onMouseOver={(e) => e.target.style.background = '#2563eb'}
                                onMouseOut={(e) => e.target.style.background = '#3b82f6'}
                              >
                                🔑 Войти снова
                              </button>

                              <button
                                onClick={() => {
                                  // Обновляем данные
                                  loadAppointments({ source: 'manual_refresh_button' });
                                }}
                                style={{
                                  padding: '12px 24px',
                                  background: '#10b981',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '8px',
                                  fontSize: '14px',
                                  fontWeight: '500',
                                  cursor: 'pointer',
                                  transition: 'all 0.2s'
                                }}
                                onMouseOver={(e) => e.target.style.background = '#059669'}
                                onMouseOut={(e) => e.target.style.background = '#10b981'}
                              >
                                🔄 Обновить данные
                              </button>

                              <button
                                onClick={() => {
                                  // Перезапускаем приложение
                                  window.location.reload();
                                }}
                                style={{
                                  padding: '12px 24px',
                                  background: '#6b7280',
                                  color: 'white',
                                  border: 'none',
                                  borderRadius: '8px',
                                  fontSize: '14px',
                                  fontWeight: '500',
                                  cursor: 'pointer',
                                  transition: 'all 0.2s'
                                }}
                                onMouseOver={(e) => e.target.style.background = '#4b5563'}
                                onMouseOut={(e) => e.target.style.background = '#6b7280'}
                              >
                                🔄 Перезапустить приложение
                              </button>
                            </div>
                          )}
                          <p style={{
                            fontSize: '14px',
                            color: textColor,
                            marginBottom: '24px'
                          }}>
                            {activeTab
                              ? `Сегодня нет записей в отделении ${activeTab === 'cardio' ? 'Кардиология' : activeTab === 'derma' ? 'Дерматология' : activeTab === 'dental' ? 'Стоматология' : activeTab === 'lab' ? 'Лаборатория' : activeTab}`
                              : 'Сегодня пока нет записей'}
                          </p>
                          <Button
                            variant="primary"
                            onClick={() => {
                              setWizardEditMode(false);  // ✅ Сброс режима
                              setWizardInitialData(null); // ✅ Сброс данных
                              setShowWizard(true);
                            }}
                            style={{
                              padding: '12px 24px',
                              fontSize: '14px'
                            }}
                          >
                            ➕ Создать первую запись
                          </Button>
                        </div>
                      )}

                    {/* Таблица отображается только если есть данные */}
                    {(appointmentsLoading || filteredAppointments.length > 0) && (
                      <EnhancedAppointmentsTable
                        data={filteredAppointments}
                        rawEntries={rawEntries}  // ⭐ SSOT FIX: Сырые данные для полного Tooltip
                        loading={appointmentsLoading}
                        theme={theme}
                        language={language}
                        selectedRows={appointmentsSelected}
                        outerBorder={true}
                        services={services}
                        showCheckboxes={false}  // ✅ Отключаем чекбоксы для регистратуры
                        onRowSelect={(id, checked) => {
                          const newSelected = new Set(appointmentsSelected);
                          if (checked) {
                            newSelected.add(id);
                          } else {
                            newSelected.delete(id);
                          }
                          setAppointmentsSelected(newSelected);
                        }}
                        onRowClick={(row) => {
                          logger.info('Открыть детали записи:', row);
                          // Здесь можно открыть модальное окно с деталями записи
                        }}
                        onActionClick={(action, row, event) => {
                          switch (action) {
                            case 'view':
                              logger.info('Просмотр записи:', row);
                              setWizardEditMode(true);
                              setWizardInitialData(row);
                              setShowWizard(true);
                              break;
                            case 'edit':
                              logger.info('[RegistrarPanel] Открытие мастера редактирования для:', row.patient_fio || row.patient_name);
                              setWizardEditMode(true);
                              setWizardInitialData(row);
                              setShowWizard(true);
                              break;
                            case 'payment':
                              logger.info('Открытие модального окна оплаты для записи (welcome):', row);
                              setPaymentDialog({ open: true, row, paid: false, source: 'welcome' });
                              break;
                            case 'in_cabinet':
                              logger.info('Отправка пациента в кабинет (welcome):', row);
                              updateAppointmentStatus(row.id, 'in_cabinet');
                              break;
                            case 'call':
                              logger.info('Вызов пациента (welcome):', row);
                              handleStartVisit(row);
                              break;
                            case 'complete':
                              logger.info('Завершение приёма (welcome):', row);
                              updateAppointmentStatus(row.id, 'done');
                              break;
                            case 'print':
                              logger.info('Печать талона (welcome):', row);
                              setPrintDialog({ open: true, type: 'ticket', data: row });
                              break;
                            case 'more': {
                              // Показать контекстное меню с дополнительными действиями
                              const rect = event?.target?.getBoundingClientRect();
                              setContextMenu({
                                open: true,
                                row,
                                position: {
                                  x: rect?.right || event?.clientX || 0,
                                  y: rect?.top || event?.clientY || 0
                                }
                              });
                              break;
                            }
                            default:
                              break;
                          }
                        }}
                      />
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </AnimatedTransition>
        )}

        {/* Онлайн-очередь по параметру view=queue */}
        {searchParams.get('view') === 'queue' && (
          <AnimatedTransition type="fade" delay={100}>
            <Card variant="default" style={{ margin: `0 ${getSpacing('xl')} ${getSpacing('xl')} ${getSpacing('xl')}` }}>
              <CardHeader>
                <AnimatedTransition type="slide" direction="up" delay={200}>
                  <h1 style={{
                    margin: 0,
                    fontSize: getFontSize('3xl'),
                    fontWeight: '400',
                    lineHeight: '1.25',
                    display: 'flex',
                    alignItems: 'center',
                    gap: getSpacing('sm'),
                    color: getColor('textPrimary')
                  }}>
                    📱 Онлайн-очередь
                  </h1>
                </AnimatedTransition>
                <AnimatedTransition type="fade" delay={400}>
                  <div style={{
                    fontSize: getFontSize('lg'),
                    opacity: 0.9,
                    lineHeight: '1.5',
                    color: getColor('textSecondary')
                  }}>
                    Управление онлайн-записью и QR кодами для очереди
                  </div>
                </AnimatedTransition>
              </CardHeader>

              <CardContent>
                <ModernQueueManager
                  selectedDate={searchParams.get('date') || getLocalDateString()}
                  selectedDoctor={searchParams.get('doctor') || selectedDoctor?.id?.toString() || ''}
                  searchQuery={searchParams.get('q') || ''}
                  onQueueUpdate={loadAppointments}
                  onDateChange={(newDate) => {
                    logger.info('📅 RegistrarPanel received date change:', newDate);
                    const newParams = new URLSearchParams(searchParams);
                    newParams.set('date', newDate);
                    setSearchParams(newParams);
                  }}
                  onDoctorChange={(newDoctorId) => {
                    logger.info('👨‍⚕️ RegistrarPanel received doctor change:', newDoctorId);
                    const newParams = new URLSearchParams(searchParams);
                    newParams.set('doctor', newDoctorId);
                    setSearchParams(newParams);
                  }}
                  language={language}
                  theme={theme}
                  doctors={doctors}
                />
              </CardContent>
            </Card>
          </AnimatedTransition>
        )}

        {/* Основная панель с записями */}
        {(!searchParams.get('view') || (searchParams.get('view') !== 'welcome' && searchParams.get('view') !== 'queue')) && (
          <div
            id="main-content"
            role="tabpanel"
            aria-labelledby={activeTab ? `${activeTab}-tab` : undefined}
            style={{
              ...tableContainerStyle,
              // Убираем отрицательный отступ для идеальной стыковки с вкладками
              margin: `0 ${isMobile ? '1rem' : '1rem'} ${'2rem'} ${isMobile ? '1rem' : '1rem'}`,
              borderRadius: isMobile ? '0 0 12px 12px' : '0 0 20px 20px',
              maxWidth: 'none',
              width: 'calc(100vw - 32px)'
            }}>
            <div style={{
              ...tableContentStyle,
              padding: isMobile ? '0.5rem' : '1rem'
            }}>

              {/* Массовые действия */}
              {appointmentsSelected.size > 0 && (
                <div style={{
                  display: 'flex',
                  gap: isMobile ? '0.25rem' : '12px',
                  alignItems: 'center',
                  padding: isMobile ? '0.5rem' : '16px',
                  background: theme === 'light' ? '#f8f9fa' : '#374151',
                  borderRadius: isMobile ? '6px' : '8px',
                  flexWrap: isMobile ? 'wrap' : 'nowrap'
                }}>
                  <span style={{ fontWeight: 600, marginRight: '12px' }}>
                    🎯 {t('bulk_actions')} ({appointmentsSelected.size}):
                  </span>
                  <button
                    className="clinic-button clinic-button-success interactive-element hover-lift ripple-effect action-button-hover focus-ring"
                    style={{
                      padding: '8px 12px',
                      borderRadius: 8,
                      fontSize: 14,
                      cursor: 'pointer',
                      pointerEvents: 'auto'
                    }}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      logger.info('Кнопка "Подтвердить" нажата через onMouseDown');
                      handleBulkAction('confirmed');
                    }}
                  >
                    ✅ {!isMobile && t('confirm')}
                  </button>
                  <button
                    className="clinic-button clinic-button-outline interactive-element hover-lift ripple-effect magnetic-hover focus-ring"
                    style={{
                      padding: '8px 12px',
                      borderRadius: 8,
                      fontSize: 14,
                      cursor: 'pointer',
                      pointerEvents: 'auto'
                    }}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      logger.info('Кнопка "Отменить" нажата через onMouseDown');
                      const reason = prompt(t('reason'));
                      if (reason) handleBulkAction('cancelled', reason);
                    }}
                  >
                    ❌ {!isMobile && t('cancel')}
                  </button>
                  <button
                    className="clinic-button clinic-button-outline interactive-element hover-lift ripple-effect magnetic-hover focus-ring"
                    style={{
                      padding: '8px 12px',
                      borderRadius: 8,
                      fontSize: 14,
                      cursor: 'pointer',
                      pointerEvents: 'auto'
                    }}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      logger.info('Кнопка "Неявка" нажата через onMouseDown');
                      handleBulkAction('no_show');
                    }}
                  >
                    ⚠️ {!isMobile && t('no_show')}
                  </button>
                </div>
              )}

              {/* Таблица записей */}
              {appointmentsLoading ? (
                <AnimatedLoader.TableSkeleton rows={8} columns={10} />
              ) : filteredAppointments.length === 0 && dataSource === 'api' ? (
                <div style={{
                  padding: '60px 20px',
                  textAlign: 'center',
                  background: cardBg,
                  borderRadius: '12px',
                  border: `1px solid ${borderColor}`
                }}>
                  <div style={{
                    fontSize: '48px',
                    marginBottom: '16px',
                    opacity: 0.3
                  }}>
                    📋
                  </div>
                  <h3 style={{
                    fontSize: '20px',
                    fontWeight: '600',
                    color: textColor,
                    marginBottom: '8px'
                  }}>
                    Очередь пуста
                  </h3>
                  <p style={{
                    fontSize: '14px',
                    color: textColor,
                    opacity: 0.7,
                    marginBottom: '24px'
                  }}>
                    {activeTab
                      ? `Сегодня нет записей в отделении ${activeTab === 'cardio' ? 'Кардиология' : activeTab === 'derma' ? 'Дерматология' : activeTab === 'dental' ? 'Стоматология' : activeTab === 'lab' ? 'Лаборатория' : activeTab}`
                      : 'Сегодня пока нет записей'}
                  </p>
                  <Button
                    variant="primary"
                    onClick={() => setShowWizard(true)}
                    style={{
                      padding: '12px 24px',
                      fontSize: '14px'
                    }}
                  >
                    ➕ Создать первую запись
                  </Button>
                </div>
              ) : filteredAppointments.length === 0 ? (
                <div style={{ padding: 24, textAlign: 'center', opacity: 0.7 }}>
                  {t('empty_table')}
                </div>
              ) : (
                <EnhancedAppointmentsTable
                  data={filteredAppointments}
                  loading={appointmentsLoading}
                  theme={theme}
                  language={language}
                  selectedRows={appointmentsSelected}
                  outerBorder={false}
                  services={services}
                  showCheckboxes={false}  // ✅ Отключаем чекбоксы для регистратуры
                  onRowSelect={(id, checked) => {
                    const newSelected = new Set(appointmentsSelected);
                    if (checked) {
                      newSelected.add(id);
                    } else {
                      newSelected.delete(id);
                    }
                    setAppointmentsSelected(newSelected);
                  }}
                  onRowClick={(row) => {
                    logger.info('Открыть детали записи:', row);
                    // Здесь можно открыть модальное окно с деталями записи
                  }}
                  onActionClick={(action, row, event) => {
                    switch (action) {
                      case 'view':
                        logger.info('Просмотр записи:', row);
                        setWizardEditMode(true);
                        setWizardInitialData(row);
                        setShowWizard(true);
                        break;
                      case 'edit':
                        logger.info('[RegistrarPanel] Открытие мастера редактирования для:', row.patient_fio || row.patient_name);
                        setWizardEditMode(true);
                        setWizardInitialData(row);
                        setShowWizard(true);
                        break;
                      case 'payment':
                        logger.info('Открытие модального окна оплаты для записи:', row);
                        setPaymentDialog({ open: true, row, paid: false, source: 'table' });
                        break;
                      case 'in_cabinet':
                        logger.info('Отправка пациента в кабинет:', row);
                        updateAppointmentStatus(row.id, 'in_cabinet');
                        break;
                      case 'call':
                        logger.info('Вызов пациента:', row);
                        handleStartVisit(row);
                        break;
                      case 'complete':
                        logger.info('Завершение приёма:', row);
                        updateAppointmentStatus(row.id, 'done');
                        break;
                      case 'print':
                        logger.info('Печать талона:', row);
                        setPrintDialog({ open: true, type: 'ticket', data: row });
                        break;
                      case 'more': {
                        // Показать контекстное меню с дополнительными действиями
                        const rect = event?.target?.getBoundingClientRect();
                        setContextMenu({
                          open: true,
                          row,
                          position: {
                            x: rect?.right || event?.clientX || 0,
                            y: rect?.top || event?.clientY || 0
                          }
                        });
                        break;
                      }
                      default:
                        break;
                    }
                  }}
                />
              )}

              {/* Кнопка загрузки дополнительных записей */}
              {paginationInfo.hasMore && (
                <div style={{
                  display: 'flex',
                  justifyContent: 'center',
                  padding: '16px',
                  borderTop: `1px solid ${theme === 'light' ? '#e5e7eb' : '#374151'}`
                }}>
                  <button
                    onClick={loadMoreAppointments}
                    disabled={paginationInfo.loadingMore}
                    style={{
                      padding: '12px 24px',
                      borderRadius: '8px',
                      border: 'none',
                      background: paginationInfo.loadingMore
                        ? '#9ca3af'
                        : 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
                      color: 'white',
                      fontSize: '14px',
                      fontWeight: '500',
                      cursor: paginationInfo.loadingMore ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      transition: 'all 0.2s ease',
                      boxShadow: '0 2px 4px rgba(59, 130, 246, 0.3)'
                    }}
                  >
                    {paginationInfo.loadingMore ? (
                      <>
                        <div style={{
                          width: '16px',
                          height: '16px',
                          border: '2px solid rgba(255,255,255,0.3)',
                          borderTop: '2px solid white',
                          borderRadius: '50%',
                          animation: 'spin 1s linear infinite'
                        }} />
                        Загрузка...
                      </>
                    ) : (
                      <>
                        📥 Загрузить еще
                      </>
                    )}
                  </button>
                </div>
              )}

              {/* Старая таблица и legacy-конфигурация удалены - используется EnhancedAppointmentsTable */}
            </div>
          </div>
        )}
      </div> {/* Закрытие скроллируемого контента */}

      {/* Мастер создания записи */}

      {/* Современные диалоги */}
      <CancelDialog
        isOpen={cancelDialog.open}
        onClose={() => setCancelDialog({ open: false, row: null, reason: '' })}
        appointment={cancelDialog.row}
        onCancel={async (appointmentId, reason) => {
          // ✅ FIX: Call backend to cancel visit OR appointment OR queue entry
          // Supports cancelling multiple aggregated IDs (for multi-QR entries)

          // ⭐ TODO: BATCH API MIGRATION
          // После тестирования batch API замените текущую логику на:
          // const patientId = data?.patient_id;
          // const date = formatDateForAPI(data?.date);
          // if (patientId && date) {
          //   const result = await cancelAllPatientEntries(patientId, date, reason);
          //   if (result.success) { ... }
          // }
          // См. docs/BATCH_UPDATE_ARCHITECTURE.md

          try {
            const data = appointmentId === cancelDialog.row?.id ? cancelDialog.row : appointments.find(a => a.id === appointmentId);
            const recordType = data?.record_type || 'visit';

            // Определяем список ID для отмены (если это агрегированная запись - отменяем все)
            const idsToCancel = data?.aggregated_ids?.length > 0 ? data.aggregated_ids : [appointmentId];

            logger.info(`🔍 Отмена записи(ей). IDs: [${idsToCancel.join(', ')}]`, {
              recordType,
              source: data?.source,
              fullData: data,
              idsToCancel
            });

            // Функция отмены одной записи
            const cancelSingleRecord = async (targetId) => {
              const tryCancelVisit = async () => {
                await api.post(`/visits/${targetId}/status`, null, {
                  params: { status_new: 'canceled' }
                });
              };

              const tryCancelOnlineQueue = async () => {
                await api.post(`/online-queue/entries/${targetId}/cancel`);
              };

              const tryCancelAppointment = async () => {
                try {
                  await api.put(`/appointments/${targetId}`, { status: 'canceled' });
                } catch (e) {
                  logger.warn('PUT failed, trying DELETE for appointment cancellation');
                  await api.delete(`/appointments/${targetId}`);
                }
              };

              if (recordType === 'visit') {
                try {
                  await tryCancelVisit();
                } catch (visitError) {
                  if (visitError.response?.status === 404) {
                    logger.warn(`⚠️ Попытка отмены как 'visit' вернула 404. Пробуем как 'online_queue' (ID=${targetId})`);
                    await tryCancelOnlineQueue();
                  } else {
                    throw visitError;
                  }
                }
              } else if (recordType === 'appointment') {
                await tryCancelAppointment();
              } else if (recordType === 'online_queue') {
                await tryCancelOnlineQueue();
              } else {
                // Fallback default strategy
                try {
                  await tryCancelVisit();
                } catch (err) {
                  if (err.response?.status === 404) {
                    logger.warn('Fallback visit cancel failed 404, trying online_queue...');
                    await tryCancelOnlineQueue();
                  } else {
                    throw err;
                  }
                }
              }
            };

            // Выполняем отмену для всех ID
            // Используем Promise.allSettled или loop для попытки отмены всех
            // Для надежности используем последовательную отмену
            const cancelResults = [];
            for (const id of idsToCancel) {
              try {
                await cancelSingleRecord(id);
                cancelResults.push({ id, success: true });
              } catch (err) {
                // ✅ FIX: Не прерываем цикл при 404 (запись уже отменена или не существует)
                if (err.response?.status === 404) {
                  logger.warn(`⚠️ ID ${id} не найден (возможно уже отменён), продолжаем...`);
                  cancelResults.push({ id, success: true, alreadyCancelled: true });
                } else {
                  logger.error(`❌ Ошибка отмены ID ${id}:`, err);
                  cancelResults.push({ id, success: false, error: err });
                }
              }
            }

            const successCount = cancelResults.filter(r => r.success).length;
            const failCount = cancelResults.filter(r => !r.success).length;

            if (failCount > 0) {
              logger.warn(`⚠️ Отменено ${successCount}/${idsToCancel.length} записей, ${failCount} ошибок`);
              toast.warning(`Отменено ${successCount} из ${idsToCancel.length} услуг`);
            } else {
              logger.info(`✅ Все ${successCount} записи успешно отменены на сервере`);
            }
          } catch (error) {
            logger.error('❌ Критическая ошибка отмены визита на сервере:', error);

            // Если это 404 после всех попыток
            if (error.response?.status === 404) {
              toast.error(`Ошибка: Запись ${appointmentId} не найдена в базе данных`);
            } else {
              toast.error('Не удалось обновить статус на сервере: ' + (error.message || 'Unknown error'));
            }
            // Don't return here, still update locally to remove from view or let the user know
          }

          // Локальное обновление статуса (для всех ID)
          const data = appointmentId === cancelDialog.row?.id ? cancelDialog.row : appointments.find(a => a.id === appointmentId);
          const idsToCancel = data?.aggregated_ids?.length > 0 ? data.aggregated_ids : [appointmentId];

          setAppointments(prev => prev.map(apt =>
            idsToCancel.includes(apt.id) ? {
              ...apt,
              status: 'canceled',
              _locallyModified: true,
              _cancelReason: reason
            } : apt
          ));

          // Refresh data to ensure consistency
          setTimeout(() => loadAppointments({ silent: true, source: 'cancel_complete' }), 500);
        }}
      />

      <PaymentDialog
        isOpen={paymentDialog.open}
        onClose={() => setPaymentDialog({ open: false, row: null, paid: false, source: null })}
        appointment={paymentDialog.row}
        onPaymentSuccess={async () => {
          // ✅ ИСПРАВЛЕНО: используем реальный API вызов через handlePayment
          const appointment = paymentDialog.row;
          if (appointment) {
            const updated = await handlePayment(appointment);
            if (updated) {
              // Статус уже правильно установлен в handlePayment (status: 'queued')
              logger.info('PaymentDialog: Оплата успешна, статус обновлен:', updated);
            }
          }
        }}
        onPrintTicket={(appointment) => {
          setPrintDialog({
            open: true,
            type: 'ticket',
            data: appointment
          });
        }}
      />

      {/* Модальное окно редактирования пациента */}
      {/* ✨ ЗАКОММЕНТИРОВАНО: Теперь используется AppointmentWizardV2 для редактирования */}
      {/*
      {editPatientModal.open && (
        <EditPatientModal
          isOpen={editPatientModal.open}
          onClose={() => setEditPatientModal({ open: false, patient: null })}
          patient={editPatientModal.patient}
          onSave={async () => {
            // Обновляем список записей после сохранения
            logger.info('[RegistrarPanel] EditPatientModal: onSave вызван, обновляем список');
            await loadAppointments({ source: 'edit_patient_save', silent: false });
          }}
          theme={{ isDark, getColor, getSpacing, getFontSize }}
        />
      )}
      */}

      <PrintDialog
        isOpen={printDialog.open}
        onClose={() => setPrintDialog({ open: false, type: '', data: null })}
        documentType={printDialog.type}
        documentData={printDialog.data}
        onPrint={async (printerName, docType, docData) => {
          logger.info('Printing:', { printerName, docType, docData });
          // Здесь можно добавить реальную логику печати
        }}
      />

      {/* ✅ Используется только новый мастер (V2) */}
      <AppointmentWizardV2
        isOpen={showWizard}
        editMode={wizardEditMode}              // ✨ НОВОЕ: Передаем режим
        initialData={wizardInitialData}        // ✨ НОВОЕ: Передаем данные
        activeTab={activeTab}                   // ✅ ПЕРЕДАЕМ activeTab для фильтрации услуг
        onClose={() => {
          logger.info('AppointmentWizardV2 closing');
          setShowWizard(false);
          setWizardEditMode(false);            // ✨ Сброс режима
          setWizardInitialData(null);          // ✨ Сброс данных
        }}
        isProcessing={isProcessing}
        setIsProcessing={setIsProcessing}
        onComplete={async (wizardData) => {
          logger.info('AppointmentWizardV2 completed successfully:', wizardData);

          // Обновляем данные (работает и для создания, и для редактирования)
          try {
            // ⭐ Увеличена задержка перед обновлением данных (с 1000ms до 1500ms)
            // чтобы backend успел обновить базу данных и все связанные записи
            // Особенно важно для batch операций, которые могут занимать больше времени
            await new Promise(resolve => setTimeout(resolve, 1500));

            // Принудительное обновление данных
            await Promise.all([
              loadAppointments({ silent: false, source: 'wizard-complete', force: true }),
              loadIntegratedData()
            ]);

            setShowWizard(false);
            setWizardEditMode(false);            // ✨ Сброс режима
            setWizardInitialData(null);          // ✨ Сброс данных

            const message = wizardEditMode
              ? 'Запись успешно обновлена!'
              : 'Запись успешно создана!';
            toast.success(message);
          } catch (error) {
            logger.error('Error refreshing data after wizard completion:', error);
            // Не показываем ошибку пользователю, так как запись уже создана
            setShowWizard(false);
            toast.success('Запись создана! Обновите страницу для отображения изменений.');
          }
        }}
      />

      {/* Старые диалоги удалены - используются современные компоненты CancelDialog, PaymentDialog, PrintDialog */}
      {/* Встроенное модальное окно оплаты удалено - используется PaymentDialog компонент */}
      {/* Встроенный мастер удален - используется AppointmentWizard компонент */}

      {/* Модальное окно слотов */}
      {showSlotsModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }} role="dialog" aria-modal="true">
          <div style={{
            background: cardBg,
            padding: '24px',
            borderRadius: '12px',
            maxWidth: '500px',
            width: '90%'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0 }}>📅 {t('available_slots')}</h3>
              <button onClick={() => setShowSlotsModal(false)} style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer' }}>×</button>
            </div>
            <div style={{ display: 'grid', gap: '8px' }}>
              <button style={buttonStyle} onClick={async () => {
                if (!rescheduleData) return;
                try {
                  setShowSlotsModal(false);
                  logger.info(`Перенос визита ${rescheduleData.id} на завтра`);
                  await api.post(`/visits/${rescheduleData.id}/reschedule/tomorrow`);
                  toast.success('Визит успешно перенесен на завтра');
                  setRescheduleData(null);
                  loadAppointments({ source: 'reschedule_tomorrow' });
                } catch (e) {
                  logger.error('Ошибка переноса на завтра:', e);
                  toast.error('Ошибка переноса: ' + (e.response?.data?.detail || e.message));
                }
              }}>
                🌅 {t('tomorrow')}
              </button>
              <button style={buttonSecondaryStyle} onClick={async () => {
                if (!rescheduleData) return;
                const currentVal = getLocalDateString(rescheduleData.appointment_date || rescheduleData.visit_date || rescheduleData.date || new Date());
                const dateStr = prompt('Введите дату переноса (YYYY-MM-DD):', currentVal);

                if (dateStr) {
                  // Simple validation YYYY-MM-DD
                  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
                    toast.error('Неверный формат даты. Используйте YYYY-MM-DD');
                    return;
                  }

                  try {
                    setShowSlotsModal(false);
                    logger.info(`Перенос визита ${rescheduleData.id} на ${dateStr}`);
                    await api.post(`/visits/${rescheduleData.id}/reschedule`, null, { params: { new_date: dateStr } });
                    toast.success(`Визит перенесен на ${dateStr}`);
                    setRescheduleData(null);
                    loadAppointments({ source: 'reschedule_date' });
                  } catch (e) {
                    logger.error('Ошибка переноса на дату:', e);
                    toast.error('Ошибка переноса: ' + (e.response?.data?.detail || e.message));
                  }
                }
              }}>
                📅 {t('select_date')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно QR */}
      {showQRModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }} role="dialog" aria-modal="true">
          <div style={{
            background: cardBg,
            padding: '24px',
            borderRadius: '12px',
            maxWidth: '400px',
            width: '90%',
            textAlign: 'center'
          }}>
            <h3 style={{ margin: '0 0 16px 0' }}>📱 QR-код для пациента</h3>
            <div style={{
              background: 'white',
              padding: '20px',
              borderRadius: '8px',
              margin: '16px 0',
              display: 'inline-block'
            }}>
              {/* Здесь будет QR-код */}
              <div style={{
                width: '200px',
                height: '200px',
                background: '#f0f0f0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '14px',
                color: '#666'
              }}>
                QR-код
              </div>
            </div>
            <button
              onClick={() => setShowQRModal(false)}
              style={{
                padding: '8px 16px',
                background: accentColor,
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: 'pointer'
              }}
            >
              Закрыть
            </button>
          </div>
        </div>
      )}

      {/* Контекстное меню */}
      {contextMenu.open && (
        <AppointmentContextMenu
          row={contextMenu.row}
          position={contextMenu.position}
          theme={theme}
          onClose={() => setContextMenu({ open: false, row: null, position: { x: 0, y: 0 } })}
          onAction={handleContextMenuAction}
        />
      )}

      {/* Модуль оплаты */}
      <PaymentManager
        isOpen={showPaymentManager}
        onClose={(result) => {
          setShowPaymentManager(false);
          if (result?.success) {
            // Обновляем данные после успешной оплаты
            loadAppointments();
            loadIntegratedData();
          }
        }}
      />

      {/* ✅ Форс-мажор модальное окно */}
      <ForceMajeureModal
        isOpen={forceMajeureModal.open}
        onClose={() => setForceMajeureModal({ open: false, specialistId: null, specialistName: '' })}
        specialistId={forceMajeureModal.specialistId}
        specialistName={forceMajeureModal.specialistName}
        onSuccess={(action, result) => {
          logger.info('[RegistrarPanel] Force majeure action completed:', action, result);
          toast.success(action === 'transfer' ? 'Записи перенесены на завтра' : 'Записи отменены с возвратом');
          loadAppointments({ source: 'force_majeure' });
        }}
      />
    </div>
  );
};

export default RegistrarPanel; 
