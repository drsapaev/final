import { useState } from 'react';
import {
  MacOSCard,
  Button,
  Input,
  Select,
  Textarea,
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
  XCircle } from




'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';

const parseOptionalInteger = (value) => {
  if (value === '') return '';
  const parsed = parseInt(value, 10);
  return Number.isNaN(parsed) ? '' : parsed;
};

const parseOptionalFloat = (value) => {
  if (value === '') return '';
  const parsed = parseFloat(value);
  return Number.isNaN(parsed) ? '' : parsed;
};

const AnalyticsInsights = () => {
  const [activeTab, setActiveTab] = useState('trends');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Состояния для анализа трендов
  const [medicalData, setMedicalData] = useState([]);
  const [timePeriod, setTimePeriod] = useState('month');
  const [analysisType, setAnalysisType] = useState('disease_trends');

  // Состояния для выявления аномалий
  const [dataset, setDataset] = useState([]);
  const [baselineData, setBaselineData] = useState({
    blood_pressure_normal: { systolic: 120, diastolic: 80 },
    temperature_normal: 36.6,
    heart_rate_normal: { min: 60, max: 100 },
    expected_patterns: { daily_visits: 50, seasonal_variation: 0.2 }
  });

  // Состояния для прогнозирования исходов
  const [patientData, setPatientData] = useState({
    age: '',
    gender: '',
    diagnosis: '',
    comorbidities: [],
    treatment_start_date: '',
    baseline_bp: '',
    medications: []
  });
  const [historicalOutcomes, setHistoricalOutcomes] = useState([]);

  // Состояния для генерации отчетов
  const [analyticsData, setAnalyticsData] = useState({
    period: '',
    total_patients: '',
    departments: [],
    key_metrics: {
      patient_satisfaction: '',
      average_wait_time: '',
      treatment_success_rate: ''
    },
    trends: {
      patient_growth: '',
      revenue_growth: '',
      efficiency_improvement: ''
    }
  });
  const [reportType, setReportType] = useState('quarterly_performance');

  // Состояния для выявления паттернов рисков
  const [populationData, setPopulationData] = useState([]);
  const [riskFactors, setRiskFactors] = useState(['smoking', 'sedentary_lifestyle', 'obesity', 'family_history', 'age']);

  const tabs = [
  { id: 'trends', label: 'Анализ трендов', icon: TrendingUp },
  { id: 'anomalies', label: 'Выявление аномалий', icon: AlertTriangle },
  { id: 'outcomes', label: 'Прогноз исходов', icon: Target },
  { id: 'reports', label: 'Отчеты инсайтов', icon: FileText },
  { id: 'risk-patterns', label: 'Паттерны рисков', icon: Users }];


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
      logger.error('AI analytics error:', err);
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
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);

    const exportFileDefaultName = `analytics_insights_${activeTab}_${new Date().toISOString().split('T')[0]}.json`;

    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const addMedicalRecord = () => {
    setMedicalData((prev) => [
    ...prev,
    {
      id: '',
      date: '',
      type: '',
      diagnosis: '',
      patient_age: '',
      department: ''
    }]
    );
  };

  const removeMedicalRecord = (index) => {
    setMedicalData((prev) => prev.filter((_, i) => i !== index));
  };

  const addDatasetEntry = () => {
    setDataset((prev) => [
    ...prev,
    {
      id: '',
      value: '',
      timestamp: '',
      type: '',
      patient_id: ''
    }]
    );
  };

  const removeDatasetEntry = (index) => {
    setDataset((prev) => prev.filter((_, i) => i !== index));
  };

  const addHistoricalOutcome = () => {
    setHistoricalOutcomes((prev) => [
    ...prev,
    { condition: '', treatment: '', result: '', duration: '', patient_age: '' }]
    );
  };

  const removeHistoricalOutcome = (index) => {
    setHistoricalOutcomes((prev) => prev.filter((_, i) => i !== index));
  };

  const addPopulationEntry = () => {
    setPopulationData((prev) => [
    ...prev,
    {
      id: '',
      age: '',
      gender: '',
      conditions: [],
      lifestyle: ''
    }]
    );
  };

  const removePopulationEntry = (index) => {
    setPopulationData((prev) => prev.filter((_, i) => i !== index));
  };

  const addRiskFactor = () => {
    setRiskFactors((prev) => [...prev, '']);
  };

  const removeRiskFactor = (index) => {
    setRiskFactors((prev) => prev.filter((_, i) => i !== index));
  };

  const renderTrendsAnalysis = () =>
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
          <Button
          onClick={addMedicalRecord}
          variant="outline"
          style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить запись
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '160px', overflowY: 'auto' }}>
          {medicalData.map((record, index) =>
        <div key={record.id || index} style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(6, 1fr)',
          gap: '8px',
          alignItems: 'center'
        }}>
              <Input
            type="date"
            value={record.date}
            onChange={(e) => {
              const newData = [...medicalData];
              newData[index].date = e.target.value;
              setMedicalData(newData);
            }}
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
            <Select
            value={record.type}
            onChange={(e) => {
              const newData = [...medicalData];
              newData[index].type = e.target.value;
              setMedicalData(newData);
            }}
            placeholder="Выберите тип"
            options={[
            { value: 'consultation', label: 'Консультация' },
            { value: 'procedure', label: 'Процедура' },
            { value: 'surgery', label: 'Операция' },
            { value: 'emergency', label: 'Неотложка' }]
            }
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="text"
            value={record.diagnosis}
            onChange={(e) => {
              const newData = [...medicalData];
              newData[index].diagnosis = e.target.value;
              setMedicalData(newData);
            }}
            placeholder="Диагноз"
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="number"
            value={record.patient_age}
            onChange={(e) => {
              const newData = [...medicalData];
              newData[index].patient_age = parseOptionalInteger(e.target.value);
              setMedicalData(newData);
            }}
            placeholder="Возраст"
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
            <Select
            value={record.department}
            onChange={(e) => {
              const newData = [...medicalData];
              newData[index].department = e.target.value;
              setMedicalData(newData);
            }}
            placeholder="Выберите отделение"
            options={[
            { value: 'general', label: 'Общий' },
            { value: 'cardiology', label: 'Кардиология' },
            { value: 'endocrinology', label: 'Эндокринология' },
            { value: 'neurology', label: 'Неврология' },
            { value: 'surgery', label: 'Хирургия' }]
            }
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Button
            type="button"
            title="Remove medical record"
            aria-label={`Remove medical record ${index + 1}`}
            onClick={() => removeMedicalRecord(index)}
            variant="outline"
            style={{ padding: '4px', minWidth: 'auto' }}>

                <Minus aria-hidden="true" style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
              </Button>
            </div>
        )}
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
              <Select
              value={timePeriod}
              onChange={(e) => setTimePeriod(e.target.value)}
              options={[
              { value: 'day', label: 'День' },
              { value: 'week', label: 'Неделя' },
              { value: 'month', label: 'Месяц' },
              { value: 'quarter', label: 'Квартал' },
              { value: 'year', label: 'Год' }]
              }
              style={{ width: '100%' }} />
            
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
              <Select
              value={analysisType}
              onChange={(e) => setAnalysisType(e.target.value)}
              options={[
              { value: 'disease_trends', label: 'Тренды заболеваний' },
              { value: 'patient_flow', label: 'Поток пациентов' },
              { value: 'resource_utilization', label: 'Использование ресурсов' },
              { value: 'treatment_effectiveness', label: 'Эффективность лечения' },
              { value: 'seasonal_patterns', label: 'Сезонные паттерны' }]
              }
              style={{ width: '100%' }} />
            
            </div>
          </div>
        </MacOSCard>
      </div>
    </div>;


  const renderAnomalyDetection = () =>
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
          <Button
          type="button"
          title="Add anomaly dataset entry"
          aria-label="Add anomaly dataset entry"
          onClick={addDatasetEntry}
          variant="outline"
          style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>

            <Plus aria-hidden="true" style={{ width: '16px', height: '16px' }} />
            Добавить запись
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '160px', overflowY: 'auto' }}>
          {dataset.map((entry, index) =>
        <div key={entry.id || index} style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(5, 1fr)',
          gap: '8px',
          alignItems: 'center'
        }}>
              <Input
            type="number"
            value={entry.value}
            onChange={(e) => {
              const newDataset = [...dataset];
              newDataset[index].value = parseOptionalFloat(e.target.value);
              setDataset(newDataset);
            }}
            placeholder="Значение"
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="datetime-local"
            value={entry.timestamp.slice(0, 16)}
            onChange={(e) => {
              const newDataset = [...dataset];
              newDataset[index].timestamp = e.target.value ? `${e.target.value}:00` : '';
              setDataset(newDataset);
            }}
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
            <Select
            value={entry.type}
            onChange={(e) => {
              const newDataset = [...dataset];
              newDataset[index].type = e.target.value;
              setDataset(newDataset);
            }}
            placeholder="Выберите тип"
            options={[
            { value: 'blood_pressure', label: 'АД' },
            { value: 'temperature', label: 'Температура' },
            { value: 'heart_rate', label: 'ЧСС' },
            { value: 'glucose', label: 'Глюкоза' },
            { value: 'weight', label: 'Вес' }]
            }
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="text"
            value={entry.patient_id}
            onChange={(e) => {
              const newDataset = [...dataset];
              newDataset[index].patient_id = e.target.value;
              setDataset(newDataset);
            }}
            placeholder="ID пациента"
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Button
            type="button"
            title="Remove anomaly dataset entry"
            aria-label={`Remove anomaly dataset entry ${index + 1}`}
            onClick={() => removeDatasetEntry(index)}
            variant="outline"
            style={{ padding: '4px', minWidth: 'auto' }}>

                <Minus aria-hidden="true" style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
              </Button>
            </div>
        )}
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
          <Textarea
          value={JSON.stringify(baselineData, null, 2)}
          onChange={(e) => {
            try {
              setBaselineData(JSON.parse(e.target.value));
            } catch {


              // Игнорируем ошибки парсинга во время ввода
            }}} placeholder="JSON с базовыми показателями"
          style={{
            width: '100%',
            height: '128px',
            fontFamily: 'var(--mac-font-mono)',
            fontSize: 'var(--mac-font-size-xs)'
          }} />
        
        </div>
      </MacOSCard>
    </div>;


  const renderOutcomePrediction = () =>
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
            <Input
            type="number"
            value={patientData.age}
            onChange={(e) => setPatientData((prev) => ({ ...prev, age: parseOptionalInteger(e.target.value) }))}
            style={{ width: '100%' }} />
          
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
            <Select
            value={patientData.gender}
            onChange={(e) => setPatientData((prev) => ({ ...prev, gender: e.target.value }))}
            placeholder="Выберите пол"
            options={[
            { value: 'male', label: 'Мужской' },
            { value: 'female', label: 'Женский' }]
            }
            style={{ width: '100%' }} />
          
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
            <Input
            type="text"
            value={patientData.diagnosis}
            onChange={(e) => setPatientData((prev) => ({ ...prev, diagnosis: e.target.value }))}
            style={{ width: '100%' }} />
          
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
            <Input
            type="date"
            value={patientData.treatment_start_date}
            onChange={(e) => setPatientData((prev) => ({ ...prev, treatment_start_date: e.target.value }))}
            style={{ width: '100%' }} />
          
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
          <Button
          onClick={addHistoricalOutcome}
          variant="outline"
          style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить исход
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '160px', overflowY: 'auto' }}>
          {historicalOutcomes.map((outcome, index) =>
        <div key={index} style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(6, 1fr)',
          gap: '8px',
          alignItems: 'center'
        }}>
              <Input
            type="text"
            value={outcome.condition}
            onChange={(e) => {
              const newOutcomes = [...historicalOutcomes];
              newOutcomes[index].condition = e.target.value;
              setHistoricalOutcomes(newOutcomes);
            }}
            placeholder="Состояние"
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="text"
            value={outcome.treatment}
            onChange={(e) => {
              const newOutcomes = [...historicalOutcomes];
              newOutcomes[index].treatment = e.target.value;
              setHistoricalOutcomes(newOutcomes);
            }}
            placeholder="Лечение"
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
            <Select
            value={outcome.result}
            onChange={(e) => {
              const newOutcomes = [...historicalOutcomes];
              newOutcomes[index].result = e.target.value;
              setHistoricalOutcomes(newOutcomes);
            }}
            placeholder="Выберите исход"
            options={[
            { value: 'success', label: 'Успех' },
            { value: 'partial', label: 'Частичный' },
            { value: 'failure', label: 'Неудача' },
            { value: 'ongoing', label: 'Продолжается' }]
            }
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="text"
            value={outcome.duration}
            onChange={(e) => {
              const newOutcomes = [...historicalOutcomes];
              newOutcomes[index].duration = e.target.value;
              setHistoricalOutcomes(newOutcomes);
            }}
            placeholder="Длительность"
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="number"
            value={outcome.patient_age}
            onChange={(e) => {
              const newOutcomes = [...historicalOutcomes];
              newOutcomes[index].patient_age = parseOptionalInteger(e.target.value);
              setHistoricalOutcomes(newOutcomes);
            }}
            placeholder="Возраст"
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Button
            type="button"
            title="Remove historical outcome"
            aria-label={`Remove historical outcome ${index + 1}`}
            onClick={() => removeHistoricalOutcome(index)}
            variant="outline"
            style={{ padding: '4px', minWidth: 'auto' }}>

                <Minus aria-hidden="true" style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
              </Button>
            </div>
        )}
        </div>
      </MacOSCard>
    </div>;


  const renderInsightsReport = () =>
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
            <Select
            value={reportType}
            onChange={(e) => setReportType(e.target.value)}
            options={[
            { value: 'quarterly_performance', label: 'Квартальная производительность' },
            { value: 'annual_review', label: 'Годовой обзор' },
            { value: 'department_analysis', label: 'Анализ отделений' },
            { value: 'patient_satisfaction', label: 'Удовлетворенность пациентов' },
            { value: 'financial_overview', label: 'Финансовый обзор' },
            { value: 'quality_metrics', label: 'Метрики качества' }]
            }
            style={{ width: '100%' }} />
          
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
          <Textarea
          value={JSON.stringify(analyticsData, null, 2)}
          onChange={(e) => {
            try {
              setAnalyticsData(JSON.parse(e.target.value));
            } catch {


              // Игнорируем ошибки парсинга во время ввода
            }}} placeholder="JSON с аналитическими данными"
          style={{
            width: '100%',
            height: '160px',
            fontFamily: 'var(--mac-font-mono)',
            fontSize: 'var(--mac-font-size-xs)'
          }} />
        
        </div>
      </MacOSCard>
    </div>;


  const renderRiskPatterns = () =>
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
          <Button
          type="button"
          title="Add population patient"
          aria-label="Add population patient"
          onClick={addPopulationEntry}
          variant="outline"
          style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>

            <Plus aria-hidden="true" style={{ width: '16px', height: '16px' }} />
            Добавить пациента
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '160px', overflowY: 'auto' }}>
          {populationData.map((patient, index) =>
        <div key={patient.id || index} style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(6, 1fr)',
          gap: '8px',
          alignItems: 'center'
        }}>
              <Input
            type="text"
            value={patient.id}
            onChange={(e) => {
              const newData = [...populationData];
              newData[index].id = e.target.value;
              setPopulationData(newData);
            }}
            placeholder="ID"
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="number"
            value={patient.age}
            onChange={(e) => {
              const newData = [...populationData];
              newData[index].age = parseOptionalInteger(e.target.value);
              setPopulationData(newData);
            }}
            placeholder="Возраст"
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
            <Select
            value={patient.gender}
            onChange={(e) => {
              const newData = [...populationData];
              newData[index].gender = e.target.value;
              setPopulationData(newData);
            }}
            placeholder="Выберите пол"
            options={[
            { value: 'male', label: 'М' },
            { value: 'female', label: 'Ж' }]
            }
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="text"
            value={patient.conditions.join(', ')}
            onChange={(e) => {
              const newData = [...populationData];
              newData[index].conditions = e.target.value.split(',').map((c) => c.trim()).filter((c) => c);
              setPopulationData(newData);
            }}
            placeholder="Заболевания"
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
            <Select
            value={patient.lifestyle}
            onChange={(e) => {
              const newData = [...populationData];
              newData[index].lifestyle = e.target.value;
              setPopulationData(newData);
            }}
            placeholder="Выберите образ жизни"
            options={[
            { value: 'active', label: 'Активный' },
            { value: 'sedentary', label: 'Малоподвижный' },
            { value: 'moderate', label: 'Умеренный' }]
            }
            style={{ fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Button
            type="button"
            title="Remove population patient"
            aria-label={`Remove population patient ${index + 1}`}
            onClick={() => removePopulationEntry(index)}
            variant="outline"
            style={{ padding: '4px', minWidth: 'auto' }}>

                <Minus aria-hidden="true" style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
              </Button>
            </div>
        )}
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
          <Button
          type="button"
          title="Add risk factor"
          aria-label="Add risk factor"
          onClick={addRiskFactor}
          variant="outline"
          style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>

            <Plus aria-hidden="true" style={{ width: '16px', height: '16px' }} />
            Добавить фактор
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '128px', overflowY: 'auto' }}>
          {riskFactors.map((factor, index) =>
        <div key={index} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <Input
            type="text"
            value={factor}
            onChange={(e) => {
              const newFactors = [...riskFactors];
              newFactors[index] = e.target.value;
              setRiskFactors(newFactors);
            }}
            placeholder="Фактор риска"
            style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Button
            type="button"
            title="Remove risk factor"
            aria-label={`Remove risk factor ${index + 1}`}
            onClick={() => removeRiskFactor(index)}
            variant="outline"
            style={{ padding: '4px', minWidth: 'auto' }}>

                <Minus aria-hidden="true" style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
              </Button>
            </div>
        )}
        </div>
      </MacOSCard>
    </div>;


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
        </MacOSCard>);

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
            <Button
              onClick={() => copyToClipboard(JSON.stringify(result, null, 2))}
              variant="outline"
              style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              
              <Copy style={{ width: '16px', height: '16px' }} />
              Копировать
            </Button>
            <Button
              onClick={exportResult}
              variant="outline"
              style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              
              <Download style={{ width: '16px', height: '16px' }} />
              Экспорт
            </Button>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {Object.entries(result).map(([key, value]) =>
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
                {typeof value === 'object' && value !== null ?
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
                  </pre> :

              <p style={{ margin: 0 }}>{String(value)}</p>
              }
              </div>
            </div>
          )}
        </div>
      </MacOSCard>);

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
          {tabs.map((tab) => {
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
                }}>
                
                <Icon style={{
                  width: '16px',
                  height: '16px',
                  color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-primary)'
                }} />
                {tab.label}
                {isActive &&
                <div style={{
                  position: 'absolute',
                  bottom: '0',
                  left: '0',
                  right: '0',
                  height: '3px',
                  backgroundColor: 'var(--mac-accent)',
                  borderRadius: '2px 2px 0 0'
                }} />
                }
              </button>);

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
              <Button
                type="button"
                title={loading ? 'Running AI analytics' : 'Run AI analytics'}
                aria-label={loading ? 'Running AI analytics' : 'Run AI analytics'}
                onClick={handleSubmit}
                disabled={loading}
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                
                {loading ?
                <>
                    <Loader aria-hidden="true" style={{
                    width: '20px',
                    height: '20px',
                    animation: 'spin 1s linear infinite'
                  }} />
                    Анализируем...
                  </> :

                <>
                    <TrendingUp aria-hidden="true" style={{ width: '20px', height: '20px' }} />
                    Запустить AI анализ
                  </>
                }
              </Button>
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
            
            {error &&
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
            }
          </div>
        </div>
      </MacOSCard>
    </div>);

};

export default AnalyticsInsights;
