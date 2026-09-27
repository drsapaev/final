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
 *
 * Косметологические процедуры (review follow-up P2-4b): записи живут в
 * specialty_data.cosmetic_procedures и редактируются здесь, в едином
 * осмотре ЭМК — с общим autosave/undo/conflict-механизмом контейнера.
 * Legacy-форма (DermaExamsTab) и POST /derma/procedures удалены (410,
 * P2-4a): двойная запись расщепляла клинические данные по двум таблицам.
 * Поле цены отсутствует намеренно — ценообразование управляется
 * прайс-менеджерами, а не клинической картой.
 */

import { useCallback, useState } from 'react';
import EMRSection from '../EMRSection';

import EMRSmartFieldV2 from '../EMRSmartFieldV2';
import { Button, Input, Textarea } from '../../../ui/macos';
import i18n from '@/i18n';
const i18nT = i18n.t as unknown as (key: string, options?: Record<string, unknown>) => string;

/** Одна запись косметической процедуры в specialty_data.cosmetic_procedures. */
export interface DermatologyCosmeticProcedureRecord {
  procedure_date: string;
  procedure_type: string;
  area_treated: string;
  products_used: string;
  results: string;
}

const EMPTY_PROCEDURE_DRAFT: DermatologyCosmeticProcedureRecord = {
  procedure_date: '',
  procedure_type: '',
  area_treated: '',
  products_used: '',
  results: '',
};

