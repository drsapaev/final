import React, { useState } from 'react';
import { 
  MacOSCard,
  MacOSButton,
  MacOSInput,
  MacOSSelect,
  MacOSTextarea,
  MacOSBadge,
  MacOSLoadingSkeleton
} from '../ui/macos';
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
import { api } from '../../utils/api';

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
    { id: 'trends', label: 'Анализ трендов', icon: TrendingUp },
    { id: 'anomalies', label: 'Выявление аномалий', icon: AlertTriangle },
    { id: 'outcomes', label: 'Прогноз исходов', icon: Target },
    { id: 'reports', label: 'Отчеты инсайтов', icon: FileText },
    { id: 'risk-patterns', label: 'Паттерны рисков', icon: Users }
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-bg-primary)', 
        border: '1px solid var(--mac-border)' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-text-primary)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <BarChart3 style={{ width: '16px', height: '16px' }} />
            Медицинские данные для анализа
          </h4>
          <MacOSButton
            onClick={addMedicalRecord}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить запись
          </MacOSButton>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '160px', overflowY: 'auto' }}>
          {medicalData.map((record, index) => (
            <div key={record.id} style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(6, 1fr)', 
              gap: '8px', 
              alignItems: 'center' 
            }}>
              <MacOSInput
                type="date"
                value={record.date}
                onChange={(e) => {
                  const newData = [...medicalData];
                  newData[index].date = e.target.value;
                  setMedicalData(newData);
                }}
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSSelect
                value={record.type}
                onChange={(e) => {
                  const newData = [...medicalData];
                  newData[index].type = e.target.value;
                  setMedicalData(newData);
                }}
                options={[
                  { value: 'consultation', label: 'Консультация' },
                  { value: 'procedure', label: 'Процедура' },
                  { value: 'surgery', label: 'Операция' },
                  { value: 'emergency', label: 'Неотложка' }
                ]}
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="text"
                value={record.diagnosis}
                onChange={(e) => {
                  const newData = [...medicalData];
                  newData[index].diagnosis = e.target.value;
                  setMedicalData(newData);
                }}
                placeholder="Диагноз"
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="number"
                value={record.patient_age}
                onChange={(e) => {
                  const newData = [...medicalData];
                  newData[index].patient_age = parseInt(e.target.value) || 0;
                  setMedicalData(newData);
                }}
                placeholder="Возраст"
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSSelect
                value={record.department}
                onChange={(e) => {
                  const newData = [...medicalData];
                  newData[index].department = e.target.value;
                  setMedicalData(newData);
                }}
                options={[
                  { value: 'general', label: 'Общий' },
                  { value: 'cardiology', label: 'Кардиология' },
                  { value: 'endocrinology', label: 'Эндокринология' },
                  { value: 'neurology', label: 'Неврология' },
                  { value: 'surgery', label: 'Хирургия' }
                ]}
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSButton
                onClick={() => removeMedicalRecord(index)}
                variant="outline"
                style={{ padding: '4px', minWidth: 'auto' }}
              >
                <Minus style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
              </MacOSButton>
            </div>
          ))}
        </div>
      </MacOSCard>

      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
        gap: '16px' 
      }}>
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-bg-primary)', 
          border: '1px solid var(--mac-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-success)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Calendar style={{ width: '16px', height: '16px' }} />
            Параметры анализа
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '4px' 
              }}>
                Временной период
              </label>
              <MacOSSelect
                value={timePeriod}
                onChange={(e) => setTimePeriod(e.target.value)}
                options={[
                  { value: 'day', label: 'День' },
                  { value: 'week', label: 'Неделя' },
                  { value: 'month', label: 'Месяц' },
                  { value: 'quarter', label: 'Квартал' },
                  { value: 'year', label: 'Год' }
                ]}
                style={{ width: '100%' }}
              />
            </div>
            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '4px' 
              }}>
                Тип анализа
              </label>
              <MacOSSelect
                value={analysisType}
                onChange={(e) => setAnalysisType(e.target.value)}
                options={[
                  { value: 'disease_trends', label: 'Тренды заболеваний' },
                  { value: 'patient_flow', label: 'Поток пациентов' },
                  { value: 'resource_utilization', label: 'Использование ресурсов' },
                  { value: 'treatment_effectiveness', label: 'Эффективность лечения' },
                  { value: 'seasonal_patterns', label: 'Сезонные паттерны' }
                ]}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </MacOSCard>
      </div>
    </div>
  );

  const renderAnomalyDetection = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-bg-primary)', 
        border: '1px solid var(--mac-border)' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-warning)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Activity style={{ width: '16px', height: '16px' }} />
            Данные для анализа аномалий
          </h4>
          <MacOSButton
            onClick={addDatasetEntry}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить запись
          </MacOSButton>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '160px', overflowY: 'auto' }}>
          {dataset.map((entry, index) => (
            <div key={entry.id} style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(5, 1fr)', 
              gap: '8px', 
              alignItems: 'center' 
            }}>
              <MacOSInput
                type="number"
                value={entry.value}
                onChange={(e) => {
                  const newDataset = [...dataset];
                  newDataset[index].value = parseFloat(e.target.value) || 0;
                  setDataset(newDataset);
                }}
                placeholder="Значение"
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="datetime-local"
                value={entry.timestamp.slice(0, 16)}
                onChange={(e) => {
                  const newDataset = [...dataset];
                  newDataset[index].timestamp = e.target.value + ':00';
                  setDataset(newDataset);
                }}
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSSelect
                value={entry.type}
                onChange={(e) => {
                  const newDataset = [...dataset];
                  newDataset[index].type = e.target.value;
                  setDataset(newDataset);
                }}
                options={[
                  { value: 'blood_pressure', label: 'АД' },
                  { value: 'temperature', label: 'Температура' },
                  { value: 'heart_rate', label: 'ЧСС' },
                  { value: 'glucose', label: 'Глюкоза' },
                  { value: 'weight', label: 'Вес' }
                ]}
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="text"
                value={entry.patient_id}
                onChange={(e) => {
                  const newDataset = [...dataset];
                  newDataset[index].patient_id = e.target.value;
                  setDataset(newDataset);
                }}
                placeholder="ID пациента"
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSButton
                onClick={() => removeDatasetEntry(index)}
                variant="outline"
                style={{ padding: '4px', minWidth: 'auto' }}
              >
                <Minus style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
              </MacOSButton>
            </div>
          ))}
        </div>
      </MacOSCard>

      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-accent-bg)', 
        border: '1px solid var(--mac-accent-border)' 
      }}>
        <h4 style={{ 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-accent)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Target style={{ width: '16px', height: '16px' }} />
          Базовые показатели
        </h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <MacOSTextarea
            value={JSON.stringify(baselineData, null, 2)}
            onChange={(e) => {
              try {
                setBaselineData(JSON.parse(e.target.value));
              } catch (error) {
                // Игнорируем ошибки парсинга во время ввода
              }
            }}
            placeholder="JSON с базовыми показателями"
            style={{ 
              width: '100%', 
              height: '128px',
              fontFamily: 'var(--mac-font-mono)',
              fontSize: 'var(--mac-font-size-xs)'
            }}
          />
        </div>
      </MacOSCard>
    </div>
  );

  const renderOutcomePrediction = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-accent-bg)', 
        border: '1px solid var(--mac-accent-border)' 
      }}>
        <h4 style={{ 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-accent)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <Users style={{ width: '16px', height: '16px' }} />
          Данные пациента
        </h4>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: '16px' 
        }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Возраст
            </label>
            <MacOSInput
              type="number"
              value={patientData.age}
              onChange={(e) => setPatientData(prev => ({ ...prev, age: parseInt(e.target.value) || 0 }))}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Пол
            </label>
            <MacOSSelect
              value={patientData.gender}
              onChange={(e) => setPatientData(prev => ({ ...prev, gender: e.target.value }))}
              options={[
                { value: 'male', label: 'Мужской' },
                { value: 'female', label: 'Женский' }
              ]}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Диагноз
            </label>
            <MacOSInput
              type="text"
              value={patientData.diagnosis}
              onChange={(e) => setPatientData(prev => ({ ...prev, diagnosis: e.target.value }))}
              style={{ width: '100%' }}
            />
          </div>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Дата начала лечения
            </label>
            <MacOSInput
              type="date"
              value={patientData.treatment_start_date}
              onChange={(e) => setPatientData(prev => ({ ...prev, treatment_start_date: e.target.value }))}
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-bg-primary)', 
        border: '1px solid var(--mac-border)' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-success)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <BarChart3 style={{ width: '16px', height: '16px' }} />
            Исторические исходы
          </h4>
          <MacOSButton
            onClick={addHistoricalOutcome}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить исход
          </MacOSButton>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '160px', overflowY: 'auto' }}>
          {historicalOutcomes.map((outcome, index) => (
            <div key={index} style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(6, 1fr)', 
              gap: '8px', 
              alignItems: 'center' 
            }}>
              <MacOSInput
                type="text"
                value={outcome.condition}
                onChange={(e) => {
                  const newOutcomes = [...historicalOutcomes];
                  newOutcomes[index].condition = e.target.value;
                  setHistoricalOutcomes(newOutcomes);
                }}
                placeholder="Состояние"
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="text"
                value={outcome.treatment}
                onChange={(e) => {
                  const newOutcomes = [...historicalOutcomes];
                  newOutcomes[index].treatment = e.target.value;
                  setHistoricalOutcomes(newOutcomes);
                }}
                placeholder="Лечение"
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSSelect
                value={outcome.result}
                onChange={(e) => {
                  const newOutcomes = [...historicalOutcomes];
                  newOutcomes[index].result = e.target.value;
                  setHistoricalOutcomes(newOutcomes);
                }}
                options={[
                  { value: 'success', label: 'Успех' },
                  { value: 'partial', label: 'Частичный' },
                  { value: 'failure', label: 'Неудача' },
                  { value: 'ongoing', label: 'Продолжается' }
                ]}
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="text"
                value={outcome.duration}
                onChange={(e) => {
                  const newOutcomes = [...historicalOutcomes];
                  newOutcomes[index].duration = e.target.value;
                  setHistoricalOutcomes(newOutcomes);
                }}
                placeholder="Длительность"
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="number"
                value={outcome.patient_age}
                onChange={(e) => {
                  const newOutcomes = [...historicalOutcomes];
                  newOutcomes[index].patient_age = parseInt(e.target.value) || 0;
                  setHistoricalOutcomes(newOutcomes);
                }}
                placeholder="Возраст"
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSButton
                onClick={() => removeHistoricalOutcome(index)}
                variant="outline"
                style={{ padding: '4px', minWidth: 'auto' }}
              >
                <Minus style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
              </MacOSButton>
            </div>
          ))}
        </div>
      </MacOSCard>
    </div>
  );

  const renderInsightsReport = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-bg-primary)', 
        border: '1px solid var(--mac-border)' 
      }}>
        <h4 style={{ 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-warning)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <FileText style={{ width: '16px', height: '16px' }} />
          Параметры отчета
        </h4>
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
          gap: '16px' 
        }}>
          <div>
            <label style={{ 
              display: 'block', 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)', 
              marginBottom: '4px' 
            }}>
              Тип отчета
            </label>
            <MacOSSelect
              value={reportType}
              onChange={(e) => setReportType(e.target.value)}
              options={[
                { value: 'quarterly_performance', label: 'Квартальная производительность' },
                { value: 'annual_review', label: 'Годовой обзор' },
                { value: 'department_analysis', label: 'Анализ отделений' },
                { value: 'patient_satisfaction', label: 'Удовлетворенность пациентов' },
                { value: 'financial_overview', label: 'Финансовый обзор' },
                { value: 'quality_metrics', label: 'Метрики качества' }
              ]}
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-bg-primary)', 
        border: '1px solid var(--mac-border)' 
      }}>
        <h4 style={{ 
          fontWeight: 'var(--mac-font-weight-medium)', 
          color: 'var(--mac-text-primary)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <PieChart style={{ width: '16px', height: '16px' }} />
          Аналитические данные
        </h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <MacOSTextarea
            value={JSON.stringify(analyticsData, null, 2)}
            onChange={(e) => {
              try {
                setAnalyticsData(JSON.parse(e.target.value));
              } catch (error) {
                // Игнорируем ошибки парсинга во время ввода
              }
            }}
            placeholder="JSON с аналитическими данными"
            style={{ 
              width: '100%', 
              height: '160px',
              fontFamily: 'var(--mac-font-mono)',
              fontSize: 'var(--mac-font-size-xs)'
            }}
          />
        </div>
      </MacOSCard>
    </div>
  );

  const renderRiskPatterns = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-bg-primary)', 
        border: '1px solid var(--mac-border)' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-danger)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Users style={{ width: '16px', height: '16px' }} />
            Популяционные данные
          </h4>
          <MacOSButton
            onClick={addPopulationEntry}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить пациента
          </MacOSButton>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '160px', overflowY: 'auto' }}>
          {populationData.map((patient, index) => (
            <div key={patient.id} style={{ 
              display: 'grid', 
              gridTemplateColumns: 'repeat(6, 1fr)', 
              gap: '8px', 
              alignItems: 'center' 
            }}>
              <MacOSInput
                type="text"
                value={patient.id}
                onChange={(e) => {
                  const newData = [...populationData];
                  newData[index].id = e.target.value;
                  setPopulationData(newData);
                }}
                placeholder="ID"
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="number"
                value={patient.age}
                onChange={(e) => {
                  const newData = [...populationData];
                  newData[index].age = parseInt(e.target.value) || 0;
                  setPopulationData(newData);
                }}
                placeholder="Возраст"
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSSelect
                value={patient.gender}
                onChange={(e) => {
                  const newData = [...populationData];
                  newData[index].gender = e.target.value;
                  setPopulationData(newData);
                }}
                options={[
                  { value: 'male', label: 'М' },
                  { value: 'female', label: 'Ж' }
                ]}
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSInput
                type="text"
                value={patient.conditions.join(', ')}
                onChange={(e) => {
                  const newData = [...populationData];
                  newData[index].conditions = e.target.value.split(',').map(c => c.trim()).filter(c => c);
                  setPopulationData(newData);
                }}
                placeholder="Заболевания"
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSSelect
                value={patient.lifestyle}
                onChange={(e) => {
                  const newData = [...populationData];
                  newData[index].lifestyle = e.target.value;
                  setPopulationData(newData);
                }}
                options={[
                  { value: 'active', label: 'Активный' },
                  { value: 'sedentary', label: 'Малоподвижный' },
                  { value: 'moderate', label: 'Умеренный' }
                ]}
                style={{ fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSButton
                onClick={() => removePopulationEntry(index)}
                variant="outline"
                style={{ padding: '4px', minWidth: 'auto' }}
              >
                <Minus style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
              </MacOSButton>
            </div>
          ))}
        </div>
      </MacOSCard>

      <MacOSCard style={{ 
        padding: '16px', 
        backgroundColor: 'var(--mac-bg-primary)', 
        border: '1px solid var(--mac-border)' 
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-warning)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <AlertTriangle style={{ width: '16px', height: '16px' }} />
            Факторы риска
          </h4>
          <MacOSButton
            onClick={addRiskFactor}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить фактор
          </MacOSButton>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '128px', overflowY: 'auto' }}>
          {riskFactors.map((factor, index) => (
            <div key={index} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <MacOSInput
                type="text"
                value={factor}
                onChange={(e) => {
                  const newFactors = [...riskFactors];
                  newFactors[index] = e.target.value;
                  setRiskFactors(newFactors);
                }}
                placeholder="Фактор риска"
                style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }}
              />
              <MacOSButton
                onClick={() => removeRiskFactor(index)}
                variant="outline"
                style={{ padding: '4px', minWidth: 'auto' }}
              >
                <Minus style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
              </MacOSButton>
            </div>
          ))}
        </div>
      </MacOSCard>
    </div>
  );

  const renderResult = () => {
    if (!result) return null;

    if (result.error) {
      return (
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-bg-primary)', 
          border: '1px solid var(--mac-border)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <XCircle style={{ width: '20px', height: '20px', color: 'var(--mac-danger)' }} />
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-danger)',
              margin: 0
            }}>
              Ошибка
            </h3>
          </div>
          <p style={{ 
            marginTop: '8px',
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-danger)',
            margin: '8px 0 0 0'
          }}>
            {result.error}
          </p>
        </MacOSCard>
      );
    }

    return (
      <MacOSCard style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3 style={{ 
            fontSize: 'var(--mac-font-size-lg)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <CheckCircle style={{ width: '20px', height: '20px', color: 'var(--mac-success)' }} />
            Результаты аналитики
          </h3>
          <div style={{ display: 'flex', gap: '8px' }}>
            <MacOSButton
              onClick={() => copyToClipboard(JSON.stringify(result, null, 2))}
              variant="outline"
              style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <Copy style={{ width: '16px', height: '16px' }} />
              Копировать
            </MacOSButton>
            <MacOSButton
              onClick={exportResult}
              variant="outline"
              style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
            >
              <Download style={{ width: '16px', height: '16px' }} />
              Экспорт
            </MacOSButton>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {Object.entries(result).map(([key, value]) => (
            <div key={key} style={{ 
              borderLeft: '4px solid var(--mac-accent)', 
              paddingLeft: '16px' 
            }}>
              <h4 style={{ 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)',
                margin: '0 0 8px 0',
                fontSize: 'var(--mac-font-size-sm)',
                textTransform: 'capitalize'
              }}>
                {key.replace(/_/g, ' ')}
              </h4>
              <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-primary)' }}>
                {typeof value === 'object' && value !== null ? (
                  <pre style={{ 
                    whiteSpace: 'pre-wrap', 
                    backgroundColor: 'var(--mac-bg-primary)', 
                    border: '1px solid var(--mac-border)',
                    padding: '8px', 
                    borderRadius: 'var(--mac-radius-sm)', 
                    fontSize: 'var(--mac-font-size-xs)', 
                    overflowX: 'auto', 
                    maxHeight: '256px',
                    margin: 0,
                    fontFamily: 'var(--mac-font-mono)'
                  }}>
                    {JSON.stringify(value, null, 2)}
                  </pre>
                ) : (
                  <p style={{ margin: 0 }}>{String(value)}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </MacOSCard>
    );
  };

  return (
    <div style={{ 
      padding: '24px',
      backgroundColor: 'var(--mac-bg-primary)',
      minHeight: '100vh'
    }}>
      <MacOSCard style={{ padding: '24px' }}>
        {/* Заголовок */}
        <div style={{ 
          paddingBottom: '24px', 
          borderBottom: '1px solid var(--mac-border)',
          marginBottom: '24px'
        }}>
          <h2 style={{ 
            fontSize: 'var(--mac-font-size-2xl)', 
            fontWeight: 'var(--mac-font-weight-semibold)', 
            color: 'var(--mac-text-primary)',
            margin: '0 0 8px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            <TrendingUp style={{ width: '32px', height: '32px', color: 'var(--mac-accent)' }} />
            AI Аналитические Инсайты
          </h2>
          <p style={{ 
            color: 'var(--mac-text-primary)',
            fontSize: 'var(--mac-font-size-sm)',
            margin: 0
          }}>
            Выявление трендов, аномалий и паттернов в медицинских данных
          </p>
        </div>

        {/* Вкладки */}
        <div style={{ 
          display: 'flex', 
          marginBottom: '24px'
        }}>
          {tabs.map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: '12px 20px',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-primary)',
                  fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                  fontSize: 'var(--mac-font-size-sm)',
                  transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                  position: 'relative',
                  marginBottom: '-1px'
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    e.target.style.color = 'var(--mac-text-primary)';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    e.target.style.color = 'var(--mac-text-primary)';
                  }
                }}
              >
                <Icon style={{ 
                  width: '16px', 
                  height: '16px',
                  color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-primary)'
                }} />
                {tab.label}
                {isActive && (
                  <div style={{
                    position: 'absolute',
                    bottom: '0',
                    left: '0',
                    right: '0',
                    height: '3px',
                    backgroundColor: 'var(--mac-accent)',
                    borderRadius: '2px 2px 0 0'
                  }} />
                )}
              </button>
            );
          })}
        </div>
        
        {/* Разделительная линия */}
        <div style={{ 
          borderBottom: '1px solid var(--mac-border)',
          marginBottom: '24px'
        }} />

        {/* Контент */}
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', 
          gap: '24px' 
        }}>
          <div>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)',
              margin: '0 0 16px 0'
            }}>
              Настройки и данные
            </h3>
            
            {activeTab === 'trends' && renderTrendsAnalysis()}
            {activeTab === 'anomalies' && renderAnomalyDetection()}
            {activeTab === 'outcomes' && renderOutcomePrediction()}
            {activeTab === 'reports' && renderInsightsReport()}
            {activeTab === 'risk-patterns' && renderRiskPatterns()}
            
            <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'center' }}>
              <MacOSButton
                onClick={handleSubmit}
                disabled={loading}
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                {loading ? (
                  <>
                    <Loader style={{ 
                      width: '20px', 
                      height: '20px',
                      animation: 'spin 1s linear infinite'
                    }} />
                    Анализируем...
                  </>
                ) : (
                  <>
                    <TrendingUp style={{ width: '20px', height: '20px' }} />
                    Запустить AI анализ
                  </>
                )}
              </MacOSButton>
            </div>
          </div>

          <div>
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-text-primary)',
              margin: '0 0 16px 0'
            }}>
              Результат
            </h3>
            {renderResult()}
            
            {error && (
              <MacOSCard style={{ 
                padding: '16px', 
                backgroundColor: 'var(--mac-bg-primary)', 
                border: '1px solid var(--mac-border)',
                marginTop: '16px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <AlertTriangle style={{ width: '20px', height: '20px', color: 'var(--mac-danger)' }} />
                  <h3 style={{ 
                    fontSize: 'var(--mac-font-size-sm)', 
                    fontWeight: 'var(--mac-font-weight-medium)', 
                    color: 'var(--mac-danger)',
                    margin: 0
                  }}>
                    Ошибка
                  </h3>
                </div>
                <p style={{ 
                  marginTop: '8px',
                  fontSize: 'var(--mac-font-size-sm)', 
                  color: 'var(--mac-danger)',
                  margin: '8px 0 0 0'
                }}>
                  {error}
                </p>
              </MacOSCard>
            )}
          </div>
        </div>
      </MacOSCard>
    </div>
  );
};

export default AnalyticsInsights;



