/**
 * SingleSheetEMR - Один лист = один визит
 * 
 * ЗАКОН №1: Врач открывает пациента → сразу видит всю клиническую картину
 * 
 * Структура:
 * 1. ШАПКА (всегда видна, фиксирована) + СТАТУС ВИЗИТА
 * 2. ЖАЛОБЫ (1-3 строки)
 * 3. АНАМНЕЗ (сворачиваемый)
 * 4. ОБЪЕКТИВНО (чекбоксы + текст)
 * 5. ДИАГНОЗ (MKБ-10)
 * 6. ПЛАН (обследования, лечение, консультации)
 * 7. НАЗНАЧЕНИЯ
 * 
 * v2.0 - UX Improvements:
 * - Explicit visit status visible to doctor
 * - UX Telemetry for measuring actual usage
 * - Proper context/actions architecture
 * - No window.print() - use document generation
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import {
  Save,
  FileText,
  ChevronDown,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
  Brain,
  Printer,
  Clock,
  XCircle,
  Edit3,
  Copy } from
'lucide-react';
import './SingleSheetEMR.css';
import ComplaintsField from './ComplaintsField';
import EMRTextField from './EMRTextField';

import PrescriptionEditor from './PrescriptionEditor';
import ExaminationMatrix from './ExaminationMatrix';
import ICD10Autocomplete from './ICD10Autocomplete';
import { useEMRAI } from '../../hooks/useEMRAI';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import TreatmentTemplates from './TreatmentTemplates';
import logger from '../../utils/logger';

// ============================================
// VISIT STATUS - Клинический статус (врач видит всегда)
// ============================================
const VISIT_STATUS = {
  DRAFT: 'draft',
  IN_PROGRESS: 'in_progress',
  SIGNED: 'signed',
  CLOSED: 'closed'
};

const VISIT_STATUS_CONFIG = {
  [VISIT_STATUS.DRAFT]: {
    label: 'Черновик',
    icon: Edit3,
    color: '#ff9500',
    bgColor: 'rgba(255, 149, 0, 0.15)'
  },
  [VISIT_STATUS.IN_PROGRESS]: {
    label: 'В работе',
    icon: Clock,
    color: '#007aff',
    bgColor: 'rgba(0, 122, 255, 0.15)'
  },
  [VISIT_STATUS.SIGNED]: {
    label: 'Подписано',
    icon: CheckCircle,
    color: '#34c759',
    bgColor: 'rgba(52, 199, 89, 0.15)'
  },
  [VISIT_STATUS.CLOSED]: {
    label: 'Закрыто',
    icon: XCircle,
    color: '#8e8e93',
    bgColor: 'rgba(142, 142, 147, 0.15)'
  }
};

// ============================================
// UX TELEMETRY - Врачебные метрики
// ============================================
const createTelemetry = () => ({
  sessionStart: Date.now(),
  timeToFirstInput: null,
  totalEditTime: 0,
  fieldsTouched: new Set(),
  aiSuggestionsShown: 0,
  aiAccepted: 0,
  lastActivity: Date.now()
});

const useTelemetry = () => {
  const telemetryRef = useRef(createTelemetry());

  const recordFirstInput = useCallback(() => {
    if (telemetryRef.current.timeToFirstInput === null) {
      telemetryRef.current.timeToFirstInput = Date.now() - telemetryRef.current.sessionStart;
    }
  }, []);

  const recordFieldTouch = useCallback((fieldName) => {
    telemetryRef.current.fieldsTouched.add(fieldName);
    telemetryRef.current.lastActivity = Date.now();
    recordFirstInput();
  }, [recordFirstInput]);

  const recordAISuggestion = useCallback((accepted = false) => {
    telemetryRef.current.aiSuggestionsShown++;
    if (accepted) {
      telemetryRef.current.aiAccepted++;
    }
  }, []);

  const getTelemetry = useCallback(() => {
    const t = telemetryRef.current;
    return {
      timeToFirstInputMs: t.timeToFirstInput,
      totalSessionMs: Date.now() - t.sessionStart,
      fieldsTouched: t.fieldsTouched.size,
      aiSuggestionsShown: t.aiSuggestionsShown,
      aiAcceptRate: t.aiSuggestionsShown > 0 ?
      Math.round(t.aiAccepted / t.aiSuggestionsShown * 100) :
      0
    };
  }, []);

  return { recordFieldTouch, recordAISuggestion, getTelemetry };
};

// ============================================
// MOCK AI SERVICE - Универсальный для всех полей EMR
// В production: API к базе ранее заполненных EMR
// ============================================
const FIELD_TEMPLATES = {
  complaints: {
    'головн': [
    { id: 1, text: 'давящего характера, усиливается к вечеру, сопровождается шумом в ушах', source: 'Шаблон кардиология' },
    { id: 2, text: 'пульсирующая, в области висков, связана с повышением АД', source: '15 записей' },
    { id: 3, text: 'диффузная, умеренной интенсивности, купируется анальгетиками', source: '8 записей' }],

    'сердц': [
    { id: 1, text: 'давящего характера за грудиной, иррадиирует в левую руку, до 5 минут', source: 'Шаблон стенокардия' },
    { id: 2, text: 'колющие, в области верхушки, без иррадиации, не связаны с нагрузкой', source: '12 записей' }],

    'одышк': [
    { id: 1, text: 'при подъёме на 2 этаж, в покое не беспокоит', source: 'Шаблон ХСН' },
    { id: 2, text: 'смешанного характера, усиливается в положении лёжа', source: '7 записей' }],

    'давлен': [
    { id: 1, text: 'максимально до 180/100, адаптирован к 140/90', source: 'Шаблон ГБ' },
    { id: 2, text: 'нестабильное, от 130/80 до 170/100', source: '9 записей' }],

    '_default': [
    { id: 1, text: 'беспокоит в течение последних дней, связывает с нагрузкой', source: 'Общий' }]

  },
  anamnesisMorbi: {
    'неделю': [
    { id: 1, text: 'Заболел около недели назад, когда впервые появились вышеуказанные жалобы', source: 'Шаблон' },
    { id: 2, text: 'В течение недели постепенно нарастали симптомы', source: '10 записей' }],

    'давно': [
    { id: 1, text: 'Считает себя больным в течение многих лет, ухудшение последние дни', source: 'Шаблон хр.' },
    { id: 2, text: 'Длительный анамнез заболевания, неоднократно обследовался', source: '8 записей' }],

    '_default': [
    { id: 1, text: 'Заболел остро, связывает с физической нагрузкой', source: 'Общий' },
    { id: 2, text: 'Постепенное начало, точную дату назвать затрудняется', source: '15 записей' }]

  },
  anamnesisVitae: {
    'гиперт': [
    { id: 1, text: 'Гипертоническая болезнь в течение 10 лет, принимает антигипертензивную терапию', source: 'Шаблон ГБ' }],

    'диабет': [
    { id: 1, text: 'Сахарный диабет 2 типа, на таблетированной терапии', source: 'Шаблон СД' }],

    '_default': [
    { id: 1, text: 'Хронических заболеваний нет. Аллергоанамнез не отягощён', source: 'Здоров' },
    { id: 2, text: 'Из хронических заболеваний отмечает...', source: '20+ записей' }]

  },
  examination: {
    'удовл': [
    { id: 1, text: 'Состояние удовлетворительное. Сознание ясное. Положение активное.', source: 'Шаблон норма' },
    { id: 2, text: 'Состояние относительно удовлетворительное. Кожные покровы обычной окраски.', source: '25 записей' }],

    'средн': [
    { id: 1, text: 'Состояние средней тяжести. Сознание ясное. Положение вынужденное.', source: 'Шаблон ср.тяж.' }],

    '_default': [
    { id: 1, text: 'При осмотре: состояние удовлетворительное, сознание ясное', source: 'Стандарт' }]

  },
  diagnosis: {
    'гиперт': [
    { id: 1, text: 'Гипертоническая болезнь II стадии, риск ССО 3', source: 'Шаблон ГБ' },
    { id: 2, text: 'Гипертоническая болезнь III стадии, контролируемая', source: '12 записей' }],

    'ибс': [
    { id: 1, text: 'ИБС. Стабильная стенокардия напряжения, ФК II', source: 'Шаблон ИБС' },
    { id: 2, text: 'ИБС. Атеросклеротический кардиосклероз', source: '8 записей' }],

    '_default': []
  },
  'plan.treatment': {
    'гипот': [
    { id: 1, text: 'Лизиноприл 10 мг утром, Амлодипин 5 мг вечером', source: 'Шаблон ГБ' },
    { id: 2, text: 'Бисопролол 5 мг утром, Индапамид 2.5 мг утром', source: '10 записей' }],

    '_default': [
    { id: 1, text: 'Продолжить текущую терапию. Контроль АД ежедневно.', source: 'Стандарт' }]

  }
};

const mockEMRTemplates = async (text, fieldName) => {
  await new Promise((resolve) => setTimeout(resolve, 500));

  const lowerText = text.toLowerCase();
  const fieldTemplates = FIELD_TEMPLATES[fieldName] || FIELD_TEMPLATES.complaints;

  // Поиск по ключевым словам
  for (const [keyword, templates] of Object.entries(fieldTemplates)) {
    if (keyword !== '_default' && lowerText.includes(keyword)) {
      return templates;
    }
  }

  // Default шаблоны если есть
  if (fieldTemplates._default && text.length >= 5) {
    return fieldTemplates._default;
  }

  return [];
};

// ============================================
// VALIDATION SERVICE - Проверка перед подписью
// ============================================
const validateForSigning = (emr) => {
  const errors = {};

  if (!emr.complaints?.trim()) {
    errors.complaints = 'Жалобы обязательны для подписания';
  }

  if (!emr.diagnosis?.trim()) {
    errors.diagnosis = 'Диагноз обязателен для подписания';
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors
  };
};

// ============================================
// VISIT STATUS BADGE - Всегда видимый статус
// ============================================
const VisitStatusBadge = ({ status }) => {
  const config = VISIT_STATUS_CONFIG[status] || VISIT_STATUS_CONFIG[VISIT_STATUS.DRAFT];
  const Icon = config.icon;

  return (
    <div
      className="emr-visit-status"
      style={{
        background: config.bgColor,
        color: config.color
      }}>
      
            <Icon size={14} />
            <span>{config.label}</span>
        </div>);

};

// ============================================
// PATIENT HEADER - Всегда видна + статус визита
// ============================================
const PatientHeader = ({ patient, allergies, diagnoses, visitStatus, onAISummary }) => {
  const age = patient?.birth_date ?
  Math.floor((new Date() - new Date(patient.birth_date)) / (365.25 * 24 * 60 * 60 * 1000)) :
  null;

  const gender = patient?.sex === 'M' ? 'М' : patient?.sex === 'F' ? 'Ж' : '';

  return (
    <header className="emr-header">
            {/* Статус визита - ВСЕГДА ВИДЕН */}
            <VisitStatusBadge status={visitStatus} />

            <div className="emr-header__patient">
                <h1 className="emr-header__name">
                    {patient?.last_name} {patient?.first_name} {patient?.middle_name || ''}
                </h1>
                <span className="emr-header__meta">
                    {age && `${age} лет`} {gender && `· ${gender}`}
                </span>
            </div>

            {allergies && allergies.length > 0 &&
      <div className="emr-header__allergies">
                    <AlertTriangle size={16} />
                    <span>Аллергии: {allergies.join(', ')}</span>
                </div>
      }

            {diagnoses && diagnoses.length > 0 &&
      <div className="emr-header__diagnoses">
                    Диагнозы: {diagnoses.slice(0, 3).join(', ')}
                    {diagnoses.length > 3 && ` и ещё ${diagnoses.length - 3}`}
                </div>
      }

            <button
        className="emr-header__ai-btn"
        onClick={onAISummary}
        title="AI Summary">
        
                <Brain size={18} />
                <span>AI Summary</span>
            </button>
        </header>);

};

