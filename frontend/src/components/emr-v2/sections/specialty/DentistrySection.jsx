/**
 * DentistrySection - Специализированная секция для стоматологии
 * 
 * Интегрирует:
 * - Интерактивную зубную карту (TeethChart)
 * - Индексы гигиены (OHIS, PLI, CPI, Bleeding)
 * - Пародонтальные карманы
 * - Измерения прикуса
 * - Рентгенограммы
 */

import React, { useState, useCallback } from 'react';
import EMRSection from '../EMRSection';
import EMRTextField from '../EMRTextField';
import TeethChart from '../../../dental/TeethChart';
import './DentistrySection.css';

/**
 * DentistrySection Component
 * 
 * @param {Object} props
 * @param {Object} props.toothStatus - Статусы зубов из specialty_data
 * @param {Object} props.hygieneIndices - Индексы гигиены
 * @param {Object} props.periodontalPockets - Пародонтальные карманы
 * @param {Object} props.measurements - Измерения прикуса
 * @param {Object} props.radiographs - Рентгенограммы
 * @param {Function} props.onChange - Handler для изменения specialty_data
 * @param {boolean} props.disabled - Read-only mode
 */
export function DentistrySection({
    toothStatus = {},
    hygieneIndices = {},
    periodontalPockets = {},
    measurements = {},
    radiographs = {},
    onChange,
    disabled = false,
}) {
    const [activeTab, setActiveTab] = useState('chart'); // 'chart' | 'hygiene' | 'periodontal' | 'occlusion' | 'radiographs'

    // Handlers
    const handleToothChange = useCallback((toothNumber, toothData) => {
        onChange?.('tooth_status', {
            ...toothStatus,
            [toothNumber]: toothData
        });
    }, [toothStatus, onChange]);

    const handleHygieneIndexChange = useCallback((field, value) => {
        onChange?.('hygiene_indices', {
            ...hygieneIndices,
            [field]: value
        });
    }, [hygieneIndices, onChange]);

    const handleMeasurementChange = useCallback((field, value) => {
        onChange?.('measurements', {
            ...measurements,
            [field]: value
        });
    }, [measurements, onChange]);

    const handleRadiographChange = useCallback((field, value) => {
        onChange?.('radiographs', {
            ...radiographs,
            [field]: value
        });
    }, [radiographs, onChange]);

    return (
        <EMRSection
            title="Стоматологические данные"
            icon="🦷"
            disabled={disabled}
            defaultOpen={true}
        >
            {/* Tabs */}
            <div className="dentistry-tabs">
                <button
                    className={`dentistry-tab ${activeTab === 'chart' ? 'active' : ''}`}
                    onClick={() => setActiveTab('chart')}
                    disabled={disabled}
                >
                    Зубная карта
                </button>
                <button
                    className={`dentistry-tab ${activeTab === 'hygiene' ? 'active' : ''}`}
                    onClick={() => setActiveTab('hygiene')}
                    disabled={disabled}
                >
                    Гигиена
                </button>
                <button
                    className={`dentistry-tab ${activeTab === 'periodontal' ? 'active' : ''}`}
                    onClick={() => setActiveTab('periodontal')}
                    disabled={disabled}
                >
                    Пародонт
                </button>
                <button
                    className={`dentistry-tab ${activeTab === 'occlusion' ? 'active' : ''}`}
                    onClick={() => setActiveTab('occlusion')}
                    disabled={disabled}
                >
                    Прикус
                </button>
                <button
                    className={`dentistry-tab ${activeTab === 'radiographs' ? 'active' : ''}`}
                    onClick={() => setActiveTab('radiographs')}
                    disabled={disabled}
                >
                    Рентген
                </button>
            </div>

            {/* Tooth Chart Tab */}
            {activeTab === 'chart' && (
                <div className="dentistry-tab-content">
                    <TeethChart
                        initialData={toothStatus}
                        onToothClick={handleToothChange}
                        readOnly={disabled}
                    />
                </div>
            )}

            {/* Hygiene Indices Tab */}
            {activeTab === 'hygiene' && (
                <div className="dentistry-tab-content">
                    <div className="dentistry-indices-grid">
                        <EMRTextField
                            label="OHIS (Oral Hygiene Index Simplified)"
                            value={hygieneIndices?.ohis || ''}
                            onChange={(e) => handleHygieneIndexChange('ohis', e.target.value)}
                            disabled={disabled}
                            type="number"
                            placeholder="0.0 - 6.0"
                        />
                        <EMRTextField
                            label="PLI (Plaque Index)"
                            value={hygieneIndices?.pli || ''}
                            onChange={(e) => handleHygieneIndexChange('pli', e.target.value)}
                            disabled={disabled}
                            type="number"
                            placeholder="0.0 - 3.0"
                        />
                        <EMRTextField
                            label="CPI (Community Periodontal Index)"
                            value={hygieneIndices?.cpi || ''}
                            onChange={(e) => handleHygieneIndexChange('cpi', e.target.value)}
                            disabled={disabled}
                            type="number"
                            placeholder="0 - 4"
                        />
                        <EMRTextField
                            label="Bleeding Index (%)"
                            value={hygieneIndices?.bleeding || ''}
                            onChange={(e) => handleHygieneIndexChange('bleeding', e.target.value)}
                            disabled={disabled}
                            type="number"
                            placeholder="0 - 100"
                        />
                    </div>
                </div>
            )}

            {/* Periodontal Pockets Tab */}
            {activeTab === 'periodontal' && (
                <div className="dentistry-tab-content">
                    <div className="dentistry-periodontal-info">
                        <p>Пародонтальные карманы измеряются в мм для каждого зуба</p>
                        <p className="dentistry-note">
                            Глубина: 0-3мм — норма, 4-5мм — умеренный, 6+мм — тяжелый
                        </p>
                    </div>

                    {/* Upper Jaw */}
                    <div className="periodontal-jaw-section">
                        <h5 className="periodontal-jaw-title">Верхняя челюсть</h5>
                        <div className="periodontal-teeth-grid upper">
                            {[18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28].map(toothNum => {
                                const depth = periodontalPockets?.[toothNum] || 0;
                                const severityClass = depth >= 6 ? 'severe' : depth >= 4 ? 'moderate' : 'normal';
                                return (
                                    <div key={toothNum} className={`periodontal-tooth ${severityClass}`}>
                                        <span className="tooth-number">{toothNum}</span>
                                        <input
                                            type="number"
                                            min="0"
                                            max="15"
                                            value={depth}
                                            onChange={(e) => onChange?.('periodontal_pockets', {
                                                ...periodontalPockets,
                                                [toothNum]: parseFloat(e.target.value) || 0
                                            })}
                                            disabled={disabled}
                                            className="pocket-depth-input"
                                        />
                                        <span className="depth-unit">мм</span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Lower Jaw */}
                    <div className="periodontal-jaw-section">
                        <h5 className="periodontal-jaw-title">Нижняя челюсть</h5>
                        <div className="periodontal-teeth-grid lower">
                            {[48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38].map(toothNum => {
                                const depth = periodontalPockets?.[toothNum] || 0;
                                const severityClass = depth >= 6 ? 'severe' : depth >= 4 ? 'moderate' : 'normal';
                                return (
                                    <div key={toothNum} className={`periodontal-tooth ${severityClass}`}>
                                        <span className="tooth-number">{toothNum}</span>
                                        <input
                                            type="number"
                                            min="0"
                                            max="15"
                                            value={depth}
                                            onChange={(e) => onChange?.('periodontal_pockets', {
                                                ...periodontalPockets,
                                                [toothNum]: parseFloat(e.target.value) || 0
                                            })}
                                            disabled={disabled}
                                            className="pocket-depth-input"
                                        />
                                        <span className="depth-unit">мм</span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    {/* Summary Stats */}
                    <div className="periodontal-summary">
                        {(() => {
                            const pockets = Object.values(periodontalPockets || {}).filter(v => v > 0);
                            if (pockets.length === 0) return null;

                            const avg = (pockets.reduce((a, b) => a + b, 0) / pockets.length).toFixed(1);
                            const max = Math.max(...pockets);
                            const severe = pockets.filter(p => p >= 6).length;
                            const moderate = pockets.filter(p => p >= 4 && p < 6).length;

                            return (
                                <div className="periodontal-stats">
                                    <div className="stat-item">
                                        <span className="stat-value">{avg}</span>
                                        <span className="stat-label">Средняя глубина (мм)</span>
                                    </div>
                                    <div className="stat-item">
                                        <span className="stat-value">{max}</span>
                                        <span className="stat-label">Макс. глубина (мм)</span>
                                    </div>
                                    <div className="stat-item severe">
                                        <span className="stat-value">{severe}</span>
                                        <span className="stat-label">Тяжёлых (≥6мм)</span>
                                    </div>
                                    <div className="stat-item moderate">
                                        <span className="stat-value">{moderate}</span>
                                        <span className="stat-label">Умеренных (4-5мм)</span>
                                    </div>
                                </div>
                            );
                        })()}
                    </div>
                </div>
            )}

            {/* Occlusion Measurements Tab */}
            {activeTab === 'occlusion' && (
                <div className="dentistry-tab-content">
                    <div className="dentistry-measurements-grid">
                        <EMRTextField
                            label="Overjet (мм)"
                            value={measurements?.overjet || ''}
                            onChange={(e) => handleMeasurementChange('overjet', e.target.value)}
                            disabled={disabled}
                            type="number"
                            placeholder="Горизонтальное перекрытие"
                        />
                        <EMRTextField
                            label="Overbite (мм)"
                            value={measurements?.overbite || ''}
                            onChange={(e) => handleMeasurementChange('overbite', e.target.value)}
                            disabled={disabled}
                            type="number"
                            placeholder="Вертикальное перекрытие"
                        />
                        <EMRTextField
                            label="Midline deviation (мм)"
                            value={measurements?.midline || ''}
                            onChange={(e) => handleMeasurementChange('midline', e.target.value)}
                            disabled={disabled}
                            type="number"
                            placeholder="Отклонение срединной линии"
                        />
                        <div className="dentistry-checkbox-group">
                            <label className="dentistry-checkbox">
                                <input
                                    type="checkbox"
                                    checked={measurements?.crossbite || false}
                                    onChange={(e) => handleMeasurementChange('crossbite', e.target.checked)}
                                    disabled={disabled}
                                />
                                <span>Перекрестный прикус</span>
                            </label>
                            <label className="dentistry-checkbox">
                                <input
                                    type="checkbox"
                                    checked={measurements?.openBite || false}
                                    onChange={(e) => handleMeasurementChange('openBite', e.target.checked)}
                                    disabled={disabled}
                                />
                                <span>Открытый прикус</span>
                            </label>
                        </div>
                    </div>
                </div>
            )}

            {/* Radiographs Tab */}
            {activeTab === 'radiographs' && (
                <div className="dentistry-tab-content">
                    <div className="dentistry-radiographs-grid">
                        <EMRTextField
                            label="Панорамный снимок"
                            value={radiographs?.panoramic || ''}
                            onChange={(e) => handleRadiographChange('panoramic', e.target.value)}
                            disabled={disabled}
                            placeholder="URL или путь к файлу"
                        />
                        <EMRTextField
                            label="КЛКТ"
                            value={radiographs?.cbct || ''}
                            onChange={(e) => handleRadiographChange('cbct', e.target.value)}
                            disabled={disabled}
                            placeholder="URL или путь к файлу"
                        />
                        <div className="dentistry-radiographs-note">
                            <p>Прицельные и прикусные снимки добавляются через зубную карту</p>
                        </div>
                    </div>
                </div>
            )}
        </EMRSection>
    );
}

export default DentistrySection;
