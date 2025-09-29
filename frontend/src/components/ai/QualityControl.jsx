import React, { useState } from 'react';
import { 
  FileCheck, 
  AlertTriangle, 
  CheckCircle, 
  XCircle,
  Info,
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
  Zap
} from 'lucide-react';
import { toast } from 'react-toastify';
import api from '../../utils/api';

const QualityControl = () => {
  const [activeTab, setActiveTab] = useState('quality-analysis');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Состояния для анализа качества документации
  const [medicalRecords, setMedicalRecords] = useState([
    { id: '1', type: 'consultation', diagnosis: 'Гипертония', treatment: 'Каптоприл', symptoms: 'Головная боль' }
  ]);
  const [qualityStandards, setQualityStandards] = useState({
    completeness_threshold: 90,
    required_signatures: true,
    icd_coding_required: true,
    documentation_timeliness: 24
  });

  // Состояния для выявления пробелов
  const [patientRecord, setPatientRecord] = useState({
    patient_id: '12345',
    name: 'Иванов И.И.',
    diagnosis: 'Артериальная гипертензия',
    symptoms: 'Головная боль, головокружение'
  });
  const [requiredFields, setRequiredFields] = useState([
    'diagnosis', 'symptoms', 'treatment', 'allergies', 'vital_signs', 'family_history'
  ]);

  // Состояния для предложений улучшений
  const [recordAnalysis, setRecordAnalysis] = useState({
    completeness_score: 75,
    missing_fields: ['allergies', 'family_history'],
    quality_issues: ['incomplete_vital_signs', 'missing_icd_codes']
  });
  const [bestPractices, setBestPractices] = useState({
    documentation_standards: 'WHO guidelines',
    template_usage: true,
    real_time_documentation: true,
    quality_metrics: ['completeness', 'accuracy', 'timeliness']
  });

  // Состояния для валидации клинической согласованности
  const [diagnosis, setDiagnosis] = useState('Артериальная гипертензия I степени');
  const [symptoms, setSymptoms] = useState(['головная боль', 'головокружение', 'повышенное АД']);
  const [treatment, setTreatment] = useState({
    medications: [{ name: 'каптоприл', dosage: '25 мг', frequency: '2 раза в день' }],
    lifestyle: ['диета с ограничением соли', 'физические упражнения']
  });

  // Состояния для аудита безопасности назначений
  const [prescriptions, setPrescriptions] = useState([
    { medication: 'каптоприл', dosage: '25 мг', frequency: '2 раза в день', duration: '30 дней' }
  ]);
  const [patientProfile, setPatientProfile] = useState({
    age: 65,
    gender: 'мужской',
    weight: 80,
    allergies: ['пенициллин'],
    comorbidities: ['диабет 2 типа'],
    current_medications: []
  });

  const tabs = [
    { id: 'quality-analysis', label: 'Анализ качества', icon: <FileCheck className="w-4 h-4" /> },
    { id: 'gaps-detection', label: 'Выявление пробелов', icon: <Search className="w-4 h-4" /> },
    { id: 'improvements', label: 'Предложения улучшений', icon: <TrendingUp className="w-4 h-4" /> },
    { id: 'consistency', label: 'Клиническая согласованность', icon: <Target className="w-4 h-4" /> },
    { id: 'prescription-safety', label: 'Безопасность назначений', icon: <Shield className="w-4 h-4" /> }
  ];

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
      console.error('AI quality control error:', err);
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
    
    const exportFileDefaultName = `quality_control_${activeTab}_${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const addMedicalRecord = () => {
    setMedicalRecords(prev => [
      ...prev,
      { id: Date.now().toString(), type: 'consultation', diagnosis: '', treatment: '', symptoms: '' }
    ]);
  };

  const removeMedicalRecord = (index) => {
    setMedicalRecords(prev => prev.filter((_, i) => i !== index));
  };

  const addRequiredField = () => {
    setRequiredFields(prev => [...prev, '']);
  };

  const removeRequiredField = (index) => {
    setRequiredFields(prev => prev.filter((_, i) => i !== index));
  };

  const addSymptom = () => {
    setSymptoms(prev => [...prev, '']);
  };

  const removeSymptom = (index) => {
    setSymptoms(prev => prev.filter((_, i) => i !== index));
  };

  const addPrescription = () => {
    setPrescriptions(prev => [
      ...prev,
      { medication: '', dosage: '', frequency: '', duration: '' }
    ]);
  };

  const removePrescription = (index) => {
    setPrescriptions(prev => prev.filter((_, i) => i !== index));
  };

  const renderQualityAnalysis = () => (
    <div className="space-y-6">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-blue-900 flex items-center">
            <FileCheck className="w-4 h-4 mr-2" />
            Медицинские записи для анализа
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
          {medicalRecords.map((record, index) => (
            <div key={record.id} className="flex space-x-2 items-center">
              <select
                value={record.type}
                onChange={(e) => {
                  const newRecords = [...medicalRecords];
                  newRecords[index].type = e.target.value;
                  setMedicalRecords(newRecords);
                }}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
              >
                <option value="consultation">Консультация</option>
                <option value="procedure">Процедура</option>
                <option value="discharge">Выписка</option>
                <option value="prescription">Рецепт</option>
              </select>
              <input
                type="text"
                value={record.diagnosis}
                onChange={(e) => {
                  const newRecords = [...medicalRecords];
                  newRecords[index].diagnosis = e.target.value;
                  setMedicalRecords(newRecords);
                }}
                className="flex-2 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Диагноз"
              />
              <input
                type="text"
                value={record.treatment}
                onChange={(e) => {
                  const newRecords = [...medicalRecords];
                  newRecords[index].treatment = e.target.value;
                  setMedicalRecords(newRecords);
                }}
                className="flex-2 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Лечение"
              />
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

      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <h4 className="font-medium text-green-900 mb-3 flex items-center">
          <ClipboardCheck className="w-4 h-4 mr-2" />
          Стандарты качества
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Порог полноты (%)</label>
            <input
              type="number"
              value={qualityStandards.completeness_threshold}
              onChange={(e) => setQualityStandards(prev => ({ ...prev, completeness_threshold: parseInt(e.target.value) || 90 }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Своевременность (часы)</label>
            <input
              type="number"
              value={qualityStandards.documentation_timeliness}
              onChange={(e) => setQualityStandards(prev => ({ ...prev, documentation_timeliness: parseInt(e.target.value) || 24 }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="required_signatures"
              checked={qualityStandards.required_signatures}
              onChange={(e) => setQualityStandards(prev => ({ ...prev, required_signatures: e.target.checked }))}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label htmlFor="required_signatures" className="ml-2 text-sm text-gray-700">
              Обязательные подписи
            </label>
          </div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="icd_coding_required"
              checked={qualityStandards.icd_coding_required}
              onChange={(e) => setQualityStandards(prev => ({ ...prev, icd_coding_required: e.target.checked }))}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label htmlFor="icd_coding_required" className="ml-2 text-sm text-gray-700">
              Обязательное кодирование МКБ
            </label>
          </div>
        </div>
      </div>
    </div>
  );

  const renderGapsDetection = () => (
    <div className="space-y-6">
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <h4 className="font-medium text-yellow-900 mb-3 flex items-center">
          <Activity className="w-4 h-4 mr-2" />
          Медицинская запись пациента
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">ID пациента</label>
            <input
              type="text"
              value={patientRecord.patient_id}
              onChange={(e) => setPatientRecord(prev => ({ ...prev, patient_id: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">ФИО пациента</label>
            <input
              type="text"
              value={patientRecord.name}
              onChange={(e) => setPatientRecord(prev => ({ ...prev, name: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Диагноз</label>
            <input
              type="text"
              value={patientRecord.diagnosis}
              onChange={(e) => setPatientRecord(prev => ({ ...prev, diagnosis: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Симптомы</label>
            <input
              type="text"
              value={patientRecord.symptoms}
              onChange={(e) => setPatientRecord(prev => ({ ...prev, symptoms: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>

      <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-purple-900 flex items-center">
            <Search className="w-4 h-4 mr-2" />
            Обязательные поля для проверки
          </h4>
          <button
            onClick={addRequiredField}
            className="px-3 py-1 bg-purple-600 text-white rounded-md text-sm hover:bg-purple-700 flex items-center"
          >
            <Plus className="w-4 h-4 mr-1" />
            Добавить поле
          </button>
        </div>
        <div className="space-y-2 max-h-32 overflow-y-auto">
          {requiredFields.map((field, index) => (
            <div key={index} className="flex space-x-2 items-center">
              <input
                type="text"
                value={field}
                onChange={(e) => {
                  const newFields = [...requiredFields];
                  newFields[index] = e.target.value;
                  setRequiredFields(newFields);
                }}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Название поля"
              />
              <button
                onClick={() => removeRequiredField(index)}
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

  const renderImprovements = () => (
    <div className="space-y-6">
      <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
        <h4 className="font-medium text-indigo-900 mb-3 flex items-center">
          <TrendingUp className="w-4 h-4 mr-2" />
          Анализ текущего состояния
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Оценка полноты (%)</label>
            <input
              type="number"
              value={recordAnalysis.completeness_score}
              onChange={(e) => setRecordAnalysis(prev => ({ ...prev, completeness_score: parseInt(e.target.value) || 75 }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Отсутствующие поля</label>
            <input
              type="text"
              value={recordAnalysis.missing_fields.join(', ')}
              onChange={(e) => setRecordAnalysis(prev => ({ ...prev, missing_fields: e.target.value.split(',').map(f => f.trim()) }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Через запятую"
            />
          </div>
        </div>
      </div>

      <div className="bg-teal-50 border border-teal-200 rounded-lg p-4">
        <h4 className="font-medium text-teal-900 mb-3 flex items-center">
          <Target className="w-4 h-4 mr-2" />
          Лучшие практики
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Стандарт документации</label>
            <select
              value={bestPractices.documentation_standards}
              onChange={(e) => setBestPractices(prev => ({ ...prev, documentation_standards: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="WHO guidelines">WHO guidelines</option>
              <option value="HL7 FHIR">HL7 FHIR</option>
              <option value="ICD-11">ICD-11</option>
              <option value="SNOMED CT">SNOMED CT</option>
            </select>
          </div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="template_usage"
              checked={bestPractices.template_usage}
              onChange={(e) => setBestPractices(prev => ({ ...prev, template_usage: e.target.checked }))}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label htmlFor="template_usage" className="ml-2 text-sm text-gray-700">
              Использование шаблонов
            </label>
          </div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="real_time_documentation"
              checked={bestPractices.real_time_documentation}
              onChange={(e) => setBestPractices(prev => ({ ...prev, real_time_documentation: e.target.checked }))}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label htmlFor="real_time_documentation" className="ml-2 text-sm text-gray-700">
              Документирование в реальном времени
            </label>
          </div>
        </div>
      </div>
    </div>
  );

  const renderConsistency = () => (
    <div className="space-y-6">
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <h4 className="font-medium text-red-900 mb-3 flex items-center">
          <Target className="w-4 h-4 mr-2" />
          Клинические данные
        </h4>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Диагноз</label>
            <input
              type="text"
              value={diagnosis}
              onChange={(e) => setDiagnosis(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">Симптомы</label>
              <button
                onClick={addSymptom}
                className="px-2 py-1 bg-red-600 text-white rounded text-xs hover:bg-red-700 flex items-center"
              >
                <Plus className="w-3 h-3 mr-1" />
                Добавить
              </button>
            </div>
            <div className="space-y-2 max-h-24 overflow-y-auto">
              {symptoms.map((symptom, index) => (
                <div key={index} className="flex space-x-2 items-center">
                  <input
                    type="text"
                    value={symptom}
                    onChange={(e) => {
                      const newSymptoms = [...symptoms];
                      newSymptoms[index] = e.target.value;
                      setSymptoms(newSymptoms);
                    }}
                    className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
                    placeholder="Симптом"
                  />
                  <button
                    onClick={() => removeSymptom(index)}
                    className="p-1 text-red-600 hover:text-red-800"
                  >
                    <Minus className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Лечение (JSON)</label>
            <textarea
              value={JSON.stringify(treatment, null, 2)}
              onChange={(e) => {
                try {
                  setTreatment(JSON.parse(e.target.value));
                } catch (error) {
                  // Игнорируем ошибки парсинга во время ввода
                }
              }}
              className="w-full h-24 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
            />
          </div>
        </div>
      </div>
    </div>
  );

  const renderPrescriptionSafety = () => (
    <div className="space-y-6">
      <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-medium text-orange-900 flex items-center">
            <Shield className="w-4 h-4 mr-2" />
            Назначения для проверки
          </h4>
          <button
            onClick={addPrescription}
            className="px-3 py-1 bg-orange-600 text-white rounded-md text-sm hover:bg-orange-700 flex items-center"
          >
            <Plus className="w-4 h-4 mr-1" />
            Добавить назначение
          </button>
        </div>
        <div className="space-y-3 max-h-40 overflow-y-auto">
          {prescriptions.map((prescription, index) => (
            <div key={index} className="flex space-x-2 items-center">
              <input
                type="text"
                value={prescription.medication}
                onChange={(e) => {
                  const newPrescriptions = [...prescriptions];
                  newPrescriptions[index].medication = e.target.value;
                  setPrescriptions(newPrescriptions);
                }}
                className="flex-2 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Препарат"
              />
              <input
                type="text"
                value={prescription.dosage}
                onChange={(e) => {
                  const newPrescriptions = [...prescriptions];
                  newPrescriptions[index].dosage = e.target.value;
                  setPrescriptions(newPrescriptions);
                }}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Дозировка"
              />
              <input
                type="text"
                value={prescription.frequency}
                onChange={(e) => {
                  const newPrescriptions = [...prescriptions];
                  newPrescriptions[index].frequency = e.target.value;
                  setPrescriptions(newPrescriptions);
                }}
                className="flex-1 px-2 py-1 border border-gray-300 rounded text-sm"
                placeholder="Частота"
              />
              <button
                onClick={() => removePrescription(index)}
                className="p-1 text-red-600 hover:text-red-800"
              >
                <Minus className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-4">
        <h4 className="font-medium text-cyan-900 mb-3 flex items-center">
          <Activity className="w-4 h-4 mr-2" />
          Профиль пациента
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Возраст</label>
            <input
              type="number"
              value={patientProfile.age}
              onChange={(e) => setPatientProfile(prev => ({ ...prev, age: parseInt(e.target.value) || 0 }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Пол</label>
            <select
              value={patientProfile.gender}
              onChange={(e) => setPatientProfile(prev => ({ ...prev, gender: e.target.value }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="мужской">Мужской</option>
              <option value="женский">Женский</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Вес (кг)</label>
            <input
              type="number"
              value={patientProfile.weight}
              onChange={(e) => setPatientProfile(prev => ({ ...prev, weight: parseInt(e.target.value) || 0 }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Аллергии</label>
            <input
              type="text"
              value={patientProfile.allergies.join(', ')}
              onChange={(e) => setPatientProfile(prev => ({ ...prev, allergies: e.target.value.split(',').map(a => a.trim()) }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Через запятую"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Сопутствующие заболевания</label>
            <input
              type="text"
              value={patientProfile.comorbidities.join(', ')}
              onChange={(e) => setPatientProfile(prev => ({ ...prev, comorbidities: e.target.value.split(',').map(c => c.trim()) }))}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Через запятую"
            />
          </div>
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
            Результат анализа качества
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
            <ClipboardCheck className="h-6 w-6 text-blue-600 mr-2" />
            AI Контроль Качества Медицинских Записей
          </h2>
          <p className="mt-1 text-sm text-gray-600">
            Анализ качества документации, выявление пробелов и предложение улучшений
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
              
              {activeTab === 'quality-analysis' && renderQualityAnalysis()}
              {activeTab === 'gaps-detection' && renderGapsDetection()}
              {activeTab === 'improvements' && renderImprovements()}
              {activeTab === 'consistency' && renderConsistency()}
              {activeTab === 'prescription-safety' && renderPrescriptionSafety()}
              
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
                      <Zap className="h-5 w-5 mr-2" />
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

export default QualityControl;



