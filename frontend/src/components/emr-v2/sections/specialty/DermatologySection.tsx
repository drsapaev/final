
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
import EMRSectionRaw from '../EMRSection';
import React from 'react';
const EMRSection = EMRSectionRaw as unknown as React.ComponentType<Record<string, unknown>>;

import EMRSmartFieldV2Raw from '../EMRSmartFieldV2';
const EMRSmartFieldV2 = EMRSmartFieldV2Raw as unknown as React.ComponentType<Record<string, unknown>>;
import { useEMRAI } from '../../../../hooks/useEMRAI';
import { MCP_PROVIDERS } from '../../../../constants/ai';
import logger from '../../../../utils/logger';
import './DermatologySection.css';
import { Checkbox } from '../../../ui/macos';
import { useTranslation } from '../../../../i18n/useTranslation';
import { i18n } from '../../../../i18n/useTranslation';
const t18 = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;

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
  photos: photosRaw = [],
  skinType = '',
  conditions: condRaw = [],
  localization: locRaw = {},
  onChange: onChangeRaw,
  disabled: disabledRaw = false
}: Record<string, unknown>) {
  const localization = locRaw as Record<string, unknown>;
  const conditions = condRaw as unknown[];
  const photos = photosRaw as Array<Record<string, unknown>>;
  const disabled = disabledRaw as boolean;
  const onChange = onChangeRaw as ((field: string, value: unknown) => void) | undefined;
  const [selectedPhoto, setSelectedPhoto] = useState(null);
  const [analyzingPhoto, setAnalyzingPhoto] = useState(false);
  const fileInputRef = useRef(null);

  // AI для анализа кожи
  const {
    analyzeSkinLesion


  } = useEMRAI(true, MCP_PROVIDERS.DEEPSEEK);

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
    if (!conditions.includes(condition as unknown as string)) {
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
    // t accessed via closure or t18()
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      action();
    }
  };

  return (
    <EMRSection
      title={t18('misc.ds_dermatologicheskie_dannye')}
      icon=""
      disabled={disabled}
      defaultOpen={true}>
      
            {/* Skin Type */}
            <div className="dermatology-field-group">
                <label className="dermatology-label">{t18('misc.ds_tip_kozhi')}</label>
                <select
          value={skinType as string}
          onChange={(e) => handleSkinTypeChange(e.target.value)}
          disabled={disabled}
          className="dermatology-select">
          
                    <option value="">{t18('misc.ds_ne_ukazan')}</option>
                    <option value="normal">{t18('misc.ds_normalnaya')}</option>
                    <option value="dry">{t18('misc.ds_suhaya')}</option>
                    <option value="oily">{t18('misc.ds_zhirnaya')}</option>
                    <option value="combination">{t18('misc.ds_kombinirovannaya')}</option>
                    <option value="sensitive">{t18('misc.ds_chuvstvitelnaya')}</option>
                </select>
            </div>

            {/* Conditions */}
            <div className="dermatology-field-group">
                <label className="dermatology-label">{t18('misc.ds_sostoyaniya')}</label>
                <div className="dermatology-conditions">
                    {[t18('misc.ds_akne'), t18('misc.ds_rozatsea'), t18('misc.ds_ekzema'), t18('misc.ds_psoriaz'), t18('misc.ds_pigmentatsiya'), t18('misc.ds_morschiny')].map((condition) =>
          <label key={condition} className="dermatology-checkbox">
                            <Checkbox aria-label={t18('misc.ds_sostoyanie_kozhi_condition', { condition: condition })} checked={conditions.includes(condition as unknown as string)} onChange={(e) => {
                if (e) {
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
                    <label className="dermatology-label">{t18('misc.ds_foto_arhiv')}</label>
                    {!disabled &&
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="dermatology-upload-btn"
            disabled={analyzingPhoto}>
            
                            <Camera size={16} />
                            {analyzingPhoto ? t18('misc.ds_analiz') : t18('misc.ds_zagruzit_foto')}
                        </button>
          }
                </div>
                <input
          ref={fileInputRef}
          type="file"
          aria-label={t18('misc.ds_zagruzit_foto_dlya_dermatolo')}
          accept="image/*"
          onChange={handleFileSelect}
          style={{ display: 'none' }} />
        

                {photos.length === 0 ?
        <div className="dermatology-empty-photos">
                        <ImageIcon size={48} />
                        <p>{t18('misc.ds_net_zagruzhennyh_foto')}</p>
                    </div> :

        <div className="dermatology-photo-grid">
                        {photos.map((photo) =>
          <div key={String(photo.id)} className="dermatology-photo-item">
                                <img
              src={String(photo.url)}
              alt={t18('misc.ds_foto_photo_category', { category: photo.category })}
              aria-label={t18('misc.ds_otkryt_foto_photo_category', { category: photo.category })}
              role="button"
              tabIndex={0}
              onClick={() => setSelectedPhoto(photo as unknown)}
              onKeyDown={(event) => handleActivationKeyDown(event, () => setSelectedPhoto(photo as unknown))} />
            
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
              aria-label={t18('misc.ds_udalit_foto_photo_category', { category: photo.category })}
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
                <label className="dermatology-label">{t18('misc.ds_lokalizatsiya_porazheniy')}</label>
                <EMRSmartFieldV2
          value={localization?.description || ''}
          onChange={(value) => onChange?.('localization', {
            ...localization,
            description: value
          })}
          placeholder={t18('misc.ds_opishite_lokalizatsiyu_poraz')}
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
                        <img src={selectedPhoto.url} alt={t18('misc.ds_uvelichennoe_foto')} />
                        {selectedPhoto.analysis &&
          <div className="dermatology-photo-analysis-detail">
                                <h4>AI Анализ:</h4>
                                <pre>{JSON.stringify(selectedPhoto.analysis, null, 2)}</pre>
                            </div>
          }
                        <button
            type="button"
            onClick={() => setSelectedPhoto(null)}
            aria-label={t18('misc.ds_zakryt_prosmotr_foto')}
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
