import React, { useState, useCallback } from 'react';
import { 
  Heart, 
  Pill, 
  Activity, 
  FileText, 
  AlertCircle, 
  CheckCircle, 
  Loader, 
  User,
  Calendar,
  TrendingUp,
  Download,
  Share2,
  Stethoscope,
  Brain,
  Target,
  Clock
} from 'lucide-react';
import { toast } from 'react-toastify';
import api from '../../utils/api';

const TreatmentRecommendations = () => {
  const [activeTab, setActiveTab] = useState('treatment-plan');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  // Состояния для разных форм
  const [treatmentPlanData, setTreatmentPlanData] = useState({
    patient_data: {
      age: '',
      gender: '',
      weight: '',
      allergies: [],
      comorbidities: []
    },
    diagnosis: '',
    medical_history: []
  });

  const [medicationData, setMedicationData] = useState({
    current_medications: [],
    patient_profile: {
      age: '',
      gender: '',
      weight: '',
      kidney_function: '',
      liver_function: '',
      allergies: []
    },
    condition: ''
  });

  const [effectivenessData, setEffectivenessData] = useState({
    treatment_history: [],
    patient_response: {
      symptoms: [],
      side_effects: [],
      quality_of_life_score: '',
      adherence_rate: ''
    }
  });

  const [lifestyleData, setLifestyleData] = useState({
    patient_profile: {
      age: '',
      gender: '',
      bmi: '',
      activity_level: '',
      smoking_status: '',
      alcohol_consumption: '',
      occupation: ''
    },
    conditions: []
  });

  const tabs = [
    { id: 'treatment-plan', label: 'План лечения', icon: <FileText className="w-4 h-4" /> },
    { id: 'medication', label: 'Оптимизация терапии', icon: <Pill className="w-4 h-4" /> },
    { id: 'effectiveness', label: 'Эффективность', icon: <TrendingUp className="w-4 h-4" /> },
    { id: 'lifestyle', label: 'Образ жизни', icon: <Activity className="w-4 h-4" /> }
  ];

  const handleSubmit = async (endpoint, data) => {
    setLoading(true);
    setResult(null);

    try {
      const response = await api.post(`/ai/${endpoint}`, data);
      setResult(response.data);
      toast.success('Рекомендации получены!');
    } catch (error) {
      console.error('Ошибка получения рекомендаций:', error);
      toast.error(error.response?.data?.detail || 'Ошибка при получении рекомендаций');
    } finally {
      setLoading(false);
    }
  };

  const exportResult = () => {
    if (!result) return;
    
    const dataStr = JSON.stringify(result, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `treatment_recommendations_${activeTab}_${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const renderTreatmentPlanForm = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Возраст пациента</label>
          <input
            type="number"
            value={treatmentPlanData.patient_data.age}
            onChange={(e) => setTreatmentPlanData(prev => ({
              ...prev,
              patient_data: { ...prev.patient_data, age: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Например: 45"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Пол</label>
          <select
            value={treatmentPlanData.patient_data.gender}
            onChange={(e) => setTreatmentPlanData(prev => ({
              ...prev,
              patient_data: { ...prev.patient_data, gender: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите пол</option>
            <option value="мужской">Мужской</option>
            <option value="женский">Женский</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Вес (кг)</label>
          <input
            type="number"
            value={treatmentPlanData.patient_data.weight}
            onChange={(e) => setTreatmentPlanData(prev => ({
              ...prev,
              patient_data: { ...prev.patient_data, weight: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Например: 70"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Диагноз</label>
          <input
            type="text"
            value={treatmentPlanData.diagnosis}
            onChange={(e) => setTreatmentPlanData(prev => ({
              ...prev,
              diagnosis: e.target.value
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Основной диагноз"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Аллергии</label>
        <input
          type="text"
          value={treatmentPlanData.patient_data.allergies.join(', ')}
          onChange={(e) => setTreatmentPlanData(prev => ({
            ...prev,
            patient_data: { 
              ...prev.patient_data, 
              allergies: e.target.value.split(',').map(item => item.trim()).filter(Boolean)
            }
          }))}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Например: пенициллин, аспирин"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Сопутствующие заболевания</label>
        <input
          type="text"
          value={treatmentPlanData.patient_data.comorbidities.join(', ')}
          onChange={(e) => setTreatmentPlanData(prev => ({
            ...prev,
            patient_data: { 
              ...prev.patient_data, 
              comorbidities: e.target.value.split(',').map(item => item.trim()).filter(Boolean)
            }
          }))}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Например: гипертония, диабет"
        />
      </div>

      <button
        onClick={() => handleSubmit('generate-treatment-plan', treatmentPlanData)}
        disabled={loading || !treatmentPlanData.diagnosis}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
            Генерируем план...
          </>
        ) : (
          <>
            <Target className="h-5 w-5 mr-2" />
            Создать план лечения
          </>
        )}
      </button>
    </div>
  );

  const renderMedicationForm = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Возраст</label>
          <input
            type="number"
            value={medicationData.patient_profile.age}
            onChange={(e) => setMedicationData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, age: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Состояние</label>
          <input
            type="text"
            value={medicationData.condition}
            onChange={(e) => setMedicationData(prev => ({
              ...prev,
              condition: e.target.value
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Диагноз или состояние"
          />
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Текущие препараты</label>
        <textarea
          value={medicationData.current_medications.map(med => `${med.name} ${med.dosage} ${med.frequency}`).join('\n')}
          onChange={(e) => {
            const lines = e.target.value.split('\n').filter(Boolean);
            const medications = lines.map(line => {
              const parts = line.split(' ');
              return {
                name: parts[0] || '',
                dosage: parts[1] || '',
                frequency: parts.slice(2).join(' ') || ''
              };
            });
            setMedicationData(prev => ({
              ...prev,
              current_medications: medications
            }));
          }}
          rows={4}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Например:&#10;Лизиноприл 10мг 1 раз в день&#10;Метформин 500мг 2 раза в день"
        />
      </div>

      <button
        onClick={() => handleSubmit('optimize-medication', medicationData)}
        disabled={loading || !medicationData.condition}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
            Оптимизируем...
          </>
        ) : (
          <>
            <Pill className="h-5 w-5 mr-2" />
            Оптимизировать терапию
          </>
        )}
      </button>
    </div>
  );

  const renderEffectivenessForm = () => (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Текущие симптомы</label>
        <input
          type="text"
          value={effectivenessData.patient_response.symptoms.join(', ')}
          onChange={(e) => setEffectivenessData(prev => ({
            ...prev,
            patient_response: { 
              ...prev.patient_response, 
              symptoms: e.target.value.split(',').map(item => item.trim()).filter(Boolean)
            }
          }))}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Например: головная боль, слабость"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Качество жизни (1-10)</label>
          <input
            type="number"
            min="1"
            max="10"
            value={effectivenessData.patient_response.quality_of_life_score}
            onChange={(e) => setEffectivenessData(prev => ({
              ...prev,
              patient_response: { ...prev.patient_response, quality_of_life_score: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Приверженность лечению (%)</label>
          <input
            type="number"
            min="0"
            max="100"
            value={effectivenessData.patient_response.adherence_rate}
            onChange={(e) => setEffectivenessData(prev => ({
              ...prev,
              patient_response: { ...prev.patient_response, adherence_rate: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <button
        onClick={() => handleSubmit('assess-treatment-effectiveness', effectivenessData)}
        disabled={loading}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
            Оцениваем...
          </>
        ) : (
          <>
            <TrendingUp className="h-5 w-5 mr-2" />
            Оценить эффективность
          </>
        )}
      </button>
    </div>
  );

  const renderLifestyleForm = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Возраст</label>
          <input
            type="number"
            value={lifestyleData.patient_profile.age}
            onChange={(e) => setLifestyleData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, age: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">ИМТ</label>
          <input
            type="number"
            step="0.1"
            value={lifestyleData.patient_profile.bmi}
            onChange={(e) => setLifestyleData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, bmi: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Уровень активности</label>
          <select
            value={lifestyleData.patient_profile.activity_level}
            onChange={(e) => setLifestyleData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, activity_level: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите уровень</option>
            <option value="низкий">Низкий</option>
            <option value="умеренный">Умеренный</option>
            <option value="высокий">Высокий</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Курение</label>
          <select
            value={lifestyleData.patient_profile.smoking_status}
            onChange={(e) => setLifestyleData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, smoking_status: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите статус</option>
            <option value="не курит">Не курит</option>
            <option value="курит">Курит</option>
            <option value="бросил">Бросил</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Заболевания</label>
        <input
          type="text"
          value={lifestyleData.conditions.join(', ')}
          onChange={(e) => setLifestyleData(prev => ({
            ...prev,
            conditions: e.target.value.split(',').map(item => item.trim()).filter(Boolean)
          }))}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Например: гипертония, диабет"
        />
      </div>

      <button
        onClick={() => handleSubmit('suggest-lifestyle-modifications', lifestyleData)}
        disabled={loading}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-orange-600 hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
            Генерируем рекомендации...
          </>
        ) : (
          <>
            <Activity className="h-5 w-5 mr-2" />
            Получить рекомендации
          </>
        )}
      </button>
    </div>
  );

  const renderResult = () => {
    if (!result) return null;

    if (result.error) {
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <AlertCircle className="h-5 w-5 text-red-400 mr-2" />
            <h3 className="text-sm font-medium text-red-800">Ошибка</h3>
          </div>
          <p className="mt-2 text-sm text-red-700">{result.error}</p>
        </div>
      );
    }

    return (
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 flex items-center">
            <CheckCircle className="h-5 w-5 text-green-500 mr-2" />
            Результат анализа
          </h3>
          <button
            onClick={exportResult}
            className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <Download className="h-4 w-4 mr-1" />
            Экспорт
          </button>
        </div>

        <div className="space-y-4">
          {Object.entries(result).map(([key, value]) => (
            <div key={key} className="border-l-4 border-blue-400 pl-4">
              <h4 className="font-medium text-gray-900 capitalize mb-2">
                {key.replace(/_/g, ' ')}
              </h4>
              <div className="text-sm text-gray-600">
                {typeof value === 'object' && value !== null ? (
                  <pre className="whitespace-pre-wrap bg-gray-50 p-2 rounded text-xs">
                    {JSON.stringify(value, null, 2)}
                  </pre>
                ) : (
                  <p>{String(value)}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900 flex items-center">
            <Heart className="h-6 w-6 text-red-600 mr-2" />
            AI Рекомендации Лечения
          </h2>
          <p className="mt-1 text-sm text-gray-600">
            Персонализированные планы лечения и рекомендации на основе данных пациента
          </p>
        </div>

        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8 px-6">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                {tabs.find(tab => tab.id === activeTab)?.label}
              </h3>
              {activeTab === 'treatment-plan' && renderTreatmentPlanForm()}
              {activeTab === 'medication' && renderMedicationForm()}
              {activeTab === 'effectiveness' && renderEffectivenessForm()}
              {activeTab === 'lifestyle' && renderLifestyleForm()}
            </div>

            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">Результат</h3>
              {renderResult()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TreatmentRecommendations;

