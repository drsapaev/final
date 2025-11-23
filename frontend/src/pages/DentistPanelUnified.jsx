import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTheme } from '../contexts/ThemeContext';
import { useBreakpoint, useTouchDevice } from '../hooks/useEnhancedMediaQuery';
import { Button, Badge, Card, Icon } from '../components/ui/macos';
import auth from '../stores/auth.js';
import AIAssistant from '../components/ai/AIAssistant';
import TeethChart from '../components/dental/TeethChart';
import ToothModal from '../components/dental/ToothModal';
import TreatmentPlanner from '../components/dental/TreatmentPlanner';
import PatientCard from '../components/dental/PatientCard';
import DentalPriceManager from '../components/dental/DentalPriceManager';
import ExaminationForm from '../components/dental/ExaminationForm';
import DiagnosisForm from '../components/dental/DiagnosisForm';
import VisitProtocol from '../components/dental/VisitProtocol';
import PhotoArchive from '../components/dental/PhotoArchive';
import ProtocolTemplates from '../components/dental/ProtocolTemplates';
import ReportsAndAnalytics from '../components/dental/ReportsAndAnalytics';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import { queueService } from '../services/queue';
import EMRSystem from '../components/medical/EMRSystem';
import { 
  User, 
  Calendar, 
  Clock, 
  Stethoscope, 
  FileText, 
  Pill, 
  Activity,
  Brain, 
  Heart,
  Eye,
  Zap,
  Search,
  Filter,
  Plus,
  Edit,
  Trash2,
  CheckCircle,
  XCircle,
  AlertCircle,
  Printer,
  Download,
  Settings,
  Bell,
  LogOut,
  Stethoscope as Tooth,
  Smile,
  Shield,
  Camera,
  BarChart3,
  RefreshCw,
  TrendingUp,
  Users,
  DollarSign,
  Scissors,
  Save,
  Building
} from 'lucide-react';
import '../styles/animations.css';

/**
 * Объединенная стоматологическая панель с полным функционалом
 * Включает:
 * - Схемы зубов и планирование лечения
 * - AI помощник
 * - Управление пациентами
 * - Интеграция с очередями
 * - Современный UI
 */
