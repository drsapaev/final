// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect } from 'react';
import logger from '../../utils/logger';
import { Camera, Check, Edit, FileText, Pill, Plus, Save, Scissors, Syringe, Trash2, Upload, X } from 'lucide-react';
import PropTypes from 'prop-types';
import notify from '../../services/notify';

/**
 * Протокол лечения по визитам для стоматологической ЭМК
 * Включает процедуры, материалы, анестезию, фото до/после
 */
const VisitProtocol = ({
  patientName,
  initialData = null,
  onSave,
  onClose,
  onComplete
}) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState({
    // Основные данные визита
    visitDate: new Date().toISOString().split('T')[0],
    visitTime: new Date().toTimeString().slice(0, 5),
    doctor: '',
    assistant: '',

    // Жалобы и анамнез
    chiefComplaint: '',
    historyOfPresentIllness: '',

    // Выполненные процедуры
    procedures: [],

    // Использованные материалы
    materials: [],

    // Анестезия
    anesthesia: [],

    // Фотофиксация
    photos: {
      before: [],
      during: [],
      after: []
    },

    // Рентгенологические данные
    radiographs: [],

    // Назначения
    prescriptions: [],
    recommendations: '',

    // Следующий визит
    nextVisit: {
      date: '',
      time: '',
      purpose: ''
    },

    // Метаданные
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  });

  const [isEditing, setIsEditing] = useState(true);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('procedures');

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

  const handleArrayUpdate = (field, index, updates) => {
    setFormData((prev) => ({
      ...prev,
      [field]: prev[field].map((item, i) =>
      i === index ? { ...item, ...updates } : item
      )
    }));
  };

  const handlePhotoUpload = (category, file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const photoData = {
        id: Date.now(),
        url: e.target.result,
        filename: file.name,
        size: file.size,
        type: file.type,
        uploadedAt: new Date().toISOString(),
        description: ''
      };

      handleArrayAdd(`photos.${category}`, photoData);
    };
    reader.readAsDataURL(file);
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
      notify.error(t('dental2.visit_protocol_save_failed'));
    } finally {
      setLoading(false);
    }
  };

  // Вкладки
  const tabs = [
  { id: 'procedures', label: t('dental.dental_vp_tab_procedures'), icon: Scissors },
  { id: 'materials', label: t('dental.dental_vp_tab_materials'), icon: Pill },
  { id: 'anesthesia', label: t('dental.dental_vp_tab_anesthesia'), icon: Syringe },
  { id: 'photos', label: t('dental.dental_vp_tab_photos'), icon: Camera },
  { id: 'radiographs', label: t('dental.dental_vp_tab_radiographs'), icon: FileText },
  { id: 'prescriptions', label: t('dental.dental_vp_tab_prescriptions'), icon: Pill }];


  // Стандартные процедуры
  const standardProcedures = [
  t('dental.dental_vp_std_proc_oral_exam'),
  t('dental.dental_vp_std_proc_prof_hygiene'),
  t('dental.dental_vp_std_proc_caries'),
  t('dental.dental_vp_std_proc_endo'),
  t('dental.dental_vp_std_proc_filling'),
  t('dental.dental_vp_std_proc_crown_restore'),
  t('dental.dental_vp_std_proc_extraction'),
  t('dental.dental_vp_std_proc_implant'),
  t('dental.dental_vp_std_proc_prosthetics'),
  t('dental.dental_vp_std_proc_ortho'),
  t('dental.dental_vp_std_proc_perio'),
  t('dental.dental_vp_std_proc_surgery'),
  t('dental.dental_vp_std_proc_consult'),
  t('dental.dental_vp_std_proc_checkup')];


  // Рендер процедур
  const renderProcedures = () =>
  <div className="space-y-6">
      <div className="bg-blue-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_vp_proc_title')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_vp_proc_subtitle')}
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.procedures.map((procedure, index) =>
      <div key={index} className="border rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_proc_label_name')}
                </label>
                <select
              value={procedure.name || ''}
              onChange={(e) => handleArrayUpdate('procedures', index, { name: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100">
              
                  <option value="">{t('dental.dental_vp_proc_select_placeholder')}</option>
                  {standardProcedures.map((proc) =>
              <option key={proc} value={proc}>{proc}</option>
              )}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_proc_label_teeth')}
                </label>
                <input
              type="text"
              aria-label={t('dental.dental_vp_proc_aria_teeth', { index: index + 1 })}
              value={procedure.teeth || ''}
              onChange={(e) => handleArrayUpdate('procedures', index, { teeth: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_vp_proc_ph_teeth')} />
            
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_proc_label_start')}
                </label>
                <input
              type="time"
              aria-label={t('dental.dental_vp_proc_aria_start', { index: index + 1 })}
              value={procedure.startTime || ''}
              onChange={(e) => handleArrayUpdate('procedures', index, { startTime: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
            
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_proc_label_end')}
                </label>
                <input
              type="time"
              aria-label={t('dental.dental_vp_proc_aria_end', { index: index + 1 })}
              value={procedure.endTime || ''}
              onChange={(e) => handleArrayUpdate('procedures', index, { endTime: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
            
              </div>
            </div>
            
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('dental.dental_vp_proc_label_desc')}
              </label>
              <textarea
            aria-label={t('dental.dental_vp_proc_aria_desc', { index: index + 1 })}
            value={procedure.description || ''}
            onChange={(e) => handleArrayUpdate('procedures', index, { description: e.target.value })}
            disabled={!isEditing}
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_vp_proc_ph_desc')} />
          
            </div>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input
                type="checkbox"
                aria-label={t('dental.dental_vp_proc_aria_completed', { index: index + 1 })}
                checked={procedure.completed || false}
                onChange={(e) => handleArrayUpdate('procedures', index, { completed: e.target.checked })}
                disabled={!isEditing}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
              
                  <span className="text-sm text-gray-700">{t('dental.dental_vp_proc_chk_completed')}</span>
                </label>
                
                <label className="flex items-center gap-2">
                  <input
                type="checkbox"
                aria-label={t('dental.dental_vp_proc_aria_complications', { index: index + 1 })}
                checked={procedure.complications || false}
                onChange={(e) => handleArrayUpdate('procedures', index, { complications: e.target.checked })}
                disabled={!isEditing}
                className="rounded border-gray-300 text-red-600 focus:ring-red-500" />
              
                  <span className="text-sm text-gray-700">{t('dental.dental_vp_proc_chk_complications')}</span>
                </label>
              </div>
              
              {isEditing &&
          <button
            onClick={() => handleArrayRemove('procedures', index)}
            aria-label={t('dental.dental_vp_proc_aria_remove', { index: index + 1 })}
            className="text-red-500 hover:text-red-700">
            
                  <Trash2 className="h-4 w-4" />
                </button>
          }
            </div>
          </div>
      )}
        
        {isEditing &&
      <button
        onClick={() => handleArrayAdd('procedures', {
          name: '',
          teeth: '',
          startTime: '',
          endTime: '',
          description: '',
          completed: false,
          complications: false
        })}
        className="flex items-center gap-2 w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600">
        
            <Plus className="h-4 w-4" />
            {t('dental.dental_vp_proc_btn_add')}
          </button>
      }
      </div>
    </div>;


  // Рендер материалов
  const renderMaterials = () =>
  <div className="space-y-6">
      <div className="bg-green-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_vp_mat_title')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_vp_mat_subtitle')}
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.materials.map((material, index) =>
      <div key={index} className="border rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_mat_label_name')}
                </label>
                <input
              type="text"
              aria-label={t('dental.dental_vp_mat_aria_name', { index: index + 1 })}
              value={material.name || ''}
              onChange={(e) => handleArrayUpdate('materials', index, { name: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_vp_mat_ph_name')} />
            
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_mat_label_quantity')}
                </label>
                <input
              type="text"
              aria-label={t('dental.dental_vp_mat_aria_quantity', { index: index + 1 })}
              value={material.quantity || ''}
              onChange={(e) => handleArrayUpdate('materials', index, { quantity: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_vp_mat_ph_quantity')} />
            
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_mat_label_batch')}
                </label>
                <input
              type="text"
              aria-label={t('dental.dental_vp_mat_aria_batch', { index: index + 1 })}
              value={material.batch || ''}
              onChange={(e) => handleArrayUpdate('materials', index, { batch: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_vp_mat_ph_batch')} />
            
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <textarea
            aria-label={t('dental.dental_vp_mat_aria_notes', { index: index + 1 })}
            value={material.notes || ''}
            onChange={(e) => handleArrayUpdate('materials', index, { notes: e.target.value })}
            disabled={!isEditing}
            rows={2}
            className="flex-1 mr-3 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_vp_mat_ph_notes')} />
          
              {isEditing &&
          <button
            onClick={() => handleArrayRemove('materials', index)}
            aria-label={t('dental.dental_vp_mat_aria_remove', { index: index + 1 })}
            className="text-red-500 hover:text-red-700">
            
                  <Trash2 className="h-4 w-4" />
                </button>
          }
            </div>
          </div>
      )}
        
        {isEditing &&
      <button
        onClick={() => handleArrayAdd('materials', {
          name: '',
          quantity: '',
          batch: '',
          notes: ''
        })}
        className="flex items-center gap-2 w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600">
        
            <Plus className="h-4 w-4" />
            {t('dental.dental_vp_mat_btn_add')}
          </button>
      }
      </div>
    </div>;


  // Рендер анестезии
  const renderAnesthesia = () =>
  <div className="space-y-6">
      <div className="bg-purple-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_vp_anes_title')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_vp_anes_subtitle')}
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.anesthesia.map((anesthesia, index) =>
      <div key={index} className="border rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_anes_label_drug')}
                </label>
                <input
              type="text"
              aria-label={t('dental.dental_vp_anes_aria_drug', { index: index + 1 })}
              value={anesthesia.drug || ''}
              onChange={(e) => handleArrayUpdate('anesthesia', index, { drug: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_vp_anes_ph_drug')} />
            
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_anes_label_dose')}
                </label>
                <input
              type="text"
              aria-label={t('dental.dental_vp_anes_aria_dose', { index: index + 1 })}
              value={anesthesia.dose || ''}
              onChange={(e) => handleArrayUpdate('anesthesia', index, { dose: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_vp_anes_ph_dose')} />
            
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_anes_label_method')}
                </label>
                <select
              value={anesthesia.method || ''}
              onChange={(e) => handleArrayUpdate('anesthesia', index, { method: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100">
              
                  <option value="">{t('dental.dental_vp_anes_select_placeholder')}</option>
                  <option value="infiltration">{t('dental.dental_vp_anes_method_infiltration')}</option>
                  <option value="conduction">{t('dental.dental_vp_anes_method_conduction')}</option>
                  <option value="intraligamentary">{t('dental.dental_vp_anes_method_intraligamentary')}</option>
                  <option value="intraosseous">{t('dental.dental_vp_anes_method_intraosseous')}</option>
                  <option value="topical">{t('dental.dental_vp_anes_method_topical')}</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_anes_label_area')}
                </label>
                <input
              type="text"
              aria-label={t('dental.dental_vp_anes_aria_area', { index: index + 1 })}
              value={anesthesia.area || ''}
              onChange={(e) => handleArrayUpdate('anesthesia', index, { area: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_vp_anes_ph_area')} />
            
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input
                type="checkbox"
                aria-label={t('dental.dental_vp_anes_aria_effective', { index: index + 1 })}
                checked={anesthesia.effective || false}
                onChange={(e) => handleArrayUpdate('anesthesia', index, { effective: e.target.checked })}
                disabled={!isEditing}
                className="rounded border-gray-300 text-green-600 focus:ring-green-500" />
              
                  <span className="text-sm text-gray-700">{t('dental.dental_vp_anes_chk_effective')}</span>
                </label>
                
                <label className="flex items-center gap-2">
                  <input
                type="checkbox"
                aria-label={t('dental.dental_vp_anes_aria_complications', { index: index + 1 })}
                checked={anesthesia.complications || false}
                onChange={(e) => handleArrayUpdate('anesthesia', index, { complications: e.target.checked })}
                disabled={!isEditing}
                className="rounded border-gray-300 text-red-600 focus:ring-red-500" />
              
                  <span className="text-sm text-gray-700">{t('dental.dental_vp_anes_chk_complications')}</span>
                </label>
              </div>
              
              {isEditing &&
          <button
            onClick={() => handleArrayRemove('anesthesia', index)}
            aria-label={t('dental.dental_vp_anes_aria_remove', { index: index + 1 })}
            className="text-red-500 hover:text-red-700">
            
                  <Trash2 className="h-4 w-4" />
                </button>
          }
            </div>
          </div>
      )}
        
        {isEditing &&
      <button
        onClick={() => handleArrayAdd('anesthesia', {
          drug: '',
          dose: '',
          method: '',
          area: '',
          effective: false,
          complications: false
        })}
        className="flex items-center gap-2 w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600">
        
            <Plus className="h-4 w-4" />
            {t('dental.dental_vp_anes_btn_add')}
          </button>
      }
      </div>
    </div>;


  // Рендер фотофиксации
  const renderPhotos = () =>
  <div className="space-y-6">
      <div className="bg-orange-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_vp_photo_title')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_vp_photo_subtitle')}
        </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {['before', 'during', 'after'].map((category) =>
      <div key={category}>
            <h4 className="font-semibold mb-3 capitalize">
              {category === 'before' ? t('dental.dental_vp_photo_before') :
          category === 'during' ? t('dental.dental_vp_photo_during') : t('dental.dental_vp_photo_after')}
            </h4>
            <div className="space-y-2">
              {formData.photos[category].map((photo, index) =>
          <div key={photo.id} className="flex items-center gap-2 p-2 border rounded">
                  <Camera className="h-4 w-4 text-blue-500" />
                  <span className="text-sm flex-1">{photo.filename}</span>
                  {isEditing &&
            <button
              onClick={() => handleArrayRemove(`photos.${category}`, index)}
              aria-label={t('dental.dental_vp_photo_aria_remove', { index: index + 1 })}
              className="text-red-500 hover:text-red-700">
              
                      <Trash2 className="h-4 w-4" />
                    </button>
            }
                </div>
          )}
              {isEditing &&
          <label className="flex items-center gap-2 p-2 border-2 border-dashed border-gray-300 rounded cursor-pointer hover:border-blue-500">
                  <Upload className="h-4 w-4" />
                  <span className="text-sm">{t('dental.dental_vp_photo_btn_upload')}</span>
                  <input
              type="file"
              aria-label={t('dental.dental_vp_photo_aria_upload', { category })}
              accept="image/*"
              onChange={(e) => {
                if (e.target.files[0]) {
                  handlePhotoUpload(category, e.target.files[0]);
                }
              }}
              className="hidden" />
            
                </label>
          }
            </div>
          </div>
      )}
      </div>
    </div>;


  // Рендер рентгенов
  const renderRadiographs = () =>
  <div className="space-y-6">
      <div className="bg-cyan-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_vp_radio_title')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_vp_radio_subtitle')}
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.radiographs.map((radiograph, index) =>
      <div key={index} className="border rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_radio_label_type')}
                </label>
                <select
              value={radiograph.type || ''}
              onChange={(e) => handleArrayUpdate('radiographs', index, { type: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100">
              
                  <option value="">{t('dental.dental_vp_radio_select_placeholder')}</option>
                  <option value="periapical">{t('dental.dental_vp_radio_type_periapical')}</option>
                  <option value="bitewing">{t('dental.dental_vp_radio_type_bitewing')}</option>
                  <option value="panoramic">{t('dental.dental_vp_radio_type_panoramic')}</option>
                  <option value="cbct">{t('dental.dental_vp_radio_type_cbct')}</option>
                  <option value="lateral">{t('dental.dental_vp_radio_type_lateral')}</option>
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_radio_label_area')}
                </label>
                <input
              type="text"
              aria-label={t('dental.dental_vp_radio_aria_area', { index: index + 1 })}
              value={radiograph.area || ''}
              onChange={(e) => handleArrayUpdate('radiographs', index, { area: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_vp_radio_ph_area')} />
            
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <textarea
            aria-label={t('dental.dental_vp_radio_aria_findings', { index: index + 1 })}
            value={radiograph.findings || ''}
            onChange={(e) => handleArrayUpdate('radiographs', index, { findings: e.target.value })}
            disabled={!isEditing}
            rows={2}
            className="flex-1 mr-3 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_vp_radio_ph_findings')} />
          
              {isEditing &&
          <button
            onClick={() => handleArrayRemove('radiographs', index)}
            aria-label={t('dental.dental_vp_radio_aria_remove', { index: index + 1 })}
            className="text-red-500 hover:text-red-700">
            
                  <Trash2 className="h-4 w-4" />
                </button>
          }
            </div>
          </div>
      )}
        
        {isEditing &&
      <button
        onClick={() => handleArrayAdd('radiographs', {
          type: '',
          area: '',
          findings: ''
        })}
        className="flex items-center gap-2 w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600">
        
            <Plus className="h-4 w-4" />
            {t('dental.dental_vp_radio_btn_add')}
          </button>
      }
      </div>
    </div>;


  // Рендер назначений
  const renderPrescriptions = () =>
  <div className="space-y-6">
      <div className="bg-red-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_vp_rx_title')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_vp_rx_subtitle')}
        </p>
      </div>
      
      <div className="space-y-4">
        {formData.prescriptions.map((prescription, index) =>
      <div key={index} className="border rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_rx_label_medication')}
                </label>
                <input
              type="text"
              aria-label={t('dental.dental_vp_rx_aria_medication', { index: index + 1 })}
              value={prescription.medication || ''}
              onChange={(e) => handleArrayUpdate('prescriptions', index, { medication: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_vp_rx_ph_medication')} />
            
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('dental.dental_vp_rx_label_dosage')}
                </label>
                <input
              type="text"
              aria-label={t('dental.dental_vp_rx_aria_dosage', { index: index + 1 })}
              value={prescription.dosage || ''}
              onChange={(e) => handleArrayUpdate('prescriptions', index, { dosage: e.target.value })}
              disabled={!isEditing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
              placeholder={t('dental.dental_vp_rx_ph_dosage')} />
            
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <textarea
            aria-label={t('dental.dental_vp_rx_aria_instructions', { index: index + 1 })}
            value={prescription.instructions || ''}
            onChange={(e) => handleArrayUpdate('prescriptions', index, { instructions: e.target.value })}
            disabled={!isEditing}
            rows={2}
            className="flex-1 mr-3 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_vp_rx_ph_instructions')} />
          
              {isEditing &&
          <button
            onClick={() => handleArrayRemove('prescriptions', index)}
            aria-label={t('dental.dental_vp_rx_aria_remove', { index: index + 1 })}
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
          instructions: ''
        })}
        className="flex items-center gap-2 w-full p-4 border-2 border-dashed border-gray-300 rounded-lg text-gray-600 hover:border-blue-500 hover:text-blue-600">
        
            <Plus className="h-4 w-4" />
            {t('dental.dental_vp_rx_btn_add')}
          </button>
      }
      </div>
      
      {/* Рекомендации */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {t('dental.dental_vp_label_recommendations')}
        </label>
        <textarea
        aria-label={t('dental.dental_vp_aria_recommendations')}
        value={formData.recommendations || ''}
        onChange={(e) => handleInputChange('recommendations', e.target.value)}
        disabled={!isEditing}
        rows={4}
        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
        placeholder={t('dental.dental_vp_ph_recommendations')} />
      
      </div>
      
      {/* Следующий визит */}
      <div className="border-t pt-4">
        <h4 className="font-semibold mb-3">{t('dental.dental_vp_next_visit_title')}</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('dental.dental_vp_next_visit_label_date')}
            </label>
            <input
            type="date"
            aria-label={t('dental.dental_vp_next_visit_aria_date')}
            value={formData.nextVisit.date || ''}
            onChange={(e) => handleInputChange('nextVisit.date', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
          
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('dental.dental_vp_next_visit_label_time')}
            </label>
            <input
            type="time"
            aria-label={t('dental.dental_vp_next_visit_aria_time')}
            value={formData.nextVisit.time || ''}
            onChange={(e) => handleInputChange('nextVisit.time', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
          
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {t('dental.dental_vp_next_visit_label_purpose')}
            </label>
            <input
            type="text"
            aria-label={t('dental.dental_vp_next_visit_aria_purpose')}
            value={formData.nextVisit.purpose || ''}
            onChange={(e) => handleInputChange('nextVisit.purpose', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_vp_next_visit_ph_purpose')} />
          
          </div>
        </div>
      </div>
    </div>;


  // Рендер контента по вкладкам
  const renderTabContent = () => {
    switch (activeTab) {
      case 'procedures':
        return renderProcedures();
      case 'materials':
        return renderMaterials();
      case 'anesthesia':
        return renderAnesthesia();
      case 'photos':
        return renderPhotos();
      case 'radiographs':
        return renderRadiographs();
      case 'prescriptions':
        return renderPrescriptions();
      default:
        return renderProcedures();
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg w-full max-w-6xl h-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Заголовок */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-xl font-semibold">
              {t('dental.dental_vp_title', { name: patientName })}
            </h2>
            <p className="text-gray-600 text-sm">
              {t('dental.dental_vp_subtitle', { date: formData.visitDate, time: formData.visitTime, mode: isEditing ? t('dental.dental_vp_mode_edit') : t('dental.dental_vp_mode_view') })}
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {!isEditing ?
            <button
              onClick={() => setIsEditing(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
              
                <Edit className="h-4 w-4" />
                {t('dental.dental_vp_btn_edit')}
              </button> :

            <>
                <button
                onClick={() => setIsEditing(false)}
                className="flex items-center gap-2 px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600">
                
                  <X className="h-4 w-4" />
                  {t('dental.dental_vp_btn_cancel')}
                </button>
                <button
                onClick={handleSave}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50">
                
                  <Save className="h-4 w-4" />
                  {loading ? t('dental.dental_vp_btn_saving') : t('dental.dental_vp_btn_save')}
                </button>
                {onComplete && (
                  <button
                    onClick={onComplete}
                    disabled={loading}
                    aria-label={t('dental.dental_vp_aria_complete')}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-700 text-white rounded-md hover:bg-blue-800 disabled:opacity-50">

                    <Check className="h-4 w-4" />
                    {t('dental.dental_vp_btn_complete')}
                  </button>
                )}
              </>
            }
            <button
              onClick={onClose}
              aria-label={t('dental.dental_vp_aria_close')}
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


VisitProtocol.propTypes = {
  ...(VisitProtocol.propTypes || {}),
  initialData: PropTypes.any,
  onClose: PropTypes.any,
  onComplete: PropTypes.func,
  onSave: PropTypes.any,
  patientName: PropTypes.any,
};

export default VisitProtocol;
