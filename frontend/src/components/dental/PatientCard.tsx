// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect } from 'react';
import logger from '../../utils/logger';
import {
  User,
  Phone,
  Mail,
  MapPin,

  CreditCard,
  Shield,
  AlertTriangle,
  Edit,
  Save,
  X,
  Plus,

  FileText,
  Heart } from


'lucide-react';
import PropTypes from 'prop-types';
import notify from '../../services/notify';

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
  const { t } = useTranslation();
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
      setFormData((prev) => ({
        ...prev,
        ...patient,
        medicalHistory: {
          ...prev.medicalHistory,
          ...patient.medicalHistory
        },
        passport: {
          ...prev.passport,
          ...patient.passport
        },
        insurance: {
          ...prev.insurance,
          ...patient.insurance
        },
        emergencyContact: {
          ...prev.emergencyContact,
          ...patient.emergencyContact
        }
      }));
    }
  }, [patient]);

  // Обработчики
  const handleInputChange = (field, value) => {
    if (field.includes('.')) {
      const [parent, child] = field.split('.');
      setFormData((prev) => ({
        ...prev,
        [parent]: {
          ...prev[parent],
          [child]: value
        }
      }));
    } else {
      setFormData((prev) => ({
        ...prev,
        [field]: value
      }));
    }
  };

  const handleArrayAdd = (field, item) => {
    setFormData((prev) => ({
      ...prev,
      [field]: [...prev[field], item]
    }));
  };

  const handleArrayRemove = (field, index) => {
    setFormData((prev) => ({
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
      logger.error('Ошибка сохранения:', error);
      notify.error(t('dental2.patient_save_failed'));
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
  { id: 'basic', label: t('dental.dental_pc_tab_basic'), icon: User },
  { id: 'documents', label: t('dental.dental_pc_tab_documents'), icon: FileText },
  { id: 'medical', label: t('dental.dental_pc_tab_medical'), icon: Heart },
  { id: 'emergency', label: t('dental.dental_pc_tab_emergency'), icon: AlertTriangle }];


  // Рендер основных данных
  const renderBasicData = () =>
  <div className="space-y-6">
      {/* Личная информация */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_pc_label_surname')}
          </label>
          <input
          type="text"
          aria-label={t('dental.dental_pc_aria_surname')}
          value={formData.surname || ''}
          onChange={(e) => handleInputChange('surname', e.target.value)}
          disabled={!isEditing}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          required />
        
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_pc_label_name')}
          </label>
          <input
          type="text"
          aria-label={t('dental.dental_pc_aria_name')}
          value={formData.name || ''}
          onChange={(e) => handleInputChange('name', e.target.value)}
          disabled={!isEditing}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          required />
        
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_pc_label_patronymic')}
          </label>
          <input
          type="text"
          aria-label={t('dental.dental_pc_aria_patronymic')}
          value={formData.patronymic || ''}
          onChange={(e) => handleInputChange('patronymic', e.target.value)}
          disabled={!isEditing}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
        
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_pc_label_birth_date')}
          </label>
          <input
          type="date"
          aria-label={t('dental.dental_pc_aria_birth_date')}
          value={formData.birthDate || ''}
          onChange={(e) => handleInputChange('birthDate', e.target.value)}
          disabled={!isEditing}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          required />
        
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_pc_label_gender')}
          </label>
          <select
          value={formData.gender || ''}
          onChange={(e) => handleInputChange('gender', e.target.value)}
          disabled={!isEditing}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          required>
          
            <option value="">{t('dental.dental_pc_select_gender')}</option>
            <option value="male">{t('dental.dental_pc_gender_male')}</option>
            <option value="female">{t('dental.dental_pc_gender_female')}</option>
          </select>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_pc_label_age')}
          </label>
          <input
          type="text"
          aria-label={t('dental.dental_pc_aria_age')}
          value={formData.birthDate ?
          Math.floor((new Date() - new Date(formData.birthDate)) / (365.25 * 24 * 60 * 60 * 1000)) : ''
          }
          disabled
          className="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-100" />
        
        </div>
      </div>

      {/* Контактная информация */}
      <div className="border-t pt-6">
        <h3 className="text-lg font-semibold mb-4">{t('dental.dental_pc_contact_info_title')}</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_phone')}
            </label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
              type="tel"
              aria-label={t('dental.dental_pc_aria_phone')}
              value={formData.phone || ''}
              onChange={(e) => handleInputChange('phone', e.target.value)}
              disabled={!isEditing}
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              required />
            
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_email')}
            </label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
              type="email"
              aria-label={t('dental.dental_pc_aria_email')}
              value={formData.email || ''}
              onChange={(e) => handleInputChange('email', e.target.value)}
              disabled={!isEditing}
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
            
            </div>
          </div>
          
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_address')}
            </label>
            <div className="relative">
              <MapPin className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
              <textarea
              aria-label={t('dental.dental_pc_aria_address')}
              value={formData.address || ''}
              onChange={(e) => handleInputChange('address', e.target.value)}
              disabled={!isEditing}
              rows={2}
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_pc_ph_address')} />
            
            </div>
          </div>
        </div>
      </div>
    </div>;


  // Рендер документов
  const renderDocuments = () =>
  <div className="space-y-6">
      {/* Паспортные данные */}
      <div className="border rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <CreditCard className="h-5 w-5" />
          {t('dental.dental_pc_passport_title')}
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_passport_series')}
            </label>
            <input
            type="text"
            aria-label={t('dental.dental_pc_aria_passport_series')}
            value={formData.passport.series || ''}
            onChange={(e) => handleInputChange('passport.series', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder="1234" />
          
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_passport_number')}
            </label>
            <input
            type="text"
            aria-label={t('dental.dental_pc_aria_passport_number')}
            value={formData.passport.number || ''}
            onChange={(e) => handleInputChange('passport.number', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder="123456" />
          
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_passport_issued_by')}
            </label>
            <input
            type="text"
            aria-label={t('dental.dental_pc_aria_passport_issued_by')}
            value={formData.passport.issuedBy || ''}
            onChange={(e) => handleInputChange('passport.issuedBy', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_pc_ph_passport_issued_by')} />
          
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_passport_issue_date')}
            </label>
            <input
            type="date"
            aria-label={t('dental.dental_pc_aria_passport_issue_date')}
            value={formData.passport.issueDate || ''}
            onChange={(e) => handleInputChange('passport.issueDate', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
          
          </div>
        </div>
      </div>

      {/* Страховые данные */}
      <div className="border rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Shield className="h-5 w-5" />
          {t('dental.dental_pc_insurance_title')}
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_policy_number')}
            </label>
            <input
            type="text"
            aria-label={t('dental.dental_pc_aria_policy_number')}
            value={formData.insurance.policyNumber || ''}
            onChange={(e) => handleInputChange('insurance.policyNumber', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder="1234567890123456" />
          
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_insurance_company')}
            </label>
            <input
            type="text"
            aria-label={t('dental.dental_pc_aria_insurance_company')}
            value={formData.insurance.company || ''}
            onChange={(e) => handleInputChange('insurance.company', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_pc_ph_insurance_company')} />
          
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_valid_until')}
            </label>
            <input
            type="date"
            aria-label={t('dental.dental_pc_aria_valid_until')}
            value={formData.insurance.validUntil || ''}
            onChange={(e) => handleInputChange('insurance.validUntil', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
          
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_insurance_type')}
            </label>
            <select
            value={formData.insurance.type || ''}
            onChange={(e) => handleInputChange('insurance.type', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100">
            
              <option value="voluntary">{t('dental.dental_pc_insurance_voluntary')}</option>
              <option value="mandatory">{t('dental.dental_pc_insurance_mandatory')}</option>
            </select>
          </div>
        </div>
      </div>
    </div>;


  // Рендер медицинского анамнеза
  const renderMedicalHistory = () =>
  <div className="space-y-6">
      {/* Жалобы */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {t('dental.dental_pc_label_complaints')}
        </label>
        <textarea
        aria-label={t('dental.dental_pc_aria_complaints')}
        value={formData.medicalHistory.complaints || ''}
        onChange={(e) => handleInputChange('medicalHistory.complaints', e.target.value)}
        disabled={!isEditing}
        rows={3}
        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
        placeholder={t('dental.dental_pc_ph_complaints')} />
      
      </div>

      {/* Соматические заболевания */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {t('dental.dental_pc_label_somatic_diseases')}
        </label>
        <div className="space-y-2">
          {formData.medicalHistory.somaticDiseases.map((disease, index) =>
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
            aria-label={t('dental.dental_pc_aria_somatic_disease', { index: index + 1 })}
            placeholder={t('dental.dental_pc_ph_disease_name')} />
          
              {isEditing &&
          <button
            type="button"
            onClick={() => handleArrayRemove('medicalHistory.somaticDiseases', index)}
            aria-label={t('dental.dental_pc_aria_remove_somatic_disease', { index: index + 1 })}
            className="text-red-500 hover:text-red-700">
            
                  <X className="h-4 w-4" />
                </button>
          }
            </div>
        )}
          {isEditing &&
        <button
          type="button"
          onClick={() => handleArrayAdd('medicalHistory.somaticDiseases', '')}
          className="flex items-center gap-2 text-blue-600 hover:text-blue-800">
          
              <Plus className="h-4 w-4" />
              {t('dental.dental_pc_btn_add_disease')}
            </button>
        }
        </div>
      </div>

      {/* Аллергии */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {t('dental.dental_pc_label_allergies')}
        </label>
        <div className="space-y-2">
          {formData.medicalHistory.allergies.map((allergy, index) =>
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
            aria-label={t('dental.dental_pc_aria_allergy', { index: index + 1 })}
            placeholder={t('dental.dental_pc_ph_allergy')} />
          
              {isEditing &&
          <button
            type="button"
            onClick={() => handleArrayRemove('medicalHistory.allergies', index)}
            aria-label={t('dental.dental_pc_aria_remove_allergy', { index: index + 1 })}
            className="text-red-500 hover:text-red-700">
            
                  <X className="h-4 w-4" />
                </button>
          }
            </div>
        )}
          {isEditing &&
        <button
          type="button"
          onClick={() => handleArrayAdd('medicalHistory.allergies', '')}
          className="flex items-center gap-2 text-blue-600 hover:text-blue-800">
          
              <Plus className="h-4 w-4" />
              {t('dental.dental_pc_btn_add_allergy')}
            </button>
        }
        </div>
      </div>

      {/* Текущие лекарства */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {t('dental.dental_pc_label_current_medications')}
        </label>
        <div className="space-y-2">
          {formData.medicalHistory.currentMedications.map((medication, index) =>
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
            aria-label={t('dental.dental_pc_aria_medication', { index: index + 1 })}
            placeholder={t('dental.dental_pc_ph_medication')} />
          
              {isEditing &&
          <button
            type="button"
            onClick={() => handleArrayRemove('medicalHistory.currentMedications', index)}
            aria-label={t('dental.dental_pc_aria_remove_medication', { index: index + 1 })}
            className="text-red-500 hover:text-red-700">
            
                  <X className="h-4 w-4" />
                </button>
          }
            </div>
        )}
          {isEditing &&
        <button
          type="button"
          onClick={() => handleArrayAdd('medicalHistory.currentMedications', '')}
          className="flex items-center gap-2 text-blue-600 hover:text-blue-800">
          
              <Plus className="h-4 w-4" />
              {t('dental.dental_pc_btn_add_medication')}
            </button>
        }
        </div>
      </div>

      {/* Группа крови */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_pc_label_blood_type')}
          </label>
          <select
          value={formData.medicalHistory.bloodType || ''}
          onChange={(e) => handleInputChange('medicalHistory.bloodType', e.target.value)}
          disabled={!isEditing}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100">
          
            <option value="">{t('dental.dental_pc_blood_not_specified')}</option>
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
            {t('dental.dental_pc_label_rh_factor')}
          </label>
          <select
          value={formData.medicalHistory.rhFactor || ''}
          onChange={(e) => handleInputChange('medicalHistory.rhFactor', e.target.value)}
          disabled={!isEditing}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100">
          
            <option value="">{t('dental.dental_pc_rh_not_specified')}</option>
            <option value="positive">{t('dental.dental_pc_rh_positive')}</option>
            <option value="negative">{t('dental.dental_pc_rh_negative')}</option>
          </select>
        </div>
      </div>

      {/* Стоматологический анамнез */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {t('dental.dental_pc_label_dental_history')}
        </label>
        <textarea
        aria-label={t('dental.dental_pc_aria_dental_history')}
        value={formData.medicalHistory.dentalHistory || ''}
        onChange={(e) => handleInputChange('medicalHistory.dentalHistory', e.target.value)}
        disabled={!isEditing}
        rows={3}
        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
        placeholder={t('dental.dental_pc_ph_dental_history')} />
      
      </div>
    </div>;


  // Рендер экстренных контактов
  const renderEmergencyContacts = () =>
  <div className="space-y-6">
      <div className="border rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-orange-500" />
          {t('dental.dental_pc_emergency_title')}
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_emergency_name')}
            </label>
            <input
            type="text"
            aria-label={t('dental.dental_pc_aria_emergency_name')}
            value={formData.emergencyContact.name || ''}
            onChange={(e) => handleInputChange('emergencyContact.name', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_pc_ph_emergency_name')} />
          
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_relationship')}
            </label>
            <select
            value={formData.emergencyContact.relationship || ''}
            onChange={(e) => handleInputChange('emergencyContact.relationship', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100">
            
              <option value="">{t('dental.dental_pc_select_relationship')}</option>
              <option value="spouse">{t('dental.dental_pc_rel_spouse')}</option>
              <option value="parent">{t('dental.dental_pc_rel_parent')}</option>
              <option value="child">{t('dental.dental_pc_rel_child')}</option>
              <option value="sibling">{t('dental.dental_pc_rel_sibling')}</option>
              <option value="other">{t('dental.dental_pc_rel_other')}</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_emergency_phone')}
            </label>
            <div className="relative">
              <Phone className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <input
              type="tel"
              aria-label={t('dental.dental_pc_aria_emergency_phone')}
              value={formData.emergencyContact.phone || ''}
              onChange={(e) => handleInputChange('emergencyContact.phone', e.target.value)}
              disabled={!isEditing}
              className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder="+7 (999) 123-45-67" />
            
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_pc_label_emergency_address')}
            </label>
            <input
            type="text"
            aria-label={t('dental.dental_pc_aria_emergency_address')}
            value={formData.emergencyContact.address || ''}
            onChange={(e) => handleInputChange('emergencyContact.address', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_pc_ph_emergency_address')} />
          
          </div>
        </div>
      </div>
    </div>;


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
              {patient ? t('dental.dental_pc_title_with_patient', { name: `${patient.surname} ${patient.name}` }) : t('dental.dental_pc_title_new')}
            </h2>
            <p className="text-gray-600 text-sm">
              {isEditing ? t('dental.dental_pc_mode_edit') : t('dental.dental_pc_mode_view')}
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {!isEditing ?
            <button
              onClick={() => setIsEditing(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
              
                <Edit className="h-4 w-4" />
                {t('dental.dental_pc_btn_edit')}
              </button> :

            <>
                <button
                onClick={handleCancel}
                className="flex items-center gap-2 px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600">
                
                  <X className="h-4 w-4" />
                  {t('dental.dental_pc_btn_cancel')}
                </button>
                <button
                onClick={handleSave}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50">
                
                  <Save className="h-4 w-4" />
                  {loading ? t('dental.dental_pc_btn_saving') : t('dental.dental_pc_btn_save')}
                </button>
              </>
            }
            <button
              onClick={onClose}
              aria-label={t('dental.dental_pc_aria_close', { name: `${formData.surname || ''} ${formData.name || ''}`.trim() })}
              className="p-2 text-gray-500 hover:text-gray-700">
              
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Вкладки */}
        <div className="border-b">
          <nav className="flex space-x-8 px-6">
            {tabs.map((tab) =>
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === tab.id ?
              'border-blue-500 text-blue-600' :
              'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`
              }>
              
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            )}
          </nav>
        </div>

        {/* Контент */}
        <div className="flex-1 overflow-auto p-6">
          {renderTabContent()}
        </div>
      </div>
    </div>);

};


PatientCard.propTypes = {
  ...(PatientCard.propTypes || {}),
  emergencyContact: PropTypes.any,
  insurance: PropTypes.any,
  isEditMode: PropTypes.any,
  medicalHistory: PropTypes.any,
  name: PropTypes.any,
  onClose: PropTypes.any,
  onSave: PropTypes.any,
  passport: PropTypes.any,
  patient: PropTypes.any,
  surname: PropTypes.any,
};

export default PatientCard;