const DentistPanelUnified = () => {
  // Всегда вызываем хуки первыми
  const { isMobile, isTablet, isDesktop } = useBreakpoint();
  const isTouch = useTouchDevice();
  const location = useLocation();
  const navigate = useNavigate();
  const [authState, setAuthState] = useState(auth.getState());
  
  useEffect(() => {
    const unsubscribe = auth.subscribe(setAuthState);
    return unsubscribe;
  }, []);
  
  const user = authState.profile;
  
  // Синхронизация активной вкладки с URL
  const getActiveTabFromURL = () => {
    const params = new URLSearchParams(location.search);
    return params.get('tab') || 'appointments';
  };
  
  // Состояние
  const [activeTab, setActiveTab] = useState(getActiveTabFromURL());
  
  // Синхронизация URL с активной вкладкой
  useEffect(() => {
    const urlTab = getActiveTabFromURL();
    if (urlTab !== activeTab) {
      setActiveTab(urlTab);
    }
  }, [location.search]);
  
  // Функция для изменения активной вкладки с обновлением URL
  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    navigate(`/dentist?tab=${tabId}`, { replace: true });
  };
  const [patients, setPatients] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [dentalExaminations, setDentalExaminations] = useState([]);
  const [treatmentPlans, setTreatmentPlans] = useState([]);
  const [prosthetics, setProsthetics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [scheduleNextModal, setScheduleNextModal] = useState({ open: false, patient: null });
  const [emr, setEmr] = useState(null);
  
  // Состояния для таблицы записей
  const [appointmentsTableData, setAppointmentsTableData] = useState([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [appointmentsSelected, setAppointmentsSelected] = useState(new Set());
  const [services, setServices] = useState({});
  const [showPatientModal, setShowPatientModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [showDentalChart, setShowDentalChart] = useState(false);
  const [showTreatmentPlanner, setShowTreatmentPlanner] = useState(false);
  const [showPatientCard, setShowPatientCard] = useState(false);
  const [showExaminationForm, setShowExaminationForm] = useState(false);
  const [showDiagnosisForm, setShowDiagnosisForm] = useState(false);
  const [showVisitProtocol, setShowVisitProtocol] = useState(false);
  const [showPhotoArchive, setShowPhotoArchive] = useState(false);
  const [showProtocolTemplates, setShowProtocolTemplates] = useState(false);
  const [showReports, setShowReports] = useState(false);
  const [showTreatmentForm, setShowTreatmentForm] = useState(false);
  const [showProstheticForm, setShowProstheticForm] = useState(false);
  const [dentalChartData, setDentalChartData] = useState(null);
  
  // Состояние для DentalPriceManager
  const [showPriceManager, setShowPriceManager] = useState(false);
  const [selectedServiceForPrice, setSelectedServiceForPrice] = useState(null);
  const [currentTreatmentPlan, setCurrentTreatmentPlan] = useState(null);
  const [selectedTooth, setSelectedTooth] = useState(null);
  const [toothModalOpen, setToothModalOpen] = useState(false);

  // Формы данных
  const [examinationForm, setExaminationForm] = useState({
    patient_id: '',
    examination_date: '',
    oral_hygiene: '',
    caries_status: '',
    periodontal_status: '',
    occlusion: '',
    missing_teeth: '',
    dental_plaque: '',
    gingival_bleeding: '',
    diagnosis: '',
    recommendations: ''
  });

  const [treatmentForm, setTreatmentForm] = useState({
    patient_id: '',
    treatment_date: '',
    treatment_type: '',
    teeth_involved: '',
    procedure_description: '',
    materials_used: '',
    anesthesia: '',
    complications: '',
    follow_up_date: '',
    cost: ''
  });

  const [prostheticForm, setProstheticForm] = useState({
    patient_id: '',
    prosthetic_date: '',
    prosthetic_type: '',
    teeth_replaced: '',
    material: '',
    shade: '',
    fit_quality: '',
    patient_satisfaction: '',
    warranty_period: '',
    cost: ''
  });

  // Refs
  const headerRef = React.useRef(null);
  const [headerHeight, setHeaderHeight] = useState(0);

  // Используем централизованную систему темизации
  const { 
    isDark, 
    isLight, 
    getColor, 
    getSpacing, 
    getFontSize, 
    getShadow,
    designTokens 
  } = useTheme();

  // Цвета и стили
  const primaryColor = getColor('primary', 500);
  const successColor = getColor('success', 500);
  const warningColor = getColor('warning', 500);
  const dangerColor = getColor('danger', 500);
  const accentColor = getColor('info', 500);

  // Загрузка данных
  const loadData = async () => {
    setLoading(true);
    try {
      await Promise.all([
        loadPatients(),
        loadDentalExaminations(),
        loadTreatmentPlans(),
        loadProsthetics()
      ]);
    } catch (error) {
      console.error('Ошибка загрузки данных:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    loadServices();
  }, []);

  // Загрузка услуг для правильного отображения в tooltips
  const loadServices = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return;
      const API_BASE = import.meta?.env?.VITE_API_BASE_URL || 'http://localhost:8000';
      const response = await fetch(`${API_BASE}/api/v1/registrar/services`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        const servicesData = data.services_by_group || {};
        setServices(servicesData);
        console.log('[Dentist] Услуги загружены:', Object.keys(servicesData).length, 'групп');
      }
    } catch (error) {
      console.error('[Dentist] Ошибка загрузки услуг:', error);
    }
  };

  // Функция для получения всех услуг пациента из всех записей
  const getAllPatientServices = useCallback((patientId, allAppointments) => {
    const patientServices = new Set();
    const patientServiceCodes = new Set();
    
    allAppointments.forEach(appointment => {
      if (appointment.patient_id === patientId) {
        if (appointment.services && Array.isArray(appointment.services)) {
          appointment.services.forEach(service => patientServices.add(service));
        }
        if (appointment.service_codes && Array.isArray(appointment.service_codes)) {
          appointment.service_codes.forEach(code => patientServiceCodes.add(code));
        }
      }
    });
    
    return {
      services: Array.from(patientServices),
      service_codes: Array.from(patientServiceCodes)
    };
  }, []);

  // Загрузка записей стоматолога
  const loadDentistryAppointments = async () => {
    setAppointmentsLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        console.log('Нет токена аутентификации');
        setAppointmentsLoading(false);
        return;
      }
      
      // Загружаем ВСЕ очереди для получения полной картины услуг пациентов
      const response = await fetch('http://localhost:8000/api/v1/registrar/queues/today', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        
        // Собираем ВСЕ записи из всех очередей для получения полной картины услуг
        let allAppointments = [];
        if (data && data.queues && Array.isArray(data.queues)) {
          data.queues.forEach(queue => {
            if (queue.entries) {
              queue.entries.forEach(entry => {
                allAppointments.push({
                  id: entry.id,
                  visit_id: entry.id, // Добавляем visit_id для сопоставления с БД
                  patient_id: entry.patient_id,
                  patient_fio: entry.patient_name || `${entry.patient?.first_name || ''} ${entry.patient?.last_name || ''}`.trim(),
                  patient_phone: entry.phone || '',
                  patient_birth_year: entry.patient_birth_year || '',
                  address: entry.address || '',
                  visit_type: entry.discount_mode === 'paid' ? 'Оплачено' : 'Платный',
                  discount_mode: entry.discount_mode || 'none',
                  services: entry.services || [],
                  service_codes: entry.service_codes || [],
                  payment_type: entry.payment_status || 'Не оплачено',
                  payment_status: entry.payment_status || (entry.discount_mode === 'paid' ? 'paid' : 'pending'), // ✅ ИСПРАВЛЕНО: берем из entry
                  doctor: entry.doctor_name || 'Врач',
                  specialty: queue.specialty,
                  created_at: entry.created_at,
                  appointment_date: entry.created_at ? entry.created_at.split('T')[0] : new Date().toISOString().split('T')[0],
                  appointment_time: entry.visit_time || '09:00',
                  status: entry.status || 'waiting',
                  cost: entry.cost || 0
                });
              });
            }
          });
        }

        // Фильтруем только стоматологические записи для отображения
        const appointmentsData = allAppointments.filter(apt =>
          apt.specialty === 'dental' || apt.specialty === 'dentist' || apt.specialty === 'dentistry'
        );

        // 2. Получаем актуальный payment_status из БД через all-appointments
        const API_BASE = import.meta?.env?.VITE_API_BASE_URL || 'http://localhost:8000';
        const today = new Date().toISOString().split('T')[0];
        try {
          const appointmentsResponse = await fetch(`${API_BASE}/api/v1/registrar/all-appointments?date_from=${today}&date_to=${today}&limit=500`, {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            }
          });

          if (appointmentsResponse.ok) {
            const appointmentsDBResponse = await appointmentsResponse.json();
            const appointmentsDBData = appointmentsDBResponse.data || appointmentsDBResponse || [];  // ✅ ИСПРАВЛЕНО: Извлекаем data из ответа
            console.log('[Dentist] Получены appointments из БД:', appointmentsDBData.length);

            // Создаем карту id -> payment_status
            const paymentStatusMap = new Map();
            appointmentsDBData.forEach(apt => {
              if (apt.id) {
                paymentStatusMap.set(apt.id, apt.payment_status || 'pending');
              }
              if (apt.patient_id && apt.appointment_date) {
                const key = `${apt.patient_id}_${apt.appointment_date}`;
                paymentStatusMap.set(key, apt.payment_status || 'pending');
              }
            });

            // Обновляем payment_status в наших записях
            allAppointments = allAppointments.map(apt => {
              let paymentStatus = paymentStatusMap.get(apt.id);
              if (!paymentStatus && apt.patient_id && apt.appointment_date) {
                const key = `${apt.patient_id}_${apt.appointment_date}`;
                paymentStatus = paymentStatusMap.get(key);
              }
              return {
                ...apt,
                payment_status: paymentStatus || apt.payment_status || 'pending',
                payment_type: paymentStatus || apt.payment_type
              };
            });

            console.log('[Dentist] Обновлены payment_status для', allAppointments.length, 'записей');
          }
        } catch (err) {
          console.warn('[Dentist] Не удалось загрузить payment_status из БД:', err);
        }

        // Добавляем информацию о всех услугах пациента в каждую запись
        const enrichedAppointmentsData = appointmentsData.map(apt => {
          const allPatientServices = getAllPatientServices(apt.patient_id, allAppointments);
          return {
            ...apt,
            all_patient_services: allPatientServices.services,
            all_patient_service_codes: allPatientServices.service_codes
          };
        });

        setAppointmentsTableData(enrichedAppointmentsData);
      }
    } catch (error) {
      console.error('Ошибка загрузки записей стоматолога:', error);
    } finally {
      setAppointmentsLoading(false);
    }
  };

  // Загружаем записи при переключении на вкладку
  useEffect(() => {
    if (activeTab === 'appointments') {
      loadDentistryAppointments();
    }
    
    // Слушаем глобальные события обновления очереди
    const handleQueueUpdate = (event) => {
      console.log('[Dentist] Получено событие обновления очереди:', event.detail);
      if (activeTab === 'appointments') {
        loadDentistryAppointments();
      }
    };
    window.addEventListener('queueUpdated', handleQueueUpdate);
    
    return () => {
      window.removeEventListener('queueUpdated', handleQueueUpdate);
    };
  }, [activeTab]);

  // Обработчики для таблицы записей
  const handleAppointmentRowClick = (row) => {
    console.log('Клик по записи:', row);
    // Можно открыть детали записи или переключиться на прием
    if (row.patient_fio) {
      // Создаем объект пациента для переключения на прием
      const patientData = {
        id: row.id,
        patient_name: row.patient_fio,
        phone: row.patient_phone,
        number: row.id,
        source: 'appointments'
      };
      setSelectedPatient(patientData);
      handleTabChange('examinations');
    }
  };

  const handleAppointmentActionClick = async (action, row, event) => {
    console.log('[Dentist] handleAppointmentActionClick:', action, row);
    event.stopPropagation();

    switch (action) {
      case 'view':
        handleAppointmentRowClick(row);
        break;
      case 'call':
        // Вызвать пациента
        try {
          const apiUrl = `http://localhost:8000/api/v1/registrar/queue/${row.id}/start-visit`;
          const token = localStorage.getItem('auth_token');
          const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            }
          });

          if (response.ok) {
            console.log('[Dentist] Пациент вызван:', row.patient_fio);
            await loadDentistryAppointments();
          }
        } catch (error) {
          console.error('[Dentist] Ошибка вызова пациента:', error);
        }
        break;
      case 'payment':
        console.log('[Dentist] Открытие окна оплаты для:', row.patient_fio);
        alert(`Оплата для пациента: ${row.patient_fio}\nФункция будет реализована позже`);
        break;
      case 'print':
        console.log('[Dentist] Печать талона для:', row.patient_fio);
        window.print();
        break;
      case 'complete':
        // Завершить приём
        try {
          const patient = {
            id: row.id,
            patient_name: row.patient_fio,
            phone: row.patient_phone,
            number: row.id,
            source: 'appointments',
            status: 'in_cabinet'
          };
          console.log('[Dentist] Завершение приёма для:', patient.patient_name);
          setSelectedPatient(patient);
          handleTabChange('examinations');
        } catch (error) {
          console.error('[Dentist] Ошибка при завершении приёма:', error);
        }
        break;
      case 'edit':
        // Логика редактирования записи
        break;
      case 'cancel':
        // Логика отмены записи
        break;
      default:
        break;
    }
  };

  // Проверяем демо-режим после всех хуков
  const isDemoMode = window.location.pathname.includes('/medilab-demo');
  
  // В демо-режиме не рендерим компонент
  if (isDemoMode) {
    console.log('DentistPanelUnified: Skipping render in demo mode');
    return null;
  }

  const authHeader = () => ({
    Authorization: `Bearer ${localStorage.getItem('auth_token') || ''}`,
  });

  const loadPatients = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/v1/patients?department=Dental&limit=100', { headers: authHeader() });
      if (response.ok) {
        const data = await response.json();
        setPatients(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.error('Ошибка загрузки пациентов:', e);
    }
  };

  const loadAppointments = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/v1/appointments?department=Dental&limit=100', { headers: authHeader() });
      if (response.ok) {
        const data = await response.json();
        setAppointments(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.error('Ошибка загрузки записей:', e);
    }
  };

  const loadDentalExaminations = async () => {
    try {
      // TODO: Implement dental examinations endpoint
      // const res = await fetch('http://localhost:8000/api/v1/dental/examinations?limit=100', { headers: authHeader() });
      // if (res.ok) setDentalExaminations(await res.json());
      console.log('Dental examinations endpoint not implemented yet');
    } catch {
      // Игнорируем ошибки загрузки обследований
    }
  };

  const loadTreatmentPlans = async () => {
    try {
      // TODO: Implement treatment plans endpoint
      // const res = await fetch('http://localhost:8000/api/v1/dental/treatments?limit=100', { headers: authHeader() });
      // if (res.ok) setTreatmentPlans(await res.json());
      console.log('Treatment plans endpoint not implemented yet');
    } catch {
      // Игнорируем ошибки загрузки планов лечения
    }
  };

  const loadProsthetics = async () => {
    try {
      // TODO: Implement prosthetics endpoint
      // const res = await fetch('http://localhost:8000/api/v1/dental/prosthetics?limit=100', { headers: authHeader() });
      // if (res.ok) setProsthetics(await res.json());
      console.log('Prosthetics endpoint not implemented yet');
    } catch {
      // Игнорируем ошибки загрузки протезирования
    }
  };

  // Обработчики
  const handlePatientSelect = (patient) => {
    setSelectedPatient(patient);
    // Переключаемся на вкладку визита для работы с EMR
    handleTabChange('visits');
  };

  // Сохранение EMR
  const saveEMR = async (emrData) => {
    try {
      const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
      if (!selectedPatient?.id) {
        console.warn('[Dentist] saveEMR: нет selectedPatient.id');
        return;
      }
      
      const appointmentForEMR = {
        id: selectedPatient.id,
        patient_id: selectedPatient.patient?.id || selectedPatient.patient_id || selectedPatient.id,
        patient_name: selectedPatient.patient_name || selectedPatient.name
      };
      
      const response = await fetch(`/api/v1/appointments/${appointmentForEMR.id}/emr`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(emrData)
      });

      if (response.ok) {
        const savedEMR = await response.json();
        setEmr(savedEMR);
        console.log('[Dentist] saveEMR: успешно', savedEMR);
      } else {
        const error = await response.json();
        console.error('[Dentist] saveEMR: ошибка', error);
        throw new Error(error.detail || 'Ошибка при сохранении EMR');
      }
    } catch (error) {
      console.error('DentistPanel: Save EMR error:', error);
      throw error;
    }
  };

  // Завершение визита
  const handleCompleteVisit = async () => {
    if (!selectedPatient) return;
    
    try {
      const visitPayload = {
        patient_id: selectedPatient.patient?.id || selectedPatient.patient_id || selectedPatient.id,
        notes: 'Стоматологический прием завершен'
      };
      
      await queueService.completeVisit(selectedPatient.id, visitPayload);
      
      // Автоматически вызвать следующего пациента
      try {
        await queueService.callNextWaiting('dentist');
      } catch (err) {
        console.warn('[Dentist] callNextWaiting failed:', err);
      }
      
      setSelectedPatient(null);
      setEmr(null);
      handleTabChange('queue');
    } catch (error) {
      console.error('[Dentist] handleCompleteVisit: error', error);
    }
  };

  const handleExamination = (patient) => {
    setSelectedPatient(patient);
    setExaminationForm({ ...examinationForm, patient_id: patient.id });
    setShowExaminationForm(true);
  };

  const handleTreatment = (patient) => {
    setSelectedPatient(patient);
    setTreatmentForm({ ...treatmentForm, patient_id: patient.id });
    setShowTreatmentForm(true);
  };

  const handleProsthetic = (patient) => {
    setSelectedPatient(patient);
    setProstheticForm({ ...prostheticForm, patient_id: patient.id });
    setShowProstheticForm(true);
  };

  const handleDiagnosis = (patient) => {
    setSelectedPatient(patient);
    setShowDiagnosisForm(true);
  };

  const handleVisitProtocol = (patient) => {
    setSelectedPatient(patient);
    setShowVisitProtocol(true);
  };

  const handlePhotoArchive = (patient) => {
    setSelectedPatient(patient);
    setShowPhotoArchive(true);
  };

  const handleProtocolTemplates = () => {
    setShowProtocolTemplates(true);
  };

  const handleReports = () => {
    setShowReports(true);
  };

  const handleDentalChart = (patient) => {
    setSelectedPatient(patient);
    setDentalChartData(patient.dentalChart || null);
    setShowDentalChart(true);
  };

  const handleTreatmentPlanner = (patient) => {
    setSelectedPatient(patient);
    setCurrentTreatmentPlan(patient.treatmentPlan || null);
    setShowTreatmentPlanner(true);
  };

  const handleSaveDentalChart = (chartData) => {
    // Сохранение схемы зубов
    console.log('Сохранение схемы зубов:', chartData);
    // Здесь будет API вызов для сохранения
  };

  const handleSaveTreatmentPlan = (planData) => {
    // Сохранение плана лечения
    console.log('Сохранение плана лечения:', planData);
    // Здесь будет API вызов для сохранения
  };

  const handleSendToPatient = (planData) => {
    // Отправка плана пациенту
    console.log('Отправка плана пациенту:', planData);
    // Здесь будет API вызов для отправки
  };

  // Обработчики отправки форм
  const handleExaminationSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/v1/dental/examinations', {
        method: 'POST', 
        headers: { 'Content-Type': 'application/json', ...authHeader() }, 
        body: JSON.stringify(examinationForm)
      });
      if (res.ok) {
        setShowExaminationForm(false);
        setExaminationForm({ 
          patient_id: '', examination_date: '', oral_hygiene: '', caries_status: '', 
          periodontal_status: '', occlusion: '', missing_teeth: '', dental_plaque: '', 
          gingival_bleeding: '', diagnosis: '', recommendations: '' 
        });
        loadDentalExaminations();
      }
    } catch (e) { 
      console.error('Ошибка сохранения осмотра:', e); 
    }
  };

  const handleTreatmentSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/v1/dental/treatments', {
        method: 'POST', 
        headers: { 'Content-Type': 'application/json', ...authHeader() }, 
        body: JSON.stringify(treatmentForm)
      });
      if (res.ok) {
        setShowTreatmentForm(false);
        setTreatmentForm({ 
          patient_id: '', treatment_date: '', treatment_type: '', teeth_involved: '', 
          procedure_description: '', materials_used: '', anesthesia: '', complications: '', 
          follow_up_date: '', cost: '' 
        });
        loadTreatmentPlans();
      }
    } catch (e) { 
      console.error('Ошибка сохранения лечения:', e); 
    }
  };

  const handleProstheticSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/v1/dental/prosthetics', {
        method: 'POST', 
        headers: { 'Content-Type': 'application/json', ...authHeader() }, 
        body: JSON.stringify(prostheticForm)
      });
      if (res.ok) {
        setShowProstheticForm(false);
        setProstheticForm({ 
          patient_id: '', prosthetic_date: '', prosthetic_type: '', teeth_replaced: '', 
          material: '', shade: '', fit_quality: '', patient_satisfaction: '', 
          warranty_period: '', cost: '' 
        });
        loadProsthetics();
      }
    } catch (e) { 
      console.error('Ошибка сохранения протеза:', e); 
    }
  };

  // Фильтрация пациентов
  const filteredPatients = patients.filter(patient => {
    const matchesSearch = !searchQuery || 
      patient.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      patient.phone?.includes(searchQuery);
    
    const matchesStatus = filterStatus === 'all' || patient.status === filterStatus;
    
    return matchesSearch && matchesStatus;
  });

  // Статистика
  const stats = {
    totalPatients: patients.length,
    todayAppointments: appointments.filter(apt => 
      new Date(apt.date).toDateString() === new Date().toDateString()
    ).length,
    activeTreatmentPlans: treatmentPlans.filter(plan => plan.status === 'active').length,
    completedProsthetics: prosthetics.filter(prosthetic => prosthetic.status === 'completed').length
  };

  // Вкладки
  const tabs = [
    { id: 'dashboard', label: 'Дашборд', icon: BarChart3 },
    { id: 'patients', label: 'Пациенты', icon: Users },
    { id: 'appointments', label: 'Записи', icon: Calendar },
    { id: 'examinations', label: 'Осмотры', icon: Eye },
    { id: 'diagnoses', label: 'Диагнозы', icon: Stethoscope },
    { id: 'visits', label: 'Протоколы', icon: FileText },
    { id: 'photos', label: 'Архив', icon: Camera },
    { id: 'templates', label: 'Шаблоны', icon: FileText },
    { id: 'reports', label: 'Отчеты', icon: BarChart3 },
    { id: 'dental-chart', label: 'Схемы зубов', icon: Tooth },
    { id: 'treatment-plans', label: 'Планы лечения', icon: FileText },
    { id: 'prosthetics', label: 'Протезирование', icon: Smile },
    { id: 'ai-assistant', label: 'AI Помощник', icon: Brain }
  ];

  // Рендер дашборда
  const renderDashboard = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      {/* Статистические карточки */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
        gap: '24px'
      }}>
        <div style={{
          background: 'var(--mac-bg-primary)',
          borderRadius: 'var(--mac-radius-xl)',
          padding: '24px',
          boxShadow: 'var(--mac-shadow-sm)',
          border: '1px solid var(--mac-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)',
          cursor: 'pointer'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.boxShadow = 'var(--mac-shadow-md)';
          e.currentTarget.style.transform = 'translateY(-2px)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
          e.currentTarget.style.transform = 'translateY(0)';
        }}>
          <div>
            <p style={{ 
              fontSize: 'var(--mac-font-size-xs)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-secondary)',
              marginBottom: '4px' 
            }}>Всего пациентов</p>
            <p style={{ 
              fontSize: 'var(--mac-font-size-3xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-text-primary)' 
            }}>{stats.totalPatients}</p>
            <p style={{ 
              fontSize: 'var(--mac-font-size-xs)', 
              color: 'var(--mac-success)',
              marginTop: '4px' 
            }}>+12% за месяц</p>
          </div>
          <div style={{
            width: '56px',
            height: '56px',
            background: 'var(--mac-accent-blue)',
            borderRadius: 'var(--mac-radius-xl)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: 'var(--mac-shadow-lg)'
          }}>
            <Users style={{ height: '28px', width: '28px', color: 'white' }} />
          </div>
        </div>

        <div style={{
          background: 'var(--mac-bg-primary)',
          borderRadius: 'var(--mac-radius-xl)',
          padding: '24px',
          boxShadow: 'var(--mac-shadow-sm)',
          border: '1px solid var(--mac-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)',
          cursor: 'pointer'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.boxShadow = 'var(--mac-shadow-md)';
          e.currentTarget.style.transform = 'translateY(-2px)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
          e.currentTarget.style.transform = 'translateY(0)';
        }}>
          <div>
            <p style={{ 
              fontSize: 'var(--mac-font-size-xs)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-secondary)',
              marginBottom: '4px' 
            }}>Записей сегодня</p>
            <p style={{ 
              fontSize: 'var(--mac-font-size-3xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-text-primary)' 
            }}>{stats.todayAppointments}</p>
            <p style={{ 
              fontSize: 'var(--mac-font-size-xs)', 
              color: 'var(--mac-accent-blue)',
              marginTop: '4px' 
            }}>8 из 12 слотов</p>
          </div>
          <div style={{
            width: '56px',
            height: '56px',
            background: 'var(--mac-success)',
            borderRadius: 'var(--mac-radius-xl)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: 'var(--mac-shadow-lg)'
          }}>
            <Calendar style={{ height: '28px', width: '28px', color: 'white' }} />
          </div>
        </div>

        <div style={{
          background: 'var(--mac-bg-primary)',
          borderRadius: 'var(--mac-radius-xl)',
          padding: '24px',
          boxShadow: 'var(--mac-shadow-sm)',
          border: '1px solid var(--mac-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)',
          cursor: 'pointer'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.boxShadow = 'var(--mac-shadow-md)';
          e.currentTarget.style.transform = 'translateY(-2px)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
          e.currentTarget.style.transform = 'translateY(0)';
        }}>
          <div>
            <p style={{ 
              fontSize: 'var(--mac-font-size-xs)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-secondary)',
              marginBottom: '4px' 
            }}>Активные планы</p>
            <p style={{ 
              fontSize: 'var(--mac-font-size-3xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-text-primary)' 
            }}>{stats.activeTreatmentPlans}</p>
            <p style={{ 
              fontSize: 'var(--mac-font-size-xs)', 
              color: 'var(--mac-accent-purple)',
              marginTop: '4px' 
            }}>+8% к прошлому месяцу</p>
          </div>
          <div style={{
            width: '56px',
            height: '56px',
            background: 'var(--mac-accent-purple)',
            borderRadius: 'var(--mac-radius-xl)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: 'var(--mac-shadow-lg)'
          }}>
            <FileText style={{ height: '28px', width: '28px', color: 'white' }} />
          </div>
        </div>

        <div style={{
          background: 'var(--mac-bg-primary)',
          borderRadius: 'var(--mac-radius-xl)',
          padding: '24px',
          boxShadow: 'var(--mac-shadow-sm)',
          border: '1px solid var(--mac-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          transition: 'all var(--mac-duration-normal) var(--mac-ease)',
          cursor: 'pointer'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.boxShadow = 'var(--mac-shadow-md)';
          e.currentTarget.style.transform = 'translateY(-2px)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
          e.currentTarget.style.transform = 'translateY(0)';
        }}>
          <div>
            <p style={{ 
              fontSize: 'var(--mac-font-size-xs)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-secondary)',
              marginBottom: '4px' 
            }}>Протезы</p>
            <p style={{ 
              fontSize: 'var(--mac-font-size-3xl)', 
              fontWeight: 'var(--mac-font-weight-bold)', 
              color: 'var(--mac-text-primary)' 
            }}>{stats.completedProsthetics}</p>
            <p style={{ 
              fontSize: 'var(--mac-font-size-xs)', 
              color: 'var(--mac-warning)',
              marginTop: '4px' 
            }}>+15% к прошлому месяцу</p>
          </div>
          <div style={{
            width: '56px',
            height: '56px',
            background: 'var(--mac-warning)',
            borderRadius: 'var(--mac-radius-xl)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: 'var(--mac-shadow-lg)'
          }}>
            <Smile style={{ height: '28px', width: '28px', color: 'white' }} />
          </div>
        </div>
      </div>

      {/* Быстрые действия */}
      <div style={{
        background: 'var(--mac-bg-primary)',
        borderRadius: 'var(--mac-radius-xl)',
        padding: '24px',
        boxShadow: 'var(--mac-shadow-sm)',
        border: '1px solid var(--mac-border)'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '24px'
        }}>
          <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)'
          }}>Быстрые действия</h3>
          <Button
            variant="text"
            size="sm"
            onClick={() => {}}
            style={{
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-accent-blue)'
            }}
          >
            Показать все
          </Button>
        </div>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '24px'
        }}>
          <Button
            onClick={() => handleTabChange('patients')}
            variant="primary"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '16px 24px',
              borderRadius: 'var(--mac-radius-lg)',
              boxShadow: 'var(--mac-shadow-sm)',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)',
              background: 'var(--mac-accent-blue)',
              color: 'white',
              fontWeight: 'var(--mac-font-weight-medium)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow = 'var(--mac-shadow-md)';
              e.currentTarget.style.transform = 'translateY(-2px)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            <Plus style={{ height: '20px', width: '20px' }} />
            <span style={{ fontWeight: 'var(--mac-font-weight-medium)' }}>Новый пациент</span>
          </Button>
          <Button
            onClick={() => handleTabChange('appointments')}
            variant="outline"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '16px 24px',
              borderRadius: 'var(--mac-radius-lg)',
              boxShadow: 'var(--mac-shadow-sm)',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)',
              border: '1px solid var(--mac-border)',
              fontWeight: 'var(--mac-font-weight-medium)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow = 'var(--mac-shadow-md)';
              e.currentTarget.style.transform = 'translateY(-2px)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            <Calendar style={{ height: '20px', width: '20px' }} />
            <span style={{ fontWeight: 'var(--mac-font-weight-medium)' }}>Записать на прием</span>
          </Button>
          <Button
            onClick={() => handleTabChange('dental-chart')}
            variant="outline"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              padding: '16px 24px',
              borderRadius: 'var(--mac-radius-lg)',
              boxShadow: 'var(--mac-shadow-sm)',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)',
              border: '1px solid var(--mac-border)',
              fontWeight: 'var(--mac-font-weight-medium)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow = 'var(--mac-shadow-md)';
              e.currentTarget.style.transform = 'translateY(-2px)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            <Tooth style={{ height: '20px', width: '20px' }} />
            <span style={{ fontWeight: 'var(--mac-font-weight-medium)' }}>Схема зубов</span>
          </Button>
        </div>
      </div>

      {/* Последние записи */}
      <div style={{
        background: 'var(--mac-bg-primary)',
        borderRadius: 'var(--mac-radius-xl)',
        padding: '24px',
        boxShadow: 'var(--mac-shadow-sm)',
        border: '1px solid var(--mac-border)'
      }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '24px'
        }}>
          <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)'
          }}>Последние записи</h3>
          <Button
            variant="text"
            size="sm"
            onClick={() => {}}
            style={{
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-accent-blue)'
            }}
          >
            Показать все
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {appointments.slice(0, 5).map(appointment => (
            <div 
              key={appointment.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '24px',
                background: 'var(--mac-bg-secondary)',
                borderRadius: 'var(--mac-radius-lg)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                cursor: 'pointer'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--mac-bg-hover)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'var(--mac-bg-secondary)';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{
                  width: '40px',
                  height: '40px',
                  background: 'var(--mac-accent-blue)',
                  borderRadius: 'var(--mac-radius-lg)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: 'var(--mac-shadow-sm)'
                }}>
                  <span style={{
                    color: 'white',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-bold)'
                  }}>
                    {appointment.patientName?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p style={{
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-base)'
                  }}>{appointment.patientName}</p>
                  <p style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)'
                  }}>{appointment.date} {appointment.time}</p>
                </div>
              </div>
              <div style={{
                padding: '4px 12px',
                borderRadius: 'var(--mac-radius-full)',
                fontSize: 'var(--mac-font-size-xs)',
                fontWeight: 'var(--mac-font-weight-medium)',
                background: appointment.status === 'confirmed' ? 'var(--mac-success-bg)' : 'var(--mac-warning-bg)',
                color: appointment.status === 'confirmed' ? 'var(--mac-success)' : 'var(--mac-warning)'
              }}>
                {appointment.status}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // Рендер пациентов
  const renderPatients = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Поиск и фильтры */}
      <Card padding="lg">
        <div style={{ display: 'flex', flexDirection: 'row', gap: '16px', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '200px' }}>
            <div style={{ position: 'relative' }}>
              <Search style={{
                position: 'absolute',
                left: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                height: '16px',
                width: '16px',
                color: 'var(--mac-text-tertiary)'
              }} />
              <input
                type="text"
                placeholder="Поиск пациентов..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: '100%',
                  paddingLeft: '40px',
                  paddingRight: '16px',
                  paddingTop: '8px',
                  paddingBottom: '8px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-lg)',
                  fontSize: 'var(--mac-font-size-base)',
                  fontFamily: 'inherit',
                  backgroundColor: 'var(--mac-bg-primary)',
                  color: 'var(--mac-text-primary)',
                  transition: 'all var(--mac-duration-fast) var(--mac-ease)'
                }}
                onFocus={(e) => {
                  e.target.style.outline = 'var(--mac-focus-ring)';
                  e.target.style.outlineOffset = '2px';
                  e.target.style.borderColor = 'var(--mac-accent-blue)';
                }}
                onBlur={(e) => {
                  e.target.style.outline = 'none';
                  e.target.style.borderColor = 'var(--mac-border)';
                }}
              />
            </div>
          </div>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            style={{
              padding: '8px 16px',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-lg)',
              fontSize: 'var(--mac-font-size-base)',
              fontFamily: 'inherit',
              backgroundColor: 'var(--mac-bg-primary)',
              color: 'var(--mac-text-primary)',
              cursor: 'pointer',
              transition: 'all var(--mac-duration-fast) var(--mac-ease)'
            }}
            onFocus={(e) => {
              e.target.style.outline = 'var(--mac-focus-ring)';
              e.target.style.outlineOffset = '2px';
              e.target.style.borderColor = 'var(--mac-accent-blue)';
            }}
            onBlur={(e) => {
              e.target.style.outline = 'none';
              e.target.style.borderColor = 'var(--mac-border)';
            }}
          >
            <option value="all">Все статусы</option>
            <option value="active">Активные</option>
            <option value="inactive">Неактивные</option>
          </select>
        </div>
      </Card>

      {/* Список пациентов */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
        gap: '24px'
      }}>
        {filteredPatients.map(patient => (
          <Card 
            key={patient.id} 
            padding="lg"
            style={{
              transition: 'all var(--mac-duration-normal) var(--mac-ease)',
              cursor: 'pointer'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow = 'var(--mac-shadow-lg)';
              e.currentTarget.style.transform = 'translateY(-2px)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow = 'var(--mac-shadow-sm)';
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '48px',
                  height: '48px',
                  background: 'var(--mac-accent-blue)',
                  borderRadius: 'var(--mac-radius-full)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <span style={{
                    color: 'white',
                    fontSize: 'var(--mac-font-size-lg)',
                    fontWeight: 'var(--mac-font-weight-medium)'
                  }}>
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <h3 style={{
                    fontWeight: 'var(--mac-font-weight-semibold)',
                    fontSize: 'var(--mac-font-size-lg)',
                    color: 'var(--mac-text-primary)',
                    marginBottom: '4px'
                  }}>{patient.name}</h3>
                  <p style={{
                    color: 'var(--mac-text-secondary)',
                    fontSize: 'var(--mac-font-size-sm)'
                  }}>{patient.phone}</p>
                </div>
              </div>
              <Badge variant={patient.status === 'active' ? 'success' : 'warning'}>
                {patient.status}
              </Badge>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '16px' }}>
              <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>
                <strong style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>Возраст:</strong> {patient.age} лет
              </p>
              <p style={{
                fontSize: 'var(--mac-font-size-sm)',
                color: 'var(--mac-text-secondary)'
              }}>
                <strong style={{ fontWeight: 'var(--mac-font-weight-semibold)' }}>Последний визит:</strong> {patient.lastVisit || 'Не было'}
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
              <Button
                size="sm"
                onClick={() => handlePatientSelect(patient)}
                style={{ gridColumn: 'span 2', marginBottom: '8px' }}
              >
                <Edit style={{ height: '16px', width: '16px', marginRight: '4px' }} />
                Карточка пациента
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleExamination(patient)}
                title="Осмотр"
                style={{ padding: '8px' }}
              >
                <Eye style={{ height: '16px', width: '16px' }} />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleDiagnosis(patient)}
                title="Диагнозы"
                style={{ padding: '8px' }}
              >
                <Stethoscope style={{ height: '16px', width: '16px' }} />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleVisitProtocol(patient)}
                title="Протокол визита"
                style={{ padding: '8px' }}
              >
                <FileText style={{ height: '16px', width: '16px' }} />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleDentalChart(patient)}
                title="Схема зубов"
                style={{ padding: '8px' }}
              >
                <Tooth style={{ height: '16px', width: '16px' }} />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleTreatment(patient)}
                title="Лечение"
                style={{ padding: '8px' }}
              >
                <Scissors style={{ height: '16px', width: '16px' }} />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleProsthetic(patient)}
                title="Протезирование"
                style={{ padding: '8px' }}
              >
                <Smile style={{ height: '16px', width: '16px' }} />
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );

  // Рендер записей
  const renderAppointments = () => (
    <div style={{ 
      width: '100%', 
      maxWidth: 'none',
      display: 'flex',
      flexDirection: 'column',
      gap: '24px'
    }}>
      <Card padding="lg" style={{
        width: '100%',
        maxWidth: '100%',
        minWidth: 0,
        boxSizing: 'border-box',
        overflow: 'hidden'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '16px'
        }}>
          <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-medium)',
            display: 'flex',
            alignItems: 'center',
            color: 'var(--mac-text-primary)'
          }}>
            <Calendar size={20} style={{ marginRight: '8px', color: 'var(--mac-success)' }} />
            Записи к стоматологу
          </h3>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Badge variant="info">Всего: {appointmentsTableData.length}</Badge>
            <Badge variant="warning">
              Ожидают: {appointmentsTableData.filter(a => a.status === 'waiting' || a.status === 'confirmed' || a.status === 'pending').length}
            </Badge>
            <Badge variant="primary">
              Вызваны: {appointmentsTableData.filter(a => a.status === 'called' || a.status === 'in_progress').length}
            </Badge>
            <Badge variant="success">
              Приняты: {appointmentsTableData.filter(a => a.status === 'completed' || a.status === 'done').length}
            </Badge>
            <Button
              variant="secondary"
              size="sm"
              onClick={loadDentistryAppointments}
              disabled={appointmentsLoading}
            >
              <RefreshCw size={16} style={{ marginRight: '4px' }} />
              Обновить
            </Button>
          </div>
        </div>
        
        <EnhancedAppointmentsTable
          data={appointmentsTableData}
          loading={appointmentsLoading}
          theme="light"
          language="ru"
          view="doctor"
          selectedRows={new Set()}
          outerBorder={false}
          services={services}
          showCheckboxes={false}
          onRowSelect={() => {}}
          onRowClick={handleAppointmentRowClick}
          onActionClick={handleAppointmentActionClick}
        />
      </Card>
    </div>
  );

  // Рендер осмотров
  const renderExaminations = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          marginBottom: '16px',
          color: 'var(--mac-text-primary)'
        }}>Объективные осмотры</h3>
        <p style={{
          color: 'var(--mac-text-secondary)',
          marginBottom: '16px',
          fontSize: 'var(--mac-font-size-base)'
        }}>
          Выберите пациента для проведения или просмотра объективного осмотра
        </p>
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
          gap: '16px'
        }}>
          {patients.map(patient => (
            <div
              key={patient.id}
              style={{
                padding: '24px',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-lg)',
                cursor: 'pointer',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
              onClick={() => handleExamination(patient)}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  background: 'var(--mac-success)',
                  borderRadius: 'var(--mac-radius-full)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <span style={{
                    color: 'white',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)'
                  }}>
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p style={{
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-base)'
                  }}>{patient.name}</p>
                  <p style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)'
                  }}>Провести осмотр</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );

  // Рендер диагнозов
  const renderDiagnoses = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          marginBottom: '16px',
          color: 'var(--mac-text-primary)'
        }}>Диагнозы и назначения</h3>
        <p style={{
          color: 'var(--mac-text-secondary)',
          marginBottom: '16px',
          fontSize: 'var(--mac-font-size-base)'
        }}>
          Выберите пациента для постановки диагнозов и назначений
        </p>
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
          gap: '16px'
        }}>
          {patients.map(patient => (
            <div
              key={patient.id}
              style={{
                padding: '24px',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-lg)',
                cursor: 'pointer',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
              onClick={() => handleDiagnosis(patient)}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  background: 'var(--mac-accent-blue)',
                  borderRadius: 'var(--mac-radius-full)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <span style={{
                    color: 'white',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)'
                  }}>
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p style={{
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-base)'
                  }}>{patient.name}</p>
                  <p style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)'
                  }}>Поставить диагноз</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );

  // Рендер протоколов визитов
  const renderVisits = () => {
    // Если выбран пациент из очереди - показываем EMR
    if (selectedPatient) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <Card padding="lg">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <h3 style={{
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <Stethoscope size={20} />
                Прием пациента: {selectedPatient.patient_name || selectedPatient.name || `№${selectedPatient.number}`}
              </h3>
              <Button
                variant="outline"
                onClick={() => {
                  setSelectedPatient(null);
                  handleTabChange('queue');
                }}
              >
                Вернуться в очередь
              </Button>
            </div>
            
            {/* EMR System */}
            <EMRSystem
              appointment={{
                id: selectedPatient.id,
                patient_id: selectedPatient.patient?.id || selectedPatient.patient_id || selectedPatient.id,
                patient_name: selectedPatient.patient_name || selectedPatient.name,
                specialty: 'dentist',
                status: selectedPatient.status || 'in_visit'
              }}
              emr={emr}
              onSave={saveEMR}
              onComplete={handleCompleteVisit}
            />
          </Card>
        </div>
      );
    }
    
    // Иначе показываем список пациентов для выбора протокола
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <Card padding="lg">
          <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            marginBottom: '16px',
            color: 'var(--mac-text-primary)'
          }}>Протоколы визитов</h3>
          <p style={{
            color: 'var(--mac-text-secondary)',
            marginBottom: '16px',
            fontSize: 'var(--mac-font-size-base)'
          }}>
            Выберите пациента из очереди или выберите из списка для создания протокола визита
          </p>
          
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
            gap: '16px'
          }}>
            {patients.map(patient => (
              <div
                key={patient.id}
                style={{
                  padding: '24px',
                  border: '1px solid var(--mac-border)',
                  borderRadius: 'var(--mac-radius-lg)',
                  cursor: 'pointer',
                  transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                }}
                onClick={() => handleVisitProtocol(patient)}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'var(--mac-bg-secondary)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{
                    width: '32px',
                    height: '32px',
                    background: 'var(--mac-accent-purple)',
                    borderRadius: 'var(--mac-radius-full)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}>
                    <span style={{
                      color: 'white',
                      fontSize: 'var(--mac-font-size-sm)',
                      fontWeight: 'var(--mac-font-weight-medium)'
                    }}>
                      {patient.name?.charAt(0)}
                    </span>
                  </div>
                  <div>
                    <p style={{
                      fontWeight: 'var(--mac-font-weight-medium)',
                      color: 'var(--mac-text-primary)',
                      fontSize: 'var(--mac-font-size-base)'
                    }}>{patient.name}</p>
                    <p style={{
                      fontSize: 'var(--mac-font-size-sm)',
                      color: 'var(--mac-text-secondary)'
                    }}>Создать протокол</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    );
  };

  // Рендер фото архива
  const renderPhotos = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          marginBottom: '16px',
          color: 'var(--mac-text-primary)'
        }}>Фото и рентген архив</h3>
        <p style={{
          color: 'var(--mac-text-secondary)',
          marginBottom: '16px',
          fontSize: 'var(--mac-font-size-base)'
        }}>
          Выберите пациента для просмотра и управления фото и рентгеновскими снимками
        </p>
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
          gap: '16px'
        }}>
          {patients.map(patient => (
            <div
              key={patient.id}
              style={{
                padding: '24px',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-lg)',
                cursor: 'pointer',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
              onClick={() => handlePhotoArchive(patient)}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  background: 'var(--mac-warning)',
                  borderRadius: 'var(--mac-radius-full)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <span style={{
                    color: 'white',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)'
                  }}>
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p style={{
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-base)'
                  }}>{patient.name}</p>
                  <p style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)'
                  }}>Открыть архив</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );

  // Рендер шаблонов
  const renderTemplates = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '16px'
        }}>
          <div>
            <h3 style={{
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              marginBottom: '4px'
            }}>Шаблоны протоколов</h3>
            <p style={{
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-sm)'
            }}>
              Стандартные протоколы для быстрого создания протоколов визитов
            </p>
          </div>
          <Button
            onClick={handleProtocolTemplates}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <FileText style={{ height: '16px', width: '16px' }} />
            Управление шаблонами
          </Button>
        </div>
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: '16px'
        }}>
          <div
            style={{
              padding: '16px',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-lg)',
              cursor: 'pointer',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--mac-bg-secondary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              marginBottom: '12px'
            }}>
              <div style={{
                width: '40px',
                height: '40px',
                background: 'var(--mac-accent-blue-bg)',
                borderRadius: 'var(--mac-radius-lg)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Scissors style={{ height: '20px', width: '20px', color: 'var(--mac-accent-blue)' }} />
              </div>
              <div>
                <h4 style={{
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)'
                }}>Лечение кариеса</h4>
                <p style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>60 мин</p>
              </div>
            </div>
            <p style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)',
              marginBottom: '12px'
            }}>
              Стандартный протокол лечения кариеса с анестезией и пломбированием
            </p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <Button size="sm" style={{ flex: 1 }}>
                Использовать
              </Button>
              <Button size="sm" variant="outline">
                <Edit style={{ height: '16px', width: '16px' }} />
              </Button>
            </div>
          </div>
          
          <div
            style={{
              padding: '16px',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-lg)',
              cursor: 'pointer',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--mac-bg-secondary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              marginBottom: '12px'
            }}>
              <div style={{
                width: '40px',
                height: '40px',
                background: 'var(--mac-danger-bg)',
                borderRadius: 'var(--mac-radius-lg)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Scissors style={{ height: '20px', width: '20px', color: 'var(--mac-danger)' }} />
              </div>
              <div>
                <h4 style={{
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)'
                }}>Эндодонтическое лечение</h4>
                <p style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>120 мин</p>
              </div>
            </div>
            <p style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)',
              marginBottom: '12px'
            }}>
              Протокол лечения корневых каналов с инструментальной обработкой
            </p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <Button size="sm" style={{ flex: 1 }}>
                Использовать
              </Button>
              <Button size="sm" variant="outline">
                <Edit style={{ height: '16px', width: '16px' }} />
              </Button>
            </div>
          </div>
          
          <div
            style={{
              padding: '16px',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-lg)',
              cursor: 'pointer',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--mac-bg-secondary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              marginBottom: '12px'
            }}>
              <div style={{
                width: '40px',
                height: '40px',
                background: 'var(--mac-success-bg)',
                borderRadius: 'var(--mac-radius-lg)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Scissors style={{ height: '20px', width: '20px', color: 'var(--mac-success)' }} />
              </div>
              <div>
                <h4 style={{
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)'
                }}>Профессиональная гигиена</h4>
                <p style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>75 мин</p>
              </div>
            </div>
            <p style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)',
              marginBottom: '12px'
            }}>
              Протокол профессиональной гигиены полости рта
            </p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <Button size="sm" style={{ flex: 1 }}>
                Использовать
              </Button>
              <Button size="sm" variant="outline">
                <Edit style={{ height: '16px', width: '16px' }} />
              </Button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );

  // Рендер отчетов
  const renderReports = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '16px'
        }}>
          <div>
            <h3 style={{
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-semibold)',
              color: 'var(--mac-text-primary)',
              marginBottom: '4px'
            }}>Отчеты и аналитика</h3>
            <p style={{
              color: 'var(--mac-text-secondary)',
              fontSize: 'var(--mac-font-size-sm)'
            }}>
              Статистика по пациентам, врачам, процедурам и клинике
            </p>
          </div>
          <Button
            onClick={handleReports}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <BarChart3 style={{ height: '16px', width: '16px' }} />
            Открыть отчеты
          </Button>
        </div>
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
          gap: '16px'
        }}>
          <div
            style={{
              padding: '16px',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-lg)',
              cursor: 'pointer',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)'
            }}
            onClick={handleReports}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--mac-bg-secondary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              marginBottom: '12px'
            }}>
              <div style={{
                width: '40px',
                height: '40px',
                background: 'var(--mac-accent-blue-bg)',
                borderRadius: 'var(--mac-radius-lg)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <BarChart3 style={{ height: '20px', width: '20px', color: 'var(--mac-accent-blue)' }} />
              </div>
              <div>
                <h4 style={{
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)'
                }}>Общий обзор</h4>
                <p style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>Основные показатели</p>
              </div>
            </div>
            <p style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              Общая статистика по всем направлениям деятельности
            </p>
          </div>
          
          <div
            style={{
              padding: '16px',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-lg)',
              cursor: 'pointer',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)'
            }}
            onClick={handleReports}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--mac-bg-secondary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              marginBottom: '12px'
            }}>
              <div style={{
                width: '40px',
                height: '40px',
                background: 'var(--mac-success-bg)',
                borderRadius: 'var(--mac-radius-lg)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Users style={{ height: '20px', width: '20px', color: 'var(--mac-success)' }} />
              </div>
              <div>
                <h4 style={{
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)'
                }}>По пациентам</h4>
                <p style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>Демография и активность</p>
              </div>
            </div>
            <p style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              Анализ пациентской базы и их активности
            </p>
          </div>
          
          <div
            style={{
              padding: '16px',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-lg)',
              cursor: 'pointer',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)'
            }}
            onClick={handleReports}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--mac-bg-secondary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              marginBottom: '12px'
            }}>
              <div style={{
                width: '40px',
                height: '40px',
                background: 'var(--mac-accent-purple-bg)',
                borderRadius: 'var(--mac-radius-lg)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Stethoscope style={{ height: '20px', width: '20px', color: 'var(--mac-accent-purple)' }} />
              </div>
              <div>
                <h4 style={{
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)'
                }}>По врачам</h4>
                <p style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>Производительность</p>
              </div>
            </div>
            <p style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              Статистика работы врачей и их специализаций
            </p>
          </div>
          
          <div
            style={{
              padding: '16px',
              border: '1px solid var(--mac-border)',
              borderRadius: 'var(--mac-radius-lg)',
              cursor: 'pointer',
              transition: 'all var(--mac-duration-normal) var(--mac-ease)'
            }}
            onClick={handleReports}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--mac-bg-secondary)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
            }}
          >
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              marginBottom: '12px'
            }}>
              <div style={{
                width: '40px',
                height: '40px',
                background: 'var(--mac-warning-bg)',
                borderRadius: 'var(--mac-radius-lg)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Building style={{ height: '20px', width: '20px', color: 'var(--mac-warning)' }} />
              </div>
              <div>
                <h4 style={{
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: 'var(--mac-text-primary)',
                  fontSize: 'var(--mac-font-size-base)'
                }}>По клинике</h4>
                <p style={{
                  fontSize: 'var(--mac-font-size-sm)',
                  color: 'var(--mac-text-secondary)'
                }}>Оборудование и загруженность</p>
              </div>
            </div>
            <p style={{
              fontSize: 'var(--mac-font-size-sm)',
              color: 'var(--mac-text-primary)'
            }}>
              Анализ работы клиники и состояния оборудования
            </p>
          </div>
        </div>
      </Card>
    </div>
  );

  // Рендер схем зубов
  const renderDentalChart = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          marginBottom: '16px',
          color: 'var(--mac-text-primary)'
        }}>Схемы зубов</h3>
        <p style={{
          color: 'var(--mac-text-secondary)',
          marginBottom: '16px',
          fontSize: 'var(--mac-font-size-base)'
        }}>
          Выберите пациента для просмотра и редактирования схемы зубов
        </p>
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
          gap: '16px'
        }}>
          {patients.map(patient => (
            <div
              key={patient.id}
              style={{
                padding: '24px',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-lg)',
                cursor: 'pointer',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
              onClick={() => handleDentalChart(patient)}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  background: 'var(--mac-accent-blue)',
                  borderRadius: 'var(--mac-radius-full)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <span style={{
                    color: 'white',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)'
                  }}>
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p style={{
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-base)'
                  }}>{patient.name}</p>
                  <p style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)'
                  }}>Открыть схему</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );

  // Рендер планов лечения
  const renderTreatmentPlans = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          marginBottom: '16px',
          color: 'var(--mac-text-primary)'
        }}>Планы лечения</h3>
        <p style={{
          color: 'var(--mac-text-secondary)',
          marginBottom: '16px',
          fontSize: 'var(--mac-font-size-base)'
        }}>
          Выберите пациента для создания или редактирования плана лечения
        </p>
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
          gap: '16px'
        }}>
          {patients.map(patient => (
            <div
              key={patient.id}
              style={{
                padding: '24px',
                border: '1px solid var(--mac-border)',
                borderRadius: 'var(--mac-radius-lg)',
                cursor: 'pointer',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
              onClick={() => handleTreatmentPlanner(patient)}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--mac-bg-secondary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  background: 'var(--mac-success)',
                  borderRadius: 'var(--mac-radius-full)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <span style={{
                    color: 'white',
                    fontSize: 'var(--mac-font-size-sm)',
                    fontWeight: 'var(--mac-font-weight-medium)'
                  }}>
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p style={{
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-base)'
                  }}>{patient.name}</p>
                  <p style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)'
                  }}>Открыть план</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );

  // Рендер протезирования
  const renderProsthetics = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          marginBottom: '16px',
          color: 'var(--mac-text-primary)'
        }}>Протезирование</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {prosthetics.map(prosthetic => (
            <div
              key={prosthetic.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '16px',
                background: 'var(--mac-bg-secondary)',
                borderRadius: 'var(--mac-radius-lg)',
                transition: 'all var(--mac-duration-normal) var(--mac-ease)'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--mac-bg-hover)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'var(--mac-bg-secondary)';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <div style={{
                  width: '40px',
                  height: '40px',
                  background: 'var(--mac-warning)',
                  borderRadius: 'var(--mac-radius-full)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  <Smile style={{ height: '20px', width: '20px', color: 'white' }} />
                </div>
                <div>
                  <p style={{
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: 'var(--mac-text-primary)',
                    fontSize: 'var(--mac-font-size-base)'
                  }}>{prosthetic.patientName}</p>
                  <p style={{
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)'
                  }}>{prosthetic.type}</p>
                </div>
              </div>
              <Badge variant={prosthetic.status === 'completed' ? 'success' : 'warning'}>
                {prosthetic.status}
              </Badge>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );

  // Рендер AI помощника
  const renderAIAssistant = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card padding="lg">
        <h3 style={{
          fontSize: 'var(--mac-font-size-lg)',
          fontWeight: 'var(--mac-font-weight-semibold)',
          marginBottom: '16px',
          color: 'var(--mac-text-primary)'
        }}>AI Помощник</h3>
        <AIAssistant
          context="dental"
          onSuggestion={(suggestion) => {
            console.log('AI предложение:', suggestion);
          }}
        />
      </Card>
    </div>
  );

  // Рендер контента
  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return renderDashboard();
      case 'queue':
        return (
          <QueueIntegration
            specialist="Стоматолог"
            onPatientSelect={handlePatientSelect}
            onStartVisit={(appointment) => {
              setSelectedPatient(appointment);
              handleTabChange('visits');
            }}
          />
        );
      case 'patients':
        return renderPatients();
      case 'appointments':
        return renderAppointments();
      case 'examinations':
        return renderExaminations();
      case 'diagnoses':
        return renderDiagnoses();
      case 'visits':
        return renderVisits();
      case 'photos':
        return renderPhotos();
      case 'templates':
        return renderTemplates();
      case 'reports':
        return renderReports();
      case 'dental-chart':
        return renderDentalChart();
      case 'treatment-plans':
        return renderTreatmentPlans();
      case 'prosthetics':
        return renderProsthetics();
      case 'ai-assistant':
        return renderAIAssistant();
      default:
        return renderDashboard();
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div style={{
            height: '32px',
            background: 'var(--mac-bg-secondary)',
            borderRadius: 'var(--mac-radius-md)',
            width: '25%',
            animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
          }}></div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '24px'
          }}>
            {[...Array(4)].map((_, i) => (
              <div key={i} style={{
                height: '96px',
                background: 'var(--mac-bg-secondary)',
                borderRadius: 'var(--mac-radius-md)',
                animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
              }}></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="dentist-panel" style={{
      padding: '0px', // Убираем padding, так как он уже есть в main контейнере
      boxSizing: 'border-box',
      width: '100%',
      position: 'relative',
      zIndex: 1,
      display: 'block',
      maxWidth: '100%',
      margin: 0,
      minHeight: '100vh',
      background: 'var(--mac-gradient-window)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
      color: 'var(--mac-text-primary)',
      transition: 'background var(--mac-duration-normal) var(--mac-ease)'
    }}>
      {renderContent()}

      {/* Модальные окна */}
      {showPatientCard && selectedPatient && (
        <PatientCard
          patient={selectedPatient}
          onSave={(updatedPatient) => {
            console.log('Сохранение пациента:', updatedPatient);
            setShowPatientCard(false);
          }}
          onClose={() => setShowPatientCard(false)}
        />
      )}

      {showExaminationForm && selectedPatient && (
        <ExaminationForm
          patientId={selectedPatient.id}
          initialData={selectedPatient.examinationData}
          onSave={(examinationData) => {
            console.log('Сохранение осмотра:', examinationData);
            setShowExaminationForm(false);
          }}
          onClose={() => setShowExaminationForm(false)}
        />
      )}

      {showDiagnosisForm && selectedPatient && (
        <DiagnosisForm
          patientId={selectedPatient.id}
          patientName={selectedPatient.name}
          initialData={selectedPatient.diagnosisData}
          onSave={(diagnosisData) => {
            console.log('Сохранение диагнозов:', diagnosisData);
            setShowDiagnosisForm(false);
          }}
          onClose={() => setShowDiagnosisForm(false)}
        />
      )}

      {showVisitProtocol && selectedPatient && (
        <VisitProtocol
          patientId={selectedPatient.id}
          patientName={selectedPatient.name}
          visitId={Date.now()}
          initialData={selectedPatient.visitData}
          onSave={(visitData) => {
            console.log('Сохранение протокола визита:', visitData);
            setShowVisitProtocol(false);
          }}
          onClose={() => setShowVisitProtocol(false)}
        />
      )}

      {showPhotoArchive && selectedPatient && (
        <PhotoArchive
          patientId={selectedPatient.id}
          patientName={selectedPatient.name}
          initialData={selectedPatient.photoArchive}
          onSave={(archiveData) => {
            console.log('Сохранение фото архива:', archiveData);
            setShowPhotoArchive(false);
          }}
          onClose={() => setShowPhotoArchive(false)}
        />
      )}

      {showProtocolTemplates && (
        <ProtocolTemplates
          onSelectTemplate={(template) => {
            console.log('Выбран шаблон:', template);
            // Здесь можно открыть протокол визита с выбранным шаблоном
          }}
          onClose={() => setShowProtocolTemplates(false)}
        />
      )}

      {showReports && (
        <ReportsAndAnalytics
          patientId={selectedPatient?.id}
          doctorId={user?.id}
          clinicId={user?.clinic_id}
          initialData={null}
          onSave={(reportData) => {
            console.log('Сохранение отчета:', reportData);
            setShowReports(false);
          }}
          onClose={() => setShowReports(false)}
        />
      )}

      {showDentalChart && selectedPatient && (
        <div style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 50
        }}>
          <div style={{
            background: 'var(--mac-bg-primary)',
            borderRadius: 'var(--mac-radius-xl)',
            padding: '24px',
            width: '100%',
            maxWidth: '1152px',
            height: '100%',
            maxHeight: '90vh',
            overflow: 'auto',
            boxShadow: 'var(--mac-shadow-xl)',
            border: '1px solid var(--mac-border)'
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '16px'
            }}>
              <h2 style={{
                fontSize: 'var(--mac-font-size-xl)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)'
              }}>
                Схема зубов: {selectedPatient.name}
              </h2>
              <button
                onClick={() => setShowDentalChart(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--mac-text-secondary)',
                  cursor: 'pointer',
                  transition: 'all var(--mac-duration-fast) var(--mac-ease)',
                  padding: '4px',
                  borderRadius: 'var(--mac-radius-sm)'
                }}
                onMouseEnter={(e) => {
                  e.target.style.color = 'var(--mac-text-primary)';
                  e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.color = 'var(--mac-text-secondary)';
                  e.target.style.backgroundColor = 'transparent';
                }}
              >
                <XCircle style={{ height: '24px', width: '24px' }} />
              </button>
            </div>
            <TeethChart
              patientId={selectedPatient.id}
              initialData={dentalChartData}
              onToothClick={(toothNumber, toothData) => {
                console.log('Клик по зубу:', toothNumber, toothData);
                setSelectedTooth({ number: toothNumber, data: toothData });
                setToothModalOpen(true);
              }}
              readOnly={false}
            />
          </div>
        </div>
      )}

      {showTreatmentPlanner && selectedPatient && (
        <div style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 50
        }}>
          <div style={{
            background: 'var(--mac-bg-primary)',
            borderRadius: 'var(--mac-radius-xl)',
            padding: '24px',
            width: '100%',
            maxWidth: '1152px',
            height: '100%',
            maxHeight: '90vh',
            overflow: 'auto',
            boxShadow: 'var(--mac-shadow-xl)',
            border: '1px solid var(--mac-border)'
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '16px'
            }}>
              <h2 style={{
                fontSize: 'var(--mac-font-size-xl)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                color: 'var(--mac-text-primary)'
              }}>
                План лечения: {selectedPatient.name}
              </h2>
              <button
                onClick={() => setShowTreatmentPlanner(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--mac-text-secondary)',
                  cursor: 'pointer',
                  transition: 'all var(--mac-duration-fast) var(--mac-ease)',
                  padding: '4px',
                  borderRadius: 'var(--mac-radius-sm)'
                }}
                onMouseEnter={(e) => {
                  e.target.style.color = 'var(--mac-text-primary)';
                  e.target.style.backgroundColor = 'var(--mac-bg-secondary)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.color = 'var(--mac-text-secondary)';
                  e.target.style.backgroundColor = 'transparent';
                }}
              >
                <XCircle style={{ height: '24px', width: '24px' }} />
              </button>
            </div>
            <TreatmentPlanner
              patientId={selectedPatient.id}
              visitId={selectedPatient.visitId || 'demo-visit-1'}
              teethData={dentalChartData || {}}
              onUpdate={(plan) => {
                console.log('План лечения обновлен:', plan);
                setCurrentTreatmentPlan(plan);
              }}
            />
          </div>
        </div>
      )}

      {/* Форма осмотра */}
      {showExaminationForm && selectedPatient && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg w-full max-w-4xl h-full max-h-[90vh] overflow-auto">
            <div className="p-6 border-b">
              <h2 className="text-xl font-semibold">
                Новый стоматологический осмотр — {selectedPatient.name}
              </h2>
            </div>
            <div className="p-6">
              <form onSubmit={handleExaminationSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Дата осмотра *</label>
                    <input
                      type="date"
                      value={examinationForm.examination_date}
                      onChange={(e) => setExaminationForm({ ...examinationForm, examination_date: e.target.value })}
                      required
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Гигиена полости рта</label>
                    <select
                      value={examinationForm.oral_hygiene}
                      onChange={(e) => setExaminationForm({ ...examinationForm, oral_hygiene: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Выберите</option>
                      <option value="excellent">Отличная</option>
                      <option value="good">Хорошая</option>
                      <option value="fair">Удовлетворительная</option>
                      <option value="poor">Плохая</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Статус кариеса</label>
                    <select
                      value={examinationForm.caries_status}
                      onChange={(e) => setExaminationForm({ ...examinationForm, caries_status: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Выберите</option>
                      <option value="none">Нет кариеса</option>
                      <option value="initial">Начальный</option>
                      <option value="superficial">Поверхностный</option>
                      <option value="medium">Средний</option>
                      <option value="deep">Глубокий</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Статус пародонта</label>
                    <select
                      value={examinationForm.periodontal_status}
                      onChange={(e) => setExaminationForm({ ...examinationForm, periodontal_status: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Выберите</option>
                      <option value="healthy">Здоровый</option>
                      <option value="gingivitis">Гингивит</option>
                      <option value="periodontitis">Пародонтит</option>
                      <option value="advanced">Тяжелый</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Прикус</label>
                    <select
                      value={examinationForm.occlusion}
                      onChange={(e) => setExaminationForm({ ...examinationForm, occlusion: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Выберите</option>
                      <option value="normal">Нормальный</option>
                      <option value="open_bite">Открытый</option>
                      <option value="deep_bite">Глубокий</option>
                      <option value="cross_bite">Перекрестный</option>
                      <option value="crowding">Скученность</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Отсутствующие зубы</label>
                    <input
                      type="text"
                      value={examinationForm.missing_teeth}
                      onChange={(e) => setExaminationForm({ ...examinationForm, missing_teeth: e.target.value })}
                      placeholder="Номера отсутствующих зубов"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Зубной налет</label>
                    <select
                      value={examinationForm.dental_plaque}
                      onChange={(e) => setExaminationForm({ ...examinationForm, dental_plaque: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Выберите</option>
                      <option value="none">Нет</option>
                      <option value="minimal">Минимальный</option>
                      <option value="moderate">Умеренный</option>
                      <option value="heavy">Тяжелый</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Кровоточивость десен</label>
                    <select
                      value={examinationForm.gingival_bleeding}
                      onChange={(e) => setExaminationForm({ ...examinationForm, gingival_bleeding: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Выберите</option>
                      <option value="none">Нет</option>
                      <option value="mild">Легкая</option>
                      <option value="moderate">Умеренная</option>
                      <option value="severe">Тяжелая</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Диагноз</label>
                  <textarea
                    value={examinationForm.diagnosis}
                    onChange={(e) => setExaminationForm({ ...examinationForm, diagnosis: e.target.value })}
                    placeholder="Стоматологический диагноз"
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Рекомендации</label>
                  <textarea
                    value={examinationForm.recommendations}
                    onChange={(e) => setExaminationForm({ ...examinationForm, recommendations: e.target.value })}
                    placeholder="Рекомендации по лечению и уходу"
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div className="flex gap-2">
                  <Button type="submit" className="flex items-center gap-2">
                    <Save className="h-4 w-4" />
                    Сохранить осмотр
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowExaminationForm(false)}
                  >
                    Отмена
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Форма лечения */}
      {showTreatmentForm && selectedPatient && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg w-full max-w-4xl h-full max-h-[90vh] overflow-auto">
            <div className="p-6 border-b">
              <h2 className="text-xl font-semibold">
                Новый план лечения — {selectedPatient.name}
              </h2>
            </div>
            <div className="p-6">
              <form onSubmit={handleTreatmentSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Дата лечения *</label>
                    <input
                      type="date"
                      value={treatmentForm.treatment_date}
                      onChange={(e) => setTreatmentForm({ ...treatmentForm, treatment_date: e.target.value })}
                      required
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Тип лечения *</label>
                    <select
                      value={treatmentForm.treatment_type}
                      onChange={(e) => setTreatmentForm({ ...treatmentForm, treatment_type: e.target.value })}
                      required
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Выберите тип</option>
                      <option value="filling">Пломбирование</option>
                      <option value="root_canal">Каналы</option>
                      <option value="extraction">Удаление</option>
                      <option value="cleaning">Чистка</option>
                      <option value="whitening">Отбеливание</option>
                      <option value="orthodontics">Ортодонтия</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Вовлеченные зубы</label>
                    <input
                      type="text"
                      value={treatmentForm.teeth_involved}
                      onChange={(e) => setTreatmentForm({ ...treatmentForm, teeth_involved: e.target.value })}
                      placeholder="Номера зубов"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Стоимость</label>
                    <input
                      type="number"
                      value={treatmentForm.cost}
                      onChange={(e) => setTreatmentForm({ ...treatmentForm, cost: e.target.value })}
                      placeholder="Сумма"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Описание процедуры</label>
                  <textarea
                    value={treatmentForm.procedure_description}
                    onChange={(e) => setTreatmentForm({ ...treatmentForm, procedure_description: e.target.value })}
                    placeholder="Подробное описание"
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Материалы</label>
                    <input
                      type="text"
                      value={treatmentForm.materials_used}
                      onChange={(e) => setTreatmentForm({ ...treatmentForm, materials_used: e.target.value })}
                      placeholder="Названия материалов"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Анестезия</label>
                    <select
                      value={treatmentForm.anesthesia}
                      onChange={(e) => setTreatmentForm({ ...treatmentForm, anesthesia: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Выберите</option>
                      <option value="none">Не требуется</option>
                      <option value="local">Местная</option>
                      <option value="sedation">Седация</option>
                      <option value="general">Общая</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Осложнения</label>
                    <input
                      type="text"
                      value={treatmentForm.complications}
                      onChange={(e) => setTreatmentForm({ ...treatmentForm, complications: e.target.value })}
                      placeholder="Описание осложнений"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Дата контроля</label>
                    <input
                      type="date"
                      value={treatmentForm.follow_up_date}
                      onChange={(e) => setTreatmentForm({ ...treatmentForm, follow_up_date: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                </div>

                <div className="flex gap-2">
                  <Button type="submit" className="flex items-center gap-2">
                    <Save className="h-4 w-4" />
                    Сохранить лечение
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      // Открываем менеджер цен для указания итоговой стоимости
                      setSelectedServiceForPrice({
                        id: 1, // ID услуги - в реальном приложении получать из формы
                        name: treatmentForm.procedure_type || 'Стоматологическое лечение',
                        price: Number(treatmentForm.cost) || 50000
                      });
                      setShowPriceManager(true);
                    }}
                    className="flex items-center gap-2"
                  >
                    <DollarSign className="h-4 w-4" />
                    Указать цену
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowTreatmentForm(false)}
                  >
                    Отмена
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Форма протезирования */}
      {showProstheticForm && selectedPatient && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg w-full max-w-4xl h-full max-h-[90vh] overflow-auto">
            <div className="p-6 border-b">
              <h2 className="text-xl font-semibold">
                Новый протез — {selectedPatient.name}
              </h2>
            </div>
            <div className="p-6">
              <form onSubmit={handleProstheticSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Дата протезирования *</label>
                    <input
                      type="date"
                      value={prostheticForm.prosthetic_date}
                      onChange={(e) => setProstheticForm({ ...prostheticForm, prosthetic_date: e.target.value })}
                      required
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Тип протеза *</label>
                    <select
                      value={prostheticForm.prosthetic_type}
                      onChange={(e) => setProstheticForm({ ...prostheticForm, prosthetic_type: e.target.value })}
                      required
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Выберите тип</option>
                      <option value="crown">Коронка</option>
                      <option value="bridge">Мост</option>
                      <option value="implant">Имплант</option>
                      <option value="partial_denture">Частичный протез</option>
                      <option value="full_denture">Полный протез</option>
                      <option value="veneer">Винир</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Заменяемые зубы</label>
                    <input
                      type="text"
                      value={prostheticForm.teeth_replaced}
                      onChange={(e) => setProstheticForm({ ...prostheticForm, teeth_replaced: e.target.value })}
                      placeholder="Номера зубов"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Материал</label>
                    <select
                      value={prostheticForm.material}
                      onChange={(e) => setProstheticForm({ ...prostheticForm, material: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Выберите материал</option>
                      <option value="porcelain">Фарфор</option>
                      <option value="metal">Металл</option>
                      <option value="ceramic">Керамика</option>
                      <option value="composite">Композит</option>
                      <option value="zirconia">Диоксид циркония</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Оттенок</label>
                    <input
                      type="text"
                      value={prostheticForm.shade}
                      onChange={(e) => setProstheticForm({ ...prostheticForm, shade: e.target.value })}
                      placeholder="A1, B2, C3 и т.д."
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Стоимость</label>
                    <input
                      type="number"
                      value={prostheticForm.cost}
                      onChange={(e) => setProstheticForm({ ...prostheticForm, cost: e.target.value })}
                      placeholder="Сумма"
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Качество посадки</label>
                    <select
                      value={prostheticForm.fit_quality}
                      onChange={(e) => setProstheticForm({ ...prostheticForm, fit_quality: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Выберите</option>
                      <option value="excellent">Отличная</option>
                      <option value="good">Хорошая</option>
                      <option value="fair">Удовлетворительная</option>
                      <option value="poor">Плохая</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Удовлетворенность пациента</label>
                    <select
                      value={prostheticForm.patient_satisfaction}
                      onChange={(e) => setProstheticForm({ ...prostheticForm, patient_satisfaction: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    >
                      <option value="">Выберите</option>
                      <option value="very_satisfied">Очень доволен</option>
                      <option value="satisfied">Доволен</option>
                      <option value="neutral">Нейтрально</option>
                      <option value="dissatisfied">Не доволен</option>
                      <option value="very_dissatisfied">Очень не доволен</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Гарантийный период</label>
                  <input
                    type="text"
                    value={prostheticForm.warranty_period}
                    onChange={(e) => setProstheticForm({ ...prostheticForm, warranty_period: e.target.value })}
                    placeholder="Например: 2 года"
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                <div className="flex gap-2">
                  <Button type="submit" className="flex items-center gap-2">
                    <Save className="h-4 w-4" />
                    Сохранить протез
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setShowProstheticForm(false)}
                  >
                    Отмена
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Модальное окно для работы с зубом */}
      {toothModalOpen && selectedTooth && (
        <ToothModal
          open={toothModalOpen}
          onClose={() => {
            setToothModalOpen(false);
            setSelectedTooth(null);
          }}
          toothNumber={selectedTooth.number}
          toothData={selectedTooth.data}
          onSave={(toothNumber, data) => {
            console.log('Сохранение данных зуба:', toothNumber, data);
            // Обновляем данные зубной карты
            setDentalChartData(prev => ({
              ...prev,
              [toothNumber]: data
            }));
            setToothModalOpen(false);
          }}
          patientId={selectedPatient?.id}
          visitId={selectedPatient?.visitId || 'demo-visit-1'}
        />
      )}
      
      {/* DentalPriceManager Modal */}
      {showPriceManager && selectedServiceForPrice && (
        <DentalPriceManager
          visitId={selectedPatient?.id || 1} // Используем ID пациента как visitId для демо
          serviceId={selectedServiceForPrice.id}
          serviceName={selectedServiceForPrice.name}
          originalPrice={selectedServiceForPrice.price}
          isOpen={showPriceManager}
          onClose={() => {
            setShowPriceManager(false);
            setSelectedServiceForPrice(null);
          }}
          onPriceSet={(priceData) => {
            console.log('Price set:', priceData);
            // Можно добавить логику обновления состояния
          }}
        />
      )}

      {/* Модальное окно Schedule Next */}
      {scheduleNextModal.open && (
        <ScheduleNextModal
          isOpen={scheduleNextModal.open}
          onClose={() => setScheduleNextModal({ open: false, patient: null })}
          patient={scheduleNextModal.patient}
          theme={{ isDark, getColor, getSpacing, getFontSize }}
          specialtyFilter="dentistry"
        />
      )}
    </div>
  );
};

export default DentistPanelUnified;
