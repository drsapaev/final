import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { 
  Camera, 
  Activity, 
  FileText, 
  User,
  Users, 
  Settings,
  Save,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Stethoscope,
  Calendar,
  Brain,
  Phone,
  Plus,
  TestTube,
  Image as ImageIcon,
  Scissors,
  Sparkles,
  DollarSign,
  Clock
} from 'lucide-react';
import { MacOSButton, MacOSCard, MacOSBadge, MacOSInput, MacOSTextarea, MacOSSelect, MacOSCheckbox, MacOSLoadingSkeleton, MacOSEmptyState, MacOSAlert, Icon } from '../components/ui/macos';
import { useTheme } from '../contexts/ThemeContext';
import DoctorQueuePanel from '../components/doctor/DoctorQueuePanel';
import DoctorServiceSelector from '../components/doctor/DoctorServiceSelector';
import AIAssistant from '../components/ai/AIAssistant';
import ServiceChecklist from '../components/ServiceChecklist';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import EMRSystem from '../components/medical/EMRSystem';
import PhotoUploader from '../components/dermatology/PhotoUploader';
import PhotoComparison from '../components/dermatology/PhotoComparison';
import ProcedureTemplates from '../components/dermatology/ProcedureTemplates';
import SkinAnalysis from '../components/dermatology/SkinAnalysis';
import PriceOverrideManager from '../components/dermatology/PriceOverrideManager';
import PrescriptionSystem from '../components/PrescriptionSystem';
import VisitTimeline from '../components/VisitTimeline';
import QueueIntegration from '../components/QueueIntegration';
import { APPOINTMENT_STATUS } from '../constants/appointmentStatus';

/**
 * Унифицированная панель дерматолога
 * Объединяет: очередь + фото до/после + косметология + AI
 */
