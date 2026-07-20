
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

import PropTypes from 'prop-types';
import { useState, useCallback } from 'react';
import EMRSection from '../EMRSection';
import React from 'react';
import EMRTextField from '../EMRTextField';
import TeethChart from '../../../dental/TeethChart';
import './DentistrySection.css';
import { Input, Checkbox } from '../../../ui/macos';
import { useTranslation } from '../../../../i18n/useTranslation';

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
    toothStatus: toothStatusRaw = {},
    hygieneIndices: hygieneIndicesRaw = {},
    periodontalPockets: periodontalPocketsRaw = {},
    measurements: measurementsRaw = {},
    radiographs: radiographsRaw = {},
    onChange,
    disabled = false,
}) {
  const { t: rawT } = useTranslation(); const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
    const hygieneIndices = hygieneIndicesRaw as Record<string, any>;
  const toothStatus = toothStatusRaw as Record<string, any>;
  const periodontalPockets = periodontalPocketsRaw as Record<string, any>;
  const measurements = measurementsRaw as Record<string, any>;
  const radiographs = radiographsRaw as Record<string, any>;
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
            title={t('misc.ds_stomatologicheskie_dannye')}
            icon="smile"
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
                            onChange={(e) => handleHygieneIndexChange('ohis', e as unknown as string)}
                            disabled={disabled}
                            type="number"
                            placeholder="0.0 - 6.0"
                        />
                        <EMRTextField
                            label="PLI (Plaque Index)"
                            value={hygieneIndices?.pli || ''}
                            onChange={(e) => handleHygieneIndexChange('pli', e as unknown as string)}
                            disabled={disabled}
                            type="number"
                            placeholder="0.0 - 3.0"
                        />
                        <EMRTextField
                            label="CPI (Community Periodontal Index)"
                            value={hygieneIndices?.cpi || ''}
                            onChange={(e) => handleHygieneIndexChange('cpi', e as unknown as string)}
                            disabled={disabled}
                            type="number"
                            placeholder="0 - 4"
                        />
                        <EMRTextField
                            label="Bleeding Index (%)"
                            value={hygieneIndices?.bleeding || ''}
                            onChange={(e) => handleHygieneIndexChange('bleeding', e as unknown as string)}
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
                        <p>{t('misc.ds_parodontalnye_karmany_izmery')}</p>
                        <p className="dentistry-note">
                            Глубина: 0-3мм — норма, 4-5мм — умеренный, 6+мм — тяжелый
                        </p>
                    </div>

                    {/* Upper Jaw */}
                    <div className="periodontal-jaw-section">
                        <h5 className="periodontal-jaw-title">{t('misc.ds_verhnyaya_chelyust')}</h5>
                        <div className="periodontal-teeth-grid upper">
                            {[18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28].map(toothNum => {
                                const depth = periodontalPockets?.[toothNum] || 0;
                                const severityClass = depth >= 6 ? 'severe' : depth >= 4 ? 'moderate' : 'normal';
                                return (
                                    <div key={toothNum} className={`periodontal-tooth ${severityClass}`}>
                                        <span className="tooth-number">{toothNum}</span>
                                        <Input
                                            type="number"
                                            aria-label={`Periodontal pocket depth for tooth ${toothNum}`}
                                            min="0"
                                            max="15"
                                            value={depth}
                                            onChange={(e) => onChange?.('periodontal_pockets', {
                                                ...periodontalPockets,
                                                [toothNum]: parseFloat(e as unknown as string) || 0
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
                        <h5 className="periodontal-jaw-title">{t('misc.ds_nizhnyaya_chelyust')}</h5>
                        <div className="periodontal-teeth-grid lower">
                            {[48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38].map(toothNum => {
                                const depth = periodontalPockets?.[toothNum] || 0;
                                const severityClass = depth >= 6 ? 'severe' : depth >= 4 ? 'moderate' : 'normal';
                                return (
                                    <div key={toothNum} className={`periodontal-tooth ${severityClass}`}>
                                        <span className="tooth-number">{toothNum}</span>
                                        <Input
                                            type="number"
                                            aria-label={`Periodontal pocket depth for tooth ${toothNum}`}
                                            min="0"
                                            max="15"
                                            value={depth}
                                            onChange={(e) => onChange?.('periodontal_pockets', {
                                                ...periodontalPockets,
                                                [toothNum]: parseFloat(e as unknown as string) || 0
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
                            const pockets = Object.values((periodontalPockets || {}) as Record<string, number>).filter(v => v > 0);
                            if (pockets.length === 0) return null;

                            const avg = (pockets.reduce((a, b) => a + b, 0) / pockets.length).toFixed(1);
                            const max = Math.max(...pockets);
                            const severe = pockets.filter(p => p >= 6).length;
                            const moderate = pockets.filter(p => p >= 4 && p < 6).length;

                            return (
                                <div className="periodontal-stats">
                                    <div className="stat-item">
                                        <span className="stat-value">{avg}</span>
                                        <span className="stat-label">{t('misc.ds_srednyaya_glubina_mm')}</span>
                                    </div>
                                    <div className="stat-item">
                                        <span className="stat-value">{max}</span>
                                        <span className="stat-label">{t('misc.ds_maks_glubina_mm')}</span>
                                    </div>
                                    <div className="stat-item severe">
                                        <span className="stat-value">{severe}</span>
                                        <span className="stat-label">{t('misc.ds_tyazhyolyh_6mm')}</span>
                                    </div>
                                    <div className="stat-item moderate">
                                        <span className="stat-value">{moderate}</span>
                                        <span className="stat-label">{t('misc.ds_umerennyh_4_5mm')}</span>
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
                            label={t('misc.ds_overjet_mm')}
                            value={measurements?.overjet || ''}
                            onChange={(e) => handleMeasurementChange('overjet', e as unknown as string)}
                            disabled={disabled}
                            type="number"
                            placeholder={t('misc.ds_gorizontalnoe_perekrytie')}
                        />
                        <EMRTextField
                            label={t('misc.ds_overbite_mm')}
                            value={measurements?.overbite || ''}
                            onChange={(e) => handleMeasurementChange('overbite', e as unknown as string)}
                            disabled={disabled}
                            type="number"
                            placeholder={t('misc.ds_vertikalnoe_perekrytie')}
                        />
                        <EMRTextField
                            label={t('misc.ds_midline_deviation_mm')}
                            value={measurements?.midline || ''}
                            onChange={(e) => handleMeasurementChange('midline', e as unknown as string)}
                            disabled={disabled}
                            type="number"
                            placeholder={t('misc.ds_otklonenie_sredinnoy_linii')}
                        />
                        <div className="dentistry-checkbox-group">
                            <label className="dentistry-checkbox">
                                <Checkbox aria-label="Crossbite measurement" checked={measurements?.crossbite || false} onChange={(e) => handleMeasurementChange('crossbite', e)}
                                    disabled={disabled}
                                />
                                <span>{t('misc.ds_perekrestnyy_prikus')}</span>
                            </label>
                            <label className="dentistry-checkbox">
                                <Checkbox aria-label="Open bite measurement" checked={measurements?.openBite || false} onChange={(e) => handleMeasurementChange('openBite', e)}
                                    disabled={disabled}
                                />
                                <span>{t('misc.ds_otkrytyy_prikus')}</span>
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
                            label={t('misc.ds_panoramnyy_snimok')}
                            value={radiographs?.panoramic || ''}
                            onChange={(e) => handleRadiographChange('panoramic', e as unknown as string)}
                            disabled={disabled}
                            placeholder={t('misc.ds_url_ili_put_k_faylu')}
                        />
                        <EMRTextField
                            label={t('misc.ds_klkt')}
                            value={radiographs?.cbct || ''}
                            onChange={(e) => handleRadiographChange('cbct', e as unknown as string)}
                            disabled={disabled}
                            placeholder={t('misc.ds_url_ili_put_k_faylu')}
                        />
                        <div className="dentistry-radiographs-note">
                            <p>{t('misc.ds_pritselnye_i_prikusnye_snimk')}</p>
                        </div>
                    </div>
                </div>
            )}
        </EMRSection>
    );
}

export default DentistrySection;

DentistrySection.propTypes = {
    toothStatus: PropTypes.object,
    hygieneIndices: PropTypes.object,
    periodontalPockets: PropTypes.object,
    measurements: PropTypes.object,
    radiographs: PropTypes.object,
    onChange: PropTypes.func,
    disabled: PropTypes.bool,
};
