import React, { useState, useEffect, useCallback, useRef, useMemo, memo, startTransition } from 'react';
import { useSearchParams } from 'react-router-dom';
import PhoneInput from '../components/ui/PhoneInput';
import { ToastContainer, toast } from 'react-toastify';
// import ServiceChecklist from '../components/ServiceChecklist';
import IntegratedServiceSelector from '../components/registrar/IntegratedServiceSelector';
import IntegratedDoctorSelector from '../components/registrar/IntegratedDoctorSelector';
// OnlineQueueManager удален - используется ModernQueueManager
import AppointmentFlow from '../components/AppointmentFlow';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import AppointmentContextMenu from '../components/tables/AppointmentContextMenu';
import ModernTabs from '../components/navigation/ModernTabs';
import ResponsiveNavigation from '../components/layout/ResponsiveNavigation';
import { Button, Card, Badge, Skeleton, AnimatedTransition, AnimatedToast, AnimatedLoader } from '../components/ui';
import { useBreakpoint, useTouchDevice } from '../hooks/useMediaQuery';
import { useTheme } from '../contexts/ThemeContext';
import PrintButton from '../components/print/PrintButton';
import { 
  Hospital, 
  Calendar, 
  Search, 
  MessageCircle, 
  HelpCircle, 
  Plus, 
  Download, 
  Sun, 
  Moon, 
  LogOut,
  Home,
  FileText,
  Heart,
  Activity,
  User,
  TestTube,
  Syringe,
  Settings,
  Globe,
  Printer,
  X,
  CreditCard
} from 'lucide-react';
import '../components/ui/animations.css';
import '../styles/responsive.css';
import '../styles/animations.css';
import '../styles/dark-theme-visibility-fix.css';

// Современные диалоги
import PaymentDialog from '../components/dialogs/PaymentDialog';
import CancelDialog from '../components/dialogs/CancelDialog';
import PrintDialog from '../components/dialogs/PrintDialog';

// Современный мастер
import AppointmentWizard from '../components/wizard/AppointmentWizard';
import AppointmentWizardV2 from '../components/wizard/AppointmentWizardV2';
import PaymentManager from '../components/payment/PaymentManager';
import useWizardSettings from '../hooks/useWizardSettings';

// Современные фильтры
import ModernFilters from '../components/filters/ModernFilters';

// Современная очередь
import ModernQueueManager from '../components/queue/ModernQueueManager';

// Современная статистика
import ModernStatistics from '../components/statistics/ModernStatistics';
 

