import React, { useState, useEffect } from 'react';
import { 
  FileText, 
  Pill, 
  Stethoscope, 
  Plus, 
  Edit, 
  Trash2,
  Save,
  X,
  CheckCircle,
  AlertCircle,
  Clock,
  User,
  Calendar,
  Printer,
  Download,
  Send
} from 'lucide-react';

/**
 * Форма диагнозов и назначений для стоматологической ЭМК
 * Включает диагнозы по зубам, общие диагнозы, рецепты, направления
 */
const DiagnosisForm = ({ 
  patientId, 
  patientName,
  initialData = null, 
  onSave, 
  onClose 
}) => {
  const [formData, setFormData] = useState({
    // Основные данные
    diagnosisDate: new Date().toISOString().split('T')[0],
    doctor: '',
    
    // Диагнозы по зубам
    toothDiagnoses: {},
    
    // Общие диагнозы
    generalDiagnoses: [],
    
    // План лечения
    treatmentPlan: {
      immediate: [], // Немедленные меры
      shortTerm: [], // Краткосрочный план
      longTerm: []   // Долгосрочный план
    },
    
    // Назначения
    prescriptions: [],
    referrals: [],
    recommendations: [],
    
    // Метаданные
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  });

  const [isEditing, setIsEditing] = useState(true);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('tooth-diagnoses');

  // Инициализация данных
  useEffect(() => {
    if (initialData) {
      setFormData({
        ...formData,
        ...initialData
      });
      setIsEditing(false);
    }
  }, [initialData]);

  // Обработчики
  const handleInputChange = (field, value) => {
    if (field.includes('.')) {
      const [parent, child] = field.split('.');
      setFormData(prev => ({
        ...prev,
        [parent]: {
          ...prev[parent],
          [child]: value
        }
      }));
    } else {
      setFormData(prev => ({
        ...prev,
        [field]: value
      }));
    }
  };

  const handleArrayAdd = (field, item) => {
    setFormData(prev => ({
      ...prev,
      [field]: [...prev[field], item]
    }));
  };

  const handleArrayRemove = (field, index) => {
    setFormData(prev => ({
      ...prev,
      [field]: prev[field].filter((_, i) => i !== index)
    }));
  };

  const handleToothDiagnosisChange = (toothId, diagnosis) => {
    setFormData(prev => ({
      ...prev,
      toothDiagnoses: {
        ...prev.toothDiagnoses,
        [toothId]: diagnosis
      }
    }));
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      const updatedData = {
        ...formData,
        updatedAt: new Date().toISOString()
      };
      
      if (onSave) {
        await onSave(updatedData);
      }
      
      setIsEditing(false);
    } catch (error) {
      console.error('Ошибка сохранения:', error);
    } finally {
      setLoading(false);
    }
  };

  // Вкладки
  const tabs = [
    { id: 'tooth-diagnoses', label: 'Диагнозы по зубам', icon: Stethoscope },
    { id: 'general-diagnoses', label: 'Общие диагнозы', icon: FileText },
    { id: 'treatment-plan', label: 'План лечения', icon: Calendar },
    { id: 'prescriptions', label: 'Рецепты', icon: Pill },
    { id: 'referrals', label: 'Направления', icon: Send }
  ];

  // Стандартные диагнозы по зубам
  const standardToothDiagnoses = [
    'Кариес',
    'Пульпит',
    'Периодонтит',
    'Периапикальный абсцесс',
    'Травма зуба',
    'Стираемость',
    'Эрозия',
    'Гипоплазия',
    'Флюороз',
    'Зубной камень',
    'Гингивит',
    'Пародонтит',
    'Подвижность зуба',
    'Резорбция корня',
    'Киста',
    'Гранулема',
    'Норма'
  ];

  // Рендер диагнозов по зубам
  const renderToothDiagnoses = () => (
    <div className="space-y-6">
      <div className="bg-blue-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Диагнозы по зубам</h3>
        <p className="text-sm text-gray-600">
          Укажите диагноз для каждого зуба, требующего лечения
        </p>
      </div>
      
      {/* Верхняя челюсть */}
      <div>
        <h4 className="font-semibold mb-3 text-gray-700">Верхняя челюсть</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28].map(toothId => (
            <div key={toothId} className="border rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-sm">Зуб {toothId}</span>
                <div className="w-3 h-3 rounded-full bg-gray-200"></div>
              </div>
              <select
                value={formData.toothDiagnoses[toothId] || ''}
                onChange={(e) => handleToothDiagnosisChange(toothId, e.target.value)}
                disabled={!isEditing}
                className="w-full text-xs px-2 py-1 border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              >
                <option value="">Выберите диагноз</option>
                {standardToothDiagnoses.map(diagnosis => (
                  <option key={diagnosis} value={diagnosis}>{diagnosis}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </div>
      
      {/* Нижняя челюсть */}
      <div>
        <h4 className="font-semibold mb-3 text-gray-700">Нижняя челюсть</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38].map(toothId => (
            <div key={toothId} className="border rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-sm">Зуб {toothId}</span>
                <div className="w-3 h-3 rounded-full bg-gray-200"></div>
              </div>
              <select
                value={formData.toothDiagnoses[toothId] || ''}
                onChange={(e) => handleToothDiagnosisChange(toothId, e.target.value)}
                disabled={!isEditing}
                className="w-full text-xs px-2 py-1 border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              >
                <option value="">Выберите диагноз</option>
                {standardToothDiagnoses.map(diagnosis => (
                  <option key={diagnosis} value={diagnosis}>{diagnosis}</option>
                ))}
              </select>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  // Рендер общих диагнозов
  const renderGeneralDiagnoses = () => (
    <div className="space-y-6">
      <div className="bg-green-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Общие диагнозы</h3>
        <p className="text-sm text-gray-600">
          Системные диагнозы, влияющие на стоматологическое лечение
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.generalDiagnoses.map((diagnosis, index) => (
          <div key={index} className="flex items-center gap-3 p-3 border rounded-lg">
            <input
              type="text"
              value={diagnosis}
              onChange={(e) => {
                const newDiagnoses = [...formData.generalDiagnoses];
                newDiagnoses[index] = e.target.value;
                handleInputChange('generalDiagnoses', newDiagnoses);
              }}
              disabled={!isEditing}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder="Введите диагноз"
            />
            {isEditing && (
              <button
                onClick={() => handleArrayRemove('generalDiagnoses', index)}
                className="text-red-500 hover:text-red-700"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
          </div>
        ))}
        
        {isEditing && (
          <button
            onClick={() => handleArrayAdd('generalDiagnoses', '')}
            className="flex items-center gap-2 w-full p-3 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600"
          >
            <Plus className="h-4 w-4" />
            Добавить диагноз
          </button>
        )}
      </div>
    </div>
  );

  // Рендер плана лечения
  const renderTreatmentPlan = () => (
    <div className="space-y-6">
      <div className="bg-yellow-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">План лечения</h3>
        <p className="text-sm text-gray-600">
          Поэтапное планирование стоматологического лечения
        </p>
      </div>
      
      {/* Немедленные меры */}
      <div>
        <h4 className="font-semibold mb-3 text-red-600 flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          Немедленные меры
        </h4>
        <div className="space-y-2">
          {formData.treatmentPlan.immediate.map((item, index) => (
            <div key={index} className="flex items-center gap-3 p-3 bg-red-50 border border-red-200 rounded-lg">
              <input
                type="text"
                value={item}
                onChange={(e) => {
                  const newItems = [...formData.treatmentPlan.immediate];
                  newItems[index] = e.target.value;
                  handleInputChange('treatmentPlan.immediate', newItems);
                }}
                disabled={!isEditing}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="Срочные меры (например: обезболивание, дренирование)"
              />
              {isEditing && (
                <button
                  onClick={() => handleArrayRemove('treatmentPlan.immediate', index)}
                  className="text-red-500 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
          {isEditing && (
            <button
              onClick={() => handleArrayAdd('treatmentPlan.immediate', '')}
              className="flex items-center gap-2 w-full p-3 border-2 border-dashed border-red-300 rounded-lg text-red-600 hover:border-red-500"
            >
              <Plus className="h-4 w-4" />
              Добавить срочную меру
            </button>
          )}
        </div>
      </div>
      
      {/* Краткосрочный план */}
      <div>
        <h4 className="font-semibold mb-3 text-orange-600 flex items-center gap-2">
          <Clock className="h-4 w-4" />
          Краткосрочный план (1-3 месяца)
        </h4>
        <div className="space-y-2">
          {formData.treatmentPlan.shortTerm.map((item, index) => (
            <div key={index} className="flex items-center gap-3 p-3 bg-orange-50 border border-orange-200 rounded-lg">
              <input
                type="text"
                value={item}
                onChange={(e) => {
                  const newItems = [...formData.treatmentPlan.shortTerm];
                  newItems[index] = e.target.value;
                  handleInputChange('treatmentPlan.shortTerm', newItems);
                }}
                disabled={!isEditing}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="Краткосрочные процедуры (например: лечение кариеса, чистка)"
              />
              {isEditing && (
                <button
                  onClick={() => handleArrayRemove('treatmentPlan.shortTerm', index)}
                  className="text-red-500 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
          {isEditing && (
            <button
              onClick={() => handleArrayAdd('treatmentPlan.shortTerm', '')}
              className="flex items-center gap-2 w-full p-3 border-2 border-dashed border-orange-300 rounded-lg text-orange-600 hover:border-orange-500"
            >
              <Plus className="h-4 w-4" />
              Добавить краткосрочную процедуру
            </button>
          )}
        </div>
      </div>
      
      {/* Долгосрочный план */}
      <div>
        <h4 className="font-semibold mb-3 text-blue-600 flex items-center gap-2">
          <Calendar className="h-4 w-4" />
          Долгосрочный план (3+ месяцев)
        </h4>
        <div className="space-y-2">
          {formData.treatmentPlan.longTerm.map((item, index) => (
            <div key={index} className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <input
                type="text"
                value={item}
                onChange={(e) => {
                  const newItems = [...formData.treatmentPlan.longTerm];
                  newItems[index] = e.target.value;
                  handleInputChange('treatmentPlan.longTerm', newItems);
                }}
                disabled={!isEditing}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="Долгосрочные процедуры (например: протезирование, имплантация)"
              />
              {isEditing && (
                <button
                  onClick={() => handleArrayRemove('treatmentPlan.longTerm', index)}
                  className="text-red-500 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
          {isEditing && (
            <button
              onClick={() => handleArrayAdd('treatmentPlan.longTerm', '')}
              className="flex items-center gap-2 w-full p-3 border-2 border-dashed border-blue-300 rounded-lg text-blue-600 hover:border-blue-500"
            >
              <Plus className="h-4 w-4" />
              Добавить долгосрочную процедуру
            </button>
          )}
        </div>
      </div>
    </div>
  );

  // Рендер рецептов
  const renderPrescriptions = () => (
    <div className="space-y-6">
      <div className="bg-purple-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Рецепты</h3>
        <p className="text-sm text-gray-600">
          Назначение лекарственных препаратов
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.prescriptions.map((prescription, index) => (
          <div key={index} className="border rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Название препарата
                </label>
                <input
                  type="text"
                  value={prescription.medication || ''}
                  onChange={(e) => {
                    const newPrescriptions = [...formData.prescriptions];
                    newPrescriptions[index] = { ...prescription, medication: e.target.value };
                    handleInputChange('prescriptions', newPrescriptions);
                  }}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  placeholder="Название лекарства"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Дозировка
                </label>
                <input
                  type="text"
                  value={prescription.dosage || ''}
                  onChange={(e) => {
                    const newPrescriptions = [...formData.prescriptions];
                    newPrescriptions[index] = { ...prescription, dosage: e.target.value };
                    handleInputChange('prescriptions', newPrescriptions);
                  }}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  placeholder="Например: 500мг"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Способ применения
                </label>
                <input
                  type="text"
                  value={prescription.administration || ''}
                  onChange={(e) => {
                    const newPrescriptions = [...formData.prescriptions];
                    newPrescriptions[index] = { ...prescription, administration: e.target.value };
                    handleInputChange('prescriptions', newPrescriptions);
                  }}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  placeholder="Например: 3 раза в день после еды"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Продолжительность
                </label>
                <input
                  type="text"
                  value={prescription.duration || ''}
                  onChange={(e) => {
                    const newPrescriptions = [...formData.prescriptions];
                    newPrescriptions[index] = { ...prescription, duration: e.target.value };
                    handleInputChange('prescriptions', newPrescriptions);
                  }}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                  placeholder="Например: 7 дней"
                />
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <textarea
                value={prescription.notes || ''}
                onChange={(e) => {
                  const newPrescriptions = [...formData.prescriptions];
                  newPrescriptions[index] = { ...prescription, notes: e.target.value };
                  handleInputChange('prescriptions', newPrescriptions);
                }}
                disabled={!isEditing}
                rows={2}
                className="flex-1 mr-3 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="Дополнительные указания"
              />
              {isEditing && (
                <button
                  onClick={() => handleArrayRemove('prescriptions', index)}
                  className="text-red-500 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        ))}
        
        {isEditing && (
          <button
            onClick={() => handleArrayAdd('prescriptions', {
              medication: '',
              dosage: '',
              administration: '',
              duration: '',
              notes: ''
            })}
            className="flex items-center gap-2 w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600"
          >
            <Plus className="h-4 w-4" />
            Добавить рецепт
          </button>
        )}
      </div>
    </div>
  );

  // Рендер направлений
  const renderReferrals = () => (
    <div className="space-y-6">
      <div className="bg-indigo-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">Направления</h3>
        <p className="text-sm text-gray-600">
          Направления к другим специалистам
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.referrals.map((referral, index) => (
          <div key={index} className="border rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Специалист
                </label>
                <select
                  value={referral.specialist || ''}
                  onChange={(e) => {
                    const newReferrals = [...formData.referrals];
                    newReferrals[index] = { ...referral, specialist: e.target.value };
                    handleInputChange('referrals', newReferrals);
                  }}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                >
                  <option value="">Выберите специалиста</option>
                  <option value="orthodontist">Ортодонт</option>
                  <option value="oral_surgeon">Челюстно-лицевой хирург</option>
                  <option value="periodontist">Пародонтолог</option>
                  <option value="endodontist">Эндодонтист</option>
                  <option value="prosthodontist">Ортопед</option>
                  <option value="radiologist">Рентгенолог</option>
                  <option value="therapist">Терапевт</option>
                  <option value="cardiologist">Кардиолог</option>
                  <option value="endocrinologist">Эндокринолог</option>
                  <option value="other">Другой</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Приоритет
                </label>
                <select
                  value={referral.priority || ''}
                  onChange={(e) => {
                    const newReferrals = [...formData.referrals];
                    newReferrals[index] = { ...referral, priority: e.target.value };
                    handleInputChange('referrals', newReferrals);
                  }}
                  disabled={!isEditing}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                >
                  <option value="">Выберите приоритет</option>
                  <option value="urgent">Срочно</option>
                  <option value="high">Высокий</option>
                  <option value="medium">Средний</option>
                  <option value="low">Низкий</option>
                </select>
              </div>
            </div>
            
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Причина направления
              </label>
              <textarea
                value={referral.reason || ''}
                onChange={(e) => {
                  const newReferrals = [...formData.referrals];
                  newReferrals[index] = { ...referral, reason: e.target.value };
                  handleInputChange('referrals', newReferrals);
                }}
                disabled={!isEditing}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="Опишите причину направления"
              />
            </div>
            
            <div className="flex items-center justify-between">
              <input
                type="text"
                value={referral.notes || ''}
                onChange={(e) => {
                  const newReferrals = [...formData.referrals];
                  newReferrals[index] = { ...referral, notes: e.target.value };
                  handleInputChange('referrals', newReferrals);
                }}
                disabled={!isEditing}
                className="flex-1 mr-3 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="Дополнительные указания"
              />
              {isEditing && (
                <button
                  onClick={() => handleArrayRemove('referrals', index)}
                  className="text-red-500 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        ))}
        
        {isEditing && (
          <button
            onClick={() => handleArrayAdd('referrals', {
              specialist: '',
              priority: '',
              reason: '',
              notes: ''
            })}
            className="flex items-center gap-2 w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600"
          >
            <Plus className="h-4 w-4" />
            Добавить направление
          </button>
        )}
      </div>
    </div>
  );

  // Рендер контента по вкладкам
  const renderTabContent = () => {
    switch (activeTab) {
      case 'tooth-diagnoses':
        return renderToothDiagnoses();
      case 'general-diagnoses':
        return renderGeneralDiagnoses();
      case 'treatment-plan':
        return renderTreatmentPlan();
      case 'prescriptions':
        return renderPrescriptions();
      case 'referrals':
        return renderReferrals();
      default:
        return renderToothDiagnoses();
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg w-full max-w-6xl h-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Заголовок */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-xl font-semibold">
              Диагнозы и назначения: {patientName}
            </h2>
            <p className="text-gray-600 text-sm">
              {formData.diagnosisDate} | {isEditing ? 'Режим редактирования' : 'Просмотр данных'}
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {!isEditing ? (
              <button
                onClick={() => setIsEditing(true)}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
              >
                <Edit className="h-4 w-4" />
                Редактировать
              </button>
            ) : (
              <>
                <button
                  onClick={() => setIsEditing(false)}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600"
                >
                  <X className="h-4 w-4" />
                  Отмена
                </button>
                <button
                  onClick={handleSave}
                  disabled={loading}
                  className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
                >
                  <Save className="h-4 w-4" />
                  {loading ? 'Сохранение...' : 'Сохранить'}
                </button>
              </>
            )}
            <button
              onClick={onClose}
              className="p-2 text-gray-500 hover:text-gray-700"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Вкладки */}
        <div className="border-b">
          <nav className="flex space-x-8 px-6">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {/* Контент */}
        <div className="flex-1 overflow-auto p-6">
          {renderTabContent()}
        </div>
      </div>
    </div>
  );
};

export default DiagnosisForm;
