import React, { useState } from 'react';
import { 
  TrendingUp, 
  AlertTriangle, 
  BarChart3, 
  PieChart,
  Activity,
  Target,
  Users,
  Calendar,
  FileText,
  Download,
  Copy,
  Plus,
  Minus,
  Loader,
  CheckCircle,
  XCircle,
  Info,
  Search,
  Filter,
  RefreshCw
} from 'lucide-react';
import { toast } from 'react-toastify';
import api from '../../utils/api';

const AnalyticsInsights = () => {
  const [activeTab, setActiveTab] = useState('trends');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Состояния для анализа трендов
  const [medicalData, setMedicalData] = useState([
    { id: '1', date: '2024-01-15', type: 'consultation', diagnosis: 'Гипертония', patient_age: 55, department: 'cardiology' },
    { id: '2', date: '2024-01-16', type: 'procedure', diagnosis: 'Диабет 2 типа', patient_age: 62, department: 'endocrinology' }
  ]);
  const [timePeriod, setTimePeriod] = useState('month');
  const [analysisType, setAnalysisType] = useState('disease_trends');

  // Состояния для выявления аномалий
  const [dataset, setDataset] = useState([
    { id: '1', value: 120, timestamp: '2024-01-15T10:00:00', type: 'blood_pressure', patient_id: 'P001' },
    { id: '2', value: 180, timestamp: '2024-01-15T11:00:00', type: 'blood_pressure', patient_id: 'P002' }
  ]);
  const [baselineData, setBaselineData] = useState({
    blood_pressure_normal: { systolic: 120, diastolic: 80 },
    temperature_normal: 36.6,
    heart_rate_normal: { min: 60, max: 100 },
    expected_patterns: { daily_visits: 50, seasonal_variation: 0.2 }
  });

  // Состояния для прогнозирования исходов
  const [patientData, setPatientData] = useState({
    age: 45,
    gender: 'male',
    diagnosis: 'Артериальная гипертензия',
    comorbidities: ['диабет 2 типа'],
    treatment_start_date: '2024-01-10',
    baseline_bp: '160/95',
    medications: ['каптоприл', 'метформин']
  });
  const [historicalOutcomes, setHistoricalOutcomes] = useState([
    { condition: 'гипертония', treatment: 'каптоприл', result: 'success', duration: '4 weeks', patient_age: 50 },
    { condition: 'гипертония', treatment: 'каптоприл', result: 'partial', duration: '8 weeks', patient_age: 60 }
  ]);

  // Состояния для генерации отчетов
  const [analyticsData, setAnalyticsData] = useState({
    period: 'Q1 2024',
    total_patients: 1250,
    departments: ['cardiology', 'endocrinology', 'neurology'],
    key_metrics: {
      patient_satisfaction: 4.2,
      average_wait_time: 25,
      treatment_success_rate: 0.85
    },
    trends: {
      patient_growth: 0.15,
      revenue_growth: 0.12,
      efficiency_improvement: 0.08
    }
  });
  const [reportType, setReportType] = useState('quarterly_performance');

  // Состояния для выявления паттернов рисков
  const [populationData, setPopulationData] = useState([
    { id: 'P001', age: 45, gender: 'male', conditions: ['hypertension'], lifestyle: 'sedentary', smoking: true },
    { id: 'P002', age: 62, gender: 'female', conditions: ['diabetes'], lifestyle: 'active', smoking: false }
  ]);
  const [riskFactors, setRiskFactors] = useState(['smoking', 'sedentary_lifestyle', 'obesity', 'family_history', 'age']);

  const tabs = [
    { id: 'trends', label: 'Анализ трендов', icon: <TrendingUp className="w-4 h-4" /> },
    { id: 'anomalies', label: 'Выявление аномалий', icon: <AlertTriangle className="w-4 h-4" /> },
    { id: 'outcomes', label: 'Прогноз исходов', icon: <Target className="w-4 h-4" /> },
    { id: 'reports', label: 'Отчеты инсайтов', icon: <FileText className="w-4 h-4" /> },
    { id: 'risk-patterns', label: 'Паттерны рисков', icon: <Users className="w-4 h-4" /> }
  ];

  const handleSubmit = async () => {
    setLoading(true);
    setResult(null);
    setError(null);

    let endpoint = '';
    let data = {};

    try {
      switch (activeTab) {
        case 'trends':
          endpoint = '/ai/analyze-medical-trends';
          data = {
            medical_data: medicalData,
            time_period: timePeriod,
            analysis_type: analysisType
          };
          break;
        case 'anomalies':
          endpoint = '/ai/detect-anomalies';
          data = {
            dataset: dataset,
            baseline_data: baselineData
          };
          break;
        case 'outcomes':
          endpoint = '/ai/predict-outcomes';
          data = {
            patient_data: patientData,
            historical_outcomes: historicalOutcomes
          };
          break;
        case 'reports':
          endpoint = '/ai/generate-insights-report';
          data = {
            analytics_data: analyticsData,
            report_type: reportType
          };
          break;
        case 'risk-patterns':
          endpoint = '/ai/identify-risk-patterns';
          data = {
            population_data: populationData,
            risk_factors: riskFactors
          };
          break;
        default:
          throw new Error('Неизвестный тип запроса');
      }

      const response = await api.post(endpoint, data);
      setResult(response.data);
      toast.success('AI аналитика успешно выполнена!');
    } catch (err) {
      toast.error('Ошибка при выполнении AI аналитики.');
      console.error('AI analytics error:', err);
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => {
      toast.success('Скопировано в буфер обмена');
    });
  };

  const exportResult = () => {
    if (!result) return;
    
    const dataStr = JSON.stringify(result, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `analytics_insights_${activeTab}_${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const addMedicalRecord = () => {
    setMedicalData(prev => [
      ...prev,
      { 
        id: Date.now().toString(), 
        date: new Date().toISOString().split('T')[0], 
        type: 'consultation', 
        diagnosis: '', 
        patient_age: 30, 
        department: 'general' 
      }
    ]);
  };

  const removeMedicalRecord = (index) => {
    setMedicalData(prev => prev.filter((_, i) => i !== index));
  };

  const addDatasetEntry = () => {
    setDataset(prev => [
      ...prev,
      { 
        id: Date.now().toString(), 
        value: 0, 
        timestamp: new Date().toISOString(), 
        type: 'measurement', 
        patient_id: '' 
      }
    ]);
  };

  const removeDatasetEntry = (index) => {
    setDataset(prev => prev.filter((_, i) => i !== index));
  };

  const addHistoricalOutcome = () => {
    setHistoricalOutcomes(prev => [
      ...prev,
      { condition: '', treatment: '', result: 'success', duration: '', patient_age: 30 }
    ]);
  };

  const removeHistoricalOutcome = (index) => {
    setHistoricalOutcomes(prev => prev.filter((_, i) => i !== index));
  };

  const addPopulationEntry = () => {
    setPopulationData(prev => [
      ...prev,
      { 
        id: `P${Date.now()}`, 
        age: 30, 
        gender: 'male', 
        conditions: [], 
        lifestyle: 'active', 
        smoking: false 
      }
    ]);
  };

  const removePopulationEntry = (index) => {
    setPopulationData(prev => prev.filter((_, i) => i !== index));
  };

  const addRiskFactor = () => {
    setRiskFactors(prev => [...prev, '']);
  };

  const removeRiskFactor = (index) => {
    setRiskFactors(prev => prev.filter((_, i) => i !== index));
  };

  const renderTrendsAnalysis = () => (
    <div className="space-y-6">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-blue-900 flex items-center">
            <BarChart3 className="w-4 h-4 mr-2" />
            Медицинские данные для анализа
          </h4>
          <button
            onClick={addMedicalRecord}
            className="px-3 py-1 bg-blue-600 text-white rounded-md text-sm hover:bg-blue-700 flex items-center"
          >
            <Plus className="w-4 h-4 mr-1" />
            Добавить запись
          </button>
        </div>
        <div className="space-y-3 max-h-40 overflow-y-auto">
          {medicalData.map((record, index) => (
            <div key={record.id} className="grid grid-cols-6 gap-2 items-center">
              <input
                type="date"
                value={record.date}
                onChange={(e) => {
                  const newData = [...medicalData];
                  newData[index].date = e.target.value;
                  setMedicalData(newData);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
              />
              <select
                value={record.type}
                onChange={(e) => {
                  const newData = [...medicalData];
                  newData[index].type = e.target.value;
                  setMedicalData(newData);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
              >
                <option value="consultation">Консультация</option>
                <option value="procedure">Процедура</option>
                <option value="surgery">Операция</option>
                <option value="emergency">Неотложка</option>
              </select>
              <input
                type="text"
                value={record.diagnosis}
                onChange={(e) => {
                  const newData = [...medicalData];
                  newData[index].diagnosis = e.target.value;
                  setMedicalData(newData);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Диагноз"
              />
              <input
                type="number"
                value={record.patient_age}
                onChange={(e) => {
                  const newData = [...medicalData];
                  newData[index].patient_age = parseInt(e.target.value) || 0;
                  setMedicalData(newData);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Возраст"
              />
              <select
                value={record.department}
                onChange={(e) => {
                  const newData = [...medicalData];
                  newData[index].department = e.target.value;
                  setMedicalData(newData);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
              >
                <option value="general">Общий</option>
                <option value="cardiology">Кардиология</option>
                <option value="endocrinology">Эндокринология</option>
                <option value="neurology">Неврология</option>
                <option value="surgery">Хирургия</option>
              </select>
              <button
                onClick={() => removeMedicalRecord(index)}
                className="p-1 text-red-600 hover:text-red-800"
              >
                <Minus className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <h4 className="font-medium text-green-900 mb-3 flex items-center">
            <Calendar className="w-4 h-4 mr-2" />
            Параметры анализа
          </h4>
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Временной период</label>
              <select
                value={timePeriod}
                onChange={(e) => setTimePeriod(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="day">День</option>
                <option value="week">Неделя</option>
                <option value="month">Месяц</option>
                <option value="quarter">Квартал</option>
                <option value="year">Год</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Тип анализа</label>
              <select
                value={analysisType}
                onChange={(e) => setAnalysisType(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="disease_trends">Тренды заболеваний</option>
                <option value="patient_flow">Поток пациентов</option>
                <option value="resource_utilization">Использование ресурсов</option>
                <option value="treatment_effectiveness">Эффективность лечения</option>
                <option value="seasonal_patterns">Сезонные паттерны</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderAnomalyDetection = () => (
    <div className="space-y-6">
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-yellow-900 flex items-center">
            <Activity className="w-4 h-4 mr-2" />
            Данные для анализа аномалий
          </h4>
          <button
            onClick={addDatasetEntry}
            className="px-3 py-1 bg-yellow-600 text-white rounded-md text-sm hover:bg-yellow-700 flex items-center"
          >
            <Plus className="w-4 h-4 mr-1" />
            Добавить запись
          </button>
        </div>
        <div className="space-y-3 max-h-40 overflow-y-auto">
          {dataset.map((entry, index) => (
            <div key={entry.id} className="grid grid-cols-5 gap-2 items-center">
              <input
                type="number"
                value={entry.value}
                onChange={(e) => {
                  const newDataset = [...dataset];
                  newDataset[index].value = parseFloat(e.target.value) || 0;
                  setDataset(newDataset);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Значение"
              />
              <input
                type="datetime-local"
                value={entry.timestamp.slice(0, 16)}
                onChange={(e) => {
                  const newDataset = [...dataset];
                  newDataset[index].timestamp = e.target.value + ':00';
                  setDataset(newDataset);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
              />
              <select
                value={entry.type}
                onChange={(e) => {
                  const newDataset = [...dataset];
                  newDataset[index].type = e.target.value;
                  setDataset(newDataset);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
              >
                <option value="blood_pressure">АД</option>
                <option value="temperature">Температура</option>
                <option value="heart_rate">ЧСС</option>
                <option value="glucose">Глюкоза</option>
                <option value="weight">Вес</option>
              </select>
              <input
                type="text"
                value={entry.patient_id}
                onChange={(e) => {
                  const newDataset = [...dataset];
                  newDataset[index].patient_id = e.target.value;
                  setDataset(newDataset);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="ID пациента"
              />
              <button
                onClick={() => removeDatasetEntry(index)}
                className="p-1 text-red-600 hover:text-red-800"
              >
                <Minus className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <h4 className="font-medium text-purple-900 mb-3 flex items-center">
          <Target className="w-4 h-4 mr-2" />
          Базовые показатели
        </h4>
        <div className="space-y-3">
          <textarea
            value={JSON.stringify(baselineData, null, 2)}
            onChange={(e) => {
              try {
                setBaselineData(JSON.parse(e.target.value));
              } catch (error) {
                // Игнорируем ошибки парсинга во время ввода
              }
            }}
            className="w-full h-32 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
            placeholder="JSON с базовыми показателями"
          />
        </div>
      </div>
    </div>
  );

  const renderOutcomePrediction = () => (
    <div className="space-y-6">
      <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
        <h4 className="font-medium text-indigo-900 mb-3 flex items-center">
          <Users className="w-4 h-4 mr-2" />
          Данные пациента
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Возраст</label>
            <input
              type="number"
              value={patientData.age}
              onChange={(e) => setPatientData(prev => ({ ...prev, age: parseInt(e.target.value) || 0 }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Пол</label>
            <select
              value={patientData.gender}
              onChange={(e) => setPatientData(prev => ({ ...prev, gender: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="male">Мужской</option>
              <option value="female">Женский</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Диагноз</label>
            <input
              type="text"
              value={patientData.diagnosis}
              onChange={(e) => setPatientData(prev => ({ ...prev, diagnosis: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Дата начала лечения</label>
            <input
              type="date"
              value={patientData.treatment_start_date}
              onChange={(e) => setPatientData(prev => ({ ...prev, treatment_start_date: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      <div className="bg-teal-50 border border-teal-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-teal-900 flex items-center">
            <BarChart3 className="w-4 h-4 mr-2" />
            Исторические исходы
          </h4>
          <button
            onClick={addHistoricalOutcome}
            className="px-3 py-1 bg-teal-600 text-white rounded-md text-sm hover:bg-teal-700 flex items-center"
          >
            <Plus className="w-4 h-4 mr-1" />
            Добавить исход
          </button>
        </div>
        <div className="space-y-3 max-h-40 overflow-y-auto">
          {historicalOutcomes.map((outcome, index) => (
            <div key={index} className="grid grid-cols-6 gap-2 items-center">
              <input
                type="text"
                value={outcome.condition}
                onChange={(e) => {
                  const newOutcomes = [...historicalOutcomes];
                  newOutcomes[index].condition = e.target.value;
                  setHistoricalOutcomes(newOutcomes);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Состояние"
              />
              <input
                type="text"
                value={outcome.treatment}
                onChange={(e) => {
                  const newOutcomes = [...historicalOutcomes];
                  newOutcomes[index].treatment = e.target.value;
                  setHistoricalOutcomes(newOutcomes);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Лечение"
              />
              <select
                value={outcome.result}
                onChange={(e) => {
                  const newOutcomes = [...historicalOutcomes];
                  newOutcomes[index].result = e.target.value;
                  setHistoricalOutcomes(newOutcomes);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
              >
                <option value="success">Успех</option>
                <option value="partial">Частичный</option>
                <option value="failure">Неудача</option>
                <option value="ongoing">Продолжается</option>
              </select>
              <input
                type="text"
                value={outcome.duration}
                onChange={(e) => {
                  const newOutcomes = [...historicalOutcomes];
                  newOutcomes[index].duration = e.target.value;
                  setHistoricalOutcomes(newOutcomes);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Длительность"
              />
              <input
                type="number"
                value={outcome.patient_age}
                onChange={(e) => {
                  const newOutcomes = [...historicalOutcomes];
                  newOutcomes[index].patient_age = parseInt(e.target.value) || 0;
                  setHistoricalOutcomes(newOutcomes);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Возраст"
              />
              <button
                onClick={() => removeHistoricalOutcome(index)}
                className="p-1 text-red-600 hover:text-red-800"
              >
                <Minus className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const renderInsightsReport = () => (
    <div className="space-y-6">
      <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
        <h4 className="font-medium text-orange-900 mb-3 flex items-center">
          <FileText className="w-4 h-4 mr-2" />
          Параметры отчета
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Тип отчета</label>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="quarterly_performance">Квартальная производительность</option>
              <option value="annual_review">Годовой обзор</option>
              <option value="department_analysis">Анализ отделений</option>
              <option value="patient_satisfaction">Удовлетворенность пациентов</option>
              <option value="financial_overview">Финансовый обзор</option>
              <option value="quality_metrics">Метрики качества</option>
            </select>
          </div>
        </div>
      </div>

      <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-4">
        <h4 className="font-medium text-cyan-900 mb-3 flex items-center">
          <PieChart className="w-4 h-4 mr-2" />
          Аналитические данные
        </h4>
        <div className="space-y-3">
          <textarea
            value={JSON.stringify(analyticsData, null, 2)}
            onChange={(e) => {
              try {
                setAnalyticsData(JSON.parse(e.target.value));
              } catch (error) {
                // Игнорируем ошибки парсинга во время ввода
              }
            }}
            className="w-full h-40 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
            placeholder="JSON с аналитическими данными"
          />
        </div>
      </div>
    </div>
  );

  const renderRiskPatterns = () => (
    <div className="space-y-6">
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-red-900 flex items-center">
            <Users className="w-4 h-4 mr-2" />
            Популяционные данные
          </h4>
          <button
            onClick={addPopulationEntry}
            className="px-3 py-1 bg-red-600 text-white rounded-md text-sm hover:bg-red-700 flex items-center"
          >
            <Plus className="w-4 h-4 mr-1" />
            Добавить пациента
          </button>
        </div>
        <div className="space-y-3 max-h-40 overflow-y-auto">
          {populationData.map((patient, index) => (
            <div key={patient.id} className="grid grid-cols-6 gap-2 items-center">
              <input
                type="text"
                value={patient.id}
                onChange={(e) => {
                  const newData = [...populationData];
                  newData[index].id = e.target.value;
                  setPopulationData(newData);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="ID"
              />
              <input
                type="number"
                value={patient.age}
                onChange={(e) => {
                  const newData = [...populationData];
                  newData[index].age = parseInt(e.target.value) || 0;
                  setPopulationData(newData);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Возраст"
              />
              <select
                value={patient.gender}
                onChange={(e) => {
                  const newData = [...populationData];
                  newData[index].gender = e.target.value;
                  setPopulationData(newData);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
              >
                <option value="male">М</option>
                <option value="female">Ж</option>
              </select>
              <input
                type="text"
                value={patient.conditions.join(', ')}
                onChange={(e) => {
                  const newData = [...populationData];
                  newData[index].conditions = e.target.value.split(',').map(c => c.trim()).filter(c => c);
                  setPopulationData(newData);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Заболевания"
              />
              <select
                value={patient.lifestyle}
                onChange={(e) => {
                  const newData = [...populationData];
                  newData[index].lifestyle = e.target.value;
                  setPopulationData(newData);
                }}
                className="px-2 py-1 border border-gray-300 rounded text-sm"
              >
                <option value="active">Активный</option>
                <option value="sedentary">Малоподвижный</option>
                <option value="moderate">Умеренный</option>
              </select>
              <button
                onClick={() => removePopulationEntry(index)}
                className="p-1 text-red-600 hover:text-red-800"
              >
                <Minus className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-pink-50 border border-pink-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-pink-900 flex items-center">
            <AlertTriangle className="w-4 h-4 mr-2" />
            Факторы риска
          </h4>
          <button
            onClick={addRiskFactor}
            className="px-3 py-1 bg-pink-600 text-white rounded-md text-sm hover:bg-pink-700 flex items-center"
          >
            <Plus className="w-4 h-4 mr-1" />
            Добавить фактор
          </button>
        </div>
        <div className="space-y-2 max-h-32 overflow-y-auto">
          {riskFactors.map((factor, index) => (
            <div key={index} className="flex space-x-2 items-center">
              <input
                type="text"
                value={factor}
                onChange={(e) => {
                  const newFactors = [...riskFactors];
                  newFactors[index] = e.target.value;
                  setRiskFactors(newFactors);
                }}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Фактор риска"
              />
              <button
                onClick={() => removeRiskFactor(index)}
                className="p-1 text-red-600 hover:text-red-800"
              >
                <Minus className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      </div>
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
            Результаты аналитики
          </h3>
          <div className="flex space-x-2">
            <button
              onClick={() => copyToClipboard(JSON.stringify(result, null, 2))}
              className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              <Copy className="h-4 w-4 mr-1" />
              Копировать
            </button>
            <button
              onClick={exportResult}
              className="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              <Download className="h-4 w-4 mr-1" />
              Экспорт
            </button>
          </div>
        </div>

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
      </div>
    );
  };

  return (
    <div className="max-w-7xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-lg">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900 flex items-center">
            <TrendingUp className="h-6 w-6 text-blue-600 mr-2" />
            AI Аналитические Инсайты
          </h2>
          <p className="mt-1 text-sm text-gray-600">
            Выявление трендов, аномалий и паттернов в медицинских данных
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
                Настройки и данные
              </h3>
              
              {activeTab === 'trends' && renderTrendsAnalysis()}
              {activeTab === 'anomalies' && renderAnomalyDetection()}
              {activeTab === 'outcomes' && renderOutcomePrediction()}
              {activeTab === 'reports' && renderInsightsReport()}
              {activeTab === 'risk-patterns' && renderRiskPatterns()}
              
              <div className="mt-6 flex justify-center">
                <button
                  onClick={handleSubmit}
                  disabled={loading}
                  className="flex items-center px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <>
                      <Loader className="animate-spin -ml-1 mr-3 h-5 w-5" />
                      Анализируем...
                    </>
                  ) : (
                    <>
                      <TrendingUp className="h-5 w-5 mr-2" />
                      Запустить AI анализ
                    </>
                  )}
                </button>
              </div>
            </div>

            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">Результат</h3>
              {renderResult()}
              
              {error && (
                <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
                  <div className="flex items-center">
                    <AlertTriangle className="h-5 w-5 text-red-400 mr-2" />
                    <h3 className="text-sm font-medium text-red-800">Ошибка</h3>
                  </div>
                  <p className="mt-2 text-sm text-red-700">{error}</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AnalyticsInsights;



