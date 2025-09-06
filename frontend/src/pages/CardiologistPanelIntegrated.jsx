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
  Phone
} from 'lucide-react';
import { Card, Button, Badge } from '../design-system/components';
import { useTheme } from '../contexts/ThemeContext';
import DoctorQueuePanel from '../components/doctor/DoctorQueuePanel';
import DoctorServiceSelector from '../components/doctor/DoctorServiceSelector';
import AIAssistant from '../components/ai/AIAssistant';

/**
 * Интегрированная панель кардиолога
 * Основа: passport.md стр. 1141-1568
 */
const CardiologistPanelIntegrated = () => {
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

  // Вкладки панели
  const tabs = [
    { id: 'queue', label: 'Очередь', icon: Users, color: 'text-blue-600' },
    { id: 'visit', label: 'Прием пациента', icon: Heart, color: 'text-red-600' },
    { id: 'ai', label: 'AI Помощник', icon: Brain, color: 'text-purple-600' },
    { id: 'services', label: 'Услуги', icon: Activity, color: 'text-green-600' },
    { id: 'history', label: 'История', icon: FileText, color: 'text-gray-600' }
  ];

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

      // Завершаем прием в очереди
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
              Интегрированная панель с очередью и услугами из админ системы
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
      <div className="flex space-x-2 mb-6">
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
    </div>
  );
};

export default CardiologistPanelIntegrated;
