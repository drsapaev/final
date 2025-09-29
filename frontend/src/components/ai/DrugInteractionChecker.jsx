import React, { useState, useCallback } from 'react';
import { 
  Pill, 
  AlertTriangle, 
  Shield, 
  Calculator, 
  RefreshCw,
  Plus,
  Minus,
  CheckCircle,
  XCircle,
  AlertCircle,
  Info,
  Loader,
  Download,
  Search,
  User,
  Clock,
  Target,
  Zap
} from 'lucide-react';
import { toast } from 'react-toastify';
import api from '../../utils/api';

const DrugInteractionChecker = () => {
  const [activeTab, setActiveTab] = useState('interactions');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  // Состояния для разных форм
  const [interactionData, setInteractionData] = useState({
    medications: [
      { name: '', dosage: '', frequency: '' }
    ],
    patient_profile: {
      age: '',
      gender: '',
      weight: '',
      kidney_function: '',
      liver_function: '',
      allergies: []
    }
  });

  const [safetyData, setSafetyData] = useState({
    medication: { name: '', dosage: '', frequency: '' },
    patient_profile: {
      age: '',
      gender: '',
      weight: '',
      pregnancy_status: '',
      breastfeeding: '',
      kidney_function: '',
      liver_function: '',
      allergies: []
    },
    conditions: []
  });

  const [alternativesData, setAlternativesData] = useState({
    medication: '',
    reason: '',
    patient_profile: {
      age: '',
      gender: '',
      weight: '',
      kidney_function: '',
      liver_function: '',
      allergies: [],
      conditions: []
    }
  });

  const [dosageData, setDosageData] = useState({
    medication: '',
    indication: '',
    patient_profile: {
      age: '',
      gender: '',
      weight: '',
      height: '',
      creatinine: '',
      creatinine_clearance: '',
      liver_function: ''
    }
  });

  const tabs = [
    { id: 'interactions', label: 'Взаимодействия', icon: <AlertTriangle className="w-4 h-4" /> },
    { id: 'safety', label: 'Безопасность', icon: <Shield className="w-4 h-4" /> },
    { id: 'alternatives', label: 'Альтернативы', icon: <RefreshCw className="w-4 h-4" /> },
    { id: 'dosage', label: 'Дозировка', icon: <Calculator className="w-4 h-4" /> }
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

  const addMedication = () => {
    setInteractionData(prev => ({
      ...prev,
      medications: [...prev.medications, { name: '', dosage: '', frequency: '' }]
    }));
  };

  const removeMedication = (index) => {
    setInteractionData(prev => ({
      ...prev,
      medications: prev.medications.filter((_, i) => i !== index)
    }));
  };

  const updateMedication = (index, field, value) => {
    setInteractionData(prev => ({
      ...prev,
      medications: prev.medications.map((med, i) => 
        i === index ? { ...med, [field]: value } : med
      )
    }));
  };

  const exportResult = () => {
    if (!result) return;
    
    const dataStr = JSON.stringify(result, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `drug_analysis_${activeTab}_${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const getSeverityColor = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'критическое':
      case 'critical':
        return 'text-red-600 bg-red-50 border-red-200';
      case 'значительное':
      case 'major':
        return 'text-orange-600 bg-orange-50 border-orange-200';
      case 'умеренное':
      case 'moderate':
        return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'незначительное':
      case 'minor':
        return 'text-green-600 bg-green-50 border-green-200';
      default:
        return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const renderInteractionsForm = () => (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-lg font-medium text-gray-900">Препараты</h4>
          <button
            onClick={addMedication}
            className="inline-flex items-center px-3 py-1 border border-transparent text-sm font-medium rounded-md text-blue-700 bg-blue-100 hover:bg-blue-200"
          >
            <Plus className="w-4 h-4 mr-1" />
            Добавить препарат
          </button>
        </div>

        {interactionData.medications.map((medication, index) => (
          <div key={index} className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-3 p-3 border border-gray-200 rounded-lg">
            <input
              type="text"
              placeholder="Название препарата"
              value={medication.name}
              onChange={(e) => updateMedication(index, 'name', e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <input
              type="text"
              placeholder="Дозировка"
              value={medication.dosage}
              onChange={(e) => updateMedication(index, 'dosage', e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <input
              type="text"
              placeholder="Частота приема"
              value={medication.frequency}
              onChange={(e) => updateMedication(index, 'frequency', e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {interactionData.medications.length > 1 && (
              <button
                onClick={() => removeMedication(index)}
                className="inline-flex items-center justify-center px-3 py-2 border border-red-300 text-red-700 rounded-md hover:bg-red-50"
              >
                <Minus className="w-4 h-4" />
              </button>
            )}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Возраст</label>
          <input
            type="number"
            value={interactionData.patient_profile.age}
            onChange={(e) => setInteractionData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, age: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Пол</label>
          <select
            value={interactionData.patient_profile.gender}
            onChange={(e) => setInteractionData(prev => ({
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
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Вес (кг)</label>
          <input
            type="number"
            value={interactionData.patient_profile.weight}
            onChange={(e) => setInteractionData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, weight: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Функция почек</label>
          <select
            value={interactionData.patient_profile.kidney_function}
            onChange={(e) => setInteractionData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, kidney_function: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите</option>
            <option value="нормальная">Нормальная</option>
            <option value="легкое снижение">Легкое снижение</option>
            <option value="умеренное снижение">Умеренное снижение</option>
            <option value="тяжелое снижение">Тяжелое снижение</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Аллергии</label>
        <input
          type="text"
          value={interactionData.patient_profile.allergies.join(', ')}
          onChange={(e) => setInteractionData(prev => ({
            ...prev,
            patient_profile: { 
              ...prev.patient_profile, 
              allergies: e.target.value.split(',').map(item => item.trim()).filter(Boolean)
            }
          }))}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Например: пенициллин, аспирин"
        />
      </div>

      <button
        onClick={() => handleSubmit('check-drug-interactions', interactionData)}
        disabled={loading || interactionData.medications.length < 2 || !interactionData.medications[0].name}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
            Проверяем взаимодействия...
          </>
        ) : (
          <>
            <AlertTriangle className="h-5 w-5 mr-2" />
            Проверить взаимодействия
          </>
        )}
      </button>
    </div>
  );

  const renderSafetyForm = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Препарат</label>
          <input
            type="text"
            value={safetyData.medication.name}
            onChange={(e) => setSafetyData(prev => ({
              ...prev,
              medication: { ...prev.medication, name: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Название препарата"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Дозировка</label>
          <input
            type="text"
            value={safetyData.medication.dosage}
            onChange={(e) => setSafetyData(prev => ({
              ...prev,
              medication: { ...prev.medication, dosage: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Например: 10 мг"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Частота</label>
          <input
            type="text"
            value={safetyData.medication.frequency}
            onChange={(e) => setSafetyData(prev => ({
              ...prev,
              medication: { ...prev.medication, frequency: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Например: 2 раза в день"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Возраст</label>
          <input
            type="number"
            value={safetyData.patient_profile.age}
            onChange={(e) => setSafetyData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, age: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Пол</label>
          <select
            value={safetyData.patient_profile.gender}
            onChange={(e) => setSafetyData(prev => ({
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
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Беременность</label>
          <select
            value={safetyData.patient_profile.pregnancy_status}
            onChange={(e) => setSafetyData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, pregnancy_status: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите</option>
            <option value="не беременна">Не беременна</option>
            <option value="беременна">Беременна</option>
            <option value="планирует беременность">Планирует беременность</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Грудное вскармливание</label>
          <select
            value={safetyData.patient_profile.breastfeeding}
            onChange={(e) => setSafetyData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, breastfeeding: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Выберите</option>
            <option value="нет">Нет</option>
            <option value="да">Да</option>
          </select>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Заболевания</label>
        <input
          type="text"
          value={safetyData.conditions.join(', ')}
          onChange={(e) => setSafetyData(prev => ({
            ...prev,
            conditions: e.target.value.split(',').map(item => item.trim()).filter(Boolean)
          }))}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Например: гипертония, диабет"
        />
      </div>

      <button
        onClick={() => handleSubmit('analyze-drug-safety', safetyData)}
        disabled={loading || !safetyData.medication.name}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
            Анализируем безопасность...
          </>
        ) : (
          <>
            <Shield className="h-5 w-5 mr-2" />
            Проверить безопасность
          </>
        )}
      </button>
    </div>
  );

  const renderAlternativesForm = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Препарат для замены</label>
          <input
            type="text"
            value={alternativesData.medication}
            onChange={(e) => setAlternativesData(prev => ({
              ...prev,
              medication: e.target.value
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Название препарата"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Причина замены</label>
          <input
            type="text"
            value={alternativesData.reason}
            onChange={(e) => setAlternativesData(prev => ({
              ...prev,
              reason: e.target.value
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Например: побочные эффекты, аллергия"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Возраст</label>
          <input
            type="number"
            value={alternativesData.patient_profile.age}
            onChange={(e) => setAlternativesData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, age: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Пол</label>
          <select
            value={alternativesData.patient_profile.gender}
            onChange={(e) => setAlternativesData(prev => ({
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
        onClick={() => handleSubmit('suggest-drug-alternatives', alternativesData)}
        disabled={loading || !alternativesData.medication || !alternativesData.reason}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
            Ищем альтернативы...
          </>
        ) : (
          <>
            <RefreshCw className="h-5 w-5 mr-2" />
            Найти альтернативы
          </>
        )}
      </button>
    </div>
  );

  const renderDosageForm = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Препарат</label>
          <input
            type="text"
            value={dosageData.medication}
            onChange={(e) => setDosageData(prev => ({
              ...prev,
              medication: e.target.value
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Название препарата"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Показание</label>
          <input
            type="text"
            value={dosageData.indication}
            onChange={(e) => setDosageData(prev => ({
              ...prev,
              indication: e.target.value
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Диагноз или показание"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Возраст</label>
          <input
            type="number"
            value={dosageData.patient_profile.age}
            onChange={(e) => setDosageData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, age: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Вес (кг)</label>
          <input
            type="number"
            value={dosageData.patient_profile.weight}
            onChange={(e) => setDosageData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, weight: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Рост (см)</label>
          <input
            type="number"
            value={dosageData.patient_profile.height}
            onChange={(e) => setDosageData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, height: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Креатинин (мкмоль/л)</label>
          <input
            type="number"
            value={dosageData.patient_profile.creatinine}
            onChange={(e) => setDosageData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, creatinine: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Клиренс креатинина (мл/мин)</label>
          <input
            type="number"
            value={dosageData.patient_profile.creatinine_clearance}
            onChange={(e) => setDosageData(prev => ({
              ...prev,
              patient_profile: { ...prev.patient_profile, creatinine_clearance: e.target.value }
            }))}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      <button
        onClick={() => handleSubmit('calculate-drug-dosage', dosageData)}
        disabled={loading || !dosageData.medication || !dosageData.indication}
        className="w-full flex items-center justify-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-purple-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <>
            <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
            Рассчитываем дозировку...
          </>
        ) : (
          <>
            <Calculator className="h-5 w-5 mr-2" />
            Рассчитать дозировку
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

        {/* Специальное отображение для взаимодействий */}
        {activeTab === 'interactions' && result.interactions && (
          <div className="space-y-4">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="font-medium text-blue-900 mb-2">Сводка взаимодействий</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <span className="text-blue-600">Всего:</span>
                  <span className="ml-1 font-medium">{result.interaction_summary?.total_interactions || 0}</span>
                </div>
                <div>
                  <span className="text-red-600">Критические:</span>
                  <span className="ml-1 font-medium">{result.interaction_summary?.severity_distribution?.critical || 0}</span>
                </div>
                <div>
                  <span className="text-orange-600">Значительные:</span>
                  <span className="ml-1 font-medium">{result.interaction_summary?.severity_distribution?.major || 0}</span>
                </div>
                <div>
                  <span className="text-yellow-600">Умеренные:</span>
                  <span className="ml-1 font-medium">{result.interaction_summary?.severity_distribution?.moderate || 0}</span>
                </div>
              </div>
            </div>

            {result.interactions.map((interaction, index) => (
              <div key={index} className={`border rounded-lg p-4 ${getSeverityColor(interaction.severity)}`}>
                <div className="flex items-center justify-between mb-2">
                  <h5 className="font-medium">
                    {interaction.drug_1} ↔ {interaction.drug_2}
                  </h5>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSeverityColor(interaction.severity)}`}>
                    {interaction.severity}
                  </span>
                </div>
                <p className="text-sm mb-2">{interaction.clinical_effect}</p>
                <p className="text-sm font-medium">Управление: {interaction.management}</p>
              </div>
            ))}
          </div>
        )}

        {/* Общее отображение для других результатов */}
        {activeTab !== 'interactions' && (
          <div className="space-y-4">
            {Object.entries(result).map(([key, value]) => (
              <div key={key} className="border-l-4 border-blue-400 pl-4">
                <h4 className="font-medium text-gray-900 capitalize mb-2">
                  {key.replace(/_/g, ' ')}
                </h4>
                <div className="text-sm text-gray-600">
                  {typeof value === 'object' && value !== null ? (
                    <pre className="whitespace-pre-wrap bg-gray-50 p-2 rounded text-xs overflow-x-auto">
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
            <Pill className="h-6 w-6 text-blue-600 mr-2" />
            AI Проверка Лекарственных Взаимодействий
          </h2>
          <p className="mt-1 text-sm text-gray-600">
            Анализ безопасности препаратов, взаимодействий и расчет дозировок
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
              {activeTab === 'interactions' && renderInteractionsForm()}
              {activeTab === 'safety' && renderSafetyForm()}
              {activeTab === 'alternatives' && renderAlternativesForm()}
              {activeTab === 'dosage' && renderDosageForm()}
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

export default DrugInteractionChecker;



