import React, { useState, useEffect, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Select, Option, Badge, Icon } from '../components/ui/macos';
import { useTheme } from '../contexts/ThemeContext';
import AIAssistant from '../components/ai/AIAssistant';
import QueueIntegration from '../components/QueueIntegration';
import LabResultsManager from '../components/laboratory/LabResultsManager';
import LabReportGenerator from '../components/laboratory/LabReportGenerator';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';

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
  
  // Состояния для таблицы записей
  const [appointments, setAppointments] = useState([]);
  const [appointmentsLoading, setAppointmentsLoading] = useState(false);
  const [appointmentsSelected, setAppointmentsSelected] = useState(new Set());
  
  // ✅ УЛУЧШЕНИЕ: Универсальные хуки вместо дублированных состояний
  const patientModal = useModal();
  const visitModal = useModal();

  const [testForm, setTestForm] = useState({ patient_id: '', test_date: '', test_type: '', sample_type: '', notes: '' });
  const [resultForm, setResultForm] = useState({ patient_id: '', result_date: '', test_type: '', parameter: '', value: '', unit: '', reference: '', interpretation: '' });

  const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem('auth_token') || ''}` });

  useEffect(() => {
    loadPatients();
    loadTests();
    loadResults();
  }, []);

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

        // Фильтруем только лабораторные записи для отображения
        const appointmentsData = allAppointments.filter(apt => 
          apt.specialty === 'lab' || apt.specialty === 'laboratory'
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
      console.error('Ошибка загрузки записей лаборатории:', error);
    } finally {
      setAppointmentsLoading(false);
    }
  };

  // Загружаем записи при переключении на вкладку
  useEffect(() => {
    if (activeTab === 'appointments') {
      loadLabAppointments();
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
      setActiveTab('tests');
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

  const loadPatients = async () => {
    try {
      setLoading(true);
      const res = await fetch('http://localhost:8000/api/v1/patients?department=Lab&limit=100', { headers: authHeader() });
      if (res.ok) setPatients(await res.json());
    } catch {
      // Игнорируем ошибки загрузки пациентов
    } finally { setLoading(false); }
  };

  const loadTests = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/lab/tests?limit=100', { headers: authHeader() });
      if (res.ok) setTests(await res.json());
    } catch {
      // Игнорируем ошибки загрузки тестов
    }
  };

  const loadResults = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/lab/results?limit=100', { headers: authHeader() });
      if (res.ok) setResults(await res.json());
    } catch {
      // Игнорируем ошибки загрузки результатов
    }
  };

  const handleTestSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('http://localhost:8000/api/v1/lab/tests', { method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeader() }, body: JSON.stringify(testForm) });
      if (res.ok) { setShowTestForm(false); setTestForm({ patient_id: '', test_date: '', test_type: '', sample_type: '', notes: '' }); loadTests(); }
    } catch {
      // Игнорируем ошибки создания теста
    }
  };

  const handleResultSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('http://localhost:8000/api/v1/lab/results', { method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeader() }, body: JSON.stringify(resultForm) });
      if (res.ok) { setShowResultForm(false); setResultForm({ patient_id: '', result_date: '', test_type: '', parameter: '', value: '', unit: '', reference: '', interpretation: '' }); loadResults(); }
    } catch {
      // Игнорируем ошибки создания результата
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
              services={{}}
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

      {activeTab === 'queue' && (
        <QueueIntegration
          specialist="Лаборатория"
          onPatientSelect={(patient) => {
            console.log('Выбран пациент:', patient);
            patientModal.open(patient);
          }}
          onStartVisit={(appointment) => {
            console.log('Начало приема:', appointment);
            patientModal.open(appointment);
          }}
        />
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


