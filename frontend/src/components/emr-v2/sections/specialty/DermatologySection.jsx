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
import { useEMRAI } from '../../ai/useEMRAI';
import { MCP_PROVIDERS } from '../../../../constants/ai';
import logger from '../../../../utils/logger';
import './DermatologySection.css';

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
 * @param {number} props.visitId - Visit ID
 * @param {number} props.patientId - Patient ID
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
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      action();
    }
  };

  return (
    <EMRSection
      title="Дерматологические данные"
      icon="🧴"
      disabled={disabled}
      defaultOpen={true}>
      
            {/* Skin Type */}
            <div className="dermatology-field-group">
                <label className="dermatology-label">Тип кожи</label>
                <select
          value={skinType}
          onChange={(e) => handleSkinTypeChange(e.target.value)}
          disabled={disabled}
          className="dermatology-select">
          
                    <option value="">Не указан</option>
                    <option value="normal">Нормальная</option>
                    <option value="dry">Сухая</option>
                    <option value="oily">Жирная</option>
                    <option value="combination">Комбинированная</option>
                    <option value="sensitive">Чувствительная</option>
                </select>
            </div>

            {/* Conditions */}
            <div className="dermatology-field-group">
                <label className="dermatology-label">Состояния</label>
                <div className="dermatology-conditions">
                    {['Акне', 'Розацеа', 'Экзема', 'Псориаз', 'Пигментация', 'Морщины'].map((condition) =>
          <label key={condition} className="dermatology-checkbox">
                            <input
              type="checkbox"
              checked={conditions.includes(condition)}
              onChange={(e) => {
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
                    <label className="dermatology-label">Фото-архив</label>
                    {!disabled &&
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="dermatology-upload-btn"
            disabled={analyzingPhoto}>
            
                            <Camera size={16} />
                            {analyzingPhoto ? 'Анализ...' : 'Загрузить фото'}
                        </button>
          }
                </div>
                <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileSelect}
          style={{ display: 'none' }} />
        

                {photos.length === 0 ?
        <div className="dermatology-empty-photos">
                        <ImageIcon size={48} />
                        <p>Нет загруженных фото</p>
                    </div> :

        <div className="dermatology-photo-grid">
                        {photos.map((photo) =>
          <div key={photo.id} className="dermatology-photo-item">
                                <img
              src={photo.url}
              alt={`Фото ${photo.category}`}
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
                <label className="dermatology-label">Локализация поражений</label>
                <EMRSmartFieldV2
          value={localization?.description || ''}
          onChange={(value) => onChange?.('localization', {
            ...localization,
            description: value
          })}
          placeholder="Опишите локализацию поражений..."
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
                        <img src={selectedPhoto.url} alt="Увеличенное фото" />
                        {selectedPhoto.analysis &&
          <div className="dermatology-photo-analysis-detail">
                                <h4>AI Анализ:</h4>
                                <pre>{JSON.stringify(selectedPhoto.analysis, null, 2)}</pre>
                            </div>
          }
                        <button
            type="button"
            onClick={() => setSelectedPhoto(null)}
            className="dermatology-photo-modal-close">
            
                            <X size={20} />
                        </button>
                    </div>
                </div>
      }
        </EMRSection>);

}

export default DermatologySection;
