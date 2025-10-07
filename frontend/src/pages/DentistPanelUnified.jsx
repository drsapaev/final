import React, { useState, useEffect } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import { useBreakpoint, useTouchDevice } from '../hooks/useMediaQuery';
import { Button, AnimatedTransition, Badge, Card } from '../components/ui/native';
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
  const [authState, setAuthState] = useState(auth.getState());
  
  useEffect(() => {
    const unsubscribe = auth.subscribe(setAuthState);
    return unsubscribe;
  }, []);
  
  const user = authState.profile;
  
  // Состояние
  const [activeTab, setActiveTab] = useState('dashboard');
  const [patients, setPatients] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [dentalExaminations, setDentalExaminations] = useState([]);
  const [treatmentPlans, setTreatmentPlans] = useState([]);
  const [prosthetics, setProsthetics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [scheduleNextModal, setScheduleNextModal] = useState({ open: false, patient: null });
  
  // Состояния для таблицы записей
  const [appointmentsTableData, setAppointmentsTableData] = useState([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [appointmentsSelected, setAppointmentsSelected] = useState(new Set());
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
        loadAppointments(),
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
      
      const response = await fetch('http://localhost:8000/api/v1/registrar/queues/today?department=dental', {
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
          const dentalQueue = data.queues.find(queue => 
            queue.specialty === 'dental' || queue.specialty === 'dentist' || queue.specialty === 'dentistry'
          );
          
          if (dentalQueue && dentalQueue.entries) {
            appointmentsData = dentalQueue.entries.map(entry => ({
              id: entry.id,
              patient_fio: entry.patient_name || `${entry.patient?.first_name || ''} ${entry.patient?.last_name || ''}`.trim(),
              patient_phone: entry.patient?.phone || entry.phone || '',
              patient_birth_year: entry.patient?.birth_year || entry.birth_year || '',
              address: entry.patient?.address || entry.address || '',
              visit_type: entry.visit_type || 'Платный',
              services: entry.services || [],
              payment_type: entry.payment_status || 'Не оплачено',
              doctor: entry.doctor_name || 'Стоматолог',
              date: entry.appointment_date || new Date().toISOString().split('T')[0],
              time: entry.appointment_time || '09:00',
              status: entry.status || 'Ожидает',
              cost: entry.total_cost || 0,
              payment: entry.payment_status || 'Не оплачено'
            }));
          }
        }
        
        setAppointmentsTableData(appointmentsData);
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
      setActiveTab('examinations');
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
      const res = await fetch('http://localhost:8000/api/v1/dental/examinations?limit=100', { headers: authHeader() });
      if (res.ok) setDentalExaminations(await res.json());
    } catch {
      // Игнорируем ошибки загрузки обследований
    }
  };

  const loadTreatmentPlans = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/dental/treatments?limit=100', { headers: authHeader() });
      if (res.ok) setTreatmentPlans(await res.json());
    } catch {
      // Игнорируем ошибки загрузки планов лечения
    }
  };

  const loadProsthetics = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/dental/prosthetics?limit=100', { headers: authHeader() });
      if (res.ok) setProsthetics(await res.json());
    } catch {
      // Игнорируем ошибки загрузки протезирования
    }
  };

  // Обработчики
  const handlePatientSelect = (patient) => {
    setSelectedPatient(patient);
    setShowPatientCard(true);
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
    <div className="space-y-8">
      {/* Статистические карточки */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 hover:shadow-md transition-shadow duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600 mb-1">Всего пациентов</p>
              <p className="text-3xl font-bold text-slate-900">{stats.totalPatients}</p>
              <p className="text-xs text-green-600 mt-1">+12% за месяц</p>
            </div>
            <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl flex items-center justify-center shadow-lg">
              <Users className="h-7 w-7 text-white" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 hover:shadow-md transition-shadow duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600 mb-1">Записей сегодня</p>
              <p className="text-3xl font-bold text-slate-900">{stats.todayAppointments}</p>
              <p className="text-xs text-blue-600 mt-1">8 из 12 слотов</p>
            </div>
            <div className="w-14 h-14 bg-gradient-to-br from-green-500 to-green-600 rounded-2xl flex items-center justify-center shadow-lg">
              <Calendar className="h-7 w-7 text-white" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 hover:shadow-md transition-shadow duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600 mb-1">Активные планы</p>
              <p className="text-3xl font-bold text-slate-900">{stats.activeTreatmentPlans}</p>
              <p className="text-xs text-purple-600 mt-1">+8% к прошлому месяцу</p>
            </div>
            <div className="w-14 h-14 bg-gradient-to-br from-purple-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg">
              <FileText className="h-7 w-7 text-white" />
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 hover:shadow-md transition-shadow duration-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600 mb-1">Протезы</p>
              <p className="text-3xl font-bold text-slate-900">{stats.completedProsthetics}</p>
              <p className="text-xs text-orange-600 mt-1">+15% к прошлому месяцу</p>
            </div>
            <div className="w-14 h-14 bg-gradient-to-br from-orange-500 to-orange-600 rounded-2xl flex items-center justify-center shadow-lg">
              <Smile className="h-7 w-7 text-white" />
            </div>
          </div>
        </div>
      </div>

      {/* Быстрые действия */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-slate-900">Быстрые действия</h3>
          <button className="text-sm text-blue-600 hover:text-blue-700 font-medium">
            Показать все
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            onClick={() => setActiveTab('patients')}
            className="flex items-center gap-3 px-6 py-4 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl hover:from-blue-600 hover:to-blue-700 transition-all duration-200 shadow-sm"
          >
            <Plus className="h-5 w-5" />
            <span className="font-medium">Новый пациент</span>
          </button>
          <button
            onClick={() => setActiveTab('appointments')}
            className="flex items-center gap-3 px-6 py-4 bg-white text-slate-700 border border-slate-200 rounded-xl hover:bg-slate-50 transition-all duration-200 shadow-sm"
          >
            <Calendar className="h-5 w-5" />
            <span className="font-medium">Записать на прием</span>
          </button>
          <button
            onClick={() => setActiveTab('dental-chart')}
            className="flex items-center gap-3 px-6 py-4 bg-white text-slate-700 border border-slate-200 rounded-xl hover:bg-slate-50 transition-all duration-200 shadow-sm"
          >
            <Tooth className="h-5 w-5" />
            <span className="font-medium">Схема зубов</span>
          </button>
        </div>
      </div>

      {/* Последние записи */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-slate-900">Последние записи</h3>
          <button className="text-sm text-blue-600 hover:text-blue-700 font-medium">
            Показать все
          </button>
        </div>
        <div className="space-y-3">
          {appointments.slice(0, 5).map(appointment => (
            <div key={appointment.id} className="flex items-center justify-between p-4 bg-slate-50 rounded-xl hover:bg-slate-100 transition-colors">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center shadow-sm">
                  <span className="text-white text-sm font-bold">
                    {appointment.patientName?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="font-medium text-slate-900">{appointment.patientName}</p>
                  <p className="text-sm text-slate-600">{appointment.date} {appointment.time}</p>
                </div>
              </div>
              <div className={`px-3 py-1 rounded-full text-xs font-medium ${
                appointment.status === 'confirmed' 
                  ? 'bg-green-100 text-green-700' 
                  : 'bg-yellow-100 text-yellow-700'
              }`}>
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
    <div className="space-y-6">
      {/* Поиск и фильтры */}
      <Card className="p-6">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="text"
                placeholder="Поиск пациентов..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="all">Все статусы</option>
            <option value="active">Активные</option>
            <option value="inactive">Неактивные</option>
          </select>
        </div>
      </Card>

      {/* Список пациентов */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredPatients.map(patient => (
          <Card key={patient.id} className="p-6 hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-blue-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-lg font-medium">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <h3 className="font-semibold text-lg">{patient.name}</h3>
                  <p className="text-gray-600">{patient.phone}</p>
                </div>
              </div>
              <Badge variant={patient.status === 'active' ? 'success' : 'warning'}>
                {patient.status}
              </Badge>
            </div>

            <div className="space-y-2 mb-4">
              <p className="text-sm text-gray-600">
                <strong>Возраст:</strong> {patient.age} лет
              </p>
              <p className="text-sm text-gray-600">
                <strong>Последний визит:</strong> {patient.lastVisit || 'Не было'}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <Button
                size="sm"
                onClick={() => handlePatientSelect(patient)}
                className="col-span-2"
              >
                <Edit className="h-4 w-4 mr-1" />
                Карточка пациента
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleExamination(patient)}
                title="Осмотр"
              >
                <Eye className="h-4 w-4" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleDiagnosis(patient)}
                title="Диагнозы"
              >
                <Stethoscope className="h-4 w-4" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleVisitProtocol(patient)}
                title="Протокол визита"
              >
                <FileText className="h-4 w-4" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleDentalChart(patient)}
                title="Схема зубов"
              >
                <Tooth className="h-4 w-4" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleTreatment(patient)}
                title="Лечение"
              >
                <Scissors className="h-4 w-4" />
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleProsthetic(patient)}
                title="Протезирование"
              >
                <Smile className="h-4 w-4" />
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );

  // Рендер записей
  const renderAppointments = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium flex items-center">
            <Calendar size={20} className="mr-2 text-green-600" />
            Записи к стоматологу
          </h3>
          <div className="flex items-center gap-2">
            <Badge variant="info">
              Всего: {appointmentsTableData.length}
            </Badge>
            <Button 
              variant="secondary" 
              size="sm"
              onClick={loadDentistryAppointments}
              disabled={appointmentsLoading}
            >
              <RefreshCw size={16} className="mr-1" />
              Обновить
            </Button>
          </div>
        </div>
        
        <EnhancedAppointmentsTable
          data={appointmentsTableData}
          loading={appointmentsLoading}
          theme="light"
          language="ru"
          selectedRows={appointmentsSelected}
          outerBorder={false}
          services={{}}
          showCheckboxes={false}
          onRowSelect={(id, checked) => {
            const newSelected = new Set(appointmentsSelected);
            if (checked) {
              newSelected.add(id);
            } else {
              newSelected.delete(id);
            }
            setAppointmentsSelected(newSelected);
          }}
          onRowClick={handleAppointmentRowClick}
          onActionClick={handleAppointmentActionClick}
        />
      </Card>
    </div>
  );

  // Рендер осмотров
  const renderExaminations = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Объективные осмотры</h3>
        <p className="text-gray-600 mb-4">
          Выберите пациента для проведения или просмотра объективного осмотра
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {patients.map(patient => (
            <div
              key={patient.id}
              className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer"
              onClick={() => handleExamination(patient)}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-medium">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="font-medium">{patient.name}</p>
                  <p className="text-sm text-gray-600">Провести осмотр</p>
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
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Диагнозы и назначения</h3>
        <p className="text-gray-600 mb-4">
          Выберите пациента для постановки диагнозов и назначений
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {patients.map(patient => (
            <div
              key={patient.id}
              className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer"
              onClick={() => handleDiagnosis(patient)}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-medium">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="font-medium">{patient.name}</p>
                  <p className="text-sm text-gray-600">Поставить диагноз</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );

  // Рендер протоколов визитов
  const renderVisits = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Протоколы визитов</h3>
        <p className="text-gray-600 mb-4">
          Выберите пациента для создания или просмотра протокола визита
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {patients.map(patient => (
            <div
              key={patient.id}
              className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer"
              onClick={() => handleVisitProtocol(patient)}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-purple-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-medium">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="font-medium">{patient.name}</p>
                  <p className="text-sm text-gray-600">Создать протокол</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );

  // Рендер фото архива
  const renderPhotos = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Фото и рентген архив</h3>
        <p className="text-gray-600 mb-4">
          Выберите пациента для просмотра и управления фото и рентгеновскими снимками
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {patients.map(patient => (
            <div
              key={patient.id}
              className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer"
              onClick={() => handlePhotoArchive(patient)}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-orange-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-medium">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="font-medium">{patient.name}</p>
                  <p className="text-sm text-gray-600">Открыть архив</p>
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
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold">Шаблоны протоколов</h3>
            <p className="text-gray-600 text-sm">
              Стандартные протоколы для быстрого создания протоколов визитов
            </p>
          </div>
          <Button
            onClick={handleProtocolTemplates}
            className="flex items-center gap-2"
          >
            <FileText className="h-4 w-4" />
            Управление шаблонами
          </Button>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                <Scissors className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <h4 className="font-medium">Лечение кариеса</h4>
                <p className="text-sm text-gray-600">60 мин</p>
              </div>
            </div>
            <p className="text-sm text-gray-700 mb-3">
              Стандартный протокол лечения кариеса с анестезией и пломбированием
            </p>
            <div className="flex gap-2">
              <Button size="sm" className="flex-1">
                Использовать
              </Button>
              <Button size="sm" variant="outline">
                <Edit className="h-4 w-4" />
              </Button>
            </div>
          </div>
          
          <div className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 bg-red-100 rounded-lg flex items-center justify-center">
                <Scissors className="h-5 w-5 text-red-600" />
              </div>
              <div>
                <h4 className="font-medium">Эндодонтическое лечение</h4>
                <p className="text-sm text-gray-600">120 мин</p>
              </div>
            </div>
            <p className="text-sm text-gray-700 mb-3">
              Протокол лечения корневых каналов с инструментальной обработкой
            </p>
            <div className="flex gap-2">
              <Button size="sm" className="flex-1">
                Использовать
              </Button>
              <Button size="sm" variant="outline">
                <Edit className="h-4 w-4" />
              </Button>
            </div>
          </div>
          
          <div className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                <Scissors className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <h4 className="font-medium">Профессиональная гигиена</h4>
                <p className="text-sm text-gray-600">75 мин</p>
              </div>
            </div>
            <p className="text-sm text-gray-700 mb-3">
              Протокол профессиональной гигиены полости рта
            </p>
            <div className="flex gap-2">
              <Button size="sm" className="flex-1">
                Использовать
              </Button>
              <Button size="sm" variant="outline">
                <Edit className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );

  // Рендер отчетов
  const renderReports = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold">Отчеты и аналитика</h3>
            <p className="text-gray-600 text-sm">
              Статистика по пациентам, врачам, процедурам и клинике
            </p>
          </div>
          <Button
            onClick={handleReports}
            className="flex items-center gap-2"
          >
            <BarChart3 className="h-4 w-4" />
            Открыть отчеты
          </Button>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer" onClick={handleReports}>
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                <BarChart3 className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <h4 className="font-medium">Общий обзор</h4>
                <p className="text-sm text-gray-600">Основные показатели</p>
              </div>
            </div>
            <p className="text-sm text-gray-700">
              Общая статистика по всем направлениям деятельности
            </p>
          </div>
          
          <div className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer" onClick={handleReports}>
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
                <Users className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <h4 className="font-medium">По пациентам</h4>
                <p className="text-sm text-gray-600">Демография и активность</p>
              </div>
            </div>
            <p className="text-sm text-gray-700">
              Анализ пациентской базы и их активности
            </p>
          </div>
          
          <div className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer" onClick={handleReports}>
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                <Stethoscope className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <h4 className="font-medium">По врачам</h4>
                <p className="text-sm text-gray-600">Производительность</p>
              </div>
            </div>
            <p className="text-sm text-gray-700">
              Статистика работы врачей и их специализаций
            </p>
          </div>
          
          <div className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer" onClick={handleReports}>
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 bg-orange-100 rounded-lg flex items-center justify-center">
                <Building className="h-5 w-5 text-orange-600" />
              </div>
              <div>
                <h4 className="font-medium">По клинике</h4>
                <p className="text-sm text-gray-600">Оборудование и загруженность</p>
              </div>
            </div>
            <p className="text-sm text-gray-700">
              Анализ работы клиники и состояния оборудования
            </p>
          </div>
        </div>
      </Card>
    </div>
  );

  // Рендер схем зубов
  const renderDentalChart = () => (
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Схемы зубов</h3>
        <p className="text-gray-600 mb-4">
          Выберите пациента для просмотра и редактирования схемы зубов
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {patients.map(patient => (
            <div
              key={patient.id}
              className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer"
              onClick={() => handleDentalChart(patient)}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-medium">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="font-medium">{patient.name}</p>
                  <p className="text-sm text-gray-600">Открыть схему</p>
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
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Планы лечения</h3>
        <p className="text-gray-600 mb-4">
          Выберите пациента для создания или редактирования плана лечения
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {patients.map(patient => (
            <div
              key={patient.id}
              className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer"
              onClick={() => handleTreatmentPlanner(patient)}
            >
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                  <span className="text-white text-sm font-medium">
                    {patient.name?.charAt(0)}
                  </span>
                </div>
                <div>
                  <p className="font-medium">{patient.name}</p>
                  <p className="text-sm text-gray-600">Открыть план</p>
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
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">Протезирование</h3>
        <div className="space-y-3">
          {prosthetics.map(prosthetic => (
            <div key={prosthetic.id} className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-orange-500 rounded-full flex items-center justify-center">
                  <Smile className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="font-medium">{prosthetic.patientName}</p>
                  <p className="text-sm text-gray-600">{prosthetic.type}</p>
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
    <div className="space-y-6">
      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">AI Помощник</h3>
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
      <div className="p-6">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Сайдбар */}
      <div className="w-72 bg-white shadow-xl border-r border-slate-200 flex flex-col">
        {/* Заголовок сайдбара */}
        <div className="p-6 border-b border-slate-200">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center shadow-lg">
              <Stethoscope className="h-6 w-6 text-white" />
            </div>
            <div className="flex-1">
              <h1 className="text-xl font-bold text-slate-900">
                Стоматология
              </h1>
              <p className="text-sm text-slate-600">
                {user?.name || 'Доктор'}
              </p>
            </div>
          </div>
          
          {/* Кнопка назначить следующий визит */}
          <div className="mt-4">
            <Button 
              variant="primary"
              onClick={() => setScheduleNextModal({ open: true, patient: selectedPatient })}
              className="w-full flex items-center justify-center gap-2 text-sm"
              size="sm"
            >
              <Plus size={14} />
              Назначить следующий визит
            </Button>
          </div>
        </div>

        {/* Поиск */}
        <div className="p-4 border-b border-slate-200">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Поиск пациентов..."
              className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200"
            />
          </div>
        </div>

        {/* Навигация */}
        <nav className="flex-1 p-4">
          <div className="space-y-1">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 group ${
                  activeTab === tab.id
                    ? 'bg-blue-50 text-blue-700 border border-blue-200 shadow-sm'
                    : 'text-slate-700 hover:bg-slate-50 hover:text-slate-900'
                }`}
              >
                <tab.icon className={`h-5 w-5 transition-colors ${
                  activeTab === tab.id ? 'text-blue-600' : 'text-slate-500 group-hover:text-slate-700'
                }`} />
                <span className="truncate">{tab.label}</span>
              </button>
            ))}
          </div>
        </nav>

        {/* Футер сайдбара */}
        <div className="p-4 border-t border-slate-200 bg-slate-50">
          <div className="text-center mb-4">
            <p className="text-sm font-medium text-slate-900">
              {new Date().toLocaleDateString('ru-RU', { 
                day: 'numeric',
                month: 'short'
              })}
            </p>
            <p className="text-xs text-slate-600">
              {new Date().toLocaleTimeString('ru-RU', { 
                hour: '2-digit',
                minute: '2-digit'
              })}
            </p>
          </div>
          
          <div className="space-y-1">
            <button className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-700 hover:bg-white rounded-xl transition-colors">
              <Settings className="h-4 w-4" />
              Настройки
            </button>
            <button className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-slate-700 hover:bg-white rounded-xl transition-colors">
              <LogOut className="h-4 w-4" />
              Выход
            </button>
          </div>
        </div>
      </div>

      {/* Основной контент */}
      <div className="flex-1 flex flex-col">
        {/* Заголовок контента */}
        <div className="bg-white shadow-sm border-b border-slate-200 px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-slate-900">
                {tabs.find(tab => tab.id === activeTab)?.label || 'Дашборд'}
              </h2>
              <p className="text-slate-600 mt-1">
                {activeTab === 'dashboard' && 'Обзор статистики и активности'}
                {activeTab === 'patients' && 'Управление пациентами и их данными'}
                {activeTab === 'appointments' && 'Расписание и записи на прием'}
                {activeTab === 'examinations' && 'Осмотры и диагностика'}
                {activeTab === 'diagnoses' && 'Диагнозы и назначения'}
                {activeTab === 'visits' && 'Протоколы визитов'}
                {activeTab === 'photos' && 'Фото и рентген архив'}
                {activeTab === 'templates' && 'Шаблоны протоколов'}
                {activeTab === 'reports' && 'Отчеты и аналитика'}
                {activeTab === 'dental-chart' && 'Схемы зубов'}
                {activeTab === 'treatment-plans' && 'Планы лечения'}
                {activeTab === 'prosthetics' && 'Протезирование'}
                {activeTab === 'ai-assistant' && 'AI Помощник'}
              </p>
            </div>
            
            {/* Быстрые действия */}
            <div className="flex items-center gap-3">
              <button className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors shadow-sm">
                <Plus className="h-4 w-4" />
                Добавить
              </button>
              <button className="flex items-center gap-2 px-4 py-2.5 bg-white text-slate-700 border border-slate-200 rounded-xl hover:bg-slate-50 transition-colors">
                <Filter className="h-4 w-4" />
                Фильтры
              </button>
            </div>
          </div>
        </div>

        {/* Контент */}
        <div className="flex-1 p-8 overflow-auto">
          <AnimatedTransition>
            {renderContent()}
          </AnimatedTransition>
        </div>
      </div>

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
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-6xl h-full max-h-[90vh] overflow-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">
                Схема зубов: {selectedPatient.name}
              </h2>
              <button
                onClick={() => setShowDentalChart(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                <XCircle className="h-6 w-6" />
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
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-6xl h-full max-h-[90vh] overflow-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold">
                План лечения: {selectedPatient.name}
              </h2>
              <button
                onClick={() => setShowTreatmentPlanner(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                <XCircle className="h-6 w-6" />
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