const RegistrarPanel = () => {
  console.log('🔄 RegistrarPanel component rendered at:', new Date().toISOString());
  // Адаптивные хуки
  const { isMobile, isTablet, isDesktop } = useBreakpoint();
  const isTouch = useTouchDevice();

  // Основные состояния
  const [activeTab, setActiveTab] = useState(null);
  const [searchParams] = useSearchParams();
  const todayStr = new Date().toISOString().split('T')[0];
  
  // Состояния для печати
  const [printDialog, setPrintDialog] = useState({ open: false, type: '', data: null });
  const [printInProgress, setPrintInProgress] = useState(false);
  const [cancelDialog, setCancelDialog] = useState({ open: false, row: null, reason: '' });
  const [paymentDialog, setPaymentDialog] = useState({ open: false, row: null, paid: false, source: null });
  
  const [contextMenu, setContextMenu] = useState({ open: false, row: null, position: { x: 0, y: 0 } });
  // Демо-данные вынесены в константу
  const DEMO_APPOINTMENTS = [
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
      appointment_date: todayStr
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
      department: 'ecg',
      doctor_specialty: 'cardiology',
      date: todayStr,
      appointment_date: todayStr
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
      appointment_date: todayStr
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
      status: 'plan',
      isEmpty: false,
      department: 'stomatology',
      doctor_specialty: 'stomatology',
      date: todayStr,
      appointment_date: todayStr
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
      appointment_date: todayStr
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
      appointment_date: todayStr
    }
  ];

  // Состояния для управления данными
  const [appointments, setAppointments] = useState([]);
  const [dataSource, setDataSource] = useState('loading'); // 'loading' | 'api' | 'demo' | 'error'
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [appointmentsSelected, setAppointmentsSelected] = useState(new Set());
  const [showAddressColumn, setShowAddressColumn] = useState(true);
  // Состояния встроенного мастера удалены - используется AppointmentWizard компонент
  const [showWizard, setShowWizard] = useState(false); // Для современного AppointmentWizard
  const [showPaymentManager, setShowPaymentManager] = useState(false); // Для модуля оплаты
  const [isProcessing, setIsProcessing] = useState(false); // Состояние обработки
  
  // Настройки мастера регистрации (A/B тест)
  const { useNewWizard, loading: wizardSettingsLoading } = useWizardSettings();
  const [patientSuggestions, setPatientSuggestions] = useState([]);
  const [showPatientSuggestions, setShowPatientSuggestions] = useState(false);
  const [patientErrors, setPatientErrors] = useState({});
  
  // Refs для фокуса в мастере
  const fioRef = useRef(null);
  const dobRef = useRef(null);
  const phoneRef = useRef(null);
  
  // Отладка состояния мастера удалена - используется AppointmentWizard

  // Отладка состояния загрузки
  useEffect(() => {
    console.log('⏳ appointmentsLoading changed:', appointmentsLoading);
  }, [appointmentsLoading]);

  // Отладка изменений appointments
  useEffect(() => {
    console.log('📋 appointments changed, count:', appointments.length);
  }, [appointments]);

  // Убираем дублирование - filteredAppointments уже определена ниже в коде
  const [showSlotsModal, setShowSlotsModal] = useState(false);
  const [selectedAppointment, setSelectedAppointment] = useState(null);
  const [showAppointmentFlow, setShowAppointmentFlow] = useState(false);
  const [showQRModal, setShowQRModal] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Фиксированный хедер убран - теперь используется глобальный хедер
  
  // Состояние для выбранного пациента в новом мастере
  const [selectedPatientId, setSelectedPatientId] = useState(null);
  
  // Новые состояния для интеграции с админ панелью
  const [doctors, setDoctors] = useState([]);
  const [services, setServices] = useState({});
  const [queueSettings, setQueueSettings] = useState({});
  const [selectedDoctor, setSelectedDoctor] = useState(null);
  const [selectedServices, setSelectedServices] = useState([]);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  
  // Язык (тема теперь централизована)
  const [language, setLanguage] = useState(() => localStorage.getItem('ui_lang') || 'ru');
  
  useEffect(() => { localStorage.setItem('ui_lang', language); }, [language]);

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
    isLight, 
    getColor, 
    getSpacing, 
    getFontSize, 
    designTokens 
  } = useTheme();

  // Адаптивные цвета из централизованной системы темизации
  const cardBg = isDark ? getColor('secondary', 900) : getColor('secondary', 50);
  const textColor = isDark ? getColor('secondary', 50) : getColor('secondary', 900);
  const borderColor = isDark ? getColor('secondary', 700) : getColor('secondary', 200);
  const accentColor = getColor('primary', 500);
  const successColor = getColor('success', 500);
  const warningColor = getColor('warning', 500);
  const dangerColor = getColor('danger', 500);

  // Используем централизованную типографику и отступы
  // Убираем локальные spacing и typography - используем getSpacing и getColor напрямую

  const pageStyle = {
    padding: '0',
    maxWidth: 'none',
    margin: '0',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    fontSize: isMobile ? getFontSize('sm') : isTablet ? getFontSize('base') : getFontSize('lg'),
    fontWeight: 400,
    lineHeight: 1.5,
    background: theme === 'light' 
      ? 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)'
      : 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
    minHeight: '100vh',
    position: 'relative'
  };

  const cardStyle = {
    background: theme === 'light' 
      ? 'rgba(255, 255, 255, 0.8)' 
      : 'rgba(15, 23, 42, 0.8)',
    backdropFilter: 'blur(20px)',
    color: textColor,
    border: `1px solid ${theme === 'light' ? 'rgba(255, 255, 255, 0.2)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderRadius: '20px',
    margin: '0 20px 20px 20px',
    boxShadow: theme === 'light' 
      ? '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
      : '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
    overflow: 'hidden',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
  };

  const cardHeaderStyle = {
    padding: '32px',
    borderBottom: `1px solid ${theme === 'light' ? 'rgba(255, 255, 255, 0.2)' : 'rgba(255, 255, 255, 0.1)'}`,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    background: `linear-gradient(135deg, ${getColor('primary', 500)} 0%, ${getColor('primary', 700)} 50%, ${getColor('primary', 900)} 100%)`,
    color: 'white',
    textShadow: '0 1px 2px rgba(0, 0, 0, 0.5)',
    position: 'relative',
    overflow: 'hidden'
  };

  const cardContentStyle = {
    padding: '20px',
    color: textColor
  };

  // Контейнер таблицы, визуально "сливается" с вкладками
  const tableContainerStyle = {
    background: theme === 'light' 
      ? 'rgba(255, 255, 255, 0.8)' 
      : 'rgba(15, 23, 42, 0.8)',
    backdropFilter: 'blur(20px)',
    color: textColor,
    borderLeft: `1px solid ${theme === 'light' ? 'rgba(255, 255, 255, 0.2)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderRight: `1px solid ${theme === 'light' ? 'rgba(255, 255, 255, 0.2)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderBottom: `1px solid ${theme === 'light' ? 'rgba(255, 255, 255, 0.2)' : 'rgba(255, 255, 255, 0.1)'}`,
    borderTop: 'none',
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
    padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
    background: `linear-gradient(135deg, ${getColor('primary', 500)} 0%, ${getColor('primary', 600)} 100%)`,
    color: 'white',
    border: 'none',
    borderRadius: '12px',
    cursor: 'pointer',
    marginRight: getSpacing('sm'),
    fontSize: getFontSize('sm'),
    fontWeight: '600',
    lineHeight: '1.25',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)',
    position: 'relative',
    overflow: 'hidden',
    textShadow: '0 1px 2px rgba(0, 0, 0, 0.5)'
  };

  const buttonSecondaryStyle = {
    padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
    background: theme === 'light' ? 'white' : getColor('gray', 800),
    color: textColor,
    border: `1px solid ${borderColor}`,
    borderRadius: '12px',
    cursor: 'pointer',
    marginRight: getSpacing('sm'),
    fontSize: getFontSize('sm'),
    fontWeight: '600',
    lineHeight: '1.25',
    transition: 'all 0.2s ease',
    boxShadow: 'none',
  };
  

  const buttonSuccessStyle = {
    ...buttonStyle,
    background: `linear-gradient(135deg, ${getColor('success', 500)} 0%, ${getColor('success', 600)} 100%)`,
    boxShadow: '0 4px 14px 0 rgba(34, 197, 94, 0.3)'
  };

  const buttonDangerStyle = {
    ...buttonStyle,
    background: `linear-gradient(135deg, ${getColor('danger', 500)} 0%, ${getColor('danger', 600)} 100%)`,
    boxShadow: '0 4px 14px 0 rgba(239, 68, 68, 0.3)'
  };

  const buttonWarningStyle = {
    ...buttonStyle,
    background: `linear-gradient(135deg, ${getColor('warning', 500)} 0%, ${getColor('warning', 600)} 100%)`,
    color: '#212529',
    boxShadow: '0 4px 14px 0 rgba(245, 158, 11, 0.3)'
  };

  const inputStyle = {
    width: '100%',
    padding: '12px 16px',
    border: '1px solid #ddd',
    borderRadius: '8px',
    fontSize: '14px',
    marginBottom: '16px',
    transition: 'border-color 0.2s'
  };

  const labelStyle = {
    display: 'block',
    marginBottom: '8px',
    fontWeight: '500',
    fontSize: '14px'
  };

  const tabStyle = {
    padding: isMobile ? `${getSpacing('xs')} ${getSpacing('sm')}` : `${getSpacing('sm')} ${getSpacing('xl')}`,
    border: 'none',
    background: 'transparent',
    cursor: 'pointer',
    fontSize: isMobile ? getFontSize('xs') : getFontSize('sm'),
    fontWeight: '500',
    lineHeight: '1.25',
    color: textColor,
    borderRadius: isMobile ? '8px' : '12px',
    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    position: 'relative',
    overflow: 'hidden',
    minWidth: isMobile ? 'auto' : '120px',
    justifyContent: isMobile ? 'center' : 'flex-start',
    whiteSpace: 'nowrap',
    display: 'flex',
    alignItems: 'center',
    gap: isMobile ? '4px' : getSpacing('xs'),
    borderBottom: '3px solid transparent'
  };

  const activeTabStyle = {
    ...tabStyle,
    background: `linear-gradient(135deg, ${getColor('primary', 500)} 0%, ${getColor('primary', 600)} 100%)`,
    color: 'white',
    boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)',
    transform: 'translateY(-2px)',
    borderBottom: `3px solid ${getColor('primary', 700)}`
  };

  // Базовый URL API
    const API_BASE = (import.meta?.env?.VITE_API_BASE_URL) || 'http://localhost:8000';

  // Загрузка данных из админ панели
  const loadIntegratedData = useCallback(async () => {
    console.log('🔧 loadIntegratedData called at:', new Date().toISOString());
    try {
      // УБИРАЕМ setAppointmentsLoading(true) - это не должно влиять на загрузку записей
      // setAppointmentsLoading(true);
      
      // Сначала устанавливаем fallback данные для врачей и услуг
      // console.debug('Setting fallback doctors and services data');
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
      console.log('🔍 RegistrarPanel: token from localStorage:', token ? `${token.substring(0, 30)}...` : 'null');

      const [doctorsRes, servicesRes, queueRes] = await Promise.all([
          fetch(`${API_BASE}/api/v1/registrar/doctors`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
          fetch(`${API_BASE}/api/v1/registrar/services`, {
          headers: { 'Authorization': `Bearer ${token}` }
        }),
          fetch(`${API_BASE}/api/v1/registrar/queue-settings`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
      ]);

      if (doctorsRes.ok) {
        const doctorsData = await doctorsRes.json();
        const apiDoctors = doctorsData.doctors || [];
        // Если API пустой — оставляем уже установленные фолбэк-данные без лишних перерисовок
        if (apiDoctors.length > 0) {
          setDoctors(apiDoctors);
        }
      } else {
        // Fallback данные для врачей
        setDoctors([
          { id: 1, specialty: 'cardiology', user: { full_name: 'Доктор Кардиолог' }, cabinet: '101', price_default: 50000 },
          { id: 2, specialty: 'dermatology', user: { full_name: 'Доктор Дерматолог' }, cabinet: '102', price_default: 45000 },
          { id: 3, specialty: 'stomatology', user: { full_name: 'Доктор Стоматолог' }, cabinet: '103', price_default: 60000 }
        ]);
      }

      if (servicesRes.ok) {
        const servicesData = await servicesRes.json();
        const apiServices = servicesData.services_by_group || {};
        // Если API пустой — оставляем уже установленные фолбэк-данные без лишних перерисовок
        if (Object.keys(apiServices).length > 0) {
          setServices(apiServices);
        } else {
          setServices({
            laboratory: [
              { id: 1, name: 'Общий анализ крови', price: 15000, specialty: 'laboratory', group: 'laboratory' },
              { id: 2, name: 'Биохимический анализ крови', price: 25000, specialty: 'laboratory', group: 'laboratory' },
              { id: 3, name: 'Анализ мочи', price: 10000, specialty: 'laboratory', group: 'laboratory' },
              { id: 4, name: 'Анализ кала', price: 12000, specialty: 'laboratory', group: 'laboratory' }
            ],
            dermatology: [
              { id: 5, name: 'Консультация дерматолога', price: 40000, specialty: 'dermatology', group: 'dermatology' },
              { id: 6, name: 'Дерматоскопия', price: 30000, specialty: 'dermatology', group: 'dermatology' },
              { id: 7, name: 'УЗИ кожи', price: 20000, specialty: 'dermatology', group: 'dermatology' },
              { id: 8, name: 'Лечение акне', price: 60000, specialty: 'dermatology', group: 'dermatology' }
            ],
            cosmetology: [
              { id: 9, name: 'Чистка лица', price: 35000, specialty: 'cosmetology', group: 'cosmetology' },
              { id: 10, name: 'Пилинг лица', price: 40000, specialty: 'cosmetology', group: 'cosmetology' },
              { id: 11, name: 'Массаж лица', price: 25000, specialty: 'cosmetology', group: 'cosmetology' },
              { id: 12, name: 'Мезотерапия', price: 120000, specialty: 'cosmetology', group: 'cosmetology' }
            ]
          });
        }
      } else {
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
      }

      if (queueRes.ok) {
        const queueData = await queueRes.json();
        setQueueSettings(queueData);
        }
      } catch (fetchError) {
        // Backend недоступен - используем демо-данные (уже установлены выше)
        console.warn('Backend недоступен для загрузки интегрированных данных, используем демо-режим:', fetchError.message);
      }

    } catch (error) {
      console.error('Ошибка загрузки интегрированных данных:', error);
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
        console.error(`Error fetching patient ${patientId}:`, error);
      }
    }
    return null;
  }, [API_BASE]);

  // Функция для обогащения записей данными пациентов и недостающими полями
  const enrichAppointmentsWithPatientData = useCallback(async (appointments) => {
    const enrichedAppointments = await Promise.all(appointments.map(async (apt) => {
      let enrichedApt = { ...apt };
      
      // Обогащаем данными пациента
      if (apt.patient_id) {
        const patient = await fetchPatientData(apt.patient_id);
        if (patient) {
          enrichedApt = {
            ...enrichedApt,
            patient_fio: `${patient.last_name || ''} ${patient.first_name || ''} ${patient.middle_name || ''}`.trim(),
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
            enrichedApt = { ...enrichedApt, ...ov };
          }
        }
      } catch(_) {
        // Игнорируем ошибки парсинга JSON
      }

      // Добавляем недостающие поля для таблицы с значениями по умолчанию
      enrichedApt = {
        ...enrichedApt,
        // Если поля уже есть в API, используем их, иначе значения по умолчанию
        visit_type: enrichedApt.visit_type || 'paid', // Платный по умолчанию
        payment_type: enrichedApt.payment_type || (enrichedApt.payment_provider === 'online' ? 'online' : 'cash'), // Определяем по провайдеру
        // Если пришел payment_status от API — уважаем его; иначе — выводим из payment_processed_at
        payment_status: enrichedApt.payment_status || (enrichedApt.payment_processed_at ? 'paid' : (enrichedApt.payment_amount > 0 ? 'pending' : 'pending')),
        services: enrichedApt.services || [], // ✅ ИСПРАВЛЕНО: оставляем пустым если нет услуг
        // Добавляем поле cost для совместимости с таблицей (используем payment_amount если cost отсутствует)
        cost: enrichedApt.cost || enrichedApt.payment_amount || 0,
      };
      
      return enrichedApt;
    }));
    return enrichedAppointments;
  }, [fetchPatientData]);

  // Улучшенная загрузка записей с поддержкой тихого режима
  const loadAppointments = useCallback(async (options = { silent: false }) => {
    console.log('📥 loadAppointments called at:', new Date().toISOString(), options);
    const { silent } = options || {};
    try {
      if (!silent) {
      setAppointmentsLoading(true);
      setDataSource('loading');
      }
      
      // Проверяем наличие токена
      const token = localStorage.getItem('auth_token');
      console.log('🔍 loadAppointments: token from localStorage:', token ? `${token.substring(0, 30)}...` : 'null');
      if (!token) {
        console.warn('Токен аутентификации отсутствует, используем демо-данные');
        // Применяем локальные оверрайды к демо-данным
        let demo = DEMO_APPOINTMENTS;
        try {
          const overridesRaw = localStorage.getItem('appointments_local_overrides');
          const overrides = overridesRaw ? JSON.parse(overridesRaw) : {};
          demo = DEMO_APPOINTMENTS.map(apt => {
            const ov = overrides[String(apt.id)];
            if (ov && (!ov.expiresAt || ov.expiresAt > Date.now())) {
              return { ...apt, ...ov };
            }
            return apt;
          });
        } catch(_) {
        // Игнорируем ошибки парсинга JSON
      }
        startTransition(() => {
          if (!silent) setDataSource('demo');
          setAppointments(demo);
        });
        return;
      }
      
      console.log('🔍 loadAppointments: making request with token:', token ? `${token.substring(0, 30)}...` : 'null');
      const response = await fetch(`${API_BASE}/api/v1/registrar/all-appointments?limit=50`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        const appointmentsData = Array.isArray(data) ? data : (data.items || data.appointments || []);
        
        if (appointmentsData.length > 0) {
          // Обогащаем данные записей информацией о пациентах
          const enriched = await enrichAppointmentsWithPatientData(appointmentsData);
          
          // Сохраняем локальные изменения при обновлении
          startTransition(() => {
            setAppointments(prev => {
              const locallyModified = prev.filter(apt => apt._locallyModified);
              // Также учитываем локальные оверрайды из localStorage (например, после оплаты)
              let overrides = {};
              try {
                const overridesRaw = localStorage.getItem('appointments_local_overrides');
                overrides = overridesRaw ? JSON.parse(overridesRaw) : {};
              } catch(_) {
        // Игнорируем ошибки парсинга JSON
      }

              const enrichedWithLocal = enriched.map(apt => {
                const localVersion = locallyModified.find(local => local.id === apt.id);
                const override = overrides[String(apt.id)];
                let merged = localVersion ? { ...apt, ...localVersion } : apt;
                if (override && (!override.expiresAt || override.expiresAt > Date.now())) {
                  merged = { ...merged, ...override };
                }
                return merged;
              });
              // Обновляем только если реально изменилось
              try {
                const prevStr = JSON.stringify(prev);
                const nextStr = JSON.stringify(enrichedWithLocal);
                if (prevStr === nextStr) return prev;
              } catch (_) {
              // Игнорируем ошибки сравнения JSON
            }
              return enrichedWithLocal;
            });
            // Не триггерим обновление, если значение не меняется
            setDataSource(prev => (prev === 'api' ? prev : 'api'));
          });
          console.debug('✅ Загружены и обогащены данные из API:', enriched.length, 'записей');
        } else {
          // API вернул пустой массив - показываем демо-данные с учетом оверрайдов
          let demo = DEMO_APPOINTMENTS;
          try {
            const overridesRaw = localStorage.getItem('appointments_local_overrides');
            const overrides = overridesRaw ? JSON.parse(overridesRaw) : {};
            demo = DEMO_APPOINTMENTS.map(apt => {
              const ov = overrides[String(apt.id)];
              if (ov && (!ov.expiresAt || ov.expiresAt > Date.now())) {
                return { ...apt, ...ov };
              }
              return apt;
            });
          } catch(_) {
        // Игнорируем ошибки парсинга JSON
      }
          startTransition(() => {
            setAppointments(prev => {
              try {
                const prevStr = JSON.stringify(prev);
                const nextStr = JSON.stringify(demo);
                if (prevStr === nextStr) return prev;
              } catch (_) {
              // Игнорируем ошибки сравнения JSON
            }
              return demo;
            });
            setDataSource(prev => (prev === 'demo' ? prev : 'demo'));
          });
        }
      } else if (response.status === 401) {
        // Токен недействителен
        console.warn('Токен недействителен (401), очищаем и используем демо-данные');
        localStorage.removeItem('auth_token');
        startTransition(() => {
          if (!silent) setDataSource(prev => (prev === 'demo' ? prev : 'demo'));
          // Применяем оверрайды к демо-данным
          let demo = DEMO_APPOINTMENTS;
          try {
            const overridesRaw = localStorage.getItem('appointments_local_overrides');
            const overrides = overridesRaw ? JSON.parse(overridesRaw) : {};
            demo = DEMO_APPOINTMENTS.map(apt => {
              const ov = overrides[String(apt.id)];
              if (ov && (!ov.expiresAt || ov.expiresAt > Date.now())) {
                return { ...apt, ...ov };
              }
              return apt;
            });
          } catch(_) {
        // Игнорируем ошибки парсинга JSON
      }
          setAppointments(prev => {
            try {
              const prevStr = JSON.stringify(prev);
              const nextStr = JSON.stringify(demo);
              if (prevStr === nextStr) return prev;
            } catch (_) {
              // Игнорируем ошибки сравнения JSON
            }
            return demo;
          });
        });
      } else {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      console.warn('Backend недоступен для загрузки записей, используем демо-режим:', error.message);
        startTransition(() => {
          if (!silent) setDataSource(prev => (prev === 'demo' ? prev : 'demo'));
          setAppointments(prev => {
            try {
              const prevStr = JSON.stringify(prev);
              const nextStr = JSON.stringify(DEMO_APPOINTMENTS);
              if (prevStr === nextStr) return prev;
            } catch (_) {
              // Игнорируем ошибки сравнения JSON
            }
            return DEMO_APPOINTMENTS;
          });
        });
      startTransition(() => {
        if (!silent) setDataSource(prev => (prev === 'demo' ? prev : 'demo'));
        setAppointments(prev => {
          try {
            const prevStr = JSON.stringify(prev);
            const nextStr = JSON.stringify(DEMO_APPOINTMENTS);
            if (prevStr === nextStr) return prev;
          } catch (_) {
            // Игнорируем ошибки сравнения JSON
          }
          return DEMO_APPOINTMENTS;
        });
      });
      
      // Показываем уведомление пользователю только при первой загрузке
      if (appointments.length === 0) {
        toast('Backend недоступен. Работаем в демо-режиме.', { icon: 'ℹ️' });
      }
    } finally {
      if (!silent) setAppointmentsLoading(false);
    }
  }, [enrichAppointmentsWithPatientData]);

  // Первичная загрузка данных (однократно) с защитой от двойного вызова в React 18
  const initialLoadRef = useRef(false);
  useEffect(() => {
    if (initialLoadRef.current) return;
    initialLoadRef.current = true;
    console.log('🚀 Starting initial data load (guarded)...');
    loadAppointments();
    loadIntegratedData();
    setIsInitialLoad(false);
  }, [loadAppointments, loadIntegratedData]);

  // Обработчик события из хедера для открытия мастера записи
  useEffect(() => {
    const handleOpenWizard = () => {
      // Очищаем данные предыдущего пациента
      setSelectedPatientId(null);
      setPatientSuggestions([]);
      setShowPatientSuggestions(false);
      // Открываем современный мастер через состояние в AppointmentWizard
      setShowWizard(true);
    };

    window.addEventListener('openAppointmentWizard', handleOpenWizard);
    return () => {
      window.removeEventListener('openAppointmentWizard', handleOpenWizard);
    };
  }, []);

  // Автообновление очереди с возможностью паузы (в тихом режиме)
  useEffect(() => {
    // Во время мастера записи или модальных окон автообновление отключаем, чтобы не было мерцаний
    if (showWizard || paymentDialog.open || printDialog.open || cancelDialog.open) return;
    if (!autoRefresh) return;
    
    const id = setInterval(() => {
      // Загружаем только записи тихо, без смены индикаторов
      loadAppointments({ silent: true });
    }, 15000);
    
    return () => clearInterval(id);
  }, [autoRefresh, showWizard, paymentDialog.open, printDialog.open, cancelDialog.open]);

  // Функции для жесткого потока
  const handleStartVisit = async (appointment) => {
    try {
      // ✅ ИСПРАВЛЕНО: Используем существующий эндпоинт для обновления статуса
      const response = await fetch(`${API_BASE}/api/v1/appointments/${appointment.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({
          status: 'in_progress'
        })
      });

      if (response.ok) {
        const updatedAppointment = await response.json();
        // Обновляем список записей
        setAppointments(prev => prev.map(apt => 
          apt.id === appointment.id ? { ...apt, status: 'in_progress', _locallyModified: true } : apt
        ));
        toast.success('Прием начат успешно!');
      } else {
        // Если PATCH не поддерживается, обновляем локально
        console.warn('PATCH не поддерживается, обновляем локально');
        setAppointments(prev => prev.map(apt => 
          apt.id === appointment.id ? { ...apt, status: 'in_progress', _locallyModified: true } : apt
        ));
        toast.success('Прием начат (локально)');
      }
    } catch (error) {
      console.warn('RegistrarPanel: Start visit API error, updating locally:', error);
      // Фолбэк - обновляем локально
      setAppointments(prev => prev.map(apt => 
        apt.id === appointment.id ? { ...apt, status: 'in_progress', _locallyModified: true } : apt
      ));
      toast.success('Прием начат (локально)');
    }
  };

  const handlePayment = async (appointment) => {
    try {
      console.log('🔍 handlePayment вызван с данными:', appointment);
      console.log('🔍 appointment.id:', appointment.id, 'тип:', typeof appointment.id);
      
      // Проверяем, не оплачена ли уже запись
      const paymentStatus = (appointment.payment_status || '').toLowerCase();
      const status = (appointment.status || '').toLowerCase();
      console.log('Текущий статус оплаты:', paymentStatus, 'Статус записи:', status);
      
      if (paymentStatus === 'paid' || status === 'paid' || status === 'queued') {
        toast('Запись уже оплачена', { icon: 'ℹ️' });
        return appointment;
      }
      
      // Определяем источник записи и правильный ID
      const isFromVisits = appointment.id >= 20000;
      const realId = isFromVisits ? appointment.id - 20000 : appointment.id;
      const source = appointment.source || (isFromVisits ? 'visits' : 'appointments');
      
      console.log('Попытка оплатить запись:', appointment.id, 'Реальный ID:', realId, 'Источник:', source);
      
      const API_BASE = (import.meta?.env?.VITE_API_BASE_URL) || 'http://localhost:8000';
      
      // Используем правильный API в зависимости от источника
      let url;
      if (source === 'visits') {
        // Для записей из visits используем API visits
        url = `${API_BASE}/api/v1/registrar/visits/${realId}/mark-paid`;
      } else {
        // Для записей из appointments используем старый API
        url = `${API_BASE}/api/v1/appointments/${realId}/mark-paid`;
      }
      
      console.log('🔍 Отправляем запрос на:', url);
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      
      console.log('Ответ сервера:', response.status, response.statusText);

      if (response.ok) {
        const updatedAppointment = await response.json();
        console.log('Успешный ответ:', updatedAppointment);
        
        // Обновляем список записей - устанавливаем статус 'queued' после оплаты
        const appointmentWithQueuedStatus = {
          ...updatedAppointment,
          status: 'queued', // Принудительно устанавливаем статус "В очереди" после оплаты
          payment_status: 'paid',
          _locallyModified: true // Помечаем как локально измененную, чтобы избежать перезаписи при обновлении
        };
        
        // Сохраняем локальный оверрайд в localStorage (на случай полного перезагрузки страницы)
        try {
          const overridesRaw = localStorage.getItem('appointments_local_overrides');
          const overrides = overridesRaw ? JSON.parse(overridesRaw) : {};
          overrides[String(appointment.id)] = {
            status: appointmentWithQueuedStatus.status,
            payment_status: appointmentWithQueuedStatus.payment_status,
            // TTL 10 минут
            expiresAt: Date.now() + 10 * 60 * 1000
          };
          localStorage.setItem('appointments_local_overrides', JSON.stringify(overrides));
        } catch(_) {
        // Игнорируем ошибки парсинга JSON
      }

        setAppointments(prev => prev.map(apt => (
          apt.id === appointment.id ? appointmentWithQueuedStatus : apt
        )));
        toast.success('Запись оплачена и добавлена в очередь!');
        // Мягко подтянем данные из API, чтобы зафиксировать статус с бэкенда
        setTimeout(() => loadAppointments({ silent: true }), 800);
        return appointmentWithQueuedStatus;
      } else {
        const errorText = await response.text();
        console.error('Ошибка API:', response.status, errorText);
        
        let errorMessage = 'Ошибка при оплате';
        try {
          const errorData = JSON.parse(errorText);
          if (errorData.detail) {
            errorMessage = errorData.detail;
            // Если запись уже оплачена, обрабатываем как успех
            if (errorMessage.includes('уже оплачена') || errorMessage.includes('PAID -> PAID')) {
              toast('Запись уже оплачена', { icon: 'ℹ️' });
              const updatedAppointment = {
                ...appointment,
                status: 'queued',
                payment_status: 'paid'
              };
              // Сохраняем локальный оверрайд
              try {
                const overridesRaw = localStorage.getItem('appointments_local_overrides');
                const overrides = overridesRaw ? JSON.parse(overridesRaw) : {};
                overrides[String(appointment.id)] = {
                  status: updatedAppointment.status,
                  payment_status: updatedAppointment.payment_status,
                  expiresAt: Date.now() + 10 * 60 * 1000
                };
                localStorage.setItem('appointments_local_overrides', JSON.stringify(overrides));
              } catch(_) {
        // Игнорируем ошибки парсинга JSON
      }

              setAppointments(prev => prev.map(apt => (
                apt.id === appointment.id ? updatedAppointment : apt
              )));
              setTimeout(() => loadAppointments({ silent: true }), 800);
              return updatedAppointment;
            }
          }
        } catch (e) {
          errorMessage = errorText || errorMessage;
        }
        
        toast.error(errorMessage);
        return null;
      }
    } catch (error) {
      console.error('RegistrarPanel: Payment error:', error);
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
      let method = 'POST';
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
        console.log('Отмена записи (локально):', appointmentId);
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
        console.log('Подтверждение записи (локально):', appointmentId);
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
        console.log('Неявка записи (локально):', appointmentId, 'Причина:', reason);
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
          url = `${API_BASE}/api/v1/appointments/${realId}/start-visit`;
        }
      } else {
        console.log('Неподдерживаемый статус:', status);
        toast.error('Изменение данного статуса не поддерживается');
        return;
      }
      
      console.log('Обновляем статус записи:', appointmentId, 'на', status, 'URL:', url);
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body
      });
      
      console.log('Ответ API обновления статуса:', response.status, response.statusText);
      
      if (!response.ok) {
        const errText = await response.text().catch(() => '');
        console.error('Ошибка API обновления статуса:', response.status, errText);
        throw new Error(errText || `API ${response.status}`);
      }
      
      const updatedAppointment = await response.json();
      console.log('Обновленная запись:', updatedAppointment);
      
      // Обновляем локальное состояние
      setAppointments(prev => prev.map(apt => 
        apt.id === appointmentId ? { ...apt, status: updatedAppointment.status || status } : apt
      ));
      
      await loadAppointments();
      toast.success('Статус обновлен');
      return updatedAppointment;
    } catch (error) {
      console.error('RegistrarPanel: Update status error:', error);
      toast.error('Не удалось обновить статус: ' + error.message);
      return null;
    }
  }, [API_BASE, loadAppointments]);

  // Функция для определения варианта Badge по статусу
  const getStatusVariant = (status) => {
    const variantMap = {
      'plan': 'primary',
      'confirmed': 'success',
      'queued': 'warning',
      'in_cabinet': 'purple',
      'done': 'success',
      'cancelled': 'danger',
      'no_show': 'orange',
      'paid_pending': 'warning',
      'paid': 'success'
    };
    return variantMap[status] || 'default';
  };

  const handleBulkAction = useCallback(async (action, reason = '') => {
    if (appointmentsSelected.size === 0) return;
    
    // Подтверждение для опасных действий
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

  // Горячие клавиши
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Отладка всех нажатий клавиш
      console.log('Key pressed:', e.key, 'Ctrl:', e.ctrlKey, 'Alt:', e.altKey, 'Target:', e.target.tagName);
      
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        console.log('Ignoring key press in input/textarea');
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
          // Открываем мастер создания записи
          setSelectedPatientId(null);
          setPatientSuggestions([]);
          setShowPatientSuggestions(false);
          setShowWizard(true);
        } else if (e.key === '1') setActiveTab('welcome');
        else if (e.key === '2') setActiveTab('appointments');
        else if (e.key === '3') setActiveTab('cardio');
        else if (e.key === '4') setActiveTab('derma');
        else if (e.key === '5') setActiveTab('queue');
        else if (e.key === 'a') {
          e.preventDefault();
          console.log('Ctrl+A: Выбрать все записи');
          const allIds = filteredAppointments.map(a => a.id);
          setAppointmentsSelected(new Set(allIds));
          console.log('Выбрано записей:', allIds.length);
        } else if (e.key === 'd') {
          e.preventDefault();
          console.log('Ctrl+D: Снять выделение');
          setAppointmentsSelected(new Set());
        }
      } else if (e.altKey) {
        console.log('Alt key pressed with:', e.key, 'Selected rows:', appointmentsSelected.size);
        if (e.key === '1') { 
          e.preventDefault(); 
          console.log('Alt+1: Подтвердить');
          if (appointmentsSelected.size > 0) {
            handleBulkAction('confirmed'); 
          } else {
            console.log('Нет выбранных записей для подтверждения');
          }
        } else if (e.key === '2') { 
          e.preventDefault(); 
          console.log('Alt+2: Отменить');
          if (appointmentsSelected.size > 0) {
            const reason = window.prompt('Причина отмены');
            if (reason) handleBulkAction('cancelled', reason);
          } else {
            console.log('Нет выбранных записей для отмены');
          }
        } else if (e.key === '3') { 
          e.preventDefault(); 
          console.log('Alt+3: Неявка');
          if (appointmentsSelected.size > 0) {
            handleBulkAction('no_show'); 
          } else {
            console.log('Нет выбранных записей для неявки');
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

  // ✅ УНИВЕРСАЛЬНАЯ СИСТЕМА ФИЛЬТРАЦИИ ПО ОТДЕЛАМ
  const isInDepartment = useCallback((appointment, departmentKey) => {
    const dept = (appointment.department?.toLowerCase() || '');
    const specialty = (appointment.doctor_specialty?.toLowerCase() || '');
    const appointmentServiceCodes = appointment.service_codes || []; // Используем коды услуг
    
    // ✅ ОБНОВЛЕННАЯ СИСТЕМА: маппинг по кодам категорий
    const departmentCategoryMapping = {
      'cardio': ['K'],           // Кардиология (консультации кардиолога)
      'echokg': ['ECG'],         // ЭКГ - отдельная категория
      'derma': ['D'],            // Дерматология
      'dental': ['S'],           // Стоматология
      'lab': ['L'],              // Лаборатория
      'procedures': ['C', 'O']   // Процедуры включают косметологию (C) и прочие процедуры (O)
    };
    
    // Получаем коды категорий для данного отдела
    const targetCategoryCodes = departmentCategoryMapping[departmentKey] || [];
    
    // Маппинг кодов услуг к категориям (поддерживает разные форматы)
    const getServiceCategoryByCode = (serviceCode) => {
      if (!serviceCode) return null;
      
      // ЭКГ - отдельная категория
      if (serviceCode === 'CARD_ECG' || serviceCode.includes('ECG') || serviceCode.includes('ЭКГ')) return 'ECG';
      
      // ЭхоКГ - тоже кардиология, но отдельно от ЭКГ
      if (serviceCode === 'CARD_ECHO' || serviceCode.includes('ECHO')) return 'K';
      
      // Новый формат кодов (K11, D01, S05, L12, etc.)
      if (serviceCode.match(/^K\d+$/)) return 'K';  // K11, K12 -> Кардиология
      if (serviceCode.match(/^D\d+$/)) return 'D';  // D01, D02 -> Дерматология  
      if (serviceCode.match(/^S\d+$/)) return 'S';  // S01, S02 -> Стоматология
      if (serviceCode.match(/^L\d+$/)) return 'L';  // L01, L02 -> Лаборатория
      if (serviceCode.match(/^C\d+$/)) return 'C';  // C01, C02 -> Косметология
      if (serviceCode.match(/^O\d+$/)) return 'O';  // O01, O02 -> Прочие процедуры
      
      // Старый формат кодов (префиксы)
      if (serviceCode.startsWith('CONS_CARD')) return 'K';
      if (serviceCode.startsWith('CONS_DERM') || serviceCode.startsWith('DERMA_')) return 'D';
      if (serviceCode.startsWith('CONS_DENT') || serviceCode.startsWith('DENT_') || serviceCode.startsWith('STOM_')) return 'S';
      if (serviceCode.startsWith('LAB_')) return 'L';
      if (serviceCode.startsWith('COSM_')) return 'C';
      if (serviceCode.startsWith('PROC_')) return 'O';
      
      // Дополнительные паттерны для кардиологии
      if (serviceCode.startsWith('CARD_')) return 'K';
      
      return null;
    };
    
    // Проверяем различными способами
    const matchesByDepartment = dept.includes(departmentKey) || 
                               (departmentKey === 'derma' && (dept.includes('dermat') || dept.includes('dermatology'))) ||
                               (departmentKey === 'dental' && (dept.includes('dental') || dept.includes('stoma') || dept.includes('dentistry'))) ||
                               (departmentKey === 'cardio' && dept.includes('cardiology')) ||
                               (departmentKey === 'echokg' && (dept.includes('ecg') || dept.includes('экг'))) ||
                               (departmentKey === 'lab' && (dept.includes('lab') || dept.includes('laboratory'))) ||
                               (departmentKey === 'procedures' && (dept.includes('procedures') || dept.includes('cosmetology')));
    
    const matchesBySpecialty = specialty.includes(departmentKey) ||
                              (departmentKey === 'derma' && specialty.includes('dermat')) ||
                              (departmentKey === 'dental' && (specialty.includes('dental') || specialty.includes('stoma'))) ||
                              (departmentKey === 'cardio' && specialty.includes('cardio')) ||
                              (departmentKey === 'echokg' && (specialty.includes('ecg') || specialty.includes('экг'))) ||
                              (departmentKey === 'lab' && (specialty.includes('lab') || specialty.includes('laboratory')));
    
    // ✅ НОВАЯ ЛОГИКА: проверяем по кодам услуг
    const matchesByServices = appointmentServiceCodes.some(serviceCode => {
      const serviceCategory = getServiceCategoryByCode(serviceCode);
      return targetCategoryCodes.includes(serviceCategory);
    });
    
    const result = matchesByDepartment || matchesBySpecialty || matchesByServices;
    
    // Отладка убрана - система работает корректно
    
    // ✅ Возвращаем результат универсальной проверки
    return result;
  }, [services]);

  // Мемоизированные счетчики и индикаторы по отделам
  const departmentStats = useMemo(() => {
    const stats = {};
    const departments = ['cardio', 'echokg', 'derma', 'dental', 'lab', 'procedures'];
    
    departments.forEach(dept => {
      const deptAppointments = appointments.filter(a => isInDepartment(a, dept));
      const todayAppointments = deptAppointments.filter(a => {
        // Проверяем и текущую дату и поле date
        const appointmentDate = a.date || a.appointment_date;
        return appointmentDate === todayStr;
      });
      
      stats[dept] = {
        todayCount: todayAppointments.length,
        hasActiveQueue: deptAppointments.some(a => a.status === 'queued'),
        hasPendingPayments: deptAppointments.some(a => a.status === 'paid_pending' || a.payment_status === 'pending')
      };
    });
    
    return stats;
  }, [appointments, todayStr]);

  // Счетчик «сегодня» по отделам
  const getDepartmentCount = useCallback((departmentKey) => {
    return departmentStats[departmentKey]?.todayCount || 0;
  }, [departmentStats]);

  // Индикаторы статусов по отделу
  const hasActiveQueue = useCallback((departmentKey) => {
    return departmentStats[departmentKey]?.hasActiveQueue || false;
  }, [departmentStats]);

  const hasPendingPayments = useCallback((departmentKey) => {
    return departmentStats[departmentKey]?.hasPendingPayments || false;
  }, [departmentStats]);

  // Мемоизированная фильтрация записей по выбранной вкладке (повторный клик снимает фильтр → activeTab === null)
  // Фильтрация по вкладке + по дате (?date=YYYY-MM-DD) + по поиску (?q=...)
  const searchDate = searchParams.get('date');
  const searchQuery = (searchParams.get('q') || '').toLowerCase();
  const statusFilter = searchParams.get('status');

  const filteredAppointments = useMemo(() => {
    // console.log('Filtering appointments:', {
    //   total: appointments.length,
    //   activeTab,
    //   searchDate,
    //   statusFilter,
    //   searchQuery
    // });
    
    const filtered = appointments.filter(appointment => {
      // Фильтр по вкладке (отдел)
      if (activeTab && !isInDepartment(appointment, activeTab)) {
        return false;
      }
      // Фильтр по дате: если не задана, показываем все даты
      if (searchDate && appointment.date !== searchDate) return false;
      // Фильтр по статусу
      if (statusFilter && appointment.status !== statusFilter) return false;
      // Поиск по ФИО/телефону/услугам
      if (searchQuery) {
        const inFio = (appointment.patient_fio || '').toLowerCase().includes(searchQuery);
        const inPhone = (appointment.patient_phone || '').toLowerCase().includes(searchQuery);
        const inServices = Array.isArray(appointment.services) && appointment.services.some(s => String(s).toLowerCase().includes(searchQuery));
        if (!inFio && !inPhone && !inServices) return false;
      }
    return true;
  });

    // console.log('Filtered appointments result:', filtered.length);
    return filtered;
  }, [appointments, activeTab, searchDate, statusFilter, searchQuery, isInDepartment]);

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
            onClick={loadAppointments}
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
          <span>Данные загружены с сервера ({count} записей)</span>
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

  // Мемоизированная статистика для экрана приветствия
  const stats = useMemo(() => {
    const todayStr = new Date().toISOString().split('T')[0];
    return {
    totalPatients: appointments.length,
      todayAppointments: appointments.filter(a => a.date === todayStr).length,
    pendingPayments: appointments.filter(a => a.status === 'paid_pending').length,
    activeQueues: appointments.filter(a => a.status === 'queued').length
  };
  }, [appointments]);

  // Простой режим выбора врача (для 3 специализаций)
  const simpleDoctorMode = true;
  const getDoctorBySpecialty = useCallback((spec) => {
    const found = doctors.find(d => d.specialty === spec) || null;
    return found;
  }, [doctors]);

  // Обработчик действий контекстного меню
  const handleContextMenuAction = useCallback(async (action, row) => {
    switch (action) {
      case 'view':
        setSelectedAppointment(row);
        setShowAppointmentFlow(true);
        break;
      case 'edit':
        console.log('Редактирование записи:', row);
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
        setSelectedAppointment(row);
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
      default:
        console.log('Неизвестное действие:', action);
        break;
    }
  }, [updateAppointmentStatus, handleStartVisit]);

  return (
    <div style={{ ...pageStyle, overflow: 'hidden' }} role="main" aria-label="Панель регистратора">
      <ToastContainer position="bottom-right" />
      {/* Фиксированная верхняя часть убрана - используется глобальный хедер */}

      {/* Skip to content link for screen readers */}
      <a 
        href="#main-content" 
        style={{
          position: 'absolute',
          left: '-9999px',
          top: '0',
          zIndex: 9999,
          padding: '8px 16px',
          background: getColor('primary', 600),
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
          margin: `0 ${getSpacing('md')}`,
          maxWidth: 'none',
          width: 'calc(100vw - 32px)'
        }}>
          <ModernTabs
            activeTab={activeTab}
            onTabChange={setActiveTab}
            departmentStats={departmentStats}
            theme={theme}
            language={language}
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
              margin: `0 ${getSpacing('md')} ${getSpacing('xl')} ${getSpacing('md')}`,
              maxWidth: 'none',
              width: 'calc(100vw - 32px)'
            }}>
              <Card.Header>
                <AnimatedTransition type="slide" direction="up" delay={200}>
                  <h1 style={{ 
                    margin: 0, 
                    fontSize: getFontSize('3xl'), 
                    fontWeight: '400', 
                    lineHeight: '1.25',
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '12px' 
                  }}>
                    {t('welcome')} в панель регистратора!
                    <span style={{ fontSize: getFontSize('2xl') }}>👋</span>
                  </h1>
                </AnimatedTransition>
                <AnimatedTransition type="fade" delay={400}>
                  <div style={{ fontSize: getFontSize('lg'), opacity: 0.9, lineHeight: '1.5' }}>
                    {new Date().toLocaleDateString(language === 'ru' ? 'ru-RU' : 'uz-UZ', { 
                      weekday: 'long', 
                      year: 'numeric', 
                      month: 'long', 
                      day: 'numeric' 
                    })}
        </div>
                </AnimatedTransition>
              </Card.Header>
            
            <Card.Content>
              {/* Современная статистика */}
              <ModernStatistics
                appointments={appointments}
                departmentStats={departmentStats}
                language={language}
                onExport={() => {
                  // Экспорт данных
                  console.log('Экспорт статистики');
                }}
                onRefresh={() => {
                  // Обновление данных - загружаем только записи
                  loadAppointments();
                }}
              />

              {/* Онлайн-очередь */}
              <AnimatedTransition type="fade" delay={800}>
                <div style={{ marginBottom: '32px' }}>
                  <h2 style={{ fontSize: '24px', marginBottom: '20px', color: accentColor }}>
                    📱 Онлайн-очередь
                  </h2>
                  <ModernQueueManager
                    selectedDate={selectedDate}
                    selectedDoctor={selectedDoctor?.id?.toString() || ''}
                    searchQuery={''}
                    onQueueUpdate={loadIntegratedData}
                    language={language}
                    theme={theme}
                    doctors={doctors}
                  />
                </div>
              </AnimatedTransition>

              {/* Панель управления и фильтров */}
              <AnimatedTransition type="fade" delay={1000}>
                <div style={{ marginBottom: '32px' }}>
                  <AnimatedTransition type="slide" direction="up" delay={1100}>
                    <h2 style={{ fontSize: '24px', marginBottom: '20px', color: accentColor }}>
                      🎛️ Панель управления
                    </h2>
                  </AnimatedTransition>
                  
                  {/* Быстрые действия */}
                  <AnimatedTransition type="fade" delay={1200}>
                    <div style={{ 
                      display: 'grid', 
                      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                      gap: '16px',
                      alignItems: 'stretch',
                      marginBottom: '24px'
                    }}>
                  <AnimatedTransition type="scale" delay={1300}>
                    <button 
                          type="button"
                          onClick={(e) => {
                            console.log('Кнопка "Новая запись" нажата');
                            // Открываем мастер создания записи
                            setSelectedPatientId(null);
                            setPatientSuggestions([]);
                            setShowPatientSuggestions(false);
                            setShowWizard(true);
                          }}
                          aria-label="Create new appointment"
                      style={{
                            padding: '12px 16px', 
                            borderRadius: 8, 
                            fontSize: 14, 
                            fontWeight: '600',
                            cursor: 'pointer',
                            pointerEvents: 'auto',
                            background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                            color: 'white',
                            border: 'none',
                            boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)',
                            transition: 'all 0.2s ease'
                      }}
                    >
                      ➕ {t('new_appointment')}
                      {!wizardSettingsLoading && (
                        <span style={{
                          marginLeft: '8px',
                          fontSize: '10px',
                          opacity: 0.8,
                          background: useNewWizard ? '#10b981' : '#f59e0b',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          fontWeight: '500'
                        }}>
                          {useNewWizard ? 'V2' : 'V1'}
                        </span>
                      )}
                    </button>
                  </AnimatedTransition>

                  {/* Кнопка модуля оплаты */}
                  <AnimatedTransition type="scale" delay={1350}>
                    <button 
                      type="button"
                      onClick={() => setShowPaymentManager(true)}
                      aria-label="Open payment module"
                      style={{
                        padding: '12px 16px', 
                        backgroundColor: '#8b5cf6', 
                        color: 'white', 
                        border: 'none', 
                        borderRadius: '8px', 
                        cursor: 'pointer',
                        fontSize: '14px',
                        fontWeight: '500',
                        transition: 'all 0.2s ease',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                      }}
                    >
                      💳 Модуль оплаты
                    </button>
                  </AnimatedTransition>
                      
                  <AnimatedTransition type="scale" delay={1400}>
                    <button 
                          type="button"
                      style={{
                            padding: '12px 16px', 
                            borderRadius: 8, 
                            fontSize: 14, 
                            fontWeight: '600',
                            cursor: 'pointer',
                            pointerEvents: 'auto',
                            background: 'white',
                            color: '#374151',
                            border: '1px solid #d1d5db',
                            boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                            transition: 'all 0.2s ease'
                          }}
                          onClick={(e) => {
                            console.log('Кнопка "Экспорт CSV" нажата');
                            const csvContent = generateCSV(appointments);
                            const filename = `appointments_${new Date().toISOString().split('T')[0]}.csv`;
                            downloadCSV(csvContent, filename);
                            toast.success(`Экспортировано ${appointments.length} записей`);
                      }}
                    >
                      📊 {t('export_csv')}
                    </button>
                  </AnimatedTransition>
                    </div>
                  </AnimatedTransition>

                  {/* Фильтры и навигация */}
                  <AnimatedTransition type="fade" delay={1500}>
                    <div style={{
                      background: theme === 'light' ? '#f8f9fa' : '#374151',
                      borderRadius: '12px',
                      padding: '20px',
                      border: `1px solid ${theme === 'light' ? '#e9ecef' : '#4b5563'}`
                    }}>
                      <h3 style={{ 
                        fontSize: '18px', 
                        marginBottom: '16px', 
                        color: textColor,
                        fontWeight: '600'
                      }}>
                        🔍 Фильтры и навигация
                      </h3>
                      
                      <div style={{ 
                        display: 'grid', 
                        gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', 
                        gap: '12px',
                        alignItems: 'stretch'
                      }}>
                    <button 
                          type="button"
                      style={{
                            padding: '10px 14px', 
                            borderRadius: 8, 
                            fontSize: 14, 
                            fontWeight: '500',
                            cursor: 'pointer',
                            pointerEvents: 'auto',
                            background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
                            color: 'white',
                            border: 'none',
                            boxShadow: '0 2px 4px 0 rgba(245, 158, 11, 0.3)',
                            transition: 'all 0.2s ease'
                          }}
                          onClick={(e) => {
                            console.log('Кнопка "Записи на сегодня" нажата');
                            // Переходим к основной таблице с фильтром по сегодняшней дате
                            const today = new Date().toISOString().split('T')[0];
                            window.location.href = `/registrar-panel?date=${today}`;
                          }}
                        >
                          📅 Записи на сегодня
                        </button>
                        
                        <button 
                          type="button"
                          style={{ 
                            padding: '10px 14px', 
                            borderRadius: 8, 
                            fontSize: 14, 
                            fontWeight: '500',
                            cursor: 'pointer',
                            pointerEvents: 'auto',
                            background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                            color: 'white',
                            border: 'none',
                            boxShadow: '0 2px 4px 0 rgba(16, 185, 129, 0.3)',
                            transition: 'all 0.2s ease'
                          }}
                          onClick={(e) => {
                            console.log('Кнопка "Активная очередь" нажата');
                            // Переходим к таблице с фильтром по статусу "В очереди"
                            window.location.href = `/registrar-panel?status=queued`;
                          }}
                        >
                          🟢 Активная очередь
                    </button>
                        
                    <button 
                          type="button"
                      style={{
                            padding: '10px 14px', 
                            borderRadius: 8, 
                            fontSize: 14, 
                            fontWeight: '500',
                            cursor: 'pointer',
                            pointerEvents: 'auto',
                            background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                            color: 'white',
                            border: 'none',
                            boxShadow: '0 2px 4px 0 rgba(59, 130, 246, 0.3)',
                            transition: 'all 0.2s ease'
                          }}
                          onClick={(e) => {
                            console.log('Кнопка "Ожидают оплаты" нажата');
                            // Переходим к таблице с фильтром по статусу "Ожидает оплаты"
                            window.location.href = `/registrar-panel?status=paid_pending`;
                          }}
                        >
                          💰 Ожидают оплаты
                        </button>
                        
                        <button 
                          type="button"
                          style={{ 
                            padding: '10px 14px', 
                            borderRadius: 8, 
                            fontSize: 14, 
                            fontWeight: '500',
                            cursor: 'pointer',
                            pointerEvents: 'auto',
                            background: 'white',
                            color: '#374151',
                            border: '1px solid #d1d5db',
                            boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                            transition: 'all 0.2s ease'
                          }}
                          onClick={(e) => {
                            console.log('Кнопка "Все записи" нажата');
                            // Переходим к основной таблице без фильтров
                            window.location.href = `/registrar-panel`;
                          }}
                        >
                          📋 Все записи
                    </button>
                        
                        <button 
                          type="button"
                          style={{ 
                            padding: '10px 14px', 
                            borderRadius: 8, 
                            fontSize: 14, 
                            fontWeight: '500',
                            cursor: 'pointer',
                            pointerEvents: 'auto',
                            background: 'white',
                            color: '#374151',
                            border: '1px solid #d1d5db',
                            boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                            transition: 'all 0.2s ease'
                          }}
                          onClick={(e) => {
                            console.log('Кнопка "Онлайн-очередь" нажата');
                            // Переходим к экрану онлайн-очереди
                            window.location.href = `/registrar-panel?view=queue`;
                          }}
                        >
                          🌐 Онлайн-очередь
                        </button>
                        
                        <button 
                          type="button"
                          style={{ 
                            padding: '10px 14px', 
                            borderRadius: 8, 
                            fontSize: 14, 
                            fontWeight: '500',
                            cursor: 'pointer',
                            pointerEvents: 'auto',
                            background: 'white',
                            color: '#374151',
                            border: '1px solid #d1d5db',
                            boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                            transition: 'all 0.2s ease'
                          }}
                          onClick={(e) => {
                            console.log('Кнопка "Обновить данные" нажата');
                            // Обновляем данные
                            loadAppointments();
                            toast.success('Данные обновлены');
                          }}
                        >
                          🔄 Обновить данные
                        </button>
                      </div>
                    </div>
                  </AnimatedTransition>
                </div>
              </AnimatedTransition>

              {/* Недавние записи */}
              {appointments.length > 0 && (
                <div>
                  <h3 style={{ fontSize: '20px', marginBottom: '16px', color: accentColor }}>
                    📋 Недавние записи
                  </h3>
                  <div style={{ 
                    background: cardBg,
                    border: `1px solid ${borderColor}`,
                    borderRadius: '8px',
                    padding: '16px'
                  }}>
            {/* Индикатор источника данных */}
            <DataSourceIndicator count={appointments.length} />

            <EnhancedAppointmentsTable
              data={appointments.slice(0, 5)}
              loading={appointmentsLoading}
              theme={theme}
              language={language}
              selectedRows={appointmentsSelected}
              outerBorder={true}
              services={services}
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
                console.log('Открыть детали записи:', row);
                // Здесь можно открыть модальное окно с деталями записи
              }}
              onActionClick={(action, row, event) => {
                switch (action) {
                  case 'view':
                    console.log('Просмотр записи:', row);
                    // Открыть модальное окно с деталями записи
                    setSelectedAppointment(row);
                    setShowAppointmentFlow(true);
                    break;
                  case 'edit':
                    console.log('Редактирование записи:', row);
                    // Открыть форму редактирования (пока что показываем уведомление)
                    toast('Функция редактирования записи будет добавлена в следующих версиях', { 
                      icon: 'ℹ️',
                      style: {
                        background: '#3b82f6',
                        color: 'white'
                      }
                    });
                    break;
                  case 'payment':
                    console.log('Открытие модального окна оплаты для записи (welcome):', row);
                    setPaymentDialog({ open: true, row, paid: false, source: 'welcome' });
                    break;
                  case 'in_cabinet':
                    console.log('Отправка пациента в кабинет (welcome):', row);
                    updateAppointmentStatus(row.id, 'in_cabinet');
                    break;
                  case 'call':
                    console.log('Вызов пациента (welcome):', row);
                    handleStartVisit(row);
                    break;
                  case 'complete':
                    console.log('Завершение приёма (welcome):', row);
                    updateAppointmentStatus(row.id, 'done');
                    break;
                  case 'print':
                    console.log('Печать талона (welcome):', row);
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
                  </div>
                </div>
              )}
            </Card.Content>
          </Card>
          </AnimatedTransition>
        )}

        {/* Онлайн-очередь по параметру view=queue */}
        {searchParams.get('view') === 'queue' && (
          <AnimatedTransition type="fade" delay={100}>
            <Card variant="default" style={{ margin: `0 ${getSpacing('xl')} ${getSpacing('xl')} ${getSpacing('xl')}` }}>
              <Card.Header>
                <AnimatedTransition type="slide" direction="up" delay={200}>
                  <h1 style={{ 
                    margin: 0, 
                    fontSize: getFontSize('3xl'), 
                    fontWeight: '400', 
                    lineHeight: '1.25',
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '12px' 
                  }}>
                    📱 Онлайн-очередь
                  </h1>
                </AnimatedTransition>
                <AnimatedTransition type="fade" delay={400}>
                  <div style={{ fontSize: getFontSize('lg'), opacity: 0.9, lineHeight: '1.5' }}>
                    Управление онлайн-записью и QR кодами для очереди
                  </div>
                </AnimatedTransition>
              </Card.Header>
            
              <Card.Content>
              <ModernQueueManager 
                selectedDate={searchParams.get('date') || new Date().toISOString().split('T')[0]}
                selectedDoctor={searchParams.get('doctor') || selectedDoctor?.id?.toString() || ''}
                searchQuery={searchParams.get('q') || ''}
                onQueueUpdate={loadAppointments}
                language={language}
                theme={theme}
                doctors={doctors}
              />
              </Card.Content>
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
              margin: `0 ${isMobile ? getSpacing('md') : getSpacing('md')} ${getSpacing('xl')} ${isMobile ? getSpacing('md') : getSpacing('md')}`,
            borderRadius: isMobile ? '0 0 12px 12px' : '0 0 20px 20px',
              maxWidth: 'none',
              width: 'calc(100vw - 32px)'
          }}>
            <div style={{
              ...tableContentStyle,
              padding: isMobile ? getSpacing('sm') : getSpacing('md')
            }}>
              
              {/* Массовые действия */}
              {appointmentsSelected.size > 0 && (
              <div style={{
                display: 'flex',
                  gap: isMobile ? getSpacing('xs') : '12px', 
                alignItems: 'center',
                  padding: isMobile ? getSpacing('sm') : '16px',
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
                      console.log('Кнопка "Подтвердить" нажата через onMouseDown');
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
                      console.log('Кнопка "Отменить" нажата через onMouseDown');
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
                      console.log('Кнопка "Неявка" нажата через onMouseDown');
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
                    console.log('Открыть детали записи:', row);
                    // Здесь можно открыть модальное окно с деталями записи
                  }}
                  onActionClick={(action, row, event) => {
                    switch (action) {
                      case 'view':
                        console.log('Просмотр записи:', row);
                        // Открыть модальное окно с деталями записи
                        setSelectedAppointment(row);
                        setShowAppointmentFlow(true);
                        break;
                      case 'edit':
                        console.log('Редактирование записи:', row);
                        // Открыть форму редактирования (пока что показываем уведомление)
                        toast('Функция редактирования записи будет добавлена в следующих версиях', { 
                          icon: 'ℹ️',
                          style: {
                            background: '#3b82f6',
                            color: 'white'
                          }
                        });
                        break;
                      case 'payment':
                        console.log('Открытие модального окна оплаты для записи:', row);
                        setPaymentDialog({ open: true, row, paid: false, source: 'table' });
                        break;
                      case 'in_cabinet':
                        console.log('Отправка пациента в кабинет:', row);
                        updateAppointmentStatus(row.id, 'in_cabinet');
                        break;
                      case 'call':
                        console.log('Вызов пациента:', row);
                        handleStartVisit(row);
                        break;
                      case 'complete':
                        console.log('Завершение приёма:', row);
                        updateAppointmentStatus(row.id, 'done');
                        break;
                      case 'print':
                        console.log('Печать талона:', row);
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
          // Локальное обновление статуса
          setAppointments(prev => prev.map(apt => 
            apt.id === appointmentId ? {
              ...apt,
              status: 'canceled',
              _locallyModified: true,
              _cancelReason: reason
            } : apt
          ));
        }}
      />

      <PaymentDialog
        isOpen={paymentDialog.open}
        onClose={() => setPaymentDialog({ open: false, row: null, paid: false, source: null })}
        appointment={paymentDialog.row}
        onPaymentSuccess={async (paymentData) => {
          // ✅ ИСПРАВЛЕНО: используем реальный API вызов через handlePayment
          const appointment = paymentDialog.row;
          if (appointment) {
            const updated = await handlePayment(appointment);
            if (updated) {
              // Статус уже правильно установлен в handlePayment (status: 'queued')
              console.log('PaymentDialog: Оплата успешна, статус обновлен:', updated);
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

      <PrintDialog
        isOpen={printDialog.open}
        onClose={() => setPrintDialog({ open: false, type: '', data: null })}
        documentType={printDialog.type}
        documentData={printDialog.data}
        onPrint={async (printerName, docType, docData) => {
          console.log('Printing:', { printerName, docType, docData });
          // Здесь можно добавить реальную логику печати
        }}
      />

      {/* A/B тест: условный рендеринг мастера */}
      {!wizardSettingsLoading && (
        useNewWizard ? (
          <AppointmentWizardV2
            isOpen={showWizard}
            onClose={() => {
              console.log('AppointmentWizardV2 closing');
              setShowWizard(false);
            }}
            isProcessing={isProcessing}
            setIsProcessing={setIsProcessing}
            onComplete={async (wizardData) => {
              console.log('AppointmentWizardV2 completed successfully:', wizardData);
              
              // Новый мастер уже создал корзину, просто обновляем данные
              try {
                // Обновляем данные
                await Promise.all([
                  loadAppointments(),
                  loadIntegratedData()
                ]);
                
                setShowWizard(false);
                toast.success('Запись успешно создана!');
              } catch (error) {
                console.error('Error refreshing data after wizard completion:', error);
                // Не показываем ошибку пользователю, так как запись уже создана
                setShowWizard(false);
                toast.success('Запись создана! Обновите страницу для отображения изменений.');
              }
            }}
          />
        ) : (
          <AppointmentWizard
            isOpen={showWizard}
            onClose={() => {
              console.log('AppointmentWizard closing');
              setShowWizard(false);
            }}
            doctors={doctors}
            services={services}
            onComplete={async (wizardData) => {
          console.log('Creating appointment with data:', wizardData);
          console.log('wizardData.patient:', wizardData.patient);
          console.log('wizardData.appointment:', wizardData.appointment);
          console.log('wizardData.payment:', wizardData.payment);
          
          try {
            // Создание пациента (если нужно)
            let patientId = selectedPatientId;
            if (!patientId) {
              try {
                const patientResponse = await fetch(`${API_BASE}/api/v1/patients/`, {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
                  },
                  body: JSON.stringify({
                    last_name: wizardData.patient.fio.split(' ')[0] || '',
                    first_name: wizardData.patient.fio.split(' ')[1] || '',
                    middle_name: wizardData.patient.fio.split(' ').slice(2).join(' ') || null,
                    birth_date: wizardData.patient.birth_date,
                    phone: wizardData.patient.phone,
                    address: wizardData.patient.address || '',
                    doc_number: wizardData.patient.doc_number || null
                  })
                });
              
              if (patientResponse.ok) {
                const patient = await patientResponse.json();
                patientId = patient.id;
                console.log('Created new patient with ID:', patientId);
              } else {
                const errorData = await patientResponse.json().catch(() => ({}));
                console.log('Patient creation error:', errorData);
                
                // Если пациент уже существует, пытаемся найти его
                if (errorData.detail && errorData.detail.includes('уже существует')) {
                  try {
                    const searchResponse = await fetch(`${API_BASE}/api/v1/patients/?phone=${encodeURIComponent(wizardData.patient.phone)}`, {
                      headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` }
                    });
                    if (searchResponse.ok) {
                      const searchData = await searchResponse.json();
                      if (searchData.length > 0) {
                        patientId = searchData[0].id;
                        console.log('Found existing patient with ID:', patientId);
                      }
                    }
                  } catch (findError) {
                    console.warn('Error finding existing patient:', findError);
                  }
                }
                
                if (!patientId) {
                  const details = Array.isArray(errorData.detail) 
                    ? errorData.detail.map(err => `${err.loc?.join('.')}: ${err.msg}`).join(', ')
                    : errorData.detail || 'Неверные данные пациента';
                  throw new Error('Ошибка создания пациента: ' + details);
                }
              }
            } catch (fetchError) {
              // Обработка CORS и других ошибок сети
              if (fetchError.message.includes('401') || fetchError.message.includes('Unauthorized')) {
                console.warn('Токен недействителен, требуется повторный вход');
                localStorage.removeItem('auth_token');
                toast.error('Сессия истекла. Перенаправляем на страницу входа...');
                setTimeout(() => {
                  window.location.href = '/login';
                }, 2000);
                return;
              }
              
              console.warn('Backend недоступен, используем демо-режим:', fetchError.message);
              
              // В демо-режиме создаем виртуального пациента
              patientId = Math.floor(Math.random() * 1000) + 1000;
              console.log('Created demo patient with ID:', patientId);
              
              toast.success('Запись создана в демо-режиме (backend недоступен)');
            }
            }
            
            // Создание записи
            try {
              // Подготовим корректный payload и подробный лог
              const _doctorId = wizardData.appointment?.doctor_id ? parseInt(wizardData.appointment.doctor_id) : (selectedDoctor?.id || null);
              const _visitType = wizardData.appointment?.visit_type === 'Платный' ? 'paid'
                : wizardData.appointment?.visit_type === 'Повторный' ? 'repeat'
                : wizardData.appointment?.visit_type === 'Льготный' ? 'free' : 'paid';
              const paymentMethod = wizardData.payment?.method || wizardData.payment?.type || 'Наличные';
              const _paymentType = (paymentMethod === 'Карта' ? 'card' : paymentMethod === 'Онлайн' ? 'online' : 'cash');
              // ✅ ИСПРАВЛЕННАЯ ЛОГИКА МАППИНГА УСЛУГ
              const _services = Array.isArray(wizardData.appointment?.services)
                ? wizardData.appointment.services
                    .map(s => {
                      // Всегда возвращаем ID услуги как строку
                      if (typeof s === 'number') return String(s);
                      if (typeof s === 'string' && /^\d+$/.test(s)) return s; // Уже ID как строка
                      if (typeof s === 'object' && (s?.id || s?.service_id)) {
                        return String(s.id || s.service_id);
                      }
                      // ❌ НЕ используем s?.code || s?.name - это может быть группа!
                      return null; // Неизвестный формат услуги
                    })
                    .filter(s => s && s !== 'null' && s !== 'undefined')
                : [];

              const payload = {
                patient_id: patientId,
                doctor_id: _doctorId || null,
                appointment_date: wizardData.appointment.date,
                appointment_time: wizardData.appointment.time || (() => {
                  // Генерируем случайное время от 09:00 до 17:00
                  const hour = 9 + Math.floor(Math.random() * 8);
                  const minute = Math.floor(Math.random() * 4) * 15; // 00, 15, 30, 45
                  return `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
                })(),
                department: wizardData.appointment.department || selectedDoctor?.specialty || (() => {
                  // Определяем отделение по выбранным услугам (по структуре демо-режима)
                  const labServices = ['1', '2', '3', '4', '38', '39', '40', '41', '42', '43']; // Лаборатория: демо ID 1,2,3,4 + API ID 38-43
                  const dermaServices = ['5', '6', '7', '8']; // Дерматология: демо ID 5,6,7,8
                  const cosmetoServices = ['9', '10', '11', '12', '20', '21', '25', '26', '27']; // Косметология: демо ID 9,10,11,12 + API ID 20,21,25-27
                  const cardioServices = ['13', '14', '15', '16', '17', '28', '29', '30', '46']; // Кардиология: демо ID 13,14,15,16,17 + API ID 28-30,46
                  const dentistryServices = ['18', '19', '37']; // Стоматология: демо ID 18,19 + API ID 37
                  const procedureServices = ['22', '23', '24']; // Процедуры: демо ID 22,23,24
                  
                  if (_services.some(s => cardioServices.includes(s))) return 'cardiology';
                  if (_services.some(s => dermaServices.includes(s))) return 'dermatology';
                  if (_services.some(s => cosmetoServices.includes(s))) return 'cosmetology';
                  if (_services.some(s => dentistryServices.includes(s))) return 'dentistry';
                  if (_services.some(s => labServices.includes(s))) return 'laboratory';
                  if (_services.some(s => procedureServices.includes(s))) return 'procedures';
                  return 'procedures'; // По умолчанию для прочих услуг
                })(),
                notes: wizardData.appointment.notes || '',
                status: 'scheduled',
                visit_type: _visitType,
                payment_type: _paymentType,
                services: _services,
                payment_amount: wizardData.payment?.amount || 0,
                payment_currency: 'UZS'
              };
              console.log('Raw services from wizard:', wizardData.appointment?.services);
              console.log('Processed services:', _services);
              console.log('Appointment payload:', payload);

              const appointmentResponse = await fetch(`${API_BASE}/api/v1/appointments/`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
                },
                body: JSON.stringify(payload)
              });
              
              if (appointmentResponse.ok) {
                const appointment = await appointmentResponse.json();
                
                // Обновляем локальный список и перезагружаем данные
                setAppointments(prev => [appointment, ...prev]);
                
                // Принудительно обновляем данные из API
                setTimeout(() => {
                  loadAppointments();
                }, 500);
                
                // Закрываем мастер
                setShowWizard(false);
                setSelectedPatientId(null);
                
                toast.success('Запись успешно создана!');
                
                // Предлагаем печать талона с данными пациента
                setTimeout(() => {
                        setPrintDialog({ 
                          open: true, 
                          type: 'ticket', 
                    data: {
                      ...appointment,
                      patient_fio: wizardData.patient.fio,
                      patient_phone: wizardData.patient.phone,
                      patient_birth_year: wizardData.patient.birth_date ? new Date(wizardData.patient.birth_date).getFullYear() : null,
                      address: wizardData.patient.address || 'Не указан',
                      services: _services
                    }
                  });
                }, 500);
                
                    } else {
                let errDetail = '';
                try {
                  const err = await appointmentResponse.json();
                  errDetail = JSON.stringify(err);
                } catch(e) {
                  // Игнорируем ошибки парсинга JSON
                }
                console.error('Create appointment failed:', appointmentResponse.status, errDetail);
                throw new Error('Ошибка создания записи');
              }
            } catch (fetchError) {
              // Обработка CORS и других ошибок сети для создания записи
              if (fetchError.message.includes('401') || fetchError.message.includes('Unauthorized')) {
                console.warn('Токен недействителен при создании записи');
                localStorage.removeItem('auth_token');
                toast.error('Сессия истекла. Перенаправляем на страницу входа...');
                setTimeout(() => {
                  window.location.href = '/login';
                }, 2000);
                return;
              }
              
              console.warn('Backend недоступен для создания записи, используем демо-режим:', fetchError.message);
              
          // Создаем демо-запись
          const demoAppointment = {
            id: Math.floor(Math.random() * 1000) + 2000,
            patient_id: patientId,
            doctor_id: wizardData.appointment.doctor_id || null,
            appointment_date: wizardData.appointment.date,
            appointment_time: wizardData.appointment.time || '09:00',
            notes: wizardData.appointment.notes || '',
            status: 'scheduled',
            payment_amount: wizardData.payment.amount || 0,
            payment_currency: 'UZS',
            // Дополнительные поля для отображения
            patient_fio: wizardData.patient.fio,
            patient_phone: wizardData.patient.phone,
            created_at: new Date().toISOString()
          };
              
              // Обновляем локальный список
              setAppointments(prev => [demoAppointment, ...prev]);
              
              // Закрываем мастер
              setShowWizard(false);
              setSelectedPatientId(null);
              
              toast.success('Запись создана в демо-режиме (backend недоступен)');
            }
            
          } catch (error) {
            console.error('Error in wizard completion:', error);
            throw error; // Пробрасываем ошибку в мастер
          }
        }}
          />
        )
      )}

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
              <button style={buttonStyle} onClick={() => {
                setShowSlotsModal(false);
              }}>
                🌅 {t('tomorrow')}
              </button>
              <button style={buttonSecondaryStyle} onClick={() => {
                setShowSlotsModal(false);
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
    </div>
  );
};

export default RegistrarPanel; 
