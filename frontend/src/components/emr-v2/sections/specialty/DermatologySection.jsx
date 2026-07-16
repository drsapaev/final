/**
 * DermatologySection - Специализированная секция для дерматологии
 * 
 * Интегрирует:
 * - Фото-галерею до/после
 * - Тип кожи и состояние
 * - Локализацию поражений
 * - AI анализ изображений
 * - Шаблоны косметологических процедур
 */

import PropTypes from 'prop-types';
import { useState, useCallback, useRef } from 'react';
import { Camera, X, Image as ImageIcon, Sparkles } from 'lucide-react';
import EMRSection from '../EMRSection';

import EMRSmartFieldV2 from '../EMRSmartFieldV2';
import { useEMRAI } from '../../../../hooks/useEMRAI';
import { MCP_PROVIDERS } from '../../../../constants/ai';
import logger from '../../../../utils/logger';
import './DermatologySection.css';
import { Checkbox } from '../../../ui/macos';
import { useTranslation } from '../../../../i18n/useTranslation';
import i18n from '../../../../i18n';

/**
 * DermatologySection Component
 *
 * @param {Object} props
 * @param {Array} props.photos - Массив фото из specialty_data
 * @param {string} props.skinType - Тип кожи
 * @param {Array} props.conditions - Состояния кожи
 * @param {Object} props.localization - Локализация поражений
 * @param {Function} props.onChange - Handler для изменения specialty_data
 * @param {boolean} props.disabled - Read-only mode
 */
