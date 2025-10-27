import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Heart,
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
  TestTube
} from 'lucide-react';
import { 
  MacOSCard, 
  MacOSButton, 
  MacOSBadge, 
  MacOSLoadingSkeleton,
  MacOSEmptyState,
  MacOSInput,
  MacOSTextarea,
  MacOSCheckbox,
  Icon 
} from '../components/ui/macos';
import { useTheme } from '../contexts/ThemeContext';
import QueueIntegration from '../components/QueueIntegration';
import DoctorServiceSelector from '../components/doctor/DoctorServiceSelector';
import AIAssistant from '../components/ai/AIAssistant';
import ECGViewer from '../components/cardiology/ECGViewer';
import EchoForm from '../components/cardiology/EchoForm';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';

/**
 * Унифицированная панель кардиолога
 * Объединяет: очередь + специализированные функции + AI + ЭКГ/ЭхоКГ
 */
const MacOSCardiologistPanelUnified = () => {
  // Всегда вызываем хуки первыми
  const { theme, isDark, getColor, getSpacing, getFontSize, getShadow } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();

  // Получаем активную вкладку из URL параметров
  const getInitialTab = () => {
    const params = new URLSearchParams(location.search);
    return params.get('tab') || 'queue';
  };

  const [activeTab, setActiveTab] = useState(getInitialTab);
  const [selectedPatient, setSelectedPatient] = useState(null);
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
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settings, setSettings] = useState({ ldlThreshold: 100, showEcgEchoTogether: true });
  
  // Состояния для таблицы записей
  const [appointments, setAppointments] = useState([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);

  // Специализированные данные кардиолога
  const [ecgForm, setEcgForm] = useState({
    patient_id: '',
    ecg_date: '',
    rhythm: '',
    heart_rate: '',
    pr_interval: '',
    qrs_duration: '',
    qt_interval: '',
    st_segment: '',
    t_wave: '',
    interpretation: '',
    recommendations: ''
  });

  const [bloodTestForm, setBloodTestForm] = useState({
    patient_id: '',
    test_date: '',
    cholesterol_total: '',
    cholesterol_hdl: '',
    cholesterol_ldl: '',
    triglycerides: '',
    glucose: '',
    crp: '',
    troponin: '',
    interpretation: ''
  });

  const [showForm, setShowForm] = useState({ open: false, type: 'blood' });
  const [ecgResults, setEcgResults] = useState([]);
  const [bloodTests, setBloodTests] = useState([]);

  // Вкладки панели
  const tabs = [
    { id: 'queue', label: 'Очередь', icon: Users, color: 'text-blue-600' },
    { id: 'appointments', label: 'Записи', icon: Calendar, color: 'text-green-600' },
    { id: 'visit', label: 'Прием', icon: Heart, color: 'text-red-600' },
    { id: 'ecg', label: 'ЭКГ', icon: Activity, color: 'text-green-600' },
    { id: 'blood', label: 'Анализы', icon: TestTube, color: 'text-purple-600' },
    { id: 'ai', label: 'AI Помощник', icon: Brain, color: 'text-indigo-600' },
    { id: 'services', label: 'Услуги', icon: Stethoscope, color: 'text-orange-600' },
    { id: 'history', label: 'История', icon: FileText, color: 'text-gray-600' }
  ];

  useEffect(() => {
    if (selectedPatient) {
      loadPatientData();
    }
  }, [selectedPatient]);

  // Отслеживаем изменения URL для синхронизации активной вкладки
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const tabParam = params.get('tab');
    if (tabParam && tabParam !== activeTab) {
      setActiveTab(tabParam);
    }
  }, [location.search, activeTab]);

  // Смена вкладки с синхронизацией URL
  const goToTab = (tabId) => {
    if (!tabId) return;
    setActiveTab(tabId);
    const params = new URLSearchParams(location.search);
    params.set('tab', tabId);
    navigate({ pathname: location.pathname, search: params.toString() }, { replace: true });
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

  // Загрузка записей кардиолога
  const loadMacOSCardiologyAppointments = async () => {
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

        // Фильтруем только кардиологические записи для отображения
        const appointmentsData = allAppointments.filter(apt => 
          apt.specialty === 'cardio' || apt.specialty === 'cardiology'
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
      console.error('Ошибка загрузки записей кардиолога:', error);
    } finally {
      setAppointmentsLoading(false);
    }
  };

  // Загружаем записи при переключении на вкладку
  useEffect(() => {
    if (activeTab === 'appointments') {
      loadMacOSCardiologyAppointments();
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
      goToTab('visit');
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
      case 'schedule_next':
        // Назначить следующий визит
        setScheduleNextModal({ open: true, patient: row });
        break;
      default:
        break;
    }
  };

  // Проверяем демо-режим после всех хуков
  const isDemoMode = window.location.pathname.includes('/medilab-demo');
  
  // В демо-режиме не рендерим компонент
  if (isDemoMode) {
    console.log('MacOSCardiologistPanelUnified: Skipping render in demo mode');
    return null;
  }

  const loadPatientData = async () => {
    if (!selectedPatient?.patient?.id) return;
    
    try {
      // Загружаем ЭКГ пациента
      const ecgResponse = await fetch(`/api/v1/cardio/ecg?patient_id=${selectedPatient.patient.id}&limit=10`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (ecgResponse.ok) {
        const ecgData = await ecgResponse.json();
        setEcgResults(ecgData);
      }

      // Загружаем анализы крови пациента
      const bloodResponse = await fetch(`/api/v1/cardio/blood-tests?patient_id=${selectedPatient.patient.id}&limit=10`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (bloodResponse.ok) {
        const bloodData = await bloodResponse.json();
        setBloodTests(bloodData);
      }
    } catch (error) {
      console.error('Ошибка загрузки данных пациента:', error);
    }
  };

  // Обработка выбора пациента из очереди
  const handlePatientSelect = (patient) => {
    setSelectedPatient(patient);
    goToTab('visit');
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
        setActiveTab('queue');
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

  // Обработка ЭКГ
  const handleEcgSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('/api/v1/cardio/ecg', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(ecgForm)
      });

      if (response.ok) {
        setShowForm({ open: false, type: 'ecg' });
        setEcgForm({
          patient_id: '',
          ecg_date: '',
          rhythm: '',
          heart_rate: '',
          pr_interval: '',
          qrs_duration: '',
          qt_interval: '',
          st_segment: '',
          t_wave: '',
          interpretation: '',
          recommendations: ''
        });
        loadPatientData();
        setMessage({ type: 'success', text: 'ЭКГ сохранено успешно' });
      }
    } catch (error) {
      console.error('Ошибка сохранения ЭКГ:', error);
      setMessage({ type: 'error', text: 'Ошибка сохранения ЭКГ' });
    }
  };

  // Обработка анализов крови
  const handleBloodTestSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('/api/v1/cardio/blood-tests', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(bloodTestForm)
      });

      if (response.ok) {
        setShowForm({ open: false, type: 'blood' });
        setBloodTestForm({
          patient_id: '',
          test_date: '',
          cholesterol_total: '',
          cholesterol_hdl: '',
          cholesterol_ldl: '',
          triglycerides: '',
          glucose: '',
          crp: '',
          troponin: '',
          interpretation: ''
        });
        loadPatientData();
        setMessage({ type: 'success', text: 'Анализ крови сохранен успешно' });
      }
    } catch (error) {
      console.error('Ошибка сохранения анализа:', error);
      setMessage({ type: 'error', text: 'Ошибка сохранения анализа' });
    }
  };

  // Используем дизайн-систему вместо инлайновых стилей
  const pageStyle = {
    padding: getSpacing('lg'),
    width: '100%',
    minHeight: 'calc(100vh - 60px)',
    background: getColor('background'),
    color: getColor('text'),
    overflow: 'visible'
  };

  const headerStyle = {
    marginBottom: getSpacing('xl'),
    padding: getSpacing('lg'),
    background: getColor('surface'),
    borderRadius: '12px',
    border: `1px solid ${getColor('border')}`,
    boxShadow: getShadow('sm')
  };

  const tabStyle = {
    padding: `${getSpacing('sm')} ${getSpacing('lg')}`,
    border: 'none',
    background: 'transparent',
    cursor: 'pointer',
    fontSize: getFontSize('sm'),
    fontWeight: '500',
    color: getColor('textSecondary'),
    borderRadius: '8px',
    transition: 'all 0.2s ease',
    display: 'flex',
    alignItems: 'center',
    gap: getSpacing('sm')
  };

  const activeTabStyle = {
    ...tabStyle,
    background: getColor('danger', 500),
    color: 'white',
    boxShadow: `0 2px 4px ${getColor('danger', 500)}30`
  };

  return (
    <div style={{
      ...pageStyle,
      padding: 0,
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

      {/* Навигация по вкладкам удалена — управление через сайдбар и URL */}

      {/* Контент вкладок */}
      <div style={{
        width: '100%',
        maxWidth: 'none',
        overflow: 'visible',
        boxSizing: 'border-box',
        position: 'relative',
        zIndex: 1,
        display: 'block',
        gap: getSpacing('lg')
      }}>
        {/* Очередь пациентов */}
        {activeTab === 'queue' && (
          <div style={{ width: '100%', maxWidth: 'none', overflow: 'visible' }}>
            <QueueIntegration
              specialist="Кардиолог"
              onPatientSelect={handlePatientSelect}
              onStartVisit={(appointment) => {
                setSelectedPatient(appointment);
                goToTab('visit');
              }}
            />
          </div>
        )}

        {/* Записи кардиолога */}
        {activeTab === 'appointments' && (
          <div style={{
            width: '100%',
            maxWidth: 'none',
            display: 'flex',
            flexDirection: 'column',
            gap: getSpacing('xl')
          }}>
            <MacOSCard style={{
              width: '100%',
              maxWidth: '100%',
              minWidth: 0,
              boxSizing: 'border-box',
              overflow: 'hidden',
              padding: '24px'
            }}>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                marginBottom: '24px'
              }}>
                <h3 style={{
                  display: 'flex',
                  alignItems: 'center',
                  fontSize: 'var(--mac-font-size-lg)',
                  fontWeight: 'var(--mac-font-weight-semibold)',
                  color: 'var(--mac-text-primary)',
                  margin: 0
                }}>
                  <Calendar size={20} style={{
                    marginRight: '12px',
                    color: 'var(--mac-accent)'
                  }} />
                  Записи к кардиологу
                </h3>
                <div style={{ 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '12px'
                }}>
                  <MacOSBadge variant="info">
                    Всего: {appointments.length}
                  </MacOSBadge>
                  <MacOSButton 
                    variant="outline"
                    onClick={loadMacOSCardiologyAppointments}
                    disabled={appointmentsLoading}
                    style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      gap: '8px' 
                    }}
                  >
                    <RefreshCw size={16} />
                    Обновить
                  </MacOSButton>
                </div>
              </div>
              
              {appointmentsLoading ? (
                <MacOSLoadingSkeleton type="table" count={5} />
              ) : appointments.length === 0 ? (
                <MacOSEmptyState
                  type="calendar"
                  title="Записи не найдены"
                  description="В системе пока нет записей к кардиологу"
                />
              ) : (
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
              )}
            </MacOSCard>
          </div>
        )}

        {/* Прием пациента */}
        {activeTab === 'visit' && selectedPatient && (
          <div style={{
            width: '100%',
            maxWidth: 'none',
            overflow: 'visible',
            display: 'flex',
            flexDirection: 'column',
            gap: '24px'
          }}>
            {/* Информация о пациенте */}
            <MacOSCard style={{ padding: '24px' }}>
              <h3 style={{
                display: 'flex',
                alignItems: 'center',
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-semibold)',
                marginBottom: '20px',
                color: 'var(--mac-text-primary)',
                fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Display", system-ui, sans-serif'
              }}>
                <User size={20} style={{
                  marginRight: '8px',
                  color: 'var(--mac-blue-500)'
                }} />
                Пациент #{selectedPatient.number}
              </h3>
              
              <div style={{ 
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
                gap: '20px'
              }}>
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
                    fontWeight: '500',
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
                    <div style={{
                      display: 'flex',
                      alignItems: 'center'
                    }}>
                      <Phone size={16} style={{
                        marginRight: '6px',
                        color: 'var(--mac-text-secondary)'
                      }} />
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
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-semibold)',
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
                    placeholder="Опишите жалобы пациента..."
                    rows={4}
                    style={{
                      minHeight: '96px'
                    }}
                  />
                </div>

                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
                  gap: '20px'
                }}>
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
                      placeholder="I25.9"
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
                    placeholder="Дополнительные примечания..."
                    rows={3}
                    style={{
                      minHeight: '72px'
                    }}
                  />
                </div>
              </div>
            </MacOSCard>

            {/* Услуги визита */}
            <DoctorServiceSelector
              specialty="cardiology"
              selectedServices={selectedServices}
              onServicesChange={setSelectedServices}
              canEditPrices={true}
            />

            {/* Действия */}
            <MacOSCard style={{ padding: '24px' }}>
              <div className="flex justify-end" style={{ gap: '12px' }}>
                <MacOSButton
                  variant="outline"
                  onClick={() => {
                    setSelectedPatient(null);
                    setActiveTab('queue');
                  }}
                >
                  Отменить
                </MacOSButton>
                <MacOSButton
                  onClick={handleSaveVisit}
                  disabled={loading || !visitData.complaint}
                >
                  {loading ? (
                    <RefreshCw size={16} style={{ marginRight: '8px' }} />
                  ) : (
                    <Save size={16} style={{ marginRight: '8px' }} />
                  )}
                  Завершить прием
                </MacOSButton>
              </div>
            </MacOSCard>
          </div>
        )}

        {/* ЭКГ */}
        {activeTab === 'ecg' && (
          <div style={{
            width: '100%',
            maxWidth: 'none',
            overflow: 'visible',
            display: 'flex',
            flexDirection: 'column',
            gap: getSpacing('xl')
          }}>
            <div className="flex justify-end">
              <MacOSButton onClick={() => setShowForm({ open: true, type: 'ecg' })}>
                <Plus size={16} style={{ marginRight: '8px' }} /> Добавить ЭКГ
              </MacOSButton>
            </div>
            {/* Используем новые компоненты ЭКГ и ЭхоКГ */}
            <ECGViewer 
              visitId={selectedPatient?.visitId || 'demo-visit-1'}
              patientId={selectedPatient?.patient?.id || 'demo-patient-1'}
              onDataUpdate={() => {
                console.log('ЭКГ данные обновлены');
                loadPatientData();
              }}
            />
            
            <EchoForm
              visitId={selectedPatient?.visitId || 'demo-visit-1'}
              patientId={selectedPatient?.patient?.id || 'demo-patient-1'}
              onDataUpdate={() => {
                console.log('ЭхоКГ данные обновлены');
                loadPatientData();
              }}
            />
          </div>
        )}
        
        {/* Анализы крови */}
        {activeTab === 'blood' && (
          <div style={{
            width: '100%',
            maxWidth: 'none',
            overflow: 'visible',
            display: 'flex',
            flexDirection: 'column',
            gap: getSpacing('xl')
          }}>
            <MacOSCard style={{ padding: '24px' }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: getSpacing('lg')
              }}>
                <h3 style={{
                  display: 'flex',
                  alignItems: 'center',
                  fontSize: getFontSize('lg'),
                  fontWeight: '500',
                  color: getColor('text')
                }}>
                  <TestTube size={20} style={{
                    marginRight: getSpacing('sm'),
                    color: getColor('secondary', 600)
                  }} />
                  Анализы крови
                </h3>
                <MacOSButton onClick={() => setShowForm({ open: true, type: 'blood' })}>
                  <Plus size={16} style={{ marginRight: '8px' }} />
                  Новый анализ
                </MacOSButton>
              </div>

              {/* Небольшая аналитика по имеющимся анализам */}
              {bloodTests.length > 0 && (
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                  gap: getSpacing('lg'),
                  marginBottom: getSpacing('xl')
                }}>
                  {(() => {
                    const avg = (key) => {
                      const nums = bloodTests
                        .map(t => Number(t[key]))
                        .filter(v => !Number.isNaN(v));
                      if (nums.length === 0) return '—';
                      const sum = nums.reduce((a,b)=>a+b,0);
                      return Math.round((sum/nums.length) * 10) / 10;
                    };
                    const items = [
                      { label: 'Средний общий холестерин', value: avg('cholesterol_total'), unit: 'мг/дл' },
                      { label: 'Средний LDL', value: avg('cholesterol_ldl'), unit: 'мг/дл' },
                      { label: 'Средняя глюкоза', value: avg('glucose'), unit: 'мг/дл' },
                    ];
                    return items.map((it, idx) => (
                      <div key={idx} style={{
                        padding: getSpacing('md'),
                        border: `1px solid ${getColor('border')}`,
                        backgroundColor: getColor('surface'),
                        color: getColor('text'),
                        borderRadius: '8px'
                      }}>
                        <div style={{
                          fontSize: getFontSize('sm'),
                          color: getColor('textSecondary'),
                          marginBottom: getSpacing('xs')
                        }}>{it.label}</div>
                        <div style={{
                          fontSize: getFontSize('xl'),
                          fontWeight: '600',
                          color: getColor('text')
                        }}>{it.value} {typeof it.value === 'number' ? it.unit : ''}</div>
                      </div>
                    ));
                  })()}
                </div>
              )}

              {bloodTests.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('lg') }}>
                  {bloodTests.map((test) => (
                    <div key={test.id} style={{
                      padding: getSpacing('lg'),
                      border: `1px solid ${getColor('border')}`,
                      backgroundColor: getColor('surface'),
                      borderRadius: '8px'
                    }}>
                      <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        marginBottom: getSpacing('sm')
                      }}>
                        <h4 style={{
                          fontSize: getFontSize('base'),
                          fontWeight: '500',
                          color: getColor('text')
                        }}>Анализ #{test.id}</h4>
                        <MacOSBadge variant="info">{test.test_date}</MacOSBadge>
                      </div>
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
                        gap: getSpacing('lg'),
                        fontSize: getFontSize('sm'),
                        color: getColor('textSecondary'),
                        marginBottom: getSpacing('sm')
                      }}>
                        <div>🩸 Холестерин: {test.cholesterol_total} мг/дл</div>
                        <div>HDL: {test.cholesterol_hdl}</div>
                        <div>LDL: {test.cholesterol_ldl}</div>
                        <div>Триглицериды: {test.triglycerides}</div>
                      </div>
                      <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
                        gap: getSpacing('lg'),
                        fontSize: getFontSize('sm'),
                        color: getColor('textSecondary')
                      }}>
                        <div>🍬 Глюкоза: {test.glucose} мг/дл</div>
                        <div>CRP: {test.crp} мг/л</div>
                        <div>Тропонин: {test.troponin} нг/мл</div>
                      </div>
                      {test.interpretation && (
                        <div style={{
                          marginTop: getSpacing('sm'),
                          fontSize: getFontSize('sm'),
                          color: getColor('text')
                        }}>
                          <strong>Интерпретация:</strong> {test.interpretation}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{
                  textAlign: 'center',
                  padding: getSpacing('xl'),
                  color: getColor('textSecondary')
                }}>
                  <TestTube size={48} style={{
                    margin: '0 auto 16px',
                    color: getColor('textSecondary')
                  }} />
                  <p>Нет данных анализов</p>
                </div>
              )}
            </MacOSCard>

            {/* Форма анализа крови */}
            {showForm.open && showForm.type === 'blood' && (
              <MacOSCard style={{ padding: '24px' }}>
                <h3 style={{
                  fontSize: getFontSize('lg'),
                  fontWeight: '500',
                  marginBottom: getSpacing('lg'),
                  color: getColor('text')
                }}>Новый анализ крови</h3>
                <form onSubmit={handleBloodTestSubmit} style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: getSpacing('lg')
                }}>
                  <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: getSpacing('lg') }}>
                    <div>
                      <label className="block" style={{
                        fontSize: getFontSize('sm'),
                        fontWeight: '500',
                        color: getColor('textSecondary'),
                        marginBottom: getSpacing('sm')
                      }}>
                        Дата анализа *
                      </label>
                      <input
                        type="date"
                        value={bloodTestForm.test_date}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, test_date: e.target.value })}
                        className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white"
                        style={{
                          padding: `${getSpacing('sm')} ${getSpacing('md')}`,
                          border: `1px solid ${getColor('border')}`,
                          backgroundColor: getColor('surface'),
                          color: getColor('text'),
                          fontSize: getFontSize('base'),
                          borderRadius: '6px'
                        }}
                        required
                      />
                    </div>
                    <div>
                      <label className="block" style={{
                        fontSize: getFontSize('sm'),
                        fontWeight: '500',
                        color: getColor('textSecondary'),
                        marginBottom: getSpacing('sm')
                      }}>
                        Общий холестерин (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.cholesterol_total}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, cholesterol_total: e.target.value })}
                        className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white"
                        style={{
                          padding: `${getSpacing('sm')} ${getSpacing('md')}`,
                          border: `1px solid ${getColor('border')}`,
                          backgroundColor: getColor('surface'),
                          color: getColor('text'),
                          fontSize: getFontSize('base'),
                          borderRadius: '6px'
                        }}
                        placeholder="<200"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3" style={{ gap: getSpacing('lg') }}>
                    <div>
                      <label className="block" style={{
                        fontSize: getFontSize('sm'),
                        fontWeight: '500',
                        color: getColor('textSecondary'),
                        marginBottom: getSpacing('sm')
                      }}>
                        HDL холестерин (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.cholesterol_hdl}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, cholesterol_hdl: e.target.value })}
                        className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white"
                        style={{
                          padding: `${getSpacing('sm')} ${getSpacing('md')}`,
                          border: `1px solid ${getColor('border')}`,
                          backgroundColor: getColor('surface'),
                          color: getColor('text'),
                          fontSize: getFontSize('base'),
                          borderRadius: '6px'
                        }}
                        placeholder=">40"
                      />
                    </div>
                    <div>
                      <label className="block" style={{
                        fontSize: getFontSize('sm'),
                        fontWeight: '500',
                        color: getColor('textSecondary'),
                        marginBottom: getSpacing('sm')
                      }}>
                        LDL холестерин (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.cholesterol_ldl}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, cholesterol_ldl: e.target.value })}
                        className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white"
                        style={{
                          padding: `${getSpacing('sm')} ${getSpacing('md')}`,
                          border: `1px solid ${getColor('border')}`,
                          backgroundColor: getColor('surface'),
                          color: getColor('text'),
                          fontSize: getFontSize('base'),
                          borderRadius: '6px'
                        }}
                        placeholder="<100"
                      />
                    </div>
                    <div>
                      <label className="block" style={{
                        fontSize: getFontSize('sm'),
                        fontWeight: '500',
                        color: getColor('textSecondary'),
                        marginBottom: getSpacing('sm')
                      }}>
                        Триглицериды (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.triglycerides}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, triglycerides: e.target.value })}
                        className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white"
                        style={{
                          padding: `${getSpacing('sm')} ${getSpacing('md')}`,
                          border: `1px solid ${getColor('border')}`,
                          backgroundColor: getColor('surface'),
                          color: getColor('text'),
                          fontSize: getFontSize('base'),
                          borderRadius: '6px'
                        }}
                        placeholder="<150"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3" style={{ gap: getSpacing('lg') }}>
                    <div>
                      <label className="block" style={{
                        fontSize: getFontSize('sm'),
                        fontWeight: '500',
                        color: getColor('textSecondary'),
                        marginBottom: getSpacing('sm')
                      }}>
                        Глюкоза (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.glucose}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, glucose: e.target.value })}
                        className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white"
                        style={{
                          padding: `${getSpacing('sm')} ${getSpacing('md')}`,
                          border: `1px solid ${getColor('border')}`,
                          backgroundColor: getColor('surface'),
                          color: getColor('text'),
                          fontSize: getFontSize('base'),
                          borderRadius: '6px'
                        }}
                        placeholder="70-100"
                      />
                    </div>
                    <div>
                      <label className="block" style={{
                        fontSize: getFontSize('sm'),
                        fontWeight: '500',
                        color: getColor('textSecondary'),
                        marginBottom: getSpacing('sm')
                      }}>
                        CRP (мг/л)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.crp}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, crp: e.target.value })}
                        className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white"
                        style={{
                          padding: `${getSpacing('sm')} ${getSpacing('md')}`,
                          border: `1px solid ${getColor('border')}`,
                          backgroundColor: getColor('surface'),
                          color: getColor('text'),
                          fontSize: getFontSize('base'),
                          borderRadius: '6px'
                        }}
                        placeholder="<3.0"
                      />
                    </div>
                    <div>
                      <label className="block" style={{
                        fontSize: getFontSize('sm'),
                        fontWeight: '500',
                        color: getColor('textSecondary'),
                        marginBottom: getSpacing('sm')
                      }}>
                        Тропонин (нг/мл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.troponin}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, troponin: e.target.value })}
                        className="w-full rounded-md focus:outline-none focus:ring-2 dark:text-white"
                        style={{
                          padding: `${getSpacing('sm')} ${getSpacing('md')}`,
                          border: `1px solid ${getColor('border')}`,
                          backgroundColor: getColor('surface'),
                          color: getColor('text'),
                          fontSize: getFontSize('base'),
                          borderRadius: '6px'
                        }}
                        placeholder="<0.04"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block" style={{
                      fontSize: getFontSize('sm'),
                      fontWeight: '500',
                      color: getColor('textSecondary'),
                      marginBottom: getSpacing('sm')
                    }}>
                      Интерпретация
                    </label>
                    <MacOSTextarea
                      value={bloodTestForm.interpretation}
                      onChange={(e) => setBloodTestForm({ ...bloodTestForm, interpretation: e.target.value })}
                      placeholder="Интерпретация результатов анализов"
                      rows={4}
                    />
                  </div>

                  <div className="flex justify-end" style={{ gap: getSpacing('md') }}>
                    <MacOSButton
                      type="button"
                      variant="outline"
                      onClick={() => setShowForm({ open: false, type: 'blood' })}
                    >
                      Отмена
                    </MacOSButton>
                    <MacOSButton type="submit">
                      <Save size={16} style={{ marginRight: '8px' }} />
                      Сохранить анализ
                    </MacOSButton>
                  </div>
                </form>
              </MacOSCard>
            )}
          </div>
        )}

        {/* AI Помощник */}
        {activeTab === 'ai' && (
          <div style={{
            width: '100%',
            maxWidth: 'none',
            overflow: 'visible'
          }}>
            <AIAssistant
              specialty="cardiology"
              onSuggestionSelect={handleAISuggestion}
            />
          </div>
        )}

        {/* Управление услугами */}
        {activeTab === 'services' && (
          <div style={{
            width: '100%',
            maxWidth: 'none',
            overflow: 'visible'
          }}>
            <DoctorServiceSelector
              specialty="cardiology"
              selectedServices={[]}
              onServicesChange={() => {}}
              canEditPrices={false}
            />
          </div>
        )}

        {/* История (заглушка) */}
        {activeTab === 'history' && (
          <div style={{
            width: '100%',
            maxWidth: 'none',
            overflow: 'visible',
            display: 'flex',
            flexDirection: 'column',
            gap: getSpacing('xl')
          }}>
            {!selectedPatient ? (
              <MacOSCard style={{
                padding: getSpacing('xl'),
                textAlign: 'center'
              }}>
                <Calendar size={48} style={{
                  margin: '0 auto 16px',
                  color: getColor('textSecondary')
                }} />
                <h3 style={{
                  fontSize: getFontSize('lg'),
                  fontWeight: '500',
                  marginBottom: getSpacing('sm'),
                  color: getColor('text')
                }}>История</h3>
                <p style={{ color: getColor('textSecondary') }}>Выберите пациента в очереди или из записей</p>
              </MacOSCard>
            ) : (
              <>
                <MacOSCard style={{ padding: '24px' }}>
                  <h3 style={{
                    fontSize: getFontSize('lg'),
                    fontWeight: '500',
                    marginBottom: getSpacing('lg'),
                    color: getColor('text')
                  }}>Хронология записей пациента</h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('md') }}>
                    {bloodTests.length === 0 && ecgResults.length === 0 && (
                      <div style={{ color: getColor('textSecondary') }}>Нет данных по ЭКГ или анализам крови</div>
                    )}
                    {bloodTests.map((t) => (
                      <div key={`blood-${t.id}`} style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: getSpacing('md')
                      }}>
                        <div style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          backgroundColor: getColor('secondary', 500),
                          marginTop: getSpacing('sm')
                        }} />
                        <div>
                          <div style={{
                            fontSize: getFontSize('base'),
                            fontWeight: '500',
                            color: getColor('text')
                          }}>Анализ крови — {t.test_date}</div>
                          <div style={{
                            fontSize: getFontSize('sm'),
                            color: getColor('textSecondary')
                          }}>
                            Хол: {t.cholesterol_total}; LDL: {t.cholesterol_ldl}; Глюкоза: {t.glucose}
                          </div>
                        </div>
                      </div>
                    ))}
                    {ecgResults.map((e) => (
                      <div key={`ecg-${e.id || e.ecg_date}`} style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: getSpacing('md')
                      }}>
                        <div style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          backgroundColor: getColor('success', 500),
                          marginTop: getSpacing('sm')
                        }} />
                        <div>
                          <div style={{
                            fontSize: getFontSize('base'),
                            fontWeight: '500',
                            color: getColor('text')
                          }}>ЭКГ — {e.ecg_date || '—'}</div>
                          <div style={{
                            fontSize: getFontSize('sm'),
                            color: getColor('textSecondary')
                          }}>
                            Ритм: {e.rhythm || '—'}, ЧСС: {e.heart_rate || '—'}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </MacOSCard>

                <MacOSCard style={{ padding: '24px' }}>
                  <h3 style={{
                    fontSize: getFontSize('lg'),
                    fontWeight: '500',
                    marginBottom: getSpacing('lg'),
                    color: getColor('text')
                  }}>Сводка по пациенту</h3>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                    gap: getSpacing('lg')
                  }}>
                    <div style={{
                      padding: getSpacing('md'),
                      border: `1px solid ${getColor('border')}`,
                      backgroundColor: getColor('surface'),
                      borderRadius: '8px'
                    }}>
                      <div style={{
                        fontSize: getFontSize('sm'),
                        color: getColor('textSecondary'),
                        marginBottom: getSpacing('xs')
                      }}>Количество ЭКГ</div>
                      <div style={{
                        fontSize: getFontSize('xl'),
                        fontWeight: '600',
                        color: getColor('text')
                      }}>{ecgResults.length}</div>
                    </div>
                    <div style={{
                      padding: getSpacing('md'),
                      border: `1px solid ${getColor('border')}`,
                      backgroundColor: getColor('surface'),
                      borderRadius: '8px'
                    }}>
                      <div style={{
                        fontSize: getFontSize('sm'),
                        color: getColor('textSecondary'),
                        marginBottom: getSpacing('xs')
                      }}>Количество анализов</div>
                      <div style={{
                        fontSize: getFontSize('xl'),
                        fontWeight: '600',
                        color: getColor('text')
                      }}>{bloodTests.length}</div>
                    </div>
                    <div style={{
                      padding: getSpacing('md'),
                      border: `1px solid ${getColor('border')}`,
                      backgroundColor: getColor('surface'),
                      borderRadius: '8px'
                    }}>
                      <div style={{
                        fontSize: getFontSize('sm'),
                        color: getColor('textSecondary'),
                        marginBottom: getSpacing('xs')
                      }}>Выбранный пациент</div>
                      <div style={{
                        fontSize: getFontSize('xl'),
                        fontWeight: '600',
                        color: getColor('text')
                      }}>{selectedPatient?.patient_name || '—'}</div>
                    </div>
                  </div>
                </MacOSCard>
              </>
            )}
          </div>
        )}
      </div>

      {/* Модальное окно Schedule Next */}
      {scheduleNextModal.open && (
        <ScheduleNextModal
          isOpen={scheduleNextModal.open}
          onClose={() => setScheduleNextModal({ open: false, patient: null })}
          patient={scheduleNextModal.patient}
          theme={{ isDark, getColor, getSpacing, getFontSize }}
          specialtyFilter="cardiology"
        />
      )}

      {/* Настройки кардиолога: плавающая кнопка и панель */}
      <button
        onClick={() => setSettingsOpen(true)}
        style={{
          position: 'fixed',
          right: 16,
          bottom: 16,
          background: getColor('surface'),
          border: `1px solid ${getColor('border')}`,
          borderRadius: '9999px',
          padding: getSpacing('md'),
          boxShadow: getShadow('lg')
        }}
        aria-label="Открыть настройки"
      >
        <Settings size={18} />
      </button>
      {settingsOpen && (
        <MacOSCard style={{
          padding: '24px',
          position: 'fixed',
          right: 16,
          bottom: 80,
          width: 360,
          backgroundColor: getColor('surface'),
          border: `1px solid ${getColor('border')}`,
          boxShadow: getShadow('xl')
        }}>
          <h3 style={{
            fontSize: getFontSize('lg'),
            fontWeight: '500',
            marginBottom: getSpacing('md'),
            color: getColor('text')
          }}>Настройки кардиолога</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing('md') }}>
            <label className="flex items-center" style={{
              gap: '8px',
              color: 'var(--mac-text-primary)',
              fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif'
            }}>
              <MacOSCheckbox 
                checked={settings.showEcgEchoTogether} 
                onChange={(e)=>setSettings({ ...settings, showEcgEchoTogether: e.target.checked })} 
              />
              Показывать ЭКГ и ЭхоКГ вместе
            </label>
            <div>
              <div className="text-sm" style={{
                color: getColor('textSecondary'),
                marginBottom: getSpacing('xs')
              }}>Порог LDL (мг/дл)</div>
              <input
                type="number"
                value={settings.ldlThreshold}
                onChange={(e)=>setSettings({ ...settings, ldlThreshold: Number(e.target.value) })}
                style={{
                  width: '100%',
                  padding: `${getSpacing('sm')} ${getSpacing('md')}`,
                  border: `1px solid ${getColor('border')}`,
                  borderRadius: '6px',
                  backgroundColor: getColor('surface'),
                  color: getColor('text'),
                  fontSize: getFontSize('base'),
                  outline: 'none'
                }}
              />
            </div>
          </div>
          <div className="flex justify-end" style={{
            gap: getSpacing('sm'),
            marginTop: getSpacing('lg')
          }}>
            <MacOSButton variant="outline" onClick={()=>setSettingsOpen(false)}>Закрыть</MacOSButton>
            <MacOSButton onClick={()=>setSettingsOpen(false)}><Save size={16} style={{ marginRight: '8px' }}/>Сохранить</MacOSButton>
          </div>
        </MacOSCard>
      )}
      </div>
    </div>
  );
};

export default MacOSCardiologistPanelUnified;
