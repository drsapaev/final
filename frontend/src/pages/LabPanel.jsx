import { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button, Card, CardContent, CardHeader, CardTitle, Badge, Icon, Alert } from '../components/ui/macos';
import { useTheme } from '../contexts/ThemeContext';
import AIAssistant from '../components/ai/AIAssistant';
import LabResultsManager from '../components/laboratory/LabResultsManager';
import LabReportGenerator from '../components/laboratory/LabReportGenerator';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';
import EditPatientModal from '../components/common/EditPatientModal';
import AIChatWidget from '../components/ai/AIChatWidget';
import { getApiBaseUrl } from '../api/runtime';
import { resolveCanonicalVisitId } from '../utils/canonicalVisit';
import logger from '../utils/logger';
import tokenManager from '../utils/tokenManager';

const API_V1_BASE = getApiBaseUrl();

const LabPanel = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { isDark, getColor, getSpacing, getFontSize } = useTheme();

  // Синхронизация активной вкладки с URL
  const getActiveTabFromURL = useCallback(() => {
    const params = new URLSearchParams(location.search);
    // Если есть patientId, переходим на вкладку результатов
    if (params.get('patientId')) {
      return 'results';
    }
    return params.get('tab') || 'tests';
  }, [location.search]);

  // Получаем patientId из URL для автоматической загрузки пациента
  const getPatientIdFromUrl = useCallback(() => {
    const params = new URLSearchParams(location.search);
    return params.get('patientId') ? parseInt(params.get('patientId'), 10) : null;
  }, [location.search]);

  const [activeTab, setActiveTab] = useState(getActiveTabFromURL());

  // Синхронизация URL с активной вкладкой
  useEffect(() => {
    const urlTab = getActiveTabFromURL();
    if (urlTab !== activeTab) {
      setActiveTab(urlTab);
    }
  }, [activeTab, getActiveTabFromURL]);

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
  const [services, setServices] = useState({});
  const [editPatientModal, setEditPatientModal] = useState({ open: false, patient: null, loading: false });

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

  const authHeader = useCallback(
    () => ({ Authorization: `Bearer ${tokenManager.getAccessToken()}` }),
    []
  );

  // ✅ Загрузка услуг для правильного отображения в tooltips (объявлена до использования)
  const loadServices = useCallback(async () => {
    try {
      const token = tokenManager.getAccessToken();
      if (!token) return;
      const response = await fetch(`${API_V1_BASE}/registrar/services`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        const servicesData = data.services_by_group || {};
        setServices(servicesData);
        logger.info('[Lab] Услуги загружены:', Object.keys(servicesData).length, 'групп');
      }
    } catch (error) {
      logger.error('[Lab] Ошибка загрузки услуг:', error);
    }
  }, []);

  // ✅ Функции загрузки данных (объявлены до использования в useEffect)
  const loadPatients = useCallback(async () => {
    try {
      logger.info('[Lab] loadPatients: start');
      setLoading(true);
      const res = await fetch(`${API_V1_BASE}/patients?department=Lab&limit=100`, { headers: authHeader() });
      if (res.ok) {
        const data = await res.json();
        setPatients(data);
        logger.info('[Lab] loadPatients: успешно загружено', data.length, 'пациентов');
      } else {
        const errorText = await res.text();
        logger.error('[Lab] loadPatients: HTTP error', {
          status: res.status,
          statusText: res.statusText,
          error: errorText
        });
        throw new Error(`Ошибка загрузки пациентов: ${res.status} ${res.statusText}`);
      }
    } catch (error) {
      logger.error('[Lab] loadPatients: ошибка', error);
      setMessage({ type: 'error', text: 'Ошибка при загрузке списка пациентов' });
    } finally {
      setLoading(false);
      logger.info('[Lab] loadPatients: finish');
    }
  }, [authHeader, setMessage]);

  const loadTests = useCallback(async () => {
    try {
      logger.info('[Lab] loadTests: start');
      const res = await fetch(`${API_V1_BASE}/lab/tests?limit=100`, { headers: authHeader() });
      if (res.ok) {
        const data = await res.json();
        setTests(data);
        logger.info('[Lab] loadTests: успешно загружено', data.length, 'тестов');
      } else {
        const errorText = await res.text();
        logger.error('[Lab] loadTests: HTTP error', {
          status: res.status,
          statusText: res.statusText,
          error: errorText
        });
        throw new Error(`Ошибка загрузки тестов: ${res.status} ${res.statusText}`);
      }
    } catch (error) {
      logger.error('[Lab] loadTests: ошибка', error);
      setMessage({ type: 'error', text: 'Ошибка при загрузке списка тестов' });
    }
  }, [authHeader, setMessage]);

  const loadResults = useCallback(async () => {
    try {
      logger.info('[Lab] loadResults: start');
      const res = await fetch(`${API_V1_BASE}/lab/results?limit=100`, { headers: authHeader() });
      if (res.ok) {
        const data = await res.json();
        setResults(data);
        logger.info('[Lab] loadResults: успешно загружено', data.length, 'результатов');
      } else {
        const errorText = await res.text();
        logger.error('[Lab] loadResults: HTTP error', {
          status: res.status,
          statusText: res.statusText,
          error: errorText
        });
        throw new Error(`Ошибка загрузки результатов: ${res.status} ${res.statusText}`);
      }
    } catch (error) {
      logger.error('[Lab] loadResults: ошибка', error);
      setMessage({ type: 'error', text: 'Ошибка при загрузке результатов анализов' });
    }
  }, [authHeader, setMessage]);

  const [selectedPatientForResults, setSelectedPatientForResults] = useState(null);
  const [selectedVisitForResults, setSelectedVisitForResults] = useState(null);

  useEffect(() => {
    loadPatients();
    loadTests();
    loadResults();
    loadServices();
  }, [loadPatients, loadTests, loadResults, loadServices]);

  // ✅ Автоматическая загрузка пациента из URL для результатов
  useEffect(() => {
    const loadPatientFromUrl = async () => {
      const patientIdFromUrl = getPatientIdFromUrl();
      if (!patientIdFromUrl) return;

      try {
        const token = tokenManager.getAccessToken();
        if (!token) return;

        const response = await fetch(`${API_V1_BASE}/patients/${patientIdFromUrl}`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (response.ok) {
          const patientData = await response.json();
          const patientObj = {
            id: patientData.id,
            name: `${patientData.last_name || ''} ${patientData.first_name || ''}`.trim(),
            last_name: patientData.last_name,
            first_name: patientData.first_name,
            birthDate: patientData.birth_date,
            phone: patientData.phone
          };
          setSelectedPatientForResults(patientObj);
          logger.info('[Lab] Загружен пациент из URL для результатов:', patientObj.name);
        }
      } catch (error) {
        logger.error('[Lab] Не удалось загрузить пациента из URL:', error);
      }
    };

    loadPatientFromUrl();
  }, [getPatientIdFromUrl]);

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
  const loadLabAppointments = useCallback(async () => {
    setAppointmentsLoading(true);
    try {
      logger.info('[Lab] loadLabAppointments: start');
      const token = tokenManager.getAccessToken();
      if (!token) {
        logger.warn('[Lab] loadLabAppointments: нет токена аутентификации');
        setMessage({ type: 'error', text: 'Требуется авторизация. Пожалуйста, войдите в систему.' });
        setAppointmentsLoading(false);
        return;
      }

      // Загружаем ВСЕ очереди для получения полной картины услуг пациентов
      const response = await fetch(`${API_V1_BASE}/registrar/queues/today`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorText = await response.text();
        logger.error('[Lab] loadLabAppointments: HTTP error', {
          status: response.status,
          statusText: response.statusText,
          error: errorText
        });
        throw new Error(`Ошибка загрузки записей: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      logger.info('[Lab] loadLabAppointments: данные получены', { queuesCount: data?.queues?.length || 0 });

      // Собираем ВСЕ записи из всех очередей для получения полной картины услуг
      let allAppointments = [];
      if (data && data.queues && Array.isArray(data.queues)) {
        data.queues.forEach(queue => {
          if (queue.entries) {
              queue.entries.forEach(entry => {
                allAppointments.push({
                  id: entry.id,
                  appointment_id: entry.appointment_id || null,
                  visit_id: entry.visit_id || null,
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
      let appointmentsData = allAppointments.filter(apt =>
        apt.specialty === 'lab' || apt.specialty === 'laboratory'
      );
      logger.info('[Lab] loadLabAppointments: отфильтровано лабораторных записей', appointmentsData.length);

      // 2. Получаем актуальный payment_status из БД через all-appointments
      const today = new Date().toISOString().split('T')[0];
      try {
        const appointmentsResponse = await fetch(`${API_V1_BASE}/registrar/all-appointments?date_from=${today}&date_to=${today}&limit=500`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (appointmentsResponse.ok) {
          const appointmentsDBResponse = await appointmentsResponse.json();
          const appointmentsDBData = appointmentsDBResponse.data || appointmentsDBResponse || [];  // ✅ ИСПРАВЛЕНО: Извлекаем data из ответа
          logger.info('[Lab] Получены appointments из БД:', appointmentsDBData.length);

          // Создаем карту id -> payment_status
          const appointmentMetaMap = new Map();
          appointmentsDBData.forEach(apt => {
            const appointmentMeta = {
              payment_status: apt.payment_status || 'pending',
              visit_id: apt.visit_id || null,
              appointment_id: apt.appointment_id || (apt.source === 'appointments' ? apt.id : null)
            };
            if (apt.id) {
              appointmentMetaMap.set(apt.id, appointmentMeta);
            }
            if (apt.patient_id && apt.appointment_date) {
              const key = `${apt.patient_id}_${apt.appointment_date}`;
              appointmentMetaMap.set(key, appointmentMeta);
            }
          });

          // Обновляем payment_status в наших записях
          allAppointments = allAppointments.map(apt => {
            let appointmentMeta = appointmentMetaMap.get(apt.appointment_id || apt.id);
            if (!appointmentMeta && apt.patient_id && apt.appointment_date) {
              const key = `${apt.patient_id}_${apt.appointment_date}`;
              appointmentMeta = appointmentMetaMap.get(key);
            }
            return {
              ...apt,
              appointment_id: appointmentMeta?.appointment_id || apt.appointment_id,
              visit_id: appointmentMeta?.visit_id || apt.visit_id || null,
              payment_status: appointmentMeta?.payment_status || apt.payment_status || 'pending',
              payment_type: appointmentMeta?.payment_status || apt.payment_type
            };
          });
          appointmentsData = appointmentsData.map((apt) => {
            let appointmentMeta = appointmentMetaMap.get(apt.appointment_id || apt.id);
            if (!appointmentMeta && apt.patient_id && apt.appointment_date) {
              const key = `${apt.patient_id}_${apt.appointment_date}`;
              appointmentMeta = appointmentMetaMap.get(key);
            }
            return {
              ...apt,
              appointment_id: appointmentMeta?.appointment_id || apt.appointment_id,
              visit_id: appointmentMeta?.visit_id || apt.visit_id || null,
              payment_status: appointmentMeta?.payment_status || apt.payment_status || 'pending',
              payment_type: appointmentMeta?.payment_status || apt.payment_type
            };
          });

          logger.info('[Lab] Обновлены payment_status для', allAppointments.length, 'записей');
        }
      } catch (err) {
        logger.warn('[Lab] Не удалось загрузить payment_status из БД:', err);
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
      logger.info('[Lab] loadLabAppointments: успешно загружено', enrichedAppointmentsData.length, 'записей');
    } catch (error) {
      logger.error('[Lab] loadLabAppointments: ошибка', error);
      setMessage({ type: 'error', text: error.message || 'Ошибка при загрузке записей лаборатории' });
    } finally {
      setAppointmentsLoading(false);
      logger.info('[Lab] loadLabAppointments: finish');
    }
  }, [getAllPatientServices]);

  // Загружаем записи при переключении на вкладку
  useEffect(() => {
    if (activeTab === 'appointments') {
      loadLabAppointments();
    }

    // Слушаем глобальные события обновления очереди
    const handleQueueUpdate = (event) => {
      logger.info('[Lab] Получено событие обновления очереди:', event.detail);
      if (activeTab === 'appointments') {
        loadLabAppointments();
      }
    };
    window.addEventListener('queueUpdated', handleQueueUpdate);

    return () => {
      window.removeEventListener('queueUpdated', handleQueueUpdate);
    };
  }, [activeTab, loadLabAppointments]);

  const ensureCanonicalVisitId = useCallback(async (row) => {
    const appointmentId = row?.appointment_id || row?.id;
    const visitId = row?.visit_id || await resolveCanonicalVisitId(appointmentId);

    if (visitId) {
      setAppointments((prev) => prev.map((appointment) =>
        appointment.id === row.id ? { ...appointment, visit_id: visitId } : appointment
      ));
    }

    return visitId;
  }, []);

  // Функция для получения данных пациента по ID
  const fetchPatientData = useCallback(async (patientId) => {
    if (patientId >= 1000) {
      return null;
    }

    const token = tokenManager.getAccessToken();
    if (!token) return null;

    try {
      const response = await fetch(`${API_V1_BASE}/patients/${patientId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        return await response.json();
      }
    } catch (error) {
      logger.error(`Ошибка загрузки данных пациента ${patientId}:`, error);
    }
    return null;
  }, []);

  // Функция для преобразования данных пациента из формата API в формат PatientModal
  const transformPatientData = useCallback((apiPatient) => {
    if (!apiPatient) return null;

    return {
      id: apiPatient.id,
      firstName: apiPatient.first_name || '',
      lastName: apiPatient.last_name || '',
      middleName: apiPatient.middle_name || '',
      email: apiPatient.email || '',
      phone: apiPatient.phone || '',
      birthDate: apiPatient.birth_date || '',
      gender: apiPatient.sex === 'M' ? 'male' : apiPatient.sex === 'F' ? 'female' : '',
      address: apiPatient.address || '',
      passport: apiPatient.doc_number || '',
      insuranceNumber: '',
      emergencyContact: '',
      emergencyPhone: '',
      bloodType: '',
      allergies: '',
      chronicDiseases: '',
      notes: ''
    };
  }, []);

  // Функция для создания частичного объекта пациента из данных row (для QR-пациентов)
  const createPartialPatientFromRow = useCallback((row) => {
    const nameParts = (row.patient_fio || '').split(' ').filter(Boolean);
    return {
      firstName: nameParts[1] || '',
      lastName: nameParts[0] || '',
      middleName: nameParts[2] || '',
      phone: row.patient_phone || '',
      address: row.address || '',
      birthDate: row.patient_birth_year ? `${row.patient_birth_year}-01-01` : ''
    };
  }, []);

  // Обработчик редактирования пациента
  const handleEditPatient = useCallback(async (row) => {
    // Если нет patient_id (QR-пациент), используем частичные данные из row
    if (!row.patient_id) {
      logger.info('[Lab] QR-пациент без patient_id, используем частичные данные из row');
      const partialPatient = createPartialPatientFromRow(row);
      setEditPatientModal({ open: true, patient: partialPatient, loading: false });
      return;
    }

    try {
      // Показываем индикатор загрузки
      setEditPatientModal({ open: true, patient: null, loading: true });

      // Загружаем полные данные пациента
      const apiPatient = await fetchPatientData(row.patient_id);

      if (!apiPatient) {
        // Если не удалось загрузить, используем данные из row (частичные)
        const partialPatient = createPartialPatientFromRow(row);
        setEditPatientModal({ open: true, patient: partialPatient, loading: false });
        logger.warn('[Lab] Не удалось загрузить данные из API, используем частичные данные пациента из row');
        return;
      }

      // Преобразуем данные в формат PatientModal
      const transformedPatient = transformPatientData(apiPatient);
      setEditPatientModal({ open: true, patient: transformedPatient, loading: false });

    } catch (error) {
      logger.error('[Lab] Ошибка при загрузке данных пациента:', error);
      // В случае ошибки используем частичные данные
      const partialPatient = createPartialPatientFromRow(row);
      setEditPatientModal({ open: true, patient: partialPatient, loading: false });
      logger.warn('[Lab] Ошибка загрузки, используем частичные данные пациента из row');
    }
  }, [fetchPatientData, transformPatientData, createPartialPatientFromRow]);

  // Обработчики для таблицы записей
  const handleAppointmentRowClick = async (row) => {
    logger.info('Клик по записи:', row);
    if (!row.patient_fio) {
      return;
    }

    const visitId = await ensureCanonicalVisitId(row);
    if (!visitId) {
      setMessage({ type: 'error', text: 'Не удалось определить канонический visit_id для лабораторной записи' });
      return;
    }

    setSelectedPatientForResults({
      id: row.patient_id,
      name: row.patient_fio,
      phone: row.patient_phone || '',
      birthDate: row.patient_birth_year ? `${row.patient_birth_year}-01-01` : ''
    });
    setSelectedVisitForResults({
      id: visitId,
      appointment_id: row.appointment_id || row.id
    });
    handleTabChange('results');
  };

  const handleAppointmentActionClick = async (action, row, event) => {
    logger.info('[Lab] handleAppointmentActionClick:', action, row);
    event.stopPropagation();

    switch (action) {
      case 'view':
        await handleAppointmentRowClick(row);
        break;
      case 'call':
        // Вызвать пациента
        try {
          const token = tokenManager.getAccessToken();
          const response = await fetch(`${API_V1_BASE}/registrar/queue/${row.id}/start-visit`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            }
          });

          if (response.ok) {
            logger.info('[Lab] Пациент вызван:', row.patient_fio);
            await loadLabAppointments();
            setMessage({ type: 'success', text: 'Пациент вызван' });
          }
        } catch (error) {
          logger.error('[Lab] Ошибка вызова пациента:', error);
          setMessage({ type: 'error', text: 'Ошибка вызова пациента' });
        }
        break;
      case 'payment':
        logger.info('[Lab] Открытие окна оплаты для:', row.patient_fio);
        alert(`Оплата для пациента: ${row.patient_fio}\nФункция будет реализована позже`);
        break;
      case 'print':
        logger.info('[Lab] Печать талона для:', row.patient_fio);
        window.print();
        break;
      case 'complete':
        // Завершить приём
        try {
          logger.info('[Lab] Завершение приёма для:', row.patient_fio);
          await handleAppointmentRowClick(row);
        } catch (error) {
          logger.error('[Lab] Ошибка при завершении приёма:', error);
        }
        break;
      case 'edit':
        // Загружаем полные данные пациента перед открытием модального окна
        logger.info('[Lab] Открытие модального окна редактирования для:', row.patient_fio);
        await handleEditPatient(row);
        break;
      case 'cancel':
        logger.info('[Lab] Отмена записи', row.id);
        // Логика отмены записи
        break;
      default:
        logger.warn('[Lab] Неизвестное действие', action);
        break;
    }
  };

  const handleTestSubmit = async (e) => {
    e.preventDefault();
    try {
      logger.info('[Lab] handleTestSubmit: start', testForm);
      setLoading(true);
      const res = await fetch(`${API_V1_BASE}/lab/tests`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader()
        },
        body: JSON.stringify(testForm)
      });

      if (res.ok) {
        const savedTest = await res.json();
        logger.info('[Lab] handleTestSubmit: успешно создан тест', savedTest);
        setShowTestForm(false);
        setTestForm({ patient_id: '', test_date: '', test_type: '', sample_type: '', notes: '' });
        setMessage({ type: 'success', text: 'Анализ успешно создан' });
        await loadTests();
      } else {
        const errorData = await res.json().catch(() => ({ detail: `HTTP ${res.status}: ${res.statusText}` }));
        logger.error('[Lab] handleTestSubmit: HTTP error', {
          status: res.status,
          statusText: res.statusText,
          error: errorData
        });
        throw new Error(errorData.detail || `Ошибка создания теста: ${res.status} ${res.statusText}`);
      }
    } catch (error) {
      logger.error('[Lab] handleTestSubmit: ошибка', error);
      setMessage({ type: 'error', text: error.message || 'Ошибка при создании анализа' });
    } finally {
      setLoading(false);
      logger.info('[Lab] handleTestSubmit: finish');
    }
  };

  const handleResultSubmit = async (e) => {
    e.preventDefault();
    try {
      logger.info('[Lab] handleResultSubmit: start', resultForm);
      setLoading(true);
      const res = await fetch(`${API_V1_BASE}/lab/results`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader()
        },
        body: JSON.stringify(resultForm)
      });

      if (res.ok) {
        const savedResult = await res.json();
        logger.info('[Lab] handleResultSubmit: успешно создан результат', savedResult);
        setShowResultForm(false);
        setResultForm({ patient_id: '', result_date: '', test_type: '', parameter: '', value: '', unit: '', reference: '', interpretation: '' });
        setMessage({ type: 'success', text: 'Результат анализа успешно сохранен' });
        await loadResults();
      } else {
        const errorData = await res.json().catch(() => ({ detail: `HTTP ${res.status}: ${res.statusText}` }));
        logger.error('[Lab] handleResultSubmit: HTTP error', {
          status: res.status,
          statusText: res.statusText,
          error: errorData
        });
        throw new Error(errorData.detail || `Ошибка сохранения результата: ${res.status} ${res.statusText}`);
      }
    } catch (error) {
      logger.error('[Lab] handleResultSubmit: ошибка', error);
      setMessage({ type: 'error', text: error.message || 'Ошибка при сохранении результата анализа' });
    } finally {
      setLoading(false);
      logger.info('[Lab] handleResultSubmit: finish');
    }
  };

  const cardStyle = {
    background: 'var(--mac-bg-secondary)',
    border: '1px solid var(--mac-border)',
    borderRadius: 'var(--mac-radius-md)',
    boxShadow: 'var(--mac-shadow-sm)',
    marginBottom: getSpacing(4)
  };

  const cardHeaderStyle = {
    padding: getSpacing(4),
    borderBottom: '1px solid var(--mac-border)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: 'var(--mac-bg-tertiary)',
    borderRadius: 'var(--mac-radius-md) var(--mac-radius-md) 0 0'
  };

  const cardContentStyle = {
    padding: getSpacing(4),
    backgroundColor: 'var(--mac-bg-secondary)'
  };

  const formStyle = {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: getSpacing(3),
    marginBottom: getSpacing(4)
  };

  const labelStyle = {
    display: 'block',
    marginBottom: getSpacing(1),
    fontWeight: 500,
    fontSize: '14px',
    color: 'var(--mac-text-primary)'
  };

  const inputStyle = {
    width: '100%',
    padding: '8px 12px',
    border: '1px solid var(--mac-border)',
    borderRadius: 'var(--mac-radius-sm)',
    fontSize: '14px',
    backgroundColor: 'var(--mac-bg-primary)',
    color: 'var(--mac-text-primary)'
  };

  const buttonStyle = {
    padding: '8px 16px',
    backgroundColor: 'var(--mac-accent)',
    color: 'var(--mac-text-on-accent)',
    border: 'none',
    borderRadius: 'var(--mac-radius-sm)',
    cursor: 'pointer',
    marginRight: getSpacing(2),
    fontSize: '14px'
  };

  const buttonSecondaryStyle = {
    ...buttonStyle,
    backgroundColor: 'var(--mac-bg-tertiary)',
    color: 'var(--mac-text-primary)',
    border: '1px solid var(--mac-border)'
  };

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
              onRowSelect={() => { }}
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
              {selectedPatientForResults?.id && selectedVisitForResults?.id ? (
                <LabResultsManager
                  patientId={selectedPatientForResults.id}
                  visitId={selectedVisitForResults.id}
                  onUpdate={() => {
                    logger.info('Результаты обновлены');
                    setResults(prev => [...prev]);
                  }}
                />
              ) : (
                <Alert severity="info">
                  Выберите запись из вкладки "Записи", чтобы открыть результаты для канонического визита.
                </Alert>
              )}
            </CardContent>
          </Card>

          {results.length > 0 && selectedPatientForResults?.id && selectedVisitForResults?.id && (
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
                  patient={selectedPatientForResults}
                  doctor={{ name: 'Доктор Иванов', specialty: 'Терапевт' }}
                  clinic={{ name: 'Медицинская клиника' }}
                  visitId={selectedVisitForResults.id}
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
                  logger.info('AI интерпретация анализов:', suggestion);
                } else if (type === 'anomaly') {
                  logger.info('AI обнаружил аномалию:', suggestion);
                }
              }}
            />
          </div>
        </div>
      )}

      {/* Модальное окно редактирования пациента */}
      {editPatientModal.open && (
        <EditPatientModal
          isOpen={editPatientModal.open}
          onClose={() => setEditPatientModal({ open: false, patient: null, loading: false })}
          patient={editPatientModal.patient}
          onSave={async () => {
            await loadLabAppointments();
            setEditPatientModal({ open: false, patient: null, loading: false });
          }}
          loading={editPatientModal.loading}
          theme={{ isDark, getColor, getSpacing, getFontSize }}
        />
      )}

      {/* AI Chat Widget */}
      <AIChatWidget
        contextType="general"
        specialty="laboratory"
        useWebSocket={false}
        position="bottom-right"
      />
    </div>
  );
};

export default LabPanel;
