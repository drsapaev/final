import React, { useState, useEffect } from 'react';
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
  BarChart3,
  TestTube
} from 'lucide-react';
import { Card, Button, Badge } from '../design-system/components';
import { useTheme } from '../contexts/ThemeContext';
import DoctorQueuePanel from '../components/doctor/DoctorQueuePanel';
import DoctorServiceSelector from '../components/doctor/DoctorServiceSelector';
import AIAssistant from '../components/ai/AIAssistant';
import ECGViewer from '../components/cardiology/ECGViewer';
import EchoForm from '../components/cardiology/EchoForm';
import ScheduleNextModal from '../components/common/ScheduleNextModal';

/**
 * Унифицированная панель кардиолога
 * Объединяет: очередь + специализированные функции + AI + ЭКГ/ЭхоКГ
 */
const CardiologistPanelUnified = () => {
  // Всегда вызываем хуки первыми
  const { theme, isDark, getColor } = useTheme();
  
  const [activeTab, setActiveTab] = useState('queue');
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

  const [showEcgForm, setShowEcgForm] = useState(false);
  const [showBloodTestForm, setShowBloodTestForm] = useState(false);
  const [ecgResults, setEcgResults] = useState([]);
  const [bloodTests, setBloodTests] = useState([]);

  // Вкладки панели
  const tabs = [
    { id: 'queue', label: 'Очередь', icon: Users, color: 'text-blue-600' },
    { id: 'visit', label: 'Прием', icon: Heart, color: 'text-red-600' },
    { id: 'ecg', label: 'ЭКГ', icon: Activity, color: 'text-green-600' },
    { id: 'blood', label: 'Анализы', icon: TestTube, color: 'text-purple-600' },
    { id: 'ai', label: 'AI Помощник', icon: Brain, color: 'text-indigo-600' },
    { id: 'services', label: 'Услуги', icon: Stethoscope, color: 'text-orange-600' },
    { id: 'history', label: 'История', icon: FileText, color: 'text-gray-600' }
  ];

  useEffect(() => {
    if (selectedPatient) {
      loadPatientData();
    }
  }, [selectedPatient]);

  // Проверяем демо-режим после всех хуков
  const isDemoMode = window.location.pathname.includes('/medilab-demo');
  
  // В демо-режиме не рендерим компонент
  if (isDemoMode) {
    console.log('CardiologistPanelUnified: Skipping render in demo mode');
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
    setSelectedPatient(patient);
    setActiveTab('visit');
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
      
      const visitPayload = {
        patient_id: selectedPatient.patient?.id,
        complaint: visitData.complaint,
        diagnosis: visitData.diagnosis,
        icd10: visitData.icd10,
        services: selectedServices,
        notes: visitData.notes
      };

      const response = await fetch(`/api/v1/doctor/queue/${selectedPatient.id}/complete`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(visitPayload)
      });

      if (response.ok) {
        setMessage({ type: 'success', text: 'Прием завершен успешно' });
        
        // Очищаем форму
        setSelectedPatient(null);
        setSelectedServices([]);
        setVisitData({ complaint: '', diagnosis: '', icd10: '', notes: '' });
        setActiveTab('queue');
      } else {
        const error = await response.json();
        throw new Error(error.detail);
      }

    } catch (error) {
      console.error('Ошибка сохранения визита:', error);
      setMessage({ type: 'error', text: error.message });
    } finally {
      setLoading(false);
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
        loadPatientData();
        setMessage({ type: 'success', text: 'Анализ крови сохранен успешно' });
      }
    } catch (error) {
      console.error('Ошибка сохранения анализа:', error);
      setMessage({ type: 'error', text: 'Ошибка сохранения анализа' });
    }
  };

  const pageStyle = {
    padding: '20px',
    maxWidth: '1400px',
    margin: '0 auto',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    background: isDark ? 'var(--bg-primary)' : '#f8fafc',
    minHeight: '100vh',
    color: isDark ? 'var(--text-primary)' : '#1a202c'
  };

  const headerStyle = {
    marginBottom: '24px',
    padding: '20px',
    background: isDark ? 'var(--bg-secondary)' : 'white',
    borderRadius: '12px',
    border: isDark ? '1px solid var(--border-color)' : '1px solid #e2e8f0',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)'
  };

  const tabStyle = {
    padding: '12px 24px',
    border: 'none',
    background: 'transparent',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: '500',
    color: isDark ? 'var(--text-secondary)' : '#64748b',
    borderRadius: '8px',
    transition: 'all 0.2s ease',
    display: 'flex',
    alignItems: 'center',
    gap: '8px'
  };

  const activeTabStyle = {
    ...tabStyle,
    background: '#dc3545',
    color: 'white',
    boxShadow: '0 2px 4px rgba(220, 53, 69, 0.3)'
  };

  return (
    <div style={pageStyle}>
      {/* Заголовок */}
      <div style={headerStyle}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center">
              <Heart className="mr-3 text-red-600" size={28} />
              Панель кардиолога
            </h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Унифицированная панель с очередью, ЭКГ, анализами и AI помощником
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            <Button 
              variant="primary"
              onClick={() => setScheduleNextModal({ open: true, patient: selectedPatient?.patient || null })}
              className="flex items-center gap-2"
            >
              <Plus size={16} />
              Назначить следующий визит
            </Button>
          </div>
          
          {selectedPatient && (
            <div className="text-right">
              <div className="font-medium">Пациент: {selectedPatient.patient_name}</div>
              <div className="text-sm text-gray-500">Номер: #{selectedPatient.number}</div>
              <Badge variant="info" className="mt-1">
                {selectedPatient.source === 'online' ? '📱 Онлайн' : '🏥 Регистратура'}
              </Badge>
            </div>
          )}
        </div>
      </div>

      {/* Сообщения */}
      {message.text && (
        <div className={`flex items-center p-4 rounded-lg mb-4 ${
          message.type === 'success' 
            ? 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-400'
            : message.type === 'error'
            ? 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400'
            : 'bg-blue-50 text-blue-700 dark:bg-blue-900/20 dark:text-blue-400'
        }`}>
          {message.type === 'success' ? (
            <CheckCircle size={20} className="mr-2" />
          ) : (
            <AlertCircle size={20} className="mr-2" />
          )}
          {message.text}
        </div>
      )}

      {/* Навигация по вкладкам */}
      <div className="flex space-x-2 mb-6 overflow-x-auto">
        {tabs.map(tab => {
          const isActive = activeTab === tab.id;
          const TabIcon = tab.icon;
          
          return (
            <button
              key={tab.id}
              style={isActive ? activeTabStyle : tabStyle}
              onClick={() => setActiveTab(tab.id)}
            >
              <TabIcon size={18} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Контент вкладок */}
      <div>
        {/* Очередь пациентов */}
        {activeTab === 'queue' && (
          <DoctorQueuePanel
            specialty="cardiology"
            onPatientSelect={handlePatientSelect}
          />
        )}

        {/* Прием пациента */}
        {activeTab === 'visit' && selectedPatient && (
          <div className="space-y-6">
            {/* Информация о пациенте */}
            <Card className="p-6">
              <h3 className="text-lg font-medium mb-4 flex items-center">
                <User size={20} className="mr-2 text-blue-600" />
                Пациент #{selectedPatient.number}
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    ФИО пациента
                  </label>
                  <div className="text-lg font-medium">{selectedPatient.patient_name}</div>
                </div>
                
                {selectedPatient.phone && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Телефон
                    </label>
                    <div className="flex items-center">
                      <Phone size={16} className="mr-2 text-gray-400" />
                      {selectedPatient.phone}
                    </div>
                  </div>
                )}
              </div>
            </Card>

            {/* Жалобы и диагноз */}
            <Card className="p-6">
              <h3 className="text-lg font-medium mb-4">📝 Жалобы и диагноз</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Жалобы пациента
                  </label>
                  <textarea
                    value={visitData.complaint}
                    onChange={(e) => setVisitData({ ...visitData, complaint: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    rows={4}
                    placeholder="Опишите жалобы пациента..."
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Диагноз
                    </label>
                    <input
                      type="text"
                      value={visitData.diagnosis}
                      onChange={(e) => setVisitData({ ...visitData, diagnosis: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                      placeholder="Диагноз"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      МКБ-10
                    </label>
                    <input
                      type="text"
                      value={visitData.icd10}
                      onChange={(e) => setVisitData({ ...visitData, icd10: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                      placeholder="I25.9"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Примечания
                  </label>
                  <textarea
                    value={visitData.notes}
                    onChange={(e) => setVisitData({ ...visitData, notes: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    rows={3}
                    placeholder="Дополнительные примечания..."
                  />
                </div>
              </div>
            </Card>

            {/* Услуги визита */}
            <DoctorServiceSelector
              specialty="cardiology"
              selectedServices={selectedServices}
              onServicesChange={setSelectedServices}
              canEditPrices={true}
            />

            {/* Действия */}
            <Card className="p-6">
              <div className="flex justify-end space-x-3">
                <Button
                  variant="outline"
                  onClick={() => {
                    setSelectedPatient(null);
                    setActiveTab('queue');
                  }}
                >
                  Отменить
                </Button>
                <Button
                  onClick={handleSaveVisit}
                  disabled={loading || !visitData.complaint}
                >
                  {loading ? (
                    <RefreshCw size={16} className="animate-spin mr-2" />
                  ) : (
                    <Save size={16} className="mr-2" />
                  )}
                  Завершить прием
                </Button>
              </div>
            </Card>
          </div>
        )}

        {/* ЭКГ */}
        {activeTab === 'ecg' && (
          <div className="space-y-6">
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
          <div className="space-y-6">
            <Card className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium flex items-center">
                  <TestTube size={20} className="mr-2 text-purple-600" />
                  Анализы крови
                </h3>
                <Button onClick={() => setShowBloodTestForm(true)}>
                  <Plus size={16} className="mr-2" />
                  Новый анализ
                </Button>
              </div>

              {bloodTests.length > 0 ? (
                <div className="space-y-4">
                  {bloodTests.map((test) => (
                    <div key={test.id} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex justify-between items-start mb-2">
                        <h4 className="font-medium">Анализ #{test.id}</h4>
                        <Badge variant="info">{test.test_date}</Badge>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-gray-600">
                        <div>🩸 Холестерин: {test.cholesterol_total} мг/дл</div>
                        <div>HDL: {test.cholesterol_hdl}</div>
                        <div>LDL: {test.cholesterol_ldl}</div>
                        <div>Триглицериды: {test.triglycerides}</div>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm text-gray-600 mt-2">
                        <div>🍬 Глюкоза: {test.glucose} мг/дл</div>
                        <div>CRP: {test.crp} мг/л</div>
                        <div>Тропонин: {test.troponin} нг/мл</div>
                      </div>
                      {test.interpretation && (
                        <div className="mt-2 text-sm">
                          <strong>Интерпретация:</strong> {test.interpretation}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <TestTube size={48} className="mx-auto mb-4 text-gray-300" />
                  <p>Нет данных анализов</p>
                </div>
              )}
            </Card>

            {/* Форма анализа крови */}
            {showBloodTestForm && (
              <Card className="p-6">
                <h3 className="text-lg font-medium mb-4">Новый анализ крови</h3>
                <form onSubmit={handleBloodTestSubmit} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Дата анализа *
                      </label>
                      <input
                        type="date"
                        value={bloodTestForm.test_date}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, test_date: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Общий холестерин (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.cholesterol_total}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, cholesterol_total: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="<200"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        HDL холестерин (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.cholesterol_hdl}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, cholesterol_hdl: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder=">40"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        LDL холестерин (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.cholesterol_ldl}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, cholesterol_ldl: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="<100"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Триглицериды (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.triglycerides}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, triglycerides: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="<150"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Глюкоза (мг/дл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.glucose}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, glucose: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="70-100"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        CRP (мг/л)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.crp}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, crp: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="<3.0"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Тропонин (нг/мл)
                      </label>
                      <input
                        type="number"
                        value={bloodTestForm.troponin}
                        onChange={(e) => setBloodTestForm({ ...bloodTestForm, troponin: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="<0.04"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Интерпретация
                    </label>
                    <textarea
                      value={bloodTestForm.interpretation}
                      onChange={(e) => setBloodTestForm({ ...bloodTestForm, interpretation: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                      rows={4}
                      placeholder="Интерпретация результатов анализов"
                    />
                  </div>

                  <div className="flex justify-end space-x-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setShowBloodTestForm(false)}
                    >
                      Отмена
                    </Button>
                    <Button type="submit">
                      <Save size={16} className="mr-2" />
                      Сохранить анализ
                    </Button>
                  </div>
                </form>
              </Card>
            )}
          </div>
        )}

        {/* AI Помощник */}
        {activeTab === 'ai' && (
          <AIAssistant
            specialty="cardiology"
            onSuggestionSelect={handleAISuggestion}
          />
        )}

        {/* Управление услугами */}
        {activeTab === 'services' && (
          <DoctorServiceSelector
            specialty="cardiology"
            selectedServices={[]}
            onServicesChange={() => {}}
            canEditPrices={false}
          />
        )}

        {/* История (заглушка) */}
        {activeTab === 'history' && (
          <Card className="p-8 text-center">
            <Calendar size={48} className="mx-auto text-gray-400 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              История приемов
            </h3>
            <p className="text-gray-500">
              Функция в разработке
            </p>
          </Card>
        )}
      </div>

      {/* Модальное окно Schedule Next */}
      {scheduleNextModal.open && (
        <ScheduleNextModal
          isOpen={scheduleNextModal.open}
          onClose={() => setScheduleNextModal({ open: false, patient: null })}
          patient={scheduleNextModal.patient}
          theme={{ isDark, getColor, getSpacing: (size) => theme.spacing[size], getFontSize: (size) => theme.fontSize[size] }}
          specialtyFilter="cardiology"
        />
      )}
    </div>
  );
};

export default CardiologistPanelUnified;
