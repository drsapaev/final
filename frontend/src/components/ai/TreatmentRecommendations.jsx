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
      logger.error('Ошибка получения рекомендаций:', error);
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
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
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
            <User style={{ width: '16px', height: '16px' }} />
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
                Возраст пациента
              </label>
              <MacOSInput
                type="number"
                value={treatmentPlanData.patient_data.age}
                onChange={(e) => setTreatmentPlanData(prev => ({
                  ...prev,
                  patient_data: { ...prev.patient_data, age: e.target.value }
                }))}
                placeholder="Например: 45"
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
                value={treatmentPlanData.patient_data.gender}
                onChange={(e) => setTreatmentPlanData(prev => ({
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
                value={treatmentPlanData.patient_data.weight}
                onChange={(e) => setTreatmentPlanData(prev => ({
                  ...prev,
                  patient_data: { ...prev.patient_data, weight: e.target.value }
                }))}
                placeholder="Например: 70"
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
                value={treatmentPlanData.diagnosis}
                onChange={(e) => setTreatmentPlanData(prev => ({
                  ...prev,
                  diagnosis: e.target.value
                }))}
                placeholder="Основной диагноз"
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </MacOSCard>

        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-warning-bg)', 
          border: '1px solid var(--mac-warning-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-warning)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <AlertCircle style={{ width: '16px', height: '16px' }} />
            Аллергии
          </h4>
          <MacOSInput
            type="text"
            value={treatmentPlanData.patient_data.allergies.join(', ')}
            onChange={(e) => setTreatmentPlanData(prev => ({
              ...prev,
              patient_data: { 
                ...prev.patient_data, 
                allergies: e.target.value.split(',').map(item => item.trim()).filter(Boolean)
              }
            }))}
            placeholder="Например: пенициллин, аспирин"
            style={{ width: '100%' }}
          />
        </MacOSCard>

        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-error-bg)', 
          border: '1px solid var(--mac-error-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-error)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <FileText style={{ width: '16px', height: '16px' }} />
            Сопутствующие заболевания
          </h4>
          <MacOSInput
            type="text"
            value={treatmentPlanData.patient_data.comorbidities.join(', ')}
            onChange={(e) => setTreatmentPlanData(prev => ({
              ...prev,
              patient_data: { 
                ...prev.patient_data, 
                comorbidities: e.target.value.split(',').map(item => item.trim()).filter(Boolean)
              }
            }))}
            placeholder="Например: гипертония, диабет"
            style={{ width: '100%' }}
          />
        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={() => handleSubmit('generate-treatment-plan', treatmentPlanData)}
            disabled={loading || !treatmentPlanData.diagnosis}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              backgroundColor: 'var(--mac-accent-blue)',
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
                Генерируем план...
              </>
            ) : (
              <>
                <Target style={{ width: '20px', height: '20px' }} />
                Создать план лечения
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
  );

  const renderMedicationForm = () => (
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-success-bg)', 
          border: '1px solid var(--mac-success-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-success)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <Pill style={{ width: '16px', height: '16px' }} />
            Информация о пациенте
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
                value={medicationData.patient_profile.age}
                onChange={(e) => setMedicationData(prev => ({
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
                Состояние
              </label>
              <MacOSInput
                type="text"
                value={medicationData.condition}
                onChange={(e) => setMedicationData(prev => ({
                  ...prev,
                  condition: e.target.value
                }))}
                placeholder="Диагноз или состояние"
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
            <FileText style={{ width: '16px', height: '16px' }} />
            Текущие препараты
          </h4>
          <MacOSTextarea
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
            placeholder="Например:&#10;Лизиноприл 10мг 1 раз в день&#10;Метформин 500мг 2 раза в день"
            style={{ width: '100%' }}
          />
        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={() => handleSubmit('optimize-medication', medicationData)}
            disabled={loading || !medicationData.condition}
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
                Оптимизируем...
              </>
            ) : (
              <>
                <Pill style={{ width: '20px', height: '20px' }} />
                Оптимизировать терапию
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
  );

  const renderEffectivenessForm = () => (
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-accent-bg)', 
          border: '1px solid var(--mac-accent-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-accent-blue)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <TrendingUp style={{ width: '16px', height: '16px' }} />
            Текущие симптомы
          </h4>
          <MacOSInput
            type="text"
            value={effectivenessData.patient_response.symptoms.join(', ')}
            onChange={(e) => setEffectivenessData(prev => ({
              ...prev,
              patient_response: { 
                ...prev.patient_response, 
                symptoms: e.target.value.split(',').map(item => item.trim()).filter(Boolean)
              }
            }))}
            placeholder="Например: головная боль, слабость"
            style={{ width: '100%' }}
          />
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
            <User style={{ width: '16px', height: '16px' }} />
            Оценка состояния пациента
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
                Качество жизни (1-10)
              </label>
              <MacOSInput
                type="number"
                min="1"
                max="10"
                value={effectivenessData.patient_response.quality_of_life_score}
                onChange={(e) => setEffectivenessData(prev => ({
                  ...prev,
                  patient_response: { ...prev.patient_response, quality_of_life_score: e.target.value }
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
                Приверженность лечению (%)
              </label>
              <MacOSInput
                type="number"
                min="0"
                max="100"
                value={effectivenessData.patient_response.adherence_rate}
                onChange={(e) => setEffectivenessData(prev => ({
                  ...prev,
                  patient_response: { ...prev.patient_response, adherence_rate: e.target.value }
                }))}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={() => handleSubmit('assess-treatment-effectiveness', effectivenessData)}
            disabled={loading}
            style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px',
              backgroundColor: 'var(--mac-accent-blue)',
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
                Оцениваем...
              </>
            ) : (
              <>
                <TrendingUp style={{ width: '20px', height: '20px' }} />
                Оценить эффективность
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
  );

  const renderLifestyleForm = () => (
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-warning-bg)', 
          border: '1px solid var(--mac-warning-border)' 
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
            Основные параметры пациента
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
                value={lifestyleData.patient_profile.age}
                onChange={(e) => setLifestyleData(prev => ({
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
                ИМТ
              </label>
              <MacOSInput
                type="number"
                step="0.1"
                value={lifestyleData.patient_profile.bmi}
                onChange={(e) => setLifestyleData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, bmi: e.target.value }
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
                Уровень активности
              </label>
              <MacOSSelect
                value={lifestyleData.patient_profile.activity_level}
                onChange={(e) => setLifestyleData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, activity_level: e.target.value }
                }))}
                options={[
                  { value: '', label: 'Выберите уровень' },
                  { value: 'низкий', label: 'Низкий' },
                  { value: 'умеренный', label: 'Умеренный' },
                  { value: 'высокий', label: 'Высокий' }
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
                Курение
              </label>
              <MacOSSelect
                value={lifestyleData.patient_profile.smoking_status}
                onChange={(e) => setLifestyleData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, smoking_status: e.target.value }
                }))}
                options={[
                  { value: '', label: 'Выберите статус' },
                  { value: 'не курит', label: 'Не курит' },
                  { value: 'курит', label: 'Курит' },
                  { value: 'бросил', label: 'Бросил' }
                ]}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </MacOSCard>

        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-error-bg)', 
          border: '1px solid var(--mac-error-border)' 
        }}>
          <h4 style={{ 
            fontWeight: 'var(--mac-font-weight-medium)', 
            color: 'var(--mac-error)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <AlertCircle style={{ width: '16px', height: '16px' }} />
            Заболевания
          </h4>
          <MacOSInput
            type="text"
            value={lifestyleData.conditions.join(', ')}
            onChange={(e) => setLifestyleData(prev => ({
              ...prev,
              conditions: e.target.value.split(',').map(item => item.trim()).filter(Boolean)
            }))}
            placeholder="Например: гипертония, диабет"
            style={{ width: '100%' }}
          />
        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={() => handleSubmit('suggest-lifestyle-modifications', lifestyleData)}
            disabled={loading}
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
                Генерируем рекомендации...
              </>
            ) : (
              <>
                <Activity style={{ width: '20px', height: '20px' }} />
                Получить рекомендации
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
          backgroundColor: 'var(--mac-error-bg)', 
          border: '1px solid var(--mac-error-border)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <AlertCircle style={{ width: '20px', height: '20px', color: 'var(--mac-error)' }} />
            <h3 style={{ 
              fontSize: 'var(--mac-font-size-sm)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-error)',
              margin: 0
            }}>
              Ошибка
            </h3>
          </div>
          <p style={{ 
            marginTop: '8px',
            fontSize: 'var(--mac-font-size-sm)', 
            color: 'var(--mac-error)',
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
            Результат анализа
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

        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {Object.entries(result).map(([key, value]) => (
            <div key={key} style={{ 
              borderLeft: '4px solid var(--mac-accent-blue)', 
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
            <Heart style={{ width: '32px', height: '32px', color: 'var(--mac-error)' }} />
            AI Рекомендации Лечения
          </h2>
          <p style={{ 
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
            margin: 0
          }}>
            Персонализированные планы лечения и рекомендации на основе данных пациента
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
                  color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)',
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
                  color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
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
                    backgroundColor: 'var(--mac-accent-blue)',
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
            {activeTab === 'treatment-plan' && renderTreatmentPlanForm()}
            {activeTab === 'medication' && renderMedicationForm()}
            {activeTab === 'effectiveness' && renderEffectivenessForm()}
            {activeTab === 'lifestyle' && renderLifestyleForm()}
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

export default TreatmentRecommendations;

