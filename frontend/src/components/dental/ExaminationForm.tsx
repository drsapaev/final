import { useTranslation } from '../../i18n/useTranslation';
import { useState, useEffect } from 'react';
import logger from '../../utils/logger';
import {
  Camera,
  Upload,
  Save,
  X,
  Edit,

  Trash2,
  Eye,
  Activity,
  Heart,
  AlertCircle,
  CheckCircle,
  FileImage } from

'lucide-react';
import PropTypes from 'prop-types';
import notify from '../../services/notify';

/**
 * Форма объективного осмотра для стоматологической ЭМК
 * Включает индексы гигиены, пародонт, фотофиксацию
 */
const ExaminationForm = ({
  initialData = null,
  onSave,
  onClose
}: { patientId?: string | number; initialData?: Record<string, unknown> | null; onSave?: (data: unknown) => void; onClose?: () => void }) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const [formData, setFormData] = useState({
    // Основные данные осмотра
    examinationDate: new Date().toISOString().split('T')[0],
    doctor: '',
    complaints: '',

    // Общий осмотр
    generalCondition: {
      face: '',
      lips: '',
      tongue: '',
      mucosa: '',
      gums: ''
    },

    // Индексы гигиены
    hygieneIndices: {
      ohis: '', // Oral Hygiene Index Simplified
      pli: '', // Plaque Index
      cpi: '', // Community Periodontal Index
      bleeding: '' // Bleeding Index
    },

    // Пародонтальные карманы (по зубам)
    periodontalPockets: {},

    // Дополнительные измерения
    measurements: {
      overjet: '', // Горизонтальное перекрытие
      overbite: '', // Вертикальное перекрытие
      midline: '', // Срединная линия
      crossbite: '', // Перекрестный прикус
      openBite: '' // Открытый прикус
    },

    // Фото и рентген
    photos: {
      before: [],
      after: [],
      intraoral: [],
      extraoral: []
    },

    // Рентгенологические данные
    radiographs: {
      panoramic: '',
      periapical: [],
      bitewing: [],
      cbct: ''
    },

    // Заключение
    conclusion: '',
    recommendations: '',

    // Метаданные
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString()
  });

  const [activeTab, setActiveTab] = useState('general');
  const [isEditing, setIsEditing] = useState(true);
  const [loading, setLoading] = useState(false);

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

  const handlePhotoUpload = (category, file) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const photoData = {
        id: Date.now(),
        url: e.target.result,
        filename: file.name,
        size: file.size,
        type: file.type,
        uploadedAt: new Date().toISOString()
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
      notify.error(t('dental2.exam_save_failed'));
    } finally {
      setLoading(false);
    }
  };

  // Вкладки
  const tabs = [
  { id: 'general', label: t('dental.dental_ef_tab_general'), icon: Eye },
  { id: 'hygiene', label: t('dental.dental_ef_tab_hygiene'), icon: Activity },
  { id: 'periodontal', label: t('dental.dental_ef_tab_periodontal'), icon: Heart },
  { id: 'measurements', label: t('dental.dental_ef_tab_measurements'), icon: AlertCircle },
  { id: 'photos', label: t('dental.dental_ef_tab_photos'), icon: Camera },
  { id: 'conclusion', label: t('dental.dental_ef_tab_conclusion'), icon: CheckCircle }];


  // Рендер общего осмотра
  const renderGeneralExamination = () =>
  <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_ef_general_face')}
          </label>
          <textarea
          aria-label={t('dental.dental_ef_general_aria_face')}
          value={formData.generalCondition.face || ''}
          onChange={(e) => handleInputChange('generalCondition.face', e.target.value)}
          disabled={!isEditing}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          placeholder={t('dental.dental_ef_general_ph_face')} />
        
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_ef_general_lips')}
          </label>
          <textarea
          aria-label={t('dental.dental_ef_general_aria_lips')}
          value={formData.generalCondition.lips || ''}
          onChange={(e) => handleInputChange('generalCondition.lips', e.target.value)}
          disabled={!isEditing}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          placeholder={t('dental.dental_ef_general_ph_lips')} />
        
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_ef_general_tongue')}
          </label>
          <textarea
          aria-label={t('dental.dental_ef_general_aria_tongue')}
          value={formData.generalCondition.tongue || ''}
          onChange={(e) => handleInputChange('generalCondition.tongue', e.target.value)}
          disabled={!isEditing}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          placeholder={t('dental.dental_ef_general_ph_tongue')} />
        
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_ef_general_mucosa')}
          </label>
          <textarea
          aria-label={t('dental.dental_ef_general_aria_mucosa')}
          value={formData.generalCondition.mucosa || ''}
          onChange={(e) => handleInputChange('generalCondition.mucosa', e.target.value)}
          disabled={!isEditing}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          placeholder={t('dental.dental_ef_general_ph_mucosa')} />
        
        </div>
        
        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_ef_general_gums')}
          </label>
          <textarea
          aria-label={t('dental.dental_ef_general_aria_gums')}
          value={formData.generalCondition.gums || ''}
          onChange={(e) => handleInputChange('generalCondition.gums', e.target.value)}
          disabled={!isEditing}
          rows={3}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
          placeholder={t('dental.dental_ef_general_ph_gums')} />
        
        </div>
      </div>
    </div>;


  // Рендер индексов гигиены
  const renderHygieneIndices = () =>
  <div className="space-y-6">
      <div className="bg-blue-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_ef_hygiene_title')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_ef_hygiene_subtitle')}
        </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_ef_hygiene_ohis_label')}
          </label>
          <div className="flex items-center gap-2">
            <input
            type="number"
            aria-label={t('dental.dental_ef_hygiene_aria_ohis')}
            step="0.1"
            min="0"
            max="6"
            value={formData.hygieneIndices.ohis || ''}
            onChange={(e) => handleInputChange('hygieneIndices.ohis', e.target.value)}
            disabled={!isEditing}
            className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
          
            <span className="text-sm text-gray-600">
              {formData.hygieneIndices.ohis ?
            parseFloat(formData.hygieneIndices.ohis) < 1.2 ? t('dental.dental_ef_hygiene_good') :
            parseFloat(formData.hygieneIndices.ohis) < 3.0 ? t('dental.dental_ef_hygiene_satisfactory') : t('dental.dental_ef_hygiene_poor') : ''
            }
            </span>
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_ef_hygiene_pli_label')}
          </label>
          <div className="flex items-center gap-2">
            <input
            type="number"
            aria-label={t('dental.dental_ef_hygiene_aria_pli')}
            step="0.1"
            min="0"
            max="3"
            value={formData.hygieneIndices.pli || ''}
            onChange={(e) => handleInputChange('hygieneIndices.pli', e.target.value)}
            disabled={!isEditing}
            className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
          
            <span className="text-sm text-gray-600">
              {formData.hygieneIndices.pli ?
            parseFloat(formData.hygieneIndices.pli) < 0.5 ? t('dental.dental_ef_hygiene_excellent') :
            parseFloat(formData.hygieneIndices.pli) < 1.0 ? t('dental.dental_ef_hygiene_good') :
            parseFloat(formData.hygieneIndices.pli) < 2.0 ? t('dental.dental_ef_hygiene_satisfactory') : t('dental.dental_ef_hygiene_poor') : ''
            }
            </span>
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_ef_hygiene_cpi_label')}
          </label>
          <div className="flex items-center gap-2">
            <input
            type="number"
            aria-label={t('dental.dental_ef_hygiene_aria_cpi')}
            step="0.1"
            min="0"
            max="4"
            value={formData.hygieneIndices.cpi || ''}
            onChange={(e) => handleInputChange('hygieneIndices.cpi', e.target.value)}
            disabled={!isEditing}
            className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
          
            <span className="text-sm text-gray-600">
              {formData.hygieneIndices.cpi ?
            parseFloat(formData.hygieneIndices.cpi) === 0 ? t('dental.dental_ef_hygiene_cpi_0') :
            parseFloat(formData.hygieneIndices.cpi) === 1 ? t('dental.dental_ef_hygiene_cpi_1') :
            parseFloat(formData.hygieneIndices.cpi) === 2 ? t('dental.dental_ef_hygiene_cpi_2') :
            parseFloat(formData.hygieneIndices.cpi) === 3 ? t('dental.dental_ef_hygiene_cpi_3') : t('dental.dental_ef_hygiene_cpi_4') : ''
            }
            </span>
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_ef_hygiene_bleeding_label')}
          </label>
          <div className="flex items-center gap-2">
            <input
            type="number"
            aria-label={t('dental.dental_ef_hygiene_aria_bleeding')}
            step="0.1"
            min="0"
            max="100"
            value={formData.hygieneIndices.bleeding || ''}
            onChange={(e) => handleInputChange('hygieneIndices.bleeding', e.target.value)}
            disabled={!isEditing}
            className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
          
            <span className="text-sm text-gray-600">%</span>
          </div>
        </div>
      </div>
    </div>;


  // Рендер пародонтальных карманов
  const renderPeriodontalPockets = () =>
  <div className="space-y-6">
      <div className="bg-green-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_ef_perio_title')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_ef_perio_subtitle')}
        </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Верхняя челюсть */}
        <div>
          <h4 className="font-semibold mb-3">{t('dental.dental_ef_perio_upper')}</h4>
          <div className="space-y-2">
            {[18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28].map((toothId) =>
          <div key={toothId} className="flex items-center gap-2">
                <span className="w-8 text-sm font-medium">{toothId}</span>
                <div className="flex gap-1">
                  {['M', 'B', 'L', 'D'].map((position) =>
              <input
                key={position}
                type="number"
                aria-label={t('dental.dental_ef_perio_aria_pocket', { tooth: toothId, position })}
                step="0.5"
                min="0"
                max="10"
                value={formData.periodontalPockets[`${toothId}_${position}`] || ''}
                onChange={(e) => handleInputChange(`periodontalPockets.${toothId}_${position}`, e.target.value)}
                disabled={!isEditing}
                className="w-12 px-2 py-1 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="0" />

              )}
                </div>
              </div>
          )}
          </div>
        </div>
        
        {/* Нижняя челюсть */}
        <div>
          <h4 className="font-semibold mb-3">{t('dental.dental_ef_perio_lower')}</h4>
          <div className="space-y-2">
            {[48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38].map((toothId) =>
          <div key={toothId} className="flex items-center gap-2">
                <span className="w-8 text-sm font-medium">{toothId}</span>
                <div className="flex gap-1">
                  {['M', 'B', 'L', 'D'].map((position) =>
              <input
                key={position}
                type="number"
                aria-label={t('dental.dental_ef_perio_aria_pocket', { tooth: toothId, position })}
                step="0.5"
                min="0"
                max="10"
                value={formData.periodontalPockets[`${toothId}_${position}`] || ''}
                onChange={(e) => handleInputChange(`periodontalPockets.${toothId}_${position}`, e.target.value)}
                disabled={!isEditing}
                className="w-12 px-2 py-1 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
                placeholder="0" />

              )}
                </div>
              </div>
          )}
          </div>
        </div>
      </div>
      
      <div className="text-xs text-gray-600">
        <p>{t('dental.dental_ef_perio_legend', { interpolation: { escapeValue: false } })}</p>
        <p>{t('dental.dental_ef_perio_unit_mm')}</p>
      </div>
    </div>;


  // Рендер измерений
  const renderMeasurements = () =>
  <div className="space-y-6">
      <div className="bg-yellow-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_ef_meas_title')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_ef_meas_subtitle')}
        </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_ef_meas_overjet_label')}
          </label>
          <div className="flex items-center gap-2">
            <input
            type="number"
            aria-label={t('dental.dental_ef_meas_aria_overjet')}
            step="0.1"
            value={formData.measurements.overjet || ''}
            onChange={(e) => handleInputChange('measurements.overjet', e.target.value)}
            disabled={!isEditing}
            className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
          
            <span className="text-sm text-gray-600">{t('dental.dental_ef_meas_unit_mm')}</span>
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_ef_meas_overbite_label')}
          </label>
          <div className="flex items-center gap-2">
            <input
            type="number"
            aria-label={t('dental.dental_ef_meas_aria_overbite')}
            step="0.1"
            value={formData.measurements.overbite || ''}
            onChange={(e) => handleInputChange('measurements.overbite', e.target.value)}
            disabled={!isEditing}
            className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
          
            <span className="text-sm text-gray-600">{t('dental.dental_ef_meas_unit_mm')}</span>
          </div>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_ef_meas_midline_label')}
          </label>
          <select
          aria-label={t('dental.dental_ef_meas_aria_midline')}
          value={formData.measurements.midline || ''}
          onChange={(e) => handleInputChange('measurements.midline', e.target.value)}
          disabled={!isEditing}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100">
          
            <option value="">{t('dental.dental_ef_meas_select_placeholder')}</option>
            <option value="coincident">{t('dental.dental_ef_meas_midline_coincident')}</option>
            <option value="deviated_right">{t('dental.dental_ef_meas_midline_right')}</option>
            <option value="deviated_left">{t('dental.dental_ef_meas_midline_left')}</option>
          </select>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_ef_meas_crossbite_label')}
          </label>
          <select
          aria-label={t('dental.dental_ef_meas_aria_crossbite')}
          value={formData.measurements.crossbite || ''}
          onChange={(e) => handleInputChange('measurements.crossbite', e.target.value)}
          disabled={!isEditing}
          className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100">
          
            <option value="">{t('dental.dental_ef_meas_select_placeholder')}</option>
            <option value="none">{t('dental.dental_ef_meas_crossbite_none')}</option>
            <option value="anterior">{t('dental.dental_ef_meas_crossbite_anterior')}</option>
            <option value="posterior">{t('dental.dental_ef_meas_crossbite_posterior')}</option>
            <option value="both">{t('dental.dental_ef_meas_crossbite_both')}</option>
          </select>
        </div>
        
        <div className="md:col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('dental.dental_ef_meas_openbite_label')}
          </label>
          <div className="flex items-center gap-2">
            <input
            type="number"
            aria-label={t('dental.dental_ef_meas_aria_openbite')}
            step="0.1"
            value={formData.measurements.openBite || ''}
            onChange={(e) => handleInputChange('measurements.openBite', e.target.value)}
            disabled={!isEditing}
            className="w-20 px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100" />
          
            <span className="text-sm text-gray-600">{t('dental.dental_ef_meas_openbite_unit')}</span>
          </div>
        </div>
      </div>
    </div>;


  // Рендер фото и рентгена
  const renderPhotosAndRadiographs = () =>
  <div className="space-y-6">
      <div className="bg-purple-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_ef_photo_title')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_ef_photo_subtitle')}
        </p>
      </div>
      
      {/* Фотографии */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h4 className="font-semibold mb-3">{t('dental.dental_ef_photo_before_title')}</h4>
          <div className="space-y-2">
            {formData.photos.before.map((photo, index) =>
          <div key={photo.id} className="flex items-center gap-2 p-2 border rounded">
                <FileImage className="h-4 w-4 text-blue-500" />
                <span className="text-sm flex-1">{photo.filename}</span>
                {isEditing &&
            <button
              onClick={() => handleArrayRemove('photos.before', index)}
              aria-label={t('dental.dental_ef_photo_aria_remove_before', { index: index + 1 })}
              className="text-red-500 hover:text-red-700">
              
                    <Trash2 className="h-4 w-4" />
                  </button>
            }
              </div>
          )}
            {isEditing &&
          <label className="flex items-center gap-2 p-2 border-2 border-dashed border-gray-300 rounded cursor-pointer hover:border-blue-500">
                <Upload className="h-4 w-4" />
                <span className="text-sm">{t('dental.dental_ef_photo_btn_upload')}</span>
                <input
              type="file"
              aria-label={t('dental.dental_ef_photo_aria_upload_before')}
              accept="image/*"
              onChange={(e) => {
                if (e.target.files[0]) {
                  handlePhotoUpload('before', e.target.files[0]);
                }
              }}
              className="hidden" />
            
              </label>
          }
          </div>
        </div>
        
        <div>
          <h4 className="font-semibold mb-3">{t('dental.dental_ef_photo_after_title')}</h4>
          <div className="space-y-2">
            {formData.photos.after.map((photo, index) =>
          <div key={photo.id} className="flex items-center gap-2 p-2 border rounded">
                <FileImage className="h-4 w-4 text-green-500" />
                <span className="text-sm flex-1">{photo.filename}</span>
                {isEditing &&
            <button
              onClick={() => handleArrayRemove('photos.after', index)}
              aria-label={t('dental.dental_ef_photo_aria_remove_after', { index: index + 1 })}
              className="text-red-500 hover:text-red-700">
              
                    <Trash2 className="h-4 w-4" />
                  </button>
            }
              </div>
          )}
            {isEditing &&
          <label className="flex items-center gap-2 p-2 border-2 border-dashed border-gray-300 rounded cursor-pointer hover:border-blue-500">
                <Upload className="h-4 w-4" />
                <span className="text-sm">{t('dental.dental_ef_photo_btn_upload')}</span>
                <input
              type="file"
              aria-label={t('dental.dental_ef_photo_aria_upload_after')}
              accept="image/*"
              onChange={(e) => {
                if (e.target.files[0]) {
                  handlePhotoUpload('after', e.target.files[0]);
                }
              }}
              className="hidden" />
            
              </label>
          }
          </div>
        </div>
        
        <div>
          <h4 className="font-semibold mb-3">{t('dental.dental_ef_photo_intraoral_title')}</h4>
          <div className="space-y-2">
            {formData.photos.intraoral.map((photo, index) =>
          <div key={photo.id} className="flex items-center gap-2 p-2 border rounded">
                <FileImage className="h-4 w-4 text-purple-500" />
                <span className="text-sm flex-1">{photo.filename}</span>
                {isEditing &&
            <button
              onClick={() => handleArrayRemove('photos.intraoral', index)}
              aria-label={t('dental.dental_ef_photo_aria_remove_intraoral', { index: index + 1 })}
              className="text-red-500 hover:text-red-700">
              
                    <Trash2 className="h-4 w-4" />
                  </button>
            }
              </div>
          )}
            {isEditing &&
          <label className="flex items-center gap-2 p-2 border-2 border-dashed border-gray-300 rounded cursor-pointer hover:border-blue-500">
                <Upload className="h-4 w-4" />
                <span className="text-sm">{t('dental.dental_ef_photo_btn_upload')}</span>
                <input
              type="file"
              aria-label={t('dental.dental_ef_photo_aria_upload_intraoral')}
              accept="image/*"
              onChange={(e) => {
                if (e.target.files[0]) {
                  handlePhotoUpload('intraoral', e.target.files[0]);
                }
              }}
              className="hidden" />
            
              </label>
          }
          </div>
        </div>
        
        <div>
          <h4 className="font-semibold mb-3">{t('dental.dental_ef_photo_extraoral_title')}</h4>
          <div className="space-y-2">
            {formData.photos.extraoral.map((photo, index) =>
          <div key={photo.id} className="flex items-center gap-2 p-2 border rounded">
                <FileImage className="h-4 w-4 text-orange-500" />
                <span className="text-sm flex-1">{photo.filename}</span>
                {isEditing &&
            <button
              onClick={() => handleArrayRemove('photos.extraoral', index)}
              aria-label={t('dental.dental_ef_photo_aria_remove_extraoral', { index: index + 1 })}
              className="text-red-500 hover:text-red-700">
              
                    <Trash2 className="h-4 w-4" />
                  </button>
            }
              </div>
          )}
            {isEditing &&
          <label className="flex items-center gap-2 p-2 border-2 border-dashed border-gray-300 rounded cursor-pointer hover:border-blue-500">
                <Upload className="h-4 w-4" />
                <span className="text-sm">{t('dental.dental_ef_photo_btn_upload')}</span>
                <input
              type="file"
              aria-label={t('dental.dental_ef_photo_aria_upload_extraoral')}
              accept="image/*"
              onChange={(e) => {
                if (e.target.files[0]) {
                  handlePhotoUpload('extraoral', e.target.files[0]);
                }
              }}
              className="hidden" />
            
              </label>
          }
          </div>
        </div>
      </div>
      
      {/* Рентгенологические данные */}
      <div className="border-t pt-6">
        <h4 className="font-semibold mb-3">{t('dental.dental_ef_radio_title')}</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_ef_radio_panoramic_label')}
            </label>
            <input
            type="text"
            aria-label={t('dental.dental_ef_radio_aria_panoramic')}
            value={formData.radiographs.panoramic || ''}
            onChange={(e) => handleInputChange('radiographs.panoramic', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_ef_radio_ph_number')} />
          
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {t('dental.dental_ef_radio_cbct_label')}
            </label>
            <input
            type="text"
            aria-label={t('dental.dental_ef_radio_aria_cbct')}
            value={formData.radiographs.cbct || ''}
            onChange={(e) => handleInputChange('radiographs.cbct', e.target.value)}
            disabled={!isEditing}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
            placeholder={t('dental.dental_ef_radio_ph_number')} />
          
          </div>
        </div>
      </div>
    </div>;


  // Рендер заключения
  const renderConclusion = () =>
  <div className="space-y-6">
      <div className="bg-green-50 p-4 rounded-lg">
        <h3 className="text-lg font-semibold mb-2">{t('dental.dental_ef_conclusion_title')}</h3>
        <p className="text-sm text-gray-600">
          {t('dental.dental_ef_conclusion_subtitle')}
        </p>
      </div>
      
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {t('dental.dental_ef_conclusion_label')}
        </label>
        <textarea
        aria-label={t('dental.dental_ef_conclusion_aria')}
        value={formData.conclusion || ''}
        onChange={(e) => handleInputChange('conclusion', e.target.value)}
        disabled={!isEditing}
        rows={4}
        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
        placeholder={t('dental.dental_ef_conclusion_ph_findings')} />
      
      </div>
      
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {t('dental.dental_ef_conclusion_label_rec')}
        </label>
        <textarea
        aria-label={t('dental.dental_ef_conclusion_aria_rec')}
        value={formData.recommendations || ''}
        onChange={(e) => handleInputChange('recommendations', e.target.value)}
        disabled={!isEditing}
        rows={4}
        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100"
        placeholder={t('dental.dental_ef_conclusion_ph_rec')} />
      
      </div>
    </div>;


  // Рендер контента по вкладкам
  const renderTabContent = () => {
    switch (activeTab) {
      case 'general':
        return renderGeneralExamination();
      case 'hygiene':
        return renderHygieneIndices();
      case 'periodontal':
        return renderPeriodontalPockets();
      case 'measurements':
        return renderMeasurements();
      case 'photos':
        return renderPhotosAndRadiographs();
      case 'conclusion':
        return renderConclusion();
      default:
        return renderGeneralExamination();
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg w-full max-w-6xl h-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Заголовок */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-xl font-semibold">
              {t('dental.dental_ef_title')}
            </h2>
            <p className="text-gray-600 text-sm">
              {t('dental.dental_ef_subtitle', { date: formData.examinationDate, mode: isEditing ? t('dental.dental_ef_mode_edit') : t('dental.dental_ef_mode_view') })}
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            {!isEditing ?
            <button
              onClick={() => setIsEditing(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
              
                <Edit className="h-4 w-4" />
                {t('dental.dental_ef_btn_edit')}
              </button> :

            <>
                <button
                onClick={() => setIsEditing(false)}
                className="flex items-center gap-2 px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600">
                
                  <X className="h-4 w-4" />
                  {t('dental.dental_ef_btn_cancel')}
                </button>
                <button
                onClick={handleSave}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50">
                
                  <Save className="h-4 w-4" />
                  {loading ? t('dental.dental_ef_btn_saving') : t('dental.dental_ef_btn_save')}
                </button>
              </>
            }
            <button
              onClick={onClose}
              aria-label={t('dental.dental_ef_aria_close')}
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


ExaminationForm.propTypes = {
  ...(ExaminationForm.propTypes || {}),
  initialData: PropTypes.any,
  onClose: PropTypes.any,
  onSave: PropTypes.any,
};

export default ExaminationForm;
