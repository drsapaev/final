import React, { useState, useEffect } from 'react';
import { 
  User, 
  Phone, 
  Mail, 
  MapPin, 
  Calendar, 
  CreditCard, 
  Shield, 
  AlertTriangle,
  Edit,
  Save,
  X,
  Plus,
  Camera,
  FileText,
  Heart,
  Pill,
  Activity
} from 'lucide-react';

/**
 * Расширенная карточка пациента для стоматологической ЭМК
 * Включает все необходимые поля согласно медицинским стандартам
 */
const PatientCard = ({ 
  patient, 
  onSave, 
  onClose, 
  isEditMode = false 
}) => {
  const [formData, setFormData] = useState({
    // Основные данные
    id: '',
    name: '',
    surname: '',
    patronymic: '',
    birthDate: '',
    gender: '',
    phone: '',
    email: '',
    address: '',
    
    // Документы
    passport: {
      series: '',
      number: '',
      issuedBy: '',
      issueDate: '',
      departmentCode: ''
    },
    
    // Страхование
    insurance: {
      policyNumber: '',
      company: '',
      validUntil: '',
      type: 'voluntary' // voluntary, mandatory
    },
    
    // Экстренные контакты
    emergencyContact: {
      name: '',
      relationship: '',
      phone: '',
      address: ''
    },
    
    // Медицинский анамнез
    medicalHistory: {
      complaints: '',
      somaticDiseases: [],
      dentalHistory: '',
      allergies: [],
      currentMedications: [],
      bloodType: '',
      rhFactor: ''
    },
    
    // Дополнительная информация
    notes: '',
    createdAt: '',
    updatedAt: ''
  });

  const [isEditing, setIsEditing] = useState(isEditMode);
  const [activeTab, setActiveTab] = useState('basic');
  const [loading, setLoading] = useState(false);

  // Инициализация данных
  useEffect(() => {
    if (patient) {
      setFormData({
        ...formData,
        ...patient,
        medicalHistory: {
          ...formData.medicalHistory,
          ...patient.medicalHistory
        },
        passport: {
          ...formData.passport,
          ...patient.passport
        },
        insurance: {
          ...formData.insurance,
          ...patient.insurance
        },
        emergencyContact: {
          ...formData.emergencyContact,
          ...patient.emergencyContact
        }
      });
    }
  }, [patient]);

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

  const handleCancel = () => {
    if (patient) {
      setFormData(patient);
    }
    setIsEditing(false);
  };

  // Вкладки
  const tabs = [
    { id: 'basic', label: 'Основные данные', icon: User },
    { id: 'documents', label: 'Документы', icon: FileText },
    { id: 'medical', label: 'Мед. анамнез', icon: Heart },
    { id: 'emergency', label: 'Экстренные контакты', icon: AlertTriangle }
  ];

  // Рендер основных данных
  const renderBasicData = () => (
    <div className="space-y-6">
      {/* Личная информация */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Фамилия *
          </label>
          <input
            type="text"
            value={formData.surname || ''}
            onChange={(e) => handleInputChange('surname', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            required
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Имя *
          </label>
          <input
            type="text"
            value={formData.name || ''}
            onChange={(e) => handleInputChange('name', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            required
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Отчество
          </label>
          <input
            type="text"
            value={formData.patronymic || ''}
            onChange={(e) => handleInputChange('patronymic', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Дата рождения *
          </label>
          <input
            type="date"
            value={formData.birthDate || ''}
            onChange={(e) => handleInputChange('birthDate', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            required
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Пол *
          </label>
          <select
            value={formData.gender || ''}
            onChange={(e) => handleInputChange('gender', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            required
          >
            <option value="">Выберите пол</option>
            <option value="male">Мужской</option>
            <option value="female">Женский</option>
          </select>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Возраст
          </label>
          <input
            type="text"
            value={formData.birthDate ? 
              Math.floor((new Date() - new Date(formData.birthDate)) / (365.25 * 24 * 60 * 60 * 1000)) : ''
            }
            disabled
            className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-100"
          />
        </div>
      </div>

      {/* Контактная информация */}
      <div className="border-t pt-6">
        <h3 className="text-lg font-semibold mb-4">Контактная информация</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Телефон *
            </label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="tel"
                value={formData.phone || ''}
                onChange={(e) => handleInputChange('phone', e.target.value)}
                disabled={!isEditing}
                className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                required
              />
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Email
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="email"
                value={formData.email || ''}
                onChange={(e) => handleInputChange('email', e.target.value)}
                disabled={!isEditing}
                className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              />
            </div>
          </div>
          
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Адрес
            </label>
            <div className="relative">
              <MapPin className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
              <textarea
                value={formData.address || ''}
                onChange={(e) => handleInputChange('address', e.target.value)}
                disabled={!isEditing}
                rows={2}
                className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="Полный адрес проживания"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Рендер документов
  const renderDocuments = () => (
    <div className="space-y-6">
      {/* Паспортные данные */}
      <div className="border rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <CreditCard className="h-5 w-5" />
          Паспортные данные
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Серия
            </label>
            <input
              type="text"
              value={formData.passport.series || ''}
              onChange={(e) => handleInputChange('passport.series', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder="1234"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Номер
            </label>
            <input
              type="text"
              value={formData.passport.number || ''}
              onChange={(e) => handleInputChange('passport.number', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder="123456"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Выдан
            </label>
            <input
              type="text"
              value={formData.passport.issuedBy || ''}
              onChange={(e) => handleInputChange('passport.issuedBy', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder="Орган выдачи"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Дата выдачи
            </label>
            <input
              type="date"
              value={formData.passport.issueDate || ''}
              onChange={(e) => handleInputChange('passport.issueDate', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            />
          </div>
        </div>
      </div>

      {/* Страховые данные */}
      <div className="border rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Shield className="h-5 w-5" />
          Страховые данные
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Номер полиса
            </label>
            <input
              type="text"
              value={formData.insurance.policyNumber || ''}
              onChange={(e) => handleInputChange('insurance.policyNumber', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder="1234567890123456"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Страховая компания
            </label>
            <input
              type="text"
              value={formData.insurance.company || ''}
              onChange={(e) => handleInputChange('insurance.company', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder="Название страховой компании"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Действует до
            </label>
            <input
              type="date"
              value={formData.insurance.validUntil || ''}
              onChange={(e) => handleInputChange('insurance.validUntil', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Тип страхования
            </label>
            <select
              value={formData.insurance.type || ''}
              onChange={(e) => handleInputChange('insurance.type', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            >
              <option value="voluntary">Добровольное</option>
              <option value="mandatory">Обязательное</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );

  // Рендер медицинского анамнеза
  const renderMedicalHistory = () => (
    <div className="space-y-6">
      {/* Жалобы */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Жалобы на момент обращения
        </label>
        <textarea
          value={formData.medicalHistory.complaints || ''}
          onChange={(e) => handleInputChange('medicalHistory.complaints', e.target.value)}
          disabled={!isEditing}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          placeholder="Опишите жалобы пациента"
        />
      </div>

      {/* Соматические заболевания */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Соматические заболевания
        </label>
        <div className="space-y-2">
          {formData.medicalHistory.somaticDiseases.map((disease, index) => (
            <div key={index} className="flex items-center gap-2">
              <input
                type="text"
                value={disease}
                onChange={(e) => {
                  const newDiseases = [...formData.medicalHistory.somaticDiseases];
                  newDiseases[index] = e.target.value;
                  handleInputChange('medicalHistory.somaticDiseases', newDiseases);
                }}
                disabled={!isEditing}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="Название заболевания"
              />
              {isEditing && (
                <button
                  type="button"
                  onClick={() => handleArrayRemove('medicalHistory.somaticDiseases', index)}
                  className="text-red-500 hover:text-red-700"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
          {isEditing && (
            <button
              type="button"
              onClick={() => handleArrayAdd('medicalHistory.somaticDiseases', '')}
              className="flex items-center gap-2 text-blue-600 hover:text-blue-800"
            >
              <Plus className="h-4 w-4" />
              Добавить заболевание
            </button>
          )}
        </div>
      </div>

      {/* Аллергии */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Аллергии
        </label>
        <div className="space-y-2">
          {formData.medicalHistory.allergies.map((allergy, index) => (
            <div key={index} className="flex items-center gap-2">
              <input
                type="text"
                value={allergy}
                onChange={(e) => {
                  const newAllergies = [...formData.medicalHistory.allergies];
                  newAllergies[index] = e.target.value;
                  handleInputChange('medicalHistory.allergies', newAllergies);
                }}
                disabled={!isEditing}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="Аллерген (например: лидокаин, пенициллин)"
              />
              {isEditing && (
                <button
                  type="button"
                  onClick={() => handleArrayRemove('medicalHistory.allergies', index)}
                  className="text-red-500 hover:text-red-700"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
          {isEditing && (
            <button
              type="button"
              onClick={() => handleArrayAdd('medicalHistory.allergies', '')}
              className="flex items-center gap-2 text-blue-600 hover:text-blue-800"
            >
              <Plus className="h-4 w-4" />
              Добавить аллергию
            </button>
          )}
        </div>
      </div>

      {/* Текущие лекарства */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Текущие лекарства
        </label>
        <div className="space-y-2">
          {formData.medicalHistory.currentMedications.map((medication, index) => (
            <div key={index} className="flex items-center gap-2">
              <input
                type="text"
                value={medication}
                onChange={(e) => {
                  const newMedications = [...formData.medicalHistory.currentMedications];
                  newMedications[index] = e.target.value;
                  handleInputChange('medicalHistory.currentMedications', newMedications);
                }}
                disabled={!isEditing}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="Название лекарства и дозировка"
              />
              {isEditing && (
                <button
                  type="button"
                  onClick={() => handleArrayRemove('medicalHistory.currentMedications', index)}
                  className="text-red-500 hover:text-red-700"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
          {isEditing && (
            <button
              type="button"
              onClick={() => handleArrayAdd('medicalHistory.currentMedications', '')}
              className="flex items-center gap-2 text-blue-600 hover:text-blue-800"
            >
              <Plus className="h-4 w-4" />
              Добавить лекарство
            </button>
          )}
        </div>
      </div>

      {/* Группа крови */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Группа крови
          </label>
          <select
            value={formData.medicalHistory.bloodType || ''}
            onChange={(e) => handleInputChange('medicalHistory.bloodType', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          >
            <option value="">Не указана</option>
            <option value="A+">A+</option>
            <option value="A-">A-</option>
            <option value="B+">B+</option>
            <option value="B-">B-</option>
            <option value="AB+">AB+</option>
            <option value="AB-">AB-</option>
            <option value="O+">O+</option>
            <option value="O-">O-</option>
          </select>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Резус-фактор
          </label>
          <select
            value={formData.medicalHistory.rhFactor || ''}
            onChange={(e) => handleInputChange('medicalHistory.rhFactor', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          >
            <option value="">Не указан</option>
            <option value="positive">Положительный (+)</option>
            <option value="negative">Отрицательный (-)</option>
          </select>
        </div>
      </div>

      {/* Стоматологический анамнез */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Стоматологический анамнез
        </label>
        <textarea
          value={formData.medicalHistory.dentalHistory || ''}
          onChange={(e) => handleInputChange('medicalHistory.dentalHistory', e.target.value)}
          disabled={!isEditing}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          placeholder="Предыдущее стоматологическое лечение, импланты, протезы, ортодонтия"
        />
      </div>
    </div>
  );

  // Рендер экстренных контактов
  const renderEmergencyContacts = () => (
    <div className="space-y-6">
      <div className="border rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-orange-500" />
          Экстренный контакт
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              ФИО контактного лица
            </label>
            <input
              type="text"
              value={formData.emergencyContact.name || ''}
              onChange={(e) => handleInputChange('emergencyContact.name', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder="Фамилия Имя Отчество"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Родство
            </label>
            <select
              value={formData.emergencyContact.relationship || ''}
              onChange={(e) => handleInputChange('emergencyContact.relationship', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            >
              <option value="">Выберите родство</option>
              <option value="spouse">Супруг/супруга</option>
              <option value="parent">Родитель</option>
              <option value="child">Ребенок</option>
              <option value="sibling">Брат/сестра</option>
              <option value="other">Другое</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Телефон
            </label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
                type="tel"
                value={formData.emergencyContact.phone || ''}
                onChange={(e) => handleInputChange('emergencyContact.phone', e.target.value)}
                disabled={!isEditing}
                className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="+7 (999) 123-45-67"
              />
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Адрес
            </label>
            <input
              type="text"
              value={formData.emergencyContact.address || ''}
              onChange={(e) => handleInputChange('emergencyContact.address', e.target.value)}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder="Адрес проживания"
            />
          </div>
        </div>
      </div>
    </div>
  );

  // Рендер контента по вкладкам
  const renderTabContent = () => {
    switch (activeTab) {
      case 'basic':
        return renderBasicData();
      case 'documents':
        return renderDocuments();
      case 'medical':
        return renderMedicalHistory();
      case 'emergency':
        return renderEmergencyContacts();
      default:
        return renderBasicData();
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg w-full max-w-4xl h-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Заголовок */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-xl font-semibold">
              {patient ? `Карточка пациента: ${patient.surname} ${patient.name}` : 'Новый пациент'}
            </h2>
            <p className="text-gray-600 text-sm">
              {isEditing ? 'Режим редактирования' : 'Просмотр данных'}
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
                  onClick={handleCancel}
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

export default PatientCard;

