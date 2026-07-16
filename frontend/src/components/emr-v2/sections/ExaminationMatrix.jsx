/**
 * ExaminationMatrix - Быстрый ввод объективного статуса
 *
 * Концепция:
 * - Сетка параметров для конкретной специальности
 * - Три состояния: Не выбрано (серый), Норма (зеленый), Патология (красный)
 * - При клике генерирует текст и добавляет в поле "Объективно"
 */

import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Check, AlertCircle } from 'lucide-react';
import './ExaminationMatrix.css';
import { useTranslation } from '../../../i18n/useTranslation';

// Конфигурация матриц для разных специальностей
const MATRICES = {
  general: {
    em_cat_general: ['em_item_condition', 'em_item_consciousness', 'em_item_skin', 'em_item_lymph'],
    em_cat_respiration: ['em_item_rr', 'em_item_breathing', 'em_item_wheezing'],
    em_cat_heart: ['em_item_tones', 'em_item_rhythm', 'em_item_bp', 'em_item_murmurs'],
    em_cat_abdomen: ['em_item_shape', 'em_item_palpation', 'em_item_liver', 'em_item_spleen'],
    em_cat_physio: ['em_item_urination', 'em_item_stool']
  },
  cardiology: {
    em_cat_examination: ['em_item_skin_color', 'em_item_edema', 'em_item_neck_veins', 'em_item_pulsation'],
    em_cat_heart: ['em_item_apex_beat', 'em_item_borders', 'em_item_tones', 'em_item_rhythm', 'em_item_murmurs', 'em_item_gallop'],
    em_cat_lungs: ['em_item_breathing', 'em_item_wheezing', 'em_item_congestion', 'em_item_effusion'],
    em_cat_pulse: ['em_item_filling', 'em_item_tension', 'em_item_deficit', 'em_item_arrhythmia'],
    em_cat_bp: ['em_item_systolic', 'em_item_diastolic', 'em_item_pulse_pressure']
  },
  dermatology: {
    em_cat_skin_type: ['em_item_normal', 'em_item_dry', 'em_item_oily', 'em_item_combined', 'em_item_sensitive'],
    em_cat_condition: ['em_item_acne', 'em_item_rosacea', 'em_item_eczema', 'em_item_psoriasis', 'em_item_pigmentation', 'em_item_wrinkles'],
    em_cat_localization: ['em_item_face', 'em_item_neck', 'em_item_decollete', 'em_item_arms', 'em_item_body'],
    em_cat_characteristics: ['em_item_size', 'em_item_color', 'em_item_texture', 'em_item_borders', 'em_item_symmetry']
  },
  dentist: {
    em_cat_general_dental: ['em_item_mucosa', 'em_item_tongue', 'em_item_lips', 'em_item_cheeks'],
    em_cat_periodont: ['em_item_bleeding', 'em_item_pockets', 'em_item_mobility', 'em_item_recession'],
    em_cat_occlusion: ['em_item_orthognathic', 'em_item_prognathia', 'em_item_progenia', 'em_item_open', 'em_item_deep'],
    em_cat_hygiene: ['em_item_good', 'em_item_fair', 'em_item_poor', 'em_item_very_poor']
  },
  dentistry: {
    em_cat_general_dental: ['em_item_mucosa', 'em_item_tongue', 'em_item_lips', 'em_item_cheeks'],
    em_cat_periodont: ['em_item_bleeding', 'em_item_pockets', 'em_item_mobility', 'em_item_recession'],
    em_cat_occlusion: ['em_item_orthognathic', 'em_item_prognathia', 'em_item_progenia', 'em_item_open', 'em_item_deep'],
    em_cat_hygiene: ['em_item_good', 'em_item_fair', 'em_item_poor', 'em_item_very_poor']
  }
};

