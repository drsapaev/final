
/**
 * DermaExamsTab — R-15: extracted from DermatologistPanelUnified.
 *
 * Renders the "Осмотр кожи" (skin) and "Косметология" (cosmetic) tabs.
 * Each tab shows a form + history list.
 */
import PropTypes from 'prop-types';
import { MacOSCard, Button, Input, Select, Textarea, Badge } from '../ui/macos';
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";

export function DermaExamsTab({
  activeTab,
  // Skin examination
  skinExamination,
  setSkinExamination,
  showSkinForm,
  skinExaminations = [],
  onSkinSubmit,
  onOpenSkinForm,
  onCancelSkinForm,
  // Cosmetic procedures
  cosmeticProcedure,
  setCosmeticProcedure,
  showCosmeticForm,
  cosmeticProcedures = [],
  onCosmeticSubmit,
  onOpenCosmeticForm,
  onCancelCosmeticForm,
  // Theme
  getColor,
  getFontSize,
  getSpacing,
}) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  if (activeTab === 'skin') {
    return (
      <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: getSpacing('xl') }}>
        <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--mac-spacing-5)' }}>
            <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
              {t('derma.derma_exams_skin_title')}
            </h3>
            <Button onClick={onOpenSkinForm}>{t('derma.derma_exams_skin_new')}</Button>
          </div>

          {showSkinForm && (
            <form onSubmit={onSkinSubmit} style={{ marginBottom: 'var(--mac-spacing-6)' }}>
              <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: 'var(--mac-spacing-4)' }}>
                <div>
                  <label className="derma-form-label">{t('derma.derma_exams_skin_date')}</label>
                  <Input type="date" aria-label={t('derma.derma_exams_skin_date')} value={skinExamination.exam_date || ''} onChange={(e) => setSkinExamination({ ...skinExamination, exam_date: e.target.value })} required />
                </div>
                <div>
                  <label className="derma-form-label">{t('derma.derma_exams_skin_type')}</label>
                  <Select aria-label={t('derma.derma_exams_skin_type')} value={skinExamination.skin_type || ''} onChange={(v: unknown) => setSkinExamination({ ...skinExamination, skin_type: String(v) })}>
                    <option value="">{t('derma.derma_exams_select')}</option>
                    <option value="normal">{t('derma.derma_exams_skin_type_normal')}</option>
                    <option value="dry">{t('derma.derma_exams_skin_type_dry')}</option>
                    <option value="oily">{t('derma.derma_exams_skin_type_oily')}</option>
                    <option value="combination">{t('derma.derma_exams_skin_type_combination')}</option>
                    <option value="sensitive">{t('derma.derma_exams_skin_type_sensitive')}</option>
                  </Select>
                </div>
                <div>
                  <label className="derma-form-label">{t('derma.derma_exams_skin_condition')}</label>
                  <Input aria-label={t('derma.derma_exams_skin_condition')} value={skinExamination.skin_condition || ''} onChange={(e) => setSkinExamination({ ...skinExamination, skin_condition: e.target.value })} placeholder={t('derma.derma_exams_ph_skin_condition')} />
                </div>
                <div>
                  <label className="derma-form-label">{t('derma.derma_exams_lesions')}</label>
                  <Input aria-label={t('derma.derma_exams_lesions')} value={skinExamination.lesions || ''} onChange={(e) => setSkinExamination({ ...skinExamination, lesions: e.target.value })} placeholder={t('derma.derma_exams_ph_lesions')} />
                </div>
                <div>
                  <label className="derma-form-label">{t('derma.derma_exams_distribution')}</label>
                  <Input aria-label={t('derma.derma_exams_distribution')} value={skinExamination.distribution || ''} onChange={(e) => setSkinExamination({ ...skinExamination, distribution: e.target.value })} placeholder={t('derma.derma_exams_ph_face_neck')} />
                </div>
                <div>
                  <label className="derma-form-label">{t('derma.derma_exams_symptoms')}</label>
                  <Input aria-label={t('derma.derma_exams_symptoms')} value={skinExamination.symptoms || ''} onChange={(e) => setSkinExamination({ ...skinExamination, symptoms: e.target.value })} placeholder={t('derma.derma_exams_ph_symptoms')} />
                </div>
              </div>
              <div style={{ marginTop: 'var(--mac-spacing-4)' }}>
                <label className="derma-form-label">{t('derma.derma_exams_diagnosis')}</label>
                <Textarea aria-label={t('derma.derma_exams_diagnosis')} value={skinExamination.diagnosis || ''} onChange={(e) => setSkinExamination({ ...skinExamination, diagnosis: e.target.value })} rows={2} />
              </div>
              <div style={{ marginTop: 'var(--mac-spacing-4)' }}>
                <label className="derma-form-label">{t('derma.derma_exams_treatment_plan')}</label>
                <Textarea aria-label={t('derma.derma_exams_treatment_plan')} value={skinExamination.treatment_plan || ''} onChange={(e) => setSkinExamination({ ...skinExamination, treatment_plan: e.target.value })} rows={3} />
              </div>
              <div style={{ display: 'flex', gap: 'var(--mac-spacing-3)', justifyContent: 'flex-end', marginTop: 'var(--mac-spacing-4)' }}>
                <Button type="button" variant="outline" onClick={onCancelSkinForm}>{t('common.cancel')}</Button>
                <Button type="submit">{t('derma.derma_exams_skin_save')}</Button>
              </div>
            </form>
          )}

          {skinExaminations.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-3)' }}>
              {skinExaminations.map((exam) => (
                <div key={exam.id} style={{ padding: 'var(--mac-spacing-4)', border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-md)', background: 'var(--mac-surface)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--mac-spacing-2)' }}>
                    <Badge variant="info">{exam.exam_date}</Badge>
                    {exam.skin_type && <span style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)' }}>{t('derma.derma_exams_skin_type_inline')} {exam.skin_type}</span>}
                  </div>
                  {exam.skin_condition && <div style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>{t('derma.derma_exams_condition_inline')} {exam.skin_condition}</div>}
                  {exam.lesions && <div style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>{t('derma.derma_exams_lesions_inline')} {exam.lesions}</div>}
                  {exam.diagnosis && <div style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>{t('derma.derma_exams_diagnosis_inline')} {exam.diagnosis}</div>}
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '48px', color: 'var(--mac-text-secondary)' }}>
              {t('derma.derma_exams_skin_empty')}
            </div>
          )}
        </MacOSCard>
      </div>
    );
  }

  if (activeTab === 'cosmetic') {
    return (
      <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: getSpacing('xl') }}>
        <MacOSCard style={{ padding: 'var(--mac-spacing-6)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--mac-spacing-5)' }}>
            <h3 style={{ fontSize: 'var(--mac-font-size-xl)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
              {t('derma.derma_exams_cosmetic_title')}
            </h3>
            <Button onClick={onOpenCosmeticForm}>{t('derma.derma_exams_cosmetic_new')}</Button>
          </div>

          {showCosmeticForm && (
            <form onSubmit={onCosmeticSubmit} style={{ marginBottom: 'var(--mac-spacing-6)' }}>
              <div className="grid grid-cols-1 md:grid-cols-2" style={{ gap: 'var(--mac-spacing-4)' }}>
                <div>
                  <label className="derma-form-label">{t('derma.derma_exams_cosmetic_date')}</label>
                  <Input type="date" aria-label={t('derma.derma_exams_cosmetic_date')} value={cosmeticProcedure.procedure_date || ''} onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, procedure_date: e.target.value })} required />
                </div>
                <div>
                  <label className="derma-form-label">{t('derma.derma_exams_cosmetic_type')}</label>
                  <Input aria-label={t('derma.derma_exams_cosmetic_type')} value={cosmeticProcedure.procedure_type || ''} onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, procedure_type: e.target.value })} placeholder={t('derma.derma_exams_ph_meso')} />
                </div>
                <div>
                  <label className="derma-form-label">{t('derma.derma_exams_cosmetic_area')}</label>
                  <Input aria-label={t('derma.derma_exams_cosmetic_area_aria')} value={cosmeticProcedure.area_treated || ''} onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, area_treated: e.target.value })} placeholder={t('derma.derma_exams_ph_face_neck')} />
                </div>
                <div>
                  <label className="derma-form-label">{t('derma.derma_exams_cosmetic_products')}</label>
                  <Input aria-label={t('derma.derma_exams_cosmetic_products')} value={cosmeticProcedure.products_used || ''} onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, products_used: e.target.value })} placeholder={t('derma.derma_exams_ph_hyaluronic')} />
                </div>
                <div>
                  <label className="derma-form-label">{t('derma.derma_exams_cosmetic_cost')}</label>
                  <Input type="number" aria-label={t('derma.derma_exams_cosmetic_cost_aria')} value={cosmeticProcedure.total_cost || ''} onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, total_cost: e.target.value })} placeholder="0" />
                </div>
              </div>
              <div style={{ marginTop: 'var(--mac-spacing-4)' }}>
                <label className="derma-form-label">{t('derma.derma_exams_cosmetic_results')}</label>
                <Textarea aria-label={t('derma.derma_exams_cosmetic_results')} value={cosmeticProcedure.results || ''} onChange={(e) => setCosmeticProcedure({ ...cosmeticProcedure, results: e.target.value })} rows={2} />
              </div>
              <div style={{ display: 'flex', gap: 'var(--mac-spacing-3)', justifyContent: 'flex-end', marginTop: 'var(--mac-spacing-4)' }}>
                <Button type="button" variant="outline" onClick={onCancelCosmeticForm}>{t('common.cancel')}</Button>
                <Button type="submit">{t('derma.derma_exams_cosmetic_save')}</Button>
              </div>
            </form>
          )}

          {cosmeticProcedures.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--mac-spacing-3)' }}>
              {cosmeticProcedures.map((proc) => (
                <div key={proc.id} style={{ padding: 'var(--mac-spacing-4)', border: '1px solid var(--mac-border)', borderRadius: 'var(--mac-radius-md)', background: 'var(--mac-surface)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--mac-spacing-2)' }}>
                    <Badge variant="info">{proc.procedure_date}</Badge>
                    <span style={{ fontSize: 'var(--mac-font-size-base)', fontWeight: 'var(--mac-font-weight-semibold)', color: 'var(--mac-text-primary)' }}>
                      {Number(proc.total_cost || 0).toLocaleString()} UZS
                    </span>
                  </div>
                  {proc.procedure_type && <div style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>{t('derma.derma_exams_cosmetic_type_inline')} {proc.procedure_type}</div>}
                  {proc.area_treated && <div style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>{t('derma.derma_exams_cosmetic_area_inline')} {proc.area_treated}</div>}
                  {proc.products_used && <div style={{ fontSize: 'var(--mac-font-size-base)', color: 'var(--mac-text-secondary)', marginBottom: 'var(--mac-spacing-1)' }}>{t('derma.derma_exams_cosmetic_products_inline')} {proc.products_used}</div>}
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '48px', color: 'var(--mac-text-secondary)' }}>
              {t('derma.derma_exams_cosmetic_empty')}
            </div>
          )}
        </MacOSCard>
      </div>
    );
  }

  return null;
}

DermaExamsTab.propTypes = {
  activeTab: PropTypes.string.isRequired,
  skinExamination: PropTypes.object,
  setSkinExamination: PropTypes.func,
  showSkinForm: PropTypes.bool,
  skinExaminations: PropTypes.array,
  onSkinSubmit: PropTypes.func,
  onOpenSkinForm: PropTypes.func,
  onCancelSkinForm: PropTypes.func,
  cosmeticProcedure: PropTypes.object,
  setCosmeticProcedure: PropTypes.func,
  showCosmeticForm: PropTypes.bool,
  cosmeticProcedures: PropTypes.array,
  onCosmeticSubmit: PropTypes.func,
  onOpenCosmeticForm: PropTypes.func,
  onCancelCosmeticForm: PropTypes.func,
  getColor: PropTypes.func,
  getFontSize: PropTypes.func,
  getSpacing: PropTypes.func,
};

export default DermaExamsTab;