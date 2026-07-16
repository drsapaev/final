// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect } from 'react';
import logger from '../../utils/logger';
import {
  FileText,
  Pill,
  Stethoscope,
  Plus,
  Edit,
  Trash2,
  Save,
  X,

  AlertCircle,
  Clock,

  Calendar,


  Send } from
'lucide-react';
import PropTypes from 'prop-types';
import notify from '../../services/notify';

/**
 * Форма диагнозов и назначений для стоматологической ЭМК
 * Включает диагнозы по зубам, общие диагнозы, рецепты, направления
 */
const DiagnosisForm = ({
  patientName,
  initialData = null,
  onSave,
  onClose
}) => {
  const { t } = useTranslation();
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
      longTerm: [] // Долгосрочный план
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
      setFormData((prev) => ({
        ...prev,
        ...initialData
      }));
      setIsEditing(false);
    }
  }, [initialData]);

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

  const handleToothDiagnosisChange = (toothId, diagnosis) => {
    setFormData((prev) => ({
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
      logger.error('Ошибка сохранения:', error);
      notify.error(t('dental2.diagnosis_save_failed'));
    } finally {
      setLoading(false);
    }
  };

  // Вкладки
  const tabs = [
  { id: 'tooth-diagnoses', label: t('dental.dental_df_tab_tooth_diagnoses'), icon: Stethoscope },
  { id: 'general-diagnoses', label: t('dental.dental_df_tab_general_diagnoses'), icon: FileText },
  { id: 'treatment-plan', label: t('dental.dental_df_tab_treatment_plan'), icon: Calendar },
  { id: 'prescriptions', label: t('dental.dental_df_tab_prescriptions'), icon: Pill },
  { id: 'referrals', label: t('dental.dental_df_tab_referrals'), icon: Send }];


  // Стандартные диагнозы по зубам
  const standardToothDiagnoses = [
  { value: t('misc.df_karies'), label: t('dental.dental_df_dx_caries') },
  { value: t('misc.df_pulpit'), label: t('dental.dental_df_dx_pulpitis') },
  { value: t('misc.df_periodontit'), label: t('dental.dental_df_dx_periodontitis') },
  { value: t('misc.df_periapikalnyy_abstsess'), label: t('dental.dental_df_dx_periapical_abscess') },
  { value: t('misc.df_travma_zuba'), label: t('dental.dental_df_dx_tooth_trauma') },
  { value: t('misc.df_stiraemost'), label: t('dental.dental_df_dx_attrition') },
  { value: t('misc.df_eroziya'), label: t('dental.dental_df_dx_erosion') },
  { value: t('misc.df_gipoplaziya'), label: t('dental.dental_df_dx_hypoplasia') },
  { value: t('misc.df_flyuoroz'), label: t('dental.dental_df_dx_fluorosis') },
  { value: t('misc.df_zubnoy_kamen'), label: t('dental.dental_df_dx_calculus') },
  { value: t('misc.df_gingivit'), label: t('dental.dental_df_dx_gingivitis') },
  { value: t('misc.df_parodontit'), label: t('dental.dental_df_dx_marginal_periodontitis') },
  { value: t('misc.df_podvizhnost_zuba'), label: t('dental.dental_df_dx_tooth_mobility') },
  { value: t('misc.df_rezorbtsiya_kornya'), label: t('dental.dental_df_dx_root_resorption') },
  { value: t('misc.df_kista'), label: t('dental.dental_df_dx_cyst') },
  { value: t('misc.df_granulema'), label: t('dental.dental_df_dx_granuloma') },
  { value: t('misc.df_norma'), label: t('dental.dental_df_dx_normal') }];


  // Рендер диагнозов по зубам
  const renderToothDiagnoses = () =>
  <div className="space-y-6">
      <div className="bg-blue-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_df_tab_tooth_diagnoses')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_df_section_tooth_subtitle')}
        </p>
      </div>
      
      {/* Верхняя челюсть */}
      <div>
        <h4 className="font-semibold mb-3 text-gray-700">{t('dental.dental_df_upper_jaw')}</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28].map((toothId) =>
        <div key={toothId} className="border rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-sm">{t('dental.dental_df_tooth_label', { toothId })}</span>
                <div className="w-3 h-3 rounded-full bg-gray-200"></div>
              </div>
              <select
            value={formData.toothDiagnoses[toothId] || ''}
            onChange={(e) => handleToothDiagnosisChange(toothId, e.target.value)}
            disabled={!isEditing}
            className="w-full text-xs px-2 py-1 border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100">
            
                <option value="">{t('dental.dental_df_select_diagnosis')}</option>
                {standardToothDiagnoses.map((diagnosis) =>
            <option key={diagnosis.value} value={diagnosis.value}>{diagnosis.label}</option>
            )}
              </select>
            </div>
        )}
        </div>
      </div>
      
      {/* Нижняя челюсть */}
      <div>
        <h4 className="font-semibold mb-3 text-gray-700">{t('dental.dental_df_lower_jaw')}</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38].map((toothId) =>
        <div key={toothId} className="border rounded-lg p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-sm">{t('dental.dental_df_tooth_label', { toothId })}</span>
                <div className="w-3 h-3 rounded-full bg-gray-200"></div>
              </div>
              <select
            value={formData.toothDiagnoses[toothId] || ''}
            onChange={(e) => handleToothDiagnosisChange(toothId, e.target.value)}
            disabled={!isEditing}
            className="w-full text-xs px-2 py-1 border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100">
            
                <option value="">{t('dental.dental_df_select_diagnosis')}</option>
                {standardToothDiagnoses.map((diagnosis) =>
            <option key={diagnosis.value} value={diagnosis.value}>{diagnosis.label}</option>
            )}
              </select>
            </div>
        )}
        </div>
      </div>
    </div>;


  // Рендер общих диагнозов
  const renderGeneralDiagnoses = () =>
  <div className="space-y-6">
      <div className="bg-green-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_df_tab_general_diagnoses')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_df_section_general_subtitle')}
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.generalDiagnoses.map((diagnosis, index) =>
      <div key={index} className="flex items-center gap-3 p-3 border rounded-lg">
            <input
          type="text"
          aria-label={t('dental.dental_df_aria_general_diagnosis', { index: index + 1 })}
          value={diagnosis}
          onChange={(e) => {
            const newDiagnoses = [...formData.generalDiagnoses];
            newDiagnoses[index] = e.target.value;
            handleInputChange('generalDiagnoses', newDiagnoses);
          }}
          disabled={!isEditing}
          className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          placeholder={t('dental.dental_df_ph_enter_diagnosis')} />
        
            {isEditing &&
        <button
          onClick={() => handleArrayRemove('generalDiagnoses', index)}
          aria-label={t('dental.dental_df_aria_remove_general_diagnosis', { index: index + 1 })}
          className="text-red-500 hover:text-red-700">
          
                <Trash2 className="h-4 w-4" />
              </button>
        }
          </div>
      )}
        
        {isEditing &&
      <button
        onClick={() => handleArrayAdd('generalDiagnoses', '')}
        className="flex items-center gap-2 w-full p-3 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600">
        
            <Plus className="h-4 w-4" />
            {t('dental.dental_df_btn_add_diagnosis')}
          </button>
      }
      </div>
    </div>;


  // Рендер плана лечения
  const renderTreatmentPlan = () =>
  <div className="space-y-6">
      <div className="bg-yellow-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_df_tab_treatment_plan')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_df_section_treatment_subtitle')}
        </p>
      </div>
      
      {/* Немедленные меры */}
      <div>
        <h4 className="font-semibold mb-3 text-red-600 flex items-center gap-2">
          <AlertCircle className="h-4 w-4" />
          {t('dental.dental_df_immediate_title')}
        </h4>
        <div className="space-y-2">
          {formData.treatmentPlan.immediate.map((item, index) =>
        <div key={index} className="flex items-center gap-3 p-3 bg-red-50 border border-red-200 rounded-lg">
              <input
            type="text"
            aria-label={t('dental.dental_df_aria_immediate_item', { index: index + 1 })}
            value={item}
            onChange={(e) => {
              const newItems = [...formData.treatmentPlan.immediate];
              newItems[index] = e.target.value;
              handleInputChange('treatmentPlan.immediate', newItems);
            }}
            disabled={!isEditing}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_df_ph_immediate')} />
          
              {isEditing &&
          <button
            onClick={() => handleArrayRemove('treatmentPlan.immediate', index)}
            aria-label={t('dental.dental_df_aria_remove_immediate', { index: index + 1 })}
            className="text-red-500 hover:text-red-700">
            
                  <Trash2 className="h-4 w-4" />
                </button>
          }
            </div>
        )}
          {isEditing &&
        <button
          onClick={() => handleArrayAdd('treatmentPlan.immediate', '')}
          className="flex items-center gap-2 w-full p-3 border-2 border-dashed border-red-300 rounded-lg text-red-600 hover:border-red-500">
          
              <Plus className="h-4 w-4" />
              {t('dental.dental_df_btn_add_immediate')}
            </button>
        }
        </div>
      </div>
      
      {/* Краткосрочный план */}
      <div>
        <h4 className="font-semibold mb-3 text-orange-600 flex items-center gap-2">
          <Clock className="h-4 w-4" />
          {t('dental.dental_df_short_term_title')}
        </h4>
        <div className="space-y-2">
          {formData.treatmentPlan.shortTerm.map((item, index) =>
        <div key={index} className="flex items-center gap-3 p-3 bg-orange-50 border border-orange-200 rounded-lg">
              <input
            type="text"
            aria-label={t('dental.dental_df_aria_short_term_item', { index: index + 1 })}
            value={item}
            onChange={(e) => {
              const newItems = [...formData.treatmentPlan.shortTerm];
              newItems[index] = e.target.value;
              handleInputChange('treatmentPlan.shortTerm', newItems);
            }}
            disabled={!isEditing}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_df_ph_short_term')} />
          
              {isEditing &&
          <button
            onClick={() => handleArrayRemove('treatmentPlan.shortTerm', index)}
            aria-label={t('dental.dental_df_aria_remove_short_term', { index: index + 1 })}
            className="text-red-500 hover:text-red-700">
            
                  <Trash2 className="h-4 w-4" />
                </button>
          }
            </div>
        )}
          {isEditing &&
        <button
          onClick={() => handleArrayAdd('treatmentPlan.shortTerm', '')}
          className="flex items-center gap-2 w-full p-3 border-2 border-dashed border-orange-300 rounded-lg text-orange-600 hover:border-orange-500">
          
              <Plus className="h-4 w-4" />
              {t('dental.dental_df_btn_add_short_term')}
            </button>
        }
        </div>
      </div>
      
      {/* Долгосрочный план */}
      <div>
        <h4 className="font-semibold mb-3 text-blue-600 flex items-center gap-2">
          <Calendar className="h-4 w-4" />
          {t('dental.dental_df_long_term_title')}
        </h4>
        <div className="space-y-2">
          {formData.treatmentPlan.longTerm.map((item, index) =>
        <div key={index} className="flex items-center gap-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <input
            type="text"
            aria-label={t('dental.dental_df_aria_long_term_item', { index: index + 1 })}
            value={item}
            onChange={(e) => {
              const newItems = [...formData.treatmentPlan.longTerm];
              newItems[index] = e.target.value;
              handleInputChange('treatmentPlan.longTerm', newItems);
            }}
            disabled={!isEditing}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_df_ph_long_term')} />
          
              {isEditing &&
          <button
            onClick={() => handleArrayRemove('treatmentPlan.longTerm', index)}
            aria-label={t('dental.dental_df_aria_remove_long_term', { index: index + 1 })}
            className="text-red-500 hover:text-red-700">
            
                  <Trash2 className="h-4 w-4" />
                </button>
          }
            </div>
        )}
          {isEditing &&
        <button
          onClick={() => handleArrayAdd('treatmentPlan.longTerm', '')}
          className="flex items-center gap-2 w-full p-3 border-2 border-dashed border-blue-300 rounded-lg text-blue-600 hover:border-blue-500">
          
              <Plus className="h-4 w-4" />
              {t('dental.dental_df_btn_add_long_term')}
            </button>
        }
        </div>
      </div>
    </div>;


  // Рендер рецептов
  const renderPrescriptions = () =>
  <div className="space-y-6">
      <div className="bg-purple-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_df_tab_prescriptions')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_df_section_prescriptions_subtitle')}
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.prescriptions.map((prescription, index) =>
      <div key={index} className="border rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_df_label_medication')}
                </label>
                <input
              type="text"
              aria-label={t('dental.dental_df_aria_medication', { index: index + 1 })}
              value={prescription.medication || ''}
              onChange={(e) => {
                const newPrescriptions = [...formData.prescriptions];
                newPrescriptions[index] = { ...prescription, medication: e.target.value };
                handleInputChange('prescriptions', newPrescriptions);
              }}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_df_ph_medication')} />
            
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_df_label_dosage')}
                </label>
                <input
              type="text"
              aria-label={t('dental.dental_df_aria_dosage', { index: index + 1 })}
              value={prescription.dosage || ''}
              onChange={(e) => {
                const newPrescriptions = [...formData.prescriptions];
                newPrescriptions[index] = { ...prescription, dosage: e.target.value };
                handleInputChange('prescriptions', newPrescriptions);
              }}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_df_ph_dosage')} />
            
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_df_label_administration')}
                </label>
                <input
              type="text"
              aria-label={t('dental.dental_df_aria_administration', { index: index + 1 })}
              value={prescription.administration || ''}
              onChange={(e) => {
                const newPrescriptions = [...formData.prescriptions];
                newPrescriptions[index] = { ...prescription, administration: e.target.value };
                handleInputChange('prescriptions', newPrescriptions);
              }}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_df_ph_administration')} />
            
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_df_label_duration')}
                </label>
                <input
              type="text"
              aria-label={t('dental.dental_df_aria_duration', { index: index + 1 })}
              value={prescription.duration || ''}
              onChange={(e) => {
                const newPrescriptions = [...formData.prescriptions];
                newPrescriptions[index] = { ...prescription, duration: e.target.value };
                handleInputChange('prescriptions', newPrescriptions);
              }}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_df_ph_duration')} />
            
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <textarea
            aria-label={t('dental.dental_df_aria_prescription_notes', { index: index + 1 })}
            value={prescription.notes || ''}
            onChange={(e) => {
              const newPrescriptions = [...formData.prescriptions];
              newPrescriptions[index] = { ...prescription, notes: e.target.value };
              handleInputChange('prescriptions', newPrescriptions);
            }}
            disabled={!isEditing}
            rows={2}
            className="flex-1 mr-3 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_df_ph_additional_instructions')} />
          
              {isEditing &&
          <button
            onClick={() => handleArrayRemove('prescriptions', index)}
            aria-label={t('dental.dental_df_aria_remove_prescription', { index: index + 1 })}
            className="text-red-500 hover:text-red-700">
            
                  <Trash2 className="h-4 w-4" />
                </button>
          }
            </div>
          </div>
      )}
        
        {isEditing &&
      <button
        onClick={() => handleArrayAdd('prescriptions', {
          medication: '',
          dosage: '',
          administration: '',
          duration: '',
          notes: ''
        })}
        className="flex items-center gap-2 w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600">
        
            <Plus className="h-4 w-4" />
            {t('dental.dental_df_btn_add_prescription')}
          </button>
      }
      </div>
    </div>;


  // Рендер направлений
  const renderReferrals = () =>
  <div className="space-y-6">
      <div className="bg-indigo-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_df_tab_referrals')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_df_section_referrals_subtitle')}
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.referrals.map((referral, index) =>
      <div key={index} className="border rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_df_label_specialist')}
                </label>
                <select
              value={referral.specialist || ''}
              onChange={(e) => {
                const newReferrals = [...formData.referrals];
                newReferrals[index] = { ...referral, specialist: e.target.value };
                handleInputChange('referrals', newReferrals);
              }}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100">
              
                  <option value="">{t('dental.dental_df_select_specialist')}</option>
                  <option value="orthodontist">{t('dental.dental_df_specialist_orthodontist')}</option>
                  <option value="oral_surgeon">{t('dental.dental_df_specialist_oral_surgeon')}</option>
                  <option value="periodontist">{t('dental.dental_df_specialist_periodontist')}</option>
                  <option value="endodontist">{t('dental.dental_df_specialist_endodontist')}</option>
                  <option value="prosthodontist">{t('dental.dental_df_specialist_prosthodontist')}</option>
                  <option value="radiologist">{t('dental.dental_df_specialist_radiologist')}</option>
                  <option value="therapist">{t('dental.dental_df_specialist_therapist')}</option>
                  <option value="cardiologist">{t('dental.dental_df_specialist_cardiologist')}</option>
                  <option value="endocrinologist">{t('dental.dental_df_specialist_endocrinologist')}</option>
                  <option value="other">{t('dental.dental_df_specialist_other')}</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_df_label_priority')}
                </label>
                <select
              value={referral.priority || ''}
              onChange={(e) => {
                const newReferrals = [...formData.referrals];
                newReferrals[index] = { ...referral, priority: e.target.value };
                handleInputChange('referrals', newReferrals);
              }}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100">
              
                  <option value="">{t('dental.dental_df_select_priority')}</option>
                  <option value="urgent">{t('dental.dental_df_priority_urgent')}</option>
                  <option value="high">{t('dental.dental_df_priority_high')}</option>
                  <option value="medium">{t('dental.dental_df_priority_medium')}</option>
                  <option value="low">{t('dental.dental_df_priority_low')}</option>
                </select>
              </div>
            </div>
            
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('dental.dental_df_label_referral_reason')}
              </label>
              <textarea
            aria-label={t('dental.dental_df_aria_referral_reason', { index: index + 1 })}
            value={referral.reason || ''}
            onChange={(e) => {
              const newReferrals = [...formData.referrals];
              newReferrals[index] = { ...referral, reason: e.target.value };
              handleInputChange('referrals', newReferrals);
            }}
            disabled={!isEditing}
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_df_ph_referral_reason')} />
          
            </div>
            
            <div className="flex items-center justify-between">
              <input
            type="text"
            aria-label={t('dental.dental_df_aria_referral_notes', { index: index + 1 })}
            value={referral.notes || ''}
            onChange={(e) => {
              const newReferrals = [...formData.referrals];
              newReferrals[index] = { ...referral, notes: e.target.value };
              handleInputChange('referrals', newReferrals);
            }}
            disabled={!isEditing}
            className="flex-1 mr-3 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_df_ph_additional_instructions')} />
          
              {isEditing &&
          <button
            onClick={() => handleArrayRemove('referrals', index)}
            aria-label={t('dental.dental_df_aria_remove_referral', { index: index + 1 })}
            className="text-red-500 hover:text-red-700">
            
                  <Trash2 className="h-4 w-4" />
                </button>
          }
            </div>
          </div>
      )}
        
        {isEditing &&
      <button
        onClick={() => handleArrayAdd('referrals', {
          specialist: '',
          priority: '',
          reason: '',
          notes: ''
        })}
        className="flex items-center gap-2 w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600">
        
            <Plus className="h-4 w-4" />
            {t('dental.dental_df_btn_add_referral')}
          </button>
      }
      </div>
    </div>;


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
              {t('dental.dental_df_title', { name: patientName })}
            </h2>
            <p className="text-gray-600 text-sm">
              {formData.diagnosisDate} | {isEditing ? t('dental.dental_df_mode_edit') : t('dental.dental_df_mode_view')}
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {!isEditing ?
            <button
              onClick={() => setIsEditing(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
              
                <Edit className="h-4 w-4" />
                {t('dental.dental_df_btn_edit')}
              </button> :

            <>
                <button
                onClick={() => setIsEditing(false)}
                className="flex items-center gap-2 px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600">
                
                  <X className="h-4 w-4" />
                  {t('dental.dental_df_btn_cancel')}
                </button>
                <button
                onClick={handleSave}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50">
                
                  <Save className="h-4 w-4" />
                  {loading ? t('dental.dental_df_btn_saving') : t('dental.dental_df_btn_save')}
                </button>
              </>
            }
            <button
              onClick={onClose}
              aria-label={t('dental.dental_df_aria_close')}
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


DiagnosisForm.propTypes = {
  ...(DiagnosisForm.propTypes || {}),
  initialData: PropTypes.any,
  onClose: PropTypes.any,
  onSave: PropTypes.any,
  patientName: PropTypes.any,
};

export default DiagnosisForm;
