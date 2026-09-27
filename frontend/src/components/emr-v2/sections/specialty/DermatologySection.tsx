/**
 * DermatologySection - Специализированная секция для дерматологии
 *
 * Клинические поля дерматологического осмотра внутри ЭМК (единый осмотр,
 * пункт 7 плана аудита): диагноз остаётся в основном поле ЭМК.
 *
 * Фото визита НЕ хранятся в specialty_data (пункт 8 плана аудита):
 * единственный источник фото — файловый API /files, галерея текущего визита
 * встроена в экран приёма (DermaVisitGallery). Старые значения blob: в
 * specialty_data.photos не мигрируются и не считаются сохранёнными.
 */

import { useCallback } from 'react';
import EMRSection from '../EMRSection';

import EMRSmartFieldV2 from '../EMRSmartFieldV2';
import i18n from '@/i18n';
const i18nT = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;

/**
 * DermatologySection Component
 *
 * @param {Object} props
 * @param {string} props.skinType - Тип кожи
 * @param {string} props.skinCondition - Состояние кожи
 * @param {Object} props.localization - Локализация поражений
 * @param {Function} props.onChange - Handler для изменения specialty_data
 * @param {boolean} props.disabled - Read-only mode
 */
interface DermatologySectionProps {
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

  // Handlers
  const handleSkinTypeChange = useCallback((value: string) => {
    onChange?.('skin_type', value);
  }, [onChange]);

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
        </EMRSection>);

}

export default DermatologySection;
