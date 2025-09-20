import React, { useState, useEffect, useCallback, useRef, useMemo, memo } from 'react';
import { useSearchParams } from 'react-router-dom';
import PhoneInput from '../components/ui/PhoneInput';
import { Toaster, toast } from 'react-hot-toast';
import AppointmentsTable from '../components/AppointmentsTable';
// import ServiceChecklist from '../components/ServiceChecklist';
import IntegratedServiceSelector from '../components/registrar/IntegratedServiceSelector';
import IntegratedDoctorSelector from '../components/registrar/IntegratedDoctorSelector';
import OnlineQueueManager from '../components/queue/OnlineQueueManager';
import AppointmentFlow from '../components/AppointmentFlow';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import AppointmentContextMenu from '../components/tables/AppointmentContextMenu';
import ModernTabs from '../components/navigation/ModernTabs';
import ResponsiveTable from '../components/ResponsiveTable';
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

// Современные фильтры
import ModernFilters from '../components/filters/ModernFilters';

// Современная очередь
import ModernQueueManager from '../components/queue/ModernQueueManager';

// Современная статистика
import ModernStatistics from '../components/statistics/ModernStatistics';
 

const RegistrarPanel = () => {
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
      services: ['Консультация кардиолога', 'ЭКГ'],
      visit_type: 'Платный',
      payment_type: 'Карта',
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
      services: ['ЭКГ', 'Холтер'],
      visit_type: 'Повторный',
      payment_type: 'Наличные',
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
      services: ['Консультация дерматолога'],
      visit_type: 'Платный',
      payment_type: 'Карта',
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
      services: ['Лечение кариеса'],
      visit_type: 'Платный',
      payment_type: 'Наличные',
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
      services: ['Общий анализ крови', 'Биохимия'],
      visit_type: 'Платный',
      payment_type: 'Карта',
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
      services: ['Капельница', 'Инъекция'],
      visit_type: 'Повторный',
      payment_type: 'Наличные',
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
  const [appointmentsSelected, setAppointmentsSelected] = useState(new Set());
  const [showAddressColumn, setShowAddressColumn] = useState(true);
  const [showWizard, setShowWizard] = useState(false);
  
  // Отладка состояния мастера
  useEffect(() => {
    console.log('showWizard changed:', showWizard);
  }, [showWizard]);
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
  const loadIntegratedData = async () => {
    try {
      setAppointmentsLoading(true);
      
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
      const [doctorsRes, servicesRes, queueRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/registrar/doctors`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` }
        }),
        fetch(`${API_BASE}/api/v1/registrar/services`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` }
        }),
        fetch(`${API_BASE}/api/v1/registrar/queue-settings`, {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` }
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

    } catch (error) {
      console.error('Ошибка загрузки интегрированных данных:', error);
      toast.error('Ошибка загрузки данных из админ панели');
    } finally {
      setAppointmentsLoading(false);
    }
  };

  // Функция для получения данных пациента по ID
  const fetchPatientData = useCallback(async (patientId) => {
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
      console.error(`Error fetching patient ${patientId}:`, error);
    }
    return null;
  }, [API_BASE]);

  // Функция для обогащения записей данными пациентов
  const enrichAppointmentsWithPatientData = useCallback(async (appointments) => {
    const enrichedAppointments = await Promise.all(appointments.map(async (apt) => {
      if (apt.patient_id) {
        const patient = await fetchPatientData(apt.patient_id);
        if (patient) {
          return {
            ...apt,
            patient_fio: `${patient.last_name || ''} ${patient.first_name || ''} ${patient.middle_name || ''}`.trim(),
            patient_phone: patient.phone,
            patient_birth_year: patient.birth_date ? new Date(patient.birth_date).getFullYear() : null,
          };
        }
      }
      return apt;
    }));
    return enrichedAppointments;
  }, [fetchPatientData]);

  // Улучшенная загрузка записей с правильной обработкой ошибок
  const loadAppointments = async () => {
    try {
      setAppointmentsLoading(true);
      setDataSource('loading');
      
      // Проверяем наличие токена
      const token = localStorage.getItem('auth_token');
      if (!token) {
        console.warn('Токен аутентификации отсутствует, используем демо-данные');
        setDataSource('demo');
        setAppointments(DEMO_APPOINTMENTS);
        return;
      }
      
      const response = await fetch(`${API_BASE}/api/v1/appointments/?limit=50`, {
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
          setAppointments(prev => {
            const locallyModified = prev.filter(apt => apt._locallyModified);
            const enrichedWithLocal = enriched.map(apt => {
              const localVersion = locallyModified.find(local => local.id === apt.id);
              return localVersion ? { ...apt, ...localVersion } : apt;
            });
            return enrichedWithLocal;
          });
          
          setDataSource('api');
          console.debug('✅ Загружены и обогащены данные из API:', enriched.length, 'записей');
        } else {
          // API вернул пустой массив - показываем демо-данные
          setAppointments(DEMO_APPOINTMENTS);
          setDataSource('demo');
          // console.debug('API returned empty list, using demo data');
        }
      } else if (response.status === 401) {
        // Токен недействителен
        console.warn('Токен недействителен (401), очищаем и используем демо-данные');
        localStorage.removeItem('auth_token');
        setDataSource('demo');
        setAppointments(DEMO_APPOINTMENTS);
      } else {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      console.error('Ошибка загрузки записей:', error);
      setDataSource('demo');
      setAppointments(DEMO_APPOINTMENTS);
      
      // Показываем уведомление пользователю
      toast.error('Не удалось загрузить данные с сервера. Показаны демо-данные.');
    } finally {
      setAppointmentsLoading(false);
    }
  };

  // Первичная загрузка данных (однократно)
  useEffect(() => {
    loadAppointments();
  }, []);

  // Загрузка интегрированных данных (однократно)
  useEffect(() => {
    loadIntegratedData();
  }, []);

  // Автообновление очереди с возможностью паузы
  useEffect(() => {
    // Во время мастера записи или модальных окон автообновление отключаем, чтобы не было мерцаний
    if (showWizard || paymentDialog.open || printDialog.open || cancelDialog.open) return;
    if (!autoRefresh) return;
    const id = setInterval(() => {
      loadAppointments();
    }, 15000);
    return () => clearInterval(id);
  }, [autoRefresh, showWizard, paymentDialog.open, printDialog.open, cancelDialog.open]);

  // Функции для жесткого потока
  const handleStartVisit = async (appointment) => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/appointments/${appointment.id}/start-visit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (response.ok) {
        const updatedAppointment = await response.json();
        // Обновляем список записей
        setAppointments(prev => prev.map(apt => 
          apt.id === appointment.id ? updatedAppointment : apt
        ));
        toast.success('Прием начат успешно!');
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Ошибка при начале приема');
      }
    } catch (error) {
      console.error('RegistrarPanel: Start visit error:', error);
      toast.error('Ошибка при начале приема');
    }
  };

  const handlePayment = async (appointment) => {
    try {
      console.log('handlePayment вызван с данными:', appointment);
      
      // Проверяем, не оплачена ли уже запись
      const paymentStatus = (appointment.payment_status || '').toLowerCase();
      const status = (appointment.status || '').toLowerCase();
      console.log('Текущий статус оплаты:', paymentStatus, 'Статус записи:', status);
      
      if (paymentStatus === 'paid' || status === 'paid' || status === 'queued') {
        toast.info('Запись уже оплачена');
        return appointment;
      }
      
      const API_BASE = (import.meta?.env?.VITE_API_BASE_URL) || 'http://localhost:8000';
      console.log('Отправляем запрос на:', `${API_BASE}/api/v1/appointments/${appointment.id}/mark-paid`);
      
      const response = await fetch(`${API_BASE}/api/v1/appointments/${appointment.id}/mark-paid`, {
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
        
        setAppointments(prev => prev.map(apt => 
          apt.id === appointment.id ? appointmentWithQueuedStatus : apt
        ));
        toast.success('Запись оплачена и добавлена в очередь!');
        return appointmentWithQueuedStatus;
      } else {
        const errorText = await response.text();
        console.error('Ошибка API:', response.status, errorText);
        
        let errorMessage = 'Ошибка при оплате';
        try {
          const errorData = JSON.parse(errorText);
          errorMessage = errorData.detail || errorMessage;
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
      
      if (status === 'complete' || status === 'done') {
        url = `${API_BASE}/api/v1/appointments/${appointmentId}/complete`;
        body = JSON.stringify({ reason });
      } else if (status === 'paid' || status === 'mark-paid') {
        url = `${API_BASE}/api/v1/appointments/${appointmentId}/mark-paid`;
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
        url = `${API_BASE}/api/v1/appointments/${appointmentId}/start-visit`;
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
        }
        if (e.key === '2') { 
          e.preventDefault(); 
          console.log('Alt+2: Отменить');
          if (appointmentsSelected.size > 0) {
            const reason = window.prompt('Причина отмены');
            if (reason) handleBulkAction('cancelled', reason);
          } else {
            console.log('Нет выбранных записей для отмены');
          }
        }
        if (e.key === '3') { 
          e.preventDefault(); 
          console.log('Alt+3: Неявка');
          if (appointmentsSelected.size > 0) {
            handleBulkAction('no_show'); 
          } else {
            console.log('Нет выбранных записей для неявки');
          }
        }
      } else if (e.ctrlKey && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (showWizard && wizardStep === 1) {
          handlePatientNext();
        }
      } else if (e.key === 'Escape') {
        if (showWizard) setShowWizard(false);
        if (showSlotsModal) setShowSlotsModal(false);
        if (showQRModal) setShowQRModal(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [showWizard, showSlotsModal, showQRModal, wizardStep, appointments, handleBulkAction, appointmentsSelected]);

  // Проверка принадлежности записи отделу
  const isInDepartment = (appointment, departmentKey) => {
    const dept = (appointment.department?.toLowerCase() || '');
    const specialty = (appointment.doctor_specialty?.toLowerCase() || '');
    
    // console.log('Checking department:', departmentKey, 'for appointment:', { 
    //   id: appointment.id, 
    //   department: dept, 
    //   specialty: specialty 
    // });
    
    if (departmentKey === 'cardio') return dept.includes('cardio') || specialty.includes('cardio');
    if (departmentKey === 'echokg' || departmentKey === 'ecg') return dept.includes('ecg') || dept.includes('echo') || specialty.includes('cardio');
    if (departmentKey === 'derma') return dept.includes('derma') || specialty.includes('derma');
    if (departmentKey === 'dental') return dept.includes('dental') || dept.includes('stoma') || specialty.includes('stoma');
    if (departmentKey === 'lab') return dept.includes('lab') || dept.includes('laboratory') || specialty.includes('lab');
    if (departmentKey === 'procedures' || departmentKey === 'proc') return dept.includes('proc') || dept.includes('procedure') || specialty.includes('procedure');
    return false;
  };

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

  // Предвыбор врача при открытии мастера на основе активной вкладки
  useEffect(() => {
    if (!showWizard) return;
    const tabToSpec = {
      cardio: 'cardiology',
      ecg: 'cardiology',
      derma: 'dermatology',
      dental: 'stomatology',
      lab: null,
      procedures: null
    };
    const spec = activeTab ? tabToSpec[activeTab] : null;
    if (spec) {
      const doc = getDoctorBySpecialty(spec);
      if (doc) {
        setSelectedDoctor(doc);
        setWizardData(prev => ({ ...prev, visit: { ...prev.visit, doctor_id: doc.id, specialty: spec } }));
      }
    }
  }, [showWizard, activeTab, getDoctorBySpecialty]);

  // Готовность перейти на следующий шаг (врач + минимум одна услуга)
  const canProceedStep2 = Boolean(selectedDoctor && selectedServices.length > 0);

  // Валидация шага «Пациент»
  const validatePatient = useCallback(() => {
    const fio = (wizardData.patient.fio || '').trim();
    const dob = wizardData.patient.dob || '';
    const phone = (wizardData.patient.phone || '').trim();

    console.log('Валидация пациента:', { fio, dob, phone });

    let fioError = '';
    let dobError = '';
    let phoneError = '';

    if (!fio) fioError = 'Укажите ФИО';

    // Дата рождения в диапазоне 1900..текущий-1
    if (!dob) {
      dobError = 'Укажите дату рождения';
    } else {
      const d = new Date(dob);
      const min = new Date('1900-01-01');
      const max = new Date();
      max.setFullYear(max.getFullYear() - 1);
      if (isNaN(d.getTime()) || d < min || d > max) {
        dobError = 'Дата вне допустимого диапазона';
      }
    }

    // Маска телефона: +998 (XX) XXX-XX-XX
    const uzPhoneRe = /^\+998 \(\d{2}\) \d{3}-\d{2}-\d{2}$/;
    if (!phone) {
      phoneError = 'Укажите номер телефона';
    } else if (!uzPhoneRe.test(phone)) {
      phoneError = 'Формат: +998 (XX) XXX-XX-XX';
      console.log('Телефон не прошел валидацию:', phone, 'Regex test:', uzPhoneRe.test(phone));
    }

    const errors = { fio: fioError, dob: dobError, phone: phoneError };
    const isValid = !(fioError || dobError || phoneError);
    
    console.log('Ошибки валидации:', errors);
    console.log('Валидация прошла:', isValid);

    setPatientErrors(errors);
    return isValid;
  }, [wizardData]);

  const handlePatientNext = useCallback(() => {
    if (validatePatient()) setWizardStep(2);
  }, [validatePatient]);

  // Оптимизированный автопоиск по ФИО/телефону с debounce
  useEffect(() => {
    const fio = (wizardData.patient.fio || '').trim();
    const phone = (wizardData.patient.phone || '').trim();
    const q = phone || fio;
    
    if (!q || q.length < 3) { 
      setPatientSuggestions([]);
      setShowPatientSuggestions(false);
      return; 
    }

    const ctrl = new AbortController();
    const token = localStorage.getItem('auth_token');
    
    const doFetch = async () => {
      try {
        // Пытаемся искать на сервере
        const res = await fetch(`${API_BASE}/api/v1/patients/?q=${encodeURIComponent(q)}`, {
          headers: { 'Authorization': `Bearer ${token}` },
          signal: ctrl.signal
        });
        if (res.ok) {
          const data = await res.json();
          const suggestions = Array.isArray(data?.items) ? data.items : [];
          setPatientSuggestions(suggestions);
          setShowPatientSuggestions(suggestions.length > 0);
          return;
        }
      } catch (error) {
        if (error.name !== 'AbortError') {
          console.warn('Patient search API error:', error);
        }
      }
      
      // Фолбэк — ищем по локальным данным записей
      const items = appointments
        .map(a => ({ 
          id: a.id, 
          patient_fio: a.patient_fio, 
          phone: a.patient_phone, 
          dob: a.patient_birth_date || a.patient_birth_year 
        }))
        .filter(x => {
          const matchesFio = x.patient_fio && fio && x.patient_fio.toLowerCase().includes(fio.toLowerCase());
          const matchesPhone = x.phone && phone && (
            x.phone.includes(phone.replace(/\D/g, '')) || 
            phone.replace(/\D/g, '').includes(x.phone.replace(/\D/g, ''))
          );
          return matchesFio || matchesPhone;
        })
        .slice(0, 5);
      
      setPatientSuggestions(items);
      setShowPatientSuggestions(items.length > 0);
    };
    
    // Увеличиваем debounce до 500ms для лучшей производительности
    const debounceTimer = setTimeout(doFetch, 500);
    
    function handleClickOutside(e) {
      if (showPatientSuggestions) setShowPatientSuggestions(false);
    }
    document.addEventListener('click', handleClickOutside, { once: true });
    
    return () => { 
      clearTimeout(debounceTimer); 
      ctrl.abort(); 
      document.removeEventListener('click', handleClickOutside); 
    };
  }, [wizardData.patient.fio, wizardData.patient.phone, appointments, API_BASE]);

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
      <Toaster position="bottom-right" />
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
        <ModernTabs
          activeTab={activeTab}
          onTabChange={setActiveTab}
          departmentStats={departmentStats}
          theme={theme}
          language={language}
        />
      )}

      {/* Старые вкладки (скрыты) */}
      {false && (
        <nav 
          role="tablist" 
          aria-label="Фильтры по отделам"
          style={{
          display: 'flex',
          gap: isMobile ? '4px' : getSpacing('sm'),
          background: theme === 'light' 
            ? 'rgba(255, 255, 255, 0.8)' 
            : 'rgba(15, 23, 42, 0.8)',
          backdropFilter: 'blur(20px)',
          padding: isMobile ? `${getSpacing('xs')} ${getSpacing('sm')}` : `${getSpacing('sm')} ${getSpacing('md')}`,
          // Стили для слияния с таблицей
          borderLeft: `1px solid ${theme === 'light' ? 'rgba(255, 255, 255, 0.2)' : 'rgba(255, 255, 255, 0.1)'}`,
          borderRight: `1px solid ${theme === 'light' ? 'rgba(255, 255, 255, 0.2)' : 'rgba(255, 255, 255, 0.1)'}`,
          borderTop: `1px solid ${theme === 'light' ? 'rgba(255, 255, 255, 0.2)' : 'rgba(255, 255, 255, 0.1)'}`,
          borderBottom: 'none',
          borderRadius: isMobile ? '12px 12px 0 0' : '20px 20px 0 0',
          margin: `0 ${isMobile ? getSpacing('md') : getSpacing('xl')}`,
          boxShadow: theme === 'light' 
            ? '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
            : '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
          overflowX: isMobile ? 'auto' : 'visible',
          flexWrap: isMobile ? 'nowrap' : 'wrap'
        }}>
          {/* Оставляем только отделы: Кардиолог, ЭКГ, Дерматолог, Стоматолог, Лаборатория, Процедуры */}
          <button
          role="tab"
          className={`px-4 py-2 rounded-lg transition-all duration-200 text-sm font-medium flex items-center gap-2 interactive-element hover-lift ripple-effect focus-ring ${
            activeTab === 'cardio' 
              ? 'bg-gradient-to-r from-blue-600 to-blue-700 text-white shadow-md transform -translate-y-0.5' 
              : 'border border-gray-300 hover:bg-gray-50 hover:-translate-y-0.5'
          }`}
          style={{
            padding: isMobile ? '8px 10px' : '10px 16px',
            fontSize: isMobile ? getFontSize('sm') : getFontSize('base'),
            borderRadius: isMobile ? 10 : 12,
            minWidth: isMobile ? 'auto' : '128px',
            height: isMobile ? 36 : 40,
            fontWeight: 600,
            borderColor: activeTab !== 'cardio' ? (isDark ? '#374151' : '#d1d5db') : undefined,
            color: activeTab !== 'cardio' ? (isDark ? '#f9fafb' : '#374151') : undefined,
            backgroundColor: activeTab !== 'cardio' ? (isDark ? '#374151' : 'white') : undefined,
            boxShadow: activeTab === 'cardio' ? '0 4px 6px -1px rgba(59, 130, 246, 0.3)' : undefined
          }}
          onClick={() => setActiveTab(prev => prev === 'cardio' ? null : 'cardio')}
          aria-selected={activeTab === 'cardio'}
          aria-controls="appointments-table"
          aria-describedby="cardio-tab-description"
          tabIndex={activeTab === 'cardio' ? 0 : -1}
        >
            <Heart size={16} />
          {t('tabs_cardio')} ({getDepartmentCount('cardio')})
            {hasActiveQueue('cardio') && <span className="w-2 h-2 bg-green-500 rounded-full" />}
            {hasPendingPayments('cardio') && <span className="w-2 h-2 bg-yellow-500 rounded-full" />}
        </button>
        <button
          className={`px-4 py-2 rounded-lg transition-all duration-200 text-sm font-medium flex items-center gap-2 interactive-element hover-lift ripple-effect focus-ring ${
            activeTab === 'echokg' 
              ? 'bg-gradient-to-r from-purple-600 to-purple-700 text-white shadow-md transform -translate-y-0.5' 
              : 'border border-gray-300 hover:bg-gray-50 hover:-translate-y-0.5'
          }`}
          style={{
            padding: isMobile ? '8px 10px' : '10px 16px',
            fontSize: isMobile ? getFontSize('sm') : getFontSize('base'),
            borderRadius: isMobile ? 10 : 12,
            minWidth: isMobile ? 'auto' : '128px',
            height: isMobile ? 36 : 40,
            fontWeight: 600,
            borderColor: activeTab !== 'echokg' ? (isDark ? '#374151' : '#d1d5db') : undefined,
            color: activeTab !== 'echokg' ? (isDark ? '#f9fafb' : '#374151') : undefined,
            backgroundColor: activeTab !== 'echokg' ? (isDark ? '#374151' : 'white') : undefined,
            boxShadow: activeTab === 'echokg' ? '0 4px 6px -1px rgba(147, 51, 234, 0.3)' : undefined
          }}
          onClick={() => setActiveTab(prev => prev === 'echokg' ? null : 'echokg')}
          aria-selected={activeTab === 'echokg'}
        >
            <Activity size={16} />
            {t('tabs_echokg')} ({getDepartmentCount('echokg')})
            {hasActiveQueue('echokg') && <span className="w-2 h-2 bg-green-500 rounded-full" />}
            {hasPendingPayments('echokg') && <span className="w-2 h-2 bg-yellow-500 rounded-full" />}
        </button>
        <button
          className={`px-4 py-2 rounded-lg transition-all duration-200 text-sm font-medium flex items-center gap-2 interactive-element hover-lift ripple-effect focus-ring ${
            activeTab === 'derma' 
              ? 'bg-gradient-to-r from-pink-600 to-pink-700 text-white shadow-md transform -translate-y-0.5' 
              : 'border border-gray-300 hover:bg-gray-50 hover:-translate-y-0.5'
          }`}
          style={{
            padding: isMobile ? '8px 10px' : '10px 16px',
            fontSize: isMobile ? getFontSize('sm') : getFontSize('base'),
            borderRadius: isMobile ? 10 : 12,
            minWidth: isMobile ? 'auto' : '128px',
            height: isMobile ? 36 : 40,
            fontWeight: 600,
            borderColor: activeTab !== 'derma' ? (isDark ? '#374151' : '#d1d5db') : undefined,
            color: activeTab !== 'derma' ? (isDark ? '#f9fafb' : '#374151') : undefined,
            backgroundColor: activeTab !== 'derma' ? (isDark ? '#374151' : 'white') : undefined,
            boxShadow: activeTab === 'derma' ? '0 4px 6px -1px rgba(219, 39, 119, 0.3)' : undefined
          }}
          onClick={() => setActiveTab(prev => prev === 'derma' ? null : 'derma')}
          aria-selected={activeTab === 'derma'}
        >
            <User size={16} />
          {t('tabs_derma')} ({getDepartmentCount('derma')})
            {hasActiveQueue('derma') && <span className="w-2 h-2 bg-green-500 rounded-full" />}
            {hasPendingPayments('derma') && <span className="w-2 h-2 bg-yellow-500 rounded-full" />}
        </button>
        <button
          className={`px-4 py-2 rounded-lg transition-all duration-200 text-sm font-medium flex items-center gap-2 interactive-element hover-lift ripple-effect focus-ring ${
            activeTab === 'dental' 
              ? 'bg-gradient-to-r from-indigo-600 to-indigo-700 text-white shadow-md transform -translate-y-0.5' 
              : 'border border-gray-300 hover:bg-gray-50 hover:-translate-y-0.5'
          }`}
          style={{
            padding: isMobile ? '8px 10px' : '10px 16px',
            fontSize: isMobile ? getFontSize('sm') : getFontSize('base'),
            borderRadius: isMobile ? 10 : 12,
            minWidth: isMobile ? 'auto' : '128px',
            height: isMobile ? 36 : 40,
            fontWeight: 600,
            borderColor: activeTab !== 'dental' ? (isDark ? '#374151' : '#d1d5db') : undefined,
            color: activeTab !== 'dental' ? (isDark ? '#f9fafb' : '#374151') : undefined,
            backgroundColor: activeTab !== 'dental' ? (isDark ? '#374151' : 'white') : undefined,
            boxShadow: activeTab === 'dental' ? '0 4px 6px -1px rgba(79, 70, 229, 0.3)' : undefined
          }}
          onClick={() => setActiveTab(prev => prev === 'dental' ? null : 'dental')}
          aria-selected={activeTab === 'dental'}
        >
            <User size={16} />
          {t('tabs_dental')} ({getDepartmentCount('dental')})
            {hasActiveQueue('dental') && <span className="w-2 h-2 bg-green-500 rounded-full" />}
            {hasPendingPayments('dental') && <span className="w-2 h-2 bg-yellow-500 rounded-full" />}
        </button>
        <button
          className={`px-4 py-2 rounded-lg transition-all duration-200 text-sm font-medium flex items-center gap-2 interactive-element hover-lift ripple-effect focus-ring ${
            activeTab === 'lab' 
              ? 'bg-gradient-to-r from-green-600 to-green-700 text-white shadow-md transform -translate-y-0.5' 
              : 'border border-gray-300 hover:bg-gray-50 hover:-translate-y-0.5'
          }`}
          style={{
            padding: isMobile ? '8px 10px' : '10px 16px',
            fontSize: isMobile ? getFontSize('sm') : getFontSize('base'),
            borderRadius: isMobile ? 10 : 12,
            minWidth: isMobile ? 'auto' : '128px',
            height: isMobile ? 36 : 40,
            fontWeight: 600,
            borderColor: activeTab !== 'lab' ? (isDark ? '#374151' : '#d1d5db') : undefined,
            color: activeTab !== 'lab' ? (isDark ? '#f9fafb' : '#374151') : undefined,
            backgroundColor: activeTab !== 'lab' ? (isDark ? '#374151' : 'white') : undefined,
            boxShadow: activeTab === 'lab' ? '0 4px 6px -1px rgba(34, 197, 94, 0.3)' : undefined
          }}
          onClick={() => setActiveTab(prev => prev === 'lab' ? null : 'lab')}
          aria-selected={activeTab === 'lab'}
        >
            <TestTube size={16} />
          {t('tabs_lab')} ({getDepartmentCount('lab')})
            {hasActiveQueue('lab') && <span className="w-2 h-2 bg-green-500 rounded-full" />}
            {hasPendingPayments('lab') && <span className="w-2 h-2 bg-yellow-500 rounded-full" />}
        </button>
        <button
          className={`px-4 py-2 rounded-lg transition-all duration-200 text-sm font-medium flex items-center gap-2 interactive-element hover-lift ripple-effect focus-ring ${
            activeTab === 'procedures' 
              ? 'bg-gradient-to-r from-orange-600 to-orange-700 text-white shadow-md transform -translate-y-0.5' 
              : 'border border-gray-300 hover:bg-gray-50 hover:-translate-y-0.5'
          }`}
          style={{
            padding: isMobile ? '8px 10px' : '10px 16px',
            fontSize: isMobile ? getFontSize('sm') : getFontSize('base'),
            borderRadius: isMobile ? 10 : 12,
            minWidth: isMobile ? 'auto' : '128px',
            height: isMobile ? 36 : 40,
            fontWeight: 600,
            borderColor: activeTab !== 'procedures' ? (isDark ? '#374151' : '#d1d5db') : undefined,
            color: activeTab !== 'procedures' ? (isDark ? '#f9fafb' : '#374151') : undefined,
            backgroundColor: activeTab !== 'procedures' ? (isDark ? '#374151' : 'white') : undefined,
            boxShadow: activeTab === 'procedures' ? '0 4px 6px -1px rgba(234, 88, 12, 0.3)' : undefined
          }}
          onClick={() => setActiveTab(prev => prev === 'procedures' ? null : 'procedures')}
          aria-selected={activeTab === 'procedures'}
        >
            <Syringe size={16} />
            {t('tabs_procedures')} ({getDepartmentCount('procedures')})
            {hasActiveQueue('procedures') && <span className="w-2 h-2 bg-green-500 rounded-full" />}
            {hasPendingPayments('procedures') && <span className="w-2 h-2 bg-yellow-500 rounded-full" />}
        </button>
        </nav>
      )}
      {/* </nav> Закрытие старых вкладок */}

      {/* Основной контент без отступа сверху */}
      <div style={{ overflow: 'hidden' }}>
        {/* Экран приветствия по параметру view=welcome (с историей: календарь + поиск) */}
        {searchParams.get('view') === 'welcome' && (
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
                  // Обновление данных
                  loadAppointments();
                  loadIntegratedData();
                }}
              />

              {/* Онлайн-очередь */}
              <AnimatedTransition type="fade" delay={800}>
                <div style={{ marginBottom: '32px' }}>
                  <h2 style={{ fontSize: '24px', marginBottom: '20px', color: accentColor }}>
                    📱 Онлайн-очередь
                  </h2>
                  <OnlineQueueManager
                    selectedDoctorId={selectedDoctor?.id}
                    selectedDate={selectedDate}
                    onQueueUpdate={loadIntegratedData}
                  />
                </div>
              </AnimatedTransition>

              {/* Быстрый старт */}
              <AnimatedTransition type="fade" delay={1000}>
                <div style={{ marginBottom: '32px' }}>
                  <AnimatedTransition type="slide" direction="up" delay={1100}>
                    <h2 style={{ fontSize: '24px', marginBottom: '20px', color: accentColor }}>
                      🚀 {t('quick_start')}
                    </h2>
                  </AnimatedTransition>
                  <AnimatedTransition type="fade" delay={1200}>
                    <div style={{ 
                      display: 'grid', 
                      gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                      gap: '16px',
                      alignItems: 'stretch'
                    }}>
                  <AnimatedTransition type="scale" delay={1300}>
                    <button 
                      className="clinic-button clinic-button-primary interactive-element hover-lift ripple-effect action-button-hover focus-ring"
                      onClick={() => setShowWizard(true)}
                      aria-label="Create new appointment"
                      style={{ padding: '8px 12px', borderRadius: 8, fontSize: 14 }}
                    >
                      ➕ {t('new_appointment')}
                    </button>
                  </AnimatedTransition>
                  <AnimatedTransition type="scale" delay={1400}>
                    <button 
                      className="clinic-button clinic-button-outline interactive-element hover-lift ripple-effect magnetic-hover focus-ring"
                      style={{ padding: '8px 12px', borderRadius: 8, fontSize: 14 }}
                    >
                      📊 {t('export_csv')}
                    </button>
                  </AnimatedTransition>
                  <AnimatedTransition type="scale" delay={1500}>
                    <button 
                      className="clinic-button clinic-button-warning interactive-element hover-lift ripple-effect action-button-hover focus-ring"
                      style={{ padding: '8px 12px', borderRadius: 8, fontSize: 14 }}
                    >
                      📅 {t('today')}
                    </button>
                  </AnimatedTransition>
                  <AnimatedTransition type="scale" delay={1600}>
                    <button 
                      className="clinic-button clinic-button-outline interactive-element hover-lift ripple-effect magnetic-hover focus-ring"
                      style={{ padding: '8px 12px', borderRadius: 8, fontSize: 14 }}
                    >
                      🔄 {t('reset')}
                    </button>
                  </AnimatedTransition>
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

            <AppointmentsTable
                      appointments={appointments.slice(0, 5)}
              appointmentsSelected={appointmentsSelected}
              setAppointmentsSelected={setAppointmentsSelected}
              updateAppointmentStatus={updateAppointmentStatus}
              setShowWizard={setShowWizard}
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
              {/* Современная панель фильтров для онлайн-очереди */}
              <ModernFilters
                searchParams={searchParams}
                onParamsChange={(params) => {
                  params.delete('view');
                  window.history.replaceState(null, '', `/registrar-panel?${params.toString()}`);
                }}
                autoRefresh={false}
                onAutoRefreshChange={() => {}}
                appointmentsCount={0}
              />
                
              <ModernQueueManager 
                selectedDate={searchParams.get('date') || new Date().toISOString().split('T')[0]}
                selectedDoctor={searchParams.get('doctor') || ''}
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
              margin: `0 ${isMobile ? getSpacing('md') : getSpacing('xl')} ${getSpacing('xl')} ${isMobile ? getSpacing('md') : getSpacing('xl')}`,
            borderRadius: isMobile ? '0 0 12px 12px' : '0 0 20px 20px'
          }}>
            <div style={{
              ...tableContentStyle,
              padding: isMobile ? getSpacing('sm') : getSpacing('md')
            }}>
              
              {/* Современная панель фильтров */}
              <ModernFilters
                searchParams={searchParams}
                onParamsChange={(params) => {
                  params.delete('view');
                  window.history.replaceState(null, '', `/registrar-panel?${params.toString()}`);
                }}
                autoRefresh={autoRefresh}
                onAutoRefreshChange={setAutoRefresh}
                appointmentsCount={filteredAppointments.length}
              />
              
              {/* Панель управления таблицей */}
              <div style={{
                display: 'flex',
                gap: '12px', 
                alignItems: 'center',
                padding: '16px 0',
                borderBottom: `1px solid ${borderColor}`,
                marginBottom: '16px',
                position: 'relative',
                zIndex: 10
              }}>
                  <button
                  onClick={(e) => {
                    e.stopPropagation(); // Предотвращаем всплытие события
                    console.log('Кнопка "Новая запись" нажата, showWizard:', showWizard);
                    setShowWizard(true);
                    console.log('setShowWizard(true) вызвана');
                  }}
                    style={{
                    padding: '12px 20px',
                    borderRadius: '8px',
                      fontSize: '14px',
                    fontWeight: '600',
                    background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                    color: 'white',
                    border: 'none',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    boxShadow: '0 2px 4px rgba(59, 130, 246, 0.3)',
                    position: 'relative',
                    zIndex: 20,
                    minWidth: '140px'
                  }}
                  onMouseEnter={(e) => {
                    e.target.style.transform = 'translateY(-1px)';
                    e.target.style.boxShadow = '0 4px 8px rgba(59, 130, 246, 0.4)';
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.transform = 'translateY(0)';
                    e.target.style.boxShadow = '0 2px 4px rgba(59, 130, 246, 0.3)';
                  }}
                >
                  ➕ {t('new_appointment')}
                  </button>
                  <button
                  className="clinic-button clinic-button-outline interactive-element hover-lift ripple-effect magnetic-hover focus-ring"
                  onClick={() => {
                    const csvContent = generateCSV(filteredAppointments);
                    downloadCSV(csvContent, `appointments_${new Date().toISOString().split('T')[0]}.csv`);
                  }}
                  style={{ padding: '8px 16px', borderRadius: 8, fontSize: 14 }}
                >
                  📊 {t('export_csv')}
                  </button>
                  <button
                  className="clinic-button clinic-button-outline interactive-element hover-lift ripple-effect magnetic-hover focus-ring"
                    onClick={() => {
                    const params = new URLSearchParams(window.location.search);
                    params.set('date', new Date().toISOString().split('T')[0]);
                    window.history.replaceState(null, '', `/registrar-panel?${params.toString()}`);
                  }}
                  style={{ padding: '8px 16px', borderRadius: 8, fontSize: 14 }}
                >
                  📅 {t('today')}
                </button>
                <button 
                  className="clinic-button clinic-button-outline interactive-element hover-lift ripple-effect magnetic-hover focus-ring"
                  onClick={() => {
                    const params = new URLSearchParams(window.location.search);
                    params.delete('date');
                    params.delete('q');
                    params.delete('status');
                    setActiveTab(null);
                    window.history.replaceState(null, '', '/registrar-panel');
                  }}
                  style={{ padding: '8px 16px', borderRadius: 8, fontSize: 14 }}
                >
                  🔄 {t('reset')}
                  </button>
              </div>
              
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
                      case 'more':
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
                      default:
                        break;
                    }
                  }}
                />
              )}
              
              {/* Старая таблица (скрыта) */}
              {false && (
                <ResponsiveTable
                  id="appointments-table-old"
                  role="table"
                  aria-label={`Таблица записей${activeTab ? ` - ${t('tabs_' + activeTab)}` : ''}`}
                  aria-rowcount={filteredAppointments.length}
                  data={filteredAppointments}
                  columns={[
                    { 
                      key: 'number', 
                      label: '№', 
                      align: 'center', 
                      minWidth: '50px',
                      fixed: true,
                      render: (value, row, index) => index + 1
                    },
                    { 
                      key: 'patient_fio', 
                      label: 'ФИО', 
                      minWidth: '250px',
                      clickable: true,
                      onClick: (row) => {
                        // Открыть карту пациента
                        console.log('Открыть карту пациента:', row.patient_fio);
                      }
                    },
                    { 
                      key: 'patient_birth_year', 
                      label: 'Год рождения', 
                      align: 'center', 
                      minWidth: '100px',
                      validate: (value) => {
                        const currentYear = new Date().getFullYear();
                        return value >= 1900 && value <= currentYear - 1;
                      }
                    },
                    { 
                      key: 'patient_phone', 
                      label: 'Телефон', 
                      minWidth: '150px',
                      masked: true,
                      copyable: true,
                      clickable: true,
                      onClick: (row) => {
                        // Звонок по клику
                        console.log('Звонок:', row.patient_phone);
                      }
                    },
                    { 
                      key: 'address', 
                      label: 'Адрес', 
                      minWidth: '200px',
                      collapsible: true,
                      hidden: !showAddressColumn,
                      mobileHidden: true
                    },
                    { 
                      key: 'services', 
                      label: 'Услуги', 
                      minWidth: '250px',
                      render: (value) => {
                        if (Array.isArray(value)) {
                          return (
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                              {value.map((service, idx) => {
                                // Определяем группу услуги
                                const getServiceGroup = (service) => {
                                  const s = service.toLowerCase();
                                  if (s.includes('дерм') || s.includes('косм')) return 'derm';
                                  if (s.includes('кардио')) return 'cardio';
                                  if (s.includes('экг')) return 'ecg';
                                  if (s.includes('эхо')) return 'echo';
                                  if (s.includes('стомат') || s.includes('зуб')) return 'stomatology';
                                  if (s.includes('лаб') || s.includes('анализ')) return 'lab';
                                  return 'other';
                                };
                                
                                const group = getServiceGroup(service);
                                const groupColors = {
                                  derm: '#f59e0b',
                                  cardio: '#ef4444',
                                  ecg: '#ec4899',
                                  echo: '#8b5cf6',
                                  stomatology: '#3b82f6',
                                  lab: '#10b981',
                                  other: '#6b7280'
                                };
                                
                                return (
                                  <span
                                    key={idx}
                                    style={{
                                      padding: '2px 8px',
                                      borderRadius: '4px',
                                      fontSize: '12px',
                                      backgroundColor: groupColors[group] + '20',
                                      color: groupColors[group],
                                      border: `1px solid ${groupColors[group]}50`
                                    }}
                                  >
                                    {service}
                                  </span>
                                );
                              })}
                            </div>
                          );
                        }
                        return value;
                      }
                    },
                    { 
                      key: 'visit_type', 
                      label: 'Тип обращения', 
                      minWidth: '120px',
                      align: 'center',
                      render: (value) => {
                        const types = {
                          'Платный': { color: '#3b82f6', icon: '💰' },
                          'Повторный': { color: '#10b981', icon: '🔄' },
                          'Льготный': { color: '#f59e0b', icon: '🎫' }
                        };
                        const type = types[value] || { color: '#6b7280', icon: '📋' };
                        return (
                          <span style={{ color: type.color, fontWeight: '500' }}>
                            {type.icon} {value}
                          </span>
                        );
                      }
                    },
                    { 
                      key: 'payment_type', 
                      label: 'Вид оплаты', 
                      minWidth: '110px',
                      align: 'center',
                      render: (value) => {
                        const payments = {
                          'Наличные': '💵',
                          'Карта': '💳',
                          'Онлайн': '🌐',
                          'Перевод': '📱'
                        };
                        return (
                          <span>
                            {payments[value] || '💰'} {value}
                          </span>
                        );
                      }
                    },
                    { 
                      key: 'cost', 
                      label: 'Стоимость', 
                      align: 'right', 
                      minWidth: '100px',
                      render: (value) => {
                        return (
                          <span style={{ fontWeight: '600', color: '#059669' }}>
                            {value ? `${value.toLocaleString()} ₽` : '—'}
                          </span>
                        );
                      }
                    },
                    { 
                      key: 'status', 
                      label: 'Статус', 
                      align: 'center', 
                      minWidth: '130px',
                      render: (value) => {
                        const map = {
                          confirmed: { bg: '#dcfce7', text: '#166534', label: 'Подтвержден' },
                          queued: { bg: '#fef9c3', text: '#854d0e', label: 'В очереди' },
                          paid_pending: { bg: '#ffedd5', text: '#9a3412', label: 'Ожидает оплаты' },
                          in_cabinet: { bg: '#dbeafe', text: '#1e3a8a', label: 'В кабинете' },
                          done: { bg: '#e0f2fe', text: '#075985', label: 'Завершен' },
                          canceled: { bg: '#fee2e2', text: '#991b1b', label: 'Отменен' },
                          no_show: { bg: '#e5e7eb', text: '#374151', label: 'Неявка' },
                          plan: { bg: '#e0e7ff', text: '#3730a3', label: 'Запланирован' },
                          paid: { bg: '#dcfce7', text: '#166534', label: 'Оплачен' }
                        };
                        const cfg = map[value] || { bg: '#e5e7eb', text: '#374151', label: value || '—' };
                        return (
                          <span style={{
                            padding: '2px 8px',
                            borderRadius: 999,
                            background: cfg.bg,
                            color: cfg.text,
                            fontSize: 12,
                            fontWeight: 600
                          }}>
                            {cfg.label}
                          </span>
                        );
                      }
                    }
                  ]}
                  actions={[
                    { 
                      icon: <User size={16} />, 
                      className: 'clinic-button clinic-button-outline',
                      title: 'В кабинет',
                      onClick: async (row) => {
                        await updateAppointmentStatus(row.id, 'in_cabinet');
                        toast.success('Пациент отправлен в кабинет');
                      },
                      visible: (row) => row.status === 'confirmed' || row.status === 'queued',
                      style: { padding: '6px 10px', borderRadius: 8, fontSize: 12 }
                    },
                    {
                      // Вызвать пациента (начать приём)
                      className: 'clinic-button clinic-button-success',
                      title: 'Вызвать',
                      onClick: async (row) => {
                        await handleStartVisit(row);
                      },
                      visible: (row) => row.status === 'queued',
                      style: { padding: '6px 10px', borderRadius: 8, fontSize: 12 }
                    },
                    { 
                      icon: <Printer size={16} />, 
                      className: 'clinic-button clinic-button-primary',
                      title: 'Печать талона',
                      onClick: (row) => {
                        setPrintDialog({ 
                          open: true, 
                          type: 'ticket', 
                          data: row 
                        });
                      },
                      visible: (row) => (row.payment_status === 'paid') || (row.status === 'queued'),
                      style: { padding: '6px 10px', borderRadius: 8, fontSize: 12 }
                    },
                    { 
                      icon: <X size={16} />, 
                      className: 'clinic-button clinic-button-outline',
                      title: 'Отмена',
                      onClick: (row) => setCancelDialog({ open: true, row, reason: '' }),
                      visible: (row) => row.status !== 'canceled' && row.status !== 'done',
                      style: { padding: '6px 10px', borderRadius: 8, fontSize: 12 }
                    },
                    { 
                      icon: <Calendar size={16} />, 
                      className: 'clinic-button clinic-button-outline',
                      title: 'Перенос',
                      onClick: (row) => {
                        setSelectedAppointment(row);
                        setShowSlotsModal(true);
                      },
                      visible: (row) => row.status !== 'done' && row.status !== 'in_cabinet',
                      style: { padding: '6px 10px', borderRadius: 8, fontSize: 12 }
                    },
                    {
                      // Завершить приём
                      className: 'clinic-button clinic-button-success',
                      title: 'Завершить',
                      onClick: async (row) => {
                        await updateAppointmentStatus(row.id, 'done');
                        toast.success('Приём завершён');
                      },
                      visible: (row) => row.status === 'in_cabinet',
                      style: { padding: '6px 10px', borderRadius: 8, fontSize: 12 }
                    },
                    { 
                      icon: <CreditCard size={16} />, 
                      className: 'clinic-button clinic-button-success',
                      title: 'Оплата',
                      onClick: (row) => setPaymentDialog({ open: true, row, paid: false, source: 'table' }),
                      visible: (row) => {
                        const s = (row.status || '').toLowerCase();
                        const ps = (row.payment_status || '').toLowerCase();
                        return s !== 'paid' && ps !== 'paid' && (s === 'paid_pending' || !ps);
                      },
                      style: { padding: '6px 10px', borderRadius: 8, fontSize: 12 }
                    }
                  ]}
                  selectedRows={appointmentsSelected}
                  onRowSelect={(index, selected) => {
                    const newSelected = new Set(appointmentsSelected);
                    if (selected) {
                      newSelected.add(index);
                    } else {
                      newSelected.delete(index);
                    }
                    setAppointmentsSelected(newSelected);
                  }}
                  onRowClick={(row, index) => {
                    // Открываем поток записи
                    setSelectedAppointment(row);
                    setShowAppointmentFlow(true);
                  }}
                />
              )}
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
        onPaymentSuccess={(paymentData) => {
          // Локальное обновление статуса оплаты
          setAppointments(prev => prev.map(apt => 
            apt.id === paymentData.appointmentId ? {
              ...apt,
              status: 'paid',
              payment_status: 'paid',
              payment_amount: paymentData.amount,
              payment_type: paymentData.method,
              _locallyModified: true
            } : apt
          ));
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
          
          try {
            // Создание пациента (если нужно)
            let patientId = selectedPatientId;
            if (!patientId) {
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
                  sex: wizardData.patient.sex || 'M',
                  email: wizardData.patient.email || null,
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
            }
            
            // Создание записи
            const appointmentResponse = await fetch(`${API_BASE}/api/v1/appointments/`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
              },
              body: JSON.stringify({
                patient_id: patientId,
                doctor_id: wizardData.appointment.doctor_id,
                services: wizardData.appointment.services,
                appointment_date: wizardData.appointment.date,
                appointment_time: wizardData.appointment.time || '09:00',
                visit_type: wizardData.appointment.visit_type,
                payment_method: wizardData.payment.method,
                cost: wizardData.payment.amount,
                notes: wizardData.appointment.notes || ''
              })
            });
            
            if (appointmentResponse.ok) {
              const appointment = await appointmentResponse.json();
              
              // Обновляем локальный список
              setAppointments(prev => [appointment, ...prev]);
              
              // Сбрасываем состояние мастера
              setWizardStep(1);
              setWizardData({
                patient: {},
                visit: {},
                payment: {}
              });
              setSelectedPatientId(null);
              
              toast.success('Запись успешно создана!');
              
              // Предлагаем печать талона
              setTimeout(() => {
                setPrintDialog({ 
                  open: true, 
                  type: 'ticket', 
                  data: appointment 
                });
              }, 500);
              
            } else {
              throw new Error('Ошибка создания записи');
            }
            
          } catch (error) {
            console.error('Error in wizard completion:', error);
            throw error; // Пробрасываем ошибку в мастер
          }
        }}
      />

      {/* Старые диалоги (временно скрыты) */}
      {false && cancelDialog.open && (
        <div 
          role="dialog" 
          aria-modal="true"
          aria-labelledby="cancel-dialog-title"
          aria-describedby="cancel-dialog-description"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 99999
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setCancelDialog({ open: false, row: null, reason: '' });
            }
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setCancelDialog({ open: false, row: null, reason: '' });
            }
          }}
        >
          <div style={{
            backgroundColor: cardBg,
            borderRadius: '12px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            width: '100%',
            maxWidth: '28rem',
            margin: '0 1rem'
          }}>
            <div className="p-6">
              <h3 
                id="cancel-dialog-title"
                className="text-xl font-semibold mb-4 text-gray-900" 
                style={{ color: textColor }}
              >
                Отменить запись
              </h3>
              <div 
                id="cancel-dialog-description"
                className="mb-4 text-sm text-gray-600" 
                style={{ color: textColor }}
              >
                Пациент: <span className="font-medium">{cancelDialog.row?.patient_fio}</span>
              </div>
              <label 
                htmlFor="cancel-reason-textarea"
                className="block text-sm font-medium mb-2 text-gray-700" 
                style={{ color: textColor }}
              >
                Причина отмены
              </label>
              <textarea
                id="cancel-reason-textarea"
                value={cancelDialog.reason}
                onChange={(e) => setCancelDialog(prev => ({ ...prev, reason: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent resize-none transition-all duration-200"
                style={{ 
                  borderColor: isDark ? '#374151' : '#d1d5db',
                  backgroundColor: isDark ? '#374151' : 'white',
                  color: textColor
                }}
                rows="3"
                placeholder="Укажите причину отмены записи..."
                aria-required="true"
                aria-describedby="cancel-reason-help"
                autoFocus
              />
              <div 
                id="cancel-reason-help"
                className="text-xs text-gray-500 mt-1"
                style={{ color: isDark ? '#9ca3af' : '#6b7280' }}
              >
                Обязательное поле для отмены записи
              </div>
            </div>
            <div className="px-6 py-4 bg-gray-50 rounded-b-xl flex justify-end gap-3" style={{ backgroundColor: isDark ? '#1f2937' : '#f9fafb' }}>
              <button 
                type="button"
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
                  console.log('Кнопка "Отмена" отмены записи нажата через onMouseDown');
                  setCancelDialog({ open: false, row: null, reason: '' });
                }}
              >
                Отмена
              </button>
              <button
                type="button"
                className="clinic-button clinic-button-danger interactive-element hover-lift ripple-effect action-button-hover focus-ring"
                style={{ 
                  padding: '8px 12px', 
                  borderRadius: 8, 
                  fontSize: 14,
                  cursor: 'pointer',
                  pointerEvents: 'auto'
                }}
                onMouseDown={async (e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  console.log('Кнопка "Подтвердить отмену" нажата через onMouseDown');
                  
                  if (!cancelDialog.reason.trim()) {
                    toast.error('Укажите причину отмены');
                    return;
                  }
                  
                  try {
                    console.log('Отменяем запись:', cancelDialog.row.id, 'Причина:', cancelDialog.reason.trim());
                    
                    // Пока нет специального API для отмены, просто обновляем локально
                    // В будущем здесь будет вызов API отмены
                    console.log('Отменяем запись локально (API отмены будет добавлен позже)');
                    
                    // Обновляем список записей - помечаем как отмененную
                    setAppointments(prev => prev.map(apt => 
                      apt.id === cancelDialog.row.id ? { 
                        ...apt, 
                        status: 'cancelled',
                        // Добавляем метку, что это локальное изменение
                        _locallyModified: true,
                        _cancelReason: cancelDialog.reason.trim()
                      } : apt
                    ));
                    
                    setCancelDialog({ open: false, row: null, reason: '' });
                    toast.success('Запись отменена (локально)');
                  } catch (error) {
                    console.error('Ошибка при отмене записи:', error);
                    toast.error('Ошибка при отмене записи: ' + error.message);
                  }
                }}
              >
                Подтвердить отмену
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Диалог оплаты */}
      {paymentDialog.open && (
        <div 
          role="dialog" 
          aria-modal="true" 
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 99999
          }}
        >
          <div style={{
            backgroundColor: cardBg,
            borderRadius: '12px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            width: '100%',
            maxWidth: '28rem',
            margin: '0 1rem'
          }}>
            <div style={{ padding: '24px' }}>
              <h3 style={{ 
                color: textColor, 
                fontSize: '20px', 
                fontWeight: '600', 
                marginBottom: '16px',
                margin: 0
              }}>
                💳 Оплата услуг
              </h3>
              <div style={{ 
                color: textColor, 
                fontSize: '14px', 
                marginBottom: '16px' 
              }}>
                Пациент: <span style={{ fontWeight: '500' }}>{paymentDialog.row?.patient_fio}</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: '14px', 
                    fontWeight: '500', 
                    marginBottom: '8px', 
                    color: textColor 
                  }}>
                    Сумма к оплате
                  </label>
                  <input 
                    type="number" 
                    defaultValue={paymentDialog.row?.cost || paymentDialog.row?.payment_amount || ''} 
                    style={{ 
                      width: '100%',
                      padding: '8px 12px',
                      border: `1px solid ${isDark ? '#374151' : '#d1d5db'}`,
                      borderRadius: '8px',
                      backgroundColor: isDark ? '#374151' : 'white',
                      color: textColor,
                      fontSize: '14px'
                    }}
                    placeholder="Введите сумму к оплате"
                    onChange={(e) => {
                      // Обновляем сумму в состоянии
                      setPaymentDialog(prev => ({
                        ...prev,
                        row: { ...prev.row, payment_amount: parseFloat(e.target.value) || 0 }
                      }));
                    }}
                  />
                </div>
                <div>
                  <label style={{ 
                    display: 'block', 
                    fontSize: '14px', 
                    fontWeight: '500', 
                    marginBottom: '8px', 
                    color: textColor 
                  }}>
                    Способ оплаты
                  </label>
                  <select 
                    defaultValue={paymentDialog.row?.payment_type || 'Карта'} 
                    style={{ 
                      width: '100%',
                      padding: '8px 12px',
                      border: `1px solid ${isDark ? '#374151' : '#d1d5db'}`,
                      borderRadius: '8px',
                      backgroundColor: isDark ? '#374151' : 'white',
                      color: textColor,
                      fontSize: '14px'
                    }}
                  >
                    <option>Карта</option>
                    <option>Наличные</option>
                    <option>Перевод</option>
                    <option>Онлайн</option>
                  </select>
                </div>
              </div>
            </div>
            <div style={{ 
              padding: '16px 24px', 
              backgroundColor: isDark ? '#1f2937' : '#f9fafb',
              borderRadius: '0 0 12px 12px',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '12px'
            }}>
              {/* После оплаты показываем кнопку печати талона */}
              {paymentDialog.paid ? (
                <>
                  <button 
                    type="button"
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
                      console.log('Кнопка "Закрыть" (оплачено) нажата через onMouseDown');
                      setPaymentDialog({ open: false, row: null, paid: false, source: null });
                    }}
                  >
                    Закрыть
                  </button>
                  <button
                    type="button"
                    className="clinic-button clinic-button-primary interactive-element hover-lift ripple-effect action-button-hover focus-ring"
                    style={{ 
                      padding: '8px 12px', 
                      borderRadius: 8, 
                      fontSize: 14,
                      position: 'relative',
                      zIndex: 10,
                      cursor: 'pointer',
                      pointerEvents: 'auto'
                    }}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      console.log('Кнопка "Печать талона" нажата через onMouseDown');
                      
                      const data = paymentDialog.row;
                      setPaymentDialog({ open: false, row: null, paid: false, source: null });
                      setTimeout(() => setPrintDialog({ open: true, type: 'ticket', data }), 0);
                    }}
                  >
                    🖨️ Печать талона
                  </button>
                </>
              ) : (
                <>
                  <button 
                    type="button"
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
                      console.log('Кнопка "Закрыть" (не оплачено) нажата через onMouseDown');
                      setPaymentDialog({ open: false, row: null, paid: false, source: null });
                    }}
                  >
                    Закрыть
                  </button>
                  <button
                    type="button"
                    className="clinic-button clinic-button-success interactive-element hover-lift ripple-effect action-button-hover focus-ring"
                    style={{ 
                      padding: '8px 12px', 
                      borderRadius: 8, 
                      fontSize: 14,
                      position: 'relative',
                      zIndex: 10,
                      cursor: 'pointer',
                      pointerEvents: 'auto'
                    }}
                    onMouseDown={async (e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      console.log('Кнопка "Оплатить" нажата через onMouseDown');
                      
                      try {
                        console.log('Начинаем оплату для записи:', paymentDialog.row.id);
                        const updated = await handlePayment(paymentDialog.row);
                        console.log('Результат оплаты:', updated);
                        
                        if (updated) {
                          // Обновляем состояние модального окна - показываем кнопку печати
                          setPaymentDialog(prev => ({ 
                            ...prev, 
                            paid: true, 
                            row: { ...prev.row, status: 'paid', payment_status: 'paid' }
                          }));
                          
                          toast.success('Оплата успешна. Пациент добавлен в очередь');
                          
                          // Если оплата была из таблицы, автоматически открываем печать
                          if (paymentDialog.source === 'table') {
                            setTimeout(() => {
                              setPaymentDialog({ open: false, row: null, paid: false, source: null });
                              setPrintDialog({ open: true, type: 'ticket', data: updated });
                            }, 1000);
                          }
                        }
                      } catch (error) {
                        console.error('Ошибка при оплате:', error);
                        toast.error('Ошибка при оплате: ' + error.message);
                      }
                    }}
                  >
                    💰 Оплатить
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
      {showWizard && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.8)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999
        }} role="dialog" aria-modal="true"
        onClick={(e) => {
          // Закрываем только при клике именно по фону, не по содержимому
          if (e.target === e.currentTarget) {
            console.log('Клик по фону мастера - закрываем');
            setShowWizard(false);
          }
        }}>
          <div 
            onClick={(e) => e.stopPropagation()} // Предотвращаем закрытие при клике внутри
            style={{
            background: cardBg,
            padding: '32px',
            borderRadius: '16px',
            maxWidth: '700px',
            width: '90%',
            maxHeight: '90vh',
            overflow: 'auto'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ margin: 0 }}>➕ {t('new_appointment')} (Шаг {wizardStep})</h2>
              <button onClick={() => setShowWizard(false)} style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer' }}>×</button>
            </div>
            
            {/* Шаг 1: Пациент */}
            {wizardStep === 1 && (
              <div>
                <h3 style={{ marginBottom: '16px', color: accentColor }}>👤 {t('patient')}</h3>
                <div style={{ display: 'grid', gap: '16px' }}>
                  {/* Резюме шага (контекст) */}
                  <div style={{
                    border: `1px solid ${borderColor}`,
                    borderRadius: 12,
                    padding: 12,
                    background: cardBg
                  }}>
                    <div style={{ fontWeight: 600, marginBottom: 6 }}>Контекст записи</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, fontSize: 13 }}>
                      <div>Пациент: {(wizardData.patient.fio || '—')}</div>
                      <div>Телефон: {(wizardData.patient.phone || '—')}</div>
                      <div>Дата рождения: {(wizardData.patient.dob || '—')}</div>
                    </div>
                  </div>
                  <div>
                    <label style={labelStyle}>ФИО пациента</label>
                <input
                  ref={fioRef}
                  type="text"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
                  style={{ 
                    borderColor: patientErrors.fio ? '#ef4444' : (isDark ? '#374151' : '#d1d5db'),
                    backgroundColor: isDark ? '#374151' : 'white',
                    color: textColor
                  }}
                      placeholder="Введите ФИО"
                  value={wizardData.patient.fio || ''}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        patient: { ...wizardData.patient, fio: e.target.value }
                      })}
                  onKeyDown={(e) => { if (e.key === 'Enter') dobRef.current?.focus(); }}
                    />
                    {patientErrors.fio && <div style={{ color: '#ef4444', fontSize: 12, marginTop: 4 }}>{patientErrors.fio}</div>}
                  </div>
                  <div>
                    <label style={labelStyle}>Дата рождения</label>
                <input
                      ref={dobRef}
                      type="date"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
                      style={{ 
                        borderColor: patientErrors.dob ? '#ef4444' : (isDark ? '#374151' : '#d1d5db'),
                        backgroundColor: isDark ? '#374151' : 'white',
                        color: textColor
                      }}
                      value={wizardData.patient.dob || ''}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        patient: { ...wizardData.patient, dob: e.target.value }
                      })}
                      onKeyDown={(e) => { if (e.key === 'Enter') phoneRef.current?.focus(); }}
                    />
                    {patientErrors.dob && <div style={{ color: '#ef4444', fontSize: 12, marginTop: 4 }}>{patientErrors.dob}</div>}
                  </div>
                  <div>
                    <label style={labelStyle}>Телефон</label>
                    <input
                      ref={phoneRef}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
                      style={{ 
                        borderColor: patientErrors.phone ? '#ef4444' : (isDark ? '#374151' : '#d1d5db'),
                        backgroundColor: isDark ? '#374151' : 'white',
                        color: textColor
                      }}
                      placeholder="+998 (90) 123-45-67"
                      value={wizardData.patient.phone || ''}
                      onChange={(e) => {
                        const raw = e.target.value;
                        let digits = raw.replace(/\D/g, '');
                        
                        // Если пользователь удаляет все, оставляем пустое поле
                        if (digits.length === 0) {
                          setWizardData({ ...wizardData, patient: { ...wizardData.patient, phone: '' } });
                          return;
                        }
                        
                        // Если пользователь не начал с 998, добавляем автоматически
                        if (!digits.startsWith('998')) {
                          digits = '998' + digits;
                        }
                        
                        // Ограничиваем длину (998 + 9 цифр = 12 максимум)
                        if (digits.length > 12) {
                          digits = digits.slice(0, 12);
                        }
                        
                        // Форматируем
                        let formatted = '+998';
                        const userDigits = digits.slice(3); // Убираем 998
                        
                        if (userDigits.length >= 1) {
                          formatted += ` (${userDigits.slice(0, 2)}`;
                          if (userDigits.length >= 2) {
                            formatted += ')';
                            if (userDigits.length >= 3) {
                              formatted += ` ${userDigits.slice(2, 5)}`;
                              if (userDigits.length >= 5) {
                                formatted += `-${userDigits.slice(5, 7)}`;
                                if (userDigits.length >= 7) {
                                  formatted += `-${userDigits.slice(7, 9)}`;
                                }
                              }
                            }
                          }
                        }
                        
                        setWizardData({ ...wizardData, patient: { ...wizardData.patient, phone: formatted } });
                      }}
                      onKeyDown={(e) => { if (e.key === 'Enter') handlePatientNext(); }}
                    />
                    {patientErrors.phone && <div style={{ color: '#ef4444', fontSize: 12, marginTop: 4 }}>{patientErrors.phone}</div>}
                  </div>
                </div>
                {showPatientSuggestions && patientSuggestions.length > 0 && (
                  <div style={{ marginTop: 8, background: '#fff', border: `1px solid ${borderColor}`, borderRadius: 8, padding: 8 }}>
                    <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 6 }}>Возможные совпадения:</div>
                    {patientSuggestions.map(s => (
                      <div key={s.id} style={{ padding: '6px 8px', cursor: 'pointer' }}
                        onClick={() => {
                          setWizardData({
                            ...wizardData,
                            patient: {
                              fio: s.patient_fio || wizardData.patient.fio,
                              dob: s.dob || wizardData.patient.dob,
                              phone: s.phone || wizardData.patient.phone
                            }
                          });
                          setSelectedPatientId(s.id || null);
                          setShowPatientSuggestions(false);
                        }}
                      >
                        {(s.patient_fio || '')} • {(s.phone || '')}
                      </div>
                    ))}
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 6 }}>
                      <button style={buttonSecondaryStyle} onClick={() => setShowPatientSuggestions(false)}>Скрыть</button>
                    </div>
                  </div>
                )}
                <div className="flex gap-3 mt-6">
                  <button 
                    type="button"
                    style={{ 
                      padding: '8px 16px',
                      borderRadius: '8px',
                      fontSize: '14px',
                      fontWeight: '600',
                      background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                      color: 'white',
                      border: 'none',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      boxShadow: '0 2px 4px rgba(59, 130, 246, 0.3)',
                      position: 'relative',
                      zIndex: 20,
                      minWidth: '100px'
                    }}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      console.log('Кнопка "Далее" нажата мышью');
                      handlePatientNext();
                    }}
                    onMouseEnter={(e) => {
                      e.target.style.transform = 'translateY(-1px)';
                      e.target.style.boxShadow = '0 4px 8px rgba(59, 130, 246, 0.4)';
                    }}
                    onMouseLeave={(e) => {
                      e.target.style.transform = 'translateY(0)';
                      e.target.style.boxShadow = '0 2px 4px rgba(59, 130, 246, 0.3)';
                    }}
                  >
                    {t('next')} →
                  </button>
                  <button 
                    className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-all duration-200 text-sm font-medium interactive-element hover-lift ripple-effect magnetic-hover focus-ring"
                    style={{ 
                      borderColor: isDark ? '#374151' : '#d1d5db',
                      color: isDark ? '#f9fafb' : '#374151',
                      backgroundColor: isDark ? '#374151' : 'white'
                    }}
                    onClick={() => setShowWizard(false)}
                  >
                    {t('close')}
                  </button>
                </div>
              </div>
            )}
            
            {/* Шаг 2: Детали */}
            {wizardStep === 2 && (
              <div>
                <h3 style={{ marginBottom: '16px', color: accentColor }}>📋 {t('details')}</h3>
                <div style={{ display: 'grid', gap: '16px' }}>
                  <div>
                    <label style={labelStyle}>Врач</label>
                    {simpleDoctorMode ? (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
                        {[
                          { key: 'cardiology', label: 'Кардиолог', emoji: '❤️' },
                          { key: 'dermatology', label: 'Дерматолог/Косметолог', emoji: '✨' },
                          { key: 'stomatology', label: 'Стоматолог', emoji: '🦷' }
                        ].map(s => {
                          const doc = getDoctorBySpecialty(s.key);
                          const isSelected = selectedDoctor?.specialty === s.key;
                          return (
                            <button key={s.key}
                              onClick={() => {
                                if (doc) {
                                  setSelectedDoctor(doc);
                                  setWizardData({ ...wizardData, visit: { ...wizardData.visit, doctor_id: doc?.id, specialty: s.key } });
                                }
                              }}
                              disabled={!doc}
                              style={{
                                textAlign: 'left',
                                padding: 12,
                                borderRadius: 12,
                                border: `2px solid ${isSelected ? accentColor : (doc ? borderColor : '#e5e7eb')}`,
                                background: isSelected ? `${accentColor}15` : (doc ? cardBg : '#f9fafb'),
                                cursor: doc ? 'pointer' : 'not-allowed',
                                opacity: doc ? 1 : 0.6
                              }}
                            >
                              <div style={{ fontSize: 18, fontWeight: 600 }}>{s.emoji} {s.label}</div>
                              <div style={{ fontSize: 13, opacity: 0.8, marginTop: 6 }}>
                                {doc ? (doc.user?.full_name || `Врач #${doc.id}`) : 'Врач не назначен'}
                              </div>
                              {doc?.cabinet && (
                                <div style={{ fontSize: 12, opacity: 0.7, marginTop: 4 }}>Кабинет: {doc.cabinet}</div>
                              )}
                              {doc?.price_default > 0 && (
                                <div style={{ fontSize: 12, marginTop: 4 }}>Цена от: {doc.price_default.toLocaleString()} UZS</div>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                    <IntegratedDoctorSelector
                      selectedDoctorId={selectedDoctor?.id}
                      onDoctorChange={(doctor) => {
                        setSelectedDoctor(doctor);
                        setWizardData({
                          ...wizardData,
                          visit: { ...wizardData.visit, doctor_id: doctor.id }
                        });
                      }}
                        showSchedule={false}
                    />
                    )}
                  </div>
                  <div>
                    <label style={labelStyle}>Услуги</label>
                    <IntegratedServiceSelector
                      selectedServices={selectedServices}
                      onServicesChange={(services) => {
                        setSelectedServices(services);
                        setWizardData({
                          ...wizardData,
                          visit: { ...wizardData.visit, services }
                        });
                      }}
                      simple
                      onNext={() => setWizardStep(3)}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Тип обращения</label>
                <select
                  style={inputStyle}
                      value={wizardData.visit.type || 'paid'}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        visit: { ...wizardData.visit, type: e.target.value }
                      })}
                    >
                      <option value="paid">Платный</option>
                      <option value="repeat">Повторный</option>
                      <option value="free">Льготный</option>
                </select>
                  </div>
                  {/* Поле "Приоритет" удалено по ТЗ */}
                  </div>
                {/* Нижняя панель действий шага */}
                <div style={{ display: 'flex', gap: '12px', marginTop: '24px', alignItems: 'center' }}>
                  <button style={buttonSecondaryStyle} onClick={() => setWizardStep(1)}>
                    ← {t('back')}
                  </button>
                  <button style={{ ...buttonStyle, opacity: canProceedStep2 ? 1 : 0.5, cursor: canProceedStep2 ? 'pointer' : 'not-allowed' }}
                          disabled={!canProceedStep2}
                          onClick={() => canProceedStep2 && setWizardStep(3)}>
                    {t('next')} →
                  </button>
                  {!selectedDoctor && (
                    <span style={{ color: '#ef4444', fontSize: 12 }}>Выберите врача</span>
                  )}
                  {selectedDoctor && selectedServices.length === 0 && (
                    <span style={{ color: '#ef4444', fontSize: 12 }}>
                      Выберите минимум одну услугу (выбрано: {selectedServices.length})
                    </span>
                  )}
                </div>
              </div>
            )}
            
            {/* Шаг 3: Подтверждение и оплата */}
            {wizardStep === 3 && (
              <div>
                <h3 style={{ marginBottom: '16px', color: accentColor }}>✅ Подтверждение</h3>
                <div style={{ display: 'grid', gap: 12 }}>
                  <div style={{ border: `1px solid ${borderColor}`, borderRadius: 12, padding: 12 }}>
                    <div style={{ fontWeight: 600, marginBottom: 6 }}>Пациент</div>
                    <div>{wizardData.patient.fio} • {wizardData.patient.phone} • {wizardData.patient.dob}</div>
                  </div>
                  <div style={{ border: `1px solid ${borderColor}`, borderRadius: 12, padding: 12 }}>
                    <div style={{ fontWeight: 600, marginBottom: 6 }}>Врач</div>
                    <div>{selectedDoctor?.user?.full_name || '—'} ({selectedDoctor?.specialty || '—'})</div>
              </div>
                  <div style={{ border: `1px solid ${borderColor}`, borderRadius: 12, padding: 12 }}>
                    <div style={{ fontWeight: 600, marginBottom: 6 }}>Услуги</div>
                    <ul style={{ margin: 0, paddingLeft: 18 }}>
                      {selectedServices.map(s => (
                        <li key={s.id}>{s.name} — {s.price?.toLocaleString()} UZS</li>
                      ))}
                    </ul>
                    <div style={{ marginTop: 8, fontWeight: 700 }}>Итого: {selectedServices.reduce((a,b)=>a+(b.price||0),0).toLocaleString()} UZS</div>
                </div>
                </div>
                <div style={{ display: 'flex', gap: 12, marginTop: 16 }}>
                  <button style={buttonSecondaryStyle} onClick={() => setWizardStep(2)}>← {t('back')}</button>
                  <button style={buttonStyle} onClick={async () => {
                    try {
                      const token = localStorage.getItem('auth_token');
                      if (!token) {
                        toast.error('Требуется авторизация. Пожалуйста, войдите в систему.');
                        return;
                      }
                      
                      const API_BASE = (import.meta?.env?.VITE_API_BASE_URL) || 'http://localhost:8000';
                      
                      // Сначала пытаемся найти существующего пациента по телефону
                      let patientId = selectedPatientId;
                      
                      if (!patientId && wizardData.patient?.phone) {
                        console.log('Searching for existing patient by phone:', wizardData.patient.phone);
                        
                        try {
                          // Пробуем разные варианты поиска
                          const searchVariants = [
                            `${API_BASE}/api/v1/patients/?q=${encodeURIComponent(wizardData.patient.phone)}`,
                            `${API_BASE}/api/v1/patients/?phone=${encodeURIComponent(wizardData.patient.phone)}`,
                            `${API_BASE}/api/v1/patients/search?phone=${encodeURIComponent(wizardData.patient.phone)}`,
                            `${API_BASE}/api/v1/patients/?search=${encodeURIComponent(wizardData.patient.phone)}`
                          ];
                          
                          for (const searchUrl of searchVariants) {
                            try {
                              console.log('Trying search URL:', searchUrl);
                              const response = await fetch(searchUrl, {
                                headers: { 'Authorization': `Bearer ${token}` }
                              });
                              
                              if (response.ok) {
                                const data = await response.json();
                                console.log('Search response:', data);
                                
                                // Пробуем разные форматы ответа
                                let patients = [];
                                if (Array.isArray(data)) {
                                  patients = data;
                                } else if (data.items && Array.isArray(data.items)) {
                                  patients = data.items;
                                } else if (data.results && Array.isArray(data.results)) {
                                  patients = data.results;
                                } else if (data.data && Array.isArray(data.data)) {
                                  patients = data.data;
                                }
                                
                                if (patients.length > 0) {
                                  // Ищем точное совпадение по телефону
                                  const phoneMatch = patients.find(p => 
                                    p.phone === wizardData.patient.phone ||
                                    p.phone?.replace(/\D/g, '') === wizardData.patient.phone.replace(/\D/g, '')
                                  );
                                  
                                  if (phoneMatch) {
                                    patientId = phoneMatch.id;
                                    console.log('Found existing patient with ID:', patientId, phoneMatch);
                                    break;
                                  }
                                }
                              }
                            } catch (searchError) {
                              console.warn('Search variant failed:', searchUrl, searchError.message || searchError);
                              // Не показываем ошибку пользователю, просто продолжаем поиск
                            }
                          }
                        } catch (error) {
                          console.warn('Error searching for existing patient:', error);
                        }
                      }
                      
                      // Если пациент не найден, создаем нового
                      if (!patientId && wizardData.patient) {
                        console.log('Creating new patient:', wizardData.patient);
                        
                        // Разделяем ФИО на части
                        const fioparts = wizardData.patient.fio.trim().split(' ');
                        const lastName = fioparts[0] || '';
                        const firstName = fioparts[1] || '';
                        const middleName = fioparts.slice(2).join(' ') || null;
                        
                        const patientData = {
                          last_name: lastName,
                          first_name: firstName,
                          middle_name: middleName,
                          birth_date: wizardData.patient.dob,
                          phone: wizardData.patient.phone,
                          sex: wizardData.patient.gender === 'female' ? 'F' : 'M'
                        };
                        
                        console.log('Patient data being sent:', patientData);
                        
                        try {
                          const patientResponse = await fetch(`${API_BASE}/api/v1/patients/`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                            body: JSON.stringify(patientData)
                          });
                          
                          if (patientResponse.ok) {
                            const newPatient = await patientResponse.json();
                            patientId = newPatient.id;
                            console.log('Created new patient with ID:', patientId);
                        } else {
                          const errorData = await patientResponse.json().catch(() => ({}));
                          console.log('Patient creation error:', errorData);
                          
                          // Если пациент уже существует, пытаемся найти его
                          if (errorData.detail && errorData.detail.includes('уже существует')) {
                            console.log('Patient already exists, trying to find by phone number');
                            
                            // Пробуем получить всех пациентов и найти нужного
                            try {
                              const allPatientsResponse = await fetch(`${API_BASE}/api/v1/patients/?limit=1000`, {
                                headers: { 'Authorization': `Bearer ${token}` }
                              });
                              
                              if (allPatientsResponse.ok) {
                                const allPatientsData = await allPatientsResponse.json();
                                const allPatients = Array.isArray(allPatientsData) ? allPatientsData : 
                                                  (allPatientsData.items || allPatientsData.results || allPatientsData.data || []);
                                
                                console.log('All patients for search:', allPatients.length);
                                
                                // Ищем по телефону
                                const existingPatient = allPatients.find(p => 
                                  p.phone === wizardData.patient.phone ||
                                  p.phone?.replace(/\D/g, '') === wizardData.patient.phone.replace(/\D/g, '')
                                );
                                
                                if (existingPatient) {
                                  patientId = existingPatient.id;
                                  console.log('Found existing patient in full list with ID:', patientId);
                                } else {
                                  console.log('Patient not found in full list, will show error');
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
                        } catch (error) {
                          console.error('Error creating patient:', error);
                          toast.error('Ошибка создания пациента: ' + error.message);
                          return;
                        }
                      }
                      
                      if (!patientId) {
                        toast.error('Не удалось определить пациента. Пожалуйста, заполните данные пациента.');
                        return;
                      }
                      
                      if (!selectedDoctor?.id) {
                        toast.error('Не выбран врач. Пожалуйста, выберите врача.');
                        return;
                      }
                      
                      if (selectedServices.length === 0) {
                        toast.error('Не выбраны услуги. Пожалуйста, выберите минимум одну услугу.');
                        return;
                      }
                      
                      console.log('Creating appointment with API_BASE:', API_BASE, 'Token exists:', !!token);
                      console.log('Token value:', token ? token.substring(0, 20) + '...' : 'null');
                      console.log('selectedPatientId:', selectedPatientId, 'type:', typeof selectedPatientId);
                      console.log('selectedDoctor:', selectedDoctor);
                      console.log('selectedServices:', selectedServices);
                      
                      const appointmentData = {
                        patient_id: parseInt(patientId),
                        doctor_id: parseInt(selectedDoctor?.id) || null,
                        appointment_date: new Date().toISOString().split('T')[0], // Сегодняшняя дата
                        appointment_time: new Date().toTimeString().slice(0, 5), // Текущее время
                        department: selectedDoctor?.specialty || 'general',
                        notes: `Услуги: ${selectedServices.map(s => s.name).join(', ')}`,
                        status: 'scheduled',
                        payment_amount: selectedServices.reduce((sum, s) => sum + (s.price || 0), 0),
                        payment_currency: 'UZS'
                      };
                      console.log('Appointment data being sent:', appointmentData);
                      
                      const res = await fetch(`${API_BASE}/api/v1/appointments`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                        body: JSON.stringify(appointmentData)
                      });
                      console.log('Appointment creation response status:', res.status);
                      if (!res.ok) {
                        const errorData = await res.json().catch(() => ({}));
                        console.log('Appointment creation error:', errorData);
                        if (res.status === 401) {
                          throw new Error('Сессия истекла. Пожалуйста, войдите в систему заново.');
                        } else if (res.status === 422) {
                          // Показываем детали ошибки валидации
                          const details = Array.isArray(errorData.detail) 
                            ? errorData.detail.map(err => `${err.loc?.join('.')}: ${err.msg}`).join(', ')
                            : errorData.detail || 'Неверные данные';
                          console.log('Validation errors:', errorData.detail);
                          throw new Error('Ошибка валидации данных: ' + details);
                        } else {
                          throw new Error('Ошибка создания записи: ' + (errorData.detail || `HTTP ${res.status}`));
                        }
                      }
                      const created = await res.json();
                      console.log('Created appointment:', created);
                      
                      // Закрываем мастер
                      setShowWizard(false);
                      setWizardStep(1);
                      
                      // Сбрасываем данные мастера
                      setWizardData({ patient: {}, visit: {}, payment: {} });
                      setSelectedDoctor(null);
                      setSelectedServices([]);
                      setSelectedPatientId(null);
                      
                      // Обновляем таблицу
                      await loadAppointments();
                      
                      // Подготавливаем данные для модального окна оплаты
                      const paymentRow = {
                        ...created,
                        patient_fio: wizardData.patient.fio,
                        patient_phone: wizardData.patient.phone,
                        cost: selectedServices.reduce((sum, s) => sum + (s.price || 0), 0),
                        payment_amount: selectedServices.reduce((sum, s) => sum + (s.price || 0), 0),
                        services: selectedServices.map(s => s.name).join(', '),
                        services_list: selectedServices, // Массив услуг для детального отображения
                        doctor_name: selectedDoctor?.user?.full_name || 'Не указан',
                        doctor_specialty: selectedDoctor?.specialty || 'Не указано',
                        appointment_date: new Date().toISOString().split('T')[0],
                        appointment_time: new Date().toTimeString().slice(0, 5)
                      };
                      
                      // Открываем модальное окно оплаты
                      setPaymentDialog({ 
                        open: true, 
                        row: paymentRow, 
                        paid: false, 
                        source: 'wizard' 
                      });
                      
                      toast.success('Запись создана! Переходим к оплате.');
                    } catch (e) {
                      toast.error(e.message || 'Ошибка создания записи');
                    }
                  }}>Создать запись → Оплата</button>
          </div>
        </div>
      )}
          </div>
              </div>
      )}
      
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
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h3 style={{ margin: 0 }}>💳 {t('online_payment')}</h3>
              <button onClick={() => setShowQRModal(false)} style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer' }}>×</button>
            </div>
            <div style={{ 
              width: '200px', 
              height: '200px', 
              background: '#f0f0f0', 
              margin: '0 auto 20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '12px',
              color: '#666',
              borderRadius: '8px'
            }}>
              QR код для оплаты
            </div>
            <p>Сумма: Не указано</p>
            <button style={buttonStyle} onClick={() => setShowQRModal(false)}>
              {t('close')}
            </button>
          </div>
        </div>
      )}

      {/* Простое модальное окно печати */}
      {printDialog.open && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 99999
        }}>
          <div style={{
            backgroundColor: cardBg,
            borderRadius: '12px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            width: '100%',
            maxWidth: '28rem',
            margin: '0 1rem'
          }}>
            <div style={{ padding: '24px' }}>
              <h3 style={{ 
                color: textColor, 
                fontSize: '20px', 
                fontWeight: '600', 
                marginBottom: '16px',
                margin: 0
              }}>
                🖨️ Печать талона
              </h3>
              <div style={{
                backgroundColor: isDark ? '#374151' : '#f8f9fa',
                borderRadius: '8px',
                padding: '16px',
                marginBottom: '16px'
              }}>
                <div style={{ 
                  color: textColor, 
                  fontSize: '14px', 
                  marginBottom: '12px',
                  display: 'flex',
                  justifyContent: 'space-between'
                }}>
                  <span>Пациент:</span>
                  <span style={{ fontWeight: '600' }}>{printDialog.data?.patient_fio || 'Не указано'}</span>
                </div>
                <div style={{ 
                  color: textColor, 
                  fontSize: '14px', 
                  marginBottom: '12px',
                  display: 'flex',
                  justifyContent: 'space-between'
                }}>
                  <span>Телефон:</span>
                  <span style={{ fontWeight: '500' }}>{printDialog.data?.patient_phone || 'Не указано'}</span>
                </div>
                <div style={{ 
                  color: textColor, 
                  fontSize: '14px', 
                  marginBottom: '12px'
                }}>
                  <div style={{ marginBottom: '8px', fontWeight: '500' }}>Услуги:</div>
                  <div style={{ paddingLeft: '12px' }}>
                    {printDialog.data?.services_list && Array.isArray(printDialog.data.services_list) ? (
                      printDialog.data.services_list.map((service, index) => (
                        <div key={index} style={{ 
                          display: 'flex', 
                          justifyContent: 'space-between', 
                          marginBottom: '4px',
                          fontSize: '13px'
                        }}>
                          <span>{service.name}</span>
                          <span style={{ fontWeight: '500' }}>{service.price?.toLocaleString()} UZS</span>
                        </div>
                      ))
                    ) : (
                      <div style={{ fontSize: '13px', fontStyle: 'italic' }}>
                        {printDialog.data?.services || 
                         printDialog.data?.doctor_specialty || 
                         'Консультация врача'}
                      </div>
                    )}
                  </div>
                </div>
                <div style={{ 
                  color: textColor, 
                  fontSize: '14px', 
                  marginBottom: '12px',
                  display: 'flex',
                  justifyContent: 'space-between'
                }}>
                  <span>Врач:</span>
                  <span style={{ fontWeight: '500' }}>
                    {printDialog.data?.doctor_name || 'Не указан'}
                  </span>
                </div>
                <div style={{ 
                  color: textColor, 
                  fontSize: '16px', 
                  fontWeight: '700',
                  display: 'flex',
                  justifyContent: 'space-between',
                  paddingTop: '8px',
                  borderTop: `1px solid ${isDark ? '#4b5563' : '#e5e7eb'}`
                }}>
                  <span>Итого:</span>
                  <span style={{ color: '#059669' }}>
                    {(printDialog.data?.cost || printDialog.data?.payment_amount || 0).toLocaleString()} UZS
                  </span>
                </div>
                <div style={{ 
                  color: textColor, 
                  fontSize: '12px', 
                  marginTop: '8px',
                  opacity: 0.7
                }}>
                  Дата: {new Date().toLocaleDateString('ru-RU')} • 
                  Время: {new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>
            </div>
            <div style={{ 
              padding: '16px 24px', 
              backgroundColor: isDark ? '#1f2937' : '#f9fafb',
              borderRadius: '0 0 12px 12px',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '12px'
            }}>
              <button 
                type="button"
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
                  console.log('Кнопка "Отмена" печати нажата через onMouseDown');
                  setPrintDialog({ open: false, type: '', data: null });
                }}
              >
                Отмена
              </button>
              <button
                type="button"
                className="clinic-button clinic-button-primary interactive-element hover-lift ripple-effect action-button-hover focus-ring"
                style={{ 
                  padding: '8px 12px', 
                  borderRadius: 8, 
                  fontSize: 14,
                  position: 'relative',
                  zIndex: 10,
                  cursor: 'pointer',
                  pointerEvents: 'auto'
                }}
                onMouseDown={async (e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  
                  if (printInProgress) {
                    console.log('Печать уже выполняется, игнорируем клик');
                    return;
                  }
                  
                  console.log('Кнопка "Печать" нажата через onMouseDown');
                  console.log('Данные для печати:', printDialog.data);
                  
                  setPrintInProgress(true);
                  
                  // Подготавливаем данные для API печати
                  const printData = {
                    ...printDialog.data,
                    queue_number: String(printDialog.data?.id || Math.floor(Math.random() * 1000)),
                    doctor_name: printDialog.data?.doctor_name || 'Врач не указан',
                    specialty_name: printDialog.data?.doctor_specialty === 'cardiology' ? 'Кардиология' :
                                   printDialog.data?.doctor_specialty === 'dermatology' ? 'Дерматология' :
                                   printDialog.data?.doctor_specialty === 'stomatology' ? 'Стоматология' :
                                   printDialog.data?.department === 'laboratory' ? 'Лаборатория' :
                                   printDialog.data?.department === 'procedures' ? 'Процедуры' :
                                   'Общая медицина'
                  };
                  
                  console.log('Подготовленные данные для печати:', printData);
                  
                  try {
                    const response = await fetch(`${API_BASE}/api/v1/print/ticket`, {
                      method: 'POST',
                      headers: {
                        'Authorization': `Bearer ${localStorage.getItem('auth_token')}`,
                        'Content-Type': 'application/json'
                      },
                      body: JSON.stringify(printData)
                    });
                    
                    console.log('Ответ печати:', response.status, response.statusText);
                    
                    if (response.ok) {
                      toast.success('Талон отправлен на печать');
                      setPrintDialog({ open: false, type: '', data: null });
                    } else {
                      const errorText = await response.text();
                      console.error('Ошибка печати:', response.status, errorText);
                      toast.error('Ошибка печати: ' + response.status);
                    }
                  } catch (e) {
                    console.error('Ошибка печати:', e);
                    toast.error('Ошибка печати');
                  } finally {
                    setPrintInProgress(false);
                  }
                }}
              >
                🖨️ Печать
              </button>
            </div>
          </div>
        </div>
      )} */

      {/* Модальное окно жесткого потока */}
      {showAppointmentFlow && selectedAppointment && (
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
            padding: '32px',
            borderRadius: '16px',
            maxWidth: '600px',
            width: '90%',
            maxHeight: '90vh',
            overflow: 'auto'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ margin: 0 }}>🔄 Поток записи</h2>
              <button onClick={() => setShowAppointmentFlow(false)} style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer' }}>×</button>
            </div>
            
            <AppointmentFlow
              appointment={selectedAppointment}
              onStartVisit={handleStartVisit}
              onPayment={handlePayment}
            />
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
    </div>
  );
};

export default RegistrarPanel; 