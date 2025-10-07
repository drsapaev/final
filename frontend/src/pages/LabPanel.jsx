import React, { useState, useEffect } from 'react';
import AIAssistant from '../components/ai/AIAssistant';
import LabResultsManager from '../components/laboratory/LabResultsManager';
import LabReportGenerator from '../components/laboratory/LabReportGenerator';
import EnhancedAppointmentsTable from '../components/tables/EnhancedAppointmentsTable';

// ✅ УЛУЧШЕНИЕ: Универсальные хуки для устранения дублирования
import useModal from '../hooks/useModal';

const LabPanel = () => {
  const [activeTab, setActiveTab] = useState('tests');
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
      
      const response = await fetch('http://localhost:8000/api/v1/registrar/queues/today?department=lab', {
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
          const labQueue = data.queues.find(queue => 
            queue.specialty === 'lab' || queue.specialty === 'laboratory'
          );
          
          if (labQueue && labQueue.entries) {
            appointmentsData = labQueue.entries.map(entry => ({
              id: entry.id,
              patient_fio: entry.patient_name || `${entry.patient?.first_name || ''} ${entry.patient?.last_name || ''}`.trim(),
              patient_phone: entry.patient?.phone || entry.phone || '',
              patient_birth_year: entry.patient?.birth_year || entry.birth_year || '',
              address: entry.patient?.address || entry.address || '',
              visit_type: entry.visit_type || 'Платный',
              services: entry.services || [],
              payment_type: entry.payment_status || 'Не оплачено',
              doctor: entry.doctor_name || 'Лаборатория',
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
    background: 'var(--bg-primary)',
    color: 'var(--text-primary)',
    minHeight: '100vh'
  };
  const cardStyle = { 
    background: 'var(--bg-primary)', 
    border: '1px solid var(--border-color)', 
    borderRadius: '12px', 
    marginBottom: '20px', 
    boxShadow: 'var(--shadow-md)' 
  };
  const cardHeaderStyle = { 
    padding: '20px', 
    borderBottom: '1px solid var(--border-color)', 
    display: 'flex', 
    justifyContent: 'space-between', 
    alignItems: 'center', 
    backgroundColor: '#28a745', 
    color: 'white', 
    borderRadius: '12px 12px 0 0' 
  };
  const cardContentStyle = { 
    padding: '20px' 
  };
  const buttonStyle = { 
    padding: '8px 16px', 
    backgroundColor: '#28a745', 
    color: 'white', 
    border: 'none', 
    borderRadius: '4px', 
    cursor: 'pointer', 
    marginRight: '8px', 
    fontSize: '14px' 
  };
  const buttonSecondaryStyle = { 
    ...buttonStyle, 
    backgroundColor: '#6c757d' 
  };
  const buttonSuccessStyle = { 
    ...buttonStyle, 
    backgroundColor: '#0d6efd' 
  };
  const tabsStyle = { display: 'flex', borderBottom: '1px solid #e5e5e5', marginBottom: '20px' };
  const tabStyle = { padding: '12px 20px', border: 'none', background: 'none', cursor: 'pointer', fontSize: '14px', borderBottom: '2px solid transparent' };
  const activeTabStyle = { padding: '12px 20px', border: 'none', background: 'none', cursor: 'pointer', fontSize: '14px', borderBottom: '2px solid #28a745', color: '#28a745' };
  const listItemStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px', border: '1px solid #e5e5e5', borderRadius: '4px', marginBottom: '12px' };
  const formStyle = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' };
  const inputStyle = { width: '100%', padding: '8px 12px', border: '1px solid #ddd', borderRadius: '4px', fontSize: '14px', marginBottom: '12px' };
  const labelStyle = { display: 'block', marginBottom: '4px', fontWeight: '500', fontSize: '14px' };

  return (
    <div style={pageStyle}>
      <div style={{ marginBottom: '30px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 'bold', marginBottom: '8px', color: '#28a745' }}>🧪 Лабораторная панель</h1>
        <p style={{ color: '#666', fontSize: '14px' }}>Анализы, результаты, пациенты и отчеты</p>
      </div>

      <div style={tabsStyle}>
        <button style={activeTab === 'tests' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('tests')}>🧪 Анализы</button>
        <button style={activeTab === 'appointments' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('appointments')}>📅 Записи</button>
        <button style={activeTab === 'results' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('results')}>📊 Результаты</button>
        <button style={activeTab === 'patients' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('patients')}>👥 Пациенты</button>
        <button style={activeTab === 'reports' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('reports')}>📋 Отчеты</button>
        <button style={activeTab === 'ai' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('ai')}>🧠 AI Анализ</button>
      </div>

      {activeTab === 'tests' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Лабораторные исследования</h2>
              <button style={{ ...buttonStyle, backgroundColor: 'white', color: '#28a745' }} onClick={() => setShowTestForm(true)}>➕ Новый анализ</button>
            </div>
            <div style={cardContentStyle}>
              <div>
                {tests.map((t) => (
                  <div key={t.id} style={listItemStyle}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                        <h3 style={{ margin: 0, fontSize: '16px' }}>Анализ #{t.id} — Пациент ID: {t.patient_id}</h3>
                        <span style={{ padding: '4px 8px', fontSize: '12px', borderRadius: '12px', backgroundColor: '#e8f5e8', color: '#2e7d32', marginLeft: '8px' }}>{t.test_date}</span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>Тип: {t.test_type} | Образец: {t.sample_type}</div>
                    </div>
                    <div>
                      <button style={buttonStyle}>📋 Бланк</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'appointments' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>📅 Записи в лабораторию</h2>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span style={{ fontSize: '14px', color: '#666' }}>Всего: {appointments.length}</span>
                <button 
                  style={{ ...buttonStyle, backgroundColor: 'white', color: '#28a745' }} 
                  onClick={loadLabAppointments}
                  disabled={appointmentsLoading}
                >
                  🔄 Обновить
                </button>
              </div>
            </div>
            <div style={cardContentStyle}>
              <EnhancedAppointmentsTable
                data={appointments}
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
            </div>
          </div>
        </div>
      )}

      {activeTab === 'results' && (
        <div>
          {/* Новый компонент управления результатами */}
          <LabResultsManager
            patientId={patientModal.selectedItem?.id || 'demo-patient-1'}
            visitId={visitModal.selectedItem?.id || 'demo-visit-1'}
            onUpdate={() => {
              console.log('Результаты обновлены');
              // Обновляем список результатов
              setResults(prev => [...prev]);
            }}
          />
          
          {/* Генератор отчетов */}
          {results.length > 0 && (
            <div style={{ marginTop: '20px' }}>
              <LabReportGenerator
                results={results}
                patient={patientModal.selectedItem || { name: 'Демо пациент', birthDate: '01.01.1990', phone: '+998901234567' }}
                doctor={{ name: 'Доктор Иванов', specialty: 'Терапевт' }}
                clinic={{ name: 'Медицинская клиника' }}
                visitId={visitModal.selectedItem?.id || 'demo-visit-1'}
              />
            </div>
          )}
        </div>
      )}

      {activeTab === 'patients' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Пациенты лаборатории</h2>
              <span style={{ fontSize: '14px' }}>Всего: {patients.length}</span>
            </div>
            <div style={cardContentStyle}>
              {loading ? (
                <div style={{ textAlign: 'center', padding: '40px' }}>Загрузка пациентов...</div>
              ) : (
                <div>
                  {patients.map((p) => (
                    <div key={p.id} style={listItemStyle}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                          <h3 style={{ margin: 0, fontSize: '16px' }}>{p.last_name} {p.first_name} {p.middle_name}</h3>
                          <span style={{ padding: '4px 8px', fontSize: '12px', borderRadius: '12px', backgroundColor: '#fff3cd', color: '#856404', marginLeft: '8px' }}>Лаборатория</span>
                        </div>
                        <div style={{ fontSize: '12px', color: '#666' }}>📱 {p.phone} | 📅 {p.birth_date} | 🆔 ID: {p.id}</div>
                      </div>
                      <div>
                        <button style={buttonStyle} onClick={() => { setShowTestForm(true); setTestForm({ ...testForm, patient_id: p.id }); }}>🧪 Назначить анализ</button>
                        <button style={buttonSuccessStyle} onClick={() => { setShowResultForm(true); setResultForm({ ...resultForm, patient_id: p.id }); }}>📊 Внести результат</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'reports' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Отчеты лаборатории</h2>
            </div>
            <div style={cardContentStyle}>
              <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>🚧 Модуль отчетов будет доступен в следующей версии</div>
            </div>
          </div>
        </div>
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


