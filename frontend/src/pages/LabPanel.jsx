import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Select, Option, Badge, Icon, Alert } from '../components/ui/macos';
import { useTheme } from '../contexts/ThemeContext';
import AIAssistant from '../components/ai/AIAssistant';
import LabResultsManager from '../components/laboratory/LabResultsManager';
import LabReportGenerator from '../components/laboratory/LabReportGenerator';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import { queueService } from '../services/queue';

// ✅ УЛУЧШЕНИЕ: Универсальные хуки для устранения дублирования
import useModal from '../hooks/useModal.jsx';

const LabPanel = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, getColor, getSpacing } = useTheme();
  
  // Синхронизация активной вкладки с URL
  const getActiveTabFromURL = () => {
    const params = new URLSearchParams(location.search);
    return params.get('tab') || 'tests';
  };
  
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
    navigate(`/lab-panel?tab=${tabId}`, { replace: true });
  };
  const [tests, setTests] = useState([]);
  const [results, setResults] = useState([]);
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showTestForm, setShowTestForm] = useState(false);
  const [showResultForm, setShowResultForm] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  
  // Состояния для таблицы записей
  const [appointments, setAppointments] = useState([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [appointmentsSelected, setAppointmentsSelected] = useState(new Set());
  const [services, setServices] = useState({});
  
  // ✅ УЛУЧШЕНИЕ: Универсальные хуки вместо дублированных состояний
  const patientModal = useModal();
  const visitModal = useModal();

  // Автоматическое скрытие сообщений через 5 секунд
  useEffect(() => {
    if (message.text) {
      const timer = setTimeout(() => {
        setMessage({ type: '', text: '' });
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  const [testForm, setTestForm] = useState({ patient_id: '', test_date: '', test_type: '', sample_type: '', notes: '' });
  const [resultForm, setResultForm] = useState({ patient_id: '', result_date: '', test_type: '', parameter: '', value: '', unit: '', reference: '', interpretation: '' });

  const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem('auth_token') || ''}` });

  useEffect(() => {
    loadPatients();
    loadTests();
    loadResults();
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
        console.log('[Lab] Услуги загружены:', Object.keys(servicesData).length, 'групп');
      }
    } catch (error) {
      console.error('[Lab] Ошибка загрузки услуг:', error);
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

  // Загрузка записей лаборатории
  const loadLabAppointments = async () => {
    setAppointmentsLoading(true);
    try {
      console.log('[Lab] loadLabAppointments: start');
      const token = localStorage.getItem('auth_token');
      if (!token) {
        console.warn('[Lab] loadLabAppointments: нет токена аутентификации');
        setMessage({ type: 'error', text: 'Требуется авторизация. Пожалуйста, войдите в систему.' });
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
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('[Lab] loadLabAppointments: HTTP error', {
          status: response.status,
          statusText: response.statusText,
          error: errorText
        });
        throw new Error(`Ошибка загрузки записей: ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log('[Lab] loadLabAppointments: данные получены', { queuesCount: data?.queues?.length || 0 });
      
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

      // Фильтруем только лабораторные записи для отображения
      const appointmentsData = allAppointments.filter(apt =>
        apt.specialty === 'lab' || apt.specialty === 'laboratory'
      );
      console.log('[Lab] loadLabAppointments: отфильтровано лабораторных записей', appointmentsData.length);

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
          console.log('[Lab] Получены appointments из БД:', appointmentsDBData.length);

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

          console.log('[Lab] Обновлены payment_status для', allAppointments.length, 'записей');
        }
      } catch (err) {
        console.warn('[Lab] Не удалось загрузить payment_status из БД:', err);
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
      console.log('[Lab] loadLabAppointments: успешно загружено', enrichedAppointmentsData.length, 'записей');
    } catch (error) {
      console.error('[Lab] loadLabAppointments: ошибка', error);
      setMessage({ type: 'error', text: error.message || 'Ошибка при загрузке записей лаборатории' });
    } finally {
      setAppointmentsLoading(false);
      console.log('[Lab] loadLabAppointments: finish');
    }
  };

  // Загружаем записи при переключении на вкладку
  useEffect(() => {
    if (activeTab === 'appointments') {
      loadLabAppointments();
    }
    
    // Слушаем глобальные события обновления очереди
    const handleQueueUpdate = (event) => {
      console.log('[Lab] Получено событие обновления очереди:', event.detail);
      if (activeTab === 'appointments') {
        loadLabAppointments();
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
      setActiveTab('tests');
    }
  };

  const handleAppointmentActionClick = async (action, row, event) => {
    console.log('[Lab] handleAppointmentActionClick:', action, row);
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
            console.log('[Lab] Пациент вызван:', row.patient_fio);
            await loadLabAppointments();
            setMessage({ type: 'success', text: 'Пациент вызван' });
          }
        } catch (error) {
          console.error('[Lab] Ошибка вызова пациента:', error);
          setMessage({ type: 'error', text: 'Ошибка вызова пациента' });
        }
        break;
      case 'payment':
        console.log('[Lab] Открытие окна оплаты для:', row.patient_fio);
        alert(`Оплата для пациента: ${row.patient_fio}\nФункция будет реализована позже`);
        break;
      case 'print':
        console.log('[Lab] Печать талона для:', row.patient_fio);
        window.print();
        break;
      case 'complete':
        // Завершить приём
        try {
          console.log('[Lab] Завершение приёма для:', row.patient_fio);
          handleTabChange('tests');
        } catch (error) {
          console.error('[Lab] Ошибка при завершении приёма:', error);
        }
        break;
      case 'edit':
        console.log('[Lab] Редактирование записи', row.id);
        // Логика редактирования записи
        break;
      case 'cancel':
        console.log('[Lab] Отмена записи', row.id);
        // Логика отмены записи
        break;
      default:
        console.warn('[Lab] Неизвестное действие', action);
        break;
    }
  };

  const loadPatients = async () => {
    try {
      console.log('[Lab] loadPatients: start');
      setLoading(true);
      const res = await fetch('http://localhost:8000/api/v1/patients?department=Lab&limit=100', { headers: authHeader() });
      if (res.ok) {
        const data = await res.json();
        setPatients(data);
        console.log('[Lab] loadPatients: успешно загружено', data.length, 'пациентов');
      } else {
        const errorText = await res.text();
        console.error('[Lab] loadPatients: HTTP error', {
          status: res.status,
          statusText: res.statusText,
          error: errorText
        });
        throw new Error(`Ошибка загрузки пациентов: ${res.status} ${res.statusText}`);
      }
    } catch (error) {
      console.error('[Lab] loadPatients: ошибка', error);
      setMessage({ type: 'error', text: 'Ошибка при загрузке списка пациентов' });
    } finally {
      setLoading(false);
      console.log('[Lab] loadPatients: finish');
    }
  };

  const loadTests = async () => {
    try {
      console.log('[Lab] loadTests: start');
      const res = await fetch('http://localhost:8000/api/v1/lab/tests?limit=100', { headers: authHeader() });
      if (res.ok) {
        const data = await res.json();
        setTests(data);
        console.log('[Lab] loadTests: успешно загружено', data.length, 'тестов');
      } else {
        const errorText = await res.text();
        console.error('[Lab] loadTests: HTTP error', {
          status: res.status,
          statusText: res.statusText,
          error: errorText
        });
        throw new Error(`Ошибка загрузки тестов: ${res.status} ${res.statusText}`);
      }
    } catch (error) {
      console.error('[Lab] loadTests: ошибка', error);
      setMessage({ type: 'error', text: 'Ошибка при загрузке списка тестов' });
    }
  };

  const loadResults = async () => {
    try {
      console.log('[Lab] loadResults: start');
      const res = await fetch('http://localhost:8000/api/v1/lab/results?limit=100', { headers: authHeader() });
      if (res.ok) {
        const data = await res.json();
        setResults(data);
        console.log('[Lab] loadResults: успешно загружено', data.length, 'результатов');
      } else {
        const errorText = await res.text();
        console.error('[Lab] loadResults: HTTP error', {
          status: res.status,
          statusText: res.statusText,
          error: errorText
        });
        throw new Error(`Ошибка загрузки результатов: ${res.status} ${res.statusText}`);
      }
    } catch (error) {
      console.error('[Lab] loadResults: ошибка', error);
      setMessage({ type: 'error', text: 'Ошибка при загрузке результатов анализов' });
    }
  };

  const handleTestSubmit = async (e) => {
    e.preventDefault();
    try {
      console.log('[Lab] handleTestSubmit: start', testForm);
      setLoading(true);
      const res = await fetch('http://localhost:8000/api/v1/lab/tests', { 
        method: 'POST', 
        headers: { 
          'Content-Type': 'application/json', 
          ...authHeader() 
        }, 
        body: JSON.stringify(testForm) 
      });
      
      if (res.ok) {
        const savedTest = await res.json();
        console.log('[Lab] handleTestSubmit: успешно создан тест', savedTest);
        setShowTestForm(false);
        setTestForm({ patient_id: '', test_date: '', test_type: '', sample_type: '', notes: '' });
        setMessage({ type: 'success', text: 'Анализ успешно создан' });
        await loadTests();
      } else {
        const errorData = await res.json().catch(() => ({ detail: `HTTP ${res.status}: ${res.statusText}` }));
        console.error('[Lab] handleTestSubmit: HTTP error', {
          status: res.status,
          statusText: res.statusText,
          error: errorData
        });
        throw new Error(errorData.detail || `Ошибка создания теста: ${res.status} ${res.statusText}`);
      }
    } catch (error) {
      console.error('[Lab] handleTestSubmit: ошибка', error);
      setMessage({ type: 'error', text: error.message || 'Ошибка при создании анализа' });
    } finally {
      setLoading(false);
      console.log('[Lab] handleTestSubmit: finish');
    }
  };

  const handleResultSubmit = async (e) => {
    e.preventDefault();
    try {
      console.log('[Lab] handleResultSubmit: start', resultForm);
      setLoading(true);
      const res = await fetch('http://localhost:8000/api/v1/lab/results', { 
        method: 'POST', 
        headers: { 
          'Content-Type': 'application/json', 
          ...authHeader() 
        }, 
        body: JSON.stringify(resultForm) 
      });
      
      if (res.ok) {
        const savedResult = await res.json();
        console.log('[Lab] handleResultSubmit: успешно создан результат', savedResult);
        setShowResultForm(false);
        setResultForm({ patient_id: '', result_date: '', test_type: '', parameter: '', value: '', unit: '', reference: '', interpretation: '' });
        setMessage({ type: 'success', text: 'Результат анализа успешно сохранен' });
        await loadResults();
      } else {
        const errorData = await res.json().catch(() => ({ detail: `HTTP ${res.status}: ${res.statusText}` }));
        console.error('[Lab] handleResultSubmit: HTTP error', {
          status: res.status,
          statusText: res.statusText,
          error: errorData
        });
        throw new Error(errorData.detail || `Ошибка сохранения результата: ${res.status} ${res.statusText}`);
      }
    } catch (error) {
      console.error('[Lab] handleResultSubmit: ошибка', error);
      setMessage({ type: 'error', text: error.message || 'Ошибка при сохранении результата анализа' });
    } finally {
      setLoading(false);
      console.log('[Lab] handleResultSubmit: finish');
    }
  };

  const pageStyle = { 
    padding: '20px', 
    maxWidth: '1400px', 
    margin: '0 auto', 
    fontFamily: 'system-ui, -apple-system, sans-serif',
    background: 'var(--mac-bg-primary)',
    color: 'var(--mac-text-primary)',
    minHeight: '100vh'
  };
  const cardStyle = { 
    background: 'var(--mac-bg-secondary)', 
    border: '1px solid var(--mac-border)', 
    borderRadius: 'var(--mac-radius-md)', 
    marginBottom: '20px', 
    boxShadow: 'var(--mac-shadow-sm)' 
  };
  const cardHeaderStyle = { 
    padding: '20px', 
    borderBottom: '1px solid var(--mac-border)', 
    display: 'flex', 
    justifyContent: 'space-between', 
    alignItems: 'center', 
    backgroundColor: 'var(--mac-bg-tertiary)', 
    color: 'var(--mac-text-primary)', 
    borderRadius: 'var(--mac-radius-md) var(--mac-radius-md) 0 0' 
  };
  const cardContentStyle = { 
    padding: '20px',
    backgroundColor: 'var(--mac-bg-secondary)'
  };
  const buttonStyle = { 
    padding: '8px 16px', 
    backgroundColor: 'var(--mac-accent)', 
    color: 'var(--mac-text-on-accent)', 
    border: 'none', 
    borderRadius: 'var(--mac-radius-sm)', 
    cursor: 'pointer', 
    marginRight: '8px', 
    fontSize: '14px',
    transition: 'all var(--mac-duration-normal) var(--mac-ease)'
  };
  const buttonSecondaryStyle = { 
    ...buttonStyle, 
    backgroundColor: 'var(--mac-bg-tertiary)',
    color: 'var(--mac-text-primary)',
    border: '1px solid var(--mac-border)'
  };
  const buttonSuccessStyle = { 
    ...buttonStyle, 
    backgroundColor: 'var(--mac-success)' 
  };
  const tabsStyle = { display: 'flex', borderBottom: '1px solid var(--mac-border)', marginBottom: '20px' };
  const tabStyle = { padding: '12px 20px', border: 'none', background: 'none', cursor: 'pointer', fontSize: '14px', borderBottom: '2px solid transparent', color: 'var(--mac-text-secondary)' };
  const activeTabStyle = { padding: '12px 20px', border: 'none', background: 'none', cursor: 'pointer', fontSize: '14px', borderBottom: '2px solid var(--mac-accent)', color: 'var(--mac-accent)' };
  const listItemStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px', border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-sm)', marginBottom: '12px', backgroundColor: 'var(--mac-bg-primary)' };
  const formStyle = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' };
  const inputStyle = { width: '100%', padding: '8px 12px', border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-sm)', fontSize: '14px', marginBottom: '12px', backgroundColor: 'var(--mac-bg-primary)', color: 'var(--mac-text-primary)' };
  const labelStyle = { display: 'block', marginBottom: '4px', fontWeight: '500', fontSize: '14px', color: 'var(--mac-text-primary)' };

  return (
    <div style={{
      boxSizing: 'border-box',
      width: '100%',
      minHeight: 'calc(100vh - 120px)',
      background: 'var(--mac-bg-primary)',
      color: 'var(--mac-text-primary)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif'
    }}>
      {/* Сообщения об ошибках/успехе */}
      {message.text && (
        <div style={{ padding: '12px', marginBottom: '16px' }}>
          <Alert 
            severity={message.type === 'error' ? 'error' : message.type === 'success' ? 'success' : 'info'}
            onClose={() => setMessage({ type: '', text: '' })}
          >
            {message.text}
          </Alert>
        </div>
      )}

      {activeTab === 'tests' && (
        <Card 
          variant="filled"
          padding="none"
          style={{ 
            marginBottom: getSpacing(4)
          }}
        >
          <CardHeader style={{
            backgroundColor: 'var(--mac-bg-tertiary)',
            borderBottom: '1px solid var(--mac-border)',
            padding: getSpacing(4)
          }}>
            <CardTitle style={{ 
              color: 'var(--mac-text-primary)',
              fontSize: '18px',
              fontWeight: '600',
              margin: 0
            }}>
              Лабораторные исследования
            </CardTitle>
            <Button 
              variant="primary" 
              onClick={() => setShowTestForm(true)}
              style={{ marginLeft: 'auto' }}
            >
              <Icon name="plus" size={16} />
              Новый анализ
            </Button>
          </CardHeader>
          <CardContent style={{
            padding: getSpacing(4),
            backgroundColor: 'var(--mac-bg-secondary)'
          }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing(4) }}>
              {tests.map((t) => (
                <div 
                  key={t.id} 
                  style={{ 
                    backgroundColor: 'var(--mac-bg-primary)',
                    border: '1px solid var(--mac-border)',
                    borderRadius: 'var(--mac-radius-md)',
                    boxShadow: 'var(--mac-shadow-sm)',
                    transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: getSpacing(2) }}>
                        <h3 style={{ 
                          margin: 0, 
                          fontSize: '16px', 
                          fontWeight: '600',
                          color: 'var(--mac-text-primary)'
                        }}>
                          Анализ #{t.id} — Пациент ID: {t.patient_id}
                        </h3>
                        <Badge variant="success" style={{ marginLeft: getSpacing(2) }}>
                          {t.test_date}
                        </Badge>
                      </div>
                      <div style={{ 
                        fontSize: '14px', 
                        color: 'var(--mac-text-secondary)',
                        lineHeight: '1.4'
                      }}>
                        Тип: {t.test_type} | Образец: {t.sample_type}
                      </div>
                    </div>
                    <Button variant="outline" size="small">
                      <Icon name="doc.text" size={16} />
                      Бланк
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === 'appointments' && (
        <Card 
          variant="filled"
          padding="none"
          style={{ 
            marginBottom: getSpacing(4)
          }}
        >
          <CardHeader style={{
            backgroundColor: 'var(--mac-bg-tertiary)',
            borderBottom: '1px solid var(--mac-border)',
            padding: getSpacing(4)
          }}>
            <CardTitle style={{ 
              color: 'var(--mac-text-primary)',
              fontSize: '18px',
              fontWeight: '600',
              margin: 0
            }}>
              <Icon name="calendar" size={20} style={{ marginRight: getSpacing(2) }} />
              Записи в лабораторию
            </CardTitle>
            <div style={{ display: 'flex', alignItems: 'center', gap: getSpacing(2) }}>
              <Badge variant="info">Всего: {appointments.length}</Badge>
              <Badge variant="warning">
                Ожидают: {appointments.filter(a => a.status === 'waiting' || a.status === 'confirmed' || a.status === 'pending').length}
              </Badge>
              <Badge variant="primary">
                Вызваны: {appointments.filter(a => a.status === 'called' || a.status === 'in_progress').length}
              </Badge>
              <Badge variant="success">
                Приняты: {appointments.filter(a => a.status === 'completed' || a.status === 'done').length}
              </Badge>
              <Button
                variant="outline"
                onClick={loadLabAppointments}
                disabled={appointmentsLoading}
              >
                <Icon name="arrow.clockwise" size={16} />
                Обновить
              </Button>
            </div>
          </CardHeader>
          <CardContent style={{
            padding: getSpacing(4),
            backgroundColor: 'var(--mac-bg-secondary)'
          }}>
            <EnhancedAppointmentsTable
              data={appointments}
              loading={appointmentsLoading}
              theme="light"
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
          </CardContent>
        </Card>
      )}

      {activeTab === 'results' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing(4) }}>
          <Card 
            variant="filled"
            padding="none"
          >
            <CardHeader style={{
              backgroundColor: 'var(--mac-bg-tertiary)',
              borderBottom: '1px solid var(--mac-border)',
              padding: getSpacing(4)
            }}>
              <CardTitle style={{ 
                color: 'var(--mac-text-primary)',
                fontSize: '18px',
                fontWeight: '600',
                margin: 0
              }}>
                <Icon name="chart.bar" size={20} style={{ marginRight: getSpacing(2) }} />
                Результаты анализов
              </CardTitle>
            </CardHeader>
            <CardContent style={{
              padding: getSpacing(4),
              backgroundColor: 'var(--mac-bg-secondary)'
            }}>
              <LabResultsManager
                patientId={patientModal.selectedItem?.id || 'demo-patient-1'}
                visitId={visitModal.selectedItem?.id || 'demo-visit-1'}
                onUpdate={() => {
                  console.log('Результаты обновлены');
                  setResults(prev => [...prev]);
                }}
              />
            </CardContent>
          </Card>
          
          {results.length > 0 && (
            <Card 
              variant="filled"
              padding="none"
            >
              <CardHeader style={{
                backgroundColor: 'var(--mac-bg-tertiary)',
                borderBottom: '1px solid var(--mac-border)',
                padding: getSpacing(4)
              }}>
                <CardTitle style={{ 
                  color: 'var(--mac-text-primary)',
                  fontSize: '18px',
                  fontWeight: '600',
                  margin: 0
                }}>
                  <Icon name="doc.text" size={20} style={{ marginRight: getSpacing(2) }} />
                  Генератор отчетов
                </CardTitle>
              </CardHeader>
              <CardContent style={{
                padding: getSpacing(4),
                backgroundColor: 'var(--mac-bg-secondary)'
              }}>
                <LabReportGenerator
                  results={results}
                  patient={patientModal.selectedItem || { name: 'Демо пациент', birthDate: '01.01.1990', phone: '+998901234567' }}
                  doctor={{ name: 'Доктор Иванов', specialty: 'Терапевт' }}
                  clinic={{ name: 'Медицинская клиника' }}
                  visitId={visitModal.selectedItem?.id || 'demo-visit-1'}
                />
              </CardContent>
            </Card>
          )}
        </div>
      )}


      {activeTab === 'patients' && (
        <Card 
          variant="filled"
          padding="none"
          style={{ 
            marginBottom: getSpacing(4)
          }}
        >
          <CardHeader style={{
            backgroundColor: 'var(--mac-bg-tertiary)',
            borderBottom: '1px solid var(--mac-border)',
            padding: getSpacing(4)
          }}>
            <CardTitle style={{ 
              color: 'var(--mac-text-primary)',
              fontSize: '18px',
              fontWeight: '600',
              margin: 0
            }}>
              <Icon name="person.2" size={20} style={{ marginRight: getSpacing(2) }} />
              Пациенты лаборатории
            </CardTitle>
            <Badge variant="info">Всего: {patients.length}</Badge>
          </CardHeader>
          <CardContent style={{
            padding: getSpacing(4),
            backgroundColor: 'var(--mac-bg-secondary)'
          }}>
            {loading ? (
              <div style={{ textAlign: 'center', padding: getSpacing(8) }}>
                <Icon name="arrow.clockwise" size={24} style={{ animation: 'spin 1s linear infinite' }} />
                <div style={{ marginTop: getSpacing(2) }}>Загрузка пациентов...</div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: getSpacing(4) }}>
                {patients.map((p) => (
                  <div 
                    key={p.id} 
                    style={{ 
                      backgroundColor: 'var(--mac-bg-primary)',
                      border: '1px solid var(--mac-border)',
                      borderRadius: 'var(--mac-radius-md)',
                      boxShadow: 'var(--mac-shadow-sm)',
                      transition: 'all var(--mac-duration-normal) var(--mac-ease)'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', marginBottom: getSpacing(2) }}>
                          <h3 style={{ 
                            margin: 0, 
                            fontSize: '16px', 
                            fontWeight: '600',
                            color: 'var(--mac-text-primary)'
                          }}>
                            {p.last_name} {p.first_name} {p.middle_name}
                          </h3>
                          <Badge variant="warning" style={{ marginLeft: getSpacing(2) }}>
                            Лаборатория
                          </Badge>
                        </div>
                        <div style={{ 
                          fontSize: '14px', 
                          color: 'var(--mac-text-secondary)',
                          lineHeight: '1.4'
                        }}>
                          <Icon name="phone" size={14} style={{ marginRight: getSpacing(1) }} />
                          {p.phone} | 
                          <Icon name="calendar" size={14} style={{ marginLeft: getSpacing(1), marginRight: getSpacing(1) }} />
                          {p.birth_date} | 
                          <Icon name="person.badge" size={14} style={{ marginLeft: getSpacing(1), marginRight: getSpacing(1) }} />
                          ID: {p.id}
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: getSpacing(2) }}>
                        <Button 
                          variant="primary" 
                          size="small"
                          onClick={() => { setShowTestForm(true); setTestForm({ ...testForm, patient_id: p.id }); }}
                        >
                          <Icon name="testtube.2" size={16} />
                          Назначить анализ
                        </Button>
                        <Button 
                          variant="outline" 
                          size="small"
                          onClick={() => { setShowResultForm(true); setResultForm({ ...resultForm, patient_id: p.id }); }}
                        >
                          <Icon name="chart.bar" size={16} />
                          Внести результат
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === 'reports' && (
        <Card 
          variant="filled"
          padding="none"
          style={{ 
            marginBottom: getSpacing(4)
          }}
        >
          <CardHeader style={{
            backgroundColor: 'var(--mac-bg-tertiary)',
            borderBottom: '1px solid var(--mac-border)',
            padding: getSpacing(4)
          }}>
            <CardTitle style={{ 
              color: 'var(--mac-text-primary)',
              fontSize: '18px',
              fontWeight: '600',
              margin: 0
            }}>
              <Icon name="doc.text" size={20} style={{ marginRight: getSpacing(2) }} />
              Отчеты лаборатории
            </CardTitle>
          </CardHeader>
          <CardContent style={{
            padding: getSpacing(4),
            backgroundColor: 'var(--mac-bg-secondary)'
          }}>
            <div style={{ 
              textAlign: 'center', 
              padding: getSpacing(8), 
              color: 'var(--mac-text-secondary)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: getSpacing(2)
            }}>
              <Icon name="hammer" size={48} style={{ opacity: 0.5 }} />
              <div style={{ fontSize: '16px', fontWeight: '500' }}>
                Модуль отчетов будет доступен в следующей версии
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {showTestForm && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <h2 style={{ margin: 0, fontSize: '18px' }}>Новый анализ</h2>
          </div>
          <div style={cardContentStyle}>
            <form onSubmit={handleTestSubmit}>
              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Дата анализа *</label>
                  <input style={inputStyle} type="date" value={testForm.test_date} onChange={(e) => setTestForm({ ...testForm, test_date: e.target.value })} required />
                </div>
                <div>
                  <label style={labelStyle}>Тип анализа *</label>
                  <select style={inputStyle} value={testForm.test_type} onChange={(e) => setTestForm({ ...testForm, test_type: e.target.value })} required>
                    <option value="">Выберите</option>
                    <option value="cbc">ОАК</option>
                    <option value="biochem">Биохимия</option>
                    <option value="urine">Анализ мочи</option>
                    <option value="immuno">Иммунология</option>
                  </select>
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Тип образца</label>
                  <select style={inputStyle} value={testForm.sample_type} onChange={(e) => setTestForm({ ...testForm, sample_type: e.target.value })}>
                    <option value="">Выберите</option>
                    <option value="blood">Кровь</option>
                    <option value="urine">Моча</option>
                    <option value="swab">Мазок</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Примечания</label>
                  <input style={inputStyle} value={testForm.notes} onChange={(e) => setTestForm({ ...testForm, notes: e.target.value })} placeholder="Комментарий" />
                </div>
              </div>

              <div>
                <button type="submit" style={buttonStyle}>💾 Сохранить анализ</button>
                <button type="button" style={buttonSecondaryStyle} onClick={() => setShowTestForm(false)}>Отмена</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showResultForm && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <h2 style={{ margin: 0, fontSize: '18px' }}>Новый результат</h2>
          </div>
          <div style={cardContentStyle}>
            <form onSubmit={handleResultSubmit}>
              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Дата результата *</label>
                  <input style={inputStyle} type="date" value={resultForm.result_date} onChange={(e) => setResultForm({ ...resultForm, result_date: e.target.value })} required />
                </div>
                <div>
                  <label style={labelStyle}>Тип анализа *</label>
                  <select style={inputStyle} value={resultForm.test_type} onChange={(e) => setResultForm({ ...resultForm, test_type: e.target.value })} required>
                    <option value="">Выберите</option>
                    <option value="cbc">ОАК</option>
                    <option value="biochem">Биохимия</option>
                    <option value="urine">Анализ мочи</option>
                    <option value="immuno">Иммунология</option>
                  </select>
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Параметр *</label>
                  <input style={inputStyle} value={resultForm.parameter} onChange={(e) => setResultForm({ ...resultForm, parameter: e.target.value })} required placeholder="Например: Гемоглобин" />
                </div>
                <div>
                  <label style={labelStyle}>Значение *</label>
                  <input style={inputStyle} value={resultForm.value} onChange={(e) => setResultForm({ ...resultForm, value: e.target.value })} required placeholder="Например: 135" />
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Единица</label>
                  <input style={inputStyle} value={resultForm.unit} onChange={(e) => setResultForm({ ...resultForm, unit: e.target.value })} placeholder="г/л, ммоль/л и т.п." />
                </div>
                <div>
                  <label style={labelStyle}>Референс</label>
                  <input style={inputStyle} value={resultForm.reference} onChange={(e) => setResultForm({ ...resultForm, reference: e.target.value })} placeholder="Нормальные диапазоны" />
                </div>
              </div>

              <div>
                <label style={labelStyle}>Интерпретация</label>
                <textarea style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }} value={resultForm.interpretation} onChange={(e) => setResultForm({ ...resultForm, interpretation: e.target.value })} placeholder="Клиническая интерпретация" />
              </div>

              <div>
                <button type="submit" style={buttonStyle}>💾 Сохранить результат</button>
                <button type="button" style={buttonSecondaryStyle} onClick={() => setShowResultForm(false)}>Отмена</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* AI Анализ */}
      {activeTab === 'ai' && (
        <div style={cardStyle}>
          <div style={cardContentStyle}>
            <AIAssistant
              specialty="laboratory"
              onSuggestionSelect={(type, suggestion) => {
                if (type === 'interpretation') {
                  console.log('AI интерпретация анализов:', suggestion);
                } else if (type === 'anomaly') {
                  console.log('AI обнаружил аномалию:', suggestion);
                }
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default LabPanel;


