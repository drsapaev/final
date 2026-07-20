
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

import PropTypes from 'prop-types';
import { useState, useCallback } from 'react';
import EMRSection from '../EMRSection';
import React from 'react';
import EMRTextField from '../EMRTextField';
import './CardiologySection.css';
import { Heart, FileText } from 'lucide-react';
import { useTranslation } from '../../../../i18n/useTranslation';

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
export function CardiologySection({
  ecgData: ecgDataRaw = {},
  echoData: echoDataRaw = {},
  labResults: labResultsRaw = {},
  onChange,
  disabled = false,
}) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const ecgData = ecgDataRaw as Record<string, any>;
  const echoData = echoDataRaw as Record<string, any>;
  const labResults = labResultsRaw as Record<string, any>;
  const [activeTab, setActiveTab] = useState('ecg'); // 'ecg' | 'echo' | 'labs' | 'risk'

  // Handlers
  const handleLabResultChange = useCallback((field, value) => {
    onChange?.('cardio_labs', {
      ...labResults,
      [field]: value
    });
  }, [labResults, onChange]);

  return (
    <EMRSection
      title={t('misc.cs_title')}
      icon={<Heart size={16 as unknown as "small" | "default" | "large" | "xlarge"} aria-hidden="true" />}
      disabled={disabled}
      defaultOpen={true}>
      
            {/* Tabs */}
            <div className="cardiology-tabs">
                <button
          className={`cardiology-tab ${activeTab === 'ecg' ? 'active' : ''}`}
          onClick={() => setActiveTab('ecg')}
          disabled={disabled}>

                    {t('misc.cs_tab_ecg')}
                </button>
                <button
          className={`cardiology-tab ${activeTab === 'echo' ? 'active' : ''}`}
          onClick={() => setActiveTab('echo')}
          disabled={disabled}>

                    {t('misc.cs_tab_echo')}
                </button>
                <button
          className={`cardiology-tab ${activeTab === 'labs' ? 'active' : ''}`}
          onClick={() => setActiveTab('labs')}
          disabled={disabled}>

                    {t('misc.cs_tab_labs')}
                </button>
                <button
          className={`cardiology-tab ${activeTab === 'risk' ? 'active' : ''}`}
          onClick={() => setActiveTab('risk')}
          disabled={disabled}>

                    {t('misc.cs_tab_risk')}
                </button>
            </div>

            {/* ECG Tab - R-13: read-only summary instead of duplicate ECGViewer */}
            {activeTab === 'ecg' &&
      <div className="cardiology-tab-content">
                    <div className="cardiology-info-panel" role="status">
                            <div className="cardiology-info-icon"><FileText size={20 as unknown as "small" | "default" | "large" | "xlarge"} aria-hidden="true" /></div>
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
                            <div className="cardiology-info-icon"><FileText size={20 as unknown as "small" | "default" | "large" | "xlarge"} aria-hidden="true" /></div>
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
                            <div className="cardiology-info-icon"><FileText size={20 as unknown as "small" | "default" | "large" | "xlarge"} aria-hidden="true" /></div>
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
            onChange={(e) => handleLabResultChange('troponin_i', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 0.04" />

                        <EMRTextField
            label={t('misc.cs_lab_crp')}
            value={labResults?.crp || ''}
            onChange={(e) => handleLabResultChange('crp', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 3.0" />

                        <EMRTextField
            label={t('misc.cs_lab_cholesterol_total')}
            value={labResults?.cholesterol_total || ''}
            onChange={(e) => handleLabResultChange('cholesterol_total', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 200" />

                        <EMRTextField
            label={t('misc.cs_lab_cholesterol_hdl')}
            value={labResults?.cholesterol_hdl || ''}
            onChange={(e) => handleLabResultChange('cholesterol_hdl', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="> 40" />

                        <EMRTextField
            label={t('misc.cs_lab_cholesterol_ldl')}
            value={labResults?.cholesterol_ldl || ''}
            onChange={(e) => handleLabResultChange('cholesterol_ldl', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 100" />

                        <EMRTextField
            label={t('misc.cs_lab_triglycerides')}
            value={labResults?.triglycerides || ''}
            onChange={(e) => handleLabResultChange('triglycerides', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 150" />

                        <EMRTextField
            label={t('misc.cs_lab_glucose')}
            value={labResults?.glucose || ''}
            onChange={(e) => handleLabResultChange('glucose', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="70-100" />

                    </div>
                </div>
      }

            {/* Risk Calculator Tab */}
            {activeTab === 'risk' &&
      <div className="cardiology-tab-content">
                    <div className="cardiology-risk-calculator">
                        <h4>{t('misc.cs_score2_title')}</h4>
                        <p className="cardiology-info">
                            {t('misc.cs_score2_desc')}
                        </p>

                        {/* Risk Input Fields */}
                        <div className="cardiology-risk-inputs">
                            <EMRTextField
              label={t('misc.cs_age')}
              value={labResults?.patient_age || ''}
              onChange={(e) => handleLabResultChange('patient_age', e.target.value)}
              disabled={disabled}
              type="number"
              placeholder="40-69" />
            
                            <div className="cardiology-select-field">
                                <label>{t('misc.cs_sex')}</label>
                                <select
                value={labResults?.patient_sex || ''}
                onChange={(e) => handleLabResultChange('patient_sex', e.target.value)}
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
                onChange={(e) => handleLabResultChange('smoking', e.target.value)}
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
              onChange={(e) => handleLabResultChange('systolic_bp', e.target.value)}
              disabled={disabled}
              type="number"
              placeholder="120-180" />

                            <EMRTextField
              label={t('misc.cs_score2_chol')}
              value={labResults?.cholesterol_total || ''}
              onChange={(e) => handleLabResultChange('cholesterol_total', e.target.value)}
              disabled={disabled}
              type="number"
              placeholder={t('misc.cs_score2_chol_ph')} />
            
                        </div>

                        {/* Risk Calculation Result */}
                        <div className="cardiology-risk-result">
                            {(() => {
              const age = parseFloat(labResults?.patient_age);
              const sex = labResults?.patient_sex;
              const smoking = labResults?.smoking === 'yes';
              const sbp = parseFloat(labResults?.systolic_bp);
              const cholesterol = parseFloat(labResults?.cholesterol_total);

              // Check if all fields are filled
              if (!age || !sex || !labResults?.smoking || !sbp || !cholesterol) {
                return <p className="cardiology-risk-placeholder">{t('misc.cs_fill_all_fields')}</p>;
              }

              // Simplified SCORE2 calculation (ESC 2021 low-risk region approximation)
              // Base risk depends on age and sex
              const baseRisk = sex === 'male' ? 3 : 1.5;

              // Age factor (increases exponentially with age)
              const ageFactor = Math.pow(1.06, age - 50);

              // Smoking factor
              const smokingFactor = smoking ? 2.0 : 1.0;

              // SBP factor (per 10 mmHg above 120)
              const sbpFactor = 1 + (sbp - 120) / 10 * 0.15;

              // Cholesterol factor (per 1 mmol/L above 5)
              const cholesterolFactor = 1 + (cholesterol - 5) * 0.2;

              // Calculate final risk
              let risk = baseRisk * ageFactor * smokingFactor * sbpFactor * cholesterolFactor;
              risk = Math.max(1, Math.min(risk, 30)); // Clamp between 1-30%

              // Determine risk category
              let category, categoryClass, recommendation;
              if (risk < 5) {
                category = t('misc.cs_risk_low');
                categoryClass = 'low';
                recommendation = t('misc.cs_rec_low');
              } else if (risk < 10) {
                category = t('misc.cs_risk_moderate');
                categoryClass = 'moderate';
                recommendation = t('misc.cs_rec_moderate');
              } else if (risk < 20) {
                category = t('misc.cs_risk_high');
                categoryClass = 'high';
                recommendation = t('misc.cs_rec_high');
              } else {
                category = t('misc.cs_risk_very_high');
                categoryClass = 'very-high';
                recommendation = t('misc.cs_rec_very_high');
              }

              return (
                <div className="cardiology-risk-display">
                                        <div className={`cardiology-risk-score ${categoryClass}`}>
                                            <span className="risk-value">{risk.toFixed(1)}%</span>
                                            <span className="risk-label">{t('misc.cs_10y_risk')}</span>
                                        </div>
                                        <div className={`cardiology-risk-category ${categoryClass}`}>
                                            <span className="category-name">{category} {t('misc.cs_risk_word')}</span>
                                            <span className="category-recommendation">{recommendation}</span>
                                        </div>
                                        <div className="cardiology-risk-legend">
                                            <div className="legend-item low">{'<5%'} {t('misc.cs_risk_low')}</div>
                                            <div className="legend-item moderate">5-10% {t('misc.cs_risk_moderate')}</div>
                                            <div className="legend-item high">10-20% {t('misc.cs_risk_high')}</div>
                                            <div className="legend-item very-high">{'>20%'} {t('misc.cs_risk_very_high')}</div>
                                        </div>
                                    </div>);

            })()}
                        </div>
                    </div>
                </div>
      }
        </EMRSection>);

}

export default CardiologySection;

CardiologySection.propTypes = {
  ecgData: PropTypes.object,
  echoData: PropTypes.object,
  labResults: PropTypes.object,
  onChange: PropTypes.func,
  disabled: PropTypes.bool,
};