/**
 * DermatologySection Component
 *
 * @param {Object} props
 * @param {string} props.skinType - Тип кожи
 * @param {string} props.skinCondition - Состояние кожи
 * @param {Object} props.localization - Локализация поражений
 * @param {Function} props.onChange - Handler для изменения specialty_data
 * @param {boolean} props.disabled - Read-only mode
 * @param {Array} props.cosmeticProcedures - specialty_data.cosmetic_procedures
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
  cosmeticProcedures?: DermatologyCosmeticProcedureRecord[];
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
  disabled = false,
  cosmeticProcedures = [],
}: DermatologySectionProps) {

  // Handlers
  const handleSkinTypeChange = useCallback((value: string) => {
    onChange?.('skin_type', value);
  }, [onChange]);

  const [showProcedureForm, setShowProcedureForm] = useState(false);
  const [procedureDraft, setProcedureDraft] = useState<DermatologyCosmeticProcedureRecord>(
    EMPTY_PROCEDURE_DRAFT,
  );

  const handleProcedureAdd = useCallback(() => {
    if (disabled) return;
    const procedureDate = procedureDraft.procedure_date.trim();
    const procedureType = procedureDraft.procedure_type.trim();
    if (!procedureDate || !procedureType) return;

    onChange?.('cosmetic_procedures', [
      ...cosmeticProcedures,
      {
        procedure_date: procedureDate,
        procedure_type: procedureType,
        area_treated: procedureDraft.area_treated.trim(),
        products_used: procedureDraft.products_used.trim(),
        results: procedureDraft.results.trim(),
      },
    ]);
    setProcedureDraft(EMPTY_PROCEDURE_DRAFT);
    setShowProcedureForm(false);
  }, [cosmeticProcedures, disabled, onChange, procedureDraft]);

  const handleProcedureRemove = useCallback((index: number) => {
    if (disabled) return;
    onChange?.(
      'cosmetic_procedures',
      cosmeticProcedures.filter((_, position) => position !== index),
    );
  }, [cosmeticProcedures, disabled, onChange]);

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

            {/* Косметологические процедуры — specialty_data.cosmetic_procedures (P2-4b). */}
            <div className="dermatology-field-group">
              <div className="derma-flex-between-top">
                <label className="dermatology-label">
                  {i18nT('derma.derma_exams_cosmetic_title')} ({cosmeticProcedures.length})
                </label>
                {!disabled && !showProcedureForm && (
                  <Button type="button" onClick={() => setShowProcedureForm(true)}>
                    {i18nT('derma.derma_exams_cosmetic_new')}
                  </Button>
                )}
              </div>

              {cosmeticProcedures.length > 0 ? (
                <div className="derma-history-list-scroll derma-mt-16">
                  {cosmeticProcedures.map((procedure, index) => (
                    <article key={`${procedure.procedure_date}-${procedure.procedure_type}-${index}`} className="derma-card-p12-bg2-13">
                      <div className="derma-flex-between-top">
                        <span className="derma-p-14-secondary">{procedure.procedure_date}</span>
                        {!disabled && (
                          <Button
                            type="button"
                            variant="outline"
                            aria-label={i18nT('derma.derma_exams_cosmetic_remove', {
                              type: procedure.procedure_type,
                            })}
                            onClick={() => handleProcedureRemove(index)}>
                            {i18nT('derma.derma_exams_cosmetic_remove')}
                          </Button>
                        )}
                      </div>
                      {(procedure.procedure_type || procedure.area_treated || procedure.products_used || procedure.results) && (
                        <p className="derma-p-14-secondary">
                          {[
                            procedure.procedure_type ? `${i18nT('derma.derma_exams_cosmetic_type_inline')} ${procedure.procedure_type}` : '',
                            procedure.area_treated ? `${i18nT('derma.derma_exams_cosmetic_area_inline')} ${procedure.area_treated}` : '',
                            procedure.products_used ? `${i18nT('derma.derma_exams_cosmetic_products_inline')} ${procedure.products_used}` : '',
                            procedure.results,
                          ].filter(Boolean).join(' · ')}
                        </p>
                      )}
                    </article>
                  ))}
                </div>
              ) : (
                !showProcedureForm && (
                  <p className="derma-p-14-secondary derma-mt-16">
                    {i18nT('derma.derma_exams_cosmetic_empty')}
                  </p>
                )
              )}

              {showProcedureForm && !disabled && (
                <form
                  className="derma-mt-16"
                  onSubmit={(event) => {
                    event.preventDefault();
                    handleProcedureAdd();
                  }}>
                  <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: 'var(--mac-spacing-4)' }}>
                    <div>
                      <label className="derma-form-label" htmlFor="derma-procedure-date">
                        {i18nT('derma.derma_exams_cosmetic_date')}
                      </label>
                      <Input
                        id="derma-procedure-date"
                        type="date"
                        value={procedureDraft.procedure_date}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setProcedureDraft({
                          ...procedureDraft,
                          procedure_date: e.target.value,
                        })}
                        required />
                    </div>
                    <div>
                      <label className="derma-form-label" htmlFor="derma-procedure-type">
                        {i18nT('derma.derma_exams_cosmetic_type')}
                      </label>
                      <Input
                        id="derma-procedure-type"
                        value={procedureDraft.procedure_type}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setProcedureDraft({
                          ...procedureDraft,
                          procedure_type: e.target.value,
                        })}
                        placeholder={i18nT('derma.derma_exams_ph_meso')}
                        required />
                    </div>
                    <div>
                      <label className="derma-form-label" htmlFor="derma-procedure-area">
                        {i18nT('derma.derma_exams_cosmetic_area')}
                      </label>
                      <Input
                        id="derma-procedure-area"
                        value={procedureDraft.area_treated}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setProcedureDraft({
                          ...procedureDraft,
                          area_treated: e.target.value,
                        })}
                        placeholder={i18nT('derma.derma_exams_ph_face_neck')} />
                    </div>
                    <div>
                      <label className="derma-form-label" htmlFor="derma-procedure-products">
                        {i18nT('derma.derma_exams_cosmetic_products')}
                      </label>
                      <Input
                        id="derma-procedure-products"
                        value={procedureDraft.products_used}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setProcedureDraft({
                          ...procedureDraft,
                          products_used: e.target.value,
                        })}
                        placeholder={i18nT('derma.derma_exams_ph_hyaluronic')} />
                    </div>
                  </div>

                  <div className="derma-mt-16">
                    <label className="derma-form-label" htmlFor="derma-procedure-results">
                      {i18nT('derma.derma_exams_cosmetic_results')}
                    </label>
                    <Textarea
                      id="derma-procedure-results"
                      value={procedureDraft.results}
                      onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setProcedureDraft({
                        ...procedureDraft,
                        results: e.target.value,
                      })}
                      rows={2} />
                  </div>

                  <div className="derma-flex-gap-8 derma-mt-16" style={{ justifyContent: 'flex-end' }}>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setProcedureDraft(EMPTY_PROCEDURE_DRAFT);
                        setShowProcedureForm(false);
                      }}>
                      {i18nT('common.cancel')}
                    </Button>
                    <Button type="submit">{i18nT('derma.derma_exams_cosmetic_save')}</Button>
                  </div>
                </form>
              )}
            </div>
        </EMRSection>);

}

export default DermatologySection;
