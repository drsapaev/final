
/**
 * CardiologySection - Специализированная секция для кардиологии
 *
 * R-13 / P-005 (UX audit): the ECGViewer and EchoForm were previously
 * rendered inside this EMR specialty section AND on the dedicated
 * 'ecg' tab of CardiologistPanelUnified - two independent instances of
 * the same component sharing the same visitId/patientId but with
 * independent local state. Edits in one place were not visible in the
 * other without a reload, which violated DRY and created cognitive load
 * (the doctor had to remember "where did I enter this?").
 *
 * Fix: this section now shows a read-only summary of the latest ECG and
 * Echo data stored in specialty_data.ecg / specialty_data.echo, plus a
 * pointer to the dedicated 'ecg' tab where the full ECGViewer / EchoForm
 * live. Labs and the SCORE2 risk calculator stay here (they are unique
 * to the EMR context and not duplicated elsewhere).
 */

import { useState, useCallback } from 'react';
import EMRSection from '../EMRSection';
import React from 'react';
import EMRTextField from '../EMRTextField';
import type { EMRTextFieldChangeEvent } from '../EMRTextField';
import './CardiologySection.css';
import { Heart, FileText } from 'lucide-react';
import { useTranslation } from '@/i18n/useTranslation';

/**
 * CardiologySection Component
 * 
 * @param {Object} props
 * @param {Object} props.ecgData - ЭКГ данные из specialty_data
 * @param {Object} props.echoData - ЭхоКГ данные
 * @param {Object} props.labResults - Кардиологические анализы
 * @param {Function} props.onChange - Handler для изменения specialty_data
 * @param {boolean} props.disabled - Read-only mode
 */
interface CardiologySectionProps {
  ecgData?: Record<string, unknown>;
  echoData?: Record<string, unknown>;
  labResults?: Record<string, unknown>;
  onChange?: ((field: string, value: unknown) => void) | undefined;
  disabled?: boolean;
  visitId?: string | number | null | undefined;
  patientId?: string | number | null | undefined;
}