// ============================================
// COLLAPSIBLE SECTION
// ============================================
const CollapsibleSection = ({ title, children, defaultOpen = true, badge }) => {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <section className={`emr-section ${isOpen ? 'emr-section--open' : ''}`}>
            <button
        className="emr-section__header"
        onClick={() => setIsOpen(!isOpen)}>
        
                {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                <span className="emr-section__title">{title}</span>
                {badge && <span className="emr-section__badge">{badge}</span>}
            </button>
            {isOpen &&
      <div className="emr-section__content">
                    {children}
                </div>
      }
        </section>);

};

// ============================================
// INLINE TEXT FIELD with AI suggestion
// ============================================






















































































// ============================================
// VITALS WIDGET (Кардиология)
// ============================================
const VitalsWidget = ({ vitals, onChange, onFieldTouch, disabled }) => {
  const handleChange = (field, value) => {
    onChange({ ...vitals, [field]: value });
    onFieldTouch?.(`vitals.${field}`);
  };

  // BP Warning (subtle, non-blocking)
  const systolic = parseInt(vitals?.systolic) || 0;
  const diastolic = parseInt(vitals?.diastolic) || 0;
  const isBPHigh = systolic > 140 || diastolic > 90;
  const isBPCritical = systolic > 180 || diastolic > 120;

  // BMI calculation
  const bmi = vitals?.height && vitals?.weight ?
  (vitals.weight / Math.pow(vitals.height / 100, 2)).toFixed(1) :
  null;

  return (
    <div className="emr-vitals">
            <div className="emr-vitals__row">
                <div className={`emr-vitals__field ${isBPCritical ? 'emr-vitals__field--critical' : isBPHigh ? 'emr-vitals__field--warning' : ''}`}>
                    <label>АД сист.</label>
                    <input
            type="number"
            value={vitals?.systolic || ''}
            onChange={(e) => handleChange('systolic', e.target.value)}
            placeholder="120"
            disabled={disabled} />
          
                </div>
                <span className="emr-vitals__separator">/</span>
                <div className={`emr-vitals__field ${isBPCritical ? 'emr-vitals__field--critical' : isBPHigh ? 'emr-vitals__field--warning' : ''}`}>
                    <label>АД диаст.</label>
                    <input
            type="number"
            value={vitals?.diastolic || ''}
            onChange={(e) => handleChange('diastolic', e.target.value)}
            placeholder="80"
            disabled={disabled} />
          
                </div>
                <div className="emr-vitals__field">
                    <label>Пульс</label>
                    <input
            type="number"
            value={vitals?.pulse || ''}
            onChange={(e) => handleChange('pulse', e.target.value)}
            placeholder="72"
            disabled={disabled} />
          
                </div>
                <div className="emr-vitals__field">
                    <label>SpO₂</label>
                    <input
            type="number"
            value={vitals?.spo2 || ''}
            onChange={(e) => handleChange('spo2', e.target.value)}
            placeholder="98"
            disabled={disabled} />
          
                    <span className="emr-vitals__unit">%</span>
                </div>

                {/* BP Warning - subtle, non-blocking */}
                {isBPHigh &&
        <div className={`emr-vitals__warning ${isBPCritical ? 'emr-vitals__warning--critical' : ''}`}>
                        {isBPCritical ? '⚠️ Криз' : '↑ АД'}
                    </div>
        }
            </div>
            <div className="emr-vitals__row">
                <div className="emr-vitals__field">
                    <label>Рост {vitals?.heightSource && <small>({vitals.heightSource})</small>}</label>
                    <input
            type="number"
            value={vitals?.height || ''}
            onChange={(e) => handleChange('height', e.target.value)}
            placeholder="170"
            disabled={disabled} />
          
                    <span className="emr-vitals__unit">см</span>
                </div>
                <div className="emr-vitals__field">
                    <label>Вес {vitals?.weightSource && <small>({vitals.weightSource})</small>}</label>
                    <input
            type="number"
            value={vitals?.weight || ''}
            onChange={(e) => handleChange('weight', e.target.value)}
            placeholder="70"
            disabled={disabled} />
          
                    <span className="emr-vitals__unit">кг</span>
                </div>
                {bmi &&
        <div className="emr-vitals__bmi">
                        ИМТ: {bmi}
                    </div>
        }
            </div>
        </div>);

};