// Текстовые шаблоны для генерации
const TEMPLATES = {
  // General
  em_item_condition: { norm: 'em_tpl_condition_norm', path: 'em_tpl_condition_path' },
  em_item_consciousness: { norm: 'em_tpl_consciousness_norm', path: 'em_tpl_consciousness_path' },
  em_item_skin: { norm: 'em_tpl_skin_norm', path: 'em_tpl_skin_path' },
  em_item_edema: { norm: 'em_tpl_edema_norm', path: 'em_tpl_edema_path' },
  em_item_tones: { norm: 'em_tpl_tones_norm', path: 'em_tpl_tones_path' },
  em_item_rhythm: { norm: 'em_tpl_rhythm_norm', path: 'em_tpl_rhythm_path' },
  em_item_breathing: { norm: 'em_tpl_breathing_norm', path: 'em_tpl_breathing_path' },
  em_item_wheezing: { norm: 'em_tpl_wheezing_norm', path: 'em_tpl_wheezing_path' },
  em_item_abdomen: { norm: 'em_tpl_abdomen_norm', path: 'em_tpl_abdomen_path' },
  // Cardiology
  em_item_skin_color: { norm: 'em_tpl_skin_color_norm', path: 'em_tpl_skin_color_path' },
  em_item_neck_veins: { norm: 'em_tpl_neck_veins_norm', path: 'em_tpl_neck_veins_path' },
  em_item_apex_beat: { norm: 'em_tpl_apex_beat_norm', path: 'em_tpl_apex_beat_path' },
  em_item_borders: { norm: 'em_tpl_borders_norm', path: 'em_tpl_borders_path' },
  em_item_gallop: { norm: 'em_tpl_gallop_norm', path: 'em_tpl_gallop_path' },
  em_item_congestion: { norm: 'em_tpl_congestion_norm', path: 'em_tpl_congestion_path' },
  em_item_effusion: { norm: 'em_tpl_effusion_norm', path: 'em_tpl_effusion_path' },
  em_item_arrhythmia: { norm: 'em_tpl_arrhythmia_norm', path: 'em_tpl_arrhythmia_path' },
  // Dermatology
  em_item_normal: { norm: 'em_tpl_normal_norm', path: null },
  em_item_dry: { norm: 'em_tpl_dry_norm', path: null },
  em_item_oily: { norm: 'em_tpl_oily_norm', path: null },
  em_item_combined: { norm: 'em_tpl_combined_norm', path: null },
  em_item_sensitive: { norm: 'em_tpl_sensitive_norm', path: null },
  em_item_acne: { norm: 'em_tpl_acne_norm', path: 'em_tpl_acne_path' },
  em_item_rosacea: { norm: 'em_tpl_rosacea_norm', path: 'em_tpl_rosacea_path' },
  em_item_eczema: { norm: 'em_tpl_eczema_norm', path: 'em_tpl_eczema_path' },
  em_item_psoriasis: { norm: 'em_tpl_psoriasis_norm', path: 'em_tpl_psoriasis_path' },
  em_item_pigmentation: { norm: 'em_tpl_pigmentation_norm', path: 'em_tpl_pigmentation_path' },
  em_item_wrinkles: { norm: 'em_tpl_wrinkles_norm', path: 'em_tpl_wrinkles_path' },
  // Dentistry
  em_item_mucosa: { norm: 'em_tpl_mucosa_norm', path: 'em_tpl_mucosa_path' },
  em_item_tongue: { norm: 'em_tpl_tongue_norm', path: 'em_tpl_tongue_path' },
  em_item_lips: { norm: 'em_tpl_lips_norm', path: 'em_tpl_lips_path' },
  em_item_cheeks: { norm: 'em_tpl_cheeks_norm', path: 'em_tpl_cheeks_path' },
  em_item_bleeding: { norm: 'em_tpl_bleeding_norm', path: 'em_tpl_bleeding_path' },
  em_item_pockets: { norm: 'em_tpl_pockets_norm', path: 'em_tpl_pockets_path' },
  em_item_mobility: { norm: 'em_tpl_mobility_norm', path: 'em_tpl_mobility_path' },
  em_item_recession: { norm: 'em_tpl_recession_norm', path: 'em_tpl_recession_path' },
  em_item_orthognathic: { norm: 'em_tpl_orthognathic_norm', path: null },
  em_item_prognathia: { norm: 'em_tpl_prognathia_norm', path: null },
  em_item_progenia: { norm: 'em_tpl_progenia_norm', path: null },
  em_item_open: { norm: 'em_tpl_open_norm', path: null },
  em_item_deep: { norm: 'em_tpl_deep_norm', path: null },
  em_item_good: { norm: 'em_tpl_good_norm', path: null },
  em_item_fair: { norm: 'em_tpl_fair_norm', path: null },
  em_item_poor: { norm: 'em_tpl_poor_norm', path: null },
  em_item_very_poor: { norm: 'em_tpl_very_poor_norm', path: null }
};

