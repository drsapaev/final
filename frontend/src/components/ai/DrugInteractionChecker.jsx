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
        return {
          backgroundColor: 'var(--mac-bg-primary)',
          borderColor: 'var(--mac-border)',
          textColor: 'var(--mac-danger)'
        };
      case 'значительное':
      case 'major':
        return {
          backgroundColor: 'var(--mac-bg-primary)',
          borderColor: 'var(--mac-border)',
          textColor: 'var(--mac-warning)'
        };
      case 'умеренное':
      case 'moderate':
        return {
          backgroundColor: 'var(--mac-bg-primary)',
          borderColor: 'var(--mac-border)',
          textColor: 'var(--mac-accent)'
        };
      case 'незначительное':
      case 'minor':
        return {
          backgroundColor: 'var(--mac-success-bg)',
          borderColor: 'var(--mac-success-border)',
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

  const renderInteractionsForm = () => (
    <MacOSCard style={{ padding: '24px' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <MacOSCard style={{ 
          padding: '16px', 
          backgroundColor: 'var(--mac-bg-primary)', 
          border: '1px solid var(--mac-border)' 
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h4 style={{ 
              fontSize: 'var(--mac-font-size-lg)', 
              fontWeight: 'var(--mac-font-weight-medium)', 
              color: 'var(--mac-danger)',
              margin: 0,
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <Pill style={{ width: '16px', height: '16px' }} />
              Препараты
            </h4>
            <MacOSButton
              onClick={addMedication}
              variant="outline"
              style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px' }}
            >
              <Plus style={{ width: '12px', height: '12px' }} />
              Добавить препарат
            </MacOSButton>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '200px', overflowY: 'auto' }}>
            {interactionData.medications.map((medication, index) => (
              <MacOSCard key={index} style={{ 
                padding: '12px', 
                backgroundColor: 'var(--mac-bg-primary)', 
                border: '1px solid var(--mac-border)' 
              }}>
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', 
                  gap: '12px',
                  alignItems: 'center'
                }}>
                  <MacOSInput
                    type="text"
                    placeholder="Название препарата"
                    value={medication.name}
                    onChange={(e) => updateMedication(index, 'name', e.target.value)}
                    style={{ fontSize: 'var(--mac-font-size-xs)' }}
                  />
                  <MacOSInput
                    type="text"
                    placeholder="Дозировка"
                    value={medication.dosage}
                    onChange={(e) => updateMedication(index, 'dosage', e.target.value)}
                    style={{ fontSize: 'var(--mac-font-size-xs)' }}
                  />
                  <MacOSInput
                    type="text"
                    placeholder="Частота приема"
                    value={medication.frequency}
                    onChange={(e) => updateMedication(index, 'frequency', e.target.value)}
                    style={{ fontSize: 'var(--mac-font-size-xs)' }}
                  />
                  {interactionData.medications.length > 1 && (
                    <MacOSButton
                      onClick={() => removeMedication(index)}
                      variant="outline"
                      style={{ padding: '4px', minWidth: 'auto' }}
                    >
                      <Minus style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
                    </MacOSButton>
                  )}
                </div>
              </MacOSCard>
            ))}
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
            <User style={{ width: '16px', height: '16px' }} />
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
                value={interactionData.patient_profile.age}
                onChange={(e) => setInteractionData(prev => ({
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
                value={interactionData.patient_profile.gender}
                onChange={(e) => setInteractionData(prev => ({
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
                value={interactionData.patient_profile.weight}
                onChange={(e) => setInteractionData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, weight: e.target.value }
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
                Функция почек
              </label>
              <MacOSSelect
                value={interactionData.patient_profile.kidney_function}
                onChange={(e) => setInteractionData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, kidney_function: e.target.value }
                }))}
                options={[
                  { value: '', label: 'Выберите' },
                  { value: 'нормальная', label: 'Нормальная' },
                  { value: 'легкое снижение', label: 'Легкое снижение' },
                  { value: 'умеренное снижение', label: 'Умеренное снижение' },
                  { value: 'тяжелое снижение', label: 'Тяжелое снижение' }
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
            color: 'var(--mac-warning)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <AlertTriangle style={{ width: '16px', height: '16px' }} />
            Аллергии
          </h4>
          <MacOSInput
            type="text"
            value={interactionData.patient_profile.allergies.join(', ')}
            onChange={(e) => setInteractionData(prev => ({
              ...prev,
              patient_profile: { 
                ...prev.patient_profile, 
                allergies: e.target.value.split(',').map(item => item.trim()).filter(Boolean)
              }
            }))}
            placeholder="Например: пенициллин, аспирин"
            style={{ width: '100%' }}
          />
        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={() => handleSubmit('check-drug-interactions', interactionData)}
            disabled={loading || interactionData.medications.length < 2 || !interactionData.medications[0].name}
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
                Проверяем взаимодействия...
              </>
            ) : (
              <>
                <AlertTriangle style={{ width: '20px', height: '20px' }} />
                Проверить взаимодействия
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
  );

  const renderSafetyForm = () => (
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
            Информация о препарате
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
                Препарат
              </label>
              <MacOSInput
                type="text"
                value={safetyData.medication.name}
                onChange={(e) => setSafetyData(prev => ({
                  ...prev,
                  medication: { ...prev.medication, name: e.target.value }
                }))}
                placeholder="Название препарата"
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
                Дозировка
              </label>
              <MacOSInput
                type="text"
                value={safetyData.medication.dosage}
                onChange={(e) => setSafetyData(prev => ({
                  ...prev,
                  medication: { ...prev.medication, dosage: e.target.value }
                }))}
                placeholder="Например: 10 мг"
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
                Частота
              </label>
              <MacOSInput
                type="text"
                value={safetyData.medication.frequency}
                onChange={(e) => setSafetyData(prev => ({
                  ...prev,
                  medication: { ...prev.medication, frequency: e.target.value }
                }))}
                placeholder="Например: 2 раза в день"
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
            <User style={{ width: '16px', height: '16px' }} />
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
                value={safetyData.patient_profile.age}
                onChange={(e) => setSafetyData(prev => ({
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
                value={safetyData.patient_profile.gender}
                onChange={(e) => setSafetyData(prev => ({
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
            <div>
              <label style={{ 
                display: 'block', 
                fontSize: 'var(--mac-font-size-sm)', 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-text-primary)', 
                marginBottom: '4px' 
              }}>
                Беременность
              </label>
              <MacOSSelect
                value={safetyData.patient_profile.pregnancy_status}
                onChange={(e) => setSafetyData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, pregnancy_status: e.target.value }
                }))}
                options={[
                  { value: '', label: 'Выберите' },
                  { value: 'не беременна', label: 'Не беременна' },
                  { value: 'беременна', label: 'Беременна' },
                  { value: 'планирует беременность', label: 'Планирует беременность' }
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
                Грудное вскармливание
              </label>
              <MacOSSelect
                value={safetyData.patient_profile.breastfeeding}
                onChange={(e) => setSafetyData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, breastfeeding: e.target.value }
                }))}
                options={[
                  { value: '', label: 'Выберите' },
                  { value: 'нет', label: 'Нет' },
                  { value: 'да', label: 'Да' }
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
            color: 'var(--mac-warning)',
            margin: '0 0 12px 0',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <AlertTriangle style={{ width: '16px', height: '16px' }} />
            Заболевания
          </h4>
          <MacOSInput
            type="text"
            value={safetyData.conditions.join(', ')}
            onChange={(e) => setSafetyData(prev => ({
              ...prev,
              conditions: e.target.value.split(',').map(item => item.trim()).filter(Boolean)
            }))}
            placeholder="Например: гипертония, диабет"
            style={{ width: '100%' }}
          />
        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={() => handleSubmit('analyze-drug-safety', safetyData)}
            disabled={loading || !safetyData.medication.name}
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
                Анализируем безопасность...
              </>
            ) : (
              <>
                <Shield style={{ width: '20px', height: '20px' }} />
                Проверить безопасность
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
  );

  const renderAlternativesForm = () => (
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
            <RefreshCw style={{ width: '16px', height: '16px' }} />
            Информация о замене
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
                Препарат для замены
              </label>
              <MacOSInput
                type="text"
                value={alternativesData.medication}
                onChange={(e) => setAlternativesData(prev => ({
                  ...prev,
                  medication: e.target.value
                }))}
                placeholder="Название препарата"
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
                Причина замены
              </label>
              <MacOSInput
                type="text"
                value={alternativesData.reason}
                onChange={(e) => setAlternativesData(prev => ({
                  ...prev,
                  reason: e.target.value
                }))}
                placeholder="Например: побочные эффекты, аллергия"
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
            <User style={{ width: '16px', height: '16px' }} />
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
                value={alternativesData.patient_profile.age}
                onChange={(e) => setAlternativesData(prev => ({
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
                value={alternativesData.patient_profile.gender}
                onChange={(e) => setAlternativesData(prev => ({
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
            onClick={() => handleSubmit('suggest-drug-alternatives', alternativesData)}
            disabled={loading || !alternativesData.medication || !alternativesData.reason}
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
                Ищем альтернативы...
              </>
            ) : (
              <>
                <RefreshCw style={{ width: '20px', height: '20px' }} />
                Найти альтернативы
              </>
            )}
          </MacOSButton>
        </div>
      </div>
    </MacOSCard>
  );

  const renderDosageForm = () => (
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
            <Calculator style={{ width: '16px', height: '16px' }} />
            Информация о препарате
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
                Препарат
              </label>
              <MacOSInput
                type="text"
                value={dosageData.medication}
                onChange={(e) => setDosageData(prev => ({
                  ...prev,
                  medication: e.target.value
                }))}
                placeholder="Название препарата"
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
                Показание
              </label>
              <MacOSInput
                type="text"
                value={dosageData.indication}
                onChange={(e) => setDosageData(prev => ({
                  ...prev,
                  indication: e.target.value
                }))}
                placeholder="Диагноз или показание"
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
            <User style={{ width: '16px', height: '16px' }} />
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
                value={dosageData.patient_profile.age}
                onChange={(e) => setDosageData(prev => ({
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
                Вес (кг)
              </label>
              <MacOSInput
                type="number"
                value={dosageData.patient_profile.weight}
                onChange={(e) => setDosageData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, weight: e.target.value }
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
                Рост (см)
              </label>
              <MacOSInput
                type="number"
                value={dosageData.patient_profile.height}
                onChange={(e) => setDosageData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, height: e.target.value }
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
            <AlertTriangle style={{ width: '16px', height: '16px' }} />
            Лабораторные показатели
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
                Креатинин (мкмоль/л)
              </label>
              <MacOSInput
                type="number"
                value={dosageData.patient_profile.creatinine}
                onChange={(e) => setDosageData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, creatinine: e.target.value }
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
                Клиренс креатинина (мл/мин)
              </label>
              <MacOSInput
                type="number"
                value={dosageData.patient_profile.creatinine_clearance}
                onChange={(e) => setDosageData(prev => ({
                  ...prev,
                  patient_profile: { ...prev.patient_profile, creatinine_clearance: e.target.value }
                }))}
                style={{ width: '100%' }}
              />
            </div>
          </div>
        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <MacOSButton
            onClick={() => handleSubmit('calculate-drug-dosage', dosageData)}
            disabled={loading || !dosageData.medication || !dosageData.indication}
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
                Рассчитываем дозировку...
              </>
            ) : (
              <>
                <Calculator style={{ width: '20px', height: '20px' }} />
                Рассчитать дозировку
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

        {/* Специальное отображение для взаимодействий */}
        {activeTab === 'interactions' && result.interactions && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <MacOSCard style={{ 
              padding: '16px',
              backgroundColor: 'var(--mac-accent-bg)',
              border: '1px solid var(--mac-accent-border)'
            }}>
              <h4 style={{ 
                fontWeight: 'var(--mac-font-weight-medium)', 
                color: 'var(--mac-accent)',
                margin: '0 0 8px 0'
              }}>
                Сводка взаимодействий
              </h4>
              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', 
                gap: '16px',
                fontSize: 'var(--mac-font-size-sm)'
              }}>
                <div>
                  <span style={{ color: 'var(--mac-accent)' }}>Всего:</span>
                  <span style={{ marginLeft: '4px', fontWeight: 'var(--mac-font-weight-medium)' }}>
                    {result.interaction_summary?.total_interactions || 0}
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--mac-danger)' }}>Критические:</span>
                  <span style={{ marginLeft: '4px', fontWeight: 'var(--mac-font-weight-medium)' }}>
                    {result.interaction_summary?.severity_distribution?.critical || 0}
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--mac-warning)' }}>Значительные:</span>
                  <span style={{ marginLeft: '4px', fontWeight: 'var(--mac-font-weight-medium)' }}>
                    {result.interaction_summary?.severity_distribution?.major || 0}
                  </span>
                </div>
                <div>
                  <span style={{ color: 'var(--mac-accent)' }}>Умеренные:</span>
                  <span style={{ marginLeft: '4px', fontWeight: 'var(--mac-font-weight-medium)' }}>
                    {result.interaction_summary?.severity_distribution?.moderate || 0}
                  </span>
                </div>
              </div>
            </MacOSCard>

            {result.interactions.map((interaction, index) => (
              <MacOSCard key={index} style={{ 
                padding: '16px',
                backgroundColor: getSeverityColor(interaction.severity).backgroundColor,
                border: `1px solid ${getSeverityColor(interaction.severity).borderColor}`
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <h5 style={{ 
                    fontWeight: 'var(--mac-font-weight-medium)',
                    color: getSeverityColor(interaction.severity).textColor,
                    margin: 0
                  }}>
                    {interaction.drug_1} ↔ {interaction.drug_2}
                  </h5>
                  <MacOSBadge style={{ 
                    backgroundColor: getSeverityColor(interaction.severity).textColor,
                    color: 'white',
                    fontSize: 'var(--mac-font-size-xs)'
                  }}>
                    {interaction.severity}
                  </MacOSBadge>
                </div>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  marginBottom: '8px',
                  color: getSeverityColor(interaction.severity).textColor
                }}>
                  {interaction.clinical_effect}
                </p>
                <p style={{ 
                  fontSize: 'var(--mac-font-size-sm)', 
                  fontWeight: 'var(--mac-font-weight-medium)',
                  color: getSeverityColor(interaction.severity).textColor,
                  margin: 0
                }}>
                  Управление: {interaction.management}
                </p>
              </MacOSCard>
            ))}
          </div>
        )}

        {/* Общее отображение для других результатов */}
        {activeTab !== 'interactions' && (
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
            <Pill style={{ width: '32px', height: '32px', color: 'var(--mac-accent)' }} />
            AI Проверка Лекарственных Взаимодействий
          </h2>
          <p style={{ 
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
            margin: 0
          }}>
            Анализ безопасности препаратов, взаимодействий и расчет дозировок
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
            {activeTab === 'interactions' && renderInteractionsForm()}
            {activeTab === 'safety' && renderSafetyForm()}
            {activeTab === 'alternatives' && renderAlternativesForm()}
            {activeTab === 'dosage' && renderDosageForm()}
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

export default DrugInteractionChecker;



