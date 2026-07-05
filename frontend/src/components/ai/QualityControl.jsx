import { useState } from 'react';
import {
  MacOSCard,
  Button,
  Input,
  Select,
  Textarea,
  Checkbox,
} from '../ui/macos';
import {
  FileCheck,
  AlertTriangle,
  CheckCircle,
  XCircle,

  Loader,
  Download,
  Copy,
  Plus,
  Minus,
  Search,
  Shield,
  Activity,
  ClipboardCheck,
  TrendingUp,
  Target,
  Zap } from
'lucide-react';
import { toast } from 'react-toastify';
import { api } from '../../api/client';

import logger from '../../utils/logger';

const parseOptionalInteger = (value) => {
  if (value === '') return '';
  const parsed = parseInt(value, 10);
  return Number.isNaN(parsed) ? '' : parsed;
};

const parseCommaSeparated = (value) =>
  value.
    split(',').
    map((item) => item.trim()).
    filter(Boolean);

const QualityControl = () => {
  const [activeTab, setActiveTab] = useState('quality-analysis');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Состояния для анализа качества документации
  const [medicalRecords, setMedicalRecords] = useState([]);
  const [qualityStandards, setQualityStandards] = useState({
    completeness_threshold: 90,
    required_signatures: true,
    icd_coding_required: true,
    documentation_timeliness: 24
  });

  // Состояния для выявления пробелов
  const [patientRecord, setPatientRecord] = useState({
    patient_id: '',
    name: '',
    diagnosis: '',
    symptoms: ''
  });
  const [requiredFields, setRequiredFields] = useState([
  'diagnosis', 'symptoms', 'treatment', 'allergies', 'vital_signs', 'family_history']
  );

  // Состояния для предложений улучшений
  const [recordAnalysis, setRecordAnalysis] = useState({
    completeness_score: '',
    missing_fields: [],
    quality_issues: []
  });
  const [bestPractices, setBestPractices] = useState({
    documentation_standards: '',
    template_usage: false,
    real_time_documentation: false,
    quality_metrics: []
  });

  // Состояния для валидации клинической согласованности
  const [diagnosis, setDiagnosis] = useState('');
  const [symptoms, setSymptoms] = useState([]);
  const [treatment, setTreatment] = useState({
    medications: [],
    lifestyle: []
  });

  // Состояния для аудита безопасности назначений
  const [prescriptions, setPrescriptions] = useState([]);
  const [patientProfile, setPatientProfile] = useState({
    age: '',
    gender: '',
    weight: '',
    allergies: [],
    comorbidities: [],
    current_medications: []
  });

  const tabs = [
  { id: 'quality-analysis', label: 'Анализ качества', icon: FileCheck },
  { id: 'gaps-detection', label: 'Выявление пробелов', icon: Search },
  { id: 'improvements', label: 'Предложения улучшений', icon: TrendingUp },
  { id: 'consistency', label: 'Клиническая согласованность', icon: Target },
  { id: 'prescription-safety', label: 'Безопасность назначений', icon: Shield }];


  const handleSubmit = async () => {
    setLoading(true);
    setResult(null);
    setError(null);

    let endpoint = '';
    let data = {};

    try {
      switch (activeTab) {
        case 'quality-analysis':
          endpoint = '/ai/analyze-documentation-quality';
          data = {
            medical_records: medicalRecords,
            quality_standards: qualityStandards
          };
          break;
        case 'gaps-detection':
          endpoint = '/ai/detect-documentation-gaps';
          data = {
            patient_record: patientRecord,
            required_fields: requiredFields
          };
          break;
        case 'improvements':
          endpoint = '/ai/suggest-documentation-improvements';
          data = {
            record_analysis: recordAnalysis,
            best_practices: bestPractices
          };
          break;
        case 'consistency':
          endpoint = '/ai/validate-clinical-consistency';
          data = {
            diagnosis: diagnosis,
            symptoms: symptoms,
            treatment: treatment
          };
          break;
        case 'prescription-safety':
          endpoint = '/ai/audit-prescription-safety';
          data = {
            prescriptions: prescriptions,
            patient_profile: patientProfile
          };
          break;
        default:
          throw new Error('Неизвестный тип запроса');
      }

      const response = await api.post(endpoint, data);
      setResult(response.data);
      toast.success('AI анализ качества успешно выполнен!');
    } catch (err) {
      toast.error('Ошибка при выполнении AI анализа качества.');
      logger.error('AI quality control error:', err);
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

    const exportFileDefaultName = `quality_control_${activeTab}_${new Date().toISOString().split('T')[0]}.json`;

    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const addMedicalRecord = () => {
    setMedicalRecords((prev) => [
    ...prev,
    { id: Date.now().toString(), type: 'consultation', diagnosis: '', treatment: '', symptoms: '' }]
    );
  };

  const removeMedicalRecord = (index) => {
    setMedicalRecords((prev) => prev.filter((_, i) => i !== index));
  };

  const addRequiredField = () => {
    setRequiredFields((prev) => [...prev, '']);
  };

  const removeRequiredField = (index) => {
    setRequiredFields((prev) => prev.filter((_, i) => i !== index));
  };

  const addSymptom = () => {
    setSymptoms((prev) => [...prev, '']);
  };

  const removeSymptom = (index) => {
    setSymptoms((prev) => prev.filter((_, i) => i !== index));
  };

  const addPrescription = () => {
    setPrescriptions((prev) => [
    ...prev,
    { medication: '', dosage: '', frequency: '', duration: '' }]
    );
  };

  const removePrescription = (index) => {
    setPrescriptions((prev) => prev.filter((_, i) => i !== index));
  };

  const renderQualityAnalysis = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{
      padding: '16px',
      backgroundColor: 'var(--mac-info-bg)',
      border: '1px solid var(--mac-info-border)'
    }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-info)',
          margin: 0,
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
            <FileCheck style={{ width: '16px', height: '16px' }} />
            Медицинские записи для анализа
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
          {medicalRecords.map((record, index) =>
        <div key={record.id} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <Select
            value={record.type}
            onChange={(e) => {
              const newRecords = [...medicalRecords];
              newRecords[index].type = e.target.value;
              setMedicalRecords(newRecords);
            }}
            options={[
            { value: 'consultation', label: 'Консультация' },
            { value: 'procedure', label: 'Процедура' },
            { value: 'discharge', label: 'Выписка' },
            { value: 'prescription', label: 'Рецепт' }]
            }
            style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="text"
            value={record.diagnosis}
            onChange={(e) => {
              const newRecords = [...medicalRecords];
              newRecords[index].diagnosis = e.target.value;
              setMedicalRecords(newRecords);
            }}
            placeholder="Диагноз"
            style={{ flex: 2, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="text"
            value={record.treatment}
            onChange={(e) => {
              const newRecords = [...medicalRecords];
              newRecords[index].treatment = e.target.value;
              setMedicalRecords(newRecords);
            }}
            placeholder="Лечение"
            style={{ flex: 2, fontSize: 'var(--mac-font-size-xs)' }} />
          
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
          <ClipboardCheck style={{ width: '16px', height: '16px' }} />
          Стандарты качества
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
              Порог полноты (%)
            </label>
            <Input
            type="number"
            value={qualityStandards.completeness_threshold}
            onChange={(e) => setQualityStandards((prev) => ({ ...prev, completeness_threshold: parseInt(e.target.value) || 90 }))}
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
              Своевременность (часы)
            </label>
            <Input
            type="number"
            value={qualityStandards.documentation_timeliness}
            onChange={(e) => setQualityStandards((prev) => ({ ...prev, documentation_timeliness: parseInt(e.target.value) || 24 }))}
            style={{ width: '100%' }} />
          
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Checkbox
            id="required_signatures"
            checked={qualityStandards.required_signatures}
            onChange={(e) => setQualityStandards((prev) => ({ ...prev, required_signatures: e.target.checked }))} />
          
            <label htmlFor="required_signatures" style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
              Обязательные подписи
            </label>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Checkbox
            id="icd_coding_required"
            checked={qualityStandards.icd_coding_required}
            onChange={(e) => setQualityStandards((prev) => ({ ...prev, icd_coding_required: e.target.checked }))} />
          
            <label htmlFor="icd_coding_required" style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
              Обязательное кодирование МКБ
            </label>
          </div>
        </div>
      </MacOSCard>
    </div>;


  const renderGapsDetection = () =>
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
          Медицинская запись пациента
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
              ID пациента
            </label>
            <Input
            type="text"
            value={patientRecord.patient_id}
            onChange={(e) => setPatientRecord((prev) => ({ ...prev, patient_id: e.target.value }))}
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
              ФИО пациента
            </label>
            <Input
            type="text"
            value={patientRecord.name}
            onChange={(e) => setPatientRecord((prev) => ({ ...prev, name: e.target.value }))}
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
            value={patientRecord.diagnosis}
            onChange={(e) => setPatientRecord((prev) => ({ ...prev, diagnosis: e.target.value }))}
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
              Симптомы
            </label>
            <Input
            type="text"
            value={patientRecord.symptoms}
            onChange={(e) => setPatientRecord((prev) => ({ ...prev, symptoms: e.target.value }))}
            style={{ width: '100%' }} />
          
          </div>
        </div>
      </MacOSCard>

      <MacOSCard style={{
      padding: '16px',
      backgroundColor: 'var(--mac-accent-bg)',
      border: '1px solid var(--mac-accent-border)'
    }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h4 style={{
          fontWeight: 'var(--mac-font-weight-medium)',
          color: 'var(--mac-accent)',
          margin: 0,
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
            <Search style={{ width: '16px', height: '16px' }} />
            Обязательные поля для проверки
          </h4>
          <Button
          onClick={addRequiredField}
          variant="outline"
          style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить поле
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '128px', overflowY: 'auto' }}>
          {requiredFields.map((field, index) =>
        <div key={index} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <Input
            type="text"
            value={field}
            onChange={(e) => {
              const newFields = [...requiredFields];
              newFields[index] = e.target.value;
              setRequiredFields(newFields);
            }}
            placeholder="Название поля"
            style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Button
            type="button"
            title="Remove required field"
            aria-label={`Remove required field ${index + 1}`}
            onClick={() => removeRequiredField(index)}
            variant="outline"
            style={{ padding: '4px', minWidth: 'auto' }}>
            
                <Minus aria-hidden="true" style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
              </Button>
            </div>
        )}
        </div>
      </MacOSCard>
    </div>;


  const renderImprovements = () =>
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
          <TrendingUp style={{ width: '16px', height: '16px' }} />
          Анализ текущего состояния
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
              Оценка полноты (%)
            </label>
            <Input
            type="number"
            value={recordAnalysis.completeness_score}
            onChange={(e) => setRecordAnalysis((prev) => ({ ...prev, completeness_score: parseOptionalInteger(e.target.value) }))}
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
              Отсутствующие поля
            </label>
            <Input
            type="text"
            value={recordAnalysis.missing_fields.join(', ')}
            onChange={(e) => setRecordAnalysis((prev) => ({ ...prev, missing_fields: parseCommaSeparated(e.target.value) }))}
            placeholder="Через запятую"
            style={{ width: '100%' }} />
          
          </div>
        </div>
      </MacOSCard>

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
          <Target style={{ width: '16px', height: '16px' }} />
          Лучшие практики
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
              Стандарт документации
            </label>
            <Select
            value={bestPractices.documentation_standards}
            onChange={(e) => setBestPractices((prev) => ({ ...prev, documentation_standards: e.target.value }))}
            placeholder="Выберите стандарт"
            options={[
            { value: 'WHO guidelines', label: 'WHO guidelines' },
            { value: 'HL7 FHIR', label: 'HL7 FHIR' },
            { value: 'ICD-11', label: 'ICD-11' },
            { value: 'SNOMED CT', label: 'SNOMED CT' }]
            }
            style={{ width: '100%' }} />
          
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Checkbox
            id="template_usage"
            checked={bestPractices.template_usage}
            onChange={(e) => setBestPractices((prev) => ({ ...prev, template_usage: e.target.checked }))} />
          
            <label htmlFor="template_usage" style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
              Использование шаблонов
            </label>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Checkbox
            id="real_time_documentation"
            checked={bestPractices.real_time_documentation}
            onChange={(e) => setBestPractices((prev) => ({ ...prev, real_time_documentation: e.target.checked }))} />
          
            <label htmlFor="real_time_documentation" style={{
            fontSize: 'var(--mac-font-size-sm)',
            color: 'var(--mac-text-primary)',
            margin: 0
          }}>
              Документирование в реальном времени
            </label>
          </div>
        </div>
      </MacOSCard>
    </div>;


  const renderConsistency = () =>
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
          <Target style={{ width: '16px', height: '16px' }} />
          Клинические данные
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
              Диагноз
            </label>
            <Input
            type="text"
            value={diagnosis}
            onChange={(e) => setDiagnosis(e.target.value)}
            style={{ width: '100%' }} />
          
          </div>
          
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <label style={{
              fontSize: 'var(--mac-font-size-sm)',
              fontWeight: 'var(--mac-font-weight-medium)',
              color: 'var(--mac-text-primary)',
              margin: 0
            }}>
                Симптомы
              </label>
              <Button
              onClick={addSymptom}
              variant="outline"
              style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px' }}>
              
                <Plus style={{ width: '12px', height: '12px' }} />
                Добавить
              </Button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '96px', overflowY: 'auto' }}>
              {symptoms.map((symptom, index) =>
            <div key={index} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <Input
                type="text"
                value={symptom}
                onChange={(e) => {
                  const newSymptoms = [...symptoms];
                  newSymptoms[index] = e.target.value;
                  setSymptoms(newSymptoms);
                }}
                placeholder="Симптом"
                style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
              
                  <Button
                type="button"
                title="Remove symptom"
                aria-label={`Remove symptom ${index + 1}`}
                onClick={() => removeSymptom(index)}
                variant="outline"
                style={{ padding: '4px', minWidth: 'auto' }}>
                
                    <Minus aria-hidden="true" style={{ width: '16px', height: '16px', color: 'var(--mac-danger)' }} />
                  </Button>
                </div>
            )}
            </div>
          </div>

          <div>
            <label style={{
            display: 'block',
            fontSize: 'var(--mac-font-size-sm)',
            fontWeight: 'var(--mac-font-weight-medium)',
            color: 'var(--mac-text-primary)',
            marginBottom: '4px'
          }}>
              Лечение (JSON)
            </label>
            <Textarea
            value={JSON.stringify(treatment, null, 2)}
            onChange={(e) => {
              try {
                setTreatment(JSON.parse(e.target.value));
              } catch {


                // Игнорируем ошибки парсинга во время ввода
              }}} style={{
              width: '100%',
              height: '96px',
              fontFamily: 'var(--mac-font-mono)',
              fontSize: 'var(--mac-font-size-xs)'
            }} />
          
          </div>
        </div>
      </MacOSCard>
    </div>;


  const renderPrescriptionSafety = () =>
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <MacOSCard style={{
      padding: '16px',
      backgroundColor: 'var(--mac-warning-bg)',
      border: '1px solid var(--mac-warning-border)'
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
            <Shield style={{ width: '16px', height: '16px' }} />
            Назначения для проверки
          </h4>
          <Button
          onClick={addPrescription}
          variant="outline"
          style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
          
            <Plus style={{ width: '16px', height: '16px' }} />
            Добавить назначение
          </Button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '160px', overflowY: 'auto' }}>
          {prescriptions.map((prescription, index) =>
        <div key={index} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <Input
            type="text"
            value={prescription.medication}
            onChange={(e) => {
              const newPrescriptions = [...prescriptions];
              newPrescriptions[index].medication = e.target.value;
              setPrescriptions(newPrescriptions);
            }}
            placeholder="Препарат"
            style={{ flex: 2, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="text"
            value={prescription.dosage}
            onChange={(e) => {
              const newPrescriptions = [...prescriptions];
              newPrescriptions[index].dosage = e.target.value;
              setPrescriptions(newPrescriptions);
            }}
            placeholder="Дозировка"
            style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Input
            type="text"
            value={prescription.frequency}
            onChange={(e) => {
              const newPrescriptions = [...prescriptions];
              newPrescriptions[index].frequency = e.target.value;
              setPrescriptions(newPrescriptions);
            }}
            placeholder="Частота"
            style={{ flex: 1, fontSize: 'var(--mac-font-size-xs)' }} />
          
              <Button
            type="button"
            title="Remove prescription"
            aria-label={`Remove prescription ${index + 1}`}
            onClick={() => removePrescription(index)}
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
          <Activity style={{ width: '16px', height: '16px' }} />
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
            <Input
            type="number"
            value={patientProfile.age}
            onChange={(e) => setPatientProfile((prev) => ({ ...prev, age: parseOptionalInteger(e.target.value) }))}
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
            value={patientProfile.gender}
            onChange={(e) => setPatientProfile((prev) => ({ ...prev, gender: e.target.value }))}
            placeholder="Выберите пол"
            options={[
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
            marginBottom: '4px'
          }}>
              Вес (кг)
            </label>
            <Input
            type="number"
            value={patientProfile.weight}
            onChange={(e) => setPatientProfile((prev) => ({ ...prev, weight: parseOptionalInteger(e.target.value) }))}
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
              Аллергии
            </label>
            <Input
            type="text"
            value={patientProfile.allergies.join(', ')}
            onChange={(e) => setPatientProfile((prev) => ({ ...prev, allergies: parseCommaSeparated(e.target.value) }))}
            placeholder="Через запятую"
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
              Сопутствующие заболевания
            </label>
            <Input
            type="text"
            value={patientProfile.comorbidities.join(', ')}
            onChange={(e) => setPatientProfile((prev) => ({ ...prev, comorbidities: parseCommaSeparated(e.target.value) }))}
            placeholder="Через запятую"
            style={{ width: '100%' }} />
          
          </div>
        </div>
      </MacOSCard>
    </div>;


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
            Результат анализа качества
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
              <div style={{ fontSize: 'var(--mac-font-size-sm)', color: 'var(--mac-text-secondary)' }}>
                {typeof value === 'object' && value !== null ?
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
            <ClipboardCheck style={{ width: '32px', height: '32px', color: 'var(--mac-accent)' }} />
            AI Контроль Качества Медицинских Записей
          </h2>
          <p style={{
            color: 'var(--mac-text-secondary)',
            fontSize: 'var(--mac-font-size-sm)',
            margin: 0
          }}>
            Анализ качества документации, выявление пробелов и предложение улучшений
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
                }}>
                
                <Icon style={{
                  width: '16px',
                  height: '16px',
                  color: isActive ? 'var(--mac-accent)' : 'var(--mac-text-secondary)'
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
            
            {activeTab === 'quality-analysis' && renderQualityAnalysis()}
            {activeTab === 'gaps-detection' && renderGapsDetection()}
            {activeTab === 'improvements' && renderImprovements()}
            {activeTab === 'consistency' && renderConsistency()}
            {activeTab === 'prescription-safety' && renderPrescriptionSafety()}
            
            <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'center' }}>
              <Button
                type="button"
                title={loading ? 'Running quality control AI analysis' : 'Run quality control AI analysis'}
                aria-label={loading ? 'Running quality control AI analysis' : 'Run quality control AI analysis'}
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
                    <Zap aria-hidden="true" style={{ width: '20px', height: '20px' }} />
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
              backgroundColor: 'var(--mac-error-bg)',
              border: '1px solid var(--mac-error-border)',
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

export default QualityControl;
