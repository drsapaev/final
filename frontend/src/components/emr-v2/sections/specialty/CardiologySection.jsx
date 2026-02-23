/**
 * CardiologySection - Специализированная секция для кардиологии
 * 
 * Интегрирует:
 * - ECGViewer для просмотра и анализа ЭКГ
 * - Поля для ЭхоКГ результатов
 * - Кардиологические маркеры (тропонин, CRP, холестерин)
 * - Калькуляторы рисков
 */

import { useState, useCallback } from 'react';
import EMRSection from '../EMRSection';
import EMRTextField from '../EMRTextField';
import ECGViewer from '../../../cardiology/ECGViewer';
import EchoForm from '../../../cardiology/EchoForm';
import { useAppData } from '../../../../contexts/AppDataContext';
import './CardiologySection.css';

/**
 * CardiologySection Component
 * 
 * @param {Object} props
 * @param {Object} props.ecgData - ЭКГ данные из specialty_data
 * @param {Object} props.echoData - ЭхоКГ данные
 * @param {Object} props.labResults - Кардиологические анализы
 * @param {Function} props.onChange - Handler для изменения specialty_data
 * @param {boolean} props.disabled - Read-only mode
 * @param {number} props.visitId - Visit ID для ECGViewer
 * @param {number} props.patientId - Patient ID
 */
export function CardiologySection({
  ecgData = {},
  echoData = {},
  labResults = {},
  onChange,
  disabled = false,
  visitId,
  patientId
}) {void
  useAppData();
  const [activeTab, setActiveTab] = useState('ecg'); // 'ecg' | 'echo' | 'labs' | 'risk'

  // Handlers
  const handleECGDataUpdate = useCallback((updatedData) => {
    onChange?.('ecg', updatedData);
  }, [onChange]);

  const handleEchoDataUpdate = useCallback((updatedData) => {
    onChange?.('echo', updatedData);
  }, [onChange]);

  const handleLabResultChange = useCallback((field, value) => {
    onChange?.('cardio_labs', {
      ...labResults,
      [field]: value
    });
  }, [labResults, onChange]);

  return (
    <EMRSection
      title="Кардиологические данные"
      icon="🫀"
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

            {/* ECG Tab */}
            {activeTab === 'ecg' &&
      <div className="cardiology-tab-content">
                    <ECGViewer
          visitId={visitId}
          patientId={patientId}
          onDataUpdate={handleECGDataUpdate} />
        
                    {ecgData?.interpretation &&
        <div className="cardiology-interpretation">
                            <h4>Интерпретация ЭКГ:</h4>
                            <p>{ecgData.interpretation}</p>
                        </div>
        }
                </div>
      }

            {/* Echo Tab */}
            {activeTab === 'echo' &&
      <div className="cardiology-tab-content">
                    <EchoForm
          initialData={echoData}
          onSave={handleEchoDataUpdate}
          disabled={disabled} />
        
                </div>
      }

            {/* Lab Results Tab */}
            {activeTab === 'labs' &&
      <div className="cardiology-tab-content">
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
            label="Холестерин общий (ммоль/л)"
            value={labResults?.cholesterol_total || ''}
            onChange={(e) => handleLabResultChange('cholesterol_total', e.target.value)}
            disabled={disabled}
            type="number" />
          
                        <EMRTextField
            label="Холестерин ЛПВП (ммоль/л)"
            value={labResults?.cholesterol_hdl || ''}
            onChange={(e) => handleLabResultChange('cholesterol_hdl', e.target.value)}
            disabled={disabled}
            type="number" />
          
                        <EMRTextField
            label="Холестерин ЛПНП (ммоль/л)"
            value={labResults?.cholesterol_ldl || ''}
            onChange={(e) => handleLabResultChange('cholesterol_ldl', e.target.value)}
            disabled={disabled}
            type="number" />
          
                        <EMRTextField
            label="Триглицериды (ммоль/л)"
            value={labResults?.triglycerides || ''}
            onChange={(e) => handleLabResultChange('triglycerides', e.target.value)}
            disabled={disabled}
            type="number" />
          
                        <EMRTextField
            label="Глюкоза (ммоль/л)"
            value={labResults?.glucose || ''}
            onChange={(e) => handleLabResultChange('glucose', e.target.value)}
            disabled={disabled}
            type="number" />
          
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
              label="Общий холестерин (ммоль/л)"
              value={labResults?.cholesterol_total || ''}
              onChange={(e) => handleLabResultChange('cholesterol_total', e.target.value)}
              disabled={disabled}
              type="number"
              placeholder="4-8" />
            
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