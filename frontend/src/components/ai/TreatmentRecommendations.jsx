import { useState } from 'react';
import {
  Heart,
  Pill,
  Activity,
  FileText,
  AlertCircle,
  CheckCircle,
  Loader,
  User,

  TrendingUp,
  Download,



  Target } from

'lucide-react';
import {
  MacOSCard,
  Button,
  Input,
  Select,
  Textarea,
} from '../ui/macos';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

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
  { id: 'lifestyle', label: 'Образ жизни', icon: <Activity className="w-4 h-4" /> }];


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
    const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);

    const exportFileDefaultName = `treatment_recommendations_${activeTab}_${new Date().toISOString().split('T')[0]}.json`;

    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const renderTreatmentPlanForm = () =>
  <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
        <MacOSCard style={{
        padding: 'var(--mac-spacing-4)',
        backgroundColor: 'var(--mac-bg-primary)',
        border: '1px solid var(--mac-border)'
      }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <User style={{ width: '16px', height: '16px' }} />
            Основные данные пациента
          </h4>
          <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 'var(--mac-spacing-4)'
        }}>
            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
                Возраст пациента
              </label>
              <Input
              type="number"
              value={treatmentPlanData.patient_data.age}
              onChange={(e) => setTreatmentPlanData((prev) => ({
                ...prev,
                patient_data: { ...prev.patient_data, age: e.target.value }
              }))}
              placeholder="Например: 45"
              style={{ width: '100%' }} />

            </div>
            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
                Пол
              </label>
              <Select
              value={treatmentPlanData.patient_data.gender}
              onChange={(e) => setTreatmentPlanData((prev) => ({
                ...prev,
                patient_data: { ...prev.patient_data, gender: e.target.value }
              }))}
              options={[
              { value: '', label: 'Выберите пол' },
              { value: 'мужской', label: 'Мужской' },
              { value: 'женский', label: 'Женский' }]
              }
              style={{ width: '100%' }} />

            </div>
            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
                Вес (кг)
              </label>
              <Input
              type="number"
              value={treatmentPlanData.patient_data.weight}
              onChange={(e) => setTreatmentPlanData((prev) => ({
                ...prev,
                patient_data: { ...prev.patient_data, weight: e.target.value }
              }))}
              placeholder="Например: 70"
              style={{ width: '100%' }} />

            </div>
            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
                Диагноз
              </label>
              <Input
              type="text"
              value={treatmentPlanData.diagnosis}
              onChange={(e) => setTreatmentPlanData((prev) => ({
                ...prev,
                diagnosis: e.target.value
              }))}
              placeholder="Основной диагноз"
              style={{ width: '100%' }} />

            </div>
          </div>
        </MacOSCard>

        <MacOSCard style={{
        padding: 'var(--mac-spacing-4)',
        backgroundColor: 'var(--mac-warning-bg)',
        border: '1px solid var(--mac-warning-border)'
      }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-warning)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <AlertCircle style={{ width: '16px', height: '16px' }} />
            Аллергии
          </h4>
          <Input
          type="text"
          value={treatmentPlanData.patient_data.allergies.join(', ')}
          onChange={(e) => setTreatmentPlanData((prev) => ({
            ...prev,
            patient_data: {
              ...prev.patient_data,
              allergies: e.target.value.split(',').map((item) => item.trim()).filter(Boolean)
            }
          }))}
          placeholder="Например: пенициллин, аспирин"
          style={{ width: '100%' }} />

        </MacOSCard>

        <MacOSCard style={{
        padding: 'var(--mac-spacing-4)',
        backgroundColor: 'var(--mac-error-bg)',
        border: '1px solid var(--mac-error-border)'
      }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-error)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <FileText style={{ width: '16px', height: '16px' }} />
            Сопутствующие заболевания
          </h4>
          <Input
          type="text"
          value={treatmentPlanData.patient_data.comorbidities.join(', ')}
          onChange={(e) => setTreatmentPlanData((prev) => ({
            ...prev,
            patient_data: {
              ...prev.patient_data,
              comorbidities: e.target.value.split(',').map((item) => item.trim()).filter(Boolean)
            }
          }))}
          placeholder="Например: гипертония, диабет"
          style={{ width: '100%' }} />

        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <Button
          type="button"
          title={loading ? 'Generating treatment plan' : 'Generate treatment plan'}
          aria-label={loading ? 'Generating treatment plan' : 'Generate treatment plan'}
          onClick={() => handleSubmit('generate-treatment-plan', treatmentPlanData)}
          disabled={loading || !treatmentPlanData.diagnosis}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            backgroundColor: 'var(--mac-accent-blue)',
            border: 'none'
          }}>

            {loading ?
          <>
                <Loader aria-hidden="true" style={{
              width: '20px',
              height: '20px',
              animation: 'spin 1s linear infinite'
            }} />
                Генерируем план...
              </> :

          <>
                <Target aria-hidden="true" style={{ width: '20px', height: '20px' }} />
                Создать план лечения
              </>
          }
          </Button>
        </div>
      </div>
    </MacOSCard>;


  const renderMedicationForm = () =>
  <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
        <MacOSCard style={{
        padding: 'var(--mac-spacing-4)',
        backgroundColor: 'var(--mac-success-bg)',
        border: '1px solid var(--mac-success-border)'
      }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-success)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <Pill style={{ width: '16px', height: '16px' }} />
            Информация о пациенте
          </h4>
          <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 'var(--mac-spacing-4)'
        }}>
            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
                Возраст
              </label>
              <Input
              type="number"
              value={medicationData.patient_profile.age}
              onChange={(e) => setMedicationData((prev) => ({
                ...prev,
                patient_profile: { ...prev.patient_profile, age: e.target.value }
              }))}
              style={{ width: '100%' }} />

            </div>
            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
                Состояние
              </label>
              <Input
              type="text"
              value={medicationData.condition}
              onChange={(e) => setMedicationData((prev) => ({
                ...prev,
                condition: e.target.value
              }))}
              placeholder="Диагноз или состояние"
              style={{ width: '100%' }} />

            </div>
          </div>
        </MacOSCard>

        <MacOSCard style={{
        padding: 'var(--mac-spacing-4)',
        backgroundColor: 'var(--mac-bg-primary)',
        border: '1px solid var(--mac-border)'
      }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <FileText style={{ width: '16px', height: '16px' }} />
            Текущие препараты
          </h4>
          <Textarea
          value={medicationData.current_medications.map((med) => `${med.name} ${med.dosage} ${med.frequency}`).join('\n')}
          onChange={(e) => {
            const lines = e.target.value.split('\n').filter(Boolean);
            const medications = lines.map((line) => {
              const parts = line.split(' ');
              return {
                name: parts[0] || '',
                dosage: parts[1] || '',
                frequency: parts.slice(2).join(' ') || ''
              };
            });
            setMedicationData((prev) => ({
              ...prev,
              current_medications: medications
            }));
          }}
          rows={4}
          placeholder="Например:&#10;Лизиноприл 10мг 1 раз в день&#10;Метформин 500мг 2 раза в день"
          style={{ width: '100%' }} />

        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <Button
          type="button"
          title={loading ? 'Optimizing medication therapy' : 'Optimize medication therapy'}
          aria-label={loading ? 'Optimizing medication therapy' : 'Optimize medication therapy'}
          onClick={() => handleSubmit('optimize-medication', medicationData)}
          disabled={loading || !medicationData.condition}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            backgroundColor: 'var(--mac-success)',
            border: 'none'
          }}>

            {loading ?
          <>
                <Loader aria-hidden="true" style={{
              width: '20px',
              height: '20px',
              animation: 'spin 1s linear infinite'
            }} />
                Оптимизируем...
              </> :

          <>
                <Pill aria-hidden="true" style={{ width: '20px', height: '20px' }} />
                Оптимизировать терапию
              </>
          }
          </Button>
        </div>
      </div>
    </MacOSCard>;


  const renderEffectivenessForm = () =>
  <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
        <MacOSCard style={{
        padding: 'var(--mac-spacing-4)',
        backgroundColor: 'var(--mac-accent-bg)',
        border: '1px solid var(--mac-accent-border)'
      }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-accent-blue)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <TrendingUp style={{ width: '16px', height: '16px' }} />
            Текущие симптомы
          </h4>
          <Input
          type="text"
          value={effectivenessData.patient_response.symptoms.join(', ')}
          onChange={(e) => setEffectivenessData((prev) => ({
            ...prev,
            patient_response: {
              ...prev.patient_response,
              symptoms: e.target.value.split(',').map((item) => item.trim()).filter(Boolean)
            }
          }))}
          placeholder="Например: головная боль, слабость"
          style={{ width: '100%' }} />

        </MacOSCard>

        <MacOSCard style={{
        padding: 'var(--mac-spacing-4)',
        backgroundColor: 'var(--mac-bg-primary)',
        border: '1px solid var(--mac-border)'
      }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-text-primary)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <User style={{ width: '16px', height: '16px' }} />
            Оценка состояния пациента
          </h4>
          <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 'var(--mac-spacing-4)'
        }}>
            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
                Качество жизни (1-10)
              </label>
              <Input
              type="number"
              min="1"
              max="10"
              value={effectivenessData.patient_response.quality_of_life_score}
              onChange={(e) => setEffectivenessData((prev) => ({
                ...prev,
                patient_response: { ...prev.patient_response, quality_of_life_score: e.target.value }
              }))}
              style={{ width: '100%' }} />

            </div>
            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
                Приверженность лечению (%)
              </label>
              <Input
              type="number"
              min="0"
              max="100"
              value={effectivenessData.patient_response.adherence_rate}
              onChange={(e) => setEffectivenessData((prev) => ({
                ...prev,
                patient_response: { ...prev.patient_response, adherence_rate: e.target.value }
              }))}
              style={{ width: '100%' }} />

            </div>
          </div>
        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <Button
          type="button"
          title={loading ? 'Assessing treatment effectiveness' : 'Assess treatment effectiveness'}
          aria-label={loading ? 'Assessing treatment effectiveness' : 'Assess treatment effectiveness'}
          onClick={() => handleSubmit('assess-treatment-effectiveness', effectivenessData)}
          disabled={loading}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            backgroundColor: 'var(--mac-accent-blue)',
            border: 'none'
          }}>

            {loading ?
          <>
                <Loader aria-hidden="true" style={{
              width: '20px',
              height: '20px',
              animation: 'spin 1s linear infinite'
            }} />
                Оцениваем...
              </> :

          <>
                <TrendingUp aria-hidden="true" style={{ width: '20px', height: '20px' }} />
                Оценить эффективность
              </>
          }
          </Button>
        </div>
      </div>
    </MacOSCard>;


  const renderLifestyleForm = () =>
  <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-6)' }}>
        <MacOSCard style={{
        padding: 'var(--mac-spacing-4)',
        backgroundColor: 'var(--mac-warning-bg)',
        border: '1px solid var(--mac-warning-border)'
      }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-warning)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <Activity style={{ width: '16px', height: '16px' }} />
            Основные параметры пациента
          </h4>
          <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 'var(--mac-spacing-4)'
        }}>
            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
                Возраст
              </label>
              <Input
              type="number"
              value={lifestyleData.patient_profile.age}
              onChange={(e) => setLifestyleData((prev) => ({
                ...prev,
                patient_profile: { ...prev.patient_profile, age: e.target.value }
              }))}
              style={{ width: '100%' }} />

            </div>
            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
                ИМТ
              </label>
              <Input
              type="number"
              step="0.1"
              value={lifestyleData.patient_profile.bmi}
              onChange={(e) => setLifestyleData((prev) => ({
                ...prev,
                patient_profile: { ...prev.patient_profile, bmi: e.target.value }
              }))}
              style={{ width: '100%' }} />

            </div>
            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
                Уровень активности
              </label>
              <Select
              value={lifestyleData.patient_profile.activity_level}
              onChange={(e) => setLifestyleData((prev) => ({
                ...prev,
                patient_profile: { ...prev.patient_profile, activity_level: e.target.value }
              }))}
              options={[
              { value: '', label: 'Выберите уровень' },
              { value: 'низкий', label: 'Низкий' },
              { value: 'умеренный', label: 'Умеренный' },
              { value: 'высокий', label: 'Высокий' }]
              }
              style={{ width: '100%' }} />

            </div>
            <div>
              <label style={{
              display: 'block',
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              marginBottom: 'var(--mac-spacing-1)'
            }}>
                Курение
              </label>
              <Select
              value={lifestyleData.patient_profile.smoking_status}
              onChange={(e) => setLifestyleData((prev) => ({
                ...prev,
                patient_profile: { ...prev.patient_profile, smoking_status: e.target.value }
              }))}
              options={[
              { value: '', label: 'Выберите статус' },
              { value: 'не курит', label: 'Не курит' },
              { value: 'курит', label: 'Курит' },
              { value: 'бросил', label: 'Бросил' }]
              }
              style={{ width: '100%' }} />

            </div>
          </div>
        </MacOSCard>

        <MacOSCard style={{
        padding: 'var(--mac-spacing-4)',
        backgroundColor: 'var(--mac-error-bg)',
        border: '1px solid var(--mac-error-border)'
      }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-error)',
          margin: '0 0 12px 0',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--mac-spacing-2)'
        }}>
            <AlertCircle style={{ width: '16px', height: '16px' }} />
            Заболевания
          </h4>
          <Input
          type="text"
          value={lifestyleData.conditions.join(', ')}
          onChange={(e) => setLifestyleData((prev) => ({
            ...prev,
            conditions: e.target.value.split(',').map((item) => item.trim()).filter(Boolean)
          }))}
          placeholder="Например: гипертония, диабет"
          style={{ width: '100%' }} />

        </MacOSCard>

        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <Button
          type="button"
          title={loading ? 'Generating lifestyle recommendations' : 'Get lifestyle recommendations'}
          aria-label={loading ? 'Generating lifestyle recommendations' : 'Get lifestyle recommendations'}
          onClick={() => handleSubmit('suggest-lifestyle-modifications', lifestyleData)}
          disabled={loading}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)',
            backgroundColor: 'var(--mac-warning)',
            border: 'none'
          }}>

            {loading ?
          <>
                <Loader aria-hidden="true" style={{
              width: '20px',
              height: '20px',
              animation: 'spin 1s linear infinite'
            }} />
                Генерируем рекомендации...
              </> :

          <>
                <Activity aria-hidden="true" style={{ width: '20px', height: '20px' }} />
                Получить рекомендации
              </>
          }
          </Button>
        </div>
      </div>
    </MacOSCard>;


  const renderResult = () => {
    if (!result) return null;

    if (result.error) {
      return (
        <MacOSCard style={{
          padding: 'var(--mac-spacing-4)',
          backgroundColor: 'var(--mac-error-bg)',
          border: '1px solid var(--mac-error-border)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-2)' }}>
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
            marginTop: 'var(--mac-spacing-2)',
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-error)',
            margin: '8px 0 0 0'
          }}>
            {result.error}
          </p>
        </MacOSCard>);

    }

    return (
      <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--mac-spacing-4)' }}>
          <h3 style={{
            fontSize: 'var(--mac-font-size-lg)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            margin: 0,
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-2)'
          }}>
            <CheckCircle style={{ width: '20px', height: '20px', color: 'var(--mac-success)' }} />
            Результат анализа
          </h3>
          <Button
            onClick={exportResult}
            variant="outline"
            style={{ display: 'flex', alignItems: 'center', gap: 'var(--mac-spacing-1)' }}>

            <Download style={{ width: '16px', height: '16px' }} />
            Экспорт
          </Button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-4)' }}>
          {Object.entries(result).map(([key, value]) =>
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
                {typeof value === 'object' && value !== null ?
              <pre style={{
                whiteSpace: 'pre-wrap',
                backgroundColor: 'var(--mac-bg-secondary)',
                padding: 'var(--mac-spacing-2)',
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
      padding: 'var(--mac-spacing-6)',
      backgroundColor: 'var(--mac-bg-primary)',
      minHeight: '100vh'
    }}>
      <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
        {/* Заголовок */}
        <div style={{
          paddingBottom: '24px',
          borderBottom: '1px solid var(--mac-border)',
          marginBottom: 'var(--mac-spacing-6)'
        }}>
          <h2 style={{
            fontSize: 'var(--mac-font-size-2xl)',
            fontWeight: 'var(--mac-font-weight-semibold)',
            color: 'var(--mac-text-primary)',
            margin: '0 0 8px 0',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--mac-spacing-3)'
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
          marginBottom: 'var(--mac-spacing-6)'
        }}>
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  padding: 'var(--mac-spacing-3) var(--mac-spacing-5)',
                  border: 'none',
                  background: 'transparent',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--mac-spacing-2)',
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
                }}>

                <div style={{
                  width: '16px',
                  height: '16px',
                  color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
                }}>
                  {tab.icon}
                </div>
                {tab.label}
                {isActive &&
                <div style={{
                  position: 'absolute',
                  bottom: '0',
                  left: '0',
                  right: '0',
                  height: '3px',
                  backgroundColor: 'var(--mac-accent-blue)',
                  borderRadius: 'var(--mac-radius-sm) var(--mac-radius-sm) 0 0'
                }} />
                }
              </button>);

          })}
        </div>
        
        {/* Разделительная линия */}
        <div style={{
          borderBottom: '1px solid var(--mac-border)',
          marginBottom: 'var(--mac-spacing-6)'
        }} />

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
          gap: 'var(--mac-spacing-6)'
        }}>
          <div>
            <h3 style={{
              fontSize: 'var(--mac-font-size-lg)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              margin: '0 0 16px 0'
            }}>
              {tabs.find((tab) => tab.id === activeTab)?.label}
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
    </div>);

};

export default TreatmentRecommendations;
