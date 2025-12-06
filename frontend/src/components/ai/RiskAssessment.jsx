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
import {
  MacOSCard,
  MacOSButton,
  MacOSInput,
  MacOSSelect,
  MacOSTextarea,
  MacOSCheckbox,
  MacOSBadge,
  MacOSLoadingSkeleton
} from '../ui/macos';
import { toast } from 'react-toastify';
import { api } from '../../utils/api';

import logger from '../../utils/logger';
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
      logger.error('Ошибка анализа:', error);
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
        return {
          backgroundColor: 'var(--mac-bg-primary)',
          borderColor: 'var(--mac-border)',
          textColor: 'var(--mac-danger)'
        };
      case 'высокий':
      case 'high':
        return {
          backgroundColor: 'var(--mac-bg-primary)',
          borderColor: 'var(--mac-border)',
          textColor: 'var(--mac-warning)'
        };
      case 'умеренный':
      case 'moderate':
        return {
          backgroundColor: 'var(--mac-bg-primary)',
          borderColor: 'var(--mac-border)',
          textColor: 'var(--mac-accent)'
        };
      case 'низкий':
      case 'low':
        return {
          backgroundColor: 'var(--mac-bg-primary)',
          borderColor: 'var(--mac-border)',
          textColor: 'var(--mac-success)'
        };
      default:
        return {
          backgroundColor: 'var(--mac-bg-secondary)',
          borderColor: 'var(--mac-border)',
          textColor: 'var(--mac-text-primary)'
        };
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
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-bg-primary)', 
          border: '1px solid var(--mac-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-danger)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <AlertTriangle style={{ width: '16px', height: '16px' }} />
            Основные данные пациента
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
                value={patientRiskData.patient_data.age}
                onChange={(e) => setPatientRiskData(prev => ({
                  ...prev,
                  patient_data: { ...prev.patient_data, age: e.target.value }
                }))}
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
                value={patientRiskData.patient_data.gender}
                onChange={(e) => setPatientRiskData(prev => ({
                  ...prev,
                  patient_data: { ...prev.patient_data, gender: e.target.value }
                }))}
                options={[
                  { value: '', label: 'Выберите пол' },
                  { value: 'мужской', label: 'Мужской' },
                  { value: 'женский', label: 'Женский' }
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
                Вес (кг)
              </label>
              <MacOSInput
                type="number"
                value={patientRiskData.patient_data.weight}
                onChange={(e) => setPatientRiskData(prev => ({
                  ...prev,
                  patient_data: { ...prev.patient_data, weight: e.target.value }
                }))}
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
            color: 'var(--mac-warning)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Activity style={{ width: '16px', height: '16px' }} />
            Факторы образа жизни
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
                Курение
              </label>
              <MacOSSelect
                value={patientRiskData.patient_data.smoking_status}
                onChange={(e) => setPatientRiskData(prev => ({
                  ...prev,
                  patient_data: { ...prev.patient_data, smoking_status: e.target.value }
                }))}
                options={[
                  { value: '', label: 'Выберите статус' },
                  { value: 'никогда не курил', label: 'Никогда не курил' },
                  { value: 'бросил курить', label: 'Бросил курить' },
                  { value: 'курит', label: 'Курит' }
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
                Употребление алкоголя
              </label>
              <MacOSSelect
                value={patientRiskData.patient_data.alcohol_consumption}
                onChange={(e) => setPatientRiskData(prev => ({
                  ...prev,
                  patient_data: { ...prev.patient_data, alcohol_consumption: e.target.value }
                }))}
                options={[
                  { value: '', label: 'Выберите' },
                  { value: 'не употребляет', label: 'Не употребляет' },
                  { value: 'умеренное', label: 'Умеренное' },
                  { value: 'чрезмерное', label: 'Чрезмерное' }
                ]}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </MacOSCard>

        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-info-bg)', 
          border: '1px solid var(--mac-info-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-info)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <FileText style={{ width: '16px', height: '16px' }} />
            Медицинская информация
          </h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '4px' 
              }}>
                Состояние/Заболевание
              </label>
              <MacOSInput
                type="text"
                value={patientRiskData.condition}
                onChange={(e) => setPatientRiskData(prev => ({ ...prev, condition: e.target.value }))}
                placeholder="Например: Ишемическая болезнь сердца"
                style={{ width: '100%' }}
              />
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <label style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)',
                  margin: 0
                }}>
                  Сопутствующие заболевания
                </label>
                <MacOSButton
                  onClick={() => addArrayItem(setPatientRiskData, 'patient_data.comorbidities')}
                  variant="outline"
                  style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px' }}
                >
                  <Plus style={{ width: '12px', height: '12px' }} />
                  Добавить
                </MacOSButton>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '120px', overflowY: 'auto' }}>
                {patientRiskData.patient_data.comorbidities.map((item, index) => (
                  <div key={index} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <MacOSInput
                      type="text"
                      value={item}
                      onChange={(e) => updateArrayItem(setPatientRiskData, 'patient_data.comorbidities', index, e.target.value)}
                      placeholder="Заболевание"
                      style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }}
                    />
                    <MacOSButton
                      onClick={() => removeArrayItem(setPatientRiskData, 'patient_data.comorbidities', index)}
                      variant="outline"
                      style={{ padding: '4px', minWidth: 'auto' }}
                    >
                      <Minus style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
                    </MacOSButton>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                <label style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)', 
                  color: 'var(--mac-text-primary)',
                  margin: 0
                }}>
                  Факторы риска
                </label>
                <MacOSButton
                  onClick={() => addArrayItem(setPatientRiskData, 'risk_factors')}
                  variant="outline"
                  style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px' }}
                >
                  <Plus style={{ width: '12px', height: '12px' }} />
                  Добавить
                </MacOSButton>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '120px', overflowY: 'auto' }}>
                {patientRiskData.risk_factors.map((item, index) => (
                  <div key={index} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <MacOSInput
                      type="text"
                      value={item}
                      onChange={(e) => updateArrayItem(setPatientRiskData, 'risk_factors', index, e.target.value)}
                      placeholder="Фактор риска"
                      style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }}
                    />
                    <MacOSButton
                      onClick={() => removeArrayItem(setPatientRiskData, 'risk_factors', index)}
                      variant="outline"
                      style={{ padding: '4px', minWidth: 'auto' }}
                    >
                      <Minus style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
                    </MacOSButton>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={() => handleSubmit('assess-patient-risk', patientRiskData)}
            disabled={loading || !patientRiskData.condition}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              backgroundColor: 'var(--mac-danger)',
              border: 'none'
            }}
          >
            {loading ? (
              <>
                <Loader style={{ 
                  width: '20px', 
                  height: '20px',
                  animation: 'spin 1s linear infinite'
                }} />
                Оцениваем риски...
              </>
            ) : (
              <>
                <AlertTriangle style={{ width: '20px', height: '20px' }} />
                Оценить риски
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
  );

  const renderComplicationForm = () => (
    <MacOSCard style={{ padding: '24px' }}>
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
            <Activity style={{ width: '16px', height: '16px' }} />
            Информация о процедуре
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
                Процедура/Состояние
              </label>
              <MacOSInput
                type="text"
                value={complicationData.procedure_or_condition}
                onChange={(e) => setComplicationData(prev => ({ ...prev, procedure_or_condition: e.target.value }))}
                placeholder="Например: Лапароскопическая холецистэктомия"
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
                Временные рамки
              </label>
              <MacOSSelect
                value={complicationData.timeline}
                onChange={(e) => setComplicationData(prev => ({ ...prev, timeline: e.target.value }))}
                options={[
                  { value: '', label: 'Выберите период' },
                  { value: '24 часа', label: '24 часа' },
                  { value: '7 дней', label: '7 дней' },
                  { value: '30 дней', label: '30 дней' },
                  { value: '90 дней', label: '90 дней' },
                  { value: '1 год', label: '1 год' }
                ]}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </MacOSCard>

        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-info-bg)', 
          border: '1px solid var(--mac-info-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-info)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <UserCheck style={{ width: '16px', height: '16px' }} />
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
                value={complicationData.patient_profile.age}
                onChange={(e) => setComplicationData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, age: e.target.value }
                }))}
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
                value={complicationData.patient_profile.gender}
                onChange={(e) => setComplicationData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, gender: e.target.value }
                }))}
                options={[
                  { value: '', label: 'Выберите пол' },
                  { value: 'мужской', label: 'Мужской' },
                  { value: 'женский', label: 'Женский' }
                ]}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={() => handleSubmit('predict-complications', complicationData)}
            disabled={loading || !complicationData.procedure_or_condition || !complicationData.timeline}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              backgroundColor: 'var(--mac-warning)',
              border: 'none'
            }}
          >
            {loading ? (
              <>
                <Loader style={{ 
                  width: '20px', 
                  height: '20px',
                  animation: 'spin 1s linear infinite'
                }} />
                Прогнозируем осложнения...
              </>
            ) : (
              <>
                <Activity style={{ width: '20px', height: '20px' }} />
                Спрогнозировать осложнения
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
  );

  const renderMortalityForm = () => (
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-bg-primary)', 
          border: '1px solid var(--mac-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-danger)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Heart style={{ width: '16px', height: '16px' }} />
            Информация о состоянии
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
                Состояние
              </label>
              <MacOSInput
                type="text"
                value={mortalityData.condition}
                onChange={(e) => setMortalityData(prev => ({ ...prev, condition: e.target.value }))}
                placeholder="Например: Острый инфаркт миокарда"
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
                Система оценки
              </label>
              <MacOSSelect
                value={mortalityData.scoring_system}
                onChange={(e) => setMortalityData(prev => ({ ...prev, scoring_system: e.target.value }))}
                options={[
                  { value: '', label: 'Автоматический выбор' },
                  { value: 'APACHE II', label: 'APACHE II' },
                  { value: 'SOFA', label: 'SOFA' },
                  { value: 'SAPS II', label: 'SAPS II' },
                  { value: 'CHA2DS2-VASc', label: 'CHA2DS2-VASc' },
                  { value: 'GRACE', label: 'GRACE' }
                ]}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </MacOSCard>

        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-info-bg)', 
          border: '1px solid var(--mac-info-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-info)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <UserCheck style={{ width: '16px', height: '16px' }} />
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
                value={mortalityData.patient_data.age}
                onChange={(e) => setMortalityData(prev => ({
                  ...prev,
                  patient_data: { ...prev.patient_data, age: e.target.value }
                }))}
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
                value={mortalityData.patient_data.gender}
                onChange={(e) => setMortalityData(prev => ({
                  ...prev,
                  patient_data: { ...prev.patient_data, gender: e.target.value }
                }))}
                options={[
                  { value: '', label: 'Выберите пол' },
                  { value: 'мужской', label: 'Мужской' },
                  { value: 'женский', label: 'Женский' }
                ]}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={() => handleSubmit('calculate-mortality-risk', mortalityData)}
            disabled={loading || !mortalityData.condition}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              backgroundColor: 'var(--mac-danger)',
              border: 'none'
            }}
          >
            {loading ? (
              <>
                <Loader style={{ 
                  width: '20px', 
                  height: '20px',
                  animation: 'spin 1s linear infinite'
                }} />
                Рассчитываем риск...
              </>
            ) : (
              <>
                <Heart style={{ width: '20px', height: '20px' }} />
                Рассчитать риск смертности
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
  );

  const renderSurgicalForm = () => (
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-bg-primary)', 
          border: '1px solid var(--mac-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-accent)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Stethoscope style={{ width: '16px', height: '16px' }} />
            Информация об операции
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
                Тип операции
              </label>
              <MacOSInput
                type="text"
                value={surgicalData.surgery_type}
                onChange={(e) => setSurgicalData(prev => ({ ...prev, surgery_type: e.target.value }))}
                placeholder="Например: Аппендэктомия"
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
                Тип анестезии
              </label>
              <MacOSSelect
                value={surgicalData.anesthesia_type}
                onChange={(e) => setSurgicalData(prev => ({ ...prev, anesthesia_type: e.target.value }))}
                options={[
                  { value: '', label: 'Выберите тип' },
                  { value: 'общая', label: 'Общая анестезия' },
                  { value: 'спинальная', label: 'Спинальная анестезия' },
                  { value: 'эпидуральная', label: 'Эпидуральная анестезия' },
                  { value: 'местная', label: 'Местная анестезия' },
                  { value: 'седация', label: 'Седация' }
                ]}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </MacOSCard>

        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-info-bg)', 
          border: '1px solid var(--mac-info-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-info)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <UserCheck style={{ width: '16px', height: '16px' }} />
            Профиль пациента
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
                value={surgicalData.patient_profile.age}
                onChange={(e) => setSurgicalData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, age: e.target.value }
                }))}
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
                Класс ASA
              </label>
              <MacOSSelect
                value={surgicalData.patient_profile.asa_class}
                onChange={(e) => setSurgicalData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, asa_class: e.target.value }
                }))}
                options={[
                  { value: '', label: 'Выберите класс' },
                  { value: 'I', label: 'ASA I - Здоровый пациент' },
                  { value: 'II', label: 'ASA II - Легкое системное заболевание' },
                  { value: 'III', label: 'ASA III - Тяжелое системное заболевание' },
                  { value: 'IV', label: 'ASA IV - Угроза жизни' },
                  { value: 'V', label: 'ASA V - Умирающий пациент' }
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
                Функциональный статус
              </label>
              <MacOSSelect
                value={surgicalData.patient_profile.functional_status}
                onChange={(e) => setSurgicalData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, functional_status: e.target.value }
                }))}
                options={[
                  { value: '', label: 'Выберите статус' },
                  { value: 'независимый', label: 'Независимый' },
                  { value: 'частично зависимый', label: 'Частично зависимый' },
                  { value: 'полностью зависимый', label: 'Полностью зависимый' }
                ]}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={() => handleSubmit('assess-surgical-risk', surgicalData)}
            disabled={loading || !surgicalData.surgery_type || !surgicalData.anesthesia_type}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              backgroundColor: 'var(--mac-accent)',
              border: 'none'
            }}
          >
            {loading ? (
              <>
                <Loader style={{ 
                  width: '20px', 
                  height: '20px',
                  animation: 'spin 1s linear infinite'
                }} />
                Оцениваем риски...
              </>
            ) : (
              <>
                <Stethoscope style={{ width: '20px', height: '20px' }} />
                Оценить хирургические риски
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
  );

  const renderReadmissionForm = () => (
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
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
            <UserCheck style={{ width: '16px', height: '16px' }} />
            Информация о выписке
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
                Основной диагноз
              </label>
              <MacOSInput
                type="text"
                value={readmissionData.patient_data.primary_diagnosis}
                onChange={(e) => setReadmissionData(prev => ({
                  ...prev,
                  patient_data: { ...prev.patient_data, primary_diagnosis: e.target.value }
                }))}
                placeholder="Диагноз при выписке"
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
                Состояние при выписке
              </label>
              <MacOSSelect
                value={readmissionData.discharge_condition}
                onChange={(e) => setReadmissionData(prev => ({ ...prev, discharge_condition: e.target.value }))}
                options={[
                  { value: '', label: 'Выберите состояние' },
                  { value: 'стабильное', label: 'Стабильное' },
                  { value: 'улучшение', label: 'Улучшение' },
                  { value: 'без изменений', label: 'Без изменений' },
                  { value: 'ухудшение', label: 'Ухудшение' }
                ]}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </MacOSCard>

        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-info-bg)', 
          border: '1px solid var(--mac-info-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-info)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Clock style={{ width: '16px', height: '16px' }} />
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
                value={readmissionData.patient_data.age}
                onChange={(e) => setReadmissionData(prev => ({
                  ...prev,
                  patient_data: { ...prev.patient_data, age: e.target.value }
                }))}
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
                Длительность госпитализации
              </label>
              <MacOSInput
                type="text"
                value={readmissionData.patient_data.length_of_stay}
                onChange={(e) => setReadmissionData(prev => ({
                  ...prev,
                  patient_data: { ...prev.patient_data, length_of_stay: e.target.value }
                }))}
                placeholder="Например: 5 дней"
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
                Социальная поддержка
              </label>
              <MacOSSelect
                value={readmissionData.social_factors.social_support}
                onChange={(e) => setReadmissionData(prev => ({
                  ...prev,
                  social_factors: { ...prev.social_factors, social_support: e.target.value }
                }))}
                options={[
                  { value: '', label: 'Выберите уровень' },
                  { value: 'хорошая', label: 'Хорошая' },
                  { value: 'умеренная', label: 'Умеренная' },
                  { value: 'ограниченная', label: 'Ограниченная' },
                  { value: 'отсутствует', label: 'Отсутствует' }
                ]}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={() => handleSubmit('predict-readmission-risk', readmissionData)}
            disabled={loading || !readmissionData.patient_data.primary_diagnosis || !readmissionData.discharge_condition}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              backgroundColor: 'var(--mac-success)',
              border: 'none'
            }}
          >
            {loading ? (
              <>
                <Loader style={{ 
                  width: '20px', 
                  height: '20px',
                  animation: 'spin 1s linear infinite'
                }} />
                Прогнозируем риск...
              </>
            ) : (
              <>
                <UserCheck style={{ width: '20px', height: '20px' }} />
                Спрогнозировать риск реадмиссии
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
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
            Результат анализа рисков
          </h3>
          <MacOSButton
            onClick={exportResult}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <Download style={{ width: '16px', height: '16px' }} />
            Экспорт
          </MacOSButton>
        </div>

        {/* Специальное отображение для оценки рисков пациента */}
        {activeTab === 'patient-risk' && result.overall_risk_assessment && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <MacOSCard style={{ 
              padding: '16px',
              backgroundColor: getRiskColor(result.overall_risk_assessment.risk_level).backgroundColor,
              border: `1px solid ${getRiskColor(result.overall_risk_assessment.risk_level).borderColor}`
            }}>
              <h4 style={{ 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: getRiskColor(result.overall_risk_assessment.risk_level).textColor,
                margin: '0 0 8px 0'
              }}>
                Общая оценка риска
              </h4>
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', 
                gap: '16px',
                fontSize: 'var(--mac-font-size-sm)'
              }}>
                <div>
                  <span style={{ fontWeight: 'var(--mac-font-weight-medium)', color: getRiskColor(result.overall_risk_assessment.risk_level).textColor }}>Уровень:</span>
                  <span style={{ marginLeft: '4px', color: getRiskColor(result.overall_risk_assessment.risk_level).textColor }}>
                    {result.overall_risk_assessment.risk_level}
                  </span>
                </div>
                <div>
                  <span style={{ fontWeight: 'var(--mac-font-weight-medium)', color: getRiskColor(result.overall_risk_assessment.risk_level).textColor }}>Балл:</span>
                  <span style={{ marginLeft: '4px', color: getRiskColor(result.overall_risk_assessment.risk_level).textColor }}>
                    {result.overall_risk_assessment.risk_score}
                  </span>
                </div>
                <div>
                  <span style={{ fontWeight: 'var(--mac-font-weight-medium)', color: getRiskColor(result.overall_risk_assessment.risk_level).textColor }}>Достоверность:</span>
                  <span style={{ marginLeft: '4px', color: getRiskColor(result.overall_risk_assessment.risk_level).textColor }}>
                    {result.overall_risk_assessment.confidence_level}
                  </span>
                </div>
                <div>
                  <span style={{ fontWeight: 'var(--mac-font-weight-medium)', color: getRiskColor(result.overall_risk_assessment.risk_level).textColor }}>Дата:</span>
                  <span style={{ marginLeft: '4px', color: getRiskColor(result.overall_risk_assessment.risk_level).textColor }}>
                    {result.overall_risk_assessment.assessment_date}
                  </span>
                </div>
              </div>
            </MacOSCard>

            {result.risk_categories && (
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                gap: '16px' 
              }}>
                {Object.entries(result.risk_categories).map(([category, data]) => (
                  <MacOSCard key={category} style={{ 
                    padding: '12px',
                    backgroundColor: getRiskColor(data.level).backgroundColor,
                    border: `1px solid ${getRiskColor(data.level).borderColor}`
                  }}>
                    <h5 style={{ 
                      fontWeight: 'var(--mac-font-weight-medium)', 
                      color: getRiskColor(data.level).textColor,
                      margin: '0 0 4px 0',
                      fontSize: 'var(--mac-font-size-sm)',
                      textTransform: 'capitalize'
                    }}>
                      {category.replace(/_/g, ' ')}
                    </h5>
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-xs)', 
                      color: getRiskColor(data.level).textColor,
                      margin: '0 0 2px 0'
                    }}>
                      Уровень: {data.level}
                    </p>
                    <p style={{ 
                      fontSize: 'var(--mac-font-size-xs)', 
                      color: getRiskColor(data.level).textColor,
                      margin: 0
                    }}>
                      Балл: {data.score}
                    </p>
                  </MacOSCard>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Общее отображение для других результатов */}
        {activeTab !== 'patient-risk' && (
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
                <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                  {typeof value === 'object' && value !== null ? (
                    <pre style={{ 
                      whiteSpace: 'pre-wrap', 
                      backgroundColor: 'var(--mac-bg-secondary)', 
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
        )}
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
            <Shield style={{ width: '32px', height: '32px', color: 'var(--mac-danger)' }} />
            AI Оценка Рисков и Прогнозирование Осложнений
          </h2>
          <p style={{ 
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
            margin: 0
          }}>
            Комплексная оценка медицинских рисков с использованием искусственного интеллекта
          </p>
        </div>

        {/* Вкладки */}
        <div style={{ 
          display: 'flex', 
          marginBottom: '24px'
        }}>
          {tabs.map(tab => {
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
                  color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)',
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
                    e.target.style.color = 'var(--mac-text-secondary)';
                  }
                }}
              >
                <div style={{ 
                  width: '16px', 
                  height: '16px',
                  color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)'
                }}>
                  {tab.icon}
                </div>
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
              {tabs.find(tab => tab.id === activeTab)?.label}
            </h3>
            {activeTab === 'patient-risk' && renderPatientRiskForm()}
            {activeTab === 'complications' && renderComplicationForm()}
            {activeTab === 'mortality' && renderMortalityForm()}
            {activeTab === 'surgical' && renderSurgicalForm()}
            {activeTab === 'readmission' && renderReadmissionForm()}
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
          </div>
        </div>
      </MacOSCard>
    </div>
  );
};

export default RiskAssessment;



