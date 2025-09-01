import React, { useState, useEffect } from 'react';

const CardiologistPanel = () => {
  const [activeTab, setActiveTab] = useState('patients');
  const [patients, setPatients] = useState([]);
  const [ecgResults, setEcgResults] = useState([]);
  const [bloodTests, setBloodTests] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [showEcgForm, setShowEcgForm] = useState(false);
  const [showBloodTestForm, setShowBloodTestForm] = useState(false);

  // Состояния для кардиологических данных
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

  useEffect(() => {
    loadPatients();
    loadEcgResults();
    loadBloodTests();
  }, []);

  const loadPatients = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/v1/patients?department=Cardio&limit=100', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setPatients(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки пациентов:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadEcgResults = async () => {
    try {
      const response = await fetch('/api/v1/cardio/ecg?limit=100', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setEcgResults(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки ЭКГ:', error);
    }
  };

  const loadBloodTests = async () => {
    try {
      const response = await fetch('/api/v1/cardio/blood-tests?limit=100', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        }
      });
      if (response.ok) {
        const data = await response.json();
        setBloodTests(data);
      }
    } catch (error) {
      console.error('Ошибка загрузки анализов крови:', error);
    }
  };

  const handleEcgSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('/api/v1/cardio/ecg', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify(ecgForm)
      });

      if (response.ok) {
        setShowEcgForm(false);
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
        loadEcgResults();
      }
    } catch (error) {
      console.error('Ошибка сохранения ЭКГ:', error);
    }
  };

  const handleBloodTestSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('/api/v1/cardio/blood-tests', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify(bloodTestForm)
      });

      if (response.ok) {
        setShowBloodTestForm(false);
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
        loadBloodTests();
      }
    } catch (error) {
      console.error('Ошибка сохранения анализа крови:', error);
    }
  };

  // Стили
  const pageStyle = {
    padding: '20px',
    maxWidth: '1400px',
    margin: '0 auto',
    fontFamily: 'system-ui, -apple-system, sans-serif'
  };

  const cardStyle = {
    background: '#fff',
    border: '1px solid #e5e5e5',
    borderRadius: '8px',
    marginBottom: '20px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
  };

  const cardHeaderStyle = {
    padding: '20px',
    borderBottom: '1px solid #e5e5e5',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#dc3545',
    color: 'white',
    borderRadius: '8px 8px 0 0'
  };

  const cardContentStyle = {
    padding: '20px'
  };

  const buttonStyle = {
    padding: '8px 16px',
    backgroundColor: '#dc3545',
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
    backgroundColor: '#28a745'
  };

  const tabsStyle = {
    display: 'flex',
    borderBottom: '1px solid #e5e5e5',
    marginBottom: '20px'
  };

  const tabStyle = {
    padding: '12px 20px',
    border: 'none',
    background: 'none',
    cursor: 'pointer',
    fontSize: '14px',
    borderBottom: '2px solid transparent'
  };

  const activeTabStyle = {
    padding: '12px 20px',
    border: 'none',
    background: 'none',
    cursor: 'pointer',
    fontSize: '14px',
    borderBottom: '2px solid #dc3545',
    color: '#dc3545'
  };

  const patientItemStyle = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '16px',
    border: '1px solid #e5e5e5',
    borderRadius: '4px',
    marginBottom: '12px'
  };

  const formStyle = {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px'
  };

  const inputStyle = {
    width: '100%',
    padding: '8px 12px',
    border: '1px solid #ddd',
    borderRadius: '4px',
    fontSize: '14px',
    marginBottom: '12px'
  };

  const labelStyle = {
    display: 'block',
    marginBottom: '4px',
    fontWeight: '500',
    fontSize: '14px'
  };

  return (
    <div style={pageStyle}>
      <div style={{ marginBottom: '30px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 'bold', marginBottom: '8px', color: '#dc3545' }}>
          🫀 Кардиологическая панель
        </h1>
        <p style={{ color: '#666', fontSize: '14px' }}>
          Специализированная панель для кардиологов - ЭКГ, анализы крови, кардиологические исследования
        </p>
      </div>

      {/* Вкладки */}
      <div style={tabsStyle}>
        <button
          style={activeTab === 'patients' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('patients')}
        >
          👥 Пациенты
        </button>
        <button
          style={activeTab === 'ecg' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('ecg')}
        >
          📊 ЭКГ
        </button>
        <button
          style={activeTab === 'blood-tests' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('blood-tests')}
        >
          🩸 Анализы крови
        </button>
        <button
          style={activeTab === 'risk-assessment' ? activeTabStyle : tabStyle}
          onClick={() => setActiveTab('risk-assessment')}
        >
          ⚠️ Оценка рисков
        </button>
      </div>

      {/* Вкладка Пациенты */}
      {activeTab === 'patients' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Кардиологические пациенты</h2>
              <span style={{ fontSize: '14px' }}>
                Всего: {patients.length} пациентов
              </span>
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
                          <h3 style={{ margin: 0, fontSize: '16px' }}>
                            {patient.last_name} {patient.first_name} {patient.middle_name}
                          </h3>
                          <span style={{ 
                            padding: '4px 8px', 
                            fontSize: '12px', 
                            borderRadius: '12px', 
                            backgroundColor: '#f8d7da', 
                            color: '#721c24',
                            marginLeft: '8px'
                          }}>
                            Кардиология
                          </span>
                        </div>
                        <div style={{ fontSize: '12px', color: '#666' }}>
                          📱 {patient.phone} | 📅 {patient.birth_date} | 
                          🆔 ID: {patient.id}
                        </div>
                      </div>
                      <div>
                        <button
                          style={buttonStyle}
                          onClick={() => {
                            setSelectedPatient(patient);
                            setEcgForm({ ...ecgForm, patient_id: patient.id });
                            setShowEcgForm(true);
                          }}
                        >
                          📊 ЭКГ
                        </button>
                        <button
                          style={buttonStyle}
                          onClick={() => {
                            setSelectedPatient(patient);
                            setBloodTestForm({ ...bloodTestForm, patient_id: patient.id });
                            setShowBloodTestForm(true);
                          }}
                        >
                          🩸 Анализ крови
                        </button>
                        <button
                          style={buttonSuccessStyle}
                          onClick={() => setSelectedPatient(patient)}
                        >
                          👁️ Просмотр
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Вкладка ЭКГ */}
      {activeTab === 'ecg' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Результаты ЭКГ</h2>
              <button 
                style={{ ...buttonStyle, backgroundColor: 'white', color: '#dc3545' }}
                onClick={() => setShowEcgForm(true)}
              >
                ➕ Новое ЭКГ
              </button>
            </div>
            <div style={cardContentStyle}>
              <div>
                {ecgResults.map((ecg) => (
                  <div key={ecg.id} style={patientItemStyle}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                        <h3 style={{ margin: 0, fontSize: '16px' }}>
                          ЭКГ #{ecg.id} - Пациент ID: {ecg.patient_id}
                        </h3>
                        <span style={{ 
                          padding: '4px 8px', 
                          fontSize: '12px', 
                          borderRadius: '12px', 
                          backgroundColor: '#e3f2fd', 
                          color: '#1976d2',
                          marginLeft: '8px'
                        }}>
                          {ecg.ecg_date}
                        </span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        💓 Ритм: {ecg.rhythm} | 🫀 ЧСС: {ecg.heart_rate} уд/мин | 
                        ⏱️ PR: {ecg.pr_interval}мс | QRS: {ecg.qrs_duration}мс
                      </div>
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                        📊 ST: {ecg.st_segment} | T: {ecg.t_wave} | QT: {ecg.qt_interval}мс
                      </div>
                    </div>
                    <div>
                      <button style={buttonStyle}>
                        📋 Отчет
                      </button>
                      <button style={buttonSuccessStyle}>
                        📊 График
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Вкладка Анализы крови */}
      {activeTab === 'blood-tests' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Анализы крови</h2>
              <button 
                style={{ ...buttonStyle, backgroundColor: 'white', color: '#dc3545' }}
                onClick={() => setShowBloodTestForm(true)}
              >
                ➕ Новый анализ
              </button>
            </div>
            <div style={cardContentStyle}>
              <div>
                {bloodTests.map((test) => (
                  <div key={test.id} style={patientItemStyle}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                        <h3 style={{ margin: 0, fontSize: '16px' }}>
                          Анализ #{test.id} - Пациент ID: {test.patient_id}
                        </h3>
                        <span style={{ 
                          padding: '4px 8px', 
                          fontSize: '12px', 
                          borderRadius: '12px', 
                          backgroundColor: '#e8f5e8', 
                          color: '#2e7d32',
                          marginLeft: '8px'
                        }}>
                          {test.test_date}
                        </span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>
                        🩸 Холестерин: {test.cholesterol_total} мг/дл | 
                        HDL: {test.cholesterol_hdl} | LDL: {test.cholesterol_ldl} | 
                        Триглицериды: {test.triglycerides}
                      </div>
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                        🍬 Глюкоза: {test.glucose} мг/дл | 
                        CRP: {test.crp} мг/л | Тропонин: {test.troponin} нг/мл
                      </div>
                    </div>
                    <div>
                      <button style={buttonStyle}>
                        📋 Отчет
                      </button>
                      <button style={buttonSuccessStyle}>
                        📊 График
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Вкладка Оценка рисков */}
      {activeTab === 'risk-assessment' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Оценка кардиологических рисков</h2>
            </div>
            <div style={cardContentStyle}>
              <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
                🚧 Модуль оценки кардиологических рисков будет доступен в следующей версии
                <br />
                <small>Включает: калькулятор рисков, шкалы SCORE, Framingham, рекомендации</small>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Форма ЭКГ */}
      {showEcgForm && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <h2 style={{ margin: 0, fontSize: '18px' }}>
              Новое ЭКГ исследование
              {selectedPatient && ` - ${selectedPatient.last_name} ${selectedPatient.first_name}`}
            </h2>
          </div>
          <div style={cardContentStyle}>
            <form onSubmit={handleEcgSubmit}>
              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Дата ЭКГ *</label>
                  <input
                    style={inputStyle}
                    type="date"
                    value={ecgForm.ecg_date}
                    onChange={(e) => setEcgForm({ ...ecgForm, ecg_date: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label style={labelStyle}>Ритм *</label>
                  <select
                    style={inputStyle}
                    value={ecgForm.rhythm}
                    onChange={(e) => setEcgForm({ ...ecgForm, rhythm: e.target.value })}
                    required
                  >
                    <option value="">Выберите ритм</option>
                    <option value="sinus">Синусовый</option>
                    <option value="atrial_fibrillation">Фибрилляция предсердий</option>
                    <option value="atrial_flutter">Трепетание предсердий</option>
                    <option value="ventricular_tachycardia">Желудочковая тахикардия</option>
                    <option value="bradycardia">Брадикардия</option>
                  </select>
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>ЧСС (уд/мин) *</label>
                  <input
                    style={inputStyle}
                    type="number"
                    value={ecgForm.heart_rate}
                    onChange={(e) => setEcgForm({ ...ecgForm, heart_rate: e.target.value })}
                    required
                    placeholder="60-100"
                  />
                </div>
                <div>
                  <label style={labelStyle}>PR интервал (мс)</label>
                  <input
                    style={inputStyle}
                    type="number"
                    value={ecgForm.pr_interval}
                    onChange={(e) => setEcgForm({ ...ecgForm, pr_interval: e.target.value })}
                    placeholder="120-200"
                  />
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>QRS длительность (мс)</label>
                  <input
                    style={inputStyle}
                    type="number"
                    value={ecgForm.qrs_duration}
                    onChange={(e) => setEcgForm({ ...ecgForm, qrs_duration: e.target.value })}
                    placeholder="80-120"
                  />
                </div>
                <div>
                  <label style={labelStyle}>QT интервал (мс)</label>
                  <input
                    style={inputStyle}
                    type="number"
                    value={ecgForm.qt_interval}
                    onChange={(e) => setEcgForm({ ...ecgForm, qt_interval: e.target.value })}
                    placeholder="350-450"
                  />
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>ST сегмент</label>
                  <select
                    style={inputStyle}
                    value={ecgForm.st_segment}
                    onChange={(e) => setEcgForm({ ...ecgForm, st_segment: e.target.value })}
                  >
                    <option value="">Выберите</option>
                    <option value="normal">Нормальный</option>
                    <option value="elevated">Поднят</option>
                    <option value="depressed">Опущен</option>
                    <option value="horizontal">Горизонтальный</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>T волна</label>
                  <select
                    style={inputStyle}
                    value={ecgForm.t_wave}
                    onChange={(e) => setEcgForm({ ...ecgForm, t_wave: e.target.value })}
                  >
                    <option value="">Выберите</option>
                    <option value="normal">Нормальная</option>
                    <option value="inverted">Инвертированная</option>
                    <option value="flattened">Сглаженная</option>
                    <option value="biphasic">Двухфазная</option>
                  </select>
                </div>
              </div>

              <div>
                <label style={labelStyle}>Интерпретация</label>
                <textarea
                  style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }}
                  value={ecgForm.interpretation}
                  onChange={(e) => setEcgForm({ ...ecgForm, interpretation: e.target.value })}
                  placeholder="Описание ЭКГ изменений"
                />
              </div>

              <div>
                <label style={labelStyle}>Рекомендации</label>
                <textarea
                  style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }}
                  value={ecgForm.recommendations}
                  onChange={(e) => setEcgForm({ ...ecgForm, recommendations: e.target.value })}
                  placeholder="Рекомендации по лечению и наблюдению"
                />
              </div>

              <div>
                <button type="submit" style={buttonStyle}>
                  💾 Сохранить ЭКГ
                </button>
                <button
                  type="button"
                  style={buttonSecondaryStyle}
                  onClick={() => setShowEcgForm(false)}
                >
                  Отмена
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Форма анализа крови */}
      {showBloodTestForm && (
        <div style={cardStyle}>
          <div style={cardHeaderStyle}>
            <h2 style={{ margin: 0, fontSize: '18px' }}>
              Новый анализ крови
              {selectedPatient && ` - ${selectedPatient.last_name} ${selectedPatient.first_name}`}
            </h2>
          </div>
          <div style={cardContentStyle}>
            <form onSubmit={handleBloodTestSubmit}>
              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Дата анализа *</label>
                  <input
                    style={inputStyle}
                    type="date"
                    value={bloodTestForm.test_date}
                    onChange={(e) => setBloodTestForm({ ...bloodTestForm, test_date: e.target.value })}
                    required
                  />
                </div>
                <div>
                  <label style={labelStyle}>Общий холестерин (мг/дл)</label>
                  <input
                    style={inputStyle}
                    type="number"
                    value={bloodTestForm.cholesterol_total}
                    onChange={(e) => setBloodTestForm({ ...bloodTestForm, cholesterol_total: e.target.value })}
                    placeholder="<200"
                  />
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>HDL холестерин (мг/дл)</label>
                  <input
                    style={inputStyle}
                    type="number"
                    value={bloodTestForm.cholesterol_hdl}
                    onChange={(e) => setBloodTestForm({ ...bloodTestForm, cholesterol_hdl: e.target.value })}
                    placeholder=">40"
                  />
                </div>
                <div>
                  <label style={labelStyle}>LDL холестерин (мг/дл)</label>
                  <input
                    style={inputStyle}
                    type="number"
                    value={bloodTestForm.cholesterol_ldl}
                    onChange={(e) => setBloodTestForm({ ...bloodTestForm, cholesterol_ldl: e.target.value })}
                    placeholder="<100"
                  />
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>Триглицериды (мг/дл)</label>
                  <input
                    style={inputStyle}
                    type="number"
                    value={bloodTestForm.triglycerides}
                    onChange={(e) => setBloodTestForm({ ...bloodTestForm, triglycerides: e.target.value })}
                    placeholder="<150"
                  />
                </div>
                <div>
                  <label style={labelStyle}>Глюкоза (мг/дл)</label>
                  <input
                    style={inputStyle}
                    type="number"
                    value={bloodTestForm.glucose}
                    onChange={(e) => setBloodTestForm({ ...bloodTestForm, glucose: e.target.value })}
                    placeholder="70-100"
                  />
                </div>
              </div>

              <div style={formStyle}>
                <div>
                  <label style={labelStyle}>CRP (мг/л)</label>
                  <input
                    style={inputStyle}
                    type="number"
                    value={bloodTestForm.crp}
                    onChange={(e) => setBloodTestForm({ ...bloodTestForm, crp: e.target.value })}
                    placeholder="<3.0"
                  />
                </div>
                <div>
                  <label style={labelStyle}>Тропонин (нг/мл)</label>
                  <input
                    style={inputStyle}
                    type="number"
                    value={bloodTestForm.troponin}
                    onChange={(e) => setBloodTestForm({ ...bloodTestForm, troponin: e.target.value })}
                    placeholder="<0.04"
                  />
                </div>
              </div>

              <div>
                <label style={labelStyle}>Интерпретация</label>
                <textarea
                  style={{ ...inputStyle, minHeight: '80px', resize: 'vertical' }}
                  value={bloodTestForm.interpretation}
                  onChange={(e) => setBloodTestForm({ ...bloodTestForm, interpretation: e.target.value })}
                  placeholder="Интерпретация результатов анализов"
                />
              </div>

              <div>
                <button type="submit" style={buttonStyle}>
                  🩸 Сохранить анализ
                </button>
                <button
                  type="button"
                  style={buttonSecondaryStyle}
                  onClick={() => setShowBloodTestForm(false)}
                >
                  Отмена
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default CardiologistPanel;
