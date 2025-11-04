import React, { useState, useEffect, useCallback, useRef } from 'react';
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
import DoctorServiceSelector from '../components/doctor/DoctorServiceSelector';
import AIAssistant from '../components/ai/AIAssistant';
import ECGViewer from '../components/cardiology/ECGViewer';
import EchoForm from '../components/cardiology/EchoForm';
import ScheduleNextModal from '../components/common/ScheduleNextModal';
import { queueService } from '../services/queue';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import EMRSystem from '../components/medical/EMRSystem';

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
    return params.get('tab') || 'appointments';
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
  const [emr, setEmr] = useState(null);
  
  // Ref для отслеживания предыдущего пациента для очистки EMR
  const prevSelectedPatientRef = useRef(null);
  
  // Состояния для таблицы записей
  const [appointments, setAppointments] = useState([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [services, setServices] = useState({});  // ✅ Добавлено: состояние для услуг

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

  // ✅ Очистка EMR и visitData при смене пациента
  useEffect(() => {
    if (selectedPatient) {
      const currentPatientId = selectedPatient.patient_id || selectedPatient.id || selectedPatient.appointment_id;
      const previousPatientId = prevSelectedPatientRef.current;
      
      // Если это новый пациент (не просто обновление того же)
      if (previousPatientId !== null && previousPatientId !== currentPatientId) {
        console.log('[Cardiology] Смена пациента, очищаем EMR и visitData', {
          previousPatientId,
          currentPatientId
        });
        // Очищаем EMR и visitData при смене пациента
        setEmr(null);
        setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
      }
      
      // Сохраняем ID текущего пациента
      prevSelectedPatientRef.current = currentPatientId;
      
      // Загружаем данные пациента
      loadPatientData();
    } else {
      // Если пациента нет, очищаем всё
      prevSelectedPatientRef.current = null;
      setEmr(null);
      setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
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

  // ✅ Загрузка услуг при монтировании
  useEffect(() => {
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
          console.log('[Cardiology] Услуги загружены:', servicesData);
        }
      } catch (error) {
        console.error('[Cardiology] Ошибка загрузки услуг:', error);
      }
    };

    loadServices();
  }, []);

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
        const seenIds = new Set(); // Для отслеживания уже добавленных записей
        
        if (data && data.queues && Array.isArray(data.queues)) {
          data.queues.forEach(queue => {
            if (queue.entries) {
              queue.entries.forEach(entry => {
                const appointmentId = entry.appointment_id || entry.id;
                const recordKey = `${entry.patient_id}_${appointmentId}_${queue.specialty}`;
                
                // Пропускаем дубликаты (один и тот же пациент с одним и тем же appointment_id в одной специальности)
                if (seenIds.has(recordKey)) {
                  console.log('[Cardiology] Пропущен дубликат записи:', recordKey);
                  return;
                }
                seenIds.add(recordKey);
                
                allAppointments.push({
                  id: appointmentId, // Приоритет appointment_id
                  appointment_id: appointmentId, // Явно указываем appointment_id
                  visit_id: appointmentId, // Добавляем visit_id для сопоставления с БД
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

        // ✅ Фильтруем только кардиологические записи, исключая ЭКГ
        const appointmentsData = allAppointments.filter(apt => {
          // Исключаем записи из очереди ЭКГ
          if (apt.specialty === 'echokg' || apt.specialty === 'ecg') {
            return false;
          }
          
          // Проверяем по specialty
          const isCardiology = apt.specialty === 'cardio' || apt.specialty === 'cardiology';
          
          // ✅ Проверяем по кодам услуг: исключаем записи, которые содержат только ЭКГ
          const serviceCodes = apt.service_codes || apt.services || [];
          const hasOnlyECG = serviceCodes.length > 0 && serviceCodes.every(code => {
            const codeStr = String(code).toUpperCase();
            return codeStr.includes('ECG') || codeStr.includes('ЭКГ') || codeStr === 'ECG';
          });
          
          // Если запись содержит только ЭКГ, исключаем её
          if (hasOnlyECG) {
            return false;
          }
          
          // ✅ Проверяем, содержит ли запись консультацию кардиолога (не только ЭКГ)
          const hasCardiologyConsultation = serviceCodes.some(code => {
            const codeStr = String(code).toUpperCase();
            // Коды кардиологии: K01, K02, CARD_, CONSULTATION.CARDIOLOGY и т.д., но не ECG
            return (codeStr.startsWith('K') || codeStr.startsWith('CARD_') || codeStr.includes('CONSULT')) 
                   && !codeStr.includes('ECG') && !codeStr.includes('ЭКГ');
          });
          
          // Если есть консультация кардиолога и specialty правильный, включаем
          return isCardiology && (hasCardiologyConsultation || serviceCodes.length === 0);
        });

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
            console.log('[Cardiology] Получены appointments из БД:', appointmentsDBData.length);

            // Создаем карту id -> payment_status (используем id без смещения, так как бэкенд добавляет +20000 для Visit)
            const paymentStatusMap = new Map();
            appointmentsDBData.forEach(apt => {
              // Для Visit id уже добавлено +20000 в бэкенде, сохраняем как есть
              if (apt.id) {
                paymentStatusMap.set(apt.id, apt.payment_status || 'pending');
              }
              // Также сохраняем по patient_id+date для связи (если нужно)
              if (apt.patient_id && apt.appointment_date) {
                const key = `${apt.patient_id}_${apt.appointment_date}`;
                paymentStatusMap.set(key, apt.payment_status || 'pending');
              }
            });

            // Обновляем payment_status в наших записях
            allAppointments = allAppointments.map(apt => {
              // Пробуем найти по id
              let paymentStatus = paymentStatusMap.get(apt.id);
              // Если не нашли, пробуем по patient_id+date
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

            console.log('[Cardiology] Обновлены payment_status для', allAppointments.length, 'записей');
          }
        } catch (err) {
          console.warn('[Cardiology] Не удалось загрузить payment_status из БД:', err);
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
    
    // Слушаем глобальные события обновления очереди
    const handleQueueUpdate = (event) => {
      console.log('[Cardiology] Получено событие обновления очереди:', event.detail);
      const { action, specialty } = event.detail || {};

      // Автоматически обновляем список appointments после завершения приёма
      if (action === 'visitCompleted' || action === 'nextPatientCalled') {
        if (activeTab === 'appointments') {
          console.log('[Cardiology] Автообновление списка appointments после', action);
          loadMacOSCardiologyAppointments();
        }
      }

      // Обновляем при любых изменениях, если открыта вкладка appointments
      if (activeTab === 'appointments') {
        // Небольшая задержка, чтобы дать бэкенду время обновить статусы
        setTimeout(() => {
          loadMacOSCardiologyAppointments();
        }, 500);
      }
    };
    window.addEventListener('queueUpdated', handleQueueUpdate);
    
    return () => {
      window.removeEventListener('queueUpdated', handleQueueUpdate);
    };
  }, [activeTab]);

  // Обработчики для таблицы записей
  const handleAppointmentRowClick = async (row) => {
    console.log('[Cardiology] handleAppointmentRowClick: клик по записи', row);
    // Можно открыть детали записи или переключиться на прием
    if (row.patient_fio) {
      // Создаем объект пациента для переключения на прием
      // Важно: используем row.id как appointment_id, так как row.id - это ID appointment из таблицы appointments
      const appointmentId = row.appointment_id || row.id;
      const patientData = {
        id: row.id, // Это appointment ID
        appointment_id: appointmentId, // Явно указываем appointment_id
        patient_id: row.patient_id,
        patient_name: row.patient_fio,
        phone: row.patient_phone,
        number: row.id,
        source: 'appointments',
        status: row.status || 'waiting',
        payment_status: row.payment_status || (row.discount_mode === 'paid' ? 'paid' : 'pending'),
        discount_mode: row.discount_mode,
        specialty: row.specialty || 'cardiology'
      };
      console.log('[Cardiology] handleAppointmentRowClick: patientData', patientData);
      setSelectedPatient(patientData);
      
      // Если запись завершена - загружаем EMR для просмотра
      const isCompleted = row.status === 'served' || row.status === 'completed' || row.status === 'done';
      if (isCompleted) {
        console.log('[Cardiology] handleAppointmentRowClick: запись завершена, загружаем EMR');
        await loadEMR(appointmentId);
      } else {
        // Для незавершённых записей очищаем EMR
        setEmr(null);
      }
      
      goToTab('visit');
    }
  };

  const handleAppointmentActionClick = async (action, row, event) => {
    console.log('[Cardiology] handleAppointmentActionClick: действие', action, row);
    event.stopPropagation();

    switch (action) {
      case 'view':
        await handleAppointmentRowClick(row);
        break;
      case 'view_emr':
        // Просмотр EMR для завершённой записи
        const appointmentId = row.appointment_id || row.id;
        console.log('[Cardiology] handleAppointmentActionClick: просмотр EMR для appointment_id', appointmentId);

        // Создаем объект пациента
        const patientData = {
          id: row.id,
          appointment_id: appointmentId,
          patient_id: row.patient_id,
          patient_name: row.patient_fio,
          phone: row.patient_phone,
          number: row.id,
          source: 'appointments',
          status: row.status || 'waiting',
          payment_status: row.payment_status || (row.discount_mode === 'paid' ? 'paid' : 'pending'),
          discount_mode: row.discount_mode,
          specialty: row.specialty || 'cardiology'
        };

        setSelectedPatient(patientData);

        // Загружаем EMR
        await loadEMR(appointmentId);

        // Переходим на вкладку visit
        goToTab('visit');
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
            console.log('[Cardiology] Пациент вызван:', row.patient_fio);
            // Обновляем статус в локальном состоянии
            setAppointments(prev => prev.map(a =>
              a.id === row.id ? { ...a, status: 'called' } : a
            ));
            // Вызываем обновление списка
            await handleRefreshAppointments();
          }
        } catch (error) {
          console.error('[Cardiology] Ошибка вызова пациента:', error);
        }
        break;
      case 'payment':
        // Открыть окно оплаты
        console.log('[Cardiology] Открытие окна оплаты для:', row.patient_fio);
        // Здесь можно добавить модальное окно оплаты
        alert(`Оплата для пациента: ${row.patient_fio}\nФункция будет реализована позже`);
        break;
      case 'print':
        // Печать талона
        console.log('[Cardiology] Печать талона для:', row.patient_fio);
        window.print();
        break;
      case 'complete':
        // Завершить приём
        try {
          // Переходим на вкладку визита для завершения
          const patient = {
            id: row.id,
            appointment_id: row.appointment_id || row.id,
            patient_id: row.patient_id,
            patient_name: row.patient_fio,
            phone: row.patient_phone,
            number: row.id,
            source: 'appointments',
            status: 'in_cabinet',
            payment_status: row.payment_status,
            discount_mode: row.discount_mode,
            specialty: row.specialty || 'cardiology'
          };

          console.log('[Cardiology] Завершение приёма для:', patient.patient_name);
          setSelectedPatient(patient);

          // Загружаем EMR если есть
          await loadEMR(patient.appointment_id);

          // Переходим на вкладку visit для завершения
          goToTab('visit');
        } catch (error) {
          console.error('[Cardiology] Ошибка при завершении приёма:', error);
        }
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
    console.log('[Cardiology] onPatientSelect:', patient);
    // ✅ Очищаем EMR и visitData перед выбором нового пациента
    setEmr(null);
    setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
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
      console.log('[Cardiology] handleSaveVisit: start', { selectedEntryId: selectedPatient.id, selectedPatient });
      
      const visitPayload = {
        patient_id: selectedPatient.patient?.id || selectedPatient.patient_id || selectedPatient.id,
        complaint: visitData.complaint,
        diagnosis: visitData.diagnosis,
        icd10: visitData.icd10,
        services: selectedServices,
        notes: visitData.notes
      };
      console.log('[Cardiology] handleSaveVisit: payload', visitPayload);
      await queueService.completeVisit(selectedPatient.id, visitPayload);
      console.log('[Cardiology] handleSaveVisit: completeVisit OK');
      setMessage({ type: 'success', text: 'Прием завершен успешно' });
      
      // Очищаем форму и возвращаемся в очередь
      setSelectedPatient(null);
      setSelectedServices([]);
      setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
      setActiveTab('queue');
      
      // Автоматически вызвать следующего пациента для кардиолога
      try {
        console.log('[Cardiology] callNextWaiting(cardiology): start');
        const next = await queueService.callNextWaiting('cardiology');
        console.log('[Cardiology] callNextWaiting(cardiology): result', next);
        if (next?.success) {
          setMessage({ type: 'success', text: `Вызван следующий пациент №${next.entry.number}` });
        }
      } catch (err) {
        console.warn('[Cardiology] callNextWaiting(cardiology): failed', err);
      }

    } catch (error) {
      console.error('Ошибка сохранения визита:', error);
      setMessage({ type: 'error', text: error.message });
    } finally {
      console.log('[Cardiology] handleSaveVisit: finish');
      setLoading(false);
    }
  };

  // Загрузка EMR для просмотра
  const loadEMR = async (appointmentId) => {
    try {
      const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
      if (!appointmentId) {
        console.warn('[Cardiology] loadEMR: нет appointmentId');
        return null;
      }

      const API_BASE = (import.meta?.env?.VITE_API_BASE_URL) || 'http://localhost:8000';
      console.log('[Cardiology] loadEMR: загрузка EMR для appointment_id', appointmentId);

      const response = await fetch(`${API_BASE}/api/v1/appointments/${appointmentId}/emr`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      });

      if (response.ok) {
        const emrData = await response.json();
        console.log('[Cardiology] loadEMR: успешно загружена EMR', emrData);
        setEmr(emrData);
        return emrData;
      } else if (response.status === 404) {
        // EMR ещё не создана - это нормально
        console.log('[Cardiology] loadEMR: EMR не найдена для appointment_id', appointmentId);
        setEmr(null);
        return null;
      } else {
        const error = await response.json().catch(() => ({ detail: 'Ошибка при загрузке EMR' }));
        console.error('[Cardiology] loadEMR: ошибка', { status: response.status, error });
        setMessage({ type: 'error', text: error.detail || 'Ошибка при загрузке EMR' });
        return null;
      }
    } catch (error) {
      console.error('[Cardiology] loadEMR: исключение', error);
      setMessage({ type: 'error', text: error.message || 'Ошибка при загрузке EMR' });
      return null;
    }
  };

  // Сохранение EMR
  const saveEMR = async (emrData) => {
    try {
      const token = localStorage.getItem('auth_token') || localStorage.getItem('access_token');
      if (!selectedPatient?.id) {
        console.warn('[Cardiology] saveEMR: нет selectedPatient.id', { selectedPatient });
        setMessage({ type: 'error', text: 'Не выбран пациент для сохранения EMR' });
        return;
      }
      
      // appointmentId - это ID записи (appointment), а не ID пациента или записи из очереди
      // Приоритет: appointment_id (из очереди) > id (если это уже appointment)
      const appointmentId = selectedPatient.appointment_id || selectedPatient.id;
      const patientId = selectedPatient.patient?.id || selectedPatient.patient_id;
      
      console.log('[Cardiology] saveEMR: проверка appointmentId', {
        appointment_id: selectedPatient.appointment_id,
        id: selectedPatient.id,
        selectedPatient_keys: Object.keys(selectedPatient || {}),
        calculated_appointmentId: appointmentId
      });
      
      if (!appointmentId || appointmentId <= 0) {
        console.error('[Cardiology] saveEMR: некорректный appointmentId', { 
          appointmentId, 
          selectedPatient,
          has_appointment_id: !!selectedPatient.appointment_id,
          has_id: !!selectedPatient.id
        });
        setMessage({ type: 'error', text: `Некорректный ID записи. Проверьте наличие appointment_id или id в данных пациента.` });
        return;
      }
      
      console.log('[Cardiology] saveEMR: start', { appointmentId, patientId, emrDataKeys: Object.keys(emrData || {}) });
      
      // Используем правильный URL с backend
      const API_BASE = (import.meta?.env?.VITE_API_BASE_URL) || 'http://localhost:8000';
      
      // Backend автоматически обновит статус called/calling на in_visit при сохранении EMR
      // Не нужно пытаться обновлять статус заранее через start-visit
      
      // Подготавливаем данные для сохранения согласно EMRCreate схеме
      // appointment_id обязателен в схеме EMRCreate
      const emrPayload = {
        appointment_id: appointmentId, // Обязательное поле в EMRCreate
        complaints: emrData.complaints || null,
        anamnesis: emrData.anamnesis || null,
        examination: emrData.examination || null,
        diagnosis: emrData.diagnosis || null,
        icd10: emrData.icd10 || null,
        recommendations: emrData.recommendations || null,
        procedures: emrData.procedures || null,
        attachments: emrData.attachments ? emrData.attachments.map(att => ({
          name: att.name || '',
          type: att.type || '',
          category: att.category || '',
          // Не включаем file объект, только метаданные
        })) : null,
        is_draft: emrData.isDraft !== undefined ? emrData.isDraft : false,
        specialty: selectedPatient?.specialty || 'cardiology'
      };
      
      // Добавляем dentalData если есть (это дополнительное поле, не в базовой схеме)
      if (emrData.dentalData) {
        emrPayload.dentalData = emrData.dentalData;
      }
      
      console.log('[Cardiology] saveEMR: отправляем данные', { appointmentId, is_draft: emrPayload.is_draft, payloadKeys: Object.keys(emrPayload) });
      
      // Используем эндпоинт для сохранения EMR для appointment
      // appointment_id передается в URL, не в body
      const response = await fetch(`${API_BASE}/api/v1/appointments/${appointmentId}/emr`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(emrPayload)
      });

      if (response.ok) {
        const savedEMR = await response.json();
        setEmr(savedEMR);
        setMessage({ type: 'success', text: 'EMR сохранена успешно!' });
        console.log('[Cardiology] saveEMR: успешно', savedEMR);
        return savedEMR;
      } else {
        const error = await response.json().catch(() => ({ detail: 'Ошибка при сохранении EMR' }));
        console.error('[Cardiology] saveEMR: ошибка', { status: response.status, error });
        
        // Формируем читаемое сообщение об ошибке
        let errorMessage = 'Ошибка при сохранении EMR';
        if (error.detail) {
          if (Array.isArray(error.detail)) {
            // Если это массив ошибок валидации Pydantic
            errorMessage = error.detail.map(err => {
              if (typeof err === 'string') return err;
              if (err.loc && err.msg) {
                return `${err.loc.join('.')}: ${err.msg}`;
              }
              return JSON.stringify(err);
            }).join(', ');
          } else if (typeof error.detail === 'string') {
            errorMessage = error.detail;
          } else {
            errorMessage = JSON.stringify(error.detail);
          }
        }
        
        setMessage({ type: 'error', text: errorMessage });
        throw new Error(errorMessage);
      }
    } catch (error) {
      console.error('[Cardiology] saveEMR: исключение', error);
      setMessage({ type: 'error', text: error.message || 'Ошибка при сохранении EMR' });
      throw error;
    }
  };

  // Обработка завершения приема через EMR
  const handleCompleteVisitFromEMR = async () => {
    if (!selectedPatient) return;
    
    try {
      console.log('[Cardiology] handleCompleteVisitFromEMR: start');
      await handleSaveVisit();
    } catch (error) {
      console.error('[Cardiology] handleCompleteVisitFromEMR: ошибка', error);
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
                  {/* Статистика очереди */}
                  <MacOSBadge variant="info">
                    Всего: {appointments.length}
                  </MacOSBadge>
                  <MacOSBadge variant="warning">
                    Ожидают: {appointments.filter(a => a.status === 'waiting' || a.status === 'confirmed' || a.status === 'pending').length}
                  </MacOSBadge>
                  <MacOSBadge variant="primary">
                    Вызваны: {appointments.filter(a => a.status === 'called' || a.status === 'in_progress').length}
                  </MacOSBadge>
                  <MacOSBadge variant="success">
                    Приняты: {appointments.filter(a => a.status === 'completed' || a.status === 'done').length}
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
                  services={services}
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


            {/* Электронная медицинская карта */}
            <MacOSCard style={{ padding: '24px' }}>
              <h3 style={{
                fontSize: 'var(--mac-font-size-lg)',
                fontWeight: 'var(--mac-font-weight-semibold)',
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
                appointment={{
                  id: selectedPatient?.appointment_id || selectedPatient?.id,
                  patient_id: selectedPatient?.patient?.id || selectedPatient?.patient_id,
                  patient_name: selectedPatient?.patient_name || selectedPatient?.name,
                  status: selectedPatient?.status || 'waiting',
                  payment_status: selectedPatient?.payment_status || (selectedPatient?.discount_mode === 'paid' ? 'paid' : 'pending'),
                  specialty: 'cardiology',
                  discount_mode: selectedPatient?.discount_mode
                }}
                emr={emr}
                onSave={saveEMR}
                onComplete={handleCompleteVisitFromEMR}
              />
            </MacOSCard>

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
                  onClick={handleCompleteVisitFromEMR}
                  disabled={loading}
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
