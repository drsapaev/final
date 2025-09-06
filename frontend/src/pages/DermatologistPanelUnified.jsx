import React, { useState, useEffect } from 'react';
import { 
  Camera, 
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
  TestTube,
  Image as ImageIcon,
  Scissors,
  Sparkles
} from 'lucide-react';
import { Card, Button, Badge } from '../design-system/components';
import { useTheme } from '../contexts/ThemeContext';
import DoctorQueuePanel from '../components/doctor/DoctorQueuePanel';
import DoctorServiceSelector from '../components/doctor/DoctorServiceSelector';
import AIAssistant from '../components/ai/AIAssistant';
import PhotoComparison from '../components/dermatology/PhotoComparison';

/**
 * Унифицированная панель дерматолога
 * Объединяет: очередь + фото до/после + косметология + AI
 */
const DermatologistPanelUnified = () => {
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

  // Специализированные данные дерматолога
  const [skinExamination, setSkinExamination] = useState({
    patient_id: '',
    examination_date: '',
    skin_type: '',
    skin_condition: '',
    lesions: '',
    distribution: '',
    symptoms: '',
    diagnosis: '',
    treatment_plan: ''
  });

  const [cosmeticProcedure, setCosmeticProcedure] = useState({
    patient_id: '',
    procedure_date: '',
    procedure_type: '',
    area_treated: '',
    products_used: '',
    results: '',
    follow_up: ''
  });

  const [showSkinForm, setShowSkinForm] = useState(false);
  const [showCosmeticForm, setShowCosmeticForm] = useState(false);
  const [skinExaminations, setSkinExaminations] = useState([]);
  const [cosmeticProcedures, setCosmeticProcedures] = useState([]);

  // Вкладки панели
  const tabs = [
    { id: 'queue', label: 'Очередь', icon: Users, color: 'text-blue-600' },
    { id: 'visit', label: 'Прием', icon: Stethoscope, color: 'text-orange-600' },
    { id: 'photos', label: 'Фото', icon: Camera, color: 'text-purple-600' },
    { id: 'skin', label: 'Осмотр кожи', icon: Activity, color: 'text-green-600' },
    { id: 'cosmetic', label: 'Косметология', icon: Sparkles, color: 'text-pink-600' },
    { id: 'ai', label: 'AI Помощник', icon: Brain, color: 'text-indigo-600' },
    { id: 'services', label: 'Услуги', icon: Scissors, color: 'text-orange-600' },
    { id: 'history', label: 'История', icon: FileText, color: 'text-gray-600' }
  ];

  useEffect(() => {
    if (selectedPatient) {
      loadPatientData();
    }
  }, [selectedPatient]);

  const loadPatientData = async () => {
    if (!selectedPatient?.patient?.id) return;
    
    try {
      // Загружаем осмотры кожи пациента
      const skinResponse = await fetch(`/api/v1/dermatology/skin-examinations?patient_id=${selectedPatient.patient.id}&limit=10`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (skinResponse.ok) {
        const skinData = await skinResponse.json();
        setSkinExaminations(skinData);
      }

      // Загружаем косметические процедуры пациента
      const cosmeticResponse = await fetch(`/api/v1/dermatology/cosmetic-procedures?patient_id=${selectedPatient.patient.id}&limit=10`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` }
      });
      if (cosmeticResponse.ok) {
        const cosmeticData = await cosmeticResponse.json();
        setCosmeticProcedures(cosmeticData);
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

  // Обработка осмотра кожи
  const handleSkinExaminationSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('/api/v1/dermatology/skin-examinations', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(skinExamination)
      });

      if (response.ok) {
        setShowSkinForm(false);
        setSkinExamination({
          patient_id: '',
          examination_date: '',
          skin_type: '',
          skin_condition: '',
          lesions: '',
          distribution: '',
          symptoms: '',
          diagnosis: '',
          treatment_plan: ''
        });
        loadPatientData();
        setMessage({ type: 'success', text: 'Осмотр кожи сохранен успешно' });
      }
    } catch (error) {
      console.error('Ошибка сохранения осмотра:', error);
      setMessage({ type: 'error', text: 'Ошибка сохранения осмотра кожи' });
    }
  };

  // Обработка косметической процедуры
  const handleCosmeticProcedureSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch('/api/v1/dermatology/cosmetic-procedures', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(cosmeticProcedure)
      });

      if (response.ok) {
        setShowCosmeticForm(false);
        setCosmeticProcedure({
          patient_id: '',
          procedure_date: '',
          procedure_type: '',
          area_treated: '',
          products_used: '',
          results: '',
          follow_up: ''
        });
        loadPatientData();
        setMessage({ type: 'success', text: 'Косметическая процедура сохранена успешно' });
      }
    } catch (error) {
      console.error('Ошибка сохранения процедуры:', error);
      setMessage({ type: 'error', text: 'Ошибка сохранения косметической процедуры' });
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
    background: '#fd7e14',
    color: 'white',
    boxShadow: '0 2px 4px rgba(253, 126, 20, 0.3)'
  };

  return (
    <div style={pageStyle}>
      {/* Заголовок */}
      <div style={headerStyle}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center">
              <Camera className="mr-3 text-orange-600" size={28} />
              Панель дерматолога
            </h1>
            <p className="text-gray-600 dark:text-gray-400 mt-1">
              Унифицированная панель с фото до/после, осмотрами кожи и косметологией
            </p>
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
            specialty="dermatology"
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
                      placeholder="L70.9"
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
              specialty="dermatology"
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

        {/* Фото до/после */}
        {activeTab === 'photos' && selectedPatient && (
          <PhotoComparison
            patientId={selectedPatient.patient?.id}
            patientName={selectedPatient.patient_name}
            onPhotosChange={(photos) => {
              console.log('Фото обновлены:', photos);
            }}
          />
        )}

        {/* Осмотр кожи */}
        {activeTab === 'skin' && (
          <div className="space-y-6">
            <Card className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium flex items-center">
                  <Activity size={20} className="mr-2 text-green-600" />
                  Осмотры кожи
                </h3>
                <Button onClick={() => setShowSkinForm(true)}>
                  <Plus size={16} className="mr-2" />
                  Новый осмотр
                </Button>
              </div>

              {skinExaminations.length > 0 ? (
                <div className="space-y-4">
                  {skinExaminations.map((exam) => (
                    <div key={exam.id} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex justify-between items-start mb-2">
                        <h4 className="font-medium">Осмотр #{exam.id}</h4>
                        <Badge variant="info">{exam.examination_date}</Badge>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-gray-600">
                        <div>🧴 Тип кожи: {exam.skin_type}</div>
                        <div>📈 Состояние: {exam.skin_condition}</div>
                        <div>🎯 Поражения: {exam.lesions}</div>
                        <div>📍 Распространение: {exam.distribution}</div>
                      </div>
                      {exam.diagnosis && (
                        <div className="mt-2 text-sm">
                          <strong>Диагноз:</strong> {exam.diagnosis}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <Activity size={48} className="mx-auto mb-4 text-gray-300" />
                  <p>Нет данных осмотров кожи</p>
                </div>
              )}
            </Card>

            {/* Форма осмотра кожи */}
            {showSkinForm && (
              <Card className="p-6">
                <h3 className="text-lg font-medium mb-4">Новый осмотр кожи</h3>
                <form onSubmit={handleSkinExaminationSubmit} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Дата осмотра *
                      </label>
                      <input
                        type="date"
                        value={skinExamination.examination_date}
                        onChange={(e) => setSkinExamination({ ...skinExamination, examination_date: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Тип кожи *
                      </label>
                      <select
                        value={skinExamination.skin_type}
                        onChange={(e) => setSkinExamination({ ...skinExamination, skin_type: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        required
                      >
                        <option value="">Выберите тип кожи</option>
                        <option value="normal">Нормальная</option>
                        <option value="dry">Сухая</option>
                        <option value="oily">Жирная</option>
                        <option value="combination">Комбинированная</option>
                        <option value="sensitive">Чувствительная</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Состояние кожи
                      </label>
                      <input
                        type="text"
                        value={skinExamination.skin_condition}
                        onChange={(e) => setSkinExamination({ ...skinExamination, skin_condition: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="Хорошее, удовлетворительное, проблемное"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Поражения
                      </label>
                      <input
                        type="text"
                        value={skinExamination.lesions}
                        onChange={(e) => setSkinExamination({ ...skinExamination, lesions: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="Акне, пигментация, родинки"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Диагноз
                    </label>
                    <input
                      type="text"
                      value={skinExamination.diagnosis}
                      onChange={(e) => setSkinExamination({ ...skinExamination, diagnosis: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                      placeholder="Диагноз"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      План лечения
                    </label>
                    <textarea
                      value={skinExamination.treatment_plan}
                      onChange={(e) => setSkinExamination({ ...skinExamination, treatment_plan: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                      rows={4}
                      placeholder="План лечения и рекомендации"
                    />
                  </div>

                  <div className="flex justify-end space-x-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setShowSkinForm(false)}
                    >
                      Отмена
                    </Button>
                    <Button type="submit">
                      <Save size={16} className="mr-2" />
                      Сохранить осмотр
                    </Button>
                  </div>
                </form>
              </Card>
            )}
          </div>
        )}

        {/* Косметология */}
        {activeTab === 'cosmetic' && (
          <div className="space-y-6">
            <Card className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium flex items-center">
                  <Sparkles size={20} className="mr-2 text-pink-600" />
                  Косметические процедуры
                </h3>
                <Button onClick={() => setShowCosmeticForm(true)}>
                  <Plus size={16} className="mr-2" />
                  Новая процедура
                </Button>
              </div>

              {cosmeticProcedures.length > 0 ? (
                <div className="space-y-4">
                  {cosmeticProcedures.map((procedure) => (
                    <div key={procedure.id} className="border border-gray-200 rounded-lg p-4">
                      <div className="flex justify-between items-start mb-2">
                        <h4 className="font-medium">Процедура #{procedure.id}</h4>
                        <Badge variant="info">{procedure.procedure_date}</Badge>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm text-gray-600">
                        <div>✨ Тип: {procedure.procedure_type}</div>
                        <div>📍 Область: {procedure.area_treated}</div>
                        <div>🧴 Продукты: {procedure.products_used}</div>
                      </div>
                      {procedure.results && (
                        <div className="mt-2 text-sm">
                          <strong>Результаты:</strong> {procedure.results}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <Sparkles size={48} className="mx-auto mb-4 text-gray-300" />
                  <p>Нет данных косметических процедур</p>
                </div>
              )}
            </Card>

            {/* Форма косметической процедуры */}
            {showCosmeticForm && (
              <Card className="p-6">
                <h3 className="text-lg font-medium mb-4">Новая косметическая процедура</h3>
                <form onSubmit={handleCosmeticProcedureSubmit} className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Дата процедуры *
                      </label>
                      <input
                        type="date"
                        value={cosmeticProcedure.procedure_date}
                        onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, procedure_date: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Тип процедуры *
                      </label>
                      <select
                        value={cosmeticProcedure.procedure_type}
                        onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, procedure_type: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        required
                      >
                        <option value="">Выберите процедуру</option>
                        <option value="cleaning">Чистка лица</option>
                        <option value="peeling">Пилинг</option>
                        <option value="botox">Ботокс</option>
                        <option value="filler">Филлеры</option>
                        <option value="laser">Лазерная терапия</option>
                        <option value="mesotherapy">Мезотерапия</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Область обработки
                      </label>
                      <input
                        type="text"
                        value={cosmeticProcedure.area_treated}
                        onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, area_treated: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="Лицо, шея, декольте"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Использованные продукты
                      </label>
                      <input
                        type="text"
                        value={cosmeticProcedure.products_used}
                        onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, products_used: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                        placeholder="Названия препаратов"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Результаты
                    </label>
                    <textarea
                      value={cosmeticProcedure.results}
                      onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, results: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                      rows={4}
                      placeholder="Описание результатов процедуры"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                      Рекомендации по уходу
                    </label>
                    <textarea
                      value={cosmeticProcedure.follow_up}
                      onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, follow_up: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                      rows={3}
                      placeholder="Рекомендации по уходу после процедуры"
                    />
                  </div>

                  <div className="flex justify-end space-x-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setShowCosmeticForm(false)}
                    >
                      Отмена
                    </Button>
                    <Button type="submit">
                      <Save size={16} className="mr-2" />
                      Сохранить процедуру
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
            specialty="dermatology"
            onSuggestionSelect={handleAISuggestion}
          />
        )}

        {/* Управление услугами */}
        {activeTab === 'services' && (
          <DoctorServiceSelector
            specialty="dermatology"
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
    </div>
  );
};

export default DermatologistPanelUnified;