export function DermatologySection({
  photos = [],
  skinType = '',
  conditions = [],
  localization = {},
  onChange,
  disabled = false
}) {
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [analyzingPhoto, setAnalyzingPhoto] = useState(false);
  const fileInputRef = useRef(null);

  // AI для анализа кожи
  const {
    analyzeSkinLesion


  } = useEMRAI(true, MCP_PROVIDERS.DEEPSEE);

  // Handlers
  const handlePhotoUpload = useCallback(async (file) => {
    if (!file) return;

    const newPhoto = {
      id: Date.now(),
      file,
      url: URL.createObjectURL(file),
      category: 'examination', // 'examination' | 'before' | 'after'
      uploadedAt: new Date().toISOString(),
      analysis: null
    };

    const updatedPhotos = [...photos, newPhoto];
    onChange?.('photos', updatedPhotos);

    // Автоматический AI анализ
    try {
      setAnalyzingPhoto(true);
      const analysis = await analyzeSkinLesion({
        image: file,
        patientAge: null, // TODO: получить из контекста
        patientGender: null
      });

      if (analysis) {
        const updatedPhotosWithAnalysis = updatedPhotos.map((p) =>
        p.id === newPhoto.id ? { ...p, analysis } : p
        );
        onChange?.('photos', updatedPhotosWithAnalysis);
      }
    } catch (error) {
      logger.error('[DermatologySection] AI analysis error:', error);
    } finally {
      setAnalyzingPhoto(false);
    }
  }, [photos, onChange, analyzeSkinLesion]);

  const handlePhotoDelete = useCallback((photoId) => {
    const updatedPhotos = photos.filter((p) => p.id !== photoId);
    onChange?.('photos', updatedPhotos);
  }, [photos, onChange]);

  const handleSkinTypeChange = useCallback((value) => {
    onChange?.('skin_type', value);
  }, [onChange]);

  const handleConditionAdd = useCallback((condition) => {
    if (!conditions.includes(condition)) {
      onChange?.('conditions', [...conditions, condition]);
    }
  }, [conditions, onChange]);

  const handleConditionRemove = useCallback((condition) => {
    onChange?.('conditions', conditions.filter((c) => c !== condition));
  }, [conditions, onChange]);

  const handleFileSelect = useCallback((e) => {
    const file = e.target.files?.[0];
    if (file) {
      handlePhotoUpload(file);
    }
  }, [handlePhotoUpload]);
  const handleActivationKeyDown = (event, action) => {
    // t accessed via closure or i18n.t()
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      action();
    }
  };

  return (
    <EMRSection
      title={i18n.t('misc.ds_dermatologicheskie_dannye')}
      icon=""
      disabled={disabled}
      defaultOpen={true}>
      
            {/* Skin Type */}
            <div className="dermatology-field-group">
                <label className="dermatology-label">{i18n.t('misc.ds_tip_kozhi')}</label>
                <select
          value={skinType}
          onChange={(e) => handleSkinTypeChange(e.target.value)}
          disabled={disabled}
          className="dermatology-select">
          
                    <option value="">{i18n.t('misc.ds_ne_ukazan')}</option>
                    <option value="normal">{i18n.t('misc.ds_normalnaya')}</option>
                    <option value="dry">{i18n.t('misc.ds_suhaya')}</option>
                    <option value="oily">{i18n.t('misc.ds_zhirnaya')}</option>
                    <option value="combination">{i18n.t('misc.ds_kombinirovannaya')}</option>
                    <option value="sensitive">{i18n.t('misc.ds_chuvstvitelnaya')}</option>
                </select>
            </div>

            {/* Conditions */}
            <div className="dermatology-field-group">
                <label className="dermatology-label">{i18n.t('misc.ds_sostoyaniya')}</label>
                <div className="dermatology-conditions">
                    {[i18n.t('misc.ds_akne'), i18n.t('misc.ds_rozatsea'), i18n.t('misc.ds_ekzema'), i18n.t('misc.ds_psoriaz'), i18n.t('misc.ds_pigmentatsiya'), i18n.t('misc.ds_morschiny')].map((condition) =>
          <label key={condition} className="dermatology-checkbox">
                            <Checkbox aria-label={i18n.t('misc.ds_sostoyanie_kozhi_condition', { condition: condition })} checked={conditions.includes(condition)} onChange={(e) => {
                if (e.target.checked) {
                  handleConditionAdd(condition);
                } else {
                  handleConditionRemove(condition);
                }
              }}
              disabled={disabled} />
            
                            <span>{condition}</span>
                        </label>
          )}
                </div>
            </div>

            {/* Photo Gallery */}
            <div className="dermatology-field-group">
                <div className="dermatology-photo-header">
                    <label className="dermatology-label">{i18n.t('misc.ds_foto_arhiv')}</label>
                    {!disabled &&
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="dermatology-upload-btn"
            disabled={analyzingPhoto}>
            
                            <Camera size={16} />
                            {analyzingPhoto ? i18n.t('misc.ds_analiz') : i18n.t('misc.ds_zagruzit_foto')}
                        </button>
          }
                </div>
                <input
          ref={fileInputRef}
          type="file"
          aria-label={i18n.t('misc.ds_zagruzit_foto_dlya_dermatolo')}
          accept="image/*"
          onChange={handleFileSelect}
          style={{ display: 'none' }} />
        

                {photos.length === 0 ?
        <div className="dermatology-empty-photos">
                        <ImageIcon size={48} />
                        <p>{i18n.t('misc.ds_net_zagruzhennyh_foto')}</p>
                    </div> :

        <div className="dermatology-photo-grid">
                        {photos.map((photo) =>
          <div key={photo.id} className="dermatology-photo-item">
                                <img
              src={photo.url}
              alt={i18n.t('misc.ds_foto_photo_category', { category: photo.category })}
              aria-label={i18n.t('misc.ds_otkryt_foto_photo_category', { category: photo.category })}
              role="button"
              tabIndex={0}
              onClick={() => setSelectedPhoto(photo)}
              onKeyDown={(event) => handleActivationKeyDown(event, () => setSelectedPhoto(photo))} />
            
                                {photo.analysis &&
            <div className="dermatology-photo-analysis">
                                        <Sparkles size={12} />
                                        <span>AI анализ</span>
                                    </div>
            }
                                {!disabled &&
            <button
              type="button"
              onClick={() => handlePhotoDelete(photo.id)}
              aria-label={i18n.t('misc.ds_udalit_foto_photo_category', { category: photo.category })}
              className="dermatology-photo-delete">
              
                                        <X size={14} />
                                    </button>
            }
                            </div>
          )}
                    </div>
        }
            </div>

            {/* Localization */}
            <div className="dermatology-field-group">
                <label className="dermatology-label">{i18n.t('misc.ds_lokalizatsiya_porazheniy')}</label>
                <EMRSmartFieldV2
          value={localization?.description || ''}
          onChange={(value) => onChange?.('localization', {
            ...localization,
            description: value
          })}
          placeholder={i18n.t('misc.ds_opishite_lokalizatsiyu_poraz')}
          multiline
          rows={3}
          disabled={disabled} />
        
            </div>

            {/* Photo Modal */}
            {selectedPhoto &&
      <div
        className="dermatology-photo-modal"
        role="button"
        tabIndex={0}
        onClick={() => setSelectedPhoto(null)}
        onKeyDown={(event) => handleActivationKeyDown(event, () => setSelectedPhoto(null))}>
        
                    <div className="dermatology-photo-modal-content" onClickCapture={(e) => e.stopPropagation()}>
                        <img src={selectedPhoto.url} alt={i18n.t('misc.ds_uvelichennoe_foto')} />
                        {selectedPhoto.analysis &&
          <div className="dermatology-photo-analysis-detail">
                                <h4>AI Анализ:</h4>
                                <pre>{JSON.stringify(selectedPhoto.analysis, null, 2)}</pre>
                            </div>
          }
                        <button
            type="button"
            onClick={() => setSelectedPhoto(null)}
            aria-label={i18n.t('misc.ds_zakryt_prosmotr_foto')}
            className="dermatology-photo-modal-close">
            
                            <X size={20} />
                        </button>
                    </div>
                </div>
      }
        </EMRSection>);

}

export default DermatologySection;

DermatologySection.propTypes = {
  photos: PropTypes.array,
  skinType: PropTypes.string,
  conditions: PropTypes.array,
  localization: PropTypes.object,
  onChange: PropTypes.func,
  disabled: PropTypes.bool,
};
