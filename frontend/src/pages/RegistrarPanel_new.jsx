import React, { useState, useEffect, useCallback, useMemo, memo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Toaster, toast } from 'react-hot-toast';
import { Plus, Download, Printer, RotateCcw } from 'lucide-react';

// Контексты и хуки
import { useTheme } from '../contexts/ThemeContext';
import { useBreakpoint, useTouchDevice } from '../hooks/useMediaQuery';

// Компоненты UI
import { Card, AnimatedTransition } from '../components/ui';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import AppointmentContextMenu from '../components/tables/AppointmentContextMenu';
import ModernTabs from '../components/navigation/ModernTabs';

// Современные диалоги
import PaymentDialog from '../components/dialogs/PaymentDialog';
import CancelDialog from '../components/dialogs/CancelDialog';
import PrintDialog from '../components/dialogs/PrintDialog';

// Современный мастер
import AppointmentWizard from '../components/wizard/AppointmentWizard';

// Компонент потока записи
import AppointmentFlow from '../components/AppointmentFlow';

// Современные фильтры (заглушка)
const ModernFilters = ({ searchParams, onParamsChange, autoRefresh, onAutoRefreshChange, appointmentsCount }) => (
  <div style={{ padding: '16px', marginBottom: '16px', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
    <p>Фильтры: {appointmentsCount} записей найдено</p>
  </div>
);

// Современная очередь (заглушка)
const ModernQueueManager = (props) => (
  <div style={{ padding: '16px', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
    <p>Онлайн-очередь (в разработке)</p>
  </div>
);

// Современная статистика (заглушка)
const ModernStatistics = ({ appointments, onExport, onRefresh }) => (
  <div style={{ padding: '16px', marginBottom: '16px', border: '1px solid #e5e7eb', borderRadius: '8px' }}>
    <h3>Статистика</h3>
    <p>Всего записей: {appointments.length}</p>
    <button onClick={onRefresh} style={{ marginRight: '8px' }}>Обновить</button>
    <button onClick={onExport}>Экспорт</button>
  </div>
);

// Стили
import '../components/ui/animations.css';
import '../styles/responsive.css';

const RegistrarPanel = () => {
  // Хуки
  const { theme, getColor } = useTheme();
  const { isMobile, isTablet, isDesktop } = useBreakpoint();
  const isTouch = useTouchDevice();
  
  // Переводы (упрощенная версия)
  const t = (key) => {
    const translations = {
      'welcome_back': 'Добро пожаловать',
      'new_appointment': 'Новая запись',
      'online_queue': 'Онлайн-очередь',
      'quick_start': 'Быстрый старт',
      'export_csv': 'Экспорт CSV',
      'today': 'Сегодня',
      'reset': 'Сброс'
    };
    return translations[key] || key;
  };
  
  // URL параметры
  const [searchParams] = useSearchParams();
  
  // Основные состояния
  const [activeTab, setActiveTab] = useState(null);
  const [loading, setLoading] = useState(false);
  const [appointments, setAppointments] = useState([]);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [dataSource, setDataSource] = useState('loading'); // 'loading' | 'api' | 'demo' | 'error'
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [appointmentsSelected, setAppointmentsSelected] = useState(new Set());
  
  // Демо-данные
  const todayStr = new Date().toISOString().split('T')[0];
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
    }
  ];
  
  // Диалоги
  const [showWizard, setShowWizard] = useState(false);
  const [paymentDialog, setPaymentDialog] = useState({ open: false, row: null });
  const [cancelDialog, setCancelDialog] = useState({ open: false, row: null });
  const [printDialog, setPrintDialog] = useState({ open: false, row: null });
  const [contextMenu, setContextMenu] = useState({ open: false, row: null, position: { x: 0, y: 0 } });
  
  // Данные
  const [doctors, setDoctors] = useState([]);
  const [services, setServices] = useState({});
  const [queueSettings, setQueueSettings] = useState({});
  const [selectedPatientId, setSelectedPatientId] = useState(null);
  const [selectedAppointment, setSelectedAppointment] = useState(null);
  const [showAppointmentFlow, setShowAppointmentFlow] = useState(false);
  
  // Язык
  const [language, setLanguage] = useState(() => localStorage.getItem('ui_lang') || 'ru');
  
  // Простой компонент индикатора данных
  const DataSourceIndicator = ({ count }) => (
    <div style={{ 
      fontSize: '12px', 
      color: getColor('textSecondary'), 
      marginBottom: '8px',
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    }}>
      <span>✅ Загружено записей: {count}</span>
    </div>
  );
  
  // API Base
  const API_BASE = 'http://localhost:8000';
  
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
      // Только логируем ошибку, не спамим консоль
      if (error.message !== 'Failed to fetch') {
        console.error(`Error fetching patient ${patientId}:`, error);
      }
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

  // Загрузка записей с API
  const loadAppointments = useCallback(async () => {
    try {
      setAppointmentsLoading(true);
      setDataSource('loading');
      
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
          // Обогащаем данные пациентов только если не на главной странице
          const shouldEnrichPatientData = activeTab !== null;
          const enriched = shouldEnrichPatientData 
            ? await enrichAppointmentsWithPatientData(appointmentsData)
            : appointmentsData;
          
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
          console.debug('✅ Загружены данные из API:', enriched.length, 'записей');
        } else {
          setAppointments(DEMO_APPOINTMENTS);
          setDataSource('demo');
        }
      } else if (response.status === 401) {
        console.warn('Токен недействителен (401), используем демо-данные');
        localStorage.removeItem('auth_token');
        setDataSource('demo');
        setAppointments(DEMO_APPOINTMENTS);
      } else {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }
    } catch (error) {
      // Не логируем "Failed to fetch" чтобы не спамить консоль
      if (error.message !== 'Failed to fetch') {
        console.error('Ошибка загрузки записей:', error);
        toast.error('Не удалось загрузить данные с сервера. Показаны демо-данные.');
      } else {
        console.warn('Сервер недоступен, используем демо-данные');
      }
      setDataSource('demo');
      setAppointments(DEMO_APPOINTMENTS);
    } finally {
      setAppointmentsLoading(false);
    }
  }, [API_BASE, activeTab]); // Убираем функции из зависимостей

  // Загрузка интегрированных данных
  const loadIntegratedData = useCallback(async () => {
    try {
      setAppointmentsLoading(true);
      
      // Устанавливаем fallback данные
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

      // Попытка загрузки с API
      const token = localStorage.getItem('auth_token');
      if (token) {
        try {
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
            if (apiDoctors.length > 0) {
              setDoctors(apiDoctors);
            }
          }

          if (servicesRes.ok) {
            const servicesData = await servicesRes.json();
            const apiServices = servicesData.services_by_group || {};
            if (Object.keys(apiServices).length > 0) {
              setServices(apiServices);
            }
          }

          if (queueRes.ok) {
            const queueData = await queueRes.json();
            setQueueSettings(queueData);
          }
        } catch (error) {
          console.warn('Ошибка загрузки данных из админ панели:', error);
        }
      }
    } catch (error) {
      console.error('Ошибка загрузки интегрированных данных:', error);
    } finally {
      setAppointmentsLoading(false);
    }
  }, [API_BASE]);

  // Функция обновления статуса записи
  const updateAppointmentStatus = useCallback(async (appointmentId, status, reason = '') => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      toast.error('Токен аутентификации отсутствует');
      return null;
    }

    try {
      let url, method = 'POST', body;
      
      if (status === 'complete' || status === 'done') {
        url = `${API_BASE}/api/v1/appointments/${appointmentId}/complete`;
        body = JSON.stringify({ reason });
      } else if (status === 'paid' || status === 'mark-paid') {
        url = `${API_BASE}/api/v1/appointments/${appointmentId}/mark-paid`;
      } else if (status === 'cancelled' || status === 'canceled') {
        // Локальное обновление для отмены
        setAppointments(prev => prev.map(apt => 
          apt.id === appointmentId ? { 
            ...apt, 
            status: 'cancelled',
            _locallyModified: true,
            _cancelReason: reason
          } : apt
        ));
        toast.success('Запись отменена');
        return { id: appointmentId, status: 'cancelled' };
      } else if (status === 'confirmed') {
        // Локальное обновление для подтверждения
        setAppointments(prev => prev.map(apt => 
          apt.id === appointmentId ? { 
            ...apt, 
            status: 'confirmed',
            _locallyModified: true
          } : apt
        ));
        toast.success('Запись подтверждена');
        return { id: appointmentId, status: 'confirmed' };
      } else if (status === 'no_show') {
        // Локальное обновление для неявки
        setAppointments(prev => prev.map(apt => 
          apt.id === appointmentId ? { 
            ...apt, 
            status: 'no_show',
            _locallyModified: true,
            _noShowReason: reason
          } : apt
        ));
        toast.success('Отмечено как неявка');
        return { id: appointmentId, status: 'no_show' };
      } else if (status === 'in_cabinet') {
        url = `${API_BASE}/api/v1/appointments/${appointmentId}/start-visit`;
      } else {
        toast.error('Изменение данного статуса не поддерживается');
        return;
      }
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body
      });
      
      if (!response.ok) {
        const errText = await response.text().catch(() => '');
        throw new Error(errText || `API ${response.status}`);
      }
      
      const updatedAppointment = await response.json();
      
      // Обновляем локальное состояние
      setAppointments(prev => prev.map(apt => 
        apt.id === appointmentId ? { ...apt, status: updatedAppointment.status || status } : apt
      ));
      
      await loadAppointments();
      toast.success('Статус обновлен');
      return updatedAppointment;
    } catch (error) {
      console.error('Update status error:', error);
      toast.error('Не удалось обновить статус: ' + error.message);
      return null;
    }
  }, [API_BASE, loadAppointments]);

  // Массовые действия
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

  // Функция для начала приема (вызов пациента)
  const handleStartVisit = useCallback(async (appointment) => {
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
  }, [API_BASE]);

  // Функция для переноса записи
  const handleReschedule = useCallback(async (appointment) => {
    // Показываем диалог выбора новой даты
    const newDate = window.prompt('Выберите новую дату для записи (формат: ГГГГ-ММ-ДД)', appointment.date || appointment.appointment_date);
    
    if (!newDate) return;
    
    // Валидация формата даты
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    if (!dateRegex.test(newDate)) {
      toast.error('Неверный формат даты. Используйте формат: ГГГГ-ММ-ДД');
      return;
    }
    
    try {
      const response = await fetch(`${API_BASE}/api/v1/appointments/${appointment.id}/reschedule`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({ new_date: newDate })
      });

      if (response.ok) {
        const updatedAppointment = await response.json();
        // Обновляем список записей
        setAppointments(prev => prev.map(apt => 
          apt.id === appointment.id ? { ...updatedAppointment, _locallyModified: true } : apt
        ));
        toast.success(`Запись перенесена на ${newDate}`);
        await loadAppointments();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Ошибка при переносе записи');
      }
    } catch (error) {
      console.error('Ошибка переноса записи:', error);
      // Временное решение - локальное обновление
      setAppointments(prev => prev.map(apt => 
        apt.id === appointment.id ? { 
          ...apt, 
          date: newDate, 
          appointment_date: newDate,
          _locallyModified: true,
          _rescheduled: true
        } : apt
      ));
      toast.success(`Запись перенесена на ${newDate} (локально)`);
    }
  }, [API_BASE, loadAppointments]);

  // Функция для обработки оплаты
  const handlePayment = useCallback(async (appointment) => {
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
      
      console.log('Отправляем запрос на:', `${API_BASE}/api/v1/appointments/${appointment.id}/mark-paid`);
      
      const response = await fetch(`${API_BASE}/api/v1/appointments/${appointment.id}/mark-paid`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (response.ok) {
        const updatedAppointment = await response.json();
        console.log('Получен ответ от сервера:', updatedAppointment);
        
        // Обновляем локальное состояние
        setAppointments(prev => prev.map(apt => 
          apt.id === appointment.id ? { 
            ...updatedAppointment, 
            status: 'queued',
            payment_status: 'paid',
            _locallyModified: true 
          } : apt
        ));
        
        // Перезагружаем данные для синхронизации
        await loadAppointments();
        
        return updatedAppointment;
      } else {
        const error = await response.json();
        console.error('Ошибка API:', error);
        throw new Error(error.detail || 'Ошибка при оплате');
      }
    } catch (error) {
      console.error('handlePayment error:', error);
      toast.error('Ошибка при обработке оплаты: ' + error.message);
      return null;
    }
  }, [API_BASE, loadAppointments]);

  // Первичная загрузка данных (убрано - дублирует эффект ниже)

  // Автообновление отключено для избежания циклов рендеринга

  // Фильтрация записей
  const searchDate = searchParams.get('date');
  const searchQuery = (searchParams.get('q') || '').toLowerCase();
  const statusFilter = searchParams.get('status');

  const isInDepartment = useCallback((appointment, departmentKey) => {
    const dept = (appointment.department?.toLowerCase() || '');
    const specialty = (appointment.doctor_specialty?.toLowerCase() || '');
    
    if (departmentKey === 'cardio') return dept.includes('cardio') || specialty.includes('cardio');
    if (departmentKey === 'echokg' || departmentKey === 'ecg') return dept.includes('ecg') || dept.includes('echo') || specialty.includes('cardio');
    if (departmentKey === 'derma') return dept.includes('derma') || specialty.includes('derma');
    if (departmentKey === 'dental') return dept.includes('dental') || dept.includes('stoma') || specialty.includes('stoma');
    if (departmentKey === 'lab') return dept.includes('lab') || dept.includes('laboratory') || specialty.includes('lab');
    if (departmentKey === 'procedures' || departmentKey === 'proc') return dept.includes('proc') || dept.includes('procedure') || specialty.includes('procedure');
    return false;
  }, []);

  const filteredAppointments = useMemo(() => {
    return appointments.filter(appointment => {
      // Фильтр по вкладке (отдел)
      if (activeTab && !isInDepartment(appointment, activeTab)) {
        return false;
      }
      // Фильтр по дате
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
  }, [appointments, activeTab, searchDate, statusFilter, searchQuery, isInDepartment]);

  // Статистика по отделам
  const departmentStats = useMemo(() => {
    const stats = {};
    const departments = ['cardio', 'echokg', 'derma', 'dental', 'lab', 'procedures'];
    
    departments.forEach(dept => {
      const deptAppointments = appointments.filter(a => isInDepartment(a, dept));
      const todayAppointments = deptAppointments.filter(a => {
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
  }, [appointments, todayStr, isInDepartment]);

  // Счетчики по отделам
  const getDepartmentCount = useCallback((departmentKey) => {
    return departmentStats[departmentKey]?.todayCount || 0;
  }, [departmentStats]);

  const hasActiveQueue = useCallback((departmentKey) => {
    return departmentStats[departmentKey]?.hasActiveQueue || false;
  }, [departmentStats]);

  const hasPendingPayments = useCallback((departmentKey) => {
    return departmentStats[departmentKey]?.hasPendingPayments || false;
  }, [departmentStats]);

  // Горячие клавиши
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
      }
      
      if (e.ctrlKey) {
        if (e.key === 'k') {
          e.preventDefault();
          setShowWizard(true);
        } else if (e.key === '1') setActiveTab('cardio');
        else if (e.key === '2') setActiveTab('derma');
        else if (e.key === '3') setActiveTab('dental');
        else if (e.key === '4') setActiveTab('lab');
        else if (e.key === '5') setActiveTab('procedures');
        else if (e.key === 'a') {
          e.preventDefault();
          const allIds = filteredAppointments.map(a => a.id);
          setAppointmentsSelected(new Set(allIds));
        } else if (e.key === 'd') {
          e.preventDefault();
          setAppointmentsSelected(new Set());
        }
      } else if (e.altKey) {
        if (e.key === '1') { 
          e.preventDefault(); 
          if (appointmentsSelected.size > 0) {
            handleBulkAction('confirmed'); 
          }
        } else if (e.key === '2') { 
          e.preventDefault(); 
          if (appointmentsSelected.size > 0) {
            const reason = window.prompt('Причина отмены');
            if (reason) handleBulkAction('cancelled', reason);
          }
        } else if (e.key === '3') { 
          e.preventDefault(); 
          if (appointmentsSelected.size > 0) {
            handleBulkAction('no_show'); 
          }
        }
      } else if (e.key === 'Escape') {
        if (showWizard) setShowWizard(false);
        if (paymentDialog.open) setPaymentDialog({ open: false, row: null });
        if (cancelDialog.open) setCancelDialog({ open: false, row: null });
        if (printDialog.open) setPrintDialog({ open: false, row: null });
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [showWizard, paymentDialog.open, cancelDialog.open, printDialog.open, filteredAppointments, appointmentsSelected, handleBulkAction]);

  // Обновленный компонент индикатора данных
  const DataSourceIndicatorUpdated = memo(({ count }) => {
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
  
  // Стили
  const pageStyle = {
    minHeight: '100vh',
    backgroundColor: getColor('bg'),
    color: getColor('textPrimary'),
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
  };





  // Обработчики действий
  const handleRowClick = useCallback((row) => {
    console.log('Row clicked:', row);
    // Можно открыть детали записи
  }, []);

  const handleContextMenuAction = useCallback(async (action, row) => {
    setContextMenu({ open: false, row: null, position: { x: 0, y: 0 } });
    
    switch (action) {
      case 'view':
        console.log('Просмотр записи:', row);
        setSelectedAppointment(row);
        setShowAppointmentFlow(true);
        break;
      case 'edit':
        console.log('Редактирование записи:', row);
        toast('Функция редактирования будет добавлена в следующих версиях', { 
          icon: 'ℹ️',
          style: {
            background: '#3b82f6',
            color: 'white'
          }
        });
        break;
      case 'in_cabinet':
        await updateAppointmentStatus(row.id, 'in_cabinet');
        toast.success('Пациент отправлен в кабинет');
        break;
      case 'call':
        console.log('Начать прием:', row);
        await handleStartVisit(row);
        break;
      case 'complete':
        await updateAppointmentStatus(row.id, 'done');
        toast.success('Приём завершён');
        break;
      case 'payment':
      case 'pay':
        setPaymentDialog({ open: true, row });
        break;
      case 'print':
        setPrintDialog({ open: true, row });
        break;
      case 'reschedule':
        console.log('Перенести запись:', row);
        handleReschedule(row);
        break;
      case 'cancel':
        setCancelDialog({ open: true, row });
        break;
      case 'call_patient':
        if (row.patient_phone) {
          window.open(`tel:${row.patient_phone}`);
        }
        break;
      default:
        console.log('Unknown action:', action);
    }
  }, [updateAppointmentStatus]);

  // Эффекты
  useEffect(() => {
    loadAppointments();
    loadIntegratedData();
  }, []);

  useEffect(() => {
    localStorage.setItem('ui_lang', language);
  }, [language]);

  // Автообновление отключено для избежания циклов

  return (
    <div style={pageStyle} role="main" aria-label="Панель регистратора">
      <Toaster position="bottom-right" />

      {/* Skip to content link */}
      <a 
        href="#main-content" 
        style={{
          position: 'absolute',
          left: '-9999px',
          top: '0',
          zIndex: 9999,
          padding: '8px 16px',
          background: getColor('primary'),
          color: 'white',
          textDecoration: 'none',
          borderRadius: '0 0 4px 4px'
        }}
        onFocus={(e) => e.target.style.left = '0'}
        onBlur={(e) => e.target.style.left = '-9999px'}
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

      {/* Welcome View - Главная вкладка */}
      {(searchParams.get('view') === 'welcome' || (!searchParams.get('view') && activeTab === null)) && (
        <AnimatedTransition type="fade" delay={200}>
          <Card style={{
            background: getColor('cardBg'),
            border: `1px solid ${getColor('border')}`,
            borderRadius: '20px',
            margin: isMobile ? '12px 16px' : '16px 32px',
            marginTop: isMobile ? '12px' : '16px',
            boxShadow: theme === 'light'
              ? '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
              : '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
          }}>
            <Card.Header style={{
              padding: isMobile ? '16px' : '24px',
              borderBottom: `1px solid ${getColor('border')}`,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '16px'
            }}>
              <h1 style={{
                fontSize: isMobile ? '24px' : '28px',
                fontWeight: 700,
                color: getColor('textPrimary'),
                margin: 0
              }}>
                👋 Добро пожаловать!
              </h1>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  className="clinic-button clinic-button-primary"
                  onClick={() => setShowWizard(true)}
                  style={{ padding: '8px 12px', borderRadius: 8, fontSize: 14 }}
                >
                  ➕ Новая запись
                </button>
                <button
                  className="clinic-button clinic-button-outline"
                  onClick={() => window.open('/online-booking', '_blank')}
                  style={{ padding: '8px 12px', borderRadius: 8, fontSize: 14 }}
                >
                  🌐 Онлайн запись
                </button>
              </div>
            </Card.Header>

            <Card.Content>
              <ModernStatistics
                appointments={appointments}
                departmentStats={departmentStats}
                language={language}
                onExport={() => console.log('Экспорт статистики')}
                onRefresh={() => {
                  loadAppointments();
                  loadIntegratedData();
                }}
              />

              {appointments.length > 0 && (
                <div>
                  <h3 style={{ fontSize: '20px', marginBottom: '16px', color: getColor('accent') }}>
                    📋 Краткая сводка
                  </h3>
                  <div style={{
                    background: getColor('cardBg'),
                    border: `1px solid ${getColor('border')}`,
                    borderRadius: '8px',
                    padding: '16px'
                  }}>
                    <DataSourceIndicator count={appointments.length} />
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fit, minmax(200px, 1fr))',
                      gap: '16px',
                      marginTop: '16px'
                    }}>
                      <div style={{
                        padding: '16px',
                        background: getColor('primary') + '10',
                        borderRadius: '8px',
                        textAlign: 'center'
                      }}>
                        <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('primary') }}>
                          {appointments.length}
                        </div>
                        <div style={{ fontSize: '14px', color: getColor('textSecondary') }}>
                          Всего записей
                        </div>
                      </div>
                      <div style={{
                        padding: '16px',
                        background: getColor('success') + '10',
                        borderRadius: '8px',
                        textAlign: 'center'
                      }}>
                        <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('success') }}>
                          {appointments.filter(a => a.status === 'confirmed' || a.status === 'queued').length}
                        </div>
                        <div style={{ fontSize: '14px', color: getColor('textSecondary') }}>
                          Активных
                        </div>
                      </div>
                      <div style={{
                        padding: '16px',
                        background: getColor('warning') + '10',
                        borderRadius: '8px',
                        textAlign: 'center'
                      }}>
                        <div style={{ fontSize: '24px', fontWeight: 'bold', color: getColor('warning') }}>
                          {appointments.filter(a => a.payment_status === 'pending').length}
                        </div>
                        <div style={{ fontSize: '14px', color: getColor('textSecondary') }}>
                          Ожидают оплаты
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </Card.Content>
          </Card>
        </AnimatedTransition>
      )}

      {/* Queue View */}
      {searchParams.get('view') === 'queue' && (
        <AnimatedTransition type="fade" delay={200}>
          <Card style={{
            background: getColor('cardBg'),
            border: `1px solid ${getColor('border')}`,
            borderRadius: '20px',
            margin: isMobile ? '12px 16px' : '16px 32px',
            marginTop: isMobile ? '12px' : '16px',
            boxShadow: theme === 'light'
              ? '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
              : '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
          }}>
            <Card.Header style={{
              padding: isMobile ? '16px' : '24px',
              borderBottom: `1px solid ${getColor('border')}`,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: '16px'
            }}>
              <h1 style={{
                fontSize: isMobile ? '24px' : '28px',
                fontWeight: 700,
                color: getColor('textPrimary'),
                margin: 0
              }}>
                📱 Онлайн-очередь
              </h1>
              <button
                className="clinic-button clinic-button-primary"
                onClick={() => setShowWizard(true)}
                style={{ padding: '8px 12px', borderRadius: 8, fontSize: 14 }}
              >
                ➕ Новая запись
              </button>
            </Card.Header>

            <Card.Content>
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
                selectedSpecialist={searchParams.get('doctor') || ''}
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

      {/* Main Panel */}
      {(!searchParams.get('view') || (searchParams.get('view') !== 'welcome' && searchParams.get('view') !== 'queue')) && (
        <div id="main-content" style={{
          background: getColor('cardBg'),
          border: `1px solid ${getColor('border')}`,
          borderRadius: '20px',
          margin: isMobile ? '12px 16px' : '16px 32px',
          boxShadow: theme === 'light'
            ? '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)'
            : '0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
        }}>
          <div style={{ padding: isMobile ? '12px' : '16px' }}>
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

            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '16px',
              flexWrap: 'wrap',
              gap: '12px'
            }}>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                <button
                  className="clinic-button clinic-button-primary"
                  onClick={() => setShowWizard(true)}
                >
                  <Plus size={16} />
                  <span className="hide-on-mobile">Новая запись</span>
                </button>
                <button className="clinic-button clinic-button-outline">
                  <Download size={16} />
                  <span className="hide-on-mobile">Экспорт CSV</span>
                </button>
              </div>
              <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                <button className="clinic-button clinic-button-outline">
                  <Printer size={16} />
                  <span className="hide-on-mobile">Печать</span>
                </button>
                <button
                  className="clinic-button clinic-button-outline"
                  onClick={() => {
                    const params = new URLSearchParams();
                    params.delete('view');
                    window.history.replaceState(null, '', `/registrar-panel?${params.toString()}`);
                  }}
                >
                  <RotateCcw size={16} />
                  <span className="hide-on-mobile">Сбросить фильтры</span>
                </button>
              </div>
            </div>

            <DataSourceIndicator count={filteredAppointments.length} />
            
            <EnhancedAppointmentsTable
              data={filteredAppointments}
              loading={loading}
              selected={appointmentsSelected}
              onSelectionChange={setAppointmentsSelected}
              onRowClick={handleRowClick}
              onActionClick={handleContextMenuAction}
              theme={theme}
              language={language}
            />

            {/* Массовые действия */}
            {appointmentsSelected.size > 0 && (
              <div style={{
                display: 'flex',
                gap: '12px',
                alignItems: 'center',
                padding: '16px',
                background: theme === 'light' ? '#f8f9fa' : '#374151',
                borderRadius: '8px',
                marginTop: '16px',
                flexWrap: 'wrap'
              }}>
                <span style={{ fontWeight: 600, marginRight: '12px' }}>
                  🎯 Массовые действия ({appointmentsSelected.size}):
                </span>
                <button 
                  className="clinic-button clinic-button-success"
                  onClick={() => handleBulkAction('confirmed')}
                  style={{ padding: '8px 12px', borderRadius: 8, fontSize: 14 }}
                >
                  ✅ Подтвердить
                </button>
                <button 
                  className="clinic-button clinic-button-danger"
                  onClick={() => {
                    const reason = window.prompt('Причина отмены');
                    if (reason) handleBulkAction('cancelled', reason);
                  }}
                  style={{ padding: '8px 12px', borderRadius: 8, fontSize: 14 }}
                >
                  ❌ Отменить
                </button>
                <button 
                  className="clinic-button clinic-button-warning"
                  onClick={() => handleBulkAction('no_show')}
                  style={{ padding: '8px 12px', borderRadius: 8, fontSize: 14 }}
                >
                  👻 Неявка
                </button>
                <button 
                  className="clinic-button clinic-button-outline"
                  onClick={() => setAppointmentsSelected(new Set())}
                  style={{ padding: '8px 12px', borderRadius: 8, fontSize: 14 }}
                >
                  ✖️ Снять выделение
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Диалоги */}
      <PaymentDialog
        isOpen={paymentDialog.open}
        onClose={() => setPaymentDialog({ open: false, row: null })}
        appointment={paymentDialog.row}
        onPayment={handlePayment}
        onSuccess={() => {
          setPaymentDialog({ open: false, row: null });
          loadAppointments();
        }}
      />

      <CancelDialog
        isOpen={cancelDialog.open}
        onClose={() => setCancelDialog({ open: false, row: null })}
        appointment={cancelDialog.row}
        onSuccess={() => {
          setCancelDialog({ open: false, row: null });
          loadAppointments();
        }}
      />

      <PrintDialog
        isOpen={printDialog.open}
        onClose={() => setPrintDialog({ open: false, row: null })}
        appointment={printDialog.row}
      />

      {/* Мастер создания записи */}
      <AppointmentWizard
        isOpen={showWizard}
        onClose={() => setShowWizard(false)}
        doctors={doctors}
        services={services}
        onComplete={async (wizardData) => {
          try {
            // Создание пациента
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
                  email: null,
                  doc_number: null
                })
              });
              
              if (patientResponse.ok) {
                const patient = await patientResponse.json();
                patientId = patient.id;
              } else {
                throw new Error('Ошибка создания пациента');
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
                doctor_id: wizardData.appointment.doctor_id || null,
                services: wizardData.appointment.services,
                date: wizardData.appointment.date,
                time: wizardData.appointment.time || '09:00',
                visit_type: wizardData.appointment.visit_type || 'Платный',
                notes: wizardData.appointment.notes || '',
                status: 'confirmed'
              })
            });

            if (appointmentResponse.ok) {
              setShowWizard(false);
              loadAppointments();
              
              // Открыть диалог оплаты
              const appointment = await appointmentResponse.json();
              setPaymentDialog({ 
                open: true, 
                row: {
                  ...appointment,
                  patient_fio: wizardData.patient.fio,
                  patient_phone: wizardData.patient.phone,
                  cost: wizardData.payment.amount
                }
              });
            } else {
              throw new Error('Ошибка создания записи');
            }
            
          } catch (error) {
            console.error('Error in wizard completion:', error);
            throw error;
          }
        }}
      />

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

      {/* Модальное окно потока записи */}
      {showAppointmentFlow && selectedAppointment && (
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
          zIndex: 9999
        }}>
          <div style={{
            backgroundColor: getColor('cardBg'),
            borderRadius: '20px',
            padding: '24px',
            maxWidth: '600px',
            width: '90%',
            maxHeight: '90vh',
            overflowY: 'auto',
            position: 'relative'
          }}>
            <button
              onClick={() => {
                setShowAppointmentFlow(false);
                setSelectedAppointment(null);
              }}
              style={{
                position: 'absolute',
                top: '16px',
                right: '16px',
                background: 'none',
                border: 'none',
                fontSize: '24px',
                cursor: 'pointer',
                color: getColor('textSecondary')
              }}
            >
              ✕
            </button>
            
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