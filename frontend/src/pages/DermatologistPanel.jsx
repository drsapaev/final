import React, { useState, useEffect, useMemo } from 'react';
import ServiceChecklist from '../components/ServiceChecklist';
import EMRSystem from '../components/EMRSystem';
import PrescriptionSystem from '../components/PrescriptionSystem';
import VisitTimeline from '../components/VisitTimeline';
import QueueIntegration from '../components/QueueIntegration';
import AIAssistant from '../components/ai/AIAssistant';
import { APPOINTMENT_STATUS } from '../constants/appointmentStatus';

const DermatologistPanel = () => {
  const [activeTab, setActiveTab] = useState('patients');
  const [patients, setPatients] = useState([]);
  const [skinExaminations, setSkinExaminations] = useState([]);
  const [cosmeticProcedures, setCosmeticProcedures] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [showExaminationForm, setShowExaminationForm] = useState(false);
  const [showProcedureForm, setShowProcedureForm] = useState(false);
  
  // Состояние для жесткого потока
  const [currentAppointment, setCurrentAppointment] = useState(null);
  const [emr, setEmr] = useState(null);
  const [prescription, setPrescription] = useState(null);

  // Дерма: выбор услуг и цена от врача
  const [selectedServices, setSelectedServices] = useState([]);
  const [doctorPrice, setDoctorPrice] = useState('');

  // Локальный справочник цен для дерма/косметологии (синхронен с ServiceChecklist)
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

  const [examinationForm, setExaminationForm] = useState({
    patient_id: '',
    examination_date: '',
    skin_type: '',
    skin_condition: '',
    lesions: '',
    distribution: '',
    symptoms: '',
    diagnosis: '',
    treatment_plan: '',
    follow_up: ''
  });

  const [procedureForm, setProcedureForm] = useState({
    patient_id: '',
    procedure_date: '',
    procedure_type: '',
    area_treated: '',
    technique: '',
    products_used: '',
    duration: '',
    results: '',
    recommendations: ''
  });

  useEffect(() => {
    loadPatients();
    loadSkinExaminations();
    loadCosmeticProcedures();
  }, []);

  const authHeader = () => ({
    Authorization: `Bearer ${localStorage.getItem('auth_token') || ''}`,
  });

  const loadPatients = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/patients?department=Derma&limit=100', {
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
      const response = await fetch('/api/v1/derma/examinations?limit=100', {
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
      const response = await fetch('/api/v1/derma/procedures?limit=100', {
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

  const handleExaminationSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('/api/v1/derma/examinations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader(),
        },
        body: JSON.stringify(examinationForm),
      });
      if (response.ok) {
        setShowExaminationForm(false);
        setExaminationForm({
          patient_id: '',
          examination_date: '',
          skin_type: '',
          skin_condition: '',
          lesions: '',
          distribution: '',
          symptoms: '',
          diagnosis: '',
          treatment_plan: '',
          follow_up: '',
        });
        loadSkinExaminations();
      }
    } catch (error) {
      console.error('Ошибка сохранения осмотра:', error);
    }
  };

  const handleProcedureSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('/api/v1/derma/procedures', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader(),
        },
        body: JSON.stringify({
          ...procedureForm,
          services: selectedServices,
          services_subtotal: servicesSubtotal,
          doctor_price: doctorPriceNum,
          total_cost: totalCost,
        }),
      });
      if (response.ok) {
        setShowProcedureForm(false);
        setProcedureForm({
          patient_id: '',
          procedure_date: '',
          procedure_type: '',
          area_treated: '',
          technique: '',
          products_used: '',
          duration: '',
          results: '',
          recommendations: '',
        });
        setSelectedServices([]);
        setDoctorPrice('');
        loadCosmeticProcedures();
      }
    } catch (error) {
      console.error('Ошибка сохранения процедуры:', error);
    }
  };

  // Функции для жесткого потока
  const startVisit = async (appointment) => {
    try {
      const response = await fetch(`/api/v1/appointments/${appointment.id}/start-visit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });

      if (response.ok) {
        const updatedAppointment = await response.json();
        setCurrentAppointment(updatedAppointment);
        alert('Прием начат успешно!');
      } else {
        const error = await response.json();
        alert(error.detail || 'Ошибка при начале приема');
      }
    } catch (error) {
      console.error('DermatologistPanel: Start visit error:', error);
      alert('Ошибка при начале приема');
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
        alert('EMR сохранена успешно!');
      } else {
        const error = await response.json();
        alert(error.detail || 'Ошибка при сохранении EMR');
      }
    } catch (error) {
      console.error('DermatologistPanel: Save EMR error:', error);
      alert('Ошибка при сохранении EMR');
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
        alert('Рецепт сохранен успешно!');
      } else {
        const error = await response.json();
        alert(error.detail || 'Ошибка при сохранении рецепта');
      }
    } catch (error) {
      console.error('DermatologistPanel: Save prescription error:', error);
      alert('Ошибка при сохранении рецепта');
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
        alert('Прием завершен успешно!');
        // Сброс состояния
        setCurrentAppointment(null);
        setEmr(null);
        setPrescription(null);
      } else {
        const error = await response.json();
        alert(error.detail || 'Ошибка при завершении приема');
      }
    } catch (error) {
      console.error('DermatologistPanel: Complete visit error:', error);
      alert('Ошибка при завершении приема');
    }
  };

  const pageStyle = { padding: '20px', maxWidth: '1400px', margin: '0 auto', fontFamily: 'system-ui, -apple-system, sans-serif' };
  const cardStyle = { background: '#fff', border: '1px solid #e5e5e5', borderRadius: '8px', marginBottom: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' };
  const cardHeaderStyle = { padding: '20px', borderBottom: '1px solid #e5e5e5', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#fd7e14', color: 'white', borderRadius: '8px 8px 0 0' };
  const cardContentStyle = { padding: '20px' };
  const buttonStyle = { padding: '8px 16px', backgroundColor: '#fd7e14', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', marginRight: '8px', fontSize: '14px' };
  const buttonSecondaryStyle = { ...buttonStyle, backgroundColor: '#6c757d' };
  const buttonSuccessStyle = { ...buttonStyle, backgroundColor: '#28a745' };
  const tabsStyle = { display: 'flex', borderBottom: '1px solid #e5e5e5', marginBottom: '20px' };
  const tabStyle = { padding: '12px 20px', border: 'none', background: 'none', cursor: 'pointer', fontSize: '14px', borderBottom: '2px solid transparent' };
  const activeTabStyle = { padding: '12px 20px', border: 'none', background: 'none', cursor: 'pointer', fontSize: '14px', borderBottom: '2px solid #fd7e14', color: '#fd7e14' };
  const patientItemStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px', border: '1px solid #e5e5e5', borderRadius: '4px', marginBottom: '12px' };
  const formStyle = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' };
  const inputStyle = { width: '100%', padding: '8px 12px', border: '1px solid #ddd', borderRadius: '4px', fontSize: '14px', marginBottom: '12px' };
  const labelStyle = { display: 'block', marginBottom: '4px', fontWeight: '500', fontSize: '14px' };

  return (
    <div style={pageStyle}>
      <div style={{ marginBottom: '30px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 'bold', marginBottom: '8px', color: '#fd7e14' }}>🧴 Дерматологическая панель</h1>
        <p style={{ color: '#666', fontSize: '14px' }}>Осмотры кожи, косметические процедуры и ведение дерматологических пациентов</p>
      </div>

      <div style={tabsStyle}>
        <button style={activeTab === 'queue' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('queue')}>📋 Очередь</button>
        <button 
          style={activeTab === 'visit' ? activeTabStyle : tabStyle} 
          onClick={() => setActiveTab('visit')}
          disabled={!currentAppointment}
        >
          🩺 Прием
        </button>
        <button style={activeTab === 'patients' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('patients')}>👥 Пациенты</button>
        <button style={activeTab === 'examinations' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('examinations')}>🔍 Осмотры кожи</button>
        <button style={activeTab === 'procedures' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('procedures')}>✨ Косметические процедуры</button>
        <button style={activeTab === 'ai' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('ai')}>🧠 AI Помощник</button>
      </div>

      {activeTab === 'patients' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Дерматологические пациенты</h2>
              <span style={{ fontSize: '14px' }}>Всего: {patients.length} пациентов</span>
            </div>
            <div style={cardContentStyle}>
              {loading ? (
                <div style={{ textAlign: 'center', padding: '40px' }}>Загрузка пациентов...</div>
              ) : (
                <div>
                  {patients.map((patient) => (
                    <div key={patient.id} style={patientItemStyle}>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                          <h3 style={{ margin: 0, fontSize: '16px' }}>{patient.last_name} {patient.first_name} {patient.middle_name}</h3>
                          <span style={{ padding: '4px 8px', fontSize: '12px', borderRadius: '12px', backgroundColor: '#fff3cd', color: '#856404', marginLeft: '8px' }}>Дерматология</span>
                        </div>
                        <div style={{ fontSize: '12px', color: '#666' }}>📱 {patient.phone} | 📅 {patient.birth_date} | 🆔 ID: {patient.id}</div>
                      </div>
                      <div>
                        <button style={buttonStyle} onClick={() => { setSelectedPatient(patient); setExaminationForm({ ...examinationForm, patient_id: patient.id }); setShowExaminationForm(true); }}>🔍 Осмотр</button>
                        <button style={buttonStyle} onClick={() => { setSelectedPatient(patient); setProcedureForm({ ...procedureForm, patient_id: patient.id }); setShowProcedureForm(true); }}>✨ Процедура</button>
                        <button style={buttonSuccessStyle} onClick={() => setSelectedPatient(patient)}>👁️ Просмотр</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'examinations' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Осмотры кожи</h2>
              <button style={{ ...buttonStyle, backgroundColor: 'white', color: '#fd7e14' }} onClick={() => setShowExaminationForm(true)}>➕ Новый осмотр</button>
            </div>
            <div style={cardContentStyle}>
              <div>
                {skinExaminations.map((exam) => (
                  <div key={exam.id} style={patientItemStyle}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                        <h3 style={{ margin: 0, fontSize: '16px' }}>Осмотр #{exam.id} — Пациент ID: {exam.patient_id}</h3>
                        <span style={{ padding: '4px 8px', fontSize: '12px', borderRadius: '12px', backgroundColor: '#e3f2fd', color: '#1976d2', marginLeft: '8px' }}>{exam.examination_date}</span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>🧴 Тип кожи: {exam.skin_type} | 📈 Состояние: {exam.skin_condition} | 🎯 Поражения: {exam.lesions}</div>
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>📍 Распространение: {exam.distribution} | 💬 Симптомы: {exam.symptoms}</div>
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>🧪 Диагноз: {exam.diagnosis}</div>
                    </div>
                    <div>
                      <button style={buttonStyle}>📋 Отчет</button>
                      <button style={buttonSuccessStyle}>📸 Фото</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'procedures' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Косметические процедуры</h2>
              <button style={{ ...buttonStyle, backgroundColor: 'white', color: '#fd7e14' }} onClick={() => setShowProcedureForm(true)}>➕ Новая процедура</button>
            </div>
            <div style={cardContentStyle}>
              <div>
                {cosmeticProcedures.map((procedure) => (
                  <div key={procedure.id} style={patientItemStyle}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                        <h3 style={{ margin: 0, fontSize: '16px' }}>Процедура #{procedure.id} — Пациент ID: {procedure.patient_id}</h3>
                        <span style={{ padding: '4px 8px', fontSize: '12px', borderRadius: '12px', backgroundColor: '#e8f5e8', color: '#2e7d32', marginLeft: '8px' }}>{procedure.procedure_date}</span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>✨ Тип: {procedure.procedure_type} | 🎯 Область: {procedure.area_treated} | ⏱️ Длительность: {procedure.duration}</div>
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>🧪 Техника: {procedure.technique} | 🧴 Продукты: {procedure.products_used}</div>
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>📊 Результаты: {procedure.results}</div>
                      {Array.isArray(procedure.services) && procedure.services.length > 0 && (
                        <div style={{ fontSize: '12px', color: '#444', marginTop: '6px' }}>
                          Услуги: {procedure.services.join(', ')}
                        </div>
                      )}
                      {(procedure.total_cost || procedure.services_subtotal || procedure.doctor_price) && (
                        <div style={{ fontSize: '12px', color: '#111', marginTop: '6px', fontWeight: 600 }}>
                          Стоимость: {(procedure.total_cost ?? 0).toLocaleString()} UZS
                          {procedure.services_subtotal ? ` (услуги: ${Number(procedure.services_subtotal).toLocaleString()} UZS` : ''}
                          {procedure.doctor_price ? `${procedure.services_subtotal ? ', ' : ' ('}от врача: ${Number(procedure.doctor_price).toLocaleString()} UZS)` : (procedure.services_subtotal ? ')' : '')}
                        </div>
                      )}
                    </div>
                    <div>
                      <button style={buttonStyle}>📋 Отчет</button>
                      <button style={buttonSuccessStyle}>📸 До/После</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {showExaminationForm && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <h2 style={{ margin: 0, fontSize: '18px' }}>Новый осмотр кожи {selectedPatient ? `— ${selectedPatient.last_name} ${selectedPatient.first_name}` : ''}</h2>
          </div>
          <div style={cardContentStyle}>
            <form onSubmit={handleExaminationSubmit}>
              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Дата осмотра *</label>
                  <input style={inputStyle} type="date" value={examinationForm.examination_date} onChange={(e) => setExaminationForm({ ...examinationForm, examination_date: e.target.value })} required />
                </div>
                <div>
                  <label style={labelStyle}>Тип кожи *</label>
                  <select style={inputStyle} value={examinationForm.skin_type} onChange={(e) => setExaminationForm({ ...examinationForm, skin_type: e.target.value })} required>
                    <option value="">Выберите тип кожи</option>
                    <option value="normal">Нормальная</option>
                    <option value="dry">Сухая</option>
                    <option value="oily">Жирная</option>
                    <option value="combination">Комбинированная</option>
                    <option value="sensitive">Чувствительная</option>
                    <option value="mature">Зрелая</option>
                  </select>
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Состояние кожи</label>
                  <select style={inputStyle} value={examinationForm.skin_condition} onChange={(e) => setExaminationForm({ ...examinationForm, skin_condition: e.target.value })}>
                    <option value="">Выберите состояние</option>
                    <option value="healthy">Здоровая</option>
                    <option value="acne">Акне</option>
                    <option value="rosacea">Розацеа</option>
                    <option value="eczema">Экзема</option>
                    <option value="psoriasis">Псориаз</option>
                    <option value="hyperpigmentation">Гиперпигментация</option>
                    <option value="aging">Признаки старения</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Поражения</label>
                  <input style={inputStyle} value={examinationForm.lesions} onChange={(e) => setExaminationForm({ ...examinationForm, lesions: e.target.value })} placeholder="Описание поражений" />
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Распространение</label>
                  <input style={inputStyle} value={examinationForm.distribution} onChange={(e) => setExaminationForm({ ...examinationForm, distribution: e.target.value })} placeholder="Локализация поражений" />
                </div>
                <div>
                  <label style={labelStyle}>Симптомы</label>
                  <input style={inputStyle} value={examinationForm.symptoms} onChange={(e) => setExaminationForm({ ...examinationForm, symptoms: e.target.value })} placeholder="Зуд, боль, жжение и т.д." />
                </div>
              </div>

              <div>
                <label style={labelStyle}>Диагноз</label>
                <textarea style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }} value={examinationForm.diagnosis} onChange={(e) => setExaminationForm({ ...examinationForm, diagnosis: e.target.value })} placeholder="Предварительный/окончательный диагноз" />
              </div>

              <div>
                <label style={labelStyle}>План лечения</label>
                <textarea style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }} value={examinationForm.treatment_plan} onChange={(e) => setExaminationForm({ ...examinationForm, treatment_plan: e.target.value })} placeholder="Рекомендуемые методы лечения" />
              </div>

              <div>
                <label style={labelStyle}>Контрольный осмотр</label>
                <input style={inputStyle} type="date" value={examinationForm.follow_up} onChange={(e) => setExaminationForm({ ...examinationForm, follow_up: e.target.value })} />
              </div>

              <div>
                <button type="submit" style={buttonStyle}>💾 Сохранить осмотр</button>
                <button type="button" style={buttonSecondaryStyle} onClick={() => setShowExaminationForm(false)}>Отмена</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showProcedureForm && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <h2 style={{ margin: 0, fontSize: '18px' }}>Новая косметическая процедура {selectedPatient ? `— ${selectedPatient.last_name} ${selectedPatient.first_name}` : ''}</h2>
          </div>
          <div style={cardContentStyle}>
            <form onSubmit={handleProcedureSubmit}>
              {/* Выбор услуг (дерма/косметология) */}
              <div>
                <label style={labelStyle}>Услуги</label>
                <ServiceChecklist
                  value={selectedServices}
                  onChange={setSelectedServices}
                  department="derma"
                />
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Дата процедуры *</label>
                  <input style={inputStyle} type="date" value={procedureForm.procedure_date} onChange={(e) => setProcedureForm({ ...procedureForm, procedure_date: e.target.value })} required />
                </div>
                <div>
                  <label style={labelStyle}>Тип процедуры *</label>
                  <select style={inputStyle} value={procedureForm.procedure_type} onChange={(e) => setProcedureForm({ ...procedureForm, procedure_type: e.target.value })} required>
                    <option value="">Выберите процедуру</option>
                    <option value="cleaning">Чистка лица</option>
                    <option value="peeling">Пилинг</option>
                    <option value="mesotherapy">Мезотерапия</option>
                    <option value="botox">Ботокс</option>
                    <option value="fillers">Филлеры</option>
                    <option value="laser">Лазерная терапия</option>
                    <option value="ultrasound">Ультразвуковая терапия</option>
                    <option value="microdermabrasion">Микродермабразия</option>
                  </select>
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Область обработки</label>
                  <input style={inputStyle} value={procedureForm.area_treated} onChange={(e) => setProcedureForm({ ...procedureForm, area_treated: e.target.value })} placeholder="Лицо, шея, декольте и т.д." />
                </div>
                <div>
                  <label style={labelStyle}>Техника выполнения</label>
                  <input style={inputStyle} value={procedureForm.technique} onChange={(e) => setProcedureForm({ ...procedureForm, technique: e.target.value })} placeholder="Описание техники" />
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Использованные продукты</label>
                  <input style={inputStyle} value={procedureForm.products_used} onChange={(e) => setProcedureForm({ ...procedureForm, products_used: e.target.value })} placeholder="Названия препаратов, концентрации" />
                </div>
                <div>
                  <label style={labelStyle}>Длительность процедуры (мин)</label>
                  <input style={inputStyle} value={procedureForm.duration} onChange={(e) => setProcedureForm({ ...procedureForm, duration: e.target.value })} placeholder="Время в минутах" />
                </div>
              </div>

              {/* Стоимость от врача + Итог */}
              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Стоимость от врача (UZS)</label>
                  <input
                    style={inputStyle}
                    value={doctorPrice}
                    onChange={(e) => setDoctorPrice(e.target.value)}
                    placeholder="Например: 50000"
                    inputMode="numeric"
                  />
                </div>
                <div>
                  <label style={labelStyle}>Итого к оплате</label>
                  <div style={{
                    display: 'flex', alignItems: 'center', height: '38px', padding: '0 12px',
                    border: '1px dashed #ddd', borderRadius: '4px', fontWeight: 600
                  }}>
                    {totalCost.toLocaleString()} UZS
                    <span style={{ marginLeft: '8px', color: '#666', fontWeight: 400 }}>
                      (услуги: {servicesSubtotal.toLocaleString()} UZS{doctorPriceNum ? `, врач: ${doctorPriceNum.toLocaleString()} UZS` : ''})
                    </span>
                  </div>
                </div>
              </div>

              <div>
                <label style={labelStyle}>Результаты процедуры</label>
                <textarea style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }} value={procedureForm.results} onChange={(e) => setProcedureForm({ ...procedureForm, results: e.target.value })} placeholder="Немедленные результаты, изменения" />
              </div>

              <div>
                <label style={labelStyle}>Рекомендации</label>
                <textarea style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }} value={procedureForm.recommendations} onChange={(e) => setProcedureForm({ ...procedureForm, recommendations: e.target.value })} placeholder="Уход после процедуры, ограничения" />
              </div>

              <div>
                <button type="submit" style={buttonStyle}>✨ Сохранить процедуру</button>
                <button type="button" style={buttonSecondaryStyle} onClick={() => setShowProcedureForm(false)}>Отмена</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Вкладка "Очередь" */}
      {activeTab === 'queue' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>📋 Очередь пациентов</h2>
            </div>
            <div style={cardContentStyle}>
              <QueueIntegration
                department="Derma"
                onSelectAppointment={(appointment) => {
                  setCurrentAppointment(appointment);
                  setActiveTab('visit');
                }}
                onStartVisit={startVisit}
              />
            </div>
          </div>
        </div>
      )}

      {/* Вкладка "Прием" */}
      {activeTab === 'visit' && currentAppointment && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>
                🩺 Прием пациента: {currentAppointment.patient_name || 'Не указано'}
              </h2>
              <span style={{ fontSize: '14px' }}>
                Статус: {currentAppointment.status}
              </span>
            </div>
            <div style={cardContentStyle}>
              {/* Временная шкала приема */}
              <VisitTimeline
                appointment={currentAppointment}
                emr={emr}
                prescription={prescription}
              />

              {/* EMR система */}
              <div style={{ marginTop: '20px' }}>
                <h3 style={{ color: '#fd7e14', marginBottom: '15px' }}>📋 Электронная медицинская карта</h3>
                <EMRSystem
                  appointment={currentAppointment}
                  emr={emr}
                  onSave={saveEMR}
                />
              </div>

              {/* Система рецептов */}
              {emr && !emr.is_draft && (
                <div style={{ marginTop: '20px' }}>
                  <h3 style={{ color: '#fd7e14', marginBottom: '15px' }}>💊 Рецепт</h3>
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
                <div style={{ marginTop: '20px', textAlign: 'center' }}>
                  <button 
                    style={{ ...buttonSuccessStyle, fontSize: '16px', padding: '12px 24px' }}
                    onClick={completeVisit}
                  >
                    ✅ Завершить прием
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* AI Помощник */}
      {activeTab === 'ai' && (
        <div style={cardStyle}>
          <div style={cardContentStyle}>
            <AIAssistant
              specialty="dermatology"
              onSuggestionSelect={(type, suggestion) => {
                if (type === 'icd10') {
                  console.log('AI предложил МКБ-10:', suggestion);
                } else if (type === 'diagnosis') {
                  console.log('AI предложил диагноз:', suggestion);
                }
              }}
            />
          </div>
        </div>
      )}

      {/* Сообщение если нет активного приема */}
      {activeTab === 'visit' && !currentAppointment && (
        <div style={cardStyle}>
          <div style={cardContentStyle}>
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <h3 style={{ color: '#666', marginBottom: '15px' }}>Нет активного приема</h3>
              <p style={{ color: '#999', marginBottom: '20px' }}>
                Выберите пациента из очереди для начала приема
              </p>
              <button 
                style={buttonStyle}
                onClick={() => setActiveTab('queue')}
              >
                📋 Перейти к очереди
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DermatologistPanel;