export function CardiologySection({
  ecgData: ecgDataRaw = {},
  echoData: echoDataRaw = {},
  labResults: labResultsRaw = {},
  onChange,
  disabled = false,
}: CardiologySectionProps) {
  const { t: rawT } = useTranslation(); const t = rawT;
  const ecgData = ecgDataRaw as Record<string, any>;
  const echoData = echoDataRaw as Record<string, any>;
  const labResults = labResultsRaw as Record<string, any>;
  const [activeTab, setActiveTab] = useState('ecg'); // 'ecg' | 'echo' | 'labs' | 'risk'

  // Handlers
  const handleLabResultChange = useCallback((field: string, value: unknown) => {
    onChange?.('cardio_labs', {
      ...labResults,
      [field]: value
    });
  }, [labResults, onChange]);

  return (
    <EMRSection
      title={t('misc.cs_title')}
      icon={<Heart size={16} aria-hidden="true" />}
      disabled={disabled}
      defaultOpen={true}>
      
            {/* Tabs */}
            {/* EMRCARD-FE-001 (audit 3886, round 21): the four tab buttons only
                switch the LOCAL view — they never mutate EMR data. Disabling them
                for signed/completed encounters locked the doctor out of the
                read-only Echo/Labs/Risk summaries, so navigation stays enabled
                while every clinical input inside the tabs keeps disabled={disabled}. */}
            <div className="cardiology-tabs">
                <button
          className={`cardiology-tab ${activeTab === 'ecg' ? 'active' : ''}`}
          onClick={() => setActiveTab('ecg')}
          aria-pressed={activeTab === 'ecg'}>

                    {t('misc.cs_tab_ecg')}
                </button>
                <button
          className={`cardiology-tab ${activeTab === 'echo' ? 'active' : ''}`}
          onClick={() => setActiveTab('echo')}
          aria-pressed={activeTab === 'echo'}>

                    {t('misc.cs_tab_echo')}
                </button>
                <button
          className={`cardiology-tab ${activeTab === 'labs' ? 'active' : ''}`}
          onClick={() => setActiveTab('labs')}
          aria-pressed={activeTab === 'labs'}>

                    {t('misc.cs_tab_labs')}
                </button>
                <button
          className={`cardiology-tab ${activeTab === 'risk' ? 'active' : ''}`}
          onClick={() => setActiveTab('risk')}
          aria-pressed={activeTab === 'risk'}>

                    {t('misc.cs_tab_risk')}
                </button>
            </div>

            {/* ECG Tab - R-13: read-only summary instead of duplicate ECGViewer */}
            {activeTab === 'ecg' &&
      <div className="cardiology-tab-content">
                    <div className="cardiology-info-panel" role="status">
                            <div className="cardiology-info-icon"><FileText size={20} aria-hidden="true" /></div>
                            <div className="cardiology-info-text">
                                <h4>{t('misc.cs_ecg_separate_tab')}</h4>
                                <p>
                                    {t('misc.cs_ecg_separate_tab_desc')}
                                </p>
                            </div>
                        </div>

                    {/* Summary of the latest ECG data stored in specialty_data.ecg */}
                    {(ecgData?.heart_rate || ecgData?.rhythm || ecgData?.interpretation) &&
        <div className="cardiology-interpretation">
                            <h4>{t('misc.cs_latest_ecg')}</h4>
                            <div className="cardiology-ecg-summary">
                                {ecgData?.heart_rate &&
                                    <div><strong>{t('misc.cs_hr')}</strong> {ecgData.heart_rate} {t('misc.cs_unit_bpm')}</div>
                                }
                                {ecgData?.rhythm &&
                                    <div><strong>{t('misc.cs_rhythm')}</strong> {ecgData.rhythm}</div>
                                }
                                {ecgData?.pr_interval &&
                                    <div><strong>PR:</strong> {ecgData.pr_interval} {t('misc.cs_unit_ms')}</div>
                                }
                                {ecgData?.qrs_duration &&
                                    <div><strong>QRS:</strong> {ecgData.qrs_duration} {t('misc.cs_unit_ms')}</div>
                                }
                                {ecgData?.qt_interval &&
                                    <div><strong>QT:</strong> {ecgData.qt_interval} {t('misc.cs_unit_ms')}</div>
                                }
                                {ecgData?.st_segment &&
                                    <div><strong>ST:</strong> {ecgData.st_segment}</div>
                                }
                                {ecgData?.t_wave &&
                                    <div><strong>T:</strong> {ecgData.t_wave}</div>
                                }
                            </div>
                            {ecgData?.interpretation &&
                                <p className="cardiology-ecg-interpretation">
                                    <em>{t('misc.cs_interpretation')}</em> {ecgData.interpretation}
                                </p>
                            }
                        </div>
        }
                </div>
      }

            {/* Echo Tab - R-13: read-only summary instead of duplicate EchoForm */}
            {activeTab === 'echo' &&
      <div className="cardiology-tab-content">
                    <div className="cardiology-info-panel" role="status">
                            <div className="cardiology-info-icon"><FileText size={20} aria-hidden="true" /></div>
                            <div className="cardiology-info-text">
                                <h4>{t('misc.cs_echo_separate_tab')}</h4>
                                <p>
                                    {t('misc.cs_echo_separate_tab_desc')}
                                </p>
                            </div>
                        </div>

                    {/* Summary of the latest Echo data stored in specialty_data.echo */}
                    {(echoData?.ef || echoData?.edd || echoData?.la || echoData?.conclusion) &&
        <div className="cardiology-interpretation">
                            <h4>{t('misc.cs_latest_echo')}</h4>
                            <div className="cardiology-ecg-summary">
                                {echoData?.edd &&
                                    <div><strong>{t('misc.cs_edd_lv')}</strong> {echoData.edd} {t('misc.cs_unit_mm')}</div>
                                }
                                {echoData?.esd &&
                                    <div><strong>{t('misc.cs_esd_lv')}</strong> {echoData.esd} {t('misc.cs_unit_mm')}</div>
                                }
                                {echoData?.ef &&
                                    <div><strong>{t('misc.cs_ef')}</strong> {echoData.ef}%</div>
                                }
                                {echoData?.la &&
                                    <div><strong>{t('misc.cs_la')}</strong> {echoData.la} {t('misc.cs_unit_mm')}</div>
                                }
                                {echoData?.aortic?.peak_velocity &&
                                    <div><strong>{t('misc.cs_vmax_av')}</strong> {echoData.aortic.peak_velocity} {t('misc.cs_unit_ms2')}</div>
                                }
                            </div>
                            {echoData?.conclusion &&
                                <p className="cardiology-ecg-interpretation">
                                    <em>{t('misc.cs_conclusion')}</em> {echoData.conclusion}
                                </p>
                            }
                        </div>
        }
                </div>
      }

            {/* Lab Results Tab - R-12 / P-004 (UX audit): unified units to мг/дл.
                P2: legacy manual-entry CardioBloodTest. This will be deprecated
                in favor of LabResultsSection (below specialty sections in
                EMRContainerV2) which reads from the canonical LabReportInstance
                model. Kept for back-compat until CardioBloodTest data is migrated. */}
            {activeTab === 'labs' &&
      <div className="cardiology-tab-content">
                    <div className="cardiology-info-panel" role="status">
                            <div className="cardiology-info-icon"><FileText size={20} aria-hidden="true" /></div>
                            <div className="cardiology-info-text">
                                <h4>{t('misc.cs_labs_full_form_tab')}</h4>
                                <p>
                                    {t('misc.cs_labs_full_form_tab_desc')}
                                </p>
                            </div>
                        </div>

                    <div className="cardiology-labs-grid">
                        <EMRTextField
            label={t('misc.cs_lab_troponin')}
            value={labResults?.troponin_i || ''}
            onChange={(e: EMRTextFieldChangeEvent) => handleLabResultChange('troponin_i', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 0.04" />

                        <EMRTextField
            label={t('misc.cs_lab_crp')}
            value={labResults?.crp || ''}
            onChange={(e: EMRTextFieldChangeEvent) => handleLabResultChange('crp', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 3.0" />

                        <EMRTextField
            label={t('misc.cs_lab_cholesterol_total')}
            value={labResults?.cholesterol_total || ''}
            onChange={(e: EMRTextFieldChangeEvent) => handleLabResultChange('cholesterol_total', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 200" />

                        <EMRTextField
            label={t('misc.cs_lab_cholesterol_hdl')}
            value={labResults?.cholesterol_hdl || ''}
            onChange={(e: EMRTextFieldChangeEvent) => handleLabResultChange('cholesterol_hdl', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="> 40" />

                        <EMRTextField
            label={t('misc.cs_lab_cholesterol_ldl')}
            value={labResults?.cholesterol_ldl || ''}
            onChange={(e: EMRTextFieldChangeEvent) => handleLabResultChange('cholesterol_ldl', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 100" />

                        <EMRTextField
            label={t('misc.cs_lab_triglycerides')}
            value={labResults?.triglycerides || ''}
            onChange={(e: EMRTextFieldChangeEvent) => handleLabResultChange('triglycerides', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 150" />

                        <EMRTextField
            label={t('misc.cs_lab_glucose')}
            value={labResults?.glucose || ''}
            onChange={(e: EMRTextFieldChangeEvent) => handleLabResultChange('glucose', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="70-100" />

                    </div>
                </div>
      }

            {/* Risk Calculator Tab */}
            {/* EMRSCORE-FE-001 + EMRSCORE-FE-002 (audit 3886, round 21):
                this panel used to multiply a few linear factors (with the
                legacy mg/dL cholesterol fed straight into a per-mmol/L
                formula!) and present the clamped result as a «SCORE2
                10-year risk» with fixed 5/10/20% treatment bands. That
                number was never a SCORE2 prediction and could clinically
                misclassify patients. The panel is now an eligibility check:
                explicit prior-CVD / diabetes / ESC-risk-region inputs,
                a hard 40–69 age gate, unit-explicit cholesterol (mg/dL is
                converted with the exact 38.67 divisor for display only),
                and an honest verdict — NO fabricated numeric risk, category
                or drug recommendation is rendered; the eligible case points
                to the official ESC calculator. Only input facts are
                persisted (cardio_labs.*), never a computed "official" score. */}
            {activeTab === 'risk' &&
      <div className="cardiology-tab-content">
                    <div className="cardiology-risk-calculator">
                        <h4>{t('misc.cs_score2_title')}</h4>
                        <p className="cardiology-info">
                            {t('misc.cs_score2_desc_v2')}
                        </p>

                        {/* Risk Input Fields */}
                        <div className="cardiology-risk-inputs">
                            <EMRTextField
              label={t('misc.cs_age')}
              value={labResults?.patient_age || ''}
              onChange={(e: EMRTextFieldChangeEvent) => handleLabResultChange('patient_age', e.target.value)}
              disabled={disabled}
              type="number"
              placeholder="40-69" />

                            <div className="cardiology-select-field">
                                <label>{t('misc.cs_sex')}</label>
                                <select
                value={labResults?.patient_sex || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleLabResultChange('patient_sex', e.target.value)}
                disabled={disabled}
                className="cardiology-select">

                                    <option value="">{t('misc.cs_select')}</option>
                                    <option value="male">{t('misc.cs_male')}</option>
                                    <option value="female">{t('misc.cs_female')}</option>
                                </select>
                            </div>
                            <div className="cardiology-select-field">
                                <label>{t('misc.cs_smoking')}</label>
                                <select
                value={labResults?.smoking || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleLabResultChange('smoking', e.target.value)}
                disabled={disabled}
                className="cardiology-select">

                                    <option value="">{t('misc.cs_select')}</option>
                                    <option value="no">{t('misc.cs_not_smoking')}</option>
                                    <option value="yes">{t('misc.cs_smoking_yes')}</option>
                                </select>
                            </div>
                            <EMRTextField
              label={t('misc.cs_systolic_bp')}
              value={labResults?.systolic_bp || ''}
              onChange={(e: EMRTextFieldChangeEvent) => handleLabResultChange('systolic_bp', e.target.value)}
              disabled={disabled}
              type="number"
              placeholder="120-180" />

                            {/* EMRSCORE-FE-001: cholesterol for the risk panel is
                                its OWN unit-explicit field — the legacy
                                cardio_labs.cholesterol_total stays mg/dL for the
                                labs tab and is never silently reinterpreted as
                                mmol/L by the risk formula again. */}
                            <div className="cardiology-chol-field">
                                <EMRTextField
              label={t('misc.cs_score2_chol_own')}
              value={labResults?.score2_chol || ''}
              onChange={(e: EMRTextFieldChangeEvent) => handleLabResultChange('score2_chol', e.target.value)}
              disabled={disabled}
              type="number"
              placeholder={labResults?.score2_chol_unit === 'mgdl' ? '150-250' : '4-8'} />
                                <div className="cardiology-select-field">
                                    <label>{t('misc.cs_score2_unit')}</label>
                                    <select
                value={labResults?.score2_chol_unit || 'mmol'}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleLabResultChange('score2_chol_unit', e.target.value)}
                disabled={disabled}
                className="cardiology-select">
                                        <option value="mmol">{t('misc.cs_unit_mmol')}</option>
                                        <option value="mgdl">{t('misc.cs_unit_mgdl')}</option>
                                    </select>
                                </div>
                                {(() => {
                                    const cholRaw = parseFloat(labResults?.score2_chol);
                                    if (labResults?.score2_chol_unit === 'mgdl' && Number.isFinite(cholRaw) && cholRaw > 0) {
                                        return <p className="cardiology-chol-equiv" data-testid="score2-chol-equiv">
                                            {t('misc.cs_score2_chol_equiv', { value: (cholRaw / 38.67).toFixed(1) })}
                                        </p>;
                                    }
                                    return null;
                                })()}
                            </div>

                            {/* EMRSCORE-FE-002: eligibility inputs — SCORE2 is
                                validated for 40–69-year-olds WITHOUT established
                                CVD and WITHOUT diabetes. */}
                            <div className="cardiology-select-field">
                                <label>{t('misc.cs_score2_prior_cvd')}</label>
                                <select
                value={labResults?.prior_cvd || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleLabResultChange('prior_cvd', e.target.value)}
                disabled={disabled}
                className="cardiology-select">
                                    <option value="">{t('misc.cs_select')}</option>
                                    <option value="no">{t('common.no')}</option>
                                    <option value="yes">{t('common.yes')}</option>
                                </select>
                            </div>
                            <div className="cardiology-select-field">
                                <label>{t('misc.cs_score2_diabetes')}</label>
                                <select
                value={labResults?.diabetes || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleLabResultChange('diabetes', e.target.value)}
                disabled={disabled}
                className="cardiology-select">
                                    <option value="">{t('misc.cs_select')}</option>
                                    <option value="no">{t('common.no')}</option>
                                    <option value="yes">{t('common.yes')}</option>
                                </select>
                            </div>
                            <div className="cardiology-select-field">
                                <label>{t('misc.cs_score2_region')}</label>
                                <select
                value={labResults?.risk_region || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => handleLabResultChange('risk_region', e.target.value)}
                disabled={disabled}
                className="cardiology-select">
                                    <option value="">{t('misc.cs_select')}</option>
                                    <option value="low">{t('misc.cs_score2_region_low')}</option>
                                    <option value="moderate">{t('misc.cs_score2_region_moderate')}</option>
                                    <option value="high">{t('misc.cs_score2_region_high')}</option>
                                    <option value="very-high">{t('misc.cs_score2_region_very_high')}</option>
                                </select>
                            </div>
                        </div>

                        {/* Eligibility verdict — replaces the fabricated number */}
                        <div className="cardiology-risk-result" data-testid="score2-verdict">
                            {(() => {
              const age = parseFloat(labResults?.patient_age);
              const sex = labResults?.patient_sex;
              const smoking = labResults?.smoking;
              const sbp = parseFloat(labResults?.systolic_bp);
              const chol = parseFloat(labResults?.score2_chol);
              const priorCvd = labResults?.prior_cvd;
              const diabetes = labResults?.diabetes;
              const region = labResults?.risk_region;
              const regionLabel = (code: string) => ({
                'low': t('misc.cs_score2_region_low'),
                'moderate': t('misc.cs_score2_region_moderate'),
                'high': t('misc.cs_score2_region_high'),
                'very-high': t('misc.cs_score2_region_very_high'),
              } as Record<string, string>)[code] || code;

              // Missing or non-positive inputs → keep the fill-in placeholder
              if (!Number.isFinite(age) || age <= 0 || !sex || !smoking
                || !Number.isFinite(sbp) || sbp <= 0
                || !Number.isFinite(chol) || chol <= 0
                || !priorCvd || !diabetes) {
                return <p className="cardiology-risk-placeholder">{t('misc.cs_fill_all_fields')}</p>;
              }

              // EMRSCORE-FE-002: region is required — the model is calibrated
              // per ESC risk region and an uncalibrated verdict is meaningless.
              if (!region) {
                return <p className="cardiology-score2-notice" role="status">{t('misc.cs_score2_region_missing')}</p>;
              }

              // EMRSCORE-FE-002: hard age gate — the SCORE2 cohort is 40–69.
              if (age < 40 || age > 69) {
                return <p className="cardiology-score2-notice" role="status">{t('misc.cs_score2_age_out')}</p>;
              }

              // EMRSCORE-FE-002: established CVD / diabetes are outside the
              // SCORE2 population (secondary prevention / other scales).
              if (priorCvd === 'yes' || diabetes === 'yes') {
                return <p className="cardiology-score2-notice" role="status">{t('misc.cs_score2_high_risk_pop')}</p>;
              }

              // EMRSCORE-FE-001: eligible inputs, but NO fabricated number —
              // the numeric SCORE2 must come from the official ESC calculator
              // with region calibration; we only echo the unit-canonical input.
              const cholMmol = labResults?.score2_chol_unit === 'mgdl' ? chol / 38.67 : chol;
              return (
                <div className="cardiology-score2-eligible" role="status">
                  <p>{t('misc.cs_score2_no_number', { region: regionLabel(region), chol: cholMmol.toFixed(1) })}</p>
                </div>
              );

            })()}
                        </div>
                    </div>
                </div>
      }
        </EMRSection>);

}

export default CardiologySection;

