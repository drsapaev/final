import React, { useState, useEffect } from 'react';

const LabPanel = () => {
  const [activeTab, setActiveTab] = useState('tests');
  const [tests, setTests] = useState([]);
  const [results, setResults] = useState([]);
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showTestForm, setShowTestForm] = useState(false);
  const [showResultForm, setShowResultForm] = useState(false);

  const [testForm, setTestForm] = useState({ patient_id: '', test_date: '', test_type: '', sample_type: '', notes: '' });
  const [resultForm, setResultForm] = useState({ patient_id: '', result_date: '', test_type: '', parameter: '', value: '', unit: '', reference: '', interpretation: '' });

  const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem('auth_token') || ''}` });

  useEffect(() => {
    loadPatients();
    loadTests();
    loadResults();
  }, []);

  const loadPatients = async () => {
    try {
      setLoading(true);
      const res = await fetch('/api/v1/patients?department=Lab&limit=100', { headers: authHeader() });
      if (res.ok) setPatients(await res.json());
    } catch {
      // Игнорируем ошибки загрузки пациентов
    } finally { setLoading(false); }
  };

  const loadTests = async () => {
    try {
      const res = await fetch('/api/v1/lab/tests?limit=100', { headers: authHeader() });
      if (res.ok) setTests(await res.json());
    } catch {
      // Игнорируем ошибки загрузки тестов
    }
  };

  const loadResults = async () => {
    try {
      const res = await fetch('/api/v1/lab/results?limit=100', { headers: authHeader() });
      if (res.ok) setResults(await res.json());
    } catch {
      // Игнорируем ошибки загрузки результатов
    }
  };

  const handleTestSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/v1/lab/tests', { method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeader() }, body: JSON.stringify(testForm) });
      if (res.ok) { setShowTestForm(false); setTestForm({ patient_id: '', test_date: '', test_type: '', sample_type: '', notes: '' }); loadTests(); }
    } catch {
      // Игнорируем ошибки создания теста
    }
  };

  const handleResultSubmit = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch('/api/v1/lab/results', { method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeader() }, body: JSON.stringify(resultForm) });
      if (res.ok) { setShowResultForm(false); setResultForm({ patient_id: '', result_date: '', test_type: '', parameter: '', value: '', unit: '', reference: '', interpretation: '' }); loadResults(); }
    } catch {
      // Игнорируем ошибки создания результата
    }
  };

  const pageStyle = { 
    padding: getSpacing('lg'), 
    maxWidth: '1400px', 
    margin: '0 auto', 
    fontFamily: 'system-ui, -apple-system, sans-serif',
    background: isLight ? 'var(--bg-primary)' : 'var(--bg-secondary)',
    color: 'var(--text-primary)',
    minHeight: '100vh'
  };
  const cardStyle = { 
    background: 'var(--bg-primary)', 
    border: '1px solid var(--border-color)', 
    borderRadius: '12px', 
    marginBottom: getSpacing('lg'), 
    boxShadow: 'var(--shadow-md)' 
  };
  const cardHeaderStyle = { 
    padding: getSpacing('lg'), 
    borderBottom: '1px solid var(--border-color)', 
    display: 'flex', 
    justifyContent: 'space-between', 
    alignItems: 'center', 
    backgroundColor: getColor('success', 500), 
    color: 'white', 
    borderRadius: '12px 12px 0 0' 
  };
  const cardContentStyle = { 
    padding: getSpacing('lg') 
  };
  const buttonStyle = { 
    padding: `${getSpacing('xs')} ${getSpacing('sm')}`, 
    backgroundColor: getColor('success', 500), 
    color: 'white', 
    border: 'none', 
    borderRadius: '4px', 
    cursor: 'pointer', 
    marginRight: getSpacing('xs'), 
    fontSize: getFontSize('sm') 
  };
  const buttonSecondaryStyle = { 
    ...buttonStyle, 
    backgroundColor: getColor('secondary', 500) 
  };
  const buttonSuccessStyle = { 
    ...buttonStyle, 
    backgroundColor: getColor('info', 500) 
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
        <button style={activeTab === 'results' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('results')}>📊 Результаты</button>
        <button style={activeTab === 'patients' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('patients')}>👥 Пациенты</button>
        <button style={activeTab === 'reports' ? activeTabStyle : tabStyle} onClick={() => setActiveTab('reports')}>📋 Отчеты</button>
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

      {activeTab === 'results' && (
        <div>
          <div style={cardStyle}>
            <div style={cardHeaderStyle}>
              <h2 style={{ margin: 0, fontSize: '18px' }}>Результаты анализов</h2>
              <button style={{ ...buttonStyle, backgroundColor: 'white', color: '#28a745' }} onClick={() => setShowResultForm(true)}>➕ Новый результат</button>
            </div>
            <div style={cardContentStyle}>
              <div>
                {results.map((r) => (
                  <div key={r.id} style={listItemStyle}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
                        <h3 style={{ margin: 0, fontSize: '16px' }}>Результат #{r.id} — Пациент ID: {r.patient_id}</h3>
                        <span style={{ padding: '4px 8px', fontSize: '12px', borderRadius: '12px', backgroundColor: '#e3f2fd', color: '#1976d2', marginLeft: '8px' }}>{r.result_date}</span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#666' }}>{r.test_type} — {r.parameter}: {r.value} {r.unit} (норма: {r.reference})</div>
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>Интерпретация: {r.interpretation}</div>
                    </div>
                    <div>
                      <button style={buttonStyle}>📄 Печать</button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
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
    </div>
  );
};

export default LabPanel;


