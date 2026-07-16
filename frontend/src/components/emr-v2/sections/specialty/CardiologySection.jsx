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
  ecgData = {},
  echoData = {},
  labResults = {},
  onChange,
  disabled = false,
}) {
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
      title="Кардиологические данные"
      icon={<Heart size={16} aria-hidden="true" />}
      disabled={disabled}
      defaultOpen={true}>
      
            {/* Tabs */}
            <div className="cardiology-tabs">
                <button
          className={`cardiology-tab ${activeTab === 'ecg' ? 'active' : ''}`}
          onClick={() => setActiveTab('ecg')}
          disabled={disabled}>
          
                    ЭКГ
                </button>
                <button
          className={`cardiology-tab ${activeTab === 'echo' ? 'active' : ''}`}
          onClick={() => setActiveTab('echo')}
          disabled={disabled}>
          
                    ЭхоКГ
                </button>
                <button
          className={`cardiology-tab ${activeTab === 'labs' ? 'active' : ''}`}
          onClick={() => setActiveTab('labs')}
          disabled={disabled}>
          
                    Анализы
                </button>
                <button
          className={`cardiology-tab ${activeTab === 'risk' ? 'active' : ''}`}
          onClick={() => setActiveTab('risk')}
          disabled={disabled}>
          
                    Риски
                </button>
            </div>

            {/* ECG Tab - R-13: read-only summary instead of duplicate ECGViewer */}
            {activeTab === 'ecg' &&
      <div className="cardiology-tab-content">
                    <div className="cardiology-info-panel" role="status">
                            <div className="cardiology-info-icon"><FileText size={20} aria-hidden="true" /></div>
                            <div className="cardiology-info-text">
                                <h4>ЭКГ доступна на отдельной вкладке</h4>
                                <p>
                                    Полный просмотрщик ЭКГ (загрузка файлов, парсинг параметров,
                                    AI-анализ) находится на вкладке <strong>«ЭКГ»</strong> в боковой
                                    панели кардиолога. Это устраняет дублирование данных и
                                    гарантирует, что изменения отображаются в одном месте.
                                </p>
                            </div>
                        </div>

                    {/* Summary of the latest ECG data stored in specialty_data.ecg */}
                    {(ecgData?.heart_rate || ecgData?.rhythm || ecgData?.interpretation) &&
        <div className="cardiology-interpretation">
                            <h4>Последняя запись ЭКГ:</h4>
                            <div className="cardiology-ecg-summary">
                                {ecgData?.heart_rate &&
                                    <div><strong>ЧСС:</strong> {ecgData.heart_rate} уд/мин</div>
                                }
                                {ecgData?.rhythm &&
                                    <div><strong>Ритм:</strong> {ecgData.rhythm}</div>
                                }
                                {ecgData?.pr_interval &&
                                    <div><strong>PR:</strong> {ecgData.pr_interval} мс</div>
                                }
                                {ecgData?.qrs_duration &&
                                    <div><strong>QRS:</strong> {ecgData.qrs_duration} мс</div>
                                }
                                {ecgData?.qt_interval &&
                                    <div><strong>QT:</strong> {ecgData.qt_interval} мс</div>
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
                                    <em>Интерпретация:</em> {ecgData.interpretation}
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
                                <h4>ЭхоКГ доступна на отдельной вкладке</h4>
                                <p>
                                    Полная форма ЭхоКГ (левый желудочек, предсердия, клапаны,
                                    заключение) находится на вкладке <strong>«ЭКГ»</strong> в боковой
                                    панели кардиолога (в разделе ЭхоКГ под загрузчиком ЭКГ).
                                </p>
                            </div>
                        </div>

                    {/* Summary of the latest Echo data stored in specialty_data.echo */}
                    {(echoData?.ef || echoData?.edd || echoData?.la || echoData?.conclusion) &&
        <div className="cardiology-interpretation">
                            <h4>Последние данные ЭхоКГ:</h4>
                            <div className="cardiology-ecg-summary">
                                {echoData?.edd &&
                                    <div><strong>КДО ЛЖ:</strong> {echoData.edd} мм</div>
                                }
                                {echoData?.esd &&
                                    <div><strong>КСО ЛЖ:</strong> {echoData.esd} мм</div>
                                }
                                {echoData?.ef &&
                                    <div><strong>ФВ:</strong> {echoData.ef}%</div>
                                }
                                {echoData?.la &&
                                    <div><strong>ЛП:</strong> {echoData.la} мм</div>
                                }
                                {echoData?.aortic?.peak_velocity &&
                                    <div><strong>Vmax аорт. клапана:</strong> {echoData.aortic.peak_velocity} м/с</div>
                                }
                            </div>
                            {echoData?.conclusion &&
                                <p className="cardiology-ecg-interpretation">
                                    <em>Заключение:</em> {echoData.conclusion}
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
                                <h4>Полная форма анализов крови — на вкладке «Анализы крови»</h4>
                                <p>
                                    Ввод, история и средние значения анализов крови доступны на
                                    отдельной вкладке <strong>«Анализы крови»</strong> в боковой панели
                                    кардиолога. Ниже приведены единицы измерения и нормальные значения
                                    для быстрого ориентирования. <strong>Все единицы унифицированы
                                    с основной формой (мг/дл)</strong> — устраняет риск путаницы
                                    между мг/дл и ммоль/л (разница в 38.7 раз).
                                </p>
                            </div>
                        </div>

                    <div className="cardiology-labs-grid">
                        <EMRTextField
            label="Тропонин I (нг/мл)"
            value={labResults?.troponin_i || ''}
            onChange={(e) => handleLabResultChange('troponin_i', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 0.04" />

                        <EMRTextField
            label="CRP (мг/л)"
            value={labResults?.crp || ''}
            onChange={(e) => handleLabResultChange('crp', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 3.0" />

                        <EMRTextField
            label="Холестерин общий (мг/дл)"
            value={labResults?.cholesterol_total || ''}
            onChange={(e) => handleLabResultChange('cholesterol_total', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 200" />

                        <EMRTextField
            label="Холестерин ЛПВП (мг/дл)"
            value={labResults?.cholesterol_hdl || ''}
            onChange={(e) => handleLabResultChange('cholesterol_hdl', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="> 40" />

                        <EMRTextField
            label="Холестерин ЛПНП (мг/дл)"
            value={labResults?.cholesterol_ldl || ''}
            onChange={(e) => handleLabResultChange('cholesterol_ldl', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 100" />

                        <EMRTextField
            label="Триглицериды (мг/дл)"
            value={labResults?.triglycerides || ''}
            onChange={(e) => handleLabResultChange('triglycerides', e.target.value)}
            disabled={disabled}
            type="number"
            placeholder="< 150" />

                        <EMRTextField
            label="Глюкоза (мг/дл)"
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
                        <h4>SCORE2 калькулятор риска</h4>
                        <p className="cardiology-info">
                            Калькулятор 10-летнего риска сердечно-сосудистых событий (ESC 2021)
                        </p>

                        {/* Risk Input Fields */}
                        <div className="cardiology-risk-inputs">
                            <EMRTextField
              label="Возраст (лет)"
              value={labResults?.patient_age || ''}
              onChange={(e) => handleLabResultChange('patient_age', e.target.value)}
              disabled={disabled}
              type="number"
              placeholder="40-69" />
            
                            <div className="cardiology-select-field">
                                <label>Пол</label>
                                <select
                value={labResults?.patient_sex || ''}
                onChange={(e) => handleLabResultChange('patient_sex', e.target.value)}
                disabled={disabled}
                className="cardiology-select">
                
                                    <option value="">Выберите</option>
                                    <option value="male">Мужской</option>
                                    <option value="female">Женский</option>
                                </select>
                            </div>
                            <div className="cardiology-select-field">
                                <label>Курение</label>
                                <select
                value={labResults?.smoking || ''}
                onChange={(e) => handleLabResultChange('smoking', e.target.value)}
                disabled={disabled}
                className="cardiology-select">
                
                                    <option value="">Выберите</option>
                                    <option value="no">Не курит</option>
                                    <option value="yes">Курит</option>
                                </select>
                            </div>
                            <EMRTextField
              label="Систолическое АД (мм рт.ст.)"
              value={labResults?.systolic_bp || ''}
              onChange={(e) => handleLabResultChange('systolic_bp', e.target.value)}
              disabled={disabled}
              type="number"
              placeholder="120-180" />
            
                            <EMRTextField
              label="Общий холестерин для SCORE2 (ммоль/л)"
              value={labResults?.cholesterol_total || ''}
              onChange={(e) => handleLabResultChange('cholesterol_total', e.target.value)}
              disabled={disabled}
              type="number"
              placeholder="4-8 (ммоль/л)" />
            
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
                return <p className="cardiology-risk-placeholder">Заполните все поля для расчета риска</p>;
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
                category = 'Низкий';
                categoryClass = 'low';
                recommendation = 'Продолжать здоровый образ жизни';
              } else if (risk < 10) {
                category = 'Умеренный';
                categoryClass = 'moderate';
                recommendation = 'Рекомендуется модификация факторов риска';
              } else if (risk < 20) {
                category = 'Высокий';
                categoryClass = 'high';
                recommendation = 'Показана медикаментозная терапия';
              } else {
                category = 'Очень высокий';
                categoryClass = 'very-high';
                recommendation = 'Требуется агрессивная терапия';
              }

              return (
                <div className="cardiology-risk-display">
                                        <div className={`cardiology-risk-score ${categoryClass}`}>
                                            <span className="risk-value">{risk.toFixed(1)}%</span>
                                            <span className="risk-label">10-летний риск</span>
                                        </div>
                                        <div className={`cardiology-risk-category ${categoryClass}`}>
                                            <span className="category-name">{category} риск</span>
                                            <span className="category-recommendation">{recommendation}</span>
                                        </div>
                                        <div className="cardiology-risk-legend">
                                            <div className="legend-item low">{'<5%'} Низкий</div>
                                            <div className="legend-item moderate">5-10% Умеренный</div>
                                            <div className="legend-item high">10-20% Высокий</div>
                                            <div className="legend-item very-high">{'>20%'} Очень высокий</div>
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
