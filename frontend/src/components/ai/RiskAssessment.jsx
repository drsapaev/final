import React, { useState } from 'react';
import { 
  AlertTriangle, 
  Activity, 
  Heart, 
  Stethoscope, 
  UserCheck,
  TrendingUp,
  Shield,
  Clock,
  FileText,
  BarChart3,
  Target,
  Zap,
  CheckCircle,
  XCircle,
  AlertCircle,
  Info,
  Loader,
  Download,
  Plus,
  Minus
} from 'lucide-react';
import { toast } from 'react-toastify';
import api from '../../utils/api';

const RiskAssessment = () => {
  const [activeTab, setActiveTab] = useState('patient-risk');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  // Состояния для разных форм
  const [patientRiskData, setPatientRiskData] = useState({
    patient_data: {
      age: '',
      gender: '',
      weight: '',
      height: '',
      bmi: '',
      smoking_status: '',
      alcohol_consumption: '',
      comorbidities: [],
      medications: [],
      family_history: []
    },
    risk_factors: [],
    condition: ''
  });

  const [complicationData, setComplicationData] = useState({
    patient_profile: {
      age: '',
      gender: '',
      comorbidities: [],
      medications: [],
      allergies: [],
      previous_complications: []
    },
    procedure_or_condition: '',
    timeline: ''
  });

  const [mortalityData, setMortalityData] = useState({
    patient_data: {
      age: '',
      gender: '',
      vital_signs: {},
      laboratory_values: {},
      comorbidities: [],
      severity_indicators: {}
    },
    condition: '',
    scoring_system: ''
  });

  const [surgicalData, setSurgicalData] = useState({
    patient_profile: {
      age: '',
      gender: '',
      weight: '',
      height: '',
      asa_class: '',
      comorbidities: [],
      medications: [],
      previous_surgeries: [],
      allergies: [],
      functional_status: ''
    },
    surgery_type: '',
    anesthesia_type: ''
  });

  const [readmissionData, setReadmissionData] = useState({
    patient_data: {
      age: '',
      gender: '',
      primary_diagnosis: '',
      comorbidities: [],
      medications: [],
      length_of_stay: '',
      previous_admissions: ''
    },
    discharge_condition: '',
    social_factors: {
      social_support: '',
      insurance_status: '',
      transportation: '',
      housing_situation: '',
      caregiver_availability: '',
      health_literacy: ''
    }
  });

  const tabs = [
    { id: 'patient-risk', label: 'Оценка рисков', icon: <AlertTriangle className="w-4 h-4" /> },
    { id: 'complications', label: 'Прогноз осложнений', icon: <Activity className="w-4 h-4" /> },
    { id: 'mortality', label: 'Риск смертности', icon: <Heart className="w-4 h-4" /> },
    { id: 'surgical', label: 'Хирургические риски', icon: <Stethoscope className="w-4 h-4" /> },
    { id: 'readmission', label: 'Реадмиссия', icon: <UserCheck className="w-4 h-4" /> }
  ];

  const handleSubmit = async (endpoint, data) => {
    setLoading(true);
    setResult(null);

    try {
      const response = await api.post(`/ai/${endpoint}`, data);
      setResult(response.data);
      toast.success('Анализ завершен!');
    } catch (error) {
      console.error('Ошибка анализа:', error);
      toast.error(error.response?.data?.detail || 'Ошибка при выполнении анализа');
    } finally {
      setLoading(false);
    }
  };

  const exportResult = () => {
    if (!result) return;
    
    const dataStr = JSON.stringify(result, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `risk_assessment_${activeTab}_${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const getRiskColor = (level) => {
    switch (level?.toLowerCase()) {
      case 'критический':
      case 'critical':
        return 'text-red-600 bg-red-50 border-red-200';
      case 'высокий':
      case 'high':
        return 'text-orange-600 bg-orange-50 border-orange-200';
      case 'умеренный':
      case 'moderate':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'низкий':
      case 'low':
        return 'text-green-600 bg-green-50 border-green-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const addArrayItem = (setter, path, defaultItem = '') => {
    setter(prev => {
      const newState = { ...prev };
      const keys = path.split('.');
      let current = newState;
      
      for (let i = 0; i < keys.length - 1; i++) {
        current = current[keys[i]];
      }
      
      const lastKey = keys[keys.length - 1];
      current[lastKey] = [...current[lastKey], defaultItem];
      
      return newState;
    });
  };

  const removeArrayItem = (setter, path, index) => {
    setter(prev => {
      const newState = { ...prev };
      const keys = path.split('.');
      let current = newState;
      
      for (let i = 0; i < keys.length - 1; i++) {
        current = current[keys[i]];
      }
      
      const lastKey = keys[keys.length - 1];
      current[lastKey] = current[lastKey].filter((_, i) => i !== index);
      
      return newState;
    });
  };

  const updateArrayItem = (setter, path, index, value) => {
    setter(prev => {
      const newState = { ...prev };
      const keys = path.split('.');
      let current = newState;
      
      for (let i = 0; i < keys.length - 1; i++) {
        current = current[keys[i]];
      }
      
      const lastKey = keys[keys.length - 1];
      current[lastKey][index] = value;
      
      return newState;
    });
  };

  const renderPatientRiskForm = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Возраст</label>
          <input
            type="number"
            value={patientRiskData.patient_data.age}
            onChange={(e) => setPatientRiskData(prev => ({
              ...prev,
              patient_data: { ...prev.patient_data, age: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Пол</label>
          <select
            value={patientRiskData.patient_data.gender}
            onChange={(e) => setPatientRiskData(prev => ({
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
            value={patientRiskData.patient_data.weight}
            onChange={(e) => setPatientRiskData(prev => ({
              ...prev,
              patient_data: { ...prev.patient_data, weight: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Курение</label>
          <select
            value={patientRiskData.patient_data.smoking_status}
            onChange={(e) => setPatientRiskData(prev => ({
              ...prev,
              patient_data: { ...prev.patient_data, smoking_status: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите статус</option>
            <option value="никогда не курил">Никогда не курил</option>
            <option value="бросил курить">Бросил курить</option>
            <option value="курит">Курит</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Употребление алкоголя</label>
          <select
            value={patientRiskData.patient_data.alcohol_consumption}
            onChange={(e) => setPatientRiskData(prev => ({
              ...prev,
              patient_data: { ...prev.patient_data, alcohol_consumption: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите</option>
            <option value="не употребляет">Не употребляет</option>
            <option value="умеренное">Умеренное</option>
            <option value="чрезмерное">Чрезмерное</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Состояние/Заболевание</label>
        <input
          type="text"
          value={patientRiskData.condition}
          onChange={(e) => setPatientRiskData(prev => ({ ...prev, condition: e.target.value }))}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Например: Ишемическая болезнь сердца"
        />
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-medium text-gray-700">Сопутствующие заболевания</label>
          <button
            onClick={() => addArrayItem(setPatientRiskData, 'patient_data.comorbidities')}
            className="inline-flex items-center px-2 py-1 border border-transparent text-sm font-medium rounded-md text-blue-700 bg-blue-100 hover:bg-blue-200"
          >
            <Plus className="w-4 h-4 mr-1" />
            Добавить
          </button>
        </div>
        {patientRiskData.patient_data.comorbidities.map((item, index) => (
          <div key={index} className="flex gap-2 mb-2">
            <input
              type="text"
              value={item}
              onChange={(e) => updateArrayItem(setPatientRiskData, 'patient_data.comorbidities', index, e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Заболевание"
            />
            <button
              onClick={() => removeArrayItem(setPatientRiskData, 'patient_data.comorbidities', index)}
              className="px-3 py-2 border border-red-300 text-red-700 rounded-md hover:bg-red-50"
            >
              <Minus className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-medium text-gray-700">Факторы риска</label>
          <button
            onClick={() => addArrayItem(setPatientRiskData, 'risk_factors')}
            className="inline-flex items-center px-2 py-1 border border-transparent text-sm font-medium rounded-md text-blue-700 bg-blue-100 hover:bg-blue-200"
          >
            <Plus className="w-4 h-4 mr-1" />
            Добавить
          </button>
        </div>
        {patientRiskData.risk_factors.map((item, index) => (
          <div key={index} className="flex gap-2 mb-2">
            <input
              type="text"
              value={item}
              onChange={(e) => updateArrayItem(setPatientRiskData, 'risk_factors', index, e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Фактор риска"
            />
            <button
              onClick={() => removeArrayItem(setPatientRiskData, 'risk_factors', index)}
              className="px-3 py-2 border border-red-300 text-red-700 rounded-md hover:bg-red-50"
            >
              <Minus className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      <button
        onClick={() => handleSubmit('assess-patient-risk', patientRiskData)}
        disabled={loading || !patientRiskData.condition}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
            Оцениваем риски...
          </>
        ) : (
          <>
            <AlertTriangle className="h-5 w-5 mr-2" />
            Оценить риски
          </>
        )}
      </button>
    </div>
  );

  const renderComplicationForm = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Процедура/Состояние</label>
          <input
            type="text"
            value={complicationData.procedure_or_condition}
            onChange={(e) => setComplicationData(prev => ({ ...prev, procedure_or_condition: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Например: Лапароскопическая холецистэктомия"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Временные рамки</label>
          <select
            value={complicationData.timeline}
            onChange={(e) => setComplicationData(prev => ({ ...prev, timeline: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите период</option>
            <option value="24 часа">24 часа</option>
            <option value="7 дней">7 дней</option>
            <option value="30 дней">30 дней</option>
            <option value="90 дней">90 дней</option>
            <option value="1 год">1 год</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Возраст</label>
          <input
            type="number"
            value={complicationData.patient_profile.age}
            onChange={(e) => setComplicationData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, age: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Пол</label>
          <select
            value={complicationData.patient_profile.gender}
            onChange={(e) => setComplicationData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, gender: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите пол</option>
            <option value="мужской">Мужской</option>
            <option value="женский">Женский</option>
          </select>
        </div>
      </div>

      <button
        onClick={() => handleSubmit('predict-complications', complicationData)}
        disabled={loading || !complicationData.procedure_or_condition || !complicationData.timeline}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-orange-600 hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-orange-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
            Прогнозируем осложнения...
          </>
        ) : (
          <>
            <Activity className="h-5 w-5 mr-2" />
            Спрогнозировать осложнения
          </>
        )}
      </button>
    </div>
  );

  const renderMortalityForm = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Состояние</label>
          <input
            type="text"
            value={mortalityData.condition}
            onChange={(e) => setMortalityData(prev => ({ ...prev, condition: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Например: Острый инфаркт миокарда"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Система оценки</label>
          <select
            value={mortalityData.scoring_system}
            onChange={(e) => setMortalityData(prev => ({ ...prev, scoring_system: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Автоматический выбор</option>
            <option value="APACHE II">APACHE II</option>
            <option value="SOFA">SOFA</option>
            <option value="SAPS II">SAPS II</option>
            <option value="CHA2DS2-VASc">CHA2DS2-VASc</option>
            <option value="GRACE">GRACE</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Возраст</label>
          <input
            type="number"
            value={mortalityData.patient_data.age}
            onChange={(e) => setMortalityData(prev => ({
              ...prev,
              patient_data: { ...prev.patient_data, age: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Пол</label>
          <select
            value={mortalityData.patient_data.gender}
            onChange={(e) => setMortalityData(prev => ({
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
      </div>

      <button
        onClick={() => handleSubmit('calculate-mortality-risk', mortalityData)}
        disabled={loading || !mortalityData.condition}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
            Рассчитываем риск...
          </>
        ) : (
          <>
            <Heart className="h-5 w-5 mr-2" />
            Рассчитать риск смертности
          </>
        )}
      </button>
    </div>
  );

  const renderSurgicalForm = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Тип операции</label>
          <input
            type="text"
            value={surgicalData.surgery_type}
            onChange={(e) => setSurgicalData(prev => ({ ...prev, surgery_type: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Например: Аппендэктомия"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Тип анестезии</label>
          <select
            value={surgicalData.anesthesia_type}
            onChange={(e) => setSurgicalData(prev => ({ ...prev, anesthesia_type: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите тип</option>
            <option value="общая">Общая анестезия</option>
            <option value="спинальная">Спинальная анестезия</option>
            <option value="эпидуральная">Эпидуральная анестезия</option>
            <option value="местная">Местная анестезия</option>
            <option value="седация">Седация</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Возраст</label>
          <input
            type="number"
            value={surgicalData.patient_profile.age}
            onChange={(e) => setSurgicalData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, age: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Класс ASA</label>
          <select
            value={surgicalData.patient_profile.asa_class}
            onChange={(e) => setSurgicalData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, asa_class: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите класс</option>
            <option value="I">ASA I - Здоровый пациент</option>
            <option value="II">ASA II - Легкое системное заболевание</option>
            <option value="III">ASA III - Тяжелое системное заболевание</option>
            <option value="IV">ASA IV - Угроза жизни</option>
            <option value="V">ASA V - Умирающий пациент</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Функциональный статус</label>
          <select
            value={surgicalData.patient_profile.functional_status}
            onChange={(e) => setSurgicalData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, functional_status: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите статус</option>
            <option value="независимый">Независимый</option>
            <option value="частично зависимый">Частично зависимый</option>
            <option value="полностью зависимый">Полностью зависимый</option>
          </select>
        </div>
      </div>

      <button
        onClick={() => handleSubmit('assess-surgical-risk', surgicalData)}
        disabled={loading || !surgicalData.surgery_type || !surgicalData.anesthesia_type}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
            Оцениваем риски...
          </>
        ) : (
          <>
            <Stethoscope className="h-5 w-5 mr-2" />
            Оценить хирургические риски
          </>
        )}
      </button>
    </div>
  );

  const renderReadmissionForm = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Основной диагноз</label>
          <input
            type="text"
            value={readmissionData.patient_data.primary_diagnosis}
            onChange={(e) => setReadmissionData(prev => ({
              ...prev,
              patient_data: { ...prev.patient_data, primary_diagnosis: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Диагноз при выписке"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Состояние при выписке</label>
          <select
            value={readmissionData.discharge_condition}
            onChange={(e) => setReadmissionData(prev => ({ ...prev, discharge_condition: e.target.value }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите состояние</option>
            <option value="стабильное">Стабильное</option>
            <option value="улучшение">Улучшение</option>
            <option value="без изменений">Без изменений</option>
            <option value="ухудшение">Ухудшение</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Возраст</label>
          <input
            type="number"
            value={readmissionData.patient_data.age}
            onChange={(e) => setReadmissionData(prev => ({
              ...prev,
              patient_data: { ...prev.patient_data, age: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Длительность госпитализации</label>
          <input
            type="text"
            value={readmissionData.patient_data.length_of_stay}
            onChange={(e) => setReadmissionData(prev => ({
              ...prev,
              patient_data: { ...prev.patient_data, length_of_stay: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Например: 5 дней"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Социальная поддержка</label>
          <select
            value={readmissionData.social_factors.social_support}
            onChange={(e) => setReadmissionData(prev => ({
              ...prev,
              social_factors: { ...prev.social_factors, social_support: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите уровень</option>
            <option value="хорошая">Хорошая</option>
            <option value="умеренная">Умеренная</option>
            <option value="ограниченная">Ограниченная</option>
            <option value="отсутствует">Отсутствует</option>
          </select>
        </div>
      </div>

      <button
        onClick={() => handleSubmit('predict-readmission-risk', readmissionData)}
        disabled={loading || !readmissionData.patient_data.primary_diagnosis || !readmissionData.discharge_condition}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
            Прогнозируем риск...
          </>
        ) : (
          <>
            <UserCheck className="h-5 w-5 mr-2" />
            Спрогнозировать риск реадмиссии
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
            <XCircle className="h-5 w-5 text-red-400 mr-2" />
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
            Результат анализа рисков
          </h3>
          <button
            onClick={exportResult}
            className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
          >
            <Download className="h-4 w-4 mr-1" />
            Экспорт
          </button>
        </div>

        {/* Специальное отображение для оценки рисков пациента */}
        {activeTab === 'patient-risk' && result.overall_risk_assessment && (
          <div className="space-y-4">
            <div className={`border rounded-lg p-4 ${getRiskColor(result.overall_risk_assessment.risk_level)}`}>
              <h4 className="font-medium mb-2">Общая оценка риска</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="font-medium">Уровень:</span>
                  <span className="ml-1">{result.overall_risk_assessment.risk_level}</span>
                </div>
                <div>
                  <span className="font-medium">Балл:</span>
                  <span className="ml-1">{result.overall_risk_assessment.risk_score}</span>
                </div>
                <div>
                  <span className="font-medium">Достоверность:</span>
                  <span className="ml-1">{result.overall_risk_assessment.confidence_level}</span>
                </div>
                <div>
                  <span className="font-medium">Дата:</span>
                  <span className="ml-1">{result.overall_risk_assessment.assessment_date}</span>
                </div>
              </div>
            </div>

            {result.risk_categories && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(result.risk_categories).map(([category, data]) => (
                  <div key={category} className={`border rounded-lg p-3 ${getRiskColor(data.level)}`}>
                    <h5 className="font-medium capitalize mb-1">
                      {category.replace(/_/g, ' ')}
                    </h5>
                    <p className="text-sm">Уровень: {data.level}</p>
                    <p className="text-sm">Балл: {data.score}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Общее отображение для других результатов */}
        {activeTab !== 'patient-risk' && (
          <div className="space-y-4">
            {Object.entries(result).map(([key, value]) => (
              <div key={key} className="border-l-4 border-blue-400 pl-4">
                <h4 className="font-medium text-gray-900 capitalize mb-2">
                  {key.replace(/_/g, ' ')}
                </h4>
                <div className="text-sm text-gray-600">
                  {typeof value === 'object' && value !== null ? (
                    <pre className="whitespace-pre-wrap bg-gray-50 p-2 rounded text-xs overflow-x-auto max-h-64">
                      {JSON.stringify(value, null, 2)}
                    </pre>
                  ) : (
                    <p>{String(value)}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900 flex items-center">
            <Shield className="h-6 w-6 text-red-600 mr-2" />
            AI Оценка Рисков и Прогнозирование Осложнений
          </h2>
          <p className="mt-1 text-sm text-gray-600">
            Комплексная оценка медицинских рисков с использованием искусственного интеллекта
          </p>
        </div>

        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8 px-6 overflow-x-auto">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 whitespace-nowrap ${
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
              {activeTab === 'patient-risk' && renderPatientRiskForm()}
              {activeTab === 'complications' && renderComplicationForm()}
              {activeTab === 'mortality' && renderMortalityForm()}
              {activeTab === 'surgical' && renderSurgicalForm()}
              {activeTab === 'readmission' && renderReadmissionForm()}
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

export default RiskAssessment;