const ExaminationMatrix = ({
  specialty = 'general',
  onGenerateText,
  isEditable = true
}) => {
  const { t } = useTranslation();
  const [activeCategory, setActiveCategory] = useState(Object.keys(MATRICES[specialty] || MATRICES.general)[0]);
  const [status, setStatus] = useState({}); // { 'em_item_tones': 'norm' | 'path' }

  // Update categories if specialty changes
  useEffect(() => {
    const matrix = MATRICES[specialty] || MATRICES.general;
    setActiveCategory(Object.keys(matrix)[0]);
  }, [specialty]);

  const handleToggle = (item, type) => {
    if (!isEditable) return;

    const current = status[item];
    let newType = type;

    // Toggle off if clicking same
    if (current === type) {
      newType = null;
    }

    const newStatus = { ...status, [item]: newType };

    // Remove key if null
    if (!newType) delete newStatus[item];

    setStatus(newStatus);
    generateText(newStatus);
  };

  const generateText = (currentStatus) => {
    const phrases = [];

    Object.entries(currentStatus).forEach(([item, type]) => {
      const template = TEMPLATES[item];
      if (template && template[type]) {
        phrases.push(t(`misc.${template[type]}`));
      } else {
        // Fallback for missing templates
        const prefix = type === 'norm' ? 'N: ' : 'Path: ';
        phrases.push(`${prefix}${t(`misc.${item}`)}`);
      }
    });

    const text = phrases.length > 0 ?
    phrases.join('. ') + '.' :
    '';

    onGenerateText?.(text);
  };

  const matrix = MATRICES[specialty] || MATRICES.general;
  const items = matrix[activeCategory] || [];

  return (
    <div className={`ex-matrix ${!isEditable ? 'ex-matrix--readonly' : ''}`}>
            {/* Categories */}
            <div className="ex-matrix__categories">
                {Object.keys(matrix).map((cat) =>
        <button
          key={cat}
          className={`ex-matrix__cat-btn ${activeCategory === cat ? 'ex-matrix__cat-btn--active' : ''}`}
          onClick={() => setActiveCategory(cat)}>

                        {t(`misc.${cat}`)}
                    </button>
        )}
            </div>

            {/* Grid */}
            <div className="ex-matrix__grid">
                {items.map((item) => {
          const currentStatus = status[item];
          return (
            <div
              key={item}
              className={`ex-matrix__item ${currentStatus ? `ex-matrix__item--${currentStatus}` : 'ex-matrix__item--normal'}`}>

                            <span className="ex-matrix__label">{t(`misc.${item}`)}</span>
                            <div className="ex-matrix__actions">
                                {/* Button: Norm */}
                                <button
                  className={'ex-matrix__action-btn ex-matrix__action-btn--norm'}
                  onClick={() => handleToggle(item, 'norm')}
                  aria-label={t('misc.em_mark_norm', { item: t(`misc.${item}`) })}
                  title={t('misc.em_norm')}>

                                    <Check size={14} />
                                </button>
                                {/* Button: Path */}
                                <button
                  className={'ex-matrix__action-btn ex-matrix__action-btn--path'}
                  onClick={() => handleToggle(item, 'path')}
                  aria-label={t('misc.em_mark_path', { item: t(`misc.${item}`) })}
                  title={t('misc.em_pathology')}>

                                    <AlertCircle size={14} />
                                </button>
                            </div>
                        </div>);

        })}
            </div>
        </div>);

};

export default ExaminationMatrix;

ExaminationMatrix.propTypes = {
  specialty: PropTypes.oneOf(['general', 'cardiology', 'dermatology', 'dentist', 'dentistry']),
  onGenerateText: PropTypes.func,
  isEditable: PropTypes.bool,
};
