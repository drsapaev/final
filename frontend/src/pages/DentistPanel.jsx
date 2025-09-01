import React, { useState, useEffect } from 'react';

const DentistPanel = () => {
  const [activeTab, setActiveTab] = useState('patients');
  const [patients, setPatients] = useState([]);
  const [dentalExaminations, setDentalExaminations] = useState([]);
  const [treatmentPlans, setTreatmentPlans] = useState([]);
  const [prosthetics, setProsthetics] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [showExaminationForm, setShowExaminationForm] = useState(false);
  const [showTreatmentForm, setShowTreatmentForm] = useState(false);
  const [showProstheticForm, setShowProstheticForm] = useState(false);

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

  useEffect(() => {
    loadPatients();
    loadDentalExaminations();
    loadTreatmentPlans();
    loadProsthetics();
  }, []);

  const authHeader = () => ({
    Authorization: `Bearer ${localStorage.getItem('auth_token') || ''}`,
  });

  const loadPatients = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/patients?department=Dental&limit=100', { headers: authHeader() });
      if (response.ok) {
        const data = await response.json();
        setPatients(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.error('Ошибка загрузки пациентов:', e);
    } finally {
      setLoading(false);
    }
  };

  const loadDentalExaminations = async () => {
    try {
      const res = await fetch('/api/v1/dental/examinations?limit=100', { headers: authHeader() });
      if (res.ok) setDentalExaminations(await res.json());
    } catch {
      // Игнорируем ошибки загрузки обследований
    }
  };

  const loadTreatmentPlans = async () => {
    try {
      const res = await fetch('/api/v1/dental/treatments?limit=100', { headers: authHeader() });
      if (res.ok) setTreatmentPlans(await res.json());
    } catch {
      // Игнорируем ошибки загрузки планов лечения
    }
  };

  const loadProsthetics = async () => {
    try {
      const res = await fetch('/api/v1/dental/prosthetics?limit=100', { headers: authHeader() });
      if (res.ok) setProsthetics(await res.json());
    } catch {
      // Игнорируем ошибки загрузки протезирования
    }
  };

  const handleExaminationSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/v1/dental/examinations', {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeader() }, body: JSON.stringify(examinationForm)
      });
      if (res.ok) {
        setShowExaminationForm(false);
        setExaminationForm({ patient_id: '', examination_date: '', oral_hygiene: '', caries_status: '', periodontal_status: '', occlusion: '', missing_teeth: '', dental_plaque: '', gingival_bleeding: '', diagnosis: '', recommendations: '' });
        loadDentalExaminations();
      }
    } catch (e) { console.error('Ошибка сохранения осмотра:', e); }
  };

  const handleTreatmentSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/v1/dental/treatments', {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeader() }, body: JSON.stringify(treatmentForm)
      });
      if (res.ok) {
        setShowTreatmentForm(false);
        setTreatmentForm({ patient_id: '', treatment_date: '', treatment_type: '', teeth_involved: '', procedure_description: '', materials_used: '', anesthesia: '', complications: '', follow_up_date: '', cost: '' });
        loadTreatmentPlans();
      }
    } catch (e) { console.error('Ошибка сохранения лечения:', e); }
  };

  const handleProstheticSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/v1/dental/prosthetics', {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeader() }, body: JSON.stringify(prostheticForm)
      });
      if (res.ok) {
        setShowProstheticForm(false);
        setProstheticForm({ patient_id: '', prosthetic_date: '', prosthetic_type: '', teeth_replaced: '', material: '', shade: '', fit_quality: '', patient_satisfaction: '', warranty_period: '', cost: '' });
        loadProsthetics();
      }
    } catch (e) { console.error('Ошибка сохранения протеза:', e); }
  };

  const pageStyle = { padding: '20px', maxWidth: '1400px', margin: '0 auto', fontFamily: 'system-ui, -apple-system, sans-serif' };
  const cardStyle = { background: '#fff', border: '1px solid #e5e5e5', borderRadius: '8px', marginBottom: '20px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)' };
  const cardHeaderStyle = { padding: '20px', borderBottom: '1px solid #e5e5e5', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#007bff', color: 'white', borderRadius: '8px 8px 0 0' };
  const cardContentStyle = { padding: '20px' };
  const buttonStyle = { padding: '8px 16px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', marginRight: '8px', fontSize: '14px' };
  const buttonSecondaryStyle = { ...buttonStyle, backgroundColor: '#6c757d' };
  const buttonSuccessStyle = { ...buttonStyle, backgroundColor: '#28a745' };
  const tabsStyle = { display: 'flex', borderBottom: '1px solid #e5e5e5', marginBottom: '20px' };
  const tabStyle = { padding: '12px 20px', border: 'none', background: 'none', cursor: 'pointer', fontSize: '14px', borderBottom: '2px solid transparent' };
  const activeTabStyle = { padding: '12px 20px', border: 'none', background: 'none', cursor: 'pointer', fontSize: '14px', borderBottom: '2px solid #007bff', color: '#007bff' };
  const patientItemStyle = { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px', border: '1px solid #e5e5e5', borderRadius: '4px', marginBottom: '12px' };
  const formStyle = { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' };
  const inputStyle = { width: '100%', padding: '8px 12px', border: '1px solid #ddd', borderRadius: '4px', fontSize: '14px', marginBottom: '12px' };
  const labelStyle = { display: 'block', marginBottom: '4px', fontWeight: '500', fontSize: '14px' };

  return (
    <div style={pageStyle}>
      <div style={{ marginBottom: '30px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 'bold', marginBottom: '8px', color: '#007bff' }}>🦷 Стоматологическая панель</h1>
        <p style={{ color: '#666', fontSize: '14px' }}>Осмотры, лечение и протезирование</p>
      </div>

      <div style={tabsStyle}>
        <button style={activeTab === 'patients' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('patients')}>👥 Пациенты</button>
        <button style={activeTab === 'examinations' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('examinations')}>🔍 Осмотры</button>
        <button style={activeTab === 'treatments' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('treatments')}>🦷 Лечение</button>
        <button style={activeTab === 'prosthetics' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('prosthetics')}>🦿 Протезирование</button>
      </div>

      {activeTab === 'patients' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Стоматологические пациенты</h2>
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
                          <span style={{ padding: '4px 8px', fontSize: '12px', borderRadius: '12px', backgroundColor: '#e3f2fd', color: '#1976d2', marginLeft: '8px' }}>Стоматология</span>
                        </div>
                        <div style={{ fontSize: '12px', color: '#666' }}>📱 {patient.phone} | 📅 {patient.birth_date} | 🆔 ID: {patient.id}</div>
                      </div>
                      <div>
                        <button style={buttonStyle} onClick={() => { setSelectedPatient(patient); setExaminationForm({ ...examinationForm, patient_id: patient.id }); setShowExaminationForm(true); }}>🔍 Осмотр</button>
                        <button style={buttonStyle} onClick={() => { setSelectedPatient(patient); setTreatmentForm({ ...treatmentForm, patient_id: patient.id }); setShowTreatmentForm(true); }}>🦷 Лечение</button>
                        <button style={buttonStyle} onClick={() => { setSelectedPatient(patient); setProstheticForm({ ...prostheticForm, patient_id: patient.id }); setShowProstheticForm(true); }}>🦿 Протез</button>
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
              <h2 style={{ margin: 0, fontSize: '18px' }}>Стоматологические осмотры</h2>
              <button style={{ ...buttonStyle, backgroundColor: 'white', color: '#007bff' }} onClick={() => setShowExaminationForm(true)}>➕ Новый осмотр</button>
            </div>
            <div style={cardContentStyle}>
              <div>
                {dentalExaminations.map((exam) => (
                  <div key={exam.id} style={patientItemStyle}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                        <h3 style={{ margin: 0, fontSize: '16px' }}>Осмотр #{exam.id} — Пациент ID: {exam.patient_id}</h3>
                        <span style={{ padding: '4px 8px', fontSize: '12px', borderRadius: '12px', backgroundColor: '#e8f5e8', color: '#2e7d32', marginLeft: '8px' }}>{exam.examination_date}</span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>🦷 Кариес: {exam.caries_status} | 🦷 Пародонт: {exam.periodontal_status} | 🦷 Прикус: {exam.occlusion}</div>
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>🦷 Отсутствующие зубы: {exam.missing_teeth} | 🦷 Налет: {exam.dental_plaque} | 🩸 Кровоточивость: {exam.gingival_bleeding}</div>
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

      {activeTab === 'treatments' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Планы лечения</h2>
              <button style={{ ...buttonStyle, backgroundColor: 'white', color: '#007bff' }} onClick={() => setShowTreatmentForm(true)}>➕ Новый план</button>
            </div>
            <div style={cardContentStyle}>
              <div>
                {treatmentPlans.map((treatment) => (
                  <div key={treatment.id} style={patientItemStyle}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                        <h3 style={{ margin: 0, fontSize: '16px' }}>Лечение #{treatment.id} — Пациент ID: {treatment.patient_id}</h3>
                        <span style={{ padding: '4px 8px', fontSize: '12px', borderRadius: '12px', backgroundColor: '#fff3cd', color: '#856404', marginLeft: '8px' }}>{treatment.treatment_date}</span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>🦷 Тип: {treatment.treatment_type} | 🦷 Зубы: {treatment.teeth_involved} | 💰 Стоимость: {treatment.cost}</div>
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>🧪 Материалы: {treatment.materials_used} | 💉 Анестезия: {treatment.anesthesia}</div>
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>📅 Контроль: {treatment.follow_up_date}</div>
                    </div>
                    <div>
                      <button style={buttonStyle}>📋 Отчет</button>
                      <button style={buttonSuccessStyle}>📊 Прогресс</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'prosthetics' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Протезирование</h2>
              <button style={{ ...buttonStyle, backgroundColor: 'white', color: '#007bff' }} onClick={() => setShowProstheticForm(true)}>➕ Новый протез</button>
            </div>
            <div style={cardContentStyle}>
              <div>
                {prosthetics.map((prosthetic) => (
                  <div key={prosthetic.id} style={patientItemStyle}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                        <h3 style={{ margin: 0, fontSize: '16px' }}>Протез #{prosthetic.id} — Пациент ID: {prosthetic.patient_id}</h3>
                        <span style={{ padding: '4px 8px', fontSize: '12px', borderRadius: '12px', backgroundColor: '#f8d7da', color: '#721c24', marginLeft: '8px' }}>{prosthetic.prosthetic_date}</span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>🧩 Тип: {prosthetic.prosthetic_type} | 🦷 Зубы: {prosthetic.teeth_replaced} | 💰 Стоимость: {prosthetic.cost}</div>
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>🧱 Материал: {prosthetic.material} | 🎨 Оттенок: {prosthetic.shade}</div>
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>✅ Посадка: {prosthetic.fit_quality} | 😊 Удовлетворенность: {prosthetic.patient_satisfaction}</div>
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

      {showExaminationForm && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <h2 style={{ margin: 0, fontSize: '18px' }}>Новый стоматологический осмотр {selectedPatient ? `— ${selectedPatient.last_name} ${selectedPatient.first_name}` : ''}</h2>
          </div>
          <div style={cardContentStyle}>
            <form onSubmit={handleExaminationSubmit}>
              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Дата осмотра *</label>
                  <input style={inputStyle} type="date" value={examinationForm.examination_date} onChange={(e) => setExaminationForm({ ...examinationForm, examination_date: e.target.value })} required />
                </div>
                <div>
                  <label style={labelStyle}>Гигиена полости рта</label>
                  <select style={inputStyle} value={examinationForm.oral_hygiene} onChange={(e) => setExaminationForm({ ...examinationForm, oral_hygiene: e.target.value })}>
                    <option value="">Выберите</option>
                    <option value="excellent">Отличная</option>
                    <option value="good">Хорошая</option>
                    <option value="fair">Удовлетворительная</option>
                    <option value="poor">Плохая</option>
                  </select>
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Статус кариеса</label>
                  <select style={inputStyle} value={examinationForm.caries_status} onChange={(e) => setExaminationForm({ ...examinationForm, caries_status: e.target.value })}>
                    <option value="">Выберите</option>
                    <option value="none">Нет кариеса</option>
                    <option value="initial">Начальный</option>
                    <option value="superficial">Поверхностный</option>
                    <option value="medium">Средний</option>
                    <option value="deep">Глубокий</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Статус пародонта</label>
                  <select style={inputStyle} value={examinationForm.periodontal_status} onChange={(e) => setExaminationForm({ ...examinationForm, periodontal_status: e.target.value })}>
                    <option value="">Выберите</option>
                    <option value="healthy">Здоровый</option>
                    <option value="gingivitis">Гингивит</option>
                    <option value="periodontitis">Пародонтит</option>
                    <option value="advanced">Тяжелый</option>
                  </select>
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Прикус</label>
                  <select style={inputStyle} value={examinationForm.occlusion} onChange={(e) => setExaminationForm({ ...examinationForm, occlusion: e.target.value })}>
                    <option value="">Выберите</option>
                    <option value="normal">Нормальный</option>
                    <option value="open_bite">Открытый</option>
                    <option value="deep_bite">Глубокий</option>
                    <option value="cross_bite">Перекрестный</option>
                    <option value="crowding">Скученность</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Отсутствующие зубы</label>
                  <input style={inputStyle} value={examinationForm.missing_teeth} onChange={(e) => setExaminationForm({ ...examinationForm, missing_teeth: e.target.value })} placeholder="Номера отсутствующих зубов" />
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Зубной налет</label>
                  <select style={inputStyle} value={examinationForm.dental_plaque} onChange={(e) => setExaminationForm({ ...examinationForm, dental_plaque: e.target.value })}>
                    <option value="">Выберите</option>
                    <option value="none">Нет</option>
                    <option value="minimal">Минимальный</option>
                    <option value="moderate">Умеренный</option>
                    <option value="heavy">Тяжелый</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Кровоточивость десен</label>
                  <select style={inputStyle} value={examinationForm.gingival_bleeding} onChange={(e) => setExaminationForm({ ...examinationForm, gingival_bleeding: e.target.value })}>
                    <option value="">Выберите</option>
                    <option value="none">Нет</option>
                    <option value="mild">Легкая</option>
                    <option value="moderate">Умеренная</option>
                    <option value="severe">Тяжелая</option>
                  </select>
                </div>
              </div>

              <div>
                <label style={labelStyle}>Диагноз</label>
                <textarea style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }} value={examinationForm.diagnosis} onChange={(e) => setExaminationForm({ ...examinationForm, diagnosis: e.target.value })} placeholder="Стоматологический диагноз" />
              </div>

              <div>
                <label style={labelStyle}>Рекомендации</label>
                <textarea style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }} value={examinationForm.recommendations} onChange={(e) => setExaminationForm({ ...examinationForm, recommendations: e.target.value })} placeholder="Рекомендации по лечению и уходу" />
              </div>

              <div>
                <button type="submit" style={buttonStyle}>💾 Сохранить осмотр</button>
                <button type="button" style={buttonSecondaryStyle} onClick={() => setShowExaminationForm(false)}>Отмена</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showTreatmentForm && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <h2 style={{ margin: 0, fontSize: '18px' }}>Новый план лечения {selectedPatient ? `— ${selectedPatient.last_name} ${selectedPatient.first_name}` : ''}</h2>
          </div>
          <div style={cardContentStyle}>
            <form onSubmit={handleTreatmentSubmit}>
              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Дата лечения *</label>
                  <input style={inputStyle} type="date" value={treatmentForm.treatment_date} onChange={(e) => setTreatmentForm({ ...treatmentForm, treatment_date: e.target.value })} required />
                </div>
                <div>
                  <label style={labelStyle}>Тип лечения *</label>
                  <select style={inputStyle} value={treatmentForm.treatment_type} onChange={(e) => setTreatmentForm({ ...treatmentForm, treatment_type: e.target.value })} required>
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

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Вовлеченные зубы</label>
                  <input style={inputStyle} value={treatmentForm.teeth_involved} onChange={(e) => setTreatmentForm({ ...treatmentForm, teeth_involved: e.target.value })} placeholder="Номера зубов" />
                </div>
                <div>
                  <label style={labelStyle}>Стоимость</label>
                  <input style={inputStyle} type="number" value={treatmentForm.cost} onChange={(e) => setTreatmentForm({ ...treatmentForm, cost: e.target.value })} placeholder="Сумма" />
                </div>
              </div>

              <div>
                <label style={labelStyle}>Описание процедуры</label>
                <textarea style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }} value={treatmentForm.procedure_description} onChange={(e) => setTreatmentForm({ ...treatmentForm, procedure_description: e.target.value })} placeholder="Подробное описание" />
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Материалы</label>
                  <input style={inputStyle} value={treatmentForm.materials_used} onChange={(e) => setTreatmentForm({ ...treatmentForm, materials_used: e.target.value })} placeholder="Названия материалов" />
                </div>
                <div>
                  <label style={labelStyle}>Анестезия</label>
                  <select style={inputStyle} value={treatmentForm.anesthesia} onChange={(e) => setTreatmentForm({ ...treatmentForm, anesthesia: e.target.value })}>
                    <option value="">Выберите</option>
                    <option value="none">Не требуется</option>
                    <option value="local">Местная</option>
                    <option value="sedation">Седация</option>
                    <option value="general">Общая</option>
                  </select>
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Осложнения</label>
                  <input style={inputStyle} value={treatmentForm.complications} onChange={(e) => setTreatmentForm({ ...treatmentForm, complications: e.target.value })} placeholder="Описание осложнений" />
                </div>
                <div>
                  <label style={labelStyle}>Дата контроля</label>
                  <input style={inputStyle} type="date" value={treatmentForm.follow_up_date} onChange={(e) => setTreatmentForm({ ...treatmentForm, follow_up_date: e.target.value })} />
                </div>
              </div>

              <div>
                <button type="submit" style={buttonStyle}>🦷 Сохранить лечение</button>
                <button type="button" style={buttonSecondaryStyle} onClick={() => setShowTreatmentForm(false)}>Отмена</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showProstheticForm && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <h2 style={{ margin: 0, fontSize: '18px' }}>Новый протез {selectedPatient ? `— ${selectedPatient.last_name} ${selectedPatient.first_name}` : ''}</h2>
          </div>
          <div style={cardContentStyle}>
            <form onSubmit={handleProstheticSubmit}>
              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Дата протезирования *</label>
                  <input style={inputStyle} type="date" value={prostheticForm.prosthetic_date} onChange={(e) => setProstheticForm({ ...prostheticForm, prosthetic_date: e.target.value })} required />
                </div>
                <div>
                  <label style={labelStyle}>Тип протеза *</label>
                  <select style={inputStyle} value={prostheticForm.prosthetic_type} onChange={(e) => setProstheticForm({ ...prostheticForm, prosthetic_type: e.target.value })} required>
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

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Заменяемые зубы</label>
                  <input style={inputStyle} value={prostheticForm.teeth_replaced} onChange={(e) => setProstheticForm({ ...prostheticForm, teeth_replaced: e.target.value })} placeholder="Номера зубов" />
                </div>
                <div>
                  <label style={labelStyle}>Материал</label>
                  <select style={inputStyle} value={prostheticForm.material} onChange={(e) => setProstheticForm({ ...prostheticForm, material: e.target.value })}>
                    <option value="">Выберите материал</option>
                    <option value="porcelain">Фарфор</option>
                    <option value="metal">Металл</option>
                    <option value="ceramic">Керамика</option>
                    <option value="composite">Композит</option>
                    <option value="zirconia">Диоксид циркония</option>
                  </select>
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Оттенок</label>
                  <input style={inputStyle} value={prostheticForm.shade} onChange={(e) => setProstheticForm({ ...prostheticForm, shade: e.target.value })} placeholder="A1, B2, C3 и т.д." />
                </div>
                <div>
                  <label style={labelStyle}>Стоимость</label>
                  <input style={inputStyle} type="number" value={prostheticForm.cost} onChange={(e) => setProstheticForm({ ...prostheticForm, cost: e.target.value })} placeholder="Сумма" />
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Качество посадки</label>
                  <select style={inputStyle} value={prostheticForm.fit_quality} onChange={(e) => setProstheticForm({ ...prostheticForm, fit_quality: e.target.value })}>
                    <option value="">Выберите</option>
                    <option value="excellent">Отличная</option>
                    <option value="good">Хорошая</option>
                    <option value="fair">Удовлетворительная</option>
                    <option value="poor">Плохая</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Удовлетворенность пациента</label>
                  <select style={inputStyle} value={prostheticForm.patient_satisfaction} onChange={(e) => setProstheticForm({ ...prostheticForm, patient_satisfaction: e.target.value })}>
                    <option value="">Выберите</option>
                    <option value="very_satisfied">Очень доволен</option>
                    <option value="satisfied">Доволен</option>
                    <option value="neutral">Нейтрально</option>
                    <option value="dissatisfied">Не доволен</option>
                    <option value="very_dissatisfied">Очень не доволен</option>
                  </select>
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Гарантийный период</label>
                  <input style={inputStyle} value={prostheticForm.warranty_period} onChange={(e) => setProstheticForm({ ...prostheticForm, warranty_period: e.target.value })} placeholder="Например: 2 года" />
                </div>
              </div>

              <div>
                <button type="submit" style={buttonStyle}>🧩 Сохранить протез</button>
                <button type="button" style={buttonSecondaryStyle} onClick={() => setShowProstheticForm(false)}>Отмена</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default DentistPanel;


