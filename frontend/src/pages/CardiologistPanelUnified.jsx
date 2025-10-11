import React, { useState, useEffect } from 'react';
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
import { Card, Button, Badge } from '../components/ui/native';
import { useTheme } from '../contexts/ThemeContext';
import DoctorQueuePanel from '../components/doctor/DoctorQueuePanel';
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
const CardiologistPanelUnified = () => {
  // Всегда вызываем хуки первыми
  const { theme, isDark, getColor, getSpacing, getFontSize } = useTheme();
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

  // Загрузка записей кардиолога
  const loadCardiologyAppointments = async () => {
    setAppointmentsLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        console.log('Нет токена аутентификации');
        setAppointmentsLoading(false);
        return;
      }
      
      const response = await fetch('http://localhost:8000/api/v1/registrar/queues/today?department=cardio', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        
        // Обрабатываем данные из API
        let appointmentsData = [];
        if (data && data.queues && Array.isArray(data.queues)) {
          const cardioQueue = data.queues.find(queue => 
            queue.specialty === 'cardio' || queue.specialty === 'cardiology'
          );
          
          if (cardioQueue && cardioQueue.entries) {
            appointmentsData = cardioQueue.entries.map(entry => ({
              id: entry.id,
              patient_fio: entry.patient_name || `${entry.patient?.first_name || ''} ${entry.patient?.last_name || ''}`.trim(),
              patient_phone: entry.patient?.phone || entry.phone || '',
              patient_birth_year: entry.patient?.birth_year || entry.birth_year || '',
              address: entry.patient?.address || entry.address || '',
              visit_type: entry.visit_type || 'Платный',
              services: entry.services || [],
              payment_type: entry.payment_status || 'Не оплачено',
              doctor: entry.doctor_name || 'Кардиолог',
              date: entry.appointment_date || new Date().toISOString().split('T')[0],
              time: entry.appointment_time || '09:00',
              status: entry.status || 'Ожидает',
              cost: entry.total_cost || 0,
              payment: entry.payment_status || 'Не оплачено'
            }));
          }
        }
        
        setAppointments(appointmentsData);
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
      loadCardiologyAppointments();
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
    console.log('CardiologistPanelUnified: Skipping render in demo mode');
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

  const pageStyle = {
    padding: '0',
    width: '100%',
    height: '100%',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    background: isDark ? 'var(--bg-primary)' : '#f8fafc',
    minHeight: 'calc(100vh - 60px)', // Вычитаем высоту хедера
    color: isDark ? 'var(--text-primary)' : '#1a202c',
    overflow: 'visible'
  };

  const headerStyle = {
    marginBottom: '24px',
    padding: '20px',
    background: isDark ? 'var(--bg-secondary)' : 'white',
    borderRadius: '12px',
    border: isDark ? '1px solid var(--border-color)' : '1px solid #e2e8f0',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
  };

  const tabStyle = {
    padding: '12px 24px',
    border: 'none',
    background: 'transparent',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
    color: isDark ? 'var(--text-secondary)' : '#64748b',
    borderRadius: '8px',
    transition: 'all 0.2s ease',
    display: 'flex',
    alignItems: 'center',
    gap: '8px'
  };

  const activeTabStyle = {
    ...tabStyle,
    background: '#dc3545',
    color: 'white',
    boxShadow: '0 2px 4px rgba(220, 53, 69, 0.3)'
  };

  return (
    <div className="cardiologist-panel" style={{
      ...pageStyle,
      padding: '20px',
      boxSizing: 'border-box',
      overflow: 'hidden',
      width: '100%',
      position: 'relative',
      zIndex: 1,
      display: 'block',
      maxWidth: '100%',
      margin: 0
    }}>

      {/* Сообщения */}
      {message.text && (
        <div className={`flex items-center p-4 rounded-lg mb-4 ${
          message.type === 'success' 
            ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
            : message.type === 'error'
            ? 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
            : 'bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400'
        }`}>
          {message.type === 'success' ? (
            <CheckCircle size={20} className="mr-2" />
          ) : (
            <AlertCircle size={20} className="mr-2" />
          )}
          {message.text}
        </div>
      )}

      {/* Навигация по вкладкам удалена — управление через сайдбар и URL */}

      {/* Контент вкладок */}
      <div style={{
        width: '100%',
        maxWidth: 'none',
        overflow: 'visible',
        boxSizing: 'border-box',
        position: 'relative',
        zIndex: 1,
        display: 'block'
      }}>
        {/* Очередь пациентов */}
        {activeTab === 'queue' && (
          <div style={{ width: '100%', maxWidth: 'none', overflow: 'visible' }}>
            <DoctorQueuePanel
              specialty="cardiology"
              onPatientSelect={handlePatientSelect}
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
            gap: '24px'
          }}>
            <Card padding="lg" style={{
              width: '100%',
              maxWidth: '100%',
              minWidth: 0,
              boxSizing: 'border-box',
              overflow: 'hidden'
            }}>
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium flex items-center">
                  <Calendar size={20} className="mr-2 text-green-600" />
                  Записи к кардиологу
                </h3>
                <div className="flex items-center gap-2">
                  <Badge variant="info">
                    Всего: {appointments.length}
                  </Badge>
                  <Button 
                    variant="secondary" 
                    size="sm"
                    onClick={loadCardiologyAppointments}
                    disabled={appointmentsLoading}
                  >
                    <RefreshCw size={16} className="mr-1" />
                    Обновить
                  </Button>
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
            </Card>
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
            <Card padding="lg">
              <h3 className="text-lg font-medium mb-4 flex items-center">
                <User size={20} className="mr-2 text-blue-600" />
                Пациент #{selectedPatient.number}
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    ФИО пациента
                  </label>
                  <div className="text-lg font-medium">{selectedPatient.patient_name}</div>
                </div>
                
                {selectedPatient.phone && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Телефон
                    </label>
                    <div className="flex items-center">
                      <Phone size={16} className="mr-2 text-gray-400" />
                      {selectedPatient.phone}
                    </div>
                  </div>
                )}
              </div>
            </Card>

            {/* Жалобы и диагноз */}
            <Card padding="lg">
              <h3 className="text-lg font-medium mb-4">📝 Жалобы и диагноз</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Жалобы пациента
                  </label>
                  <textarea
                    value={visitData.complaint}
                    onChange={(e) => setVisitData({ ...visitData, complaint: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    rows={4}
                    placeholder="Опишите жалобы пациента..."
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Диагноз
                    </label>
                    <input
                      type="text"
                      value={visitData.diagnosis}
                      onChange={(e) => setVisitData({ ...visitData, diagnosis: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                      placeholder="Диагноз"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      МКБ-10
                    </label>
                    <input
                      type="text"
                      value={visitData.icd10}
                      onChange={(e) => setVisitData({ ...visitData, icd10: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                      placeholder="I25.9"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Примечания
                  </label>
                  <textarea
                    value={visitData.notes}
                    onChange={(e) => setVisitData({ ...visitData, notes: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    rows={3}
                    placeholder="Дополнительные примечания..."
                  />
                </div>
              </div>
            </Card>

            {/* Услуги визита */}
            <DoctorServiceSelector
              specialty="cardiology"
              selectedServices={selectedServices}
              onServicesChange={setSelectedServices}
              canEditPrices={true}
            />

            {/* Действия */}
            <Card padding="lg">
              <div className="flex justify-end space-x-3">
                <Button
                  variant="outline"
                  onClick={() => {
                    setSelectedPatient(null);
                    setActiveTab('queue');
                  }}
                >
                  Отменить
                </Button>
                <Button
                  onClick={handleSaveVisit}
                  disabled={loading || !visitData.complaint}
                >
                  {loading ? (
                    <RefreshCw size={16} className="animate-spin mr-2" />
                  ) : (
                    <Save size={16} className="mr-2" />
                  )}
                  Завершить прием
                </Button>
              </div>
            </Card>
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
            gap: '24px'
          }}>
            <div className="flex justify-end">
              <Button onClick={() => setShowForm({ open: true, type: 'ecg' })}>
                <Plus size={16} className="mr-2" /> Добавить ЭКГ
              </Button>
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
            gap: '24px'
          }}>
            <Card padding="lg">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium flex items-center">
                  <TestTube size={20} className="mr-2 text-purple-600" />
                  Анализы крови
                </h3>
                <Button onClick={() => setShowForm({ open: true, type: 'blood' })}>
                  <Plus size={16} className="mr-2" />
                  Новый анализ
                </Button>
              </div>

              {/* Небольшая аналитика по имеющимся анализам */}
              {bloodTests.length > 0 && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
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
                      <div key={idx} className="p-3 rounded-lg border" style={{
                        borderColor: isDark ? '#374151' : '#e5e7eb',
                        backgroundColor: isDark ? '#1f2937' : '#ffffff',
                        color: isDark ? '#f9fafb' : '#111827'
                      }}>
                        <div className="text-sm" style={{ color: isDark ? '#9ca3af' : '#6b7280' }}>{it.label}</div>
                        <div className="text-xl font-semibold mt-1">{it.value} {typeof it.value === 'number' ? it.unit : ''}</div>
                      </div>
                    ));
                  })()}
                </div>
              )}

              {bloodTests.length > 0 ? (
                <div className="space-y-4">
                  {bloodTests.map((test) => (
                    <div key={test.id} className="rounded-lg p-4" style={{
                      border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`,
                      backgroundColor: isDark ? '#1f2937' : '#ffffff'
                    }}>
                      <div className="flex justify-between items-start mb-2">
                        <h4 className="font-medium" style={{ color: isDark ? '#f9fafb' : '#111827' }}>Анализ #{test.id}</h4>
                        <Badge variant="info">{test.test_date}</Badge>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm" style={{ color: isDark ? '#d1d5db' : '#4b5563' }}>
                        <div>🩸 Холестерин: {test.cholesterol_total} мг/дл</div>
                        <div>HDL: {test.cholesterol_hdl}</div>
                        <div>LDL: {test.cholesterol_ldl}</div>
                        <div>Триглицериды: {test.triglycerides}</div>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm mt-2" style={{ color: isDark ? '#d1d5db' : '#4b5563' }}>
                        <div>🍬 Глюкоза: {test.glucose} мг/дл</div>
                        <div>CRP: {test.crp} мг/л</div>
                        <div>Тропонин: {test.troponin} нг/мл</div>
                      </div>
                      {test.interpretation && (
                        <div className="mt-2 text-sm" style={{ color: isDark ? '#f3f4f6' : '#374151' }}>
                          <strong>Интерпретация:</strong> {test.interpretation}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8" style={{ color: isDark ? '#9ca3af' : '#6b7280' }}>
                  <TestTube size={48} className="mx-auto mb-4" style={{ color: isDark ? '#6b7280' : '#d1d5db' }} />
                  <p>Нет данных анализов</p>
                </div>
              )}
            </Card>

            {/* Форма анализа крови */}
            {showForm.open && showForm.type === 'blood' && (
              <Card padding="lg">
                <h3 className="text-lg font-medium mb-4">Новый анализ крови</h3>
                <form onSubmit={handleBloodTestSubmit} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Дата анализа *
                      </label>
                      <input
                        type="date"
                        value={bloodTestForm.test_date}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, test_date: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Общий холестерин (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.cholesterol_total}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, cholesterol_total: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="<200"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        HDL холестерин (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.cholesterol_hdl}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, cholesterol_hdl: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder=">40"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        LDL холестерин (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.cholesterol_ldl}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, cholesterol_ldl: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="<100"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Триглицериды (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.triglycerides}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, triglycerides: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="<150"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Глюкоза (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.glucose}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, glucose: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="70-100"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        CRP (мг/л)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.crp}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, crp: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="<3.0"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Тропонин (нг/мл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.troponin}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, troponin: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="<0.04"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Интерпретация
                    </label>
                    <textarea
                      value={bloodTestForm.interpretation}
                      onChange={(e) => setBloodTestForm({ ...bloodTestForm, interpretation: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                      rows={4}
                      placeholder="Интерпретация результатов анализов"
                    />
                  </div>

                  <div className="flex justify-end space-x-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setShowForm({ open: false, type: 'blood' })}
                    >
                      Отмена
                    </Button>
                    <Button type="submit">
                      <Save size={16} className="mr-2" />
                      Сохранить анализ
                    </Button>
                  </div>
                </form>
              </Card>
            )}
          </div>
        )}

        {/* AI Помощник */}
        {activeTab === 'ai' && (
          <div style={{ width: '100%', maxWidth: 'none', overflow: 'visible' }}>
            <AIAssistant
              specialty="cardiology"
              onSuggestionSelect={handleAISuggestion}
            />
          </div>
        )}

        {/* Управление услугами */}
        {activeTab === 'services' && (
          <div style={{ width: '100%', maxWidth: 'none', overflow: 'visible' }}>
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
            gap: '24px'
          }}>
            {!selectedPatient ? (
              <Card className="p-8 text-center">
                <Calendar size={48} className="mx-auto mb-4" style={{ color: isDark ? '#9ca3af' : '#6b7280' }} />
                <h3 className="text-lg font-medium mb-2" style={{ color: isDark ? '#f9fafb' : '#111827' }}>История</h3>
                <p style={{ color: isDark ? '#9ca3af' : '#6b7280' }}>Выберите пациента в очереди или из записей</p>
              </Card>
            ) : (
              <>
                <Card padding="lg">
                  <h3 className="text-lg font-medium mb-4">Хронология записей пациента</h3>
                  <div className="space-y-3">
                    {bloodTests.length === 0 && ecgResults.length === 0 && (
                      <div style={{ color: isDark ? '#9ca3af' : '#6b7280' }}>Нет данных по ЭКГ или анализам крови</div>
                    )}
                    {bloodTests.map((t) => (
                      <div key={`blood-${t.id}`} className="flex items-start gap-3">
                        <div className="w-2 h-2 rounded-full bg-purple-500 mt-2" />
                        <div>
                          <div className="font-medium">Анализ крови — {t.test_date}</div>
                          <div className="text-sm text-gray-600 dark:text-gray-400">
                            Хол: {t.cholesterol_total}; LDL: {t.cholesterol_ldl}; Глюкоза: {t.glucose}
                          </div>
                        </div>
                      </div>
                    ))}
                    {ecgResults.map((e) => (
                      <div key={`ecg-${e.id || e.ecg_date}`} className="flex items-start gap-3">
                        <div className="w-2 h-2 rounded-full bg-green-500 mt-2" />
                        <div>
                          <div className="font-medium">ЭКГ — {e.ecg_date || '—'}</div>
                          <div className="text-sm text-gray-600 dark:text-gray-400">
                            Ритм: {e.rhythm || '—'}, ЧСС: {e.heart_rate || '—'}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>

                <Card padding="lg">
                  <h3 className="text-lg font-medium mb-4">Сводка по пациенту</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="p-3 rounded-lg border" style={{
                      borderColor: isDark ? '#374151' : '#e5e7eb',
                      backgroundColor: isDark ? '#1f2937' : '#ffffff'
                    }}>
                      <div className="text-sm" style={{ color: isDark ? '#9ca3af' : '#6b7280' }}>Количество ЭКГ</div>
                      <div className="text-xl font-semibold mt-1" style={{ color: isDark ? '#f9fafb' : '#111827' }}>{ecgResults.length}</div>
                    </div>
                    <div className="p-3 rounded-lg border" style={{
                      borderColor: isDark ? '#374151' : '#e5e7eb',
                      backgroundColor: isDark ? '#1f2937' : '#ffffff'
                    }}>
                      <div className="text-sm" style={{ color: isDark ? '#9ca3af' : '#6b7280' }}>Количество анализов</div>
                      <div className="text-xl font-semibold mt-1" style={{ color: isDark ? '#f9fafb' : '#111827' }}>{bloodTests.length}</div>
                    </div>
                    <div className="p-3 rounded-lg border" style={{
                      borderColor: isDark ? '#374151' : '#e5e7eb',
                      backgroundColor: isDark ? '#1f2937' : '#ffffff'
                    }}>
                      <div className="text-sm" style={{ color: isDark ? '#9ca3af' : '#6b7280' }}>Выбранный пациент</div>
                      <div className="text-xl font-semibold mt-1" style={{ color: isDark ? '#f9fafb' : '#111827' }}>{selectedPatient?.patient_name || '—'}</div>
                    </div>
                  </div>
                </Card>
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
        style={{ position: 'fixed', right: 16, bottom: 16, background: isDark ? '#1f2937' : 'white', border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`, borderRadius: 9999, padding: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}
        aria-label="Открыть настройки"
      >
        <Settings size={18} />
      </button>
      {settingsOpen && (
        <Card padding="lg" style={{ 
          position: 'fixed', 
          right: 16, 
          bottom: 80, 
          width: 360,
          backgroundColor: isDark ? '#1f2937' : '#ffffff',
          border: `1px solid ${isDark ? '#374151' : '#e5e7eb'}`,
          boxShadow: isDark ? '0 10px 25px rgba(0,0,0,0.5)' : '0 10px 25px rgba(0,0,0,0.15)'
        }}>
          <h3 className="text-lg font-medium mb-3" style={{ color: isDark ? '#f9fafb' : '#111827' }}>Настройки кардиолога</h3>
          <div className="space-y-3">
            <label className="flex items-center gap-2" style={{ color: isDark ? '#f3f4f6' : '#374151' }}>
              <input type="checkbox" checked={settings.showEcgEchoTogether} onChange={(e)=>setSettings({ ...settings, showEcgEchoTogether: e.target.checked })} />
              Показывать ЭКГ и ЭхоКГ вместе
            </label>
            <div>
              <div className="text-sm mb-1" style={{ color: isDark ? '#9ca3af' : '#6b7280' }}>Порог LDL (мг/дл)</div>
              <input 
                type="number" 
                value={settings.ldlThreshold} 
                onChange={(e)=>setSettings({ ...settings, ldlThreshold: Number(e.target.value) })} 
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  border: `1px solid ${isDark ? '#4b5563' : '#d1d5db'}`,
                  borderRadius: '6px',
                  backgroundColor: isDark ? '#374151' : '#ffffff',
                  color: isDark ? '#f9fafb' : '#111827',
                  outline: 'none'
                }}
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <Button variant="outline" onClick={()=>setSettingsOpen(false)}>Закрыть</Button>
            <Button onClick={()=>setSettingsOpen(false)}><Save size={16} className="mr-2"/>Сохранить</Button>
          </div>
        </Card>
      )}
    </div>
  );
};

export default CardiologistPanelUnified;