const DermatologistPanelUnified = () => {
  // Всегда вызываем хуки первыми
  const { theme, isDark, getColor, getSpacing, getFontSize, getShadow } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  
  // Синхронизация активной вкладки с URL
  const getActiveTabFromURL = () => {
    const params = new URLSearchParams(location.search);
    return params.get('tab') || 'queue';
  };
  
  const [activeTab, setActiveTab] = useState(getActiveTabFromURL());
  const [selectedPatient, setSelectedPatient] = useState(null);
  
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
    navigate(`/dermatologist?tab=${tabId}`, { replace: true });
  };
  const [selectedServices, setSelectedServices] = useState([]);
  const [visitData, setVisitData] = useState({
    complaint: '',
    diagnosis: '',
    icd10: '',
    notes: ''
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [scheduleNextModal, setScheduleNextModal] = useState({ open: false, patient: null });
  
  // Состояния для таблицы записей
  const [appointments, setAppointments] = useState([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [appointmentsSelected, setAppointmentsSelected] = useState(new Set());

  // Специализированные данные дерматолога
  const [skinExamination, setSkinExamination] = useState({
    patient_id: '',
    examination_date: '',
    skin_type: '',
    skin_condition: '',
    lesions: '',
    distribution: '',
    symptoms: '',
    diagnosis: '',
    treatment_plan: ''
  });

  const [cosmeticProcedure, setCosmeticProcedure] = useState({
    patient_id: '',
    procedure_date: '',
    procedure_type: '',
    area_treated: '',
    products_used: '',
    results: '',
    follow_up: ''
  });

  const [showSkinForm, setShowSkinForm] = useState(false);
  const [showCosmeticForm, setShowCosmeticForm] = useState(false);
  const [skinExaminations, setSkinExaminations] = useState([]);
  const [cosmeticProcedures, setCosmeticProcedures] = useState([]);
  const [photoData, setPhotoData] = useState([]);
  
  // Дополнительные состояния из старого файла
  const [patients, setPatients] = useState([]);
  const [currentAppointment, setCurrentAppointment] = useState(null);
  const [emr, setEmr] = useState(null);
  const [prescription, setPrescription] = useState(null);
  const [doctorPrice, setDoctorPrice] = useState('');
  
  // Состояние для PriceOverrideManager
  const [showPriceOverride, setShowPriceOverride] = useState(false);
  const [selectedServiceForPriceOverride, setSelectedServiceForPriceOverride] = useState(null);
  
  // Локальный справочник цен для дерма/косметологии
  const dermaPriceMap = useMemo(() => ({
    derma_consultation: 50000,
    derma_biopsy: 150000,
    cosm_cleaning: 80000,
    cosm_botox: 300000,
    cosm_laser: 250000,
  }), []);

  const servicesSubtotal = useMemo(() => {
    return selectedServices.reduce((sum, id) => sum + (dermaPriceMap[id] || 0), 0);
  }, [selectedServices, dermaPriceMap]);

  const doctorPriceNum = useMemo(() => {
    const n = Number(String(doctorPrice).replace(/[^0-9.-]/g, ''));
    return Number.isFinite(n) ? Math.max(0, n) : 0;
  }, [doctorPrice]);

  const totalCost = useMemo(() => servicesSubtotal + doctorPriceNum, [servicesSubtotal, doctorPriceNum]);

  // Вкладки панели
  const tabs = [
    { id: 'queue', label: 'Очередь', icon: Users, color: 'text-blue-600' },
    { id: 'appointments', label: 'Записи', icon: Calendar, color: 'text-green-600' },
    { id: 'visit', label: 'Прием', icon: Stethoscope, color: 'text-orange-600' },
    { id: 'patients', label: 'Пациенты', icon: User, color: 'text-green-600' },
    { id: 'photos', label: 'Фото', icon: Camera, color: 'text-purple-600' },
    { id: 'skin', label: 'Осмотр кожи', icon: Activity, color: 'text-green-600' },
    { id: 'cosmetic', label: 'Косметология', icon: Sparkles, color: 'text-pink-600' },
    { id: 'ai', label: 'AI Помощник', icon: Brain, color: 'text-indigo-600' },
    { id: 'services', label: 'Услуги', icon: Scissors, color: 'text-orange-600' },
    { id: 'history', label: 'История', icon: FileText, color: 'text-gray-600' }
  ];

  useEffect(() => {
    loadPatients();
    loadSkinExaminations();
    loadCosmeticProcedures();
  }, []);

  useEffect(() => {
    if (selectedPatient) {
      loadPatientData();
    }
  }, [selectedPatient]);

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

  // Загрузка записей дерматолога
  const loadDermatologyAppointments = async () => {
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
                  payment_status: entry.payment_status || 'pending',
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

        // Фильтруем только дерматологические записи для отображения
        const appointmentsData = allAppointments.filter(apt => 
          apt.specialty === 'derma' || apt.specialty === 'dermatology'
        );

        // Добавляем информацию о всех услугах пациента в каждую запись
        const enrichedAppointmentsData = appointmentsData.map(apt => {
          const allPatientServices = getAllPatientServices(apt.patient_id, allAppointments);
          return {
            ...apt,
            all_patient_services: allPatientServices.services,
            all_patient_service_codes: allPatientServices.service_codes
          };
        });
        
        setAppointments(enrichedAppointmentsData);
      }
    } catch (error) {
      console.error('Ошибка загрузки записей дерматолога:', error);
    } finally {
      setAppointmentsLoading(false);
    }
  };

  // Загружаем записи при переключении на вкладку
  useEffect(() => {
    if (activeTab === 'appointments') {
      loadDermatologyAppointments();
    }
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
        handleTabChange('visit');
    }
  };

  const handleAppointmentActionClick = (action, row, event) => {
    console.log('Действие с записью:', action, row);
    event.stopPropagation();
    
    switch (action) {
      case 'view':
        handleAppointmentRowClick(row);
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
    console.log('DermatologistPanelUnified: Skipping render in demo mode');
    return null;
  }

  const authHeader = () => ({
    Authorization: `Bearer ${localStorage.getItem('auth_token') || localStorage.getItem('token') || ''}`,
  });

  const loadPatients = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8000/api/v1/patients?department=Derma&limit=100', {
        headers: authHeader(),
      });
      if (response.ok) {
        const data = await response.json();
        setPatients(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      console.error('Ошибка загрузки пациентов:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadSkinExaminations = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/v1/derma/examinations?limit=100', {
        headers: authHeader(),
      });
      if (response.ok) {
        const data = await response.json();
        setSkinExaminations(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      // эндпоинт может отсутствовать
    }
  };

  const loadCosmeticProcedures = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/v1/derma/procedures?limit=100', {
        headers: authHeader(),
      });
      if (response.ok) {
        const data = await response.json();
        setCosmeticProcedures(Array.isArray(data) ? data : []);
      }
    } catch (error) {
      // эндпоинт может отсутствовать
    }
  };

  const loadPatientData = async () => {
    if (!selectedPatient?.patient?.id) return;
    
    try {
      // Загружаем осмотры кожи пациента
      const skinResponse = await fetch(`/api/v1/dermatology/skin-examinations?patient_id=${selectedPatient.patient.id}&limit=10`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (skinResponse.ok) {
        const skinData = await skinResponse.json();
        setSkinExaminations(skinData);
      }

      // Загружаем косметические процедуры пациента
      const cosmeticResponse = await fetch(`/api/v1/dermatology/cosmetic-procedures?patient_id=${selectedPatient.patient.id}&limit=10`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (cosmeticResponse.ok) {
        const cosmeticData = await cosmeticResponse.json();
        setCosmeticProcedures(cosmeticData);
      }
    } catch (error) {
      console.error('Ошибка загрузки данных пациента:', error);
    }
  };

  // Функции EMR системы из старого файла
  const startVisit = async (appointment) => {
    try {
      const token = localStorage.getItem('auth_token') || localStorage.getItem('token');
      
      const response = await fetch(`/api/v1/appointments/${appointment.id}/start-visit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token || ''}`
        }
      });

      if (response.ok) {
        const updatedAppointment = await response.json();
        setCurrentAppointment(updatedAppointment);
        setMessage({ type: 'success', text: 'Прием начат успешно!' });
      } else {
        const error = await response.json().catch(() => ({ detail: 'Ошибка при начале приема' }));
        console.error('Start visit error:', error);
        setMessage({ type: 'error', text: error.detail || 'Ошибка при начале приема' });
      }
    } catch (error) {
      console.error('DermatologistPanel: Start visit error:', error);
      setMessage({ type: 'error', text: 'Ошибка при начале приема' });
    }
  };

  const saveEMR = async (emrData) => {
    try {
      const response = await fetch(`/api/v1/appointments/${currentAppointment.id}/emr`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify(emrData)
      });

      if (response.ok) {
        const savedEMR = await response.json();
        setEmr(savedEMR);
        setMessage({ type: 'success', text: 'EMR сохранена успешно!' });
      } else {
        const error = await response.json();
        setMessage({ type: 'error', text: error.detail || 'Ошибка при сохранении EMR' });
      }
    } catch (error) {
      console.error('DermatologistPanel: Save EMR error:', error);
      setMessage({ type: 'error', text: 'Ошибка при сохранении EMR' });
    }
  };

  const savePrescription = async (prescriptionData) => {
    try {
      const response = await fetch(`/api/v1/appointments/${currentAppointment.id}/prescription`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify(prescriptionData)
      });

      if (response.ok) {
        const savedPrescription = await response.json();
        setPrescription(savedPrescription);
        setMessage({ type: 'success', text: 'Рецепт сохранен успешно!' });
      } else {
        const error = await response.json();
        setMessage({ type: 'error', text: error.detail || 'Ошибка при сохранении рецепта' });
      }
    } catch (error) {
      console.error('DermatologistPanel: Save prescription error:', error);
      setMessage({ type: 'error', text: 'Ошибка при сохранении рецепта' });
    }
  };

  const completeVisit = async () => {
    try {
      const response = await fetch(`/api/v1/appointments/${currentAppointment.id}/complete`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (response.ok) {
        const completedAppointment = await response.json();
        setCurrentAppointment(completedAppointment);
        setMessage({ type: 'success', text: 'Прием завершен успешно!' });
        // Сброс состояния
        setCurrentAppointment(null);
        setEmr(null);
        setPrescription(null);
      } else {
        const error = await response.json();
        setMessage({ type: 'error', text: error.detail || 'Ошибка при завершении приема' });
      }
    } catch (error) {
      console.error('DermatologistPanel: Complete visit error:', error);
      setMessage({ type: 'error', text: 'Ошибка при завершении приема' });
    }
  };

  // Обработка выбора пациента из очереди
  const handlePatientSelect = (patient) => {
    setSelectedPatient(patient);
        handleTabChange('visit');
    setMessage({ type: 'info', text: `Выбран пациент: ${patient.patient_name}` });
  };

  // Обработка AI предложений
  const handleAISuggestion = (type, suggestion) => {
    if (type === 'icd10') {
      setVisitData({ ...visitData, icd10: suggestion });
      setMessage({ type: 'success', text: 'Код МКБ-10 добавлен из AI предложения' });
    } else if (type === 'diagnosis') {
      setVisitData({ ...visitData, diagnosis: suggestion });
      setMessage({ type: 'success', text: 'Диагноз добавлен из AI предложения' });
    }
  };

  // Обработка сохранения визита
  const handleSaveVisit = async () => {
    if (!selectedPatient) return;

    try {
      setLoading(true);
      
      const visitPayload = {
        patient_id: selectedPatient.patient?.id,
        complaint: visitData.complaint,
        diagnosis: visitData.diagnosis,
        icd10: visitData.icd10,
        services: selectedServices,
        notes: visitData.notes
      };

      const response = await fetch(`http://localhost:8000/api/v1/doctor/queue/${selectedPatient.id}/complete`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${localStorage.getItem('auth_token') || ''}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(visitPayload)
      });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Прием завершен успешно' });
        
        // Очищаем форму
        setSelectedPatient(null);
        setSelectedServices([]);
        setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
        handleTabChange('queue');
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }

    } catch (error) {
      console.error('Ошибка сохранения визита:', error);
      setMessage({ type: 'error', text: error.message });
    } finally {
      setLoading(false);
    }
  };

  // Обработка осмотра кожи
  const handleSkinExaminationSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('http://localhost:8000/api/v1/dermatology/skin-examinations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(skinExamination)
      });

      if (response.ok) {
        setShowSkinForm(false);
        setSkinExamination({
          patient_id: '',
          examination_date: '',
          skin_type: '',
          skin_condition: '',
          lesions: '',
          distribution: '',
          symptoms: '',
          diagnosis: '',
          treatment_plan: ''
        });
        loadPatientData();
        setMessage({ type: 'success', text: 'Осмотр кожи сохранен успешно' });
      }
    } catch (error) {
      console.error('Ошибка сохранения осмотра:', error);
      setMessage({ type: 'error', text: 'Ошибка сохранения осмотра кожи' });
    }
  };

  // Обработка косметической процедуры
  const handleCosmeticProcedureSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('http://localhost:8000/api/v1/dermatology/cosmetic-procedures', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(cosmeticProcedure)
      });

      if (response.ok) {
        setShowCosmeticForm(false);
        setCosmeticProcedure({
          patient_id: '',
          procedure_date: '',
          procedure_type: '',
          area_treated: '',
          products_used: '',
          results: '',
          follow_up: ''
        });
        loadPatientData();
        setMessage({ type: 'success', text: 'Косметическая процедура сохранена успешно' });
      }
    } catch (error) {
      console.error('Ошибка сохранения процедуры:', error);
      setMessage({ type: 'error', text: 'Ошибка сохранения косметической процедуры' });
    }
  };

  const pageStyle = {
    padding: '20px',
    maxWidth: '1400px',
    margin: '0 auto',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    background: 'var(--mac-bg-primary)',
    minHeight: '100vh',
    color: 'var(--mac-text-primary)'
  };

  const headerStyle = {
    marginBottom: '24px',
    padding: '20px',
    background: 'var(--mac-bg-secondary)',
    borderRadius: 'var(--mac-radius-md)',
    border: '1px solid var(--mac-border)',
    boxShadow: 'var(--mac-shadow-sm)'
  };

  const tabStyle = {
    padding: '12px 24px',
    border: 'none',
    background: 'transparent',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
    color: 'var(--mac-text-secondary)',
    borderRadius: 'var(--mac-radius-sm)',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)',
    display: 'flex',
    alignItems: 'center',
    gap: '8px'
  };

  const activeTabStyle = {
    ...tabStyle,
    background: 'var(--mac-accent)',
    color: 'var(--mac-text-on-accent)',
    boxShadow: 'var(--mac-shadow-sm)'
  };

  return (
    <div style={{
      ...pageStyle,
      padding: '0',
      boxSizing: 'border-box',
      overflow: 'hidden',
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

      <div style={{ padding: '0px' }}> {/* Убираем padding, так как он уже есть в main контейнере */}


      {/* Контент вкладок */}
      <div>
        {/* Очередь пациентов */}
        {activeTab === 'queue' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <MacOSCard style={{ padding: '24px' }}>
              <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '20px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
                display: 'flex',
                alignItems: 'center'
              }}>
                <Users size={20} style={{ marginRight: '8px', color: 'var(--mac-blue-500)' }} />
                Очередь пациентов
              </h3>
              <QueueIntegration
                specialist="Дерматолог"
                onPatientSelect={(patient) => {
                  const appointment = {
                    id: patient.id,
                    patient_id: patient.id,
                    patient_name: patient.patient_name,
                    status: patient.status || 'in_cabinet'
                  };
                  setCurrentAppointment(appointment);
                  handleTabChange('visit');
                }}
                onStartVisit={(patient) => {
                  // Если есть appointment_id, используем его; иначе создаем объект appointment
                  if (patient.appointment_id) {
                    const appointment = {
                      id: patient.appointment_id,
                      patient_id: patient.patient_id || patient.id,
                      patient_name: patient.patient_name,
                      status: patient.status || 'in_cabinet'
                    };
                    startVisit(appointment);
                  } else {
                    // Если нет appointment_id, просто показываем пациента
                    setSelectedPatient({
                      id: patient.id,
                      patient_name: patient.patient_name,
                      patient_id: patient.patient_id || patient.id,
                      status: patient.status,
                      source: 'queue'
                    });
                    setCurrentAppointment(null);
                    handleTabChange('visit');
                  }
                }}
              />
            </MacOSCard>
          </div>
        )}

        {/* Записи дерматолога */}
        {activeTab === 'appointments' && (
          <div style={{ 
            width: '100%', 
            maxWidth: 'none',
            display: 'flex',
            flexDirection: 'column',
            gap: '24px'
          }}>
            <MacOSCard style={{
              padding: '24px',
              width: '100%',
              maxWidth: '100%',
              minWidth: 0,
              boxSizing: 'border-box',
              overflow: 'hidden'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3 style={{
                  fontSize: '18px',
                  fontWeight: '600',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
                  display: 'flex',
                  alignItems: 'center',
                  margin: 0
                }}>
                  <Calendar size={20} style={{ marginRight: '8px', color: 'var(--mac-green-500)' }} />
                  Записи к дерматологу
                </h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <MacOSBadge variant="info">
                    Всего: {appointments.length}
                  </MacOSBadge>
                  <MacOSButton 
                    variant="outline"
                    onClick={loadDermatologyAppointments}
                    disabled={appointmentsLoading}
                    style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    <RefreshCw size={16} />
                    Обновить
                  </MacOSButton>
                </div>
              </div>
              
              <EnhancedAppointmentsTable
                data={appointments}
                loading={appointmentsLoading}
                theme={isDark ? 'dark' : 'light'}
                language="ru"
                selectedRows={new Set()}
                outerBorder={false}
                services={{}}
                showCheckboxes={false}
                view="doctor"
                onRowSelect={() => {}}
                onRowClick={handleAppointmentRowClick}
                onActionClick={handleAppointmentActionClick}
              />
            </MacOSCard>
          </div>
        )}

        {/* Список пациентов */}
        {activeTab === 'patients' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <MacOSCard style={{ padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3 style={{
                  fontSize: '18px',
                  fontWeight: '600',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
                  display: 'flex',
                  alignItems: 'center',
                  marginBottom: '20px'
                }}>
                  <User size={20} style={{ marginRight: '8px', color: 'var(--mac-green-500)' }} />
                  Дерматологические пациенты
                </h3>
                <MacOSBadge variant="info">Всего: {patients.length} пациентов</MacOSBadge>
              </div>

              {loading ? (
                <div style={{ textAlign: 'center', padding: '32px' }}>
                  <RefreshCw size={32} style={{ margin: '0 auto 16px', color: 'var(--mac-text-secondary)', animation: 'spin 1s linear infinite' }} />
                  <p style={{ color: 'var(--mac-text-secondary)', fontSize: '14px' }}>Загрузка пациентов...</p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  {patients.map((patient) => (
                    <div key={patient.id} style={{
                      border: '1px solid var(--mac-border)',
                      borderRadius: 'var(--mac-radius-lg)',
                      padding: '24px',
                      backgroundColor: 'var(--mac-bg-primary)',
                      transition: 'box-shadow var(--mac-duration-normal) var(--mac-ease)'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '16px' }}>
                            <h4 style={{
                              fontSize: '16px',
                              fontWeight: '600',
                              color: 'var(--mac-text-primary)',
                              fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
                              margin: 0
                            }}>
                              {patient.last_name} {patient.first_name} {patient.middle_name}
                            </h4>
                            <MacOSBadge variant="success" style={{ marginLeft: '12px' }}>Дерматология</MacOSBadge>
                          </div>
                          <div style={{
                            fontSize: '13px',
                            color: 'var(--mac-text-secondary)',
                            fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '12px'
                          }}>
                            <div style={{ display: 'flex', alignItems: 'center' }}>
                              <Phone size={18} style={{ marginRight: '8px', color: 'var(--mac-accent)' }} />
                              {patient.phone}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center' }}>
                              <Calendar size={14} style={{ marginRight: '8px' }} />
                              {patient.birth_date}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center' }}>
                              <User size={14} style={{ marginRight: '8px' }} />
                              ID: {patient.id}
                            </div>
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: '16px' }}>
                          <MacOSButton
                            variant="outline"
                            onClick={() => {
                              setSelectedPatient(patient);
                              setSkinExamination({ ...skinExamination, patient_id: patient.id });
                              setShowSkinForm(true);
                            }}
                            style={{ fontSize: '13px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}
                          >
                            <Activity size={16} />
                            Осмотр
                          </MacOSButton>
                          <MacOSButton
                            variant="outline"
                            onClick={() => {
                              setSelectedPatient(patient);
                              setCosmeticProcedure({ ...cosmeticProcedure, patient_id: patient.id });
                              setShowCosmeticForm(true);
                            }}
                            style={{ fontSize: '13px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}
                          >
                            <Sparkles size={16} />
                            Процедура
                          </MacOSButton>
                          <MacOSButton
                            variant="outline"
                            onClick={() => setSelectedPatient(patient)}
                            style={{ fontSize: '13px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '6px' }}
                          >
                            <User size={16} />
                            Просмотр
                          </MacOSButton>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </MacOSCard>
          </div>
        )}

        {/* Прием пациента - EMR система */}
        {activeTab === 'visit' && currentAppointment && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <MacOSCard style={{ padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h3 style={{
                  fontSize: '18px',
                  fontWeight: '600',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
                  display: 'flex',
                  alignItems: 'center',
                  margin: 0
                }}>
                  <Stethoscope size={20} style={{ marginRight: '8px', color: 'var(--mac-orange-500)' }} />
                  Прием пациента: {currentAppointment.patient_name || 'Не указано'}
                </h3>
                <MacOSBadge variant="info">
                  Статус: {currentAppointment.status}
                </MacOSBadge>
              </div>

              {/* Временная шкала приема */}
              <VisitTimeline
                appointment={currentAppointment}
                emr={emr}
                prescription={prescription}
              />

              {/* EMR система */}
              <div style={{ marginTop: '24px' }}>
                <h4 style={{
                  fontSize: '16px',
                  fontWeight: '600',
                  marginBottom: '16px',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
                  display: 'flex',
                  alignItems: 'center'
                }}>
                  <FileText size={20} style={{ marginRight: '8px', color: 'var(--mac-blue-500)' }} />
                  Электронная медицинская карта
                </h4>
                <EMRSystem
                  appointment={currentAppointment}
                  emr={emr}
                  onSave={saveEMR}
                />
              </div>

              {/* Система рецептов */}
              {emr && !emr.is_draft && (
                <div style={{ marginTop: '24px' }}>
                  <h4 style={{
                    fontSize: '16px',
                    fontWeight: '600',
                    marginBottom: '16px',
                    color: 'var(--mac-text-primary)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
                    display: 'flex',
                    alignItems: 'center'
                  }}>
                    <TestTube size={20} style={{ marginRight: '8px', color: 'var(--mac-green-500)' }} />
                    Рецепт
                  </h4>
                  <PrescriptionSystem
                    appointment={currentAppointment}
                    emr={emr}
                    prescription={prescription}
                    onSave={savePrescription}
                  />
                </div>
              )}

              {/* Кнопка завершения приема */}
              {emr && !emr.is_draft && (
                <div style={{ marginTop: '24px', textAlign: 'center' }}>
                  <MacOSButton
                    onClick={completeVisit}
                    style={{ 
                      backgroundColor: 'var(--mac-green-500)',
                      color: 'white',
                      fontSize: '16px',
                      padding: '12px 32px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      margin: '0 auto'
                    }}
                  >
                    <CheckCircle size={20} />
                    Завершить прием
                  </MacOSButton>
                </div>
              )}
            </MacOSCard>
          </div>
        )}

        {/* Прием пациента - простая версия */}
        {activeTab === 'visit' && selectedPatient && !currentAppointment && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* Информация о пациенте */}
            <MacOSCard style={{ padding: '24px' }}>
              <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '20px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
                display: 'flex',
                alignItems: 'center'
              }}>
                <User size={20} style={{ marginRight: '8px', color: 'var(--mac-blue-500)' }} />
                Пациент #{selectedPatient.number}
              </h3>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                <div>
                  <label style={{
                    display: 'block',
                    fontSize: '13px',
                    fontWeight: '500',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: '6px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                    ФИО пациента
                  </label>
                  <div style={{
                    fontSize: '16px',
                    fontWeight: '600',
                    color: 'var(--mac-text-primary)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>{selectedPatient.patient_name}</div>
                </div>
                
                {selectedPatient.phone && (
                  <div>
                    <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                      Телефон
                    </label>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      <Phone size={16} style={{ marginRight: '8px', color: 'var(--mac-text-secondary)' }} />
                      <span style={{
                        fontSize: '16px',
                        fontWeight: '500',
                        color: 'var(--mac-text-primary)',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>{selectedPatient.phone}</span>
                    </div>
                  </div>
                )}
              </div>
            </MacOSCard>

            {/* Жалобы и диагноз */}
            <MacOSCard style={{ padding: '24px' }}>
              <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '20px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>📝 Жалобы и диагноз</h3>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div>
                  <label style={{
                    display: 'block',
                    fontSize: '13px',
                    fontWeight: '500',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: '6px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                    Жалобы пациента
                  </label>
                  <MacOSTextarea
                    value={visitData.complaint}
                    onChange={(e) => setVisitData({ ...visitData, complaint: e.target.value })}
                    rows={4}
                    placeholder="Опишите жалобы пациента..."
                  />
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                  <div>
                    <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                      Диагноз
                    </label>
                    <MacOSInput
                      type="text"
                      value={visitData.diagnosis}
                      onChange={(e) => setVisitData({ ...visitData, diagnosis: e.target.value })}
                      placeholder="Диагноз"
                    />
                  </div>

                  <div>
                    <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                      МКБ-10
                    </label>
                    <MacOSInput
                      type="text"
                      value={visitData.icd10}
                      onChange={(e) => setVisitData({ ...visitData, icd10: e.target.value })}
                      placeholder="L70.9"
                    />
                  </div>
                </div>

                <div>
                  <label style={{
                    display: 'block',
                    fontSize: '13px',
                    fontWeight: '500',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: '6px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                    Примечания
                  </label>
                  <MacOSTextarea
                    value={visitData.notes}
                    onChange={(e) => setVisitData({ ...visitData, notes: e.target.value })}
                    rows={3}
                    placeholder="Дополнительные примечания..."
                  />
                </div>
              </div>
            </MacOSCard>

            {/* Услуги визита */}
            <DoctorServiceSelector
              specialty="dermatology"
              selectedServices={selectedServices}
              onServicesChange={setSelectedServices}
              canEditPrices={true}
            />

            {/* EMR система */}
            {currentAppointment && (
              <MacOSCard style={{ padding: '24px' }}>
                <h3 style={{
                  fontSize: '18px',
                  fontWeight: '600',
                  marginBottom: '20px',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif',
                  display: 'flex',
                  alignItems: 'center'
                }}>
                  <FileText size={20} style={{ marginRight: '8px', color: 'var(--mac-blue-500)' }} />
                  Электронная медицинская карта
                </h3>
                <EMRSystem
                  appointment={currentAppointment}
                  emr={emr}
                  onSave={saveEMR}
                />
              </MacOSCard>
            )}

            {/* Система рецептов */}
            {currentAppointment && emr && !emr.is_draft && (
              <MacOSCard style={{ padding: '24px' }}>
                <h3 className="text-lg font-medium mb-4 flex items-center">
                  <TestTube size={20} className="mr-2 text-green-600" />
                  Рецепт
                </h3>
                <PrescriptionSystem
                  appointment={currentAppointment}
                  emr={emr}
                  prescription={prescription}
                  onSave={savePrescription}
                />
              </MacOSCard>
            )}

            {/* Действия */}
            <MacOSCard style={{ padding: '24px' }}>
              <div className="flex justify-end space-x-3">
                <MacOSButton
                  variant="outline"
                  onClick={() => {
                    setSelectedPatient(null);
                    handleTabChange('queue');
                  }}
                >
                  Отменить
                </MacOSButton>
                {currentAppointment && emr && !emr.is_draft ? (
                  <MacOSButton
                    onClick={completeVisit}
                    className="bg-green-600 hover:bg-green-700"
                  >
                    <CheckCircle size={16} className="mr-2" />
                    Завершить прием
                  </MacOSButton>
                ) : (
                  <MacOSButton
                    onClick={handleSaveVisit}
                    disabled={loading || !visitData.complaint}
                  >
                    {loading ? (
                      <RefreshCw size={16} className="animate-spin mr-2" />
                    ) : (
                      <Save size={16} className="mr-2" />
                    )}
                    Завершить прием
                  </MacOSButton>
                )}
              </div>
            </MacOSCard>
          </div>
        )}

        {/* Фото до/после */}
        {activeTab === 'photos' && (currentAppointment || selectedPatient) && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <MacOSCard style={{ padding: '24px' }}>
              <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '20px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>
                Загрузить фото
              </h3>
              {/* Загрузчик фото с HEIC поддержкой */}
              <PhotoUploader
                visitId={currentAppointment?.id || selectedPatient?.visitId || 'demo-visit-1'}
                patientId={currentAppointment?.patient_id || selectedPatient?.patient?.id || 'demo-patient-1'}
                onDataUpdate={() => {
                  console.log('Фото обновлены');
                  loadPatientData();
                }}
              />
            </MacOSCard>
            
            <MacOSCard style={{ padding: '24px' }}>
              <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '20px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>
                AI анализ кожи
              </h3>
              {/* AI анализ кожи */}
              <SkinAnalysis
                photos={photoData}
                visitId={currentAppointment?.id || selectedPatient?.visitId || 'demo-visit-1'}
                patientId={currentAppointment?.patient_id || selectedPatient?.patient?.id || 'demo-patient-1'}
                onAnalysisComplete={(result) => {
                  console.log('AI анализ завершен:', result);
                }}
              />
            </MacOSCard>

            <MacOSCard style={{ padding: '24px' }}>
              <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '20px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>
                Сравнение «до» и «после»
              </h3>
              {/* Сравнение фото до и после */}
              <PhotoComparison
                photos={photoData}
                visitId={currentAppointment?.id || selectedPatient?.visitId || 'demo-visit-1'}
                patientId={currentAppointment?.patient_id || selectedPatient?.patient?.id || 'demo-patient-1'}
                onComparisonComplete={(result) => {
                  console.log('Сравнение завершено:', result);
                }}
              />
            </MacOSCard>
          </div>
        )}

        {activeTab === 'photos' && !currentAppointment && !selectedPatient && (
          <MacOSCard style={{ padding: '48px', textAlign: 'center' }}>
            <MacOSEmptyState
              type="image"
              title="Выберите пациента"
              description="Перейдите на вкладку 'Очередь' и выберите пациента для просмотра фото"
              action={
                <MacOSButton variant="outline" onClick={() => handleTabChange('queue')} style={{ marginTop: '16px' }}>
                  Перейти к очереди
                </MacOSButton>
              }
            />
          </MacOSCard>
        )}

        {/* Осмотр кожи */}
        {activeTab === 'skin' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <MacOSCard style={{ padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{
                  fontSize: '18px',
                  fontWeight: '600',
                  display: 'flex',
                  alignItems: 'center',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
                }}>
                  <Activity size={20} style={{ marginRight: '8px', color: 'var(--mac-green-500)' }} />
                  Осмотры кожи
                </h3>
                <MacOSButton onClick={() => setShowSkinForm(true)}>
                  <Plus size={16} style={{ marginRight: '6px' }} />
                  Новый осмотр
                </MacOSButton>
              </div>

              {skinExaminations.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {skinExaminations.map((exam) => (
                    <div key={exam.id} style={{
                      border: '1px solid var(--mac-border)',
                      borderRadius: '8px',
                      padding: '16px',
                      backgroundColor: 'var(--mac-bg-secondary)'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                        <h4 style={{
                          fontWeight: '600',
                          fontSize: '16px',
                          color: 'var(--mac-text-primary)',
                          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                        }}>Осмотр #{exam.id}</h4>
                        <MacOSBadge variant="info">{exam.examination_date}</MacOSBadge>
                      </div>
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                        gap: '16px',
                        fontSize: '14px',
                        color: 'var(--mac-text-secondary)',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                        <div>🧴 Тип кожи: {exam.skin_type}</div>
                        <div>📈 Состояние: {exam.skin_condition}</div>
                        <div>🎯 Поражения: {exam.lesions}</div>
                        <div>📍 Распространение: {exam.distribution}</div>
                      </div>
                      {exam.diagnosis && (
                        <div style={{
                          marginTop: '8px',
                          fontSize: '14px',
                          color: 'var(--mac-text-primary)',
                          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                        }}>
                          <strong>Диагноз:</strong> {exam.diagnosis}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <MacOSEmptyState
                  type="doc"
                  title="Нет данных осмотров кожи"
                  description="Добавьте новый осмотр кожи для пациента"
                />
              )}
            </MacOSCard>

            {/* Форма осмотра кожи */}
            {showSkinForm && (
              <MacOSCard style={{ padding: '24px' }}>
                <h3 style={{
                  fontSize: '18px',
                  fontWeight: '600',
                  marginBottom: '16px',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
                }}>Новый осмотр кожи</h3>
                <form onSubmit={handleSkinExaminationSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
                    <div>
                      <label style={{
                        display: 'block',
                        fontSize: '13px',
                        fontWeight: '500',
                        color: 'var(--mac-text-secondary)',
                        marginBottom: '6px',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                        Дата осмотра *
                      </label>
                      <MacOSInput
                        type="date"
                        value={skinExamination.examination_date}
                        onChange={(e) => setSkinExamination({ ...skinExamination, examination_date: e.target.value })}
                        required
                      />
                    </div>
                    <div>
                      <label style={{
                        display: 'block',
                        fontSize: '13px',
                        fontWeight: '500',
                        color: 'var(--mac-text-secondary)',
                        marginBottom: '6px',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                        Тип кожи *
                      </label>
                      <MacOSSelect
                        value={skinExamination.skin_type}
                        onChange={(e) => setSkinExamination({ ...skinExamination, skin_type: e.target.value })}
                        required
                      >
                        <option value="">Выберите тип кожи</option>
                        <option value="normal">Нормальная</option>
                        <option value="dry">Сухая</option>
                        <option value="oily">Жирная</option>
                        <option value="combination">Комбинированная</option>
                        <option value="sensitive">Чувствительная</option>
                      </MacOSSelect>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
                    <div>
                      <label style={{
                        display: 'block',
                        fontSize: '13px',
                        fontWeight: '500',
                        color: 'var(--mac-text-secondary)',
                        marginBottom: '6px',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                        Состояние кожи
                      </label>
                      <MacOSInput
                        type="text"
                        value={skinExamination.skin_condition}
                        onChange={(e) => setSkinExamination({ ...skinExamination, skin_condition: e.target.value })}
                        placeholder="Хорошее, удовлетворительное, проблемное"
                      />
                    </div>
                    <div>
                      <label style={{
                        display: 'block',
                        fontSize: '13px',
                        fontWeight: '500',
                        color: 'var(--mac-text-secondary)',
                        marginBottom: '6px',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                        Поражения
                      </label>
                      <MacOSInput
                        type="text"
                        value={skinExamination.lesions}
                        onChange={(e) => setSkinExamination({ ...skinExamination, lesions: e.target.value })}
                        placeholder="Акне, пигментация, родинки"
                      />
                    </div>
                  </div>

                  <div>
                    <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                      Диагноз
                    </label>
                    <MacOSInput
                      type="text"
                      value={skinExamination.diagnosis}
                      onChange={(e) => setSkinExamination({ ...skinExamination, diagnosis: e.target.value })}
                      placeholder="Диагноз"
                    />
                  </div>

                  <div>
                    <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                      План лечения
                    </label>
                    <MacOSTextarea
                      value={skinExamination.treatment_plan}
                      onChange={(e) => setSkinExamination({ ...skinExamination, treatment_plan: e.target.value })}
                      rows={4}
                      placeholder="План лечения и рекомендации"
                    />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                    <MacOSButton
                      type="button"
                      variant="outline"
                      onClick={() => setShowSkinForm(false)}
                    >
                      Отмена
                    </MacOSButton>
                    <MacOSButton type="submit">
                      <Save size={16} style={{ marginRight: '6px' }} />
                      Сохранить осмотр
                    </MacOSButton>
                  </div>
                </form>
              </MacOSCard>
            )}
          </div>
        )}

        {/* Косметология */}
        {activeTab === 'cosmetic' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <MacOSCard style={{ padding: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{
                  fontSize: '18px',
                  fontWeight: '600',
                  display: 'flex',
                  alignItems: 'center',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
                }}>
                  <Sparkles size={20} style={{ marginRight: '8px', color: 'var(--mac-pink-500)' }} />
                  Косметические процедуры
                </h3>
                <MacOSButton onClick={() => setShowCosmeticForm(true)}>
                  <Plus size={16} style={{ marginRight: '6px' }} />
                  Новая процедура
                </MacOSButton>
              </div>

              {cosmeticProcedures.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {cosmeticProcedures.map((procedure) => (
                    <div key={procedure.id} style={{
                      border: '1px solid var(--mac-border)',
                      borderRadius: '8px',
                      padding: '16px',
                      backgroundColor: 'var(--mac-bg-secondary)'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                        <h4 style={{
                          fontWeight: '600',
                          fontSize: '16px',
                          color: 'var(--mac-text-primary)',
                          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                        }}>Процедура #{procedure.id}</h4>
                        <MacOSBadge variant="info">{procedure.procedure_date}</MacOSBadge>
                      </div>
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                        gap: '16px',
                        fontSize: '14px',
                        color: 'var(--mac-text-secondary)',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                        <div>✨ Тип: {procedure.procedure_type}</div>
                        <div>📍 Область: {procedure.area_treated}</div>
                        <div>🧴 Продукты: {procedure.products_used}</div>
                      </div>
                      {procedure.results && (
                        <div style={{
                          marginTop: '8px',
                          fontSize: '14px',
                          color: 'var(--mac-text-primary)',
                          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                        }}>
                          <strong>Результаты:</strong> {procedure.results}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <MacOSEmptyState
                  type="doc"
                  title="Нет данных косметических процедур"
                  description="Добавьте новую косметическую процедуру для пациента"
                />
              )}
            </MacOSCard>

            {/* Форма косметической процедуры */}
            {showCosmeticForm && (
              <MacOSCard style={{ padding: '24px' }}>
                <h3 style={{
                  fontSize: '18px',
                  fontWeight: '600',
                  marginBottom: '16px',
                  color: 'var(--mac-text-primary)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
                }}>Новая косметическая процедура</h3>
                <form onSubmit={handleCosmeticProcedureSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
                    <div>
                      <label style={{
                        display: 'block',
                        fontSize: '13px',
                        fontWeight: '500',
                        color: 'var(--mac-text-secondary)',
                        marginBottom: '6px',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                        Дата процедуры *
                      </label>
                      <MacOSInput
                        type="date"
                        value={cosmeticProcedure.procedure_date}
                        onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, procedure_date: e.target.value })}
                        required
                      />
                    </div>
                    <div>
                      <label style={{
                        display: 'block',
                        fontSize: '13px',
                        fontWeight: '500',
                        color: 'var(--mac-text-secondary)',
                        marginBottom: '6px',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                        Тип процедуры *
                      </label>
                      <MacOSSelect
                        value={cosmeticProcedure.procedure_type}
                        onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, procedure_type: e.target.value })}
                        required
                      >
                        <option value="">Выберите процедуру</option>
                        <option value="cleaning">Чистка лица</option>
                        <option value="peeling">Пилинг</option>
                        <option value="botox">Ботокс</option>
                        <option value="filler">Филлеры</option>
                        <option value="laser">Лазерная терапия</option>
                        <option value="mesotherapy">Мезотерапия</option>
                      </MacOSSelect>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
                    <div>
                      <label style={{
                        display: 'block',
                        fontSize: '13px',
                        fontWeight: '500',
                        color: 'var(--mac-text-secondary)',
                        marginBottom: '6px',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                        Область обработки
                      </label>
                      <MacOSInput
                        type="text"
                        value={cosmeticProcedure.area_treated}
                        onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, area_treated: e.target.value })}
                        placeholder="Лицо, шея, декольте"
                      />
                    </div>
                    <div>
                      <label style={{
                        display: 'block',
                        fontSize: '13px',
                        fontWeight: '500',
                        color: 'var(--mac-text-secondary)',
                        marginBottom: '6px',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                        Использованные продукты
                      </label>
                      <MacOSInput
                        type="text"
                        value={cosmeticProcedure.products_used}
                        onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, products_used: e.target.value })}
                        placeholder="Названия препаратов"
                      />
                    </div>
                  </div>

                  <div>
                    <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                      Результаты
                    </label>
                    <MacOSTextarea
                      value={cosmeticProcedure.results}
                      onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, results: e.target.value })}
                      rows={4}
                      placeholder="Описание результатов процедуры"
                    />
                  </div>

                  <div>
                    <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '6px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                      Рекомендации по уходу
                    </label>
                    <MacOSTextarea
                      value={cosmeticProcedure.follow_up}
                      onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, follow_up: e.target.value })}
                      rows={3}
                      placeholder="Рекомендации по уходу после процедуры"
                    />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                    <MacOSButton
                      type="button"
                      variant="outline"
                      onClick={() => setShowCosmeticForm(false)}
                    >
                      Отмена
                    </MacOSButton>
                    <MacOSButton type="submit">
                      <Save size={16} style={{ marginRight: '6px' }} />
                      Сохранить процедуру
                    </MacOSButton>
                  </div>
                </form>
              </MacOSCard>
            )}
          </div>
        )}

        {/* AI Помощник */}
        {activeTab === 'ai' && (
          <AIAssistant
            specialty="dermatology"
            onSuggestionSelect={handleAISuggestion}
          />
        )}

        {/* Управление услугами */}
        {activeTab === 'services' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <MacOSCard style={{ padding: '24px' }}>
              <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '16px',
                display: 'flex',
                alignItems: 'center',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>
                <Scissors size={20} style={{ marginRight: '8px', color: 'var(--mac-orange-600)' }} />
                Услуги дерматологии и косметологии
              </h3>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <label style={{
                    display: 'block',
                    fontSize: '13px',
                    fontWeight: '500',
                    color: 'var(--mac-text-secondary)',
                    marginBottom: '8px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                    Выбор услуг
                  </label>
                  
                  {/* Шаблоны процедур */}
                  <ProcedureTemplates
                    visitId={selectedPatient?.visitId || 'demo-visit-1'}
                    onSelectProcedure={(procedure) => {
                      console.log('Выбрана процедура:', procedure);
                      // Добавляем процедуру в список услуг
                      setSelectedServices(prev => [...prev, {
                        id: Date.now(),
                        name: procedure.name,
                        price: procedure.price,
                        duration: procedure.duration,
                      }]);
                    }}
                  />
                  
                  <div style={{ marginTop: '16px' }}>
                    <ServiceChecklist
                      value={selectedServices}
                      onChange={setSelectedServices}
                      department="derma"
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
                  <div>
                    <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '8px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                      Стоимость от врача (UZS)
                    </label>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <div style={{ position: 'relative', flex: '1' }}>
                        <DollarSign size={16} style={{
                          position: 'absolute',
                          left: '12px',
                          top: '50%',
                          transform: 'translateY(-50%)',
                          color: 'var(--mac-text-secondary)'
                        }} />
                        <MacOSInput
                          type="text"
                          value={doctorPrice}
                          onChange={(e) => setDoctorPrice(e.target.value)}
                          placeholder="Например: 50000"
                          inputMode="numeric"
                          style={{ paddingLeft: '40px' }}
                        />
                      </div>
                      <MacOSButton
                        onClick={() => {
                          if (selectedServices.length > 0) {
                            setSelectedServiceForPriceOverride({
                              id: selectedServices[0].id || 1,
                              name: selectedServices[0].name || 'Выбранная услуга',
                              price: selectedServices[0].price || 50000
                            });
                            setShowPriceOverride(true);
                          } else {
                            alert('Сначала выберите услугу');
                          }
                        }}
                        variant="primary"
                        title="Изменить цену процедуры"
                      >
                        <DollarSign size={16} />
                      </MacOSButton>
                    </div>
                  </div>
                  
                  <div>
                    <label style={{
                      display: 'block',
                      fontSize: '13px',
                      fontWeight: '500',
                      color: 'var(--mac-text-secondary)',
                      marginBottom: '8px',
                      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                    }}>
                      Итого к оплате
                    </label>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      height: '40px',
                      padding: '0 12px',
                      border: '2px dashed var(--mac-border)',
                      borderRadius: '8px',
                      backgroundColor: 'var(--mac-bg-secondary)'
                    }}>
                      <span style={{
                        fontSize: '18px',
                        fontWeight: '600',
                        color: 'var(--mac-text-primary)',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                        {totalCost.toLocaleString()} UZS
                      </span>
                      <span style={{
                        marginLeft: '8px',
                        fontSize: '13px',
                        color: 'var(--mac-text-secondary)',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                      }}>
                        (услуги: {servicesSubtotal.toLocaleString()} UZS
                        {doctorPriceNum ? `, врач: ${doctorPriceNum.toLocaleString()} UZS` : ''})
                      </span>
                    </div>
                  </div>
                </div>

                <div style={{
                  backgroundColor: 'var(--mac-blue-50)',
                  padding: '16px',
                  borderRadius: '8px',
                  border: '1px solid var(--mac-blue-200)'
                }}>
                  <h4 style={{
                    fontWeight: '600',
                    fontSize: '14px',
                    color: 'var(--mac-blue-900)',
                    marginBottom: '8px',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                    💡 Справочник цен
                  </h4>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: '8px',
                    fontSize: '13px',
                    color: 'var(--mac-blue-800)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                    <div>• Консультация: 50,000 UZS</div>
                    <div>• Биопсия: 150,000 UZS</div>
                    <div>• Чистка лица: 80,000 UZS</div>
                    <div>• Ботокс: 300,000 UZS</div>
                    <div>• Лазер: 250,000 UZS</div>
                    <div>• + стоимость от врача</div>
                  </div>
                </div>
              </div>
            </MacOSCard>
          </div>
        )}

        {/* История */}
        {activeTab === 'history' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <MacOSCard style={{ padding: '24px' }}>
              <h3 style={{
                fontSize: '18px',
                fontWeight: '600',
                marginBottom: '16px',
                display: 'flex',
                alignItems: 'center',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>
                <Calendar size={20} style={{ marginRight: '8px', color: 'var(--mac-text-secondary)' }} />
                История приемов и процедур
              </h3>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '24px' }}>
                {/* История осмотров кожи */}
                <div>
                  <h4 style={{
                    fontWeight: '600',
                    fontSize: '14px',
                    marginBottom: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    color: 'var(--mac-text-primary)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                    <Activity size={16} style={{ marginRight: '8px', color: 'var(--mac-green-600)' }} />
                    Осмотры кожи ({skinExaminations.length})
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '400px', overflowY: 'auto' }}>
                    {skinExaminations.map((exam) => (
                      <div key={exam.id} style={{
                        border: '1px solid var(--mac-border)',
                        borderRadius: '8px',
                        padding: '12px',
                        fontSize: '13px',
                        backgroundColor: 'var(--mac-bg-secondary)'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                          <span style={{
                            fontWeight: '600',
                            fontSize: '14px',
                            color: 'var(--mac-text-primary)',
                            fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                          }}>#{exam.id}</span>
                          <MacOSBadge variant="info">{exam.examination_date}</MacOSBadge>
                        </div>
                        <div style={{
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '4px',
                          fontSize: '13px',
                          color: 'var(--mac-text-secondary)',
                          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                        }}>
                          <div>🧴 {exam.skin_type} • {exam.skin_condition}</div>
                          <div>🎯 {exam.lesions}</div>
                          {exam.diagnosis && <div>📋 {exam.diagnosis}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* История косметических процедур */}
                <div>
                  <h4 style={{
                    fontWeight: '600',
                    fontSize: '14px',
                    marginBottom: '12px',
                    display: 'flex',
                    alignItems: 'center',
                    color: 'var(--mac-text-primary)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                  }}>
                    <Sparkles size={16} style={{ marginRight: '8px', color: 'var(--mac-pink-600)' }} />
                    Косметические процедуры ({cosmeticProcedures.length})
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '400px', overflowY: 'auto' }}>
                    {cosmeticProcedures.map((procedure) => (
                      <div key={procedure.id} style={{
                        border: '1px solid var(--mac-border)',
                        borderRadius: '8px',
                        padding: '12px',
                        fontSize: '13px',
                        backgroundColor: 'var(--mac-bg-secondary)'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                          <span style={{
                            fontWeight: '600',
                            fontSize: '14px',
                            color: 'var(--mac-text-primary)',
                            fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                          }}>#{procedure.id}</span>
                          <MacOSBadge variant="info">{procedure.procedure_date}</MacOSBadge>
                        </div>
                        <div style={{
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '4px',
                          fontSize: '13px',
                          color: 'var(--mac-text-secondary)',
                          fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
                        }}>
                          <div>✨ {procedure.procedure_type}</div>
                          <div>📍 {procedure.area_treated}</div>
                          {procedure.results && <div>📊 {procedure.results}</div>}
                          {procedure.total_cost && (
                            <div style={{
                              fontWeight: '600',
                              fontSize: '14px',
                              color: 'var(--mac-green-600)',
                              marginTop: '4px'
                            }}>
                              💰 {Number(procedure.total_cost).toLocaleString()} UZS
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {skinExaminations.length === 0 && cosmeticProcedures.length === 0 && (
                <MacOSEmptyState
                  type="calendar"
                  title="Нет данных о приемах и процедурах"
                  description="История приемов и процедур будет отображаться здесь"
                />
              )}
            </MacOSCard>
          </div>
        )}
      </div>
      
      {/* PriceOverrideManager Modal */}
      {showPriceOverride && selectedServiceForPriceOverride && (
        <PriceOverrideManager
          visitId={selectedPatient?.id || 1} // Используем ID пациента как visitId для демо
          serviceId={selectedServiceForPriceOverride.id}
          serviceName={selectedServiceForPriceOverride.name}
          originalPrice={selectedServiceForPriceOverride.price}
          isOpen={showPriceOverride}
          onClose={() => {
            setShowPriceOverride(false);
            setSelectedServiceForPriceOverride(null);
          }}
          onPriceOverrideCreated={(override) => {
            console.log('Price override created:', override);
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
          specialtyFilter="dermatology"
        />
      )}
      </div>
    </div>
  );
};

export default DermatologistPanelUnified;