// ============================================
// DIAGNOSIS FIELD with ICD-10
// ============================================






























































// ============================================
// PLAN SECTION
// ============================================
const PlanSection = ({ plan, onChange, onFieldTouch, disabled }) => {
  const handleChange = (field, value) => {
    onChange({ ...plan, [field]: value });
    onFieldTouch?.(`plan.${field}`);
  };

  return (
    <div className="emr-plan">
            <div className="emr-plan__row">
                <label>Обследования:</label>
                <input
          type="text"
          value={plan?.examinations || ''}
          onChange={(e) => handleChange('examinations', e.target.value)}
          placeholder="ОАК, ОАМ, ЭКГ..."
          disabled={disabled} />
        
            </div>
            <div className="emr-plan__row">
                <label>Лечение:</label>
                <input
          type="text"
          value={plan?.treatment || ''}
          onChange={(e) => handleChange('treatment', e.target.value)}
          placeholder="Медикаментозная терапия..."
          disabled={disabled} />
        
            </div>
            <div className="emr-plan__row">
                <label>Консультации:</label>
                <input
          type="text"
          value={plan?.consultations || ''}
          onChange={(e) => handleChange('consultations', e.target.value)}
          placeholder="Кардиолог, эндокринолог..."
          disabled={disabled} />
        
            </div>
        </div>);

};

