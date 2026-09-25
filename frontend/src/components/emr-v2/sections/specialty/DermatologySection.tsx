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

import { useState, useCallback, useRef } from 'react';
import { Camera, X, Image as ImageIcon, Sparkles } from 'lucide-react';
import EMRSection from '../EMRSection';

import EMRSmartFieldV2 from '../EMRSmartFieldV2';
import { useEMRAI } from '@/hooks/useEMRAI';
import { MCP_PROVIDERS } from '@/constants/ai';
import logger from '@/utils/logger';
import './DermatologySection.css';
import i18n from '@/i18n';
const i18nT = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;

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
export interface DermatologyPhoto {
  id: string | number;
  url?: string;
  category?: string;
  analysis?: unknown;
  file?: File;
  uploadedAt?: string;
  [key: string]: unknown;
}

interface DermatologySectionProps {
  photos?: DermatologyPhoto[];
  skinType?: string;
  skinCondition?: string;
  localization?: Record<string, unknown>;
  lesions?: string;
  distribution?: string;
  symptoms?: string;
  treatmentPlan?: string;
  onChange?: ((field: string, value: unknown) => void) | undefined;
  disabled?: boolean;
  visitId?: string | number | null | undefined;
  patientId?: string | number | null | undefined;
}


export function DermatologySection({
  photos = [],
  skinType = '',
  skinCondition = '',
  localization = {} as Record<string, unknown>,
  lesions = '',
  distribution = '',
  symptoms = '',
  treatmentPlan = '',
  onChange,
  disabled = false
}: DermatologySectionProps) {
  const [selectedPhoto, setSelectedPhoto] = useState<DermatologyPhoto | null>(null);
  const [analyzingPhoto, setAnalyzingPhoto] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // AI для анализа кожи
  const {
    analyzeSkinLesion


  } = useEMRAI(true, MCP_PROVIDERS.DEEPSEEK);

  // Handlers
  const handlePhotoUpload = useCallback(async (file: File) => {
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

  const handlePhotoDelete = useCallback((photoId: string | number) => {
    const updatedPhotos = photos.filter((p) => p.id !== photoId);
    onChange?.('photos', updatedPhotos);
  }, [photos, onChange]);

  const handleSkinTypeChange = useCallback((value: string) => {
    onChange?.('skin_type', value);
  }, [onChange]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handlePhotoUpload(file);
    }
  }, [handlePhotoUpload]);
  const handleActivationKeyDown = (event: React.KeyboardEvent<HTMLElement>, action: () => void) => {
    // t accessed via closure or i18nT()
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      action();
    }
  };

  const skinExamFields = [
    {
      field: 'skin_condition',
      id: 'dermatology-skin-condition',
      label: i18nT('derma.derma_exams_skin_condition'),
      value: skinCondition,
      placeholder: i18nT('derma.derma_exams_ph_skin_condition'),
    },
    {
      field: 'lesions',
      id: 'dermatology-lesions',
      label: i18nT('derma.derma_exams_lesions'),
      value: lesions,
      placeholder: i18nT('derma.derma_exams_ph_lesions'),
    },
    {
      field: 'distribution',
      id: 'dermatology-distribution',
      label: i18nT('derma.derma_exams_distribution'),
      value: distribution,
      placeholder: i18nT('derma.derma_exams_ph_face_neck'),
    },
    {
      field: 'symptoms',
      id: 'dermatology-symptoms',
      label: i18nT('derma.derma_exams_symptoms'),
      value: symptoms,
      placeholder: i18nT('derma.derma_exams_ph_symptoms'),
    },
    {
      field: 'treatment_plan',
      id: 'dermatology-treatment-plan',
      label: i18nT('derma.derma_exams_treatment_plan'),
      value: treatmentPlan,
      placeholder: i18nT('derma.derma_exams_treatment_plan'),
    },
  ];

  return (
    <EMRSection
      title={i18nT('misc.ds_dermatologicheskie_dannye')}
      icon=""
      disabled={disabled}
      defaultOpen={true}>

            {/* Skin Type */}
            <div className="dermatology-field-group">
                <label className="dermatology-label">{i18nT('misc.ds_tip_kozhi')}</label>
                <select
          value={skinType}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) => handleSkinTypeChange(e.target.value)}
          disabled={disabled}
          className="dermatology-select">

                    <option value="">{i18nT('misc.ds_ne_ukazan')}</option>
                    <option value="normal">{i18nT('misc.ds_normalnaya')}</option>
                    <option value="dry">{i18nT('misc.ds_suhaya')}</option>
                    <option value="oily">{i18nT('misc.ds_zhirnaya')}</option>
                    <option value="combination">{i18nT('misc.ds_kombinirovannaya')}</option>
                    <option value="sensitive">{i18nT('misc.ds_chuvstvitelnaya')}</option>
                </select>
            </div>

            {/* Unified skin examination: diagnosis remains in the main EMR field. */}
            <div className="dermatology-field-group">
                <label className="dermatology-label" htmlFor="dermatology-localization">
                  {i18nT('misc.ds_lokalizatsiya_porazheniy')}
                </label>
                <EMRSmartFieldV2
                  id="dermatology-localization"
                  value={String(localization?.description ?? '')}
                  onChange={(value: string) => onChange?.('localization', {
                    ...localization,
                    description: value
                  })}
                  placeholder={i18nT('misc.ds_opishite_lokalizatsiyu_poraz')}
                  multiline
                  rows={2}
                  showAIButton={false}
                  disabled={disabled} />
            </div>

            {skinExamFields.map(({ field, id, label, value, placeholder }) => (
              <div className="dermatology-field-group" key={field}>
                <label className="dermatology-label" htmlFor={id}>{label}</label>
                <EMRSmartFieldV2
                  id={id}
                  value={value}
                  onChange={(nextValue: string) => onChange?.(field, nextValue)}
                  placeholder={placeholder}
                  multiline
                  rows={2}
                  showAIButton={false}
                  disabled={disabled} />
              </div>
            ))}

            {/* Photo Gallery */}
            <div className="dermatology-field-group">
                <div className="dermatology-photo-header">
                    <label className="dermatology-label">{i18nT('misc.ds_foto_arhiv')}</label>
                    {!disabled &&
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="dermatology-upload-btn"
            disabled={analyzingPhoto}>

                            <Camera size={16} />
                            {analyzingPhoto ? i18nT('misc.ds_analiz') : i18nT('misc.ds_zagruzit_foto')}
                        </button>
          }
                </div>
                <input
          ref={fileInputRef}
          type="file"
          aria-label={i18nT('misc.ds_zagruzit_foto_dlya_dermatolo')}
          accept="image/*"
          onChange={handleFileSelect}
          style={{ display: 'none' }} />


                {photos.length === 0 ?
        <div className="dermatology-empty-photos">
                        <ImageIcon size={48} />
                        <p>{i18nT('misc.ds_net_zagruzhennyh_foto')}</p>
                    </div> :

        <div className="dermatology-photo-grid">
                        {photos.map((photo) =>
          <div key={photo.id} className="dermatology-photo-item">
                                <img
              src={photo.url}
              alt={i18nT('misc.ds_foto_photo_category', { category: photo.category })}
              aria-label={i18nT('misc.ds_otkryt_foto_photo_category', { category: photo.category })}
              role="button"
              tabIndex={0}
              onClick={() => setSelectedPhoto(photo)}
              onKeyDown={(event) => handleActivationKeyDown(event, () => setSelectedPhoto(photo))} />

                                {Boolean(photo.analysis) &&
            <div className="dermatology-photo-analysis">
                                        <Sparkles size={12} />
                                        <span>AI анализ</span>
                                    </div>
            }
                                {!disabled &&
            <button
              type="button"
              onClick={() => handlePhotoDelete(photo.id)}
              aria-label={i18nT('misc.ds_udalit_foto_photo_category', { category: photo.category })}
              className="dermatology-photo-delete">

                                        <X size={14} />
                                    </button>
            }
                            </div>
          )}
                    </div>
        }
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
                        <img src={selectedPhoto.url} alt={i18nT('misc.ds_uvelichennoe_foto')} />
                        {Boolean(selectedPhoto.analysis) &&
          <div className="dermatology-photo-analysis-detail">
                                <h4>AI Анализ:</h4>
                                <pre>{JSON.stringify(selectedPhoto.analysis, null, 2)}</pre>
                            </div>
          }
                        <button
            type="button"
            onClick={() => setSelectedPhoto(null)}
            aria-label={i18nT('misc.ds_zakryt_prosmotr_foto')}
            className="dermatology-photo-modal-close">

                            <X size={20} />
                        </button>
                    </div>
                </div>
      }
        </EMRSection>);

}

export default DermatologySection;
