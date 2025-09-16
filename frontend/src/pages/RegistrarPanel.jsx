import React, { useState, useEffect, useCallback } from 'react';
import PhoneInput from '../components/ui/PhoneInput';
import { Toaster, toast } from 'react-hot-toast';
import AppointmentsTable from '../components/AppointmentsTable';
import ServiceChecklist from '../components/ServiceChecklist';
import IntegratedServiceSelector from '../components/registrar/IntegratedServiceSelector';
import IntegratedDoctorSelector from '../components/registrar/IntegratedDoctorSelector';
import OnlineQueueManager from '../components/queue/OnlineQueueManager';
import AppointmentFlow from '../components/AppointmentFlow';
import ResponsiveTable from '../components/ResponsiveTable';
import ResponsiveNavigation from '../components/layout/ResponsiveNavigation';
import { Button, Card, Badge, Skeleton, AnimatedTransition, AnimatedToast, AnimatedLoader } from '../components/ui';
import { useBreakpoint, useTouchDevice } from '../hooks/useMediaQuery';
import { useTheme } from '../contexts/ThemeContext';
import PrintButton from '../components/print/PrintButton';
import PrintDialog from '../components/print/PrintDialog';
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
 

const RegistrarPanel = () => {
  // Адаптивные хуки
  const { isMobile, isTablet, isDesktop } = useBreakpoint();
  const isTouch = useTouchDevice();

  // Основные состояния
  const [activeTab, setActiveTab] = useState('welcome');
  
  // Состояния для печати
  const [printDialog, setPrintDialog] = useState({ open: false, type: '', data: null });
  // Демо-данные вынесены в константу
  const DEMO_APPOINTMENTS = [
    {
      id: 1,
      patient_fio: 'Иванов Иван Иванович',
      patient_birth_year: 1985,
      patient_phone: '+7 (999) 123-45-67',
      services: ['Консультация кардиолога', 'ЭКГ'],
      visit_type: 'Платный',
      payment_type: 'Карта',
      cost: 2500,
      status: 'confirmed',
      isEmpty: false,
      department: 'cardio'
    },
    {
      id: 2,
      patient_fio: 'Петрова Анна Сергеевна',
      patient_birth_year: 1990,
      patient_phone: '+7 (999) 234-56-78',
      services: ['УЗИ сердца'],
      visit_type: 'Повторный',
      payment_type: 'Наличные',
      cost: 1800,
      status: 'queued',
      isEmpty: false,
      department: 'echokg'
    },
    {
      id: 3,
      patient_fio: 'Сидоров Петр Александрович',
      patient_birth_year: 1975,
      patient_phone: '+7 (999) 345-67-89',
      services: ['Консультация дерматолога'],
      visit_type: 'Платный',
      payment_type: 'Карта',
      cost: 2000,
      status: 'confirmed',
      isEmpty: false,
      department: 'derma'
    },
    {
      id: 4,
      patient_fio: 'Козлова Мария Владимировна',
      patient_birth_year: 1988,
      patient_phone: '+7 (999) 456-78-90',
      services: ['Лечение кариеса'],
      visit_type: 'Платный',
      payment_type: 'Наличные',
      cost: 3000,
      status: 'plan',
      isEmpty: false,
      department: 'dental'
    },
    {
      id: 5,
      patient_fio: 'Морозов Алексей Игоревич',
      patient_birth_year: 1992,
      patient_phone: '+7 (999) 567-89-01',
      services: ['Общий анализ крови', 'Биохимия'],
      visit_type: 'Платный',
      payment_type: 'Карта',
      cost: 1200,
      status: 'confirmed',
      isEmpty: false,
      department: 'lab'
    },
    {
      id: 6,
      patient_fio: 'Волкова Елена Сергеевна',
      patient_birth_year: 1983,
      patient_phone: '+7 (999) 678-90-12',
      services: ['Капельница', 'Инъекция'],
      visit_type: 'Повторный',
      payment_type: 'Наличные',
      cost: 1500,
      status: 'queued',
      isEmpty: false,
      department: 'procedures'
    }
  ];

  // Состояния для управления данными
  const [appointments, setAppointments] = useState([]);
  const [dataSource, setDataSource] = useState('loading'); // 'loading' | 'api' | 'demo' | 'error'
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [appointmentsSelected, setAppointmentsSelected] = useState(new Set());
  const [showAddressColumn, setShowAddressColumn] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const [showSlotsModal, setShowSlotsModal] = useState(false);
  const [selectedAppointment, setSelectedAppointment] = useState(null);
  const [showAppointmentFlow, setShowAppointmentFlow] = useState(false);
  const [showQRModal, setShowQRModal] = useState(false);

  // Фиксированный хедер убран - теперь используется глобальный хедер
  
  // Состояния мастера
  const [wizardStep, setWizardStep] = useState(1);
  const [wizardData, setWizardData] = useState({
    patient: {},
    visit: {},
    payment: {}
  });
  
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
      
      // Вкладки
      tabs_welcome: 'Главная',
      tabs_appointments: 'Все записи',
      tabs_cardio: 'Кардиолог',
      tabs_echokg: 'ЭхоКГ',
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
      
      // Статистика
      total_patients: 'Всего пациентов',
      today_appointments: 'Записей сегодня',
      pending_payments: 'Ожидают оплаты',
      active_queues: 'Активные очереди'
    },
    uz: {
      // Основные
      welcome: 'Xush kelibsiz',
      start_work: 'Ishni boshlash',
      quick_start: 'Tezkor start',
      
      // Вкладки
      tabs_welcome: 'Asosiy',
      tabs_appointments: 'Barcha yozuvlar',
      tabs_cardio: 'Kardiolog',
      tabs_echokg: 'EchoKG',
      tabs_derma: 'Dermatolog',
      tabs_dental: 'Stomatolog',
      tabs_lab: 'Laboratoriya',
      tabs_procedures: 'Protseduralar',
      
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
      
      // Статистика
      total_patients: 'Jami bemorlar',
      today_appointments: 'Bugungi yozuvlar',
      pending_payments: 'To\'lovni kutmoqda',
      active_queues: 'Faol navbatlar'
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
    ...buttonStyle,
    background: `linear-gradient(135deg, ${getColor('gray', 500)} 0%, ${getColor('gray', 600)} 100%)`,
    boxShadow: '0 4px 14px 0 rgba(107, 114, 128, 0.3)',
    textShadow: '0 1px 2px rgba(0, 0, 0, 0.5)'
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
    gap: isMobile ? '4px' : getSpacing('xs')
  };

  const activeTabStyle = {
    ...tabStyle,
    background: `linear-gradient(135deg, ${getColor('primary', 500)} 0%, ${getColor('primary', 600)} 100%)`,
    color: 'white',
    boxShadow: '0 4px 14px 0 rgba(59, 130, 246, 0.3)',
    transform: 'translateY(-2px)'
  };

  // Загрузка данных из админ панели
  const loadIntegratedData = async () => {
    try {
      setAppointmentsLoading(true);
      
      // Загружаем врачей, услуги и настройки очередей из админ панели
      const [doctorsRes, servicesRes, queueRes] = await Promise.all([
        fetch('/api/v1/registrar/doctors', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` }
        }),
        fetch('/api/v1/registrar/services', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` }
        }),
        fetch('/api/v1/registrar/queue-settings', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` }
        })
      ]);

      if (doctorsRes.ok) {
        const doctorsData = await doctorsRes.json();
        setDoctors(doctorsData.doctors);
      }

      if (servicesRes.ok) {
        const servicesData = await servicesRes.json();
        setServices(servicesData.services_by_group);
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
      
      const response = await fetch('/api/v1/appointments/?limit=50', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        const appointmentsData = Array.isArray(data) ? data : (data.items || data.appointments || []);
        
        if (appointmentsData.length > 0) {
          setAppointments(appointmentsData);
          setDataSource('api');
          console.log('✅ Загружены данные из API:', appointmentsData.length, 'записей');
        } else {
          // API вернул пустой массив - показываем демо-данные
          setAppointments(DEMO_APPOINTMENTS);
          setDataSource('demo');
          console.log('ℹ️ API вернул пустые данные, используем демо-данные');
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
      if (window.toast) {
        window.toast.error('Не удалось загрузить данные с сервера. Показаны демо-данные.');
      }
    } finally {
      setAppointmentsLoading(false);
    }
  };

  useEffect(() => {
    loadAppointments();
    loadIntegratedData(); // Загружаем данные из админ панели
  }, []);

  // Функции для жесткого потока
  const handleStartVisit = async (appointment) => {
    try {
      const response = await fetch(`/api/v1/appointments/${appointment.id}/start-visit`, {
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
      const response = await fetch(`/api/v1/appointments/${appointment.id}/mark-paid`, {
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
        toast.success('Запись отмечена как оплаченная!');
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Ошибка при оплате');
      }
    } catch (error) {
      console.error('RegistrarPanel: Payment error:', error);
      toast.error('Ошибка при оплате');
    }
  };

  // Обработчики событий
  const updateAppointmentStatus = useCallback(async (appointmentId, status, reason = '') => {
    try {
      const response = await fetch(`/api/v1/appointments/${appointmentId}/status`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({ status, reason })
      });
      if (response.ok) {
        await loadAppointments();
      }
    } catch (error) {
      console.error('Ошибка обновления статуса:', error);
    }
  }, []);

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
    
    const promises = Array.from(appointmentsSelected).map(id => 
      updateAppointmentStatus(id, action, reason)
    );
    
    await Promise.all(promises);
    toast.success(`Статус ${appointmentsSelected.size} записей успешно обновлен!`);
    setAppointmentsSelected(new Set());
  }, [appointmentsSelected, updateAppointmentStatus]);

  // Горячие клавиши
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      
      if (e.key === 'Enter') {
        if (showWizard) {
          if (wizardStep < 3) {
            setWizardStep(wizardStep + 1);
          } else {
            setShowWizard(false);
            setWizardStep(1);
            loadAppointments();
          }
        }
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
          setAppointmentsSelected(new Set(appointments.map(a => a.id)));
        } else if (e.key === 'd') {
          e.preventDefault();
          setAppointmentsSelected(new Set());
        }
      } else if (e.key === 'Escape') {
        if (showWizard) setShowWizard(false);
        if (showSlotsModal) setShowSlotsModal(false);
        if (showQRModal) setShowQRModal(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [showWizard, showSlotsModal, showQRModal, wizardStep, appointments]);

  // Функция для подсчета записей по отделам (исправляет двойную фильтрацию)
  const getDepartmentCount = (department) => {
    return appointments.filter(a => 
      a.department?.toLowerCase().includes(department.toLowerCase())
    ).length;
  };

  // Фильтрация записей по вкладке
  const filteredAppointments = appointments.filter(appointment => {
    if (activeTab === 'welcome' || activeTab === 'appointments') return true;
    if (activeTab === 'cardio') return appointment.department?.toLowerCase().includes('cardio');
    if (activeTab === 'echokg') return appointment.department?.toLowerCase().includes('echo');
    if (activeTab === 'derma') return appointment.department?.toLowerCase().includes('derma');
    if (activeTab === 'dental') return appointment.department?.toLowerCase().includes('dental');
    if (activeTab === 'lab') return appointment.department?.toLowerCase().includes('lab');
    if (activeTab === 'procedures') return appointment.department?.toLowerCase().includes('proc');
    return true;
  });

  // Компонент индикатора источника данных (для всех вкладок)
  const DataSourceIndicator = ({ count }) => {
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
  };

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

  // Статистика для экрана приветствия
  const stats = {
    totalPatients: appointments.length,
    todayAppointments: appointments.filter(a => a.date === new Date().toISOString().split('T')[0]).length,
    pendingPayments: appointments.filter(a => a.status === 'paid_pending').length,
    activeQueues: appointments.filter(a => a.status === 'queued').length
  };

  

  return (
    <div style={{ ...pageStyle, overflow: 'hidden' }} role="main" aria-label="Панель регистратора">
      <Toaster position="bottom-right" />
      {/* Фиксированная верхняя часть убрана - используется глобальный хедер */}

      {/* Вкладки */}
        <div style={{
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
          <button
            style={activeTab === 'welcome' ? activeTabStyle : tabStyle}
            onClick={() => setActiveTab('welcome')}
            aria-selected={activeTab === 'welcome'}
          >
            <Home size={16} style={{ marginRight: '8px' }} />
            {t('tabs_welcome')}
          </button>
        <button
          style={activeTab === 'appointments' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('appointments')}
          aria-selected={activeTab === 'appointments'}
        >
            <FileText size={16} style={{ marginRight: '8px' }} />
          {t('tabs_appointments')} ({appointments.length})
        </button>
        <button
          style={activeTab === 'cardio' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('cardio')}
          aria-selected={activeTab === 'cardio'}
        >
            <Heart size={16} style={{ marginRight: '8px' }} />
          {t('tabs_cardio')} ({getDepartmentCount('cardio')})
        </button>
        <button
          style={activeTab === 'echokg' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('echokg')}
          aria-selected={activeTab === 'echokg'}
        >
            <Activity size={16} style={{ marginRight: '8px' }} />
          {t('tabs_echokg')} ({getDepartmentCount('echo')})
        </button>
        <button
          style={activeTab === 'derma' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('derma')}
          aria-selected={activeTab === 'derma'}
        >
            <User size={16} style={{ marginRight: '8px' }} />
          {t('tabs_derma')} ({getDepartmentCount('derma')})
        </button>
        <button
          style={activeTab === 'dental' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('dental')}
          aria-selected={activeTab === 'dental'}
        >
            <User size={16} style={{ marginRight: '8px' }} />
          {t('tabs_dental')} ({getDepartmentCount('dental')})
        </button>
        <button
          style={activeTab === 'lab' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('lab')}
          aria-selected={activeTab === 'lab'}
        >
            <TestTube size={16} style={{ marginRight: '8px' }} />
          {t('tabs_lab')} ({getDepartmentCount('lab')})
        </button>
        <button
          style={activeTab === 'queue' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('queue')}
          aria-selected={activeTab === 'queue'}
        >
            <MessageCircle size={16} style={{ marginRight: '8px' }} />
          {t('tabs_queue')}
        </button>
        <button
          style={activeTab === 'procedures' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('procedures')}
          aria-selected={activeTab === 'procedures'}
        >
            <Syringe size={16} style={{ marginRight: '8px' }} />
          {t('tabs_procedures')} ({getDepartmentCount('proc')})
        </button>
      </div>
      {/* </div> Закрытие фиксированного контейнера */}

      {/* Основной контент без отступа сверху */}
      <div style={{ overflow: 'hidden' }}>
        {/* Экран приветствия */}
        {activeTab === 'welcome' && (
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
              {/* Статистика */}
              <AnimatedTransition type="fade" delay={600}>
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', 
                  gap: '20px', 
                  marginBottom: '32px' 
                }}>
                <div style={{
                  background: `linear-gradient(135deg, ${accentColor} 0%, #0056b3 100%)`,
                  color: 'white',
                  padding: '24px',
                  borderRadius: '12px',
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '32px', fontWeight: 'bold', marginBottom: '8px' }}>
                    {stats.totalPatients}
                  </div>
                  <div style={{ fontSize: '16px', opacity: 0.9 }}>
                    {t('total_patients')}
                  </div>
              </div>
              
                <div style={{
                  background: `linear-gradient(135deg, ${successColor} 0%, #1e7e34 100%)`,
                  color: 'white',
                  padding: '24px',
                  borderRadius: '12px',
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '32px', fontWeight: 'bold', marginBottom: '8px' }}>
                    {stats.todayAppointments}
                  </div>
                  <div style={{ fontSize: '16px', opacity: 0.9 }}>
                    {t('today_appointments')}
                </div>
            </div>
                
                <div style={{
                  background: `linear-gradient(135deg, ${warningColor} 0%, #e0a800 100%)`,
                  color: '#212529',
                  padding: '24px',
                  borderRadius: '12px',
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '32px', fontWeight: 'bold', marginBottom: '8px' }}>
                    {stats.pendingPayments}
                  </div>
                  <div style={{ fontSize: '16px', opacity: 0.9 }}>
                    {t('pending_payments')}
            </div>
          </div>

                <div style={{
                  background: `linear-gradient(135deg, ${dangerColor} 0%, #c82333 100%)`,
                  color: 'white',
                  padding: '24px',
                  borderRadius: '12px',
                  textAlign: 'center'
                }}>
                  <div style={{ fontSize: '32px', fontWeight: 'bold', marginBottom: '8px' }}>
                    {stats.activeQueues}
            </div>
                  <div style={{ fontSize: '16px', opacity: 0.9 }}>
                    {t('active_queues')}
                  </div>
                </div>
                </div>
              </AnimatedTransition>

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
                      gap: '16px' 
                    }}>
                  <AnimatedTransition type="scale" delay={1300}>
                    <button 
                      style={{
                        ...buttonStyle,
                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
                      }}
                      onClick={() => setShowWizard(true)}
                      onMouseEnter={(e) => {
                        e.target.style.transform = 'translateY(-2px) scale(1.05)';
                        e.target.style.boxShadow = '0 8px 25px 0 rgba(59, 130, 246, 0.4)';
                      }}
                      onMouseLeave={(e) => {
                        e.target.style.transform = 'translateY(0) scale(1)';
                        e.target.style.boxShadow = '0 4px 14px 0 rgba(59, 130, 246, 0.3)';
                      }}
                    >
                      ➕ {t('new_appointment')}
                    </button>
                  </AnimatedTransition>
                  <AnimatedTransition type="scale" delay={1400}>
                    <button 
                      style={{
                        ...buttonSecondaryStyle,
                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
                      }}
                      onMouseEnter={(e) => {
                        e.target.style.transform = 'translateY(-2px) scale(1.05)';
                      }}
                      onMouseLeave={(e) => {
                        e.target.style.transform = 'translateY(0) scale(1)';
                      }}
                    >
                      📊 {t('export_csv')}
                    </button>
                  </AnimatedTransition>
                  <AnimatedTransition type="scale" delay={1500}>
                    <button 
                      style={{
                        ...buttonWarningStyle,
                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
                      }}
                      onMouseEnter={(e) => {
                        e.target.style.transform = 'translateY(-2px) scale(1.05)';
                      }}
                      onMouseLeave={(e) => {
                        e.target.style.transform = 'translateY(0) scale(1)';
                      }}
                    >
                      📅 {t('today')}
                    </button>
                  </AnimatedTransition>
                  <AnimatedTransition type="scale" delay={1600}>
                    <button 
                      style={{
                        ...buttonSecondaryStyle,
                        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
                      }}
                      onMouseEnter={(e) => {
                        e.target.style.transform = 'translateY(-2px) scale(1.05)';
                      }}
                      onMouseLeave={(e) => {
                        e.target.style.transform = 'translateY(0) scale(1)';
                      }}
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

        {/* Вкладка онлайн-очереди */}
        {activeTab === 'queue' && (
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
                <OnlineQueueManager />
              </Card.Content>
            </Card>
          </AnimatedTransition>
        )}

        {/* Основная панель с записями */}
        {activeTab !== 'welcome' && activeTab !== 'queue' && (
          <div style={{
            ...tableContainerStyle, 
            // избегаем конфликта marginTop + margin (шорткат)
            margin: `${-1}px ${isMobile ? getSpacing('md') : getSpacing('xl')} ${getSpacing('xl')} ${isMobile ? getSpacing('md') : getSpacing('xl')}`,
            borderRadius: isMobile ? '0 0 12px 12px' : '0 0 20px 20px'
          }}>
            <div style={{
              ...tableContentStyle,
              padding: isMobile ? getSpacing('sm') : getSpacing('md')
            }}>
              
              {/* Индикатор источника данных для всех вкладок */}
              <DataSourceIndicator count={filteredAppointments.length} />
              
              {/* Панель управления таблицей */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '12px',
                flexWrap: 'wrap',
                gap: '8px'
              }}>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <button
                    onClick={() => setShowAddressColumn(!showAddressColumn)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: showAddressColumn ? '2px solid #3b82f6' : '1px solid #d1d5db',
                      background: showAddressColumn ? '#3b82f620' : 'white',
                      color: showAddressColumn ? '#3b82f6' : '#6b7280',
                      cursor: 'pointer',
                      fontSize: '14px',
                      fontWeight: '500',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    📍 {showAddressColumn ? 'Скрыть адрес' : 'Показать адрес'}
                  </button>
                  
                  <button
                    onClick={() => loadAppointments()}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid #d1d5db',
                      background: 'white',
                      color: '#6b7280',
                      cursor: 'pointer',
                      fontSize: '14px',
                      fontWeight: '500',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    🔄 Обновить
                  </button>
                  
                  <button
                    onClick={() => {
                      const csv = generateCSV(filteredAppointments);
                      downloadCSV(csv, `appointments_${new Date().toISOString().split('T')[0]}.csv`);
                    }}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid #d1d5db',
                      background: 'white',
                      color: '#6b7280',
                      cursor: 'pointer',
                      fontSize: '14px',
                      fontWeight: '500',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px'
                    }}
                  >
                    📥 Экспорт CSV
                  </button>
                </div>
                
                <div style={{ 
                  fontSize: '14px', 
                  color: '#6b7280',
                  fontWeight: '500'
                }}>
                  Показано: {filteredAppointments.length} записей
                </div>
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
                  <Button variant="success" size={isMobile ? 'xs' : 'sm'} onClick={() => handleBulkAction('confirmed')}>
                    ✅ {!isMobile && t('confirm')}
                  </Button>
                  <Button variant="danger" size={isMobile ? 'xs' : 'sm'} onClick={() => {
                    const reason = prompt(t('reason'));
                    if (reason) handleBulkAction('cancelled', reason);
                  }}>
                    ❌ {!isMobile && t('cancel')}
                  </Button>
                  <Button variant="warning" size={isMobile ? 'xs' : 'sm'} onClick={() => handleBulkAction('no_show')}>
                    ⚠️ {!isMobile && t('no_show')}
                  </Button>
        </div>
              )}
              
              {/* Таблица записей */}
              {appointmentsLoading ? (
                <AnimatedLoader.TableSkeleton rows={8} columns={10} />
              ) : (
                <ResponsiveTable
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
                        const statusConfig = {
                          'plan': { label: 'Запланирован', color: 'info', icon: '📅' },
                          'confirmed': { label: 'Подтвержден', color: 'success', icon: '✅' },
                          'queued': { label: 'В очереди', color: 'warning', icon: '⏳' },
                          'in_cabinet': { label: 'В кабинете', color: 'primary', icon: '🏥' },
                          'done': { label: 'Завершен', color: 'success', icon: '✔️' },
                          'canceled': { label: 'Отменен', color: 'danger', icon: '❌' },
                          'no_show': { label: 'Неявка', color: 'secondary', icon: '🚫' },
                          'paid_pending': { label: 'Ожидает оплаты', color: 'warning', icon: '💳' },
                          'paid': { label: 'Оплачен', color: 'success', icon: '💰' }
                        };
                        
                        const config = statusConfig[value] || { 
                          label: value || 'Неизвестно', 
                          color: 'secondary', 
                          icon: '❓' 
                        };
                        
                        return (
                          <Badge variant={config.color} size="md">
                            {config.icon} {config.label}
                          </Badge>
                        );
                      }
                    }
                  ]}
                  actions={[
                    { 
                      icon: <Printer size={16} />, 
                      variant: 'primary', 
                      title: 'Печать талона',
                      onClick: (row) => {
                        setPrintDialog({ 
                          open: true, 
                          type: 'ticket', 
                          data: row 
                        });
                      },
                      visible: (row) => row.status !== 'canceled' && row.status !== 'done'
                    },
                    { 
                      icon: <X size={16} />, 
                      variant: 'danger', 
                      title: 'Отмена',
                      onClick: async (row) => {
                        const reason = prompt('Укажите причину отмены:');
                        if (reason) {
                          await updateAppointmentStatus(row.id, 'canceled', reason);
                          toast.success('Запись отменена');
                        }
                      },
                      visible: (row) => row.status !== 'canceled' && row.status !== 'done'
                    },
                    { 
                      icon: <Calendar size={16} />, 
                      variant: 'warning', 
                      title: 'Перенос',
                      onClick: (row) => {
                        setSelectedAppointment(row);
                        setShowSlotsModal(true);
                      },
                      visible: (row) => row.status !== 'done' && row.status !== 'in_cabinet'
                    },
                    { 
                      icon: <CreditCard size={16} />, 
                      variant: 'info', 
                      title: 'Оплата',
                      onClick: (row) => {
                        handlePayment(row);
                      },
                      visible: (row) => row.status === 'paid_pending' || !row.payment_status
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
      {showWizard && (
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
            maxWidth: '700px',
            width: '90%',
            maxHeight: '90vh',
            overflow: 'auto'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h2 style={{ margin: 0 }}>➕ {t('new_appointment')}</h2>
              <button onClick={() => setShowWizard(false)} style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer' }}>×</button>
            </div>
            
            {/* Шаг 1: Пациент */}
            {wizardStep === 1 && (
              <div>
                <h3 style={{ marginBottom: '16px', color: accentColor }}>👤 {t('patient')}</h3>
                <div style={{ display: 'grid', gap: '16px' }}>
                  <div>
                    <label style={labelStyle}>ФИО пациента</label>
                <input
                  type="text"
                  style={inputStyle}
                      placeholder="Введите ФИО"
                  value={wizardData.patient.fio || ''}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        patient: { ...wizardData.patient, fio: e.target.value }
                      })}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Год рождения</label>
                <input
                  type="number"
                      style={inputStyle}
                      placeholder="1985"
                  min="1900"
                  max={new Date().getFullYear() - 1}
                      value={wizardData.patient.birthYear || ''}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        patient: { ...wizardData.patient, birthYear: e.target.value }
                      })}
                    />
                  </div>
                  <div>
                    <label style={labelStyle}>Телефон</label>
                    <PhoneInput
                      style={inputStyle}
                      placeholder="+7 (999) 123-45-67"
                      value={wizardData.patient.phone || ''}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        patient: { ...wizardData.patient, phone: e.target.value }
                      })}
                    />
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
                  <button style={buttonStyle} onClick={() => setWizardStep(2)}>
                    {t('next')} →
                  </button>
                  <button style={buttonSecondaryStyle} onClick={() => setShowWizard(false)}>
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
                    <IntegratedDoctorSelector
                      selectedDoctorId={selectedDoctor?.id}
                      onDoctorChange={(doctor) => {
                        setSelectedDoctor(doctor);
                        setWizardData({
                          ...wizardData,
                          visit: { ...wizardData.visit, doctor_id: doctor.id }
                        });
                      }}
                      showSchedule={true}
                    />
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
                      specialty={selectedDoctor?.specialty}
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
                  <div>
                    <label style={labelStyle}>Приоритет</label>
                    <select
                  style={inputStyle}
                      value={wizardData.visit.priority || 'normal'}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        visit: { ...wizardData.visit, priority: e.target.value }
                      })}
                    >
                      <option value="normal">Обычный</option>
                      <option value="high">Высокий</option>
                      <option value="urgent">Срочный</option>
                    </select>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
                  <button style={buttonSecondaryStyle} onClick={() => setWizardStep(1)}>
                    ← {t('back')}
                  </button>
                  <button style={buttonStyle} onClick={() => setWizardStep(3)}>
                    {t('next')} →
                  </button>
                </div>
              </div>
            )}
            
            {/* Шаг 3: Оплата */}
            {wizardStep === 3 && (
              <div>
                <h3 style={{ marginBottom: '16px', color: accentColor }}>💳 {t('payment')}</h3>
                <div style={{ display: 'grid', gap: '16px' }}>
                  <div>
                    <label style={labelStyle}>Способ оплаты</label>
                <select
                  style={inputStyle}
                      value={wizardData.payment.method || 'cash'}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        payment: { ...wizardData.payment, method: e.target.value }
                      })}
                    >
                  <option value="cash">Наличные</option>
                      <option value="card">Банковская карта</option>
                  <option value="online">Онлайн</option>
                </select>
                  </div>
                  <div>
                    <label style={labelStyle}>Стоимость (₽)</label>
                  <input
                      type="number"
                      style={inputStyle}
                      placeholder="1000"
                      min="0"
                      value={wizardData.payment.amount || ''}
                      onChange={(e) => setWizardData({
                        ...wizardData,
                        payment: { ...wizardData.payment, amount: e.target.value }
                      })}
                    />
              </div>
                </div>
                <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
                  <button style={buttonSecondaryStyle} onClick={() => setWizardStep(2)}>
                    ← {t('back')}
                </button>
                  <button style={buttonStyle} onClick={() => {
                    // Здесь будет логика сохранения записи
                    setShowWizard(false);
                    setWizardStep(1);
                    loadAppointments();
                  }}>
                    ✅ {t('save')}
                  </button>
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
    </div>
  );
};

export default RegistrarPanel; 