// ============================================
// CLINICAL DOCUMENT GENERATOR (вместо window.print)
// ============================================
const generateClinicalDocument = (emrData, patient, options = {}) => {
  // Генерация клинического документа для печати
  // В будущем: PDF, подпись, QR-код, hash
  return {
    type: 'clinical_document',
    version: '1.0',
    generated_at: new Date().toISOString(),
    patient: {
      name: `${patient?.last_name} ${patient?.first_name} ${patient?.middle_name || ''}`.trim(),
      birth_date: patient?.birth_date
    },
    content: emrData,
    options
  };
};

// ============================================
// MAIN COMPONENT
// ============================================
const SingleSheetEMR = ({
  // Context (кто, что, зачем)
  context: {
    patient,
    visit,
    specialty = 'general'
  } = {},
  // Actions (что можно делать)
  actions: {
    onSave,
    onSign,
    onPrint,
    onAISummary
  } = {},
  // Initial data
  initialData,
  // Read-only mode
  readOnly = false,
  // Dev mode (для telemetry)
  enableTelemetry = false
}) => {
  // UX Telemetry
  const { recordFieldTouch, getTelemetry } = useTelemetry();

  // AI Integration через MCP (useEMRAI)
  // ⚠️ ПРАВИЛО: AI всегда вызывается через useEMRAI / mcpClient
  const {
    loading: aiLoading,
    icd10Suggestions,
    getICD10Suggestions,
    clearSuggestions
  } = useEMRAI(true, 'deepseek'); // useMCP=true, provider=deepseek

  // User Preferences (EMR settings)
  const {
    getEMRPreferences,

    addRecentICD10,
    addRecentTemplate
  } = useUserPreferences();

  // Get EMR preferences (with defaults)
  const emrPrefs = getEMRPreferences();

  // Derive visit status
  const getVisitStatus = useCallback(() => {
    if (!visit) return VISIT_STATUS.DRAFT;
    if (visit.status === 'closed' || visit.status === 'completed') return VISIT_STATUS.CLOSED;
    if (visit.is_signed || visit.signed_at) return VISIT_STATUS.SIGNED;
    if (visit.status === 'in_progress' || visit.started_at) return VISIT_STATUS.IN_PROGRESS;
    return VISIT_STATUS.DRAFT;
  }, [visit]);

  const [visitStatus, setVisitStatus] = useState(getVisitStatus());

  // EMR State
  const [emr, setEmr] = useState({
    complaints: '',
    anamnesisMorbi: '',
    anamnesisVitae: '',
    examination: '',
    diagnosis: '',
    icd10: '',
    plan: {
      examinations: '',
      treatment: '',
      consultations: ''
    },
    vitals: {},
    prescriptions: [],
    ...initialData
  });

  const [hasChanges, setHasChanges] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [validationErrors, setValidationErrors] = useState({});
  const handleSaveDraftRef = useRef(async () => {});

  // Update visit status when visit changes
  useEffect(() => {
    setVisitStatus(getVisitStatus());
  }, [visit, getVisitStatus]);

  // Auto-save every 30 seconds
  useEffect(() => {
    if (!hasChanges || readOnly || visitStatus === VISIT_STATUS.CLOSED) return;

    const timer = setTimeout(async () => {
      await handleSaveDraftRef.current?.();
    }, 30000);

    return () => clearTimeout(timer);
  }, [hasChanges, readOnly, visitStatus, emr]);

  // Load initial data
  useEffect(() => {
    if (initialData) {
      setEmr((prev) => ({ ...prev, ...initialData }));
    }
  }, [initialData]);

  // Pre-fill vitals from patient history (height/weight)
  useEffect(() => {
    if (patient?.vitals_history && !emr.vitals.height && !emr.vitals.weight) {
      const lastVitals = patient.vitals_history;
      if (lastVitals.height || lastVitals.weight) {
        setEmr((prev) => ({
          ...prev,
          vitals: {
            ...prev.vitals,
            height: lastVitals.height || prev.vitals.height,
            weight: lastVitals.weight || prev.vitals.weight,
            // Mark as from history
            heightSource: lastVitals.date ? `из визита ${lastVitals.date}` : 'из истории',
            weightSource: lastVitals.date ? `из визита ${lastVitals.date}` : 'из истории'
          }
        }));
      }
    }
  }, [patient, emr.vitals.height, emr.vitals.weight]);

  // Mock Copy Previous
  const handleCopyPrevious = async (section) => {
    // Здесь должен быть API запрос
    await new Promise((r) => setTimeout(r, 500));

    const mockLastVisit = {
      complaints: 'Головная боль, головокружение, шум в ушах',
      diagnosis: 'Гипертоническая болезнь II ст., риск 3',
      plan: {
        treatment: 'Эналаприл 10мг 2р/д',
        examinations: 'ЭКГ, ОАК'
      }
    };

    if (section === 'complaints') {
      handleFieldChange('complaints', mockLastVisit.complaints);
    } else if (section === 'diagnosis') {
      handleFieldChange('diagnosis', mockLastVisit.diagnosis);
    } else if (section === 'plan') {
      handleFieldChange('plan', mockLastVisit.plan);
    }
    recordFieldTouch(`${section}_copy`);
  };

  // Field change handler
  const handleFieldChange = useCallback((field, value) => {
    setEmr((prev) => {
      if (field.includes('.')) {
        const [parent, child] = field.split('.');
        return {
          ...prev,
          [parent]: { ...prev[parent], [child]: value }
        };
      }
      return { ...prev, [field]: value };
    });
    setHasChanges(true);
    recordFieldTouch(field);
  }, [recordFieldTouch]);

  // Save draft
  const handleSaveDraft = useCallback(async () => {
    if (readOnly || isSaving || visitStatus === VISIT_STATUS.CLOSED) return;

    setIsSaving(true);
    try {
      const telemetry = enableTelemetry ? getTelemetry() : undefined;
      await onSave?.({
        ...emr,
        isDraft: true,
        telemetry
      });
      setLastSaved(new Date());
      setHasChanges(false);
      setVisitStatus(VISIT_STATUS.IN_PROGRESS);
    } catch (error) {
      logger.error('Save error:', error);
    } finally {
      setIsSaving(false);
    }
  }, [readOnly, isSaving, visitStatus, enableTelemetry, getTelemetry, onSave, emr]);
  handleSaveDraftRef.current = handleSaveDraft;

  // Sign and complete
  const handleSign = async () => {
    if (readOnly || visitStatus === VISIT_STATUS.CLOSED) return;

    // Validate before signing
    const validation = validateForSigning(emr);
    if (!validation.isValid) {
      setValidationErrors(validation.errors);
      return;
    }

    // Clear any previous errors
    setValidationErrors({});

    setIsSaving(true);
    try {
      const telemetry = enableTelemetry ? getTelemetry() : undefined;
      await onSign?.({
        ...emr,
        isDraft: false,
        telemetry
      });
      setHasChanges(false);
      setVisitStatus(VISIT_STATUS.SIGNED);
    } catch (error) {
      logger.error('Sign error:', error);
    } finally {
      setIsSaving(false);
    }
  };

  // Print via document generation (NOT window.print)
  const handlePrint = () => {
    const document = generateClinicalDocument(emr, patient, {
      includeSignature: visitStatus === VISIT_STATUS.SIGNED,
      format: 'a4'
    });
    onPrint?.(document);
  };

  // AI Summary
  const handleAISummary = () => {
    onAISummary?.(emr);
  };

  // Check if editing is allowed
  const isEditable = !readOnly &&
  visitStatus !== VISIT_STATUS.CLOSED &&
  visitStatus !== VISIT_STATUS.SIGNED;

  return (
    <div className="single-sheet-emr">
            {/* HEADER - Always visible + Visit Status */}
            <PatientHeader
        patient={patient}
        allergies={patient?.allergies || []}
        diagnoses={patient?.diagnoses || []}
        visitStatus={visitStatus}
        onAISummary={handleAISummary} />
      

            {/* MAIN CONTENT - Scrollable */}
            <main className="emr-content">
                {/* ЖАЛОБЫ - Smart Field with mode switcher */}
                <section className="emr-section emr-section--complaints">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <h2 className="emr-section__label" style={{ marginBottom: 0 }}>Жалобы</h2>
                        {isEditable &&
            <button
              className="emr-btn-text"
              onClick={() => handleCopyPrevious('complaints')}
              title="Скопировать из прошлого визита">
              
                                <Copy size={12} />
                                Из прошлого
                            </button>
            }
                    </div>
                    <ComplaintsField
            value={emr.complaints}
            onChange={(v) => handleFieldChange('complaints', v)}
            isEditable={isEditable}
            aiEnabled={specialty === 'cardiology' || specialty === 'general'}
            onRequestAI={(text) => mockEMRTemplates(text, 'complaints')}
            autoFocus={isEditable}
            onFieldTouch={() => recordFieldTouch('complaints')}
            error={validationErrors.complaints}
            onBlur={() => {








              // Trigger draft save on blur? 
              // SingleSheetEMR handles auto-save periodically, but we can hint 'saved'
            }} />
                </section>

                {/* АНАМНЕЗ */}
                <CollapsibleSection title="Анамнез заболевания" defaultOpen={!emr.anamnesisMorbi}>
                    <EMRTextField value={emr.anamnesisMorbi} onChange={(v) => handleFieldChange('anamnesisMorbi', v)} isEditable={isEditable} aiEnabled={true} onRequestAI={mockEMRTemplates} fieldName="anamnesisMorbi" onFieldTouch={() => recordFieldTouch('anamnesisMorbi')}
            placeholder="Когда началось, как развивалось..." />
          
                </CollapsibleSection>

                <CollapsibleSection title="Анамнез жизни" defaultOpen={false}>
                    <EMRTextField
            value={emr.anamnesisVitae}
            onChange={(v) => handleFieldChange('anamnesisVitae', v)}
            isEditable={isEditable}
            aiEnabled={true}
            onRequestAI={mockEMRTemplates}
            fieldName="anamnesisVitae"
            onFieldTouch={() => recordFieldTouch('anamnesisVitae')}
            placeholder="Перенесённые заболевания, операции, аллергии..." />
          
                </CollapsibleSection>

                {/* ОБЪЕКТИВНО */}
                <section className="emr-section">
                    <h2 className="emr-section__label">Объективный статус</h2>

                    {/* Витальные показатели для кардиологии */}
                    {(specialty === 'cardiology' || specialty === 'general') &&
          <VitalsWidget
            vitals={emr.vitals}
            onChange={(v) => handleFieldChange('vitals', v)}
            onFieldTouch={recordFieldTouch}
            disabled={!isEditable} />

          }

                    {/* Матрица осмотра (Checklist) */}
                    <div style={{ marginBottom: '12px' }}>
                        <ExaminationMatrix
              specialty={specialty}
              isEditable={isEditable}
              onGenerateText={(text) => {
                // Если поле пустое - просто ставим текст
                // Если нет - спрашиваем или добавляем
                if (!emr.examination) {
                  handleFieldChange('examination', text);
                } else {
                  // Append if not included
                  if (!emr.examination.includes(text)) {
                    handleFieldChange('examination', `${emr.examination} ${text}`);
                  }
                }
                recordFieldTouch('examination_matrix');
              }} />
            
                    </div>

                    <EMRTextField
            value={emr.examination}
            onChange={(v) => handleFieldChange('examination', v)}
            isEditable={isEditable}
            aiEnabled={true}
            onRequestAI={mockEMRTemplates}
            fieldName="examination"
            onFieldTouch={() => recordFieldTouch('examination')}
            label="Осмотр"
            placeholder="Состояние удовлетворительное, сознание ясное..." />
          
                </section>

                {/* ДИАГНОЗ */}
                <section className="emr-section">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <h2 className="emr-section__label" style={{ marginBottom: 0 }}>Диагноз</h2>
                        {isEditable &&
            <button
              className="emr-btn-text"
              onClick={() => handleCopyPrevious('diagnosis')}
              title="Скопировать из прошлого визита">
              
                                <Copy size={12} />
                                Из прошлого
                            </button>
            }
                    </div>

                    {/* МКБ-10 Autocomplete */}
                    <div style={{ marginBottom: '12px' }}>
                        <label style={{
              display: 'block',
              marginBottom: '6px',
              fontSize: '12px',
              fontWeight: '600',
              color: '#86868b',
              textTransform: 'uppercase'
            }}>
                            Код МКБ-10
                        </label>
                        <ICD10Autocomplete
              value={emr.icd10}
              onChange={(code, name) => {
                handleFieldChange('icd10', code);
                // Если диагноз пустой - заполняем из МКБ
                if (!emr.diagnosis && name) {
                  handleFieldChange('diagnosis', name);
                }
                // ✅ Сохраняем в недавние
                if (code) {
                  addRecentICD10(code);
                }
                clearSuggestions();
              }}
              // AI suggestions from useEMRAI (UI-only pattern)
              suggestions={icd10Suggestions.map((s) => ({
                code: s.code,
                name: s.name || s.title || s.description,
                confidence: s.confidence || s.relevance
              }))}
              loading={aiLoading}
              onSearch={(query) => {
                // Вызов AI через useEMRAI
                if (query.length >= 2) {
                  getICD10Suggestions(emr.complaints, query, specialty);
                }
              }}
              // ✅ Недавние коды из preferences
              recentCodes={emrPrefs.recentIcd10}
              disabled={!isEditable}
              placeholder="I10, I25.9, гипертония..." />
            
                        {validationErrors.icd10 &&
            <div style={{ marginTop: '4px', fontSize: '12px', color: '#ff3b30' }}>
                                ⚠️ {validationErrors.icd10}
                            </div>
            }
                    </div>

                    {/* Текстовый диагноз */}
                    <EMRTextField
            value={emr.diagnosis}
            onChange={(v) => handleFieldChange('diagnosis', v)}
            isEditable={isEditable}
            aiEnabled={true}
            onRequestAI={mockEMRTemplates}
            error={validationErrors.diagnosis}
            fieldName="diagnosis"
            onFieldTouch={() => {
              recordFieldTouch('diagnosis');
              if (validationErrors.diagnosis) {
                setValidationErrors((prev) => ({ ...prev, diagnosis: null }));
              }
            }}
            label="Клинический диагноз"
            placeholder="Гипертоническая болезнь II стадии, риск ССО 3..."
            multiline={true}
            rows={2} />
          
                </section>

                {/* ПЛАН */}
                <section className="emr-section">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                            <h2 className="emr-section__label" style={{ marginBottom: 0 }}>План</h2>
                            {isEditable &&
              <button
                className="emr-btn-text"
                onClick={() => handleCopyPrevious('plan')}
                title="Скопировать из прошлого визита">
                
                                    <Copy size={12} />
                                    Из прошлого
                                </button>
              }
                        </div>
                        {isEditable &&
            <TreatmentTemplates
              specialty={specialty}
              onSelect={(template, category) => {
                // Вставляем шаблон в соответствующее поле
                const fieldMap = {
                  medications: 'treatment',
                  examinations: 'examinations',
                  labs: 'examinations',
                  followup: 'consultations'
                };
                const targetField = fieldMap[category] || 'treatment';

                // Добавляем к существующему значению
                const currentValue = emr.plan?.[targetField] || '';
                const newValue = currentValue ?
                `${currentValue}, ${template}` :
                template;

                handleFieldChange('plan', {
                  ...emr.plan,
                  [targetField]: newValue
                });
                recordFieldTouch(`plan.${targetField}`);
              }}
              // ✅ Недавние шаблоны из preferences
              recentTemplates={emrPrefs.recentTemplates}
              onRecentUpdate={(templateIds) => {
                templateIds.forEach((id) => addRecentTemplate(id));
              }}
              disabled={!isEditable} />

            }
                    </div>
                    <PlanSection
            plan={emr.plan}
            onChange={(v) => handleFieldChange('plan', v)}
            onFieldTouch={recordFieldTouch}
            disabled={!isEditable} />
          

                    {/* PRESCRIPTIONS (NEW) */}
                    <div style={{ marginTop: '20px' }}>
                        <h3 className="emr-section__label">Назначения (рецепт)</h3>
                        <PrescriptionEditor
              prescriptions={emr.prescriptions || []}
              onChange={(v) => handleFieldChange('prescriptions', v)}
              isEditable={isEditable}
              onFieldTouch={recordFieldTouch} />
            
                    </div>
                </section>
            </main>

            {/* FOOTER - Actions + Status */}
            <footer className="emr-footer">
                <div className="emr-footer__status">
                    {lastSaved &&
          <span className="emr-footer__saved">
                            <Clock size={12} />
                            Сохранено {lastSaved.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                        </span>
          }
                    {hasChanges &&
          <span className="emr-footer__unsaved">● Есть изменения</span>
          }
                </div>

                <div className="emr-footer__actions">
                    <button
            className="emr-btn emr-btn--secondary"
            onClick={handleSaveDraft}
            disabled={!isEditable || isSaving}>
            
                        <Save size={16} />
                        Черновик
                    </button>

                    <button
            className="emr-btn emr-btn--secondary"
            onClick={handlePrint}
            disabled={isSaving}>
            
                        <Printer size={16} />
                        Печать
                    </button>

                    <button
            className="emr-btn emr-btn--primary"
            onClick={handleSign}
            disabled={!isEditable || isSaving}>
            
                        <FileText size={16} />
                        Подписать
                    </button>
                </div>
            </footer>
        </div>);

};

VisitStatusBadge.propTypes = {
  status: PropTypes.string
};

PatientHeader.propTypes = {
  patient: PropTypes.object,
  allergies: PropTypes.array,
  diagnoses: PropTypes.array,
  visitStatus: PropTypes.string,
  onAISummary: PropTypes.func
};

CollapsibleSection.propTypes = {
  title: PropTypes.node,
  children: PropTypes.node,
  defaultOpen: PropTypes.bool,
  badge: PropTypes.node
};

VitalsWidget.propTypes = {
  vitals: PropTypes.object,
  onChange: PropTypes.func,
  onFieldTouch: PropTypes.func,
  disabled: PropTypes.bool
};

PlanSection.propTypes = {
  plan: PropTypes.object,
  onChange: PropTypes.func,
  onFieldTouch: PropTypes.func,
  disabled: PropTypes.bool
};

SingleSheetEMR.propTypes = {
  context: PropTypes.shape({
    patient: PropTypes.object,
    visit: PropTypes.object,
    specialty: PropTypes.string
  }),
  actions: PropTypes.shape({
    onSave: PropTypes.func,
    onSign: PropTypes.func,
    onPrint: PropTypes.func,
    onAISummary: PropTypes.func
  }),
  initialData: PropTypes.object,
  readOnly: PropTypes.bool,
  enableTelemetry: PropTypes.bool
};

// Export with constants for external use
SingleSheetEMR.VISIT_STATUS = VISIT_STATUS;
SingleSheetEMR.generateClinicalDocument = generateClinicalDocument;

export default SingleSheetEMR;
